"""F04 故事開場（2026-11-10 自 8445 的 app/works.py 移植）：保存 AI 產生的故事開場、改版、讀回。

規則與 8445 相同：
- 故事開場只能引用本人角色卡的既有版本；新故事不能用已封存的角色卡。
- 引用 AI 原稿時，角色卡來源必須與生成紀錄一致；內容與原稿相同記為 ai，修改過記為 ai_edited。
- 同一篇故事的角色卡來源固定，改版不能更換；版本只新增、不改寫。
"""
import json
from typing import Optional
from uuid import uuid4

from pydantic import Field, StrictInt

from .character_cards import encoded
from .errors import require
from .gen_schemas import StoryOpeningContent
from .schemas import Model

STORY_KIND, STORY_SCHEMA = 'story_opening', 'story_opening.v1'


class StoryCreate(Model):
    request_id: str = Field(min_length=1, max_length=128)
    content: StoryOpeningContent
    generation_id: Optional[str] = Field(default=None, min_length=1, max_length=128)


class StoryVersionCreate(Model):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)
    base_version: StrictInt = Field(ge=1)
    content: StoryOpeningContent
    generation_id: Optional[str] = Field(default=None, min_length=1, max_length=128)


class StoriesMixin:
    """擴充 LifeWorld；所有查詢都以 owner 過濾，查不到一律 404。"""

    @staticmethod
    def _story_generation(c, owner, generation_id):
        if not generation_id:
            return None
        row = c.execute('SELECT * FROM ai_generations WHERE id=? AND owner_id=?', (generation_id, owner)).fetchone()
        require(row is not None, 404, 'not_found', '找不到可存取的生成紀錄。')
        require(row['status'] == 'succeeded' and row['module'] == STORY_KIND and row['output_json'] is not None,
                409, 'generation_not_usable', '這次生成沒有可用的故事開場，請重新生成或改為手動填寫。')
        return row

    @staticmethod
    def _check_story_source(c, owner, content, generation, fixed_source=None):
        source = content['source']
        work = c.execute('SELECT id,kind,status FROM works WHERE id=? AND owner_id=?', (source['character_work_id'], owner)).fetchone()
        require(work is not None, 404, 'not_found', '找不到可存取的角色卡。')
        require(work['kind'] == 'character_card', 422, 'source_not_character_card', '故事開場只能引用角色卡作品。')
        if fixed_source is None:
            require(work['status'] == 'active', 409, 'character_archived', '角色已封存，不能用於新故事；請先恢復。')
        version = c.execute('SELECT content_json FROM work_versions WHERE work_id=? AND owner_id=? AND version_no=?',
                            (work['id'], owner, source['character_version'])).fetchone()
        require(version is not None, 404, 'not_found', '找不到指定的角色卡版本。')
        require(json.loads(version['content_json'])['name'] == source['character_name'], 409, 'source_mismatch', '故事引用的角色名稱與該版本角色卡不符。')
        if generation is not None:
            used = json.loads(generation['input_json'])
            require(used.get('character_work_id') == source['character_work_id'] and used.get('character_version') == source['character_version'],
                    409, 'source_mismatch', '故事內容的角色卡來源與這次生成紀錄不符。')
        if fixed_source is not None:
            require(fixed_source == source, 409, 'source_mismatch', '同一個故事作品的角色卡來源不能改變；要換角色請另建新作品。')

    @staticmethod
    def _story_origin(content, generation):
        if generation is None:
            return 'human'
        return 'ai' if encoded(content) == encoded(json.loads(generation['output_json'])) else 'ai_edited'

    def create_story(self, owner, data):
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, 'work:create', data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            content = data.content.model_dump(mode='json')
            generation = self._story_generation(c, owner, data.generation_id)
            self._check_story_source(c, owner, content, generation)
            work_id, now = str(uuid4()), self.now().isoformat()
            c.execute("INSERT INTO works(id,owner_id,kind,title,status,current_version,revision,created_at,updated_at) VALUES (?,?,?,?,'active',1,1,?,?)",
                      (work_id, owner, STORY_KIND, content['title'], now, now))
            c.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                      'VALUES (?,?,1,NULL,?,?,?,?,?)', (work_id, owner, self._story_origin(content, generation), STORY_SCHEMA, encoded(content), data.generation_id, now))
            result = self._work_detail(c, owner, work_id)
            self._remember(c, owner, 'work:create', data.request_id, fingerprint, result)
            return result

    def add_story_version(self, owner, work_id, data):
        operation = 'work:version:' + work_id
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            work = self._work_row(c, owner, work_id)
            require(work['kind'] == STORY_KIND, 404, 'not_found', '找不到可存取的故事開場。')
            require(work['status'] == 'active', 409, 'work_archived', '作品已封存；請先恢復再修改。')
            require(data.base_version == work['current_version'], 409, 'stale_version',
                    f"這篇故事已在其他地方更新為 v{work['current_version']}；為避免覆蓋，這次沒有保存。請重新載入最新版本後再修改。")
            self._revision(work, data.expected_revision)
            content = data.content.model_dump(mode='json')
            current = json.loads(c.execute('SELECT content_json FROM work_versions WHERE work_id=? AND owner_id=? AND version_no=?',
                                           (work_id, owner, work['current_version'])).fetchone()['content_json'])
            generation = self._story_generation(c, owner, data.generation_id)
            self._check_story_source(c, owner, content, generation, current['source'])
            version_no, now = work['current_version'] + 1, self.now().isoformat()
            c.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                      'VALUES (?,?,?,?,?,?,?,?,?)', (work_id, owner, version_no, data.base_version, self._story_origin(content, generation),
                                                     STORY_SCHEMA, encoded(content), data.generation_id, now))
            c.execute('UPDATE works SET current_version=?,revision=revision+1,title=?,updated_at=? WHERE id=? AND owner_id=?',
                      (version_no, content['title'], now, work_id, owner))
            result = self._work_detail(c, owner, work_id)
            self._remember(c, owner, operation, data.request_id, fingerprint, result)
            return result
