"""人物經歷 E2／E3 在 Cloud SQL 上的 API 驗收：Local 8030 → Cloud Run e2e → life_world_e2e（PostgreSQL 18.6）。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號、人物、我的經歷、人物經歷與關係）：

    LW_E2E_PERSONS=1 .venv\\Scripts\\python.exe -m pytest -q tests/test_person_experiences_records_cloudsql_e2e.py

驗收重點：紀錄頁的人物經歷總列表與人物頁是同一批資料；關係可以引用人物經歷（沿用 person_connection_experience_sources），
原有的我的經歷來源與順序不遺失；不相關或已封存的來源被拒絕；Revision 檢查；Owner 隔離；我的經歷與積分不受影響。
"""
import os

import pytest

from test_person_experiences_cloudsql_e2e import add, patch, tab
from test_person_relations_cloudsql_e2e import record
from test_persons_cloudsql_e2e import account, create, preflight  # noqa: F401（preflight 是 autouse fixture）

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS') != '1', reason='部署後以 LW_E2E_PERSONS=1 對 Local 8030（Cloud SQL E2E）執行')


def relation_patch(client, connection_id, request_id, expected_revision, **body):
    return client.call('PATCH', f'/connections/{connection_id}', {'request_id': request_id, 'expected_revision': expected_revision, **body})


def test_records_list_and_relation_sources_on_cloud_sql():
    c, _, _ = account('rec')
    zhou = create(c, '周瑜', 'rec-a', person_subtype='historical', description='東吳軍事統帥')
    sun = create(c, '孫策', 'rec-b', person_subtype='historical', description='江東之主')
    lu = create(c, '魯肅', 'rec-c', person_subtype='historical')
    mine = record(c, zhou, 1)  # 一筆我的經歷（與周瑜有關）
    before = c.ok('GET', '/state')
    assert c.ok('GET', '/person-experiences') == {'items': [], 'total': 0, 'archived_total': 0}

    _, both = add(c, zhou, 'rec-1', title='平定江東', participant_ids=[sun['id']], occurred_precision='year', occurred_on='199')
    _, only_sun = add(c, sun, 'rec-2', content='孫策少年時的經歷，沒有標題。')
    _, unrelated = add(c, lu, 'rec-3', title='魯肅的事', occurred_precision='month', occurred_on='208-12')
    _, archived = add(c, zhou, 'rec-4', title='已封存的經歷')
    assert patch(c, archived['id'], 'rec-5', 1, status='archived')[0] == 200

    # 紀錄頁的總列表：與單筆讀取、人物頁是同一筆資料；知道時間的在前，不知道的最後；封存的另外列
    listed = c.ok('GET', '/person-experiences')
    assert [x['id'] for x in listed['items']] == [unrelated['id'], both['id'], only_sun['id']]
    assert (listed['total'], listed['archived_total']) == (3, 1)
    assert listed['items'][1] == c.ok('GET', f"/person-experiences/{both['id']}")
    assert [x['id'] for x in tab(c, sun)['person_experiences']['items']] == [both['id'], only_sun['id']]
    assert [x['id'] for x in c.ok('GET', '/person-experiences?archived=true')['items']] == [archived['id']]

    # 可引用的來源：我的經歷照舊；人物經歷只列未封存、且兩端至少一人是主體或參與人物的
    eligible = c.ok('GET', f"/persons/{zhou['id']}/connection-sources?other_person_id={sun['id']}")
    assert [item['id'] for item in eligible['items']] == [mine] and eligible['total'] == 1
    offered = eligible['person_experiences']
    assert [item['id'] for item in offered['items']] == [both['id'], only_sun['id']] and offered['total'] == 2
    assert offered['items'][0] == {'id': both['id'], 'title': '平定江東', 'experience_type': 'historical', 'occurred_precision': 'year',
                                   'occurred_on': '0199', 'occurred_label': '', 'subject': '周瑜'}

    # 建立關係：兩種來源一起保存，順序照送出的順序；雙方人物頁讀到同一組來源
    code, connection = c.call('POST', f"/people/{zhou['id']}/connections", {
        'request_id': 'rec-rel-1', 'other_person_id': sun['id'], 'relation_types': [{'kind': 'friend'}], 'description': '一同平定江東',
        'source_experience_ids': [mine], 'source_person_experience_ids': [only_sun['id'], both['id']]})
    assert code == 201, connection
    assert connection['source_experience_ids'] == [mine] and connection['source_person_experience_ids'] == [only_sun['id'], both['id']]
    for person in (zhou, sun):
        view = c.ok('GET', f"/persons/{person['id']}")['connections'][0]
        assert [s['id'] for s in view['sources']['experiences']] == [mine]
        assert [s['id'] for s in view['sources']['person_experiences']] == [only_sun['id'], both['id']]
        assert (view['sources']['person_experiences'][1]['title'], view['sources']['person_experiences'][1]['subject']) == ('平定江東', '周瑜')

    # 不相關、已封存或不存在的人物經歷不能引用；Revision 衝突；失敗不改動原本的來源
    for key, source_id, status, error_code in (('unrelated', unrelated['id'], 422, 'unrelated_source'), ('archived', archived['id'], 422, 'archived_source'),
                                               ('missing', 'no-such-experience', 404, 'not_found')):
        code, error = relation_patch(c, connection['id'], 'rec-rel-bad-' + key, 1, source_person_experience_ids=[source_id])
        assert code == status and error['error']['code'] == error_code, error
    code, stale = relation_patch(c, connection['id'], 'rec-rel-stale', 9, source_person_experience_ids=[both['id']])
    assert code == 409 and stale['error']['code'] == 'stale_revision', stale
    assert c.ok('GET', f"/connections/{connection['id']}")['source_person_experience_ids'] == [only_sun['id'], both['id']]
    # 只改人物經歷來源：我的經歷來源保留
    code, edited = relation_patch(c, connection['id'], 'rec-rel-2', 1, source_person_experience_ids=[both['id']])
    assert code == 200 and edited['source_experience_ids'] == [mine] and edited['source_person_experience_ids'] == [both['id']], edited
    # 只改我的經歷來源：人物經歷來源保留
    code, edited = relation_patch(c, connection['id'], 'rec-rel-3', 2, source_experience_ids=[])
    assert code == 200 and edited['source_experience_ids'] == [] and edited['source_person_experience_ids'] == [both['id']], edited

    # 共同參與不自動建立關係；我的經歷與積分不受影響
    assert c.ok('GET', f"/persons/{lu['id']}")['connections'] == []
    after = c.ok('GET', '/state')
    assert after['rewards'] == before['rewards'] and after['experiences'] == before['experiences']

    # Owner 隔離：另一個帳號看不到、也不能引用
    other, _, _ = account('recx')
    a = create(other, '甲', 'recx-a')
    b = create(other, '乙', 'recx-b')
    assert other.ok('GET', '/person-experiences') == {'items': [], 'total': 0, 'archived_total': 0}
    code, error = other.call('POST', f"/people/{a['id']}/connections", {'request_id': 'recx-1', 'other_person_id': b['id'], 'relation_types': [{'kind': 'friend'}],
                                                                        'description': 'x', 'source_person_experience_ids': [both['id']]})
    assert code == 404, error
    assert other.ok('GET', f"/persons/{a['id']}")['connections'] == []
