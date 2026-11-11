"""AI 路由只建立候選；正式任務沿用既有 tasks/requests，零獎勵副作用。"""
from typing import Literal
from uuid import uuid4
from fastapi import Request
from pydantic import BaseModel,ConfigDict,Field,field_validator
from .ai_runtime import AIRuntime
from .errors import require

class ConfirmedInput(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    request_id:str|None=Field(default=None,min_length=1,max_length=128,pattern=r'^[A-Za-z0-9_.:-]+$')
    consent:Literal[True]
    @field_validator('consent',mode='before')
    @classmethod
    def explicit_consent(cls,value):
        if value is not True:raise ValueError('請明確同意傳送所選來源給模型')
        return value

class DialogueTurn(BaseModel):
    """歷史只接受有限對話內容，不能注入system角色或任意技術欄位。"""
    model_config=ConfigDict(extra='forbid',strict=True)
    speaker:Literal['user','simulation']
    text:str=Field(min_length=1,max_length=1000)

class SimulationInput(ConfirmedInput):
    fact_ids:list[str]=Field(min_length=1,max_length=10)
    message:str=Field(min_length=1,max_length=2000)
    history:list[DialogueTurn]=Field(default_factory=list,max_length=6)

class TasksConfirm(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    request_id:str=Field(min_length=1,max_length=128)
    tasks:list[str]=Field(min_length=1,max_length=20)
    confirmed:Literal[True]
    @field_validator('confirmed',mode='before')
    @classmethod
    def explicit_confirm(cls,value):
        if value is not True:raise ValueError('請明確確認所選任務')
        return value
    @field_validator('tasks')
    @classmethod
    def bounded_tasks(cls,values):
        values=[v.strip() for v in values]
        if any(not v or len(v)>300 for v in values):raise ValueError('任務需有內容且不超過300字')
        return list(dict.fromkeys(values))


def install(app):
    """不啟用 Provider、不讀 key；只有 backend 環境批准才組裝真實 Adapter。"""
    service=app.state.service;app.state.ai_runtime=AIRuntime(service)
    def owner(request):
        return service.session(request.cookies.get('lw_session'),request.headers.get('X-CSRF-Token'),True)[0]['id']
    def experience(who,experience_id):
        app.state.ai_runtime.authorize(who)
        with service.db.connect() as c:
            row=c.execute('SELECT id,summary,occurred_at FROM experiences WHERE id=? AND owner_id=?',(experience_id,who)).fetchone()
            require(row is not None,404,'not_found','找不到可存取的經歷。')
            return dict(row)

    @app.get('/api/ai/usage',tags=['AI drafts'])
    def ai_usage(request:Request):
        who=service.session(request.cookies.get('lw_session'))[0]['id']
        return app.state.ai_runtime.usage(who)

    @app.post('/api/experiences/{experience_id}/task-suggestions',tags=['AI drafts'])
    def task_suggestions(experience_id:str,request:Request,data:ConfirmedInput):
        who=owner(request);source=experience(who,experience_id)
        return app.state.ai_runtime.generate(who,'tasks',{'confirmed_experience':source},request_id=data.request_id)

    @app.post('/api/experiences/{experience_id}/tasks',status_code=201,tags=['AI drafts'])
    def confirm_tasks(experience_id:str,request:Request,data:TasksConfirm):
        who=owner(request);experience(who,experience_id)
        with service.db.connect(write=True,owner=who) as c:
            service._people_user(c,who)
            require(c.execute('SELECT id FROM experiences WHERE id=? AND owner_id=?',(experience_id,who)).fetchone() is not None,404,'not_found','找不到可存取的經歷。')
            payload={'experience_id':experience_id,'tasks':data.tasks}
            cached,fingerprint=service._cached(c,who,'confirmed_followup_tasks',data.request_id,payload)
            if cached:return cached
            tasks=[]
            for title in data.tasks:
                identifier=str(uuid4());c.execute('INSERT INTO tasks(id,owner_id,experience_id,title,done) VALUES (?,?,?,?,FALSE)',(identifier,who,experience_id,title));tasks.append({'id':identifier,'title':title,'done':False})
            result={'tasks':tasks,'points_awarded':0,'confirmed':True}
            service._remember(c,who,'confirmed_followup_tasks',data.request_id,fingerprint,result)
            return result

    @app.post('/api/people/{person_id}/simulation',tags=['AI drafts'])
    def simulation(person_id:str,request:Request,data:SimulationInput):
        who=owner(request);app.state.ai_runtime.authorize(who)
        overview=service.person_overview(who,person_id)
        available={fact['id']:fact for group in overview['facts'].values() for fact in group if fact['status']=='confirmed' and fact['sources']}
        require(all(f in available for f in data.fact_ids),422,'confirmed_sources_required','只可使用本人已確認且仍有來源的人物資訊。')
        facts=[{'fact_id':f,'value':available[f]['value'],'source_experience_ids':[s['id'] for s in available[f]['sources']]} for f in dict.fromkeys(data.fact_ids)]
        from .relationship_engine import build_context
        source_ids=sorted({ref for fact in facts for ref in fact['source_experience_ids']})
        # 來源摘要必須再次限定Owner，內部提示每次重算，撤回／刪除即不沿用。
        with service.db.connect() as db:
            records=[dict(row) for ref in source_ids for row in db.execute('SELECT id,summary,occurred_at FROM experiences WHERE id=? AND owner_id=?',(ref,who)).fetchall()]
        context=build_context(facts,records,data.message,service.now().isoformat())
        result=app.state.ai_runtime.generate(who,'simulation',{'person_id':person_id,'confirmed_facts':facts,'internal_context':context,'behavior':context['behavior'],'history':[turn.model_dump() for turn in data.history],'message':data.message},request_id=data.request_id)
        # 一般人物卡／對話UI不暴露內部雙端標籤；只回可解釋的來源與有限行為。
        return {**result,'simulation':True,'behavior':context['behavior'],'behavior_source':'rules','source_experience_ids':source_ids,'uncertainty':'simulation_not_prediction','notice':result['notice']+' 私人模擬，不是對真人反應的預測；不寫入人物事實。'}
