"""新版Guest限流契約：真交易與來源分層；只使用本機隔離資料庫。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import os
import secrets
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.runtime import RuntimeSettings


@pytest.fixture
def quota_app(tmp_path):
    """固定可推進時鐘；PG模式只允許既有帶marker的合成cluster。"""
    now=[datetime(2026,10,27,7,tzinfo=timezone.utc)]
    apps=[]
    def factory(**overrides):
        settings=RuntimeSettings(access_mode='public_alpha',auth_rate_enabled=True,auth_rate_secret=secrets.token_urlsafe(40),auth_source_mode='shared',registration_enabled=False,**overrides)
        database=None
        if os.environ.get('LIFEWORLD_TEST_BACKEND')=='postgresql':
            from pg_support import database as pg_database
            database=pg_database()
        app=create_app(tmp_path,settings=settings,database=database,clock=lambda:now[0]);apps.append(app);return app
    yield factory,now
    for app in apps:app.state.service.db.close()


@contextmanager
def request_client(app,**kwargs):
    # 多個瀏覽器共用同一服務生命週期；每關閉一個HTTP客戶端不能關閉整個PG pool。
    c=TestClient(app,**kwargs)
    try:yield c
    finally:c.close()


def count(app,table):
    # 僅測試內固定資料表名稱；不將外部輸入插入SQL。
    assert table in ('users','sessions')
    with app.state.service.db.connect() as c:return c.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']


def seed_hourly_boundary(app,now,used=999):
    """只把合成桶移到門檻前，避免測試為碰1000次上限建立1000個世界。"""
    limiter=app.state.service.db.limiter
    with app.state.service.db.connect(write=True) as c:
        assert limiter.take(c,'guest_source_create','v2:unverified-global',1000,3600) is None
        c.execute('UPDATE auth_rate_buckets SET attempts=?,window_started_at=? WHERE scope=?',(used,now.isoformat(),'guest_source_create'))


def test_global_capacity_survives_spoofed_source_headers(quota_app):
    make,_=quota_app;app=make(alpha_worlds_total=3,alpha_worlds_daily=30)
    owners=[]
    for i in range(6):
        with request_client(app,headers={'X-Forwarded-For':f'198.51.100.{i}','X-Real-IP':f'203.0.113.{i}'}) as c:
            r=c.post('/api/auth/guest')
            assert r.status_code==(201 if i<3 else 409)
            if i<3:owners.append(r.json()['owner_id'])
            else:assert r.json()['error']['code']=='guest_capacity_reached'
    assert len(set(owners))==3 and count(app,'users')==3 and count(app,'sessions')==3


def test_daily_limit_retry_after_and_next_window(quota_app):
    make,now=quota_app;app=make(alpha_worlds_total=20,alpha_worlds_daily=2)
    for _ in range(2):
        with request_client(app) as c:assert c.post('/api/auth/guest').status_code==201
    now[0]+=timedelta(seconds=123)
    with request_client(app) as c:
        denied=c.post('/api/auth/guest');assert denied.status_code==429
        assert denied.headers['X-RateLimit-Scope']=='alpha_worlds_daily'
        assert int(denied.headers['Retry-After'])==86400-123
    assert count(app,'users')==2
    now[0]+=timedelta(seconds=86400-123)
    with request_client(app) as c:assert c.post('/api/auth/guest').status_code==201


def test_shared_hourly_budget_cannot_be_reset_by_xff_or_rejection(quota_app):
    make,now=quota_app;app=make(alpha_worlds_total=30,alpha_worlds_daily=30)
    seed_hourly_boundary(app,now[0])
    with request_client(app) as c:assert c.post('/api/auth/guest').status_code==201
    now[0]+=timedelta(seconds=795)
    for forwarded in ['198.51.100.1','forged, arbitrary','203.0.113.19']:
        with request_client(app,headers={'X-Forwarded-For':forwarded}) as c:
            denied=c.post('/api/auth/guest');assert denied.status_code==429
            assert denied.headers['X-RateLimit-Scope']=='guest_source_create'
            assert int(denied.headers['Retry-After'])==2805
    assert count(app,'users')==1
    now[0]+=timedelta(seconds=2805)
    with request_client(app) as c:assert c.post('/api/auth/guest').status_code==201


def test_session_retries_do_not_create_world_or_consume_capacity(quota_app):
    make,_=quota_app;app=make(alpha_worlds_total=1,alpha_worlds_daily=1)
    with request_client(app) as c:
        first=c.post('/api/auth/guest');assert first.status_code==201
        for _ in range(5):
            retry=c.post('/api/auth/guest');assert retry.status_code==200
            assert retry.json()['owner_id']==first.json()['owner_id']
    assert count(app,'users')==1 and count(app,'sessions')==1
    with app.state.service.db.connect() as db:
        assert all(r['attempts']==1 for r in db.execute("SELECT attempts FROM auth_rate_buckets WHERE scope IN ('alpha_worlds_total','alpha_worlds_daily','guest_source_create')").fetchall())


def test_parallel_anonymous_creation_cannot_overshoot_global_capacity(quota_app):
    make,_=quota_app;app=make(alpha_worlds_total=3,alpha_worlds_daily=30)
    def create(_):
        with request_client(app) as c:return c.post('/api/auth/guest').status_code
    with ThreadPoolExecutor(max_workers=8) as executor:codes=list(executor.map(create,range(8)))
    assert codes.count(201)==3 and codes.count(409)==5
    assert count(app,'users')==3 and count(app,'sessions')==3


def test_parallel_valid_session_retries_keep_one_world(quota_app):
    make,_=quota_app;app=make(alpha_worlds_total=1,alpha_worlds_daily=1)
    with request_client(app) as c:
        first=c.post('/api/auth/guest');token=c.cookies.get('lw_session')
    def retry(_):
        with request_client(app) as c:
            c.cookies.set('lw_session',token);r=c.post('/api/auth/guest');return r.status_code,r.json()['owner_id']
    with ThreadPoolExecutor(max_workers=6) as executor:results=list(executor.map(retry,range(6)))
    assert all(code==200 and owner==first.json()['owner_id'] for code,owner in results)
    assert count(app,'users')==1 and count(app,'sessions')==1


def test_verified_direct_peer_retains_per_source_hourly_limit(quota_app):
    make,_=quota_app;app=make(alpha_worlds_total=30,alpha_worlds_daily=30)
    # 只替換測試設定中的模式；正式模式與門檻不因本測試而調低或放寬。
    from dataclasses import replace
    app.state.service.db.limiter.settings=replace(app.state.service.db.limiter.settings,auth_source_mode='direct')
    for i in range(11):
        with request_client(app,client=('198.51.100.1',1000+i)) as c:
            r=c.post('/api/auth/guest');assert r.status_code==(201 if i<10 else 429)
            if i==10:assert int(r.headers['Retry-After'])==3600
    with request_client(app,client=('198.51.100.2',1000)) as c:assert c.post('/api/auth/guest').status_code==201


def test_lifetime_creation_receipt_is_not_only_active_guest_count(quota_app):
    make,_=quota_app;app=make(alpha_worlds_total=3,alpha_worlds_daily=30)
    limiter=app.state.service.db.limiter
    with app.state.service.db.connect(write=True) as db:
        assert limiter.take(db,'alpha_worlds_total','all',3,capacity=True) is None
        db.execute("UPDATE auth_rate_buckets SET attempts=3 WHERE scope='alpha_worlds_total'")
    with request_client(app) as c:
        r=c.post('/api/auth/guest');assert r.status_code==409
        assert r.json()['error']['code']=='alpha_capacity_reached'
    assert count(app,'users')==0
