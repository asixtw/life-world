"""8030 F05 短篇互動（自 8445 移植）：從故事開場開始冒險、逐回合生成並保存、第 5 回合自動結束、玩家主動結束、過期與擁有者隔離。

只用隔離 SQLite 與 Fake Provider（不連網、不計費）。
"""
from fastapi.testclient import TestClient

from test_generation_8030 import client, copy_card, ready  # noqa: F401（pytest fixture）
from test_stories_8030 import generate as generate_story


def saved_story(client):
    card = copy_card(client)
    draft = generate_story(client, card)
    return client.post('/api/stories', json={'request_id': 'story-save', 'content': draft['output'], 'generation_id': draft['generation']['id']}).json()


def start(client, story, request_id='play-1'):
    response = client.post('/api/play/sessions', json={'request_id': request_id, 'story_work_id': story['id'], 'story_version': story['current_version']})
    assert response.status_code == 201, response.text
    return response.json()


def reply(client, session, action, request_id):
    content = session['version']['content']
    body = {'request_id': request_id, 'module': 'character_reply',
            'input': {'session_work_id': session['id'], 'session_version': session['current_version'], 'turn_no': len(content['turns']) + 1, 'action': action}}
    return client.post('/api/ai/generate', json=body)


def play_turn(client, session, action, n):
    generated = reply(client, session, action, f'turn-{n}')
    assert generated.status_code == 201, generated.text
    saved = client.post(f"/api/play/sessions/{session['id']}/turns",
                        json={'request_id': f'save-{n}', 'expected_revision': session['revision'], 'generation_id': generated.json()['generation']['id']})
    assert saved.status_code == 201, saved.text
    return generated.json(), saved.json()


def test_play_five_turns_saves_each_turn_and_ends_at_limit(client):
    ready(client, 'play_owner')
    story = saved_story(client)
    session = start(client, story)
    content = session['version']['content']
    assert session['kind'] == 'story_session' and content['status'] == 'active' and content['turns'] == []
    assert content['character']['name'] == story['version']['content']['source']['character_name']
    for n in range(1, 6):
        action = {'kind': 'choice', 'choice_index': n % 3} if n != 3 else {'kind': 'free', 'text': '我走向燈塔，敲門詢問守塔人。'}
        generated, session = play_turn(client, session, action, n)
        turns = session['version']['content']['turns']
        assert len(turns) == n and turns[-1]['generation_id'] == generated['generation']['id'] and session['version']['origin'] == 'ai'
        assert session['current_version'] == n + 1, '每回合保存一個新版本'
    assert session['version']['content']['status'] == 'ended' and session['version']['content']['ending'] == 'turn_limit'
    assert turns[2]['action'] == {'kind': 'free', 'choice_index': None, 'text': '我走向燈塔，敲門詢問守塔人。', 'strategy': ''}
    assert client.get(f"/api/works/{session['id']}/versions/2").json()['content']['turns'][0] == turns[0], '舊版本可回讀且不變'
    more = reply(client, session, {'kind': 'choice', 'choice_index': 0}, 'turn-6')
    assert more.status_code == 422, '最多 5 回合'
    assert client.get('/api/works?kind=story_session').json()['total'] == 1


def test_stale_turn_cannot_be_saved_and_player_can_end(client):
    ready(client, 'play_rules')
    session = start(client, saved_story(client))
    first = reply(client, session, {'kind': 'choice', 'choice_index': 0}, 'r1').json()
    second = reply(client, session, {'kind': 'choice', 'choice_index': 1}, 'r2')
    assert second.status_code == 201, '同一版本可以重新生成另一個候選'
    saved = client.post(f"/api/play/sessions/{session['id']}/turns",
                        json={'request_id': 's1', 'expected_revision': session['revision'], 'generation_id': first['generation']['id']}).json()
    stale = client.post(f"/api/play/sessions/{session['id']}/turns",
                        json={'request_id': 's2', 'expected_revision': saved['revision'], 'generation_id': second.json()['generation']['id']})
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'stale_session', '舊版本的候選不能接到新版本'
    old_rev = client.post(f"/api/play/sessions/{session['id']}/turns",
                          json={'request_id': 's3', 'expected_revision': session['revision'], 'generation_id': first['generation']['id']})
    assert old_rev.status_code == 409
    ended = client.post(f"/api/play/sessions/{session['id']}/end", json={'request_id': 'end', 'expected_revision': saved['revision']})
    assert ended.status_code == 200, ended.text
    content = ended.json()['version']['content']
    assert content['status'] == 'ended' and content['ending'] == 'player_ended' and len(content['turns']) == 1
    again = client.post(f"/api/play/sessions/{session['id']}/end", json={'request_id': 'end-2', 'expected_revision': ended.json()['revision']})
    assert again.status_code == 409 and again.json()['error']['code'] == 'session_ended'
    blocked = reply(client, ended.json(), {'kind': 'choice', 'choice_index': 0}, 'r3')
    assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'session_ended'


def test_play_requires_own_story_and_active_card(client):
    ready(client, 'play_a')
    story = saved_story(client)
    other = TestClient(client.app)
    ready(other, 'play_b')
    stolen = other.post('/api/play/sessions', json={'request_id': 'steal', 'story_work_id': story['id'], 'story_version': 1})
    assert stolen.status_code == 404
    session = start(client, story)
    assert other.post(f"/api/play/sessions/{session['id']}/end", json={'request_id': 'x', 'expected_revision': 1}).status_code == 404
    assert reply(other, session, {'kind': 'choice', 'choice_index': 0}, 'steal-turn').status_code == 404
    card_id = story['version']['content']['source']['character_work_id']
    card = client.get(f'/api/works/{card_id}').json()
    client.post(f'/api/characters/{card_id}/status', json={'request_id': 'arch', 'expected_revision': card['revision'], 'status': 'archived'})
    blocked = client.post('/api/play/sessions', json={'request_id': 'play-2', 'story_work_id': story['id'], 'story_version': 1})
    assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'character_archived'
