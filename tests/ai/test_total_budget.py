"""測試期總預算不隨24小時配額恢復而被重置。"""
from dataclasses import replace
from datetime import timedelta
import pytest
from test_ai_runtime import prepared


def test_total_budget_survives_daily_window(prepared):
    app,c,me,g,runtime,provider=prepared
    runtime.settings=replace(runtime.settings,max_total_budget_microusd=100)
    runtime.reserve(me['owner_id'],'experience','synthetic-fingerprint')
    instant=app.state.service.now()+timedelta(days=2);app.state.service.clock=lambda:instant
    with pytest.raises(Exception) as exc:runtime.reserve(me['owner_id'],'experience','new-day')
    assert exc.value.code=='ai_total_budget_reached'
    assert provider.calls==[]


def test_audio_segments_use_money_guard_not_daily_text_count(prepared):
    app,c,me,g,runtime,provider=prepared
    runtime.settings=replace(runtime.settings,max_owner_daily_calls=1,max_global_calls=1,max_total_budget_microusd=1000)
    runtime.reserve(me['owner_id'],'media','segment-1')
    runtime.reserve(me['owner_id'],'media','segment-2')
    # 媒體仍消耗每日金額；不能用免次數限制繞過預算。
    runtime.reserve(me['owner_id'],'media','segment-3')
    with pytest.raises(Exception) as exc:runtime.reserve(me['owner_id'],'media','segment-4')
    assert exc.value.code=='ai_quota_reached'


def test_pg_aggregate_text_budget_is_normalized(prepared,monkeypatch):
    """PG Repository會將聚合numeric序列化為字串，不能直接與int相加。"""
    from contextlib import contextmanager
    app,c,me,g,runtime,provider=prepared
    runtime.settings=replace(runtime.settings,max_total_budget_microusd=300)
    original=runtime.service.db.connect
    class TextAggregate:
        def fetchone(self):return {'used':'100'}
    class Proxy:
        def __init__(self,c):self.c=c
        def execute(self,sql,*args):
            if 'COALESCE(sum(' in sql:return TextAggregate()
            return self.c.execute(sql,*args)
    @contextmanager
    def connect(*args,**kwargs):
        with original(*args,**kwargs) as c:yield Proxy(c)
    monkeypatch.setattr(runtime.service.db,'connect',connect)
    runtime.reserve(me['owner_id'],'experience','pg-text-aggregate')


def test_approved_requires_hard_cap_and_loads_env(monkeypatch):
    from app.ai_runtime import AISettings
    base={'provider':'gemini','model':'gemini-synthetic','approved':True,'reservation_microusd':100,'max_budget_microusd':1000}
    with pytest.raises(ValueError):AISettings(**base)
    with pytest.raises(ValueError):AISettings(**base,max_total_budget_microusd=20_000_001)
    for key,value in {'LIFEWORLD_AI_PROVIDER':'gemini','LIFEWORLD_AI_MODEL':'gemini-synthetic','LIFEWORLD_AI_CALLS_APPROVED':'true','LIFEWORLD_AI_RESERVATION_MICROUSD':'100','LIFEWORLD_AI_DAILY_BUDGET_MICROUSD':'1000','LIFEWORLD_AI_TOTAL_BUDGET_MICROUSD':'19000000','LIFEWORLD_AI_HISTORICAL_RESERVATION_MICROUSD':'1000000'}.items():monkeypatch.setenv(key,value)
    settings=AISettings.from_env();assert settings.max_total_budget_microusd==19_000_000 and settings.historical_reservation_microusd==1_000_000


def test_usage_reports_reserved_not_unknown_invoice_cost(prepared):
    app,c,me,g,runtime,provider=prepared
    runtime.reserve(me['owner_id'],'experience','usage-report')
    result=runtime.usage(me['owner_id'])
    assert result['global_reserved_microusd']==100 and result['remaining_microusd']==9900
    assert result['actual_invoice_cost_microusd'] is None and result['receipts']==[]
