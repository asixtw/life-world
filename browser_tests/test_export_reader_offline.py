"""匯出的 HTML 在 Chrome 裡離線開啟（file://，不連任何網站、不需要 8030）。

    .venv\\Scripts\\python.exe -m pytest -q browser_tests/test_export_reader_offline.py

直接用 app.work_export.render_html 產生檔案，以完全離線的瀏覽環境開啟，確認：
1 內容直接寫在頁面裡，看得到標題、人物、每一段 → 2 內嵌的閱讀器程式有執行（工具列出現），沒有被 CSP 擋下 →
3 沒有任何連線、沒有主控台錯誤 → 4 作品文字裡的標籤符號照原樣顯示成文字 → 5 字級、深淺色、場景提示可以切換，重新開啟後記得偏好。
劇本對白與小說敘事兩種呈現各跑一次。這裡的劇情是測試用的示意文字，不是模型生成的作品。

閱讀器 reader-3 另外確認畫面上真的分得出來（看瀏覽器實際套用的樣式，不是只看有沒有 class）：
6 每位人物的名稱各有顏色、段落左邊的線同色 → 7 陣營分組與標籤 → 8 轉折那一幕的標題列和其他幕不同 → 9 敘事、台詞、場景提示三種字不一樣。
"""
import os
from pathlib import Path
import re

import pytest
from playwright.sync_api import expect, sync_playwright

from app.work_export import render_html

# 舊作品的樣子：規劃裡沒有陣營、幕名與預告；顏色跟著陣容，所以仍然有色號
CAST = [{'name': '溫若岑', 'role': '配角', 'color': 1, 'side': None}, {'name': '小光', 'role': None, 'color': 2, 'side': None}]


def spoken(no, speaker, line='', action='', stage='', cast=CAST):
    """一段內容；色號與陣營跟著說話的人。"""
    person = next(member for member in cast if member['name'] == speaker)
    return {'no': no, 'speaker': speaker, 'color': person['color'], 'side': person['side'], 'line': line, 'action': action, 'stage': stage}


CHAPTER = {'no': 1, 'title': '（測試樣張）留一條接縫', 'genre': '', 'premise': '兩人初次見面，要在離場前決定明天暫用的說明方式。',
           'scene': '週六午後，虛構的社區展覽試作桌。', 'form': 'script', 'teaser': '',
           'beats': [{'no': 1, 'title': '', 'kind': None, 'goal': '試讀標籤。', 'segments': [
                        spoken(1, '小光', '這裡寫「復原」，是表示有出處嗎？', '把標籤草稿拿近一點看。', '展場還沒開門'),
                        spoken(2, '溫若岑', '這一塊還是草稿。')]},
                   {'no': 2, 'title': '', 'kind': None, 'goal': '先試文字。', 'segments': [
                        spoken(3, '溫若岑', action='從抽屜拿出一小塊樣品。'),
                        spoken(4, '溫若岑', '先做一小塊。<b>粗體</b> & "引號"')]}]}

# 新作品的樣子：三位人物、兩個陣營、起承轉合四幕（第 3 幕是轉折）、有類型與下集預告
PEOPLE = [{'name': '羅映川', 'role': '主角', 'color': 1, 'side': '羅映川'}, {'name': '沈知衡', 'role': '對手', 'color': 2, 'side': '沈氏集團'},
          {'name': '蘇映舟', 'role': '配角', 'color': 3, 'side': '沈氏集團'}]
DRAMA = {'no': 1, 'title': '（測試樣張）讓渡書', 'genre': '商戰', 'premise': '慶功宴開到一半，一份讓渡書被推到他面前。',
         'scene': '虛構的頂樓會館。', 'form': 'script', 'teaser': '那份讓渡書，是誰換成了白紙？',
         'beats': [{'no': 1, 'title': '慶功宴', 'kind': 'setup', 'goal': '', 'segments': [
                        spoken(1, '沈知衡', '簽了它，今晚大家都好看。', '把讓渡書推過桌面。', '水晶燈下', PEOPLE),
                        spoken(2, '羅映川', '我的筆沒有墨水。', cast=PEOPLE)]},
                   {'no': 2, 'title': '加碼', 'kind': 'rise', 'goal': '', 'segments': [spoken(3, '蘇映舟', '我這裡有筆。', cast=PEOPLE)]},
                   {'no': 3, 'title': '酒杯落地', 'kind': 'turn', 'goal': '', 'segments': [
                        spoken(4, '蘇映舟', action='酒杯從她手裡滑落。', cast=PEOPLE),
                        spoken(5, '羅映川', '看來今晚不只我一個人不想簽。', cast=PEOPLE)]},
                   {'no': 4, 'title': '白紙', 'kind': 'payoff', 'goal': '', 'segments': [spoken(6, '沈知衡', '……這是一張白紙。', cast=PEOPLE)]}]}


def story(form, chapters=1):
    """一章或多章的測試劇情；多章時每一章用同樣的內容、不同的章名。"""
    items = [{**CHAPTER, 'form': form, 'no': number, 'title': CHAPTER['title'] if chapters == 1 else f'第{number}章的標題'} for number in range(1, chapters + 1)]
    return {'format': 'lw-story.v3', 'title': '（測試樣張）留一條接縫', 'cast': CAST, 'chapters': items}


def applied(locator, name):
    """元素實際套用的樣式值（第一個符合的元素）。由瀏覽器的自動化介面讀取，不是頁面自己的程式：不受檔案 CSP 的限制，也不會產生連線。"""
    return locator.first.evaluate('(element, name) => getComputedStyle(element).getPropertyValue(name)', name)


@pytest.fixture
def chrome():
    path = Path(os.environ.get('ProgramFiles', '')) / 'Google/Chrome/Application/chrome.exe'
    if not path.is_file():
        pytest.skip('需要本機的 Chrome')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(path))
        yield browser
        browser.close()


@pytest.mark.parametrize('form', ['script', 'narrative'])
def test_exported_html_opens_offline_and_the_reader_tools_work(chrome, tmp_path, form):
    target = tmp_path / f'work-{form}.html'
    target.write_bytes(render_html(story(form), '2026-11-11'))
    context = chrome.new_context(viewport={'width': 900, 'height': 1200}, offline=True, color_scheme='light', locale='zh-TW')
    page = context.new_page()
    problems, requests = [], []
    page.on('console', lambda message: problems.append(message.text) if message.type in ('error', 'warning') else None)
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.on('request', lambda request: requests.append(request.url))
    page.goto(target.as_uri())

    # 1. 內容直接在頁面裡
    assert page.locator('h1').inner_text() == '（測試樣張）留一條接縫'
    assert page.locator('.lw-chapter').get_attribute('data-form') == form
    assert page.locator('.lw-toc').count() == 0, '只有一章時沒有目錄'
    assert page.locator('.lw-meta').inner_text().count('溫若岑（配角）、小光') == 1
    assert page.locator('.lw-beat').count() == 2 and page.locator('.lw-seg').count() == 4
    assert '這是 AI 依人物設定生成的虛構演出' in page.locator('footer').inner_text()
    # 舊作品（沒有陣營、幕名、預告）：不出現這些新元素，照舊顯示第幾幕與目標
    for selector in ('.lw-side', '.lw-group', '.lw-kind', '.lw-beat-turn', '.lw-teaser', '.lw-genre'):
        assert page.locator(selector).count() == 0, selector
    assert page.locator('.lw-beat-title').all_inner_texts() == ['第 1 幕', '第 2 幕'] and page.locator('.lw-goal').count() == 2
    # 2. 內嵌程式有執行：工具列原本是隱藏的，由程式顯示
    tools = page.locator('.lw-tools')
    assert tools.is_visible()
    # 4. 標籤符號照原樣顯示成文字，沒有變成粗體
    assert page.locator('main b').count() == 0 and '<b>粗體</b> & "引號"' in page.locator('main').inner_text()
    if form == 'narrative':
        assert '「先做一小塊。' in page.locator('main').inner_text(), '小說敘事：台詞加引號'

    # 5. 閱讀偏好
    html = page.locator('html')
    assert html.get_attribute('data-size') == 'm' and html.get_attribute('data-stage') == 'on' and html.get_attribute('data-theme') is None
    page.get_by_role('button', name='深色').click()
    page.get_by_role('button', name='字級放大').click()
    page.get_by_role('button', name='場景提示').click()
    assert html.get_attribute('data-theme') == 'dark' and html.get_attribute('data-size') == 'l' and html.get_attribute('data-stage') == 'off'
    assert not page.locator('.lw-goal').first.is_visible() and not page.locator('.lw-stage').first.is_visible()
    assert page.get_by_role('button', name='淺色').is_visible(), '按鈕顯示的是「按下去會變成什麼」'
    page.reload()
    assert html.get_attribute('data-theme') == 'dark' and html.get_attribute('data-size') == 'l', '重新開啟後記得偏好'
    for _ in range(5):  # 字級有上下限，按超過不會壞
        page.get_by_role('button', name='字級放大').click()
    assert html.get_attribute('data-size') == 'xl'

    # 3. 完全沒有連線，也沒有主控台錯誤
    assert [url for url in requests if url != target.as_uri()] == []
    assert problems == []
    context.close()


@pytest.mark.parametrize('form', ['script', 'narrative'])
def test_people_sides_and_the_turning_point_look_different(chrome, tmp_path, form):
    """reader-3：人物眾多時，從畫面上分得出個人（顏色）、團體（陣營）與關鍵情節（轉折）；三種文字的字不一樣。"""
    target = tmp_path / f'drama-{form}.html'
    target.write_bytes(render_html({'format': 'lw-story.v3', 'title': '（測試樣張）讓渡書', 'cast': PEOPLE, 'chapters': [{**DRAMA, 'form': form}]}, '2026-11-12'))
    context = chrome.new_context(viewport={'width': 900, 'height': 1200}, offline=True, color_scheme='light', locale='zh-TW')
    page = context.new_page()
    problems, requests = [], []
    page.on('console', lambda message: problems.append(message.text) if message.type in ('error', 'warning') else None)
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.on('request', lambda request: requests.append(request.url))
    page.goto(target.as_uri())
    assert page.locator('.lw-tools').is_visible(), '內嵌程式有執行'
    assert page.locator('.lw-beat').count() == 4 and page.locator('.lw-seg').count() == 6

    def person_colours():
        """色號 → 那位人物名稱實際顯示的顏色；順便確認段落左邊的線、開頭的人物清單都是同一個顏色。"""
        colours = {}
        for number in (1, 2, 3):
            colours[number] = applied(page.locator(f'.lw-seg[data-c="{number}"] .lw-who'), 'color')
            assert applied(page.locator(f'.lw-seg[data-c="{number}"]'), 'border-left-color') == colours[number], '段落左邊的線和名稱同色'
            assert applied(page.locator(f'.lw-seg[data-c="{number}"]'), 'border-left-style') == 'solid'
            assert applied(page.locator(f'.lw-meta .lw-name[data-c="{number}"]'), 'color') == colours[number], '開頭的人物清單用同一個顏色'
        return colours

    # 6. 個人：三位人物三個顏色，而且不是一般內文的顏色
    light = person_colours()
    assert len(set(light.values())) == 3, light
    assert applied(page.locator('body'), 'color') not in light.values()

    # 7. 陣營：開頭的人物清單分組；段落裡說話者旁邊有陣營標籤（自己一個人一方就不重複標）
    assert page.locator('.lw-meta .lw-group').all_inner_texts() == ['羅映川（主角）', '沈氏集團：沈知衡（對手）、蘇映舟（配角）']
    assert page.locator('.lw-seg .lw-side').all_inner_texts() == ['沈氏集團'] * 4
    assert page.locator('.lw-seg[data-c="1"] .lw-side').count() == 0 and page.locator('.lw-seg .lw-side').first.is_visible()

    # 8. 關鍵情節：每一幕有幕名與起承轉合；轉折那一幕的標題列和其他幕不同
    assert page.locator('.lw-kind').all_inner_texts() == ['起', '承', '轉', '合']
    assert page.locator('.lw-beat-name').all_inner_texts() == ['慶功宴', '加碼', '酒杯落地', '白紙']
    assert page.locator('.lw-goal').count() == 0, '有幕名時不顯示規劃用的目標'
    usual, turning = page.locator('.lw-beat:not(.lw-beat-turn) .lw-beat-title'), page.locator('.lw-beat-turn .lw-beat-title')
    assert usual.count() == 3 and turning.count() == 1 and '酒杯落地' in turning.inner_text()
    assert applied(usual, 'border-bottom-style') == 'none' and applied(turning, 'border-bottom-style') == 'solid', '轉折的標題列有底線'
    assert applied(turning, 'border-bottom-color') != applied(usual, 'color'), '底線用強調色'
    assert applied(turning.locator('.lw-kind'), 'background-color') != applied(usual.locator('.lw-kind'), 'background-color'), '「轉」的標籤是實心的'
    assert page.locator('.lw-turn-mark').all_inner_texts() == ['轉折'] and page.locator('.lw-beat-turn .lw-turn-mark').is_visible()

    # 9. 字：敘事／動作、台詞、場景提示三種不一樣
    action, line, stage = (page.locator(f'.lw-seg .lw-{name}') for name in ('action', 'line', 'stage'))
    assert applied(action, 'font-family') != applied(line, 'font-family'), '敘事與台詞用不同的字體'
    assert applied(stage, 'font-style') == 'italic' and applied(line, 'font-style') == 'normal' and applied(action, 'font-style') == 'normal'
    assert float(applied(stage, 'font-size')[:-2]) < float(applied(line, 'font-size')[:-2]), '場景提示是小字'
    assert int(applied(line, 'font-weight')) > int(applied(action, 'font-weight')), '台詞的字重比較重'

    # 開場白、類型、下集預告
    assert page.locator('.lw-head .lw-premise .lw-label').inner_text() == '開場' and page.locator('.lw-genre').all_inner_texts() == ['商戰']
    teaser = page.locator('.lw-teaser')
    assert teaser.count() == 1 and '敬請期待下集' in teaser.inner_text() and '那份讓渡書，是誰換成了白紙？' in teaser.inner_text()
    assert page.locator('.lw-chapter > :last-child').get_attribute('class') == 'lw-teaser', '預告在這一章的最後'

    # 深色主題：換成另一組顏色，一樣三個人三個顏色；轉折照樣不同
    page.get_by_role('button', name='深色').click()
    dark = person_colours()
    assert len(set(dark.values())) == 3 and not set(dark.values()) & set(light.values()), (light, dark)
    assert applied(turning, 'border-bottom-style') == 'solid' and applied(turning, 'border-bottom-color') != applied(usual, 'color')

    # 3. 完全沒有連線，也沒有主控台錯誤
    assert [url for url in requests if url != target.as_uri()] == []
    assert problems == []
    context.close()


def test_a_collection_has_a_working_table_of_contents(chrome, tmp_path):
    """多章節作品的合集：有目錄，點章名會跳到那一章；每一章都有章名、前提與場景。"""
    target = tmp_path / 'collection.html'
    target.write_bytes(render_html(story('script', chapters=3), '2026-11-11'))
    context = chrome.new_context(viewport={'width': 900, 'height': 900}, offline=True, color_scheme='light', locale='zh-TW')
    page = context.new_page()
    problems, requests = [], []
    page.on('console', lambda message: problems.append(message.text) if message.type in ('error', 'warning') else None)
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.on('request', lambda request: requests.append(request.url))
    page.goto(target.as_uri())

    toc = page.locator('.lw-toc')
    assert toc.is_visible() and toc.get_by_role('link').count() == 3
    assert toc.get_by_role('link').all_inner_texts() == ['第 1 章　第1章的標題', '第 2 章　第2章的標題', '第 3 章　第3章的標題']
    assert page.locator('.lw-chapter').count() == 3 and page.locator('.lw-seg').count() == 12
    assert '共 3 章' in page.locator('.lw-meta').inner_text()
    assert page.locator('#ch-2 .lw-chapter-title').inner_text() == '第 2 章　第2章的標題'
    assert '場景：週六午後' in page.locator('#ch-2 .lw-scene').inner_text()

    toc.get_by_role('link', name='第 3 章').click()
    # 檔案的 CSP 不允許執行外來的字串程式，所以這裡用不注入程式的方式檢查：網址換到那一章、章名進到畫面裡
    expect(page).to_have_url(re.compile(r'#ch-3$'))
    expect(page.locator('#ch-3 .lw-chapter-title')).to_be_in_viewport()
    assert page.locator('.lw-tools').is_visible()
    assert [url for url in requests if url.split('#')[0] != target.as_uri()] == []
    assert problems == []
    context.close()
