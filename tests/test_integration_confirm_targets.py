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


def test_multiple_pending_people_survive_saved_draft_without_creating_people(client):
    _,g=onboard(client);register(client)
    pending=[{'client_ref':'p1','name':'小安','relation':'interaction'},{'client_ref':'p2','name':'小明','relation':'mention','start':8}]
    d=draft(client,g,raw_text='和小安閱讀，提到小明。',contributions=[],story={'pending_people':pending})
    assert client.get('/api/drafts/'+d['id']).json()['story']['pending_people']==pending
    assert not client.get('/api/state').json()['people']
    body=confirm_payload(d,contributions=[],story=d['story'],story_reviewed=True)
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=body);assert r.status_code==201,r.text
    assert set(r.json()['created_people'])=={'p1','p2'}
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=body).json()==r.json()
    assert len(client.get('/api/state').json()['people'])==2


def test_draft_pending_people_require_registration_and_unique_refs(client):
    _,g=onboard(client)
    payload={'raw_text':'和小安閱讀','occurred_at':'2026-10-27T00:10:00+08:00','contributions':[],'story':{'pending_people':[{'client_ref':'a','name':'小安','relation':'participant'}]}}
    assert client.post('/api/experiences/drafts',json=payload).status_code==403
    register(client)
    duplicate=payload|{'story':{'pending_people':payload['story']['pending_people']*2}}
    assert client.post('/api/experiences/drafts',json=duplicate).status_code==422


def test_pending_people_edit_source_and_ambiguous_confirm_fail_without_orphans(client):
    _,g=onboard(client);register(client)
    payload={'raw_text':'小安提到小明','occurred_at':'2026-10-27T00:10:00+08:00','contributions':[],'story':{'pending_people':[{'client_ref':'mention','name':'小明','relation':'mention','start':4}]}}
    r=client.post('/api/experiences/drafts',json=payload);assert r.status_code==201,r.text
    d=r.json();url='/api/drafts/'+d['id']
    # 原文變更不能悄悄保存舊位置；失敗保留先前草稿版本與候選，不建人物。
    assert client.put(url,json=payload|{'raw_text':'沒有原先的人名','expected_revision':d['revision']}).status_code==422
    assert client.get(url).json()['raw_text']==payload['raw_text']
    body=confirm_payload(d,contributions=[],story=d['story'],story_reviewed=True,pending_people=[{'client_ref':'extra','name':'另一人','relation':'participant'}])
    assert client.post(url+'/confirm',json=body).status_code==422
    assert not client.get('/api/state').json()['people']
    deletion={'request_id':'cancel-pending','expected_revision':d['revision']}
    assert client.request('DELETE',url,json=deletion).status_code==200
    assert not client.get('/api/state').json()['people']
