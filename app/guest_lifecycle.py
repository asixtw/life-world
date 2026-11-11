"""Explicit abandonment; isolated maintenance worker, never run by web runtime."""
from datetime import datetime,timedelta
import re


# 已審核的資料表形狀。E2E 現況（38 表）的清除收據有 owner 外鍵，會擋住清除順序，因此不在清單內。
ALPHA_034=frozenset('''actions auth_rate_buckets completions contributions draft_stories drafts evidence experience_mentions experience_participants experience_stories experiences external_identities fact_sources goal_reviews goals guest_abandonments habit_quantity_versions interaction_events interaction_experiences interaction_people note_sources notes pending_contributions people person_connections person_facts person_goals requests reward_ledger schema_migrations sessions story_history tasks users'''.split())
UNIFIED_010=ALPHA_034|frozenset({'ai_generations','data_consents','session_turns','works','work_versions',
                                 'subject_experiences','subject_experience_people','person_connection_experience_sources'})
SQLITE_ONLY=frozenset({'relationship_features','relationship_memory_preferences'})  # 009 的本機功能表，只存在於 SQLite
KEPT_TABLES=('schema_migrations','auth_rate_buckets','guest_abandonments')  # 遷移台帳、限流、清除收據：不屬於訪客，一律保留


def reviewed_shape(names,backend):
    """回傳已審核的形狀代號；任何其他形狀（含 E2E 現況或多出未審核的表）一律拒絕，不刪除任何資料。"""
    names=set(names)
    if backend=='sqlite':names-=SQLITE_ONLY
    for key,shape in (('alpha_034',ALPHA_034),('unified_010',UNIFIED_010)):
        if names==shape:return key
    raise ValueError('unreviewed_table')


def abandon(c,owner,now):
    row=c.execute('SELECT status FROM users WHERE id=?',(owner,)).fetchone()
    if not row or row['status']!='guest':raise ValueError('registered_owner_forbidden')
    if c.execute('SELECT owner_id FROM external_identities WHERE owner_id=?',(owner,)).fetchone():raise ValueError('bound_owner_forbidden')
    c.execute("INSERT INTO guest_abandonments(owner_id,abandoned_at,purge_after,status,attempts) VALUES (?,?,?,'pending',0) ON CONFLICT(owner_id) DO NOTHING",(owner,now.isoformat(),(now+timedelta(days=14)).isoformat()))
    c.execute('DELETE FROM sessions WHERE owner_id=?',(owner,))


def quote(name):
    if not re.fullmatch('[a-z_][a-z0-9_]*',name):raise ValueError('unsafe_schema')
    return '"'+name+'"'


class GuestPurger:
    def __init__(self,db,clock,media_cleanup=None):
        self.db=db;self.clock=clock;self.media_cleanup=media_cleanup

    def purge(self,owner):
        result=self._purge(owner)
        if result!='media_pending':return result
        # External deletion is outside SQL transactions. Durable state permits retries
        # after process death; adapters MUST treat owner as an idempotency key.
        try:
            with self.db.connect() as c:
                job=c.execute('SELECT * FROM guest_abandonments WHERE owner_id=?',(owner,)).fetchone()
                user=c.execute('SELECT status FROM users WHERE id=?',(owner,)).fetchone()
                if not user or user['status']!='guest':return 'owner_changed'
                if job['media_attempts']>=5:return 'media_retry_exhausted'
                evidence=c.execute('SELECT 1 FROM evidence WHERE owner_id=? LIMIT 1',(owner,)).fetchone()
            with self.db.connect(write=True,owner=owner) as c:
                c.execute('UPDATE guest_abandonments SET media_attempts=media_attempts+1 WHERE owner_id=?',(owner,))
            if self.media_cleanup:self.media_cleanup(owner)
            else:
                # Current evidence bytes live in SQL (no object-store adapter).
                # They are deleted with their row in the final atomic purge.
                with self.db.connect() as c:c.execute('SELECT content FROM evidence LIMIT 0')
            with self.db.connect(write=True,owner=owner) as c:
                c.execute("UPDATE guest_abandonments SET media_state='done' WHERE owner_id=? AND status<>'completed'",(owner,))
        except Exception:
            with self.db.connect(write=True,owner=owner) as c:
                c.execute("UPDATE guest_abandonments SET media_state='retry',status='retry',last_error_code='media_failed',attempts=attempts+1 WHERE owner_id=? AND status<>'completed'",(owner,))
            return 'cleanup_failed'
        return self._purge(owner)

    def _purge(self,owner):
        try:
            with self.db.connect(write=True,owner=owner) as c:
                job=c.execute('SELECT * FROM guest_abandonments WHERE owner_id=?',(owner,)).fetchone()
                if not job or job['status']=='completed':return 'noop'
                if datetime.fromisoformat(job['purge_after'])>self.clock():return 'not_due'
                user=c.execute('SELECT status FROM users WHERE id=?',(owner,)).fetchone()
                if not user or user['status']!='guest' or c.execute('SELECT owner_id FROM external_identities WHERE owner_id=?',(owner,)).fetchone():raise ValueError('owner_changed')
                from .guest_fk import catalog,verify_graph
                cols,groups=catalog(c,self.db.backend);names=list(cols)
                shape=reviewed_shape(names,self.db.backend)  # 先核對資料表形狀，再依形狀核對外鍵契約
                if self.db.backend=='postgresql':verify_graph(groups,shape)
                edges=[(ch,col,p,target) for ch,columns,p,targets in groups for col,target in zip(columns,targets)]
                names=[n for n in names if n not in KEPT_TABLES]
                scope={n:'owner_id=?' for n in names if 'owner_id' in cols[n]};scope['users']='id=?'
                pending=set(names)-set(scope)
                while pending:
                    progress=False
                    for n in list(pending):
                        refs=[(col,p,target) for ch,col,p,target in edges if ch==n]
                        if refs and all(p in scope for _,p,_ in refs):
                            # One controlling parent. Other FK edges are independently checked below.
                            col,p,target=refs[0];scope[n]=quote(col)+' IN (SELECT '+quote(target)+' FROM '+quote(p)+' WHERE '+scope[p]+')'
                            pending.remove(n);progress=True
                    if not progress:raise ValueError('unreviewed_table')
                for ch,columns,p,targets in groups:
                    if ch not in scope or p not in scope:continue
                    child_tuple='('+','.join(quote(x) for x in columns)+')'
                    parent_tuple=','.join(quote(x) for x in targets)
                    nonnull=' AND '.join(quote(x)+' IS NOT NULL' for x in columns)
                    for a,b in [(True,False),(False,True)]:
                        q='SELECT 1 FROM '+quote(ch)+' WHERE '+nonnull+' AND ('+scope[ch]+')='+('true' if a else 'false')+' AND '+child_tuple+' IN (SELECT '+parent_tuple+' FROM '+quote(p)+' WHERE ('+scope[p]+')='+('true' if b else 'false')+') LIMIT 1'
                        if c.execute(q,(owner,owner)).fetchone():raise ValueError('cross_owner_reference')
                if job['media_state']!='done':return 'media_pending'
                remaining=set(names)-{'external_identities'};order=[]
                while remaining:
                    leaves=[n for n in remaining if not any(p==n and ch in remaining for ch,_,p,_ in edges)]
                    if not leaves:raise ValueError('fk_cycle')
                    order+=leaves;remaining-=set(leaves)
                for n in order:c.execute('DELETE FROM '+quote(n)+' WHERE '+scope[n],(owner,))
                c.execute("UPDATE guest_abandonments SET status='completed',completed_at=?,last_error_code=NULL,attempts=attempts+1 WHERE owner_id=?",(self.clock().isoformat(),owner))
            return 'completed'
        except Exception as exc:
            # Store only bounded application codes, never SQL/provider error details.
            code=str(exc) if isinstance(exc,ValueError) else 'cleanup_failed'
            if code not in ('owner_changed','cross_owner_reference','media_cleanup_required','fk_cycle','unreviewed_table','unreviewed_fk'):code='cleanup_failed'
            with self.db.connect(write=True,owner=owner) as c:
                c.execute("UPDATE guest_abandonments SET status='retry',attempts=attempts+1,last_error_code=? WHERE owner_id=? AND status<>'completed'",(code,owner))
            return code
