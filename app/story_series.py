"""多章節作品（第 2 級）：一部作品分批續寫，草稿採納之後才成為主線的下一章。

資料模型（沒有新增資料表）：
- 多章節作品是 works 的一種（kind='story_series'）。識別碼由第 1 章的作品識別碼推導，所以一件作品只會開出一部。
  內容每變動一次就新增一個版本：episodes（主線已採納的章節，依序）、checkpoint（最新的檢查點）、
  candidates（還沒採納的草稿清單，只是指標，不算劇情）、cast 與 setup（續寫時沿用的陣容與設定）。
- 一章就是一件既有的生成作品（generated_work），有自己的規劃、段落與生成紀錄。
  續寫出來的作品在 meta.series 記下屬於哪一部、接在第幾章後面，在 meta.continuity 鎖定當時繼承的內容。

規則：
- 主線只在「採納」時改變。草稿不論生成中、完成或捨棄，都不影響已定稿的章節與檢查點。
- 草稿只能接在它開始時的那個進度上；主線已經往前，舊進度上的草稿就不能採納（分支之後再做）。
- 捨棄草稿就是封存那件作品（既有的作品封存功能）；已封存的草稿不列出。
- 續寫沿用第 1 章的陣容、風格與演出要求；每一章各自鎖定當下最新的正式人物設定。
- 劇情狀態只存在作品裡，不寫回人物、人物設定、我的設定或我的經歷。
"""
import json  # 作品內容
from typing import List, Literal, Optional
import uuid  # 由第 1 章推導多章節作品的識別碼

from pydantic import Field

from .errors import require
from .generation import encoded  # 與既有服務一致的穩定 JSON
from .roleplay import GENERATED_KIND, GenerationStart, Line, SceneStart, run_view, sha256
from .schemas import Model
from .story_continuity import checkpoint, episode_outline, identity, story_so_far  # noqa: F401（story_so_far 由這裡轉出）

SERIES_KIND, SERIES_SCHEMA = 'story_series', 'story_series.v1'
SERIES_NAMESPACE = uuid.UUID('b6a0e0f2-6a4f-4e0b-9d3a-0c2a7e5d1f47')  # 固定命名空間：由第 1 章的作品識別碼推導
WORK_COLUMNS = 'id,owner_id,kind,title,status,current_version,revision,created_at,updated_at'


class SeriesOpen(Model):
    request_id: str = Field(min_length=1, max_length=128)
    work_id: str = Field(min_length=1, max_length=128)  # 已完成的生成作品：成為第 1 章


class EpisodeScene(Model):
    """這一章的場景與目標；人物、風格與演出要求沿用整部作品的設定。"""
    description: str = Field(min_length=1, max_length=2000)
    start: SceneStart = Field(default_factory=SceneStart)
    conditions: List[Line] = Field(default_factory=list, max_length=8)


class EpisodeOutput(Model):
    length: Literal['short', 'medium', 'long'] = 'short'
    form: Literal['script', 'narrative'] = 'script'


class EpisodeStart(Model):
    request_id: str = Field(min_length=1, max_length=128)
    title: str = Field(default='', max_length=60)  # 空白時使用 AI 規劃的標題
    scene: EpisodeScene
    output: Optional[EpisodeOutput] = None  # 沒有指定就沿用第 1 章的長度與呈現形式


class EpisodeAdopt(Model):
    request_id: str = Field(min_length=1, max_length=128)


def series_id_for(work_id):
    """第 1 章的作品識別碼 → 多章節作品的識別碼（不需要另外的對照欄位或資料表）。"""
    return str(uuid.uuid5(SERIES_NAMESPACE, 'story_series:' + work_id))


class StorySeriesMixin:
    """擴充 LifeWorld；所有查詢都以 owner 過濾，別人的或不存在的一律 404。"""

    def _series_row(self, c, owner, series_id):
        row = c.execute('SELECT ' + WORK_COLUMNS + ' FROM works WHERE id=? AND owner_id=? AND kind=?', (series_id, owner, SERIES_KIND)).fetchone()
        require(row is not None, 404, 'not_found', '找不到這部多章節作品。')
        version = c.execute('SELECT content_json FROM work_versions WHERE work_id=? AND owner_id=? AND version_no=?',
                            (series_id, owner, row['current_version'])).fetchone()
        return row, json.loads(version['content_json'])

    def _series_save(self, c, owner, row, content):
        """新增一個版本（只增不改）。"""
        now, version_no = self.now().isoformat(), row['current_version'] + 1
        c.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                  "VALUES (?,?,?,?,'human',?,?,NULL,?)", (row['id'], owner, version_no, row['current_version'], SERIES_SCHEMA, encoded(content), now))
        c.execute('UPDATE works SET current_version=?,revision=revision+1,updated_at=? WHERE id=? AND owner_id=?', (version_no, now, row['id'], owner))

    def _series_detail(self, c, owner, series_id):
        """畫面用的總覽：已定稿的章節、還在處理的草稿、下一章是第幾章。"""
        row, content = self._series_row(c, owner, series_id)
        mainline = len(content['episodes'])
        drafts = []
        for item in content['candidates']:
            work = c.execute('SELECT ' + WORK_COLUMNS + ' FROM works WHERE id=? AND owner_id=? AND kind=?', (item['work_id'], owner, GENERATED_KIND)).fetchone()
            if work is None or work['status'] != 'active':
                continue  # 已捨棄（封存）的草稿不列出
            run = self._roleplay_content(c, owner, work)['run']
            saved = c.execute('SELECT count(*) FROM session_turns WHERE owner_id=? AND work_id=?', (owner, work['id'])).fetchone()[0]
            drafts.append({'work_id': work['id'], 'title': work['title'], 'run_status': run['status'], 'completed_segments': saved,
                           'total_segments': run['total_segments'], 'base_episode_no': item['base_episode_no'],
                           # 只有已完成、而且接在目前主線最後一章後面的草稿可以採納
                           'can_adopt': run['status'] == 'completed' and item['base_episode_no'] == mainline, 'created_at': work['created_at']})
        return {'id': row['id'], 'title': row['title'], 'status': row['status'], 'revision': row['revision'], 'version_no': row['current_version'],
                'cast': [{key: member[key] for key in ('name', 'source', 'position', 'is_user')} for member in content['cast']],
                'episodes': [{key: episode[key] for key in ('no', 'work_id', 'title', 'segments', 'adopted_at')} for episode in content['episodes']],
                'drafts': drafts, 'next_episode_no': mainline + 1,
                # 這部作品的長度與呈現形式（第 1 章選的）：續寫表單用它當預設，否則第 1 章是小說敘事、下一章卻變成劇本對白
                'output': content['setup'].get('output')}

    def _series_ref(self, c, owner, work, content):
        """作品頁用：這件作品屬於哪一部多章節作品、是第幾章，或還是草稿；不屬於任何一部就回 None。"""
        linked = ((content.get('meta') or {}).get('series') or {}).get('series_id')
        series_id = linked or series_id_for(work['id'])
        row = c.execute('SELECT title,current_version FROM works WHERE id=? AND owner_id=? AND kind=?', (series_id, owner, SERIES_KIND)).fetchone()
        if row is None:
            return None
        episodes = json.loads(c.execute('SELECT content_json FROM work_versions WHERE work_id=? AND owner_id=? AND version_no=?',
                                        (series_id, owner, row['current_version'])).fetchone()['content_json'])['episodes']
        number = next((episode['no'] for episode in episodes if episode['work_id'] == work['id']), None)
        return {'id': series_id, 'title': row['title'], 'episode_no': number, 'is_draft': number is None}

    def series_detail(self, owner, series_id):
        with self.db.connect() as c:
            self._ai_user(c, owner)
            return self._series_detail(c, owner, series_id)

    def open_series(self, owner, data):
        """把一件已完成的作品開成多章節作品（它是第 1 章）；已經開過，或這件作品本身就是某一部的章節，就回那一部。"""
        with self.db.connect(write=True, owner=owner) as c:
            self._ai_user(c, owner)
            cached, fingerprint = self._cached(c, owner, 'series:open', data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            work = self._roleplay_work(c, owner, data.work_id)
            require(work['kind'] == GENERATED_KIND, 409, 'series_not_supported', '這件是舊版的作品，不能續寫。')
            content = self._roleplay_content(c, owner, work)
            require(content['run']['status'] == 'completed', 409, 'work_not_completed', '作品完成之後才能續寫下一章。')
            linked = (content['meta'].get('series') or {}).get('series_id')
            series_id = linked or series_id_for(work['id'])
            if c.execute('SELECT 1 FROM works WHERE id=? AND owner_id=? AND kind=?', (series_id, owner, SERIES_KIND)).fetchone() is None:
                turns, view, now = self._roleplay_turns(c, owner, work['id']), run_view(content), self.now().isoformat()
                participants = [{'source': item['source'], 'position': item.get('position'),
                                 # 人物只記是誰：每一章開始時各自鎖定當下最新的人物設定；角色卡沿用原本的版本
                                 'ref': {'person_id': item['ref']['person_id']} if item['source'] == 'person' else item['ref']}
                                for item in content['setup']['participants']]
                series = {'schema': SERIES_SCHEMA, 'root_work_id': work['id'],
                          'cast': [{'key': identity(member), 'name': member['name'], 'source': member['source'], 'position': member.get('position'),
                                    'is_user': member['source'] == 'self'} for member in view['cast']],
                          'setup': {'participants': participants, 'include_me': content['setup']['include_me'],
                                    'style_profile': content['setup']['style_profile'], 'direction': content['setup'].get('direction'),
                                    'output': content['setup']['output']['text']},
                          'episodes': [{'no': 1, 'work_id': work['id'], 'title': work['title'], 'segments': len(turns), 'adopted_at': now,
                                        'outline': episode_outline(1, content['plan'], view['scene'])}],
                          'checkpoint': checkpoint(view['cast'], turns), 'candidates': []}
                c.execute("INSERT INTO works(id,owner_id,kind,title,status,current_version,revision,created_at,updated_at) VALUES (?,?,?,?,'active',1,1,?,?)",
                          (series_id, owner, SERIES_KIND, work['title'], now, now))
                c.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                          "VALUES (?,?,1,NULL,'human',?,?,NULL,?)", (series_id, owner, SERIES_SCHEMA, encoded(series), now))
            result = self._series_detail(c, owner, series_id)
            self._remember(c, owner, 'series:open', data.request_id, fingerprint, result)
            return result

    def start_series_episode(self, owner, series_id, data, provider_name=None):
        """續寫下一章：建立一件草稿作品（排隊中），鎖定當時繼承的內容，並記進草稿清單。排入第一個 Task 由路由在交易提交後進行。

        陣容、風格與演出要求沿用整部作品；人物能不能出場（已封存、沒有人物設定、撤回同意）照一般作品的規則檢查。
        """
        with self.db.connect() as c:
            self._ai_user(c, owner)
            row, series = self._series_row(c, owner, series_id)
        base_version, mainline = row['current_version'], len(series['episodes'])
        output = data.output.model_dump() if data.output else series['setup']['output']
        setup = {'participants': series['setup']['participants'], 'include_me': series['setup']['include_me'], 'title': data.title,
                 'scene_context': data.scene.model_dump(mode='json'), 'style_profile': series['setup']['style_profile'],
                 'output': {'type': 'text', 'text': output}}
        if series['setup'].get('direction'):
            setup['direction'] = series['setup']['direction']
        start = GenerationStart.model_validate({'request_id': data.request_id, 'setup': setup})
        continuity = {'episodes': [episode['outline'] for episode in series['episodes']], **series['checkpoint']}
        continuity['sha256'] = sha256(continuity)

        def prepare(c):
            fresh, _ = self._series_row(c, owner, series_id)
            require(fresh['current_version'] == base_version, 409, 'series_changed', '這部作品剛剛有變動，請重新整理後再試一次。')
            return {'series': {'series_id': series_id, 'base_episode_no': mainline, 'base_work_id': series['episodes'][-1]['work_id']},
                    'continuity': continuity}

        def after(c, result):
            fresh, content = self._series_row(c, owner, series_id)
            content['candidates'].append({'work_id': result['id'], 'base_episode_no': mainline})
            self._series_save(c, owner, fresh, content)
            result.update(series_id=series_id, base_episode_no=mainline)

        return self.start_generation(owner, start, provider_name, operation='series:episode:' + series_id, prepare=prepare, after=after)

    def adopt_series_episode(self, owner, series_id, work_id, data):
        """採納一份草稿成為主線的下一章：新增一個版本，更新章節清單與檢查點。只有這個動作會改變主線。"""
        operation = 'series:adopt:' + series_id
        with self.db.connect(write=True, owner=owner) as c:
            self._ai_user(c, owner)
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, {'work_id': work_id, **data.model_dump(mode='json')})
            if cached:
                return cached
            row, series = self._series_row(c, owner, series_id)
            mainline = len(series['episodes'])
            require(not any(episode['work_id'] == work_id for episode in series['episodes']), 409, 'already_adopted', '這一章已經在主線裡了。')
            candidate = next((item for item in series['candidates'] if item['work_id'] == work_id), None)
            require(candidate is not None, 404, 'not_found', '找不到這份草稿。')
            work = self._roleplay_work(c, owner, work_id)
            content = self._roleplay_content(c, owner, work)
            require(content['run']['status'] == 'completed', 409, 'work_not_completed', '草稿生成完成之後才能採納。')
            require(candidate['base_episode_no'] == mainline, 409, 'series_base_changed',
                    f"這份草稿是接在第 {candidate['base_episode_no']} 章後面寫的，主線已經到第 {mainline} 章，不能採納。")
            require(work['status'] == 'active', 409, 'draft_discarded', '這份草稿已經捨棄；恢復之後才能採納。')
            turns = self._roleplay_turns(c, owner, work_id)
            series['episodes'].append({'no': mainline + 1, 'work_id': work_id, 'title': work['title'], 'segments': len(turns),
                                       'adopted_at': self.now().isoformat(),
                                       'outline': episode_outline(mainline + 1, content['plan'], run_view(content)['scene'])})
            series['checkpoint'] = checkpoint(run_view(content)['cast'], turns, series['checkpoint'])
            series['candidates'] = [item for item in series['candidates'] if item['work_id'] != work_id]
            self._series_save(c, owner, row, series)
            result = self._series_detail(c, owner, series_id)
            self._remember(c, owner, operation, data.request_id, fingerprint, result)
            return result
