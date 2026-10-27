"""Domain operations. Every confirmation is one SQLite transaction."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import PurePath
from uuid import uuid4
from zoneinfo import ZoneInfo
import hashlib
import json
import secrets
import sqlite3
import warnings

from PIL import Image, UnidentifiedImageError

from .ai import ManualAssistant
from .errors import DomainError, require
from .schemas import format_decimal
from .security import PASSWORDS, DUMMY_HASH, digest, new_session, require_registered


def uid():
    return str(uuid4())


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


class LifeWorld:
    def __init__(self, db, policy, clock=None, assistant=None):
        self.db = db
        self.policy = policy
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.assistant = assistant or ManualAssistant()

    def now(self):
        return self.clock().astimezone(timezone.utc)

    def session(self, token, csrf=None, write=False):
        require(bool(token), 401, 'session_required', '請先開始訪客旅程或登入。')
        with self.db.connect() as c:
            session = c.execute('SELECT * FROM sessions WHERE token_hash=?', (digest(token),)).fetchone()
            require(session is not None and datetime.fromisoformat(session['expires_at']) > self.now(),
                    401, 'session_expired', '登入狀態已失效，請重新登入。')
            if write:
                require(bool(csrf) and secrets.compare_digest(csrf, session['csrf_token']),
                        403, 'csrf_failed', '安全驗證已失效，請重新整理後再試。')
            user = dict(c.execute('SELECT * FROM users WHERE id=?', (session['owner_id'],)).fetchone())
            return user, session['csrf_token']

    @staticmethod
    def public_user(user, csrf=None):
        result = {k: user[k] for k in ('status', 'username', 'name', 'bio', 'timezone')}
        result.update(owner_id=user['id'], lumi_hatched=bool(user['hatched_at']))
        if csrf:
            result['csrf_token'] = csrf
        return result

    def guest(self, token):
        if token:
            try:
                user, csrf = self.session(token)
                return self.public_user(user, csrf), None, False
            except DomainError as exc:
                if exc.status != 401:
                    raise
        with self.db.connect(write=True) as c:
            owner = uid()
            c.execute("INSERT INTO users (id,status,created_at) VALUES (?,'guest',?)", (owner, self.now().isoformat()))
            token, csrf = new_session(c, owner, self.now(), self.policy)
            user = c.execute('SELECT * FROM users WHERE id=?', (owner,)).fetchone()
            return self.public_user(user, csrf), token, True

    def profile(self, owner, data):
        with self.db.connect(write=True) as c:
            c.execute('UPDATE users SET name=?,bio=?,timezone=? WHERE id=?', (data.name, data.bio, data.timezone, owner))
            return self.public_user(c.execute('SELECT * FROM users WHERE id=?', (owner,)).fetchone())

    def claim(self, user, data):
        require(user['status'] == 'guest', 409, 'already_registered', '目前已是本機帳號。')
        password_hash = PASSWORDS.hash(data.password)
        with self.db.connect(write=True) as c:
            current = self._owned_user(c, user['id'])
            require(current['status'] == 'guest', 409, 'already_registered', '帳號狀態已變更，請重新整理。')
            require(not c.execute('SELECT 1 FROM users WHERE username=?', (data.username,)).fetchone(),
                    409, 'username_taken', '此帳號名稱已使用；請改名，或登入既有帳號。')
            c.execute("UPDATE users SET status='registered',username=?,password_hash=? WHERE id=?",
                      (data.username, password_hash, user['id']))
            c.execute('DELETE FROM sessions WHERE owner_id=?', (user['id'],))
            token, csrf = new_session(c, user['id'], self.now(), self.policy)
            return self.public_user(self._owned_user(c, user['id']), csrf), token

    def login(self, data, existing_token=None):
        with self.db.connect(write=True) as c:
            user = c.execute('SELECT * FROM users WHERE username=?', (data.username.lower(),)).fetchone()
            valid = PASSWORDS.verify(data.password, user['password_hash'] if user else DUMMY_HASH)
            require(user is not None and valid, 401, 'invalid_credentials', '帳號或密碼不正確。')
            if existing_token:
                old = c.execute('SELECT s.*,u.status FROM sessions s JOIN users u ON u.id=s.owner_id WHERE token_hash=?',
                                (digest(existing_token),)).fetchone()
                if old and datetime.fromisoformat(old['expires_at']) > self.now() and old['owner_id'] != user['id'] and old['status'] == 'guest':
                    require(data.discard_guest, 409, 'guest_conflict',
                            '此裝置有訪客世界。登入不會合併資料；若離開訪客身分，可能無法再次取回。')
                c.execute('DELETE FROM sessions WHERE token_hash=?', (digest(existing_token),))
            token, csrf = new_session(c, user['id'], self.now(), self.policy)
            return self.public_user(user, csrf), token

    def logout(self, token):
        with self.db.connect(write=True) as c:
            c.execute('DELETE FROM sessions WHERE token_hash=?', (digest(token),))

    @staticmethod
    def _owned_user(c, owner):
        user = c.execute('SELECT * FROM users WHERE id=?', (owner,)).fetchone()
        require(user is not None, 401, 'session_required', '使用者不存在。')
        return user

    def _onboarded(self, c, owner):
        user = self._owned_user(c, owner)
        require(bool(user['hatched_at']), 409, 'first_goal_required', '請先填寫 Bio 並建立第一個目標蛋。')
        return user

    @staticmethod
    def _owned(c, table, item_id, owner):
        assert table in {'goals', 'people', 'drafts', 'evidence', 'notes', 'tasks'}
        row = c.execute('SELECT * FROM ' + table + ' WHERE id=? AND owner_id=?', (item_id, owner)).fetchone()
        require(row is not None, 404, 'not_found', '找不到可存取的資料。')
        return row

    @staticmethod
    def _cached(c, owner, operation, request_id, payload):
        fingerprint = hashlib.sha256(encoded(payload).encode()).hexdigest()
        row = c.execute('SELECT * FROM requests WHERE owner_id=? AND operation=? AND request_id=?',
                        (owner, operation, request_id)).fetchone()
        if row:
            require(row['fingerprint'] == fingerprint, 409, 'idempotency_conflict', '同一提交代碼不能用於不同內容。')
            return json.loads(row['response']), fingerprint
        return None, fingerprint

    @staticmethod
    def _remember(c, owner, operation, request_id, fingerprint, response):
        c.execute('INSERT INTO requests VALUES (?,?,?,?,?)', (owner, operation, request_id, fingerprint, encoded(response)))

    def create_goal(self, owner, data):
        with self.db.connect(write=True) as c:
            user = self._owned_user(c, owner)
            require(bool(user['bio'] and user['name']), 409, 'bio_required', '請先完成 Bio。')
            cached, fingerprint = self._cached(c, owner, 'goal:create', data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            goal_id, now = uid(), self.now().isoformat()
            c.execute("INSERT INTO goals (id,owner_id,title,outcome,status,created_at) VALUES (?,?,?,?,'active',?)",
                      (goal_id, owner, data.title, data.outcome, now))
            for position, action in enumerate(data.actions):
                c.execute('INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?)',
                          (uid(), goal_id, owner, action.title, action.unit, action.target, action.level, encoded(action.weekdays), position))
            c.execute('UPDATE users SET hatched_at=COALESCE(hatched_at,?) WHERE id=?', (now, owner))
            result = self._goal(c, goal_id, owner)
            self._remember(c, owner, 'goal:create', data.request_id, fingerprint, result)
            return result

    def _goal(self, c, goal_id, owner):
        goal = dict(self._owned(c, 'goals', goal_id, owner))
        actions = []
        for row in c.execute('SELECT * FROM actions WHERE goal_id=? AND owner_id=? ORDER BY position', (goal_id, owner)):
            action = dict(row)
            action['weekdays'] = json.loads(action['weekdays'])
            quantities = c.execute('SELECT quantity FROM contributions WHERE action_id=? AND owner_id=?', (action['id'], owner)).fetchall()
            action['progress'] = format_decimal(sum((Decimal(v['quantity']) for v in quantities), Decimal(0)))
            actions.append(action)
        goal['actions'] = actions
        goal['evidence'] = [dict(r) for r in c.execute('SELECT id,filename,mime,size,created_at FROM evidence WHERE goal_id=? AND owner_id=? ORDER BY created_at,id', (goal_id, owner))]
        return goal

    def goal(self, owner, goal_id):
        with self.db.connect() as c:
            self._onboarded(c, owner)
            return self._goal(c, goal_id, owner)

    def calendar(self, owner, goal_id):
        with self.db.connect() as c:
            user = self._onboarded(c, owner)
            goal = self._goal(c, goal_id, owner)
            start = self.now().astimezone(ZoneInfo(user['timezone'])).date()
            return [{'date': (start + timedelta(days=i)).isoformat(),
                     'action_ids': [a['id'] for a in goal['actions'] if (start + timedelta(days=i)).weekday() in a['weekdays']]}
                    for i in range(28)]

    def _related(self, c, user, goal_id, person_id, contributions):
        if goal_id:
            self._owned(c, 'goals', goal_id, user['id'])
        if person_id:
            require_registered(user)
            self._owned(c, 'people', person_id, user['id'])
        for contribution in contributions:
            action = c.execute('SELECT * FROM actions WHERE id=? AND owner_id=?', (contribution.action_id, user['id'])).fetchone()
            require(action is not None and action['goal_id'] == goal_id, 422, 'invalid_action', '貢獻行動必須屬於本次選擇的目標。')

    def _valid_time(self, occurred_at):
        require(occurred_at.astimezone(timezone.utc) <= self.now(), 422, 'future_event', '真實經歷的發生時間不能在未來。')

    def create_draft(self, owner, data):
        self._valid_time(data.occurred_at)
        with self.db.connect(write=True) as c:
            user = self._onboarded(c, owner)
            self._related(c, user, data.goal_id, data.person_id, data.contributions)
            draft_id, now = uid(), self.now().isoformat()
            c.execute("INSERT INTO drafts VALUES (?,?,?,?,?,?,?,'draft',1,?,?)",
                      (draft_id, owner, data.goal_id, data.person_id, data.raw_text,
                       data.occurred_at.astimezone(timezone.utc).isoformat(), encoded([v.model_dump() for v in data.contributions]), now, now))
            return self._draft(c, owner, draft_id)

    def _draft(self, c, owner, draft_id):
        result = dict(self._owned(c, 'drafts', draft_id, owner))
        result['contributions'] = json.loads(result['contributions'])
        return result

    def draft(self, owner, draft_id):
        with self.db.connect() as c:
            self._onboarded(c, owner)
            return self._draft(c, owner, draft_id)

    def edit_draft(self, owner, draft_id, data):
        self._valid_time(data.occurred_at)
        with self.db.connect(write=True) as c:
            user = self._onboarded(c, owner)
            draft = self._draft(c, owner, draft_id)
            require(draft['status'] == 'draft', 409, 'already_confirmed', '已確認的原始紀錄不可用草稿方式修改。')
            require(draft['revision'] == data.expected_revision, 409, 'revision_conflict', '草稿已有新版，請重新載入。')
            self._related(c, user, data.goal_id, data.person_id, data.contributions)
            c.execute('UPDATE drafts SET raw_text=?,occurred_at=?,goal_id=?,person_id=?,contributions=?,revision=revision+1,updated_at=? WHERE id=? AND owner_id=?',
                      (data.raw_text, data.occurred_at.astimezone(timezone.utc).isoformat(), data.goal_id, data.person_id,
                       encoded([v.model_dump() for v in data.contributions]), self.now().isoformat(), draft_id, owner))
            return self._draft(c, owner, draft_id)

    def suggest(self, owner, draft_id):
        draft = self.draft(owner, draft_id)
        require(draft['status'] == 'draft', 409, 'already_confirmed', '這份草稿已經確認。')
        try:
            return self.assistant.suggest(draft['raw_text'])
        except Exception:
            raise DomainError(503, 'assistant_unavailable', '整理服務暫時不可用；原文已保存，可手動完成。')

    def _award(self, c, owner, experience_id, now):
        event_id = uid()
        c.execute('INSERT INTO reward_ledger VALUES (?,?,?,?,?,?)',
                  (event_id, owner, experience_id, self.policy.points_per_experience, self.policy.rule_version, now))
        return event_id

    def confirm(self, owner, draft_id, data):
        with self.db.connect(write=True) as c:
            user = self._onboarded(c, owner)
            draft = self._draft(c, owner, draft_id)
            payload = dict(data.model_dump(mode='json'), draft_id=draft_id)
            cached, fingerprint = self._cached(c, owner, 'confirm', data.request_id, payload)
            if cached:
                return cached
            require(draft['status'] == 'draft', 409, 'already_confirmed', '這份草稿已確認，不能重複計入。')
            require(draft['revision'] == data.expected_revision, 409, 'revision_conflict', '草稿已有新版，請重新核對。')
            self._related(c, user, draft['goal_id'], data.person_id, data.contributions)
            if data.contributions and draft['goal_id']:
                goal = self._owned(c, 'goals', draft['goal_id'], owner)
                require(goal['status'] == 'active', 409, 'policy_required', '完成後的貢獻更正規則尚未定案；草稿已保留，可移除貢獻後只保存經歷。')
            experience_id, now = uid(), self.now().isoformat()
            c.execute('INSERT INTO experiences VALUES (?,?,?,?,?,?,?,?,?)',
                      (experience_id, owner, draft_id, draft['goal_id'], data.person_id,
                       draft['raw_text'], data.summary, draft['occurred_at'], now))
            for item in data.contributions:
                c.execute('INSERT INTO contributions VALUES (?,?,?,?,?)', (uid(), owner, experience_id, item.action_id, item.quantity))
            for title in data.tasks:
                c.execute('INSERT INTO tasks (id,owner_id,experience_id,title) VALUES (?,?,?,?)', (uid(), owner, experience_id, title))
            reward_id = self._award(c, owner, experience_id, now)
            c.execute("UPDATE drafts SET status='confirmed',updated_at=? WHERE id=? AND owner_id=?", (now, draft_id, owner))
            result = {'experience_id': experience_id, 'reward_event_id': reward_id, 'points_awarded': self.policy.points_per_experience,
                      'rule_version': self.policy.rule_version, 'confirmed_at': now}
            self._remember(c, owner, 'confirm', data.request_id, fingerprint, result)
            return result

    def create_person(self, owner, data):
        with self.db.connect(write=True) as c:
            user = self._onboarded(c, owner)
            require_registered(user)
            person_id = uid()
            c.execute('INSERT INTO people VALUES (?,?,?,?,?,?)', (person_id, owner, data.name, data.role, data.notes, self.now().isoformat()))
            return dict(self._owned(c, 'people', person_id, owner))

    def upload(self, owner, goal_id, filename, mime, content):
        # Authorize before parsing the content, and recheck within the write transaction.
        self.goal(owner, goal_id)
        require(bool(filename) and '\\' not in filename and PurePath(filename).name == filename and len(filename) <= 200,
                422, 'invalid_filename', '請使用不含路徑的圖片檔名。')
        require(bool(content), 422, 'empty_upload', '圖片不可為空。')
        require(len(content) <= self.policy.max_upload_bytes, 413, 'upload_too_large', '圖片超過開發設定的上限。')
        accepted = {'image/png': 'PNG', 'image/jpeg': 'JPEG'}
        require(mime in accepted, 415, 'unsupported_media', '目前支援 PNG 與 JPEG 圖片。')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as image:
                    if image.format != accepted[mime] or image.width * image.height > 16000000:
                        raise ValueError('Image format or dimensions rejected')
                    image.verify()
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise DomainError(415, 'invalid_image', '圖片格式不符或檔案已損毀。')
        checksum = hashlib.sha256(content).hexdigest()
        with self.db.connect(write=True) as c:
            goal = self._owned(c, 'goals', goal_id, owner)
            require(goal['status'] == 'active', 409, 'goal_completed', '完成後新增佐證的規則尚未開放。')
            old = c.execute('SELECT id,filename,mime,size,created_at FROM evidence WHERE owner_id=? AND goal_id=? AND digest=?',
                            (owner, goal_id, checksum)).fetchone()
            if old:
                return dict(old)
            evidence_id, now = uid(), self.now().isoformat()
            c.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?)',
                      (evidence_id, owner, goal_id, filename, mime, checksum, content, len(content), now))
            return {'id': evidence_id, 'filename': filename, 'mime': mime, 'size': len(content), 'created_at': now}

    def evidence(self, owner, evidence_id):
        with self.db.connect() as c:
            self._onboarded(c, owner)
            return dict(self._owned(c, 'evidence', evidence_id, owner))

    def complete(self, owner, goal_id, data):
        with self.db.connect(write=True) as c:
            self._onboarded(c, owner)
            goal = self._owned(c, 'goals', goal_id, owner)
            payload = dict(data.model_dump(mode='json'), goal_id=goal_id)
            cached, fingerprint = self._cached(c, owner, 'goal:complete', data.request_id, payload)
            if cached:
                return cached
            require(goal['status'] == 'active', 409, 'already_completed', '這個目標已完成。')
            for evidence_id in data.evidence_ids:
                evidence = self._owned(c, 'evidence', evidence_id, owner)
                require(evidence['goal_id'] == goal_id, 404, 'not_found', '找不到此目標的佐證。')
            completion_id, now = uid(), self.now().isoformat()
            c.execute('INSERT INTO completions VALUES (?,?,?,?,?,?)',
                      (completion_id, owner, goal_id, encoded(data.evidence_ids), data.reflection, now))
            c.execute("UPDATE goals SET status='completed',completed_at=?,reflection=? WHERE id=? AND owner_id=?", (now, data.reflection, goal_id, owner))
            result = {'completion_id': completion_id, 'goal_id': goal_id, 'status': 'completed', 'evidence_ids': data.evidence_ids, 'confirmed_at': now}
            self._remember(c, owner, 'goal:complete', data.request_id, fingerprint, result)
            return result

    def create_note(self, owner, data):
        with self.db.connect(write=True) as c:
            user = self._onboarded(c, owner)
            if data.person_id:
                require_registered(user)
                self._owned(c, 'people', data.person_id, owner)
            note_id, now = uid(), self.now().isoformat()
            c.execute('INSERT INTO notes VALUES (?,?,?,?,?,?,?)', (note_id, owner, data.person_id, data.kind, data.title, data.content, now))
            return dict(self._owned(c, 'notes', note_id, owner))

    def edit_task(self, owner, task_id, data):
        with self.db.connect(write=True) as c:
            self._onboarded(c, owner)
            self._owned(c, 'tasks', task_id, owner)
            c.execute('UPDATE tasks SET done=? WHERE id=? AND owner_id=?', (int(data.done), task_id, owner))
            return dict(self._owned(c, 'tasks', task_id, owner))

    def state(self, owner):
        with self.db.connect() as c:
            user = self._onboarded(c, owner)
            goals = [self._goal(c, r['id'], owner) for r in c.execute('SELECT id FROM goals WHERE owner_id=? ORDER BY created_at,id', (owner,)).fetchall()]
            people = []
            for row in c.execute('SELECT * FROM people WHERE owner_id=? ORDER BY created_at,id', (owner,)):
                person = dict(row)
                person['interaction_count'] = c.execute('SELECT COUNT(*) FROM experiences WHERE owner_id=? AND person_id=?', (owner, row['id'])).fetchone()[0]
                people.append(person)
            rewards = [dict(r) for r in c.execute('SELECT * FROM reward_ledger WHERE owner_id=? ORDER BY created_at,id', (owner,))]
            return {'user': self.public_user(user), 'lumi': {'hatched': True, 'hatched_at': user['hatched_at'], 'care_state': 'neutral'},
                    'goals': goals, 'people': people,
                    'drafts': [self._draft(c, owner, r['id']) for r in c.execute("SELECT id FROM drafts WHERE owner_id=? AND status='draft' ORDER BY updated_at DESC,id", (owner,)).fetchall()],
                    'experiences': [dict(r) for r in c.execute('SELECT * FROM experiences WHERE owner_id=? ORDER BY occurred_at DESC,id', (owner,))],
                    'tasks': [dict(r) for r in c.execute('SELECT * FROM tasks WHERE owner_id=? ORDER BY id', (owner,))],
                    'notes': [dict(r) for r in c.execute('SELECT * FROM notes WHERE owner_id=? ORDER BY created_at DESC,id', (owner,))],
                    'rewards': {'total': sum(r['points'] for r in rewards), 'events': rewards},
                    'policy': {'mode': 'local-development', 'rule_version': self.policy.rule_version,
                               'points_per_experience': self.policy.points_per_experience, 'max_upload_bytes': self.policy.max_upload_bytes,
                               'allowed_mime_types': ['image/png', 'image/jpeg'], 'negative_decay': False, 'ai_provider': 'local-manual'}}
