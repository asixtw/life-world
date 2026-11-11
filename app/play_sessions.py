"""F05 短篇互動（2026-11-10 自 8445 的 app/works.py 移植）：從故事開場開始冒險，每回合 AI 角色回應（character_reply v3），確認後逐回合保存。

規則與 8445 相同，但互動紀錄的內容由伺服器組出，前端只送 ID：
- 開始：引用本人故事開場的某個版本；角色卡版本與目標取自該故事版本；角色卡必須仍在使用中。
- 回合：只能追加一個與生成紀錄完全相同的回合（行動、台詞、場景、選項、Provider 類型），不能人工改寫；
  生成必須依目前版本與下一個回合編號；第 5 回合保存時同時結束（turn_limit）。
- 結束：玩家可以在第 5 回合前主動結束（player_ended）；結束後不能再修改。
- 版本只新增、不改寫；同一 request_id 重送回原結果。
"""
import json
from uuid import uuid4

from pydantic import Field, StrictInt

from .character_cards import encoded
from .errors import require
from .gen_schemas import SESSION_MAX_TURNS, StorySessionContent
from .schemas import Model

SESSION_KIND, SESSION_MODULE = 'story_session', 'character_reply'


def session_schema(content):
    """與 8445 相同：含 v3 回合（有 player_action）標為 story_session.v3，含 v2 結算標為 v2，其餘 v1；舊版本不改寫。"""
    resolutions = [turn['action_resolution'] for turn in content['turns'] if turn.get('action_resolution')]
    if any('player_action' in resolution for resolution in resolutions):
        return 'story_session.v3'
    return 'story_session.v2' if resolutions else 'story_session.v1'


class SessionStart(Model):
    request_id: str = Field(min_length=1, max_length=128)
    story_work_id: str = Field(min_length=1, max_length=128)
    story_version: StrictInt = Field(ge=1)


class SessionTurnSave(Model):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)
    generation_id: str = Field(min_length=1, max_length=128)


class SessionEnd(Model):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)


class PlaySessionsMixin:
    """擴充 LifeWorld；所有查詢都以 owner 過濾，查不到一律 404。"""

    def _session_row(self, c, owner, work_id):
        work = self._work_row(c, owner, work_id)
        require(work['kind'] == SESSION_KIND, 404, 'not_found', '找不到可存取的互動紀錄。')
        return work

    @staticmethod
    def _session_content(c, owner, work):
        row = c.execute('SELECT content_json FROM work_versions WHERE work_id=? AND owner_id=? AND version_no=?',
                        (work['id'], owner, work['current_version'])).fetchone()
        return json.loads(row['content_json'])

    def _append_session_version(self, c, owner, work, content, origin, generation_id):
        content = StorySessionContent.model_validate(content).model_dump(mode='json')  # 與 8445 相同的內容結構檢查
        version_no, now = work['current_version'] + 1, self.now().isoformat()
        c.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                  'VALUES (?,?,?,?,?,?,?,?,?)', (work['id'], owner, version_no, work['current_version'], origin, session_schema(content),
                                                 encoded(content), generation_id, now))
        c.execute('UPDATE works SET current_version=?,revision=revision+1,updated_at=? WHERE id=? AND owner_id=?',
                  (version_no, now, work['id'], owner))

    def start_session(self, owner, data):
        """開始冒險：建立尚未進行回合的互動紀錄（第 1 版）。"""
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, 'work:create', data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            story_work = c.execute('SELECT id,kind,status FROM works WHERE id=? AND owner_id=?', (data.story_work_id, owner)).fetchone()
            require(story_work is not None, 404, 'not_found', '找不到可存取的故事開場。')
            require(story_work['kind'] == 'story_opening', 422, 'source_not_story_opening', '互動冒險只能從故事開場作品開始。')
            require(story_work['status'] == 'active', 409, 'work_archived', '故事開場已封存；請先恢復再開始冒險。')
            row = c.execute('SELECT content_json FROM work_versions WHERE work_id=? AND owner_id=? AND version_no=?',
                            (story_work['id'], owner, data.story_version)).fetchone()
            require(row is not None, 404, 'not_found', '找不到指定的故事開場版本。')
            story = json.loads(row['content_json'])
            source = story['source']
            actor = c.execute("SELECT status FROM works WHERE id=? AND owner_id=? AND kind='character_card'",
                              (source['character_work_id'], owner)).fetchone()
            require(actor is not None, 404, 'not_found', '找不到可存取的角色卡。')
            require(actor['status'] == 'active', 409, 'character_archived', '角色已封存，不能用於新冒險；請先恢復。')
            content = StorySessionContent.model_validate({
                'title': story['title'], 'story': {'work_id': story_work['id'], 'version_no': data.story_version, 'title': story['title']},
                'character': {'work_id': source['character_work_id'], 'version_no': source['character_version'], 'name': source['character_name']},
                'objective': story['objective'], 'status': 'active', 'ending': None, 'turns': []}).model_dump(mode='json')
            work_id, now = str(uuid4()), self.now().isoformat()
            c.execute("INSERT INTO works(id,owner_id,kind,title,status,current_version,revision,created_at,updated_at) VALUES (?,?,?,?,'active',1,1,?,?)",
                      (work_id, owner, SESSION_KIND, content['title'], now, now))
            c.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                      "VALUES (?,?,1,NULL,'human',?,?,NULL,?)", (work_id, owner, session_schema(content), encoded(content), now))
            result = self._work_detail(c, owner, work_id)
            self._remember(c, owner, 'work:create', data.request_id, fingerprint, result)
            return result

    def save_session_turn(self, owner, work_id, data):
        """把一次成功的角色回應原樣追加為下一回合；第 5 回合同時結束。"""
        operation = 'work:version:' + work_id
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            work = self._session_row(c, owner, work_id)
            require(work['status'] == 'active', 409, 'work_archived', '互動紀錄已封存；請先恢復再繼續。')
            self._revision(work, data.expected_revision)
            current = self._session_content(c, owner, work)
            require(current['status'] == 'active', 409, 'session_ended', '這段冒險已經結束，不能再修改。')
            generation = c.execute('SELECT * FROM ai_generations WHERE id=? AND owner_id=?', (data.generation_id, owner)).fetchone()
            require(generation is not None, 404, 'not_found', '找不到可存取的生成紀錄。')
            require(generation['status'] == 'succeeded' and generation['module'] == SESSION_MODULE and generation['output_json'] is not None,
                    409, 'generation_not_usable', '這次角色回應沒有可用的內容，請重新生成。')
            used = json.loads(generation['input_json'])
            turn_no = len(current['turns']) + 1
            require(used.get('session_work_id') == work_id and used.get('session_version') == work['current_version'] and used.get('turn_no') == turn_no,
                    409, 'stale_session', '這次角色回應不是依目前的互動紀錄產生；請重新整理後再行動。')
            turn = {**json.loads(generation['output_json']), 'turn_no': turn_no, 'action': used.get('resolved_action'),
                    'generation_id': generation['id'], 'provider_kind': generation['provider_kind']}
            ended = turn_no == SESSION_MAX_TURNS
            content = {**current, 'turns': current['turns'] + [turn], 'status': 'ended' if ended else 'active', 'ending': 'turn_limit' if ended else None}
            self._append_session_version(c, owner, work, content, 'ai', generation['id'])
            result = self._work_detail(c, owner, work_id)
            self._remember(c, owner, operation, data.request_id, fingerprint, result)
            return result

    def end_session(self, owner, work_id, data):
        """玩家主動結束：已保存的回合不變，只新增一個結束版本。"""
        operation = 'work:version:' + work_id
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            work = self._session_row(c, owner, work_id)
            require(work['status'] == 'active', 409, 'work_archived', '互動紀錄已封存；請先恢復再繼續。')
            self._revision(work, data.expected_revision)
            current = self._session_content(c, owner, work)
            require(current['status'] == 'active', 409, 'session_ended', '這段冒險已經結束，不能再修改。')
            self._append_session_version(c, owner, work, {**current, 'status': 'ended', 'ending': 'player_ended'}, 'human', None)
            result = self._work_detail(c, owner, work_id)
            self._remember(c, owner, operation, data.request_id, fingerprint, result)
            return result
