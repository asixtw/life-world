"""既有本機PG受限Runtime、新合成Owner；不TRUNCATE、DDL、GRANT或刪除其他Owner。"""
import os
from contextlib import closing
from datetime import datetime,timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
import test_review_security_fixes as probes
from conftest import register as original_register

pytestmark=pytest.mark.skipif(not os.environ.get('LIFEWORLD_INTEGRATION_PG_CONFIG'),reason='需要已核准本機PG合成環境')

@pytest.fixture
def app(tmp_path,monkeypatch):
    from scripts.pg_integration_fixture import connect,config,DB
    from app.main import create_app
    from app.postgres import PostgresDatabase
    from app.runtime import RuntimeSettings
    # 先讀既有cluster/database marker，指向非本機立即拒絕；不呼叫有GRANT副作用的fixture。
    with closing(connect(DB,runtime=True)):pass
    settings=RuntimeSettings(backend='postgresql',db_host='127.0.0.1',db_port=57518,db_name=DB,db_user='lw_e2e_app',db_password=config()['password'],pg_tls='disable',relation_source_store='link_table')
    monkeypatch.setattr(probes,'register',lambda c:original_register(c,'review_'+uuid4().hex[:16]))
    return create_app(data_dir=tmp_path,database=PostgresDatabase(settings),settings=settings,clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))

@pytest.fixture
def client(app):
    with TestClient(app) as client:yield client

from test_review_security_fixes import (
 test_unrelated_person_source_rejected,
 test_withdrawn_story_invalidates_basic_source,
 test_all_basic_source_writes_roll_back_and_confirmed_mentions_remain_allowed,
 test_story_source_projection_preserves_history_and_manual_withdrawal,
)


def test_media_work_pg_global_quota_and_duplicate_serialization(app,client):
    """PG advisory lock序列化父工作與成本；只新增本測試Owner的合成收據。"""
    import json
    from datetime import timedelta
    from concurrent.futures import ThreadPoolExecutor
    from app.ai_runtime import AISettings,AIRuntime
    from test_ai_runtime import Provider
    from conftest import onboard
    me,_=onboard(client);original_register(client,'media_pg_'+uuid4().hex[:12])
    # 保留既有時鐘與其他Owner收據；只把本次一個工作的額度加到目前基線，不清全庫。
    with app.state.service.db.connect() as db:
        rows=db.execute("SELECT operation,response FROM requests WHERE operation IN ('ai_attempt_v1','ai_media_work_v1') AND (response::jsonb->>'created_at') > ?",((app.state.service.now()-timedelta(days=1)).isoformat(),)).fetchall()
    baseline_jobs=sum(row['operation']=='ai_media_work_v1' or not json.loads(row['response']).get('media_work_id') for row in rows)
    baseline_cost=sum(json.loads(row['response'])['reservation_microusd'] for row in rows if row['operation']=='ai_attempt_v1')
    provider=Provider('{"text":"PG合成片段"}')
    r=AIRuntime(app.state.service,AISettings(provider='gemini',model='gemini-synthetic',approved=True,max_total_budget_microusd=9_000_000_000,max_owner_daily_calls=1,max_global_calls=baseline_jobs+1,reservation_microusd=100,max_budget_microusd=baseline_cost+1000),provider=provider)
    def start(_):
        try:return r.begin_media_work(me['owner_id'],'synthetic-pcm','pg-job')
        except Exception as e:return e.code
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(start,range(4)))
    works=[x for x in results if isinstance(x,tuple)]
    assert len(works)==1 and results.count('ai_request_already_reserved')==3
    for i in range(2):r.recognize(me['owner_id'],'audio','audio/wav',bytes([i]),media_work=works[0],request_id='pg-seg-'+str(i))
    assert len(provider.calls)==2 and r.usage(me['owner_id'])['reserved_microusd']==200
    with pytest.raises(Exception) as exc:r.begin_media_work(me['owner_id'],'different','second-job')
    assert exc.value.code=='ai_quota_reached'
