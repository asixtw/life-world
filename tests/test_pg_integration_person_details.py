"""Owner快照空副本上的PG18 API驗收；僅明確本機設定才執行，不連Cloud SQL。"""
import os
from contextlib import closing
from datetime import datetime,timezone
import pytest
from fastapi.testclient import TestClient

pytestmark=pytest.mark.skipif(not os.environ.get('LIFEWORLD_INTEGRATION_PG_CONFIG'),reason='需要明確本機PG18合成副本')

@pytest.fixture
def app(tmp_path):
    from scripts.pg_integration_fixture import connect,config,DB,SCHEMA,grant_candidate_permissions
    from app.main import create_app
    from app.postgres import PostgresDatabase
    from app.runtime import RuntimeSettings
    from app.config import DemoPolicy
    # connect先核對本機cluster及database marker；只清理這個無業務資料的合成副本。
    with closing(connect(DB)) as raw,closing(raw.cursor()) as c:
        c.execute('SELECT tablename FROM pg_tables WHERE schemaname=%s'.replace('%s','?'),(SCHEMA,))
        names=[r[0] for r in c.fetchall()]
        from scripts.pg_integration_fixture import ident
        c.execute('TRUNCATE '+','.join(SCHEMA+'.'+ident(n) for n in names)+' CASCADE')
    grant_candidate_permissions()
    settings=RuntimeSettings(backend='postgresql',db_host='127.0.0.1',db_port=57518,db_name=DB,db_user='lw_e2e_app',db_password=config()['password'],pg_tls='disable',relation_source_store='link_table')
    return create_app(data_dir=tmp_path,database=PostgresDatabase(settings),settings=settings,policy=DemoPolicy(points_per_experience=3,max_upload_bytes=4096),clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))

@pytest.fixture
def client(app):
    with TestClient(app) as c:yield c

# 同一API斷言分別在SQLite及實際PG Runtime執行，不以替身資料庫冒充。
from test_person_basic_api import (
 test_birthday_roundtrip_correction_and_history,
 test_two_current_employments_and_patch_preserve_other_fields,
 test_details_cross_owner_and_unconfirmed_are_refused,
 test_confirm_two_new_people_basic_data_and_retry,
 test_confirm_late_basic_conflict_rolls_back_all_rows,
 test_employment_patch_cannot_clear_both_fields,
 test_basic_source_withdrawal_preserves_values_history_and_retry,
 test_source_withdrawal_csrf_conflict_and_transaction_rollback,
)


def test_runtime_cannot_change_schema_or_delete_history():
    from scripts.pg_integration_fixture import connect,DB
    # 權限驗收用catalog查詢，不嘗試DDL或破壞資料。
    with closing(connect(DB,runtime=True)) as raw,closing(raw.cursor()) as c:
        c.execute("SELECT current_user,has_schema_privilege(current_user,'lw_core_draft','CREATE'),has_table_privilege(current_user,'lw_core_draft.person_basic_detail_history','DELETE'),has_table_privilege(current_user,'lw_core_draft.person_employment_history','UPDATE')")
        assert tuple(c.fetchone())==('lw_e2e_app',False,False,False)


def test_migration_replay_fails_without_changing_structure():
    from scripts.pg_integration_fixture import apply_candidate,snapshot,connect,DB
    before=snapshot()['structure']
    with pytest.raises(Exception,match='existing target requires receipt'):
        apply_candidate()
    assert snapshot()['structure']==before

# 多人事實及草稿清除沿用相同契約，額外驗證PG欄位授權與實際交易。
from test_integration_confirm_targets import (
 test_targeted_confirm_creates_people_and_facts_atomically,
 test_invalid_target_rolls_back_new_people,
 test_delete_saved_draft_revision_owner_and_retry,
 test_unqualified_people_cannot_be_real_participants,
 test_existing_person_revision_failure_rolls_back_all_new_people,
)


def test_draft_delete_permission_failure_rolls_back_and_same_request_can_retry(client):
    from conftest import onboard,register,draft
    from scripts.pg_integration_fixture import connect,DB,OWNER,APP,grant_candidate_permissions
    _,g=onboard(client);register(client)
    d=draft(client,g,story={'title':'待刪合成草稿','participants':[],'mentions':[]})
    url='/api/drafts/'+d['id'];body={'request_id':'pg-delete-permission','expected_revision':d['revision']}
    # 重現真實兩庫現有DELETE缺口；只在本機marker副本撤除/恢復提議權限。
    with closing(connect(DB)) as raw,closing(raw.cursor()) as c:
        c.execute('SET ROLE '+OWNER);c.execute('REVOKE DELETE ON lw_core_draft.drafts FROM '+APP)
    try:
        failed=client.request('DELETE',url,json=body)
        assert failed.status_code==503,failed.text
        assert client.get(url).status_code==200
        with closing(connect(DB)) as raw,closing(raw.cursor()) as c:
            c.execute('SELECT count(*) FROM lw_core_draft.draft_stories WHERE draft_id=?',(d['id'],))
            assert c.fetchone()[0]==1
    finally:
        grant_candidate_permissions()
    retried=client.request('DELETE',url,json=body)
    assert retried.status_code==200,retried.text
    assert client.request('DELETE',url,json=body).json()==retried.json()


def test_runtime_cannot_reassign_basic_data_owner_or_subject():
    from scripts.pg_integration_fixture import connect,DB
    with closing(connect(DB,runtime=True)) as raw,closing(raw.cursor()) as c:
        for table,column in [('person_basic_details','owner_id'),('person_basic_details','person_id'),('person_employments','owner_id'),('person_employments','person_id'),('person_employments','id')]:
            c.execute('SELECT has_column_privilege(current_user,?,?,?)',('lw_core_draft.'+table,column,'UPDATE'))
            assert not c.fetchone()[0],(table,column)
