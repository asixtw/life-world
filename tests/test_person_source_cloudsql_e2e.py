"""建立作品可以選人物：Cloud SQL 上的 API 驗收。Local 8030 → Cloud Run e2e → life_world_e2e（PostgreSQL）。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號）：

    LW_E2E_PERSONS=1 .venv\\Scripts\\python.exe -m pytest -q tests/test_person_source_cloudsql_e2e.py

這個環境的生成服務是真實模型。第一個案例只走「不會呼叫模型」的路徑：可選人物清單，以及建立前就被拒絕的情況
（拒絕發生在任何寫入與排程之前）。第二個案例會真的開始生成，要另外開啟，而且會計費：

    LW_E2E_PERSONS=1 LW_E2E_LIVE_GENERATION=1 .venv\\Scripts\\python.exe -m pytest -q tests/test_person_source_cloudsql_e2e.py

送給模型的內容（規劃只看公開簡介、人物發言時送九欄、雙方私有內容互不可見）在這個環境看不到，
由本機的擷取型 Fake Provider 測試驗證：tests/test_person_source_generation.py。
"""
import json
import os
import time

import pytest

from test_persons_cloudsql_e2e import PROFILE_TITLE, account, create, preflight, save  # noqa: F401（preflight 是 autouse fixture）

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS') != '1', reason='部署後以 LW_E2E_PERSONS=1 對 Local 8030（Cloud SQL E2E）執行')

FIELDS = {'background': '39 歲，展覽模型製作者，也接舞臺道具修補。', 'personality': '手藝要能說明依據；怕別人看見尚未完成的自己。',
          'motivation': '想留下別人能沿著接縫繼續追問的東西。', 'stance': '先看材料，再看故事；手作可以提出問題，不能替缺少的證據作答。',
          'abilities': '以材料、工序與用途提出問題；把大題目縮成能試做的小樣。', 'expression': '邊摸索邊確認，常說「先做一小塊」。',
          'behavior': '改動之前先問；被擅改作品會先停手。', 'knowledge_boundary': '不能只靠身分確定器物年代與真偽。',
          'restrictions': '很怕當著別人的面拆掉親手做好的部分。'}
SELF = {'display_name': '合成測試者', 'public_profile': '喜歡歷史與人文閱讀的上班族。', 'personality': '慢熟、好奇，做決定前先列選項。', 'speaking_style': '語氣平穩，不把話說滿。',
        'values': '說到做到。', 'boundaries': '不要替我做承諾。'}


def pick(person, **ref):
    return {'source': 'person', 'ref': {'person_id': person['id'], **ref}}


def start(client, participants, request_id, include_me=False):
    return client.call('POST', '/generation/runs', {'request_id': request_id, 'setup': {
        'participants': participants, 'include_me': include_me,
        'scene_context': {'description': '週六午後，虛構的社區展覽試作桌；桌上有一個紙模型和兩張標籤草稿。兩人初次見面。',
                          'start': {'event': '試讀標籤，發現「復原」兩字暗示有來源。', 'goal': '離開前選出能標明已知、推測與未知的暫用標籤。'}},
        'output': {'type': 'text', 'text': {'length': 'short', 'form': 'script'}}, 'title': '留一條接縫（驗收）'}})


def error(result):
    status, body = result
    return status, (body or {}).get('error', {}).get('code')


def archive(client, person, request_id):
    current = client.ok('GET', f"/persons/{person['id']}")['person']
    client.ok('POST', f"/persons/{person['id']}/status", {'request_id': request_id, 'expected_revision': current['revision'], 'status': 'archived'})


def test_castable_people_and_rejections_happen_before_any_work_or_model_call_on_cloud_sql():
    c, _, _ = account('cast')
    full = create(c, '溫若岑', 'cast-1', person_subtype='original', description='願意讓手藝留下接縫。', roles=['展覽模型製作者'])
    status, v1 = save(c, full['id'], 'cast-pf-1', None, **FIELDS)
    assert status == 200 and v1['version'] == 1, v1
    blank = create(c, '還沒填設定的人', 'cast-2')
    forged = {'schema': PROFILE_TITLE, 'version': 9, 'origin': 'manual', 'fields': FIELDS}  # 格式相同但沒有正式回執的私人筆記
    c.ok('POST', '/notes', {'person_id': blank['id'], 'kind': 'preparation', 'title': PROFILE_TITLE, 'content': json.dumps(forged, ensure_ascii=False)}, expected=(201,))
    gone = create(c, '封存的人', 'cast-3', person_subtype='original')
    assert save(c, gone['id'], 'cast-pf-3', None, **FIELDS)[0] == 200
    archive(c, gone, 'cast-arch')
    other, _, _ = account('castb')
    theirs = create(other, '別人的人物', 'cast-4', person_subtype='original')
    assert save(other, theirs['id'], 'cast-pf-4', None, **FIELDS)[0] == 200

    listing = c.ok('GET', '/generation/people')
    assert listing['enabled'] is True
    items = {item['id']: item for item in listing['items']}
    assert set(items) == {full['id'], blank['id']}, '只列本人使用中的人物'
    assert items[full['id']] == {'id': full['id'], 'name': '溫若岑', 'description': '願意讓手藝留下接縫。', 'person_type': 'fictional', 'person_subtype': 'original',
                                'roles': ['展覽模型製作者'], 'profile': {'id': v1['id'], 'version': 1}}
    assert items[blank['id']]['profile'] is None, '沒有回執的同格式筆記不算人物設定'
    assert [item['id'] for item in other.ok('GET', '/generation/people')['items']] == [theirs['id']]

    assert error(start(c, [pick(blank)], 'cast-r1')) == (409, 'person_profile_required')
    assert error(start(c, [pick(gone)], 'cast-r2')) == (409, 'person_archived')
    assert error(start(c, [pick(theirs)], 'cast-r3')) == (404, 'not_found')
    status, v2 = save(c, full['id'], 'cast-pf-2', v1['id'], **{**FIELDS, 'abilities': '能把大題目縮成小樣。'})
    assert status == 200 and v2['version'] == 2, v2
    assert error(start(c, [pick(full, profile_id=v1['id'])], 'cast-r4')) == (409, 'person_profile_changed')
    assert start(c, [pick(full), pick(full)], 'cast-r5')[0] == 422
    assert error(start(c, [pick(full), pick(blank)], 'cast-r6')) == (409, 'person_profile_required'), '名單裡有一位不合規就整筆拒絕'
    # 人物本身合格（已讀出並鎖定第 2 版），在「包含我」的檢查才被擋下；這一步讓人物來源的完整讀取路徑在 PostgreSQL 上執行，仍然沒有寫入。
    assert error(start(c, [pick(full, profile_id=v2['id'])], 'cast-r7', include_me=True)) == (409, 'self_persona_required')

    assert c.ok('GET', '/works?kind=generated_work')['total'] == 0, '被拒絕時沒有建立作品'
    assert c.ok('GET', '/generation/runs')['items'] == [], '沒有任何生成作品，也就沒有排程與模型呼叫'
    after = c.ok('GET', f"/persons/{full['id']}")
    assert after['person']['revision'] == full['revision'] and after['profile'] == v2, '人物與人物設定沒有被動到'
    latest = {item['id']: item['profile'] for item in c.ok('GET', '/generation/people')['items']}
    assert latest[full['id']] == {'id': v2['id'], 'version': 2}, '清單跟著最新的正式版本'


@pytest.mark.skipif(os.environ.get('LW_E2E_LIVE_GENERATION') != '1', reason='會呼叫真實模型並計費；取得授權後以 LW_E2E_LIVE_GENERATION=1 執行')
def test_live_generation_with_a_person_and_me_on_cloud_sql():
    c, _, _ = account('live')
    wen = create(c, '溫若岑', 'live-1', person_subtype='original', description='願意讓手藝留下接縫，卻很難讓別人看見自己的半成品。', roles=['展覽模型製作者'])
    status, profile = save(c, wen['id'], 'live-pf-1', None, **FIELDS)
    assert status == 200, profile
    assert c.call('PUT', '/self-persona', {'request_id': 'live-sp', 'content': SELF})[0] == 200
    assert c.ok('POST', '/self-persona/consent', {'request_id': 'live-consent', 'granted': True})['consent'] is not None
    state = c.ok('GET', '/state')
    before = (len(state['experiences']), len(state['drafts']), state['rewards']['total'], c.ok('GET', '/persons')['total'])

    status, started = start(c, [{**pick(wen, profile_id=profile['id']), 'position': 'supporting'}], 'live-run', include_me=True)
    assert status == 201 and started['module_id'] == 'T2', started
    deadline, detail = time.time() + 600, None
    while time.time() < deadline:  # 背景排程逐段生成；這裡只讀進度
        detail = c.ok('GET', f"/generation/runs/{started['id']}")
        if detail['run']['status'] in ('completed', 'failed'):
            break
        time.sleep(5)
    assert detail['run']['status'] == 'completed', detail['run']

    cast = {member['id']: member for member in detail['cast']}
    assert cast['c1']['source'] == 'person' and cast['c1']['person_id'] == wen['id'] and cast['c1']['version'] == 1
    assert cast['self']['is_user'] is True
    speakers = {segment['speaker_id'] for segment in detail['segments']}
    assert speakers == {'c1', 'self'}, '兩位都有發言，沒有第三位'
    assert all(segment['line'] or segment['action'] for segment in detail['segments'])
    assert 1 <= len(detail['segments']) == detail['run']['total_segments'] <= 40

    state = c.ok('GET', '/state')
    assert (len(state['experiences']), len(state['drafts']), state['rewards']['total'], c.ok('GET', '/persons')['total']) == before, '生成不寫回經歷、積分或人物'
    after = c.ok('GET', f"/persons/{wen['id']}")
    assert after['person']['revision'] == wen['revision'] and after['profile'] == profile
    assert c.ok('GET', '/self-persona')['persona']['version_no'] == 1
