"""Google世界轉換：明示驗證器替身，不冒充真OAuth；保存/放棄交易契約。"""
from datetime import timedelta
import json
from test_google_exchange import setup,client_for,challenge
from conftest import onboard,guest,draft,confirm_payload


def counts(app):
    with app.state.service.db.connect() as db:return {t:db.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in ['users','external_identities','guest_abandonments']}


def registered_world(app,v):
    with client_for(app) as c:
        me,g=onboard(c);d=draft(c,g);assert c.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d)).status_code==201
        body=challenge(c,v);r=c.post('/api/auth/external/exchange',json=body);assert r.status_code==200
        return me['owner_id'],c.get('/api/state').json()


def test_login_unknown_google_never_creates_or_abandons(setup):
    app,v=setup
    with client_for(app) as c:
        me,_=onboard(c);before=c.get('/api/state').json();old=c.cookies.get('lw_session');n=counts(app)
        body=challenge(c,v,mode='login',subject='missing',discard_guest=True)
        r=c.post('/api/auth/external/exchange',json=body);assert r.status_code==404
        assert r.json()['error']['code']=='google_world_not_found'
        assert c.cookies.get('lw_session')==old and c.get('/api/state').json()==before and counts(app)==n


def test_even_empty_guest_requires_consent_before_switch(setup):
    app,v=setup;owner,_=registered_world(app,v)
    with client_for(app) as c:
        me=guest(c);body=challenge(c,v,mode='login',token='no-consent')
        r=c.post('/api/auth/external/exchange',json=body);assert r.status_code==409
        assert c.get('/api/auth/me').json()['owner_id']==me['owner_id']
        assert counts(app)['guest_abandonments']==0


def test_upgrade_snapshot_includes_drafts_profile_and_no_second_user(setup):
    app,v=setup
    with client_for(app) as c:
        me,g=onboard(c);d=draft(c,g);c.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d));draft(c,g,raw_text='尚未確認的第二篇')
        before=c.get('/api/state').json();n=counts(app);body=challenge(c,v);r=c.post('/api/auth/external/exchange',json=body)
        assert r.status_code==200 and r.json()['owner_id']==me['owner_id']
        after=c.get('/api/state').json()
        assert {k:v for k,v in after.items() if k!='user'}=={k:v for k,v in before.items() if k!='user'}
        assert all(after['user'][key]==before['user'][key] for key in ['owner_id','name','bio','timezone'])
        assert counts(app)['users']==n['users'] and counts(app)['guest_abandonments']==0


def test_committed_switch_receipt_can_reconcile_without_reexchange(setup):
    app,v=setup;owner,saved=registered_world(app,v)
    with client_for(app) as c:
        source,g=onboard(c);body=challenge(c,v,mode='login',token='switch',discard_guest=True)
        r=c.post('/api/auth/external/exchange',json=body);assert r.status_code==200
        c.headers['X-CSRF-Token']=r.json()['csrf_token']
        status=c.post('/api/auth/external/status',json={'challenge_id':body['challenge_id']})
        assert status.status_code==200,status.text
        assert status.json()=={'status':'committed','mode':'login','source_owner_id':source['owner_id'],'owner_id':owner,'guest_abandoned':True}
        assert c.get('/api/state').json()==saved
        # 新Session重播相同交換不會產生第二個User／清除工作。
        assert c.post('/api/auth/external/exchange',json=body).json()['replayed']
        assert counts(app)['guest_abandonments']==1
        with app.state.service.db.connect() as db:
            job=db.execute('SELECT * FROM guest_abandonments').fetchone()
            assert job['owner_id']==source['owner_id'] and job['status']=='pending'
            from datetime import datetime
            assert datetime.fromisoformat(job['purge_after'])-datetime.fromisoformat(job['abandoned_at'])==timedelta(days=14)
            assert db.execute('SELECT id FROM goals WHERE id=?',(g['id'],)).fetchone()


def test_reconcile_cannot_read_another_session_receipt(setup):
    app,v=setup
    with client_for(app) as a,client_for(app) as b:
        onboard(a);onboard(b);body=challenge(a,v);assert a.post('/api/auth/external/exchange',json=body).status_code==200
        assert b.post('/api/auth/external/status',json={'challenge_id':body['challenge_id']}).status_code==403


def test_invalid_or_expired_exchange_keeps_guest_and_no_tombstone(setup):
    app,v=setup;registered_world(app,v)
    with client_for(app) as c:
        me,_=onboard(c);before=c.get('/api/state').json();body=challenge(c,v,mode='login',discard_guest=True,token='failed')
        v.credentials.pop(body['credential']);assert c.post('/api/auth/external/exchange',json=body).status_code==401
        assert c.get('/api/state').json()==before and counts(app)['guest_abandonments']==0
        body=challenge(c,v,mode='login',discard_guest=True,token='expired');clock=app.state.service.clock;app.state.service.clock=lambda:clock()+timedelta(minutes=6)
        assert c.post('/api/auth/external/exchange',json=body).status_code==401
        assert counts(app)['guest_abandonments']==0


def test_same_owner_never_abandons_itself(setup):
    app,v=setup
    with client_for(app) as c:
        me,_=onboard(c)
        # 合成異常情境：Guest已有相同owner映射，不能將自身世界當成放棄目標。
        with app.state.service.db.connect(write=True) as db:db.execute('INSERT INTO external_identities VALUES (?,?,?,?,?)',('google','https://accounts.google.com','subject-a',me['owner_id'],app.state.service.now().isoformat()))
        body=challenge(c,v,mode='login',discard_guest=True);r=c.post('/api/auth/external/exchange',json=body)
        assert r.status_code==200 and r.json()['owner_id']==me['owner_id'] and counts(app)['guest_abandonments']==0


def test_switch_transaction_rollback_leaves_no_abandonment(setup):
    app,v=setup;registered_world(app,v)
    with client_for(app) as c:
        source,_=onboard(c);before=c.get('/api/state').json();body=challenge(c,v,mode='login',discard_guest=True,token='rollback')
        with app.state.service.db.connect(write=True) as db:db.execute("CREATE TRIGGER fail_exchange_receipt BEFORE INSERT ON requests WHEN NEW.operation='google_exchange_v1' BEGIN SELECT RAISE(ABORT,'synthetic commit failure'); END")
        from fastapi.testclient import TestClient
        fail=TestClient(app,raise_server_exceptions=False);fail.headers.update(c.headers);fail.cookies.update(c.cookies)
        assert fail.post('/api/auth/external/exchange',json=body).status_code==500
        assert c.get('/api/state').json()==before and counts(app)['guest_abandonments']==0


def test_two_devices_login_to_same_existing_world_without_duplicate_users(setup):
    from concurrent.futures import ThreadPoolExecutor
    app,v=setup;owner,_=registered_world(app,v);before=counts(app)['users'];clients=[client_for(app),client_for(app)];bodies=[]
    for i,c in enumerate(clients):
        guest(c);bodies.append(challenge(c,v,mode='login',discard_guest=True,token='device-'+str(i)))
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(lambda pair:pair[0].post('/api/auth/external/exchange',json=pair[1]),zip(clients,bodies)))
    assert all(r.status_code==200 and r.json()['owner_id']==owner for r in responses)
    assert counts(app)['users']==before+2 and counts(app)['external_identities']==1 and counts(app)['guest_abandonments']==2
    for c in clients:c.close()


def test_expiry_during_verification_cannot_commit_late(setup):
    app,v=setup;registered_world(app,v)
    with client_for(app) as c:
        me,_=onboard(c);body=challenge(c,v,mode='login',discard_guest=True,token='slow-verification');verify=v.verify;clock=app.state.service.clock
        def slow(token,nonce):
            result=verify(token,nonce);app.state.service.clock=lambda:clock()+timedelta(minutes=6);return result
        v.verify=slow
        assert c.post('/api/auth/external/exchange',json=body).status_code==401
        result=c.post('/api/auth/external/status',json={'challenge_id':body['challenge_id']});assert result.status_code==200 and result.json()['expired'] is True
        assert c.get('/api/auth/me').json()['owner_id']==me['owner_id'] and counts(app)['guest_abandonments']==0
