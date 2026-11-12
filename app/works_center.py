"""作品管理（2026-11-10 自 8445 的 app/works.py 移植）：列表（種類、狀態、分頁）、詳情、版本讀取、封存與恢復。

- 讀取 8445 已存的所有種類（角色卡、人設、生成作品、互動紀錄等），內容原樣回傳，不轉換；
  只有回合制互動作品與生成作品依種類拿掉劇透與內部參照（public_content，2026-11-12 起）。資料庫裡的內容不變。
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
CREATION_KINDS = ('generated_work', 'roleplay_session', 'story_opening', 'story_session', 'portrayal_session', 'theater_performance',
                  'story_series',  # 多章節作品：一部持續續寫的作品，它的每一章是各自的生成作品
                  'turn_game')  # 回合制互動作品：規劃一次、每位同行者各生成一次，全部完成才能玩（app/turn_game.py）
PHASES = ('active', 'completed', 'failed')
RUN_PHASES = {'queued': 'active', 'running': 'active', 'completed': 'completed', 'failed': 'failed'}


def work_phase(kind, content):
    """作品目前所處的階段：進行中（可以繼續）、已完成、失敗／待恢復。"""
    if kind in ('generated_work', 'roleplay_session'):
        return RUN_PHASES.get((content.get('run') or {}).get('status'), 'active')
    if kind in ('story_session', 'portrayal_session'):
        return 'completed' if content.get('status') == 'ended' else 'active'
    if kind in ('theater_cast', 'story_series'):
        return 'active'  # 演出設定可以繼續演出；多章節作品可以繼續續寫
    if kind == 'turn_game':  # 還有同行者的反應沒生成（building）算進行中；ready 才算已完成（可以玩與匯出）
        return 'completed' if (content.get('build') or {}).get('status') == 'ready' else 'active'
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
    elif kind == 'story_series':  # 進度是已定稿的章數；沒有預定的總章數
        people = [member.get('name') for member in content.get('cast') or []]
        progress = {'done': len(content.get('episodes') or []), 'total': None}
    elif kind == 'turn_game':  # 人物是同行者；進度是生成的步數（規劃一步＋每位同行者一步）
        people = [member.get('name') for member in content.get('cast') or []]
        build = content.get('build') or {}
        done = len(build.get('done') or [])
        progress = {'done': done, 'total': done + len(build.get('pending') or [])}
    return [name for name in people if name], progress


def public_content(kind, content):
    """通用作品路由（作品詳情、版本詳情、封存／恢復的回應）回給本人的內容：依作品種類拿掉會劇透的內容與內部參照。

    2026-11-12 外部檢驗發現：這幾條路由原本回整份內容，本人在作品頁就讀得到底牌、互動層、遊戲的反應與結局，以及人物設定的參照。
    - turn_game：只回和 GET /api/games/{id} 同等級的公開欄位（turn_game.game_public）。
    - generated_work：規劃拿掉只給單一人物的底牌（plan.private_notes），內容拿掉互動層（interactive：抉擇、線索、結局與番外）；
      其他欄位原樣，包括 meta（多章節作品的 meta.continuity、meta.series 由畫面與雲端驗收讀取）。8445 的舊內容沒有這兩個欄位就原樣。
    - roleplay_session（8445 的舊種類）：和 generated_work 相同。2026-11-12 第二次外部檢驗發現：舊作品經相容路由恢復生成後，
      規劃同樣會帶著底牌。
    - 其他種類原樣回傳。
    已經投影過的內容再投影一次結果相同（封存回執裡保存的就是投影後的內容）。
    只改回應，不改資料庫：生成、匯出（app/work_export.py）與各功能自己的路由仍讀完整內容。
    """
    if kind == 'turn_game':
        from .turn_game import game_public  # 在函式裡匯入（和 work_summary 相同）：這個模組載入時不依賴各種作品的生成模組
        return game_public(content)
    if kind in ('generated_work', 'roleplay_session') and isinstance(content, dict):
        from .roleplay import public_plan
        shown = {key: value for key, value in content.items() if key != 'interactive'}
        if isinstance(shown.get('plan'), dict):
            shown['plan'] = public_plan(shown['plan'])
        return shown
    return content


def public_detail(detail):
    """作品詳情（含 version.content）依種類投影；其他欄位（狀態、版本號、revision、時間）原樣。用在讀回保存過的回執。"""
    version = detail.get('version') if isinstance(detail, dict) else None
    if isinstance(version, dict) and 'content' in version:
        return {**detail, 'version': {**version, 'content': public_content(detail.get('kind'), version['content'])}}
    return detail


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
        """一個版本的完整內容（不投影）：給服務內部使用；要回給前端時先經過 public_content。"""
        row = c.execute('SELECT * FROM work_versions WHERE work_id=? AND owner_id=? AND version_no=?', (work_id, owner, version_no)).fetchone()
        require(row is not None, 404, 'not_found', '找不到指定的作品版本。')
        return {'work_id': row['work_id'], 'version_no': row['version_no'], 'parent_version': row['parent_version'], 'origin': row['origin'],
                'content_schema': row['content_schema'], 'content': json.loads(row['content_json']), 'generation_id': row['generation_id'],
                'created_at': row['created_at']}

    def _work_detail(self, c, owner, work_id):
        """作品詳情（回給前端）：目前版本的內容依種類投影（public_content）。各功能建立或改版後的回應也用這一份。"""
        work = dict(self._work_row(c, owner, work_id))
        work.pop('owner_id')
        version = self._work_version(c, owner, work_id, work['current_version'])
        work['version'] = {**version, 'content': public_content(work['kind'], version['content'])}
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
        """版本詳情（回給前端）：內容依種類投影，和作品詳情相同。"""
        with self.db.connect() as c:
            self._owned_user(c, owner)
            work = self._work_row(c, owner, work_id)
            version = self._work_version(c, owner, work_id, version_no)
            return {**version, 'content': public_content(work['kind'], version['content'])}

    def set_work_status(self, owner, work_id, data):
        """封存或恢復；不刪除任何版本或原稿。回應（與保存的回執）是投影過的作品詳情，重送也不會讀到完整內容。"""
        operation = 'work:status:' + work_id  # 與 8445 相同的回執名稱
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, data.model_dump(mode='json'))
            if cached:
                # 2026-11-12 第二次外部檢驗發現：修正之前保存的回執裡是完整內容；讀出時也套用公開規則（新回執本來就是投影過的，結果相同）
                return public_detail(cached)
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

