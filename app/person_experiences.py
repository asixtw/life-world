"""人物經歷（Schema 010 的 subject_experiences／subject_experience_people）：人物自己的經歷，使用者不必參與。

產品規則（2026-11-11 裁決）：
- 與「我的紀錄」（experiences，草稿→核對→確認）是兩種資料：人物經歷直接儲存，不計積分、目標與互動統計，也不混入 experiences。
- 一筆經歷有一位主體（subject）與 0～50 位其他參與人物（participant）；可以只有主體。建立者就是登入帳號（owner_id），不另外填。
- 性質（真實／歷史／虛構）在建立時決定。Migration 010 之後 App 對 subject_experiences 只能更新標題、內容、時間、狀態與版本，
  所以性質與來源建立後不能改；選錯時封存後重新建立。
- 發生時間可以不知道：精度 unknown 時 occurred_at 是 NULL；年／年月／完整日期存成 UTC 當日零時，讀取時依精度還原，不補造日期。
- 封存不刪除（App 沒有刪除權限）；已封存的經歷唯讀，只能恢復。主體人物已封存時不能新增、修改、封存或恢復。
- 已封存的人物不能被選為主體或新加入的參與人物；原本就在經歷裡的人物被封存後仍保留在經歷中。
- 不因共同參與自動建立人物關係；不自動修改人物設定。
"""
import re
from datetime import datetime, timezone

from . import relation_sources
from .errors import require
from .persons import record_summary, uid

ROLE_SUBJECT, ROLE_PARTICIPANT = 'subject', 'participant'
LIST_LIMIT = 200  # 人物頁一次列出的筆數上限（我的紀錄與人物經歷各自計算）
COLUMNS = 'id,owner_id,experience_type,origin_type,title,raw_text,occurred_at,occurred_precision,occurred_label,status,revision,created_at,updated_at'
PERSON_KEYS = ('id', 'name', 'person_type', 'person_subtype', 'status', 'description')
DATE_SHAPES = {'year': re.compile(r'^(\d{1,4})$'), 'month': re.compile(r'^(\d{1,4})-(\d{1,2})$'), 'day': re.compile(r'^(\d{1,4})-(\d{1,2})-(\d{1,2})$')}


def occurred_at(precision, on):
    """把「精度＋日期文字」轉成資料庫的時間（UTC 當日零時的 ISO 文字）；不知道時間回 None。

    on 的格式依精度是 '208'、'208-12' 或 '208-12-01'（西元 1～9999 年）。格式或日期不合法時丟 ValueError。
    """
    if precision == 'unknown':
        if on:
            raise ValueError('不知道時間時不能填日期')
        return None
    match = DATE_SHAPES[precision].match(on or '')
    if not match:
        raise ValueError('日期格式與精度不符')
    year, month, day = ([int(part) for part in match.groups()] + [1, 1])[:3]
    return datetime(year, month, day, tzinfo=timezone.utc).isoformat()  # 不存在的日期（例如 2 月 30 日、0 年）由 datetime 拒絕


def occurred_on(value, precision):
    """把資料庫的時間依精度還原成使用者填的日期文字（'0208'、'0208-12'、'0208-12-01'）；不知道時間回 None。"""
    if precision == 'unknown' or not value:
        return None
    text = str(value)
    try:
        moment = datetime.fromisoformat(text.replace('Z', '+00:00'))
        if moment.tzinfo:
            moment = moment.astimezone(timezone.utc)
        year, month, day = moment.year, moment.month, moment.day
    except ValueError:  # 驅動程式沒有把很早的年代轉成時間物件時，直接取文字開頭的年月日
        match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', text)
        if not match:
            return None
        year, month, day = (int(part) for part in match.groups())
    if precision == 'year':
        return f'{year:04d}'
    if precision == 'month':
        return f'{year:04d}-{month:02d}'
    return f'{year:04d}-{month:02d}-{day:02d}'


class PersonExperiencesMixin:
    """/api/person-experiences 與 /api/persons/{id}/experiences 的服務實作；與 PersonsMixin 共用交易、帳號與重送工具。"""

    def _subject_experience_row(self, c, owner, experience_id):
        row = c.execute('SELECT ' + COLUMNS + ' FROM subject_experiences WHERE id=? AND owner_id=?', (experience_id, owner)).fetchone()
        require(row is not None, 404, 'not_found', '找不到這筆人物經歷。')  # 他人的經歷一律 404，不透露是否存在
        return row

    def _subject_experience_people(self, c, owner, experience_ids):
        """{經歷 ID: {'subject': 主體人物摘要, 'participants': [依姓名排序的參與人物摘要]}}；一次查完，不逐筆查詢。"""
        result = {experience_id: {'subject': None, 'participants': []} for experience_id in experience_ids}
        if not experience_ids:
            return result
        marks = ','.join('?' * len(experience_ids))
        rows = c.execute('SELECT l.subject_experience_id,l.role,p.id,p.name,p.person_type,p.person_subtype,p.status,p.description '
                         'FROM subject_experience_people l JOIN people p ON p.id=l.person_id AND p.owner_id=l.owner_id '
                         'WHERE l.owner_id=? AND l.subject_experience_id IN (' + marks + ')', (owner, *experience_ids)).fetchall()
        for row in rows:
            person = {key: row[key] for key in PERSON_KEYS}
            entry = result[row['subject_experience_id']]
            if row['role'] == ROLE_SUBJECT:
                entry['subject'] = person
            elif row['role'] == ROLE_PARTICIPANT:
                entry['participants'].append(person)
        for entry in result.values():
            entry['participants'].sort(key=lambda person: (person['name'].casefold(), person['id']))
        return result

    @staticmethod
    def _subject_experience_dto(row, people):
        return {'id': row['id'], 'owner_id': row['owner_id'], 'revision': row['revision'], 'status': row['status'], 'title': row['title'],
                'content': row['raw_text'], 'experience_type': row['experience_type'], 'origin_type': row['origin_type'],
                'occurred_precision': row['occurred_precision'], 'occurred_on': occurred_on(row['occurred_at'], row['occurred_precision']),
                'occurred_label': row['occurred_label'], 'created_at': row['created_at'], 'updated_at': row['updated_at'],
                'subject': people['subject'], 'participants': people['participants']}

    def _subject_experience(self, c, owner, experience_id):
        row = self._subject_experience_row(c, owner, experience_id)
        return self._subject_experience_dto(row, self._subject_experience_people(c, owner, [experience_id])[experience_id])

    @staticmethod
    def _occurred_at(precision, on):
        try:
            return occurred_at(precision, on)
        except ValueError:
            require(False, 422, 'invalid_date', '發生時間不正確：只知道年份就只填年，知道月份再填月，知道日期再填日。')

    def _link_person(self, c, owner, experience_id, person_id, role, now):
        c.execute('INSERT INTO subject_experience_people(subject_experience_id,owner_id,person_id,role,created_at) VALUES (?,?,?,?,?)',
                  (experience_id, owner, person_id, role, now))

    def person_experience(self, owner, experience_id):
        """讀單一人物經歷。"""
        self._persons_enabled()
        with self.db.connect() as c:
            self._people_user(c, owner)
            return self._subject_experience(c, owner, experience_id)

    def create_person_experience(self, owner, data):
        """新增人物經歷：先在同一筆交易完整驗證（帳號、人物、日期），再寫入；request_id 防重送。"""
        self._persons_enabled()
        with self.db.connect(write=True, owner=owner) as c:
            self._people_user(c, owner)
            cached, fingerprint = self._cached(c, owner, 'person-experiences:create', data.request_id, data.model_dump(exclude={'request_id'}))
            if cached:
                return cached  # 同代碼同內容的重送回原結果（即使人物之後被封存）
            people = [self._person_row(c, owner, person_id) for person_id in (data.subject_person_id, *data.participant_ids)]
            require(all(person['status'] == 'active' for person in people), 409, 'person_archived', '已封存的人物不能加入經歷；恢復人物後即可選擇。')
            moment = self._occurred_at(data.occurred_precision, data.occurred_on)
            now, experience_id = self.now().isoformat(), uid()
            c.execute('INSERT INTO subject_experiences(id,owner_id,experience_type,origin_type,title,raw_text,occurred_at,occurred_precision,'
                      "occurred_label,status,revision,created_at,updated_at) VALUES (?,?,?,'manual',?,?,?,?,?,'active',1,?,?)",
                      (experience_id, owner, data.experience_type, data.title, data.content, moment, data.occurred_precision,
                       data.occurred_label, now, now))
            self._link_person(c, owner, experience_id, data.subject_person_id, ROLE_SUBJECT, now)
            for person_id in data.participant_ids:
                self._link_person(c, owner, experience_id, person_id, ROLE_PARTICIPANT, now)
            result = self._subject_experience(c, owner, experience_id)
            self._remember(c, owner, 'person-experiences:create', data.request_id, fingerprint, result)
            return result

    def patch_person_experience(self, owner, experience_id, data):
        """編輯、封存或恢復人物經歷：只更新有送出的欄位；revision 防覆蓋；任何錯誤整筆回滾。"""
        self._persons_enabled()
        with self.db.connect(write=True, owner=owner) as c:
            self._people_user(c, owner)
            row = self._subject_experience_row(c, owner, experience_id)
            operation = 'person-experiences:patch:' + experience_id
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, data.model_dump(exclude={'request_id'}))
            if cached:
                return cached  # 同代碼同內容的重送回原結果（即使 revision 已前進）
            require(row['revision'] == data.expected_revision, 409, 'stale_revision', '這筆經歷已在其他地方更新，請重新整理後再修改。')
            date_sent = data.occurred_precision is not None or data.occurred_on is not None
            content = {key: getattr(data, key) for key in ('title', 'content', 'occurred_label', 'participant_ids') if getattr(data, key) is not None}
            require(bool(content) or date_sent or data.status is not None, 422, 'empty_patch', '請至少修改一個欄位。')
            people = self._subject_experience_people(c, owner, [experience_id])[experience_id]
            require(people['subject'] is not None and people['subject']['status'] == 'active', 409, 'person_archived',
                    '主體人物已封存，這筆經歷只能查看；恢復人物後才能修改。')
            if row['status'] == 'archived':  # 已封存的經歷唯讀：只接受單獨的恢復
                require(data.status == 'active' and not content and not date_sent, 409, 'experience_archived', '這筆經歷已封存；恢復後才能修改。')
            updates = {}
            if data.title is not None:
                updates['title'] = data.title
            if data.content is not None:
                updates['raw_text'] = data.content
            if data.occurred_label is not None:
                updates['occurred_label'] = data.occurred_label
            if date_sent:
                require(data.occurred_precision is not None, 422, 'invalid_date', '修改發生時間時要一併送出精度。')
                updates['occurred_at'] = self._occurred_at(data.occurred_precision, data.occurred_on)
                updates['occurred_precision'] = data.occurred_precision
            if data.status is not None:
                updates['status'] = data.status
            added = removed = ()
            if data.participant_ids is not None:
                current = {person['id'] for person in people['participants']}
                require(people['subject']['id'] not in data.participant_ids, 422, 'invalid_participants', '主體人物不必再列為參與人物。')
                added = [person_id for person_id in data.participant_ids if person_id not in current]
                removed = current - set(data.participant_ids)
                for person_id in added:  # 原本就在經歷裡的人物即使已封存也保留；新加入的必須是使用中的人物
                    require(self._person_row(c, owner, person_id)['status'] == 'active', 409, 'person_archived',
                            '已封存的人物不能加入經歷；恢復人物後即可選擇。')
            # 這筆經歷若是關係的來源：不能封存，也不能把參與人物改到和那段關係無關（主體不能改，一定留著）。先擋下來，什麼都不寫。
            archiving = data.status == 'archived' and row['status'] != 'archived'
            if archiving:
                relation_sources.require_still_related(c, owner, 'person_experience', experience_id, None, '這筆經歷', '不能封存')
            elif removed:
                remaining = {people['subject']['id']} | (current - removed) | set(added)
                relation_sources.require_still_related(c, owner, 'person_experience', experience_id, remaining, '這筆經歷', '移除這位參與人物後就和這段關係無關了')
            now = self.now().isoformat()
            assignments = ''.join(key + '=?,' for key in updates)  # 欄位名稱只來自上面的固定清單
            c.execute('UPDATE subject_experiences SET ' + assignments + 'revision=revision+1,updated_at=? WHERE id=? AND owner_id=?',
                      (*updates.values(), now, experience_id, owner))
            for person_id in removed:
                c.execute('DELETE FROM subject_experience_people WHERE subject_experience_id=? AND owner_id=? AND person_id=? AND role=?',
                          (experience_id, owner, person_id, ROLE_PARTICIPANT))
            for person_id in added:
                self._link_person(c, owner, experience_id, person_id, ROLE_PARTICIPANT, now)
            result = self._subject_experience(c, owner, experience_id)
            self._remember(c, owner, operation, data.request_id, fingerprint, result)
            return result

    def person_experience_lists(self, owner, person_id, archived=False):
        """人物頁「經歷」分頁的兩區：我的紀錄（與這位人物有關的已確認紀錄）與人物經歷（這位人物是主體或參與人物）。

        人物經歷排序：知道時間的在前、由新到舊；不知道時間的排在最後（不當成今天）。archived=True 時列出已封存的人物經歷。
        """
        self._persons_enabled()
        with self.db.connect() as c:
            self._people_user(c, owner)
            self._person_row(c, owner, person_id)
            linked = ('FROM experiences WHERE owner_id=? AND (person_id=? OR id IN '
                      '(SELECT experience_id FROM experience_participants WHERE person_id=?))')
            records = c.execute('SELECT id,summary,raw_text,occurred_at ' + linked + ' ORDER BY occurred_at DESC,id LIMIT ?',
                                (owner, person_id, person_id, LIST_LIMIT)).fetchall()
            record_total = c.execute('SELECT COUNT(*) ' + linked, (owner, person_id, person_id)).fetchone()[0]
            joined = ('FROM subject_experiences e JOIN subject_experience_people l ON l.subject_experience_id=e.id AND l.owner_id=e.owner_id '
                      "WHERE e.owner_id=? AND l.person_id=? AND l.role IN ('subject','participant')")
            counts = {row['status']: row['n'] for row in
                      c.execute('SELECT e.status AS status,COUNT(*) AS n ' + joined + ' GROUP BY e.status', (owner, person_id)).fetchall()}
            rows = c.execute('SELECT ' + ','.join('e.' + column for column in COLUMNS.split(',')) + ',l.role AS link_role ' + joined +
                             ' AND e.status=? ORDER BY e.occurred_at IS NULL,e.occurred_at DESC,e.created_at DESC,e.id LIMIT ?',
                             (owner, person_id, 'archived' if archived else 'active', LIST_LIMIT)).fetchall()
            people = self._subject_experience_people(c, owner, [row['id'] for row in rows])
            items = [{**self._subject_experience_dto(row, people[row['id']]), 'role': row['link_role']} for row in rows]
            return {'records': {'items': [record_summary(row) for row in records], 'total': record_total},
                    'person_experiences': {'items': items, 'total': counts.get('active', 0), 'archived_total': counts.get('archived', 0)}}

    # ---- 紀錄頁的人物經歷總列表（E2）與關係來源（E3）----

    def person_experiences_list(self, owner, archived=False, limit=LIST_LIMIT, offset=0):
        """本人帳號的全部人物經歷（紀錄頁用）：與人物頁是同一批資料。知道時間的在前、由新到舊；不知道時間的排在最後。"""
        self._persons_enabled()
        with self.db.connect() as c:
            self._people_user(c, owner)
            counts = {row['status']: row['n'] for row in
                      c.execute('SELECT status,COUNT(*) AS n FROM subject_experiences WHERE owner_id=? GROUP BY status', (owner,)).fetchall()}
            rows = c.execute('SELECT ' + COLUMNS + ' FROM subject_experiences WHERE owner_id=? AND status=? '
                             'ORDER BY occurred_at IS NULL,occurred_at DESC,created_at DESC,id LIMIT ? OFFSET ?',
                             (owner, 'archived' if archived else 'active', limit, offset)).fetchall()
            people = self._subject_experience_people(c, owner, [row['id'] for row in rows])
            return {'items': [self._subject_experience_dto(row, people[row['id']]) for row in rows],
                    'total': counts.get('active', 0), 'archived_total': counts.get('archived', 0)}

    def _person_experience_summaries(self, c, owner, experience_ids):
        """依給定順序回傳人物經歷摘要（關係來源顯示用）：標題（沒有標題用內容開頭）、性質、時間與主體姓名。"""
        if not experience_ids:
            return []
        marks = ','.join('?' * len(experience_ids))
        rows = {row['id']: row for row in c.execute(
            'SELECT e.id,e.title,e.raw_text,e.experience_type,e.occurred_at,e.occurred_precision,e.occurred_label,p.name AS subject_name '
            "FROM subject_experiences e LEFT JOIN subject_experience_people l ON l.subject_experience_id=e.id AND l.owner_id=e.owner_id AND l.role='subject' "
            'LEFT JOIN people p ON p.id=l.person_id AND p.owner_id=l.owner_id WHERE e.owner_id=? AND e.id IN (' + marks + ')',
            (owner, *experience_ids)).fetchall()}
        return [{'id': row['id'], 'title': row['title'] or (row['raw_text'] or '').strip()[:60], 'experience_type': row['experience_type'],
                 'occurred_precision': row['occurred_precision'], 'occurred_on': occurred_on(row['occurred_at'], row['occurred_precision']),
                 'occurred_label': row['occurred_label'], 'subject': row['subject_name'] or ''}
                for row in (rows[experience_id] for experience_id in experience_ids if experience_id in rows)]

    def _eligible_person_experiences(self, c, owner, pair):
        """可作為這兩位人物關係來源的人物經歷：同帳號、未封存，兩端至少一人是主體或參與人物
        （與寫入時的 relation_sources.check_person_experience 同一規則，畫面只列得出可以保存的來源）。"""
        rows = c.execute("SELECT id FROM subject_experiences WHERE owner_id=? AND status='active' AND id IN "
                         "(SELECT subject_experience_id FROM subject_experience_people WHERE owner_id=? AND role IN ('subject','participant') "
                         'AND person_id IN (?,?)) ORDER BY occurred_at IS NULL,occurred_at DESC,created_at DESC,id LIMIT ?',
                         (owner, owner, *pair, LIST_LIMIT)).fetchall()
        return self._person_experience_summaries(c, owner, [row['id'] for row in rows])
