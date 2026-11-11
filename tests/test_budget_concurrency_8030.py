"""8030 每日金額上限的並行與邊界（2026-11-10 第三階段）：真的多執行緒同時送出，確認不會突破上限、重送不重複扣款、
逾時與失敗的預留處理、24 小時後額度恢復（隔天繼續）。

只用隔離 SQLite 與標示為真實呼叫的假 Provider（不連網、不計費）。金額以測試用的小數字代表（例如預留 1000 微美元），
產品設定（每日 US$19、每次預留 US$0.50）不變。PostgreSQL 的 advisory lock 路徑由雲端 E2E 執行；本機 PG 測試叢集沒有生成資料表。
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import threading
import time

from fastapi.testclient import TestClient

from app.ai_providers import FakeProvider
from app.config import DemoPolicy
from app.main import create_app
from conftest import onboard, register


class SlowLive(FakeProvider):
    """標示為真實呼叫；每次停 0.4 秒讓請求重疊；不回報用量（費用未知，預留保留）。計算實際呼叫次數。"""
    name, kind = 'fake-live', 'live'

    def __init__(self, seconds=0.4):
        super().__init__()
        self.seconds, self.calls, self.lock = seconds, 0, threading.Lock()

    def generate(self, request):
        with self.lock:
            self.calls += 1
        time.sleep(self.seconds)
        return super().generate(request)


class Clock:
    def __init__(self):
        self.value = datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


def setup(tmp_path, monkeypatch, provider, reservations, clock=None):
    monkeypatch.setenv('LIFEWORLD_AI_RESERVATION_MICROUSD', '1000')
    monkeypatch.setenv('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD', str(1000 * reservations))
    monkeypatch.setenv('LIFEWORLD_AI_TIMEOUT_SECONDS', '5')
    app = create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                     clock=clock or Clock(), generation_provider=provider)
    return app


def account(app, username):
    client = TestClient(app)
    onboard(client)
    register(client, username)
    return client


def draft(client, request_id, name='並行測試'):
    return client.post('/api/ai/generate', json={'request_id': request_id, 'module': 'character_card', 'input': {'name': name, 'kind': 'fictional'}})


def reserved(app):
    with app.state.service.db.connect() as db:
        rows = [json.loads(r['response']) for r in db.execute("SELECT response FROM requests WHERE operation='ai_attempt_v1'").fetchall()]
    return sum(r['reservation_microusd'] for r in rows), len([r for r in rows if r['reservation_microusd'] > 0])


def test_two_accounts_race_for_the_last_reservation(tmp_path, monkeypatch):
    provider = SlowLive()
    app = setup(tmp_path, monkeypatch, provider, reservations=3)
    with TestClient(app):
        first = account(app, 'race_first')
        assert draft(first, 'warm-1').status_code == 201 and draft(first, 'warm-2').status_code == 201  # 先用掉 2 份，只剩最後 1 份
        a, b = account(app, 'race_a'), account(app, 'race_b')
        barrier = threading.Barrier(2)

        def go(client, rid):
            barrier.wait()
            return draft(client, rid)
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda args: go(*args), [(a, 'last-a'), (b, 'last-b')]))
        codes = sorted(r.status_code for r in results)
        assert codes == [201, 429], f'只有一方取得最後一份額度：{codes}'
        assert [r.json()['error']['code'] for r in results if r.status_code == 429] == ['ai_budget_reached']
        assert reserved(app) == (3000, 3), '帳上預留總額剛好等於上限，沒有突破'
        assert provider.calls == 3, '沒取得額度的一方不呼叫供應商'


def test_concurrent_generations_never_exceed_daily_cap(tmp_path, monkeypatch):
    provider = SlowLive()
    app = setup(tmp_path, monkeypatch, provider, reservations=5)
    with TestClient(app):
        clients = [account(app, f'burst_{i}') for i in range(8)]
        barrier = threading.Barrier(len(clients))

        def go(index):
            barrier.wait()
            return draft(clients[index], f'burst-{index}')
        with ThreadPoolExecutor(len(clients)) as pool:
            results = list(pool.map(go, range(len(clients))))
        ok = [r for r in results if r.status_code == 201]
        blocked = [r for r in results if r.status_code == 429]
        assert len(ok) == 5 and len(blocked) == 3, [r.status_code for r in results]
        assert reserved(app) == (5000, 5) and provider.calls == 5, '8 個同時送出也不會超過每日上限'


def test_same_request_resent_concurrently_calls_and_charges_once(tmp_path, monkeypatch):
    provider = SlowLive()
    app = setup(tmp_path, monkeypatch, provider, reservations=10)
    with TestClient(app):
        client = account(app, 'resend_owner')
        barrier = threading.Barrier(3)

        def go(_):
            barrier.wait()
            return draft(client, 'same-request')
        with ThreadPoolExecutor(3) as pool:
            results = list(pool.map(go, range(3)))
        assert 201 in [r.status_code for r in results]
        assert all(r.status_code in (201, 409) for r in results), [r.status_code for r in results]
        assert provider.calls == 1 and reserved(app) == (1000, 1), '同一請求同時重送：只呼叫一次、只預留一次'
        again = draft(client, 'same-request')
        assert again.status_code == 201 and provider.calls == 1 and reserved(app) == (1000, 1), '完成後再重送：回原結果，不再扣款'


def test_timeout_keeps_reservation_until_it_expires_and_next_day_continues(tmp_path, monkeypatch):
    clock = Clock()
    provider = SlowLive(seconds=8)  # 超過 5 秒總時限
    app = setup(tmp_path, monkeypatch, provider, reservations=1, clock=clock)
    with TestClient(app):
        client = account(app, 'timeout_owner')
        timed_out = draft(client, 'slow-1')
        assert timed_out.status_code == 504 and timed_out.json()['error']['code'] == 'provider_timeout'
        with app.state.service.db.connect() as db:
            row = db.execute('SELECT status,cost_status,cost_microusd FROM ai_generations').fetchone()
        assert (row['status'], row['cost_status'], row['cost_microusd']) == ('failed', 'unknown', None), '逾時不知道費用：標失敗、費用未知'
        assert reserved(app) == (1000, 1), '逾時無法確認供應商是否已計費，預留保留'
        provider.seconds = 0
        blocked = draft(client, 'after-timeout')
        assert blocked.status_code == 429 and blocked.json()['error']['code'] == 'ai_budget_reached', '預留還在 24 小時內，額度用完就停止'
        clock.value += timedelta(days=1, seconds=1)  # 隔天：滾動 24 小時過後預留自然釋放
        assert draft(client, 'next-day').status_code == 201, '隔天可以繼續'
