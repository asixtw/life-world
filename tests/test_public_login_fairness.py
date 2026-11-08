"""無可信IP的公開模式使用粗全域／真Session／帳號分層，不共用10人門檻。"""
from datetime import datetime,timezone
import secrets
from fastapi.testclient import TestClient
from app.main import create_app
from app.runtime import RuntimeSettings


def app_for(tmp_path):
    return create_app(tmp_path,settings=RuntimeSettings(access_mode='public_alpha',auth_rate_enabled=True,auth_rate_secret=secrets.token_urlsafe(40),auth_source_mode='shared',registration_enabled=False,test_login_usernames=('synthetic_rate',),alpha_worlds_daily=100,alpha_worlds_total=500),clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))


def test_normal_incognito_users_do_not_share_ten_guest_limit(tmp_path):
    app=app_for(tmp_path)
    for _ in range(12):
        with TestClient(app) as c:assert c.post('/api/auth/guest').status_code==201


def test_normal_logins_do_not_share_thirty_attempt_source_limit(tmp_path):
    app=app_for(tmp_path)
    with TestClient(app) as c:
        for i in range(32):
            r=c.post('/api/auth/login',json={'username':'unknown_'+str(i),'password':secrets.token_urlsafe(16)})
            assert r.status_code==401
