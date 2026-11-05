"""預建帳號登入與匿名世界分開驗收；所有帳號及資料均為合成。"""
from dataclasses import replace
from datetime import datetime, timezone
from functools import partial
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.runtime import RuntimeSettings
from app.service import PASSWORDS
from conftest import goal_payload

Client=partial(TestClient,client=('198.51.100.15',50000))
PASS='synthetic-login-password-2026'


def seed(app,name):
    """僅測試fixture預建，產品不增加註冊或建帳號API。"""
    owner=uuid4().hex
    with app.state.service.db.connect(write=True) as c:
        c.execute("INSERT INTO users(id,status,username,password_hash,created_at) VALUES (?,'registered',?,?,?)",(owner,name,PASSWORDS.hash(PASS),app.state.service.now().isoformat()))
    return owner


@pytest.fixture
def alpha_login(tmp_path):
    settings=RuntimeSettings(access_mode='public_alpha',auth_rate_enabled=True,
        auth_rate_secret='synthetic-alpha-login-key-'*3,auth_source_mode='direct',alpha_login_enabled=True)
    return create_app(tmp_path,settings=settings,clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))


def login(c,name,**extra):
    return c.post('/api/auth/login',json=dict(username=name,password=PASS,**extra))


def journey(a,b,first_name='alpha_first',second_name='alpha_second'):
    first=login(a,first_name);assert first.status_code==200
    assert first.json()['lumi_hatched'] is False
    old=a.cookies['lw_session'];a.headers['X-CSRF-Token']=first.json()['csrf_token']
    assert a.put('/api/profile',json={'name':'受邀合成人','bio':'合成測試','timezone':'Asia/Taipei'}).status_code==200
    g=a.post('/api/goals',json=goal_payload()).json();assert g['title']=='靠近更好的自己'
    # 同帳號第二裝置不建立世界，讀回原資料；兩裝置各自擁有CSRF。
    second=login(b,first_name);assert second.status_code==200
    assert second.json()['owner_id']==first.json()['owner_id']
    assert b.cookies['lw_session']!=old
    assert b.get('/api/state').json()['goals'][0]['id']==g['id']
    assert b.put('/api/profile',json={'name':'錯誤','bio':'合成','timezone':'UTC'}).status_code==403
    b.headers['X-CSRF-Token']=second.json()['csrf_token']
    assert b.put('/api/profile',json={'name':'裝置二','bio':'合成','timezone':'UTC'},headers={'Origin':'https://evil.example'}).status_code==403
    assert b.post('/api/auth/logout').status_code==204
    assert b.get('/api/auth/me').status_code==401
    assert a.get('/api/state').status_code==200
    restored=login(b,first_name);assert restored.status_code==200
    assert b.get('/api/state').json()['goals'][0]['id']==g['id']
    b.headers['X-CSRF-Token']=restored.json()['csrf_token']
    other=login(b,second_name);assert other.status_code==200
    b.headers['X-CSRF-Token']=other.json()['csrf_token']
    assert b.get('/api/goals/'+g['id']).status_code==409  # 尚未引導的獨立帳號先被引導門檻阻擋。
    assert b.put('/api/profile',json={'name':'另一帳號','bio':'合成','timezone':'Asia/Taipei'}).status_code==200
    assert b.post('/api/goals',json=goal_payload('second-goal')).status_code==201
    assert b.get('/api/goals/'+g['id']).status_code==404
    assert b.get('/api/auth/me',headers={'Cookie':'lw_session='+second.cookies.get('lw_session','invalid')}).status_code==401


def test_prebuilt_zero_goal_onboarding_second_device_readback_and_owner_isolation(alpha_login):
    seed(alpha_login,'alpha_first');seed(alpha_login,'alpha_second')
    with Client(alpha_login) as a,Client(alpha_login) as b:journey(a,b)


def test_no_public_claim_even_when_prebuilt_login_enabled(alpha_login):
    with Client(alpha_login) as c:
        cap=c.get('/api/capabilities').json()
        assert cap['accounts_available'] is True and cap['registration_available'] is False
        assert c.post('/api/auth/guest').status_code==201
        assert c.post('/api/auth/claim',json={'username':'public_signup','password':PASS}).status_code==403
        with alpha_login.state.service.db.connect() as db:
            assert db.execute("SELECT count(*) FROM users WHERE status='registered'").fetchone()[0]==0


def test_prebuilt_login_still_source_limited_and_correct_password_not_globally_locked(alpha_login):
    seed(alpha_login,'alpha_first')
    with Client(alpha_login) as c:
        for _ in range(5):assert c.post('/api/auth/login',json={'username':'alpha_first','password':'wrong'}).status_code==401
        assert c.post('/api/auth/login',json={'username':'alpha_first','password':'wrong'}).status_code==429
        assert login(c,'alpha_first').status_code==200
        c.cookies.clear();c.headers.pop('X-CSRF-Token',None)
        for _ in range(23):
            assert c.post('/api/auth/login',json={'username':'unknown','password':'wrong'}).status_code in (401,429)
        result=login(c,'alpha_first');assert result.status_code==429
        assert int(result.headers['Retry-After'])>0


def test_login_keeps_guest_conflict_without_claim_or_merge(alpha_login):
    seed(alpha_login,'alpha_first')
    with Client(alpha_login) as c:
        me=c.post('/api/auth/guest').json();token=c.cookies['lw_session']
        assert login(c,'alpha_first').status_code==403
        c.headers['X-CSRF-Token']=me['csrf_token']
        assert login(c,'alpha_first').status_code==409
        assert c.cookies['lw_session']==token
        assert login(c,'alpha_first',discard_guest=True).status_code==200
        assert c.get('/api/auth/me',headers={'Cookie':'lw_session='+token}).status_code==401


def test_prebuilt_unknown_account_is_not_created(alpha_login):
    with Client(alpha_login) as c:
        assert login(c,'not_prebuilt').status_code==401
        with alpha_login.state.service.db.connect() as db:
            assert db.execute('SELECT count(*) FROM users').fetchone()[0]==0


def test_prebuilt_login_three_clients_real_pg18(app,tmp_path):
    if app.state.service.db.backend!='postgresql':pytest.skip('dedicated synthetic PG18 required')
    from app.postgres import PostgresDatabase
    settings=replace(app.state.settings,access_mode='public_alpha',db_name='life_world_alpha',db_user='lw_alpha_app',
        auth_rate_enabled=True,auth_rate_secret='synthetic-alpha-login-pg-key-'*3,auth_source_mode='direct',alpha_login_enabled=True)
    apps=[create_app(tmp_path/str(i),settings=settings,database=PostgresDatabase(settings),clock=app.state.service.now) for i in range(3)]
    first='first_'+uuid4().hex[:12];second='second_'+uuid4().hex[:12]
    seed(apps[0],first);seed(apps[0],second)
    with Client(apps[0]) as a,Client(apps[1]) as b,Client(apps[2]) as c:
        journey(a,b,first,second)
        assert login(c,first).status_code==200
        assert c.get('/api/state').json()['goals']


def test_opt_in_env_and_secure_cookie_contract(tmp_path,monkeypatch):
    monkeypatch.setenv('LIFEWORLD_ALPHA_LOGIN_ENABLED','true')
    assert RuntimeSettings.from_env().alpha_login_enabled is True
    settings=RuntimeSettings(access_mode='public_alpha',alpha_login_enabled=True,auth_source_mode='direct',
        auth_rate_secret='synthetic-cookie-key-'*3,secure_cookies=True,trusted_hosts=('alpha.example',),external_origin='https://alpha.example')
    app=create_app(tmp_path,settings=settings)
    seed(app,'alpha_first')
    with TestClient(app,base_url='https://alpha.example',client=('198.51.100.16',50000)) as c:
        result=login(c,'alpha_first');assert result.status_code==200
        cookie=result.headers['set-cookie'].lower()
        assert 'httponly' in cookie and 'secure' in cookie and 'samesite=strict' in cookie


def test_enabled_login_without_shared_protection_fails_closed(tmp_path):
    app=create_app(tmp_path,settings=RuntimeSettings(access_mode='public_alpha',alpha_login_enabled=True))
    seed(app,'alpha_first')
    with Client(app) as c:
        assert login(c,'alpha_first').status_code==503
        assert 'lw_session' not in c.cookies
