"""未取得私人資料Gate時仍可公開安全頁；完全不使用DB或IAP替身。"""
from dataclasses import replace
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.runtime import RuntimeSettings


def test_closed_gate_serves_assets_but_never_connects_database(tmp_path):
    settings=RuntimeSettings(public_gate_closed=True,business_enabled=False,access_mode='public_alpha',backend='postgresql',db_name='life_world_public',db_user='lw_public_app')
    app=create_app(tmp_path,settings=settings)
    def forbidden(*a,**k):raise AssertionError('closed gate must not open database')
    app.state.service.db.connect=forbidden
    with TestClient(app) as c:
        assert c.get('/').status_code==200
        assert c.get('/static/art/lumi-welcome.png').status_code==200
        cap=c.get('/api/capabilities').json();assert cap['public_gate_closed'] is True
        assert not any(cap[key] for key in ['accounts_available','google_login_available','ai_available','writes_available'])
        assert c.get('/health').status_code==200
        assert c.get('/ready').status_code==503
        assert c.get('/api/auth/me').status_code==401
        for path,body in [('/api/auth/guest',{}),('/api/auth/login',{'username':'fake','password':'synthetic'}),('/api/experiences/x/task-suggestions',{'consent':True})]:
            r=c.post(path,json=body);private=not path.startswith('/api/auth/');assert r.status_code==(401 if private else 503) and r.json()['error']['code']==('unauthenticated' if private else 'release_gate_closed')
        assert c.get('/api/state').status_code==401
        assert c.get('/docs').status_code==503


def test_closed_gate_cannot_accidentally_enable_business_or_google():
    with pytest.raises(ValueError):RuntimeSettings(public_gate_closed=True,business_enabled=True)
    with pytest.raises(ValueError):RuntimeSettings(public_gate_closed=True,business_enabled=False,google_client_id='fake.apps.googleusercontent.com')


def test_anonymous_private_api_uses_401_without_database_access(tmp_path):
    """公開安全Gate未解鎖時仍維持未登入私人API的HTTP契約。"""
    app=create_app(tmp_path,settings=RuntimeSettings(public_gate_closed=True,business_enabled=False))
    def forbidden(*a,**k):raise AssertionError('must not connect database')
    app.state.service.db.connect=forbidden
    with TestClient(app) as client:
        assert client.get('/api/state').status_code==401
        assert client.get('/api/people').status_code==401
        assert client.post('/api/people/unowned/simulation',json={'consent':True,'fact_ids':['x'],'message':'合成'}).status_code==401
        assert client.post('/api/auth/login',json={'username':'fake','password':'synthetic'}).status_code==503
