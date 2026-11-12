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
