"""受限Runtime、本機marker PG；不TRUNCATE/GRANT、不連Cloud SQL或真AI。"""
import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from app.ai_runtime import AISettings, AIRuntime
from conftest import onboard, register as original_register
from test_ai_runtime import Provider
from test_pg_fact_source_safety import app
import test_owner_budget_policy as policy

pytestmark=pytest.mark.skipif(not os.environ.get('LIFEWORLD_INTEGRATION_PG_CONFIG'),reason='需要既有本機marker PG18')


@pytest.fixture
def prepared(app,monkeypatch):
    # 不清除別人的合成世界；每輪帳號獨立命名，避免共用測試帳密造成假衝突。
    monkeypatch.setattr(policy,'register',lambda client,name='budget':original_register(client,'budget_'+uuid4().hex[:20]))
    with TestClient(app) as client:
        me,goal=onboard(client);original_register(client,'budget_'+uuid4().hex[:20])
        provider=Provider(json.dumps({'summary':'合成','tasks':[]}))
        settings=AISettings(provider='gemini',model='gemini-synthetic',approved=True,max_total_budget_microusd=10000,max_owner_daily_calls=2,max_global_calls=3,reservation_microusd=100,max_budget_microusd=300)
        yield app,client,me,goal,AIRuntime(app.state.service,settings,provider=provider),provider


from test_owner_budget_policy import (
 owner_budget,
 test_daily_budget_and_unknown_failure_are_private_to_owner,
 test_total_budget_owner_scope_keeps_own_history_across_daily_windows,
 test_concurrent_reservations_cannot_overdraw_one_owner,
 test_disabled_lifetime_write_quota_still_counts_without_disabling_rate_protection,
)
