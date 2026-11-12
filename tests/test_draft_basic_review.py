"""生日/任職可保存於同一核對草稿，未確認不寫正式資料；合成資料不送模型。"""
import hashlib
from fastapi.testclient import TestClient
from conftest import onboard,register,draft,confirm_payload


def digest(raw):return hashlib.sha256(raw.encode()).hexdigest()


def setup(client):
    _,goal=onboard(client);register(client)
    raw='小安說生日是四月十二日，在組織甲工作。'
    review={'summary':'人工摘要','summary_source_sha256':digest(raw),'tasks':[],
      'birthday_candidates':[{'candidate_ref':'birthday-a','target':{'client_ref':'a'},'expected_revision':0,'value':{'birth_month':4,'birth_day':12},'source_kind':'manual','selected':True}],
      'employment_candidates':[{'candidate_ref':'job-a','target':{'client_ref':'a'},'value':{'company_name':'組織甲','job_title':'研究員','employment_status':'current'},'source_kind':'raw','source_sha256':digest(raw),'quote':'在組織甲工作','evidence_type':'stated_by_person','selected':True},
        {'candidate_ref':'job-b','target':{'client_ref':'b'},'value':{'company_name':'組織乙'},'source_kind':'manual','selected':True}]}
    d=draft(client,goal,raw_text=raw,contributions=[],story={'pending_people':[{'client_ref':'a','name':'同名','relation':'interaction'},{'client_ref':'b','name':'同名','relation':'participant'}]},review=review)
    return goal,d


def payload(d,**kwargs):
    return confirm_payload(d,summary='人工摘要',contributions=[],tasks=[],story=d['story'],story_reviewed=True,use_saved_review=True,**kwargs)


def test_basic_review_roundtrip_new_people_session_retry_and_independent_values(client,app):
    _,d=setup(client)
    assert not client.get('/api/state').json()['people']
    with TestClient(app) as other:
        r=other.post('/api/auth/login',json={'username':'lumi_user','password':'a-good-password-2026'});assert r.status_code==200
        other.headers['X-CSRF-Token']=r.json()['csrf_token']
        read=other.get('/api/drafts/'+d['id']).json();assert read['review']==d['review']
        r=other.post('/api/drafts/'+d['id']+'/confirm',json=payload(read));assert r.status_code==201,r.text
        assert other.post('/api/drafts/'+d['id']+'/confirm',json=payload(read)).json()==r.json()
        ids=r.json()['created_people'];assert ids['a']!=ids['b']
        a=other.get('/api/people/'+ids['a']+'/details').json();b=other.get('/api/people/'+ids['b']+'/details').json()
        assert a['birthday']['birth_year'] is None and a['birthday']['birth_month']==4 and b['birthday'] is None
        assert a['employments'][0]['company_name']=='組織甲' and b['employments'][0]['company_name']=='組織乙'
        assert a['employments'][0]['source_experience_id']==r.json()['experience_id']
        state=other.get('/api/state').json();assert len(state['experiences'])==len(state['rewards']['events'])==1


def test_basic_source_changes_revoke_raw_only_and_unresolved_cannot_confirm(client):
    _,d=setup(client);raw='只有更新後的真實經歷。'
    changed=client.put('/api/drafts/'+d['id'],json={'expected_revision':d['revision'],'raw_text':raw,'occurred_at':d['occurred_at'],'contributions':[]});assert changed.status_code==200,changed.text
    d=changed.json();review=d['review']
    assert review['birthday_candidates'][0]['selected']
    assert review['employment_candidates'][1]['selected']
    candidate=review['employment_candidates'][0];assert candidate['needs_review'] and not candidate['selected'] and candidate['value']['company_name']=='組織甲'
    review['summary_source_sha256']=digest(raw)
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=payload(d,review=review));assert r.status_code==409
    assert not client.get('/api/state').json()['people']
    candidate['excluded']=True
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=payload(d,review=review));assert r.status_code==201,r.text
    assert not client.get('/api/people/'+r.json()['created_people']['a']+'/details').json()['employments']


def test_basic_incomplete_preserved_and_no_legacy_silent_drop_or_mixed_contract(client):
    _,d=setup(client);review=d['review']
    review['birthday_candidates'][0]['value']={'birth_month':2,'birth_day':31}
    review['employment_candidates'][0]['value']={}
    r=client.put('/api/drafts/'+d['id'],json={'expected_revision':d['revision'],'raw_text':d['raw_text'],'occurred_at':d['occurred_at'],'contributions':[],'review':review});assert r.status_code==200,r.text
    d=r.json();assert d['review']['birthday_candidates'][0]['value']['birth_day']==31
    for key in ['birthday_candidates','employment_candidates']:assert d['review'][key][0]['needs_review'] and not d['review'][key][0]['selected']
    legacy=payload(d);legacy.pop('use_saved_review');assert client.post('/api/drafts/'+d['id']+'/confirm',json=legacy).status_code==409
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=payload(d)).status_code==409
    mixed=payload(d,birthday_updates=[{'target':{'client_ref':'a'},'expected_revision':0,'source_revision':d['revision'],'selected':True,'value':{},'source':{'source_kind':'manual'}}])
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=mixed);assert r.status_code==422,r.text
    assert not client.get('/api/state').json()['people']


def test_basic_review_guest_owner_and_duplicate_reference_boundaries(client,app):
    goal,d=setup(client);review=d['review']
    with TestClient(app) as other:
        _,g=onboard(other)
        # 即使只夾帶基本資料候選也不能繞過訪客限制。
        r=other.post('/api/experiences/drafts',json={'raw_text':d['raw_text'],'occurred_at':d['occurred_at'],'contributions':[],'review':review,'story':d['story']});assert r.status_code==403,r.text
        register(other,'basic_review_other');p=other.post('/api/people',json={'name':'別人的人物'}).json()
        assert other.get('/api/drafts/'+d['id']).status_code==404
    review['birthday_candidates'][0]['target']={'person_id':p['id']}
    r=client.put('/api/drafts/'+d['id'],json={'expected_revision':d['revision'],'raw_text':d['raw_text'],'occurred_at':d['occurred_at'],'contributions':[],'review':review});assert r.status_code==404,r.text
    review=d['review'];review['employment_candidates'][0]['candidate_ref']=review['birthday_candidates'][0]['candidate_ref']
    r=client.post('/api/experiences/drafts',json={'raw_text':d['raw_text'],'occurred_at':d['occurred_at'],'contributions':[],'review':review,'story':d['story']});assert r.status_code==422,r.text
    assert len(client.get('/api/state').json()['drafts'])==1


def test_existing_employment_partial_patch_and_late_birthday_conflict_are_atomic(client):
    goal,d=setup(client);p=client.post('/api/people',json={'name':'既有人物'}).json()
    job=client.post('/api/people/'+p['id']+'/employments',json={'request_id':'prior-job','confirmed':True,'value':{'company_name':'原組織','job_title':'原職稱','employment_status':'current'},'source':{'source_kind':'manual'}}).json()
    review=d['review'];review['birthday_candidates'][0]['expected_revision']=1  # 新人物實際尚無生日，最後階段必須衝突回滾。
    review['employment_candidates']=[{'candidate_ref':'existing-job','target':{'person_id':p['id']},'employment_id':job['id'],'expected_revision':job['revision'],'value':{'job_title':'新職稱'},'source_kind':'manual','selected':True}]
    story=d['story'];story['participants']=[{'person_id':p['id'],'interacted':False}]
    r=client.put('/api/drafts/'+d['id'],json={'expected_revision':d['revision'],'raw_text':d['raw_text'],'occurred_at':d['occurred_at'],'contributions':[],'review':review,'story':story});assert r.status_code==200,r.text
    d=r.json();assert d['review']['employment_candidates'][0]['value']=={'job_title':'新職稱'}
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=payload(d));assert r.status_code==409,r.text
    details=client.get('/api/people/'+p['id']+'/details').json();assert details['employments'][0]['job_title']=='原職稱' and len(details['employment_history'])==1
    state=client.get('/api/state').json();assert len(state['people'])==1 and not state['experiences'] and not state['rewards']['events']
    review=d['review'];review['birthday_candidates'][0]['expected_revision']=0
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=payload(d,review=review));assert r.status_code==201,r.text
    details=client.get('/api/people/'+p['id']+'/details').json();assert details['employments'][0]['company_name']=='原組織' and details['employments'][0]['job_title']=='新職稱'
    assert len(details['employment_history'])==2


def test_basic_existing_job_cannot_target_other_person_and_empty_birthday_requires_explicit_clear(client):
    goal,d=setup(client);p=client.post('/api/people',json={'name':'任職Owner'}).json();q=client.post('/api/people',json={'name':'另一人物'}).json()
    job=client.post('/api/people/'+p['id']+'/employments',json={'request_id':'job','confirmed':True,'value':{'company_name':'組織'},'source':{'source_kind':'manual'}}).json()
    review=d['review'];review['birthday_candidates'][0]['value']={}
    review['employment_candidates']=[{'candidate_ref':'wrong-job','target':{'person_id':q['id']},'employment_id':job['id'],'expected_revision':1,'value':{'job_title':'不可套錯人'},'source_kind':'manual','selected':True}]
    r=client.put('/api/drafts/'+d['id'],json={'expected_revision':d['revision'],'raw_text':d['raw_text'],'occurred_at':d['occurred_at'],'contributions':[],'review':review});assert r.status_code==404,r.text
    review['employment_candidates']=[]
    r=client.put('/api/drafts/'+d['id'],json={'expected_revision':d['revision'],'raw_text':d['raw_text'],'occurred_at':d['occurred_at'],'contributions':[],'review':review});assert r.status_code==200,r.text
    d=r.json();assert d['review']['birthday_candidates'][0]['needs_review'] and not d['review']['birthday_candidates'][0]['selected']
    review=d['review'];review['birthday_candidates'][0].update(clear=True,selected=True)
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=payload(d,review=review));assert r.status_code==201,r.text
    assert client.get('/api/people/'+r.json()['created_people']['a']+'/details').json()['birthday']['birth_month'] is None
