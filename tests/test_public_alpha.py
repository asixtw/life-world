"""公開Alpha只使用隔離合成資料；驗證配額與正式資料隔離條件。"""
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from functools import partial
import pytest
from fastapi.testclient import TestClient as HTTPClient
from app.main import create_app
from app.runtime import RuntimeSettings
from app.service import PASSWORDS
from conftest import onboard, register
from test_goal_journey import payload

Client = partial(HTTPClient, client=('127.0.0.1', 50000))

@pytest.fixture
def alpha(tmp_path):
    clock=[datetime(2026,10,27,7,tzinfo=timezone.utc)]
    settings=RuntimeSettings(access_mode='public_alpha', auth_rate_enabled=True,
        auth_rate_secret='synthetic-only-key-'*3, auth_source_mode='direct')
    return create_app(tmp_path, settings=settings, clock=lambda:clock[0]), clock


def count(app, table):
    with app.state.service.db.connect() as c:
        return c.execute('SELECT count(*) FROM '+table).fetchone()[0]


def test_alpha_rejects_credentials_and_external_media(alpha):
    app,_=alpha
    with Client(app) as c:
        assert c.get('/api/capabilities').json()['access_mode']=='public_alpha'
        assert c.post('/api/auth/login',json={'username':'fake','password':'x'}).status_code==403
        assert c.post('/api/auth/claim',json={'username':'fake','password':'long-password'}).status_code==403
        assert c.post('/api/media/recognize').status_code==401  # 真媒體服務已開放；匿名先拒絕，不先解析multipart。
        assert count(app,'users')==0


def test_guest_quota_and_session_reuse(alpha):
    app,_=alpha
    with Client(app) as c:
        first=c.post('/api/auth/guest');assert first.status_code==201
        for _ in range(9):
            assert c.post('/api/auth/guest',headers={'Cookie':'lw_session=invalid'}).status_code==201
        assert c.post('/api/auth/guest',headers={'Cookie':'lw_session=invalid'}).status_code==429
        # 顯式回送最初session，避免測試用戶端更新Cookie影響身分斷言。
        assert c.post('/api/auth/guest',headers={'Cookie':'lw_session='+first.cookies['lw_session']}).status_code==200
        assert count(app,'users')==10


def test_total_world_capacity_is_shared_across_apps(alpha,tmp_path):
    app,clock=alpha
    settings=replace(app.state.settings,alpha_worlds_total=3,alpha_worlds_daily=3)
    apps=[create_app(tmp_path,settings=settings,clock=lambda:clock[0]) for _ in range(3)]
    with ExitStack() as stack:
        clients=[stack.enter_context(Client(a)) for a in apps]
        with ThreadPoolExecutor(max_workers=10) as pool:
            statuses=list(pool.map(lambda n:clients[n%3].post('/api/auth/guest',headers={'Cookie':'lw_session=invalid'}).status_code,range(10)))
    assert statuses.count(201)==3
    assert count(app,'users')==3 and count(app,'sessions')==3


def test_owner_write_capacity_and_failure_rollback(alpha,tmp_path):
    app,clock=alpha
    app=create_app(tmp_path,settings=replace(app.state.settings,alpha_owner_writes=2),clock=lambda:clock[0])
    with Client(app) as c:
        me=c.post('/api/auth/guest').json();c.headers['X-CSRF-Token']=me['csrf_token']
        assert c.put('/api/profile',json={'name':'Alpha','bio':'合成','timezone':'UTC'}).status_code==200
        assert c.put('/api/profile',json={'name':'Alpha2','bio':'合成','timezone':'UTC'}).status_code==200
        assert c.put('/api/profile',json={'name':'Alpha3','bio':'合成','timezone':'UTC'}).status_code==409
        assert c.get('/api/auth/me').json()['name']=='Alpha2'


def test_alpha_blocks_oversized_body_before_parsing(alpha):
    app,_=alpha
    with Client(app) as c:
        assert c.post('/api/auth/guest',content=b'x'*65537).status_code==413


def test_alpha_runtime_cannot_target_private_db():
    with pytest.raises(ValueError):
        RuntimeSettings(access_mode='public_alpha',backend='postgresql',db_password='synthetic',db_name='life_world_dev',db_user='lw_app')


def test_missing_source_and_secret_fail_closed(tmp_path):
    for i,changes in enumerate(({'auth_source_mode':'unconfigured'},{'auth_rate_secret':''})):
        settings=RuntimeSettings(auth_rate_enabled=True,auth_rate_secret='synthetic-key-'*4,auth_source_mode='direct')
        app=create_app(tmp_path/str(i),settings=replace(settings,**changes))
        with Client(app) as c:
            assert c.post('/api/auth/guest').status_code==503
            assert count(app,'users')==0


def test_soft_account_bucket_accepts_correct_password(tmp_path,monkeypatch):
    clock=[datetime(2026,10,27,7,tzinfo=timezone.utc)]
    app=create_app(tmp_path,settings=RuntimeSettings(auth_rate_enabled=True,
        auth_rate_secret='synthetic-key-'*4,auth_source_mode='direct'),clock=lambda:clock[0])
    with Client(app) as c:
        onboard(c);register(c);c.post('/api/auth/logout')
        for _ in range(5):assert c.post('/api/auth/login',json={'username':'lumi_user','password':'wrong-password'}).status_code==401
        assert c.post('/api/auth/login',json={'username':'lumi_user','password':'wrong-password'}).status_code==429
        assert c.post('/api/auth/login',json={'username':'lumi_user','password':'a-good-password-2026'}).status_code==200


def test_proxy_spoofing_source_failure_and_login_hash_gate(tmp_path,monkeypatch):
    settings=RuntimeSettings(auth_rate_enabled=True,auth_rate_secret='synthetic-secret-'*3,
                            auth_source_mode='proxy',auth_trusted_proxies=('10.0.0.0/24',))
    app=create_app(tmp_path,settings=settings)
    with HTTPClient(app,client=('10.0.0.2',50000)) as c:
        for i in range(10):
            assert c.post('/api/auth/guest',headers={'Cookie':'lw_session=invalid','X-Forwarded-For':f'192.0.2.{i},198.51.100.1,10.0.0.1'}).status_code==201
        assert c.post('/api/auth/guest',headers={'Cookie':'lw_session=invalid','X-Forwarded-For':'192.0.2.99,198.51.100.1,10.0.0.1'}).status_code==429
        assert c.post('/api/auth/guest',headers={'Cookie':'lw_session=invalid'}).status_code==503
        calls=[]
        monkeypatch.setattr(PASSWORDS,'verify',lambda *args:calls.append(1) or False)
        for i in range(30):
            result=c.post('/api/auth/login',json={'username':f'unknown{i}','password':'wrong'},headers={'Cookie':'lw_session=invalid','X-Forwarded-For':'198.51.100.2'})
            assert result.status_code==401
        assert c.post('/api/auth/login',json={'username':'other','password':'wrong'},headers={'Cookie':'lw_session=invalid','X-Forwarded-For':'198.51.100.2'}).status_code==429
        assert len(calls)==30
    with HTTPClient(app,client=('203.0.113.5',50000)) as c:
        assert c.post('/api/auth/guest',headers={'X-Forwarded-For':'198.51.100.3'}).status_code==503


def test_window_expiry_global_capacity_and_pause(alpha,tmp_path):
    app,clock=alpha
    app=create_app(tmp_path,settings=replace(app.state.settings,alpha_worlds_total=12,alpha_worlds_daily=12),clock=lambda:clock[0])
    with Client(app) as c:
        for _ in range(10):assert c.post('/api/auth/guest',headers={'Cookie':'lw_session=invalid'}).status_code==201
        r=c.post('/api/auth/guest',headers={'Cookie':'lw_session=invalid'});assert r.status_code==429 and int(r.headers['Retry-After'])==3600
        clock[0]+=timedelta(hours=1)
        for _ in range(2):assert c.post('/api/auth/guest',headers={'Cookie':'lw_session=invalid'}).status_code==201
        clock[0]+=timedelta(days=1)
        assert c.post('/api/auth/guest',headers={'Cookie':'lw_session=invalid'}).status_code==409
    paused=create_app(tmp_path,settings=replace(app.state.settings,alpha_writes_enabled=False),clock=lambda:clock[0])
    with Client(paused) as c:
        assert c.post('/api/auth/guest').status_code==503


def test_alpha_full_core_isolation_and_points(alpha):
    from conftest import draft,confirm_payload
    app,_=alpha
    with Client(app) as a,Client(app) as b:
        me=a.post('/api/auth/guest').json();a.headers['X-CSRF-Token']=me['csrf_token']
        assert a.put('/api/profile',json={'name':'Alpha','bio':'合成測試','timezone':'Asia/Taipei'}).status_code==200
        g=a.post('/api/goals',json=payload()).json()
        assert a.get('/api/auth/me').json()['lumi_hatched']
        d=draft(a,g);args=confirm_payload(d)
        assert a.post('/api/drafts/'+d['id']+'/confirm',json=args).status_code==201
        assert a.post('/api/drafts/'+d['id']+'/confirm',json=args).status_code==201
        world=a.get('/api/state').json();assert len(world['experiences'])==1 and world['rewards']['total']==1
        mb=b.post('/api/auth/guest').json();b.headers['X-CSRF-Token']=mb['csrf_token']
        assert b.put('/api/profile',json={'name':'B','bio':'合成','timezone':'Asia/Taipei'}).status_code==200
        assert b.post('/api/goals',json=payload(key='b-first')).status_code==201
        assert b.get('/api/goals/'+g['id']).status_code==404
        assert b.post('/api/goals/'+g['id']+'/review',json={'request_id':'other','expected_revision':g['revision'],'decision':'end','confirmed':True}).status_code==404
        assert a.get('/api/goals/'+g['id']).status_code==200
        assert b.put('/api/profile',json={'name':'B','bio':'合成','timezone':'UTC'},headers={'X-CSRF-Token':'bad'}).status_code==403


def test_three_real_postgres_pools_share_login_and_guest_quota(app):
    if app.state.service.db.backend!='postgresql':pytest.skip('dedicated synthetic PG18 required')
    from app.postgres import PostgresDatabase
    settings=replace(app.state.settings,auth_rate_enabled=True,auth_rate_secret='synthetic-pg-key-'*3,auth_source_mode='direct')
    apps=[create_app(database=PostgresDatabase(settings),settings=settings) for _ in range(3)]
    with ExitStack() as stack:
        clients=[stack.enter_context(Client(a)) for a in apps]
        with ThreadPoolExecutor(max_workers=12) as pool:
            results=list(pool.map(lambda i:clients[i%3].post('/api/auth/guest',headers={'Cookie':'lw_session=invalid'}).status_code,range(16)))
        assert results.count(201)==10 and results.count(429)==6
        with ThreadPoolExecutor(max_workers=12) as pool:
            results=list(pool.map(lambda i:clients[i%3].post('/api/auth/login',headers={'Cookie':'lw_session=invalid'},json={'username':'unknown','password':'synthetic'}).status_code,range(12)))
        assert results.count(401)==5 and results.count(429)==7
        assert count(app,'users')==10 and count(app,'sessions')==10
