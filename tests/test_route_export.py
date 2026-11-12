"""回合制互動作品（works.kind='turn_game'、game.v1）匯出成離線 HTML，以及站內直接看的路由。

驗證重點：
1. 互動遊戲可以匯出，只有一種播放器 route-1（請求不帶 player 或帶 play 都是它）；內嵌資料是 lw-route.v1，檔名是「標題（互動遊戲）.html」。
2. 檔案裡只有作品本身：不帶建立時的說明、人物的識別碼與公開簡介、生成的識別碼；作品文字一律跳脫，內嵌資料不會提早結束 script 區塊。
3. 同樣的內容產出逐位元相同的檔案；相同內容只存一份、只記一筆。
4. 還在生成（build.status 不是 ready）的遊戲不能匯出：409 game_not_ready。
5. 沒有程式也讀得到開場白、同行的人與所有站的清單；反應、願望與結局收在預設不展開的區塊。
6. 站內直接看（GET …/exports/{版本}/view）：同一份檔案、不是附件；只有這一條回應允許被同源的頁面框住，
   而且自帶 sandbox（就算直接在分頁打開，也不會以本站的身分執行）；別人拿不到；其他回應的安全標頭和原本一樣。
   閱讀版、互動版的匯出也可以這樣看。
7. 既有作品的輸出不變：閱讀版（reader-3）與互動版（play-2）對固定輸入的檔案雜湊，和加入互動遊戲之前記下的一樣。
8. 和生成那一半接起來（假模型；那些路由還沒接上時跳過）：經過 /api/games 做出來的遊戲可以匯出，
   播放器對所有走得到的行程算出來的結局種類，和伺服器寫進作品的「走得到的結局」一致。

測試資料直接把一份 game.v1 內容寫進測試用的資料庫（不經過生成的路由，也不呼叫模型）；內容是 tests/trip_reference.py 的手寫示意資料。
這是本機 SQLite 的開發檢查（記憶體儲存，不連網、不計費）。
"""
import copy
import hashlib
import json
import os
import random
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

import trip_reference as ref
from app.object_storage import MemoryStorage
from app.work_export import render_html, render_play_html, render_route_html, play_data, route_data, story_data
from test_person_source_generation import code, fields, person, ready
from test_work_export import CAST, OLD_PLAN, TURNS, csp_hash, export, finished, make_client, plan, saved, sha, story_block

GAME_ID = 'game-1'
INTERNAL = ('〔SETUP〕', '〔PUBLIC-', 'person-c1', 'person-c2', 'profile-c1', 'sha-c1', 'gen-game-sample',
            'generation_id', 'person_id', 'public_profile', 'content_sha256', 'profile_id', '"setup"', '"build"')
DENY_ALL = "default-src 'none'; sandbox"  # 下載路由原本的 CSP


@pytest.fixture
def env(tmp_path):
    storage = MemoryStorage()
    with make_client(tmp_path, storage) as client:
        ready(client)
        yield client, storage


def plant(client, content, work_id=GAME_ID):
    """把一件互動遊戲直接寫進資料庫（生成的路由由另一個模組負責，這裡不依賴它）。回傳擁有者的識別碼。"""
    owner = client.get('/api/auth/me').json()['owner_id']
    now = '2026-11-12T03:00:00+00:00'
    with client.app.state.service.db.connect(write=True) as db:
        db.execute("INSERT INTO works(id,owner_id,kind,title,status,current_version,revision,created_at,updated_at) VALUES (?,?,'turn_game',?,'active',1,1,?,?)",
                   (work_id, owner, content['title'], now, now))
        db.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                   "VALUES (?,?,1,NULL,'ai','game.v1',?,NULL,?)", (work_id, owner, json.dumps(content, ensure_ascii=False), now))
    return owner


def body_of(html):
    """讀者看得到的頁面內容：不含內嵌的樣式、資料與程式。"""
    return html[html.index('<body>'):html.index('<script type="application/json"')]


def test_a_ready_game_exports_as_one_offline_route_file(env):
    client, storage = env
    game = ref.sample()
    owner = plant(client, game)
    assert client.get(f'/api/works/{GAME_ID}/exports').json() == {'available': True, 'items': []}

    created = export(client, GAME_ID)  # 請求不帶 player
    assert created.status_code == 201, created.text
    item = created.json()['export']
    name = f"works/{owner}/{GAME_ID}/{item['sha256']}.html"
    assert list(storage.objects) == [name] and storage.content_types[name] == 'text/html; charset=utf-8'
    data = storage.objects[name]
    assert item['version_no'] == 1 and item['format'] == 'html' and item['player'] == 'route-1'
    assert item['filename'] == '版面樣張，示意資料｜海線小鎮一日行（互動遊戲）.html'
    assert item['size'] == len(data) and item['sha256'] == sha(data) and item['source_version'] == 1
    assert export(client, GAME_ID, 'ex-2', player='play').json()['export'] == item, '帶 player=play 也是同一種播放器、同一筆匯出'
    assert len(storage.objects) == 1 and storage.writes == 1

    html = data.decode('utf-8')
    assert html.startswith('<!doctype html>') and '<html lang="zh-Hant">' in html
    assert '<meta name="generator" content="Life World route-1">' in html
    assert not re.search(r'(src|href|action)\s*=\s*["\']?(https?:)?//', html), '不引用任何外部資源'
    assert '<link' not in html and '<img' not in html and 'url(' not in html and '@import' not in html
    csp = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', html).group(1)
    style = re.search(r'<style>(.*?)</style>', html, re.S).group(1)
    script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
    assert "default-src 'none'" in csp and csp_hash(style) in csp and csp_hash(script) in csp, '內嵌的樣式與程式以雜湊鎖定'
    assert "'unsafe-inline'" not in csp and 'http' not in csp
    assert ' style="' not in body_of(html), '頁面裡沒有行內樣式（CSP 不放行）'

    # 內嵌資料 lw-route.v1：規格裡的內容去掉內部欄位，人物加上色號
    block = story_block(html)
    assert '<' not in block
    route = json.loads(block)
    assert route == route_data(game)
    assert set(route) == {'format', 'skin', 'title', 'genre', 'premise', 'cast', 'player', 'meter', 'clock', 'speed', 'home', 'events', 'wishes', 'farewells', 'endings'}
    assert route['format'] == 'lw-route.v1' and route['skin'] == 'trip' and route['title'] == game['title']
    assert route['cast'] == [{'id': 'c1', 'name': '何以晴', 'color': 1}, {'id': 'c2', 'name': '溫若岑', 'color': 2}]
    assert route['player'] == {'name': '你'}
    for key in ('genre', 'premise', 'meter', 'clock', 'speed', 'home', 'events', 'wishes', 'farewells', 'endings'):
        assert route[key] == game[key], key
    for mark in INTERNAL:
        assert mark not in html, mark

    # 下載：和其他作品一樣是附件
    downloaded = client.get(item['download_path'])
    assert downloaded.status_code == 200 and downloaded.content == data
    assert downloaded.headers['content-disposition'].startswith('attachment;') and downloaded.headers['content-security-policy'] == DENY_ALL


def test_without_scripts_the_page_lists_the_trip_and_keeps_spoilers_folded():
    game = ref.sample()
    html = render_route_html(route_data(game)).decode('utf-8')
    body = body_of(html)
    assert f'<h1>{game["title"]}</h1>' in body and game['premise'] in body and '互動遊戲' in body
    folded = body[body.index('<details'):body.index('</details>')]
    shown = body[:body.index('<details')]
    assert '<details class="lw-spoilers">' in body and body.count('<details') == 1 and ' open' not in body[body.index('<details'):body.index('<details') + 40]
    # 看得到的：同行的人、你扮演誰、出發時間與總時數、需要執行程式的說明、每一站的名稱、描述、營業時間、停留、標籤
    for text in ('何以晴', '溫若岑', '08:00', '10 小時', '18:00', '車站', game['home']['text'], '需要執行程式'):
        assert text in shown, text
    for event in game['events']:
        assert event['name'] in shown and event['text'] in shown
    assert '營業 06:00–11:00' in shown and '停留 45 分' in shown and '營業 13:00–16:00' in shown and '停留 1 小時 30 分' in shown
    assert '<span class="lw-tag">市場</span>' in shown
    assert 'data-c="1"' in shown and 'data-c="2"' in shown, '同行者的名字帶著他的色號'
    # 收起來的：每個人的反應與數值、願望、最後一句話、結局——沒有程式時也不會先露出來
    for event in game['events']:
        for reaction in event['reactions'].values():
            for key in ('low', 'mid', 'high'):
                assert reaction[key] not in shown and reaction[key] in folded
    for text in list(game['wishes'].values()) + [line for lines in game['farewells'].values() for line in lines.values()]:
        assert text not in shown and text in folded
    for ending in game['endings']['classes'].values():
        assert ending['title'] not in shown and ending['title'] in folded and ending['text'] in folded
    assert '滿意 +2' in folded and '滿意 −2' in folded and '+2' not in shown, '數值的加減只在收起來的區塊裡'
    # 要靠程式的東西先藏著：工具列與遊戲畫面
    assert '<div class="lw-tools" hidden>' in body and re.search(r'<div class="lw-game"[^>]* hidden>', body)
    assert '<button' not in re.sub(r'<div class="lw-tools" hidden>.*?</div>', '', body), '沒有程式時不會出現按了沒反應的按鈕'
    all_day = ref.sample()
    all_day['events'][0].update(open=0, close=1440)
    assert '整天開放' in render_route_html(route_data(all_day)).decode('utf-8')


def test_text_is_escaped_and_the_embedded_data_cannot_end_its_block(env):
    client, storage = env
    evil, tag = '<script>alert(1)</script>', '</script><img src=x onerror=alert(2)>'
    game = ref.sample(title=evil + '海線', premise=tag + '開場')
    game['cast'][0]['name'] = '何<b>以晴'
    game['player']['name'] = '你&me'
    game['home'].update(name='車"站', text=tag)
    game['events'][0].update(name=evil, text=tag, tags=['<i>吃', "it's"])
    game['events'][0]['reactions']['c1'].update(low=evil, mid=tag, high='A&B')
    game['wishes']['c1'] = tag
    game['farewells']['c2']['high'] = evil
    game['endings']['classes']['perfect'].update(title=evil, text=tag)
    game['meter']['label'] = '滿<意'
    plant(client, game)
    created = export(client, GAME_ID)
    assert created.status_code == 201, created.text
    assert not set('<>:"/\\|?*') & set(created.json()['export']['filename']), '檔名不含作業系統不接受的字元'
    html = next(iter(storage.objects.values())).decode('utf-8')
    assert '<script>alert(1)' not in html and '<img src=x' not in html and '何<b>以晴' not in html and '<i>吃' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;海線' in html and '何&lt;b&gt;以晴' in html and '你&amp;me' in html
    assert html.count('<script') == 2 and html.count('</script>') == 2, '只有內嵌資料與播放器這兩個區塊'
    block = story_block(html)
    assert '<' not in block and '>' not in block and '&' not in block
    route = json.loads(block)
    assert route['title'] == evil + '海線' and route['events'][0]['reactions']['c1'] == {'delta': 2, 'low': evil, 'mid': tag, 'high': 'A&B'}
    assert route['events'][0]['tags'] == ['<i>吃', "it's"] and route['meter']['label'] == '滿<意' and route['home']['name'] == '車"站'


def test_the_same_game_gives_the_same_bytes_and_is_stored_once(env):
    client, storage = env
    game = ref.sample()
    plant(client, game)
    first = export(client, GAME_ID, 'ex-1').json()
    assert export(client, GAME_ID, 'ex-2').json() == first, '內容沒有變：回同一筆匯出，不新增版本'
    assert export(client, GAME_ID, 'ex-1').json() == first, '同一提交代碼重送回原結果'
    assert len(storage.objects) == 1 and storage.writes == 1 and len(client.get(f'/api/works/{GAME_ID}/exports').json()['items']) == 1
    data = next(iter(storage.objects.values()))
    assert render_route_html(route_data(game)) == data == render_route_html(route_data(copy.deepcopy(game)))

    def shuffled(value, rng):  # 同樣的內容、不同的欄位順序（資料庫讀回來的順序不保證）
        if isinstance(value, dict):
            keys = list(value)
            rng.shuffle(keys)
            return {key: shuffled(value[key], rng) for key in keys}
        return [shuffled(item, rng) for item in value] if isinstance(value, list) else value

    assert render_route_html(route_data(shuffled(game, random.Random(7)))) == data, '欄位順序不影響輸出'
    changed = ref.sample()
    changed['events'][0]['stay'] = 60
    assert render_route_html(route_data(changed)) != data


def test_a_game_that_is_still_building_cannot_be_exported(env):
    client, storage = env
    game = ref.sample(build={'status': 'building', 'done': ['plan', 'c1'], 'pending': ['c2']})
    for event in game['events']:  # 生成到一半的樣子：第二位同行者還沒有反應，願望、最後一句話與門檻也還沒有
        del event['reactions']['c2']
    del game['wishes']['c2'], game['farewells']['c2'], game['endings']['thresholds'], game['endings']['reachable']
    plant(client, game)
    assert code(export(client, GAME_ID)) == (409, 'game_not_ready')
    assert code(export(client, GAME_ID, 'ex-play', player='play')) == (409, 'game_not_ready')
    assert storage.objects == {} and client.get(f'/api/works/{GAME_ID}/exports').json() == {'available': True, 'items': []}
    plant(client, ref.sample(build={'status': 'ready'}), 'game-2')
    assert export(client, 'game-2', 'ex-ready').status_code == 201
    no_build = ref.sample()
    del no_build['build']
    plant(client, no_build, 'game-3')
    assert code(export(client, 'game-3', 'ex-none')) == (409, 'game_not_ready'), '沒有生成進度的內容當成還沒好'


def test_only_the_owner_can_export_or_read_a_game(env):
    client, _ = env
    plant(client, ref.sample())
    item = export(client, GAME_ID).json()['export']
    other = TestClient(client.app)
    ready(other, 'route_other')
    assert code(other.get(f'/api/works/{GAME_ID}/exports')) == (404, 'not_found')
    assert code(export(other, GAME_ID, 'ex-theirs')) == (404, 'not_found')
    assert code(other.get(item['download_path'])) == (404, 'not_found')
    assert code(other.get(f'/api/works/{GAME_ID}/exports/1/view')) == (404, 'not_found')


def view_path(work_id, version=1):
    return f'/api/works/{work_id}/exports/{version}/view'


def test_the_view_route_serves_the_same_file_inline_for_same_origin_framing_only(env):
    client, storage = env
    plant(client, ref.sample())
    item = export(client, GAME_ID).json()['export']
    data = next(iter(storage.objects.values()))
    html = data.decode('utf-8')

    viewed = client.get(view_path(GAME_ID))
    assert viewed.status_code == 200 and viewed.content == data, '和下載的是同一份檔案'
    headers = viewed.headers
    assert headers['content-type'].startswith('text/html') and 'content-disposition' not in headers, '不是附件：直接顯示'
    assert headers['x-frame-options'] == 'SAMEORIGIN'
    csp = headers['content-security-policy']
    directives = dict(part.strip().split(' ', 1) if ' ' in part.strip() else (part.strip(), '') for part in csp.split(';'))
    assert directives['frame-ancestors'] == "'self'", '只允許同源的頁面框住'
    assert directives['sandbox'] == 'allow-scripts', '自帶 sandbox：直接在分頁打開也不會以本站的身分執行'
    assert directives['default-src'] == "'none'" and directives['base-uri'] == "'none'" and directives['form-action'] == "'none'"
    style = re.search(r'<style>(.*?)</style>', html, re.S).group(1)
    script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
    assert directives['script-src'] == csp_hash(script) and directives['style-src'] == csp_hash(style), '程式與樣式用檔案本身的雜湊放行'
    assert "'unsafe-inline'" not in csp and "'unsafe-eval'" not in csp and '*' not in csp and 'http' not in csp
    assert 'connect-src' not in directives, '沒有放行任何連線（default-src 是 none）'
    assert headers['x-content-type-options'] == 'nosniff' and 'no-store' in headers['cache-control']

    # 其他回應的安全標頭和原本一樣
    downloaded = client.get(item['download_path'])
    assert downloaded.headers['x-frame-options'] == 'DENY' and downloaded.headers['content-security-policy'] == DENY_ALL
    assert downloaded.headers['content-disposition'].startswith('attachment;')
    home = client.get('/')
    assert home.headers['x-frame-options'] == 'DENY' and "frame-ancestors 'none'" in home.headers['content-security-policy']
    for path in (f'/api/works/{GAME_ID}/exports', '/api/capabilities', '/static/app.js', '/api/works/center?tab=all'):
        assert client.get(path).headers['x-frame-options'] == 'DENY', path
    # 這一條路由失敗時也不放寬；長得像的路徑不算
    for path, expected in ((view_path(GAME_ID, 9), 404), (view_path('no-such-work'), 404), (view_path(GAME_ID) + '/extra', 404),
                           (f'/api/works/{GAME_ID}/exports/view', 404), (view_path(GAME_ID, 'x'), 422)):
        response = client.get(path)
        assert response.status_code == expected and response.headers['x-frame-options'] == 'DENY', path
        assert "frame-ancestors 'self'" not in response.headers.get('content-security-policy', ''), path
    assert client.post(view_path(GAME_ID)).status_code == 405

    # 檔案被改動或不見了：和下載一樣拒絕，也不放寬
    name = next(iter(storage.objects))
    storage.objects[name] = b'<html>changed</html>'
    changed = client.get(view_path(GAME_ID))
    assert code(changed) == (409, 'export_file_mismatch') and changed.headers['x-frame-options'] == 'DENY'
    del storage.objects[name]
    assert code(client.get(view_path(GAME_ID))) == (404, 'export_file_missing')


def test_the_view_route_also_shows_reader_and_play_exports(env):
    client, storage = env
    _, work_id, _ = finished(client)
    reader = export(client, work_id, 'ex-reader').json()['export']
    play = export(client, work_id, 'ex-play', player='play').json()['export']
    assert (reader['player'], play['player']) == ('reader-3', 'play-2')
    for item in (reader, play):
        viewed = client.get(view_path(work_id, item['version_no']))
        assert viewed.status_code == 200 and sha(viewed.content) == item['sha256'] and 'content-disposition' not in viewed.headers
        html = viewed.content.decode('utf-8')
        csp = viewed.headers['content-security-policy']
        assert csp_hash(re.search(r'<script>(.*?)</script>', html, re.S).group(1)) in csp
        assert csp_hash(re.search(r'<style>(.*?)</style>', html, re.S).group(1)) in csp
        assert "frame-ancestors 'self'" in csp and 'sandbox allow-scripts' in csp and viewed.headers['x-frame-options'] == 'SAMEORIGIN'
        assert client.get(item['download_path']).headers['x-frame-options'] == 'DENY'


def test_without_storage_the_view_route_is_unavailable(tmp_path):
    with make_client(tmp_path) as client:
        ready(client)
        plant(client, ref.sample())
        response = client.get(view_path(GAME_ID))
        assert code(response) == (503, 'export_storage_unavailable') and response.headers['x-frame-options'] == 'DENY'


# ---- 既有作品的輸出不變 ----
# 加入互動遊戲之前（2026-11-12），用同一批手寫輸入（tests/test_work_export.py 的陣容、段落、新舊兩種規劃）產生檔案並記下雜湊。
# 閱讀版與互動版的程式、樣式或組檔方式只要有任何一個位元組不同，這裡就會失敗；真的要改播放器時應該換新的版本名稱，再更新這些數字。
BEFORE = {
    'reader-new-script': '28cd16724073a0f64e04a854aeaa550d36e8bd02885babc732b32d808e5befa0',
    'play-new-script': '5e7fc4368240ada152e0bd5a09510ba1165a12627cdf94e84e36ea8d6b26d1d8',
    'reader-new-narrative': 'b29760f0f879693e0e42ddc5610f89802b6b1304b8f6f6bcf395c63661af36fc',
    'play-new-narrative': '0b7a5ecbe4d461649402158b547e741aafeca4b67bc040fbb4cbfb7417650a68',
    'reader-old-script': 'af5798f091d210ae418ea224833053a2f7778192d1c26a68bfb65c9204e1e45c',
    'play-old-script': '3cb830dd87eac2357f65103c335eb00c1423aae392e1cf9defd74eaf660ee403',
    'reader-old-narrative': 'b4ad5d0a6fa28897ff482587b454998630aa4e55040dde0d47d57fb50fad0336',
    'play-old-narrative': 'dfb0e0e775d965fe9cecda4689b21f94b85f9794077ac2b05417d543301878e9',
}


@pytest.mark.parametrize('name,plan_data', [('new', plan()), ('old', OLD_PLAN)])
@pytest.mark.parametrize('form', ['script', 'narrative'])
def test_reader_and_play_files_are_byte_for_byte_what_they_were(name, plan_data, form):
    chapters = [(1, plan_data['title'], saved(CAST, plan_data, form), TURNS)]
    reader = render_html(story_data(plan_data['title'], CAST, chapters), '2026-11-12')
    play = render_play_html(play_data(plan_data['title'], CAST, chapters), '2026-11-12')
    assert hashlib.sha256(reader).hexdigest() == BEFORE[f'reader-{name}-{form}']
    assert hashlib.sha256(play).hexdigest() == BEFORE[f'play-{name}-{form}']
    assert b'route-1' not in reader and b'route-1' not in play and b'lw-route' not in reader and b'lw-route' not in play


# ---- 和生成那一半接起來 ----
ENDINGS_SCRIPT = r"""
const rules = require('./app/export_player/route-1.js');
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(input.routes.map(picks => rules.ending(input.data, picks))));
"""


def test_a_game_made_by_the_generation_routes_exports_and_the_player_reaches_exactly_its_listed_endings(env):
    """兩個人各做一半（生成、播放器），靠同一份規格對接。這裡把兩半接起來走一次（假模型，不連網）：
    建立 → 每位同行者各生成一次 → ready → 匯出 → 檔案裡的資料交給播放器的規則，把所有走得到的行程都算一遍。
    播放器算出來的結局種類要剛好是伺服器寫進作品的 reachable（「已看過 n／N 種結局」的分母才是對的），參考實作也要同意。"""
    client, storage = env
    people = [person(client, f'p-{tag}', name, profile=fields(tag), person_subtype='original', description=f'〔{tag}公開〕')
              for tag, name in (('P1', '何以晴'), ('P2', '溫若岑'))]
    created = client.post('/api/games', json={'request_id': 'g-1', 'skin': 'trip', 'participants': [{'person_id': item['id']} for item in people],
                                              'player': {'name': '小光'}, 'description': '週六去海邊小鎮走走。', 'start_place': '車站', 'hours': 10,
                                              'start_time': '08:00', 'title': ''})
    if created.status_code in (404, 405):
        pytest.skip('生成的路由（/api/games）還沒有接上')
    assert created.status_code == 201, created.text
    game_id = created.json()['id']
    assert code(export(client, game_id, 'ex-early')) == (409, 'game_not_ready'), '還有同行者沒生成：不能匯出'
    for number in range(1, 9):
        build = client.post(f'/api/games/{game_id}/advance', json={'request_id': f'a-{number}'}).json()['build']
        if build['status'] == 'ready':
            break
    assert build['status'] == 'ready'

    exported = export(client, game_id, 'ex-ready')
    assert exported.status_code == 201, exported.text
    item = exported.json()['export']
    assert item['player'] == 'route-1' and item['filename'].endswith('（互動遊戲）.html')
    html = next(iter(storage.objects.values())).decode('utf-8')
    data = json.loads(story_block(html))
    assert data['format'] == 'lw-route.v1' and data['skin'] == 'trip' and data['player'] == {'name': '小光'}
    assert [(member['name'], member['color']) for member in data['cast']] == [('何以晴', 1), ('溫若岑', 2)]
    assert all(set(event['reactions']) == {member['id'] for member in data['cast']} for event in data['events']), '每一站每個人都有反應'
    assert set(data['wishes']) == set(data['farewells']) == {member['id'] for member in data['cast']}
    assert set(data['endings']['thresholds']) == {'great', 'poor'} and data['endings']['reachable']
    # 人物設定與公開簡介的標記、識別碼、建立時的設定都不在檔案裡（假模型的開場白會照抄說明的文字，所以不拿說明本身來比）
    for mark in ('〔P1', '〔P2', 'person_id', 'public_profile', 'generation_id', '"setup"', '"build"', '"description"') + tuple(item['id'] for item in people):
        assert mark not in html, mark
    viewed = client.get(f'/api/works/{game_id}/exports/{item["version_no"]}/view')
    assert viewed.status_code == 200 and viewed.headers['x-frame-options'] == 'SAMEORIGIN' and sha(viewed.content) == item['sha256']

    # 播放器的規則對這份實際的資料：所有走得到的行程（至少去一站）各算一次結局
    node = os.environ.get('LIFEWORLD_NODE') or shutil.which('node')
    if not node:
        pytest.skip('需要 Node 執行播放器的純函式；可設定 LIFEWORLD_NODE')
    routes = [picks + ['home'] for picks in ref.routes(data)]
    assert data['home']['id'] == 'home' and routes
    result = subprocess.run([node, '-e', ENDINGS_SCRIPT], input=json.dumps({'data': data, 'routes': routes}), capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    kinds = json.loads(result.stdout)
    assert kinds == [ref.ending(data, picks) for picks in routes], '播放器和參考實作對每一條行程的結局一致'
    assert sorted(set(kinds) | {'poor'}) == sorted(data['endings']['reachable']), '走得到的結局種類和伺服器算的一致（一站都沒去一律是 poor）'
