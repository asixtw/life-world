"""既有RC的身分／保存特徵測試；不宣稱公開Beta已實作。"""
from fastapi.testclient import TestClient
from conftest import onboard,register,draft,confirm_payload
from app.security import digest


def test_session_is_random_server_lookup_and_cookie_loss_is_not_deletion(app,client):
    me,goal=onboard(client)
    token=client.cookies.get('lw_session')
    with app.state.service.db.connect() as c:
        row=c.execute('SELECT owner_id FROM sessions WHERE token_hash=?',(digest(token),)).fetchone()
        assert row['owner_id']==me['owner_id']
        assert c.execute('SELECT owner_id FROM sessions WHERE token_hash=?',(token,)).fetchone() is None
    client.cookies.clear()
    assert client.get('/api/state').status_code==401
    with app.state.service.db.connect() as c:
        assert c.execute('SELECT id FROM goals WHERE id=?',(goal['id'],)).fetchone() is not None


def test_claim_keeps_world_without_reward_reimport(client):
    me,goal=onboard(client);d=draft(client,goal)
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d)).status_code in (200,201)
    before=client.get('/api/state').json()
    old=client.cookies.get('lw_session')
    register(client,'audit_owner')
    after=client.get('/api/state').json()
    assert after['goals']==before['goals'] and after['experiences']==before['experiences']
    assert after['rewards']==before['rewards'] and client.cookies.get('lw_session')!=old
    assert client.post('/api/auth/claim',json={'username':'audit_owner','password':'a-good-password-2026'}).status_code==409


def test_guest_suggest_and_recognition_require_registered(client):
    _,goal=onboard(client);d=draft(client,goal)
    # Guest仍能自己寫摘要與確認，只有候選provider與辨識入口需登入。
    assert client.post('/api/drafts/'+d['id']+'/suggest').status_code==403
    response=client.post('/api/media/recognize',data={'kind':'image'},files={'file':('sample.png',b'synthetic','image/png')})
    assert response.status_code==403
    assert client.post('/api/people',json={'name':'Synthetic','role':'customer','notes':''}).status_code==403


def test_draft_owner_isolation_and_forged_cookie(app,client):
    _,goal=onboard(client);d=draft(client,goal)
    with TestClient(app) as other:
        onboard(other)
        assert other.get('/api/drafts/'+d['id']).status_code in (403,404)
        other.cookies.clear();other.cookies.set('lw_session','guessed-owner-id')
        assert other.get('/api/state').status_code==401


def test_registered_suggest_keeps_manual_confirmation(client):
    _,goal=onboard(client);register(client,'suggest_owner');d=draft(client,goal)
    assert client.post('/api/drafts/'+d['id']+'/suggest').status_code==200
    state=client.get('/api/state').json()
    assert state['experiences']==[] and state['rewards']['total']==0


def test_draft_retry_idempotence_and_restricted_person_payload(app,client):
    _,goal=onboard(client)
    d=draft(client,goal,request_id='same-network-retry')
    again=draft(client,goal,request_id='same-network-retry');assert again['id']==d['id']
    with app.state.service.db.connect() as c:
        assert c.execute('SELECT count(*) AS n FROM drafts').fetchone()['n']==1
    from fastapi.testclient import TestClient
    with TestClient(app) as other:
        onboard(other);register(other,'person_creator')
        person=other.post('/api/people',json={'name':'Synthetic Person','role':'customer','notes':''}).json()
    payload={'raw_text':'Synthetic','occurred_at':'2026-10-27T00:10:00+08:00','goal_id':goal['id'],'person_id':person['id'],'contributions':[]}
    assert client.post('/api/experiences/drafts',json=payload).status_code==403
