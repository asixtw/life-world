"""Unified Person P4：人物詳細頁的關係整合（新增、編輯、封存、恢復）的後端規則。

程式自帶的自動測試（開發時快速檢查）；完成依據是部署後在 Cloud SQL life_world_e2e 的實測
（tests/test_person_relations_cloudsql_e2e.py、browser_tests/test_persons_relations_ui.py）。

2026-11-11 產品裁決：
- 同一對人物只有一筆關係，描述（description）由雙方共用；舊 label 是相容欄位，沒有 description 才回退顯示 label。
- 關係類型選填、可複選（12 種白名單、最多 10 種）；本階段只讀寫 kind，已儲存的方向與起迄資料不得被清除。
- 新格式建立遇到已存在的關係回 409 connection_exists，不覆蓋；新關係的狀態是 confirmed，舊 unreviewed 不強制轉換。
- 封存用 confirmation_status='archived'（不刪除），已封存的關係唯讀、可恢復；任一端人物已封存時不能新增、修改、封存或恢復。
- 來源本階段只有「我的紀錄」：同帳號、已確認、與兩端至少一人有關。
"""
import json

import pytest
from fastapi.testclient import TestClient

from conftest import confirm_payload, draft, onboard, register

KINDS = ['family', 'partner', 'friend', 'colleague', 'classmate', 'mentor', 'client', 'business', 'neighbor', 'rival', 'enemy', 'other']
FLAT_KEYS = {'id', 'owner_id', 'person_a', 'person_b', 'label', 'revision', 'source_experience_ids', 'source_person_experience_ids',
             'relation_types', 'description', 'confirmation_status'}
VIEW_KEYS = {'id', 'revision', 'status', 'confirmation_status', 'person', 'relation_types', 'description', 'label', 'text',
             'source_experience_ids', 'source_person_experience_ids', 'sources'}


def world(client, username):
    """帳號、三位人物（周瑜、孫策、諸葛亮），兩筆與周瑜有關、一筆與諸葛亮有關的已確認紀錄。"""
    _, goal = onboard(client)
    register(client, username)
    people = [client.post('/api/persons', json={'request_id': f'{username}-{name}', 'name': name, 'description': name + '的簡介'}).json()
              for name in ('周瑜', '孫策', '諸葛亮')]
    records = []
    for index, person in enumerate((people[0], people[0], people[2])):
        d = draft(client, goal, person_id=person['id'], raw_text=f'與{person["name"]}有關的紀錄 {index + 1}。')
        done = client.post(f"/api/drafts/{d['id']}/confirm", json=confirm_payload(d, request_id=f'{username}-confirm-{index}', summary=f'紀錄 {index + 1}'))
        assert done.status_code == 201, done.text
        records.append(done.json()['experience_id'])
    return {'a': people[0], 'b': people[1], 'c': people[2], 'e1': records[0], 'e2': records[1], 'unrelated': records[2]}


def relate(client, person, other, request_id='r-1', **body):
    payload = {'request_id': request_id, 'other_person_id': other['id'], 'relation_types': [{'kind': 'friend'}], 'description': '一同平定江東', **body}
    return client.post(f"/api/people/{person['id']}/connections", json=payload)


def patch(client, connection_id, request_id, expected_revision, **body):
    return client.patch(f'/api/connections/{connection_id}', json={'request_id': request_id, 'expected_revision': expected_revision, **body})


def view(client, person, connection_id):
    return next(x for x in client.get(f"/api/persons/{person['id']}").json()['connections'] if x['id'] == connection_id)


def stored(client, connection_id):
    with client.app.state.service.db.connect() as c:
        return dict(c.execute('SELECT label,description,relation_types,confirmation_status,revision FROM person_connections WHERE id=?',
                              (connection_id,)).fetchone())


def archive_person(client, person, request_id='ap'):
    current = client.get(f"/api/persons/{person['id']}").json()['person']
    response = client.post(f"/api/persons/{person['id']}/status", json={'request_id': request_id, 'expected_revision': current['revision'],
                                                                         'status': 'archived' if current['status'] == 'active' else 'active'})
    assert response.status_code == 200, response.text


def test_create_with_types_description_and_sources_is_shared_by_both_people(client):
    w = world(client, 'rel_create')
    response = relate(client, w['a'], w['b'], relation_types=[{'kind': 'friend'}, {'kind': 'colleague'}], source_experience_ids=[w['e2'], w['e1']])
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == FLAT_KEYS
    assert body['relation_types'] == [{'kind': 'friend'}, {'kind': 'colleague'}] and body['description'] == '一同平定江東'
    assert body['label'] == '一同平定江東' and body['confirmation_status'] == 'confirmed' and body['revision'] == 1
    assert body['source_experience_ids'] == [w['e2'], w['e1']]
    row = stored(client, body['id'])
    assert json.loads(row['relation_types']) == [{'kind': 'friend'}, {'kind': 'colleague'}] and row['confirmation_status'] == 'confirmed'
    assert client.get(f"/api/connections/{body['id']}").json() == body
    for mine, other in ((w['a'], w['b']), (w['b'], w['a'])):  # 兩位人物的詳細頁看到同一筆關係與同一段描述
        item = view(client, mine, body['id'])
        assert set(item) == VIEW_KEYS and item['status'] == 'active' and item['text'] == '一同平定江東'
        assert item['person']['id'] == other['id'] and item['person']['name'] == other['name'] and item['person']['description'] == other['name'] + '的簡介'
        assert item['relation_types'] == [{'kind': 'friend'}, {'kind': 'colleague'}]
        assert [s['id'] for s in item['sources']['experiences']] == [w['e2'], w['e1']] and item['sources']['experiences'][0]['summary'] == '紀錄 2'
    legacy = client.get(f"/api/people/{w['a']['id']}/overview").json()['connections']  # 舊關係頁在淘汰前仍讀得到
    assert [(x['id'], x['label']) for x in legacy] == [(body['id'], '一同平定江東')]


def test_existing_pair_is_never_overwritten(client):
    w = world(client, 'rel_exists')
    first = relate(client, w['a'], w['b'], source_experience_ids=[w['e1']]).json()
    again = relate(client, w['a'], w['b'], request_id='r-2', description='想蓋掉原本的內容', relation_types=[{'kind': 'enemy'}])
    assert again.status_code == 409 and again.json()['error']['code'] == 'connection_exists', again.text
    reverse = relate(client, w['b'], w['a'], request_id='r-3', description='從另一邊建立')
    assert reverse.status_code == 409 and reverse.json()['error']['code'] == 'connection_exists'
    assert client.get(f"/api/connections/{first['id']}").json() == first  # 描述、類型、來源、版本都沒變
    replay = relate(client, w['a'], w['b'], source_experience_ids=[w['e1']])
    assert replay.status_code == 201 and replay.json() == first  # 同一提交重送：回原結果
    conflict = relate(client, w['a'], w['b'], description='同代碼不同內容', source_experience_ids=[w['e1']])
    assert conflict.status_code == 409 and conflict.json()['error']['code'] == 'idempotency_conflict'
    with client.app.state.service.db.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM person_connections').fetchone()[0] == 1


@pytest.mark.parametrize('body,code', [
    ({'relation_types': [{'kind': 'soulmate'}]}, 'validation_error'),
    ({'relation_types': [{'kind': 'friend'}, {'kind': 'friend'}]}, 'validation_error'),
    ({'relation_types': [{'kind': k} for k in KINDS[:11]]}, 'validation_error'),
    ({'relation_types': [{'kind': 'mentor', 'direction': 'to_other'}]}, 'validation_error'),  # 本階段不開放方向與起迄
    ({'relation_types': ['friend']}, 'validation_error'),
    ({'description': 'x' * 2001}, 'validation_error'),
    ({'relation_types': [], 'description': '   '}, 'empty_relation'),
])
def test_invalid_relation_input_is_rejected(client, body, code):
    w = world(client, 'rel_invalid')
    response = relate(client, w['a'], w['b'], **body)
    assert response.status_code == 422 and response.json()['error']['code'] == code, response.text
    assert client.get(f"/api/persons/{w['a']['id']}").json()['connections'] == []


def test_ten_types_are_allowed_and_types_or_description_alone_is_enough(client):
    w = world(client, 'rel_ten')
    ten = relate(client, w['a'], w['b'], relation_types=[{'kind': k} for k in KINDS[:10]], description='')
    assert ten.status_code == 201 and len(ten.json()['relation_types']) == 10 and ten.json()['description'] == '' and ten.json()['label'] == ''
    only_text = relate(client, w['a'], w['c'], request_id='r-2', relation_types=[], description='只有描述')
    assert only_text.status_code == 201 and only_text.json()['relation_types'] == []


def test_patch_edits_description_and_types_and_keeps_stored_direction_and_dates(client):
    w = world(client, 'rel_patch')
    cid = relate(client, w['a'], w['b'], relation_types=[{'kind': 'friend'}, {'kind': 'mentor'}]).json()['id']
    with client.app.state.service.db.connect(write=True) as c:  # 模擬既有 API 留下的方向與起迄資料
        c.execute('UPDATE person_connections SET relation_types=? WHERE id=?',
                  (json.dumps([{'kind': 'friend', 'since': '2018'}, {'kind': 'mentor', 'direction': 'a_to_b', 'until': '2020'}]), cid))
    edited = patch(client, cid, 'p-1', 1, relation_types=[{'kind': 'mentor'}, {'kind': 'rival'}], description='亦師亦敵')
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert set(body) == FLAT_KEYS and body['relation_types'] == [{'kind': 'mentor'}, {'kind': 'rival'}]
    assert (body['description'], body['label'], body['revision'], body['confirmation_status']) == ('亦師亦敵', '亦師亦敵', 2, 'confirmed')
    assert json.loads(stored(client, cid)['relation_types']) == [{'kind': 'mentor', 'direction': 'a_to_b', 'until': '2020'}, {'kind': 'rival'}]
    stale = patch(client, cid, 'p-2', 1, description='過期版本')
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'stale_revision'
    assert patch(client, cid, 'p-1', 1, relation_types=[{'kind': 'mentor'}, {'kind': 'rival'}], description='亦師亦敵').json() == body  # 重送
    empty = patch(client, cid, 'p-3', 2)
    assert empty.status_code == 422 and empty.json()['error']['code'] == 'empty_patch'
    nothing_left = patch(client, cid, 'p-4', 2, relation_types=[], description='')
    assert nothing_left.status_code == 422 and nothing_left.json()['error']['code'] == 'empty_relation'
    assert stored(client, cid)['revision'] == 2


def test_legacy_label_is_shown_when_there_is_no_description_and_is_not_lost(client):
    w = world(client, 'rel_legacy')
    legacy = client.post(f"/api/people/{w['a']['id']}/connections", json={'request_id': 'old-1', 'other_person_id': w['b']['id'], 'label': '創業交流會認識'})
    assert legacy.status_code == 201, legacy.text
    cid = legacy.json()['id']
    assert legacy.json()['description'] == '' and legacy.json()['relation_types'] == [] and legacy.json()['confirmation_status'] == 'confirmed'
    with client.app.state.service.db.connect(write=True) as c:  # 模擬部署前就存在的舊資料
        c.execute("UPDATE person_connections SET confirmation_status='unreviewed' WHERE id=?", (cid,))
    item = view(client, w['a'], cid)
    assert (item['text'], item['description'], item['label'], item['status']) == ('創業交流會認識', '', '創業交流會認識', 'active')
    typed = patch(client, cid, 'p-1', 1, relation_types=[{'kind': 'business'}])
    assert typed.status_code == 200, typed.text
    row = stored(client, cid)
    assert (row['label'], row['description'], row['confirmation_status']) == ('創業交流會認識', '', 'unreviewed')  # 舊說明保留、狀態不強制轉換
    assert view(client, w['a'], cid)['text'] == '創業交流會認識'
    rewritten = patch(client, cid, 'p-2', 2, description='在創業交流會認識，後來合作創業')
    assert rewritten.status_code == 200 and view(client, w['b'], cid)['text'] == '在創業交流會認識，後來合作創業'
    assert stored(client, cid)['label'] == '在創業交流會認識，後來合作創業'


def test_archive_hides_restores_and_never_deletes(client):
    w = world(client, 'rel_archive')
    cid = relate(client, w['a'], w['b']).json()['id']
    archived = patch(client, cid, 'x-1', 1, confirmation_status='archived')
    assert archived.status_code == 200 and archived.json()['confirmation_status'] == 'archived' and archived.json()['revision'] == 2
    assert view(client, w['a'], cid)['status'] == 'archived' and view(client, w['b'], cid)['status'] == 'archived'
    assert client.get(f"/api/people/{w['a']['id']}/overview").json()['connections'] == []  # 舊關係頁也不顯示已封存
    for request_id, body in (('x-2', {'description': '封存後修改'}), ('x-3', {'relation_types': [{'kind': 'rival'}]}),
                             ('x-4', {'source_experience_ids': [w['e1']]}), ('x-5', {'confirmation_status': 'archived'}),
                             ('x-6', {'confirmation_status': 'confirmed', 'description': '恢復同時修改'})):
        refused = patch(client, cid, request_id, 2, **body)
        assert refused.status_code == 409 and refused.json()['error']['code'] == 'connection_archived', (request_id, refused.text)
    again = relate(client, w['a'], w['b'], request_id='r-2', description='重新建立')
    assert again.status_code == 409 and again.json()['error']['code'] == 'connection_exists'  # 畫面改為提供恢復
    old_page = client.post(f"/api/people/{w['a']['id']}/connections", json={'request_id': 'old-2', 'other_person_id': w['b']['id'], 'label': '舊頁面覆蓋'})
    assert old_page.status_code == 409 and old_page.json()['error']['code'] == 'connection_archived'
    assert stored(client, cid) == {'label': '一同平定江東', 'description': '一同平定江東', 'relation_types': json.dumps([{'kind': 'friend'}]),
                                   'confirmation_status': 'archived', 'revision': 2}
    restored = patch(client, cid, 'x-7', 2, confirmation_status='confirmed')
    assert restored.status_code == 200 and restored.json()['confirmation_status'] == 'confirmed' and restored.json()['revision'] == 3
    assert view(client, w['a'], cid)['status'] == 'active'
    assert patch(client, cid, 'x-8', 3, description='恢復後可以修改').status_code == 200
    with client.app.state.service.db.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM person_connections').fetchone()[0] == 1


def test_archived_person_blocks_every_relation_write_but_not_reading(client):
    w = world(client, 'rel_person_archived')
    cid = relate(client, w['a'], w['b']).json()['id']
    archived_relation = relate(client, w['a'], w['c'], request_id='r-c').json()['id']
    assert patch(client, archived_relation, 'c-1', 1, confirmation_status='archived').status_code == 200
    archive_person(client, w['b'], 'ap-b')
    archive_person(client, w['c'], 'ap-c')
    for label, response in (
            ('edit', patch(client, cid, 'b-1', 1, description='人物封存後修改')),
            ('archive', patch(client, cid, 'b-2', 1, confirmation_status='archived')),
            ('restore', patch(client, archived_relation, 'c-2', 2, confirmation_status='confirmed')),
            ('old page', client.post(f"/api/people/{w['a']['id']}/connections", json={'request_id': 'old', 'other_person_id': w['b']['id'], 'label': '舊頁面'}))):
        assert response.status_code == 409 and response.json()['error']['code'] == 'person_archived', (label, response.text)
    d = client.post('/api/persons', json={'request_id': 'd', 'name': '魯肅'}).json()
    create = relate(client, d, w['b'], request_id='r-d')
    assert create.status_code == 409 and create.json()['error']['code'] == 'person_archived'
    item = view(client, w['a'], cid)  # 讀取不受限
    assert item['person']['status'] == 'archived' and item['status'] == 'active' and stored(client, cid)['revision'] == 1
    assert client.get(f"/api/persons/{w['b']['id']}").json()['connections'][0]['id'] == cid
    archive_person(client, w['b'], 'ap-b2')  # 恢復人物後即可調整
    assert patch(client, cid, 'b-3', 1, description='人物恢復後修改').status_code == 200


def test_sources_are_limited_to_confirmed_records_related_to_either_person(client):
    w = world(client, 'rel_sources')
    eligible = client.get(f"/api/persons/{w['a']['id']}/connection-sources", params={'other_person_id': w['b']['id']})
    assert eligible.status_code == 200, eligible.text
    assert {item['id'] for item in eligible.json()['items']} == {w['e1'], w['e2']} and eligible.json()['total'] == 2
    assert set(eligible.json()['items'][0]) == {'id', 'summary', 'occurred_at'}
    both = client.get(f"/api/persons/{w['a']['id']}/connection-sources", params={'other_person_id': w['c']['id']}).json()
    assert {item['id'] for item in both['items']} == {w['e1'], w['e2'], w['unrelated']}
    unrelated = relate(client, w['a'], w['b'], source_experience_ids=[w['e1'], w['unrelated']])
    assert unrelated.status_code == 422 and unrelated.json()['error']['code'] == 'unrelated_source'
    missing = relate(client, w['a'], w['b'], request_id='r-2', source_experience_ids=['no-such-record'])
    assert missing.status_code == 404
    too_many = relate(client, w['a'], w['b'], request_id='r-3', source_experience_ids=[f'x{i}' for i in range(31)])
    assert too_many.status_code == 422
    assert client.get(f"/api/persons/{w['a']['id']}").json()['connections'] == []  # 失敗不留下關係
    cid = relate(client, w['a'], w['b'], request_id='r-4', source_experience_ids=[w['e2'], w['e1']]).json()['id']
    cleared = patch(client, cid, 'p-1', 1, source_experience_ids=[])
    assert cleared.status_code == 200 and cleared.json()['source_experience_ids'] == [] and view(client, w['a'], cid)['sources'] == {'experiences': [], 'person_experiences': []}  # E3 起來源分兩種
    assert client.get(f"/api/persons/{w['a']['id']}/connection-sources", params={'other_person_id': w['a']['id']}).status_code == 422
    assert client.get(f"/api/persons/{w['a']['id']}/connection-sources", params={'other_person_id': 'no-such-person'}).status_code == 404


def test_other_account_cannot_create_edit_or_list_sources(client):
    w = world(client, 'rel_owner_a')
    cid = relate(client, w['a'], w['b'], source_experience_ids=[w['e1']]).json()['id']
    other = TestClient(client.app)
    x = world(other, 'rel_owner_b')
    assert relate(other, w['a'], w['b'], request_id='steal-1').status_code == 404
    assert relate(other, x['a'], w['b'], request_id='steal-2').status_code == 404
    assert relate(other, x['a'], x['b'], request_id='steal-3', source_experience_ids=[w['e1']]).status_code == 404
    assert patch(other, cid, 'steal-4', 1, description='盜改').status_code == 404
    assert patch(other, cid, 'steal-5', 1, confirmation_status='archived').status_code == 404
    assert other.get(f"/api/persons/{w['a']['id']}/connection-sources", params={'other_person_id': w['b']['id']}).status_code == 404
    assert other.get(f"/api/persons/{x['a']['id']}/connection-sources", params={'other_person_id': w['b']['id']}).status_code == 404
    assert other.get(f"/api/persons/{x['a']['id']}").json()['connections'] == []
    assert stored(client, cid)['revision'] == 1 and view(client, w['a'], cid)['text'] == '一同平定江東'


def test_shared_records_do_not_create_relations_and_followed_is_exposed_for_overview(client):
    w = world(client, 'rel_overview')
    assert client.get(f"/api/persons/{w['a']['id']}").json()['connections'] == []  # 有共同紀錄也不會自動建立關係
    client.patch(f"/api/persons/{w['c']['id']}", json={'expected_revision': 1, 'followed': True})
    relate(client, w['a'], w['b'])
    relate(client, w['a'], w['c'], request_id='r-2')
    items = client.get(f"/api/persons/{w['a']['id']}").json()['connections']
    assert [(x['person']['name'], x['person']['followed']) for x in items] == [('孫策', False), ('諸葛亮', True)]
