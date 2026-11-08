"""Owner批准的全新SQLite測試表；不執行正式migration，不連外部Google。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.runtime import RuntimeSettings
from app.security import digest
from app.errors import DomainError
from conftest import onboard,draft,confirm_payload,register,guest

CLIENT_ID='test.apps.googleusercontent.com'


class Verifier:
    client_id=CLIENT_ID
    def __init__(self):self.credentials={}
    def verify(self,token,nonce_hash):
        item=self.credentials.get(token)
        if item is None or digest(item[1])!=nonce_hash:raise DomainError(401,'invalid_test_token','Invalid synthetic token')
        return 'https://accounts.google.com',item[0]


@pytest.fixture
def setup(tmp_path):
    verifier=Verifier()
    app=create_app(data_dir=tmp_path/'isolated-google',settings=RuntimeSettings(google_client_id=CLIENT_ID,password_login_enabled=False,registration_enabled=False),google_verifier=verifier,clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))
    # 只在本fixture新建且可丟棄的DB初始化新表；未寫入app/migrations。
    with app.state.service.db.connect(write=True) as c:
        c.execute("CREATE TABLE external_identities(provider TEXT NOT NULL,issuer TEXT NOT NULL,subject TEXT NOT NULL,owner_id TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,PRIMARY KEY(provider,issuer,subject))")
    with app.state.service.db.connect(write=True) as c:
        c.execute("CREATE TABLE guest_abandonments(owner_id TEXT PRIMARY KEY,abandoned_at TEXT NOT NULL,purge_after TEXT NOT NULL,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,last_error_code TEXT,completed_at TEXT,media_state TEXT NOT NULL DEFAULT 'pending',media_attempts INTEGER NOT NULL DEFAULT 0)")
    return app,verifier


def client_for(app):
    c=TestClient(app);c.headers['Origin']='http://testserver';return c


def challenge(c,v,subject='subject-a',mode='upgrade',token='synthetic-google-token',**kw):
    r=c.post('/api/auth/external/challenge',json={'mode':mode,**kw});assert r.status_code==200,r.text
    data=r.json();v.credentials[token]=(subject,data['nonce'])
    return {'challenge_id':data['challenge_id'],'credential':token}


def test_guest_upgrade_and_idempotence(setup):
    app,v=setup
    with client_for(app) as c:
        me,g=onboard(c);d=draft(c,g);assert c.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d)).status_code==201
        before=c.get('/api/state').json();old_cookie=c.cookies.get('lw_session')
        body=challenge(c,v);r=c.post('/api/auth/external/exchange',json=body);assert r.status_code==200,r.text
        assert r.json()['owner_id']==me['owner_id'] and r.json()['status']=='registered'
        assert c.cookies.get('lw_session')!=old_cookie
        c.headers['X-CSRF-Token']=r.json()['csrf_token']
        again=c.post('/api/auth/external/exchange',json=body);assert again.status_code==200 and again.json()['replayed']
        after=c.get('/api/state').json();assert before['goals']==after['goals'] and before['experiences']==after['experiences'] and before['rewards']==after['rewards']
        assert c.post('/api/auth/logout').status_code==204
        assert c.get('/api/state').status_code==401
        # 舊Cookie及重播Token都不能恢復登入。
        c.cookies.set('lw_session',old_cookie);assert c.post('/api/auth/external/exchange',json=body).status_code==401


def test_normal_login_returns_google_owner_not_same_email_local_account(setup):
    app,v=setup
    with client_for(app) as first:
        me,_=onboard(first);body=challenge(first,v);r=first.post('/api/auth/external/exchange',json=body);assert r.status_code==200
        owner=r.json()['owner_id']
    with client_for(app) as second:
        guest(second);body=challenge(second,v,mode='login',token='second-token')
        r=second.post('/api/auth/external/exchange',json=body);assert r.status_code==200 and r.json()['owner_id']==owner
    with client_for(app) as local:
        me,_=onboard(local)
        with app.state.service.db.connect(write=True) as db:
            db.execute("UPDATE users SET status='registered',username='same_email_local' WHERE id=?",(me['owner_id'],))
        # 前端自報email/user_id一律422，不參與任何帳號合併。
        assert local.post('/api/auth/external/exchange',json={**body,'email':'same@example.invalid','user_id':owner}).status_code==422
        body=challenge(local,v,subject='brand-new-subject',mode='login',token='new-token')
        r=local.post('/api/auth/external/exchange',json=body);assert r.status_code==200 and r.json()['owner_id']!=me['owner_id']


def test_different_owner_conflict_and_no_automatic_data_merge(setup):
    app,v=setup
    with client_for(app) as a:
        me,_=onboard(a);body=challenge(a,v);assert a.post('/api/auth/external/exchange',json=body).status_code==200
    with client_for(app) as b:
        other,_=onboard(b);body=challenge(b,v,token='conflict-token')
        assert b.post('/api/auth/external/exchange',json=body).status_code==409
        assert b.get('/api/auth/me').json()['owner_id']==other['owner_id']
        assert b.get('/api/auth/me').json()['status']=='guest'
        body=challenge(b,v,mode='login',token='login-conflict')
        assert b.post('/api/auth/external/exchange',json=body).status_code==409


def test_csrf_origin_nonce_and_session_binding(setup):
    app,v=setup
    with client_for(app) as a,client_for(app) as b:
        onboard(a);onboard(b);body=challenge(a,v)
        assert b.post('/api/auth/external/exchange',json=body).status_code==403
        original=a.headers['X-CSRF-Token'];a.headers['X-CSRF-Token']='wrong'
        assert a.post('/api/auth/external/exchange',json=body).status_code==403
        a.headers['X-CSRF-Token']=original;a.headers['Origin']='https://evil.invalid'
        assert a.post('/api/auth/external/exchange',json=body).status_code==403
        a.headers['Origin']='http://testserver';v.credentials[body['credential']]=('subject-a','wrong-nonce')
        assert a.post('/api/auth/external/exchange',json=body).status_code==401


def test_parallel_upgrade_binds_once(setup):
    app,v=setup
    with client_for(app) as a:
        me,_=onboard(a);body=challenge(a,v);cookie=a.cookies.get('lw_session');csrf=a.headers['X-CSRF-Token']
        def run(_):
            with client_for(app) as c:
                c.cookies.set('lw_session',cookie);c.headers['X-CSRF-Token']=csrf
                return c.post('/api/auth/external/exchange',json=body).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(run,range(2)))
        assert codes.count(200)==1 and all(x in (200,401) for x in codes)
        with app.state.service.db.connect() as c:
            assert c.execute('SELECT count(*) AS n FROM external_identities').fetchone()['n']==1
            assert c.execute('SELECT owner_id FROM external_identities').fetchone()['owner_id']==me['owner_id']


def test_public_shell_and_google_disabled_by_default(tmp_path):
    app=create_app(data_dir=tmp_path/'disabled')
    with client_for(app) as c:
        assert c.get('/').status_code==200
        assert c.get('/api/state').status_code==401
        assert c.post('/api/auth/external/challenge',json={'mode':'login'}).status_code==503


def test_google_only_blocks_legacy_password_registration(setup):
    app,_=setup
    with client_for(app) as c:
        onboard(c)
        for path in ('/api/auth/claim','/api/auth/login'):
            assert c.post(path,json={'username':'not_allowed','password':'synthetic-test-password'}).status_code==403


def test_challenge_expires_and_token_cannot_move_to_new_challenge(setup):
    from datetime import timedelta
    app,v=setup
    with client_for(app) as c:
        onboard(c);old=challenge(c,v)
        new=challenge(c,v,token='new-challenge-token')
        assert c.post('/api/auth/external/exchange',json={**new,'credential':old['credential']}).status_code==401
        clock=app.state.service.clock;app.state.service.clock=lambda:clock()+timedelta(minutes=6)
        assert c.post('/api/auth/external/exchange',json=new).status_code==401


def test_two_owners_concurrently_upgrade_same_google_subject(setup):
    app,v=setup
    with client_for(app) as a,client_for(app) as b:
        onboard(a);onboard(b);one=challenge(a,v,token='parallel-a');two=challenge(b,v,token='parallel-b')
        def run(item):
            c,body=item;return c.post('/api/auth/external/exchange',json=body).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(run,[(a,one),(b,two)]))
        assert sorted(codes)==[200,409]
        with app.state.service.db.connect() as c:
            assert c.execute('SELECT count(*) AS n FROM external_identities').fetchone()['n']==1


def test_receipts_do_not_store_credentials_and_logout_blocks_replay(setup):
    app,v=setup
    with client_for(app) as c:
        me,_=onboard(c);body=challenge(c,v);r=c.post('/api/auth/external/exchange',json=body);assert r.status_code==200
        with app.state.service.db.connect() as db:
            for row in db.execute('SELECT fingerprint,response FROM requests').fetchall():
                assert body['credential'] not in row['response'] and body['credential']!=row['fingerprint']
        c.headers['X-CSRF-Token']=r.json()['csrf_token'];assert c.post('/api/auth/logout').status_code==204
        assert c.post('/api/auth/external/exchange',json=body).status_code==401


def test_upgrade_rolls_back_if_identity_insert_fails(setup):
    app,v=setup
    with client_for(app) as c:
        me,_=onboard(c);body=challenge(c,v)
        with app.state.service.db.connect(write=True) as db:
            db.execute("CREATE TRIGGER test_identity_failure BEFORE INSERT ON external_identities BEGIN SELECT RAISE(ABORT,'synthetic rollback'); END")
        with TestClient(app,raise_server_exceptions=False) as failure:
            failure.headers.update(c.headers);failure.cookies.update(c.cookies)
            assert failure.post('/api/auth/external/exchange',json=body).status_code==500
        assert c.get('/api/auth/me').json()['status']=='guest'
        with app.state.service.db.connect() as db:
            assert db.execute('SELECT count(*) AS n FROM external_identities').fetchone()['n']==0
            assert db.execute("SELECT count(*) AS n FROM requests WHERE operation='google_exchange_v1'").fetchone()['n']==0


def test_gis_headers_preserve_origin_and_allow_only_known_style(setup):
    """依Google正式整合契約送出Origin Referer，樣式只放行已核對的CSS hash。"""
    app,_=setup
    with client_for(app) as c:
        r=c.get('/');policy=r.headers['content-security-policy']
        assert r.headers['referrer-policy']=='strict-origin-when-cross-origin'
        assert "'sha256-RU4sU0AaS8IBGZx8XrGt/pa9A5SLA3dQszGeqT5L3Kw='" in policy
        assert "'unsafe-inline'" not in policy and "'unsafe-eval'" not in policy
