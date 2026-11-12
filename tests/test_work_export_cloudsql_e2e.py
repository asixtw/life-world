"""作品匯出成 HTML：Cloud SQL 與 Cloud Storage 上的 API 驗收。Local 8030 → Cloud Run e2e → life_world_e2e、bucket lw-works-e2e-513506。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號）：

    LW_E2E_PERSONS=1 .venv\\Scripts\\python.exe -m pytest -q tests/test_work_export_cloudsql_e2e.py

匯出需要一件已完成的作品，而這個環境的生成服務是真實模型。所以分成兩個案例：
- 第一個不呼叫模型：確認匯出功能已開放（bucket 設定和環境白名單一致），以及不能匯出的對象都被拒絕。
- 第二個會真的生成一件作品再匯出、下載，要另外開啟，而且會計費（約 1 次規劃＋8 段）：

    LW_E2E_PERSONS=1 LW_E2E_LIVE_GENERATION=1 .venv\\Scripts\\python.exe -m pytest -q tests/test_work_export_cloudsql_e2e.py

  這也是第一次實際使用服務帳號在 bucket 上的新增與讀取權限。
"""
import hashlib
from html import escape
import os
import re
import time
import urllib.error
import urllib.request

import pytest

from test_person_source_cloudsql_e2e import FIELDS, error, pick
from test_persons_cloudsql_e2e import account, create, preflight, save  # noqa: F401（preflight 是 autouse fixture）
from test_relation_sources_cloudsql_e2e import BASE

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS') != '1', reason='部署後以 LW_E2E_PERSONS=1 對 Local 8030（Cloud SQL E2E）執行')
TITLE = '留一條接縫（匯出驗收）'


def export(client, work_id, request_id):
    return client.call('POST', f'/works/{work_id}/exports', {'request_id': request_id, 'format': 'html'})


def download(client, path):
    """下載回來的是 HTML，不是 JSON：用同一個登入工作階段直接讀位元組與標頭。"""
    try:
        with client.opener.open(urllib.request.Request(BASE + path), timeout=60) as response:
            return response.status, response.read(), response.headers
    except urllib.error.HTTPError as failure:
        return failure.code, failure.read(), failure.headers


def test_export_is_open_on_e2e_and_rejects_what_cannot_be_exported_on_cloud_sql():
    c, _, _ = account('exp')
    assert c.ok('GET', '/capabilities')['work_export_available'] is True, '部署的 bucket 設定和環境白名單一致，匯出才會開放'
    assert error(c.call('GET', '/works/no-such-work/exports')) == (404, 'not_found')
    assert error(export(c, 'no-such-work', 'exp-r1')) == (404, 'not_found')
    card = c.ok('POST', '/characters', {'request_id': 'exp-card', 'content': {'name': '舊卡', 'kind': 'fictional'}}, expected=(201,))
    assert error(c.call('GET', f"/works/{card['id']}/exports")) == (404, 'not_found'), '角色卡不是可匯出的作品'
    assert error(export(c, card['id'], 'exp-r2')) == (404, 'not_found')
    assert c.call('GET', f"/works/{card['id']}/exports/1/download")[0] == 404
    assert c.ok('GET', '/works?kind=work_export')['total'] == 0, '被拒絕時沒有留下匯出紀錄'


@pytest.mark.skipif(os.environ.get('LW_E2E_LIVE_GENERATION') != '1', reason='會呼叫真實模型並計費；取得同意後以 LW_E2E_LIVE_GENERATION=1 執行')
def test_live_work_is_exported_to_cloud_storage_and_downloads_unchanged_on_cloud_sql():
    c, _, _ = account('expl')
    wen = create(c, '溫若岑', 'expl-1', person_subtype='original', description='願意讓手藝留下接縫，卻很難讓別人看見自己的半成品。', roles=['展覽模型製作者'])
    assert save(c, wen['id'], 'expl-pf', None, **FIELDS)[0] == 200
    status, started = c.call('POST', '/generation/runs', {'request_id': 'expl-run', 'setup': {
        'participants': [pick(wen)], 'include_me': False, 'title': TITLE,
        'scene_context': {'description': '週六午後，虛構的社區展覽試作桌；桌上有一個紙模型和兩張標籤草稿。溫若岑一個人在收尾，自言自語地檢查標籤上的用字。'},
        'output': {'type': 'text', 'text': {'length': 'short', 'form': 'script'}}}})
    assert status == 201 and started['module_id'] == 'T1', started
    work_id = started['id']
    assert error(export(c, work_id, 'expl-early')) == (409, 'work_not_completed'), '還沒完成不能匯出'

    deadline, detail = time.time() + 600, None
    while time.time() < deadline:  # 背景排程逐段生成；這裡只讀進度
        detail = c.ok('GET', f'/generation/runs/{work_id}')
        if detail['run']['status'] in ('completed', 'failed'):
            break
        time.sleep(5)
    assert detail['run']['status'] == 'completed', detail['run']
    assert c.ok('GET', f'/works/{work_id}/exports') == {'available': True, 'items': []}

    status, body = export(c, work_id, 'expl-1')
    assert status == 201, body
    item = body['export']
    assert item['version_no'] == 1 and item['format'] == 'html' and item['player'] == 'reader-3' and item['filename'] == TITLE + '.html'
    status, data, headers = download(c, item['download_path'])
    assert status == 200 and len(data) == item['size'] and hashlib.sha256(data).hexdigest() == item['sha256'], '從 Cloud Storage 讀回來的檔案和紀錄一致'
    assert headers['Content-Type'].startswith('text/html') and headers['Content-Disposition'].startswith('attachment;')
    assert 'sandbox' in headers['Content-Security-Policy']

    html = data.decode('utf-8')
    assert html.startswith('<!doctype html>') and escape(TITLE) in html and '溫若岑' in html
    assert not re.search(r'(src|href|action)\s*=\s*["\']?(https?:)?//', html), '不引用任何外部資源'
    for segment in detail['segments']:
        for text in (segment['line'], segment['action'], segment['stage_direction']):
            assert escape(text) in html
    for value in FIELDS.values():
        assert escape(value) not in html, '檔案裡沒有人物設定'

    assert export(c, work_id, 'expl-2') == (201, body), '內容沒有變：回同一筆，不重複存檔'
    assert export(c, work_id, 'expl-1') == (201, body), '同一提交代碼重送回原結果'
    assert c.ok('GET', f'/works/{work_id}/exports') == {'available': True, 'items': [item]}

    other, _, _ = account('explb')
    assert error(other.call('GET', f'/works/{work_id}/exports')) == (404, 'not_found')
    assert download(other, item['download_path'])[0] == 404, '別人拿到下載網址也讀不到'
    after = c.ok('GET', f'/generation/runs/{work_id}')
    assert after == detail, '匯出不改動作品'
    assert c.ok('GET', '/works/center?tab=all')['total'] == 1 and c.ok('GET', '/works?kind=work_export')['total'] == 1
