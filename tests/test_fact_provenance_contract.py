"""F5獨立驗證：草稿已有來源持久化；正式來源投影仍為待審模型缺口，不冒稱已完成。"""
import hashlib
import pytest
from fastapi.testclient import TestClient
from conftest import onboard,register,draft,confirm_payload


def prepared_fact(client):
    _,goal=onboard(client);register(client)
    p=client.post('/api/people',json={'name':'合成人物'}).json()
    raw='合成人物說喜歡登山。';quote='合成人物說喜歡登山'
    item={'candidate_ref':'fact-raw','target':{'person_id':p['id']},'expected_person_revision':p['revision'],'dimension':'interests','value':'登山','evidence_type':'stated_by_person','source_kind':'raw','source_sha256':hashlib.sha256(raw.encode()).hexdigest(),'quote':quote,'selected':True}
    d=draft(client,goal,raw_text=raw,contributions=[],story={'participants':[{'person_id':p['id'],'interacted':True}]},review={'person_candidates':[item]})
    return p,d,item


def test_draft_provenance_survives_new_session_and_owner_boundary(client,app):
    p,d,item=prepared_fact(client)
    with TestClient(app) as other:
        login=other.post('/api/auth/login',json={'username':'lumi_user','password':'a-good-password-2026'});assert login.status_code==200
        read=other.get('/api/drafts/'+d['id']);assert read.status_code==200
        value=read.json()['review']['person_candidates'][0]
        for key in ('target','source_kind','source_sha256','quote','evidence_type'):assert ({k:v for k,v in value[key].items() if v is not None} if key=='target' else value[key])==item[key]
    with TestClient(app) as unrelated:
        onboard(unrelated);register(unrelated,'provenance_other')
        assert unrelated.get('/api/drafts/'+d['id']).status_code==404
    assert client.get('/api/state').json()['experiences']==[]


@pytest.mark.xfail(strict=True,reason='F5正式fact_sources缺source_kind/source_revision/quote；僅契約審查，本輪不執行Schema變更')
def test_formal_fact_provenance_requires_reviewed_schema_contract(client):
    p,d,item=prepared_fact(client)
    done=client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d,summary='合成摘要',contributions=[],tasks=[],story=d['story'],story_reviewed=True,use_saved_review=True))
    assert done.status_code==201,done.text
    # 直接使用服務公開的來源DTO，不能以仍存在的草稿冒稱正式fact來源契約。
    service=client.app.state.service
    view=service.person_overview(d['owner_id'],p['id'])
    source=view['facts']['interests'][0]['sources'][0]
    assert source['source_kind']=='raw' and source['source_revision']==d['revision'] and source['quote']==item['quote']


def test_manual_fact_still_requires_confirmed_experience(client):
    """manual是輸入方式；本輪不開無經歷來源正式fact，生日011規則不外推。"""
    p,d,item=prepared_fact(client)
    before=client.get('/api/state').json()
    r=client.post('/api/people/'+p['id']+'/facts',json={'request_id':'without-experience','dimension':'interests','value':'登山','evidence_type':'stated_by_person','source_experience_ids':[],'confirmed':True})
    assert r.status_code==422
    after=client.get('/api/state').json()
    assert after['experiences']==before['experiences'] and after['rewards']==before['rewards']
    assert client.app.state.service.person_overview(d['owner_id'],p['id'])['facts']['interests']==[]


def test_normal_upsert_must_not_restore_revoked_fact_source(client):
    """保留可重現阻擋，不以新增契約文件宣稱現碼狀態機已修復。"""
    p,d,item=prepared_fact(client)
    done=client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d,summary='合成摘要',contributions=[],tasks=[],story=d['story'],story_reviewed=True,use_saved_review=True))
    assert done.status_code==201,done.text
    service=client.app.state.service
    fact=service.person_overview(d['owner_id'],p['id'])['facts']['interests'][0]
    r=client.post('/api/people/'+p['id']+'/facts/'+fact['id']+'/sources/revoke',json={'expected_revision':fact['revision'],'experience_id':done.json()['experience_id']})
    assert r.status_code==200,r.text
    assert service.person_overview(d['owner_id'],p['id'])['facts']['interests']==[]
    # 不送restore動作，僅重新create相同fact；應拒絕或維持withdrawn，不能偷偷恢復。
    r=client.post('/api/people/'+p['id']+'/facts',json={'request_id':'ordinary-upsert','dimension':'interests','value':'登山','evidence_type':'stated_by_person','source_experience_ids':[done.json()['experience_id']],'confirmed':True})
    with service.db.connect() as c:
        row=c.execute('SELECT revoked_at FROM fact_sources WHERE fact_id=? AND experience_id=?',(fact['id'],done.json()['experience_id'])).fetchone()
    assert r.status_code==409 and r.json()['error']['code']=='source_restore_required',r.text
    assert row['revoked_at'] is not None,'一般upsert清空revoked_at，繞過明確恢復'
