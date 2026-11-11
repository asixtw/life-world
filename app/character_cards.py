"""角色卡（2026-11-10 自 8445 角色管理中心移植）：系統角色目錄、我的角色卡、複製、改版、新舊版本讀回、封存與恢復。

來源：life-world-react-integrated 的 app/characters.py、app/works.py、app/schemas.py（角色卡部分）。
沿用同一份資料格式與資料表（works／work_versions，kind=character_card），所以 8445 已建立的角色卡可以直接讀取與改版。

規則：
- 版本只新增、不改寫；每次改版以 expected_revision 防止過期分頁覆蓋，以 request_id 防止重送重複寫入。
- 來源參照與肖像只由伺服器在複製時寫入，編輯時不能更換。
- 所有查詢都以 owner 過濾；查不到一律 404，不透露其他帳號的資料是否存在。
- 系統角色可由任何已登入身分瀏覽；建立與修改角色卡需要已完成 Bio 與第一個目標的正式帳號（與 8445 相同）。
- 本批不提供刪除（刪除需檢查引用，留待作品管理）。
"""
import json
from pathlib import Path
from typing import Annotated, List, Literal, Optional
from uuid import uuid4

from pydantic import Field, StrictInt, model_validator

from .errors import require
from .schemas import Model
from .security import require_registered

CATALOG = json.loads((Path(__file__).parent / 'catalog' / 'system_characters.v1.json').read_text(encoding='utf-8'))
SYSTEM_CHARACTERS = {item['id']: item for item in CATALOG}  # 系統角色：唯讀、所有帳號共用
PACK_LABELS = {'three-kingdoms': '三國', 'international-dialogue': '國際對話', 'philosophy': '哲學'}
CARD_SCHEMA = 'character_card.v2'  # 新保存的版本；8445 時期的 character_card.v1 不改寫、照常可讀


def encoded(value):
    """與 8445 相同的穩定 JSON（作品內容與請求指紋共用）。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


# ---- 內容結構（與 8445 的 CharacterCardContent 相同，舊欄位全部保留，新欄位都是選填） ----
CARD_INSPIRATIONS = ('original', 'anime', 'wuxia', 'history', 'real_person', 'role', 'mixed')
CardLine = Annotated[str, Field(min_length=1, max_length=120)]
CardSampleLine = Annotated[str, Field(min_length=1, max_length=400)]
CardTag = Annotated[str, Field(min_length=1, max_length=20)]


class CardSourceRef(Model):  # 來源參照；只由伺服器在複製時寫入
    kind: Literal['system_character', 'character_card', 'person_portrayal']
    id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=60)
    ai_inferred: bool = False
    snapshot_sha256: Optional[str] = Field(default=None, max_length=64)
    generation_id: Optional[str] = Field(default=None, max_length=128)
    acknowledged_at: Optional[str] = Field(default=None, max_length=40)
    note: str = Field(default='', max_length=200)


class CharacterCardContent(Model):
    name: str = Field(min_length=1, max_length=60)
    kind: Literal['fictional', 'role']
    tagline: str = Field(default='', max_length=400)
    background: str = Field(default='', max_length=3000)
    personality: str = Field(default='', max_length=2000)
    motivation: str = Field(default='', max_length=1500)
    stance: str = Field(default='', max_length=1500)
    voice: str = Field(default='', max_length=600)
    knowledge_boundary: str = Field(default='', max_length=1000)
    restrictions: List[CardLine] = Field(default_factory=list, max_length=8)
    sample_lines: List[CardSampleLine] = Field(default_factory=list, max_length=3)
    values: str = Field(default='', max_length=1500)
    behavior: str = Field(default='', max_length=2000)
    appearance: str = Field(default='', max_length=1000)
    inspirations: List[Literal[CARD_INSPIRATIONS]] = Field(default_factory=list, max_length=7)
    tags: List[CardTag] = Field(default_factory=list, max_length=12)
    image_ref: Optional[str] = Field(default=None, max_length=80)
    source_references: List[CardSourceRef] = Field(default_factory=list, max_length=6)

    @model_validator(mode='after')
    def distinct_labels(self):  # 標籤與靈感不重複，避免篩選重複計數
        if len(set(self.inspirations)) != len(self.inspirations) or len(set(self.tags)) != len(self.tags):
            raise ValueError('標籤不可重複')
        return self


class CharacterCreate(Model):  # 保存 AI 草稿（附 generation_id）或人工建立的角色卡
    request_id: str = Field(min_length=1, max_length=128)
    content: CharacterCardContent
    generation_id: Optional[str] = Field(default=None, min_length=1, max_length=128)


class CharacterCopy(Model):  # 複製系統角色或自己的角色卡版本，建立獨立的新角色卡
    request_id: str = Field(min_length=1, max_length=128)
    source_kind: Literal['system', 'card']
    source_id: str = Field(min_length=1, max_length=128)
    source_version: str = Field(min_length=1, max_length=20)


class CharacterVersionCreate(Model):  # 新增版本；不改寫既有版本
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)
    base_version: StrictInt = Field(ge=1)
    content: CharacterCardContent


class CharacterStatus(Model):  # 封存或恢復；不刪除任何版本
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)
    status: Literal['active', 'archived']


def normalized(content):
    """補齊舊版缺少的選填欄位，讓列表、編輯與 8445 的舊資料使用同一結構。"""
    return CharacterCardContent.model_validate(content).model_dump(mode='json')


def system_card(persona):
    """系統角色轉成角色卡內容（與 8445 相同的對應方式）。"""
    cutoff = f"（知識截至：{persona['knowledgeCutoff']}）" if persona.get('knowledgeCutoff') else ''
    return normalized({'name': persona['name'], 'kind': 'role' if persona['kind'] == 'role' else 'fictional',
                       'tagline': persona.get('summary', ''), 'motivation': persona.get('motivation', ''), 'stance': persona.get('perspective', ''),
                       'voice': persona.get('voice', ''), 'knowledge_boundary': (persona.get('boundary', '') + cutoff)[:1000],
                       'inspirations': ['role'] if persona['kind'] == 'role' else ['history'],
                       'tags': [PACK_LABELS.get(persona.get('packId'), persona.get('packId', '範例'))[:20]],
                       'image_ref': persona.get('avatarId')})


def system_entry(persona):
    return {'id': persona['id'], 'version': persona['version'], 'name': persona['name'], 'kind': persona['kind'],
            'pack': persona.get('packId'), 'pack_label': PACK_LABELS.get(persona.get('packId'), persona.get('packId')),
            'content': system_card(persona), 'source_refs': persona.get('sourceRefs', []), 'usage_scope': persona.get('usageScope')}


def card_version_no(value):
    version = int(value) if value.isascii() and value.isdigit() else 0
    require(1 <= version <= 2147483647, 422, 'invalid_version', '角色卡版本必須是有效的正整數。')
    return version


def provenance(content, first_origin):
    """列表用的製作來源：複製系統角色／複製角色卡／人物演繹轉入／AI／人工建立。"""
    kinds = [ref.get('kind') for ref in content.get('source_references') or []]
    if 'person_portrayal' in kinds:
        return 'portrayal'
    if kinds and kinds[-1] == 'system_character':
        return 'copy_system'
    if kinds and kinds[-1] == 'character_card':
        return 'copy_card'
    return 'ai' if first_origin in ('ai', 'ai_edited') else 'manual'


REFERENCING_KINDS = ('story_opening', 'story_session', 'theater_cast', 'theater_performance', 'roleplay_session', 'generated_work')  # 會引用角色卡的作品種類
DELETED = {'_deleted': True}  # 已刪除標記（防重複送出紀錄與 AI 原稿共用）


def referenced_cards(kind, content):
    """一個作品版本引用了哪些角色卡：回傳 {(work_id, version_no)}（2026-11-10 自 8445 移植）。"""
    if kind == 'story_opening':
        source = content.get('source') or {}
        return {(source.get('character_work_id'), source.get('character_version'))}
    if kind == 'story_session':
        character = content.get('character') or {}
        return {(character.get('work_id'), character.get('version_no'))}
    if kind in ('theater_cast', 'theater_performance'):
        return {(member['id'], int(member['version'])) for member in content.get('cast', []) if member.get('source') == 'card'}
    if kind == 'roleplay_session':  # 生成作品中心：陣容代號是 c1～c4，角色卡 ID 在 work_id
        return {(member['work_id'], int(member['version'])) for member in content.get('cast', []) if member.get('source') == 'card'}
    if kind == 'generated_work':  # 參與人物與被引用為素材的角色卡都算引用
        meta = content.get('meta') or {}
        refs = {(member['work_id'], int(member['version'])) for member in meta.get('participants', []) if member.get('source') == 'card'}
        refs |= {(item['work_id'], int(item['version_no'])) for item in meta.get('materials', []) if item.get('kind') == 'character_card'}
        return refs
    return set()


class CharacterDelete(Model):  # 真正刪除；有任何引用時拒絕
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)


class CharacterCardsMixin:
    """擴充 LifeWorld；沿用既有交易、防重送回執（requests）與 revision 規則。"""

    def _card_user(self, c, owner):
        """建立與修改角色卡：沿用 8445 的條件（完成 Bio 與第一個目標，而且是正式帳號）。"""
        user = self._onboarded(c, owner)
        require_registered(user)
        return user

    @staticmethod
    def _card_row(c, owner, work_id):
        row = c.execute("SELECT id,owner_id,kind,title,status,current_version,revision,created_at,updated_at FROM works WHERE id=? AND owner_id=? AND kind='character_card'", (work_id, owner)).fetchone()
        require(row is not None, 404, 'not_found', '找不到可存取的角色卡。')
        return row

    @staticmethod
    def _card_version(c, owner, work_id, version_no):
        row = c.execute('SELECT * FROM work_versions WHERE work_id=? AND owner_id=? AND version_no=?', (work_id, owner, version_no)).fetchone()
        require(row is not None, 404, 'not_found', '找不到指定的角色卡版本。')
        return {'work_id': row['work_id'], 'version_no': row['version_no'], 'parent_version': row['parent_version'], 'origin': row['origin'],
                'content_schema': row['content_schema'], 'content': json.loads(row['content_json']), 'generation_id': row['generation_id'],
                'created_at': row['created_at']}

    def _card_detail(self, c, owner, work_id):
        work = dict(self._card_row(c, owner, work_id))
        work.pop('owner_id')
        work['version'] = self._card_version(c, owner, work_id, work['current_version'])
        work['versions'] = [dict(row) for row in c.execute(
            'SELECT version_no,parent_version,origin,content_schema,generation_id,created_at FROM work_versions '
            'WHERE work_id=? AND owner_id=? ORDER BY version_no DESC', (work_id, owner)).fetchall()]
        return work

    def _insert_card(self, c, owner, content):
        content = normalized(content)
        work_id, now = str(uuid4()), self.now().isoformat()
        c.execute("INSERT INTO works(id,owner_id,kind,title,status,current_version,revision,created_at,updated_at) "
                  "VALUES (?,?,'character_card',?,'active',1,1,?,?)", (work_id, owner, content['name'], now, now))
        c.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                  "VALUES (?,?,1,NULL,'human',?,?,NULL,?)", (work_id, owner, CARD_SCHEMA, encoded(content), now))
        return work_id

    # ---- 讀取 ----
    @staticmethod
    def system_characters():
        return {'items': [system_entry(persona) for persona in CATALOG]}

    @staticmethod
    def system_character(character_id):
        persona = SYSTEM_CHARACTERS.get(character_id)
        require(persona is not None, 404, 'not_found', '找不到系統角色。')
        return system_entry(persona)

    def characters(self, owner, status):
        with self.db.connect() as c:
            self._owned_user(c, owner)
            where, params = "owner_id=? AND kind='character_card'", [owner]
            if status != 'all':
                where += ' AND status=?'
                params.append(status)
            works = c.execute('SELECT id,title,status,current_version,revision,created_at,updated_at FROM works WHERE ' + where +
                              ' ORDER BY updated_at DESC,id LIMIT 500', params).fetchall()
            items = []
            refs = self._reference_map(c, owner)
            for work in works:
                versions = {row['version_no']: row for row in c.execute(
                    'SELECT version_no,origin,content_json FROM work_versions WHERE work_id=? AND owner_id=? AND version_no IN (1,?)',
                    (work['id'], owner, work['current_version'])).fetchall()}
                current = versions[work['current_version']]
                content = normalized(json.loads(current['content_json']))
                first = versions[1]['origin'] if 1 in versions else None
                items.append({**dict(work), 'content': content, 'origin_current': current['origin'], 'provenance': provenance(content, first),
                              'used_by': len(refs.get(work['id'], {}))})
            return {'items': items, 'total': len(items)}

    def character(self, owner, work_id):
        with self.db.connect() as c:
            self._owned_user(c, owner)
            return self._card_detail(c, owner, work_id)

    def character_version(self, owner, work_id, version_no):
        with self.db.connect() as c:
            self._owned_user(c, owner)
            self._card_row(c, owner, work_id)
            return self._card_version(c, owner, work_id, version_no)

    # ---- 寫入 ----
    def copy_character(self, owner, data):
        """複製系統角色或自己的角色卡版本：內容由伺服器讀取（不信任前端提交），來源以參照記錄。"""
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, 'character:copy', data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            if data.source_kind == 'system':
                persona = SYSTEM_CHARACTERS.get(data.source_id)
                require(persona is not None and persona['version'] == data.source_version, 404, 'not_found', '找不到指定版本的系統角色。')
                content = system_card(persona)
                content['source_references'] = [{'kind': 'system_character', 'id': persona['id'], 'version': persona['version'], 'name': persona['name']}]
            else:
                work = self._card_row(c, owner, data.source_id)
                require(work['status'] == 'active', 409, 'character_archived', '這張角色卡已封存；請先恢復再複製。')
                content = normalized(self._card_version(c, owner, work['id'], card_version_no(data.source_version))['content'])
                content['source_references'] = (content['source_references'] + [
                    {'kind': 'character_card', 'id': work['id'], 'version': data.source_version, 'name': content['name']}])[-6:]
            result = self._card_detail(c, owner, self._insert_card(c, owner, content))
            self._remember(c, owner, 'character:copy', data.request_id, fingerprint, result)
            return result

    def create_character(self, owner, data):
        """保存新角色卡；引用 AI 原稿時，內容與原稿相同記為 ai，修改過記為 ai_edited（與 8445 相同）。"""
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, 'work:create', data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            content = normalized(data.content.model_dump(mode='json'))
            require(not content['source_references'] and content['image_ref'] is None, 422, 'managed_field',
                    '來源參照與肖像由系統在複製時設定，不能自行填寫。')
            origin = 'human'
            if data.generation_id:
                row = c.execute('SELECT * FROM ai_generations WHERE id=? AND owner_id=?', (data.generation_id, owner)).fetchone()
                require(row is not None, 404, 'not_found', '找不到可存取的生成紀錄。')
                require(row['status'] == 'succeeded' and row['module'] == 'character_card' and row['output_json'] is not None,
                        409, 'generation_not_usable', '這次生成沒有可用的角色卡草稿，請重新生成或改為手動填寫。')
                origin = 'ai' if encoded(content) == encoded(normalized(json.loads(row['output_json']))) else 'ai_edited'
            work_id, now = str(uuid4()), self.now().isoformat()
            c.execute("INSERT INTO works(id,owner_id,kind,title,status,current_version,revision,created_at,updated_at) "
                      "VALUES (?,?,'character_card',?,'active',1,1,?,?)", (work_id, owner, content['name'], now, now))
            c.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                      'VALUES (?,?,1,NULL,?,?,?,?,?)', (work_id, owner, origin, CARD_SCHEMA, encoded(content), data.generation_id, now))
            result = self._card_detail(c, owner, work_id)
            self._remember(c, owner, 'work:create', data.request_id, fingerprint, result)
            return result

    def add_character_version(self, owner, work_id, data):
        """新增版本並成為目前版本；舊版本保留可讀。來源參照與肖像不能在編輯時更換。"""
        operation = 'work:version:' + work_id  # 與 8445 相同的回執名稱，重送在兩邊結果一致
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            work = self._card_row(c, owner, work_id)
            require(work['status'] == 'active', 409, 'work_archived', '角色卡已封存；請先恢復再修改。')
            self._revision(work, data.expected_revision)
            require(1 <= data.base_version <= work['current_version'], 422, 'invalid_base_version', '找不到這次修改依據的版本。')
            content = data.content.model_dump(mode='json')
            current = normalized(self._card_version(c, owner, work_id, work['current_version'])['content'])
            require(content['source_references'] == current['source_references'] and content['image_ref'] == current['image_ref'],
                    409, 'managed_field', '角色卡的來源參照與肖像不能在編輯時更換。')
            version_no, now = work['current_version'] + 1, self.now().isoformat()
            c.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                      "VALUES (?,?,?,?,'human',?,?,NULL,?)", (work_id, owner, version_no, data.base_version, CARD_SCHEMA, encoded(content), now))
            c.execute('UPDATE works SET current_version=?,revision=revision+1,title=?,updated_at=? WHERE id=? AND owner_id=?',
                      (version_no, content['name'], now, work_id, owner))
            result = self._card_detail(c, owner, work_id)
            self._remember(c, owner, operation, data.request_id, fingerprint, result)
            return result

    def set_character_status(self, owner, work_id, data):
        """封存或恢復；不刪除任何版本。"""
        operation = 'work:status:' + work_id
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            work = self._card_row(c, owner, work_id)
            self._revision(work, data.expected_revision)
            c.execute('UPDATE works SET status=?,revision=revision+1,updated_at=? WHERE id=? AND owner_id=?',
                      (data.status, self.now().isoformat(), work_id, owner))
            result = self._card_detail(c, owner, work_id)
            self._remember(c, owner, operation, data.request_id, fingerprint, result)
            return result

    # ---- 引用與刪除（2026-11-10 自 8445 的 app/characters.py 移植） ----
    def _reference_map(self, c, owner):
        """本帳號所有作品版本對角色卡的引用：{角色卡 ID: {引用作品 ID: {作品資訊與引用版本}}}。任何版本（含已封存作品）引用過就算。"""
        refs = {}
        rows = c.execute('SELECT w.id,w.kind,w.title,w.status,v.version_no,v.content_json FROM works w '
                         'JOIN work_versions v ON v.work_id=w.id AND v.owner_id=w.owner_id '
                         'WHERE w.owner_id=? AND w.kind IN (' + ','.join('?' * len(REFERENCING_KINDS)) + ')',
                         (owner, *REFERENCING_KINDS)).fetchall()
        for row in rows:
            for card_id, card_version in referenced_cards(row['kind'], json.loads(row['content_json'])):
                entry = refs.setdefault(card_id, {}).setdefault(row['id'], {'work_id': row['id'], 'kind': row['kind'], 'title': row['title'],
                                                                             'status': row['status'], 'versions': set(), 'card_versions': set()})
                entry['versions'].add(row['version_no'])
                entry['card_versions'].add(card_version)
        return refs

    @staticmethod
    def _public_refs(entries):
        return sorted(({**entry, 'versions': sorted(entry['versions']), 'card_versions': sorted(entry['card_versions'])} for entry in entries.values()),
                      key=lambda item: (item['kind'], item['title']))

    def character_references(self, owner, work_id):
        with self.db.connect() as c:
            self._owned_user(c, owner)
            self._card_row(c, owner, work_id)
            return {'items': self._public_refs(self._reference_map(c, owner).get(work_id, {}))}

    def delete_character(self, owner, work_id, data):
        """角色卡只能封存與恢復，不提供永久刪除（2026-11-10 定案）。

        先確認是本人的角色卡（他人或不存在一律 404，不透露是否存在），再固定回 409 archive_only；不改任何資料。
        舊版曾刪除的卡片，其防重送紀錄仍由 _cached 回 410 work_deleted。
        """
        with self.db.connect(owner=owner) as c:
            self._card_user(c, owner)
            self._card_row(c, owner, work_id)
        require(False, 409, 'archive_only', '角色卡只能封存，不能永久刪除。需要時可以封存，之後也能恢復。')
