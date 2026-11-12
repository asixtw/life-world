"""前端只是防呆；繞過前端仍由DTO/Confirm交易拒絕非法正式寫入。"""
import pytest
from conftest import onboard,register,draft,confirm_payload

@pytest.mark.parametrize('month,day,year',[(0,1,None),(13,1,None),(1,0,None),(1,32,None),(1,1,0)])
def test_draft_dto_still_rejects_out_of_range_birthday(client,month,day,year):
 _,g=onboard(client);register(client);p=client.post('/api/people',json={'name':'測試人物'}).json()
 before=client.get('/api/state').json()
 r=client.post('/api/experiences/drafts',json={'raw_text':'手動資訊','occurred_at':'2026-10-27T00:00:00Z','contributions':[],'review':{'birthday_candidates':[{'candidate_ref':'b','target':{'person_id':p['id']},'value':{'birth_month':month,'birth_day':day,'birth_year':year},'source_kind':'manual'}]}})
 assert r.status_code==422
 after=client.get('/api/state').json();assert after['drafts']==before['drafts'] and after['experiences']==before['experiences'] and after['rewards']==before['rewards']

@pytest.mark.parametrize('month,day,year,valid',[(4,31,None,False),(2,29,2023,False),(2,29,None,True),(4,30,None,True)])
def test_final_confirm_calendar_rechecked_and_atomic(client,month,day,year,valid):
 _,g=onboard(client);register(client);p=client.post('/api/people',json={'name':'測試人物'}).json()
 # 舊草稿契約允許保留未完成/待修正日期；正式確認必須走完整BirthdayValue驗證。
 d=draft(client,g,contributions=[],story={'participants':[{'person_id':p['id'],'interacted':False}]},review={'birthday_candidates':[{'candidate_ref':'b','target':{'person_id':p['id']},'value':{'birth_month':month,'birth_day':day,'birth_year':year},'source_kind':'manual','selected':True,'needs_review':False}]})
 r=client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d,use_saved_review=True,story=d['story'],story_reviewed=True,contributions=[],tasks=[]))
 assert r.status_code==(201 if valid else 409),r.text
 if not valid:assert r.json()['error']['code']=='candidate_review_required'
 state=client.get('/api/state').json();assert len(state['experiences'])==len(state['rewards']['events'])==(1 if valid else 0)
 birthday=client.get('/api/people/'+p['id']+'/details').json()['birthday']
 if valid:assert birthday['birth_year']==year and birthday['birth_month']==month and birthday['birth_day']==day
 else:assert birthday is None and client.get('/api/drafts/'+d['id']).json()['status']=='draft'
