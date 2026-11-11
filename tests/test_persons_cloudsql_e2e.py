"""Unified Person（Phase 1–2 與缺陷修正）在 Cloud SQL 上的 API 驗收：Local 8030 → Cloud Run e2e → life_world_e2e（PostgreSQL 18.6）。

只在明確開啟時執行（會在 life_world_e2e 建立 persons_ui_ 開頭的合成帳號與人物）：

    LW_E2E_PERSONS=1 .venv\\Scripts\\python.exe -m pytest -q tests/test_persons_cloudsql_e2e.py

前提：含新人物系統的版本已部署到 e2e 標籤（link_table），/api/capabilities 的 unified_people 是 true。
不符合就直接失敗，不會改用其他資料庫。合成帳號的密碼只在記憶體。
"""
import json
import os
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from test_relation_sources_cloudsql_e2e import BASE, Client

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS') != '1', reason='部署後以 LW_E2E_PERSONS=1 對 Local 8030（Cloud SQL E2E）執行')
PROFILE_TITLE = 'person_profile.v1'


@pytest.fixture(scope='module', autouse=True)
def preflight():
    probe = Client()
    with probe.opener.open(urllib.request.Request(BASE + '/ready'), timeout=60) as response:
        assert response.status == 200, 'Local 8030 未就緒（Cloud SQL life_world_e2e）'
    capabilities = probe.ok('GET', '/capabilities')
    assert capabilities.get('unified_people') is True and capabilities.get('relation_sources') == 'link_table', capabilities


def account(tag):
    """建立合成帳號（persons_ui_ 開頭）並完成首個目標；回傳 (client, username, password)。"""
    client = Client()
    username = 'persons_ui_' + tag + datetime.now(timezone.utc).strftime('%H%M%S') + secrets.token_hex(2)
    password = 'Syn-' + secrets.token_hex(16)
    client.ok('POST', '/auth/guest')
    client.ok('POST', '/auth/claim', {'username': username, 'password': password})
    client.ok('PUT', '/profile', {'name': '人物驗收', 'bio': 'Cloud SQL E2E 合成帳號', 'timezone': 'Asia/Taipei'})
    today = datetime.now(ZoneInfo('Asia/Taipei')).date()
    days = [(today + timedelta(days=n)).isoformat() for n in (1, 3)]
    client.goal = client.ok('POST', '/goals', {'request_id': username + '-goal', 'title': '人物驗收', 'outcome': '確認新人物系統',
                                               'deadline': (today + timedelta(days=60)).isoformat(),
                                               'actions': [{'title': t, 'unit': u, 'target': '3', 'level': i + 1, 'weekdays': [0, 2, 4], 'dates': days}
                                                           for i, (t, u) in enumerate([('練習', '小時'), ('記錄', '篇'), ('交流', '次')])]})
    return client, username, password  # client.goal：建立我的紀錄（關係來源驗收）時使用


def create(client, name, request_id, **body):
    return client.ok('POST', '/persons', {'request_id': request_id, 'name': name, **body}, expected=(201,))


def save(client, person_id, request_id, expected, **fields):
    return client.call('PUT', f'/persons/{person_id}/profile', {'request_id': request_id, 'expected_profile_id': expected, 'fields': fields})


def note_titles(client, person_id):
    return [n['title'] for n in client.ok('GET', f'/people/{person_id}/overview')['notes']]


def test_same_name_profile_receipts_and_isolation_on_cloud_sql():
    c, username, password = account('a')
    first = create(c, '王小明', 'same-1', person_type='fictional', description='第一位')
    second = create(c, '王小明', 'same-2', person_type='fictional', description='第一位')
    assert first['id'] != second['id'] and first['origin_type'] == 'manual'
    edited = c.ok('PATCH', f"/persons/{first['id']}", {'expected_revision': 1, 'description': '改過'})
    assert edited['revision'] == 2 and c.ok('GET', f"/persons/{second['id']}")['person']['description'] == '第一位'

    status, v1 = save(c, first['id'], 'pf-1', None, background='在台南長大', personality='溫和')
    assert status == 200 and v1['version'] == 1, v1
    forged = {'schema': PROFILE_TITLE, 'version': 9, 'origin': 'manual', 'fields': {'background': '私人筆記'}}
    c.ok('POST', '/notes', {'person_id': first['id'], 'kind': 'preparation', 'title': PROFILE_TITLE, 'content': json.dumps(forged, ensure_ascii=False)}, expected=(201,))
    assert note_titles(c, first['id']).count(PROFILE_TITLE) == 1  # 沒有回執的同格式筆記仍是私人筆記
    assert c.ok('GET', f"/persons/{first['id']}")['profile'] == v1
    status, v2 = save(c, first['id'], 'pf-2', v1['id'], background='在台南長大', personality='溫和但堅定')
    assert status == 200 and v2['version'] == 2, v2
    assert save(c, first['id'], 'pf-2', v1['id'], background='在台南長大', personality='溫和但堅定') == (200, v2)  # 重送不產生新版本
    stale = save(c, first['id'], 'pf-3', v1['id'], personality='覆蓋')
    assert stale[0] == 409 and stale[1]['error']['code'] == 'stale_profile'
    assert c.ok('GET', f"/persons/{first['id']}")['profile'] == v2
    assert note_titles(c, first['id']).count(PROFILE_TITLE) == 1
    assert c.ok('GET', f"/persons/{second['id']}")['profile'] is None

    other, _, _ = account('b')
    assert other.call('GET', f"/persons/{first['id']}")[0] == 404
    assert other.call('PATCH', f"/persons/{first['id']}", {'expected_revision': 2, 'name': '盜改'})[0] == 404
    assert save(other, first['id'], 'x', v2['id'], background='盜寫')[0] == 404
    assert other.ok('GET', '/persons')['items'] == []
    assert c.ok('GET', '/characters?status=active')['items'] == []  # 人物設定不建立作品角色卡

    again = Client()  # 新工作階段重新登入：資料在 Cloud SQL
    again.ok('POST', '/auth/login', {'username': username, 'password': password})
    assert again.ok('GET', f"/persons/{first['id']}")['profile'] == v2


def test_archived_person_rejects_changes_on_cloud_sql():
    c, _, _ = account('arch')
    a = create(c, '甲', 'a', description='原簡介')
    status, v1 = save(c, a['id'], 'p-1', None, background='封存前')
    assert status == 200, v1
    archived = c.ok('POST', f"/persons/{a['id']}/status", {'request_id': 's-1', 'expected_revision': 1, 'status': 'archived'})
    patch = c.call('PATCH', f"/persons/{a['id']}", {'expected_revision': archived['revision'], 'description': '偷改'})
    assert patch[0] == 409 and patch[1]['error']['code'] == 'person_archived', patch
    put = save(c, a['id'], 'p-2', v1['id'], background='封存後')
    assert put[0] == 409 and put[1]['error']['code'] == 'person_archived', put
    assert save(c, a['id'], 'p-1', None, background='封存前') == (200, v1)  # 封存前已成功的請求重送：回原回執
    detail = c.ok('GET', f"/persons/{a['id']}")
    assert detail['person']['status'] == 'archived' and detail['person']['description'] == '原簡介' and detail['profile'] == v1
    restored = c.ok('POST', f"/persons/{a['id']}/status", {'request_id': 's-2', 'expected_revision': archived['revision'], 'status': 'active'})
    assert c.ok('PATCH', f"/persons/{a['id']}", {'expected_revision': restored['revision'], 'description': '恢復後'})['description'] == '恢復後'
    assert save(c, a['id'], 'p-3', v1['id'], background='恢復後')[1]['version'] == 2


def test_pagination_101_people_on_cloud_sql():
    c, _, _ = account('page')
    made = [create(c, f'人物{i:03d}', f'n-{i}', tags=['偶數'] if i % 2 == 0 else []) for i in range(101)]

    def page(offset, **params):
        query = '&'.join([f'limit=50&offset={offset}&sort=name'] + [f'{k}={urllib.parse.quote(v)}' for k, v in params.items()])
        body = c.ok('GET', '/persons?' + query)
        return [p['id'] for p in body['items']], body['total']

    pages = [page(o) for o in (0, 50, 100)]
    assert [len(ids) for ids, _ in pages] == [50, 50, 1] and {t for _, t in pages} == {101}
    seen = [i for ids, _ in pages for i in ids]
    assert len(set(seen)) == 101 and seen == [p['id'] for p in sorted(made, key=lambda p: p['name'])]
    even = [page(o, q='偶數') for o in (0, 50)]
    assert [len(ids) for ids, _ in even] == [50, 1] and even[0][1] == 51
    for i, person in enumerate(made[:3]):
        c.ok('POST', f"/persons/{person['id']}/status", {'request_id': f'a-{i}', 'expected_revision': 1, 'status': 'archived'})
    active = [page(o) for o in (0, 50)]
    assert [len(ids) for ids, _ in active] == [50, 48] and active[0][1] == 98
    archived_ids, archived_total = page(0, status='archived')
    assert archived_total == 3 and archived_ids == [p['id'] for p in made[:3]]

