"""同一草稿JSON保存人工摘要及逐人候選；保存不建人，確認才原子寫入。"""
import hashlib
import pytest
from app.errors import DomainError
from fastapi.testclient import TestClient
from conftest import onboard,register,draft,confirm_payload


def sha(raw):return hashlib.sha256(raw.encode()).hexdigest()


def review(raw):
    return {'summary':'人工整理摘要','summary_source_sha256':sha(raw),'tasks':['下次繼續閱讀'],'person_candidates':[{'candidate_ref':'fact-one','target':{'client_ref':'one'},'dimension':'interests','value':'閱讀','source_kind':'raw','source_sha256':sha(raw),'quote':'喜歡閱讀','evidence_type':'stated_by_person','selected':True}]}


def test_saved_review_roundtrip_and_confirm_creates_selected_fact_once(client):
    _,g=onboard(client);register(client);raw='小安說喜歡閱讀。'
    d=draft(client,g,raw_text=raw,contributions=[],story={'pending_people':[{'client_ref':'one','name':'小安','relation':'interaction'}]},review=review(raw))
    read=client.get('/api/drafts/'+d['id']).json()
    assert read['review']['summary']=='人工整理摘要' and read['raw_sha256']==sha(raw)
    assert read['review']['person_candidates'][0]['selected'] and not client.get('/api/state').json()['people']
    payload=confirm_payload(d,summary='人工整理摘要',tasks=['下次繼續閱讀'],contributions=[],story=d['story'],story_reviewed=True,use_saved_review=True)
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=payload);assert r.status_code==201,r.text
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=payload).json()==r.json()
    pid=r.json()['created_people']['one'];overview=client.get('/api/people/'+pid+'/overview').json()
    assert overview['facts']['interests'][0]['value']=='閱讀'
    state=client.get('/api/state').json();assert len(state['experiences'])==len(state['tasks'])==1 and len(state['rewards']['events'])==1


def test_raw_edit_preserves_review_but_invalidates_raw_candidates(client):
    _,g=onboard(client);register(client);raw='小安說喜歡閱讀。'
    d=draft(client,g,raw_text=raw,contributions=[],story={'pending_people':[{'client_ref':'one','name':'小安','relation':'participant'}]},review=review(raw))
    changed='小安說喜歡跑步。'
    r=client.put('/api/drafts/'+d['id'],json={'raw_text':changed,'occurred_at':d['occurred_at'],'contributions':[],'expected_revision':d['revision']});assert r.status_code==200,r.text
    d=r.json();candidate=d['review']['person_candidates'][0]
    assert d['review']['summary']=='人工整理摘要' and d['review']['summary_needs_review']
    assert candidate['value']=='閱讀' and candidate['needs_review'] and not candidate['selected']
    payload=confirm_payload(d,contributions=[],story=d['story'],story_reviewed=True,use_saved_review=True)
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=payload).status_code==409
    assert not client.get('/api/state').json()['people']
    final=d['review'];final['summary']='重新核對後摘要';final['summary_source_sha256']=sha(changed);candidate['excluded']=True
    payload.update(review=final,summary=final['summary'],tasks=final['tasks'])
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=payload);assert r.status_code==201,r.text
    pid=r.json()['created_people']['one'];assert not client.get('/api/people/'+pid+'/overview').json()['facts']['interests']


def test_legacy_confirm_cannot_silently_drop_saved_person_candidates(client):
    _,g=onboard(client);register(client);raw='小安說喜歡閱讀。'
    d=draft(client,g,raw_text=raw,contributions=[],story={'pending_people':[{'client_ref':'one','name':'小安','relation':'participant'}]},review=review(raw))
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d,contributions=[],story=d['story'],story_reviewed=True))
    assert r.status_code==409 and r.json()['error']['code']=='saved_review_required'


def test_review_owner_isolation_incomplete_evidence_and_manual_preservation(client,app):
    _,g=onboard(client);register(client);raw='小安說喜歡閱讀。';r=review(raw)
    manual={'candidate_ref':'manual','target':{'client_ref':'one'},'dimension':'food','value':'清淡','source_kind':'manual','evidence_type':None,'selected':True}
    r['person_candidates'].append(manual)
    d=draft(client,g,raw_text=raw,contributions=[],story={'pending_people':[{'client_ref':'one','name':'小安','relation':'participant'}]},review=r)
    assert d['review']['person_candidates'][1]['needs_review'] and not d['review']['person_candidates'][1]['selected']
    with TestClient(app) as other:
        onboard(other);register(other,'review_other')
        assert other.get('/api/drafts/'+d['id']).status_code==404
        assert other.put('/api/drafts/'+d['id'],json={'raw_text':raw,'occurred_at':d['occurred_at'],'contributions':[],'expected_revision':1,'review':r}).status_code==404
        pid=other.post('/api/people',json={'name':'其他帳號人物'}).json()['id']
    r['person_candidates'][0]['target']={'person_id':pid}
    invalid=client.post('/api/experiences/drafts',json={'raw_text':raw,'occurred_at':d['occurred_at'],'contributions':[],'review':r})
    assert invalid.status_code==404
    assert len(client.get('/api/state').json()['drafts'])==1


def test_saved_review_person_revision_conflict_rolls_back_new_people(client):
    _,g=onboard(client);register(client);p=client.post('/api/people',json={'name':'既有人物'}).json();raw='一起閱讀。'
    r=review(raw);r['person_candidates'][0].update(target={'person_id':p['id']},expected_person_revision=p['revision']+1,source_kind='manual',source_sha256=None,quote=None)
    d=draft(client,g,raw_text=raw,contributions=[],story={'participants':[{'person_id':p['id'],'interacted':False}],'pending_people':[{'client_ref':'one','name':'不該留下','relation':'participant'}]},review=r)
    payload=confirm_payload(d,summary=r['summary'],tasks=r['tasks'],contributions=[],story=d['story'],story_reviewed=True,use_saved_review=True)
    response=client.post('/api/drafts/'+d['id']+'/confirm',json=payload);assert response.status_code==409
    state=client.get('/api/state').json();assert len(state['people'])==1 and not state['experiences'] and not state['tasks'] and not state['rewards']['events']
    assert client.get('/api/drafts/'+d['id']).json()['status']=='draft'


def test_guest_can_save_manual_review_without_person_candidates(client):
    _,g=onboard(client);raw='個人日記。'
    d=draft(client,g,raw_text=raw,contributions=[],review={'summary':'自訂摘要','summary_source_sha256':sha(raw),'tasks':['手動下一步']})
    assert d['story'] is None and d['review']['summary']=='自訂摘要'
    response=client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d,summary='自訂摘要',contributions=[],tasks=['手動下一步'],use_saved_review=True))
    assert response.status_code==201,response.text


def test_manual_candidates_survive_raw_edit_and_two_targets_remain_separate(client,app):
    me,g=onboard(client);register(client);raw='一起活動。'
    r={'summary':'自己的摘要','summary_source_sha256':sha(raw),'tasks':[],'person_candidates':[
        {'candidate_ref':'a','target':{'client_ref':'one'},'dimension':'interests','value':'登山','source_kind':'manual','evidence_type':'stated_by_person','selected':True},
        {'candidate_ref':'b','target':{'client_ref':'two'},'dimension':'food','value':'清淡','source_kind':'manual','evidence_type':'observed_by_user','selected':True}]}
    d=draft(client,g,raw_text=raw,contributions=[],story={'pending_people':[{'client_ref':'one','name':'同名','relation':'interaction'},{'client_ref':'two','name':'同名','relation':'participant'}]},review=r)
    changed=raw+'補充時間。'
    d=client.put('/api/drafts/'+d['id'],json={'raw_text':changed,'occurred_at':d['occurred_at'],'contributions':[],'expected_revision':d['revision']}).json()
    assert all(p['selected'] and not p['needs_review'] for p in d['review']['person_candidates'])
    # 重新登入是伺服器草稿讀回，不依賴前端記憶體；跨Session保留來源與逐人目標。
    with TestClient(app) as again:
        response=again.post('/api/auth/login',json={'username':'lumi_user','password':'a-good-password-2026'})
        assert response.status_code==200,response.text
        again.headers['X-CSRF-Token']=response.json()['csrf_token']
        read=again.get('/api/drafts/'+d['id']).json();assert read['review']==d['review']
        final=read['review'];final['summary_source_sha256']=sha(changed)
        response=again.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d,summary=final['summary'],tasks=[],contributions=[],story=d['story'],story_reviewed=True,review=final))
        assert response.status_code==201,response.text
        created=response.json()['created_people'];assert created['one']!=created['two']
        a=again.get('/api/people/'+created['one']+'/overview').json()['facts'];b=again.get('/api/people/'+created['two']+'/overview').json()['facts']
        assert a['interests'][0]['value']=='登山' and not a['food']
        assert b['food'][0]['value']=='清淡' and not b['interests']


def test_review_invalid_targets_and_duplicate_refs_do_not_create_drafts(client):
    _,g=onboard(client);register(client);raw='原始紀錄。';r=review(raw)
    response=client.post('/api/experiences/drafts',json={'raw_text':raw,'occurred_at':'2026-10-27T00:00:00Z','contributions':[],'review':r})
    assert response.status_code==422
    r['person_candidates'].append(r['person_candidates'][0].copy())
    response=client.post('/api/experiences/drafts',json={'raw_text':raw,'occurred_at':'2026-10-27T00:00:00Z','contributions':[],'review':r})
    assert response.status_code==422 and not client.get('/api/state').json()['drafts']


def test_confirmed_mention_can_source_explicit_fact_without_becoming_interaction(client):
    _,g=onboard(client);register(client);raw='今天提到小明。'
    r={'summary':'提到人物的真實記錄','summary_source_sha256':sha(raw),'tasks':[],'person_candidates':[{'candidate_ref':'mention-fact','target':{'client_ref':'mentioned'},'dimension':'food','value':'清淡','source_kind':'manual','evidence_type':'stated_by_person','selected':True}]}
    d=draft(client,g,raw_text=raw,contributions=[],story={'pending_people':[{'client_ref':'mentioned','name':'小明','relation':'mention','start':raw.index('小明')}]},review=r)
    payload=confirm_payload(d,summary=r['summary'],tasks=[],contributions=[],story=d['story'],story_reviewed=True,use_saved_review=True)
    response=client.post('/api/drafts/'+d['id']+'/confirm',json=payload);assert response.status_code==201,response.text
    pid=response.json()['created_people']['mentioned'];overview=client.get('/api/people/'+pid+'/overview').json()
    assert overview['facts']['food'][0]['value']=='清淡'
    assert overview['stats']['interactions']==0
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=payload).json()==response.json()
    # 人物事實可引用已人工配對的提及，不把提及變成其他API的參與/關係來源。
    with client.app.state.service.db.connect() as c:
        assert not c.execute('SELECT * FROM experience_participants WHERE person_id=?',(pid,)).fetchall()
        assert not c.execute('SELECT * FROM interaction_people WHERE person_id=?',(pid,)).fetchall()
        owner=client.get('/api/auth/me').json()['owner_id']
        with pytest.raises(DomainError) as rejected:
            client.app.state.service._source_experience(c,owner,response.json()['experience_id'],[pid])
        assert rejected.value.code=='unrelated_source'
