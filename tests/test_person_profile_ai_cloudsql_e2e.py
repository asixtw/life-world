"""第三階段在 Cloud SQL 上的驗收：Local 8030 → Cloud Run e2e（真實 AI Provider）→ life_world_e2e（PostgreSQL 18.6）。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號；每次執行呼叫 1 次真實 AI，計入每日金額上限）：

    LW_E2E_PERSONS=1 .venv\\Scripts\\python.exe -m pytest -q tests/test_person_profile_ai_cloudsql_e2e.py
"""
import os

import pytest

from test_persons_cloudsql_e2e import account, create, preflight  # noqa: F401（preflight 是 autouse fixture）
from test_relation_sources_cloudsql_e2e import Client

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS') != '1', reason='部署後以 LW_E2E_PERSONS=1 對 Local 8030（Cloud SQL E2E）執行')
FIELDS = {'background', 'personality', 'motivation', 'stance', 'abilities', 'expression', 'behavior', 'knowledge_boundary', 'restrictions'}


def put_profile(client, person_id, request_id, expected, fields, origin='manual', generation_id=None):
    body = {'request_id': request_id, 'expected_profile_id': expected, 'fields': fields, 'origin': origin}
    if generation_id:
        body['generation_id'] = generation_id
    return client.call('PUT', f'/persons/{person_id}/profile', body)


def test_ai_profile_generate_edit_save_reload_on_cloud_sql():
    c, username, password = account('ai')
    status = c.ok('GET', '/generation/status')
    assert status['available'] is True and status['provider_kind'] == 'live', status
    p = create(c, '亞瑟', 'ai-p', person_type='fictional', description='傳說中的不列顛國王，圓桌騎士的領袖', aliases=['Arthur'])
    code, v1 = put_profile(c, p['id'], 'ai-m1', None, {'background': '少年時從石中拔出聖劍而成為國王'})
    assert code == 200, v1

    refused = c.call('POST', '/ai/generate', {'request_id': 'ai-no-consent', 'module': 'person_profile',
                                              'input': {'person_id': p['id'], 'guidance': '', 'consent': False}})
    assert refused[0] == 422, refused  # 沒有同意：不呼叫 AI

    result = c.ok('POST', '/ai/generate', {'request_id': 'ai-g1', 'module': 'person_profile',
                                           'input': {'person_id': p['id'], 'guidance': '著重領導風格與責任感', 'consent': True}}, expected=(201,))
    assert set(result['output']) == FIELDS and any(result['output'].values()), result
    assert result['generation']['module'] == 'person_profile' and result['generation']['status'] == 'succeeded'
    assert result['generation']['provider_kind'] == 'live'
    assert c.ok('GET', f"/persons/{p['id']}")['profile'] == v1  # 只回候選，未保存前不改原設定

    replay = c.ok('POST', '/ai/generate', {'request_id': 'ai-g1', 'module': 'person_profile',
                                           'input': {'person_id': p['id'], 'guidance': '著重領導風格與責任感', 'consent': True}}, expected=(201,))
    assert replay['generation']['id'] == result['generation']['id']  # 同一提交不再呼叫 AI

    gid = result['generation']['id']
    code, v2 = put_profile(c, p['id'], 'ai-s1', v1['id'], result['output'], origin='ai', generation_id=gid)
    assert code == 200 and v2['version'] == 2 and v2['origin'] == 'ai' and v2['generation_id'] == gid, v2
    edited = dict(result['output'], personality='使用者修改：' + (result['output']['personality'] or '')[:100])
    code, v3 = put_profile(c, p['id'], 'ai-s2', v2['id'], edited, origin='ai_edited', generation_id=gid)
    assert code == 200 and v3['version'] == 3 and v3['origin'] == 'ai_edited', v3

    improved = c.ok('POST', '/ai/generate', {'request_id': 'ai-improve', 'module': 'person_profile',
                                             'input': {'person_id': p['id'], 'guidance': '', 'consent': True,
                                                       'target_fields': ['personality', 'restrictions'], 'mode': 'improve'}}, expected=(201,))
    assert set(improved['output']) == FIELDS and improved['generation']['prompt_version'] == 'person-profile-v2'
    assert c.ok('GET', f"/persons/{p['id']}")['profile'] == v3  # 改善結果也只回候選
    evidence = os.environ.get('LW_E2E_EVIDENCE_FILE')
    if evidence:  # 供人工檢查 AI 產出只描述人物本身（合成資料，無個資）
        import json
        with open(evidence, 'w', encoding='utf-8') as handle:
            json.dump({'generate': result['output'], 'improve': improved['output']}, handle, ensure_ascii=False, indent=2)

    mismatch = put_profile(c, p['id'], 'ai-s3', v3['id'], {'background': 'x'}, origin='ai', generation_id='not-a-generation')
    assert mismatch[0] == 409 and mismatch[1]['error']['code'] == 'generation_mismatch'
    assert c.ok('GET', f"/persons/{p['id']}")['profile'] == v3  # 錯誤不影響原設定
    assert c.ok('GET', '/characters?status=active')['items'] == []  # 不建立角色卡

    other, _, _ = account('aix')
    stolen = other.call('POST', '/ai/generate', {'request_id': 'steal', 'module': 'person_profile',
                                                 'input': {'person_id': p['id'], 'guidance': '', 'consent': True}})
    assert stolen[0] == 404, stolen  # 別人的人物：不預留、不呼叫

    again = Client()  # 新的工作階段重新登入讀回
    again.ok('POST', '/auth/login', {'username': username, 'password': password})
    assert again.ok('GET', f"/persons/{p['id']}")['profile'] == v3
