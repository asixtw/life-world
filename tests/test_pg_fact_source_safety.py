"""F5本機PG受限Runtime；只新增合成Owner，不DDL/GRANT/TRUNCATE，不連Cloud SQL。"""
import os
from contextlib import closing
from datetime import datetime,timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
import test_fact_source_safety as safety
import test_fact_provenance_contract as provenance
from conftest import register as original_register

pytestmark=pytest.mark.skipif(not os.environ.get('LIFEWORLD_INTEGRATION_PG_CONFIG'),reason='需要已核准本機PG合成環境')

@pytest.fixture
def app(tmp_path,monkeypatch):
    from scripts.pg_integration_fixture import connect,config,DB
    from app.main import create_app
    from app.postgres import PostgresDatabase
    from app.runtime import RuntimeSettings
    with closing(connect(DB,runtime=True)):pass  # 先驗本機cluster/DB marker，失配不連業務服務。
    settings=RuntimeSettings(backend='postgresql',db_host='127.0.0.1',db_port=57518,db_name=DB,db_user='lw_e2e_app',db_password=config()['password'],pg_tls='disable',relation_source_store='link_table')
    for module in (safety,provenance):monkeypatch.setattr(module,'register',lambda c:original_register(c,'f5_'+uuid4().hex[:16]))
    return create_app(data_dir=tmp_path,database=PostgresDatabase(settings),settings=settings,clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))

@pytest.fixture
def client(app):
    with TestClient(app) as client:yield client

from test_fact_source_safety import (
 test_rejected_mixed_sources_roll_back_and_new_source_does_not_restore_old,
 test_duplicate_before_and_after_revoke_never_replays_writes,
 test_existing_source_evidence_cannot_be_silently_overwritten,
)
from test_fact_provenance_contract import test_normal_upsert_must_not_restore_revoked_fact_source
