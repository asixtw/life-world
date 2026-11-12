"""作品匯出成可離線開啟的 HTML（第 1 級：純文字）。

流程：已完成的生成作品 → 伺服器用固定的播放器把劇情組成單一 HTML 檔 → 存進物件儲存 → 留下匯出紀錄 → 下載。
匯出不呼叫模型；同樣的作品內容與播放器版本，產出的檔案逐位元相同。

驗證重點：
1. HTML 可以離線開啟：不引用任何外部資源；內嵌的樣式與程式由 CSP 以雜湊鎖定。
2. 作品文字一律跳脫，嵌入的劇情資料不會提早結束 script 區塊。
3. 檔案裡只有作品本身：不含人物設定、我的設定、演出要求與場景條件。
4. 相同內容不重複存檔、不重複記錄；同一提交代碼重送回原結果。
5. 只有本人、已完成的生成作品可以匯出與下載；檔案遺失或被改動時拒絕下載。
6. 匯出不改動作品、段落與作品列表。
7. 閱讀器 reader-3（劇情資料 lw-story.v3）：人物眾多時分得出個人（每人一個顏色，跨章不變）、團體（陣營分組與標籤）
   與關鍵情節（幕名、起承轉合、轉折特別標示、下集預告）；舊作品沒有這些欄位照樣能匯出；只給單一人物的筆記不會出現在檔案裡。
8. 互動版 play-2（劇情資料 lw-play.v2，請求多帶 player='play'）：另外一個檔案、另外一筆匯出紀錄；多帶每一段之後的人物狀態（真心話）
   與每位人物的底牌。內容照樣完整寫在頁面裡，底牌預設收合；閱讀版不因此多出任何東西（同一件作品前後兩次閱讀版逐位元相同）。
9. 互動層（作品內容的 interactive，另外生成、可能不存在）：互動版多帶關鍵抉擇（題目、三個選項、另外兩個結局）、線索（原文裡的短詞被包起來）、
   各陣營的番外與給讀者的一句提問。沒有互動層、抉擇是空的、線索的詞對不到原文、文字裡有惡意字元，檔案都照樣組得出來；閱讀版完全不受影響。

這是本機 SQLite 的開發檢查（假模型＋記憶體儲存，不連網、不計費）；PostgreSQL 與真正的 Cloud Storage 在 tests/test_work_export_cloudsql_e2e.py。
"""
import base64
from datetime import datetime, timezone
import hashlib
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.ai_providers import FakeProvider
from app.config import DemoPolicy
from app.main import create_app
from app.object_storage import MemoryStorage
from app.story_continuity import identity
from app.work_export import play_data, render_html, render_play_html, story_data
from test_person_source_generation import SELF, code, fields, person, pick, ready, run_to_end, with_me

TITLE = '<script>alert(1)</script>留一條接縫'
SCENE = '週六午後的試作桌。</script><img src=x onerror=alert(2)>'
STORY_OPEN = '<script type="application/json" id="lw-story">'


def make_client(tmp_path, storage=None):
    app = create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                     clock=lambda: datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc), generation_provider=FakeProvider(), work_storage=storage)
    return TestClient(app)


@pytest.fixture
def env(tmp_path):
    storage = MemoryStorage()
    with make_client(tmp_path, storage) as client:
        yield client, storage


def start(client, participants, include_me=False, request_id='run-1', title=TITLE, form='script', direction=None):
    setup = {'participants': participants, 'include_me': include_me, 'title': title,
             'scene_context': {'description': SCENE, 'conditions': ['〔COND〕只出場兩人']},
             'output': {'type': 'text', 'text': {'length': 'short', 'form': form}}}
    if direction:
        setup['direction'] = direction
    response = client.post('/api/generation/runs', json={'request_id': request_id, 'setup': setup})
    assert response.status_code == 201, response.text
    return response.json()['id']


def finished(client, **options):
    """建立一位有人物設定的人物，生成到完成；回傳（人物, 作品識別碼, 作品詳情）。"""
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original', description='〔P1公開〕願意讓手藝留下接縫。')
    work_id = start(client, [pick(wen, position='supporting')], **options)
    detail = run_to_end(client, work_id)
    assert detail['run']['status'] == 'completed'
    return wen, work_id, detail


def export(client, work_id, request_id='ex-1', player=None):
    """請伺服器匯出一次。player 不給＝請求裡沒有這個欄位（舊的前端就是這樣送），等於閱讀版；'play'＝互動版。"""
    body = {'request_id': request_id, 'format': 'html'}
    if player is not None:
        body['player'] = player
    return client.post(f'/api/works/{work_id}/exports', json=body)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def csp_hash(text):
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"


def story_block(html):
    begin = html.index(STORY_OPEN) + len(STORY_OPEN)
    return html[begin:html.index('</script>', begin)]


def test_a_completed_work_becomes_one_offline_html_file_that_downloads_unchanged(env):
    client, storage = env
    ready(client)
    wen, work_id, detail = finished(client)
    assert client.get('/api/capabilities').json()['work_export_available'] is True
    assert client.get(f'/api/works/{work_id}/exports').json() == {'available': True, 'items': []}

    created = export(client, work_id)
    assert created.status_code == 201, created.text
    item = created.json()['export']
    name = f"works/{wen['owner_id']}/{work_id}/{item['sha256']}.html"
    assert list(storage.objects) == [name] and storage.content_types[name] == 'text/html; charset=utf-8'
    data = storage.objects[name]
    assert item['version_no'] == 1 and item['format'] == 'html' and item['player'] == 'reader-3'
    assert item['size'] == len(data) and item['sha256'] == sha(data)
    assert item['source_version'] == detail['history'][-1]['version_no']
    assert item['download_path'] == f'/api/works/{work_id}/exports/1/download'
    assert item['filename'].endswith('.html') and not set('<>:"/\\|?*') & set(item['filename']), '檔名不含作業系統不接受的字元'

    html = data.decode('utf-8')
    assert html.startswith('<!doctype html>') and '<html lang="zh-Hant">' in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;留一條接縫' in html and '<script>alert(1)' not in html, '標題跳脫後才放進頁面'
    assert '<img src=x' not in html, '場景文字不會變成標籤'
    assert not re.search(r'(src|href|action)\s*=\s*["\']?(https?:)?//', html), '不引用任何外部資源'
    for segment in detail['segments']:
        assert segment['speaker_name'] in html and escape(segment['line']) in html
    assert '第 1 幕' in html and '這是 AI 依人物設定生成的虛構演出' in html

    csp = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', html).group(1)
    style = re.search(r'<style>(.*?)</style>', html, re.S).group(1)
    script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
    assert "default-src 'none'" in csp and csp_hash(style) in csp and csp_hash(script) in csp, '內嵌的樣式與程式以雜湊鎖定'
    assert "'unsafe-inline'" not in csp and 'http' not in csp

    block = story_block(html)
    assert '<' not in block, '嵌入的劇情資料不會提早結束 script 區塊'
    story = json.loads(block)
    assert story['format'] == 'lw-story.v3' and story['title'] == TITLE and len(story['chapters']) == 1, '單一作品就是只有一章'
    chapter = story['chapters'][0]
    assert chapter['form'] == 'script' and chapter['title'] == TITLE and chapter['no'] == 1
    assert [seg['line'] for beat in chapter['beats'] for seg in beat['segments']] == [seg['line'] for seg in detail['segments']]
    assert '目錄' not in html, '只有一章時沒有目錄'
    assert [member['name'] for member in story['cast']] == ['溫若岑']

    listed = client.get(f'/api/works/{work_id}/exports').json()
    assert listed == {'available': True, 'items': [item]}
    downloaded = client.get(item['download_path'])
    assert downloaded.status_code == 200 and downloaded.content == data, '下載的檔案和存放的逐位元相同'
    headers = downloaded.headers
    assert headers['content-type'].startswith('text/html')
    assert headers['content-disposition'].startswith('attachment;') and "filename*=UTF-8''" in headers['content-disposition']
    assert 'sandbox' in headers['content-security-policy'] and headers['x-content-type-options'] == 'nosniff'
    assert 'no-store' in headers['cache-control']


def test_the_same_content_is_stored_and_recorded_once(env):
    client, storage = env
    ready(client)
    _, work_id, _ = finished(client)
    first = export(client, work_id, 'ex-1').json()
    again = export(client, work_id, 'ex-2')
    assert again.status_code == 201 and again.json() == first, '內容沒有變：回同一筆匯出，不新增版本'
    assert export(client, work_id, 'ex-1').json() == first, '同一提交代碼重送回原結果'
    assert len(storage.objects) == 1 and storage.writes == 1, '相同內容只寫入一次'
    assert len(client.get(f'/api/works/{work_id}/exports').json()['items']) == 1


def test_only_my_completed_generated_works_can_be_exported(env):
    client, storage = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original')
    waiting = start(client, [pick(wen)])
    assert code(export(client, waiting)) == (409, 'work_not_completed'), '還沒完成的作品不能匯出'
    card = client.post('/api/characters', json={'request_id': 'card-1', 'content': {'name': '舊卡', 'kind': 'fictional'}}).json()
    assert code(export(client, card['id'], 'ex-card')) == (404, 'not_found'), '角色卡不是可匯出的作品'
    assert code(export(client, 'no-such-work', 'ex-none')) == (404, 'not_found')
    assert client.post(f'/api/works/{waiting}/exports', json={'request_id': 'ex-pdf', 'format': 'pdf'}).status_code == 422

    done = run_to_end(client, waiting)
    assert done['run']['status'] == 'completed'
    item = export(client, waiting, 'ex-ok').json()['export']
    other = TestClient(client.app)
    ready(other, 'export_other')
    assert code(other.get(f'/api/works/{waiting}/exports')) == (404, 'not_found')
    assert code(export(other, waiting, 'ex-theirs')) == (404, 'not_found')
    assert code(other.get(item['download_path'])) == (404, 'not_found'), '別人的作品一律 404'
    assert code(client.get(f'/api/works/{waiting}/exports/9/download')) == (404, 'not_found')
    assert len(storage.objects) == 1


def test_the_file_holds_the_story_only_without_persona_or_production_notes(env):
    client, storage = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original', description='〔P1公開〕願意讓手藝留下接縫。')
    with_me(client)
    work_id = start(client, [pick(wen, position='supporting')], include_me=True, form='narrative',
                    direction={'adherence': 'faithful', 'notes': '〔NOTE〕共八段', 'avoid': '〔AVOID〕不要讀心'})
    assert run_to_end(client, work_id)['run']['status'] == 'completed'
    assert export(client, work_id).status_code == 201
    html = next(iter(storage.objects.values())).decode('utf-8')
    for mark in ('〔P1:', '〔P1公開〕', '〔SELF:', SELF['public_profile'], '〔NOTE〕', '〔AVOID〕', '〔COND〕'):
        assert mark not in html, mark
    assert '溫若岑' in html and '小光' in html and '配角' in html
    assert 'data-form="narrative"' in html
    story = json.loads(story_block(html))
    assert story['chapters'][0]['form'] == 'narrative'
    assert [(member['name'], member['role']) for member in story['cast']] == [('溫若岑', '配角'), ('小光', None)]
    assert set(story) == {'format', 'title', 'cast', 'chapters'}, '嵌入的資料只有劇情需要的欄位'
    assert set(story['chapters'][0]) == {'no', 'title', 'genre', 'premise', 'scene', 'form', 'beats', 'teaser'}  # v3 多了類型與下集預告
    assert all(set(member) == {'name', 'role', 'color', 'side'} for member in story['cast'])  # v3 多了色號與陣營


def test_download_refuses_a_missing_or_altered_file(env):
    client, storage = env
    ready(client)
    _, work_id, _ = finished(client)
    item = export(client, work_id).json()['export']
    name = next(iter(storage.objects))
    storage.objects[name] = b'<html>changed</html>'
    assert code(client.get(item['download_path'])) == (409, 'export_file_mismatch'), '內容和匯出紀錄的雜湊不符就不送出'
    del storage.objects[name]
    assert code(client.get(item['download_path'])) == (404, 'export_file_missing')
    restored = export(client, work_id, 'ex-again')  # 重新匯出：檔案不在就補寫，紀錄仍是同一筆
    assert restored.status_code == 201 and restored.json()['export'] == item
    assert client.get(item['download_path']).status_code == 200


def test_export_is_switched_off_without_storage(tmp_path):
    with make_client(tmp_path) as client:
        ready(client)
        _, work_id, _ = finished(client)
        assert client.get('/api/capabilities').json()['work_export_available'] is False
        assert client.get(f'/api/works/{work_id}/exports').json() == {'available': False, 'items': []}
        assert code(export(client, work_id)) == (503, 'export_storage_unavailable')


def test_exporting_does_not_change_the_work_or_the_work_lists(env):
    client, _ = env
    ready(client)
    _, work_id, _ = finished(client)

    def snapshot():
        with client.app.state.service.db.connect() as db:
            turns = db.execute('SELECT count(*) FROM session_turns WHERE work_id=?', (work_id,)).fetchone()[0]
            generations = db.execute('SELECT count(*) FROM ai_generations').fetchone()[0]
        return (client.get(f'/api/generation/runs/{work_id}').json(), client.get('/api/works/center?tab=all').json(),
                client.get('/api/works?kind=generated_work').json()['total'], turns, generations)

    before = snapshot()
    assert export(client, work_id).status_code == 201
    assert client.get(client.get(f'/api/works/{work_id}/exports').json()['items'][0]['download_path']).status_code == 200
    assert snapshot() == before, '匯出不呼叫模型，也不改動作品、段落與作品列表'


# ---- 閱讀器 reader-3：分得出個人、陣營與關鍵情節 ----
# 規劃的新欄位（類型、陣營、幕名與起承轉合、下集預告、只給單一人物的筆記）由生成引擎寫進作品內容，那一段不在這個檔案的範圍。
# 這裡直接拿「已保存內容」的形狀檢查匯出怎麼使用它們：不經過模型；最後兩個案例再走一次實際的匯出流程。

SECRET = '〔PRIVATE〕他早就把股份質押出去了'


def member(cast_id, name, position=None):
    """陣容裡的一位人物（已保存內容的形狀）。person_id 在整部作品裡不變；陣容代號（c1、c2…）每一章重新編。"""
    return {'id': cast_id, 'source': 'person', 'person_id': 'pid-' + name, 'version': 1, 'name': name, 'position': position}


def turn(turn_no, beat_no, speaker, line='', action='', stage=''):
    """一段已保存的內容：匯出只讀這些欄位。"""
    return {'turn_no': turn_no, 'speaker_ref': speaker, 'input': {'beat_no': beat_no},
            'output': {'line': line, 'action': action, 'stage_direction': stage}}


def saved(cast, plan_data, form='script'):
    """一件生成作品已保存的內容（generated_work.v1）裡，匯出會讀到的部分。"""
    return {'meta': {'module_id': 'T2', 'output_type': 'text', 'participants': cast, 'target_segments': 4},
            'setup': {'include_me': False, 'scene_context': {'description': '深夜，頂樓會館的慶功宴。'}, 'style_profile': {'style_ids': []},
                      'output': {'type': 'text', 'text': {'length': 'short', 'form': form}},
                      'interaction_ruleset': 'freeform_rp', 'grounding_mode': 'fictional'},
            'plan': plan_data, 'run': {'status': 'completed', 'finished_at': None}}


def plan(**changes):
    """新形狀的規劃：類型、陣營、只給單一人物的筆記、每一幕的幕名與起承轉合、下集預告。"""
    base = {'title': '現代商戰版鴻門宴', 'genre': '商戰', 'premise': '慶功宴開到一半，一份讓渡書被推到他面前。',
            'sides': [{'name': '沈氏集團', 'members': ['c2', 'c3']}, {'name': '羅映川', 'members': ['c1']}],
            'private_notes': [{'id': 'c1', 'note': SECRET}],
            'beats': [{'beat_no': 1, 'title': '慶功宴上的讓渡書', 'kind': 'setup', 'goal': '〔GOAL1〕沈知衡當眾逼他簽字',
                       'present': ['c1', 'c2', 'c3'], 'speaker_order': ['c2', 'c1']},
                      {'beat_no': 2, 'title': '酒杯落地', 'kind': 'turn', 'goal': '〔GOAL2〕蘇映舟臨陣倒戈',
                       'present': ['c1', 'c2', 'c3'], 'speaker_order': ['c3', 'c1']}],
            'teaser': '那份讓渡書，是誰換成了白紙？'}
    return {**base, **changes}


CAST = [member('c1', '羅映川', 'protagonist'), member('c2', '沈知衡', 'opponent'), member('c3', '蘇映舟', 'supporting')]
TURNS = [turn(1, 1, 'c2', '簽了它，今晚大家都好看。', '把讓渡書推過桌面。', '水晶燈下'), turn(2, 1, 'c1', '我的筆沒有墨水。'),
         turn(3, 2, 'c3', '', '酒杯從她手裡滑落。'), turn(4, 2, 'c1', '看來今晚不只我一個人不想簽。')]
OLD_PLAN = {'title': '留一條接縫', 'premise': '兩人初次見面。',  # 舊作品的規劃：只有標題、前提與每個節拍的目標
            'beats': [{'beat_no': 1, 'goal': '〔GOAL1〕試讀標籤', 'present': ['c1', 'c2', 'c3'], 'speaker_order': ['c2', 'c1']},
                      {'beat_no': 2, 'goal': '〔GOAL2〕先試文字', 'present': ['c1', 'c2', 'c3'], 'speaker_order': ['c3', 'c1']}]}


def one_chapter(plan_data, form='script', turns=None):
    """只有一章的作品 → 劇情資料。"""
    return story_data(plan_data['title'], CAST, [(1, plan_data['title'], saved(CAST, plan_data, form), TURNS if turns is None else turns)])


def page(html):
    """讀者看得到的頁面內容：不含內嵌的樣式、劇情資料與程式（樣式表裡本來就有這些 class 名稱）。"""
    return html[html.index('<body>'):html.index(STORY_OPEN)]


def text_only(fragment):
    return re.sub(r'<[^>]+>', '', fragment)


def cast_listing(body):
    """開頭「人物」那一格的內容（HTML）。"""
    return re.search(r'<dt>人物</dt><dd>(.*?)</dd>', body, re.S).group(1)


def cast_groups(body):
    """開頭人物清單的每一組（去掉標籤後的文字）；沒有分組時是空清單。"""
    return [text_only(group) for group in re.findall(r'<div class="lw-group">(.*?)</div>', cast_listing(body), re.S)]


def test_reader_3_gives_each_person_one_colour_by_cast_order_and_keeps_it_in_every_chapter():
    # 第 2 章的陣容代號重新編過（c1 變成蘇映舟）：顏色要跟著人，不是跟著代號
    again = [member('c1', '蘇映舟', 'supporting'), member('c2', '羅映川', 'protagonist'), member('c3', '沈知衡', 'opponent')]
    second = plan(title='白紙', sides=[], beats=[{'beat_no': 1, 'title': '白紙', 'kind': 'payoff', 'goal': '〔GOAL3〕攤牌',
                                                'present': ['c1', 'c2', 'c3'], 'speaker_order': ['c1', 'c2', 'c3']}])
    second_turns = [turn(1, 1, 'c1', '是我換的。'), turn(2, 1, 'c2', '我知道。'), turn(3, 1, 'c3', '你們兩個——')]
    # 多章節作品保存的陣容只有固定代號、名稱與定位（見 open_series）
    kept = [{'key': identity(item), 'name': item['name'], 'source': item['source'], 'position': item['position'], 'is_user': False} for item in CAST]
    story = story_data('合集', kept, [(1, '讓渡書', saved(CAST, plan()), TURNS), (2, '白紙', saved(again, second), second_turns)])
    colours = {'羅映川': 1, '沈知衡': 2, '蘇映舟': 3}
    assert [(item['name'], item['color']) for item in story['cast']] == list(colours.items()), '依陣容順序給色號'
    spoken = [(seg['speaker'], seg['color']) for chapter in story['chapters'] for beat in chapter['beats'] for seg in beat['segments']]
    assert len(spoken) == 7 and all(colour == colours[name] for name, colour in spoken), '每一章、每一段都是同一個顏色'
    body = page(render_html(story).decode('utf-8'))
    shown = re.findall(r'<article class="lw-seg" data-c="(\d)">.*?class="lw-who">([^<]+)<', body, re.S)
    assert len(shown) == 7 and all(int(colour) == colours[name] for colour, name in shown), '段落上的 data-c 就是說話者的色號'
    assert [body.count(f'<span class="lw-name" data-c="{number}">') for number in (1, 2, 3)] == [1, 1, 1], '開頭的人物清單用同一組顏色'

    crowd = [member(f'c{number}', f'人物{number}') for number in range(1, 9)]
    assert [item['color'] for item in story_data('八人', crowd, [])['cast']] == [1, 2, 3, 4, 5, 6, 1, 2], '超過六位就循環'


def test_reader_3_groups_the_cast_by_side_and_tags_each_speaker():
    story = one_chapter(plan())
    assert [(item['name'], item['side']) for item in story['cast']] == [('羅映川', '羅映川'), ('沈知衡', '沈氏集團'), ('蘇映舟', '沈氏集團')]
    body = page(render_html(story).decode('utf-8'))
    assert cast_groups(body) == ['羅映川（主角）', '沈氏集團：沈知衡（對手）、蘇映舟（配角）'], '自己一個人一方時只寫名字'
    assert ('<article class="lw-seg" data-c="2"><h3 class="lw-who">沈知衡<span class="lw-side">沈氏集團</span></h3><p class="lw-stage">（水晶燈下）</p>'
            '<p class="lw-action">把讓渡書推過桌面。</p><p class="lw-line">簽了它，今晚大家都好看。</p></article>') in body
    assert body.count('<span class="lw-side">沈氏集團</span>') == 2, '沈知衡與蘇映舟各有一段'
    assert body.count('class="lw-side"') == 2, '陣營名稱就是自己的名字時不重複標示'

    partly = page(render_html(one_chapter(plan(sides=[{'name': '沈氏集團', 'members': ['c2', 'cX']}]))).decode('utf-8'))
    assert cast_groups(partly) == ['沈氏集團：沈知衡（對手）', '羅映川（主角）、蘇映舟（配角）'], '沒有被分到陣營的人物排在後面；不認得的代號略過'
    assert partly.count('class="lw-side"') == 1

    for nothing in ([], None):
        plain = page(render_html(one_chapter(plan(sides=nothing))).decode('utf-8'))
        assert 'lw-side' not in plain and 'lw-group' not in plain
        assert text_only(cast_listing(plain)) == '羅映川（主角）、沈知衡（對手）、蘇映舟（配角）', '沒有陣營時維持原本的寫法'

    # 多章節：開頭的人物清單用每位人物第一次被分到的陣營（不先透露後面的變化）；各段的標籤照那一章自己的規劃
    later = plan(sides=[{'name': '倒戈者', 'members': ['c3']}])
    series = story_data('合集', CAST, [(1, '一', saved(CAST, plan()), TURNS), (2, '二', saved(CAST, later), TURNS)])
    assert series['cast'][2]['side'] == '沈氏集團'
    assert {seg['side'] for beat in series['chapters'][1]['beats'] for seg in beat['segments'] if seg['speaker'] == '蘇映舟'} == {'倒戈者'}


def test_reader_3_marks_people_and_sides_in_narrative_form_too():
    body = page(render_html(one_chapter(plan(), 'narrative')).decode('utf-8'))
    assert 'data-form="narrative"' in body
    assert ('<article class="lw-seg" data-c="2"><p class="lw-stage">水晶燈下</p><p class="lw-action">把讓渡書推過桌面。</p>'
            '<p class="lw-line"><span class="lw-who">沈知衡<span class="lw-side">沈氏集團</span></span>「簽了它，今晚大家都好看。」</p></article>') in body
    assert ('<article class="lw-seg" data-c="3"><p class="lw-who">蘇映舟<span class="lw-side">沈氏集團</span></p>'
            '<p class="lw-action">酒杯從她手裡滑落。</p></article>') in body, '只有動作沒有台詞：仍然標出是誰'


def test_reader_3_shows_the_beat_title_with_its_kind_and_makes_the_turn_stand_out():
    story = one_chapter(plan())
    html = render_html(story).decode('utf-8')
    body = page(html)
    assert '<span class="lw-beat-no">第 1 幕</span><span class="lw-kind">起</span><span class="lw-beat-name">慶功宴上的讓渡書</span>' in body
    assert '<span class="lw-beat-no">第 2 幕</span><span class="lw-kind">轉</span><span class="lw-beat-name">酒杯落地</span>' in body
    assert body.count('<section class="lw-beat">') == 1 and body.count('<section class="lw-beat lw-beat-turn">') == 1, '只有轉折那一幕有強調用的 class'
    turning = re.search(r'<section class="lw-beat lw-beat-turn">.*?</section>', body, re.S).group(0)
    assert '酒杯落地' in turning and '慶功宴上的讓渡書' not in turning and turning.count('<span class="lw-turn-mark">轉折</span>') == 1
    assert body.count('lw-turn-mark') == 1
    assert 'lw-goal' not in body and '〔GOAL' not in html, '有幕名時不輸出規劃用的目標（可能劇透），內嵌的資料裡也沒有'
    assert [(beat['no'], beat['title'], beat['kind'], beat['goal']) for beat in story['chapters'][0]['beats']] == [
        (1, '慶功宴上的讓渡書', 'setup', ''), (2, '酒杯落地', 'turn', '')]
    assert '<span class="lw-genre">商戰</span>' in body, '類型標籤'
    assert '<p class="lw-premise"><span class="lw-label">開場</span>慶功宴開到一半，一份讓渡書被推到他面前。</p>' in body, '開場白前面標「開場」'
    assert story['chapters'][0]['genre'] == '商戰'


@pytest.mark.parametrize('kind,label', [('setup', '起'), ('rise', '承'), ('turn', '轉'), ('payoff', '合'), (None, None), ('twist', None)])
def test_reader_3_labels_each_kind_of_beat(kind, label):
    beats = [{'beat_no': 1, 'title': '只有一幕', 'kind': kind, 'goal': '〔GOAL〕', 'present': ['c1'], 'speaker_order': ['c1']}]
    story = one_chapter(plan(beats=beats), turns=[turn(1, 1, 'c1', '開始吧。')])
    body = page(render_html(story).decode('utf-8'))
    assert '<span class="lw-beat-name">只有一幕</span>' in body and '〔GOAL〕' not in body
    if label:
        assert f'<span class="lw-kind">{label}</span>' in body
    else:
        assert 'lw-kind' not in body, '沒有填或不認得的類別不加標籤'
    assert ('lw-beat-turn' in body) == (kind == 'turn')
    assert story['chapters'][0]['beats'][0]['kind'] == (kind if label else None)


def test_reader_3_still_exports_old_works_that_have_none_of_the_new_fields():
    story = one_chapter(OLD_PLAN)
    html = render_html(story).decode('utf-8')
    body = page(html)
    for mark in ('lw-side', 'lw-group', 'lw-kind', 'lw-beat-no', 'lw-beat-name', 'lw-beat-turn', 'lw-turn-mark', 'lw-genre', 'lw-teaser', '敬請期待'):
        assert mark not in body, mark
    assert body.count('<h2 class="lw-beat-title">第 1 幕</h2><p class="lw-goal">〔GOAL1〕試讀標籤</p>') == 1, '沒有幕名時照舊顯示第幾幕與目標'
    assert body.count('<h2 class="lw-beat-title">第 2 幕</h2><p class="lw-goal">〔GOAL2〕先試文字</p>') == 1
    assert body.count('<article class="lw-seg" data-c=') == 4 and '簽了它，今晚大家都好看。' in body
    assert '<span class="lw-label">開場</span>兩人初次見面。' in body
    assert [(item['color'], item['side']) for item in story['cast']] == [(1, None), (2, None), (3, None)], '顏色跟著陣容，舊作品也有'
    chapter = story['chapters'][0]
    assert (chapter['genre'], chapter['teaser']) == ('', '')
    assert [(beat['title'], beat['kind'], beat['goal']) for beat in chapter['beats']] == [('', None, '〔GOAL1〕試讀標籤'), ('', None, '〔GOAL2〕先試文字')]
    assert all(seg['side'] is None for beat in chapter['beats'] for seg in beat['segments'])
    # 欄位存在但是空的（空字串、空陣列、None）和沒有欄位是同一件事
    blank = {**OLD_PLAN, 'genre': '', 'sides': [], 'private_notes': [], 'teaser': None,
             'beats': [{**beat, 'title': '', 'kind': None} for beat in OLD_PLAN['beats']]}
    assert render_html(one_chapter(blank)) == render_html(story)


def test_reader_3_ends_with_a_teaser_and_a_collection_only_shows_the_last_one():
    body = page(render_html(one_chapter(plan())).decode('utf-8'))
    assert body.count('<aside class="lw-teaser">') == 1 and '敬請期待下集' in body and '那份讓渡書，是誰換成了白紙？' in body
    assert body.index('lw-teaser') > body.index('看來今晚不只我一個人不想簽。'), '放在這一章的最後'
    assert 'lw-teaser' not in page(render_html(one_chapter(plan(teaser=''))).decode('utf-8'))

    chapters = [(1, '一', saved(CAST, plan(teaser='〔TEASER1〕第一章的預告')), TURNS), (2, '二', saved(CAST, plan(teaser='〔TEASER2〕第二章的預告')), TURNS)]
    story = story_data('合集', CAST, chapters)
    body = page(render_html(story).decode('utf-8'))
    assert body.count('<aside class="lw-teaser">') == 1 and '〔TEASER2〕' in body and '〔TEASER1〕' not in body, '前面幾章的下一集已經在檔案裡'
    assert body.index('id="ch-2"') < body.index('lw-teaser')
    assert [chapter['teaser'] for chapter in story['chapters']] == ['〔TEASER1〕第一章的預告', '〔TEASER2〕第二章的預告']
    chapters[1] = (2, '二', saved(CAST, plan(teaser='')), TURNS)  # 最後一章沒有預告：不拿前面章節的來補
    assert 'lw-teaser' not in page(render_html(story_data('合集', CAST, chapters)).decode('utf-8'))


def test_reader_3_never_puts_private_notes_or_planning_fields_in_the_file():
    story = one_chapter(plan())
    html = render_html(story).decode('utf-8')
    for mark in (SECRET, '〔PRIVATE〕', 'private_notes', 'speaker_order', '"present"', '"members"'):
        assert mark not in html, mark
    chapter = story['chapters'][0]
    assert set(chapter) == {'no', 'title', 'genre', 'premise', 'scene', 'form', 'beats', 'teaser'}
    assert all(set(beat) == {'no', 'title', 'kind', 'goal', 'segments'} for beat in chapter['beats'])
    assert all(set(seg) == {'no', 'speaker', 'color', 'side', 'line', 'action', 'stage'} for beat in chapter['beats'] for seg in beat['segments'])
    assert all(set(item) == {'name', 'role', 'color', 'side'} for item in story['cast'])
    assert json.loads(story_block(html)) == story, '內嵌的就是這份劇情資料'


def test_reader_3_escapes_the_new_text_and_stays_reproducible():
    nasty = plan(genre='商戰<b>&', teaser='</script><img src=x onerror=alert(3)>', sides=[{'name': '<i>沈氏</i>', 'members': ['c2']}],
                 beats=[{'beat_no': 1, 'title': '</script><script>alert(4)</script>', 'kind': 'turn', 'goal': 'x', 'present': ['c1', 'c2'], 'speaker_order': ['c2', 'c1']}])
    turns = [turn(1, 1, 'c2', '簽。'), turn(2, 1, 'c1', '不簽。')]
    data = render_html(one_chapter(nasty, turns=turns))
    html = data.decode('utf-8')
    body = page(html)
    for raw in ('<b>', '<i>', '<img', '<script', '</script'):
        assert raw not in body, raw
    assert '商戰&lt;b&gt;&amp;' in body and '&lt;i&gt;沈氏&lt;/i&gt;' in body and '&lt;/script&gt;&lt;img src=x' in body
    assert '&lt;/script&gt;&lt;script&gt;alert(4)' in body
    block = story_block(html)
    assert '<' not in block and '>' not in block and '&' not in block, '內嵌的資料裡 < > & 都改寫成跳脫碼'
    assert json.loads(block)['chapters'][0]['teaser'] == '</script><img src=x onerror=alert(3)>'
    assert render_html(one_chapter(nasty, turns=turns)) == data, '同樣的輸入，逐位元相同'
    for form in ('script', 'narrative'):
        assert render_html(one_chapter(plan(), form)) == render_html(one_chapter(plan(), form))


def luminance(colour):
    """WCAG 的相對亮度；colour 是 #rrggbb。"""
    channels = [int(colour[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    red, green, blue = [value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first, second):
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_reader_3_person_colours_are_readable_in_light_and_dark():
    css = (Path(__file__).resolve().parents[1] / 'app/export_player/reader-3.css').read_text(encoding='utf-8')

    def variables(pattern):
        return dict(re.findall(r'(--[\w-]+):(#[0-9a-f]{6})\b', re.search(pattern, css).group(1)))

    light = variables(r':root\{([^}]*)\}')
    dark = variables(r'html\[data-theme=dark\]\{([^}]*)\}')
    system = variables(r'@media \(prefers-color-scheme:dark\)\{html:not\(\[data-theme=light\]\)\{([^}]*)\}')
    assert system == dark, '跟著系統的深色與手動切換的深色是同一組'
    for theme in (light, dark):
        colours = [theme[f'--c{number}'] for number in range(1, 7)]
        assert len(set(colours)) == 6, '六個顏色各不相同'
        for colour in colours + [theme['--turn']]:
            assert contrast(colour, theme['--bg']) >= 4.5, f'{colour} 在底色上不夠清楚（WCAG AA 4.5:1）'
    assert all(f'[data-c="{number}"]{{--c:var(--c{number})}}' in css for number in range(1, 7)), '色號對應到顏色變數'


def rewrite_plan(client, work_id, change):
    """把規劃的新欄位放進已保存的作品內容（生成引擎之後會寫進去的形狀），用來檢查實際的匯出流程。"""
    with client.app.state.service.db.connect(write=True) as db:
        row = db.execute('SELECT v.version_no,v.content_json FROM works w JOIN work_versions v ON v.work_id=w.id AND v.version_no=w.current_version '
                         'WHERE w.id=?', (work_id,)).fetchone()
        content = json.loads(row['content_json'])
        change(content['plan'])
        db.execute('UPDATE work_versions SET content_json=? WHERE work_id=? AND version_no=?',
                   (json.dumps(content, ensure_ascii=False), work_id, row['version_no']))


def enrich(plan_data, teaser):
    """假模型的規劃只有標題、前提與兩個節拍的目標；補上新欄位。陣容代號：c1＝溫若岑，self＝小光。"""
    plan_data.update(genre='職人劇', teaser=teaser, private_notes=[{'id': 'c1', 'note': SECRET}],
                     sides=[{'name': '展覽工作室', 'members': ['c1']}, {'name': '訪客', 'members': ['self']}])
    for beat, (title, kind) in zip(plan_data['beats'], [('試讀標籤', 'setup'), ('接縫露出來', 'turn')]):
        beat.update(title=title, kind=kind)


def test_the_export_of_a_saved_work_uses_the_new_plan_fields_and_leaves_private_notes_out(env):
    client, storage = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original')
    with_me(client)
    work_id = start(client, [pick(wen, position='supporting')], include_me=True)
    detail = run_to_end(client, work_id)
    assert detail['run']['status'] == 'completed'
    rewrite_plan(client, work_id, lambda plan_data: enrich(plan_data, '明天開門之前，標籤會換成哪一個版本？'))
    item = export(client, work_id).json()['export']
    assert item['player'] == 'reader-3'
    html = next(iter(storage.objects.values())).decode('utf-8')
    assert SECRET not in html and 'private_notes' not in html, '只給單一人物的筆記不在檔案的任何地方'
    assert '開場：人物登場並說明立場。' not in html, '有幕名時不輸出節拍的目標'
    story = json.loads(story_block(html))
    assert story['format'] == 'lw-story.v3'
    assert [(item['name'], item['color'], item['side']) for item in story['cast']] == [('溫若岑', 1, '展覽工作室'), ('小光', 2, '訪客')]
    body = page(html)
    hers = sum(segment['speaker_name'] == '溫若岑' for segment in detail['segments'])
    assert 0 < hers < len(detail['segments'])
    assert body.count('<article class="lw-seg" data-c="1">') == hers and body.count('<article class="lw-seg" data-c="2">') == len(detail['segments']) - hers
    assert body.count('<span class="lw-side">展覽工作室</span>') == hers and body.count('<span class="lw-side">訪客</span>') == len(detail['segments']) - hers
    assert cast_groups(body) == ['展覽工作室：溫若岑（配角）', '訪客：小光']
    assert '<span class="lw-kind">轉</span><span class="lw-beat-name">接縫露出來</span>' in body and body.count('<section class="lw-beat lw-beat-turn">') == 1
    assert '<span class="lw-genre">職人劇</span>' in body
    assert body.count('<aside class="lw-teaser">') == 1 and '明天開門之前，標籤會換成哪一個版本？' in body


def test_a_collection_keeps_each_persons_colour_and_only_shows_the_last_teaser(env):
    client, storage = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original')
    with_me(client)
    first_id = start(client, [pick(wen, position='supporting')], include_me=True, title='留一條接縫')
    assert run_to_end(client, first_id)['run']['status'] == 'completed'
    opened = client.post('/api/series', json={'request_id': 'series-1', 'work_id': first_id})
    assert opened.status_code in (200, 201), opened.text
    sid = opened.json()['id']
    second = client.post(f'/api/series/{sid}/episodes', json={'request_id': 'ep-2', 'title': '開門之前', 'scene': {'description': '隔天早上，展場開門前。'}})
    assert second.status_code == 201, second.text
    second_id = second.json()['id']
    assert run_to_end(client, second_id)['run']['status'] == 'completed'
    assert client.post(f'/api/series/{sid}/episodes/{second_id}/adopt', json={'request_id': 'ad-2'}).status_code == 200
    rewrite_plan(client, first_id, lambda plan_data: enrich(plan_data, '〔TEASER1〕第一章的預告'))
    rewrite_plan(client, second_id, lambda plan_data: enrich(plan_data, '〔TEASER2〕第二章的預告'))

    created = client.post(f'/api/works/{sid}/exports', json={'request_id': 'ex-series', 'format': 'html'})
    assert created.status_code == 201, created.text
    html = storage.objects[next(name for name in storage.objects if f'/{sid}/' in name)].decode('utf-8')
    story = json.loads(story_block(html))
    assert story['format'] == 'lw-story.v3' and len(story['chapters']) == 2
    assert [(item['name'], item['color']) for item in story['cast']] == [('溫若岑', 1), ('小光', 2)]
    for chapter in story['chapters']:
        assert {(seg['speaker'], seg['color']) for beat in chapter['beats'] for seg in beat['segments']} == {('溫若岑', 1), ('小光', 2)}, '每一章都是同一個顏色'
    body = page(html)
    assert body.count('<aside class="lw-teaser">') == 1 and '〔TEASER2〕' in body and '〔TEASER1〕' not in body, '只有最後一章顯示預告'
    assert body.count('<span class="lw-genre">職人劇</span>') == 2, '合集裡類型標在各章的章名旁'
    assert SECRET not in html and 'private_notes' not in html


# ---- 互動版 play-2（劇情資料 lw-play.v2）：選視角入局、一次看一段、有限次偷看真心話、找線索、關鍵抉擇與三個結局 ----
# 匯出只用已經保存的資料，不呼叫模型：每一段之後那位人物的狀態（段落的 output.state）、只有個別人物知道的事（規劃的 private_notes），
# 以及另外生成、存在作品內容裡的互動層（content['interactive']：抉擇、線索、番外、提問；可能不存在）。
# 內容一樣完整寫在頁面裡（不能執行程式的預覽工具看得到每一段）；逐段揭開、視角與偷看、線索、抉擇由內嵌程式處理，
# 那一部分在 browser_tests/test_export_play_offline.py 用 Chrome 實際操作。這裡檢查資料、頁面的標記與匯出流程。

NOTE_FOR_SU = '〔PRIVATE-SU〕她其實是對方派來的'
STATES = {1: {'emotion': '志在必得', 'stance': '逼他簽字', 'goal': '今晚拿到簽名'}, 2: {'emotion': '強作鎮定', 'stance': '', 'goal': '拖到律師趕來'},
          3: {'emotion': '', 'stance': '', 'goal': ''}}  # 第 3 段三個欄位都是空的；第 4 段是舊資料，沒有 state
SEGMENT_KEYS = {'no', 'speaker', 'color', 'side', 'line', 'action', 'stage'}  # 閱讀版（lw-story.v3）每一段的欄位
FOLDED = r'<details class="lw-secrets">(.*?)</details>'  # 底牌收在預設不展開的區塊裡


def with_states(turns=TURNS, states=STATES):
    """段落加上那一段之後的人物狀態（已保存段落的形狀：output.state）；states 沒有列到的段落維持沒有這個欄位。"""
    return [{**item, 'output': {**item['output'], **({'state': states[item['turn_no']]} if item['turn_no'] in states else {})}} for item in turns]


def play_chapter(plan_data, form='script', turns=None):
    """只有一章的作品 → 互動版的劇情資料。"""
    return play_data(plan_data['title'], CAST, [(1, plan_data['title'], saved(CAST, plan_data, form), with_states() if turns is None else turns)])


def without_play_fields(story):
    """拿掉互動版多出來的欄位（段落的 state 與 who、人物的 secret、各章的 secrets 與 interactive），格式名稱換回閱讀版的。"""
    return {**story, 'format': 'lw-story.v3', 'cast': [{key: value for key, value in item.items() if key != 'secret'} for item in story['cast']],
            'chapters': [{**{key: value for key, value in chapter.items() if key not in ('secrets', 'interactive')},
                          'beats': [{**beat, 'segments': [{key: value for key, value in seg.items() if key not in ('state', 'who')} for seg in beat['segments']]}
                                    for beat in chapter['beats']]} for chapter in story['chapters']]}


def test_play_data_is_the_story_plus_each_segments_state_and_each_persons_secret():
    notes = [{'id': 'c1', 'note': SECRET}, {'id': 'c3', 'note': NOTE_FOR_SU}, {'id': 'cX', 'note': '〔PRIVATE〕不認得的代號'}, {'id': 'c2', 'note': '  '}]
    plan_data = plan(private_notes=notes)
    chapters = [(1, plan_data['title'], saved(CAST, plan_data), with_states())]
    story = play_data(plan_data['title'], CAST, chapters)
    assert story['format'] == 'lw-play.v2'
    segments = [seg for beat in story['chapters'][0]['beats'] for seg in beat['segments']]
    assert all(set(seg) == SEGMENT_KEYS | {'state', 'who'} for seg in segments)
    assert [seg['state'] for seg in segments] == [STATES[1], STATES[2], None, None], '三個欄位都空的、或舊資料沒有這個欄位：都是 None'
    assert [seg['who'] for seg in segments] == [2, 1, 3, 1], '說話者是陣容裡的第幾位（從 1 起）：人物篩選用，不靠名稱比對'
    assert all(set(item) == {'name', 'role', 'color', 'side', 'secret'} for item in story['cast'])
    assert [(item['name'], item['secret']) for item in story['cast']] == [('羅映川', SECRET), ('沈知衡', None), ('蘇映舟', NOTE_FOR_SU)], '空白的、不認得代號的筆記不算'
    assert story['chapters'][0]['secrets'] == [{'who': 1, 'name': '羅映川', 'color': 1, 'secret': SECRET},
                                               {'who': 3, 'name': '蘇映舟', 'color': 3, 'secret': NOTE_FOR_SU}], '依陣容順序，只列有底牌的人'
    assert set(story['chapters'][0]) == {'no', 'title', 'genre', 'premise', 'scene', 'form', 'beats', 'teaser', 'secrets', 'interactive'}
    assert story['chapters'][0]['interactive'] is None, '這件作品沒有互動層'
    assert without_play_fields(story) == story_data(plan_data['title'], CAST, chapters), '超集：拿掉多出來的欄位就是閱讀版的劇情資料'

    old = play_data(OLD_PLAN['title'], CAST, [(1, OLD_PLAN['title'], saved(CAST, OLD_PLAN), TURNS)])  # 舊作品：沒有底牌，段落也沒有狀態
    assert old['format'] == 'lw-play.v2' and old['chapters'][0]['secrets'] == [] and all(item['secret'] is None for item in old['cast'])
    assert old['chapters'][0]['interactive'] is None
    assert all(seg['state'] is None for beat in old['chapters'][0]['beats'] for seg in beat['segments'])


def test_play_page_has_every_segment_in_the_html_with_its_state_and_keeps_the_secrets_folded():
    story = play_chapter(plan(private_notes=[{'id': 'c1', 'note': SECRET}, {'id': 'c3', 'note': NOTE_FOR_SU}]))
    data = render_play_html(story, '2026-11-12')
    html = data.decode('utf-8')
    body = page(html)
    assert html.startswith('<!doctype html>') and '<meta name="generator" content="Life World play-2">' in html and '互動版' in body
    assert '由 Life World 匯出・互動版 play-2' in body and 'play-1' not in html
    # 漸進增強：四段都直接寫在頁面裡，不靠程式繪製；每一段帶著說話者是第幾位人物，開頭的人物清單帶同一個號碼（篩選用）
    for line in ('簽了它，今晚大家都好看。', '我的筆沒有墨水。', '酒杯從她手裡滑落。', '看來今晚不只我一個人不想簽。'):
        assert line in body
    assert re.findall(r'<article class="lw-seg" data-c="(\d)" data-p="(\d)">', body) == [('2', '2'), ('1', '1'), ('3', '3'), ('1', '1')]
    assert [body.count(f'<span class="lw-name" data-c="{number}" data-p="{number}">') for number in (1, 2, 3)] == [1, 1, 1]
    # 真心話：每一段的最後是那位人物在這一段之後的狀態；空的欄位不列，三個都空的段落沒有這一塊
    shown = re.findall(r'<article class="lw-seg"[^>]*>.*?</article>', body, re.S)
    assert len(shown) == 4 and [segment.count('<div class="lw-xray">') for segment in shown] == [1, 1, 0, 0]
    assert shown[0].endswith('<div class="lw-xray"><span class="lw-xray-label">真心話</span>'
                             '<span class="lw-xray-item"><span class="lw-xray-key">情緒</span>志在必得</span>'
                             '<span class="lw-xray-item"><span class="lw-xray-key">立場</span>逼他簽字</span>'
                             '<span class="lw-xray-item"><span class="lw-xray-key">目標</span>今晚拿到簽名</span></div></article>')
    assert '強作鎮定' in shown[1] and '拖到律師趕來' in shown[1] and '立場' not in shown[1]
    # 底牌：寫在檔案裡，但收在預設不展開的區塊；頁面其他地方沒有
    assert body.count('<details') == 1 and body.count('<details class="lw-secrets">') == 1, '沒有 open 屬性：打開檔案時是收合的'
    folded = re.search(FOLDED, body, re.S).group(1)
    assert folded.startswith('<summary>看底牌</summary>')
    # play-2：每一則底牌多帶是第幾位人物（data-p），清單帶第幾章（data-ch）——靠線索看穿某個人的底牌時，內嵌程式據此找到那一則
    assert ('<ul class="lw-secret-list" data-ch="1"><li class="lw-secret" data-c="1" data-p="1"><span class="lw-name">羅映川</span>'
            f'<span class="lw-secret-text">{SECRET}</span></li>') in folded, '人物名稱用他的顏色'
    assert f'<li class="lw-secret" data-c="3" data-p="3"><span class="lw-name">蘇映舟</span><span class="lw-secret-text">{NOTE_FOR_SU}</span></li>' in folded
    assert body.count('〔PRIVATE') == 2 and 'lw-secrets-chapter' not in body, '只有一章時不標第幾章'
    # 結尾卡：下集預告、看底牌、選邊、從頭再看，排在最後一段之後；預告不在章節裡
    end = body[body.index('<section class="lw-end"'):]
    assert body.count('<section class="lw-end"') == 1 and body.index('<section class="lw-end"') > body.index('看來今晚不只我一個人不想簽。')
    assert body.count('<aside class="lw-teaser">') == 1 and end.count('<aside class="lw-teaser">') == 1 and '那份讓渡書，是誰換成了白紙？' in end
    assert end.index('lw-teaser') < end.index('lw-secrets') < end.index('lw-pick') < end.index('lw-again')
    assert '你站哪一邊？' in end and re.findall(r'<button type="button" data-side="\d+">([^<]+)</button>', end) == ['羅映川', '沈氏集團']
    assert '<button type="button" data-play="restart">從頭再看</button>' in end
    # 要靠程式才有作用的部分先藏著（沒有程式的預覽工具不會看到按了沒反應的按鈕）
    for fragment in ('<div class="lw-tools" hidden>', '<nav class="lw-nav" aria-label="逐段閱讀" hidden>', '<div class="lw-pick" hidden>',
                     '<div class="lw-again" hidden>', '<p class="lw-hint" hidden>', '<section class="lw-entry" data-peeks="3" hidden>'):
        assert body.count(fragment) == 1, fragment
    for label in ('>上一段<', '>下一段<', '>全部顯示<'):
        assert label in body, label
    # play-2：真心話不再有總開關（自己視角的直接看、別人的限次偷看），工具列只多「全部顯示」
    assert re.findall(r'data-tool="(\w+)"', body) == ['smaller', 'larger', 'theme', 'stage', 'mode'], '原有的工具都保留，多了全部顯示；沒有真心話的總開關'
    # 入局：每位人物一顆按鈕（用他的顏色），另有「旁觀」；選了才開始，所以有人物狀態的作品沒有「開始」按鈕
    entry = re.search(r'<section class="lw-entry" data-peeks="3" hidden>(.*?)</section>', body, re.S).group(1)
    assert '你要以誰的視角入局？' in entry
    assert re.findall(r'<button type="button" data-view="(\d)"(?: data-c="(\d)")?>([^<]+)</button>', entry) == [
        ('1', '1', '羅映川'), ('2', '2', '沈知衡'), ('3', '3', '蘇映舟'), ('0', '', '旁觀')]
    assert 'data-play="start"' not in body and '>開始<' not in body
    # 沒有互動層：沒有抉擇、線索、番外、提問，也沒有「真結局」與結局計數
    for mark in ('lw-choice', 'lw-clue', 'lw-ending', 'lw-epilogue', 'lw-ask', 'lw-end-kind', 'lw-end-seen', '真結局', '關鍵抉擇'):
        assert mark not in body, mark
    # 人物顏色、陣營、幕名與起承轉合和閱讀版一樣
    assert cast_groups(body) == ['羅映川（主角）', '沈氏集團：沈知衡（對手）、蘇映舟（配角）']
    assert '<span class="lw-beat-no">第 2 幕</span><span class="lw-kind">轉</span><span class="lw-beat-name">酒杯落地</span>' in body
    assert body.count('<section class="lw-beat lw-beat-turn">') == 1 and body.count('<span class="lw-side">沈氏集團</span>') == 2
    assert '<span class="lw-genre">商戰</span>' in body and '<span class="lw-label">開場</span>慶功宴開到一半' in body and '〔GOAL' not in html
    # 單一檔案、離線、CSP 以雜湊鎖定內嵌的樣式與程式；沒有行內樣式或事件屬性
    csp = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', html).group(1)
    style = re.search(r'<style>(.*?)</style>', html, re.S).group(1)
    script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
    assert "default-src 'none'" in csp and csp_hash(style) in csp and csp_hash(script) in csp
    assert "'unsafe-inline'" not in csp and 'http' not in csp
    assert not re.search(r'(src|href|action)\s*=\s*["\']?(https?:)?//', html), '不引用任何外部資源'
    assert ' style="' not in body and not re.search(r'\son\w+=', body)
    block = story_block(html)
    assert '<' not in block and '>' not in block and '&' not in block
    assert json.loads(block) == story, '內嵌的就是這份劇情資料'
    assert render_play_html(story, '2026-11-12') == data, '同樣的輸入，逐位元相同'


def test_play_page_marks_people_and_states_in_narrative_form_too():
    body = page(render_play_html(play_chapter(plan(), 'narrative')).decode('utf-8'))
    assert 'data-form="narrative"' in body
    assert ('<article class="lw-seg" data-c="2" data-p="2"><p class="lw-stage">水晶燈下</p><p class="lw-action">把讓渡書推過桌面。</p>'
            '<p class="lw-line"><span class="lw-who">沈知衡<span class="lw-side">沈氏集團</span></span>「簽了它，今晚大家都好看。」</p>'
            '<div class="lw-xray">') in body
    assert ('<article class="lw-seg" data-c="3" data-p="3"><p class="lw-who">蘇映舟<span class="lw-side">沈氏集團</span></p>'
            '<p class="lw-action">酒杯從她手裡滑落。</p></article>') in body, '沒有狀態的段落和閱讀版一樣，只多了人物號碼'


def test_play_page_of_a_work_without_states_secrets_or_two_sides_has_none_of_those_parts():
    old = play_data(OLD_PLAN['title'], CAST, [(1, OLD_PLAN['title'], saved(CAST, OLD_PLAN), TURNS)])
    body = page(render_play_html(old).decode('utf-8'))
    for mark in ('lw-xray', 'data-tool="xray"', '真心話', 'lw-secrets', '看底牌', 'lw-pick', '你站哪一邊', 'data-side', 'lw-teaser', '<details',
                 'lw-entry', '視角', '偷看', 'lw-choice', 'lw-clue', '線索'):
        assert mark not in body, mark
    # 沒有任何人物狀態：選視角沒有意義，不問；照舊用「開始」按鈕
    assert body.count('<button type="button" class="lw-go" data-play="start">開始</button>') == 1
    assert body.count('<article class="lw-seg" data-c=') == 4 and '從頭再看' in body and 'data-tool="mode"' in body
    assert body.count('<h2 class="lw-beat-title">第 1 幕</h2><p class="lw-goal">〔GOAL1〕試讀標籤</p>') == 1, '舊作品照舊顯示第幾幕與目標'
    one_side = page(render_play_html(play_chapter(plan(sides=[{'name': '沈氏集團', 'members': ['c2', 'c3']}], private_notes=[]))).decode('utf-8'))
    assert 'lw-pick' not in one_side and 'lw-secrets' not in one_side and 'lw-xray' in one_side, '只有一個陣營就不問站哪一邊'


def test_play_page_gives_two_peeks_to_a_cast_of_two_and_three_to_a_larger_one():
    """可以偷看別人真心話幾次寫在選視角的區塊上（data-peeks），內嵌的程式照這個數字算：兩位人物 2 次，三位以上 3 次。"""
    pair = CAST[:2]
    plan_data = plan(sides=[], private_notes=[], beats=[{'beat_no': 1, 'title': '對坐', 'kind': 'setup', 'goal': 'x', 'present': ['c1', 'c2'], 'speaker_order': ['c2', 'c1']}])
    turns = with_states([turn(1, 1, 'c2', '簽。'), turn(2, 1, 'c1', '不簽。')], {1: STATES[1]})
    two = page(render_play_html(play_data('兩人', pair, [(1, '兩人', saved(pair, plan_data), turns)])).decode('utf-8'))
    assert two.count('<section class="lw-entry" data-peeks="2" hidden>') == 1 and '只能偷看 2 次' in two and '偷看 3 次' not in two
    assert re.findall(r'data-view="(\d)"', two) == ['1', '2', '0'], '兩位人物與旁觀'
    three = page(render_play_html(play_chapter(plan())).decode('utf-8'))
    assert three.count('<section class="lw-entry" data-peeks="3" hidden>') == 1 and '只能偷看 3 次' in three and '偷看 2 次' not in three


def test_play_page_escapes_states_and_secrets_and_stays_reproducible():
    nasty = plan(private_notes=[{'id': 'c1', 'note': '</details><script>alert(5)</script>'}],
                 sides=[{'name': '<i>沈氏</i>', 'members': ['c2']}, {'name': 'A&B', 'members': ['c1']}])
    turns = with_states(states={1: {'emotion': '<b>怒</b>', 'stance': '</script><img src=x onerror=alert(6)>', 'goal': 'a & b'}})
    data = render_play_html(play_chapter(nasty, turns=turns))
    html = data.decode('utf-8')
    body = page(html)
    for raw in ('<b>', '<i>', '<img', '<script', '</script'):
        assert raw not in body, raw
    assert body.count('</details>') == 1, '底牌的文字不能提早結束收合的區塊'
    assert '&lt;b&gt;怒&lt;/b&gt;' in body and '&lt;/script&gt;&lt;img src=x' in body and 'a &amp; b' in body
    assert '&lt;/details&gt;&lt;script&gt;alert(5)' in body and '>&lt;i&gt;沈氏&lt;/i&gt;</button>' in body and '>A&amp;B</button>' in body
    block = story_block(html)
    assert '<' not in block and '>' not in block and '&' not in block, '內嵌的資料裡 < > & 都改寫成跳脫碼'
    embedded = json.loads(block)
    assert embedded['cast'][0]['secret'] == '</details><script>alert(5)</script>'
    assert embedded['chapters'][0]['beats'][0]['segments'][0]['state']['stance'] == '</script><img src=x onerror=alert(6)>'
    assert render_play_html(play_chapter(nasty, turns=turns)) == data, '同樣的輸入，逐位元相同'
    for form in ('script', 'narrative'):
        assert render_play_html(play_chapter(plan(), form)) == render_play_html(play_chapter(plan(), form))


def test_a_play_collection_lists_the_secrets_chapter_by_chapter_and_ends_once():
    # 第 2 章的陣容代號重新編過（c1 變成蘇映舟、c2 變成羅映川）：底牌與人物號碼都要跟著人
    again = [member('c1', '蘇映舟', 'supporting'), member('c2', '羅映川', 'protagonist'), member('c3', '沈知衡', 'opponent')]
    second = plan(title='白紙', teaser='〔TEASER2〕第二章的預告', sides=[{'name': '倒戈者', 'members': ['c1']}],
                  private_notes=[{'id': 'c2', 'note': '〔PRIVATE2〕他手上有錄音'}],
                  beats=[{'beat_no': 1, 'title': '白紙', 'kind': 'payoff', 'goal': '〔GOAL3〕攤牌', 'present': ['c1', 'c2', 'c3'], 'speaker_order': ['c1', 'c2']}])
    second_turns = with_states([turn(1, 1, 'c1', '是我換的。'), turn(2, 1, 'c2', '我知道。')], {1: {'emotion': '如釋重負', 'stance': '', 'goal': ''}})
    kept = [{'key': identity(item), 'name': item['name'], 'source': item['source'], 'position': item['position'], 'is_user': False} for item in CAST]
    story = play_data('合集', kept, [(1, '讓渡書', saved(CAST, plan(teaser='〔TEASER1〕第一章的預告')), with_states()), (2, '白紙', saved(again, second), second_turns)])
    assert [chapter['secrets'] for chapter in story['chapters']] == [[{'who': 1, 'name': '羅映川', 'color': 1, 'secret': SECRET}],
                                                                    [{'who': 1, 'name': '羅映川', 'color': 1, 'secret': '〔PRIVATE2〕他手上有錄音'}]]
    assert all(item['secret'] is None for item in story['cast']), '多章節：每一章各有各的底牌，放在各章的 secrets；開頭的人物不帶'
    assert [(seg['speaker'], seg['who']) for seg in story['chapters'][1]['beats'][0]['segments']] == [('蘇映舟', 3), ('羅映川', 1)]
    body = page(render_play_html(story).decode('utf-8'))
    assert '<nav class="lw-toc"' in body and body.count('<section class="lw-chapter"') == 2
    assert body.count('<section class="lw-end"') == 1 and body.index('<section class="lw-end"') > body.index('我知道。'), '結尾卡只在整份檔案最後'
    folded = re.search(FOLDED, body, re.S).group(1)
    assert re.findall(r'<h3 class="lw-secrets-chapter">([^<]+)</h3>', folded) == ['第 1 章　讓渡書', '第 2 章　白紙'], '底牌依章分開列，標明第幾章'
    assert folded.index('第 1 章') < folded.index(SECRET) < folded.index('第 2 章') < folded.index('〔PRIVATE2〕')
    assert body.count('〔PRIVATE') == 2, '底牌只在收合的區塊裡'
    assert body.count('<aside class="lw-teaser">') == 1 and '〔TEASER2〕' in body and '〔TEASER1〕' not in body, '只有最後一章的預告，放在結尾卡'
    assert re.findall(r'data-side="\d+">([^<]+)<', body) == ['羅映川', '沈氏集團', '倒戈者'], '後面章節才出現的陣營排在後面'
    assert '<article class="lw-seg" data-c="3" data-p="3"><h4 class="lw-who">蘇映舟<span class="lw-side">倒戈者</span></h4>' in body


def test_the_reader_page_does_not_change_when_segments_carry_states_and_the_plan_has_secrets():
    """閱讀版不讀段落的狀態與底牌：同一件作品，資料裡有沒有這兩樣，閱讀版的檔案逐位元相同，而且找不到互動版的任何東西。"""
    plan_data = plan(private_notes=[{'id': 'c1', 'note': SECRET}, {'id': 'c3', 'note': NOTE_FOR_SU}])
    chapters = [(1, plan_data['title'], saved(CAST, plan_data), with_states())]
    reader = render_html(story_data(plan_data['title'], CAST, chapters), '2026-11-12')
    assert reader == render_html(one_chapter(plan(private_notes=[])), '2026-11-12')
    html = reader.decode('utf-8')
    for mark in ('〔PRIVATE', 'lw-xray', 'lw-secrets', 'lw-play', 'lw-nav', 'lw-end', 'lw-pick', 'data-p=', '"state"', '"secret', '"who"',
                 '真心話', '看底牌', '互動版', '志在必得', '拖到律師趕來', 'play-1', 'play-2'):
        assert mark not in html, mark
    assert '<meta name="generator" content="Life World reader-3">' in html and json.loads(story_block(html))['format'] == 'lw-story.v3'


def test_play_2_carries_every_reader_3_style_rule_so_colours_sides_and_beats_look_the_same():
    folder = Path(__file__).resolve().parents[1] / 'app/export_player'
    play = (folder / 'play-2.css').read_text(encoding='utf-8')
    rules = [line for line in (folder / 'reader-3.css').read_text(encoding='utf-8').splitlines()[5:] if line.strip()]  # 前五行是 reader-3 的說明
    assert len(rules) > 60 and rules[0].startswith(':root{')
    assert [rule for rule in rules if rule not in play.splitlines()] == [], 'reader-3 的每一條樣式規則都原樣在 play-2 裡（人物顏色、陣營、幕名與轉折、三種字體）'
    # play-2：真心話預設隱藏；只有那一段被打開（自己視角的、或花一次偷看的）才顯示。沒有整頁的總開關
    assert '.lw-xray{display:none' in play and '.lw-seg.lw-open .lw-xray{' in play and 'data-xray' not in play
    assert '</style' not in play and '</script' not in (folder / 'play-2.js').read_text(encoding='utf-8')
    assert not (folder / 'play-1.css').exists() and not (folder / 'play-1.js').exists(), 'play-1 已經由 play-2 取代'


# ---- 互動層（content['interactive']）：關鍵抉擇、線索、番外、提問 ----
# 互動層是另外生成、存在作品內容裡的一塊資料（另一個模組負責，可能不存在）。這裡直接拿它保存下來的形狀，檢查匯出怎麼使用：
# 抉擇放在指定節拍的最後一段之後；線索的短詞在原文裡被包起來；另外兩個結局、番外收在預設不展開的區塊。

ENDING_B, ENDING_C = '〔ENDING-B〕他簽了名，慶功宴照常散場。', '〔ENDING-C〕他掀了桌子，律師還在路上。'
HINT_1, HINT_2, HINT_3 = '〔HINT1〕這份文件經過誰的手？', '〔HINT2〕他的筆真的沒有墨水嗎？', '〔HINT3〕他早就知道有人會倒戈。'
EPILOGUE_SHEN, EPILOGUE_LUO = '〔EPI-SHEN〕沈知衡連夜清查經手的人。', '〔EPI-LUO〕羅映川把筆收進抽屜。'
ASK = '如果是你，會把筆放下嗎？'
PLAY_NOTES = [{'id': 'c1', 'note': SECRET}, {'id': 'c3', 'note': NOTE_FOR_SU}]  # 羅映川與蘇映舟各有一張底牌


def layer(**changes):
    """互動層保存下來的形狀（lw-interactive.v1）。抉擇在第 1 幕之後、由羅映川決定；三則線索（兩則指向蘇映舟、一則指向羅映川）。"""
    base = {'schema': 'lw-interactive.v1', 'generation_id': 'gen-interactive-1',
            'decision': {'after_beat': 1, 'actor': 'c1', 'question': '簽，還是不簽？', 'options': [
                {'id': 'a', 'label': '把筆放下，等她開口', 'kind': 'true', 'needs_clue': True, 'ending': ''},
                {'id': 'b', 'label': '簽了再說', 'kind': 'plain', 'needs_clue': False, 'ending': ENDING_B},
                {'id': 'c', 'label': '掀桌走人', 'kind': 'bad', 'needs_clue': False, 'ending': ENDING_C}]},
            'clues': [{'id': 'k1', 'turn_no': 1, 'field': 'action', 'phrase': '讓渡書', 'hint': HINT_1, 'secret_of': 'c3'},
                      {'id': 'k2', 'turn_no': 2, 'field': 'line', 'phrase': '墨水', 'hint': HINT_2, 'secret_of': 'c3'},
                      {'id': 'k3', 'turn_no': 4, 'field': 'line', 'phrase': '不想簽', 'hint': HINT_3, 'secret_of': 'c1'}],
            'epilogues': [{'side': '沈氏集團', 'text': EPILOGUE_SHEN}, {'side': '羅映川', 'text': EPILOGUE_LUO}],
            'question': ASK}
    return {**base, **changes}


def game(interactive, form='script', plan_data=None, turns=None):
    """只有一章、帶著互動層的作品 → 互動版的劇情資料。interactive 不給（None）就是作品內容裡沒有這個欄位。"""
    plan_data = plan_data or plan(private_notes=PLAY_NOTES)
    content = saved(CAST, plan_data, form)
    if interactive is not None:
        content['interactive'] = interactive
    return play_data(plan_data['title'], CAST, [(1, plan_data['title'], content, with_states() if turns is None else turns)])


def decision_of(story):
    return (story['chapters'][0]['interactive'] or {}).get('decision')


def clue_ids(story):
    return [clue['id'] for clue in (story['chapters'][0]['interactive'] or {}).get('clues', [])]


def test_play_data_carries_the_interactive_layer_without_its_identifiers():
    story = game(layer())
    assert story['format'] == 'lw-play.v2'
    assert story['chapters'][0]['interactive'] == {
        # after：抉擇出現在哪一段之後（那個節拍的最後一段的段號）；actor 換成整部作品的人物序號、名稱與色號
        'decision': {'after_beat': 1, 'after': 2, 'actor': {'who': 1, 'name': '羅映川', 'color': 1}, 'question': '簽，還是不簽？', 'options': [
            {'id': 'a', 'label': '把筆放下，等她開口', 'kind': 'true', 'needs_clue': True, 'ending': ''},
            {'id': 'b', 'label': '簽了再說', 'kind': 'plain', 'needs_clue': False, 'ending': ENDING_B},
            {'id': 'c', 'label': '掀桌走人', 'kind': 'bad', 'needs_clue': False, 'ending': ENDING_C}]},
        # 線索：no 是段號；who／name 是這則線索指向誰的底牌（陣容代號換成人物序號，不靠名稱比對）
        'clues': [{'id': 'k1', 'no': 1, 'field': 'action', 'phrase': '讓渡書', 'hint': HINT_1, 'who': 3, 'name': '蘇映舟'},
                  {'id': 'k2', 'no': 2, 'field': 'line', 'phrase': '墨水', 'hint': HINT_2, 'who': 3, 'name': '蘇映舟'},
                  {'id': 'k3', 'no': 4, 'field': 'line', 'phrase': '不想簽', 'hint': HINT_3, 'who': 1, 'name': '羅映川'}],
        'epilogues': [{'side': '沈氏集團', 'text': EPILOGUE_SHEN}, {'side': '羅映川', 'text': EPILOGUE_LUO}],
        'question': ASK}
    html = render_play_html(story).decode('utf-8')
    for mark in ('gen-interactive-1', 'generation_id', 'lw-interactive.v1', 'secret_of', 'turn_no'):
        assert mark not in html, mark  # 檔案裡不放識別碼與生成用的欄位名稱
    assert without_play_fields(story) == one_chapter(plan(private_notes=PLAY_NOTES)), '拿掉互動版多出來的欄位，仍然是同一件作品的閱讀版資料'


def test_play_page_puts_the_decision_after_its_beat_with_three_options_and_folds_the_other_two_endings():
    story = game(layer())
    data = render_play_html(story, '2026-11-12')
    html = data.decode('utf-8')
    body = page(html)
    # 抉擇是一個靜態區塊，排在第 1 幕（after_beat）的最後一段之後、第 2 幕之前：沒有程式也讀得到題目與三個選項
    assert body.count('<aside class="lw-choice" aria-label="關鍵抉擇">') == 1
    choice = re.search(r'<aside class="lw-choice" aria-label="關鍵抉擇">(.*?)</aside>', body, re.S).group(1)
    assert body.index('我的筆沒有') < body.index('<aside class="lw-choice"') < body.index('<section class="lw-beat lw-beat-turn">')
    assert '</article></section><aside class="lw-choice"' in body and '</aside><section class="lw-beat lw-beat-turn">' in body
    assert '<p class="lw-choice-kicker">關鍵抉擇</p>' in choice and '<p class="lw-choice-question">簽，還是不簽？</p>' in choice
    assert '<span class="lw-name" data-c="1">羅映川</span>' in choice, '標出由誰做決定，用他的顏色'
    assert ('<ol class="lw-choice-list"><li data-option="a" data-kind="true" data-needs-clue="1">把筆放下，等她開口</li>'
            '<li data-option="b" data-kind="plain">簽了再說</li><li data-option="c" data-kind="bad">掀桌走人</li></ol>') in choice, '三個選項照資料的順序'
    # 另外兩個結局收在預設不展開的區塊（沒有 open）；真結局就是原本生成的後續節拍，不另外寫
    folded = re.search(r'<details class="lw-endings"><summary>看另外兩個結局</summary>(.*?)</details>', choice, re.S).group(1)
    assert folded == ('<div class="lw-ending" data-option="b" data-kind="plain"><p class="lw-ending-kind">另一種結局</p>'
                      f'<p class="lw-ending-pick">簽了再說</p><p class="lw-ending-text">{ENDING_B}</p></div>'
                      '<div class="lw-ending" data-option="c" data-kind="bad"><p class="lw-ending-kind">壞結局</p>'
                      f'<p class="lw-ending-pick">掀桌走人</p><p class="lw-ending-text">{ENDING_C}</p></div>')
    assert body.count('〔ENDING-') == 2 and body.count('<details') == 3, '收合的區塊：另外兩個結局、底牌、番外'
    assert '<details open' not in body and ' open>' not in body
    # 原本的故事一段都沒有少：選了真結局才繼續的後續節拍照樣寫在頁面裡
    assert body.count('<article class="lw-seg"') == 4 and '看來今晚不只我一個人不想簽。' not in choice

    # 結尾卡：真結局的標示與結局計數先藏著（要靠程式）；番外收合；提問直接是文章的最後一句
    end = body[body.index('<section class="lw-end"'):]
    assert end.count('<p class="lw-end-kind" hidden>真結局</p>') == 1 and end.count('<div class="lw-end-seen" hidden>') == 1
    assert '<button type="button" data-play="rechoose">回到轉折點重選</button>' in end
    tales = re.search(r'<details class="lw-epilogues"><summary>看番外</summary>(.*?)</details>', end, re.S).group(1)
    # data-side 對到「你站哪一邊」的按鈕號碼（羅映川＝1、沈氏集團＝2）：選了哪一邊就顯示那一邊的番外
    assert tales == (f'<div class="lw-epilogue" data-side="2"><p class="lw-epilogue-side">沈氏集團</p><p class="lw-epilogue-text">{EPILOGUE_SHEN}</p></div>'
                     f'<div class="lw-epilogue" data-side="1"><p class="lw-epilogue-side">羅映川</p><p class="lw-epilogue-text">{EPILOGUE_LUO}</p></div>')
    assert re.findall(r'<button type="button" data-side="(\d+)">([^<]+)</button>', end) == [('1', '羅映川'), ('2', '沈氏集團')]
    assert body.count('〔EPI-') == 2 and f'<p class="lw-ask"><span class="lw-label">想一想</span>{ASK}</p>' in end
    assert (end.index('lw-end-kind') < end.index('lw-teaser') < end.index('lw-secrets') < end.index('lw-pick') < end.index('lw-epilogues')
            < end.index('lw-ask') < end.index('lw-end-seen') < end.index('lw-again'))
    # 仍然是單一檔案、離線、可重現；內嵌的就是這份劇情資料
    assert ' style="' not in body and not re.search(r'\son\w+=', body)
    assert not re.search(r'(src|href|action)\s*=\s*["\']?(https?:)?//', html)
    assert json.loads(story_block(html)) == story and render_play_html(story, '2026-11-12') == data


def test_play_page_wraps_each_clue_phrase_once_and_keeps_its_hint_hidden():
    body = page(render_play_html(game(layer())).decode('utf-8'))
    # 線索的短詞在那一段的台詞或動作裡被包起來；其餘文字不變
    assert '<p class="lw-action">把<span class="lw-clue" data-clue="k1">讓渡書</span>推過桌面。</p>' in body
    assert '<p class="lw-line">我的筆沒有<span class="lw-clue" data-clue="k2">墨水</span>。</p>' in body
    assert '<p class="lw-line">看來今晚不只我一個人<span class="lw-clue" data-clue="k3">不想簽</span>。</p>' in body
    assert body.count('class="lw-clue"') == 3
    # 提示寫在那一段裡、先藏著（點了線索詞才顯示）；data-who 是這則線索指向第幾位人物的底牌。真心話仍然是段落的最後一塊
    shown = re.findall(r'<article class="lw-seg"[^>]*>.*?</article>', body, re.S)
    assert f'<p class="lw-clue-note" data-clue="k1" data-who="3" hidden><span class="lw-label">線索</span>{HINT_1}</p><div class="lw-xray">' in shown[0]
    assert f'<p class="lw-clue-note" data-clue="k2" data-who="3" hidden><span class="lw-label">線索</span>{HINT_2}</p><div class="lw-xray">' in shown[1]
    assert shown[3].endswith(f'<p class="lw-clue-note" data-clue="k3" data-who="1" hidden><span class="lw-label">線索</span>{HINT_3}</p></article>')
    assert 'lw-clue' not in shown[2] and body.count('〔HINT') == 3 and body.count('class="lw-clue-note"') == 3
    assert '線索' in re.search(r'<p class="lw-hint" hidden>(.*?)</p>', body, re.S).group(1), '操作提示提到線索'

    narrative = page(render_play_html(game(layer(), 'narrative')).decode('utf-8'))
    assert '<p class="lw-action">把<span class="lw-clue" data-clue="k1">讓渡書</span>推過桌面。</p>' in narrative
    assert '</span>「我的筆沒有<span class="lw-clue" data-clue="k2">墨水</span>。」</p>' in narrative, '小說敘事：引號裡的台詞一樣包得到'

    # 同一個詞出現兩次只包第一次；同一段的兩則線索互相重疊時，後面那一則略過（不會包出交錯的標籤）
    twice = [turn(1, 1, 'c2', '白紙就是白紙。'), turn(2, 1, 'c1', '我的筆沒有墨水。')]
    clues = [{'id': 'k1', 'turn_no': 1, 'field': 'line', 'phrase': '白紙', 'hint': HINT_1, 'secret_of': 'c3'},
             {'id': 'k2', 'turn_no': 1, 'field': 'line', 'phrase': '紙就', 'hint': HINT_2, 'secret_of': 'c3'},
             {'id': 'k3', 'turn_no': 2, 'field': 'line', 'phrase': '筆', 'hint': HINT_3, 'secret_of': 'c1'},
             {'id': 'k4', 'turn_no': 2, 'field': 'line', 'phrase': '墨水', 'hint': HINT_3, 'secret_of': 'c1'}]
    story = game(layer(clues=clues, decision=None), turns=twice)
    assert clue_ids(story) == ['k1', 'k3', 'k4']
    body = page(render_play_html(story).decode('utf-8'))
    assert '<p class="lw-line"><span class="lw-clue" data-clue="k1">白紙</span>就是白紙。</p>' in body
    assert '<p class="lw-line">我的<span class="lw-clue" data-clue="k3">筆</span>沒有<span class="lw-clue" data-clue="k4">墨水</span>。</p>' in body


def test_play_page_without_an_interactive_layer_has_no_decision_clues_epilogues_or_question():
    """沒有互動層的作品（還沒生成，或舊作品）：互動版仍然有視角、限次偷看、底牌與選邊，只是沒有抉擇、線索、番外與提問。"""
    plain = game(None)
    assert plain['chapters'][0]['interactive'] is None
    body = page(render_play_html(plain).decode('utf-8'))
    for mark in ('lw-choice', 'lw-clue', 'lw-ending', 'lw-epilogue', 'lw-ask', 'lw-end-kind', 'lw-end-seen', 'rechoose', '關鍵抉擇', '真結局', '線索', '番外'):
        assert mark not in body, mark
    assert body.count('<details') == 1 and 'lw-entry' in body and 'lw-pick' in body and body.count('<div class="lw-xray">') == 2
    for empty in ('x', [], 0, {}, {'decision': None, 'clues': [], 'epilogues': [], 'question': ''}, {'decision': 'x', 'clues': 'x', 'epilogues': None}):
        assert render_play_html(game(empty)) == render_play_html(plain), f'空的或形狀不對的互動層等於沒有：{empty!r}'


def test_play_page_keeps_working_when_the_decision_is_missing_or_malformed():
    # decision 是 None：沒有抉擇，線索、番外與提問照樣有
    story = game(layer(decision=None))
    assert decision_of(story) is None and clue_ids(story) == ['k1', 'k2', 'k3']
    body = page(render_play_html(story).decode('utf-8'))
    assert 'lw-choice' not in body and 'lw-end-kind' not in body and 'lw-end-seen' not in body and 'lw-ending' not in body
    assert body.count('class="lw-clue"') == 3 and '<details class="lw-epilogues">' in body and ASK in body

    good = layer()['decision']
    options = good['options']
    broken = [
        {**good, 'after_beat': 9},                                             # 沒有這個節拍
        {**good, 'after_beat': '1'},                                           # 節拍號碼不是數字
        {**good, 'options': options[:2]},                                      # 不是三個選項
        {**good, 'options': options + [{**options[2], 'id': 'd'}]},
        {**good, 'options': [options[0], {**options[1], 'kind': 'true'}, options[2]]},   # 兩個真結局
        {**good, 'options': [{**options[0], 'kind': 'plain', 'ending': 'x'}, options[1], options[2]]},   # 沒有真結局
        {**good, 'options': [options[0], {**options[1], 'ending': '  '}, options[2]]},   # 另一個結局沒有旁白
        {**good, 'options': [options[0], {**options[1], 'label': ''}, options[2]]},      # 選項沒有文字
        {**good, 'options': [options[0], {**options[1], 'id': 'a'}, options[2]]},        # 選項代號重複
        {**good, 'options': [options[0], {**options[1], 'kind': 'twist'}, options[2]]},  # 不認得的種類
        {**good, 'options': [options[0], 'x', options[2]]},
        {**good, 'options': None}, [], 'x']
    for decision in broken:
        story = game(layer(decision=decision))
        assert decision_of(story) is None, decision
        assert 'lw-choice' not in page(render_play_html(story).decode('utf-8')), '抉擇不完整就整個不放：故事照原本的樣子讀到最後'

    # 做決定的人不在陣容裡：抉擇照樣有，只是不標是誰；題目是空的也一樣
    for actor in ('cX', None, 7):
        story = game(layer(decision={**good, 'actor': actor, 'question': ''}))
        assert decision_of(story)['actor'] is None and decision_of(story)['question'] == ''
        body = page(render_play_html(story).decode('utf-8'))
        assert 'lw-choice-actor' not in body and 'lw-choice-question' not in body and body.count('<ol class="lw-choice-list">') == 1

    # 抉擇在最後一個節拍之後：真結局沒有後續段落，直接接到結尾卡；抉擇排在最後一段之後
    last = game(layer(decision={**good, 'after_beat': 2}))
    assert decision_of(last)['after'] == 4
    body = page(render_play_html(last).decode('utf-8'))
    assert body.index('不想簽') < body.index('<aside class="lw-choice"') < body.index('<section class="lw-end"')


def test_play_page_skips_clues_that_cannot_be_matched_and_never_locks_the_true_ending_behind_them():
    good = layer()['clues']
    cases = [({**good[0], 'phrase': '找不到的詞'}, '原文裡沒有這個詞'), ({**good[0], 'turn_no': 99}, '沒有這一段'), ({**good[0], 'field': 'stage'}, '只認台詞與動作'),
             ({**good[0], 'secret_of': 'cX'}, '指向不在陣容裡的人'), ({**good[0], 'secret_of': 'c2'}, '指向沒有底牌的人'), ({**good[0], 'hint': ' '}, '沒有提示'),
             ({**good[0], 'phrase': ''}, '空的詞'), ({**good[0], 'id': ''}, '沒有代號'), ({**good[0], 'id': 'k2'}, '代號和別的線索重複'), ('x', '不是一則線索'), (None, '不是一則線索')]
    for clue, why in cases:
        story = game(layer(clues=[good[1], clue, good[2]]))
        assert clue_ids(story) == ['k2', 'k3'], why
        body = page(render_play_html(story).decode('utf-8'))
        assert body.count('class="lw-clue"') == 2 and body.count('class="lw-clue-note"') == 2, why
        assert '把讓渡書推過桌面。' in body, '略過的線索不動原文'

    # 已跳脫的文字裡找詞：「&」在頁面裡寫成 &amp;，線索的詞是 amp 時不能包到跳脫碼裡面
    amp = game(layer(clues=[{**good[0], 'turn_no': 2, 'field': 'line', 'phrase': 'amp'}]), turns=[turn(1, 1, 'c2', '簽。'), turn(2, 1, 'c1', 'A&B 都不簽。')])
    assert clue_ids(amp) == [] and '<p class="lw-line">A&amp;B 都不簽。</p>' in page(render_play_html(amp).decode('utf-8'))

    # 真結局標了「要先找到線索」，但抉擇之前一則可以找的線索都沒有（全部對不到，或都在抉擇之後）：不能把真結局鎖死，改成直接可以選
    for clues in ([], [{**good[0], 'phrase': '找不到的詞'}], [good[2]]):
        story = game(layer(clues=clues))
        assert [option['needs_clue'] for option in decision_of(story)['options']] == [False, False, False], clues
        assert 'data-needs-clue' not in page(render_play_html(story).decode('utf-8'))
    assert [option['needs_clue'] for option in decision_of(game(layer(clues=good[:1])))['options']] == [True, False, False]

    # 沒有底牌的作品就沒有線索，仍然有抉擇與番外
    bare = game(layer(), plan_data=plan(private_notes=[]))
    assert clue_ids(bare) == [] and decision_of(bare) is not None
    body = page(render_play_html(bare).decode('utf-8'))
    assert 'lw-clue' not in body and 'lw-secrets' not in body and '<aside class="lw-choice"' in body and '<details class="lw-epilogues">' in body

    # 番外：沒有陣營名稱或沒有內容的略過；同一個陣營只取第一則。提問只有空白等於沒有
    tales = [{'side': '沈氏集團', 'text': EPILOGUE_SHEN}, {'side': '沈氏集團', 'text': '〔EPI-重複〕'}, {'side': '', 'text': '〔EPI-沒有陣營〕'},
             {'side': '羅映川', 'text': '  '}, 'x']
    story = game(layer(epilogues=tales, question='   '))
    assert story['chapters'][0]['interactive']['epilogues'] == [{'side': '沈氏集團', 'text': EPILOGUE_SHEN}] and story['chapters'][0]['interactive']['question'] == ''
    body = page(render_play_html(story).decode('utf-8'))
    assert body.count('〔EPI-') == 1 and 'lw-ask' not in body
    # 番外寫給一個人物清單裡沒有的陣營：選邊的按鈕補上它，選得到才看得到
    extra = page(render_play_html(game(layer(epilogues=[{'side': '圍觀的賓客', 'text': '〔EPI-賓客〕'}]))).decode('utf-8'))
    assert re.findall(r'data-side="\d+">([^<]+)</button>', extra) == ['羅映川', '沈氏集團', '圍觀的賓客']
    assert '<div class="lw-epilogue" data-side="3"><p class="lw-epilogue-side">圍觀的賓客</p>' in extra


def test_play_page_escapes_everything_in_the_interactive_layer():
    script = '</script><script>alert(8)</script>'
    nasty = layer(question='</p><img src=x onerror=alert(9)>',
                  decision={'after_beat': 1, 'actor': 'c1', 'question': '</aside><b>簽？</b>', 'options': [
                      {'id': '"><i>a', 'label': '<u>放下</u> & 等', 'kind': 'true', 'needs_clue': True, 'ending': ''},
                      {'id': 'b', 'label': script, 'kind': 'plain', 'needs_clue': False, 'ending': '</details></aside>' + script},
                      {'id': 'c', 'label': '掀桌', 'kind': 'bad', 'needs_clue': False, 'ending': '<img src=x onerror=alert(10)>'}]},
                  clues=[{'id': '"><b>k', 'turn_no': 1, 'field': 'line', 'phrase': '<b>簽</b>', 'hint': '</p>' + script, 'secret_of': 'c3'},
                         {'id': 'k2', 'turn_no': 2, 'field': 'line', 'phrase': 'A&B', 'hint': 'a < b & c', 'secret_of': 'c3'}],
                  epilogues=[{'side': '<i>沈氏</i>', 'text': '</details>' + script}])
    turns = with_states([turn(1, 1, 'c2', '你<b>簽</b>了嗎？'), turn(2, 1, 'c1', '「A&B」都不簽。')], {})
    data = render_play_html(game(nasty, turns=turns))
    html = data.decode('utf-8')
    body = page(html)
    for raw in ('<b>', '<i>', '<u>', '<img', '<script', '</script', 'onerror=alert(9)>'):
        assert raw not in body, raw
    assert body.count('</aside>') == 2 and body.count('</details>') == 3, '文字不能提早結束抉擇或收合的區塊（aside：抉擇與下集預告各一個）'
    # 線索的詞本身帶著標籤字元：先在原文裡找到，再把前、中、後三段各自跳脫
    assert '<p class="lw-line">你<span class="lw-clue" data-clue="&quot;&gt;&lt;b&gt;k">&lt;b&gt;簽&lt;/b&gt;</span>了嗎？</p>' in body
    assert '<p class="lw-line">「<span class="lw-clue" data-clue="k2">A&amp;B</span>」都不簽。</p>' in body
    assert '<li data-option="&quot;&gt;&lt;i&gt;a" data-kind="true" data-needs-clue="1">&lt;u&gt;放下&lt;/u&gt; &amp; 等</li>' in body
    assert '&lt;/aside&gt;&lt;b&gt;簽？&lt;/b&gt;' in body and '&lt;/details&gt;&lt;/aside&gt;&lt;/script&gt;' in body
    assert 'a &lt; b &amp; c' in body and '&lt;i&gt;沈氏&lt;/i&gt;' in body and '&lt;/p&gt;&lt;img src=x' in body
    block = story_block(html)
    assert '<' not in block and '>' not in block and '&' not in block
    assert json.loads(block)['chapters'][0]['interactive']['decision']['options'][1]['label'] == script
    assert render_play_html(game(nasty, turns=turns)) == data, '同樣的輸入，逐位元相同'


def test_the_reader_page_is_byte_for_byte_the_same_when_the_work_has_an_interactive_layer():
    """閱讀版不讀互動層：作品內容裡有沒有 interactive，閱讀版的檔案逐位元相同，裡面找不到抉擇、線索、番外與提問。"""
    plan_data = plan(private_notes=PLAY_NOTES)
    for form in ('script', 'narrative'):
        with_layer = {**saved(CAST, plan_data, form), 'interactive': layer()}
        reader = render_html(story_data(plan_data['title'], CAST, [(1, plan_data['title'], with_layer, with_states())]), '2026-11-12')
        assert reader == render_html(one_chapter(plan(private_notes=[]), form), '2026-11-12')
        html = reader.decode('utf-8')
        for mark in ('interactive', 'lw-choice', 'lw-clue', 'lw-ending', 'lw-epilogue', 'lw-ask', 'lw-entry', '〔ENDING-', '〔HINT', '〔EPI-', ASK, '簽，還是不簽？',
                     '把筆放下，等她開口', '關鍵抉擇', '真結局', '線索', '番外', '視角', 'play-2', 'lw-play'):
            assert mark not in html, mark
    # 合集也一樣
    chapters = [(1, '一', with_layer, with_states()), (2, '二', saved(CAST, plan()), TURNS)]
    plain = [(1, '一', saved(CAST, plan_data, 'narrative'), TURNS), (2, '二', saved(CAST, plan()), TURNS)]
    assert render_html(story_data('合集', CAST, chapters)) == render_html(story_data('合集', CAST, plain))


def test_a_play_collection_uses_the_interactive_layer_of_each_chapter_that_has_one():
    """多章節合集：有互動層的那一章有自己的抉擇（排在那一章指定的節拍之後）與線索；沒有的那一章沒有。結尾卡只有一張，番外標明是哪一章的。"""
    again = [member('c1', '蘇映舟', 'supporting'), member('c2', '羅映川', 'protagonist'), member('c3', '沈知衡', 'opponent')]  # 第 2 章的陣容代號重新編過
    second = plan(title='白紙', teaser='', sides=[{'name': '倒戈者', 'members': ['c1']}], private_notes=[{'id': 'c2', 'note': '〔PRIVATE2〕他手上有錄音'}],
                  beats=[{'beat_no': 1, 'title': '白紙', 'kind': 'payoff', 'goal': '〔GOAL3〕攤牌', 'present': ['c1', 'c2', 'c3'], 'speaker_order': ['c1', 'c2']}])
    second_turns = with_states([turn(1, 1, 'c1', '是我換的。'), turn(2, 1, 'c2', '我知道。')], {1: {'emotion': '如釋重負', 'stance': '', 'goal': ''}})
    # 第 2 章自己的互動層：只有一則線索（指向這一章的 c2＝羅映川）與一則番外，沒有抉擇
    second_layer = {'decision': None, 'clues': [{'id': 'k1', 'turn_no': 2, 'field': 'line', 'phrase': '知道', 'hint': '〔HINT-2章〕', 'secret_of': 'c2'}],
                    'epilogues': [{'side': '倒戈者', 'text': '〔EPI-2章〕她把白紙留在桌上。'}], 'question': '〔ASK-2章〕'}
    kept = [{'key': identity(item), 'name': item['name'], 'source': item['source'], 'position': item['position'], 'is_user': False} for item in CAST]
    first_content = {**saved(CAST, plan(private_notes=PLAY_NOTES)), 'interactive': layer()}
    story = play_data('合集', kept, [(1, '讓渡書', first_content, with_states()), (2, '白紙', {**saved(again, second), 'interactive': second_layer}, second_turns)])
    assert story['chapters'][0]['interactive']['decision']['after'] == 2 and story['chapters'][1]['interactive']['decision'] is None
    assert story['chapters'][1]['interactive']['clues'] == [{'id': 'k1', 'no': 2, 'field': 'line', 'phrase': '知道', 'hint': '〔HINT-2章〕', 'who': 1, 'name': '羅映川'}]
    body = page(render_play_html(story).decode('utf-8'))
    first, rest = body[body.index('id="ch-1"'):body.index('id="ch-2"')], body[body.index('id="ch-2"'):body.index('<section class="lw-end"')]
    assert first.count('<aside class="lw-choice"') == 1 and 'lw-choice' not in rest, '抉擇在第 1 章裡（選了真結局才繼續到第 2 章）'
    assert first.count('class="lw-clue"') == 3 and rest.count('class="lw-clue"') == 1
    assert '<p class="lw-line">我<span class="lw-clue" data-clue="k1">知道</span>。</p>' in rest, '線索代號每一章各自編，重複沒有關係'
    assert '<p class="lw-clue-note" data-clue="k1" data-who="1" hidden>' in rest
    end = body[body.index('<section class="lw-end"'):]
    assert body.count('<section class="lw-end"') == 1 and end.count('<p class="lw-end-kind" hidden>真結局</p>') == 1
    assert re.findall(r'<ul class="lw-secret-list" data-ch="(\d)">', end) == ['1', '2'], '底牌依章分開，內嵌程式靠章號找到被看穿的那一則'
    # 番外：各章的都收在同一個區塊，標明第幾章；提問只用最後一章的
    tales = re.search(r'<details class="lw-epilogues"><summary>看番外</summary>(.*?)</details>', end, re.S).group(1)
    assert re.findall(r'<p class="lw-epilogue-chapter">([^<]+)</p><p class="lw-epilogue-side">([^<]+)</p>', tales) == [
        ('第 1 章　讓渡書', '沈氏集團'), ('第 1 章　讓渡書', '羅映川'), ('第 2 章　白紙', '倒戈者')]
    assert '〔ASK-2章〕' in end and ASK not in body


def rewrite_content(client, work_id, change):
    """直接改已保存的作品內容（互動層之後由另一個端點寫進去）：change 收到整份內容。"""
    with client.app.state.service.db.connect(write=True) as db:
        row = db.execute('SELECT v.version_no,v.content_json FROM works w JOIN work_versions v ON v.work_id=w.id AND v.version_no=w.current_version '
                         'WHERE w.id=?', (work_id,)).fetchone()
        content = json.loads(row['content_json'])
        change(content)
        db.execute('UPDATE work_versions SET content_json=? WHERE work_id=? AND version_no=?',
                   (json.dumps(content, ensure_ascii=False), work_id, row['version_no']))


def test_the_play_export_of_a_saved_work_uses_its_interactive_layer_and_the_reader_export_does_not(env):
    client, storage = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original')
    with_me(client)
    work_id = start(client, [pick(wen, position='supporting')], include_me=True, title='留一條接縫')
    detail = run_to_end(client, work_id)
    assert detail['run']['status'] == 'completed'
    rewrite_plan(client, work_id, lambda plan_data: enrich(plan_data, '明天開門之前，標籤會換成哪一個版本？'))
    reader = export(client, work_id, 'ex-r1').json()['export']
    before = export(client, work_id, 'ex-p1', player='play').json()['export']
    assert before['player'] == 'play-2' and 'lw-choice' not in page(client.get(before['download_path']).content.decode('utf-8'))

    # 互動層寫進作品內容之後（陣容代號：c1＝溫若岑，self＝小光）：線索的詞取第 1 段台詞裡的兩個字
    opening = detail['segments'][0]
    phrase = opening['line'][:2]
    saved_layer = {'schema': 'lw-interactive.v1', 'generation_id': 'gen-interactive-9',
                   'decision': {'after_beat': 1, 'actor': 'self', 'question': '要不要把接縫留下來？', 'options': [
                       {'id': 'a', 'label': '留下來', 'kind': 'true', 'needs_clue': True, 'ending': ''},
                       {'id': 'b', 'label': '磨平它', 'kind': 'plain', 'needs_clue': False, 'ending': ENDING_B},
                       {'id': 'c', 'label': '整塊重做', 'kind': 'bad', 'needs_clue': False, 'ending': ENDING_C}]},
                   'clues': [{'id': 'k1', 'turn_no': 1, 'field': 'line', 'phrase': phrase, 'hint': HINT_1, 'secret_of': 'c1'}],
                   'epilogues': [{'side': '訪客', 'text': EPILOGUE_LUO}], 'question': ASK}
    rewrite_content(client, work_id, lambda content: content.update(interactive=saved_layer))

    created = export(client, work_id, 'ex-p2', player='play')
    assert created.status_code == 201, created.text
    play = created.json()['export']
    assert play['player'] == 'play-2' and play['version_no'] == 3 and play['sha256'] != before['sha256'], '內容多了互動層：是新的一筆互動版'
    html = client.get(play['download_path']).content.decode('utf-8')
    story = json.loads(story_block(html))
    found = story['chapters'][0]['interactive']
    assert story['format'] == 'lw-play.v2' and found['decision']['actor'] == {'who': 2, 'name': '小光', 'color': 2}
    assert found['clues'] == [{'id': 'k1', 'no': 1, 'field': 'line', 'phrase': phrase, 'hint': HINT_1, 'who': 1, 'name': '溫若岑'}]
    body = page(html)
    assert body.count('<aside class="lw-choice"') == 1 and f'<span class="lw-clue" data-clue="k1">{escape(phrase)}</span>' in body
    assert ENDING_B in body and ENDING_C in body and EPILOGUE_LUO in body and ASK in body and 'gen-interactive-9' not in html
    assert body.count('<article class="lw-seg"') == len(detail['segments']), '原本的段落一段都沒有少'

    # 閱讀版：作品內容多了互動層，再匯出一次仍然是原來那一筆，檔案逐位元相同
    assert export(client, work_id, 'ex-r2').json()['export'] == reader
    reader_html = client.get(reader['download_path']).content.decode('utf-8')
    for mark in ('interactive', 'lw-choice', 'lw-clue', ENDING_B, HINT_1, EPILOGUE_LUO, ASK, '要不要把接縫留下來？'):
        assert mark not in reader_html, mark
    assert len(storage.objects) == 3, '閱讀版一份、互動版前後兩份'


def saved_states(client, work_id):
    """已保存段落的人物狀態（依段號）。"""
    with client.app.state.service.db.connect() as db:
        rows = db.execute('SELECT output_json FROM session_turns WHERE work_id=? ORDER BY turn_no', (work_id,)).fetchall()
    return [{key: json.loads(row['output_json'])['state'][key] for key in ('emotion', 'stance', 'goal')} for row in rows]


def test_the_play_export_is_a_second_file_and_the_reader_export_stays_byte_for_byte_the_same(env):
    client, storage = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original')
    with_me(client)
    work_id = start(client, [pick(wen, position='supporting')], include_me=True, title='留一條接縫')
    detail = run_to_end(client, work_id)
    assert detail['run']['status'] == 'completed'
    rewrite_plan(client, work_id, lambda plan_data: enrich(plan_data, '明天開門之前，標籤會換成哪一個版本？'))
    states = saved_states(client, work_id)
    assert len(states) == len(detail['segments']) and all(state['goal'].endswith('推進節拍') for state in states)

    first = export(client, work_id, 'ex-r1')  # 不帶 player：閱讀版
    assert first.status_code == 201, first.text
    reader = first.json()['export']
    assert (reader['player'], reader['filename'], reader['version_no']) == ('reader-3', '留一條接縫.html', 1)
    reader_bytes = client.get(reader['download_path']).content
    assert sha(reader_bytes) == reader['sha256']

    created = export(client, work_id, 'ex-p1', player='play')
    assert created.status_code == 201, created.text
    play = created.json()['export']
    assert (play['player'], play['filename'], play['format']) == ('play-2', '留一條接縫（互動版）.html', 'html')
    assert play['version_no'] == 2 and play['sha256'] != reader['sha256'] and play['download_path'] == f'/api/works/{work_id}/exports/2/download'
    assert play['source_version'] == reader['source_version']
    name = f"works/{wen['owner_id']}/{work_id}/{play['sha256']}.html"
    assert len(storage.objects) == 2 and storage.content_types[name] == 'text/html; charset=utf-8'

    # 閱讀版不受影響：再匯出一次（不帶 player，或明說 reader）都回原來那一筆，檔案逐位元相同；互動版也一樣不重複
    assert export(client, work_id, 'ex-r2').json()['export'] == reader
    assert export(client, work_id, 'ex-r3', player='reader').json()['export'] == reader
    assert client.get(reader['download_path']).content == reader_bytes
    assert export(client, work_id, 'ex-p2', player='play').json()['export'] == play, '互動版內容沒有變：回同一筆，不新增版本'
    assert export(client, work_id, 'ex-p1', player='play').json()['export'] == play, '同一提交代碼重送回原結果'
    assert code(export(client, work_id, 'ex-p1')) == (409, 'idempotency_conflict'), '同一提交代碼不能換成另一種播放器'
    assert len(storage.objects) == 2 and storage.writes == 2, '兩種各存一份'
    assert client.get(f'/api/works/{work_id}/exports').json() == {'available': True, 'items': [play, reader]}

    reader_html = reader_bytes.decode('utf-8')
    for mark in (SECRET, 'private_notes', 'lw-xray', 'lw-secrets', 'lw-play', '真心話', '看底牌', '互動版', '推進節拍', '"state"', '"secret'):
        assert mark not in reader_html, mark
    assert json.loads(story_block(reader_html))['format'] == 'lw-story.v3'

    downloaded = client.get(play['download_path'])
    assert downloaded.status_code == 200 and downloaded.content == storage.objects[name]
    assert quote('留一條接縫（互動版）.html', safe='') in downloaded.headers['content-disposition']
    assert 'sandbox' in downloaded.headers['content-security-policy']
    play_html = downloaded.content.decode('utf-8')
    story = json.loads(story_block(play_html))
    assert story['format'] == 'lw-play.v2' and without_play_fields(story) == json.loads(story_block(reader_html)), '互動版是閱讀版的超集'
    assert story['chapters'][0]['interactive'] is None and 'lw-choice' not in page(play_html), '還沒有生成互動層：互動版沒有抉擇'
    assert [seg['state'] for beat in story['chapters'][0]['beats'] for seg in beat['segments']] == states, '每一段之後那位人物的狀態'
    assert [(item['name'], item['secret']) for item in story['cast']] == [('溫若岑', SECRET), ('小光', None)]
    body = page(play_html)
    assert body.count('<div class="lw-xray">') == len(states) and '推進節拍' in body
    assert body.count(SECRET) == 1 and SECRET in re.search(FOLDED, body, re.S).group(1), '底牌只在預設收合的區塊裡'
    assert re.findall(r'data-side="\d+">([^<]+)<', body) == ['展覽工作室', '訪客']
    assert body.count('<article class="lw-seg"') == len(detail['segments']) and body.count('<aside class="lw-teaser">') == 1
    for mark in ('〔P1:', '〔SELF:', SELF['public_profile'], '〔COND〕', 'private_notes', 'speaker_order'):
        assert mark not in play_html, mark


def test_the_play_export_follows_the_same_access_rules(env):
    client, storage = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original')
    waiting = start(client, [pick(wen)])
    assert code(export(client, waiting, 'ex-early', player='play')) == (409, 'work_not_completed'), '還沒完成的作品不能匯出'
    for unknown in ('movie', 'play-1', 'play-2', 'reader-3', '', None, 1):
        refused = client.post(f'/api/works/{waiting}/exports', json={'request_id': 'ex-unknown', 'format': 'html', 'player': unknown})
        assert refused.status_code == 422, unknown
    assert code(export(client, 'no-such-work', 'ex-none', player='play')) == (404, 'not_found')
    assert run_to_end(client, waiting)['run']['status'] == 'completed'
    item = export(client, waiting, 'ex-ok', player='play').json()['export']
    assert item['player'] == 'play-2' and item['version_no'] == 1 and item['filename'].endswith('（互動版）.html')
    assert not set('<>:"/\\|?*') & set(item['filename']), '檔名不含作業系統不接受的字元'
    other = TestClient(client.app)
    ready(other, 'export_other')
    assert code(export(other, waiting, 'ex-theirs', player='play')) == (404, 'not_found')
    assert code(other.get(item['download_path'])) == (404, 'not_found'), '別人的互動版一樣拿不到'
    assert code(other.get(f'/api/works/{waiting}/exports')) == (404, 'not_found')
    assert len(storage.objects) == 1


def test_a_series_play_export_has_every_adopted_chapter_and_its_own_record(env):
    client, storage = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original')
    with_me(client)
    first_id = start(client, [pick(wen, position='supporting')], include_me=True, title='留一條接縫')
    assert run_to_end(client, first_id)['run']['status'] == 'completed'
    opened = client.post('/api/series', json={'request_id': 'series-1', 'work_id': first_id})
    assert opened.status_code in (200, 201), opened.text
    sid = opened.json()['id']
    second = client.post(f'/api/series/{sid}/episodes', json={'request_id': 'ep-2', 'title': '開門之前', 'scene': {'description': '隔天早上，展場開門前。'}})
    assert second.status_code == 201, second.text
    second_id = second.json()['id']
    assert run_to_end(client, second_id)['run']['status'] == 'completed'
    assert client.post(f'/api/series/{sid}/episodes/{second_id}/adopt', json={'request_id': 'ad-2'}).status_code == 200
    rewrite_plan(client, first_id, lambda plan_data: enrich(plan_data, '〔TEASER1〕第一章的預告'))
    rewrite_plan(client, second_id, lambda plan_data: enrich(plan_data, '〔TEASER2〕第二章的預告'))

    reader = export(client, sid, 'ex-series').json()['export']
    created = export(client, sid, 'ex-series-play', player='play')
    assert created.status_code == 201, created.text
    play = created.json()['export']
    assert (reader['player'], reader['version_no'], play['player'], play['version_no']) == ('reader-3', 1, 'play-2', 2)
    assert play['filename'] == '留一條接縫（互動版）.html'
    assert export(client, sid, 'ex-series-again').json()['export'] == reader, '閱讀版仍是原來那一筆'
    html = client.get(play['download_path']).content.decode('utf-8')
    story = json.loads(story_block(html))
    assert story['format'] == 'lw-play.v2' and len(story['chapters']) == 2
    assert [[(item['name'], item['secret']) for item in chapter['secrets']] for chapter in story['chapters']] == [[('溫若岑', SECRET)], [('溫若岑', SECRET)]]
    assert all(seg['state'] and seg['who'] in (1, 2) for chapter in story['chapters'] for beat in chapter['beats'] for seg in beat['segments'])
    body = page(html)
    assert re.findall(r'<h3 class="lw-secrets-chapter">([^<]+)</h3>', body) == ['第 1 章　留一條接縫', '第 2 章　開門之前']
    assert body.count('<section class="lw-end"') == 1 and body.count(SECRET) == 2
    assert body.count('<aside class="lw-teaser">') == 1 and '〔TEASER2〕' in body and '〔TEASER1〕' not in body
