"""人物經歷 E2／E3：紀錄頁的人物經歷總列表，以及人物關係引用人物經歷作為來源。

程式自帶的自動測試（開發時快速檢查）；完成依據是部署後在 Cloud SQL life_world_e2e 的實測。

2026-11-11 產品裁決：
- 紀錄頁有「我的經歷／人物經歷／全部」；人物經歷從紀錄頁與人物頁進入都是同一筆資料、同一套 API。
- 關係來源除了我的經歷，也可以引用人物經歷：同帳號、未封存、關係兩端至少一人是主體或參與人物；
  沿用 person_connection_experience_sources，原有來源與順序不因新增來源類型而遺失。
- 分類原則：我的經歷＝使用者實際參與的生活紀錄；人物經歷＝以人物為主體（真實／歷史／虛構）；作品內容不在這裡。
"""
from fastapi.testclient import TestClient

from test_person_experiences import KEYS, create, patch, world


def sources(client, person, other):
    response = client.get(f"/api/persons/{person['id']}/connection-sources?other_person_id={other['id']}")
    assert response.status_code == 200, response.text
    return response.json()


def test_records_page_lists_every_person_experience_known_dates_first(client):
    people, _ = world(client)
    zhou, sun = people['周瑜'], people['孫策']
    first = create(client, zhou, request_id='l-1', title='赤壁', occurred_precision='year', occurred_on='208', participant_ids=[sun['id']]).json()
    create(client, sun, request_id='l-2', title='不知道時間')
    create(client, zhou, request_id='l-3', title='求學', occurred_precision='year', occurred_on='190')
    listed = client.get('/api/person-experiences').json()
    assert [x['title'] for x in listed['items']] == ['赤壁', '求學', '不知道時間']
    assert (listed['total'], listed['archived_total']) == (3, 0) and set(listed['items'][0]) == KEYS
    assert listed['items'][0] == client.get(f"/api/person-experiences/{first['id']}").json()  # 與單筆讀取、人物頁是同一筆資料

    assert patch(client, first['id'], 'l-4', 1, status='archived').status_code == 200
    listed = client.get('/api/person-experiences').json()
    assert [x['title'] for x in listed['items']] == ['求學', '不知道時間'] and (listed['total'], listed['archived_total']) == (2, 1)
    assert [x['id'] for x in client.get('/api/person-experiences?archived=true').json()['items']] == [first['id']]

    other = TestClient(client.app)  # 另一個帳號看不到
    world(other, 'exp_list_other')
    assert other.get('/api/person-experiences').json() == {'items': [], 'total': 0, 'archived_total': 0}


def test_relation_can_cite_person_experiences_without_losing_record_sources(client):
    people, record = world(client)
    zhou, sun, lu = people['周瑜'], people['孫策'], people['魯肅']
    both = create(client, zhou, request_id='r-1', title='平定江東', participant_ids=[sun['id']], occurred_precision='year', occurred_on='199').json()
    only_sun = create(client, sun, request_id='r-2', content='孫策少年時的經歷，沒有標題。').json()
    unrelated = create(client, lu, request_id='r-3', title='魯肅的事').json()
    archived = create(client, zhou, request_id='r-4', title='已封存的經歷').json()
    assert patch(client, archived['id'], 'r-5', 1, status='archived').status_code == 200

    # 可引用的來源：我的經歷照舊；人物經歷只列未封存、且兩端至少一人是主體或參與人物的
    eligible = sources(client, zhou, sun)
    assert [item['id'] for item in eligible['items']] == [record] and eligible['total'] == 1
    listed = eligible['person_experiences']
    assert [item['id'] for item in listed['items']] == [both['id'], only_sun['id']] and listed['total'] == 2
    assert listed['items'][0] == {'id': both['id'], 'title': '平定江東', 'experience_type': 'historical', 'occurred_precision': 'year',
                                  'occurred_on': '0199', 'occurred_label': '', 'subject': '周瑜'}
    assert listed['items'][1]['title'] == '孫策少年時的經歷，沒有標題。' and listed['items'][1]['subject'] == '孫策'  # 沒有標題：用內容開頭

    # 建立關係：兩種來源一起保存，順序照送出的順序
    created = client.post(f"/api/people/{zhou['id']}/connections", json={
        'request_id': 'rel-1', 'other_person_id': sun['id'], 'relation_types': [{'kind': 'friend'}], 'description': '一同平定江東',
        'source_experience_ids': [record], 'source_person_experience_ids': [only_sun['id'], both['id']]})
    assert created.status_code == 201, created.text
    connection = created.json()
    assert connection['source_experience_ids'] == [record] and connection['source_person_experience_ids'] == [only_sun['id'], both['id']]
    for person in (zhou, sun):  # 雙方人物頁讀到同一組來源
        view = client.get(f"/api/persons/{person['id']}").json()['connections'][0]
        assert [s['id'] for s in view['sources']['experiences']] == [record]
        assert [s['id'] for s in view['sources']['person_experiences']] == [only_sun['id'], both['id']]
        assert view['sources']['person_experiences'][1]['title'] == '平定江東' and view['sources']['person_experiences'][1]['subject'] == '周瑜'

    # 不相關或已封存的人物經歷不能引用；失敗不改動原本的來源
    for source_id, code in ((unrelated['id'], 'unrelated_source'), (archived['id'], 'archived_source')):
        rejected = client.patch(f"/api/connections/{connection['id']}", json={'request_id': 'rel-bad-' + code, 'expected_revision': 1,
                                                                               'source_person_experience_ids': [source_id]})
        assert rejected.status_code == 422 and rejected.json()['error']['code'] == code, rejected.text
    # 只改人物經歷來源：我的經歷來源保留
    edited = client.patch(f"/api/connections/{connection['id']}", json={'request_id': 'rel-2', 'expected_revision': 1,
                                                                         'source_person_experience_ids': [both['id']]})
    assert edited.status_code == 200, edited.text
    assert edited.json()['source_experience_ids'] == [record] and edited.json()['source_person_experience_ids'] == [both['id']]
    # 共同參與不會自動建立關係：魯肅沒有任何關係
    assert client.get(f"/api/persons/{lu['id']}").json()['connections'] == []
