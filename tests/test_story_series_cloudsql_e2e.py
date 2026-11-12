"""多章節作品（續寫、採納、合集匯出）：Cloud SQL 與 Cloud Storage 上的 API 驗收。Local 8030 → Cloud Run e2e → life_world_e2e。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號）：

    LW_E2E_PERSONS=1 .venv\\Scripts\\python.exe -m pytest -q tests/test_story_series_cloudsql_e2e.py

續寫需要已完成的作品，而這個環境的生成服務是真實模型。所以分成兩個案例：
- 第一個不呼叫模型：端點已上線，不能續寫或採納的對象都被拒絕。
- 第二個會真的生成兩章（約 18 次模型呼叫，會計費），再採納、匯出合集並下載，要另外開啟：

    LW_E2E_PERSONS=1 LW_E2E_LIVE_GENERATION=1 .venv\\Scripts\\python.exe -m pytest -q tests/test_story_series_cloudsql_e2e.py

送給模型的內容在這個環境看不到；第二個案例改為核對草稿作品開始時鎖定的繼承內容（meta.continuity）。
規劃與逐段實際收到什麼，由本機的擷取型假模型測試驗證：tests/test_story_series.py。
"""
import hashlib
from html import escape
import os
import time

import pytest

from test_person_source_cloudsql_e2e import FIELDS, error, pick
from test_persons_cloudsql_e2e import account, create, preflight, save  # noqa: F401（preflight 是 autouse fixture）
from test_work_export_cloudsql_e2e import download

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS') != '1', reason='部署後以 LW_E2E_PERSONS=1 對 Local 8030（Cloud SQL E2E）執行')


def wait_completed(client, work_id, seconds=900):
    """背景排程逐段生成；這裡只讀進度。"""
    deadline, detail = time.time() + seconds, None
    while time.time() < deadline:
        detail = client.ok('GET', f'/generation/runs/{work_id}')
        if detail['run']['status'] in ('completed', 'failed'):
            break
        time.sleep(5)
    assert detail['run']['status'] == 'completed', detail['run']
    return detail


def test_series_endpoints_are_live_and_reject_what_cannot_be_continued_on_cloud_sql():
    c, _, _ = account('ser')
    card = c.ok('POST', '/characters', {'request_id': 'ser-card', 'content': {'name': '舊卡', 'kind': 'fictional'}}, expected=(201,))
    assert error(c.call('POST', '/series', {'request_id': 'ser-r1', 'work_id': 'no-such-work'})) == (404, 'not_found')
    assert error(c.call('POST', '/series', {'request_id': 'ser-r2', 'work_id': card['id']})) == (404, 'not_found'), '角色卡不能當第 1 章'
    assert error(c.call('GET', '/series/no-such-series')) == (404, 'not_found')
    assert error(c.call('GET', f"/series/{card['id']}")) == (404, 'not_found')
    scene = {'request_id': 'ser-r3', 'scene': {'description': '不存在的作品不能續寫。'}}
    assert error(c.call('POST', '/series/no-such-series/episodes', scene)) == (404, 'not_found')
    assert error(c.call('POST', '/series/no-such-series/episodes/no-such-work/adopt', {'request_id': 'ser-r4'})) == (404, 'not_found')
    assert c.ok('GET', '/works?kind=story_series')['total'] == 0 and c.ok('GET', '/generation/runs')['items'] == [], '被拒絕時沒有留下任何作品'


@pytest.mark.skipif(os.environ.get('LW_E2E_LIVE_GENERATION') != '1', reason='會呼叫真實模型並計費；取得同意後以 LW_E2E_LIVE_GENERATION=1 執行')
def test_live_two_chapters_are_continued_adopted_and_exported_as_one_html_on_cloud_sql():
    c, _, _ = account('serl')
    wen = create(c, '溫若岑', 'serl-1', person_subtype='original', description='願意讓手藝留下接縫，卻很難讓別人看見自己的半成品。', roles=['展覽模型製作者'])
    assert save(c, wen['id'], 'serl-pf', None, **FIELDS)[0] == 200
    status, started = c.call('POST', '/generation/runs', {'request_id': 'serl-run', 'setup': {
        'participants': [pick(wen)], 'include_me': False, 'title': '留一條接縫',
        'scene_context': {'description': '週六午後，虛構的社區展覽試作桌；桌上有一個紙模型和兩張標籤草稿。溫若岑一個人在收尾，自言自語地檢查標籤上的用字。'},
        'output': {'type': 'text', 'text': {'length': 'short', 'form': 'script'}}}})
    assert status == 201, started
    first = wait_completed(c, started['id'])

    status, series = c.call('POST', '/series', {'request_id': 'serl-open', 'work_id': started['id']})
    assert status == 201 and series['next_episode_no'] == 2 and [item['work_id'] for item in series['episodes']] == [started['id']], series
    sid = series['id']
    status, draft = c.call('POST', f'/series/{sid}/episodes', {'request_id': 'serl-ep2', 'title': '開門之前',
                                                               'scene': {'description': '隔天早上，展場開門前半小時。溫若岑回到試作桌前，要把昨天留下的標籤定案。'}})
    assert status == 201 and draft['series_id'] == sid and draft['base_episode_no'] == 1, draft
    listed = c.ok('GET', f'/series/{sid}')
    assert len(listed['episodes']) == 1 and [item['work_id'] for item in listed['drafts']] == [draft['id']], '草稿不影響主線'
    assert error(c.call('POST', f"/series/{sid}/episodes/{draft['id']}/adopt", {'request_id': 'serl-early'})) == (409, 'work_not_completed')

    # 草稿開始時鎖定的繼承內容：第 1 章的大綱、結尾，以及人物最後的狀態與記憶
    continuity = c.ok('GET', f"/works/{draft['id']}")['version']['content']['meta']['continuity']
    assert continuity['episodes'] == [{'no': 1, 'title': first['plan']['title'], 'premise': first['plan']['premise'],
                                       'beats': [beat['goal'] for beat in first['plan']['beats']],
                                       'scene': first['setup']['scene']['description']}]  # 連同第 1 章使用者寫的場景
    assert [(item['speaker'], item['line'], item['action']) for item in continuity['last_scene']] == \
        [(seg['speaker_name'], seg['line'], seg['action']) for seg in first['segments'][-6:]]
    character = continuity['characters']['person:' + wen['id']]
    assert character['name'] == '溫若岑' and character['state'] and len(character['memories']) <= 12

    second = wait_completed(c, draft['id'])
    assert second['series'] == {'id': sid, 'title': '留一條接縫', 'episode_no': None, 'is_draft': True}
    assert [member['source'] for member in second['cast']] == ['person']
    status, adopted = c.call('POST', f"/series/{sid}/episodes/{draft['id']}/adopt", {'request_id': 'serl-adopt'})
    assert status == 200 and [(item['no'], item['work_id']) for item in adopted['episodes']] == [(1, started['id']), (2, draft['id'])], adopted
    assert adopted['drafts'] == [] and adopted['next_episode_no'] == 3
    assert c.ok('GET', f"/generation/runs/{draft['id']}")['series']['episode_no'] == 2
    assert error(c.call('POST', f"/series/{sid}/episodes/{draft['id']}/adopt", {'request_id': 'serl-adopt-2'})) == (409, 'already_adopted')

    status, body = c.call('POST', f'/works/{sid}/exports', {'request_id': 'serl-export', 'format': 'html'})
    assert status == 201, body
    item = body['export']
    status, data, headers = download(c, item['download_path'])
    assert status == 200 and hashlib.sha256(data).hexdigest() == item['sha256'] and headers['Content-Disposition'].startswith('attachment;')
    html = data.decode('utf-8')
    assert '目錄' in html and 'href="#ch-1"' in html and 'href="#ch-2"' in html and escape('開門之前') in html
    assert html.count('<article class="lw-seg"') == len(first['segments']) + len(second['segments'])  # reader-3 起段落元素帶人物色號屬性
    for segment in first['segments'] + second['segments']:
        assert escape(segment['line']) in html
    for value in FIELDS.values():
        assert escape(value) not in html, '檔案裡沒有人物設定'

    other, _, _ = account('serlb')
    assert error(other.call('GET', f'/series/{sid}')) == (404, 'not_found')
    assert download(other, item['download_path'])[0] == 404
    after = c.ok('GET', f"/persons/{wen['id']}")
    assert after['person']['revision'] == wen['revision'] and after['profile']['version'] == 1, '續寫與採納不寫回人物'
    kinds = sorted(entry['kind'] for entry in c.ok('GET', '/works/center?tab=all')['items'])
    assert kinds == ['generated_work', 'generated_work', 'story_series'], '作品中心：兩章與這部多章節作品'
