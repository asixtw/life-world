"""E2E Migration 010 之後才執行：Local 8030 → Cloud Run e2e → Cloud SQL life_world_e2e 的關係來源驗收（PostgreSQL 18.6）。

只在明確開啟時執行（會在 life_world_e2e 建立 p0rs_ 開頭的合成帳號與資料）：

    LW_E2E_RELATION_SOURCES=1 .venv\\Scripts\\python.exe -m pytest -q tests/test_relation_sources_cloudsql_e2e.py

前提：Migration 010 已執行並通過驗收，且 e2e 版本以 `Deploy-8030-E2E.ps1 -RelationSourceStore link_table` 部署。
本測試先核對 /ready 與 /api/capabilities 的 relation_sources，不符就直接失敗，不會改用 SQLite 或其他資料庫。
合成帳號密碼只在執行當下產生並放在記憶體，不寫入任何檔案或輸出。
"""
import http.cookiejar
import json
import os
import secrets
import socket
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

BASE = os.environ.get('LW_E2E_URL', 'https://lw-core-compare.localhost:8030').rstrip('/')

_system_getaddrinfo = socket.getaddrinfo


def _localhost_is_loopback(host, *args, **kwargs):
    """*.localhost 一律是本機（RFC 6761）。瀏覽器與 curl 自己會這樣處理，但 Python 交給系統 DNS，
    有些網路的 DNS 不回答這種名稱（2026-11-11 換網路後 getaddrinfo 失敗），所以測試程序內直接對應到 127.0.0.1。
    TLS 的主機名稱檢查仍用原本的名稱，不受影響。"""
    if isinstance(host, str) and host.endswith('.localhost'):
        host = '127.0.0.1'
    return _system_getaddrinfo(host, *args, **kwargs)


socket.getaddrinfo = _localhost_is_loopback
ENABLED = os.environ.get('LW_E2E_RELATION_SOURCES') == '1'
pytestmark = pytest.mark.skipif(not ENABLED, reason='Migration 010 後以 LW_E2E_RELATION_SOURCES=1 對 Local 8030（Cloud SQL E2E）執行')
TAIPEI = ZoneInfo('Asia/Taipei')
LINK_KEYS = {'id', 'owner_id', 'person_a', 'person_b', 'label', 'revision', 'source_experience_ids', 'source_person_experience_ids',
             'relation_types', 'description', 'confirmation_status'}  # P4：關係類型、共用描述與狀態


class Client:
    """最小的 8030 API 用戶端：Cookie 工作階段＋CSRF＋同源 Origin（與瀏覽器相同的寫入條件）。"""

    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar),
                                                  urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        self.csrf = ''

    def call(self, method, path, body=None):
        headers = {'Accept': 'application/json'}
        data = None
        if method != 'GET':
            headers.update({'Origin': BASE, 'X-CSRF-Token': self.csrf})
        if body is not None:
            data = json.dumps(body).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(BASE + '/api' + path, data=data, method=method, headers=headers)
        try:
            with self.opener.open(request, timeout=60) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        payload = json.loads(raw) if raw else None
        if isinstance(payload, dict) and payload.get('csrf_token'):
            self.csrf = payload['csrf_token']
        evidence = os.environ.get('LW_E2E_REQUEST_LOG')
        if evidence:  # 驗收證據：只記時間、方法、路徑、狀態與錯誤代碼；不記請求內容、Cookie 或 CSRF
            code = payload.get('error', {}).get('code') if isinstance(payload, dict) and isinstance(payload.get('error'), dict) else None
            with open(evidence, 'a', encoding='utf-8') as handle:
                handle.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'method': method,
                                         'path': path.split('?')[0], 'status': status, 'error': code}, ensure_ascii=False) + '\n')
        return status, payload

    def ok(self, method, path, body=None, expected=(200, 201)):
        status, payload = self.call(method, path, body)
        assert status in expected, (method, path, status, payload)
        return payload


def synthetic_world(prefix):
    """建立合成帳號、目標、三位人物與兩筆主要人物是甲的已確認「我的經歷」。"""
    client = Client()
    username = prefix + datetime.now(timezone.utc).strftime('%m%d%H%M%S') + secrets.token_hex(2)
    password = 'Syn-' + secrets.token_hex(16)  # 只在記憶體；重新登入驗證後即丟棄
    client.ok('POST', '/auth/guest')
    client.ok('POST', '/auth/claim', {'username': username, 'password': password})
    client.ok('PUT', '/profile', {'name': '關係來源驗收', 'bio': 'Cloud SQL E2E 合成帳號', 'timezone': 'Asia/Taipei'})
    today = datetime.now(TAIPEI).date()
    days = [(today + timedelta(days=n)).isoformat() for n in (1, 3)]
    goal = client.ok('POST', '/goals', {'request_id': username + '-goal', 'title': '關係來源驗收', 'outcome': '確認關聯表讀寫',
                                        'deadline': (today + timedelta(days=60)).isoformat(),
                                        'actions': [{'title': t, 'unit': u, 'target': '3', 'level': i + 1, 'weekdays': [0, 2, 4], 'dates': days}
                                                    for i, (t, u) in enumerate([('練習', '小時'), ('記錄', '篇'), ('交流', '次')])]})
    people = [client.ok('POST', '/people', {'name': n}) for n in ('甲', '乙', '丙')]
    experiences = []
    for i in range(2):
        d = client.ok('POST', '/experiences/drafts', {'raw_text': f'和甲一起練習第 {i + 1} 次。', 'occurred_at': datetime.now(TAIPEI).isoformat(),
                                                      'goal_id': goal['id'], 'person_id': people[0]['id'],
                                                      'contributions': [{'action_id': goal['actions'][0]['id'], 'quantity': '0.5'}]})
        done = client.ok('POST', f"/drafts/{d['id']}/confirm", {'request_id': f'{username}-confirm-{i}', 'expected_revision': d['revision'],
                                                                 'summary': '練習了半小時。', 'person_id': people[0]['id'],
                                                                 'contributions': d['contributions'], 'tasks': []})
        experiences.append(done['experience_id'])
    return {'client': client, 'username': username, 'password': password, 'a': people[0], 'b': people[1], 'c': people[2],
            'e1': experiences[0], 'e2': experiences[1]}


@pytest.fixture(scope='module')
def preflight():
    probe = Client()
    request = urllib.request.Request(BASE + '/ready')
    with probe.opener.open(request, timeout=60) as response:
        assert response.status == 200, 'Local 8030 未就緒（Cloud SQL life_world_e2e）'
    capabilities = probe.ok('GET', '/capabilities')
    assert capabilities.get('relation_sources') == 'link_table', \
        'e2e 版本仍是 legacy_jsonb：Migration 010 驗收後以 -RelationSourceStore link_table 部署，才能執行本測試'


def overview_item(client, person_id, connection_id):
    return next(x for x in client.ok('GET', f'/people/{person_id}/overview')['connections'] if x['id'] == connection_id)


def test_link_table_round_trip_on_cloud_sql(preflight):
    w = synthetic_world('p0rs_')
    c = w['client']
    rewards_before = c.ok('GET', '/state')['rewards']['total']
    body = {'request_id': 'rs-post', 'other_person_id': w['b']['id'], 'label': '練習夥伴', 'source_experience_ids': [w['e2'], w['e1'], w['e2']]}
    created = c.ok('POST', f"/people/{w['a']['id']}/connections", body, expected=(201,))
    assert set(created) == LINK_KEYS and created['revision'] == 1
    assert created['source_experience_ids'] == [w['e2'], w['e1']] and created['source_person_experience_ids'] == []
    cid = created['id']
    assert c.ok('GET', f'/connections/{cid}') == created
    for side in ('a', 'b'):
        item = overview_item(c, w[side]['id'], cid)
        assert item['source_experience_ids'] == [w['e2'], w['e1']] and item['source_person_experience_ids'] == [] and item['revision'] == 1
    assert c.ok('POST', f"/people/{w['a']['id']}/connections", body, expected=(201,)) == created  # 同代碼重送
    assert c.call('POST', f"/people/{w['a']['id']}/connections", {**body, 'label': '改內容'})[0] == 409

    status, error = c.call('PATCH', f'/connections/{cid}', {'request_id': 'rs-missing', 'expected_revision': 1,
                                                             'source_experience_ids': [w['e1']], 'source_person_experience_ids': ['not-a-real-id']})
    assert status == 404, error
    assert c.ok('GET', f'/connections/{cid}') == created  # 錯誤整筆回滾：我的經歷來源也沒被替換

    replaced = c.ok('PATCH', f'/connections/{cid}', {'request_id': 'rs-replace', 'expected_revision': 1, 'source_experience_ids': [w['e1']]})
    assert replaced['source_experience_ids'] == [w['e1']] and replaced['revision'] == 2
    cleared = c.ok('PATCH', f'/connections/{cid}', {'request_id': 'rs-clear', 'expected_revision': 2, 'source_experience_ids': []})
    assert cleared['source_experience_ids'] == [] and cleared['source_person_experience_ids'] == [] and cleared['revision'] == 3
    labelled = c.ok('PATCH', f'/connections/{cid}', {'request_id': 'rs-label', 'expected_revision': 3, 'label': '只改說明'})
    assert labelled['label'] == '只改說明' and labelled['source_experience_ids'] == [] and labelled['revision'] == 4
    assert c.call('PATCH', f'/connections/{cid}', {'request_id': 'rs-stale', 'expected_revision': 3, 'label': '過期'})[1]['error']['code'] == 'stale_revision'
    assert c.ok('PATCH', f'/connections/{cid}', {'request_id': 'rs-replace', 'expected_revision': 1, 'source_experience_ids': [w['e1']]}) == replaced
    assert c.call('PATCH', f'/connections/{cid}', {'request_id': 'rs-replace', 'expected_revision': 1, 'source_experience_ids': []})[0] == 409
    assert c.call('PATCH', f'/connections/{cid}', {'request_id': 'rs-empty', 'expected_revision': 4})[1]['error']['code'] == 'empty_patch'
    restored = c.ok('PATCH', f'/connections/{cid}', {'request_id': 'rs-restore', 'expected_revision': 4, 'source_experience_ids': [w['e2'], w['e1']]})
    assert restored['source_experience_ids'] == [w['e2'], w['e1']] and restored['revision'] == 5

    assert len(c.ok('GET', f"/people/{w['a']['id']}/overview")['connections']) == 1  # 沒有多建關係
    assert c.ok('GET', '/state')['rewards']['total'] == rewards_before  # 來源編輯不動積分帳本

    other = synthetic_world('p0rs_x_')
    assert other['client'].call('GET', f'/connections/{cid}')[0] == 404
    assert other['client'].call('PATCH', f'/connections/{cid}', {'request_id': 'x', 'expected_revision': 5, 'label': '盜改'})[0] == 404
    cite = other['client'].call('POST', f"/people/{other['a']['id']}/connections",
                                {'request_id': 'x-cite', 'other_person_id': other['b']['id'], 'label': '盜用來源', 'source_experience_ids': [w['e1']]})
    assert cite[0] == 404, cite

    again = Client()  # 新的工作階段重新登入：資料在 Cloud SQL，不在本機
    again.ok('POST', '/auth/login', {'username': w['username'], 'password': w['password']})
    assert again.ok('GET', f'/connections/{cid}') == restored


def test_person_experience_sources_on_cloud_sql(preflight):
    """人物經歷來源的正向路徑需要 P1 的人物經歷 API 才能在 E2E 建立資料；目前只驗證不存在的 ID 會被拒絕。"""
    w = synthetic_world('p0rs_pe_')
    status, error = w['client'].call('POST', f"/people/{w['a']['id']}/connections",
                                     {'request_id': 'pe-1', 'other_person_id': w['b']['id'], 'label': '人物經歷來源',
                                      'source_person_experience_ids': ['not-a-real-id']})
    assert status == 404 and error['error']['code'] == 'not_found', error
    assert w['client'].ok('GET', f"/people/{w['a']['id']}/overview")['connections'] == []  # 失敗不留下關係
    pytest.skip('正向路徑待 P1 人物經歷 API；SQLite 單元測試 test_relation_sources.py 已涵蓋排序、替換與驗證')
