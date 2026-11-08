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
