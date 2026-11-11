"""「我的人設」在 Cloud SQL 上的 API 驗收：Local 8030 → Cloud Run e2e → life_world_e2e（PostgreSQL）。

「我的人設」是 AI 扮演使用者本人時使用的設定（works／work_versions，kind=self_persona），2026-11-11 起在「我的紀錄」上方有入口。
只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號）：

    LW_E2E_PERSONS=1 .venv\\Scripts\\python.exe -m pytest -q tests/test_self_persona_cloudsql_e2e.py

驗收重點：建立、讀回、改版保留舊版、Revision 檢查、同一 request_id 重送、同意與撤回、Owner 隔離。
"""
import os

import pytest

from test_persons_cloudsql_e2e import account, preflight  # noqa: F401（preflight 是 autouse fixture）

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS') != '1', reason='部署後以 LW_E2E_PERSONS=1 對 Local 8030（Cloud SQL E2E）執行')

CONTENT = {'display_name': '合成測試者', 'public_profile': '喜歡桌遊與慢跑的工程師。', 'personality': '慢熟、好奇，遇到問題會先觀察。', 'speaking_style': '語速慢，常先確認對方的意思。',
           'motivation': '想把生活過得明白。', 'values': '說到做到。', 'behavior': '做決定前會列出選項。', 'knowledge': '熟悉軟體開發；不懂醫療。',
           'relationships': '和大學同學固定聚會。', 'boundaries': '不要替我做承諾。', 'appearance': '戴眼鏡。', 'sample_lines': ['先聽我說完。', '這個我想一下。'], 'truth_level': 'real'}


def save(client, request_id, revision=None, **changes):
    body = {'request_id': request_id, 'content': {**CONTENT, **changes}}
    if revision is not None:
        body['expected_revision'] = revision
    return client.call('PUT', '/self-persona', body)


def consent(client, request_id, granted):
    return client.call('POST', '/self-persona/consent', {'request_id': request_id, 'granted': granted})


def test_self_persona_save_versions_consent_and_owner_isolation_on_cloud_sql():
    c, _, _ = account('self')
    empty = c.ok('GET', '/self-persona')
    assert empty['persona'] is None and empty['consent'] is None and empty['consent_text']
    code, blocked = consent(c, 'self-c0', True)  # 還沒有人設不能同意
    assert code == 409 and blocked['error']['code'] == 'self_persona_required', blocked

    code, first = save(c, 'self-1')
    assert code == 200, first
    persona = first['persona']
    assert persona['version_no'] == 1 and persona['content'] == CONTENT  # 十二欄與真實程度原樣讀回
    assert save(c, 'self-1')[1]['persona']['work_id'] == persona['work_id']  # 同一 request_id 重送不重複建立
    assert c.ok('GET', '/self-persona')['persona'] == persona

    code, missing = save(c, 'self-no-revision', personality='改了')  # 已有人設時要帶 Revision
    assert code == 409 and missing['error']['code'] == 'revision_required', missing
    code, second = save(c, 'self-2', revision=persona['revision'], personality='慢熟、好奇、很有耐心。', sample_lines=[])
    assert code == 200 and second['persona']['version_no'] == 2 and second['persona']['work_id'] == persona['work_id'], second
    code, stale = save(c, 'self-stale', revision=persona['revision'], personality='過期分頁')
    assert code == 409 and stale['error']['code'] == 'revision_conflict', stale
    assert c.ok('GET', '/self-persona')['persona']['content']['personality'] == '慢熟、好奇、很有耐心。'
    assert c.ok('GET', '/works?kind=self_persona')['total'] == 1  # 一個帳號只有一份使用中的人設
    work = c.ok('GET', f"/works/{persona['work_id']}")
    assert [v['version_no'] for v in work['versions']] == [2, 1]  # 舊版本保留
    assert c.ok('GET', f"/works/{persona['work_id']}/versions/1")['content']['personality'] == CONTENT['personality']

    code, granted = consent(c, 'self-c1', True)
    assert code == 200 and granted['consent'] and granted['consent']['consent_version'] == 'self-persona-ai-v1', granted
    assert c.ok('GET', '/self-persona')['consent']['id'] == granted['consent']['id']
    code, revoked = consent(c, 'self-c2', False)
    assert code == 200 and revoked['consent'] is None and revoked['persona'] is not None, revoked
    code, again = consent(c, 'self-c3', True)
    assert code == 200 and again['consent']['id'] != granted['consent']['id'], again  # 撤回後重新同意是新的紀錄

    other, _, _ = account('selfb')  # 另一個帳號讀不到、也看不到這份人設
    assert other.ok('GET', '/self-persona')['persona'] is None
    assert other.call('GET', f"/works/{persona['work_id']}")[0] == 404
