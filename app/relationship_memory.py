"""有限來源特徵的長期保存；不猜敏感人格、不把模擬台詞納入來源或訓練集。"""
import json
from .errors import require


class FeatureStore:
    """同一Owner的設定及來源快照；每次使用前重驗來源，撤回後覆寫失效值。"""
    def __init__(self,service):self.service=service;self.db=service.db

    def preferences(self,owner):
        with self.db.connect() as c:
            self.service._onboarded(c,owner)
            row=c.execute('SELECT enabled,preferences,revision FROM relationship_memory_preferences WHERE owner_id=?',(owner,)).fetchone()
        return {'enabled':bool(row['enabled']) if row else False,'preferences':json.loads(row['preferences']) if row else {},'revision':row['revision'] if row else 0,'training_opt_in':False}

    def configure(self,owner,enabled,preferences):
        require(set(preferences)<= {'summary_style'},422,'invalid_preference','目前只接受摘要詳略偏好。')
        require(preferences.get('summary_style','concise') in ('concise','detailed'),422,'invalid_preference','請選擇簡潔或詳細摘要。')
        with self.db.connect(write=True,owner=owner) as c:
            self.service._onboarded(c,owner)
            c.execute('INSERT INTO relationship_memory_preferences(owner_id,enabled,preferences,revision) VALUES (?,?,?,1) ON CONFLICT(owner_id) DO UPDATE SET enabled=excluded.enabled,preferences=excluded.preferences,revision=relationship_memory_preferences.revision+1',(owner,bool(enabled),json.dumps(preferences)))
            if not enabled:c.execute('DELETE FROM relationship_features WHERE owner_id=?',(owner,))
        return self.preferences(owner)

    def erase(self,owner):
        # 使用者刪除衍生資料時實際刪除；不刪正式經歷／人物來源。
        self.configure(owner,False,{})
        return {'deleted':True,'enabled':False,'training_opt_in':False}

    def context(self,owner,person=None):
        pref=self.preferences(owner)
        if not pref['enabled']:return {'enabled':False,'features':[],'training_opt_in':False}
        with self.db.connect() as c:
            self.service._onboarded(c,owner)
            records=[dict(r) for r in c.execute('SELECT id,summary,occurred_at FROM experiences WHERE owner_id=? ORDER BY occurred_at DESC,id DESC LIMIT 100',(owner,)).fetchall()]
        facts=[]
        if person:
            overview=self.service.person_overview(owner,person)
            facts=[{'fact_id':f['id'],'value':f['value'],'source_experience_ids':[s['id'] for s in f['sources']]} for group in overview['facts'].values() for f in group if f['status']=='confirmed' and f['sources']]
        # 四類都是有限情境，禁止把觀察議題當成絕對人格；矛盾資訊不選邊。
        refs=sorted({r['id'] for r in records});candidate=[]
        def add(kind,subject,key,value,sources,status):
            candidate.append({'subject_type':kind,'subject_id':subject,'feature_key':key,'value':value,'source_refs':sources,'context_scope':'owner_confirmed_records','epistemic_status':status,'model_version':'relationship-rules-v2','revocation_state':'active'})
        if pref['preferences']:add('user',owner,'explicit_preferences',pref['preferences'],['user:explicit_preference'],'explicit_user_preference')
        from .relationship_engine import build_context
        derived=build_context(facts,records,'',self.service.now().isoformat())
        for f in derived['user_features']:add('user',owner,f['tag'],{'topic':f['tag'].split('.')[-1]},f['source_refs'],'recorded_context_not_personality')
        if person:
            for f in facts:add('person',person,'fact:'+f['fact_id'],{'reported':f['value']},f['source_experience_ids'],'user_confirmed_report_not_external_truth')
            valid=sorted({s for f in facts for s in f['source_experience_ids']})
            if valid:add('relationship',person,'confirmed_interaction',{'source_count':len(valid)},valid,'limited_observation')
        if refs:add('context',person or owner,'source_window',{'latest_recorded_at':max(r['occurred_at'] for r in records),'uncertainty':'incomplete_user_records'},refs,'recorded_time_only')
        with self.db.connect(write=True,owner=owner) as c:
            self.service._onboarded(c,owner)
            # 先撤回舊值再重建當下有效快照；每次AI使用只拿本次重驗後的active集合。
            scope=(owner,) if not person else (owner,person,owner)
            where='owner_id=?' if not person else 'owner_id=? AND subject_id IN (?,?)'
            c.execute('UPDATE relationship_features SET revocation_state=\'withdrawn\',value=\'{}\',source_refs=\'[]\' WHERE '+where,scope)
            for f in candidate:
                old=c.execute('SELECT profile_version FROM relationship_features WHERE owner_id=? AND subject_type=? AND subject_id=? AND feature_key=?',(owner,f['subject_type'],f['subject_id'],f['feature_key'])).fetchone()
                version=old['profile_version']+1 if old else 1
                c.execute('INSERT INTO relationship_features(owner_id,subject_type,subject_id,feature_key,value,source_refs,context_scope,epistemic_status,model_version,profile_version,revocation_state) VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(owner_id,subject_type,subject_id,feature_key) DO UPDATE SET value=excluded.value,source_refs=excluded.source_refs,context_scope=excluded.context_scope,epistemic_status=excluded.epistemic_status,model_version=excluded.model_version,profile_version=excluded.profile_version,revocation_state=excluded.revocation_state',(owner,f['subject_type'],f['subject_id'],f['feature_key'],json.dumps(f['value']),json.dumps(f['source_refs']),f['context_scope'],f['epistemic_status'],f['model_version'],version,'active'))
                f['profile_version']=version
        return {'enabled':True,'features':candidate,'training_opt_in':False,'notice':'僅根據你確認的來源個人化；不代表真人性格或反應機率，不供模型訓練。'}


def install(app):
    """PG只有已核准增量Migration後才開啟；未啟用時不查不存在的表。"""
    import os
    from fastapi import Request
    from pydantic import BaseModel,ConfigDict,Field
    enabled=os.environ.get('LIFEWORLD_RELATIONSHIP_MEMORY_ENABLED','false')=='true'
    app.state.feature_store=FeatureStore(app.state.service) if enabled else None
    class Preferences(BaseModel):
        model_config=ConfigDict(extra='forbid',strict=True)
        enabled:bool
        preferences:dict[str,str]=Field(default_factory=dict)
    def owner(request,write=False):
        require(app.state.feature_store is not None,503,'memory_not_open','個人化長期記憶尚未開放；原有資料與功能不受影響。')
        return app.state.service.session(request.cookies.get('lw_session'),request.headers.get('X-CSRF-Token'),write)[0]['id']
    @app.get('/api/personalization')
    def get_preferences(request:Request):
        who=owner(request)
        return app.state.feature_store.preferences(who)
    @app.put('/api/personalization')
    def put_preferences(request:Request,data:Preferences):
        who=owner(request,True)
        return app.state.feature_store.configure(who,data.enabled,data.preferences)
    @app.delete('/api/personalization')
    def erase_preferences(request:Request):
        who=owner(request,True)
        return app.state.feature_store.erase(who)
