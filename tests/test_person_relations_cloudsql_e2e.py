"""Unified Person P4 在 Cloud SQL 上的 API 驗收：Local 8030 → Cloud Run e2e → life_world_e2e（PostgreSQL 18.6）。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號、人物、我的紀錄與關係）：

    LW_E2E_PERSONS=1 .venv\\Scripts\\python.exe -m pytest -q tests/test_person_relations_cloudsql_e2e.py

驗收項目（2026-11-11 指令）：新增關係、多選關係類型、編輯描述與類型、同一對人物重複建立防護、封存與恢復、
來源引用、Owner 隔離、Revision 衝突；另含任一端人物已封存的限制、舊 label 相容與舊關係頁一致、
類型上限（10 種可存、第 11 種與重複類型被拒）、舊格式（只有 label）對已存在的關係只覆蓋 label，不影響描述與類型。
關係來源 API 本身（link_table）已有既有驗收紀錄（life_world_e2e_010_api_acceptance_report.md），這裡不重跑。
"""
import os
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from test_persons_cloudsql_e2e import account, create, preflight  # noqa: F401（preflight 是 autouse fixture）
from test_relation_sources_cloudsql_e2e import Client

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS') != '1', reason='部署後以 LW_E2E_PERSONS=1 對 Local 8030（Cloud SQL E2E）執行')
TAIPEI = ZoneInfo('Asia/Taipei')
FLAT_KEYS = {'id', 'owner_id', 'person_a', 'person_b', 'label', 'revision', 'source_experience_ids', 'source_person_experience_ids',
             'relation_types', 'description', 'confirmation_status'}
DESCRIPTION = '兩人共同平定江東，建立長期合作及信任關係。'
KINDS = ['family', 'partner', 'friend', 'colleague', 'classmate', 'mentor', 'client', 'business', 'neighbor', 'rival', 'enemy', 'other']


def record(client, person, index):
    """為這位人物建立一筆已確認的「我的紀錄」；回傳紀錄 ID。發生時間取稍早的現在，避免本機與伺服器時鐘差造成未來時間。"""
    now = datetime.now(TAIPEI)
    moment = now - timedelta(minutes=2)
    if moment.date() != now.date():
        moment = now  # 剛過午夜：維持在今天（目標期間內）
    goal = client.goal
    d = client.ok('POST', '/experiences/drafts', {'raw_text': f'與{person["name"]}有關的紀錄 {index}。', 'occurred_at': moment.isoformat(), 'goal_id': goal['id'],
                                                  'person_id': person['id'], 'contributions': [{'action_id': goal['actions'][0]['id'], 'quantity': '0.5'}]})
    done = client.ok('POST', f"/drafts/{d['id']}/confirm", {'request_id': f'rel-confirm-{index}', 'expected_revision': d['revision'], 'summary': f'關係驗收紀錄 {index}',
                                                             'person_id': person['id'], 'contributions': d['contributions'], 'tasks': []})
    return done['experience_id']


def relate(client, person, other, request_id, **body):
    return client.call('POST', f"/people/{person['id']}/connections", {'request_id': request_id, 'other_person_id': other['id'], **body})


def patch(client, connection_id, request_id, expected_revision, **body):
    return client.call('PATCH', f'/connections/{connection_id}', {'request_id': request_id, 'expected_revision': expected_revision, **body})


def view(client, person, connection_id):
    return next(x for x in client.ok('GET', f"/persons/{person['id']}")['connections'] if x['id'] == connection_id)


def set_person_status(client, person, request_id, status):
    current = client.ok('GET', f"/persons/{person['id']}")['person']
    return client.ok('POST', f"/persons/{person['id']}/status", {'request_id': request_id, 'expected_revision': current['revision'], 'status': status})


def test_person_relations_on_cloud_sql():
    c, username, password = account('rel')
    a = create(c, '周瑜', 'rel-a', person_subtype='historical', description='東吳軍事統帥')
    b = create(c, '孫策', 'rel-b', person_subtype='historical', description='江東之主')
    twin = create(c, '周瑜', 'rel-twin', person_type='fictional', description='架空三國的現代企業家')  # 同名人物
    d = create(c, '諸葛亮', 'rel-d', person_subtype='historical')
    e1, e2, unrelated = record(c, a, 1), record(c, a, 2), record(c, d, 3)

    # 來源：只列與兩端至少一人有關的已確認紀錄
    eligible = c.ok('GET', f"/persons/{a['id']}/connection-sources?other_person_id={urllib.parse.quote(b['id'])}")
    assert {item['id'] for item in eligible['items']} == {e1, e2} and eligible['total'] == 2, eligible
    assert c.ok('GET', f"/persons/{a['id']}")['connections'] == []  # 共同紀錄不會自動建立關係

    # 新增：多選類型、共用描述、來源順序
    code, created = relate(c, a, b, 'rel-1', relation_types=[{'kind': 'friend'}, {'kind': 'colleague'}, {'kind': 'business'}],
                           description=DESCRIPTION, source_experience_ids=[e2, e1])
    assert code == 201 and set(created) == FLAT_KEYS, created
    assert created['relation_types'] == [{'kind': 'friend'}, {'kind': 'colleague'}, {'kind': 'business'}]
    assert (created['description'], created['label'], created['confirmation_status'], created['revision']) == (DESCRIPTION, DESCRIPTION, 'confirmed', 1)
    assert created['source_experience_ids'] == [e2, e1]
    cid = created['id']
    for mine, other in ((a, b), (b, a)):  # 兩位人物的詳細頁是同一筆關係、同一段描述
        item = view(c, mine, cid)
        assert (item['status'], item['text'], item['person']['id'], item['person']['name']) == ('active', DESCRIPTION, other['id'], other['name'])
        assert [s['id'] for s in item['sources']['experiences']] == [e2, e1] and item['sources']['experiences'][0]['summary'] == '關係驗收紀錄 2'
    assert [x['label'] for x in c.ok('GET', f"/people/{a['id']}/overview")['connections']] == [DESCRIPTION]  # 舊關係頁相容

    # 同一對人物重複建立：不覆蓋
    for request_id, person, other in (('rel-dup-1', a, b), ('rel-dup-2', b, a)):
        code, error = relate(c, person, other, request_id, relation_types=[{'kind': 'enemy'}], description='想蓋掉原本的內容')
        assert code == 409 and error['error']['code'] == 'connection_exists', error
    assert c.ok('GET', f'/connections/{cid}') == created
    code, replay = relate(c, a, b, 'rel-1', relation_types=[{'kind': 'friend'}, {'kind': 'colleague'}, {'kind': 'business'}],
                          description=DESCRIPTION, source_experience_ids=[e2, e1])
    assert code == 201 and replay == created  # 同一提交重送

    # 輸入驗證與來源限制：失敗不留下關係
    for key, body, status, error_code in (
            ('kind', {'relation_types': [{'kind': 'soulmate'}], 'description': 'x'}, 422, 'validation_error'),
            ('eleven', {'relation_types': [{'kind': kind} for kind in KINDS[:11]], 'description': 'x'}, 422, 'validation_error'),
            ('repeat', {'relation_types': [{'kind': 'friend'}, {'kind': 'friend'}], 'description': 'x'}, 422, 'validation_error'),
            ('empty', {'relation_types': [], 'description': ''}, 422, 'empty_relation'),
            ('source', {'relation_types': [{'kind': 'friend'}], 'description': '', 'source_experience_ids': [e1]}, 422, 'unrelated_source')):
        code, error = relate(c, b, twin, 'rel-bad-' + key, **body)
        assert code == status and error['error']['code'] == error_code, (key, error)
    assert c.ok('GET', f"/persons/{twin['id']}")['connections'] == []

    # 類型上限：10 種可以保存（第 11 種在上面被拒絕），順序照送出的順序
    code, ten = relate(c, b, d, 'rel-ten', relation_types=[{'kind': kind} for kind in KINDS[:10]], description='十種類型的關係')
    assert code == 201 and ten['relation_types'] == [{'kind': kind} for kind in KINDS[:10]], ten

    # 編輯描述與類型、Revision 衝突、重送
    code, edited = patch(c, cid, 'rel-edit-1', 1, relation_types=[{'kind': 'friend'}, {'kind': 'rival'}], description='亦敵亦友，彼此敬重。')
    assert code == 200 and edited['relation_types'] == [{'kind': 'friend'}, {'kind': 'rival'}], edited
    assert (edited['description'], edited['label'], edited['revision'], edited['source_experience_ids']) == ('亦敵亦友，彼此敬重。', '亦敵亦友，彼此敬重。', 2, [e2, e1])
    code, stale = patch(c, cid, 'rel-edit-2', 1, description='過期版本')
    assert code == 409 and stale['error']['code'] == 'stale_revision', stale
    assert patch(c, cid, 'rel-edit-1', 1, relation_types=[{'kind': 'friend'}, {'kind': 'rival'}], description='亦敵亦友，彼此敬重。') == (200, edited)
    code, sources = patch(c, cid, 'rel-edit-3', 2, source_experience_ids=[e1])
    assert code == 200 and sources['source_experience_ids'] == [e1] and sources['revision'] == 3 and sources['description'] == '亦敵亦友，彼此敬重。'
    assert view(c, b, cid)['text'] == '亦敵亦友，彼此敬重。'

    # 封存與恢復（不刪除）；已封存的關係唯讀
    code, archived = patch(c, cid, 'rel-arch-1', 3, confirmation_status='archived')
    assert code == 200 and archived['confirmation_status'] == 'archived' and archived['revision'] == 4, archived
    assert view(c, a, cid)['status'] == 'archived' and view(c, b, cid)['status'] == 'archived'
    assert c.ok('GET', f"/people/{a['id']}/overview")['connections'] == []
    for request_id, body in (('rel-arch-2', {'description': '封存後修改'}), ('rel-arch-3', {'confirmation_status': 'archived'})):
        code, error = patch(c, cid, request_id, 4, **body)
        assert code == 409 and error['error']['code'] == 'connection_archived', error
    code, error = relate(c, a, b, 'rel-dup-3', relation_types=[{'kind': 'friend'}], description='封存後重新建立')
    assert code == 409 and error['error']['code'] == 'connection_exists'
    code, restored = patch(c, cid, 'rel-arch-4', 4, confirmation_status='confirmed')
    assert code == 200 and restored['confirmation_status'] == 'confirmed' and restored['revision'] == 5
    assert (restored['description'], restored['relation_types'], restored['source_experience_ids']) == ('亦敵亦友，彼此敬重。', [{'kind': 'friend'}, {'kind': 'rival'}], [e1])
    assert view(c, a, cid)['status'] == 'active'

    # 任一端人物已封存：不能新增、修改、封存或恢復；讀取照常
    set_person_status(c, twin, 'rel-twin-archive', 'archived')
    code, error = relate(c, a, twin, 'rel-twin-1', relation_types=[{'kind': 'rival'}], description='與同名人物的關係')
    assert code == 409 and error['error']['code'] == 'person_archived', error
    set_person_status(c, twin, 'rel-twin-restore', 'active')
    code, twin_relation = relate(c, a, twin, 'rel-twin-2', relation_types=[{'kind': 'rival'}], description='與同名人物的關係')
    assert code == 201, twin_relation
    set_person_status(c, twin, 'rel-twin-archive-2', 'archived')
    for request_id, body in (('rel-twin-3', {'description': '人物封存後修改'}), ('rel-twin-4', {'confirmation_status': 'archived'})):
        code, error = patch(c, twin_relation['id'], request_id, 1, **body)
        assert code == 409 and error['error']['code'] == 'person_archived', error
    locked = view(c, a, twin_relation['id'])
    assert locked['person']['status'] == 'archived' and locked['status'] == 'active' and locked['revision'] == 1

    # 舊格式（只有 label）：相容；沒有描述時以 label 顯示，只改類型不會遺失 label
    code, legacy = relate(c, a, d, 'rel-legacy', label='在隆中認識', source_experience_ids=[unrelated])
    assert code == 201 and (legacy['description'], legacy['label'], legacy['relation_types']) == ('', '在隆中認識', []), legacy
    assert view(c, d, legacy['id'])['text'] == '在隆中認識'
    code, typed = patch(c, legacy['id'], 'rel-legacy-types', 1, relation_types=[{'kind': 'rival'}])
    assert code == 200 and (typed['label'], typed['description']) == ('在隆中認識', '') and view(c, a, legacy['id'])['text'] == '在隆中認識'

    # 舊關係頁的寫法（只有 label 的 POST）對已存在的關係仍是覆蓋 label；類型與描述不受影響
    code, again_legacy = relate(c, d, a, 'rel-legacy-again', label='舊關係頁再送一次', source_experience_ids=[unrelated])
    assert code == 201 and again_legacy['id'] == legacy['id'], again_legacy
    assert (again_legacy['label'], again_legacy['description'], again_legacy['relation_types'], again_legacy['revision'],
            again_legacy['source_experience_ids']) == ('舊關係頁再送一次', '', [{'kind': 'rival'}], 3, [unrelated]), again_legacy
    assert view(c, a, legacy['id'])['text'] == '舊關係頁再送一次'
    code, over = relate(c, d, b, 'rel-ten-legacy', label='舊關係頁的文字')
    assert code == 201 and over['id'] == ten['id'], over
    assert (over['label'], over['description'], over['relation_types']) == ('舊關係頁的文字', '十種類型的關係', ten['relation_types']), over
    assert view(c, b, ten['id'])['text'] == '十種類型的關係'  # 有描述時，人物頁仍以描述為主

    # Owner 隔離
    other, _, _ = account('relx')
    stranger = create(other, '陌生人', 'relx-p')
    assert relate(other, a, b, 'relx-1', relation_types=[{'kind': 'friend'}], description='x')[0] == 404
    assert relate(other, stranger, b, 'relx-2', relation_types=[{'kind': 'friend'}], description='x')[0] == 404
    assert patch(other, cid, 'relx-3', 5, description='盜改')[0] == 404
    assert patch(other, cid, 'relx-4', 5, confirmation_status='archived')[0] == 404
    assert other.call('GET', f"/persons/{a['id']}/connection-sources?other_person_id={urllib.parse.quote(b['id'])}")[0] == 404
    assert other.call('GET', f'/connections/{cid}')[0] == 404
    assert other.ok('GET', f"/persons/{stranger['id']}")['connections'] == []
    assert c.ok('GET', f'/connections/{cid}') == restored  # 沒有被動到

    again = Client()  # 新的工作階段重新登入：資料在 Cloud SQL
    again.ok('POST', '/auth/login', {'username': username, 'password': password})
    relations = {x['id']: x for x in again.ok('GET', f"/persons/{a['id']}")['connections']}
    assert set(relations) == {cid, twin_relation['id'], legacy['id']}
    assert (relations[cid]['text'], [t['kind'] for t in relations[cid]['relation_types']]) == ('亦敵亦友，彼此敬重。', ['friend', 'rival'])
