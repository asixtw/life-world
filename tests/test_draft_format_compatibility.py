"""發布/回退讀取器不得把未知格式當舊故事覆寫；同Owner舊格式保持可讀。"""
import json
import pytest
from conftest import onboard,register,draft,confirm_payload


def test_unknown_draft_envelope_is_blocked_without_overwrite(client,app):
 me,g=onboard(client);register(client);d=draft(client,g,contributions=[])
 payload=json.dumps({'_format':'experience_draft_v999','story':None,'review':{'future_field':'保留未來資料'}})
 with app.state.service.db.connect(write=True,owner=me['owner_id']) as c:c.execute('INSERT INTO draft_stories VALUES (?,?)',(d['id'],payload))
 r=client.get('/api/drafts/'+d['id']);assert r.status_code==409 and r.json()['error']['code']=='draft_format_unsupported'
 edit={'raw_text':'不能覆寫','occurred_at':d['occurred_at'],'contributions':[],'expected_revision':d['revision'],'story':None,'review':None}
 assert client.put('/api/drafts/'+d['id'],json=edit).status_code==409
 assert client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d,contributions=[])).status_code==409
 with app.state.service.db.connect() as c:
  # 內容原封不動即可：PostgreSQL（alpha 的 jsonb）會正規化格式，SQLite 保留原字串；兩者都必須等於原內容。
  assert json.loads(c.execute('SELECT payload FROM draft_stories WHERE draft_id=?',(d['id'],)).fetchone()[0])==json.loads(payload)
  row=c.execute('SELECT raw_text,revision FROM drafts WHERE id=?',(d['id'],)).fetchone();assert row['raw_text']==d['raw_text'] and row['revision']==d['revision']
  assert c.execute('SELECT count(*) FROM experiences WHERE owner_id=?',(me['owner_id'],)).fetchone()[0]==0


@pytest.mark.parametrize('format_name',[None,'experience_draft_v2'])
def test_legacy_and_current_envelopes_read_same_story(client,app,format_name):
 me,g=onboard(client);register(client);p=client.post('/api/people',json={'name':'合成人物'}).json();story={'title':'舊故事','participants':[{'person_id':p['id'],'interacted':False}],'mentions':[]}
 d=draft(client,g,contributions=[],story=story);payload=story if format_name is None else {'_format':format_name,'story':story,'review':None}
 with app.state.service.db.connect(write=True,owner=me['owner_id']) as c:c.execute('UPDATE draft_stories SET payload=? WHERE draft_id=?',(json.dumps(payload),d['id']))
 r=client.get('/api/drafts/'+d['id']);assert r.status_code==200 and r.json()['story']==story and r.json()['review'] is None
