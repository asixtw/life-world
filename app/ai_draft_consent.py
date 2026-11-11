"""草稿摘要的明確、可撤回授權；沿用data_consents，不涵蓋背景AI/媒體/人物劇場。"""
import hashlib,json
from uuid import uuid4
from .errors import require
from .security import require_registered

SUBJECT='ai:draft-experience-summary'
VERSION='draft-summary-v1'
SOURCES={'fields':['draft.raw_text'],'outputs':['summary','tasks','person_information_candidates'],'include_personalization':False,'include_media':False}


class DraftAIConsent:
    def __init__(self,service,runtime):self.service=service;self.runtime=runtime

    def _policy(self):
        runtime=self.runtime();live=bool(getattr(runtime.provider,'live',False))
        provider_scope=f'{runtime.settings.provider}:{runtime.settings.model}:{"live" if live else "test"}'
        data={'subject':SUBJECT,'consent_version':VERSION,'provider_scope':provider_scope,'source_scope':SOURCES}
        fingerprint=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return {**data,'policy_fingerprint':fingerprint,'provider_label':'尚未設定外部AI服務' if runtime.provider is None else 'Google Gemini' if live else '測試替身（不會呼叫外部服務）','live_provider':live}

    def _permission(self,c):
        if self.service.db.backend!='postgresql':return True
        relation=self.service.db.settings.db_schema+'.data_consents'
        # 未具備撤回能力時不開放授權；不在Runtime自行GRANT或改用另一份同意狀態。
        row=c.execute("SELECT has_table_privilege(current_user,?,'SELECT') AND has_table_privilege(current_user,?,'INSERT') AND has_column_privilege(current_user,?,'revoked_at','UPDATE') AS allowed",(relation,relation,relation)).fetchone()
        return bool(row['allowed'])

    def _row(self,c,owner):
        return c.execute("SELECT * FROM data_consents WHERE owner_id=? AND subject=? AND purpose='ai_generation' AND revoked_at IS NULL",(owner,SUBJECT)).fetchone()

    def _matching(self,row,policy):
        if row is None:return False
        try:scope=json.loads(row['source_scope']) if isinstance(row['source_scope'],str) else row['source_scope']
        except (ValueError,TypeError):return False
        return row['provider_scope']==policy['provider_scope'] and row['consent_version']==VERSION and scope==SOURCES

    def metadata(self,owner):
        self.runtime().authorize(owner);policy=self._policy()
        with self.service.db.connect() as c:
            permission=self._permission(c);row=self._row(c,owner) if permission else None
        return {**policy,'available':self.runtime().enabled and permission,'can_revoke':permission,'granted':self._matching(row,policy),'has_consent':row is not None if permission else None,'consent_status':'unavailable' if not permission else 'granted' if self._matching(row,policy) else 'not_granted','consent_id':row['id'] if row else None,'reason':None if self.runtime().enabled and permission else 'consent_permission_missing' if not permission else 'ai_not_configured','notice':'只在主動選用時傳送本篇草稿原文以整理摘要、後續任務與原文明示人物資訊候選；不涵蓋背景AI、媒體或人物劇場。結果仍需人工確認。撤回不會取消已送出的請求。'}

    def grant(self,owner,data):
        runtime=self.runtime();runtime.authorize(owner);policy=self._policy()
        require(runtime.enabled,503,'ai_not_configured','AI尚未設定，可繼續手動記錄。')
        require(data.policy_fingerprint==policy['policy_fingerprint'],409,'ai_consent_policy_changed','服務或授權範圍已變更，請重新閱讀。')
        with self.service.db.connect(write=True,owner=owner) as c:
            require_registered(self.service._onboarded(c,owner))
            require(self._permission(c),503,'ai_consent_permission_missing','此環境尚未具備安全撤回授權能力，請使用手動流程。')
            cached,fingerprint=self.service._cached(c,owner,'draft_ai_consent_grant_v1',data.request_id,data.model_dump(mode='json'))
            row=self._row(c,owner)
            if cached:
                require(row is not None and row['id']==cached['consent_id'] and self._matching(row,policy),409,'ai_consent_revoked','原授權已撤回或失效，舊請求不會重新授權。')
                return cached
            if not self._matching(row,policy):
                now=self.service.now().isoformat()
                if row:c.execute('UPDATE data_consents SET revoked_at=? WHERE id=? AND owner_id=?',(now,row['id'],owner))
                consent_id=str(uuid4())
                c.execute("INSERT INTO data_consents(id,owner_id,subject,purpose,provider_scope,source_scope,consent_version,granted_at,revoked_at) VALUES (?,?,?,'ai_generation',?,?,?,?,NULL)",(consent_id,owner,SUBJECT,policy['provider_scope'],json.dumps(SOURCES),VERSION,now))
            else:consent_id=row['id']
            result={'consent_id':consent_id,'granted':True,'policy_fingerprint':policy['policy_fingerprint']}
            self.service._remember(c,owner,'draft_ai_consent_grant_v1',data.request_id,fingerprint,result)
            return result

    def revoke(self,owner):
        self.runtime().authorize(owner)
        with self.service.db.connect(write=True,owner=owner) as c:
            require_registered(self.service._onboarded(c,owner))
            require(self._permission(c),503,'ai_consent_permission_missing','此環境尚未具備安全撤回授權能力。')
            c.execute("UPDATE data_consents SET revoked_at=? WHERE owner_id=? AND subject=? AND purpose='ai_generation' AND revoked_at IS NULL",(self.service.now().isoformat(),owner,SUBJECT))
        return {'granted':False,'revoked':True}

    def require(self,owner):
        data=self.metadata(owner)
        require(data['available'],503,'ai_consent_permission_missing','草稿AI目前不可用，請使用手動流程。')
        require(data['granted'],403,'draft_ai_consent_required','請先閱讀並同意本篇草稿原文的AI整理用途。')
