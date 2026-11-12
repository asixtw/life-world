"""來源撤回不得被普通寫入復活；合成資料、同交易回滾與跨Owner隔離。"""
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from conftest import onboard,register,draft,confirm_payload


def setup_source(client):
    me,goal=onboard(client);register(client)
    p=client.post('/api/people',json={'name':'合成人物'}).json()
    def experience(key):
        d=draft(client,goal,raw_text='合成人物說不吃辣。',person_id=p['id'],contributions=[])
        r=client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d,request_id=key,contributions=[]));assert r.status_code==201,r.text
        return d,r.json()
    a,confirmed=experience('source-a');b,other=experience('source-b')
    body={'request_id':'fact-a','dimension':'food','value':'不吃辣','evidence_type':'stated_by_person','source_experience_ids':[confirmed['experience_id']],'confirmed':True}
    r=client.post('/api/people/'+p['id']+'/facts',json=body);assert r.status_code==201,r.text
    return me,p,body,r.json(),a,confirmed,b,other


def snapshot(service,owner):
    """只取本合成Owner資料，確保失敗時fact/source/request/獎勵都未變更。"""
    with service.db.connect() as c:
        facts=[dict(r) for r in c.execute('SELECT * FROM person_facts WHERE owner_id=? ORDER BY id',(owner,))]
        sources=[dict(r) for r in c.execute('SELECT s.* FROM fact_sources s JOIN person_facts f ON f.id=s.fact_id WHERE f.owner_id=? ORDER BY s.fact_id,s.experience_id',(owner,))]
        requests=[dict(r) for r in c.execute('SELECT * FROM requests WHERE owner_id=? ORDER BY operation,request_id',(owner,))]
    return {'facts':facts,'sources':sources,'requests':requests}


def revoke(client,p,f,source):
    r=client.post('/api/people/'+p['id']+'/facts/'+f['id']+'/sources/revoke',json={'experience_id':source,'expected_revision':f['revision']})
    assert r.status_code==200,r.text
    return r.json()


def test_rejected_mixed_sources_roll_back_and_new_source_does_not_restore_old(client,app):
    me,p,body,f,a,ca,b,cb=setup_source(client)
    revoke(client,p,f,ca['experience_id'])
    before=snapshot(app.state.service,me['owner_id']);world=client.get('/api/state').json()
    bad={**body,'request_id':'mixed','source_experience_ids':[cb['experience_id'],ca['experience_id']]}
    r=client.post('/api/people/'+p['id']+'/facts',json=bad)
    assert r.status_code==409 and r.json()['error']['code']=='source_restore_required'
    assert snapshot(app.state.service,me['owner_id'])==before
    assert client.get('/api/state').json()==world
    # 不同有效來源仍能支持同一事實，原A撤回記錄不得被改掉。
    good={**body,'request_id':'new-source','source_experience_ids':[cb['experience_id']]}
    r=client.post('/api/people/'+p['id']+'/facts',json=good);assert r.status_code==201,r.text
    rows=snapshot(app.state.service,me['owner_id'])['sources']
    assert len(rows)==2
    assert next(x for x in rows if x['experience_id']==ca['experience_id'])['revoked_at']==before['sources'][0]['revoked_at']
    assert next(x for x in rows if x['experience_id']==cb['experience_id'])['revoked_at'] is None
    result=client.get('/api/people/'+p['id']+'/facts/'+f['id']+'/evidence').json()
    assert [x['id'] for x in result['sources']]==[cb['experience_id']]
    assert client.get('/api/state').json()['rewards']==world['rewards']


def test_duplicate_before_and_after_revoke_never_replays_writes(client,app):
    me,p,body,f,a,ca,b,cb=setup_source(client)
    revoke(client,p,f,ca['experience_id']);before=snapshot(app.state.service,me['owner_id'])
    # 同request_id只是歷史成功收據，不執行upsert；之後必須回讀現在狀態。
    replay=client.post('/api/people/'+p['id']+'/facts',json=body);assert replay.status_code==201
    assert snapshot(app.state.service,me['owner_id'])==before
    def attempt(i):
        return client.post('/api/people/'+p['id']+'/facts',json={**body,'request_id':'retry-'+str(i)}).status_code
    with ThreadPoolExecutor(max_workers=4) as pool:codes=list(pool.map(attempt,range(8)))
    assert codes==[409]*8 and snapshot(app.state.service,me['owner_id'])==before
    # resolve不能充當恢復，舊Confirm換request_id也不能重做已確認草稿。
    assert client.post('/api/people/'+p['id']+'/facts/'+f['id']+'/resolve',json={'expected_revision':f['revision']+1}).status_code==409
    assert client.post('/api/drafts/'+a['id']+'/confirm',json=confirm_payload(a,request_id='repeat-confirm',contributions=[])).status_code==409
    assert snapshot(app.state.service,me['owner_id'])==before


def test_existing_source_evidence_cannot_be_silently_overwritten(client,app):
    me,p,body,f,a,ca,b,cb=setup_source(client);before=snapshot(app.state.service,me['owner_id'])
    r=client.post('/api/people/'+p['id']+'/facts',json={**body,'request_id':'different-evidence','evidence_type':'observed_by_user'})
    assert r.status_code==409 and r.json()['error']['code']=='source_correction_required'
    assert snapshot(app.state.service,me['owner_id'])==before
    assert client.post('/api/people/'+p['id']+'/facts',json={**body,'request_id':'same-evidence'}).status_code==201
    after=snapshot(app.state.service,me['owner_id'])
    assert after['sources']==before['sources']


def test_revoke_and_upsert_cross_owner_csrf_and_version_boundaries(client,app):
    me,p,body,f,a,ca,b,cb=setup_source(client)
    before=snapshot(app.state.service,me['owner_id'])
    path='/api/people/'+p['id']+'/facts/'+f['id']+'/sources/revoke'
    assert client.post(path,json={'experience_id':ca['experience_id'],'expected_revision':f['revision']+1}).status_code==409
    assert client.post(path,headers={'X-CSRF-Token':'wrong'},json={'experience_id':ca['experience_id'],'expected_revision':f['revision']}).status_code==403
    with TestClient(app) as other:
        onboard(other);register(other,'source_attacker')
        assert other.post('/api/people/'+p['id']+'/facts',json=body).status_code==404
        assert other.post(path,json={'experience_id':ca['experience_id'],'expected_revision':f['revision']}).status_code==404
    assert snapshot(app.state.service,me['owner_id'])==before
