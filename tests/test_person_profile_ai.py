"""第三階段：AI 產生人物設定（module=person_profile）。程式自帶的自動測試，用 Fake Provider（不連網、不計費）。

完成依據是部署後在 Cloud SQL life_world_e2e 的實測（tests/test_person_profile_ai_cloudsql_e2e.py、browser_tests/test_persons_ui.py），
這裡只做開發時的快速檢查。

規則：上下文由伺服器依帳號讀取（基本資料、簡介、已保存的人物設定）；AI 結果只回傳候選、不保存；
使用者確認後走既有的保存 API 新增一版（origin=ai／ai_edited，記錄 generation_id）；失敗不影響原設定；不建立角色卡；帳號隔離。
"""
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.ai_providers import FakeProvider
from app.config import DemoPolicy
from app.main import create_app
from conftest import onboard, register

FIELDS = {'background', 'personality', 'motivation', 'stance', 'abilities', 'expression', 'behavior', 'knowledge_boundary', 'restrictions'}


@pytest.fixture
def client(tmp_path):
    app = create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                     clock=lambda: datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc), generation_provider=FakeProvider())
    with TestClient(app) as c:
        yield c


def ready(client, username):
    onboard(client)
    register(client, username)


def person(client, name='亞瑟', **body):
    response = client.post('/api/persons', json={'request_id': 'p-' + name, 'name': name, 'person_type': 'fictional',
                                                 'description': '傳說中的國王', **body})
    assert response.status_code == 201, response.text
    return response.json()


def generate(client, person_id, request_id='g-1', guidance='', consent=True):
    return client.post('/api/ai/generate', json={'request_id': request_id, 'module': 'person_profile',
                                                  'input': {'person_id': person_id, 'guidance': guidance, 'consent': consent}})


def save(client, person_id, request_id, expected, fields, origin='manual', generation_id=None):
    body = {'request_id': request_id, 'expected_profile_id': expected, 'fields': fields, 'origin': origin}
    if generation_id:
        body['generation_id'] = generation_id
    return client.put(f'/api/persons/{person_id}/profile', json=body)


def rows(client, sql, *params):
    with client.app.state.service.db.connect() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def test_generate_returns_candidate_only_and_uses_server_side_context(client):
    ready(client, 'ai_profile_ctx')
    p = person(client, aliases=['Arthur'], tags=['圓桌'])
    v1 = save(client, p['id'], 'm-1', None, {'background': '在石中拔出聖劍', 'personality': '正直'}).json()
    response = generate(client, p['id'], guidance='偏重領導風格')
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body['output']) == FIELDS and all(isinstance(v, str) for v in body['output'].values())
    assert body['generation']['module'] == 'person_profile' and body['generation']['status'] == 'succeeded'
    assert client.get(f"/api/persons/{p['id']}").json()['profile'] == v1  # 只回候選，不覆蓋、不保存
    record = rows(client, "SELECT input_json FROM ai_generations WHERE module='person_profile'")
    stored = json.loads(record[0]['input_json'])
    assert stored['person_id'] == p['id'] and stored['guidance'] == '偏重領導風格' and stored['base_profile_id'] == v1['id']
    assert stored['context']['person']['name'] == '亞瑟' and stored['context']['person']['aliases'] == ['Arthur']
    assert stored['context']['person']['description'] == '傳說中的國王'
    assert stored['context']['profile']['background'] == '在石中拔出聖劍'
    assert rows(client, "SELECT COUNT(*) AS n FROM works WHERE kind='character_card'")[0]['n'] == 0


def test_save_ai_result_as_new_versions_with_generation_link(client):
    ready(client, 'ai_profile_save')
    p = person(client)
    generated = generate(client, p['id']).json()
    gid, fields = generated['generation']['id'], generated['output']
    v1 = save(client, p['id'], 's-1', None, fields, origin='ai', generation_id=gid)
    assert v1.status_code == 200, v1.text
    assert v1.json()['origin'] == 'ai' and v1.json()['generation_id'] == gid and v1.json()['version'] == 1
    edited = dict(fields, personality='使用者修改過的性格')
    v2 = save(client, p['id'], 's-2', v1.json()['id'], edited, origin='ai_edited', generation_id=gid)
    assert v2.status_code == 200 and v2.json()['origin'] == 'ai_edited' and v2.json()['version'] == 2
    assert client.get(f"/api/persons/{p['id']}").json()['profile']['fields']['personality'] == '使用者修改過的性格'
    assert rows(client, "SELECT COUNT(*) AS n FROM works")[0]['n'] == 0  # 不建立任何作品


def test_ai_origin_requires_a_matching_successful_generation(client):
    ready(client, 'ai_profile_link')
    a, b = person(client, '甲'), person(client, '乙')
    gid_b = generate(client, b['id'], 'g-b').json()['generation']['id']
    missing = save(client, a['id'], 'x-1', None, {'background': 'x'}, origin='ai')
    assert missing.status_code == 422, missing.text
    wrong_person = save(client, a['id'], 'x-2', None, {'background': 'x'}, origin='ai', generation_id=gid_b)
    assert wrong_person.status_code == 409 and wrong_person.json()['error']['code'] == 'generation_mismatch', wrong_person.text
    manual_with_id = save(client, a['id'], 'x-3', None, {'background': 'x'}, origin='manual', generation_id=gid_b)
    assert manual_with_id.status_code == 422
    assert client.get(f"/api/persons/{a['id']}").json()['profile'] is None


def test_generation_failure_leaves_profile_untouched(client):
    ready(client, 'ai_profile_fail')
    p = person(client)
    v1 = save(client, p['id'], 'm-1', None, {'background': '原本的背景'}).json()
    failed = generate(client, p['id'], 'g-fail', guidance='#fake-fail')
    assert failed.status_code >= 500, failed.text
    assert client.get(f"/api/persons/{p['id']}").json()['profile'] == v1
    record = rows(client, "SELECT status FROM ai_generations WHERE request_id='g-fail'")
    assert record == [{'status': 'failed'}]
    with client.app.state.service.db.connect() as c:
        failed_id = c.execute("SELECT id FROM ai_generations WHERE request_id='g-fail'").fetchone()[0]
    refused = save(client, p['id'], 's-x', v1['id'], {'background': '不該存'}, origin='ai', generation_id=failed_id)
    assert refused.status_code == 409 and refused.json()['error']['code'] == 'generation_mismatch'


def test_retry_replays_and_isolation_and_archived(client):
    ready(client, 'ai_profile_owner')
    p = person(client)
    first = generate(client, p['id'], 'g-same').json()
    again = generate(client, p['id'], 'g-same').json()
    assert again['generation']['id'] == first['generation']['id']
    assert len(rows(client, "SELECT id FROM ai_generations WHERE module='person_profile'")) == 1  # 重送不再呼叫 Provider
    other = TestClient(client.app)
    ready(other, 'ai_profile_other')
    assert generate(other, p['id'], 'g-steal').status_code == 404  # 別人的人物：找不到，不預留、不呼叫
    assert save(other, p['id'], 'x', None, {'background': 'x'}, origin='ai', generation_id=first['generation']['id']).status_code == 404
    archived = client.post(f"/api/persons/{p['id']}/status", json={'request_id': 'a', 'expected_revision': 1, 'status': 'archived'})
    assert archived.status_code == 200
    blocked = generate(client, p['id'], 'g-archived')
    assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'person_archived'
    assert len(rows(client, "SELECT id FROM ai_generations WHERE module='person_profile'")) == 1


def test_generation_requires_explicit_ai_consent(client):
    """沿用既有 AI 使用同意：使用者確認人物資料會送往 AI 服務（consent=true）才可生成；否則不預留、不呼叫。"""
    ready(client, 'ai_profile_consent')
    p = person(client)
    refused = generate(client, p['id'], 'g-no', consent=False)
    assert refused.status_code == 422, refused.text
    assert rows(client, "SELECT id FROM ai_generations WHERE module='person_profile'") == []
