"""費用限額依Owner獨立；只用合成資料和替身，不呼叫付費Provider。"""
from dataclasses import replace
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from test_ai_runtime import prepared
from conftest import onboard, register
from app.ai_runtime import AISettings
from app.runtime import RuntimeSettings
from app.auth_rate_limit import AlphaDatabase, AuthRateLimiter


@pytest.fixture
def owner_budget(prepared, monkeypatch):
    app,client,me,goal,runtime,provider=prepared
    for key,value in {'LIFEWORLD_AI_BUDGET_SCOPE':'owner','LIFEWORLD_AI_PROVIDER':'gemini','LIFEWORLD_AI_MODEL':'gemini-synthetic','LIFEWORLD_AI_CALLS_APPROVED':'true','LIFEWORLD_AI_RESERVATION_MICROUSD':'100','LIFEWORLD_AI_DAILY_BUDGET_MICROUSD':'100','LIFEWORLD_AI_TOTAL_BUDGET_MICROUSD':'1000','LIFEWORLD_AI_OWNER_DAILY_CALLS':'100','LIFEWORLD_AI_GLOBAL_DAILY_CALLS':'1000'}.items():monkeypatch.setenv(key,value)
    runtime.settings=AISettings.from_env()
    with TestClient(app) as other:
        second,_=onboard(other);register(other,'budget_owner_b')
    return app,client,me,second,runtime,provider


def test_daily_budget_and_unknown_failure_are_private_to_owner(owner_budget):
    app,client,first,second,runtime,provider=owner_budget
    provider.text='not-json'
    with pytest.raises(Exception) as failed:runtime.generate(first['owner_id'],'experience',{'raw_text':'合成來源'})
    assert failed.value.code=='ai_invalid_candidate'
    # 費用未知/失敗仍保留A的預留，但不能消耗B的額度。
    runtime.reserve(second['owner_id'],'experience','owner-b')
    with pytest.raises(Exception) as exhausted:runtime.reserve(first['owner_id'],'experience','owner-a-again')
    assert exhausted.value.code=='ai_quota_reached'
    usage=runtime.usage(first['owner_id'])
    assert usage['calls']==1 and usage['reserved_microusd']==100 and usage['unknown_cost_calls']==1
    assert runtime.usage(second['owner_id'])['calls']==1


def test_total_budget_owner_scope_keeps_own_history_across_daily_windows(owner_budget):
    app,client,first,second,runtime,provider=owner_budget
    # 歷史全域預留無法歸戶，不能重複加到每個Owner；原設定仍保留供內部追溯。
    runtime.settings=replace(runtime.settings,max_budget_microusd=1000,max_total_budget_microusd=100,historical_reservation_microusd=50)
    runtime.reserve(first['owner_id'],'experience','first')
    later=app.state.service.now()+timedelta(days=2);app.state.service.clock=lambda:later
    with pytest.raises(Exception) as exhausted:runtime.reserve(first['owner_id'],'experience','next-day')
    assert exhausted.value.code=='ai_total_budget_reached'
    runtime.reserve(second['owner_id'],'experience','independent')
    assert runtime.settings.historical_reservation_microusd==50


def test_concurrent_reservations_cannot_overdraw_one_owner(owner_budget):
    app,client,first,second,runtime,provider=owner_budget
    def reserve(i):
        try:runtime.reserve(first['owner_id'],'experience','concurrent-'+str(i));return 'ok'
        except Exception as e:return e.code
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(reserve,range(4)))
    assert results.count('ok')==1 and results.count('ai_quota_reached')==3
    runtime.reserve(second['owner_id'],'experience','unaffected')
    assert runtime.usage(first['owner_id'])['reserved_microusd']==100


def test_disabled_lifetime_write_quota_still_counts_without_disabling_rate_protection(prepared,monkeypatch):
    app,client,me,goal,runtime,provider=prepared
    monkeypatch.setenv('LIFEWORLD_ALPHA_WRITE_QUOTA_ENFORCED','false')
    settings=replace(RuntimeSettings.from_env(),auth_rate_secret='synthetic-only-key-'*3,auth_source_mode='direct',alpha_owner_writes=1,alpha_global_writes=1)
    limiter=AuthRateLimiter(settings,app.state.service.now)
    limiter.backend=app.state.service.db.backend
    db=AlphaDatabase(app.state.service.db,limiter)
    for _ in range(3):
        with db.connect(write=True,owner=me['owner_id']):pass
    with db.connect() as c:
        rows=c.execute("SELECT attempts FROM auth_rate_buckets WHERE scope IN ('alpha_writes_total','alpha_owner_writes')").fetchall()
        assert sorted(r['attempts'] for r in rows)==[3,3]
    with app.state.service.db.connect(write=True) as c:
        assert limiter.take(c,'login_source_attempt','synthetic',1,900) is None
        blocked=limiter.take(c,'login_source_attempt','synthetic',1,900)
        assert blocked.status==429


def test_scope_configuration_is_explicit_and_defaults_remain_safe(monkeypatch):
    monkeypatch.setenv('LIFEWORLD_AI_BUDGET_SCOPE','invalid')
    with pytest.raises(ValueError):AISettings.from_env()
    assert RuntimeSettings().alpha_write_quota_enforced is True
