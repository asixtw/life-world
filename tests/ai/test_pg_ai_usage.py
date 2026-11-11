"""僅本機marker PG18；以受限Runtime驗證AI預留鎖及帳號隔離，沒有真模型呼叫。"""
import json,os
import pytest
from fastapi.testclient import TestClient
from conftest import onboard,register
from test_pg_integration_person_details import app
from test_ai_runtime import Provider
from app.ai_runtime import AISettings,AIRuntime
pytestmark=pytest.mark.skipif(not os.environ.get('LIFEWORLD_INTEGRATION_PG_CONFIG'),reason='需要明確本機PG18合成副本')

@pytest.fixture
def prepared(app):
    with TestClient(app) as client:
        me,g=onboard(client);register(client)
        p=Provider(json.dumps({'summary':'合成整理','tasks':[]}))
        settings=AISettings(provider='gemini',model='gemini-synthetic',approved=True,max_total_budget_microusd=10000,max_owner_daily_calls=2,max_global_calls=3,reservation_microusd=100,max_budget_microusd=300)
        runtime=AIRuntime(app.state.service,settings,provider=p)
        yield app,client,me,g,runtime,p

from test_usage_isolation import (
 test_usage_only_includes_current_owner_and_unknown_cost,
 test_usage_without_login_guest_and_admin_query_cannot_bypass,
 test_duplicate_ai_request_reserves_and_calls_provider_once,
 test_failed_unknown_cost_remains_reserved_and_budget_is_finite,
 test_inflight_guard_rejects_without_reservation_and_releases_after_failure,
 test_concurrent_same_request_and_http_retry_do_not_double_charge,
)
from test_ai_runtime import test_concurrent_reservations_do_not_overrun_global_daily_cap
