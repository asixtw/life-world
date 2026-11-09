"""Alpha部署前拒絕錯庫、啟動建帳及無累積預算；不連線任何服務。"""
import pytest
from scripts.alpha_release_plan import validate


def candidate():
    return {'env':{'LIFEWORLD_DB_BACKEND':'postgresql','LIFEWORLD_DB_NAME':'life_world_alpha','LIFEWORLD_DB_USER':'lw_alpha_app','LIFEWORLD_DB_SCHEMA':'lw_core_draft','LIFEWORLD_AI_CALLS_APPROVED':'false'},'secret_refs':{'LIFEWORLD_DB_PASSWORD':'lw-public-alpha-db-password/versions/1'},'historical_reservation_microusd':None}


def test_alpha_plan_accepts_ai_off():
    validate(candidate())


@pytest.mark.parametrize('changes',[{'LIFEWORLD_DB_NAME':'life_world_product_staging'},{'LIFEWORLD_TEST_ACCOUNT_SEED':'forbidden'},{'LIFEWORLD_AI_CALLS_APPROVED':'true','LIFEWORLD_AI_TOTAL_BUDGET_MICROUSD':'0'},{'LIFEWORLD_AI_CALLS_APPROVED':'true','LIFEWORLD_AI_TOTAL_BUDGET_MICROUSD':'20000001'}])
def test_alpha_plan_rejects_unsafe_configuration(changes):
    plan=candidate();plan['env'].update(changes)
    with pytest.raises(ValueError):validate(plan)
