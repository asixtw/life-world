"""生日與多筆任職必須保存、留版本並隔離Owner；合成SQLite API驗收。"""
from fastapi.testclient import TestClient
from conftest import onboard,register


def person(client):
    onboard(client);register(client)
    return client.post('/api/people',json={'name':'合成人物'}).json()['id']


def test_birthday_roundtrip_correction_and_history(client):
    p=person(client);url='/api/people/'+p+'/basic-details'
    body={'request_id':'birthday-one','expected_revision':0,'confirmed':True,'value':{'birth_month':4,'birth_day':12},'source':{'source_kind':'manual'}}
    r=client.patch(url,json=body);assert r.status_code==200,r.text
    assert client.patch(url,json=body).json()==r.json()
    body.update(request_id='birthday-two',expected_revision=1,value={'birth_year':1998,'birth_month':4,'birth_day':12})
    assert client.patch(url,json=body).status_code==200
    details=client.get('/api/people/'+p+'/details').json()
    assert details['birthday']['birth_year']==1998
    assert [h['revision'] for h in details['birthday_history']]==[1,2]
    assert details['birthday_history'][0]['birth_year'] is None
    assert 'age' not in details['birthday']
    assert client.patch(url,json=body|{'request_id':'stale','expected_revision':1}).status_code==409


def test_two_current_employments_and_patch_preserve_other_fields(client):
    p=person(client);url='/api/people/'+p+'/employments'
    body={'request_id':'job-one','confirmed':True,'value':{'company_name':'組織一','employment_status':'current'},'source':{'source_kind':'manual'}}
    r=client.post(url,json=body);assert r.status_code==201,r.text
    assert client.post(url,json=body).json()==r.json()
    second=client.post(url,json=body|{'request_id':'job-two','value':{'job_title':'自由工作者','employment_status':'current'}})
    assert second.status_code==201,second.text
    job=r.json()
    patch={'request_id':'job-edit','expected_revision':job['revision'],'confirmed':True,'value':{'job_title':'研究員'},'source':{'source_kind':'manual'}}
    r=client.patch(url+'/'+job['id'],json=patch);assert r.status_code==200,r.text
    assert r.json()['company_name']=='組織一' and r.json()['job_title']=='研究員'
    details=client.get('/api/people/'+p+'/details').json()
    assert len(details['employments'])==2 and all(x['employment_status']=='current' for x in details['employments'])
    assert len(details['employment_history'])==3


def test_details_cross_owner_and_unconfirmed_are_refused(client,app):
    p=person(client);url='/api/people/'+p+'/basic-details'
    body={'request_id':'birthday','expected_revision':0,'confirmed':False,'value':{},'source':{'source_kind':'manual'}}
    assert client.patch(url,json=body).status_code==422
    with TestClient(app) as other:
        onboard(other);register(other,'other_details')
        assert other.get('/api/people/'+p+'/details').status_code==404
        assert other.patch(url,json=body|{'confirmed':True}).status_code==404


def test_confirm_two_new_people_basic_data_and_retry(client):
    from conftest import draft,confirm_payload
    _,g=onboard(client);register(client)
    d=draft(client,g,raw_text='小安和小林一起閱讀。',contributions=[])
    target=lambda ref:{'client_ref':ref}
    source={'source_kind':'manual'}
    body=confirm_payload(d,contributions=[],story_reviewed=True,pending_people=[{'client_ref':'a','name':'小安','relation':'interaction'},{'client_ref':'b','name':'小林','relation':'participant'}],
        birthday_updates=[{'target':target('a'),'expected_revision':0,'source_revision':d['revision'],'selected':True,'value':{'birth_month':4,'birth_day':12},'source':source}],
        employment_updates=[{'target':target('a'),'client_ref':'a-job','source_revision':d['revision'],'selected':True,'value':{'company_name':'組織A'},'source':source},{'target':target('b'),'client_ref':'b-job','source_revision':d['revision'],'selected':True,'value':{'job_title':'設計師'},'source':source}])
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=body);assert r.status_code==201,r.text
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=body).json()==r.json()
    refs=r.json()['created_people']
    a=client.get('/api/people/'+refs['a']+'/details').json();b=client.get('/api/people/'+refs['b']+'/details').json()
    assert a['birthday']['birth_month']==4 and b['birthday'] is None
    assert a['employments'][0]['company_name']=='組織A' and b['employments'][0]['job_title']=='設計師'
    assert len(a['employment_history'])==len(b['employment_history'])==1
    state=client.get('/api/state').json();assert len(state['experiences'])==1 and state['rewards']['total']==3


def test_confirm_late_basic_conflict_rolls_back_all_rows(client):
    from conftest import draft,confirm_payload
    _,g=onboard(client);register(client)
    d=draft(client,g,contributions=[])
    body=confirm_payload(d,contributions=[],story_reviewed=True,pending_people=[{'client_ref':'a','name':'待建','relation':'participant'}],birthday_updates=[{'target':{'client_ref':'a'},'expected_revision':1,'source_revision':d['revision'],'selected':True,'value':{'birth_month':4,'birth_day':12},'source':{'source_kind':'manual'}}])
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=body);assert r.status_code==409,r.text
    state=client.get('/api/state').json();assert not state['people'] and not state['experiences'] and state['rewards']['total']==0
    with client.app.state.service.db.connect() as c:
        for table in ['person_basic_details','person_basic_detail_history','person_employments','person_employment_history']:
            assert c.execute('SELECT count(*) FROM '+table).fetchone()[0]==0
