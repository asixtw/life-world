"""人物經歷（Unified Person E1）在 Cloud SQL 上的 API 驗收：Local 8030 → Cloud Run e2e → life_world_e2e（PostgreSQL 18.6）。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號、人物、我的經歷與人物經歷）：

    LW_E2E_PERSONS=1 .venv\\Scripts\\python.exe -m pytest -q tests/test_person_experiences_cloudsql_e2e.py

驗收重點：真實寫入 subject_experiences／subject_experience_people；很早的年代（西元 208 年）與各種時間精度在 PostgreSQL 的存取；
主體與參與人物兩邊都看得到；編輯、Revision 衝突、重送；封存與恢復；已封存人物的限制；Owner 隔離；不計積分、不自動建立關係。
"""
import os

import pytest

from test_person_relations_cloudsql_e2e import record
from test_persons_cloudsql_e2e import account, create, preflight  # noqa: F401（preflight 是 autouse fixture）
from test_relation_sources_cloudsql_e2e import Client

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS') != '1', reason='部署後以 LW_E2E_PERSONS=1 對 Local 8030（Cloud SQL E2E）執行')
KEYS = {'id', 'owner_id', 'revision', 'status', 'title', 'content', 'experience_type', 'origin_type', 'occurred_precision', 'occurred_on',
        'occurred_label', 'created_at', 'updated_at', 'subject', 'participants'}


def add(client, subject, request_id, **body):
    payload = {'request_id': request_id, 'subject_person_id': subject['id'], 'content': '平定江東，建立基業。', 'experience_type': 'historical', **body}
    return client.call('POST', '/person-experiences', payload)


def patch(client, experience_id, request_id, expected_revision, **body):
    return client.call('PATCH', f'/person-experiences/{experience_id}', {'request_id': request_id, 'expected_revision': expected_revision, **body})


def tab(client, person, archived=False):
    return client.ok('GET', f"/persons/{person['id']}/experiences" + ('?archived=true' if archived else ''))


def set_person_status(client, person, request_id, status):
    current = client.ok('GET', f"/persons/{person['id']}")['person']
    return client.ok('POST', f"/persons/{person['id']}/status", {'request_id': request_id, 'expected_revision': current['revision'], 'status': status})


def test_person_experiences_on_cloud_sql():
    c, username, password = account('exp')
    zhou = create(c, '周瑜', 'exp-a', person_subtype='historical', description='東吳軍事統帥')
    sun = create(c, '孫策', 'exp-b', person_subtype='historical', description='江東之主')
    lu = create(c, '魯肅', 'exp-c', person_subtype='historical')
    real = create(c, '王小明', 'exp-d', description='認識的同事')
    mine = record(c, real, 1)  # 一筆我的經歷（與王小明有關）
    before = c.ok('GET', '/state')['rewards']

    # 新增：主體＋兩位參與人物；很早的年代只知道年份
    code, item = add(c, zhou, 'exp-1', participant_ids=[sun['id'], lu['id']], title='平定江東', occurred_precision='year', occurred_on='208',
                     occurred_label='建安十三年')
    assert code == 201 and set(item) == KEYS, item
    assert (item['title'], item['experience_type'], item['origin_type'], item['status'], item['revision']) == ('平定江東', 'historical', 'manual', 'active', 1)
    assert (item['occurred_precision'], item['occurred_on'], item['occurred_label']) == ('year', '0208', '建安十三年')
    assert item['subject']['id'] == zhou['id'] and sorted(p['name'] for p in item['participants']) == ['孫策', '魯肅']
    assert c.ok('GET', f"/person-experiences/{item['id']}") == item
    assert add(c, zhou, 'exp-1', participant_ids=[sun['id'], lu['id']], title='平定江東', occurred_precision='year', occurred_on='208',
               occurred_label='建安十三年') == (201, item)  # 同一請求重送：不另建一筆

    # 各種時間精度在 PostgreSQL 的存取；可以只有主體
    for request_id, precision, on, expected in (('exp-2', 'month', '208-12', '0208-12'), ('exp-3', 'day', '0199-06-01', '0199-06-01'),
                                                ('exp-4', 'day', '2026-02-28', '2026-02-28'), ('exp-5', 'unknown', None, None)):
        code, other = add(c, zhou, request_id, title=request_id, occurred_precision=precision, occurred_on=on)
        assert code == 201 and (other['occurred_precision'], other['occurred_on'], other['participants']) == (precision, expected, []), other
        assert c.ok('GET', f"/person-experiences/{other['id']}")['occurred_on'] == expected

    # 兩邊都看得到：主體與參與人物的頁面是同一筆；排序是知道時間的在前（新到舊），不知道的最後
    listed = tab(c, zhou)['person_experiences']
    assert (listed['total'], listed['archived_total']) == (5, 0)
    assert [x['title'] for x in listed['items']] == ['exp-4', 'exp-2', '平定江東', 'exp-3', 'exp-5']
    assert all(x['role'] == 'subject' for x in listed['items'])
    for person in (sun, lu):
        seen = tab(c, person)['person_experiences']
        assert seen['total'] == 1 and seen['items'][0]['id'] == item['id'] and seen['items'][0]['role'] == 'participant'
    # 我的經歷與人物經歷分開；不計積分、不進我的經歷、不自動建立關係、不改人物設定
    assert tab(c, zhou)['records'] == {'items': [], 'total': 0}
    records = tab(c, real)['records']
    assert records['total'] == 1 and records['items'][0]['id'] == mine and tab(c, real)['person_experiences']['total'] == 0
    assert c.ok('GET', '/state')['rewards'] == before
    detail = c.ok('GET', f"/persons/{zhou['id']}")
    assert detail['connections'] == [] and detail['profile'] is None and detail['experiences'] == {'mine': 0, 'person_experiences': 5}

    # 輸入驗證：失敗不留下資料
    for key, body, status in (('blank', {'content': '   '}, 422), ('type', {'experience_type': 'legend'}, 422),
                              ('date-1', {'occurred_precision': 'year'}, 422), ('date-2', {'occurred_precision': 'day', 'occurred_on': '2026-02-30'}, 422),
                              ('date-3', {'occurred_on': '208'}, 422), ('self', {'participant_ids': [zhou['id']]}, 422),
                              ('many', {'participant_ids': [f'p{i}' for i in range(51)]}, 422), ('missing', {'participant_ids': ['missing']}, 404)):
        code, error = add(c, zhou, 'exp-bad-' + key, **body)
        assert code == status, (key, error)
    assert tab(c, zhou)['person_experiences']['total'] == 5

    # 編輯、Revision 衝突、重送
    change = {'title': '平定江東之戰', 'content': '與孫策平定江東。', 'occurred_precision': 'month', 'occurred_on': '208-12', 'occurred_label': '建安十三年冬',
              'participant_ids': [sun['id']]}
    code, edited = patch(c, item['id'], 'exp-edit-1', 1, **change)
    assert code == 200, edited
    assert (edited['title'], edited['content'], edited['occurred_precision'], edited['occurred_on'], edited['occurred_label'], edited['revision']) == \
        ('平定江東之戰', '與孫策平定江東。', 'month', '0208-12', '建安十三年冬', 2)
    assert [p['name'] for p in edited['participants']] == ['孫策'] and edited['experience_type'] == 'historical'
    assert tab(c, lu)['person_experiences']['total'] == 0
    code, stale = patch(c, item['id'], 'exp-edit-2', 1, title='過期版本')
    assert code == 409 and stale['error']['code'] == 'stale_revision', stale
    assert patch(c, item['id'], 'exp-edit-1', 1, **change) == (200, edited)
    assert patch(c, item['id'], 'exp-edit-3', 2, experience_type='fictional')[0] == 422  # 性質建立後不能改
    code, cleared = patch(c, item['id'], 'exp-edit-4', 2, occurred_precision='unknown', occurred_label='')
    assert code == 200 and (cleared['occurred_precision'], cleared['occurred_on'], cleared['occurred_label'], cleared['revision']) == ('unknown', None, '', 3)

    # 封存與恢復（不刪除）；已封存的經歷唯讀
    code, archived = patch(c, item['id'], 'exp-arch-1', 3, status='archived')
    assert code == 200 and (archived['status'], archived['revision']) == ('archived', 4), archived
    for person, total in ((zhou, 4), (sun, 0)):
        seen = tab(c, person)['person_experiences']
        assert (seen['total'], seen['archived_total']) == (total, 1)
        assert [x['id'] for x in tab(c, person, archived=True)['person_experiences']['items']] == [item['id']]
    for request_id, body in (('exp-arch-2', {'title': '封存後修改'}), ('exp-arch-3', {'status': 'archived'})):
        code, error = patch(c, item['id'], request_id, 4, **body)
        assert code == 409 and error['error']['code'] == 'experience_archived', error
    code, restored = patch(c, item['id'], 'exp-arch-4', 4, status='active')
    assert code == 200 and (restored['status'], restored['title'], restored['revision']) == ('active', '平定江東之戰', 5)
    assert [p['name'] for p in restored['participants']] == ['孫策']

    # 已封存的人物：不能當主體或新加入；原本的參與人物保留；主體封存後整筆唯讀
    set_person_status(c, lu, 'exp-lu-1', 'archived')
    for request_id, subject, body in (('exp-lu-2', lu, {}), ('exp-lu-3', zhou, {'participant_ids': [lu['id']]})):
        code, error = add(c, subject, request_id, **body)
        assert code == 409 and error['error']['code'] == 'person_archived', error
    code, error = patch(c, item['id'], 'exp-lu-4', 5, participant_ids=[sun['id'], lu['id']])
    assert code == 409 and error['error']['code'] == 'person_archived', error
    set_person_status(c, sun, 'exp-sun-1', 'archived')
    code, kept = patch(c, item['id'], 'exp-sun-2', 5, title='參與人物封存後仍可修改')
    assert code == 200 and [(p['name'], p['status']) for p in kept['participants']] == [('孫策', 'archived')], kept
    set_person_status(c, zhou, 'exp-zhou-1', 'archived')
    for request_id, body in (('exp-zhou-2', {'title': '主體封存後修改'}), ('exp-zhou-3', {'status': 'archived'})):
        code, error = patch(c, item['id'], request_id, 6, **body)
        assert code == 409 and error['error']['code'] == 'person_archived', error
    assert tab(c, zhou)['person_experiences']['total'] == 5
    set_person_status(c, zhou, 'exp-zhou-4', 'active')

    # Owner 隔離
    other, _, _ = account('expx')
    stranger = create(other, '陌生人', 'expx-p')
    assert other.call('GET', f"/person-experiences/{item['id']}")[0] == 404
    assert patch(other, item['id'], 'expx-1', 6, title='盜改')[0] == 404
    assert patch(other, item['id'], 'expx-2', 6, status='archived')[0] == 404
    assert other.call('GET', f"/persons/{zhou['id']}/experiences")[0] == 404
    assert add(other, zhou, 'expx-3')[0] == 404
    assert add(other, stranger, 'expx-4', participant_ids=[zhou['id']])[0] == 404
    assert tab(other, stranger)['person_experiences'] == {'items': [], 'total': 0, 'archived_total': 0}
    assert c.ok('GET', f"/person-experiences/{item['id']}") == kept  # 沒有被動到

    again = Client()  # 新的工作階段重新登入：資料在 Cloud SQL
    again.ok('POST', '/auth/login', {'username': username, 'password': password})
    titles = [x['title'] for x in tab(again, zhou)['person_experiences']['items']]
    assert sorted(titles) == sorted(['exp-4', 'exp-2', 'exp-3', 'exp-5', '參與人物封存後仍可修改']), titles
    assert again.ok('GET', '/state')['rewards'] == before
