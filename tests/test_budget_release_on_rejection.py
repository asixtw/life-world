"""每日金額上限：供應商明確拒絕（HTTP 429、503）而且沒有回報用量的呼叫，不再佔住預留。

2026-11-12 實測：Gemini 過載時每成功一次約有 0.55 次失敗。原本的規則是「不知道用量就把預留保留 24 小時」，
結果實際花費約 US$0.07，卻有 US$12 的預留被失敗的呼叫佔住，每日上限 US$19 很快就擋住生成。
429（額度／速率）與 503（服務過載）是供應商在處理前就拒絕，不會產生費用，所以這兩種把預留全數退回；
逾時、連線中斷與其他錯誤仍然不知道供應商有沒有計算，維持原樣（預留保留到 24 小時後）。

只用隔離 SQLite 與標示為真實的 Fake Provider（不連網、不計費）。
"""
from dataclasses import replace

import pytest

from app.ai_text import ProviderFailure
from test_generation_8030 import DRAFT, LiveFake, copy_card, generations, ledger, make_client, priced, ready, start


class LiveRejected(LiveFake):
    """標示為真實呼叫；前 rejected 次被供應商以指定的 HTTP 狀態拒絕（沒有用量），之後正常回傳並附用量（每次實際費用 100）。"""

    def __init__(self, status, rejected=10 ** 6):
        super().__init__()
        self.status, self.rejected, self.calls = status, rejected, 0

    def generate(self, request):
        self.calls += 1
        if self.calls <= self.rejected:
            raise ProviderFailure('provider_error', http_status=self.status)
        return replace(super().generate(request), input_tokens=1000, output_tokens=200)


@pytest.mark.parametrize('status', [429, 503])
def test_explicit_rejection_without_usage_releases_the_reservation(tmp_path, monkeypatch, status):
    priced(monkeypatch)
    provider = LiveRejected(status)
    with make_client(tmp_path, provider) as c:
        ready(c, f'rejected_{status}')
        first = c.post('/api/ai/generate', json=DRAFT)
        assert first.status_code == 502, '生成仍然是失敗，不因為退回預留而變成成功'
        row = generations(c)[0]
        assert (row['status'], row['cost_status'], row['cost_microusd']) == ('failed', 'known', 0), '供應商沒有處理這次請求：費用是 0，不是未知'
        rows = ledger(c)
        assert sorted(r['reservation_microusd'] for r in rows) == [-1000, 1000], '預留 1000 全數退回，帳上不佔額度'
        assert len({r['created_at'] for r in rows}) == 1, '退回的紀錄和原預留同一時間，一起滾出 24 小時'
        again = c.post('/api/ai/generate', json=DRAFT)
        assert again.status_code == 502 and provider.calls == 1, '同一 request_id 重送不再呼叫供應商'
        assert ledger(c) == rows, '重送不重複預留、不重複退回'


@pytest.mark.parametrize('status', [500, None])
def test_other_failures_without_usage_still_hold_the_reservation(tmp_path, monkeypatch, status):
    priced(monkeypatch)
    with make_client(tmp_path, LiveRejected(status)) as c:
        ready(c, f'held_{status}')
        assert c.post('/api/ai/generate', json=DRAFT).status_code == 502
        row = generations(c)[0]
        assert (row['status'], row['cost_status'], row['cost_microusd']) == ('failed', 'unknown', None)
        assert [r['reservation_microusd'] for r in ledger(c)] == [1000], '不確定供應商有沒有計算：預留保留到 24 小時後'


def advance_past_waits(c, work_id, limit=80):
    """逐段推進到完成或失敗；遇到重試的等待就當作時間已到。被每日金額上限擋住時停下來，回傳當時的詳情。"""
    queue = c.app.state.step_queue
    for _ in range(limit):
        result = c.post(f'/api/generation/runs/{work_id}/step').json()
        detail = result['detail']
        if detail['run']['status'] in ('completed', 'failed'):
            return detail
        if (detail['run'].get('notice') or {}).get('code') == 'budget_wait':
            return detail
        entry = queue.take(work_id)
        if entry is not None:
            queue.enqueue('', entry['payload'], 0)  # 模擬重試的等待時間已到
    raise AssertionError('沒有在預期步數內結束')


def test_rejected_calls_do_not_stop_a_work_at_the_daily_cap(tmp_path, monkeypatch):
    """排程生成：前 6 次呼叫都被 503 拒絕，每日上限只夠 3 次預留。退回預留後作品照常完成，帳上只剩成功呼叫的實際費用。"""
    priced(monkeypatch)
    monkeypatch.setenv('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD', '3000')
    with make_client(tmp_path, LiveRejected(503, rejected=6)) as c:
        ready(c, 'rejected_run')
        work_id = start(c, [copy_card(c), copy_card(c, 1)]).json()['id']
        detail = advance_past_waits(c, work_id)
        assert (detail['run'].get('notice') or {}).get('code') != 'budget_wait', '被拒絕的呼叫沒有花錢，不應該用掉每日上限'
        assert detail['run']['status'] == 'completed'
        rows = generations(c)
        rejected = [r for r in rows if r['status'] == 'failed']
        succeeded = [r for r in rows if r['status'] == 'succeeded']
        assert len(rejected) == 6 and all(r['cost_status'] == 'known' and r['cost_microusd'] == 0 for r in rejected)
        assert sum(r['reservation_microusd'] for r in ledger(c)) == 100 * len(succeeded), '帳上只剩成功呼叫的實際費用'


def test_rate_limited_calls_in_a_run_release_the_reservation(tmp_path, monkeypatch):
    """排程生成把 429 另外分類成「額度不足」；分類不同，預留一樣要退回。"""
    priced(monkeypatch)
    monkeypatch.setenv('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD', '3000')
    with make_client(tmp_path, LiveRejected(429, rejected=5)) as c:
        ready(c, 'limited_run')
        work_id = start(c, [copy_card(c)]).json()['id']
        detail = advance_past_waits(c, work_id)
        assert detail['run']['status'] == 'completed'
        limited = [r for r in generations(c) if r['error_code'] == 'provider_rate_limited']
        assert len(limited) == 5 and all(r['cost_microusd'] == 0 for r in limited)
