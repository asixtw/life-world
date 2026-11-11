"""8030 角色卡（移植自 8445 角色管理中心）：系統角色、複製、改版、新舊版本讀回、舊格式可編輯、封存與擁有者隔離。

只用隔離資料庫（預設 SQLite；LIFEWORLD_TEST_BACKEND=postgresql 時用合成 PG）；不連任何雲端服務。
"""
import json
import sqlite3

from fastapi.testclient import TestClient

from conftest import onboard, register


def ready(client, username='card_owner'):
    onboard(client)
    register(client, username)


def first_system(client):
    return client.get('/api/characters/system').json()['items'][0]


def copy_system(client, system, request_id='copy-1'):
    return client.post('/api/characters/copy', json={'request_id': request_id, 'source_kind': 'system',
                                                      'source_id': system['id'], 'source_version': system['version']})


def new_version(client, work, request_id, revision=None, base=None, **changes):
    content = {**work['version']['content'], **changes}
    return client.post(f"/api/characters/{work['id']}/versions",
                       json={'request_id': request_id, 'expected_revision': revision or work['revision'],
                             'base_version': base or work['current_version'], 'content': content})


def test_system_catalog_requires_session_and_reads_fixed_versions(client):
    assert client.get('/api/characters/system').status_code == 401
    ready(client)
    items = client.get('/api/characters/system').json()['items']
    assert len(items) >= 3 and all(item['content']['name'] and item['version'] for item in items)
    one = client.get(f"/api/characters/system/{items[0]['id']}")
    assert one.status_code == 200 and one.json()['content'] == items[0]['content']
    assert client.get('/api/characters/system/not-a-character').status_code == 404


def test_copy_edit_save_new_version_and_read_old_and_new(client):
    ready(client)
    system = first_system(client)
    copied = copy_system(client, system)
    assert copied.status_code == 201, copied.text
    card = copied.json()
    assert card['kind'] == 'character_card' and card['status'] == 'active' and card['current_version'] == 1
    assert card['version']['content']['source_references'][0] == {**card['version']['content']['source_references'][0],
                                                                  'kind': 'system_character', 'id': system['id'], 'version': system['version']}
    assert copy_system(client, system).json()['id'] == card['id'], '同一 request_id 重送不重複建立'
    assert [item['id'] for item in client.get('/api/characters').json()['items']] == [card['id']]

    saved = new_version(client, card, 'edit-1', tagline='我改寫的主觀設定', voice='說話慢而清楚')
    assert saved.status_code == 201, saved.text
    work = saved.json()
    assert work['current_version'] == 2 and work['revision'] == card['revision'] + 1
    assert [v['version_no'] for v in work['versions']] == [2, 1] and work['versions'][0]['origin'] == 'human'
    old = client.get(f"/api/characters/{card['id']}/versions/1").json()
    new = client.get(f"/api/characters/{card['id']}/versions/2").json()
    assert old['content']['tagline'] == system['content']['tagline'] and new['content']['tagline'] == '我改寫的主觀設定'
    assert new['parent_version'] == 1 and new['content_schema'] == 'character_card.v2'
    assert client.get(f"/api/characters/{card['id']}").json()['version']['version_no'] == 2
    assert client.get(f"/api/characters/system/{system['id']}").json()['content'] == system['content'], '系統角色本身不變'

    stale = new_version(client, card, 'edit-stale', revision=card['revision'], base=1, tagline='過期分頁')
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'revision_conflict'
    managed = new_version(client, work, 'edit-managed', source_references=[])
    assert managed.status_code == 409 and managed.json()['error']['code'] == 'managed_field'
    assert client.get(f"/api/characters/{card['id']}/versions/3").status_code == 404


def test_copy_own_card_version_keeps_source_chain(client):
    ready(client)
    system = first_system(client)
    card = copy_system(client, system).json()
    edited = new_version(client, card, 'edit-1', tagline='第二版').json()
    copied = client.post('/api/characters/copy', json={'request_id': 'copy-own', 'source_kind': 'card', 'source_id': card['id'], 'source_version': '1'})
    assert copied.status_code == 201, copied.text
    content = copied.json()['version']['content']
    assert content['tagline'] == system['content']['tagline'], '複製指定的舊版，而不是目前版本'
    assert [ref['kind'] for ref in content['source_references']] == ['system_character', 'character_card']
    assert edited['current_version'] == 2 and len(client.get('/api/characters').json()['items']) == 2


def test_legacy_v1_card_is_readable_and_editable(sqlite_client, tmp_path):
    ready(sqlite_client)
    owner = sqlite_client.get('/api/auth/me').json()['owner_id']
    legacy = {'name': '舊格式角色', 'kind': 'fictional', 'tagline': '只有舊欄位', 'background': '', 'personality': '', 'motivation': '',
              'stance': '', 'voice': '', 'knowledge_boundary': '', 'restrictions': [], 'sample_lines': []}
    with sqlite3.connect(tmp_path / 'lifeworld.sqlite3') as c:  # 模擬 8445 時期保存的 character_card.v1
        c.execute("INSERT INTO works(id,owner_id,kind,title,status,current_version,revision,created_at,updated_at) "
                  "VALUES ('legacy-card',?,'character_card','舊格式角色','active',1,1,'2026-11-01T00:00:00+00:00','2026-11-01T00:00:00+00:00')", (owner,))
        c.execute("INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) "
                  "VALUES ('legacy-card',?,1,NULL,'human','character_card.v1',?,NULL,'2026-11-01T00:00:00+00:00')", (owner, json.dumps(legacy, ensure_ascii=False)))
    work = sqlite_client.get('/api/characters/legacy-card').json()
    assert work['version']['content_schema'] == 'character_card.v1' and work['version']['content']['tagline'] == '只有舊欄位'
    listed = sqlite_client.get('/api/characters').json()['items'][0]
    assert listed['content']['inspirations'] == [] and listed['content']['source_references'] == []
    content = {**listed['content'], 'values': '新欄位也能填'}
    saved = sqlite_client.post('/api/characters/legacy-card/versions', json={'request_id': 'legacy-edit', 'expected_revision': 1, 'base_version': 1, 'content': content})
    assert saved.status_code == 201, saved.text
    assert saved.json()['version']['content_schema'] == 'character_card.v2'
    assert sqlite_client.get('/api/characters/legacy-card/versions/1').json()['content'] == legacy


def test_other_account_cannot_read_copy_or_edit_private_card(client):
    ready(client)
    card = copy_system(client, first_system(client)).json()
    other = TestClient(client.app)
    ready(other, 'card_intruder')
    assert other.get('/api/characters').json()['items'] == []
    for path in (f"/api/characters/{card['id']}", f"/api/characters/{card['id']}/versions/1"):
        assert other.get(path).status_code == 404
    assert new_version(other, card, 'steal').status_code == 404
    stolen = other.post('/api/characters/copy', json={'request_id': 'steal-copy', 'source_kind': 'card', 'source_id': card['id'], 'source_version': '1'})
    assert stolen.status_code == 404
    assert client.get(f"/api/characters/{card['id']}").json()['current_version'] == 1


def test_guest_can_browse_system_but_cannot_create_cards(client):
    onboard(client)
    assert client.get('/api/characters/system').status_code == 200
    denied = copy_system(client, first_system(client))
    assert denied.status_code == 403 and denied.json()['error']['code'] == 'upgrade_required'


def test_archive_blocks_edit_and_restore_reopens(client):
    ready(client)
    card = copy_system(client, first_system(client)).json()
    archived = client.post(f"/api/characters/{card['id']}/status", json={'request_id': 'archive-1', 'expected_revision': card['revision'], 'status': 'archived'})
    assert archived.status_code == 200 and archived.json()['status'] == 'archived'
    assert client.get('/api/characters').json()['items'] == []
    assert [item['id'] for item in client.get('/api/characters?status=archived').json()['items']] == [card['id']]
    blocked = new_version(client, archived.json(), 'edit-archived')
    assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'work_archived'
    restored = client.post(f"/api/characters/{card['id']}/status", json={'request_id': 'restore-1', 'expected_revision': archived.json()['revision'], 'status': 'active'})
    assert restored.status_code == 200
    assert new_version(client, restored.json(), 'edit-after-restore', tagline='恢復後可編輯').status_code == 201
