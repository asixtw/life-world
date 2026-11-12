"""互動遊戲（路線播放器 route-1）的匯出檔在 Chrome 裡離線開啟（file://，不連任何網站、不需要 8030）。

    .venv\\Scripts\\python.exe -m pytest -q browser_tests/test_export_route_offline.py

直接用 app.work_export.render_route_html 產生檔案，以完全離線的瀏覽環境開啟並實際操作，確認：
1 出發前：標題、開場白、同行的人（數值都是 0）、你扮演誰、出發時間與總時數、示意地圖與「出發」；還沒有任何反應與選項 →
2 每到一站：左欄多一項（到達時間、站名、當時幾選一）、右欄是這一站與每個人的反應；時間、反應用哪一句、數值升降都和 Python 的參考實作一致 →
3 選項卡只寫代價（車程、到達、等多久、停留、打烊、標籤），不寫會讓誰的數值升降；能去的在前、由近到遠；不能去的灰掉並寫原因 →
4 先看到反應，數值過一會兒才動並標出升降（用假的時鐘確認先後）→
5 點左欄的舊站：時間與數值都回到當時，可以改選；之後的選擇作廢 →
6 回起點：依數值判定結局；結局卡、每個人最後的數值與最後一句話、這時才揭曉的願望、片尾字幕（標題、同行的人、行程表、總時間、結局）→
7 好結局有煙火或紙花、壞結局下雨並褪色、普通的結局沒有特效；音樂預設沒有播，按了才建立音訊，可以再關掉 →
8 系統要求減少動態效果時沒有動畫特效、字幕直接是全文 → 9 已看過幾種結局會累計，重新開啟還記得 →
10 手機寬度不橫向捲動，左欄收成可以展開的一列 → 11 列印時印出目前走出來的行程表 →
12 不能執行程式時是可讀的清單，反應、願望與結局收合 → 13 放進沙箱 iframe（站內直接玩的情況：沒有 localStorage）照樣能玩 →
14 沒有對外連線、主控台沒有錯誤。
另外在真的瀏覽器裡確認站內直接玩的安全標頭（請求由測試攔截後直接回應，仍然完全離線）：
本站的頁面框得住那一條回應，別的來源框不住，下載的回應也框不住。
這裡的內容是 tests/trip_reference.py 的手寫示意資料，不是模型生成的作品。
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))  # 參考實作與示意資料放在 tests/ 底下

import trip_reference as ref  # noqa: E402
from app.work_export import render_route_html, route_data  # noqa: E402

GAME = ref.sample()
NAMES = {GAME['home']['id']: GAME['home']['name'], **{event['id']: event['name'] for event in GAME['events']}}
EVENTS = {event['id']: event for event in GAME['events']}
PEOPLE = {member['id']: member['name'] for member in GAME['cast']}
LABEL = GAME['meter']['label']
PERFECT, GREAT, OK, POOR = ['p2', 'p5', 'p7', 'home'], ['p7', 'home'], ['p2', 'home'], ['p1', 'p3', 'home']  # 四種結局各一條走法
# 記下頁面建立了幾次音訊、關了幾次。由自動化介面在頁面的程式之前放進去：不受檔案 CSP 的限制，也不會產生連線。
AUDIO_PROBE = """
window.__audio = {made: 0, closed: 0};
(function () {
  var Real = window.AudioContext;
  if (!Real) return;
  window.AudioContext = function () {
    window.__audio.made += 1;
    var context = new Real();
    var close = context.close.bind(context);
    context.close = function () { window.__audio.closed += 1; return close(); };
    return context;
  };
})();
"""


@pytest.fixture
def chrome():
    path = Path(os.environ.get('ProgramFiles', '')) / 'Google/Chrome/Application/chrome.exe'
    if not path.is_file():
        pytest.skip('需要本機的 Chrome')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(path))
        yield browser
        browser.close()


def written(tmp_path, game=GAME, name='route.html'):
    target = tmp_path / name
    target.write_bytes(render_route_html(route_data(game)))
    return target


def watch(page):
    """記下主控台的問題與所有連線。"""
    problems, requests = [], []
    page.on('console', lambda message: problems.append(message.text) if message.type in ('error', 'warning') else None)
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.on('request', lambda request: requests.append(request.url))
    return problems, requests


def opened(chrome, target, width=1200, height=900, **options):
    """用完全離線的瀏覽環境開啟檔案；回傳（環境, 頁面, 主控台問題, 連線紀錄）。"""
    context = chrome.new_context(viewport={'width': width, 'height': height}, offline=True, color_scheme='light', locale='zh-TW', **options)
    context.add_init_script(AUDIO_PROBE)
    page = context.new_page()
    problems, requests = watch(page)
    page.goto(target.as_uri())
    return context, page, problems, requests


def settled(page):
    """等這一步的數值升降演完。"""
    expect(page.locator('.lw-game')).to_have_attribute('data-settled', '1')


def depart(page):
    page.get_by_role('button', name='出發', exact=True).click()
    settled(page)


def choose(page, node):
    page.locator(f'.lw-option[data-go="{node}"]').click()
    settled(page)


def walk(page, picks):
    depart(page)
    for node in picks:
        choose(page, node)


def shown_meters(page):
    """數值列上每個人現在的數值與升降標示：{代號: (數值, 升降)}；沒有標升降是空字串。"""
    result = {}
    for box in page.locator('.lw-cast .lw-meter').all():
        delta = box.locator('.lw-delta')
        result[box.get_attribute('data-who')] = (box.locator('.lw-meter-value').inner_text(), delta.inner_text() if delta.is_visible() else '')
    return result


def mark(change):
    """升降的標示：▲ +2、▼ −1；沒有變就是空的。"""
    return f'▲ {ref.signed(change)}' if change > 0 else f'▼ {ref.signed(change)}' if change < 0 else ''


def among_text(step, index):
    if index == 0:
        return '出發'
    text = f"{step['among']} 選 1" if step['among'] > 1 else '沒有別的選擇'
    return '回到起點・' + text if step['final'] else text


def when_text(step, index):
    """右欄節點上方那一行（照參考實作算出來的時間）。"""
    if index == 0:
        return ref.clock(step['arrive']) + ' 出發'
    wait = f"（等 {ref.span(step['wait'])}開門）" if step['wait'] else ''
    return f"車程 {ref.span(step['travel'])}・{ref.clock(step['arrive'])} 到{wait}・停留 {ref.span(step['stay'])}・{ref.clock(step['leave'])} 離開"


def status_text(game, now):
    limit = ref.deadline(game)
    return f"現在 {ref.clock(now)}・還剩 {ref.span(limit - now)}（{ref.clock(limit)} 前要回到{game['home']['name']}）"


def card_rows(game, option):
    """一張選項卡上的幾行（照參考實作算出來的時間）。"""
    if option['final']:
        return [ref.span(option['travel']) if option['travel'] else '就在這裡', ref.clock(option['arrive'])]
    wait = f"（等 {ref.span(option['wait'])}開門）" if option['wait'] else ''
    return [ref.span(option['travel']), ref.clock(option['arrive']) + wait, f"{ref.span(option['stay'])}，{ref.clock(option['leave'])} 離開", ref.clock(option['close'])]


def check_position(page, picks, game=GAME):
    """畫面和參考實作逐項對照：左欄每一步、右欄這一站的時間與反應、數值列、現在幾點、每一張選項卡。picks 還沒有回到起點。"""
    names = {game['home']['id']: game['home']['name'], **{event['id']: event['name'] for event in game['events']}}
    state = ref.replay(game, picks)
    steps = state['steps']
    last = steps[-1]
    # 左欄：到達時間、站名、當時幾選一；最後一項標成目前位置
    assert page.locator('.lw-step-time').all_inner_texts() == [ref.clock(step['arrive']) for step in steps]
    assert page.locator('.lw-step-name').all_inner_texts() == [names[step['node']] for step in steps]
    assert page.locator('.lw-step-among').all_inner_texts() == [among_text(step, index) for index, step in enumerate(steps)]
    assert page.locator('.lw-step[aria-current=step]').get_attribute('data-step') == str(len(steps) - 1)
    # 右欄：這一站
    assert page.locator('.lw-node-name').inner_text() == names[last['node']]
    assert page.locator('.lw-node-when').inner_text() == when_text(last, len(steps) - 1)
    assert page.locator('.lw-clock').inner_text() == status_text(game, state['now'])
    # 每個人的反應：用到站前的態度那一句；升降和參考實作一致，沒有變就不標
    rows = page.locator('.lw-reaction')
    assert [row.get_attribute('data-who') for row in rows.all()] == [item['who'] for item in last['reactions']]
    assert page.locator('.lw-reaction-text').all_inner_texts() == [item['text'] for item in last['reactions']]
    for row, item in zip(rows.all(), last['reactions']):
        delta = row.locator('.lw-delta')
        assert (delta.inner_text() if delta.is_visible() else '') == (f"{mark(item['change'])} {LABEL}" if item['change'] else '')
    changes = {item['who']: item['change'] for item in last['reactions']}
    assert shown_meters(page) == {who: (ref.signed(value), mark(changes.get(who, 0))) for who, value in state['meters'].items()}
    # 選項卡：順序、能不能選、每一行的時間、不能選的原因
    options = ref.options(game, picks)
    cards = page.locator('.lw-option')
    assert [card.get_attribute('data-go') for card in cards.all()] == [option['id'] for option in options]
    for card, option in zip(cards.all(), options):
        assert (card.get_attribute('aria-disabled') == 'true') == (not option['enabled']), option['id']
        assert card.locator('.lw-val').all_inner_texts() == card_rows(game, option), option['id']
        why = card.locator('.lw-option-why')
        reason = {'closed': f"來不及：{ref.clock(option.get('close', 0))} 打烊", 'late': '去了就趕不回起點', '': None}[option['reason']]
        assert (why.inner_text() if why.count() else None) == reason, option['id']
    return state


def audio(page):
    return page.evaluate('window.__audio')


def test_a_good_run_from_the_start_screen_to_the_perfect_ending_with_fireworks(chrome, tmp_path):
    context, page, problems, requests = opened(chrome, written(tmp_path))
    html = page.locator('html')

    # 1. 出發前：標題、開場白、同行的人（數值從 0 開始）、你扮演誰、出發時間與總時數、示意地圖、「出發」
    assert page.locator('.lw-tools').is_visible() and not page.locator('.lw-static').is_visible(), '內嵌程式有執行：靜態的清單收起來'
    assert html.get_attribute('data-phase') == 'start' and html.get_attribute('data-music') == 'off'
    assert page.locator('h1').inner_text() == GAME['title'] and page.locator('.lw-genre').inner_text() == '行程'
    assert GAME['premise'] in page.locator('.lw-premise').inner_text()
    assert page.locator('.lw-meta dt').all_inner_texts() == ['同行', '你扮演', '行程']
    assert page.locator('.lw-meta dd').all_inner_texts() == ['何以晴、溫若岑', '你', '08:00 從車站出發，10 小時內要回到車站（18:00 前）']
    assert page.locator('.lw-cast .lw-name').all_inner_texts() == ['何以晴', '溫若岑']
    assert page.locator('.lw-cast .lw-meter-label').all_inner_texts() == [LABEL, LABEL]
    assert shown_meters(page) == {'c1': ('0', ''), 'c2': ('0', '')}
    first, second = (page.locator('.lw-cast .lw-name').nth(index).evaluate('(e) => getComputedStyle(e).color') for index in (0, 1))
    assert first != second, '每位同行者用自己的顏色'
    start = page.locator('.lw-start')
    assert start.locator('.lw-intro li').all_inner_texts()[:2] == ['08:00 從車站出發', '10 小時內要回到車站（18:00 前）']
    picture = start.locator('svg.lw-map')
    assert picture.is_visible() and picture.locator('.lw-map-dot').count() == 7 and picture.locator('.lw-map-home').count() == 1
    assert set(picture.locator('.lw-map-label').all_text_contents()) == set(NAMES.values())
    assert picture.locator('.lw-map-route').count() == 0 and picture.locator('.lw-map-dot.lw-been').count() == 0, '還沒走：沒有路線'
    assert not page.locator('.lw-trail').is_visible() and page.locator('.lw-option').count() == 0 and page.locator('.lw-reaction').count() == 0
    assert page.locator('.lw-finale').count() == 0 and page.locator('.lw-fx').count() == 0
    for event in GAME['events']:  # 反應、願望與結局在選之前都看不到
        for reaction in event['reactions'].values():
            assert not page.get_by_text(reaction['mid'], exact=True).is_visible()
    go = page.get_by_role('button', name='出發', exact=True)
    assert go.is_visible() and go.bounding_box()['height'] >= 48

    # 2. 出發：人在起點，左欄一項；選項卡只有代價
    go.click()
    settled(page)
    assert html.get_attribute('data-phase') == 'play' and not page.locator('.lw-premise').is_visible()
    check_position(page, [])
    assert page.locator('.lw-node-text').inner_text() == GAME['home']['text']
    assert page.evaluate('document.activeElement.className') == 'lw-node-name', '焦點在這一站的名稱上：鍵盤再按 Tab 就是第一張選項卡'
    assert page.locator('.lw-options-title').inner_text() == '接下來去哪？'
    cards = page.locator('.lw-option-list')
    assert page.locator('.lw-option[aria-disabled=true]').count() == 0 and page.locator('.lw-option').count() == 8
    assert page.locator('.lw-option').last.locator('.lw-option-name').inner_text() == '回起點，結束行程'
    market = page.locator('.lw-option[data-go="p1"]')
    assert market.locator('.lw-option-name').inner_text().split('\n')[0].startswith('晨光魚市') and market.locator('.lw-tag').all_inner_texts() == ['吃', '市場']
    assert market.locator('.lw-key').all_inner_texts() == ['車程', '到達', '停留', '打烊'] and EVENTS['p1']['text'] in market.inner_text()
    assert page.locator('.lw-option[data-go="p7"] .lw-val').nth(1).inner_text() == '08:17（等 5 小時 43 分開門）', '要等開門就寫等多久'
    for sign in ('▲', '▼', '+', '−', LABEL, '何以晴', '溫若岑'):
        assert sign not in cards.inner_text(), f'選項卡不寫它會讓誰的數值升降（{sign}）'
    assert page.locator('.lw-option .lw-delta').count() == 0
    page.keyboard.press('Tab')  # 鍵盤：下一個焦點就是第一張選項卡，按 Enter 就選它
    assert page.evaluate('document.activeElement.getAttribute("data-go")') == 'p7'

    # 3. 一站一站走：每一步都和參考實作對照
    choose(page, 'p2')
    state = check_position(page, ['p2'])
    assert state['meters'] == {'c1': -1, 'c2': 2} and shown_meters(page) == {'c1': ('−1', '▼ −1'), 'c2': ('+2', '▲ +2')}
    assert page.locator('.lw-node-when').inner_text() == '車程 27 分・08:27 到（等 1 小時 33 分開門）・停留 45 分・10:45 離開'
    assert page.locator('.lw-reaction-text').all_inner_texts() == [EVENTS['p2']['reactions']['c1']['mid'], EVENTS['p2']['reactions']['c2']['mid']]
    assert page.locator('.lw-option[data-go="p2"]').count() == 0, '去過的站不再出現'
    assert page.locator('.lw-trail').is_visible() and page.locator('.lw-trail svg.lw-map .lw-map-route').count() == 1, '走過的路線連起來'
    assert page.locator('.lw-trail .lw-map-dot.lw-been').count() == 1
    assert page.evaluate('document.activeElement.className') == 'lw-node-name'
    expect(page.locator('.lw-node-name')).to_be_in_viewport()
    choose(page, 'p5')
    state = check_position(page, ['p2', 'p5'])
    assert page.locator('.lw-reaction-text').all_inner_texts() == [EVENTS['p5']['reactions']['c1']['mid'], EVENTS['p5']['reactions']['c2']['high']], \
        '溫若岑到站前是 +2：用有好感的那一句'
    assert shown_meters(page) == {'c1': ('0', '▲ +1'), 'c2': ('+1', '▼ −1')}
    # 不能去的選項：灰掉、寫原因、排在能去的後面；按了沒有作用
    closed = page.locator('.lw-option[data-go="p1"]')
    assert closed.get_attribute('aria-disabled') == 'true' and closed.locator('.lw-option-why').inner_text() == '來不及：11:00 打烊'
    assert float(closed.locator('.lw-option-name').evaluate('(e) => getComputedStyle(e).opacity')) < 1
    assert [card.get_attribute('data-go') for card in page.locator('.lw-option').all()] == ['p3', 'p7', 'p6', 'p4', 'p1', 'home']
    closed.click(force=True)  # 帶著 aria-disabled：強制點下去，確認真的沒有作用
    assert page.locator('.lw-step').count() == 3 and page.locator('.lw-node-name').inner_text() == '海角燈塔'
    choose(page, 'p7')
    check_position(page, ['p2', 'p5', 'p7'])
    for wish in GAME['wishes'].values():
        assert page.locator('.lw-game').get_by_text(wish).count() == 0 and not page.get_by_text(wish).first.is_visible(), '願望在結局之前不出現'

    # 4. 回起點：兩個人都 ≥ 2 → 完美結局；煙火；片尾字幕；最後一句話與願望
    choose(page, 'home')
    final = ref.replay(GAME, PERFECT)
    assert ref.ending(GAME, PERFECT) == 'perfect' and html.get_attribute('data-phase') == 'end' and html.get_attribute('data-mood') is None
    finale = page.locator('.lw-finale')
    assert finale.get_attribute('data-ending') == 'perfect' and page.locator('.lw-ending-kind').inner_text() == '完美結局'
    assert page.locator('.lw-ending-title').inner_text() == GAME['endings']['classes']['perfect']['title']
    assert page.locator('.lw-ending-text').inner_text() == GAME['endings']['classes']['perfect']['text']
    assert page.locator('.lw-ending-when').inner_text() == '車程 17 分・14:47 回到車站・總共用了 6 小時 47 分'
    assert page.evaluate('document.activeElement.className') == 'lw-ending-title'
    assert page.locator('.lw-option').count() == 0 and page.locator('.lw-node').count() == 0
    assert page.locator('.lw-step-among').last.inner_text() == '回到起點・3 選 1' and page.locator('.lw-step').count() == 5
    lines = ref.farewells(GAME, PERFECT)
    assert page.locator('.lw-farewell .lw-name').all_inner_texts() == ['何以晴', '溫若岑']
    assert page.locator('.lw-farewell-value').all_inner_texts() == [f'{LABEL} +2', f'{LABEL} +2']
    assert page.locator('.lw-farewell-text').all_inner_texts() == [item['text'] for item in lines] == [GAME['farewells']['c1']['high'], GAME['farewells']['c2']['high']]
    wishes = page.locator('.lw-wish').all_inner_texts()
    assert [GAME['wishes']['c1'] in wishes[0], GAME['wishes']['c2'] in wishes[1], '沒說出口的願望' in wishes[0]] == [True, True, True], '願望這時才揭曉'
    assert shown_meters(page) == {'c1': ('+2', ''), 'c2': ('+2', '')}
    assert page.locator('.lw-endings-seen').inner_text() == '已看過 1／4 種結局'
    # 特效：煙火（自己畫的 canvas），不擋操作
    effect = page.locator('canvas.lw-fx')
    assert effect.count() == 1 and effect.get_attribute('data-fx') == 'fireworks' and page.locator('.lw-dusk').count() == 0
    assert effect.evaluate('(e) => getComputedStyle(e).pointerEvents') == 'none'
    # 片尾字幕：標題、同行的人、行程表（時間、站名、停留、車程）、總時間、結局；正在由下往上捲
    credits = page.locator('.lw-credits')
    assert credits.locator('.lw-credits-roll').evaluate('(e) => getComputedStyle(e).animationName') == 'lw-roll'
    page.get_by_role('button', name='略過字幕').click()  # 直接看全文
    assert 'lw-still' in credits.get_attribute('class') and page.get_by_role('button', name='略過字幕').count() == 0
    assert credits.locator('.lw-credits-title').inner_text() == GAME['title']
    assert credits.locator('.lw-credits-head').all_inner_texts() == ['同行', '你扮演', '這一局的行程', '總共用了', '結局']
    assert credits.locator('.lw-credits-line').all_inner_texts() == ['何以晴　溫若岑', '你', '6 小時 47 分', GAME['endings']['classes']['perfect']['title']]
    assert credits.locator('th').all_inner_texts() == ['時間', '地點', '停留', '車程']
    rows = [row.locator('td').all_inner_texts() for row in credits.locator('tbody tr').all()]
    assert rows == [['08:00', '車站（出發）', '—', '—'], ['08:27', '山城咖啡', '45 分（先等 1 小時 33 分）', '27 分'], ['11:23', '海角燈塔', '1 小時', '38 分'],
                    ['13:12', '巷口甜點舖', '30 分（先等 48 分）', '49 分'], ['14:47', '車站（回到起點）', '—', '17 分']]
    assert [row[0] for row in rows] == [ref.clock(step['arrive']) for step in final['steps']]

    # 5. 音樂：預設沒有播，也還沒有建立音訊；按了才建立，可以再關掉
    assert audio(page) == {'made': 0, 'closed': 0}
    sound = page.get_by_role('button', name='開啟音樂')
    assert sound.get_attribute('aria-pressed') == 'false'
    sound.click()
    assert audio(page) == {'made': 1, 'closed': 0} and html.get_attribute('data-music') == 'on'
    playing = page.get_by_role('button', name='關閉音樂')
    assert playing.get_attribute('aria-pressed') == 'true'
    playing.click()
    assert audio(page) == {'made': 1, 'closed': 1} and html.get_attribute('data-music') == 'off' and page.get_by_role('button', name='開啟音樂').is_visible()
    page.get_by_role('button', name='開啟音樂').click()

    # 6. 再走一次：回到出發前，特效與音樂都停掉
    page.get_by_role('button', name='再走一次').click()
    assert html.get_attribute('data-phase') == 'start' and page.locator('.lw-fx').count() == 0 and page.locator('.lw-finale').count() == 0
    assert audio(page) == {'made': 2, 'closed': 2} and html.get_attribute('data-music') == 'off', '離開結局畫面，音樂也關掉'
    assert shown_meters(page) == {'c1': ('0', ''), 'c2': ('0', '')} and not page.locator('.lw-trail').is_visible()
    assert page.evaluate('document.activeElement.getAttribute("data-play")') == 'start' and page.locator('.lw-premise').is_visible()

    assert requests == [written(tmp_path).as_uri()], '沒有任何對外連線'
    assert problems == [], '主控台沒有錯誤（樣式與程式都通過檔案自己的 CSP）'
    context.close()


def test_reactions_show_first_and_the_values_move_a_moment_later(chrome, tmp_path):
    """到站時先看到每個人的反應，數值還停在到站前；過一會兒才動起來並標出升降。用假的時鐘確認先後，不靠真的等待。"""
    context = chrome.new_context(viewport={'width': 1200, 'height': 900}, offline=True, locale='zh-TW')
    page = context.new_page()
    problems, _ = watch(page)
    page.clock.install()
    page.goto(written(tmp_path).as_uri())
    page.get_by_role('button', name='出發', exact=True).click()
    page.locator('.lw-option[data-go="p1"]').click()
    stage = page.locator('.lw-game')
    assert stage.get_attribute('data-settled') is None
    assert page.locator('.lw-reaction-text').all_inner_texts() == [EVENTS['p1']['reactions']['c1']['mid'], EVENTS['p1']['reactions']['c2']['mid']], '反應已經出現'
    assert shown_meters(page) == {'c1': ('0', ''), 'c2': ('0', '')} and not page.locator('.lw-reaction .lw-delta').first.is_visible(), '數值還沒動、升降還沒標'
    page.clock.run_for(400)
    assert stage.get_attribute('data-settled') is None
    page.clock.run_for(400)
    assert stage.get_attribute('data-settled') == '1'
    assert shown_meters(page) == {'c1': ('+2', '▲ +2'), 'c2': ('−2', '▼ −2')}
    assert page.locator('.lw-reaction .lw-delta').all_inner_texts() == [f'▲ +2 {LABEL}', f'▼ −2 {LABEL}']
    # 還沒演完就按下一步：前一步的升降直接到位，不會漏掉也不會亂掉
    page.locator('.lw-option[data-go="p3"]').click()
    assert shown_meters(page) == {'c1': ('+2', ''), 'c2': ('−2', '')}, '新的一步：先停在到站前的數值'
    page.locator('.lw-option[data-go="p5"]').click()
    page.clock.run_for(800)
    assert shown_meters(page) == {'c1': ('+4', '▲ +1'), 'c2': ('−5', '▼ −1')} and ref.replay(GAME, ['p1', 'p3', 'p5'])['meters'] == {'c1': 4, 'c2': -5}
    assert problems == []
    context.close()


def test_a_bad_run_ends_in_rain_and_the_endings_seen_add_up_and_are_remembered(chrome, tmp_path):
    target = written(tmp_path)
    context, page, problems, requests = opened(chrome, target)
    html = page.locator('html')

    # 壞結局：何以晴 +3、溫若岑 −4，總和 −1 ≤ 門檻 0 → 下雨、畫面褪色、慢慢暗下
    walk(page, POOR)
    assert ref.ending(GAME, POOR) == 'poor' and page.locator('.lw-finale').get_attribute('data-ending') == 'poor'
    assert page.locator('.lw-ending-kind').inner_text() == '遺憾結局' and page.locator('.lw-ending-title').inner_text() == GAME['endings']['classes']['poor']['title']
    assert page.locator('.lw-farewell-value').all_inner_texts() == [f'{LABEL} +3', f'{LABEL} −4']
    assert page.locator('.lw-farewell-text').all_inner_texts() == [GAME['farewells']['c1']['high'], GAME['farewells']['c2']['low']], '最後一句話依最後的數值'
    assert page.locator('canvas.lw-fx').get_attribute('data-fx') == 'rain' and page.locator('.lw-dusk').count() == 1
    assert html.get_attribute('data-mood') == 'poor'
    expect(page.locator('.lw-dusk')).to_have_class('lw-dusk lw-on')
    assert 'grayscale' in page.locator('main').evaluate('(e) => getComputedStyle(e).filter')
    assert audio(page) == {'made': 0, 'closed': 0} and page.get_by_role('button', name='開啟音樂').is_visible(), '壞結局也一樣：音樂預設不播'
    page.get_by_role('button', name='開啟音樂').click()
    assert audio(page)['made'] == 1
    assert page.locator('.lw-endings-seen').inner_text() == '已看過 1／4 種結局'

    # 再走一次到好結局（總和 3 ≥ 門檻 3，但不是每個人都 ≥ 2）：紙花，不褪色
    page.get_by_role('button', name='再走一次').click()
    assert html.get_attribute('data-mood') is None and page.locator('.lw-dusk').count() == 0 and page.locator('.lw-fx').count() == 0
    walk(page, GREAT)
    assert ref.ending(GAME, GREAT) == 'great' and page.locator('.lw-finale').get_attribute('data-ending') == 'great'
    assert page.locator('.lw-ending-kind').inner_text() == '好結局' and page.locator('canvas.lw-fx').get_attribute('data-fx') == 'confetti'
    assert page.locator('.lw-dusk').count() == 0 and html.get_attribute('data-mood') is None
    assert page.locator('.lw-endings-seen').inner_text() == '已看過 2／4 種結局'

    # 普通的結局：平靜收尾，沒有特效
    page.get_by_role('button', name='再走一次').click()
    walk(page, OK)
    assert ref.ending(GAME, OK) == 'ok' and page.locator('.lw-finale').get_attribute('data-ending') == 'ok' and page.locator('.lw-ending-kind').inner_text() == '普通結局'
    assert page.locator('.lw-fx').count() == 0 and page.locator('.lw-dusk').count() == 0
    assert page.locator('.lw-endings-seen').inner_text() == '已看過 3／4 種結局'

    # 一站都沒去就回起點：一律是遺憾結局（已經看過，計數不變）
    page.get_by_role('button', name='再走一次').click()
    walk(page, ['home'])
    assert page.locator('.lw-finale').get_attribute('data-ending') == 'poor' and page.locator('.lw-step-among').last.inner_text() == '回到起點・8 選 1'
    assert page.locator('.lw-ending-when').inner_text() == '08:00 回到車站・總共用了 0 分'
    assert page.locator('.lw-endings-seen').inner_text() == '已看過 3／4 種結局'

    # 重新開啟：看過的結局還記得
    again = context.new_page()
    again.goto(target.as_uri())
    walk(again, OK)
    assert again.locator('.lw-endings-seen').inner_text() == '已看過 3／4 種結局'
    assert problems == [] and set(requests) == {target.as_uri()}
    context.close()


def test_going_back_on_the_trail_restores_the_time_and_values_and_lets_you_choose_again(chrome, tmp_path):
    context, page, problems, _ = opened(chrome, written(tmp_path))
    walk(page, ['p2', 'p5', 'p7'])
    check_position(page, ['p2', 'p5', 'p7'])
    assert page.locator('.lw-trail-hint').is_visible()

    # 點左欄的第二項（山城咖啡）：回到剛到那一站的時候——時間、數值、反應、選項都是當時的；後面兩站作廢
    page.locator('.lw-step[data-step="1"]').click()
    settled(page)
    state = check_position(page, ['p2'])
    assert state['now'] == 645 and shown_meters(page) == {'c1': ('−1', '▼ −1'), 'c2': ('+2', '▲ +2')}
    assert page.locator('.lw-step').count() == 2 and page.locator('.lw-option[data-go="p5"]').count() == 1, '剛才去過的站又可以選了'
    assert page.locator('.lw-trail .lw-map-dot.lw-been').count() == 1
    assert page.evaluate('document.activeElement.className') == 'lw-node-name'
    page.locator('.lw-step[data-step="1"]').click()  # 點目前這一項：沒有作用
    check_position(page, ['p2'])
    # 改選：這一次去百年書店
    choose(page, 'p6')
    state = check_position(page, ['p2', 'p6'])
    assert state['meters'] == {'c1': -3, 'c2': 4}
    assert page.locator('.lw-reaction-text').all_inner_texts() == [EVENTS['p6']['reactions']['c1']['mid'], EVENTS['p6']['reactions']['c2']['high']]

    # 點起點：回到剛出發的時候，數值都是 0
    page.locator('.lw-step[data-step="0"]').click()
    check_position(page, [])
    assert shown_meters(page) == {'c1': ('0', ''), 'c2': ('0', '')} and page.locator('.lw-option').count() == 8

    # 結局之後也可以點回去：結局畫面、特效與褪色都收掉
    for node in POOR:
        choose(page, node)
    assert page.locator('.lw-finale').count() == 1 and page.locator('.lw-fx').count() == 1 and page.locator('html').get_attribute('data-mood') == 'poor'
    page.locator('.lw-step[data-step="3"]').click()  # 目前這一項（回到起點）：沒有作用
    assert page.locator('.lw-finale').count() == 1
    page.locator('.lw-step[data-step="1"]').click()
    check_position(page, ['p1'])
    assert page.locator('.lw-finale').count() == 0 and page.locator('.lw-fx').count() == 0 and page.locator('.lw-dusk').count() == 0
    assert page.locator('html').get_attribute('data-mood') is None and page.locator('html').get_attribute('data-phase') == 'play'
    assert problems == []
    context.close()


def test_a_tight_schedule_shows_both_reasons_and_leaves_only_the_way_home(chrome, tmp_path):
    tight = ref.sample(clock={'start': 600, 'limit': 240})  # 10:00 出發、四小時
    tight['endings'].update(ref.calibrate(tight))
    context, page, problems, _ = opened(chrome, written(tmp_path, tight))
    assert page.locator('.lw-meta dd').last.inner_text() == '10:00 從車站出發，4 小時內要回到車站（14:00 前）'
    depart(page)
    check_position(page, [], tight)
    reasons = {card.get_attribute('data-go'): card.locator('.lw-option-why').inner_text() for card in page.locator('.lw-option[aria-disabled=true]').all()}
    assert reasons['p1'] == '來不及：11:00 打烊' and reasons['p7'] == '去了就趕不回起點' and set(reasons.values()) == {'來不及：11:00 打烊', '去了就趕不回起點'}
    enabled = [card.get_attribute('data-go') for card in page.locator('.lw-option:not([aria-disabled=true])').all()]
    assert enabled[-1] == 'home' and len(enabled) >= 2 and page.locator('.lw-options-note').count() == 0
    choose(page, enabled[0])
    state = check_position(page, [enabled[0]], tight)
    while len(page.locator('.lw-option:not([aria-disabled=true])').all()) > 1:  # 一直選最近的，直到沒有站可以去
        nearest = page.locator('.lw-option:not([aria-disabled=true])').first.get_attribute('data-go')
        choose(page, nearest)
        state = check_position(page, state['visited'] + [nearest], tight)
    assert page.locator('.lw-options-note').inner_text() == '已經沒有來得及去的地方了，只能回起點。'
    assert page.locator('.lw-option:not([aria-disabled=true])').get_attribute('data-go') == 'home'
    choose(page, 'home')
    picks = state['visited'] + ['home']
    assert page.locator('.lw-finale').get_attribute('data-ending') == ref.ending(tight, picks)
    assert page.locator('.lw-step-among').last.inner_text() == '回到起點・沒有別的選擇'
    assert ref.replay(tight, picks)['now'] <= ref.deadline(tight), '走得到的行程一定趕得回起點'
    assert problems == []
    context.close()


def test_reduced_motion_gets_no_animated_effects_and_the_credits_as_plain_text(chrome, tmp_path):
    context, page, problems, _ = opened(chrome, written(tmp_path), reduced_motion='reduce')
    page.get_by_role('button', name='出發', exact=True).click()
    page.locator('.lw-option[data-go="p2"]').click()
    assert page.locator('.lw-game').get_attribute('data-settled') == '1', '數值直接到位，不等'
    assert shown_meters(page) == {'c1': ('−1', '▼ −1'), 'c2': ('+2', '▲ +2')}
    assert page.locator('.lw-bar-fill').first.evaluate('(e) => getComputedStyle(e).transitionDuration') == '0s'
    assert page.locator('.lw-node').evaluate('(e) => getComputedStyle(e).animationName') == 'none'
    for node in ('p5', 'p7', 'home'):
        page.locator(f'.lw-option[data-go="{node}"]').click()
    assert page.locator('.lw-finale').get_attribute('data-ending') == 'perfect'
    assert page.locator('.lw-fx').count() == 0 and page.locator('.lw-dusk').count() == 0, '沒有動畫特效'
    credits = page.locator('.lw-credits')
    assert 'lw-still' in credits.get_attribute('class') and page.get_by_role('button', name='略過字幕').count() == 0
    assert credits.locator('.lw-credits-roll').evaluate('(e) => getComputedStyle(e).animationName') == 'none'
    for text in (GAME['title'], '何以晴　溫若岑', '山城咖啡', '6 小時 47 分', GAME['endings']['classes']['perfect']['title']):
        expect(credits.get_by_text(text, exact=True).first).to_be_visible()
    box, roll = credits.bounding_box(), credits.locator('.lw-credits-roll').bounding_box()
    assert roll['height'] <= box['height'] + 1 and roll['y'] >= box['y'] - 1, '字幕直接顯示全文，沒有被裁掉'
    assert page.locator('.lw-ending').evaluate('(e) => getComputedStyle(e).animationName') == 'none'
    # 壞結局：不下雨、不慢慢暗下
    page.get_by_role('button', name='再走一次').click()
    for node in ['出發'] + POOR:
        (page.get_by_role('button', name='出發', exact=True) if node == '出發' else page.locator(f'.lw-option[data-go="{node}"]')).click()
    assert page.locator('.lw-finale').get_attribute('data-ending') == 'poor' and page.locator('.lw-fx').count() == 0 and page.locator('.lw-dusk').count() == 0
    assert page.locator('main').evaluate('(e) => getComputedStyle(e).transitionDuration') == '0s'
    assert problems == []
    context.close()


def test_phone_width_never_scrolls_sideways_and_folds_the_trail_into_one_row(chrome, tmp_path):
    context, page, problems, _ = opened(chrome, written(tmp_path), width=375, height=760)

    def fits():
        return page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth')

    assert fits(), '出發前'
    assert page.get_by_role('button', name='出發', exact=True).bounding_box()['height'] >= 48 and page.locator('.lw-start svg.lw-map').is_visible()
    walk(page, ['p2', 'p5'])
    assert fits(), '走了兩站'
    # 左欄收成一列：預設收著，按了才展開（每一步與地圖）
    toggle = page.locator('.lw-trail-toggle')
    assert toggle.is_visible() and toggle.get_attribute('aria-expanded') == 'false' and '走過的路（去過 2 站）' in toggle.inner_text()
    expect(toggle).to_be_in_viewport()
    assert not page.locator('.lw-step').first.is_visible() and not page.locator('.lw-trail svg.lw-map').is_visible()
    assert toggle.bounding_box()['height'] >= 48
    toggle.click()
    assert toggle.get_attribute('aria-expanded') == 'true' and page.locator('.lw-step:visible').count() == 3 and page.locator('.lw-trail svg.lw-map').is_visible()
    assert fits(), '展開左欄'
    assert all(step.bounding_box()['height'] >= 44 for step in page.locator('.lw-step').all()), '每一步都夠大，手指按得到'
    assert all(card.bounding_box()['height'] >= 48 for card in page.locator('.lw-option').all())
    widths = {round(card.bounding_box()['width']) for card in page.locator('.lw-option').all()}
    assert len(widths) == 1 and widths.pop() >= 300, '選項卡一張一列'
    page.locator('.lw-step[data-step="1"]').click()  # 展開之後一樣可以點回去
    check_position(page, ['p2'])
    toggle.click()
    assert not page.locator('.lw-step').first.is_visible()
    for node in ('p5', 'p7', 'home'):
        choose(page, node)
    assert fits(), '結局'
    page.get_by_role('button', name='略過字幕').click()
    assert fits(), '字幕全文（行程表）'
    table = page.locator('.lw-credits .lw-table').bounding_box()
    assert table['x'] >= 0 and table['x'] + table['width'] <= 375
    assert problems == []
    context.close()


def test_printing_gives_the_itinerary_walked_so_far(chrome, tmp_path):
    context, page, problems, _ = opened(chrome, written(tmp_path))
    walk(page, ['p2', 'p5'])
    assert not page.locator('.lw-print').is_visible(), '螢幕上不顯示列印用的行程表'
    page.emulate_media(media='print')
    sheet = page.locator('.lw-print')
    assert sheet.is_visible() and not page.locator('.lw-game').is_visible() and not page.locator('.lw-tools').is_visible()
    assert not page.locator('.lw-static').is_visible() and page.locator('h1').is_visible() and page.locator('.lw-meta').is_visible()
    rows = [row.locator('td').all_inner_texts() for row in sheet.locator('tbody tr').all()]
    assert rows == [['08:00', '車站（出發）', '—', '—'], ['08:27', '山城咖啡', '45 分（先等 1 小時 33 分）', '27 分'], ['11:23', '海角燈塔', '1 小時', '38 分']]
    assert sheet.locator('.lw-print-total').inner_text() == '總共用了 4 小時 23 分' and sheet.locator('.lw-print-ending').count() == 0
    page.emulate_media(media='screen')
    for node in ('p7', 'home'):
        choose(page, node)
    page.emulate_media(media='print')
    assert len(sheet.locator('tbody tr').all()) == 5 and sheet.locator('.lw-print-ending').inner_text() == '結局：' + GAME['endings']['classes']['perfect']['title']
    assert not page.locator('.lw-fx').is_visible()
    assert problems == []
    context.close()


def test_the_text_size_and_theme_tools_work_and_are_shared_with_the_other_players(chrome, tmp_path):
    context, page, problems, _ = opened(chrome, written(tmp_path))
    html = page.locator('html')
    assert page.locator('.lw-tools button').all_inner_texts() == ['A−', 'A＋', '深色'], '沒有場景提示（這種作品沒有那個東西）'
    before = page.locator('body').evaluate('(e) => getComputedStyle(e).fontSize')
    page.get_by_role('button', name='字級放大').click()
    assert html.get_attribute('data-size') == 'l' and page.locator('body').evaluate('(e) => getComputedStyle(e).fontSize') != before
    page.get_by_role('button', name='深色').click()
    assert html.get_attribute('data-theme') == 'dark' and page.get_by_role('button', name='淺色').is_visible()
    assert json.loads(page.evaluate('localStorage.getItem("lw-reader-prefs")')) == {'theme': 'dark', 'size': 'l'}
    page.evaluate('localStorage.setItem("lw-reader-prefs", JSON.stringify({theme: "light", size: "s", stage: "off"}))')  # 閱讀版存的設定
    page.reload()
    assert html.get_attribute('data-theme') == 'light' and html.get_attribute('data-size') == 's'
    page.get_by_role('button', name='字級放大').click()
    assert json.loads(page.evaluate('localStorage.getItem("lw-reader-prefs")')) == {'theme': 'light', 'size': 'm', 'stage': 'off'}, '別的播放器的設定原樣留著'
    assert problems == []
    context.close()


def test_without_scripts_the_page_is_a_readable_list_with_spoilers_folded(chrome, tmp_path):
    context, page, problems, requests = opened(chrome, written(tmp_path), java_script_enabled=False)
    assert page.locator('h1').inner_text() == GAME['title'] and GAME['premise'] in page.locator('.lw-premise').inner_text()
    assert page.locator('.lw-meta dd').first.inner_text() == '何以晴、溫若岑'
    assert page.locator('.lw-need').is_visible() and '需要執行程式' in page.locator('.lw-need').inner_text()
    assert not page.locator('.lw-game').is_visible() and not page.locator('.lw-tools').is_visible()
    assert page.locator('button:visible').count() == 0, '沒有按了沒反應的按鈕'
    assert page.locator('.lw-places .lw-place-name').all_inner_texts() == [event['name'] for event in GAME['events']]
    assert page.locator('.lw-places .lw-place-text').all_inner_texts() == [event['text'] for event in GAME['events']]
    facts = page.locator('.lw-places .lw-place-facts').all_inner_texts()
    assert facts[0].startswith('營業 06:00–11:00・停留 45 分') and '吃' in facts[0] and facts[3].startswith('營業 13:00–16:00・停留 1 小時 30 分')
    assert page.get_by_text(GAME['home']['text']).is_visible()
    fold = page.locator('.lw-spoilers summary')
    assert fold.is_visible()
    hidden = [EVENTS['p1']['reactions']['c1']['mid'], GAME['wishes']['c1'], GAME['farewells']['c2']['high'], GAME['endings']['classes']['perfect']['title']]
    for text in hidden:
        assert not page.get_by_text(text).first.is_visible(), text
    fold.click()  # 原生的收合區塊，不需要程式
    for text in hidden:
        assert page.get_by_text(text).first.is_visible(), text
    assert problems == [] and requests == [written(tmp_path).as_uri()]
    context.close()


def test_it_plays_inside_a_sandboxed_frame_where_storage_is_not_available(chrome, tmp_path):
    """站內直接玩是把檔案放進 <iframe sandbox="allow-scripts">：裡面沒有 localStorage（一碰就丟例外）。播放器照常可以玩，只是不會記得。"""
    written(tmp_path)
    host = tmp_path / 'host.html'
    host.write_text('<!doctype html><meta charset="utf-8"><title>host</title><iframe id="player" sandbox="allow-scripts" src="route.html" width="1100" height="800"></iframe>',
                    encoding='utf-8')
    context, page, problems, requests = opened(chrome, host)
    frame = page.frame_locator('#player')
    assert frame.locator('.lw-tools').is_visible() and frame.locator('html').get_attribute('data-play') == '1'
    blocked = page.frames[1].evaluate('(() => { try { window.localStorage.getItem("x"); return false; } catch (error) { return true; } })()')
    assert blocked, '沙箱裡真的不能用 localStorage（這個測試才有意義）'
    frame.get_by_role('button', name='深色').click()
    assert frame.locator('html').get_attribute('data-theme') == 'dark'
    frame.get_by_role('button', name='出發', exact=True).click()
    for node in POOR:
        frame.locator(f'.lw-option[data-go="{node}"]').click()
        if node != 'home':
            expect(frame.locator('.lw-game')).to_have_attribute('data-settled', '1')
    assert frame.locator('.lw-finale').get_attribute('data-ending') == 'poor' and frame.locator('canvas.lw-fx').get_attribute('data-fx') == 'rain'
    assert frame.locator('.lw-endings-seen').inner_text() == '已看過 1／4 種結局', '這一次開啟之內照樣會數'
    frame.get_by_role('button', name='開啟音樂').click()
    assert frame.get_by_role('button', name='關閉音樂').is_visible()
    frame.get_by_role('button', name='再走一次').click()
    assert frame.get_by_role('button', name='出發', exact=True).is_visible()
    assert problems == [], '存不了也沒有任何錯誤'
    assert set(requests) == {host.as_uri(), (tmp_path / 'route.html').as_uri()}
    context.close()


def test_in_a_real_browser_only_the_same_origin_page_can_frame_the_view_response(chrome, tmp_path):
    """站內直接玩的安全標頭，在真的瀏覽器裡確認（完全離線：每個請求都由測試攔截，照實際的回應內容與標頭直接回給瀏覽器）。

    用實際的 App（測試用的資料庫與記憶體儲存）產生首頁、站內直接看與下載這三種回應，再讓 Chrome 照著它們的標頭載入：
    本站的頁面框得住「站內直接看」那一條回應，裡面的程式會執行；另一個來源的頁面框不住；同一個檔案的下載回應連本站的頁面也框不住。
    被擋下來的 iframe 裡是瀏覽器自己的錯誤頁（那一頁也有標題元素），所以用播放器才有的元素（.lw-head）判斷有沒有載入。
    """
    from fastapi.testclient import TestClient

    from app.ai_providers import FakeProvider
    from app.config import DemoPolicy
    from app.main import create_app
    from app.object_storage import MemoryStorage
    from test_person_source_generation import ready
    from test_route_export import GAME_ID, plant

    app = create_app(data_dir=tmp_path / 'data', policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                     clock=lambda: datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc), generation_provider=FakeProvider(), work_storage=MemoryStorage())
    with TestClient(app) as client:
        ready(client)
        plant(client, ref.sample())
        item = client.post(f'/api/works/{GAME_ID}/exports', json={'request_id': 'ex-1', 'format': 'html'}).json()['export']
        home, viewed, downloaded = client.get('/'), client.get(f'/api/works/{GAME_ID}/exports/1/view'), client.get(item['download_path'])
    assert viewed.status_code == 200 and downloaded.status_code == 200 and viewed.content == downloaded.content

    def kept(response):  # 和框架、執行有關的標頭原樣交給瀏覽器（下載的「附件」標頭不帶：這裡要看的是能不能被框住）
        return {name: response.headers[name] for name in ('content-type', 'content-security-policy', 'x-frame-options', 'x-content-type-options') if name in response.headers}

    assert kept(viewed)['x-frame-options'] == 'SAMEORIGIN' and kept(downloaded)['x-frame-options'] == 'DENY' and kept(home)['x-frame-options'] == 'DENY'
    site, elsewhere = 'http://lw-view.test', 'http://elsewhere.test'
    view_at, file_at = f'/api/works/{GAME_ID}/exports/1/view', f'/api/works/{GAME_ID}/exports/1/download'
    shell = ('<!doctype html><meta charset="utf-8"><title>shell</title>'
             '<iframe id="inline" sandbox="allow-scripts" src="{origin}' + view_at + '" width="1000" height="700"></iframe>'
             '<iframe id="file" sandbox="allow-scripts" src="{origin}' + file_at + '" width="300" height="200"></iframe>')
    context = chrome.new_context(viewport={'width': 1200, 'height': 900}, offline=True, locale='zh-TW')
    served, outside = [], []

    def serve(route):
        url = route.request.url
        served.append(url)
        if url == site + view_at:
            route.fulfill(status=200, headers=kept(viewed), body=viewed.content)
        elif url == site + file_at:
            route.fulfill(status=200, headers=kept(downloaded), body=downloaded.content)
        elif url == site + '/':  # 本站的頁面：帶著首頁實際的安全標頭
            route.fulfill(status=200, headers=kept(home), body=shell.format(origin=''))
        elif url == elsewhere + '/':  # 別的來源的頁面，想把本站的檔案框進去
            route.fulfill(status=200, headers={'content-type': 'text/html; charset=utf-8'}, body=shell.format(origin=site))
        else:
            outside.append(url)
            route.abort()

    context.route('**/*', serve)
    page = context.new_page()
    page.goto(site + '/')
    inside = page.frame_locator('#inline')
    expect(inside.get_by_role('button', name='出發', exact=True)).to_be_visible()
    inside.get_by_role('button', name='出發', exact=True).click()
    inside.locator('.lw-option[data-go="p7"]').click()
    expect(inside.locator('.lw-node-name')).to_have_text('巷口甜點舖')
    assert site + file_at in served and page.frame_locator('#file').locator('.lw-head').count() == 0, '下載的回應不能被框住（X-Frame-Options: DENY）'

    other = context.new_page()
    other.goto(elsewhere + '/')
    other.wait_for_load_state('load')
    assert served.count(site + view_at) == 2, '別的來源那一次也要到了內容，是瀏覽器照標頭擋下來的'
    assert other.frame_locator('#inline').locator('.lw-head').count() == 0, "別的來源框不住（frame-ancestors 'self'）"
    assert other.frame_locator('#file').locator('.lw-head').count() == 0
    assert page.frame_locator('#inline').locator('.lw-head').count() == 1, '對照：本站那一頁裡的還在'
    assert outside == [], '沒有任何其他連線'
    context.close()
