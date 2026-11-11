"""8030 AI 生成（自 8445 移植）：角色卡 AI 草稿、T1／T2 逐段生成與保存、金額上限停止與恢復、同意、擁有者隔離。

只用隔離 SQLite 與 Fake Provider（不連網、不計費）。金額上限以「標示為真實」的 Fake 模擬：真實呼叫才預留金額。
"""
from datetime import datetime, timezone
import json

import pytest
from fastapi.testclient import TestClient

from app.ai_providers import FakeProvider
from app.config import DemoPolicy
from app.main import create_app
from conftest import onboard, register


class LiveFake(FakeProvider):
    """輸出與 Fake 相同，但標示為真實呼叫，用來驗證金額上限（不連網）。"""
    name, kind = 'fake-live', 'live'


def make_client(tmp_path, provider):
    app = create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                     clock=lambda: datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc), generation_provider=provider)
    return TestClient(app)


def ready(client, username='gen_owner'):
    onboard(client)
    register(client, username)


def copy_card(client, index=0):
    system = client.get('/api/characters/system').json()['items'][index]
    return client.post('/api/characters/copy', json={'request_id': f'copy-{index}', 'source_kind': 'system', 'source_id': system['id'],
                                                     'source_version': system['version']}).json()


def start(client, cards, include_me=False, request_id='run-1', length='short'):
    body = {'request_id': request_id, 'setup': {'participants': [{'ref': {'work_id': card['id'], 'version_no': card['current_version']}} for card in cards],
                                                'include_me': include_me, 'scene_context': {'description': '霧港的夜晚，兩支商隊在碼頭相遇。'},
                                                'output': {'type': 'text', 'text': {'length': length, 'form': 'script'}}}}
    return client.post('/api/generation/runs', json=body)


def run_to_end(client, work_id, limit=60):
    """模擬頁面逐段推進：直到完成或失敗；回傳最後的詳情。"""
    for _ in range(limit):
        result = client.post(f'/api/generation/runs/{work_id}/step')
        assert result.status_code == 200, result.text
        detail = result.json()['detail']
        if detail['run']['status'] in ('completed', 'failed'):
            return detail
    raise AssertionError('沒有在預期步數內結束')


@pytest.fixture
def client(tmp_path):
    with make_client(tmp_path, FakeProvider()) as c:
        yield c


def test_ai_character_card_draft_and_save(client):
    ready(client)
    draft = client.post('/api/ai/generate', json={'request_id': 'draft-1', 'module': 'character_card', 'input': {'name': '霧港守望者', 'kind': 'fictional'}})
    assert draft.status_code == 201, draft.text
    generation, output = draft.json()['generation'], draft.json()['output']
    assert generation['provider_kind'] == 'fake' and output['name']
    content = {key: output[key] for key in output}
    saved = client.post('/api/characters', json={'request_id': 'save-1', 'content': content, 'generation_id': generation['id']})
    assert saved.status_code == 201, saved.text
    assert saved.json()['version']['origin'] == 'ai' and saved.json()['version']['generation_id'] == generation['id']
    edited = client.post('/api/characters', json={'request_id': 'save-2', 'content': {**content, 'tagline': '我改了一句'}, 'generation_id': generation['id']})
    assert edited.json()['version']['origin'] == 'ai_edited'
    manual = client.post('/api/characters', json={'request_id': 'save-3', 'content': {'name': '手寫角色', 'kind': 'fictional'}})
    assert manual.status_code == 201 and manual.json()['version']['origin'] == 'human'
    other_module = client.post('/api/ai/generate', json={'request_id': 'story-1', 'module': 'story_opening', 'input': {}})
    assert other_module.status_code == 422


def test_t1_generates_segment_by_segment_and_saves_each(client):
    ready(client)
    card = copy_card(client)
    started = start(client, [card])
    assert started.status_code == 201, started.text
    work_id = started.json()['id']
    first = client.post(f'/api/generation/runs/{work_id}/step').json()
    assert first['outcome'] == 'planned' and first['detail']['module'] == 'T1' and first['detail']['run']['total_segments'] >= 1
    second = client.post(f'/api/generation/runs/{work_id}/step').json()
    assert second['outcome'] == 'saved' and len(second['detail']['segments']) == 1, '每段完成就保存'
    detail = run_to_end(client, work_id)
    assert detail['run']['status'] == 'completed' and len(detail['segments']) == detail['run']['total_segments']
    assert client.get('/api/works?kind=generated_work').json()['total'] == 1
    again = client.post(f'/api/generation/runs/{work_id}/step').json()
    assert again['outcome'] == 'none' and again['detail']['run']['status'] == 'completed', '完成後再推進不會重複生成'


def test_progress_survives_restart_and_continues_from_next_segment(tmp_path):
    with make_client(tmp_path, FakeProvider()) as first_client:
        ready(first_client, 'restart_owner')
        card = copy_card(first_client)
        work_id = start(first_client, [card]).json()['id']
        for _ in range(3):
            first_client.post(f'/api/generation/runs/{work_id}/step')
        saved_before = len(first_client.get(f'/api/generation/runs/{work_id}').json()['segments'])
        cookies = dict(first_client.cookies)
        csrf = first_client.headers['X-CSRF-Token']
    with make_client(tmp_path, FakeProvider()) as second_client:  # 服務重啟：記憶體中的待執行段落已不存在
        second_client.cookies.update(cookies)
        second_client.headers['X-CSRF-Token'] = csrf
        step = second_client.post(f'/api/generation/runs/{work_id}/step').json()
        assert step['outcome'] == 'saved' and len(step['detail']['segments']) == saved_before + 1, '依資料庫狀態從下一段接續'
        assert run_to_end(second_client, work_id)['run']['status'] == 'completed'


def test_t2_with_me_requires_consent_bound_to_provider(client):
    ready(client, 't2_owner')
    cards = [copy_card(client, 0), copy_card(client, 1)]
    client.put('/api/self-persona', json={'request_id': 'p1', 'content': {'display_name': '小光', 'public_profile': '設計師',
                                                                           'personality': '好奇', 'speaking_style': '簡短'}})
    denied = start(client, cards, include_me=True, request_id='run-denied')
    assert denied.status_code == 409 and denied.json()['error']['code'] == 'consent_required'
    granted = client.post('/api/self-persona/consent', json={'request_id': 'c1', 'granted': True}).json()
    assert granted['consent'] is not None, '同意綁定目前的 AI 供應商'
    started = start(client, cards, include_me=True, request_id='run-t2')
    assert started.status_code == 201, started.text
    detail = run_to_end(client, started.json()['id'])
    assert detail['module'] == 'T2' and detail['run']['status'] == 'completed'
    assert any(member['is_user'] for member in detail['cast'])


def test_daily_money_cap_delays_generation_keeps_segments_and_continues_when_budget_returns(tmp_path, monkeypatch):
    """每日金額上限用完：不標失敗、不立即重試，依 24 小時時間窗延後排程；已保存的段落保留；額度恢復後自動接續到完成。"""
    monkeypatch.setenv('LIFEWORLD_AI_RESERVATION_MICROUSD', '1000')
    monkeypatch.setenv('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD', '3000')  # 只夠 3 次真實呼叫
    with make_client(tmp_path, LiveFake()) as c:
        ready(c, 'budget_owner')
        card = copy_card(c)
        work_id = start(c, [card]).json()['id']
        for _ in range(10):
            result = c.post(f'/api/generation/runs/{work_id}/step').json()
            if result['wait_seconds'] and result['wait_seconds'] >= 60:
                break
        detail = result['detail']
        assert detail['run']['status'] == 'running' and detail['run']['notice']['code'] == 'budget_wait', '延後排程中，不是失敗'
        assert '金額上限' in detail['run']['notice']['message']
        assert 60 <= result['wait_seconds'] <= 1800, '依時間窗延後，最多 30 分鐘後再確認'
        kept = len(detail['segments'])
        assert kept == 2, '規劃 1 次＋2 段，第 4 次被金額上限擋下；已保存的段落保留'
        again = c.post(f'/api/generation/runs/{work_id}/step').json()
        assert again['outcome'] == 'none' and len(again['detail']['segments']) == kept, '等待期間不會立即重試'
        draft = c.post('/api/ai/generate', json={'request_id': 'draft-over', 'module': 'character_card', 'input': {'name': '超額', 'kind': 'fictional'}})
        assert draft.status_code == 429 and draft.json()['error']['code'] == 'ai_budget_reached'
        monkeypatch.setenv('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD', '1000000')  # 額度恢復（例如隔天）
        c.app.state.step_queue.take(work_id)  # 模擬延後的時間已到
        finished = run_to_end(c, work_id)
        assert finished['run']['status'] == 'completed' and len(finished['segments']) == finished['run']['total_segments'] > kept
        with c.app.state.service.db.connect() as db:
            receipts = db.execute("SELECT count(*) AS n FROM requests WHERE operation='ai_attempt_v1'").fetchone()['n']
        assert receipts == finished['usage']['calls'], '每次真實呼叫都留下金額預留紀錄（不刪除）'


def test_fake_provider_does_not_use_money_budget(tmp_path, monkeypatch):
    monkeypatch.setenv('LIFEWORLD_AI_RESERVATION_MICROUSD', '1000')
    monkeypatch.setenv('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD', '1000')
    with make_client(tmp_path, FakeProvider()) as c:
        ready(c, 'fake_owner')
        work_id = start(c, [copy_card(c)]).json()['id']
        assert run_to_end(c, work_id)['run']['status'] == 'completed'


def test_other_account_cannot_read_or_step(client):
    ready(client, 'gen_a')
    work_id = start(client, [copy_card(client)]).json()['id']
    other = TestClient(client.app)
    ready(other, 'gen_b')
    assert other.get(f'/api/generation/runs/{work_id}').status_code == 404
    assert other.post(f'/api/generation/runs/{work_id}/step').status_code == 404
    assert client.post(f'/api/generation/runs/{work_id}/step').json()['outcome'] == 'planned', '別人的推進不會吃掉自己的待執行段落'


def test_no_provider_returns_503(tmp_path):
    with make_client(tmp_path, None) as c:
        ready(c, 'no_provider')
        assert c.get('/api/generation/status').json()['available'] is False
        assert start(c, [copy_card(c)]).status_code == 503


class LiveFakeWithUsage(LiveFake):
    """標示為真實呼叫，並回報固定用量（每次輸入 1000、輸出 200 Token），用來驗證依實際用量結算。"""
    def generate(self, request):
        from dataclasses import replace
        return replace(super().generate(request), input_tokens=1000, output_tokens=200)


def ledger(c):
    with c.app.state.service.db.connect() as db:
        rows = [json.loads(r['response']) for r in db.execute("SELECT response FROM requests WHERE operation='ai_attempt_v1'").fetchall()]
    return rows


def test_reservation_is_settled_by_actual_tokens_so_budget_lasts(tmp_path, monkeypatch):
    monkeypatch.setenv('LIFEWORLD_AI_RESERVATION_MICROUSD', '1000')
    monkeypatch.setenv('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD', '3000')  # 不結算只夠 3 次
    monkeypatch.setenv('LIFEWORLD_AI_INPUT_MICROUSD_PER_MTOK', '50000')    # 1000 Token → 50
    monkeypatch.setenv('LIFEWORLD_AI_OUTPUT_MICROUSD_PER_MTOK', '250000')  # 200 Token → 50；每次實際 100
    with make_client(tmp_path, LiveFakeWithUsage()) as c:
        ready(c, 'settle_owner')
        work_id = start(c, [copy_card(c)]).json()['id']
        detail = run_to_end(c, work_id)
        assert detail['run']['status'] == 'completed', '預留依實際用量結算後，同樣的每日上限可以完成整篇'
        rows = ledger(c)
        reservations = [r for r in rows if r['reservation_microusd'] > 0]
        settlements = [r for r in rows if r.get('operation') == 'settlement']
        assert len(reservations) == len(settlements) == detail['usage']['calls']
        assert sum(r['reservation_microusd'] for r in rows) == 100 * detail['usage']['calls'], '帳上只剩實際費用'
        assert all(s['created_at'] in {r['created_at'] for r in reservations} for s in settlements), '退款與原預留同一時間，一起滾出 24 小時'
        with c.app.state.service.db.connect() as db:
            costs = {r['cost_status']: r['n'] for r in db.execute("SELECT cost_status, count(*) AS n FROM ai_generations GROUP BY cost_status").fetchall()}
        assert costs == {'known': detail['usage']['calls']}


def test_unknown_usage_keeps_reservation_without_settlement(tmp_path, monkeypatch):
    monkeypatch.setenv('LIFEWORLD_AI_RESERVATION_MICROUSD', '1000')
    monkeypatch.setenv('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD', '100000')
    monkeypatch.setenv('LIFEWORLD_AI_INPUT_MICROUSD_PER_MTOK', '50000')
    monkeypatch.setenv('LIFEWORLD_AI_OUTPUT_MICROUSD_PER_MTOK', '250000')
    with make_client(tmp_path, LiveFake()) as c:  # 不回報用量（例如逾時或供應商沒給用量）
        ready(c, 'unknown_usage')
        c.post('/api/ai/generate', json={'request_id': 'draft-u', 'module': 'character_card', 'input': {'name': '未知用量', 'kind': 'fictional'}})
        rows = ledger(c)
        assert [r['reservation_microusd'] for r in rows] == [1000], '用量未知時不結算，預留額保留到 24 小時後自然滾出'


# ---- 2026-11-10 第三階段：Gemini 已回報用量但輸出驗證失敗時，生成紀錄也要記下實際費用（與預算帳本一致） ----
class LiveInvalidWithUsage(LiveFake):
    """標示為真實呼叫；回報用量（1000／200 Token）但輸出不是合格 JSON。計算呼叫次數，用來確認重送不再呼叫。"""
    calls = 0

    def generate(self, request):
        from dataclasses import replace
        type(self).calls += 1
        return replace(super().generate(request), text='{"not": "valid"', input_tokens=1000, output_tokens=200)


class LiveFailureWithUsage(LiveFake):
    """供應商回報失敗（例如輸出被截斷）但附上用量。"""
    def generate(self, request):
        from app.ai_text import ProviderFailure, TextResult
        raise ProviderFailure('provider_error', result=TextResult(text='', input_tokens=1000, output_tokens=200, model_version='m-1'))


class LiveFailureNoUsage(LiveFake):
    def generate(self, request):
        from app.ai_text import ProviderFailure
        raise ProviderFailure('provider_error')


def priced(monkeypatch):
    monkeypatch.setenv('LIFEWORLD_AI_RESERVATION_MICROUSD', '1000')
    monkeypatch.setenv('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD', '100000')
    monkeypatch.setenv('LIFEWORLD_AI_INPUT_MICROUSD_PER_MTOK', '50000')    # 1000 Token → 50
    monkeypatch.setenv('LIFEWORLD_AI_OUTPUT_MICROUSD_PER_MTOK', '250000')  # 200 Token → 50；每次實際 100


def generations(c):
    with c.app.state.service.db.connect() as db:
        return [dict(r) for r in db.execute('SELECT status,error_code,cost_status,cost_microusd,input_tokens,output_tokens FROM ai_generations').fetchall()]


DRAFT = {'request_id': 'draft-x', 'module': 'character_card', 'input': {'name': '驗證失敗', 'kind': 'fictional'}}


def test_invalid_output_with_known_usage_records_cost_settles_once_and_replay_does_not_charge(tmp_path, monkeypatch):
    priced(monkeypatch)
    LiveInvalidWithUsage.calls = 0
    with make_client(tmp_path, LiveInvalidWithUsage()) as c:
        ready(c, 'invalid_usage')
        first = c.post('/api/ai/generate', json=DRAFT)
        assert first.status_code == 502 and first.json()['error']['code'] == 'invalid_output', '費用結算成功不能把生成當成成功'
        assert generations(c) == [{'status': 'failed', 'error_code': 'invalid_output', 'cost_status': 'known', 'cost_microusd': 100,
                                   'input_tokens': 1000, 'output_tokens': 200}]
        rows = ledger(c)
        assert sorted(r['reservation_microusd'] for r in rows) == [-900, 1000], '預留 1000、退回 900，帳上只剩實際費用 100'
        again = c.post('/api/ai/generate', json=DRAFT)
        assert again.status_code == 502 and again.json()['error']['code'] == 'invalid_output'
        assert LiveInvalidWithUsage.calls == 1, '同一 request_id 重送不再呼叫供應商'
        assert ledger(c) == rows, '重送不重複預留、不重複結算'
        assert len(generations(c)) == 1


def test_provider_failure_with_usage_records_cost_and_without_usage_stays_unknown(tmp_path, monkeypatch):
    priced(monkeypatch)
    with make_client(tmp_path, LiveFailureWithUsage()) as c:
        ready(c, 'failure_usage')
        assert c.post('/api/ai/generate', json=DRAFT).status_code == 502
        assert generations(c)[0]['cost_status'] == 'known' and generations(c)[0]['cost_microusd'] == 100
        assert sum(r['reservation_microusd'] for r in ledger(c)) == 100
    with make_client(tmp_path / 'no-usage', LiveFailureNoUsage()) as c:
        ready(c, 'failure_no_usage')
        assert c.post('/api/ai/generate', json=DRAFT).status_code == 502
        row = generations(c)[0]
        assert row['status'] == 'failed' and row['cost_status'] == 'unknown' and row['cost_microusd'] is None, '沒有用量資料才保留 unknown'
        assert [r['reservation_microusd'] for r in ledger(c)] == [1000], '未知用量保留預留，24 小時後自然釋放'


def test_t2_segments_with_invalid_output_record_cost_for_every_attempt(tmp_path, monkeypatch):
    priced(monkeypatch)
    with make_client(tmp_path, LiveInvalidWithUsage()) as c:
        ready(c, 'invalid_segments')
        work_id = start(c, [copy_card(c), copy_card(c, 1)]).json()['id']
        detail = run_to_end(c, work_id)
        assert detail['run']['status'] == 'failed', '每次都格式失敗時作品標記失敗，不誤判成功'
        rows = generations(c)
        assert rows and all(r['status'] == 'failed' and r['cost_status'] == 'known' and r['cost_microusd'] == 100 for r in rows)
        assert sum(r['reservation_microusd'] for r in ledger(c)) == 100 * len(rows), '帳本與生成紀錄的費用一致'


def test_late_result_after_interruption_keeps_failure_but_records_cost_once(tmp_path, monkeypatch):
    """紀錄已被標為中斷後才收到結果：狀態維持中斷（不變成成功），但費用與帳本結算一致，且只結算一次。"""
    from app.ai_config import AiSettings
    from app.ai_text import TextResult
    from app.gen_schemas import GenerateRequest
    priced(monkeypatch)
    provider = LiveFake()
    with make_client(tmp_path, provider) as c:
        ready(c, 'late_owner')
        service = c.app.state.service
        with service.db.connect() as db:
            owner = db.execute("SELECT id FROM users WHERE username='late_owner'").fetchone()['id']
        prepared = service.ai_prepare(owner, GenerateRequest.model_validate(DRAFT), provider, AiSettings.from_env())
        with service.db.connect(write=True, owner=owner) as db:
            db.execute("UPDATE ai_generations SET status='interrupted',error_code='provider_interrupted' WHERE id=?", (prepared['generation_id'],))
        late = TextResult(text='{}', input_tokens=1000, output_tokens=200)
        for _ in range(2):  # 晚到結果重複送達也只結算一次
            try:
                service.ai_finish(owner, prepared, provider, late, None, 10)
            except Exception:
                pass
        row = generations(c)[0]
        assert row['status'] == 'interrupted' and row['cost_status'] == 'known' and row['cost_microusd'] == 100
        assert sorted(r['reservation_microusd'] for r in ledger(c)) == [-900, 1000]


# ---- 2026-11-10 第四階段：HTTP 已回 504，Gemini 之後才回傳用量 → 仍要記帳與結算 ----
class SlowLiveWithUsage(LiveFake):
    """標示為真實呼叫；前 slow_calls 次超過總時限才回來（附用量 1000／200 Token），之後立即回來。計算呼叫次數。"""
    def __init__(self, seconds=2.5, slow_calls=1):
        super().__init__()
        self.seconds, self.slow_calls, self.calls = seconds, slow_calls, 0

    def generate(self, request):
        import time as _time
        from dataclasses import replace
        self.calls += 1
        if self.calls <= self.slow_calls:
            _time.sleep(self.seconds)
        return replace(super().generate(request), input_tokens=1000, output_tokens=200)


def wait_for(check, seconds=10):
    import time as _time
    deadline = _time.monotonic() + seconds
    while _time.monotonic() < deadline:
        if check():
            return True
        _time.sleep(0.1)
    return False


def test_http_504_then_late_gemini_usage_is_recorded_and_settled_once(tmp_path, monkeypatch):
    priced(monkeypatch)
    monkeypatch.setenv('LIFEWORLD_AI_TIMEOUT_SECONDS', '1')
    provider = SlowLiveWithUsage()
    with make_client(tmp_path, provider) as c:
        ready(c, 'late_http')
        timed_out = c.post('/api/ai/generate', json=DRAFT)
        assert timed_out.status_code == 504 and timed_out.json()['error']['code'] == 'provider_timeout', '先回 504'
        assert generations(c)[0]['cost_status'] == 'unknown', 'HTTP 回應當下還不知道費用'
        assert wait_for(lambda: generations(c)[0]['cost_status'] == 'known'), 'Gemini 晚到的用量必須補記'
        row = generations(c)[0]
        assert row == {'status': 'failed', 'error_code': 'provider_timeout', 'cost_status': 'known', 'cost_microusd': 100,
                       'input_tokens': 1000, 'output_tokens': 200}, '維持逾時失敗，不誤判成功'
        assert sorted(r['reservation_microusd'] for r in ledger(c)) == [-900, 1000], '預留依實際費用結算'
        again = c.post('/api/ai/generate', json=DRAFT)
        assert again.status_code == 504 and provider.calls == 1, '重送同一請求不再呼叫'
        assert sorted(r['reservation_microusd'] for r in ledger(c)) == [-900, 1000], '不重複結算'


def test_worker_timeout_then_late_usage_is_settled_and_run_still_completes(tmp_path, monkeypatch):
    priced(monkeypatch)
    monkeypatch.setenv('LIFEWORLD_AI_TIMEOUT_SECONDS', '1')
    provider = SlowLiveWithUsage()
    with make_client(tmp_path, provider) as c:
        ready(c, 'late_worker')
        work_id = start(c, [copy_card(c), copy_card(c, 1)]).json()['id']
        detail = run_to_end(c, work_id)
        assert detail['run']['status'] == 'completed', '逾時的那段以新嘗試重做，作品照常完成'
        assert wait_for(lambda: all(r['cost_status'] == 'known' for r in generations(c))), '逾時那次晚到的用量也要補記'
        rows = generations(c)
        timed_out = [r for r in rows if r['error_code'] == 'provider_timeout']
        assert len(timed_out) == 1 and timed_out[0]['status'] == 'failed' and timed_out[0]['cost_microusd'] == 100
        assert sum(r['reservation_microusd'] for r in ledger(c)) == 100 * len(rows), '每一次呼叫（含逾時）都依實際費用結算'


def test_settlement_records_cost_above_reservation(tmp_path, monkeypatch):
    priced(monkeypatch)
    monkeypatch.setenv('LIFEWORLD_AI_RESERVATION_MICROUSD', '60')  # 實際 100 高於預留 60
    with make_client(tmp_path, LiveFakeWithUsage()) as c:
        ready(c, 'over_reservation')
        assert c.post('/api/ai/generate', json=DRAFT).status_code == 201
        assert sorted(r['reservation_microusd'] for r in ledger(c)) == [40, 60], '帳上是實際費用 100（預留 60＋補記 40）'
