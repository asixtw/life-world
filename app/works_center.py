"""作品管理（2026-11-10 自 8445 的 app/works.py 移植）：列表（種類、狀態、分頁）、詳情、版本讀取、封存與恢復。

- 讀取 8445 已存的所有種類（角色卡、人設、生成作品、互動紀錄等），內容原樣回傳，不轉換。
- 改版由各功能自己的 API 負責（角色卡、人設），這裡不提供通用改版，避免繞過各自的規則。
- 「我的人設」不能在這裡封存：一人一份使用中的人設，由人設頁管理。
"""
import json
from typing import Literal

from pydantic import Field, StrictInt

from .errors import require
from .schemas import Model

STATUS_LOCKED_KINDS = ('self_persona',)
# 作品中心只列「生成後的成果」；角色卡與我的人設是人物來源，在「角色」管理（2026-11-10 作品中心合併）
# 不列入：角色卡、我的人設、演出設定（theater_cast）、人物演繹工具（person_portrayal，在「角色」建立為角色卡）
CREATION_KINDS = ('generated_work', 'roleplay_session', 'story_opening', 'story_session', 'portrayal_session', 'theater_performance')
PHASES = ('active', 'completed', 'failed')
RUN_PHASES = {'queued': 'active', 'running': 'active', 'completed': 'completed', 'failed': 'failed'}


def work_phase(kind, content):
    """作品目前所處的階段：進行中（可以繼續）、已完成、失敗／待恢復。"""
    if kind in ('generated_work', 'roleplay_session'):
        return RUN_PHASES.get((content.get('run') or {}).get('status'), 'active')
    if kind in ('story_session', 'portrayal_session'):
        return 'completed' if content.get('status') == 'ended' else 'active'
    if kind == 'theater_cast':
        return 'active'  # 演出設定：可以繼續演出
    return 'completed'


def work_summary(kind, content, saved=0):
    """列表用的摘要：使用人物與進度（不回傳完整內容）。

    生成作品的已完成段數以實際保存的段落（session_turns）計算，與作品詳情相同；不依版本快照（快照只在狀態改變時更新）。
    """
    people, progress = [], None
    if kind in ('generated_work', 'roleplay_session'):
        from .roleplay import run_view
        view = run_view(content)
        people = [member.get('name') for member in view['cast'] if member.get('name')]
        progress = {'done': saved, 'total': (content.get('run') or {}).get('total_segments')}
    elif kind == 'story_opening':
        people = [(content.get('source') or {}).get('character_name')]
    elif kind == 'story_session':
        people = [(content.get('character') or {}).get('name')]
        progress = {'done': len(content.get('turns') or []), 'total': 5}
    elif kind == 'person_portrayal':
        people = [(content.get('source') or {}).get('person_name')]
    elif kind == 'portrayal_session':
        people = [(content.get('portrayal') or {}).get('person_name')]
        progress = {'done': len(content.get('turns') or []), 'total': 6}
    elif kind in ('theater_cast', 'theater_performance'):
        people = [member.get('name') for member in content.get('cast') or []]
    return [name for name in people if name], progress


class WorkStatus(Model):  # 封存或恢復；不刪除任何版本
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)
    status: Literal['active', 'archived']


class WorksMixin:
    """擴充 LifeWorld；所有查詢都以 owner 過濾，查不到一律 404。"""

    @staticmethod
    def _work_row(c, owner, work_id):
        row = c.execute('SELECT id,owner_id,kind,title,status,current_version,revision,created_at,updated_at FROM works WHERE id=? AND owner_id=?', (work_id, owner)).fetchone()
        require(row is not None, 404, 'not_found', '找不到可存取的作品。')
        return row

    @staticmethod
    def _work_version(c, owner, work_id, version_no):
        row = c.execute('SELECT * FROM work_versions WHERE work_id=? AND owner_id=? AND version_no=?', (work_id, owner, version_no)).fetchone()
        require(row is not None, 404, 'not_found', '找不到指定的作品版本。')
        return {'work_id': row['work_id'], 'version_no': row['version_no'], 'parent_version': row['parent_version'], 'origin': row['origin'],
                'content_schema': row['content_schema'], 'content': json.loads(row['content_json']), 'generation_id': row['generation_id'],
                'created_at': row['created_at']}

    def _work_detail(self, c, owner, work_id):
        work = dict(self._work_row(c, owner, work_id))
        work.pop('owner_id')
        work['version'] = self._work_version(c, owner, work_id, work['current_version'])
        work['versions'] = [dict(row) for row in c.execute(
            'SELECT version_no,parent_version,origin,content_schema,generation_id,created_at FROM work_versions '
            'WHERE work_id=? AND owner_id=? ORDER BY version_no DESC', (work_id, owner)).fetchall()]
        return work

    def works(self, owner, kind, status, limit, offset):
        with self.db.connect() as c:
            self._owned_user(c, owner)
            where, params = ['owner_id=?'], [owner]
            if kind:
                where.append('kind=?'); params.append(kind)
            if status != 'all':
                where.append('status=?'); params.append(status)
            clause = ' AND '.join(where)  # 欄位來自程式內白名單，值一律參數化
            total = c.execute('SELECT count(*) AS n FROM works WHERE ' + clause, params).fetchone()['n']
            rows = c.execute('SELECT id,kind,title,status,current_version,revision,created_at,updated_at FROM works WHERE ' + clause +
                             ' ORDER BY updated_at DESC,id LIMIT ? OFFSET ?', params + [limit, offset]).fetchall()
            return {'items': [dict(row) for row in rows], 'total': total, 'limit': limit, 'offset': offset}

    def work(self, owner, work_id):
        with self.db.connect() as c:
            self._owned_user(c, owner)
            return self._work_detail(c, owner, work_id)

    def work_version(self, owner, work_id, version_no):
        with self.db.connect() as c:
            self._owned_user(c, owner)
            self._work_row(c, owner, work_id)
            return self._work_version(c, owner, work_id, version_no)

    def set_work_status(self, owner, work_id, data):
        """封存或恢復；不刪除任何版本或原稿。"""
        operation = 'work:status:' + work_id  # 與 8445 相同的回執名稱
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            work = self._work_row(c, owner, work_id)
            require(work['kind'] not in STATUS_LOCKED_KINDS, 409, 'status_not_supported', '「我的人設」由人設頁管理，不能在這裡封存。')
            self._revision(work, data.expected_revision)
            c.execute('UPDATE works SET status=?,revision=revision+1,updated_at=? WHERE id=? AND owner_id=?',
                      (data.status, self.now().isoformat(), work_id, owner))
            result = self._work_detail(c, owner, work_id)
            self._remember(c, owner, operation, data.request_id, fingerprint, result)
            return result

    def work_center(self, owner, tab, status, kind, limit, offset):
        """作品中心列表：依階段分頁（active／completed／failed／all），附使用人物、進度與各分頁數量；新的在前。"""
        kinds = (kind,) if kind in CREATION_KINDS else CREATION_KINDS
        with self.db.connect() as c:
            self._owned_user(c, owner)
            where, params = ['w.owner_id=?', 'w.kind IN (' + ','.join('?' * len(kinds)) + ')'], [owner, *kinds]
            if status != 'all':
                where.append('w.status=?'); params.append(status)
            rows = c.execute('SELECT w.id,w.kind,w.title,w.status,w.current_version,w.revision,w.created_at,w.updated_at,v.content_json '
                             'FROM works w JOIN work_versions v ON v.work_id=w.id AND v.owner_id=w.owner_id AND v.version_no=w.current_version '
                             'WHERE ' + ' AND '.join(where) + ' ORDER BY w.updated_at DESC,w.id LIMIT 1000', params).fetchall()
            items, counts = [], {name: 0 for name in PHASES}
            saved = {row['work_id']: row['n'] for row in c.execute(  # 實際保存的段數（與作品詳情同一個來源）
                'SELECT work_id, count(*) AS n FROM session_turns WHERE owner_id=? GROUP BY work_id', (owner,)).fetchall()}
            for row in rows:
                content = json.loads(row['content_json'])
                phase = work_phase(row['kind'], content)
                counts[phase] += 1
                if tab in PHASES and phase != tab:
                    continue
                people, progress = work_summary(row['kind'], content, saved.get(row['id'], 0))
                items.append({key: row[key] for key in ('id', 'kind', 'title', 'status', 'current_version', 'revision', 'created_at', 'updated_at')}
                             | {'phase': phase, 'people': people, 'progress': progress,
                                'can_resume': phase == 'failed' and row['kind'] in ('generated_work', 'roleplay_session') and row['status'] == 'active'})
            counts['all'] = sum(counts[name] for name in PHASES)
            return {'items': items[offset:offset + limit], 'total': len(items), 'counts': counts, 'limit': limit, 'offset': offset}

    def work_history(self, owner, limit):
        """版本歷史：所有作品最近新增的版本（每一次保存、每一段生成、每一回合），新的在前。"""
        with self.db.connect() as c:
            self._owned_user(c, owner)
            rows = c.execute('SELECT v.work_id,v.version_no,v.origin,v.created_at,w.kind,w.title,w.status FROM work_versions v '
                             'JOIN works w ON w.id=v.work_id AND w.owner_id=v.owner_id '
                             'WHERE v.owner_id=? AND w.kind IN (' + ','.join('?' * len(CREATION_KINDS)) + ') '
                             'ORDER BY v.created_at DESC,v.work_id,v.version_no DESC LIMIT ?', (owner, *CREATION_KINDS, limit)).fetchall()
            return {'items': [dict(row) for row in rows]}

