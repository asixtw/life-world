from test_google_exchange import setup, client_for, challenge
from conftest import onboard


def test_returning_login_requires_explicit_guest_decision(setup):
    app,v=setup
    with client_for(app) as a:
        me,_=onboard(a); body=challenge(a,v)
        r=a.post('/api/auth/external/exchange',json=body); assert r.status_code==200
        owner=me['owner_id']; saved=a.get('/api/state').json()
        a.headers['X-CSRF-Token']=r.json()['csrf_token']
        assert a.post('/api/auth/logout').status_code==204
    with client_for(app) as b:
        other,_=onboard(b); old=b.cookies.get('lw_session'); guest_saved=b.get('/api/state').json()
        body=challenge(b,v,mode='upgrade',token='upgrade-b')
        assert b.post('/api/auth/external/exchange',json=body).status_code==409
        body=challenge(b,v,mode='login',token='login-b')
        assert b.post('/api/auth/external/exchange',json=body).status_code==409
        assert b.get('/api/state').json()==guest_saved
        body=challenge(b,v,mode='login',token='chosen-login-b',discard_guest=True)
        r=b.post('/api/auth/external/exchange',json=body); assert r.status_code==200,r.text
        assert r.json()['owner_id']==owner and b.cookies.get('lw_session')!=old
        assert b.get('/api/state').json()==saved
        with app.state.service.db.connect() as c:
            assert c.execute('SELECT count(*) FROM goals WHERE owner_id=?',(other['owner_id'],)).fetchone()[0]>0
        b.cookies.set('lw_session',old)
        assert b.get('/api/state').status_code==401
    with client_for(app) as different:
        onboard(different)
        body=challenge(different,v,mode='login',subject='different-google',token='different',discard_guest=True)
        r=different.post('/api/auth/external/exchange',json=body)
        assert r.status_code==404
        assert different.get('/api/auth/me').json()['status']=='guest'
