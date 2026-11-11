"""8030 F04 故事開場（自 8445 移植）：AI 產生、保存、改版、來源固定、封存角色與擁有者隔離。只用隔離 SQLite 與 Fake Provider。"""
from fastapi.testclient import TestClient

from test_generation_8030 import client, copy_card, ready  # noqa: F401（pytest fixture）


def story_input(card, **extra):
    return {'character_work_id': card['id'], 'character_version': card['current_version'], 'genre': '奇幻冒險',
            'setting': '霧港的燈塔下，一艘遲到的船正要靠岸。', 'conflict': '船上的貨物來路不明。', 'player_goal': '查出貨物的來源。', **extra}


def generate(client, card, request_id='story-gen-1'):
    response = client.post('/api/ai/generate', json={'request_id': request_id, 'module': 'story_opening', 'input': story_input(card)})
    assert response.status_code == 201, response.text
    return response.json()


def test_generate_save_edit_and_read_story_opening(client):
    ready(client, 'story_owner')
    card = copy_card(client)
    draft = generate(client, card)
    content = draft['output']
    assert content['source']['character_work_id'] == card['id'] and len(content['choices']) == 3
    saved = client.post('/api/stories', json={'request_id': 'story-save', 'content': content, 'generation_id': draft['generation']['id']})
    assert saved.status_code == 201, saved.text
    work = saved.json()
    assert work['kind'] == 'story_opening' and work['version']['origin'] == 'ai'
    edited = client.post(f"/api/stories/{work['id']}/versions", json={'request_id': 'story-edit', 'expected_revision': work['revision'], 'base_version': 1,
                                                                      'content': {**content, 'objective': '我改寫的目標'}, 'generation_id': draft['generation']['id']})
    assert edited.status_code == 201, edited.text
    assert edited.json()['version']['origin'] == 'ai_edited' and edited.json()['current_version'] == 2
    assert client.get(f"/api/works/{work['id']}/versions/1").json()['content']['objective'] == content['objective']
    assert client.get('/api/works?kind=story_opening').json()['total'] == 1


def test_story_source_is_fixed_and_must_be_own_active_card(client):
    ready(client, 'story_rules')
    card, other_card = copy_card(client, 0), copy_card(client, 1)
    draft = generate(client, card)
    content = draft['output']
    work = client.post('/api/stories', json={'request_id': 'story-1', 'content': content, 'generation_id': draft['generation']['id']}).json()
    other_name = other_card['version']['content']['name']
    moved = {**content, 'source': {'character_work_id': other_card['id'], 'character_version': 1, 'character_name': other_name}}
    changed = client.post(f"/api/stories/{work['id']}/versions", json={'request_id': 'story-move', 'expected_revision': work['revision'], 'base_version': 1, 'content': moved})
    assert changed.status_code == 409 and changed.json()['error']['code'] == 'source_mismatch'
    mismatch = client.post('/api/stories', json={'request_id': 'story-2', 'content': moved, 'generation_id': draft['generation']['id']})
    assert mismatch.status_code == 409 and mismatch.json()['error']['code'] == 'source_mismatch', '內容來源必須與生成紀錄一致'
    archived = client.post(f"/api/characters/{other_card['id']}/status", json={'request_id': 'arch', 'expected_revision': other_card['revision'], 'status': 'archived'})
    assert archived.status_code == 200
    blocked = client.post('/api/stories', json={'request_id': 'story-3', 'content': moved})
    assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'character_archived'


def test_other_account_cannot_use_or_read_story(client):
    ready(client, 'story_a')
    card = copy_card(client)
    draft = generate(client, card)
    work = client.post('/api/stories', json={'request_id': 'story-a', 'content': draft['output'], 'generation_id': draft['generation']['id']}).json()
    other = TestClient(client.app)
    ready(other, 'story_b')
    assert other.get(f"/api/works/{work['id']}").status_code == 404
    stolen = other.post('/api/ai/generate', json={'request_id': 'steal', 'module': 'story_opening', 'input': story_input(card)})
    assert stolen.status_code == 404, '不能用別人的角色卡產生故事'
    copied = other.post('/api/stories', json={'request_id': 'steal-save', 'content': draft['output']})
    assert copied.status_code == 404


def test_stale_tab_cannot_overwrite_newer_story_version(client):
    """A、B 兩個分頁同時開啟 v1：A 先保存 v2，B 以 v1 為基礎保存時被拒，A 的內容與所有歷史版本都保留。"""
    ready(client, 'story_tabs')
    card = copy_card(client)
    draft = generate(client, card)
    work = client.post('/api/stories', json={'request_id': 'story-save', 'content': draft['output'], 'generation_id': draft['generation']['id']}).json()
    opened = client.get(f"/api/works/{work['id']}").json()  # 兩個分頁都讀到同一版本
    content = opened['version']['content']
    tab_a = client.post(f"/api/stories/{work['id']}/versions", json={'request_id': 'tab-a', 'expected_revision': opened['revision'], 'base_version': 1,
                                                                      'content': {**content, 'opening': 'A 改寫的開場'}, 'generation_id': draft['generation']['id']})
    assert tab_a.status_code == 201, tab_a.text
    tab_b = client.post(f"/api/stories/{work['id']}/versions", json={'request_id': 'tab-b', 'expected_revision': opened['revision'], 'base_version': 1,
                                                                      'content': {**content, 'title': 'B 改的標題'}, 'generation_id': draft['generation']['id']})
    assert tab_b.status_code == 409 and tab_b.json()['error']['code'] == 'stale_version', '舊分頁不能覆寫'
    assert '重新載入' in tab_b.json()['error']['message']
    sneaky = client.post(f"/api/stories/{work['id']}/versions", json={'request_id': 'tab-b2', 'expected_revision': tab_a.json()['revision'], 'base_version': 1,
                                                                       'content': {**content, 'title': 'B 改的標題'}, 'generation_id': draft['generation']['id']})
    assert sneaky.status_code == 409 and sneaky.json()['error']['code'] == 'stale_version', '拿到新 revision 但基礎版本仍是舊的，也拒絕'
    latest = client.get(f"/api/works/{work['id']}").json()
    assert latest['current_version'] == 2 and latest['version']['content']['opening'] == 'A 改寫的開場' and latest['title'] == content['title']
    assert [v['version_no'] for v in latest['versions']] == [2, 1], '歷史版本都保留'
