"""登入Provider不決定產品能力；僅既有白名單測試帳密可與GIS共存。"""
from dataclasses import replace
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.runtime import RuntimeSettings
from app.security import PASSWORDS

PASSWORD='synthetic-provider-test-2026'


def seed(app,name):
    owner=uuid4().hex
    with app.state.service.db.connect(write=True) as c:
        c.execute("INSERT INTO users(id,status,username,password_hash,name,bio,created_at,hatched_at) VALUES (?,'registered',?,?,?,'合成驗收',?,?)",(owner,name,PASSWORDS.hash(PASSWORD),name,app.state.service.now().isoformat(),app.state.service.now().isoformat()))
    return owner


def test_google_and_authorized_password_share_registered_authorization(tmp_path):
    settings=replace(RuntimeSettings(),google_client_id='test.apps.googleusercontent.com',test_login_usernames=('invited_test',),registration_enabled=False,password_login_enabled=False)
    app=create_app(tmp_path,settings=settings);owner=seed(app,'invited_test');seed(app,'not_invited')
    with TestClient(app) as c:
        cap=c.get('/api/capabilities').json()
        assert cap['google_login_available'] and cap['password_login_available'] and not cap['registration_available']
        assert c.post('/api/auth/login',json={'username':'not_invited','password':PASSWORD}).status_code==401
        login=c.post('/api/auth/login',json={'username':'invited_test','password':PASSWORD});assert login.status_code==200
        assert login.json()['owner_id']==owner and login.json()['status']=='registered'
        # 共用正式AI授權，只查內部status/onboarding；不呼叫外部模型。
        app.state.ai_runtime.authorize(owner)
        assert c.get('/api/state').status_code==200
        assert c.post('/api/auth/claim',json={'username':'public_signup','password':PASSWORD}).status_code==403
        c.headers['X-CSRF-Token']=login.json()['csrf_token']
        assert c.post('/api/auth/logout').status_code==204
        again=c.post('/api/auth/login',json={'username':'invited_test','password':PASSWORD});assert again.json()['owner_id']==owner


def test_no_test_allowlist_does_not_open_password_with_google(tmp_path):
    app=create_app(tmp_path,settings=RuntimeSettings(google_client_id='test.apps.googleusercontent.com',password_login_enabled=False,registration_enabled=False))
    with TestClient(app) as c:assert c.post('/api/auth/login',json={'username':'unknown','password':PASSWORD}).status_code==403


def test_invalid_test_username_configuration_rejected():
    with pytest.raises(ValueError):replace(RuntimeSettings(),test_login_usernames=('*',))


def test_google_client_does_not_override_enabled_password_policy(tmp_path):
    app=create_app(tmp_path,settings=RuntimeSettings(google_client_id='test.apps.googleusercontent.com',password_login_enabled=True,registration_enabled=False))
    seed(app,'authorized_regular')
    with TestClient(app) as c:
        assert c.post('/api/auth/login',json={'username':'authorized_regular','password':PASSWORD}).status_code==200
