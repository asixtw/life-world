"""8030 的逐段推進（2026-11-10）：沒有 Cloud Tasks，頁面開著時一段一段呼叫推進 API。

- 8445 的 T1／T2 引擎（app/roleplay.py）每段結束時會「排入下一段」；這裡把它記成每件作品一個待執行的段落。
- 推進 API 每次只執行一段（規劃或一個段落），每段完成就已保存在資料庫。
- 服務重啟或記憶體中沒有待執行段落時，依資料庫狀態推算下一段：沒有規劃→第 0 段；否則已保存段數＋1。
  同一段已有生成紀錄時沿用最新的嘗試序號（重送只會回放，不會重複呼叫 Provider）。
"""
import threading
import time

from .environment import expected_for

ROLEPLAY_KINDS = ('generated_work', 'roleplay_session')


class StepQueue:
    kind = 'foreground'
    queue_name = 'foreground'

    def __init__(self, backend):
        # 沿用 8445 的環境白名單：PostgreSQL 為 E2E，SQLite 只供本機測試。
        self.environment_id = 'e2e' if backend == 'postgresql' else 'local-test'
        self.expected = expected_for(self.environment_id)
        self._pending, self._lock = {}, threading.Lock()

    def enqueue(self, name, payload, delay_seconds=0):
        with self._lock:
            self._pending[payload['work_id']] = {'payload': dict(payload), 'not_before': time.time() + max(0, int(delay_seconds))}
        return True

    def take(self, work_id):
        with self._lock:
            return self._pending.pop(work_id, None)

    def peek(self, work_id):
        with self._lock:
            return self._pending.get(work_id)


def derive_entry(service, owner, work_id, environment_id):
    """記憶體中沒有待執行段落時，依資料庫狀態推算；作品已完成或失敗時回傳 None。"""
    from .roleplay import attempt_of  # 延後匯入，避免循環
    with service.db.connect() as c:
        work = c.execute('SELECT id,owner_id,kind,title,status,current_version,revision,created_at,updated_at FROM works WHERE id=? AND owner_id=?', (work_id, owner)).fetchone()
        if work is None or work['kind'] not in ROLEPLAY_KINDS:
            return None
        content = service._roleplay_content(c, owner, work)
        if content['run']['status'] in ('completed', 'failed'):
            return None
        saved = c.execute('SELECT count(*) AS n FROM session_turns WHERE owner_id=? AND work_id=?', (owner, work_id)).fetchone()['n']
        step = 0 if content['plan'] is None else saved + 1
        floor = service._attempt_floor(content, step)
        attempts = [attempt_of(row['request_id']) for row in c.execute(
            'SELECT request_id FROM ai_generations WHERE owner_id=? AND request_id LIKE ?', (owner, f'rp:{work_id}:{step}:%')).fetchall()]
        attempt = max([a for a in attempts if a >= floor] or [floor])
    return {'payload': {'environment_id': environment_id, 'owner_id': owner, 'work_id': work_id, 'step': step, 'attempt': attempt},
            'not_before': 0}
