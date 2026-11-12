"""第 2 級：一部作品分批續寫（多章節作品）。

名詞：
- 多章節作品（works.kind='story_series'）：一部持續成長的作品；每次「採納」新增一個版本，記下主線收錄了哪幾章與最新的檢查點。
- 一章＝一件既有的生成作品（generated_work）。續寫出來的先是草稿，採納後才成為主線的下一章。
- 檢查點：各章大綱（規劃時模型寫的標題、前提與節拍）、上一章最後幾段、每位人物最後的狀態與記憶。全部取自已保存的內容，不另外呼叫模型。

驗證重點：
1. 已完成的作品可以成為多章節作品的第 1 章；其他一律拒絕。
2. 續寫時，規劃看得到前面各章的大綱與上一章結尾；每位人物發言時帶著自己上一章的記憶與狀態，看不到別人的記憶。
3. 草稿不影響主線；採納之後主線才往前；接在舊進度上的草稿不能採納。
4. 多章節作品可以匯出成一個有目錄的 HTML，只包含已採納的章節。
5. 擁有者隔離；續寫與採納都不寫回人物、人物設定、我的設定、我的經歷或積分。

這是本機 SQLite 的開發檢查（擷取型假模型＋記憶體儲存，不連網、不計費）。
"""
from datetime import datetime, timezone
import json

import pytest
from fastapi.testclient import TestClient

from app.config import DemoPolicy
from app.main import create_app
from app.object_storage import MemoryStorage
from app.story_series import story_so_far
from test_person_source_generation import PRIVATE_MARKS, Capture, code, fields, person, pick, ready, run_to_end, sent, side_effects, text_of, with_me
from test_work_export import story_block

FAKE = '（測試用假回應）'
STATE = {'emotion': '平靜', 'stance': '觀察', 'goal': FAKE[:8] + '推進節拍'}


def memory(turn_no):
    return f'{FAKE}第 {turn_no} 段我說過話。'


@pytest.fixture
def env(tmp_path):
    provider, storage = Capture(), MemoryStorage()
    app = create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                     clock=lambda: datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc), generation_provider=provider, work_storage=storage)
    with TestClient(app) as client:
        yield client, provider, storage


def first_work(client, include_me=True):
    """一位有人物設定的人物（加上我）生成到完成；回傳（人物, 作品識別碼, 作品詳情）。"""
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original', description='〔P1公開〕願意讓手藝留下接縫。')
    if include_me:
        with_me(client)
    body = {'request_id': 'run-1', 'setup': {'participants': [pick(wen, position='supporting')], 'include_me': include_me, 'title': '留一條接縫',
                                             'scene_context': {'description': '週六午後，社區展覽的試作桌。'},
                                             'output': {'type': 'text', 'text': {'length': 'short', 'form': 'script'}}}}
    started = client.post('/api/generation/runs', json=body)
    assert started.status_code == 201, started.text
    detail = run_to_end(client, started.json()['id'])
    assert detail['run']['status'] == 'completed'
    return wen, started.json()['id'], detail


def open_series(client, work_id, request_id='series-1'):
    return client.post('/api/series', json={'request_id': request_id, 'work_id': work_id})


def next_chapter(client, series_id, request_id, scene='隔天早上，展場開門前。', **extra):
    return client.post(f'/api/series/{series_id}/episodes', json={'request_id': request_id, 'scene': {'description': scene}, **extra})


def adopt(client, series_id, work_id, request_id):
    return client.post(f'/api/series/{series_id}/episodes/{work_id}/adopt', json={'request_id': request_id})


def test_a_completed_work_becomes_the_first_chapter_of_a_series(env):
    client, _, _ = env
    ready(client)
    wen, work_id, detail = first_work(client)
    waiting = client.post('/api/generation/runs', json={'request_id': 'run-wait', 'setup': {
        'participants': [pick(wen)], 'include_me': False, 'scene_context': {'description': '還沒開始的作品。'}}}).json()['id']
    card = client.post('/api/characters', json={'request_id': 'card-1', 'content': {'name': '舊卡', 'kind': 'fictional'}}).json()
    assert code(open_series(client, waiting, 's-wait')) == (409, 'work_not_completed'), '還沒完成的作品不能當第 1 章'
    assert code(open_series(client, card['id'], 's-card')) == (404, 'not_found')
    assert code(open_series(client, 'no-such-work', 's-none')) == (404, 'not_found')
    other = TestClient(client.app)
    ready(other, 'series_other')
    assert code(open_series(other, work_id, 's-theirs')) == (404, 'not_found'), '別人的作品一律 404'

    created = open_series(client, work_id)
    assert created.status_code == 201, created.text
    series = created.json()
    assert series['title'] == '留一條接縫' and series['next_episode_no'] == 2 and series['drafts'] == []
    assert [(member['name'], member['position'], member['is_user']) for member in series['cast']] == [('溫若岑', 'supporting', False), ('小光', None, True)]
    assert len(series['episodes']) == 1
    chapter = series['episodes'][0]
    assert {key: chapter[key] for key in ('no', 'work_id', 'title', 'segments')} == {'no': 1, 'work_id': work_id, 'title': '留一條接縫', 'segments': len(detail['segments'])}
    assert open_series(client, work_id, 'series-again').json() == series, '同一件作品只會有一部多章節作品'
    assert client.get(f"/api/series/{series['id']}").json() == series
    assert code(other.get(f"/api/series/{series['id']}")) == (404, 'not_found')

    assert client.get(f'/api/generation/runs/{work_id}').json()['series'] == {'id': series['id'], 'title': '留一條接縫', 'episode_no': 1, 'is_draft': False}
    assert client.get(f'/api/generation/runs/{waiting}').json()['series'] is None
    listed = {item['id']: item for item in client.get('/api/works/center?tab=all').json()['items']}
    assert listed[series['id']]['kind'] == 'story_series' and listed[series['id']]['people'] == ['溫若岑', '小光']
    assert listed[series['id']]['progress'] == {'done': 1, 'total': None}, '作品中心列出這部多章節作品與已定稿的章數'


def test_the_next_chapter_inherits_the_outline_the_last_scene_and_each_characters_own_memory(env):
    client, provider, _ = env
    ready(client)
    wen, work_id, first = first_work(client)
    owner = wen['owner_id']
    series = open_series(client, work_id).json()
    before = side_effects(client, owner)
    provider.requests.clear()

    started = next_chapter(client, series['id'], 'ep-2', title='開門之前')
    assert started.status_code == 201, started.text
    draft = started.json()
    assert draft['module_id'] == 'T2' and draft['series_id'] == series['id'] and draft['base_episode_no'] == 1
    second = run_to_end(client, draft['id'])
    assert second['run']['status'] == 'completed'
    assert second['series'] == {'id': series['id'], 'title': '留一條接縫', 'episode_no': None, 'is_draft': True}
    assert [(member['id'], member['source']) for member in second['cast']] == [('c1', 'person'), ('self', 'self')], '人物沿用第 1 章的陣容'

    plan = sent(provider, 'roleplay_plan')[0]
    outline = {'no': 1, 'title': first['plan']['title'], 'premise': first['plan']['premise'], 'beats': [beat['goal'] for beat in first['plan']['beats']],
               'scene': '週六午後，社區展覽的試作桌。'}  # 2026-11-12：連同那一章使用者寫的場景（故事裡已經成立的設定）
    tail = [{'speaker': seg['speaker_name'], 'line': seg['line'], 'action': seg['action']} for seg in first['segments'][-6:]]
    assert plan['story_so_far'] == {'episodes': [outline], 'last_scene': tail}, '規劃看得到前面各章的大綱與上一章最後幾段'
    assert plan['scene']['description'] == '隔天早上，展場開門前。'
    assert not any(mark in text_of(plan) for mark in PRIVATE_MARKS), '規劃仍然看不到任何人的私有設定'

    segments = sent(provider, 'roleplay_segment')
    hers = [payload for payload in segments if payload['turn']['speaker']['id'] == 'c1']
    mine = [payload for payload in segments if payload['turn']['speaker']['id'] == 'self']
    assert hers[0]['memories'] == [memory(n) for n in (1, 3, 5, 7)], '人物帶著自己上一章的記憶'
    assert mine[0]['memories'] == [memory(n) for n in (2, 4, 6, 8)], '我帶著我自己的；彼此看不到對方的記憶'
    assert hers[0]['last_state'] == STATE and mine[0]['last_state'] == STATE, '第一次發言時接續上一章結束時的狀態'
    assert hers[1]['memories'] == [memory(n) for n in (1, 3, 5, 7)] + [memory(hers[0]['turn']['turn_no'])], '之後再接上這一章自己的記憶'
    assert all(payload['story_so_far'] == {'episodes': [outline], 'last_scene': tail} for payload in segments)
    assert hers[0]['turn']['speaker']['persona']['background'] == '〔P1:background〕', '人物設定照常鎖定並送出'

    with client.app.state.service.db.connect() as db:
        versions = {row['module']: row['prompt_version'] for row in db.execute(
            'SELECT module,prompt_version FROM ai_generations WHERE request_id LIKE ?', (f"rp:{draft['id']}:%",)).fetchall()}
    from app.generation import MODULES
    assert versions == {'roleplay_plan': MODULES['roleplay_plan'].prompt_version, 'roleplay_segment': MODULES['roleplay_segment'].prompt_version}, '續寫的章節用現行版本'
    assert 'story_so_far' in MODULES['roleplay_plan'].system and 'story_so_far' in MODULES['roleplay_segment'].system, '延續前面章節的規則仍在'
    assert side_effects(client, owner) == before, '續寫不寫回人物、人物設定、我的設定、同意、我的經歷或積分'

    plain = [payload for payload in (json.loads(request.user) for request in provider.requests)]
    assert all('story_so_far' in payload for payload in plain)
    provider.requests.clear()  # 不屬於多章節作品的一般作品：沒有繼承的內容
    solo = client.post('/api/generation/runs', json={'request_id': 'run-solo', 'setup': {
        'participants': [pick(wen)], 'include_me': False, 'scene_context': {'description': '另一件獨立的作品。'}}}).json()['id']
    assert run_to_end(client, solo)['run']['status'] == 'completed'
    assert not any('story_so_far' in json.loads(request.user) for request in provider.requests)
    assert sent(provider, 'roleplay_segment')[0]['last_state'] is None


def test_drafts_do_not_move_the_story_until_adopted_and_stale_drafts_cannot_be_adopted(env):
    client, provider, _ = env
    ready(client)
    _, work_id, _ = first_work(client)
    series = open_series(client, work_id).json()
    sid = series['id']
    draft_a = next_chapter(client, sid, 'ep-a', scene='甲案：隔天早上。').json()['id']
    draft_b = next_chapter(client, sid, 'ep-b', scene='乙案：當天晚上。').json()['id']
    assert next_chapter(client, sid, 'ep-a', scene='甲案：隔天早上。').json()['id'] == draft_a, '同一提交代碼重送回原結果'
    assert client.post(f'/api/series/{sid}/episodes', json={'request_id': 'ep-empty', 'scene': {'description': ''}}).status_code == 422

    listed = client.get(f'/api/series/{sid}').json()
    assert len(listed['episodes']) == 1 and listed['next_episode_no'] == 2, '草稿不影響主線'
    assert [(item['work_id'], item['base_episode_no'], item['can_adopt']) for item in listed['drafts']] == [(draft_a, 1, False), (draft_b, 1, False)]
    assert code(adopt(client, sid, draft_a, 'ad-early')) == (409, 'work_not_completed'), '還沒完成的草稿不能採納'
    done_a, done_b = run_to_end(client, draft_a), run_to_end(client, draft_b)
    assert done_a['run']['status'] == done_b['run']['status'] == 'completed'
    assert all(item['can_adopt'] for item in client.get(f'/api/series/{sid}').json()['drafts'])

    adopted = adopt(client, sid, draft_a, 'ad-a')
    assert adopted.status_code == 200, adopted.text
    after = adopted.json()
    assert [(item['no'], item['work_id']) for item in after['episodes']] == [(1, work_id), (2, draft_a)] and after['next_episode_no'] == 3
    assert [(item['work_id'], item['can_adopt']) for item in after['drafts']] == [(draft_b, False)], '接在第 1 章後面的另一份草稿已經過時'
    assert adopt(client, sid, draft_a, 'ad-a').json() == after, '同一提交代碼重送回原結果'
    assert code(adopt(client, sid, draft_a, 'ad-a2')) == (409, 'already_adopted')
    assert code(adopt(client, sid, draft_b, 'ad-b')) == (409, 'series_base_changed'), '主線已經往前，舊進度上的草稿不能採納'
    assert code(adopt(client, sid, work_id, 'ad-root')) == (409, 'already_adopted')
    assert code(adopt(client, sid, 'no-such-work', 'ad-none')) == (404, 'not_found')
    assert client.get(f'/api/generation/runs/{draft_a}').json()['series']['episode_no'] == 2
    assert client.get(f'/api/generation/runs/{draft_b}').json()['series'] == {'id': sid, 'title': '留一條接縫', 'episode_no': None, 'is_draft': True}

    current = client.get(f'/api/works/{draft_b}').json()
    discarded = client.post(f'/api/works/{draft_b}/status', json={'request_id': 'discard-b', 'expected_revision': current['revision'], 'status': 'archived'})
    assert discarded.status_code == 200, discarded.text
    assert client.get(f'/api/series/{sid}').json()['drafts'] == [], '捨棄的草稿不再列出'
    assert code(adopt(client, sid, draft_b, 'ad-b2')) == (409, 'series_base_changed')

    provider.requests.clear()
    draft_c = next_chapter(client, sid, 'ep-c', scene='第三章：展覽開幕。').json()
    assert draft_c['base_episode_no'] == 2
    assert run_to_end(client, draft_c['id'])['run']['status'] == 'completed'
    plan = sent(provider, 'roleplay_plan')[0]
    assert [item['no'] for item in plan['story_so_far']['episodes']] == [1, 2], '第三章看得到前兩章的大綱'
    assert plan['story_so_far']['last_scene'] == [{'speaker': seg['speaker_name'], 'line': seg['line'], 'action': seg['action']} for seg in done_a['segments'][-6:]]
    hers = [payload for payload in sent(provider, 'roleplay_segment') if payload['turn']['speaker']['id'] == 'c1']
    assert hers[0]['memories'] == [memory(n) for n in (1, 3, 5, 7)] * 2, '記憶逐章累積（第 1 章四則＋第 2 章四則）'

    other = TestClient(client.app)
    ready(other, 'series_other')
    assert code(other.get(f'/api/series/{sid}')) == (404, 'not_found')
    assert code(next_chapter(other, sid, 'ep-theirs')) == (404, 'not_found')
    assert code(adopt(other, sid, draft_c['id'], 'ad-theirs')) == (404, 'not_found')


def test_a_series_exports_one_html_with_a_table_of_contents_and_only_adopted_chapters(env):
    client, _, storage = env
    ready(client)
    _, work_id, first = first_work(client, include_me=False)
    sid = open_series(client, work_id).json()['id']
    second_id = next_chapter(client, sid, 'ep-2', scene='第二章的場景：展場開門前。', title='開門之前').json()['id']
    second = run_to_end(client, second_id)
    unadopted = next_chapter(client, sid, 'ep-x', scene='沒有被採納的草稿場景。').json()['id']
    assert run_to_end(client, unadopted)['run']['status'] == 'completed'
    assert adopt(client, sid, second_id, 'ad-2').status_code == 200

    created = client.post(f'/api/works/{sid}/exports', json={'request_id': 'ex-series', 'format': 'html'})
    assert created.status_code == 201, created.text
    item = created.json()['export']
    assert item['filename'] == '留一條接縫.html' and item['player'] == 'reader-3'
    html = storage.objects[next(name for name in storage.objects if f'/{sid}/' in name)].decode('utf-8')
    assert '目錄' in html and 'href="#ch-1"' in html and 'href="#ch-2"' in html and 'id="ch-2"' in html
    assert '第 1 章' in html and '第 2 章' in html and '開門之前' in html
    assert html.count('<article class="lw-seg" data-c="1">') == len(first['segments']) + len(second['segments'])  # reader-3：段落帶著說話者的色號（這裡只有一位人物）
    assert '第二章的場景：展場開門前。' in html and '沒有被採納的草稿場景。' not in html, '只包含已採納的章節'
    story = json.loads(story_block(html))
    assert story['format'] == 'lw-story.v3' and [chapter['no'] for chapter in story['chapters']] == [1, 2]
    assert [seg['line'] for beat in story['chapters'][1]['beats'] for seg in beat['segments']] == [seg['line'] for seg in second['segments']]

    downloaded = client.get(item['download_path'])
    assert downloaded.status_code == 200 and downloaded.content == html.encode('utf-8')
    assert client.post(f'/api/works/{sid}/exports', json={'request_id': 'ex-series-2', 'format': 'html'}).json()['export'] == item, '內容沒有變：同一筆'
    single = client.post(f'/api/works/{work_id}/exports', json={'request_id': 'ex-single', 'format': 'html'})
    assert single.status_code == 201 and '目錄' not in storage.objects[next(name for name in storage.objects if f'/{work_id}/' in name)].decode('utf-8'), '單一作品沒有目錄'


def test_each_character_only_sees_the_part_of_the_last_scene_they_witnessed():
    continuity = {'episodes': [{'no': 1, 'title': '一', 'premise': '', 'beats': ['開場']}],
                  'last_scene': [{'speaker': '甲', 'line': '大家都在', 'action': '', 'witnesses': ['person:a', 'person:b', 'self']},
                                 {'speaker': '乙', 'line': '甲不在場時說的話', 'action': '', 'witnesses': ['person:b', 'self']}],
                  'characters': {}}
    everything = story_so_far(continuity)
    assert [item['line'] for item in everything['last_scene']] == ['大家都在', '甲不在場時說的話'] and 'witnesses' not in everything['last_scene'][0]
    assert [item['line'] for item in story_so_far(continuity, 'person:a')['last_scene']] == ['大家都在'], '人物不知道自己不在場時發生的事'
    assert [item['line'] for item in story_so_far(continuity, 'self')['last_scene']] == ['大家都在', '甲不在場時說的話']
    assert story_so_far(None) is None and story_so_far(None, 'self') is None


def test_overview_reports_the_output_setting_so_the_next_chapter_keeps_the_same_form(env):
    """2026-11-12 真實模型驗收時發現：第 1 章選小說敘事，續寫表單卻預設成劇本對白，第 2 章就換了呈現形式。
    作品總覽要回報這部作品的長度與呈現形式，續寫表單用它當預設；沒有指定時伺服器本來就沿用第 1 章。"""
    client, _, _ = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original', description='模型製作者。')
    started = client.post('/api/generation/runs', json={'request_id': 'run-n', 'setup': {
        'participants': [pick(wen)], 'include_me': False, 'title': '屋頂的紋樣', 'scene_context': {'description': '開幕前一晚的試作桌。'},
        'output': {'type': 'text', 'text': {'length': 'short', 'form': 'narrative'}}}})
    assert started.status_code == 201, started.text
    assert run_to_end(client, started.json()['id'])['run']['status'] == 'completed'
    series = open_series(client, started.json()['id']).json()
    assert series['output'] == {'length': 'short', 'form': 'narrative'}
    assert client.get(f"/api/series/{series['id']}").json()['output'] == {'length': 'short', 'form': 'narrative'}
    draft = next_chapter(client, series['id'], 'ep-2')
    assert draft.status_code == 201, draft.text
    assert client.get(f"/api/generation/runs/{draft.json()['id']}").json()['setup']['form'] == 'narrative', '沒有指定就沿用第 1 章的呈現形式'


def test_each_chapter_outline_carries_the_scene_and_conditions_the_user_wrote(env):
    """2026-11-12 真實模型驗收時發現：第 1 章的場景寫明「紋樣沒有任何依據」，第 2 章人物卻說紋樣是照榫頭位置推敲的。
    各章大綱原本只有模型寫的標題、前提與節拍；使用者寫的場景與條件才是故事裡已經成立的設定，要一起帶到後面的章節。"""
    from app.story_continuity import episode_outline
    client, provider, _ = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original', description='模型製作者。')
    started = client.post('/api/generation/runs', json={'request_id': 'run-f', 'setup': {
        'participants': [pick(wen)], 'include_me': False, 'title': '屋頂的紋樣',
        'scene_context': {'description': '開幕前一晚的試作桌。屋頂的紋樣是照想像補上的。', 'conditions': ['紋樣沒有任何依據', '印刷廠半小時後截稿']},
        'output': {'type': 'text', 'text': {'length': 'short', 'form': 'script'}}}})
    assert started.status_code == 201, started.text
    assert run_to_end(client, started.json()['id'])['run']['status'] == 'completed'
    series = open_series(client, started.json()['id']).json()

    provider.requests.clear()
    second = next_chapter(client, series['id'], 'ep-2', scene='隔天早上，展場開門前。')
    assert run_to_end(client, second.json()['id'])['run']['status'] == 'completed'
    for payload in sent(provider, 'roleplay_plan') + sent(provider, 'roleplay_segment'):
        first = payload['story_so_far']['episodes'][0]
        assert first['scene'] == '開幕前一晚的試作桌。屋頂的紋樣是照想像補上的。'
        assert first['conditions'] == ['紋樣沒有任何依據', '印刷廠半小時後截稿']
    assert adopt(client, series['id'], second.json()['id'], 'adopt-2').status_code == 200

    provider.requests.clear()
    third = next_chapter(client, series['id'], 'ep-3', scene='開幕當天中午。')
    assert third.status_code == 201, third.text
    step = client.post(f"/api/generation/runs/{third.json()['id']}/step")
    assert step.status_code == 200, step.text
    episodes = sent(provider, 'roleplay_plan')[0]['story_so_far']['episodes']
    assert [item.get('scene') for item in episodes] == ['開幕前一晚的試作桌。屋頂的紋樣是照想像補上的。', '隔天早上，展場開門前。']
    assert 'conditions' not in episodes[1], '沒有填條件就不放這個欄位'

    plan = {'title': '一', 'premise': '', 'beats': [{'goal': '開場'}]}
    assert episode_outline(1, plan) == {'no': 1, 'title': '一', 'premise': '', 'beats': ['開場']}, '沒有給場景時和原本一樣（舊資料相容）'
    long = episode_outline(1, plan, {'description': '長' * 3000, 'conditions': []})
    assert len(long['scene']) == 1000, '場景描述最多帶 1000 字，避免章節多了以後每次呼叫都很長'
