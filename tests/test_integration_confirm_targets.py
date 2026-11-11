"""同一確認交易的多人定向、待建人物與保存草稿刪除契約。"""
import pytest
from fastapi.testclient import TestClient
from conftest import onboard, register, draft, confirm_payload


def test_targeted_confirm_creates_people_and_facts_atomically(client):
    _,g=onboard(client);register(client)
    d=draft(client,g,raw_text='和小安閱讀，提到小明。',contributions=[])
    body=confirm_payload(d,contributions=[],story_reviewed=True,pending_people=[
        {'client_ref':'one','name':'小安','relation':'interaction'},
        {'client_ref':'two','name':'小明','relation':'mention','start':8}],targeted_person_updates=[
        {'target':{'client_ref':'one'},'dimension':'interests','value':'閱讀','evidence_type':'stated_by_person','selected':True,'source_kind':'manual','source_revision':d['revision']}])
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=body)
    assert r.status_code==201,r.text
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=body).json()==r.json()
    people=client.get('/api/state').json()['people']
    assert len(people)==2
    p=next(p for p in people if p['name']=='小安')
    overview=client.get('/api/people/'+p['id']+'/overview').json()
    assert '閱讀' in str(overview)
    assert overview['stats']['interactions']==1
    other=next(p for p in people if p['name']=='小明')
    assert client.get('/api/people/'+other['id']+'/overview').json()['stats']['interactions']==0


def test_invalid_target_rolls_back_new_people(client):
    _,g=onboard(client);register(client)
    d=draft(client,g,contributions=[])
    body=confirm_payload(d,contributions=[],story_reviewed=True,pending_people=[{'client_ref':'one','name':'待建','relation':'participant'}],targeted_person_updates=[{'target':{'client_ref':'missing'},'dimension':'food','value':'清淡','evidence_type':'observed_by_user','selected':True,'source_kind':'manual','source_revision':d['revision']}])
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=body)
    assert r.status_code in (404,422),r.text
    s=client.get('/api/state').json();assert not s['people'] and not s['experiences'] and s['rewards']['total']==0


def test_delete_saved_draft_revision_owner_and_retry(client,app):
    _,g=onboard(client);register(client)
    d=draft(client,g)
    url='/api/drafts/'+d['id'];body={'request_id':'delete-owned','expected_revision':d['revision']}
    with TestClient(app) as other:
        onboard(other);register(other,'other_deleter')
        assert other.request('DELETE',url,json=body).status_code==404
    stale={**body,'expected_revision':d['revision']+1}
    assert client.request('DELETE',url,json=stale).status_code==409
    r=client.request('DELETE',url,json=body);assert r.status_code==200,r.text
    assert client.request('DELETE',url,json=body).json()==r.json()
    assert client.get(url).status_code==404


@pytest.mark.parametrize('kind,subtype',[('fictional',None),('real','historical')])
def test_unqualified_people_cannot_be_real_participants(client,kind,subtype):
    _,g=onboard(client);register(client)
    p=client.post('/api/persons',json={'request_id':'typed','name':'型別人物','person_type':kind,'person_subtype':subtype}).json()
    d=draft(client,g,contributions=[])
    body=confirm_payload(d,contributions=[],story={'participants':[{'person_id':p['id'],'interacted':True}]},story_reviewed=True)
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=body)
    assert r.status_code==422,r.text
    state=client.get('/api/state').json();assert not state['experiences'] and state['rewards']['total']==0


def test_existing_person_revision_failure_rolls_back_all_new_people(client):
    _,g=onboard(client);register(client)
    p=client.post('/api/people',json={'name':'既有人物'}).json()
    d=draft(client,g,contributions=[])
    body=confirm_payload(d,contributions=[],story_reviewed=True,story={'participants':[{'person_id':p['id'],'interacted':False}]},pending_people=[{'client_ref':'one','name':'不應留下','relation':'participant'}],targeted_person_updates=[{'target':{'person_id':p['id']},'expected_person_revision':p['revision']+1,'dimension':'food','value':'清淡','evidence_type':'observed_by_user','selected':True,'source_kind':'manual','source_revision':d['revision']}])
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=body).status_code==409
    state=client.get('/api/state').json();assert len(state['people'])==1 and not state['experiences'] and state['rewards']['total']==0
