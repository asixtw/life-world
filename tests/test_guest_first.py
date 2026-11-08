"""G01–G10：同一Guest/Owner模型；PG模式只允許專用marker合成cluster。"""
from contextlib import closing
from dataclasses import replace
from datetime import datetime,timedelta,timezone,date
import os
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.runtime import RuntimeSettings
from app.errors import DomainError

ORIGIN='https://guest.example.test'

@pytest.fixture
def guest_app(tmp_path,record_property):
    settings=RuntimeSettings(access_mode='public_alpha',auth_source_mode='shared',auth_rate_enabled=True,auth_rate_secret='synthetic-guest-first-key-'*3,registration_enabled=False,secure_cookies=True,trusted_hosts=('guest.example.test',),external_origin=ORIGIN)
    db=None
    if os.environ.get('LIFEWORLD_TEST_BACKEND')=='postgresql':
        from pg_support import bootstrap
        from app.postgres import PostgresDatabase
        config=bootstrap.test_config()
        with bootstrap.admin_connection('life_world_alpha') as raw,closing(raw.cursor()) as c:
            c.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert c.fetchone()[0]=='STEP10_LOCAL_SYNTHETIC_ONLY'
            c.execute("SELECT tablename FROM pg_tables WHERE schemaname='lw_core_draft' AND tablename<>'schema_migrations'")
            names=[r[0] for r in c.fetchall()]
            c.execute('TRUNCATE '+','.join('lw_core_draft."'+n+'"' for n in names)+' RESTART IDENTITY CASCADE')
        settings=replace(settings,backend='postgresql',db_host=config['host'],db_port=config['port'],db_password=config['password'],db_name='life_world_alpha',db_user='lw_alpha_app',pg_tls='disable')
        db=PostgresDatabase(settings)
    app=create_app(tmp_path,settings=settings,database=db,clock=lambda:datetime(2026,11,8,8,tzinfo=timezone.utc))
    record_property('database_backend',app.state.service.db.backend)
    yield app
    app.state.service.db.close()


def client(app):return TestClient(app,base_url=ORIGIN,headers={'Origin':ORIGIN})
def count(app,table):
    assert table in ('users','sessions','goals','actions','experiences','reward_ledger')
    with app.state.service.db.connect() as c:return c.execute('SELECT count(*) FROM '+table).fetchone()[0]
def enter(c):
    r=c.post('/api/auth/guest');assert r.status_code==201,r.text
    c.headers['X-CSRF-Token']=r.json()['csrf_token'];return r

def goal(c):
    enter(c);assert c.put('/api/profile',json={'name':'合成訪客','bio':'測試閱讀','timezone':'Asia/Taipei'}).status_code==200
    today=c.get('/api/auth/me').json()['today'];end=(date.fromisoformat(today)+timedelta(days=7)).isoformat()
    r=c.post('/api/goals',json={'request_id':'guest-goal','title':'合成閱讀','outcome':'完成一篇心得','deadline':end,'actions':[{'title':t,'unit':'次','per_occurrence':'1','dates':[today],'weekdays':[],'cycle':'month'} for t in ['閱讀','筆記','回顧']]});assert r.status_code==201,r.text
    return r.json(),today

def test_G01_first_guest_owner(guest_app):
    with client(guest_app) as c:
        r=enter(c);assert r.json()['status']=='guest';assert count(guest_app,'users')==count(guest_app,'sessions')==1

def test_G02_retry_same_session_never_creates_second_world(guest_app):
    with client(guest_app) as c:
        first=enter(c).json()
        for _ in range(3):
            r=c.post('/api/auth/guest');assert r.status_code==200;assert r.json()['owner_id']==first['owner_id']
        assert count(guest_app,'users')==count(guest_app,'sessions')==1

def test_G03_secure_cookie_and_hash_only_storage(guest_app):
    with client(guest_app) as c:
        r=enter(c);cookie=r.headers['set-cookie'].lower()
        assert all(x in cookie for x in ['httponly','secure','samesite=strict'])
        with guest_app.state.service.db.connect() as db:
            saved=db.execute('SELECT token_hash FROM sessions').fetchone()['token_hash'];assert saved!=c.cookies.get('lw_session')

def test_G04_goal_persisted(guest_app):
    with client(guest_app) as c:g,_=goal(c);assert c.get('/api/goals/'+g['id']).status_code==200;assert count(guest_app,'goals')==1

def test_G05_three_habits_same_owner(guest_app):
    with client(guest_app) as c:
        g,_=goal(c);assert len(g['actions'])==3;assert count(guest_app,'actions')==3

def test_G06_experience_edit_confirm_reward_once(guest_app):
    with client(guest_app) as c:
        g,today=goal(c);r=c.post('/api/experiences/drafts',json={'raw_text':'合成：閱讀十五分鐘，寫一段筆記。','occurred_at':today+'T09:00:00+08:00','goal_id':g['id'],'contributions':[{'action_id':g['actions'][0]['id'],'quantity':'1'}]});assert r.status_code==201
        draft=r.json();assert count(guest_app,'experiences')==0
        payload={'request_id':'guest-confirm','expected_revision':draft['revision'],'summary':'人工確認閱讀與筆記','person_id':None,'contributions':draft['contributions'],'tasks':['明天整理下一章']}
        url='/api/drafts/'+draft['id']+'/confirm';first=c.post(url,json=payload);assert first.status_code==201,first.text;assert c.post(url,json=payload).json()==first.json()
        assert count(guest_app,'experiences')==count(guest_app,'reward_ledger')==1
        world=c.get('/api/state').json();assert len(world['tasks'])==1;assert world['goals'][0]['actions'][0]['progress']=='1'

def test_G07_new_client_with_cookie_recovers_postgres_world(guest_app):
    settings=guest_app.state.settings;old_db=guest_app.state.service.db
    with client(guest_app) as c:g,_=goal(c);cookies=dict(c.cookies);owner=c.get('/api/auth/me').json()['owner_id']
    # 關閉App後必須建立新pool，才是真正服務重啟回讀；不可重用已關閉的PG pool。
    if old_db.backend=='postgresql':
        from app.postgres import PostgresDatabase
        reopened=PostgresDatabase(settings)
    else:
        from app.db import Database
        reopened=Database(old_db.directory)
    restarted=create_app(database=reopened,settings=settings,clock=lambda:datetime(2026,11,8,8,tzinfo=timezone.utc))
    with client(restarted) as restored:
        restored.cookies.update(cookies);me=restored.get('/api/auth/me');assert me.status_code==200,me.text;assert me.json()['owner_id']==owner;assert restored.get('/api/goals/'+g['id']).status_code==200

def test_G08_anonymous_and_other_guest_isolation(guest_app):
    with client(guest_app) as a,client(guest_app) as b:
        g,_=goal(a);assert b.get('/api/state').status_code==401;other,_=goal(b);assert b.get('/api/goals/'+g['id']).status_code==404;assert a.get('/api/goals/'+other['id']).status_code==404;assert [x['id'] for x in b.get('/api/state').json()['goals']]==[other['id']]

def test_G09_wrong_origin_and_csrf_rejected(guest_app):
    with client(guest_app) as c:
        assert c.post('/api/auth/guest',headers={'Origin':'https://evil.example'}).status_code==403
        enter(c);data={'name':'合成','bio':'測試','timezone':'UTC'}
        assert c.put('/api/profile',json=data,headers={'X-CSRF-Token':'wrong'}).status_code==403
        assert c.put('/api/profile',json=data,headers={'Origin':'https://evil.example'}).status_code==403

def test_G10_database_failure_never_returns_success(guest_app,monkeypatch):
    def broken(*args,**kwargs):raise DomainError(503,'database_unavailable','資料服務暫時不可用。')
    monkeypatch.setattr(guest_app.state.service.db,'connect',broken)
    with client(guest_app) as c:
        r=c.post('/api/auth/guest');assert r.status_code==503;assert 'lw_session=' not in r.headers.get('set-cookie','');assert r.json()['error']['code'] in ('database_unavailable','protection_unavailable')
