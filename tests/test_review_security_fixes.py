"""審查專用合成SQLite探針；斷言期望安全行為，失敗即重現缺陷。"""
from test_ai_runtime import prepared
from conftest import onboard,register,draft,confirm_payload
from dataclasses import replace
import pytest

def story_source(c):
 _,g=onboard(c);register(c)
 a=c.post('/api/people',json={'name':'人物甲'}).json()['id']
 b=c.post('/api/people',json={'name':'人物乙'}).json()['id']
 d=draft(c,g,raw_text='人物甲說生日是四月十二日。',contributions=[],story={'participants':[{'person_id':a,'interacted':True}]})
 r=c.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d,contributions=[],story=d['story'],story_reviewed=True))
 assert r.status_code==201,r.text
 return a,b,r.json()['experience_id']

def write_birthday(c,p,x):
 return c.patch('/api/people/'+p+'/basic-details',json={'request_id':'birthday','expected_revision':0,'confirmed':True,'value':{'birth_month':4,'birth_day':12},'source':{'source_kind':'raw','source_experience_id':x,'evidence_type':'stated_by_person','quote':'生日是四月十二日'}})

def test_unrelated_person_source_rejected(client):
 a,b,x=story_source(client)
 r=write_birthday(client,b,x)
 assert r.status_code==422, f'unrelated source accepted: HTTP {r.status_code}'

def test_withdrawn_story_invalidates_basic_source(client):
 a,b,x=story_source(client)
 assert write_birthday(client,a,x).status_code==200
 r=client.post('/api/connections/stories/'+x+'/availability',json={'request_id':'withdraw','expected_revision':1,'available':False})
 assert r.status_code==200,r.text
 d=client.get('/api/people/'+a+'/details').json()
 assert d['birthday']['source_status']!='active', 'withdrawn story still exported as active birthday source'

def test_media_respects_owner_and_global_call_quota(prepared):
 app,c,me,g,r,p=prepared
 r.settings=replace(r.settings,max_owner_daily_calls=1,max_global_calls=1,max_budget_microusd=10000)
 p.text='{"text":"synthetic"}'
 r.generate(me['owner_id'],'media',{'kind':'image'})
 with pytest.raises(Exception) as e:r.generate(me['owner_id'],'media',{'kind':'image'})
 assert e.value.code=='ai_quota_reached'

def test_simulation_does_not_send_withdrawn_story(prepared):
 app,c,me,g,r,p=prepared;app.state.ai_runtime=r
 a=c.post('/api/people',json={'name':'合成人物'}).json()['id']
 d=draft(c,g,raw_text='合成人物說喜歡登山。',contributions=[],story={'participants':[{'person_id':a,'interacted':True}]})
 body=confirm_payload(d,contributions=[],story=d['story'],story_reviewed=True,person_id=a,person_updates=[{'dimension':'interests','value':'登山','evidence_type':'stated_by_person','selected':True}])
 done=c.post('/api/drafts/'+d['id']+'/confirm',json=body);assert done.status_code==201,done.text
 xid=done.json()['experience_id']
 overview=app.state.service.person_overview(me['owner_id'],a)
 fid=overview['facts']['interests'][0]['id']
 assert c.post('/api/connections/stories/'+xid+'/availability',json={'request_id':'withdraw','expected_revision':1,'available':False}).status_code==200
 p.text='{"utterance":"synthetic"}'
 out=c.post('/api/people/'+a+'/simulation',json={'consent':True,'fact_ids':[fid],'message':'合成問題'})
 assert out.status_code==422 and not p.calls, f'withdrawn source sent: HTTP {out.status_code}, provider calls={len(p.calls)}'


def test_all_basic_source_writes_roll_back_and_confirmed_mentions_remain_allowed(client):
    """來源錯掛不得留下生日/任職/History；人工提及合法但不算互動。"""
    a,b,x=story_source(client)
    before=client.get('/api/people/'+b+'/details').json()
    source={'source_kind':'raw','source_experience_id':x,'evidence_type':'stated_by_person','quote':'生日是四月十二日'}
    assert write_birthday(client,b,x).status_code==422
    result=client.post('/api/people/'+b+'/employments',json={'request_id':'bad-job','confirmed':True,'value':{'company_name':'甲的公司'},'source':source})
    assert result.status_code==422
    assert client.get('/api/people/'+b+'/details').json()==before
    good=client.post('/api/people/'+b+'/employments',json={'request_id':'manual-job','confirmed':True,'value':{'company_name':'乙的公司'},'source':{'source_kind':'manual'}}).json()
    before=client.get('/api/people/'+b+'/details').json()
    result=client.patch('/api/people/'+b+'/employments/'+good['id'],json={'request_id':'wrong-source-edit','confirmed':True,'expected_revision':1,'value':{'job_title':'不應保存'},'source':source})
    assert result.status_code==422 and client.get('/api/people/'+b+'/details').json()==before
    # 新來源只提及乙；允許保存明確核對的資料，不能新增互動事件。
    response=client.post('/api/experiences/drafts',json={'raw_text':'人物乙生日是四月十二日。','occurred_at':'2026-10-27T00:10:00+08:00','contributions':[],'story':{'mentions':[{'person_id':b,'name':'人物乙','start':0,'end':3}]}})
    assert response.status_code==201,response.text
    d=response.json()
    r=client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d,request_id='mention-confirm',story=d['story'],story_reviewed=True))
    assert r.status_code==201,r.text
    result=write_birthday(client,b,r.json()['experience_id']);assert result.status_code==200,result.text
    assert client.get('/api/people/'+b+'/details').json()['person']['stats']['interactions']==0


def test_story_source_projection_preserves_history_and_manual_withdrawal(client):
    """故事用途撤回只影響有效投影，恢復不得復活已人工撤回的人物來源。"""
    a,b,x=story_source(client)
    assert write_birthday(client,a,x).status_code==200
    job=client.post('/api/people/'+a+'/employments',json={'request_id':'raw-job','confirmed':True,'value':{'company_name':'合成公司'},'source':{'source_kind':'raw','source_experience_id':x,'evidence_type':'stated_by_person','quote':'人物甲'}})
    assert job.status_code==201,job.text
    before=client.get('/api/people/'+a+'/details').json()
    r=client.post('/api/connections/stories/'+x+'/availability',json={'request_id':'hide','expected_revision':1,'available':False});assert r.status_code==200
    hidden=client.get('/api/people/'+a+'/details').json()
    assert hidden['birthday']['source_status']=='withdrawn' and hidden['birthday']['recorded_source_status']=='active'
    assert hidden['employments'][0]['source_available'] is False
    assert hidden['birthday_history']==before['birthday_history'] and hidden['employment_history']==before['employment_history']
    assert hidden['birthday']['revision']==before['birthday']['revision']
    # 明確撤回生日來源，之後恢復故事不會復活這筆人物來源。
    r=client.post('/api/people/'+a+'/basic-details/source-withdrawal',json={'request_id':'withdraw-birthday','expected_revision':1,'confirmed':True});assert r.status_code==200
    r=client.post('/api/connections/stories/'+x+'/availability',json={'request_id':'show','expected_revision':2,'available':True});assert r.status_code==200
    shown=client.get('/api/people/'+a+'/details').json()
    assert shown['birthday']['source_status']=='withdrawn'
    assert shown['employments'][0]['source_status']=='active'
    assert shown['employment_history']==before['employment_history']
