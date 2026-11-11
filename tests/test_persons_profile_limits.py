"""人物設定欄位上限（2026-11-11 微調）：「說話與表達方式」放寬到 2000 字。

原始 15 張人物卡的「語言特徵與口癖」一節約 1100 字，加上示範台詞約 1500 字；原本 1000 字的上限放不下，
只能把後半段塞進「性格」。放寬後整節可以完整放在「說話與表達方式」。其他欄位上限不變。
"""
from conftest import onboard, register


def save(client, person_id, request_id, expected, **fields):
    return client.put(f'/api/persons/{person_id}/profile', json={'request_id': request_id, 'expected_profile_id': expected, 'fields': fields})


def test_expression_accepts_two_thousand_characters_and_other_limits_stay(client):
    onboard(client)
    register(client, 'limit_owner')
    person = client.post('/api/persons', json={'request_id': 'p-1', 'name': '沈知衡', 'person_subtype': 'original'}).json()
    saved = save(client, person['id'], 's-1', None, expression='語' * 2000)
    assert saved.status_code == 200, saved.text
    assert len(client.get(f"/api/persons/{person['id']}").json()['profile']['fields']['expression']) == 2000
    assert save(client, person['id'], 's-2', saved.json()['id'], expression='語' * 2001).status_code == 422
    assert save(client, person['id'], 's-3', saved.json()['id'], knowledge_boundary='知' * 1001).status_code == 422  # 其他欄位上限不變
    # 新增人物時一併保存的人物設定也適用同一個上限
    created = client.post('/api/persons', json={'request_id': 'p-2', 'name': '溫若岑', 'profile': {'expression': '語' * 1500}})
    assert created.status_code == 201, created.text
