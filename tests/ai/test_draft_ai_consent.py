"""草稿AI授權需可撤回/分Provider與範圍；模型均為替身，不呼叫外部API。"""
from dataclasses import replace
from fastapi.testclient import TestClient
from conftest import onboard,register,draft,grant_draft_ai_consent as grant
from test_ai_runtime import prepared


def test_no_consent_no_provider_or_reservation_and_repeat_grant_is_one_record(prepared):
    app,c,me,g,runtime,p=prepared;app.state.ai_runtime=runtime;d=draft(c,g)
    denied=c.post('/api/drafts/'+d['id']+'/suggest')
    assert denied.status_code==403 and denied.json()['error']['code']=='draft_ai_consent_required'
    assert not p.calls and runtime.usage(me['owner_id'])['calls']==0
    first=grant(c);assert grant(c)==first
    assert c.get('/api/ai/draft-consent').json()['granted']
    result=c.post('/api/drafts/'+d['id']+'/suggest',headers={'Idempotency-Key':'with-consent'})
    assert result.status_code==200 and len(p.calls)==1
    assert c.post('/api/drafts/'+d['id']+'/suggest',headers={'Idempotency-Key':'with-consent'}).status_code==409
    with app.state.service.db.connect() as db:
        assert db.execute("SELECT count(*) FROM data_consents WHERE owner_id=?",(me['owner_id'],)).fetchone()[0]==1


def test_provider_change_requires_new_disclosure_and_revokes_previous_record(prepared):
    app,c,me,g,runtime,p=prepared;app.state.ai_runtime=runtime
    old=c.get('/api/ai/draft-consent').json();grant(c)
    runtime.settings=replace(runtime.settings,model='gemini-new-synthetic')
    assert not c.get('/api/ai/draft-consent').json()['granted']
    stale=c.post('/api/ai/draft-consent',json={'request_id':'stale-policy','policy_fingerprint':old['policy_fingerprint'],'confirmed':True});assert stale.status_code==409
    grant(c,'new-policy')
    with app.state.service.db.connect() as db:
        rows=db.execute("SELECT revoked_at FROM data_consents WHERE owner_id=?",(me['owner_id'],)).fetchall()
    assert len(rows)==2 and sum(r[0] is None for r in rows)==1 and not p.calls


def test_revocation_when_ai_off_and_old_request_retry_cannot_regrant(prepared):
    app,c,me,g,runtime,p=prepared;app.state.ai_runtime=runtime;policy=c.get('/api/ai/draft-consent').json();grant(c)
    runtime.settings=replace(runtime.settings,approved=False)
    assert c.delete('/api/ai/draft-consent').status_code==200
    assert c.delete('/api/ai/draft-consent').json()['granted'] is False
    runtime.settings=replace(runtime.settings,approved=True)
    retry=c.post('/api/ai/draft-consent',json={'request_id':'draft-consent','policy_fingerprint':policy['policy_fingerprint'],'confirmed':True})
    assert retry.status_code==409 and not c.get('/api/ai/draft-consent').json()['granted']
    assert not p.calls


def test_owner_guest_csrf_and_explicit_confirmation_boundaries(prepared):
    app,c,me,g,runtime,p=prepared;app.state.ai_runtime=runtime;grant(c)
    with TestClient(app) as other:
        assert other.get('/api/ai/draft-consent').status_code==401
        onboard(other);assert other.get('/api/ai/draft-consent').status_code==403
        register(other,'other_consent');policy=other.get('/api/ai/draft-consent').json()
        assert not policy['granted']
        for value in [False,1,'true']:
            assert other.post('/api/ai/draft-consent',json={'request_id':'invalid','policy_fingerprint':policy['policy_fingerprint'],'confirmed':value}).status_code==422
        assert other.post('/api/ai/draft-consent',headers={'X-CSRF-Token':'wrong'},json={'request_id':'csrf','policy_fingerprint':policy['policy_fingerprint'],'confirmed':True}).status_code==403
    assert c.get('/api/ai/draft-consent').json()['granted'] and not p.calls


def test_background_consent_does_not_authorize_unconfirmed_draft(prepared):
    app,c,me,g,runtime,p=prepared;app.state.ai_runtime=runtime
    with app.state.service.db.connect(write=True,owner=me['owner_id']) as db:
        db.execute("INSERT INTO data_consents VALUES (?,?,?,'ai_generation',?,?,?, ?,NULL)",('background-only',me['owner_id'],'background-personalization','gemini','{}','background-v1',app.state.service.now().isoformat()))
    assert not c.get('/api/ai/draft-consent').json()['granted']
    d=draft(c,g);assert c.post('/api/drafts/'+d['id']+'/suggest').status_code==403
    assert not p.calls and runtime.usage(me['owner_id'])['calls']==0


def test_raw_draft_grant_does_not_send_background_memory(prepared,monkeypatch):
    from app.relationship_memory import FeatureStore
    app,c,me,g,runtime,p=prepared;app.state.ai_runtime=runtime;grant(c)
    memory=[]
    monkeypatch.setenv('LIFEWORLD_RELATIONSHIP_MEMORY_ENABLED','true')
    monkeypatch.setattr(FeatureStore,'context',lambda *args:memory.append('called') or {'private':'unapproved-background'})
    d=draft(c,g)
    r=c.post('/api/drafts/'+d['id']+'/suggest');assert r.status_code==200,r.text
    assert not memory and p.calls[0]['case']=={'raw_text':d['raw_text']}


def test_source_revision_checked_before_cost_and_result_binds_source(prepared):
    """另一裝置修改草稿時，舊畫面不可消耗額度或誤採新來源摘要。"""
    app,c,me,g,runtime,p=prepared;app.state.ai_runtime=runtime;grant(c);d=draft(c,g)
    path='/api/drafts/'+d['id']+'/suggest'
    for version,status in [('wrong',422),('0',422),(str(d['revision']+1),409)]:
        r=c.post(path,headers={'X-Draft-Revision':version});assert r.status_code==status,r.text
    assert not p.calls and runtime.usage(me['owner_id'])['calls']==0
    r=c.post(path,headers={'X-Draft-Revision':str(d['revision']),'Idempotency-Key':'bound-source'})
    assert r.status_code==200,r.text
    assert r.json()['source_revision']==d['revision']
    assert r.json()['source_sha256']==c.get('/api/drafts/'+d['id']).json()['raw_sha256']
    edited=c.put('/api/drafts/'+d['id'],json={'raw_text':'另一裝置更新的原文','occurred_at':d['occurred_at'],'contributions':[],'expected_revision':d['revision']});assert edited.status_code==200,edited.text
    r=c.post(path,headers={'X-Draft-Revision':str(d['revision'])});assert r.status_code==409
    assert len(p.calls)==1 and runtime.usage(me['owner_id'])['calls']==1
