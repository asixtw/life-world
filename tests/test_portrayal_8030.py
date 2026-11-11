"""8030 F06A 人物演繹（自 8445 移植）：只讀本人選取的人物資料 → AI 推演 → 保存與人工改版（來源固定）→ 互動試演逐來回保存、第 6 個來回結束 → 擁有者隔離。

只用隔離 SQLite 與 Fake Provider（不連網、不計費）。AI 推論不寫回人物、人物資訊或筆記。
"""
from fastapi.testclient import TestClient

from conftest import onboard, register
from test_generation_8030 import client  # noqa: F401（pytest fixture）
from test_people import event, fact_body


def setup_person(client, username='portrayal_user'):
    _, goal = onboard(client)
    register(client, username)
    person = client.post('/api/people', json={'name': '陳老師', 'roles': ['大學導師'], 'category': 'learning',
                                              'common_context': '研究所每週討論', 'notes': '說話慢，常先反問'}).json()
    experience = event(client, goal, person, 'portrayal-exp')
    fact = client.post(f"/api/people/{person['id']}/facts", json={**fact_body(experience['experience_id']), 'dimension': 'habits',
                                                                   'value': '討論前先畫架構圖', 'description': '每次會議都這樣做。'})
    assert fact.status_code == 201, fact.text
    note = client.post('/api/notes', json={'person_id': person['id'], 'kind': 'preparation', 'title': '說話方式', 'content': '語氣溫和，但會直接指出問題。'})
    assert note.status_code == 201, note.text
    return person, fact.json(), note.json()


def legacy_session(client, body):
    """D-42 後 API 不再新建互動試演；既有（舊）試演以服務直接建立，用來驗證依原契約繼續與結束。"""
    from app.portrayals import PortrayalSessionStart
    owner = client.get('/api/auth/me').json()['owner_id']
    return client.app.state.service.start_portrayal_session(owner, PortrayalSessionStart.model_validate(body))


def portray(client, person, fact, note, request_id='portray-1'):
    body = {'request_id': request_id, 'module': 'person_portrayal',
            'input': {'person_id': person['id'], 'selection': {'fact_ids': [fact['id']], 'note_ids': [note['id']], 'fields': ['roles', 'common_context']},
                      'dataset': 'custom', 'consent': True}}
    return client.post('/api/ai/generate', json=body)


def test_portrayal_generate_save_edit_and_play_six_turns(client):
    person, fact, note = setup_person(client)
    before = client.get(f"/api/people/{person['id']}/overview").json()
    generated = portray(client, person, fact, note)
    assert generated.status_code == 201, generated.text
    output = generated.json()['output']
    assert output['source']['person_id'] == person['id'] and set(output['source']['refs']) == {'f1', 'n1', 'p1', 'p2'}
    saved = client.post('/api/portrayals', json={'request_id': 'save-p', 'generation_id': generated.json()['generation']['id']})
    assert saved.status_code == 201, saved.text
    work = saved.json()
    assert work['kind'] == 'person_portrayal' and work['version']['origin'] == 'ai' and work['title'].startswith('陳老師')
    snapshot = client.get(f"/api/portrayals/{work['id']}/versions/1/snapshot").json()['items']
    assert [item['ref'] for item in snapshot] == ['f1', 'n1', 'p1', 'p2'] and '架構圖' in snapshot[0]['text']
    edited_content = {**output, 'profile': {**output['profile'], 'summary': '我修改過的摘要'}}
    edited = client.post(f"/api/portrayals/{work['id']}/versions", json={'request_id': 'edit-p', 'expected_revision': work['revision'], 'base_version': 1,
                                                                         'content': edited_content})
    assert edited.status_code == 201 and edited.json()['version']['origin'] == 'ai_edited', edited.text
    moved = {**edited_content, 'source': {**output['source'], 'person_name': '別人'}}
    blocked = client.post(f"/api/portrayals/{work['id']}/versions", json={'request_id': 'edit-p2', 'expected_revision': edited.json()['revision'],
                                                                          'base_version': 2, 'content': moved})
    assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'source_mismatch', '來源固定'
    body = {'request_id': 'ps-1', 'portrayal_work_id': work['id'], 'portrayal_version': 2, 'scenario': {'kind': 'advice', 'detail': '想請教論文方向'}}
    refused = client.post('/api/portrayal-sessions', json=body)
    assert refused.status_code == 410 and refused.json()['error']['code'] == 'legacy_flow_closed', 'D-42：API 拒絕新建互動試演'
    session = legacy_session(client, body)  # 既有的舊試演
    assert session['kind'] == 'portrayal_session' and session['version']['content']['portrayal']['version_no'] == 2
    for n in range(1, 7):
        reply = client.post('/api/ai/generate', json={'request_id': f'say-{n}', 'module': 'portrayal_reply',
                                                      'input': {'session_work_id': session['id'], 'session_version': session['current_version'], 'turn_no': n,
                                                                'message': f'老師，第 {n} 個問題想請教您。'}})
        assert reply.status_code == 201, reply.text
        saved_turn = client.post(f"/api/portrayal-sessions/{session['id']}/turns",
                                 json={'request_id': f'turn-{n}', 'expected_revision': session['revision'], 'generation_id': reply.json()['generation']['id']})
        assert saved_turn.status_code == 201, saved_turn.text
        session = saved_turn.json()
        assert session['version']['content']['turns'][-1]['reply'] == reply.json()['output']
    content = session['version']['content']
    assert content['status'] == 'ended' and content['ending'] == 'turn_limit' and len(content['turns']) == 6
    after = client.get(f"/api/people/{person['id']}/overview").json()
    assert after['facts'] == before['facts'] and after['notes'] == before['notes'], 'AI 推論不寫回人物資料'


def test_portrayal_session_end_stale_and_owner_isolation(client):
    person, fact, note = setup_person(client, 'portrayal_a')
    generated = portray(client, person, fact, note).json()
    work = client.post('/api/portrayals', json={'request_id': 'save', 'generation_id': generated['generation']['id']}).json()
    session = legacy_session(client, {'request_id': 'ps', 'portrayal_work_id': work['id'], 'portrayal_version': 1, 'scenario': {'kind': 'daily'}})
    first = client.post('/api/ai/generate', json={'request_id': 'a1', 'module': 'portrayal_reply',
                                                  'input': {'session_work_id': session['id'], 'session_version': 1, 'turn_no': 1, 'message': '老師早安'}}).json()
    second = client.post('/api/ai/generate', json={'request_id': 'a2', 'module': 'portrayal_reply',
                                                   'input': {'session_work_id': session['id'], 'session_version': 1, 'turn_no': 1, 'message': '老師午安'}}).json()
    saved = client.post(f"/api/portrayal-sessions/{session['id']}/turns",
                        json={'request_id': 't1', 'expected_revision': session['revision'], 'generation_id': first['generation']['id']}).json()
    stale = client.post(f"/api/portrayal-sessions/{session['id']}/turns",
                        json={'request_id': 't2', 'expected_revision': saved['revision'], 'generation_id': second['generation']['id']})
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'stale_session'
    other = TestClient(client.app)
    onboard(other)
    register(other, 'portrayal_b')
    assert other.get(f"/api/works/{work['id']}").status_code == 404
    assert other.get(f"/api/portrayals/{work['id']}/versions/1/snapshot").status_code == 404
    assert portray(other, person, fact, note, 'steal').status_code == 404, '不能讀別人的人物資料'
    assert other.post('/api/portrayals', json={'request_id': 'steal-save', 'generation_id': generated['generation']['id']}).status_code == 404
    assert other.post(f"/api/portrayal-sessions/{session['id']}/end", json={'request_id': 'x', 'expected_revision': saved['revision']}).status_code == 404
    ended = client.post(f"/api/portrayal-sessions/{session['id']}/end", json={'request_id': 'end', 'expected_revision': saved['revision']})
    assert ended.status_code == 200 and ended.json()['version']['content']['ending'] == 'player_ended'
    assert len(ended.json()['version']['content']['turns']) == 1


def test_portrayal_requires_consent_and_blocks_sensitive_notes(client):
    person, fact, note = setup_person(client, 'portrayal_c')
    body = {'request_id': 'no-consent', 'module': 'person_portrayal',
            'input': {'person_id': person['id'], 'selection': {'fact_ids': [], 'note_ids': [note['id']], 'fields': []}, 'dataset': 'custom', 'consent': False}}
    assert client.post('/api/ai/generate', json=body).status_code == 422
    secret = client.post('/api/notes', json={'person_id': person['id'], 'kind': 'preparation', 'title': '其他', 'content': '他的身分證是 A123456789'}).json()
    blocked = client.post('/api/ai/generate', json={**body, 'request_id': 'secret', 'input': {**body['input'], 'consent': True,
                                                                                            'selection': {'fact_ids': [], 'note_ids': [secret['id']], 'fields': []}}})
    assert blocked.status_code == 422 and blocked.json()['error']['code'] == 'sensitive_data_detected'


def test_portrayal_to_card_copies_only_selected_sections_and_marks_ai_inference(client):
    person, fact, note = setup_person(client, 'portrayal_card')
    generated = portray(client, person, fact, note).json()
    work = client.post('/api/portrayals', json={'request_id': 'save', 'generation_id': generated['generation']['id']}).json()
    profile = work['version']['content']['profile']
    body = {'request_id': 'to-card', 'portrayal_work_id': work['id'], 'version_no': 1, 'sections': ['summary', 'traits', 'speaking_style'], 'acknowledged': True}
    assert client.post('/api/characters/from-portrayal', json={**body, 'acknowledged': False}).status_code == 422, '必須確認用途'
    created = client.post('/api/characters/from-portrayal', json=body)
    assert created.status_code == 201, created.text
    card = created.json()
    content = card['version']['content']
    assert content['name'] == '陳老師' and content['kind'] == 'fictional' and content['inspirations'] == ['real_person']
    assert content['tagline'] == profile['summary'] and content['personality'] == '；'.join(item['text'] for item in profile['traits'])
    assert content['voice'] == profile['speaking_style']['text']
    assert content['motivation'] == '' and content['values'] == '' and content['sample_lines'] == [], '沒勾選的段落不轉入'
    ref = content['source_references'][0]
    assert ref['kind'] == 'person_portrayal' and ref['id'] == work['id'] and ref['ai_inferred'] is True and ref['generation_id'] == generated['generation']['id']
    assert '架構圖' not in str(content), '不複製人物事實原文'
    listed = client.get('/api/characters').json()['items']
    assert any(item['id'] == card['id'] and item['provenance'] == 'portrayal' for item in listed)
    assert client.post('/api/characters/from-portrayal', json=body).json()['id'] == card['id'], '同一 request_id 不重複建立'
    other = TestClient(client.app)
    onboard(other)
    register(other, 'portrayal_card_b')
    assert other.post('/api/characters/from-portrayal', json={**body, 'request_id': 'steal'}).status_code == 404
