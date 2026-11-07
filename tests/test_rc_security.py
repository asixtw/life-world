"""整合候選安全Gate；Provider是既有明示fixture，禁止外部模型呼叫。"""
import json
from fastapi.testclient import TestClient
from app.ai_runtime import AIRuntime,AISettings
from conftest import onboard,draft,confirm_payload,register
from ai.test_ai_runtime import Provider


def enable(app):
    provider=Provider(json.dumps({'summary':'合成摘要','tasks':['明天閱讀15分鐘']}))
    app.state.ai_runtime=AIRuntime(app.state.service,AISettings(provider='gemini',model='gemini-synthetic',approved=True,reservation_microusd=1,max_budget_microusd=10),provider)
    return provider


def test_anonymous_private_ai_routes_require_session(app,client):
    provider=enable(app)
    for path,body in [('/api/drafts/unknown/suggest',None),('/api/experiences/unknown/task-suggestions',{'consent':True}),('/api/experiences/unknown/tasks',{'request_id':'x','tasks':['合成'],'confirmed':True}),('/api/people/unknown/simulation',{'consent':True,'fact_ids':['x'],'message':'合成'})]:
        response=client.post(path,json=body)
        assert response.status_code==401
    assert provider.calls==[]


def test_enabled_ai_still_denies_guest_before_provider_or_budget(app,client):
    provider=enable(app);me,g=onboard(client);d=draft(client,g)
    assert client.get('/api/media/capabilities').json()['recognition_available'] is False
    assert client.post('/api/drafts/'+d['id']+'/suggest').status_code==403
    assert client.post('/api/experiences/x/task-suggestions',json={'consent':True}).status_code==403
    assert client.post('/api/people/x/simulation',json={'consent':True,'fact_ids':['x'],'message':'合成'}).status_code==403
    assert provider.calls==[]
    with app.state.service.db.connect() as c:
        assert c.execute("SELECT count(*) AS n FROM requests WHERE operation='ai_attempt_v1'").fetchone()['n']==0


def test_registered_owner_cannot_suggest_other_owner_draft(app,client):
    provider=enable(app);_,g=onboard(client);d=draft(client,g);register(client,'rc_owner_a')
    with TestClient(app) as other:
        onboard(other);register(other,'rc_owner_b')
        assert other.post('/api/drafts/'+d['id']+'/suggest').status_code==404
    assert provider.calls==[]


def test_fixture_candidate_does_not_claim_real_model(app,client):
    """測試Provider回應必須明示替身，不能在介面冒稱真實AI。"""
    enable(app);_,g=onboard(client);register(client,'rc_fixture_label');d=draft(client,g)
    response=client.post('/api/drafts/'+d['id']+'/suggest')
    assert response.status_code==200
    assert '測試替身' in response.json()['notice']


def test_public_capacity_counts_guests_created_before_public_mode(app,client):
    """既有Guest也要計入容量，不能只從啟用公開模式後的限流計數起算。"""
    from app.runtime import RuntimeSettings
    from app.main import create_app
    for _ in range(2):
        assert client.post('/api/auth/guest',headers={'Cookie':'lw_session=invalid'}).status_code==201
    public=create_app(database=app.state.service.db,settings=RuntimeSettings(access_mode='public_alpha',auth_rate_enabled=True,auth_rate_secret='synthetic-only-hmac-'*3,auth_source_mode='direct',alpha_worlds_total=2))
    with TestClient(public,client=('127.0.0.1',50000)) as visitor:
        response=visitor.post('/api/auth/guest')
        assert response.status_code==409
        assert response.json()['error']['code']=='guest_capacity_reached'
