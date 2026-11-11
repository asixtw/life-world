"""8030 P1 背景排程（與 8445 相同的 Cloud Tasks Worker）：以記憶體佇列模擬 Cloud Tasks，Task 送到真實的 /internal/roleplay/tasks。

驗證：開始生成即排入第 0 段；不需要頁面也能自動完成；服務重啟後接續；同一 Task 重送不重複生成；保存成功才排下一段；
每日金額上限用完時依時間窗延後；恢復後已保存的內容不遺失；背景模式下頁面讀取進度不會呼叫 Provider。
只用隔離 SQLite 與 Fake Provider。
"""
from datetime import datetime, timezone
import json

from fastapi.testclient import TestClient

from app.ai_providers import FakeProvider
from app.config import DemoPolicy
from app.main import create_app
from app.task_queue import InMemoryQueue, QueueError
from conftest import onboard, register
from test_generation_8030 import copy_card, start


class CountingFake(FakeProvider):
    def __init__(self, live=False):
        super().__init__()
        self.calls = 0
        if live:
            self.name, self.kind = 'fake-live', 'live'

    def generate(self, request):
        self.calls += 1
        return super().generate(request)


def make(tmp_path, provider, queue):
    app = create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                     clock=lambda: datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc), generation_provider=provider, task_queue=queue)
    return TestClient(app)


def ready(client, username):
    onboard(client)
    register(client, username)


def deliver(client, queue, task):
    """模擬 Cloud Tasks 把 Task 送到 Worker（帶 Queue 名稱標頭）。"""
    return client.post('/internal/roleplay/tasks', json=task['payload'], headers={'x-cloudtasks-queuename': queue.queue_name, 'x-cloudtasks-taskname': task['name']})


def drain(client, queue, limit=80):
    delivered = []
    for _ in range(limit):
        task = queue.pop()
        if task is None:
            return delivered
        response = deliver(client, queue, task)
        assert response.status_code == 200, response.text
        delivered.append(task)
    raise AssertionError('Task 沒有在預期數量內結束')


def detail(client, work_id):
    return client.get(f'/api/generation/runs/{work_id}').json()


def test_worker_completes_generation_without_the_page(tmp_path):
    queue, provider = InMemoryQueue(), CountingFake()
    with make(tmp_path, provider, queue) as c:
        ready(c, 'bg_owner')
        assert c.get('/api/generation/status').json()['background'] is True
        work_id = start(c, [copy_card(c), copy_card(c, 1)]).json()['id']
        assert [t['payload']['step'] for t in queue.tasks] == [0], '開始生成即排入第 0 段（規劃）'
        assert detail(c, work_id)['run']['status'] == 'queued'
        drain(c, queue)  # 期間沒有任何頁面讀取或推進
        final = detail(c, work_id)
        assert final['run']['status'] == 'completed' and len(final['segments']) == final['run']['total_segments']
        assert provider.calls == final['usage']['calls'] == final['run']['total_segments'] + 1, '一個 Task 只做一次 Provider 呼叫'
        versions = c.get(f'/api/works/{work_id}').json()['versions']
        assert len(versions) >= 3, '排隊中→生成中→完成都有版本'
        polled = c.post(f'/api/generation/runs/{work_id}/step').json()
        assert polled['outcome'] == 'background' and provider.calls == final['usage']['calls'], '背景模式下頁面只讀取進度'


def test_service_restart_continues_and_duplicate_task_does_not_regenerate(tmp_path):
    queue, provider = InMemoryQueue(), CountingFake()
    with make(tmp_path, provider, queue) as c:
        ready(c, 'bg_restart')
        work_id = start(c, [copy_card(c)]).json()['id']
        first = queue.pop()
        assert deliver(c, queue, first).status_code == 200  # 規劃
        second = queue.pop()
        assert deliver(c, queue, second).status_code == 200  # 第 1 段
        calls = provider.calls
        assert deliver(c, queue, second).status_code == 200, 'Cloud Tasks 重送同一個 Task'
        assert provider.calls == calls and len(detail(c, work_id)['segments']) == 1, '同一段重送不重複生成'
        pending = list(queue.tasks)
        cookies = dict(c.cookies)
        headers = dict(c.headers)
    restarted_queue = InMemoryQueue()  # 服務重啟：Cloud Tasks 上尚未執行的 Task 仍在
    restarted_queue.tasks = pending
    with make(tmp_path, provider, restarted_queue) as c2:
        c2.cookies.update(cookies)
        c2.headers.update(headers)
        drain(c2, restarted_queue)
        final = detail(c2, work_id)
        assert final['run']['status'] == 'completed' and len(final['segments']) == final['run']['total_segments']


def test_next_task_is_enqueued_only_after_save_and_retry_is_idempotent(tmp_path):
    queue, provider = InMemoryQueue(), CountingFake()
    with make(tmp_path, provider, queue) as c:
        ready(c, 'bg_enqueue')
        work_id = start(c, [copy_card(c)]).json()['id']
        deliver(c, queue, queue.pop())  # 規劃
        task = queue.pop()
        original = queue.enqueue

        def broken(*args, **kwargs):
            raise QueueError('temporarily unavailable')
        queue.enqueue = broken
        failed = deliver(c, queue, task)
        assert failed.status_code == 503, '排入下一段失敗時回 503，讓 Cloud Tasks 重送這個 Task'
        saved = len(detail(c, work_id)['segments'])
        assert saved == 1, '這一段已先保存'
        queue.enqueue = original
        calls = provider.calls
        assert deliver(c, queue, task).status_code == 200, 'Cloud Tasks 重送'
        assert provider.calls == calls and len(detail(c, work_id)['segments']) == saved, '重送不重做已保存的段落，只補排下一段'
        assert queue.tasks and queue.tasks[-1]['payload']['step'] == 2
        drain(c, queue)
        assert detail(c, work_id)['run']['status'] == 'completed'


def test_budget_exhausted_delays_task_and_continues_after_budget_returns(tmp_path, monkeypatch):
    monkeypatch.setenv('LIFEWORLD_AI_RESERVATION_MICROUSD', '1000')
    monkeypatch.setenv('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD', '3000')  # 規劃＋2 段後用完
    queue, provider = InMemoryQueue(), CountingFake(live=True)
    with make(tmp_path, provider, queue) as c:
        ready(c, 'bg_budget')
        work_id = start(c, [copy_card(c)]).json()['id']
        for _ in range(4):
            deliver(c, queue, queue.pop())
        waiting = detail(c, work_id)
        assert waiting['run']['status'] == 'running' and waiting['run']['notice']['code'] == 'budget_wait'
        assert len(waiting['segments']) == 2 and provider.calls == 3
        delayed = queue.tasks[-1]
        assert 60 <= delayed['delay_seconds'] <= 1800, '依時間窗延後排程，不立即重試'
        assert delayed['payload']['step'] == 3
        monkeypatch.setenv('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD', '1000000')  # 額度恢復
        drain(c, queue)
        final = detail(c, work_id)
        assert final['run']['status'] == 'completed' and final['segments'][:2] == waiting['segments'], '已保存的段落不遺失'


def test_worker_route_is_closed_without_background_queue(tmp_path):
    app = create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096), generation_provider=FakeProvider())
    with TestClient(app) as c:
        assert c.post('/internal/roleplay/tasks', json={}).status_code == 404
        assert c.get('/api/auth/me').status_code in (200, 401)


def test_invalid_task_is_not_retried(tmp_path):
    queue = InMemoryQueue()
    with make(tmp_path, CountingFake(), queue) as c:
        bad = c.post('/internal/roleplay/tasks', data=json.dumps({'nope': 1}), headers={'content-type': 'application/json'})
        assert bad.status_code == 200 and bad.json()['error']['code'] == 'invalid_task'
