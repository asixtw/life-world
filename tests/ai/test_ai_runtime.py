"""隔離資料＋傳輸替身只驗證契約，絕不代表真實模型 PASS。"""
import json,os
from datetime import datetime,timezone
import pytest
from app.ai_runtime import AISettings,AIRuntime
from app.main import create_app
from app.ai_provider_base import ModelResult
from conftest import onboard,register,draft,confirm_payload
from fastapi.testclient import TestClient

class Provider:
    name='test-transport'
    model='synthetic-only'
    def __init__(self,text):self.text=text;self.calls=[]
    def generate(self,prompt,max_output_tokens):self.calls.append(prompt);return ModelResult(self.text,3,4,None,None)

@pytest.fixture
def prepared(tmp_path):
    # 只重用既有marker合成PG，禁止bootstrap或指向雲端資料庫。
    database=None
    if os.environ.get('LIFEWORLD_TEST_BACKEND')=='postgresql':
        from pg_support import database as pg_database
        database=pg_database()
    app=create_app(tmp_path,database=database,clock=lambda:datetime(2026,11,7,7,tzinfo=timezone.utc))
    with TestClient(app) as client:
        # Existing helper uses October schedules, so use matching synthetic clock.
        app.state.service.clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc)
        me,g=onboard(client);register(client)
        provider=Provider(json.dumps({'summary':'合成整理','tasks':['合成後續']}))
        settings=AISettings(provider='gemini',model='gemini-synthetic',approved=True,max_owner_daily_calls=2,max_global_calls=3,reservation_microusd=100,max_budget_microusd=300)
        runtime=AIRuntime(app.state.service,settings,provider=provider)
        yield app,client,me,g,runtime,provider

def test_disabled_never_constructs_or_calls_provider(prepared):
    app,c,me,g,_,p=prepared
    runtime=AIRuntime(app.state.service,AISettings(),provider=p)
    with pytest.raises(Exception) as exc:runtime.generate(me['owner_id'],'experience',{'raw_text':'合成'})
    assert exc.value.code=='ai_not_configured' and p.calls==[]

def test_experience_candidate_does_not_write_facts_or_rewards(prepared):
    app,c,me,g,runtime,p=prepared
    before=c.get('/api/state').json()
    result=runtime.generate(me['owner_id'],'experience',{'raw_text':'合成原文'})
    assert result['summary']=='合成整理' and result['tasks']==['合成後續'] and result['applied'] is False
    after=c.get('/api/state').json();assert before==after
    assert p.calls[0]['json_output'] is True

def test_durable_budget_counts_failed_attempts_and_refuses_extra_call(prepared):
    app,c,me,g,runtime,p=prepared
    p.text='invalid JSON'
    for _ in range(2):
        with pytest.raises(Exception):runtime.generate(me['owner_id'],'experience',{'raw_text':'合成'})
    with pytest.raises(Exception) as exc:runtime.generate(me['owner_id'],'experience',{'raw_text':'合成'})
    assert exc.value.code=='ai_quota_reached' and len(p.calls)==2

def test_unknown_fields_or_model_claims_rejected(prepared):
    app,c,me,g,runtime,p=prepared
    p.text=json.dumps({'summary':'合成','tasks':[],'points_awarded':100})
    with pytest.raises(Exception) as exc:runtime.generate(me['owner_id'],'experience',{'raw_text':'合成'})
    assert exc.value.code=='ai_invalid_candidate'

def test_guest_cannot_consume_ai_budget(tmp_path):
    app=create_app(tmp_path,clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))
    with TestClient(app) as c:
        me,_=onboard(c);p=Provider('{}')
        runtime=AIRuntime(app.state.service,AISettings(),provider=p)
        with pytest.raises(Exception) as exc:runtime.generate(me['owner_id'],'experience',{'raw_text':'x'})
        assert exc.value.status==403 and p.calls==[]


def test_http_candidate_edit_confirm_and_followup_idempotence(prepared):
    app,c,me,g,runtime,p=prepared;app.state.ai_runtime=runtime
    d=draft(c,g)
    candidate=c.post('/api/drafts/'+d['id']+'/suggest');assert candidate.status_code==200,candidate.text
    assert c.get('/api/state').json()['experiences']==[]
    body=confirm_payload(d);body['summary']='使用者編輯後的合成摘要';body['tasks']=[]
    confirmed=c.post('/api/drafts/'+d['id']+'/confirm',json=body);assert confirmed.status_code==201
    xid=confirmed.json()['experience_id'];before=c.get('/api/state').json()['rewards']
    suggestion=c.post('/api/experiences/'+xid+'/task-suggestions',json={'consent':True});assert suggestion.status_code==200
    selected={'request_id':'synthetic-task-confirm','tasks':['使用者改寫的後續任務'],'confirmed':True}
    first=c.post('/api/experiences/'+xid+'/tasks',json=selected);assert first.status_code==201
    repeat=c.post('/api/experiences/'+xid+'/tasks',json=selected);assert repeat.json()==first.json()
    assert first.json()['points_awarded']==0
    state=c.get('/api/state').json();assert state['rewards']==before and len(state['tasks'])==1 and state['experiences'][0]['summary']==body['summary']
    c.headers['X-CSRF-Token']='wrong';assert c.post('/api/experiences/'+xid+'/tasks',json=selected).status_code==403


def test_simulation_uses_confirmed_sources_and_never_writes_facts(prepared):
    app,c,me,g,runtime,p=prepared;app.state.ai_runtime=runtime
    person=c.post('/api/people',json={'name':'合成人物','role':'合成角色'});assert person.status_code==201
    person_id=person.json()['id'];d=draft(c,g);confirmed=c.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d));assert confirmed.status_code==201
    with app.state.service.db.connect(write=True) as db:
        db.execute("INSERT INTO person_facts VALUES (?,?,?,?,?,?,?,'confirmed',NULL,1,?)",('synthetic-fact',me['owner_id'],person_id,'skills','合成技能','合成技能','人工確認的合成內容',app.state.service.now().isoformat()))
        db.execute("INSERT INTO fact_sources VALUES (?,?,?,NULL)",('synthetic-fact',confirmed.json()['experience_id'],'stated_by_person'))
    p.text=json.dumps({'utterance':'合成模擬發言，不代表真人反應'})
    result=c.post('/api/people/'+person_id+'/simulation',json={'consent':True,'fact_ids':['synthetic-fact'],'message':'合成演練問題'})
    assert result.status_code==200 and result.json()['simulation'] is True and result.json()['applied'] is False
    assert p.calls[-1]['case']['confirmed_facts'][0]['value']=='合成技能'
    with app.state.service.db.connect() as db:
        assert db.execute('SELECT count(*) FROM person_facts').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM notes').fetchone()[0]==0
    rejected=c.post('/api/people/'+person_id+'/simulation',json={'consent':True,'fact_ids':['foreign-or-revoked'],'message':'合成'})
    assert rejected.status_code==422 and len(p.calls)==1


def test_multimodal_adapter_uses_inline_data_without_key_in_url():
    from app.ai_gemini import GeminiProvider
    seen=[]
    def transport(url,body,headers,timeout):
        seen.append((url,json.loads(body)))
        return {'candidates':[{'content':{'parts':[{'text':'{"text":"合成名片待校對"}'}]},'finishReason':'STOP'}]}
    p=GeminiProvider('gemini-synthetic',key_supplier=lambda:'synthetic-not-a-real-key',transport=transport)
    p.generate({'system':'合成測試','case':{},'json_output':True,'inline_media':{'mime_type':'image/png','data':'c3ludGhldGlj'}},100)
    assert seen[0][1]['contents'][0]['parts'][1]['inlineData']['mimeType']=='image/png'
    assert seen[0][1]['generationConfig']['responseMimeType']=='application/json'
    assert 'synthetic-not-a-real-key' not in seen[0][0]


def test_usage_receipt_records_only_bounded_metadata(prepared):
    """留存供應商回報用量，不把未知費用當零，也不保存來源或輸出。"""
    app,c,me,g,runtime,p=prepared
    result=runtime.generate(me['owner_id'],'experience',{'raw_text':'不應留存的合成來源'})
    with app.state.service.db.connect() as db:
        row=db.execute("SELECT response FROM requests WHERE operation='ai_result_v1' AND request_id=?",(result['request_id'],)).fetchone()
    receipt=json.loads(row['response'])
    assert receipt['input_tokens']==3 and receipt['output_tokens']==4
    assert receipt['cost_microusd'] is None
    assert set(receipt)=={'created_at','status','cost_microusd','input_tokens','output_tokens'}
    assert '不應留存' not in row['response'] and '合成整理' not in row['response']


def test_invalid_ai_result_preserves_manual_confirm_and_readback(prepared):
    """模型失敗後仍能人工確認；候選/失敗本身不改進度或獎勵。"""
    app,c,me,g,runtime,p=prepared;app.state.ai_runtime=runtime
    d=draft(c,g);before=c.get('/api/state').json();p.text='not JSON'
    failed=c.post('/api/drafts/'+d['id']+'/suggest')
    assert failed.status_code==502 and failed.json()['error']['code']=='ai_invalid_candidate'
    assert c.get('/api/state').json()==before and len(p.calls)==1
    payload=confirm_payload(d,summary='人工核對的合成摘要',tasks=[])
    first=c.post('/api/drafts/'+d['id']+'/confirm',json=payload)
    assert first.status_code==201,first.text
    repeat=c.post('/api/drafts/'+d['id']+'/confirm',json=payload)
    assert repeat.json()==first.json()
    after=c.get('/api/state').json()
    assert len(after['experiences'])==1 and after['experiences'][0]['summary']==payload['summary']
    assert len(p.calls)==1
    # 重新組裝服務，從同一持久化測試資料庫讀回，並非前端快照。
    from app.service import LifeWorld
    restored=LifeWorld(app.state.service.db,app.state.service.policy,clock=app.state.service.clock)
    assert restored.state(me['owner_id'])['experiences'][0]['summary']==payload['summary']


@pytest.mark.parametrize('limiting_setting', ['max_global_calls', 'max_budget_microusd'])
def test_global_quota_recovers_after_rolling_day_and_survives_runtime_restart(prepared, limiting_setting):
    """公開服務不得因歷史試呼叫永久耗盡；重啟仍保留窗內限制。"""
    from dataclasses import replace
    from datetime import timedelta
    app,c,me,g,runtime,p=prepared
    limits={'max_owner_daily_calls':100,'max_global_calls':100,'max_budget_microusd':10000}
    limits[limiting_setting]=1 if limiting_setting=='max_global_calls' else 100
    runtime.settings=replace(runtime.settings,**limits)
    runtime.generate(me['owner_id'],'experience',{'raw_text':'第一天合成'})
    restarted=AIRuntime(app.state.service,runtime.settings,provider=p)
    with pytest.raises(Exception) as exc:
        restarted.generate(me['owner_id'],'experience',{'raw_text':'同窗不重試'})
    assert exc.value.code=='ai_quota_reached' and len(p.calls)==1
    later=app.state.service.now()+timedelta(days=1)
    app.state.service.clock=lambda:later
    result=restarted.generate(me['owner_id'],'experience',{'raw_text':'第二天合成'})
    assert result['applied'] is False and len(p.calls)==2
    # 恢復額度不刪歷史收據，也不能在同一新窗繼續超額。
    with app.state.service.db.connect() as db:
        assert db.execute("SELECT count(*) AS n FROM requests WHERE operation='ai_attempt_v1'").fetchone()['n']==2
    with pytest.raises(Exception) as exc:
        restarted.generate(me['owner_id'],'experience',{'raw_text':'第二天超額'})
    assert exc.value.code=='ai_quota_reached' and len(p.calls)==2


def test_concurrent_reservations_do_not_overrun_global_daily_cap(prepared):
    """多請求必須先在同一DB鎖內預留，不能競爭穿過全域上限。"""
    from concurrent.futures import ThreadPoolExecutor
    from dataclasses import replace
    app,c,me,g,runtime,p=prepared
    runtime.settings=replace(runtime.settings,max_owner_daily_calls=100,max_global_calls=3,max_budget_microusd=10000)
    def attempt(i):
        try:
            runtime.generate(me['owner_id'],'experience',{'raw_text':f'合成並發{i}'})
            return 'candidate'
        except Exception as exc:
            return getattr(exc,'code',type(exc).__name__)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(attempt,range(12)))
    assert results.count('candidate')==3 and results.count('ai_quota_reached')==9
    assert len(p.calls)==3
    with app.state.service.db.connect() as db:
        assert db.execute("SELECT count(*) AS n FROM requests WHERE operation='ai_attempt_v1'").fetchone()['n']==3
