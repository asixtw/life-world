"""初期公開共用嚴格總額度；不從可偽造XFF產生新桶。"""
from dataclasses import replace
from fastapi.testclient import TestClient
import pytest
from app.main import create_app
from app.runtime import RuntimeSettings
from app.auth_rate_limit import AuthRateLimiter
from datetime import datetime,timezone
from starlette.requests import Request


def settings():
    return replace(RuntimeSettings(),access_mode='public_alpha',auth_source_mode='shared',auth_rate_enabled=True,auth_rate_secret='synthetic-shared-public-key-'*3,registration_enabled=False,alpha_worlds_total=3)


def test_public_anonymous_and_private_boundaries(tmp_path):
    app=create_app(tmp_path,settings=settings())
    with TestClient(app,base_url='http://testserver') as c:
        assert c.get('/').status_code==200
        assert c.get('/static/app.js').status_code==200
        assert c.get('/api/state').status_code==401
        assert c.get('/api/people').status_code==401
        assert c.post('/api/auth/claim',json={'username':'not_allowed','password':'synthetic-pass-123'}).status_code==403
        guest=c.post('/api/auth/guest');assert guest.status_code==201
        assert c.put('/api/profile',json={'name':'合成','bio':'驗收','timezone':'Asia/Taipei'}).status_code==403
        assert c.put('/api/profile',json={'name':'合成','bio':'驗收','timezone':'Asia/Taipei'},headers={'X-CSRF-Token':guest.json()['csrf_token'],'Origin':'https://evil.example'}).status_code==403


def test_spoofed_forwarding_cannot_create_new_source_buckets():
    limiter=AuthRateLimiter(settings(),lambda:datetime.now(timezone.utc))
    def request(value):return Request({'type':'http','method':'GET','path':'/','headers':[(b'x-forwarded-for',value.encode())],'client':('169.254.169.126',1)})
    assert limiter.source(request('198.51.100.1'))==limiter.source(request('evil, forged'))=='public-shared-source'


def test_shared_profile_requires_capacity_and_closed_registration():
    with pytest.raises(ValueError):replace(RuntimeSettings(),auth_source_mode='shared',auth_rate_enabled=True,auth_rate_secret='x'*40)
