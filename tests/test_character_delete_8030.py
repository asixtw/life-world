"""8030 角色卡：只能封存與恢復，永久刪除一律回 409 archive_only（2026-11-10 定案）；引用清單照常；
其他帳號的卡一律 404，不透露是否存在。

只用隔離 SQLite 與 Fake Provider。
"""
import json

from fastapi.testclient import TestClient

from test_generation_8030 import client, copy_card, ready  # noqa: F401（pytest fixture）
from test_stories_8030 import generate as generate_story


def delete(client, card, request_id='del-1'):
    return client.post(f"/api/characters/{card['id']}/delete", json={'request_id': request_id, 'expected_revision': card['revision']})


def test_unused_card_cannot_be_deleted_only_archived(client):
    """2026-11-10 定案：角色卡只能封存與恢復。沒有引用的卡也不能永久刪除，資料與 AI 原稿都不變。"""
    ready(client, 'delete_owner')
    card = copy_card(client)
    draft = generate_story(client, card, 'unsaved-story')
    blocked = delete(client, card)
    assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'archive_only', blocked.text
    assert client.get(f"/api/characters/{card['id']}").status_code == 200
    assert client.get('/api/characters').json()['total'] == 1
    with client.app.state.service.db.connect() as db:
        row = db.execute('SELECT input_json,output_json FROM ai_generations WHERE id=?', (draft['generation']['id'],)).fetchone()
    assert '_deleted' not in json.loads(row['input_json']) and row['output_json'] is not None, 'AI 原稿不被清除'
    archived = client.post(f"/api/characters/{card['id']}/status", json={'request_id': 'arch-0', 'expected_revision': card['revision'], 'status': 'archived'})
    assert archived.status_code == 200 and archived.json()['status'] == 'archived'
    restored = client.post(f"/api/characters/{card['id']}/status", json={'request_id': 'arch-1', 'expected_revision': archived.json()['revision'], 'status': 'active'})
    assert restored.status_code == 200 and restored.json()['status'] == 'active'


def test_referenced_card_cannot_be_deleted_but_can_be_archived(client):
    ready(client, 'delete_refs')
    card = copy_card(client)
    draft = generate_story(client, card)
    story = client.post('/api/stories', json={'request_id': 'story-save', 'content': draft['output'], 'generation_id': draft['generation']['id']}).json()
    refs = client.get(f"/api/characters/{card['id']}/references").json()['items']
    assert [(r['work_id'], r['kind'], r['card_versions']) for r in refs] == [(story['id'], 'story_opening', [1])]
    assert client.get('/api/characters').json()['items'][0]['used_by'] == 1
    blocked = delete(client, card)
    assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'archive_only'
    archived = client.post(f"/api/characters/{card['id']}/status", json={'request_id': 'arch', 'expected_revision': card['revision'], 'status': 'archived'})
    assert archived.status_code == 200
    client.post(f"/api/works/{story['id']}/status", json={'request_id': 'story-arch', 'expected_revision': story['revision'], 'status': 'archived'})
    assert delete(client, archived.json(), 'del-2').status_code == 409, '已封存的作品仍算引用'


def test_theater_cast_counts_as_reference_and_other_accounts_cannot_delete(client):
    ready(client, 'delete_theater')
    card = copy_card(client, 1)
    system = client.get('/api/characters/system').json()['items'][0]
    cast = {'title': '對話', 'scenario': {'text': '碼頭相遇', 'preset_id': None}, 'mode': 'faithful', 'direction': '',
            'cast': [{'source': 'system', 'id': system['id'], 'version': system['version'], 'name': system['name'], 'position': 'protagonist'},
                     {'source': 'card', 'id': card['id'], 'version': '1', 'name': card['version']['content']['name'], 'position': 'opponent'}]}
    assert client.post('/api/theater/casts', json={'request_id': 'cast', 'content': cast}).status_code == 201
    assert delete(client, card).status_code == 409
    other = TestClient(client.app)
    ready(other, 'delete_other')
    assert other.get(f"/api/characters/{card['id']}/references").status_code == 404
    assert other.post(f"/api/characters/{card['id']}/delete", json={'request_id': 'x', 'expected_revision': 1}).status_code == 404
    fresh = copy_card(client, 2)
    stale = client.post(f"/api/characters/{fresh['id']}/delete", json={'request_id': 'stale', 'expected_revision': fresh['revision'] + 5})
    assert stale.status_code == 409, '版本不符不能刪除'
