"""Unified Person（Schema 010）：新的人物系統，逐步取代舊「關係」與「角色」的人物管理職責。

設計重點：
- 讀寫既有 people 表（含 010 的 aliases、person_type、person_subtype、description、origin_type、status），
  不新增資料表；舊 /api/people 的回應格式不變，兩邊看到同一批人物。
- 只在資料庫已有 Schema 010 時開放：與關係來源 link_table 同時啟用（PG 在 Migration 010 驗收後才設定）。
  舊結構一律回 409 unified_people_not_enabled，不假設 010 欄位存在。
- 人物設定存在 notes(kind='preparation', title=PROFILE_TITLE)，內容是 JSON。Migration 010 後 App 對 notes
  只有 INSERT／SELECT，所以每次保存都新增一筆（舊版保留），讀取取最新一筆；以 expected_profile_id 防止覆蓋他人的較新版本。
- 「是不是正式人物設定」只看 requests 裡的正式保存回執（operation＝persons:profile:{person_id}、response.id＝notes.id）。
  舊 /api/notes 可以建立標題與 JSON 格式完全相同的私人筆記，但它沒有這個回執，所以仍是私人筆記，不會被當成人物設定。
- 已封存的人物不能修改基本資料，也不能新增人物設定版本（409 person_archived，在交易內檢查）；讀取不受限。
- 同名人物可並存；類型與分類選填；封存不刪除；經歷不改人物設定；不因共同經歷自動建立關係；不建立作品角色卡。
"""
import hashlib
import json
import unicodedata
from uuid import uuid4

from .errors import require
from . import relation_sources

PROFILE_TITLE = 'person_profile.v1'  # 人物設定在 notes 的保留標題；舊人物頁的私人筆記清單不顯示它
PROFILE_SCHEMA = 'person_profile.v1'
# 人物設定欄位（取代原 AI 角色卡的設定欄位）：(欄位, 上限字數)。合計上限低於 notes 單筆 20000 字。
PROFILE_FIELDS = (('background', 3000), ('personality', 2000), ('motivation', 1500), ('stance', 1500), ('abilities', 1500),
                  ('expression', 2000), ('behavior', 2000), ('knowledge_boundary', 1000), ('restrictions', 1500))
PROFILE_ORIGINS = ('manual', 'ai', 'ai_edited')
PERSON_COLUMNS = ('id,owner_id,name,aliases,person_type,person_subtype,description,roles,tags,category,status,'
                  'origin_type,followed,revision,created_at,notes,common_context')
SUBTYPE_TYPE = {'historical': 'real', 'original': 'fictional'}  # 與 people_unification_type_ck 一致
PROFILE_OPERATION = 'persons:profile:'  # 正式保存回執的 operation 前綴，後面接 person_id


def uid():
    return str(uuid4())


def js(value):
    return json.dumps(value, ensure_ascii=False)


def resolve_type(person_type, person_subtype, current_type=None, type_sent=True):
    """把選填的類型／子類型轉成合法組合。

    只給子類型時由它推出類型（historical→real、original→fictional）；都沒給就用 Schema 010 預設 real。
    編輯時只改類型而舊子類型不再相容，子類型清空（以使用者這次的選擇為準）；同時送出不相容的組合回 422。
    """
    if person_subtype is not None:
        implied = SUBTYPE_TYPE[person_subtype]
        chosen = person_type if type_sent and person_type is not None else implied
        require(chosen == implied, 422, 'invalid_person_type', '歷史人物必須是真實人物；自創人物必須是虛構人物。')
        return implied, person_subtype
    return (person_type if type_sent and person_type is not None else current_type) or 'real', None


def person_dto(row):
    """新人物系統的人物回應（含 010 欄位）。PG 轉接層把 JSONB 轉成文字、布林轉成整數，這裡還原。"""
    return {'id': row['id'], 'owner_id': row['owner_id'], 'name': row['name'], 'aliases': json.loads(row['aliases']),
            'person_type': row['person_type'], 'person_subtype': row['person_subtype'], 'description': row['description'],
            'roles': json.loads(row['roles']), 'tags': json.loads(row['tags']), 'category': row['category'], 'status': row['status'],
            'origin_type': row['origin_type'], 'followed': bool(row['followed']), 'revision': row['revision'], 'created_at': row['created_at'],
            'notes': row['notes'], 'common_context': row['common_context']}  # 舊人物主檔欄位（人物備註、相關背景／共同場合）


def record_summary(row):
    """我的紀錄的簡短摘要：有人工摘要就用摘要，否則用原文開頭。"""
    text = (row['summary'] or '').strip() or (row['raw_text'] or '').strip()
    return {'id': row['id'], 'summary': text[:120], 'occurred_at': row['occurred_at']}


def parse_profile(note):
    """把人物設定筆記轉成回應；內容不是本系統格式就視為一般筆記（回 None）。"""
    try:
        body = json.loads(note['content'])
    except (TypeError, ValueError):
        return None
    if not isinstance(body, dict) or body.get('schema') != PROFILE_SCHEMA or not isinstance(body.get('fields'), dict):
        return None
    version = body.get('version')
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        return None
    fields = {key: str(body['fields'].get(key, '')) for key, _ in PROFILE_FIELDS}
    return {'id': note['id'], 'version': version, 'saved_at': note['created_at'], 'origin': body.get('origin', 'manual'),
            'generation_id': body.get('generation_id'), 'fields': fields}


def profile_receipts(c, owner):
    """本人帳號的正式人物設定回執：{note_id: person_id}。

    只有 save_unified_profile 會寫入 operation＝persons:profile:{person_id} 的回執，回執 response.id 就是那一版的 notes.id。
    這是辨識正式人物設定的唯一依據（內容格式相同的私人筆記沒有回執）。
    """
    receipts = {}
    rows = c.execute('SELECT operation,response FROM requests WHERE owner_id=? AND operation LIKE ?', (owner, PROFILE_OPERATION + '%')).fetchall()
    for row in rows:
        try:
            body = json.loads(row['response'])
        except (TypeError, ValueError):
            continue
        if isinstance(body, dict) and isinstance(body.get('id'), str):
            receipts[body['id']] = row['operation'][len(PROFILE_OPERATION):]
    return receipts


def is_profile_note(note, receipts):
    """正式人物設定：保留標題與格式之外，還要有回執，而且回執的人物就是這則筆記的人物（owner 由查詢範圍保證）。"""
    return (note['kind'] == 'preparation' and note['title'] == PROFILE_TITLE and note['person_id'] is not None
            and receipts.get(note['id']) == note['person_id'] and parse_profile(note) is not None)


class PersonsMixin:
    """/api/persons 的服務實作；與 PeopleMixin 共用交易、帳號與重送工具。"""

    def _persons_enabled(self):
        require(self.relation_source_store == relation_sources.LINK, 409, 'unified_people_not_enabled',
                '新人物功能要等資料庫升級（010）完成後才開放。')

    def unified_people_available(self):
        return self.relation_source_store == relation_sources.LINK

    def _person_row(self, c, owner, person_id):
        row = c.execute('SELECT ' + PERSON_COLUMNS + ' FROM people WHERE id=? AND owner_id=?', (person_id, owner)).fetchone()
        require(row is not None, 404, 'not_found', '找不到這位人物。')  # 他人的人物一律 404，不透露是否存在
        return row

    def _profile(self, c, owner, person_id):
        """最新的正式人物設定（只認有正式回執的版本）。版本號寫在內容裡（同一帳號的寫入已序列化，
        且保存前核對最新版），所以不依賴 created_at：同一時刻保存的多版也能正確排序。"""
        receipts = profile_receipts(c, owner)
        notes = c.execute("SELECT id,person_id,kind,title,content,created_at FROM notes WHERE owner_id=? AND person_id=? AND kind='preparation' AND title=?",
                          (owner, person_id, PROFILE_TITLE)).fetchall()
        versions = [parse_profile(n) for n in notes if is_profile_note(n, receipts)]
        return max(versions, key=lambda p: (p['version'], p['saved_at'], p['id'])) if versions else None

    def persons_list(self, owner, q='', person_type='', person_subtype='', category='', status='active', sort='recent', limit=50, offset=0):
        """列出本人的人物：搜尋姓名、別名、標籤、角色與簡介；依類型、子類型、分類、狀態篩選。"""
        self._persons_enabled()
        with self.db.connect() as c:
            self._people_user(c, owner)
            rows = [person_dto(r) for r in c.execute('SELECT ' + PERSON_COLUMNS + ' FROM people WHERE owner_id=?', (owner,)).fetchall()]
        query = unicodedata.normalize('NFKC', q).casefold().strip()

        def matches(p):
            text = unicodedata.normalize('NFKC', ' '.join([p['name'], *p['aliases'], *p['tags'], *p['roles'], p['description']])).casefold()
            return ((not query or query in text) and p['status'] == status and (not person_type or p['person_type'] == person_type)
                    and (not person_subtype or p['person_subtype'] == person_subtype) and (not category or p['category'] == category))

        items = [p for p in rows if matches(p)]
        if sort == 'name':
            items.sort(key=lambda p: (p['name'].casefold(), p['created_at'], p['id']))
        else:  # recent：最近建立的在前；同時間依識別碼固定順序
            items.sort(key=lambda p: (p['created_at'], p['id']), reverse=True)
        return {'items': items[offset:offset + limit], 'total': len(items), 'offset': offset, 'limit': limit}

    def create_unified_person(self, owner, data):
        """新增人物：同名可並存；request_id 防重送；來源標記為 manual。"""
        self._persons_enabled()
        with self.db.connect(write=True, owner=owner) as c:
            self._people_user(c, owner)
            cached, fingerprint = self._cached(c, owner, 'persons:create', data.request_id, data.model_dump(exclude={'request_id'}))
            if cached:
                return cached
            person_type, person_subtype = resolve_type(data.person_type, data.person_subtype)
            person_id = uid()
            # 舊欄位 role 沿用舊建立流程的規則（多角色以頓號串接），讓舊人物頁仍能顯示。
            c.execute('INSERT INTO people(id,owner_id,name,role,notes,created_at,roles,tags,category,followed,common_context,'
                      'aliases,person_type,person_subtype,description,origin_type,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (person_id, owner, data.name, '、'.join(data.roles), data.notes, self.now().isoformat(), js(data.roles), js(data.tags),
                       data.category, data.followed, data.common_context, js(data.aliases), person_type, person_subtype, data.description,
                       'manual', 'active'))
            profile_fields = {key: (getattr(data.profile, key) or '').strip() for key, _ in PROFILE_FIELDS} if data.profile else {}
            if any(profile_fields.values()):  # 單頁一次儲存：同一交易建立第 1 版人物設定，並寫正式回執
                self._insert_profile_version(c, owner, person_id, profile_fields, 'manual', None, None, 'create:' + data.request_id)
            result = person_dto(self._person_row(c, owner, person_id))
            self._remember(c, owner, 'persons:create', data.request_id, fingerprint, result)
            return result

    def _insert_profile_version(self, c, owner, person_id, fields, origin, generation_id, current, request_id, fingerprint=None):
        """新增一版人物設定（notes 只新增）並在同一交易寫入正式回執；回傳這一版的回應。"""
        version = current['version'] + 1 if current else 1
        content = js({'schema': PROFILE_SCHEMA, 'version': version, 'previous_id': current['id'] if current else None,
                      'origin': origin, 'generation_id': generation_id, 'fields': fields})
        note_id = uid()
        c.execute('INSERT INTO notes(id,owner_id,person_id,kind,title,content,created_at) VALUES (?,?,?,?,?,?,?)',
                  (note_id, owner, person_id, 'preparation', PROFILE_TITLE, content, self.now().isoformat()))
        saved_at = c.execute('SELECT created_at FROM notes WHERE id=? AND owner_id=?', (note_id, owner)).fetchone()[0]  # 與讀取時同一表示法
        # 這一版還沒有回執，_profile 讀不到它；直接用本次寫入的資料組回應，再與筆記同一交易寫入回執（回執 id＝note_id）。
        result = {'id': note_id, 'version': version, 'saved_at': saved_at, 'origin': origin, 'generation_id': generation_id, 'fields': fields}
        self._remember(c, owner, PROFILE_OPERATION + person_id, request_id, fingerprint or hashlib.sha256(js(fields).encode()).hexdigest(), result)
        return result

    def edit_unified_person(self, owner, person_id, data):
        """只更新明確送出的欄位；檢查 revision，成功後 revision 加 1。"""
        self._persons_enabled()
        with self.db.connect(write=True, owner=owner) as c:
            self._people_user(c, owner)
            row = self._person_row(c, owner, person_id)
            require(row['status'] == 'active', 409, 'person_archived', '已封存的人物不能修改；恢復後即可編輯。')
            self._revision(row, data.expected_revision)
            fields = data.model_dump(exclude_unset=True, exclude={'expected_revision'})
            updates = {}
            if 'person_type' in fields or 'person_subtype' in fields:
                subtype = fields['person_subtype'] if 'person_subtype' in fields else row['person_subtype']
                if 'person_type' in fields and 'person_subtype' not in fields and subtype and SUBTYPE_TYPE[subtype] != fields['person_type']:
                    subtype = None  # 只改類型時，不相容的舊子類型清空
                updates['person_type'], updates['person_subtype'] = resolve_type(fields.get('person_type'), subtype, row['person_type'],
                                                                                 type_sent='person_type' in fields)
            for key in ('name', 'description', 'category', 'notes', 'common_context', 'followed'):  # 含承接的舊人物主檔欄位
                if key in fields:
                    updates[key] = fields[key]
            for key in ('aliases', 'roles', 'tags'):
                if key in fields:
                    updates[key] = js(fields[key])
            if 'roles' in fields:
                updates['role'] = '、'.join(fields['roles'])  # 舊欄位同步，舊人物頁顯示一致
            if updates:
                assignments = ','.join(key + '=?' for key in updates)  # 欄位名稱只來自上面的固定清單
                c.execute('UPDATE people SET ' + assignments + ',revision=revision+1 WHERE id=? AND owner_id=?', (*updates.values(), person_id, owner))
            return person_dto(self._person_row(c, owner, person_id))

    def set_unified_person_status(self, owner, person_id, data):
        """封存或恢復人物；不刪除任何人物、經歷、關係或設定。"""
        self._persons_enabled()
        with self.db.connect(write=True, owner=owner) as c:
            self._people_user(c, owner)
            row = self._person_row(c, owner, person_id)
            op = 'persons:status:' + person_id
            cached, fingerprint = self._cached(c, owner, op, data.request_id, data.model_dump(exclude={'request_id'}))
            if cached:
                return cached
            self._revision(row, data.expected_revision)
            c.execute('UPDATE people SET status=?,revision=revision+1 WHERE id=? AND owner_id=?', (data.status, person_id, owner))
            result = person_dto(self._person_row(c, owner, person_id))
            self._remember(c, owner, op, data.request_id, fingerprint, result)
            return result

    def unified_person(self, owner, person_id):
        """人物詳細頁：基本資料、最新人物設定、關係（來源讀關聯表）與經歷摘要。"""
        self._persons_enabled()
        with self.db.connect() as c:
            self._people_user(c, owner)
            person = person_dto(self._person_row(c, owner, person_id))
            rows = c.execute('SELECT id,owner_id,person_a,person_b,label,revision,relation_types,description,confirmation_status FROM person_connections '
                             'WHERE owner_id=? AND (person_a=? OR person_b=?)', (owner, person_id, person_id)).fetchall()
            sources = relation_sources.read(c, owner, [r['id'] for r in rows])
            connections = []
            for r in rows:  # 同一對人物只有一筆關係：兩位人物的詳細頁看到同一段描述、類型與來源
                other = person_dto(self._person_row(c, owner, r['person_b'] if r['person_a'] == person_id else r['person_a']))
                connections.append({'id': r['id'], 'revision': r['revision'],
                                    'status': 'archived' if r['confirmation_status'] == relation_sources.ARCHIVED else 'active',
                                    'confirmation_status': r['confirmation_status'],
                                    'relation_types': relation_sources.relation_types_view(r['relation_types']),
                                    'description': r['description'], 'label': r['label'],
                                    'text': r['description'] or r['label'],  # 以描述為主；沒有描述才回退到舊 label
                                    'person': {key: other[key] for key in ('id', 'name', 'person_type', 'person_subtype', 'status', 'description', 'followed')},
                                    **sources[r['id']],
                                    'sources': {'experiences': self._record_summaries(c, owner, sources[r['id']]['source_experience_ids']),
                                                'person_experiences': self._person_experience_summaries(  # 人物經歷來源（PersonExperiencesMixin）
                                                    c, owner, sources[r['id']]['source_person_experience_ids'])}})
            connections.sort(key=lambda x: (x['person']['name'].casefold(), x['id']))
            mine = c.execute('SELECT COUNT(*) FROM (SELECT id FROM experiences WHERE owner_id=? AND person_id=? UNION '
                             'SELECT p.experience_id FROM experience_participants p JOIN experiences x ON x.id=p.experience_id '
                             'WHERE x.owner_id=? AND p.person_id=?) linked', (owner, person_id, owner, person_id)).fetchone()[0]
            # 人物經歷：這位人物是主體或參與人物、且未封存的筆數（與「經歷」分頁的列表一致）
            subject = c.execute('SELECT COUNT(DISTINCT l.subject_experience_id) FROM subject_experience_people l JOIN subject_experiences e '
                                "ON e.id=l.subject_experience_id AND e.owner_id=l.owner_id WHERE l.owner_id=? AND l.person_id=? "
                                "AND l.role IN ('subject','participant') AND e.status='active'", (owner, person_id)).fetchone()[0]
            return {'person': person, 'profile': self._profile(c, owner, person_id), 'connections': connections,
                    'experiences': {'mine': mine, 'person_experiences': subject}}

    def _record_summaries(self, c, owner, experience_ids):
        """依來源順序回傳我的紀錄摘要（id、summary、occurred_at）。"""
        if not experience_ids:
            return []
        marks = ','.join('?' * len(experience_ids))
        rows = {r['id']: r for r in c.execute('SELECT id,summary,raw_text,occurred_at FROM experiences WHERE owner_id=? AND id IN (' + marks + ')',
                                              (owner, *experience_ids)).fetchall()}
        return [record_summary(rows[i]) for i in experience_ids if i in rows]

    def connection_sources(self, owner, person_id, other_person_id, limit=100):
        """可作為這兩位人物關係來源的「我的紀錄」：同帳號、已確認、與兩端至少一人有關。

        與寫入時的 _source_experience 用同一規則（_experience_people），畫面只列得出可以保存的來源。最近的在前，最多 limit 筆。
        """
        self._persons_enabled()
        with self.db.connect() as c:
            self._people_user(c, owner)
            self._person_row(c, owner, person_id)
            self._person_row(c, owner, other_person_id)
            require(person_id != other_person_id, 422, 'invalid_connection', '請選擇另一位人物。')
            pair = (person_id, other_person_id)
            rows = c.execute('SELECT id,person_id,summary,raw_text,occurred_at FROM experiences WHERE owner_id=? AND (person_id IN (?,?) OR id IN '
                             '(SELECT experience_id FROM experience_participants WHERE person_id IN (?,?)))', (owner, *pair, *pair)).fetchall()
            items = [record_summary(r) for r in rows if any(p in self._experience_people(c, r) for p in pair)]
            items.sort(key=lambda item: (str(item['occurred_at'] or ''), item['id']), reverse=True)
            eligible = self._eligible_person_experiences(c, owner, pair)  # 人物經歷來源（PersonExperiencesMixin）
            return {'items': items[:limit], 'total': len(items), 'person_experiences': {'items': eligible, 'total': len(eligible)}}

    def save_unified_profile(self, owner, person_id, data):
        """保存人物設定：新增一筆 notes（舊版保留），expected_profile_id 必須是目前最新版（第一次為 null）。"""
        self._persons_enabled()
        with self.db.connect(write=True, owner=owner) as c:
            self._people_user(c, owner)
            row = self._person_row(c, owner, person_id)
            op = PROFILE_OPERATION + person_id
            cached, fingerprint = self._cached(c, owner, op, data.request_id, data.model_dump(exclude={'request_id'}))
            if cached:
                return cached  # 已成功的相同請求（即使之後人物被封存）回原本的成功回執，不產生新版本
            require(row['status'] == 'active', 409, 'person_archived', '已封存的人物不能新增人物設定；恢復後即可編輯。')
            if data.generation_id is not None:  # AI 來源：必須是本人、這位人物、成功的人物設定生成
                generation = c.execute("SELECT input_json FROM ai_generations WHERE id=? AND owner_id=? AND module='person_profile' AND status='succeeded'",
                                       (data.generation_id, owner)).fetchone()
                linked = json.loads(generation['input_json']).get('person_id') if generation else None
                require(linked == person_id, 409, 'generation_mismatch', '這份 AI 結果不屬於這位人物或沒有成功產生，請重新產生。')
            current = self._profile(c, owner, person_id)
            require((current['id'] if current else None) == data.expected_profile_id, 409, 'stale_profile',
                    '人物設定已在其他地方更新，請重新整理後再保存。')
            given = data.fields.model_dump()
            fields = {key: (given.get(key) or '').strip() for key, _ in PROFILE_FIELDS}
            return self._insert_profile_version(c, owner, person_id, fields, data.origin, data.generation_id, current, data.request_id, fingerprint)
