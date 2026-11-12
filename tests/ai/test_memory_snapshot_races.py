"""記憶重建途中撤回/停用不可重新寫入舊特徵；僅合成SQLite，非真模型。"""
import pytest
from conftest import onboard,register,draft,confirm_payload,memory_closed_on_postgres
from app.errors import DomainError
from app.relationship_memory import FeatureStore


def prepared(client,app):
 me,g=onboard(client);register(client);p=client.post('/api/people',json={'name':'合成人物'}).json()
 d=draft(client,g,raw_text='合成人物說喜歡閱讀。',contributions=[],story={'participants':[{'person_id':p['id'],'interacted':True}]})
 r=client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d,summary='一起閱讀。',contributions=[],story=d['story'],story_reviewed=True));assert r.status_code==201
 experience=client.get('/api/state').json()['experiences'][0]
 fact=client.post('/api/people/'+p['id']+'/facts',json={'request_id':'race-fact','dimension':'interests','value':'閱讀','evidence_type':'stated_by_person','source_experience_ids':[experience['id']],'confirmed':True});assert fact.status_code==201
 store=FeatureStore(app.state.service);store.configure(me['owner_id'],True,{'summary_style':'concise'})
 return store,me['owner_id'],p['id'],experience['id']


def closed_on_postgres(client,app):
 """PostgreSQL 這一輪沒有關係記憶表（規格 v1.1）：改驗證功能關閉、不寫入。"""
 if app.state.service.db.backend!='postgresql':return False
 onboard(client);register(client)
 return memory_closed_on_postgres(app,[client])


def test_disabled_during_snapshot_cannot_republish_features(client,app,monkeypatch):
 if closed_on_postgres(client,app):return
 store,owner,person,experience=prepared(client,app);original=app.state.service.person_overview
 def overview(*args):
  result=original(*args);store.configure(owner,False,{});return result
 monkeypatch.setattr(app.state.service,'person_overview',overview)
 with pytest.raises(DomainError) as error:store.context(owner,person)
 assert error.value.code=='memory_settings_changed'
 assert not store.preferences(owner)['enabled']
 with store.db.connect() as c:assert c.execute('SELECT count(*) FROM relationship_features WHERE owner_id=?',(owner,)).fetchone()[0]==0


@pytest.mark.parametrize('withdraw',['story','fact'])
def test_source_withdrawn_during_snapshot_is_not_written(client,app,monkeypatch,withdraw):
 if closed_on_postgres(client,app):return
 store,owner,person,experience=prepared(client,app)
 from app import relationship_engine
 original=relationship_engine.build_context
 def build(*args,**kwargs):
  result=original(*args,**kwargs)
  with store.db.connect(write=True,owner=owner) as c:
   if withdraw=='story':c.execute('UPDATE experience_stories SET available=FALSE,revision=revision+1 WHERE experience_id=? AND owner_id=?',(experience,owner))
   else:c.execute('UPDATE fact_sources SET revoked_at=? WHERE experience_id=? AND fact_id IN (SELECT id FROM person_facts WHERE owner_id=?)',('2026-10-27T07:00:00+00:00',experience,owner))
  return result
 monkeypatch.setattr(relationship_engine,'build_context',build)
 with pytest.raises(DomainError) as error:store.context(owner,person)
 assert error.value.code=='memory_source_changed'
 with store.db.connect() as c:
  assert c.execute('SELECT count(*) FROM relationship_features WHERE owner_id=?',(owner,)).fetchone()[0]==0
  assert c.execute('SELECT count(*) FROM experiences WHERE owner_id=?',(owner,)).fetchone()[0]==1
  assert c.execute('SELECT count(*) FROM reward_ledger WHERE owner_id=?',(owner,)).fetchone()[0]==1
