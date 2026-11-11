"""E2E Migration 010 前置：關係來源從 person_connections.source_experience_ids（JSONB）切換到 person_connection_experience_sources。

這是單元測試（明確指定的 SQLite，結構含 010）。PostgreSQL 驗收在 Migration 010 之後，
以 Local 8030 → Cloud SQL life_world_e2e 執行 tests/cloudsql/test_relation_sources_e2e.py，SQLite 結果不能代替它。

涵蓋：
- link_table：POST／PATCH 寫關聯表、GET 與人物總覽讀關聯表；兩種來源都是 ID 陣列，依 source_position 排序；
  PATCH 的新增、替換、清空與未提供維持；revision、重送、錯誤回滾、跨帳號；舊 JSONB 不再讀寫。
- legacy_jsonb：Migration 前（沒有關聯表）維持舊行為；已有關聯表卻仍是舊模式時拒絕寫入，避免分岔。
"""
import hashlib
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from conftest import confirm_payload, draft, onboard, register
from app import relation_sources
from app.config import DemoPolicy
from app.main import create_app
from app.service import encoded

NOW = '2026-10-27T07:00:00+00:00'
LINK_KEYS = {'id', 'owner_id', 'person_a', 'person_b', 'label', 'revision', 'source_experience_ids', 'source_person_experience_ids',
             'relation_types', 'description', 'confirmation_status'}  # P4：關係類型、共用描述與狀態
LEGACY_KEYS = {'id', 'owner_id', 'person_a', 'person_b', 'label', 'source_experience_ids'}


def world(client, username):
    """建立帳號、三位人物，以及兩筆主要人物是甲的已確認「我的紀錄」。"""
    _, goal = onboard(client)
    register(client, username)
    a, b, c = (client.post('/api/people', json={'name': n}).json() for n in ('甲', '乙', '丙'))
    experiences = []
    for i in range(2):
        d = draft(client, goal, person_id=a['id'], raw_text=f'和甲一起練習第 {i + 1} 次。')
        done = client.post(f"/api/drafts/{d['id']}/confirm", json=confirm_payload(d, request_id=f'{username}-confirm-{i}'))
        assert done.status_code == 201, done.text
        experiences.append(done.json()['experience_id'])
    return {'a': a, 'b': b, 'c': c, 'e1': experiences[0], 'e2': experiences[1], 'owner': a['owner_id']}


def person_experience(client, owner, sid, people, status='active'):
    """直接寫入人物經歷（P1 才有人物經歷 API）。people 為 [(person_id, role, interacted)]。"""
    with client.app.state.service.db.connect(write=True) as c:
        c.execute('INSERT INTO subject_experiences(id,owner_id,experience_type,origin_type,raw_text,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)',
                  (sid, owner, 'real', 'manual', '人物經歷 ' + sid, status, NOW, NOW))
        for person_id, role, interacted in people:
            c.execute('INSERT INTO subject_experience_people(subject_experience_id,owner_id,person_id,role,created_at,interacted) VALUES (?,?,?,?,?,?)',
                      (sid, owner, person_id, role, NOW, interacted))
    return sid


def rows(client, connection_id):
    with client.app.state.service.db.connect() as c:
        return [tuple(r) for r in c.execute('SELECT experience_id,subject_experience_id,source_position FROM person_connection_experience_sources '
                                            'WHERE connection_id=? ORDER BY experience_id IS NULL,source_position', (connection_id,))]


def jsonb(client, connection_id):
    with client.app.state.service.db.connect() as c:
        return c.execute('SELECT source_experience_ids FROM person_connections WHERE id=?', (connection_id,)).fetchone()[0]


def overview_connection(client, person_id, connection_id):
    body = client.get(f'/api/people/{person_id}/overview').json()
    return next(x for x in body['connections'] if x['id'] == connection_id)


def connect(client, w, request_id='c-1', **body):
    payload = {'request_id': request_id, 'other_person_id': w['b']['id'], 'label': '練習夥伴', **body}
    return client.post(f"/api/people/{w['a']['id']}/connections", json=payload)


def patch(client, connection_id, request_id, expected_revision, **body):
    return client.patch(f'/api/connections/{connection_id}', json={'request_id': request_id, 'expected_revision': expected_revision, **body})


def test_sqlite_link_table_matches_final_e2e_shape(client):
    with client.app.state.service.db.connect() as c:
        columns = [r[1] for r in c.execute('PRAGMA table_info(person_connection_experience_sources)')]
        fks = sorted((r[2], r[3], r[4]) for r in c.execute('PRAGMA foreign_key_list(person_connection_experience_sources)'))
    assert columns == ['connection_id', 'owner_id', 'subject_experience_id', 'experience_id', 'source_position']
    assert fks == [('experiences', 'experience_id', 'id'), ('experiences', 'owner_id', 'owner_id'),
                   ('person_connections', 'connection_id', 'id'), ('person_connections', 'owner_id', 'owner_id'),
                   ('subject_experiences', 'owner_id', 'owner_id'), ('subject_experiences', 'subject_experience_id', 'id')]
    assert client.app.state.service.relation_source_store == 'link_table'  # SQLite 的結構一定含 010


def test_post_writes_link_table_and_get_reads_it_in_order(client):
    w = world(client, 'rs_post')
    response = connect(client, w, source_experience_ids=[w['e2'], w['e1'], w['e2']])
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == LINK_KEYS
    assert body['source_experience_ids'] == [w['e2'], w['e1']] and body['source_person_experience_ids'] == [] and body['revision'] == 1
    assert rows(client, body['id']) == [(w['e2'], None, 1), (w['e1'], None, 2)]
    assert jsonb(client, body['id']) == '[]'  # 舊 JSONB 欄 NOT NULL 無預設：新列只放空陣列，不再當來源
    got = client.get(f"/api/connections/{body['id']}")
    assert got.status_code == 200 and got.json() == body
    for side in ('a', 'b'):
        item = overview_connection(client, w[side]['id'], body['id'])
        assert item['source_experience_ids'] == [w['e2'], w['e1']] and item['source_person_experience_ids'] == [] and item['revision'] == 1


def test_reads_ignore_a_diverged_jsonb_snapshot(client):
    w = world(client, 'rs_snapshot')
    body = connect(client, w, source_experience_ids=[w['e1']]).json()
    with client.app.state.service.db.connect(write=True) as c:
        c.execute('UPDATE person_connections SET source_experience_ids=? WHERE id=?', (json.dumps([w['e2']]), body['id']))
    assert client.get(f"/api/connections/{body['id']}").json()['source_experience_ids'] == [w['e1']]
    assert overview_connection(client, w['a']['id'], body['id'])['source_experience_ids'] == [w['e1']]
    edited = patch(client, body['id'], 'p-1', 1, label='新說明')
    assert edited.status_code == 200, edited.text
    assert jsonb(client, body['id']) == json.dumps([w['e2']])  # 寫入也不會碰舊快照


def test_person_experience_sources_validation_and_rollback(client):
    w = world(client, 'rs_person_exp')
    owner = w['owner']
    s1 = person_experience(client, owner, 's-1', [(w['a']['id'], 'subject', 0)])
    s2 = person_experience(client, owner, 's-2', [(w['c']['id'], 'subject', 0), (w['b']['id'], 'participant', 1)])
    mentioned = person_experience(client, owner, 's-3', [(w['c']['id'], 'subject', 0), (w['a']['id'], 'mentioned', 0)])
    archived = person_experience(client, owner, 's-4', [(w['a']['id'], 'subject', 0)], status='archived')
    ok = connect(client, w, source_experience_ids=[w['e1']], source_person_experience_ids=[s2, s1])
    assert ok.status_code == 201, ok.text
    assert ok.json()['source_person_experience_ids'] == [s2, s1] and ok.json()['source_experience_ids'] == [w['e1']]
    assert rows(client, ok.json()['id']) == [(w['e1'], None, 1), (None, s2, 1), (None, s1, 2)]
    for bad, status, code in ((mentioned, 422, 'unrelated_source'), (archived, 422, 'archived_source'), ('missing', 404, 'not_found')):
        before = rows(client, ok.json()['id'])
        refused = patch(client, ok.json()['id'], 'bad-' + bad, 1, source_person_experience_ids=[s1, bad])
        assert refused.status_code == status and refused.json()['error']['code'] == code, refused.text
        assert rows(client, ok.json()['id']) == before  # 驗證失敗不留下部分寫入
    assert client.get(f"/api/connections/{ok.json()['id']}").json()['revision'] == 1


def test_patch_add_replace_clear_keep_and_revision(client):
    w = world(client, 'rs_patch')
    s1 = person_experience(client, w['owner'], 'p-s1', [(w['b']['id'], 'subject', 0)])
    cid = connect(client, w, source_experience_ids=[w['e1'], w['e2']]).json()['id']
    added = patch(client, cid, 'p-add', 1, source_person_experience_ids=[s1])
    assert added.status_code == 200, added.text
    assert added.json()['source_experience_ids'] == [w['e1'], w['e2']] and added.json()['source_person_experience_ids'] == [s1]
    assert added.json()['revision'] == 2
    replaced = patch(client, cid, 'p-replace', 2, source_experience_ids=[w['e2'], w['e1']])
    assert replaced.json()['source_experience_ids'] == [w['e2'], w['e1']] and replaced.json()['source_person_experience_ids'] == [s1]
    cleared = patch(client, cid, 'p-clear', 3, source_experience_ids=[])
    assert cleared.json()['source_experience_ids'] == [] and cleared.json()['source_person_experience_ids'] == [s1]
    label = patch(client, cid, 'p-label', 4, label='只改說明')
    assert label.json()['label'] == '只改說明' and label.json()['source_person_experience_ids'] == [s1] and label.json()['revision'] == 5
    assert rows(client, cid) == [(None, s1, 1)]
    stale = patch(client, cid, 'p-stale', 4, label='過期')
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'stale_revision'
    again = patch(client, cid, 'p-add', 1, source_person_experience_ids=[s1])
    assert again.status_code == 200 and again.json() == added.json()  # 同代碼同內容：回原結果，不再寫入
    conflict = patch(client, cid, 'p-add', 1, source_person_experience_ids=[])
    assert conflict.status_code == 409 and conflict.json()['error']['code'] == 'idempotency_conflict'
    empty = patch(client, cid, 'p-empty', 5)
    assert empty.status_code == 422 and empty.json()['error']['code'] == 'empty_patch'
    assert client.get(f'/api/connections/{cid}').json()['revision'] == 5


def test_post_upsert_replaces_sent_type_keeps_the_other_and_bumps_revision(client):
    w = world(client, 'rs_upsert')
    s1 = person_experience(client, w['owner'], 'u-s1', [(w['a']['id'], 'subject', 0)])
    first = connect(client, w, source_experience_ids=[w['e1']], source_person_experience_ids=[s1]).json()
    reverse = client.post(f"/api/people/{w['b']['id']}/connections",
                          json={'request_id': 'c-2', 'other_person_id': w['a']['id'], 'label': '反向更新', 'source_experience_ids': [w['e2']]})
    assert reverse.status_code == 201, reverse.text
    body = reverse.json()
    assert body['id'] == first['id'] and body['label'] == '反向更新' and body['revision'] == 2
    assert body['source_experience_ids'] == [w['e2']] and body['source_person_experience_ids'] == [s1]
    retry = connect(client, w, source_experience_ids=[w['e1']], source_person_experience_ids=[s1])
    assert retry.json() == first  # 原請求重送回原結果


def test_old_format_request_keeps_its_original_fingerprint(client):
    """舊用戶端的請求指紋不因新增欄位而改變，部署前已存的重送紀錄仍有效。"""
    w = world(client, 'rs_fingerprint')
    old = {'request_id': 'legacy-1', 'other_person_id': w['b']['id'], 'label': '舊格式', 'source_experience_ids': [w['e1']]}
    assert client.post(f"/api/people/{w['a']['id']}/connections", json=old).status_code == 201
    with client.app.state.service.db.connect() as c:
        stored = c.execute("SELECT fingerprint FROM requests WHERE request_id='legacy-1'").fetchone()[0]
    assert stored == hashlib.sha256(encoded(old).encode()).hexdigest()


def test_cross_owner_cannot_read_patch_or_cite(client):
    w = world(client, 'rs_owner_a')
    s1 = person_experience(client, w['owner'], 'o-s1', [(w['a']['id'], 'subject', 0)])
    cid = connect(client, w, source_experience_ids=[w['e1']]).json()['id']
    other = TestClient(client.app)
    x = world(other, 'rs_owner_b')
    assert other.get(f'/api/connections/{cid}').status_code == 404
    assert patch(other, cid, 'x-1', 1, label='盜改').status_code == 404
    assert connect(other, x, request_id='x-2', source_experience_ids=[w['e1']]).status_code == 404
    assert connect(other, x, request_id='x-3', source_person_experience_ids=[s1]).status_code == 404
    assert client.get(f'/api/connections/{cid}').json()['revision'] == 1


def test_relationship_and_experience_counts_are_unchanged_by_source_edits(client):
    """來源只動關聯表：關係與兩類經歷筆數、積分帳本都不變。"""
    w = world(client, 'rs_counts')
    s1 = person_experience(client, w['owner'], 'n-s1', [(w['a']['id'], 'subject', 0)])
    cid = connect(client, w, source_experience_ids=[w['e1']]).json()['id']

    def counts():
        with client.app.state.service.db.connect() as c:
            return {t: c.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]
                    for t in ('person_connections', 'experiences', 'subject_experiences', 'subject_experience_people', 'reward_ledger', 'interaction_events')}
    before = counts()
    patch(client, cid, 'n-1', 1, source_person_experience_ids=[s1], source_experience_ids=[w['e2'], w['e1']])
    patch(client, cid, 'n-2', 2, source_experience_ids=[])
    assert counts() == before


def legacy_app(tmp_path, drop_link_table):
    app = create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                     clock=lambda: datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc))  # 與 conftest 的 app 相同的固定時鐘
    app.state.service.relation_source_store = relation_sources.LEGACY
    if drop_link_table:  # 模擬 Migration 010 之前的 PostgreSQL：沒有關聯表
        with app.state.service.db.connect(write=True) as c:
            c.execute('DROP TABLE person_connection_experience_sources')
    return app


def test_legacy_mode_before_migration_keeps_jsonb_behaviour(tmp_path):
    with TestClient(legacy_app(tmp_path, True)) as client:
        w = world(client, 'rs_legacy')
        response = connect(client, w, source_experience_ids=[w['e1'], w['e2']])
        assert response.status_code == 201, response.text
        assert set(response.json()) == LEGACY_KEYS  # 010 前的回應原樣保留（來源欄是資料庫的 JSON 文字）
        assert json.loads(response.json()['source_experience_ids']) == [w['e1'], w['e2']]
        assert json.loads(jsonb(client, response.json()['id'])) == [w['e1'], w['e2']]
        assert overview_connection(client, w['a']['id'], response.json()['id'])['source_experience_ids'] == [w['e1'], w['e2']]
        got = client.get(f"/api/connections/{response.json()['id']}").json()
        assert set(got) == LEGACY_KEYS and got['source_experience_ids'] == [w['e1'], w['e2']]  # 新的 GET 一律回 ID 陣列
        refused = connect(client, w, request_id='c-9', source_person_experience_ids=['s-x'])
        assert refused.status_code == 409 and refused.json()['error']['code'] == 'relation_link_table_not_enabled'
        assert connect(client, w, request_id='c-10', source_person_experience_ids=[]).status_code == 201  # 空陣列沒有東西要存
        edit = patch(client, response.json()['id'], 'p-1', 1, label='x')
        assert edit.status_code == 409 and edit.json()['error']['code'] == 'relation_link_table_not_enabled'


def test_legacy_mode_after_migration_stops_relation_writes(tmp_path):
    """Migration 已建立關聯表，但服務還沒切換：停止關係寫入，舊快照不再分岔；讀取照舊。"""
    with TestClient(legacy_app(tmp_path, False)) as client:
        w = world(client, 'rs_switch')
        refused = connect(client, w, source_experience_ids=[w['e1']])
        assert refused.status_code == 503 and refused.json()['error']['code'] == 'relation_source_switch_pending'
        assert client.get(f"/api/people/{w['a']['id']}/overview").status_code == 200
        with client.app.state.service.db.connect() as c:
            assert c.execute('SELECT COUNT(*) FROM person_connections').fetchone()[0] == 0


def test_ready_requires_the_link_table_in_link_mode(client):
    assert client.get('/ready').status_code == 200
    with client.app.state.service.db.connect(write=True) as c:
        c.execute('DROP TABLE person_connection_experience_sources')
    assert client.get('/ready').status_code == 503  # 連結模式卻沒有關聯表：明確報未就緒，不退回 JSONB
    assert client.get('/api/capabilities').json()['relation_sources'] == 'link_table'


@pytest.mark.parametrize('value,expected', [('legacy_jsonb', 'legacy_jsonb'), ('link_table', 'link_table')])
def test_store_setting_is_explicit(monkeypatch, tmp_path, value, expected):
    monkeypatch.setenv('LIFEWORLD_RELATION_SOURCE_STORE', value)
    assert create_app(data_dir=tmp_path).state.service.relation_source_store == expected


def test_unknown_store_setting_refuses_to_start(monkeypatch, tmp_path):
    monkeypatch.setenv('LIFEWORLD_RELATION_SOURCE_STORE', 'jsonb_and_table')
    with pytest.raises(ValueError, match='relation source store'):
        create_app(data_dir=tmp_path)


def test_postgres_defaults_to_legacy_until_migration_is_accepted():
    assert relation_sources.default_store('postgresql') == 'legacy_jsonb'
    assert relation_sources.default_store('sqlite') == 'link_table'
