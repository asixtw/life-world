"""8030 Self Persona、同意管理與作品管理（自 8445 移植）。只用隔離資料庫，不連任何雲端服務。"""
import json
import sqlite3

from fastapi.testclient import TestClient

from conftest import onboard, register

PERSONA = {'display_name': '小光', 'public_profile': '喜歡慢跑的設計師', 'personality': '好奇、慢熱', 'speaking_style': '說話簡短、偶爾開玩笑'}


def ready(client, username='persona_owner'):
    onboard(client)
    register(client, username)


def save(client, request_id, revision=None, **changes):
    body = {'request_id': request_id, 'content': {**PERSONA, **changes}}
    if revision is not None:
        body['expected_revision'] = revision
    return client.put('/api/self-persona', json=body)


def consent(client, request_id, granted):
    return client.post('/api/self-persona/consent', json={'request_id': request_id, 'granted': granted})


def test_self_persona_create_update_keeps_one_active_and_versions(client):
    ready(client)
    empty = client.get('/api/self-persona').json()
    assert empty['persona'] is None and empty['consent'] is None and empty['consent_text']
    first = save(client, 'p1')
    assert first.status_code == 200, first.text
    persona = first.json()['persona']
    assert persona['version_no'] == 1 and persona['content']['display_name'] == '小光'
    assert save(client, 'p1').json()['persona']['work_id'] == persona['work_id'], '同一 request_id 重送不重複建立'
    missing = save(client, 'p-no-revision', personality='改了')
    assert missing.status_code == 409 and missing.json()['error']['code'] == 'revision_required'
    second = save(client, 'p2', revision=persona['revision'], personality='好奇、慢熱、很有耐心')
    assert second.status_code == 200, second.text
    updated = second.json()['persona']
    assert updated['work_id'] == persona['work_id'] and updated['version_no'] == 2
    stale = save(client, 'p-stale', revision=persona['revision'], personality='過期分頁')
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'revision_conflict'
    assert client.get('/api/self-persona').json()['persona']['content']['personality'] == '好奇、慢熱、很有耐心'
    listed = client.get('/api/works?kind=self_persona').json()
    assert listed['total'] == 1, '同一帳號只有一份使用中的人設'
    versions = client.get(f"/api/works/{persona['work_id']}").json()['versions']
    assert [v['version_no'] for v in versions] == [2, 1]
    assert client.get(f"/api/works/{persona['work_id']}/versions/1").json()['content']['personality'] == '好奇、慢熱'


def test_consent_grant_revoke_and_read_back_after_relogin(client):
    ready(client, 'consent_owner')
    blocked = consent(client, 'c0', True)
    assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'self_persona_required'
    save(client, 'p1')
    granted = consent(client, 'c1', True).json()
    assert granted['consent'] and granted['consent']['consent_version'] == 'self-persona-ai-v1'
    client.post('/api/auth/logout')
    login = client.post('/api/auth/login', json={'username': 'consent_owner', 'password': 'a-good-password-2026'})
    client.headers['X-CSRF-Token'] = login.json()['csrf_token']
    assert client.get('/api/self-persona').json()['consent']['id'] == granted['consent']['id'], '重新登入後讀回同意狀態'
    revoked = consent(client, 'c2', False).json()
    assert revoked['consent'] is None and revoked['persona'] is not None
    regranted = consent(client, 'c3', True).json()
    assert regranted['consent']['id'] != granted['consent']['id'], '撤回後重新同意是新的紀錄'


def test_works_list_filters_pagination_detail_and_archive(client):
    ready(client, 'works_owner')
    system = client.get('/api/characters/system').json()['items']
    cards = [client.post('/api/characters/copy', json={'request_id': f'copy-{i}', 'source_kind': 'system', 'source_id': system[i]['id'],
                                                         'source_version': system[i]['version']}).json() for i in range(3)]
    save(client, 'p1')
    everything = client.get('/api/works').json()
    assert everything['total'] == 4 and {item['kind'] for item in everything['items']} == {'character_card', 'self_persona'}
    page = client.get('/api/works?kind=character_card&limit=2&offset=0').json()
    rest = client.get('/api/works?kind=character_card&limit=2&offset=2').json()
    assert page['total'] == 3 and len(page['items']) == 2 and len(rest['items']) == 1
    assert {i['id'] for i in page['items'] + rest['items']} == {card['id'] for card in cards}
    detail = client.get(f"/api/works/{cards[0]['id']}").json()
    assert detail['kind'] == 'character_card' and detail['version']['version_no'] == 1
    archived = client.post(f"/api/works/{cards[0]['id']}/status", json={'request_id': 'a1', 'expected_revision': detail['revision'], 'status': 'archived'})
    assert archived.status_code == 200 and archived.json()['status'] == 'archived'
    assert client.get('/api/works?status=archived').json()['total'] == 1
    restored = client.post(f"/api/works/{cards[0]['id']}/status", json={'request_id': 'a2', 'expected_revision': archived.json()['revision'], 'status': 'active'})
    assert restored.status_code == 200 and restored.json()['status'] == 'active'
    persona_id = client.get('/api/self-persona').json()['persona']['work_id']
    persona_work = client.get(f'/api/works/{persona_id}').json()
    refused = client.post(f'/api/works/{persona_id}/status', json={'request_id': 'a3', 'expected_revision': persona_work['revision'], 'status': 'archived'})
    assert refused.status_code == 409 and refused.json()['error']['code'] == 'status_not_supported'


def test_works_from_8445_are_readable_and_private(sqlite_client, tmp_path):
    ready(sqlite_client, 'legacy_owner')
    owner = sqlite_client.get('/api/auth/me').json()['owner_id']
    content = {'title': '霧港夜談', 'segments': [{'turn_no': 1, 'text': '旁白：霧散開了。'}]}
    with sqlite3.connect(tmp_path / 'lifeworld.sqlite3') as c:  # 模擬 8445 保存的生成作品（兩個版本）
        c.execute("INSERT INTO works(id,owner_id,kind,title,status,current_version,revision,created_at,updated_at) "
                  "VALUES ('legacy-work',?,'generated_work','霧港夜談','active',2,2,'2026-11-08T00:00:00+00:00','2026-11-08T01:00:00+00:00')", (owner,))
        for version, text in ((1, '第一版'), (2, '第二版')):
            c.execute("INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) "
                      "VALUES ('legacy-work',?,?,?,'ai','generated_work.v1',?,NULL,'2026-11-08T00:00:00+00:00')",
                      (owner, version, None if version == 1 else 1, json.dumps({**content, 'note': text}, ensure_ascii=False)))
    work = sqlite_client.get('/api/works/legacy-work').json()
    assert work['kind'] == 'generated_work' and work['version']['content']['note'] == '第二版'
    assert sqlite_client.get('/api/works/legacy-work/versions/1').json()['content']['note'] == '第一版'
    assert sqlite_client.get('/api/works?kind=generated_work').json()['total'] == 1
    other = TestClient(sqlite_client.app)
    ready(other, 'works_intruder')
    assert other.get('/api/works/legacy-work').status_code == 404
    assert other.get('/api/works/legacy-work/versions/1').status_code == 404
    assert other.get('/api/works').json()['total'] == 0
    assert other.get('/api/self-persona').json()['persona'] is None
