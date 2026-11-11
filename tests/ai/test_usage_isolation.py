"""AI費用只顯示本人metadata；模型一律明示替身，不呼叫真Gemini。"""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from test_ai_runtime import prepared
from conftest import onboard,register
from app.ai_runtime import AISettings


def test_alpha_budget_above_twenty_and_high_daily_calls_are_configurable():
    s=AISettings(provider='gemini',model='gemini-synthetic',approved=True,max_total_budget_microusd=100_000_000,reservation_microusd=100,max_budget_microusd=5_000_000,max_owner_daily_calls=500,max_global_calls=5000)
    assert s.max_total_budget_microusd==100_000_000
    with pytest.raises(ValueError):replace(s,max_total_budget_microusd=0)


def test_usage_only_includes_current_owner_and_unknown_cost(prepared):
    app,c,me,g,runtime,p=prepared;app.state.ai_runtime=runtime
    runtime.generate(me['owner_id'],'experience',{'raw_text':'甲的合成來源'})
    with TestClient(app) as other:
        other_me,_=onboard(other);register(other,'ai_usage_b')
        own=other.get('/api/ai/usage');assert own.status_code==200
        assert own.json()['reserved_microusd']==0 and own.json()['calls']==0 and own.json()['receipts']==[]
        runtime.generate(other_me['owner_id'],'experience',{'raw_text':'乙的合成來源'})
        assert other.get('/api/ai/usage').json()['calls']==1
    usage=c.get('/api/ai/usage').json()
    assert usage['calls']==1 and usage['reserved_microusd']==100
    assert usage['input_tokens']==3 and usage['output_tokens']==4
    assert usage['actual_invoice_cost_microusd'] is None
    assert len(usage['receipts'])==1
    assert not {'global_reserved_microusd','remaining_microusd','total_budget_microusd','historical_reserved_microusd'} & usage.keys()
    assert '甲的合成來源' not in str(usage) and '乙的合成來源' not in str(usage)


def test_usage_without_login_guest_and_admin_query_cannot_bypass(prepared):
    app,c,me,g,runtime,p=prepared;app.state.ai_runtime=runtime
    with TestClient(app) as anon:
        assert anon.get('/api/ai/usage').status_code==401
        onboard(anon)
        assert anon.get('/api/ai/usage').status_code==403
    for query in ['?owner_id=other','?scope=global','?admin=true']:
        r=c.get('/api/ai/usage'+query);assert r.status_code==200
        assert 'global_reserved_microusd' not in r.json()
    assert c.get('/api/ai/admin/usage').status_code==404


def test_duplicate_ai_request_reserves_and_calls_provider_once(prepared):
    app,c,me,g,runtime,p=prepared
    runtime.generate(me['owner_id'],'experience',{'raw_text':'合成'},request_id='repeat-synthetic')
    with pytest.raises(Exception) as e:runtime.generate(me['owner_id'],'experience',{'raw_text':'合成'},request_id='repeat-synthetic')
    assert e.value.code=='ai_request_already_reserved' and len(p.calls)==1
    assert runtime.usage(me['owner_id'])['calls']==1


def test_unlimited_total_requires_explicit_isolated_e2e_env(monkeypatch):
    values={'LIFEWORLD_AI_BUDGET_MODE':'isolated_e2e_unlimited_total','LIFEWORLD_DB_NAME':'life_world_alpha','LIFEWORLD_ACCESS_MODE':'public_alpha'}
    for k,v in values.items():monkeypatch.setenv(k,v)
    with pytest.raises(ValueError):AISettings.from_env()
    monkeypatch.setenv('LIFEWORLD_DB_NAME','life_world_e2e');monkeypatch.setenv('LIFEWORLD_ACCESS_MODE','legacy')
    assert AISettings.from_env().budget_mode=='isolated_e2e_unlimited_total'


def test_failed_unknown_cost_remains_reserved_and_budget_is_finite(prepared):
    app,c,me,g,runtime,p=prepared
    runtime.settings=replace(runtime.settings,max_total_budget_microusd=100)
    p.text='invalid JSON'
    with pytest.raises(Exception):runtime.generate(me['owner_id'],'experience',{'raw_text':'合成失敗'})
    usage=runtime.usage(me['owner_id'])
    assert usage['reserved_microusd']==100 and usage['unknown_cost_calls']==1
    assert usage['reported_cost_microusd'] is None and usage['receipts'][0]['status']=='failed'
    with pytest.raises(Exception) as e:runtime.generate(me['owner_id'],'experience',{'raw_text':'不能超額'})
    assert e.value.code=='ai_total_budget_reached' and len(p.calls)==1


def test_inflight_guard_rejects_without_reservation_and_releases_after_failure(prepared):
    from threading import Event
    from app.ai_runtime import AIRuntime
    app,c,me,g,runtime,p=prepared
    entered=Event();release=Event()
    def blocked(prompt,tokens):
        entered.set();assert release.wait(5)
        raise ValueError('synthetic-provider-failure')
    p.generate=blocked
    limited=AIRuntime(app.state.service,replace(runtime.settings,max_concurrent_calls=1),provider=p)
    def run():
        try:limited.generate(me['owner_id'],'experience',{'raw_text':'合成'})
        except Exception as e:return e.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(run);assert entered.wait(5)
        try:
            assert run()=='ai_busy'
            assert limited.usage(me['owner_id'])['calls']==1
        finally:release.set()
        assert first.result(5)=='ai_invalid_candidate'
    assert run()=='ai_invalid_candidate'
    assert limited.usage(me['owner_id'])['calls']==2


def test_concurrent_same_request_and_http_retry_do_not_double_charge(prepared):
    app,c,me,g,runtime,p=prepared;app.state.ai_runtime=runtime
    def run(i):
        try:runtime.generate(me['owner_id'],'experience',{'raw_text':'同一合成來源'},request_id='same-concurrent');return 'ok'
        except Exception as e:return e.code
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,range(4)))
    assert results.count('ok')==1 and results.count('ai_request_already_reserved')==3
    assert len(p.calls)==1 and runtime.usage(me['owner_id'])['calls']==1
    from conftest import draft
    d=draft(c,g)
    url='/api/drafts/'+d['id']+'/suggest';headers={'Idempotency-Key':'http-same'}
    assert c.post(url,headers=headers).status_code==200
    r=c.post(url,headers=headers)
    assert r.status_code==409 and r.json()['error']['code']=='ai_request_already_reserved'
    assert len(p.calls)==2


def test_e2e_unlimited_total_still_has_daily_budget_and_historical_is_counted(prepared):
    app,c,me,g,runtime,p=prepared
    runtime.settings=replace(runtime.settings,budget_mode='isolated_e2e_unlimited_total',max_total_budget_microusd=0,max_budget_microusd=100)
    runtime.generate(me['owner_id'],'experience',{'raw_text':'E2E有限日額'})
    with pytest.raises(Exception) as e:runtime.generate(me['owner_id'],'experience',{'raw_text':'日額拒絕'})
    assert e.value.code=='ai_quota_reached'
    runtime.settings=replace(runtime.settings,budget_mode='finite',max_total_budget_microusd=200,historical_reservation_microusd=100,max_budget_microusd=1000)
    with pytest.raises(Exception) as e:runtime.generate(me['owner_id'],'experience',{'raw_text':'歷史亦占額度'})
    assert e.value.code=='ai_total_budget_reached' and len(p.calls)==1
