"""8030 作品中心（2026-11-10，依 8445 已定案的統一生成作品中心）：作品列表依狀態分頁（進行中／已完成／失敗待恢復／全部）、
列出使用人物與進度、版本歷史；角色卡、我的人設、演出設定與人物演繹工具都不是作品，不混入列表。只用隔離 SQLite 與 Fake Provider。
"""
from fastapi.testclient import TestClient

from test_generation_8030 import LiveFake, client, copy_card, make_client, ready, run_to_end, start  # noqa: F401（pytest fixture）
from test_play_8030 import saved_story, start as start_session
from test_theater_8030 import card_member, save_cast, system, system_member


def center(client, tab='all', **params):
    response = client.get('/api/works/center', params={'tab': tab, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_center_groups_creations_by_phase_and_hides_character_cards(client):
    ready(client, 'center_owner')
    card = copy_card(client)
    run_id = start(client, [card]).json()['id']
    completed = run_to_end(client, run_id)
    assert completed['run']['status'] == 'completed'
    story = saved_story(client)
    session = start_session(client, story)
    cast = save_cast(client, [system_member(system(client, 0)), card_member(copy_card(client, 1))])
    everything = center(client)
    kinds = {item['kind'] for item in everything['items']}
    assert not kinds & {'character_card', 'self_persona', 'theater_cast', 'person_portrayal'}, '角色卡、人設、演出設定、人物演繹工具都不是作品'
    assert kinds == {'generated_work', 'story_opening', 'story_session'}
    by_id = {item['id']: item for item in everything['items']}
    assert by_id[run_id]['phase'] == 'completed' and by_id[run_id]['people'] == [card['version']['content']['name']]
    assert by_id[run_id]['progress']['done'] >= 1
    assert by_id[session['id']]['phase'] == 'active' and by_id[session['id']]['progress'] == {'done': 0, 'total': 5}
    assert by_id[story['id']]['phase'] == 'completed'
    assert cast['id'] not in by_id
    assert {item['id'] for item in center(client, 'active')['items']} == {session['id']}
    assert {item['id'] for item in center(client, 'completed')['items']} == {run_id, story['id']}
    assert center(client, 'failed')['items'] == []
    assert everything['counts'] == {'active': 1, 'completed': 2, 'failed': 0, 'all': 3}


def test_failed_runs_are_listed_as_recoverable(tmp_path, monkeypatch):
    monkeypatch.setenv('LIFEWORLD_AI_RESERVATION_MICROUSD', '1000')
    monkeypatch.setenv('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD', '1000000')
    monkeypatch.setenv('LIFEWORLD_AI_TOTAL_BUDGET_MICROUSD', '2000')  # 測試期總預算只夠 2 次：用完需要管理者處理，作品標為失敗（可恢復）
    with make_client(tmp_path, LiveFake()) as c:
        ready(c, 'center_failed')
        run_id = start(c, [copy_card(c)]).json()['id']
        detail = run_to_end(c, run_id)
        assert detail['run']['status'] == 'failed'
        failed = center(c, 'failed')['items']
        assert [item['id'] for item in failed] == [run_id] and failed[0]['can_resume'] is True


def test_version_history_lists_recent_versions_of_creations_only(client):
    ready(client, 'center_history')
    story = saved_story(client)
    session = start_session(client, story)
    history = client.get('/api/works/center/versions').json()['items']
    assert [(item['work_id'], item['version_no']) for item in history][:2] == [(session['id'], 1), (story['id'], 1)] or \
        {(item['work_id'], item['version_no']) for item in history} == {(session['id'], 1), (story['id'], 1)}
    assert all(item['kind'] not in ('character_card', 'self_persona') for item in history)
    other = TestClient(client.app)
    ready(other, 'center_other')
    assert center(other)['items'] == [] and other.get('/api/works/center/versions').json()['items'] == [], '只看得到自己的作品'


def test_new_works_are_generated_work_and_module_is_decided_by_server(client):
    """所有新作品都是 generated_work；T1／T2 由伺服器依人數判斷，前端不能自行指定模組。"""
    ready(client, 'center_module')
    one, two = copy_card(client), copy_card(client, 1)
    solo = start(client, [one], request_id='solo').json()
    duo = start(client, [one, two], request_id='duo').json()
    assert client.get(f"/api/works/{solo['id']}").json()['kind'] == 'generated_work'
    assert client.get(f"/api/generation/runs/{solo['id']}").json()['module'] == 'T1'
    assert client.get(f"/api/generation/runs/{duo['id']}").json()['module'] == 'T2'
    body = {'request_id': 'forced', 'setup': {'participants': [{'ref': {'work_id': one['id'], 'version_no': 1}}], 'include_me': False, 'module': 'T2',
                                              'scene_context': {'description': '碼頭'}, 'output': {'type': 'text', 'text': {'length': 'short', 'form': 'script'}}}}
    assert client.post('/api/generation/runs', json=body).status_code == 422, '設定契約不接受前端指定模組'
    image = {**body, 'request_id': 'image', 'setup': {**body['setup'], 'output': {'type': 'image'}}}
    image['setup'].pop('module')
    assert client.post('/api/generation/runs', json=image).status_code in (409, 422), '圖片尚未開放，不能假裝建立'


def test_material_uses_the_selected_history_version_snapshot(client):
    """⑤ 素材可以指定歷史版本：生成作品保存作品 ID、版本與該版本的內容雜湊；不會偷偷改用最新版。"""
    from app.roleplay import sha256
    ready(client, 'center_material')
    story = saved_story(client)
    v1 = client.get(f"/api/works/{story['id']}/versions/1").json()['content']
    edited = client.post(f"/api/stories/{story['id']}/versions", json={'request_id': 'story-v2', 'expected_revision': story['revision'], 'base_version': 1,
                                                                        'content': {**v1, 'objective': '第二版的目標'}})
    assert edited.status_code == 201 and edited.json()['current_version'] == 2
    card = copy_card(client)
    setup = {'participants': [{'ref': {'work_id': card['id'], 'version_no': 1}}], 'include_me': False,
             'scene_context': {'description': '碼頭', 'shared_history_refs': [{'work_id': story['id'], 'version_no': 1}]},
             'output': {'type': 'text', 'text': {'length': 'short', 'form': 'script'}}}
    work = client.post('/api/generation/runs', json={'request_id': 'with-material', 'setup': setup})
    assert work.status_code == 201, work.text
    materials = client.get(f"/api/works/{work.json()['id']}").json()['version']['content']['meta']['materials']
    assert [(m['work_id'], m['version_no']) for m in materials] == [(story['id'], 1)]
    assert materials[0]['content_sha256'] == sha256(v1), '保存的是第 1 版的內容雜湊'
    assert '第二版的目標' not in materials[0]['summary']
    detail = client.get(f"/api/generation/runs/{work.json()['id']}").json()
    assert detail['setup']['materials'][0]['version_no'] == 1


def test_list_segment_count_matches_detail_at_every_stage(tmp_path, monkeypatch):
    """作品列表與詳情用同一個實際保存的資料來源算已完成段數：0 段、1 段、多段、完成、恢復中都一致。"""
    monkeypatch.setenv('LIFEWORLD_AI_RESERVATION_MICROUSD', '1000')
    monkeypatch.setenv('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD', '1000000')
    monkeypatch.setenv('LIFEWORLD_AI_TOTAL_BUDGET_MICROUSD', '4000')  # 規劃＋3 段後總預算用完 → 失敗待恢復
    with make_client(tmp_path, LiveFake()) as c:
        ready(c, 'center_counts')
        work_id = start(c, [copy_card(c), copy_card(c, 1)]).json()['id']

        def both():
            listed = next(i for i in center(c)['items'] if i['id'] == work_id)
            detail = c.get(f'/api/generation/runs/{work_id}').json()
            assert listed['progress']['done'] == len(detail['segments']) == detail['run']['completed_segments']
            assert listed['progress']['total'] == detail['run']['total_segments']
            return listed['progress']['done'], listed['phase']
        assert both() == (0, 'active')  # 0 段（排隊中）
        c.post(f'/api/generation/runs/{work_id}/step')  # 規劃
        c.post(f'/api/generation/runs/{work_id}/step')  # 第 1 段
        assert both() == (1, 'active')
        c.post(f'/api/generation/runs/{work_id}/step')
        assert both() == (2, 'active')  # 多段
        run_to_end(c, work_id)
        assert both() == (3, 'failed')  # 失敗待恢復：已保存的段落照算
        monkeypatch.setenv('LIFEWORLD_AI_TOTAL_BUDGET_MICROUSD', '0')
        assert c.post(f'/api/generation/runs/{work_id}/resume', json={'request_id': 'resume'}).status_code == 200
        assert both() == (3, 'active')  # 恢復中
        run_to_end(c, work_id)
        done, phase = both()
        assert phase == 'completed' and done == c.get(f'/api/generation/runs/{work_id}').json()['run']['total_segments']


def test_legacy_roleplay_compat_routes_read_and_resume_without_creating(client):
    """8445 相容路由：/api/roleplay 讀取列表、詳情、風格與恢復；舊的新建入口不存在。"""
    ready(client, 'center_compat')
    work = start(client, [copy_card(client)], request_id='compat').json()
    run_to_end(client, work['id'])
    assert any(item['id'] == work['id'] for item in client.get('/api/roleplay').json()['items'])
    assert client.get(f"/api/roleplay/{work['id']}").json()['run']['status'] == 'completed'
    assert len(client.get('/api/roleplay/styles').json()['items']) == 11
    assert client.post(f"/api/roleplay/{work['id']}/resume", json={'request_id': 'r'}).status_code == 409, '已完成的作品不能恢復'
    assert client.post('/api/roleplay/runs', json={}).status_code in (404, 405), '舊的新建入口不存在'
