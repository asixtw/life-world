"""審查專用合成SQLite探針；斷言期望安全行為，失敗即重現缺陷。"""
pytest_plugins=['conftest','test_ai_runtime']
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
