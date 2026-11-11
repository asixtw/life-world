"""F06A 人物演繹的作品保存（2026-11-10 自 8445 的 app/works.py 移植）：人物演繹作品、改版、互動試演逐來回保存與結束。

規則與 8445 相同（app/portrayal.py 的檢查原樣沿用），但互動試演的內容由伺服器組出，前端只送 ID：
- 人物演繹作品必須來自一次成功的 person_portrayal 生成；來源（人物、選取的資料、快照雜湊）與生成紀錄相同，之後的版本不能更換來源。
  內容與 AI 原稿相同記為 ai，人工修改過記為 ai_edited。
- 互動試演引用本人人物演繹的某個版本；每個來回原樣保存 portrayal_reply 的生成結果，第 6 個來回同時結束，使用者可提早結束。
- 轉為角色卡：只轉入使用者勾選的段落，記錄來源快照、AI 推論標記與使用者確認；不複製人物事實，也不回寫人物資料。
- AI 推論不寫回人物、人物資訊或筆記；版本只新增、不改寫；同一 request_id 重送回原結果。
"""
import json
from typing import Optional
from uuid import uuid4

from pydantic import Field, StrictInt

from .character_cards import encoded
from .errors import require
from .gen_schemas import PORTRAYAL_MAX_TURNS, PersonPortrayalContent, PortrayalScenario, PortrayalSessionContent, PortrayalToCard  # noqa: F401（路由使用）
from .portrayal import (SCENARIO_LABELS, check_portrayal_session_start, check_portrayal_work, portrayal_generation_id,
                        portrayal_source, portrayal_title)
from .schemas import Model

PORTRAYAL_KIND, SESSION_KIND = 'person_portrayal', 'portrayal_session'


class PortrayalCreate(Model):
    request_id: str = Field(min_length=1, max_length=128)
    generation_id: str = Field(min_length=1, max_length=128)
    content: Optional[PersonPortrayalContent] = None  # 省略時原樣保存 AI 原稿


class PortrayalVersionCreate(Model):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)
    base_version: StrictInt = Field(ge=1)
    content: PersonPortrayalContent


class PortrayalSessionStart(Model):
    request_id: str = Field(min_length=1, max_length=128)
    portrayal_work_id: str = Field(min_length=1, max_length=128)
    portrayal_version: StrictInt = Field(ge=1)
    scenario: PortrayalScenario


class PortrayalTurnSave(Model):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)
    generation_id: str = Field(min_length=1, max_length=128)


class PortrayalSessionEnd(Model):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)


class PortrayalsMixin:
    """擴充 LifeWorld；所有查詢都以 owner 過濾，查不到一律 404。"""

    @staticmethod
    def _portrayal_generation(c, owner, generation_id, module):
        row = c.execute('SELECT * FROM ai_generations WHERE id=? AND owner_id=?', (generation_id, owner)).fetchone()
        require(row is not None, 404, 'not_found', '找不到可存取的生成紀錄。')
        require(row['status'] == 'succeeded' and row['module'] == module and row['output_json'] is not None,
                409, 'generation_not_usable', '這次生成沒有可用的內容，請重新生成。')
        return row

    def _kind_row(self, c, owner, work_id, kind):
        work = self._work_row(c, owner, work_id)
        require(work['kind'] == kind, 404, 'not_found', '找不到可存取的作品。')
        return work

    @staticmethod
    def _current_content(c, owner, work):
        return json.loads(c.execute('SELECT content_json FROM work_versions WHERE work_id=? AND owner_id=? AND version_no=?',
                                    (work['id'], owner, work['current_version'])).fetchone()['content_json'])

    def _insert_work(self, c, owner, kind, title, schema, content, origin, generation_id):
        work_id, now = str(uuid4()), self.now().isoformat()
        c.execute("INSERT INTO works(id,owner_id,kind,title,status,current_version,revision,created_at,updated_at) VALUES (?,?,?,?,'active',1,1,?,?)",
                  (work_id, owner, kind, title, now, now))
        c.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                  'VALUES (?,?,1,NULL,?,?,?,?,?)', (work_id, owner, origin, schema, encoded(content), generation_id, now))
        return work_id

    def _insert_version(self, c, owner, work, base_version, origin, schema, content, generation_id, title):
        version_no, now = work['current_version'] + 1, self.now().isoformat()
        c.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                  'VALUES (?,?,?,?,?,?,?,?,?)', (work['id'], owner, version_no, base_version, origin, schema, encoded(content), generation_id, now))
        c.execute('UPDATE works SET current_version=?,revision=revision+1,title=?,updated_at=? WHERE id=? AND owner_id=?',
                  (version_no, title, now, work['id'], owner))

    def create_portrayal(self, owner, data):
        """保存人物演繹：來源必須與生成紀錄相同；內容可以先人工修改。"""
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, 'work:create', data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            generation = self._portrayal_generation(c, owner, data.generation_id, PORTRAYAL_KIND)
            original = json.loads(generation['output_json'])
            content = data.content.model_dump(mode='json') if data.content is not None else original
            check_portrayal_work(content, generation)
            origin = 'ai' if encoded(content) == encoded(original) else 'ai_edited'
            work_id = self._insert_work(c, owner, PORTRAYAL_KIND, portrayal_title(content), 'person_portrayal.v1', content, origin, generation['id'])
            result = self._work_detail(c, owner, work_id)
            self._remember(c, owner, 'work:create', data.request_id, fingerprint, result)
            return result

    def add_portrayal_version(self, owner, work_id, data):
        """人工修改人物詮釋：來源固定；新版本與原始 AI 原稿比較來判定 ai／ai_edited。"""
        operation = 'work:version:' + work_id
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            work = self._kind_row(c, owner, work_id, PORTRAYAL_KIND)
            require(work['status'] == 'active', 409, 'work_archived', '作品已封存；請先恢復再修改。')
            require(data.base_version == work['current_version'], 409, 'stale_version',
                    f"這份人物演繹已在其他地方更新為 v{work['current_version']}；為避免覆蓋，這次沒有保存。請重新載入最新版本後再修改。")
            self._revision(work, data.expected_revision)
            content = data.content.model_dump(mode='json')
            generation_id = portrayal_generation_id(c, owner, work_id, work['current_version'])
            require(generation_id is not None, 409, 'source_mismatch', '找不到人物演繹原始生成的來源快照。')
            generation = self._portrayal_generation(c, owner, generation_id, PORTRAYAL_KIND)
            check_portrayal_work(content, generation, self._current_content(c, owner, work))
            origin = 'ai' if encoded(content) == encoded(json.loads(generation['output_json'])) else 'ai_edited'
            self._insert_version(c, owner, work, data.base_version, origin, 'person_portrayal.v1', content, generation_id, portrayal_title(content))
            result = self._work_detail(c, owner, work_id)
            self._remember(c, owner, operation, data.request_id, fingerprint, result)
            return result

    def start_portrayal_session(self, owner, data):
        """開始互動試演：引用本人人物演繹的某個版本與情境，建立尚未對話的紀錄。"""
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, 'work:create', data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            work = self._kind_row(c, owner, data.portrayal_work_id, PORTRAYAL_KIND)
            require(work['status'] == 'active', 409, 'work_archived', '人物演繹已封存；請先恢復再開始試演。')
            version = self._work_version(c, owner, work['id'], data.portrayal_version)
            name = version['content']['source']['person_name']
            scenario = data.scenario.model_dump(mode='json')
            content = PortrayalSessionContent.model_validate({
                'title': f"{name}｜{SCENARIO_LABELS[scenario['kind']]}",
                'portrayal': {'work_id': work['id'], 'version_no': data.portrayal_version, 'person_name': name},
                'scenario': scenario, 'status': 'active', 'ending': None, 'turns': []}).model_dump(mode='json')
            check_portrayal_session_start(c, owner, content)
            work_id = self._insert_work(c, owner, SESSION_KIND, content['title'], 'portrayal_session.v1', content, 'human', None)
            result = self._work_detail(c, owner, work_id)
            self._remember(c, owner, 'work:create', data.request_id, fingerprint, result)
            return result

    def _session_for_update(self, c, owner, work_id, expected_revision):
        work = self._kind_row(c, owner, work_id, SESSION_KIND)
        require(work['status'] == 'active', 409, 'work_archived', '互動試演已封存；請先恢復再繼續。')
        self._revision(work, expected_revision)
        current = self._current_content(c, owner, work)
        require(current['status'] == 'active', 409, 'session_ended', '這段互動試演已經結束，不能再修改。')
        return work, current

    def save_portrayal_turn(self, owner, work_id, data):
        """把一次成功的人物回應原樣追加為下一個來回；第 6 個來回同時結束。"""
        operation = 'work:version:' + work_id
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            work, current = self._session_for_update(c, owner, work_id, data.expected_revision)
            generation = self._portrayal_generation(c, owner, data.generation_id, 'portrayal_reply')
            used = json.loads(generation['input_json'])
            turn_no = len(current['turns']) + 1
            require(used.get('session_work_id') == work_id and used.get('session_version') == work['current_version'] and used.get('turn_no') == turn_no,
                    409, 'stale_session', '這次人物回應不是依目前的互動試演產生；請重新整理後再送出。')
            turn = {'turn_no': turn_no, 'message': used.get('message'), 'reply': json.loads(generation['output_json']),
                    'generation_id': generation['id'], 'provider_kind': generation['provider_kind']}
            ended = turn_no == PORTRAYAL_MAX_TURNS
            content = PortrayalSessionContent.model_validate({**current, 'turns': current['turns'] + [turn], 'status': 'ended' if ended else 'active',
                                                              'ending': 'turn_limit' if ended else None}).model_dump(mode='json')
            self._insert_version(c, owner, work, work['current_version'], 'ai', 'portrayal_session.v1', content, generation['id'], content['title'])
            result = self._work_detail(c, owner, work_id)
            self._remember(c, owner, operation, data.request_id, fingerprint, result)
            return result

    def end_portrayal_session(self, owner, work_id, data):
        """使用者主動結束：已保存的對話不變，只新增一個結束版本。"""
        operation = 'work:version:' + work_id
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            work, current = self._session_for_update(c, owner, work_id, data.expected_revision)
            content = {**current, 'status': 'ended', 'ending': 'player_ended'}
            self._insert_version(c, owner, work, work['current_version'], 'human', 'portrayal_session.v1', content, None, content['title'])
            result = self._work_detail(c, owner, work_id)
            self._remember(c, owner, operation, data.request_id, fingerprint, result)
            return result

    def portrayal_to_card(self, owner, data):
        """人物演繹結果轉為角色卡（與 8445 相同）：只轉入勾選段落；記錄來源快照、AI 推論標記與使用者確認；不複製人物事實，也不回寫人物資料。"""
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, 'character:from_portrayal', data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            work = self._kind_row(c, owner, data.portrayal_work_id, PORTRAYAL_KIND)
            portrayal, _, generation_id = portrayal_source(c, owner, {'work_id': work['id'], 'version_no': data.version_no})
            profile, source = portrayal['profile'], portrayal['source']
            person = c.execute('SELECT id FROM people WHERE id=? AND owner_id=?', (source['person_id'], owner)).fetchone()
            require(person is not None, 409, 'source_unavailable', '這份人物演繹的來源人物已不存在，不能再轉入。')
            sections = set(data.sections)

            def texts(key):
                return '；'.join(item['text'] for item in profile.get(key) or []) if key in sections else ''

            content = {'name': source['person_name'][:60], 'kind': 'fictional', 'inspirations': ['real_person'],
                       'tagline': profile['summary'] if 'summary' in sections else '',
                       'personality': texts('traits'), 'motivation': texts('motivations'), 'values': texts('values'),
                       'voice': profile['speaking_style']['text'] if 'speaking_style' in sections else '',
                       'behavior': '；'.join(part for part in (texts('behaviors'), texts('emotional_reactions')) if part),
                       'knowledge_boundary': profile['knowledge_boundary'] if 'knowledge_boundary' in sections else '',
                       'sample_lines': [f"（{item['situation']}）{item['line']}" for item in profile['sample_dialogues']][:3]
                       if 'sample_dialogues' in sections else [],
                       'source_references': [{'kind': 'person_portrayal', 'id': work['id'], 'version': str(data.version_no),
                                               'name': source['person_name'][:60], 'ai_inferred': True,
                                               'snapshot_sha256': source['snapshot_sha256'], 'generation_id': generation_id,
                                               'acknowledged_at': self.now().isoformat(),
                                               'note': '使用者確認：轉入內容是 AI 依所選資料推論的演出設定，不是真人事實。'}]}
            work_id = self._insert_card(c, owner, content)
            result = self._card_detail(c, owner, work_id)
            self._remember(c, owner, 'character:from_portrayal', data.request_id, fingerprint, result)
            return result

    def portrayal_snapshot_view(self, owner, work_id, version_no):
        """回讀人物演繹版本使用的來源快照（代號對應的原文），供畫面顯示「依據」；只限本人。"""
        with self.db.connect() as c:
            self._owned_user(c, owner)
            self._kind_row(c, owner, work_id, PORTRAYAL_KIND)
            generation_id = portrayal_generation_id(c, owner, work_id, version_no)
            require(generation_id is not None, 404, 'not_found', '找不到人物演繹的來源快照。')
            row = c.execute("SELECT input_json FROM ai_generations WHERE id=? AND owner_id=? AND module='person_portrayal'", (generation_id, owner)).fetchone()
            require(row is not None, 404, 'not_found', '找不到人物演繹的來源快照。')
            snapshot = json.loads(row['input_json']).get('snapshot') or []
            return {'items': [{key: item[key] for key in ('ref', 'kind', 'label', 'text')} for item in snapshot]}
