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
 test_multiple_pending_people_survive_saved_draft_without_creating_people,
 test_draft_pending_people_require_registration_and_unique_refs,
 test_pending_people_edit_source_and_ambiguous_confirm_fail_without_orphans,
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

# 草稿核對資料沿用既有JSON欄位，驗證PG交易與SQLite契約一致。
from test_draft_review import (
 test_saved_review_roundtrip_and_confirm_creates_selected_fact_once,
 test_raw_edit_preserves_review_but_invalidates_raw_candidates,
 test_legacy_confirm_cannot_silently_drop_saved_person_candidates,
 test_review_owner_isolation_incomplete_evidence_and_manual_preservation,
 test_saved_review_person_revision_conflict_rolls_back_new_people,
 test_guest_can_save_manual_review_without_person_candidates,
)
from test_draft_review import (
 test_manual_candidates_survive_raw_edit_and_two_targets_remain_separate,
 test_review_invalid_targets_and_duplicate_refs_do_not_create_drafts,
)

from test_draft_review import test_confirmed_mention_can_source_explicit_fact_without_becoming_interaction


# 生日/任職核對草稿與正式Confirm沿用同一受限PG交易。
from test_draft_basic_review import (
 test_basic_review_roundtrip_new_people_session_retry_and_independent_values,
 test_basic_source_changes_revoke_raw_only_and_unresolved_cannot_confirm,
 test_basic_incomplete_preserved_and_no_legacy_silent_drop_or_mixed_contract,
 test_basic_review_guest_owner_and_duplicate_reference_boundaries,
 test_existing_employment_partial_patch_and_late_birthday_conflict_are_atomic,
 test_basic_existing_job_cannot_target_other_person_and_empty_birthday_requires_explicit_clear,
)

# 正式HTTP入口隔離亦在受限PG Runtime核對；不只靠SQLite或靜態路由搜尋。
from test_role_profile_boundary import (
 test_role_profile_write_not_registered,
 test_role_profile_absent_from_openapi,
)
