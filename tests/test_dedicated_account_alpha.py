"""專用帳號線：只在隔離fixture建合成使用者，不建立真Alpha帳密或呼叫模型。"""
from dataclasses import replace
from datetime import datetime,timezone
from uuid import uuid4
import secrets
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.security import PASSWORDS
from test_guest_first import guest_app,client,goal,ORIGIN


def reopen(settings,old_db):
    if old_db.backend=='postgresql':
        from app.postgres import PostgresDatabase
        return PostgresDatabase(settings)
    from app.db import Database
    return Database(old_db.directory)

@pytest.fixture
def dedicated(guest_app):
    settings=replace(guest_app.state.settings,test_login_usernames=('lw_synthetic_test',))
    app=create_app(settings=settings,database=reopen(settings,guest_app.state.service.db),clock=lambda:datetime(2026,11,8,8,tzinfo=timezone.utc))
    owner=uuid4().hex;password=secrets.token_urlsafe(24)
    with app.state.service.db.connect(write=True) as c:
        c.execute("INSERT INTO users(id,status,username,password_hash,created_at) VALUES (?,'registered',?,?,?)",(owner,'lw_synthetic_test',PASSWORDS.hash(password),app.state.service.now().isoformat()))
    yield app,owner,password
    app.state.service.db.close()


def login(c,password):
    response=c.post('/api/auth/login',json={'username':'lw_synthetic_test','password':password});assert response.status_code==200,response.text
    c.headers['X-CSRF-Token']=response.json()['csrf_token'];return response


def test_dedicated_manual_core_logout_relogin_restart_and_isolation(dedicated):
    app,owner,password=dedicated;settings=app.state.settings;database=app.state.service.db
    with client(app) as c,client(app) as guest:
        first=login(c,password);assert first.json()['owner_id']==owner;assert first.json()['status']=='registered'
        assert all(x in first.headers['set-cookie'].lower() for x in ['httponly','secure','samesite=strict'])
        assert c.put('/api/profile',json={'name':'合成測試帳號','bio':'閱讀驗收','timezone':'Asia/Taipei'}).status_code==200
        # 使用相同既有目標payload；不透過Guest API建立這個registered Owner。
        other,_=goal(guest)
        payload={'request_id':'dedicated-goal','title':'帳密合成閱讀','outcome':'一篇心得','deadline':'2026-11-15','actions':[{'title':t,'unit':'次','per_occurrence':'1','dates':['2026-11-08'],'weekdays':[],'cycle':'month'} for t in ['閱讀','筆記','回顧']]}
        g=c.post('/api/goals',json=payload);assert g.status_code==201,g.text;g=g.json();assert len(g['actions'])==3
        # 直接共用正式AI身分授權；不配置Provider、不呼叫Gemini。
        app.state.ai_runtime.authorize(owner)
        draft=c.post('/api/experiences/drafts',json={'raw_text':'合成閱讀並寫下筆記','occurred_at':'2026-11-08T09:00:00+08:00','goal_id':g['id'],'contributions':[{'action_id':g['actions'][0]['id'],'quantity':'1'}]});assert draft.status_code==201;draft=draft.json()
        assert c.get('/api/state').json()['experiences']==[]
        body={'request_id':'dedicated-confirm','expected_revision':draft['revision'],'summary':'人工確認的合成摘要','person_id':None,'contributions':draft['contributions'],'tasks':['明天整理下一章']}
        url='/api/drafts/'+draft['id']+'/confirm';saved=c.post(url,json=body);assert saved.status_code==201;assert c.post(url,json=body).json()==saved.json()
        before=c.get('/api/state').json();assert before['rewards']['total']==1;assert len(before['experiences'])==1;assert len(before['tasks'])==1
        assert guest.get('/api/goals/'+g['id']).status_code==404;assert c.get('/api/goals/'+other['id']).status_code==404
        old_cookie=c.cookies.get('lw_session');assert c.post('/api/auth/logout').status_code==204;assert c.get('/api/auth/me').status_code==401
        assert c.get('/api/auth/me',headers={'Cookie':'lw_session='+old_cookie}).status_code==401
        login(c,password);assert c.get('/api/state').json()==before;cookies=dict(c.cookies)
    # 關閉舊App後，以全新Pool驗證所有核心資料持久化。
    restarted=create_app(settings=settings,database=reopen(settings,database),clock=lambda:datetime(2026,11,8,8,tzinfo=timezone.utc))
    with client(restarted) as c:
        c.cookies.update(cookies);assert c.get('/api/auth/me').json()['owner_id']==owner;assert c.get('/api/state').json()==before


def test_dedicated_wrong_password_and_public_registration_closed(dedicated):
    app,owner,password=dedicated
    with client(app) as c:
        assert c.post('/api/auth/login',json={'username':'lw_synthetic_test','password':secrets.token_urlsafe(24)}).status_code==401
        login(c,password);assert c.post('/api/auth/claim',json={'username':'new_public_user','password':secrets.token_urlsafe(24)}).status_code==403


def test_guest_ai_is_currently_registered_only(guest_app):
    # 明示產品缺口，不能把Guest人工確認或替身AI宣稱真AI已開。
    from app.errors import DomainError
    with client(guest_app) as c:
        goal(c);owner=c.get('/api/auth/me').json()['owner_id']
        with pytest.raises(DomainError) as error:guest_app.state.ai_runtime.authorize(owner)
        assert error.value.status==403
