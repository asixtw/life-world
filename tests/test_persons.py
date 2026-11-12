"""Unified Person 新人物系統（第一、二階段）：/api/persons 列表、新增、編輯、封存與人物設定。

單元測試使用明確指定的 SQLite（結構含 Schema 010）。PostgreSQL 驗收要在 Local 8030 → Cloud SQL life_world_e2e 部署後執行，SQLite 不能代替。

產品規則：同名人物可並存、類型與分類全部選填、人物設定存在 notes(kind='preparation') 且只新增不覆寫、
不刪除任何人物、經歷不改人物設定、共同經歷不自動建立關係、帳號隔離。
"""
import itertools
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from conftest import confirm_payload, draft, onboard, register
from legacy_profile_support import save_legacy_profile
from app import persons as persons_module
from app import relation_sources
from app.config import DemoPolicy
from app.main import create_app

PERSON_KEYS = {'id', 'owner_id', 'name', 'aliases', 'person_type', 'person_subtype', 'description', 'roles', 'tags', 'category',
               'status', 'origin_type', 'followed', 'revision', 'created_at', 'notes', 'common_context'}  # 2.0 P2 承接舊欄位
PROFILE_KEYS = {'background', 'personality', 'motivation', 'stance', 'abilities', 'expression', 'behavior', 'knowledge_boundary', 'restrictions'}


def ready(client, username):
    _, goal = onboard(client)
    register(client, username)
    return goal


def create(client, name, request_id=None, **body):
    response = client.post('/api/persons', json={'request_id': request_id or ('p-' + name + str(len(body))), 'name': name, **body})
    return response


def test_capability_and_legacy_gate(client, tmp_path):
    assert client.get('/api/capabilities').json()['unified_people'] is True
    app = create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                     clock=lambda: datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc))
    app.state.service.relation_source_store = relation_sources.LEGACY  # 010 之前的 PostgreSQL：沒有 010 人物欄位
    with TestClient(app) as legacy:
        ready(legacy, 'persons_legacy')
        assert legacy.get('/api/capabilities').json()['unified_people'] is False
        refused = legacy.get('/api/persons')
        assert refused.status_code == 409 and refused.json()['error']['code'] == 'unified_people_not_enabled'


def test_same_name_people_are_separate_records(client):
    ready(client, 'persons_same_name')
    first = create(client, '王小明', 'r-1', description='同事')
    second = create(client, '王小明', 'r-2', description='鄰居')
    assert first.status_code == 201 and second.status_code == 201, (first.text, second.text)
    assert first.json()['id'] != second.json()['id'] and set(first.json()) == PERSON_KEYS
    edited = client.patch(f"/api/persons/{first.json()['id']}", json={'expected_revision': 1, 'description': '前同事'})
    assert edited.status_code == 200, edited.text
    assert client.get(f"/api/persons/{second.json()['id']}").json()['person']['description'] == '鄰居'  # 不互相覆蓋
    names = [p['name'] for p in client.get('/api/persons').json()['items']]
    assert names.count('王小明') == 2


@pytest.mark.parametrize('body,expected', [
    ({}, ('real', None)),
    ({'person_type': 'real'}, ('real', None)),
    ({'person_subtype': 'historical'}, ('real', 'historical')),
    ({'person_type': 'fictional'}, ('fictional', None)),
    ({'person_subtype': 'original'}, ('fictional', 'original')),
])
def test_type_is_optional_and_subtype_implies_type(client, body, expected):
    ready(client, 'persons_type')
    person = create(client, '人物', 'type-' + json.dumps(body), **body)
    assert person.status_code == 201, person.text
    assert (person.json()['person_type'], person.json()['person_subtype']) == expected
    assert person.json()['origin_type'] == 'manual' and person.json()['status'] == 'active' and person.json()['category'] == 'other'


@pytest.mark.parametrize('body,field', [
    ({'person_type': 'real', 'person_subtype': 'original'}, 'person_subtype'),
    ({'person_type': 'fictional', 'person_subtype': 'historical'}, 'person_subtype'),
    ({'person_type': 'robot'}, 'person_type'),
    ({'description': 'x' * 2001}, 'description'),
    ({'aliases': ['a'] * 21}, 'aliases'),
    ({'aliases': ['']}, 'aliases'),
])
def test_invalid_person_input_is_rejected(client, body, field):
    ready(client, 'persons_invalid')
    response = create(client, '人物', 'bad', **body)
    assert response.status_code == 422, response.text


def test_create_is_idempotent_and_aliases_are_cleaned(client):
    ready(client, 'persons_idem')
    body = {'request_id': 'same', 'name': '亞瑟', 'aliases': ['亞瑟王', ' 亞瑟王 ', 'Arthur'], 'person_type': 'fictional', 'tags': ['傳說']}
    first = client.post('/api/persons', json=body)
    again = client.post('/api/persons', json=body)
    assert first.status_code == 201 and again.json() == first.json()
    assert first.json()['aliases'] == ['亞瑟王', 'Arthur']
    conflict = client.post('/api/persons', json={**body, 'name': '梅林'})
    assert conflict.status_code == 409 and conflict.json()['error']['code'] == 'idempotency_conflict'
    assert len(client.get('/api/persons').json()['items']) == 1


def ticking_client(tmp_path):
    """每次讀時鐘都前進一秒：「最近建立」排序需要不同的建立時間（固定時鐘下全部相同）。"""
    ticks = itertools.count()
    start = datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc)
    return TestClient(create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                                 clock=lambda: start + timedelta(seconds=next(ticks))))


def test_list_search_filter_sort_and_archive(tmp_path):
    client = ticking_client(tmp_path)
    ready(client, 'persons_list')
    arthur = create(client, '亞瑟', 'a', aliases=['Arthur'], person_type='fictional', category='learning').json()
    merlin = create(client, '梅林', 'm', person_subtype='original', tags=['魔法師']).json()
    lin = create(client, '林老師', 'l', description='高中數學老師', category='learning').json()
    listing = lambda **q: [p['name'] for p in client.get('/api/persons', params=q).json()['items']]
    assert listing(q='arthur') == ['亞瑟'] and listing(q='魔法') == ['梅林'] and listing(q='數學') == ['林老師']
    assert set(listing(person_type='fictional')) == {'亞瑟', '梅林'} and listing(person_subtype='original') == ['梅林']
    assert set(listing(category='learning')) == {'亞瑟', '林老師'}
    assert listing(sort='name') == sorted(['亞瑟', '梅林', '林老師'], key=str.casefold)
    assert listing(sort='recent') == ['林老師', '梅林', '亞瑟']  # 最近建立的在前
    archived = client.post(f"/api/persons/{merlin['id']}/status", json={'request_id': 's-1', 'expected_revision': 1, 'status': 'archived'})
    assert archived.status_code == 200 and archived.json()['status'] == 'archived' and archived.json()['revision'] == 2
    assert '梅林' not in listing() and listing(status='archived') == ['梅林']
    assert client.get(f"/api/persons/{merlin['id']}").status_code == 200  # 封存後仍可讀
    restored = client.post(f"/api/persons/{merlin['id']}/status", json={'request_id': 's-2', 'expected_revision': 2, 'status': 'active'})
    assert restored.json()['status'] == 'active' and '梅林' in listing()
    with client.app.state.service.db.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM people').fetchone()[0] == 3  # 封存不刪除
    assert {arthur['id'], lin['id']} <= {p['id'] for p in client.get('/api/persons').json()['items']}


def test_edit_checks_revision_and_only_changes_sent_fields(client):
    ready(client, 'persons_edit')
    person = create(client, '陳', 'e', aliases=['阿陳'], tags=['朋友'], description='大學同學').json()
    edited = client.patch(f"/api/persons/{person['id']}", json={'expected_revision': 1, 'person_subtype': 'historical', 'aliases': []})
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert (body['person_type'], body['person_subtype'], body['aliases'], body['tags'], body['description'], body['revision']) == \
        ('real', 'historical', [], ['朋友'], '大學同學', 2)
    stale = client.patch(f"/api/persons/{person['id']}", json={'expected_revision': 1, 'name': '舊版'})
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'revision_conflict'
    assert client.patch(f"/api/persons/{person['id']}", json={'expected_revision': 2, 'name': None}).status_code == 422
    cleared = client.patch(f"/api/persons/{person['id']}", json={'expected_revision': 2, 'person_type': 'fictional', 'person_subtype': None})
    assert cleared.status_code == 200 and (cleared.json()['person_type'], cleared.json()['person_subtype']) == ('fictional', None)


def save_profile(client, person_id, request_id, expected, **fields):
    return save_legacy_profile(client, person_id, {'request_id': request_id, 'expected_profile_id': expected, 'fields': fields})


def test_profile_save_read_back_versioning_and_stale(client):
    ready(client, 'persons_profile')
    a = create(client, '甲', 'pa').json()
    b = create(client, '乙', 'pb').json()
    assert client.get(f"/api/persons/{a['id']}").json()['profile'] is None
    first = save_profile(client, a['id'], 'pf-1', None, background='在台南長大', personality='溫和')
    assert first.status_code == 200, first.text
    profile = first.json()
    assert set(profile['fields']) == PROFILE_KEYS and profile['fields']['background'] == '在台南長大' and profile['fields']['stance'] == ''
    assert profile['origin'] == 'manual' and profile['version'] == 1
    assert client.get(f"/api/persons/{a['id']}").json()['profile'] == profile
    second = save_profile(client, a['id'], 'pf-2', profile['id'], background='在台南長大', personality='溫和但堅定', restrictions='不談政治')
    assert second.status_code == 200 and second.json()['version'] == 2 and second.json()['fields']['restrictions'] == '不談政治'
    stale = save_profile(client, a['id'], 'pf-3', profile['id'], personality='覆蓋')
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'stale_profile'
    assert save_profile(client, a['id'], 'pf-2', profile['id'], background='在台南長大', personality='溫和但堅定', restrictions='不談政治').json() == second.json()
    assert client.get(f"/api/persons/{b['id']}").json()['profile'] is None  # 不影響其他人物
    with client.app.state.service.db.connect() as c:
        rows = c.execute("SELECT kind,title FROM notes WHERE person_id=?", (a['id'],)).fetchall()
    assert [tuple(r) for r in rows] == [('preparation', persons_module.PROFILE_TITLE)] * 2  # 只新增，舊版保留
    assert save_profile(client, a['id'], 'pf-4', second.json()['id'], personality='x' * 2001).status_code == 422
    assert save_legacy_profile(client, a['id'], {'request_id': 'pf-5', 'expected_profile_id': second.json()['id'],
                                                               'fields': {'unknown_field': 'x'}}).status_code == 422


def test_profile_notes_do_not_appear_in_legacy_notes_list(client):
    ready(client, 'persons_notes')
    a = create(client, '甲', 'n').json()
    save_profile(client, a['id'], 'n-1', None, background='背景')
    assert client.post('/api/notes', json={'person_id': a['id'], 'kind': 'preparation', 'title': '見面準備', 'content': '帶伴手禮'}).status_code == 201
    titles = [n['title'] for n in client.get(f"/api/people/{a['id']}/overview").json()['notes']]
    assert titles == ['見面準備']


def test_owner_isolation(client):
    ready(client, 'persons_owner_a')
    mine = create(client, '甲', 'o').json()
    save_profile(client, mine['id'], 'o-1', None, background='秘密背景')
    other = TestClient(client.app)
    ready(other, 'persons_owner_b')
    assert other.get(f"/api/persons/{mine['id']}").status_code == 404
    assert other.patch(f"/api/persons/{mine['id']}", json={'expected_revision': 1, 'name': '盜改'}).status_code == 404
    assert other.post(f"/api/persons/{mine['id']}/status", json={'request_id': 'x', 'expected_revision': 1, 'status': 'archived'}).status_code == 404
    assert save_profile(other, mine['id'], 'x-1', None, background='盜寫').status_code == 404
    assert other.get('/api/persons').json()['items'] == []
    assert client.get(f"/api/persons/{mine['id']}").json()['profile']['fields']['background'] == '秘密背景'


def test_legacy_people_are_readable_in_the_new_list(client):
    ready(client, 'persons_legacy_rows')
    old = client.post('/api/people', json={'name': '舊人物', 'roles': ['同事'], 'tags': ['公司'], 'category': 'business'}).json()
    with client.app.state.service.db.connect(write=True) as c:  # 模擬 010 前就存在的列：origin_type 由 Migration 預設為 legacy
        c.execute("UPDATE people SET origin_type='legacy' WHERE id=?", (old['id'],))
    item = next(p for p in client.get('/api/persons').json()['items'] if p['id'] == old['id'])
    assert (item['origin_type'], item['person_type'], item['roles'], item['tags'], item['category']) == ('legacy', 'real', ['同事'], ['公司'], 'business')
    detail = client.get(f"/api/persons/{old['id']}").json()
    assert detail['person']['name'] == '舊人物' and detail['profile'] is None


def test_experiences_do_not_change_profile_or_create_connections(client):
    goal = ready(client, 'persons_experience')
    a = create(client, '甲', 'xa').json()
    b = create(client, '乙', 'xb').json()
    profile = save_profile(client, a['id'], 'x-1', None, personality='安靜').json()
    d = draft(client, goal, person_id=a['id'])
    done = client.post(f"/api/drafts/{d['id']}/confirm", json=confirm_payload(d, request_id='x-confirm'))
    assert done.status_code == 201, done.text
    detail = client.get(f"/api/persons/{a['id']}").json()
    assert detail['profile'] == profile  # 經歷不改人物設定
    assert detail['experiences']['mine'] == 1 and detail['connections'] == []
    with client.app.state.service.db.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM person_connections').fetchone()[0] == 0  # 不因經歷自動建立關係
    assert client.get(f"/api/persons/{b['id']}").json()['experiences']['mine'] == 0


def test_detail_lists_connections_from_the_link_table(client):
    ready(client, 'persons_detail')
    a = create(client, '甲', 'da').json()
    b = create(client, '乙', 'db').json()
    link = client.post(f"/api/people/{a['id']}/connections", json={'request_id': 'c-1', 'other_person_id': b['id'], 'label': '大學同學'})
    assert link.status_code == 201, link.text
    connections = client.get(f"/api/persons/{a['id']}").json()['connections']
    assert [(x['label'], x['person']['id'], x['person']['name']) for x in connections] == [('大學同學', b['id'], '乙')]
    assert connections[0]['source_experience_ids'] == [] and connections[0]['revision'] == 1


def test_no_new_tables_or_character_cards(client):
    ready(client, 'persons_schema')
    a = create(client, '甲', 's').json()
    save_profile(client, a['id'], 's-1', None, background='背景')
    with client.app.state.service.db.connect() as c:
        assert c.execute("SELECT COUNT(*) FROM works WHERE kind='character_card'").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE '%person_profile%'").fetchone()[0] == 0
