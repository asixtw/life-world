"""隔離公開模式驗收：無IAP替身、無模型呼叫；不冒充線上Product PG。"""
from dataclasses import replace
from datetime import date,timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import create_app
from app.runtime import RuntimeSettings
from app.security import PASSWORDS

PASSWORD='synthetic-only-public-acceptance'
ORIGIN='https://testserver'


def test_public_password_core_journey_and_owner_isolation(tmp_path):
    settings=replace(RuntimeSettings(),access_mode='public_alpha',auth_source_mode='shared',auth_rate_enabled=True,auth_rate_secret='synthetic-only-public-limit-key-'*3,registration_enabled=False,password_login_enabled=False,test_login_usernames=('synthetic_a','synthetic_b'),external_origin=ORIGIN,secure_cookies=True)
    app=create_app(tmp_path,settings=settings)
    # 僅隔離測試資料；正式環境由受控啟動配置建立一個測試帳號。
    with app.state.service.db.connect(write=True) as db:
        for username in settings.test_login_usernames:
            db.execute("INSERT INTO users(id,status,username,password_hash,name,bio,created_at) VALUES (?,'registered',?,?,?,'合成',?)",(uuid4().hex,username,PASSWORDS.hash(PASSWORD),username,app.state.service.now().isoformat()))
    with TestClient(app,base_url=ORIGIN,headers={'Origin':ORIGIN}) as a,TestClient(app,base_url=ORIGIN,headers={'Origin':ORIGIN}) as b:
        assert a.get('/').status_code==200
        assert a.get('/static/app.js').status_code==200
        assert a.get('/api/state').status_code==401
        assert a.get('/api/people').status_code==401
        assert a.post('/api/drafts/unowned/suggest').status_code==401
        assert a.post('/api/experiences/unowned/task-suggestions',json={'consent':True}).status_code==401
        assert a.post('/api/people/unowned/simulation',json={'consent':True,'fact_ids':['unowned'],'message':'合成問題'}).status_code==401
        assert a.post('/api/auth/login',json={'username':'unknown','password':PASSWORD}).status_code==401
        login=a.post('/api/auth/login',json={'username':'synthetic_a','password':PASSWORD});assert login.status_code==200
        cookie=login.headers['set-cookie'].lower();assert 'secure' in cookie and 'httponly' in cookie and 'samesite=strict' in cookie
        a.headers['X-CSRF-Token']=login.json()['csrf_token']
        assert a.post('/api/auth/claim',json={'username':'public_signup','password':PASSWORD}).status_code==403
        assert a.put('/api/profile',json={'name':'合成A','bio':'合成閱讀驗收','timezone':'Asia/Taipei'}).status_code==200
        today=a.get('/api/auth/me').json()['today']
        payload={'request_id':'public-core-goal','title':'合成閱讀挑戰','outcome':'整理閱讀心得','deadline':(date.fromisoformat(today)+timedelta(days=7)).isoformat(),'actions':[{'title':title,'unit':'次','per_occurrence':'1','dates':[today],'weekdays':[],'cycle':'month'} for title in ['閱讀','記錄心得','整理重點']]}
        goal=a.post('/api/goals',json=payload);assert goal.status_code==201
        goal=goal.json();assert len(goal['actions'])==3
        draft=a.post('/api/experiences/drafts',json={'raw_text':'合成閱讀15分鐘並整理心得。','occurred_at':today+'T09:00:00+08:00','goal_id':goal['id'],'contributions':[{'action_id':goal['actions'][0]['id'],'quantity':'1'}]});assert draft.status_code==201
        draft=draft.json();before=a.get('/api/state').json();assert before['rewards']['total']==0 and before['experiences']==[]
        confirm={'request_id':'public-core-confirm','expected_revision':draft['revision'],'summary':'人工編輯確認的合成摘要','person_id':None,'contributions':draft['contributions'],'tasks':['明天整理下一章重點']}
        url='/api/drafts/'+draft['id']+'/confirm';first=a.post(url,json=confirm);assert first.status_code==201
        repeat=a.post(url,json=confirm);assert repeat.status_code==201 and repeat.json()==first.json()
        world=a.get('/api/state').json();assert len(world['experiences'])==1 and len(world['tasks'])==1 and world['rewards']['total']==1
        assert world['goals'][0]['actions'][0]['progress']=='1'
        other=b.post('/api/auth/login',json={'username':'synthetic_b','password':PASSWORD});assert other.status_code==200
        b.headers['X-CSRF-Token']=other.json()['csrf_token'];assert b.put('/api/profile',json={'name':'合成B','bio':'隔離驗收','timezone':'Asia/Taipei'}).status_code==200
        other_goal=b.post('/api/goals',json={**payload,'request_id':'public-isolation-goal','title':'B私人合成目標'});assert other_goal.status_code==201
        assert b.get('/api/goals/'+goal['id']).status_code==404
        assert a.get('/api/goals/'+other_goal.json()['id']).status_code==404
        assert b.get('/api/state').json()['experiences']==[]
        assert a.put('/api/profile',json={'name':'合成A','bio':'合成','timezone':'Asia/Taipei'},headers={'X-CSRF-Token':'invalid'}).status_code==403
        assert a.put('/api/profile',json={'name':'合成A','bio':'合成','timezone':'Asia/Taipei'},headers={'Origin':'https://evil.example'}).status_code==403
        assert a.post('/api/auth/logout').status_code==204
        assert a.get('/api/auth/me').status_code==401
        restored=a.post('/api/auth/login',json={'username':'synthetic_a','password':PASSWORD});assert restored.status_code==200
        assert restored.json()['owner_id']==login.json()['owner_id']
        reread=a.get('/api/state').json();assert reread['rewards']['total']==1 and len(reread['experiences'])==1
        # 登入來源相同不代表同世界：B工作階段未受到A登出影響。
        assert b.get('/api/auth/me').json()['owner_id']==other.json()['owner_id']


def test_normal_guests_are_fair_and_xff_does_not_split_shared_bucket(tmp_path):
    settings=replace(RuntimeSettings(),access_mode='public_alpha',auth_source_mode='shared',auth_rate_enabled=True,auth_rate_secret='synthetic-only-public-limit-key-'*3,registration_enabled=False,alpha_worlds_total=30,alpha_worlds_daily=30)
    app=create_app(tmp_path,settings=settings)
    for i in range(11):
        with TestClient(app,headers={'X-Forwarded-For':f'198.51.100.{i+1}'}) as c:
            response=c.post('/api/auth/guest')
            assert response.status_code==201
    # shared來源是粗全域，不把所有正常訪客誤當單人10次；偽造XFF仍共用同一HMAC桶。
    with app.state.service.db.connect() as db:
        rows=db.execute("SELECT attempts FROM auth_rate_buckets WHERE scope='guest_source_create'").fetchall()
        assert len(rows)==1 and rows[0]['attempts']==11
