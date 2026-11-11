"""Unified Person 2.0（P1／P2）：單頁新增／編輯一次儲存，完整承接舊人物欄位。

程式自帶的自動測試（開發時快速檢查）；完成依據是部署後在 Cloud SQL life_world_e2e 的實測。
- P2：people.notes（人物備註）、common_context（相關背景／共同場合）、followed（關注）在新 API 可新增、編輯、讀回，
  也和舊 /api/people 互通；people.notes 與 notes 資料表（人物設定版本）是兩回事。
- P1：新增人物可同時帶人物設定，在同一筆交易建立人物與第 1 版設定（有正式回執）；重送不重複建立。
- AI 生成可指定要產生的欄位（target_fields），結果仍只回候選。
"""
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.ai_providers import FakeProvider
from app.config import DemoPolicy
from app.main import create_app
from conftest import onboard, register


@pytest.fixture
def client(tmp_path):
    app = create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                     clock=lambda: datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc), generation_provider=FakeProvider())
    with TestClient(app) as c:
        onboard(c)
        register(c, 'unified_form')
        yield c


def create(client, request_id='c-1', **body):
    response = client.post('/api/persons', json={'request_id': request_id, 'name': '周瑜', **body})
    assert response.status_code == 201, response.text
    return response.json()


def count(client, sql, *params):
    with client.app.state.service.db.connect() as c:
        return c.execute(sql, params).fetchone()[0]


def test_create_with_legacy_fields_and_profile_in_one_save(client):
    body = {'person_subtype': 'historical', 'description': '東吳將領', 'roles': ['都督'], 'tags': ['三國'], 'category': 'learning',
            'notes': '人物備註：赤壁之戰', 'common_context': '在讀書會討論過', 'followed': True,
            'profile': {'background': '出身廬江', 'personality': '儒雅'}}
    person = create(client, **body)
    assert (person['notes'], person['common_context'], person['followed']) == ('人物備註：赤壁之戰', '在讀書會討論過', True)
    detail = client.get(f"/api/persons/{person['id']}").json()
    assert detail['profile']['version'] == 1 and detail['profile']['fields']['background'] == '出身廬江' and detail['profile']['origin'] == 'manual'
    legacy = client.get(f"/api/people/{person['id']}/overview").json()['person']  # 舊頁面讀到同樣的舊欄位
    assert (legacy['notes'], legacy['common_context'], legacy['followed'], legacy['role']) == ('人物備註：赤壁之戰', '在讀書會討論過', True, '都督')
    assert '人物備註：赤壁之戰' not in [n['content'] for n in client.get(f"/api/people/{person['id']}/overview").json()['notes']]
    again = client.post('/api/persons', json={'request_id': 'c-1', 'name': '周瑜', **body})
    assert again.status_code == 201 and again.json() == person  # 重送：同一人物
    assert count(client, 'SELECT COUNT(*) FROM people') == 1
    assert count(client, "SELECT COUNT(*) FROM notes WHERE kind='preparation'") == 1  # 只有一版設定


def test_create_without_profile_has_no_profile_version(client):
    person = create(client, profile={'background': '', 'personality': '   '})
    assert client.get(f"/api/persons/{person['id']}").json()['profile'] is None
    assert (person['notes'], person['common_context'], person['followed']) == ('', '', False)


def test_edit_legacy_fields_and_old_api_sees_them(client):
    person = create(client)
    edited = client.patch(f"/api/persons/{person['id']}", json={'expected_revision': 1, 'notes': '新的備註', 'common_context': '同一個社團', 'followed': True})
    assert edited.status_code == 200, edited.text
    assert (edited.json()['notes'], edited.json()['common_context'], edited.json()['followed'], edited.json()['revision']) == ('新的備註', '同一個社團', True, 2)
    legacy = client.get(f"/api/people/{person['id']}/overview").json()['person']
    assert (legacy['notes'], legacy['common_context'], legacy['followed']) == ('新的備註', '同一個社團', True)
    assert client.patch(f"/api/persons/{person['id']}", json={'expected_revision': 2, 'notes': None}).status_code == 422


def test_people_created_by_the_old_page_keep_their_legacy_fields(client):
    old = client.post('/api/people', json={'name': '舊人物', 'notes': '舊備註', 'common_context': '舊場合', 'followed': True}).json()
    item = next(p for p in client.get('/api/persons').json()['items'] if p['id'] == old['id'])
    assert (item['notes'], item['common_context'], item['followed']) == ('舊備註', '舊場合', True)


def test_ai_generation_accepts_target_fields(client):
    person = create(client, profile={'background': '出身廬江'})
    response = client.post('/api/ai/generate', json={'request_id': 'g-1', 'module': 'person_profile',
                                                     'input': {'person_id': person['id'], 'guidance': '', 'consent': True,
                                                               'target_fields': ['personality', 'expression']}})
    assert response.status_code == 201, response.text
    with client.app.state.service.db.connect() as c:
        stored = json.loads(c.execute("SELECT input_json FROM ai_generations WHERE request_id='g-1'").fetchone()[0])
    assert stored['target_fields'] == ['personality', 'expression']
    bad = client.post('/api/ai/generate', json={'request_id': 'g-2', 'module': 'person_profile',
                                                'input': {'person_id': person['id'], 'guidance': '', 'consent': True, 'target_fields': ['unknown']}})
    assert bad.status_code == 422
    assert client.get(f"/api/persons/{person['id']}").json()['profile']['version'] == 1  # 生成不改已保存的設定
