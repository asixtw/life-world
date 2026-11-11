"""角色卡原生 UI（自 8445 移植）：從導覽進入 → 系統角色 → 複製 → 修改並儲存新版 → 讀回新版與舊版 → 重新整理仍在。

需要先啟動隔離的測試服務（LIFEWORLD_TEST_URL）；雲端驗收時把 LIFEWORLD_TEST_URL 指向 lw-core-e2e 的 HTTPS 網址。
"""
import os
import re
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import expect, sync_playwright

from test_journey import BASE, onboarding


@pytest.fixture
def page():
    """本機已安裝的 Google Chrome（與 8445 的 Chrome 驗收相同）；沒有安裝時才用 Playwright 內建的 Chromium。"""
    with sync_playwright() as playwright:
        chrome = Path(os.environ.get('ProgramFiles', '')) / 'Google/Chrome/Application/chrome.exe'
        browser = playwright.chromium.launch(headless=True, **({'executable_path': str(chrome)} if chrome.is_file() else {}))
        context = browser.new_context(viewport={'width': 1440, 'height': 1050}, locale='zh-TW')
        page = context.new_page()
        page.set_default_timeout(15000)
        yield page
        context.close()
        browser.close()


def next_node(page):
    """完成目前節點，展開下一個。"""
    page.locator('#create-step').get_by_role('button', name='下一步').click()


def open_creation(page):
    page.locator('#nav').get_by_role('link', name='作品', exact=True).click()
    expect(page.get_by_role('heading', name='作品', exact=True)).to_be_visible()
    page.get_by_role('link', name='＋ 建立新作品').click()
    expect(page.get_by_role('heading', name='建立新作品', exact=True)).to_be_visible()


def register(page):
    """在升級表單之外以 API 完成正式帳號（角色卡寫入需要正式帳號），之後重新整理沿用新 Cookie。"""
    csrf = page.request.get(BASE + '/api/auth/me').json()['csrf_token']
    username = 'card_ui_' + uuid4().hex[:10]
    claim = page.request.post(BASE + '/api/auth/claim', headers={'X-CSRF-Token': csrf}, data={'username': username, 'password': 'card-ui-password-2026'})
    assert claim.ok, claim.text()
    page.reload()
    return username


def test_character_card_copy_edit_and_versions_in_native_ui(page):
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    onboarding(page)
    register(page)

    page.locator('#nav').get_by_role('link', name='角色', exact=True).click()
    expect(page.get_by_role('heading', name='角色卡', exact=True)).to_be_visible()
    expect(page.get_by_text('還沒有角色卡。')).to_be_visible()
    system_card = page.locator('a.char-card[href^="#character-system/"]').first
    system_name = system_card.locator('strong').inner_text()
    system_card.click()
    expect(page.get_by_role('heading', name=system_name)).to_be_visible()
    original_tagline = page.locator('.char-fields dd').first.inner_text()

    page.get_by_role('button', name='複製成我的角色卡').click()
    expect(page).to_have_url(re.compile(r'#character/[0-9a-f-]+$'))
    work_id = page.url.rsplit('/', 1)[1]
    expect(page.get_by_text('我的角色卡 · 目前 v1')).to_be_visible()

    page.locator('#char-tagline').fill('在我的世界裡，他是一位溫柔的說書人。')
    page.locator('#char-tags').fill('說書人，溫柔')
    page.get_by_role('button', name='儲存新版本').click()
    expect(page.get_by_text('我的角色卡 · 目前 v2')).to_be_visible()
    expect(page.locator('.char-versions li')).to_have_count(2)
    expect(page.locator('.char-fields')).to_contain_text('溫柔的說書人')

    page.locator('.char-versions').get_by_role('link', name='v1').click()
    expect(page.get_by_role('heading', name='v1（舊版本，唯讀）')).to_be_visible()
    expect(page.locator('.char-fields')).to_contain_text(original_tagline[:20])
    expect(page.locator('#character-edit-form')).to_have_count(0)

    page.goto(BASE + '/#character/' + work_id)
    page.reload()
    expect(page.get_by_role('heading', name='v2（目前版本）')).to_be_visible()
    expect(page.locator('.char-fields')).to_contain_text('溫柔的說書人')
    v1 = page.request.get(f'{BASE}/api/characters/{work_id}/versions/1').json()
    v2 = page.request.get(f'{BASE}/api/characters/{work_id}/versions/2').json()
    assert v1['content']['tagline'] == original_tagline and v2['content']['tagline'] == '在我的世界裡，他是一位溫柔的說書人。'
    assert v2['content']['tags'] == ['說書人', '溫柔'] and v2['parent_version'] == 1

    page.locator('#nav').get_by_role('link', name='角色', exact=True).click()
    expect(page.locator('a.char-card[href="#character/' + work_id + '"]')).to_contain_text('v2')
    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto(BASE + '/#character/' + work_id)
    expect(page.get_by_role('heading', name='v2（目前版本）')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert errors == []


def test_persona_consent_and_works_in_native_ui(page):
    """我的人設建立→改版→同意→撤回（入口在「角色」）；作品中心只列生成後的作品，不混入角色卡與人設；人設可讀舊版，角色卡可封存與恢復。"""
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    onboarding(page)
    register(page)
    page.locator('#nav').get_by_role('link', name='角色', exact=True).click()
    page.get_by_role('link', name='我的人設').click()
    page.locator('#persona-display_name').fill('小光')
    page.locator('#persona-public_profile').fill('喜歡慢跑的設計師')
    page.locator('#persona-personality').fill('好奇、慢熱')
    page.locator('#persona-speaking_style').fill('說話簡短')
    page.get_by_role('button', name='建立人設').click()
    expect(page.get_by_text('目前 v1；每次保存都會保留舊版本。')).to_be_visible()
    page.locator('#persona-personality').fill('好奇、慢熱、很有耐心')
    page.get_by_role('button', name='保存新版本').click()
    expect(page.get_by_text('目前 v2；每次保存都會保留舊版本。')).to_be_visible()
    page.get_by_role('button', name='我同意').click()
    expect(page.get_by_role('button', name='撤回同意')).to_be_visible()
    page.reload()
    expect(page.get_by_role('button', name='撤回同意')).to_be_visible()
    page.get_by_role('button', name='撤回同意').click()
    expect(page.get_by_role('button', name='我同意')).to_be_visible()

    page.locator('#nav').get_by_role('link', name='角色', exact=True).click()
    page.locator('a.char-card[href^="#character-system/"]').first.click()
    page.get_by_role('button', name='複製成我的角色卡').click()
    expect(page.get_by_text('我的角色卡 · 目前 v1')).to_be_visible()
    card_url = page.url
    page.locator('#nav').get_by_role('link', name='作品', exact=True).click()
    expect(page.get_by_role('heading', name='作品', exact=True)).to_be_visible()
    expect(page.locator('a.works-item')).to_have_count(0)  # 角色卡與人設不在作品中心
    for tab in ('進行中', '已完成', '失敗／待恢復', '全部作品', '版本歷史'):
        expect(page.locator('.works-tabs').get_by_role('link', name=re.compile('^' + tab))).to_be_visible()
    page.locator('#nav').get_by_role('link', name='角色', exact=True).click()
    page.get_by_role('link', name='我的人設').click()
    page.get_by_role('link', name='查看所有版本').click()
    page.locator('.char-versions').get_by_role('link', name='v1').click()
    expect(page.get_by_role('heading', name='v1（舊版本）')).to_be_visible()
    expect(page.locator('.char-fields')).to_contain_text('好奇、慢熱')
    page.goto(card_url)
    page.get_by_role('button', name='封存').click()
    expect(page.get_by_text('我的角色卡 · 目前 v1 · 已封存')).to_be_visible()
    page.get_by_role('button', name='恢復角色卡').click()
    expect(page.get_by_role('button', name='封存')).to_be_visible()
    assert errors == []


def api(page, method, path, data=None):
    """測試準備資料用（舊功能已沒有新建入口，舊作品以 API 建立後再從畫面驗證閱讀與繼續）。"""
    csrf = page.request.get(BASE + '/api/auth/me').json()['csrf_token']
    response = page.request.fetch(BASE + '/api' + path, method=method, headers={'X-CSRF-Token': csrf}, data=data)
    assert response.ok, response.text()
    return response.json()


def legacy_card(page, index=0):
    system = api(page, 'GET', '/characters/system')['items'][index]
    return api(page, 'POST', '/characters/copy', {'request_id': f'legacy-copy-{index}', 'source_kind': 'system', 'source_id': system['id'], 'source_version': system['version']})


def legacy_story(page):
    card = legacy_card(page)
    draft = api(page, 'POST', '/ai/generate', {'request_id': 'legacy-story', 'module': 'story_opening', 'input': {
        'character_work_id': card['id'], 'character_version': 1, 'genre': '奇幻冒險', 'setting': '霧港的燈塔下，一艘遲到的船正要靠岸。',
        'conflict': '船上的貨物來路不明。', 'player_goal': '查出貨物的來源。'}})
    return api(page, 'POST', '/stories', {'request_id': 'legacy-story-save', 'content': draft['output'], 'generation_id': draft['generation']['id']})


def test_ai_draft_and_t1_generation_in_native_ui(page):
    """建立新作品（唯一入口、七節點）：預設只展開人物；完成後展開場景；素材與演出要求按了才出現；修改前面不會清除後面；
    開始生成建立 generated_work，作品頁逐段生成到完成，顯示作品設定與歷史版本。"""
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    onboarding(page)
    register(page)
    page.goto(BASE + '/#character-ai')
    page.locator('#draft-name').fill('霧港守望者')
    page.get_by_role('button', name='產生草稿').click()
    page.get_by_role('button', name='保存為我的角色卡').click()
    expect(page).to_have_url(re.compile(r'#character/[0-9a-f-]+$'))
    open_creation(page)
    nodes = page.locator('#create-root .create-node')
    expect(nodes).to_have_count(4)  # ①～④；⑤ 素材、⑥ 演出要求預設不顯示
    expect(page.locator('#create-scene')).to_have_count(0)  # ② 尚未展開
    expect(page.locator('#create-root .create-start')).to_be_visible()  # ⑦ 永遠可見
    page.locator('#create-root input[data-bind="card"]').first.check()
    expect(page.locator('#persona-form')).to_be_visible()  # 「包含我」預設勾選，沒有人設時就地建立
    page.locator('#create-root input[data-bind="me"]').uncheck()
    expect(page.locator('.create-module')).to_have_text('自動判斷：單人文字（1 位）')
    page.get_by_role('button', name='下一步：場景').click()
    expect(page.locator('#create-root input[data-bind="card"]')).to_have_count(0)  # 人物收合成摘要
    page.locator('#create-scene').fill('霧港的夜晚，守望者在燈塔下等待一艘遲到的船。')
    page.get_by_role('button', name='▸ 劇情起點（選用）').click()
    page.locator('#create-event').fill('船上的燈號突然熄滅。')
    page.get_by_role('button', name='完成場景').click()
    expect(page.locator('#create-scene')).to_have_count(0)
    page.get_by_role('button', name=re.compile('④ 輸出')).click()
    expect(page.locator('#create-root input[data-bind="output.type"][value="image"]')).to_be_disabled()  # 圖片尚未開放
    page.get_by_role('button', name='＋ 加入演出要求').click()
    expect(nodes).to_have_count(5)
    page.locator('#create-notes').fill('節奏緊湊')
    page.get_by_role('button', name=re.compile('② 場景')).click()  # 返回修改前面的節點，後面的資料不會消失
    expect(page.locator('#create-scene')).to_have_value('霧港的夜晚，守望者在燈塔下等待一艘遲到的船。')
    expect(page.locator('#create-event')).to_have_value('船上的燈號突然熄滅。')
    expect(page.locator('#create-notes')).to_have_value('節奏緊湊')
    page.get_by_role('button', name='開始生成', exact=True).click()
    expect(page).to_have_url(re.compile(r'#run/[0-9a-f-]+$'))
    expect(page.locator('#gen-run-panel')).to_contain_text('已完成', timeout=120000)
    count = page.locator('.gen-segments li.gen-seg').count()
    assert count >= 1
    page.reload()
    expect(page.locator('#gen-run-panel')).to_contain_text('已完成')
    assert page.locator('.gen-segments li.gen-seg').count() == count
    page.locator('summary', has_text='作品設定').click()
    expect(page.locator('.char-fields').last).to_contain_text('船上的燈號突然熄滅。')
    expect(page.locator('.char-fields').last).to_contain_text('節奏緊湊')
    page.locator('summary', has_text='歷史版本').click()
    assert page.locator('details .char-versions li').count() >= 3
    page.get_by_role('link', name='版本與封存').click()  # 生成作品的歷史版本（排隊中→進行中→完成）
    expect(page).to_have_url(re.compile(r'#work/[0-9a-f-]+$'))
    assert page.locator('.char-versions li').count() >= 3
    page.locator('.char-versions li a').last.click()  # 讀取最早的版本
    expect(page.get_by_text('（舊版本）', exact=False)).to_be_visible()
    assert errors == []


def test_story_opening_in_native_ui(page):
    """F04 舊作品：作品中心看得到、打開可讀內容與三個起始行動、可改版；不再有新建故事或互動冒險的入口（舊網址導向 ② 劇情起點）。"""
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    onboarding(page)
    register(page)
    story = legacy_story(page)
    page.locator('#nav').get_by_role('link', name='作品', exact=True).click()
    page.locator('.works-tabs').get_by_role('link', name=re.compile('^已完成')).click()
    page.locator('a.works-item', has_text=story['title']).click()
    expect(page).to_have_url(re.compile(r'#story/[0-9a-f-]+$'))
    expect(page.locator('.story-choices li')).to_have_count(3)
    expect(page.locator('.char-versions li')).to_have_count(1)
    expect(page.get_by_role('button', name='用這個版本開始冒險')).to_have_count(0)
    page.reload()
    expect(page.locator('.story-choices li')).to_have_count(3)
    page.locator('summary', has_text='修改並另存新版本').click()
    page.locator('#story-edit-objective').fill('我改寫的目標')
    page.get_by_role('button', name='保存新版本').click()
    expect(page.locator('.char-versions li')).to_have_count(2)
    expect(page.locator('dd', has_text='我改寫的目標')).to_be_visible()
    story_url = page.url
    page.goto(BASE + '/#story-new')  # 舊的故事開場入口：導向唯一的建立流程；完成 ① 人物後 ② 直接展開「劇情起點」
    expect(page.get_by_role('heading', name='建立新作品', exact=True)).to_be_visible()
    expect(page.locator('#create-event')).to_have_count(0)  # 人物未完成，場景還不能打開
    page.locator('#create-root input[data-bind="card"]').first.check()
    page.locator('#create-root input[data-bind="me"]').uncheck()
    expect(page.locator('#create-event')).to_be_visible()
    page.goto(story_url)
    expect(page.locator('.story-choices li')).to_have_count(3)
    assert errors == []


def test_short_play_session_in_native_ui(page):
    """F05 舊作品：進行中的互動冒險在「進行中」；依原契約繼續（選項回合、自由行動回合各確認保存）→ 重新整理仍在 → 玩家結束。"""
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('dialog', lambda dialog: dialog.accept())
    test_story_opening_in_native_ui(page)
    story_id = page.url.split('#story/')[1].split('?')[0]
    story = api(page, 'GET', '/works/' + story_id)
    session = api(page, 'POST', '/play/sessions', {'request_id': 'legacy-play', 'story_work_id': story_id, 'story_version': story['current_version']})
    page.locator('#nav').get_by_role('link', name='作品', exact=True).click()
    page.locator('.works-tabs').get_by_role('link', name=re.compile('^進行中')).click()
    page.locator(f'a.works-item[href="#play/{session["id"]}"]').click()
    expect(page.locator('#play-form .play-choice')).to_have_count(4)
    page.get_by_role('button', name='送出行動').click()
    expect(page.get_by_text('第 1 回合（尚未保存）')).to_be_visible()
    page.get_by_role('button', name='確認這回合').click()
    expect(page.get_by_text('已保存 1／5 回合', exact=False)).to_be_visible()
    page.locator('#play-form .play-choice').last.click()
    page.locator('#play-form textarea').fill('我走向燈塔，敲門詢問守塔人。')
    page.get_by_role('button', name='送出行動').click()
    page.get_by_role('button', name='確認這回合').click()
    expect(page.get_by_text('已保存 2／5 回合', exact=False)).to_be_visible()
    page.reload()
    expect(page.locator('.play-turns > li')).to_have_count(2)
    expect(page.get_by_text('你的行動：我走向燈塔，敲門詢問守塔人。')).to_be_visible()
    page.get_by_role('button', name='結束冒險').click()
    expect(page.get_by_text('你主動結束了這段冒險。')).to_be_visible()
    expect(page.locator('#play-form')).to_have_count(0)
    page.locator('#nav').get_by_role('link', name='作品', exact=True).click()
    page.locator('.works-tabs').get_by_role('link', name=re.compile('^已完成')).click()
    expect(page.locator(f'a.works-item[href="#play/{session["id"]}"]')).to_have_count(1)
    assert errors == []


def test_person_portrayal_in_native_ui(page):
    """人物演繹是「角色」的工具：從真人資料建立 → 勾選資料與同意 → 產生並保存 → 改摘要存新版 → 建立為角色卡；不再新建互動試演。"""
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    onboarding(page)
    register(page)
    person = api(page, 'POST', '/people', {'name': '陳老師', 'roles': ['大學導師'], 'category': 'learning', 'common_context': '研究所每週討論'})
    api(page, 'POST', '/notes', {'person_id': person['id'], 'kind': 'preparation', 'title': '說話方式', 'content': '語氣溫和，但會直接指出問題。'})
    page.locator('#nav').get_by_role('link', name='角色', exact=True).click()
    page.get_by_role('link', name='從真人資料建立').click()
    page.locator('a.works-item', has_text='陳老師').click()
    expect(page.locator('#nav a.active')).to_contain_text('角色')
    expect(page.locator('#portrayal-form input[name="note"]')).to_have_count(1)
    page.locator('#portrayal-form input[name="consent"]').check()
    page.get_by_role('button', name='產生人物演繹').click()
    page.get_by_role('button', name='保存人物演繹').click()
    expect(page).to_have_url(re.compile(r'#portrayal/[0-9a-f-]+$'))
    expect(page.get_by_text('AI 推演：依你選取的資料推測')).to_be_visible()
    expect(page.get_by_role('button', name='開始試演')).to_have_count(0)  # 不再新建互動試演
    page.locator('#portrayal-summary').fill('我改寫的摘要')
    page.get_by_role('button', name='保存新版本').click()
    expect(page.locator('.char-versions li')).to_have_count(2)
    page.locator('#portrayal-card-form input[name="acknowledged"]').check()
    page.get_by_role('button', name='轉為角色卡').click()
    expect(page).to_have_url(re.compile(r'#character/[0-9a-f-]+$'))
    expect(page.get_by_text('AI 推論的演出設定，不是真人事實', exact=False)).to_be_visible()
    page.goto(BASE + '/#person/' + person['id'])
    expect(page.get_by_role('link', name='從這位人物建立角色卡')).to_be_visible()
    page.locator('#nav').get_by_role('link', name='作品', exact=True).click()
    expect(page.locator('a.works-item')).to_have_count(0)  # 人物演繹工具不是作品
    assert errors == []


def test_theater_performance_in_native_ui(page):
    """人物劇場舊作品：演出在作品中心、可讀、可封存與開啟；舊演出設定只供閱讀並列出它的演出，不能再重演或修改；舊入口導向建立新作品。"""
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    onboarding(page)
    register(page)
    card, system = legacy_card(page), api(page, 'GET', '/characters/system')['items'][1]
    cast = api(page, 'POST', '/theater/casts', {'request_id': 'legacy-cast', 'content': {
        'title': '霧港夜談', 'scenario': {'text': '霧港的夜晚，兩支商隊在碼頭相遇。', 'preset_id': None}, 'mode': 'faithful', 'direction': '',
        'cast': [{'source': 'card', 'id': card['id'], 'version': '1', 'name': card['version']['content']['name'], 'position': 'protagonist'},
                 {'source': 'system', 'id': system['id'], 'version': system['version'], 'name': system['name'], 'position': 'opponent'}]}})
    performed = api(page, 'POST', '/ai/generate', {'request_id': 'legacy-perform', 'module': 'theater_performance', 'input': {'cast_work_id': cast['id'], 'cast_version': 1}})
    api(page, 'POST', '/theater/performances', {'request_id': 'legacy-perf-save', 'generation_id': performed['generation']['id']})
    page.locator('#nav').get_by_role('link', name='作品', exact=True).click()
    expect(page.locator('a.works-item')).to_have_count(1)  # 只有演出；演出設定不是作品
    page.locator('a.works-item').first.click()
    expect(page).to_have_url(re.compile(r'#performance/[0-9a-f-]+$'))
    count = page.locator('.stage-lines li').count()
    assert 6 <= count <= 12
    expect(page.get_by_text('使用設定 v1', exact=False)).to_be_visible()
    page.get_by_role('link', name='版本與封存').click()
    page.get_by_role('button', name='封存').click()
    expect(page.get_by_text('已封存', exact=False).first).to_be_visible()
    page.get_by_role('link', name='開啟').click()
    expect(page.locator('.stage-lines li')).to_have_count(count)
    page.get_by_role('link', name='回到演出設定').click()
    expect(page.locator('#stage-performances li')).to_have_count(1)
    expect(page.get_by_role('link', name='修改設定')).to_have_count(0)
    expect(page.get_by_role('button', name=re.compile('開始演出'))).to_have_count(0)
    page.goto(BASE + '/#stage')  # 舊的人物劇場入口：導向唯一的建立流程
    expect(page.get_by_role('heading', name='建立新作品', exact=True)).to_be_visible()
    assert errors == []


def test_character_references_and_archive_only_in_native_ui(page):
    """角色卡頁：只能封存與恢復，沒有永久刪除按鈕（2026-11-10 定案）；被故事開場使用時列出作品。"""
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('dialog', lambda dialog: dialog.accept())
    onboarding(page)
    register(page)
    page.locator('#nav').get_by_role('link', name='角色', exact=True).click()
    page.locator('a.char-card[href^="#character-system/"]').first.click()
    page.get_by_role('button', name='複製成我的角色卡').click()
    expect(page.get_by_text('目前沒有作品使用這張角色卡。')).to_be_visible()
    expect(page.get_by_role('button', name='刪除')).to_have_count(0)
    page.get_by_role('button', name='封存', exact=True).click()
    expect(page.get_by_role('button', name='恢復角色卡')).to_be_visible()
    page.get_by_role('button', name='恢復角色卡').click()
    expect(page.get_by_role('button', name='封存', exact=True)).to_be_visible()
    page.locator('a.char-card[href^="#character-system/"]').nth(1).click()
    page.get_by_role('button', name='複製成我的角色卡').click()
    expect(page).to_have_url(re.compile(r'#character/[0-9a-f-]+$'))
    card_id = page.url.rsplit('/', 1)[1]
    csrf = page.request.get(BASE + '/api/auth/me').json()['csrf_token']
    headers = {'X-CSRF-Token': csrf}
    draft = page.request.post(BASE + '/api/ai/generate', headers=headers, data={'request_id': 'ui-story', 'module': 'story_opening', 'input': {
        'character_work_id': card_id, 'character_version': 1, 'genre': '懸疑', 'setting': '霧港', 'conflict': '貨物來路不明', 'player_goal': '查出來源'}}).json()
    saved = page.request.post(BASE + '/api/stories', headers=headers, data={'request_id': 'ui-story-save', 'content': draft['output'], 'generation_id': draft['generation']['id']})
    assert saved.ok, saved.text()
    page.reload()
    expect(page.get_by_text('使用這張角色卡的作品（1）')).to_be_visible()
    expect(page.get_by_role('button', name='刪除')).to_have_count(0)
    page.locator('#nav').get_by_role('link', name='角色', exact=True).click()
    expect(page.get_by_text('1 個作品使用', exact=False)).to_be_visible()
    assert errors == []


def test_story_stale_tab_is_rejected_in_native_ui(page):
    """F04：同一帳號開兩個分頁到同一故事 v1；A 改開場並保存；B 改標題保存時被拒並提示重新載入，A 的內容不被覆蓋。"""
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    test_story_opening_in_native_ui(page)  # 已有 v1、v2（v2 改了目標）
    url = page.url.split('?')[0]
    tab_b = page.context.new_page()
    tab_b.on('pageerror', lambda error: errors.append(str(error)))
    tab_b.goto(url)
    for tab in (page, tab_b):
        tab.reload()
        tab.locator('summary', has_text='修改並另存新版本').click()
    page.locator('#story-edit-opening').fill('A 分頁改寫的開場')
    page.get_by_role('button', name='保存新版本').click()
    expect(page.locator('.char-versions li')).to_have_count(3)
    tab_b.locator('#story-edit-title').fill('B 分頁改的標題')
    tab_b.get_by_role('button', name='保存新版本').click()
    expect(tab_b.get_by_role('alert')).to_contain_text('重新載入最新版本')
    expect(tab_b.locator('#story-edit-title')).to_have_value('B 分頁改的標題')  # 修改內容保留在表單
    tab_b.get_by_role('button', name='重新載入最新版本').click()
    expect(tab_b.locator('.char-versions li')).to_have_count(3)
    expect(tab_b.locator('.story-opening').first).to_have_text('A 分頁改寫的開場')
    assert errors == []


def test_work_center_tabs_open_the_work_itself(page):
    """作品中心：完成的 T1 作品在「已完成」；點擊開啟作品本身（不是角色卡）；「版本歷史」列出各版本；「進行中」沒有它。"""
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    test_ai_draft_and_t1_generation_in_native_ui(page)
    page.locator('#nav').get_by_role('link', name='作品', exact=True).click()
    tabs = page.locator('.works-tabs')
    tabs.get_by_role('link', name=re.compile('^已完成')).click()
    expect(page.locator('a.works-item')).to_have_count(1)
    expect(page.locator('a.works-item').first).to_contain_text('已完成')
    tabs.get_by_role('link', name=re.compile('^進行中')).click()
    expect(page.locator('a.works-item')).to_have_count(0)
    tabs.get_by_role('link', name=re.compile('^全部作品')).click()
    page.locator('a.works-item').first.click()
    expect(page).to_have_url(re.compile(r'#run/[0-9a-f-]+$'))
    expect(page.locator('#gen-run-panel')).to_contain_text('已完成')
    page.locator('#nav').get_by_role('link', name='作品', exact=True).click()
    page.locator('.works-tabs').get_by_role('link', name=re.compile('^版本歷史')).click()
    expect(page.locator('.works-history li').first).to_be_visible()
    assert page.locator('.works-history li').count() >= 3
    page.locator('.works-history li a').last.click()  # 最早的版本
    expect(page).to_have_url(re.compile(r'#work/[0-9a-f-]+\?v=1$'))
    expect(page.get_by_text('（舊版本）', exact=False)).to_be_visible()
    assert errors == []


def test_creation_with_me_positions_and_materials(page):
    """① 勾「包含我」就地建立人設並同意 → 2 張角色卡＋我＝3 位（多人文字）→ 角色定位 → ⑤ 按「加入素材」才出現 → 重新整理設定仍在 → 開始生成。"""
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    onboarding(page)
    register(page)
    legacy_card(page, 0)
    legacy_card(page, 1)
    open_creation(page)
    cards = page.locator('#create-root input[data-bind="card"]')
    cards.nth(0).check()
    cards.nth(1).check()
    page.locator('#persona-display_name').fill('阿光')
    page.locator('#persona-public_profile').fill('喜歡慢跑的設計師')
    page.locator('#persona-personality').fill('好奇、慢熱')
    page.locator('#persona-speaking_style').fill('說話簡短')
    page.get_by_role('button', name='建立我的人設').click()
    page.get_by_role('button', name='我同意').click()
    expect(page.get_by_text('我的人設：阿光', exact=False)).to_be_visible()
    expect(page.locator('.create-module')).to_have_text('自動判斷：多人文字（3 位）')
    page.get_by_role('button', name='▸ 角色定位（選用）').click()
    page.locator('#create-root select[data-bind="position"]').first.select_option('protagonist')
    page.get_by_role('button', name='下一步：場景').click()
    page.locator('#create-scene').fill('深夜的港口倉庫，一批藥品不見了。')
    page.get_by_role('button', name='完成場景').click()
    expect(page.locator('#create-material')).to_have_count(0)  # ⑤ 預設不顯示
    page.get_by_role('button', name='＋ 加入素材').click()
    page.locator('#create-material').select_option(index=1)
    page.get_by_role('button', name='加入這個版本').click()
    expect(page.locator('#create-root .char-versions li')).to_have_count(1)
    page.reload()  # 設定只有一份草稿，重新整理後仍在
    expect(page.locator('#create-root .char-versions li')).to_have_count(1)
    expect(page.locator('.create-module')).to_have_text('自動判斷：多人文字（3 位）')
    page.get_by_role('button', name='開始生成', exact=True).click()
    expect(page).to_have_url(re.compile(r'#run/[0-9a-f-]+$'))
    expect(page.locator('#gen-run-panel')).to_contain_text('已完成', timeout=120000)
    page.locator('summary', has_text='作品設定').click()
    settings = page.locator('details .char-fields').first
    expect(settings).to_contain_text('阿光（我）')
    expect(settings).to_contain_text('主角')
    expect(settings).to_contain_text('第 1 版')
    page.locator('#nav').get_by_role('link', name='作品', exact=True).click()
    page.locator('.works-tabs').get_by_role('link', name=re.compile('^已完成')).click()
    expect(page.locator('a.works-item').first).to_contain_text('阿光')
    assert errors == []


def test_creation_draft_is_isolated_per_account_and_people_gate(page):
    """同一瀏覽器同一分頁：A 輸入場景後登出 → B 登入看不到 A 的草稿；B 人物未完成時打不開場景；A 重新登入後仍保有自己的草稿。"""
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    onboarding(page)
    user_a = register(page)
    legacy_card(page, 0)
    open_creation(page)
    page.locator('#create-root input[data-bind="card"]').first.check()
    page.locator('#create-root input[data-bind="me"]').uncheck()
    expect(page.locator('#create-scene')).to_be_visible()  # 人物完成後自動展開場景
    page.locator('#create-scene').fill('A 帳號的私人場景')
    page.locator('#account-button').click()
    page.get_by_role('button', name='登出', exact=True).click()
    expect(page.get_by_role('button', name='登入我的世界')).to_be_visible()
    onboarding(page)  # 同一分頁：B 帳號
    register(page)
    open_creation(page)
    expect(page.get_by_text('A 帳號的私人場景')).to_have_count(0)
    expect(page.locator('#create-scene')).to_have_count(0)
    page.get_by_role('button', name=re.compile('② 場景')).click()  # 人物未完成：不能打開場景
    expect(page.locator('#create-scene')).to_have_count(0)
    expect(page.get_by_role('button', name='＋ 加入素材')).to_have_count(0)
    page.reload()
    expect(page.get_by_text('A 帳號的私人場景')).to_have_count(0)
    page.locator('#account-button').click()
    page.get_by_role('button', name='登出', exact=True).click()
    page.get_by_role('button', name='登入我的世界').click()
    page.locator('#username').fill(user_a)
    page.locator('#password').fill('card-ui-password-2026')
    page.locator('#login-form').get_by_role('button', name='登入我的世界', exact=True).click()
    open_creation(page)
    expect(page.locator('#create-scene')).to_have_value('A 帳號的私人場景')  # 同帳號重新登入仍保有自己的草稿
    assert errors == []


def test_material_history_version_can_be_selected(page):
    """⑤ 素材：選作品後可以指定歷史版本；生成作品的設定顯示所選版本。"""
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    onboarding(page)
    register(page)
    story = legacy_story(page)
    v1 = api(page, 'GET', f"/works/{story['id']}/versions/1")['content']
    api(page, 'POST', f"/stories/{story['id']}/versions", {'request_id': 'material-v2', 'expected_revision': story['revision'], 'base_version': 1,
                                                          'content': {**v1, 'objective': '第二版'}})
    open_creation(page)
    page.locator('#create-root input[data-bind="card"]').first.check()
    page.locator('#create-root input[data-bind="me"]').uncheck()
    page.locator('#create-scene').fill('碼頭')
    page.get_by_role('button', name='完成場景').click()
    page.get_by_role('button', name='＋ 加入素材').click()
    page.locator('#create-material').select_option(story['id'])
    expect(page.locator('#create-material-version option')).to_have_count(2)
    page.locator('#create-material-version').select_option('1')
    page.get_by_role('button', name='加入這個版本').click()
    expect(page.locator('#create-root .char-versions li')).to_contain_text('第 1 版')
    page.get_by_role('button', name='開始生成', exact=True).click()
    expect(page).to_have_url(re.compile(r'#run/[0-9a-f-]+$'))
    page.locator('summary', has_text='作品設定').click()
    expect(page.locator('details .char-fields').first).to_contain_text('（第 1 版）')
    assert errors == []
