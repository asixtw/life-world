"""持久記憶使用真本機DB；隔離驗證不等於Alpha Migration或線上PASS。"""
import secrets
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from app.main import create_app
from app.relationship_memory import FeatureStore
from conftest import onboard,draft,confirm_payload


def test_preferences_survive_logout_login_and_can_be_erased(tmp_path):
    app=create_app(tmp_path,clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))
    with TestClient(app) as c:
        me,g=onboard(c);name='mem_'+secrets.token_hex(5);password=secrets.token_urlsafe(24)
        r=c.post('/api/auth/claim',json={'username':name,'password':password});assert r.status_code==200
        c.headers['X-CSRF-Token']=r.json()['csrf_token'];owner=r.json()['owner_id'];store=FeatureStore(app.state.service)
        store.configure(owner,True,{'summary_style':'concise'})
        first=store.context(owner);assert first['features'][0]['subject_type']=='user'
        assert c.post('/api/auth/logout').status_code==204
        c.headers.pop('X-CSRF-Token')
        r=c.post('/api/auth/login',json={'username':name,'password':password});assert r.status_code==200
        restored=FeatureStore(app.state.service).context(r.json()['owner_id'])
        assert restored['features'][0]['value']=={'summary_style':'concise'} and restored['training_opt_in'] is False
        store.erase(owner)
        with store.db.connect() as db:assert db.execute('SELECT count(*) AS n FROM relationship_features WHERE owner_id=?',(owner,)).fetchone()['n']==0


def test_owners_do_not_share_preferences_or_features(tmp_path):
    app=create_app(tmp_path,clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc));store=FeatureStore(app.state.service)
    with TestClient(app) as a,TestClient(app) as b:
        ma,_=onboard(a);mb,_=onboard(b)
        store.configure(ma['owner_id'],True,{'summary_style':'detailed'})
        assert store.context(mb['owner_id'])['features']==[]
        assert store.context(ma['owner_id'])['features'][0]['value']=={'summary_style':'detailed'}


def test_four_subjects_and_revoked_source_are_recomputed(tmp_path):
    app=create_app(tmp_path,clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))
    with TestClient(app) as c:
        me,g=onboard(c)
        r=c.post('/api/auth/claim',json={'username':'memory_'+secrets.token_hex(4),'password':secrets.token_urlsafe(24)})
        c.headers['X-CSRF-Token']=r.json()['csrf_token'];owner=r.json()['owner_id']
        person=c.post('/api/people',json={'name':'合成閱讀夥伴'}).json()
        d=draft(c,g,person_id=person['id'])
        r=c.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d,summary='與合成夥伴閱讀植物書籍',person_id=person['id']))
        assert r.status_code==201
        experience=c.get('/api/state').json()['experiences'][0]
        f=c.post('/api/people/'+person['id']+'/facts',json={'request_id':secrets.token_hex(8),'dimension':'interests','value':'閱讀植物書籍','evidence_type':'stated_by_person','source_experience_ids':[experience['id']],'confirmed':True}).json()
        store=FeatureStore(app.state.service);store.configure(owner,True,{'summary_style':'concise'})
        first=store.context(owner,person['id'])
        assert {f['subject_type'] for f in first['features']}=={'user','person','relationship','context'}
        r=c.post('/api/people/'+person['id']+'/facts/'+f['id']+'/sources/revoke',json={'expected_revision':f['revision'],'experience_id':experience['id']})
        assert r.status_code==200
        current=store.context(owner,person['id'])
        assert not any(f['subject_type'] in ('person','relationship') for f in current['features'])


def test_withdrawn_story_not_reused_in_any_memory_subject(tmp_path):
    """撤回派生來源後不可由一般經歷查詢重新帶回User/Context或人物資訊。"""
    app=create_app(tmp_path,clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))
    with TestClient(app) as c:
        me,g=onboard(c)
        r=c.post('/api/auth/claim',json={'username':'withdraw_'+secrets.token_hex(4),'password':secrets.token_urlsafe(24)})
        c.headers['X-CSRF-Token']=r.json()['csrf_token'];owner=r.json()['owner_id']
        person=c.post('/api/people',json={'name':'合成來源人物'}).json()
        d=draft(c,g,person_id=person['id'])
        r=c.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d,summary='閱讀書籍與學習工作',person_id=person['id'],story={'participants':[{'person_id':person['id'],'interacted':True}]},story_reviewed=True))
        assert r.status_code==201,r.text
        experience=c.get('/api/state').json()['experiences'][0]
        r=c.post('/api/people/'+person['id']+'/facts',json={'request_id':'source-fact','dimension':'interests','value':'閱讀','evidence_type':'stated_by_person','source_experience_ids':[experience['id']],'confirmed':True})
        assert r.status_code==201,r.text
        store=FeatureStore(app.state.service);store.configure(owner,True,{'summary_style':'concise'})
        assert any(experience['id'] in f['source_refs'] for f in store.context(owner,person['id'])['features'])
        story=c.get('/api/connections/stories/'+experience['id']).json()
        r=c.post('/api/connections/stories/'+experience['id']+'/availability',json={'request_id':'withdraw-story','expected_revision':story['revision'],'available':False})
        assert r.status_code==200,r.text
        for target in (person['id'],None):
            current=store.context(owner,target)
            assert not any(experience['id'] in f['source_refs'] for f in current['features'])
        with store.db.connect() as db:
            rows=db.execute('SELECT source_refs,revocation_state FROM relationship_features WHERE owner_id=?',(owner,)).fetchall()
            assert all(experience['id'] not in row['source_refs'] for row in rows)
        facts=c.get('/api/people/'+person['id']+'/overview').json()['facts']['interests']
        assert len(facts)==1 and facts[0]['value']=='閱讀'  # 記憶撤回不冒充刪除正式人物事實。
        # 只撤回衍生用途，原始正式經歷與獎勵不得被刪除。
        state=c.get('/api/state').json()
        assert len(state['experiences'])==len(state['rewards']['events'])==1

        restored=c.post('/api/connections/stories/'+experience['id']+'/availability',json={'request_id':'restore-story','expected_revision':r.json()['revision'],'available':True})
        assert restored.status_code==200,restored.text
        assert any(experience['id'] in f['source_refs'] for f in store.context(owner,person['id'])['features'])
