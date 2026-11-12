"""互動版（play-2）的匯出檔在 Chrome 裡離線開啟（file://，不連任何網站、不需要 8030）。

    .venv\\Scripts\\python.exe -m pytest -q browser_tests/test_export_play_offline.py

直接用 app.work_export.render_play_html 產生檔案，以完全離線的瀏覽環境開啟並實際操作，確認：
1 一開始只看到標題、類型、開場白、人物與「你要以誰的視角入局」；選了視角才開始，段落、幕名、抉擇、結尾卡都還沒出現 →
2 自己視角的真心話直接看得到；別人的要按「偷看」，按一次少一次，用完就不能再看 →
3 按「下一段」、空白鍵、→ 一次揭開一段，← 收回；「全部顯示」是整篇原本的故事，抉擇是靜態區塊（另外兩個結局收合）→
4 點線索詞顯示提示、計入「線索 n／N」；同一個人的線索都找到，顯示「你看穿了 ○○ 的底牌」與那則底牌 →
5 揭開到轉折那一幕的最後一段就停下來，出現抉擇；還沒找到線索時真結局不能選（「還少一條線索——回頭找找」）→
6 選壞結局顯示旁白、不會出現原本的結局段落，可以回到轉折點重選；選真結局才繼續到最後，結尾卡標示「真結局」→
7 已看過的結局數會增加，重新開啟後還記得 → 8 結尾卡：看穿的底牌直接顯示、其餘按「看底牌」；選邊顯示那一邊的番外與提問 →
9 「從頭再看」回到選視角之前，偷看的次數與線索重來 → 10 沒有任何連線、沒有主控台錯誤。
另外：手機寬度不會橫向捲動、按鈕夠大；多章節合集每一章各有各的抉擇與線索（選了真結局才到下一章）；
不能執行程式的環境看得到全部段落與靜態的抉擇，底牌、番外、另外兩個結局仍然收合；
沒有互動層的作品照樣有視角與限次偷看、可以讀完；沒有狀態、底牌與陣營的舊作品照舊用「開始」。
這裡的劇情是測試用的示意文字，不是模型生成的作品。
"""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from app.work_export import render_play_html

SECRET_LUO = '（測試樣張）他早就把股份質押出去了。'
SECRET_SU = '（測試樣張）讓渡書是她換成白紙的。'
PEOPLE = [{'name': '羅映川', 'role': '主角', 'color': 1, 'side': '羅映川', 'secret': SECRET_LUO},
          {'name': '沈知衡', 'role': '對手', 'color': 2, 'side': '沈氏集團', 'secret': None},
          {'name': '蘇映舟', 'role': '配角', 'color': 3, 'side': '沈氏集團', 'secret': SECRET_SU}]
SECRETS = [{'who': 1, 'name': '羅映川', 'color': 1, 'secret': SECRET_LUO}, {'who': 3, 'name': '蘇映舟', 'color': 3, 'secret': SECRET_SU}]


def spoken(no, speaker, line='', action='', stage='', state=None):
    """一段內容（lw-play.v2）：色號、陣營與人物號碼跟著說話的人；state 是這一段之後他的情緒、立場、目標（沒有就是 None）。"""
    who = next(index for index, member in enumerate(PEOPLE, start=1) if member['name'] == speaker)
    person = PEOPLE[who - 1]
    if state is not None:
        state = dict(zip(('emotion', 'stance', 'goal'), state))
    return {'no': no, 'speaker': speaker, 'color': person['color'], 'side': person['side'], 'who': who,
            'line': line, 'action': action, 'stage': stage, 'state': state}


# 三位人物、兩個陣營、起承轉合四幕（第 3 幕是轉折）共六段；第 3 段沒有狀態；兩位人物有底牌；有下集預告
BEATS = [{'no': 1, 'title': '慶功宴', 'kind': 'setup', 'goal': '', 'segments': [
              spoken(1, '沈知衡', '簽了它，今晚大家都好看。', '把讓渡書推過桌面。', '水晶燈下', ('志在必得', '逼他簽字', '今晚拿到簽名')),
              spoken(2, '羅映川', '我的筆沒有墨水。', state=('強作鎮定', '', '拖到律師趕來'))]},
         {'no': 2, 'title': '加碼', 'kind': 'rise', 'goal': '', 'segments': [spoken(3, '蘇映舟', '我這裡有筆。')]},
         {'no': 3, 'title': '酒杯落地', 'kind': 'turn', 'goal': '', 'segments': [
              spoken(4, '蘇映舟', action='酒杯從她手裡滑落。', state=('心跳得很快', '不再幫沈知衡', '')),
              spoken(5, '羅映川', '看來今晚不只我一個人不想簽。', state=('鬆了一口氣', '', ''))]},
         {'no': 4, 'title': '白紙', 'kind': 'payoff', 'goal': '', 'segments': [
              spoken(6, '沈知衡', '……這是一張白紙。', state=('錯愕', '', '查出是誰換的'))]}]
TITLE = '（測試樣張）讓渡書'
QUESTION, ASK = '羅映川該怎麼接這一步？', '（測試樣張）如果是你，會把筆放下嗎？'
LABEL_TRUE, LABEL_PLAIN, LABEL_BAD = '把筆放下，看她要做什麼', '先簽了，回頭再翻案', '掀桌走人'
ENDING_PLAIN, ENDING_BAD = '（測試樣張）他簽了名，慶功宴照常散場。', '（測試樣張）他掀了桌子，保全把他請了出去。'
HINT_1, HINT_2, HINT_3 = '（測試樣張）這份文件，最後經過誰的手？', '（測試樣張）她為什麼剛好帶著筆？', '（測試樣張）他的筆真的沒有墨水嗎？'
EPILOGUE_SHEN, EPILOGUE_LUO = '（測試樣張）沈知衡連夜清查經手的人。', '（測試樣張）羅映川把那支筆收進抽屜。'
# 互動層：抉擇在第 3 幕（轉折）之後、由羅映川決定，真結局要先找到線索；兩則線索指向蘇映舟的底牌、一則指向羅映川的
LAYER = {'decision': {'after_beat': 3, 'after': 5, 'actor': {'who': 1, 'name': '羅映川', 'color': 1}, 'question': QUESTION, 'options': [
             {'id': 'a', 'label': LABEL_TRUE, 'kind': 'true', 'needs_clue': True, 'ending': ''},
             {'id': 'b', 'label': LABEL_PLAIN, 'kind': 'plain', 'needs_clue': False, 'ending': ENDING_PLAIN},
             {'id': 'c', 'label': LABEL_BAD, 'kind': 'bad', 'needs_clue': False, 'ending': ENDING_BAD}]},
         'clues': [{'id': 'k1', 'no': 1, 'field': 'action', 'phrase': '讓渡書', 'hint': HINT_1, 'who': 3, 'name': '蘇映舟'},
                   {'id': 'k2', 'no': 3, 'field': 'line', 'phrase': '有筆', 'hint': HINT_2, 'who': 3, 'name': '蘇映舟'},
                   {'id': 'k3', 'no': 2, 'field': 'line', 'phrase': '墨水', 'hint': HINT_3, 'who': 1, 'name': '羅映川'}],
         'epilogues': [{'side': '沈氏集團', 'text': EPILOGUE_SHEN}, {'side': '羅映川', 'text': EPILOGUE_LUO}],
         'question': ASK}
DRAMA = {'no': 1, 'title': TITLE, 'genre': '商戰', 'premise': '慶功宴開到一半，一份讓渡書被推到他面前。',
         'scene': '虛構的頂樓會館。', 'form': 'script', 'teaser': '那份讓渡書，是誰換成了白紙？', 'secrets': SECRETS, 'beats': BEATS, 'interactive': LAYER}


def drama(form='script', interactive=LAYER):
    return {'format': 'lw-play.v2', 'title': TITLE, 'cast': PEOPLE, 'chapters': [{**DRAMA, 'form': form, 'interactive': interactive}]}


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


def opened(chrome, target, width=900, height=1000, **options):
    """用完全離線的瀏覽環境開啟檔案；回傳（環境, 頁面, 主控台問題, 連線紀錄）。"""
    context = chrome.new_context(viewport={'width': width, 'height': height}, offline=True, color_scheme='light', locale='zh-TW', **options)
    page = context.new_page()
    problems, requests = [], []
    page.on('console', lambda message: problems.append(message.text) if message.type in ('error', 'warning') else None)
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.on('request', lambda request: requests.append(request.url))
    page.goto(target.as_uri())
    return context, page, problems, requests


def seen(page, selector='.lw-seg'):
    """畫面上看得到幾個（display:none 的不算）。"""
    return page.locator(f'{selector}:visible').count()


def enter(page, view):
    """選視角入局：view 是第幾位人物（1 起），0 是旁觀。"""
    page.locator(f'.lw-entry button[data-view="{view}"]').click()


def reveal(page, count):
    """按「下一段」直到揭開 count 段。"""
    later = page.get_by_role('button', name='下一段', exact=True)
    while seen(page) < count:
        before = seen(page)
        later.click()
        assert seen(page) == before + 1, '「下一段」每按一次揭開一段'


def xray_items(page, index):
    """第 index 段（0 起）看得到的真心話項目；沒有顯示就是空清單。"""
    return [text.replace('\n', '') for text in page.locator('.lw-seg').nth(index).locator('.lw-xray-item:visible').all_inner_texts()]


def option(page, label):
    return page.locator('.lw-choice-play .lw-option', has_text=label)


@pytest.mark.parametrize('form', ['script', 'narrative'])
def test_play_from_one_persons_view_finds_clues_takes_a_bad_ending_then_the_true_one(chrome, tmp_path, form):
    target = tmp_path / f'play-{form}.html'
    target.write_bytes(render_play_html(drama(form), '2026-11-12'))
    context, page, problems, requests = opened(chrome, target)
    html = page.locator('html')
    progress, status = page.locator('.lw-progress'), page.locator('.lw-status')
    earlier, later = (page.get_by_role('button', name=name, exact=True) for name in ('上一段', '下一段'))
    fold = page.locator('.lw-secrets summary')
    choice, end = page.locator('.lw-choice'), page.locator('.lw-end')

    # 1. 一開始：標題、類型、開場白、人物清單與「你要以誰的視角入局」；選了才開始，段落、幕名、抉擇、結尾卡都還沒出現
    assert page.locator('.lw-tools').is_visible(), '內嵌程式有執行'
    assert page.locator('h1').inner_text() == TITLE and page.locator('.lw-genre').all_inner_texts() == ['商戰']
    assert page.locator('.lw-head .lw-premise').is_visible() and '慶功宴開到一半' in page.locator('.lw-head .lw-premise').inner_text()
    assert page.locator('.lw-meta .lw-group').all_inner_texts() == ['羅映川（主角）', '沈氏集團：沈知衡（對手）、蘇映舟（配角）']
    assert page.locator('.lw-chapter').get_attribute('data-form') == form
    entry = page.locator('.lw-entry')
    assert entry.is_visible() and '你要以誰的視角入局？' in entry.inner_text() and '偷看 3 次' in entry.inner_text(), '三位人物：可以偷看 3 次'
    assert entry.get_by_role('button').all_inner_texts() == ['羅映川', '沈知衡', '蘇映舟', '旁觀']
    assert page.get_by_role('button', name='開始', exact=True).count() == 0 and not earlier.is_visible() and not later.is_visible()
    assert page.get_by_role('button', name='真心話').count() == 0, '真心話沒有總開關了'
    assert page.locator('.lw-seg').count() == 6 and seen(page) == 0 and seen(page, '.lw-beat-title') == 0, '內容都在頁面裡，只是還沒揭開'
    assert progress.inner_text() == '共 6 段' and html.get_attribute('data-mode') == 'step'
    assert not end.is_visible() and not choice.is_visible() and not page.locator('.lw-teaser').is_visible()
    assert not fold.is_visible() and not page.get_by_text(SECRET_LUO).is_visible() and not page.get_by_text(ENDING_BAD).is_visible()
    page.locator('h1').click()
    for key in ('Space', 'ArrowRight', 'ArrowLeft'):  # 還沒選視角：鍵盤不會開始
        page.keyboard.press(key)
        assert seen(page) == 0 and entry.is_visible()

    # 2. 以羅映川的視角入局：第一段是沈知衡的——別人的真心話鎖著，要按「偷看」；羅映川自己的段落直接看得到
    enter(page, 1)
    assert seen(page) == 1 and progress.inner_text() == '第 1／6 段' and not entry.is_visible() and later.is_visible() and earlier.is_visible()
    assert page.locator('.lw-seg:visible .lw-who').inner_text().startswith('沈知衡')
    assert page.locator('.lw-beat-name:visible').all_inner_texts() == ['慶功宴'], '第 1 幕的幕名跟著第一段出現，後面的幕還沒有'
    assert status.inner_text() == '視角：羅映川・偷看剩 3 次・線索 0／3'
    peek = page.locator('.lw-seg').nth(0).locator('.lw-peek')
    assert seen(page, '.lw-xray') == 0 and peek.is_visible() and peek.inner_text() == '偷看他此刻在想什麼（剩 3 次）'
    later.click()
    assert seen(page) == 2 and progress.inner_text() == '第 2／6 段' and page.locator('.lw-beat-name:visible').all_inner_texts() == ['慶功宴']
    assert xray_items(page, 1) == ['情緒強作鎮定', '目標拖到律師趕來'], '自己視角的真心話直接顯示（空的欄位不列）'
    assert not page.locator('.lw-seg').nth(1).locator('.lw-peek').is_visible() and xray_items(page, 0) == []
    assert page.locator('.lw-seg').nth(1).locator('.lw-xray-label').inner_text() == '真心話'
    peek.click()  # 花一次偷看沈知衡這一段
    assert xray_items(page, 0) == ['情緒志在必得', '立場逼他簽字', '目標今晚拿到簽名'] and not peek.is_visible()
    assert status.inner_text() == '視角：羅映川・偷看剩 2 次・線索 0／3'

    # 3. 一次一段：空白鍵、→ 都可以；幕名跟著那一幕的第一段出現；← 收回
    page.locator('h1').click()  # 焦點離開按鈕：空白鍵由頁面接手
    page.keyboard.press('Space')
    assert seen(page) == 3 and progress.inner_text() == '第 3／6 段'
    assert page.locator('.lw-beat-name:visible').all_inner_texts() == ['慶功宴', '加碼'], '進入第 2 幕：幕名一起出現'
    expect(page.locator('.lw-seg').nth(2)).to_be_in_viewport()
    assert page.locator('.lw-seg').nth(2).locator('.lw-xray, .lw-peek').count() == 0, '沒有狀態的段落沒有真心話，也沒有偷看的按鈕'
    page.keyboard.down('ArrowRight')
    page.keyboard.down('ArrowRight')  # 按住不放（第二次是重複鍵）：只翻一段，不會一口氣揭開後面
    page.keyboard.up('ArrowRight')
    assert seen(page) == 4 and progress.inner_text() == '第 4／6 段'
    turning = page.locator('.lw-beat-turn .lw-beat-title')
    assert turning.is_visible() and '酒杯落地' in turning.inner_text() and page.locator('.lw-turn-mark').is_visible()
    assert page.locator('.lw-kind:visible').all_inner_texts() == ['起', '承', '轉']
    assert applied(turning, 'border-bottom-style') == 'solid', '轉折那一幕的標題列有強調的底線'
    assert page.locator('.lw-seg').nth(3).locator('.lw-peek').inner_text() == '偷看他此刻在想什麼（剩 2 次）', '每一顆偷看按鈕都寫著剩下的次數'
    page.keyboard.press('ArrowLeft')
    assert seen(page) == 3 and progress.inner_text() == '第 3／6 段' and not turning.is_visible(), '收回一段：那一幕只有這一段，幕名跟著收回'

    # 「全部顯示」：整篇原本的故事；抉擇是靜態的區塊（題目、三個選項、另外兩個結局收合），和沒有程式時一樣；再按回到逐段，進度還在
    page.get_by_role('button', name='全部顯示').click()
    assert html.get_attribute('data-mode') == 'all' and seen(page) == 6 and seen(page, '.lw-beat-title') == 4
    assert end.is_visible() and page.locator('.lw-teaser').is_visible() and not page.locator('.lw-nav').is_visible() and not entry.is_visible()
    assert choice.is_visible() and page.locator('.lw-choice-question').inner_text() == QUESTION and '羅映川' in page.locator('.lw-choice-actor').inner_text()
    assert page.locator('.lw-choice-list li:visible').all_inner_texts() == [LABEL_TRUE, LABEL_PLAIN, LABEL_BAD]
    assert not page.locator('.lw-choice-play').is_visible() and seen(page, '.lw-option') == 0, '整篇閱讀時沒有可以按的選項'
    assert page.locator('.lw-endings summary').is_visible() and not page.get_by_text(ENDING_BAD).is_visible() and not page.get_by_text(ENDING_PLAIN).is_visible()
    page.locator('.lw-endings summary').click()
    assert page.get_by_text(ENDING_BAD).is_visible() and page.get_by_text(ENDING_PLAIN).is_visible()
    assert page.locator('.lw-endings .lw-ending-kind').all_inner_texts() == ['另一種結局', '壞結局']
    assert not page.locator('.lw-end-kind').is_visible() and not page.locator('.lw-end-seen').is_visible(), '沒有一路選過來：不說「真結局」'
    assert fold.is_visible() and not page.get_by_text(SECRET_LUO).is_visible(), '底牌仍然要按了才看得到'
    assert xray_items(page, 1) == ['情緒強作鎮定', '目標拖到律師趕來'] and xray_items(page, 4) == ['情緒鬆了一口氣'] and xray_items(page, 5) == [], '視角與偷看照舊'
    page.get_by_role('button', name='逐段閱讀').click()
    assert html.get_attribute('data-mode') == 'step' and seen(page) == 3 and progress.inner_text() == '第 3／6 段'
    assert not end.is_visible() and not choice.is_visible() and page.get_by_role('button', name='全部顯示').is_visible()

    # 人物篩選：點名字 → 他的段落照常，其他人的變淡但還在；鍵盤也能操作
    names = page.locator('.lw-meta .lw-name')
    assert [name.get_attribute('role') for name in names.all()] == ['button'] * 3 and names.nth(1).get_attribute('aria-pressed') == 'false'
    names.nth(1).click()  # 沈知衡
    assert names.nth(1).get_attribute('aria-pressed') == 'true'
    expect(page.locator('.lw-seg[data-p="1"]').first).to_have_css('opacity', '0.3')
    expect(page.locator('.lw-seg[data-p="2"]').first).to_have_css('opacity', '1')
    assert seen(page) == 3, '變淡不是隱藏：上下文還看得到'
    names.nth(1).focus()
    page.keyboard.press('Space')  # 焦點在名字上：空白鍵是取消篩選，不是下一段
    assert names.nth(1).get_attribute('aria-pressed') == 'false' and seen(page) == 3
    expect(page.locator('.lw-seg[data-p="1"]').first).to_have_css('opacity', '1')

    # 4. 線索：原文裡的詞可以點（不顯眼的點狀底線）；點了顯示提示並計數；同一個人的線索都找到，直接看穿他的底牌
    first_clue, second_clue = page.locator('.lw-clue[data-clue="k1"]'), page.locator('.lw-clue[data-clue="k2"]')
    assert first_clue.inner_text() == '讓渡書' and first_clue.get_attribute('role') == 'button' and applied(first_clue, 'border-bottom-style') == 'dotted'
    assert seen(page, '.lw-clue-note') == 0 and seen(page, '.lw-clue') == 3
    first_clue.click()
    note = page.locator('.lw-seg').nth(0).locator('.lw-clue-note')
    assert note.is_visible() and HINT_1 in note.inner_text() and '線索' in note.inner_text()
    assert 'lw-found' in first_clue.get_attribute('class') and status.inner_text() == '視角：羅映川・偷看剩 2 次・線索 1／3'
    assert page.locator('.lw-seen').count() == 0 and not page.get_by_text(SECRET_SU).is_visible(), '蘇映舟的線索還差一則'
    first_clue.click()  # 再點一次不會重複計算
    assert status.inner_text().endswith('線索 1／3') and seen(page, '.lw-clue-note') == 1
    second_clue.focus()
    page.keyboard.press('Enter')  # 鍵盤也能點線索；焦點在線索詞上時不會翻頁
    assert seen(page) == 3 and status.inner_text().endswith('線索 2／3')
    known = page.locator('.lw-seg').nth(2).locator('.lw-seen')
    assert known.is_visible() and '你看穿了 蘇映舟 的底牌' in known.inner_text() and SECRET_SU in known.inner_text()
    assert applied(known.locator('.lw-seen-title'), 'color') == applied(page.locator('.lw-seg[data-c="3"] .lw-who'), 'color'), '看穿的底牌用那個人的顏色'
    assert page.locator('.lw-seen').count() == 1 and not page.get_by_text(SECRET_LUO).is_visible()

    # 5. 關鍵抉擇：揭開到轉折那一幕的最後一段就停下來，出現抉擇卡；後面的結局段落與結尾卡都還沒有
    page.locator('h1').click()
    page.keyboard.press('ArrowRight')
    assert seen(page) == 4 and not choice.is_visible()
    page.keyboard.press('ArrowRight')
    assert seen(page) == 5 and progress.inner_text() == '第 5／6 段' and choice.is_visible()
    expect(choice).to_be_in_viewport()
    assert page.locator('.lw-choice-kicker').inner_text() == '關鍵抉擇' and page.locator('.lw-choice-question').inner_text() == QUESTION
    assert page.locator('.lw-option:visible').all_inner_texts() == [LABEL_TRUE, LABEL_PLAIN, LABEL_BAD], '三個選項照資料的順序'
    assert not page.locator('.lw-choice-list').is_visible() and not page.locator('.lw-endings').is_visible(), '逐段時靜態的清單與收合的結局不出現'
    assert later.get_attribute('aria-disabled') == 'true' and status.inner_text().endswith('等你做決定')
    assert page.locator('.lw-choice .lw-endings-seen').inner_text() == '已看過 0／3 個結局'
    assert not page.locator('.lw-choice-lock').is_visible() and option(page, LABEL_TRUE).get_attribute('aria-disabled') == 'false', '已經找到線索：真結局可以選'
    for key in ('ArrowRight', 'Space'):  # 沒有選之前走不下去
        page.keyboard.press(key)
        assert seen(page) == 5 and not page.get_by_text('……這是一張白紙。').is_visible() and not end.is_visible()
    later.click(force=True)  # 「下一段」標成不能按（aria-disabled）：硬按下去也不會往下
    assert seen(page) == 5

    # 6. 選壞結局：顯示那個結局的旁白，不會出現原本的結局段落；可以回到轉折點重選
    option(page, LABEL_BAD).click()
    card = page.locator('.lw-ending-card')
    assert card.is_visible() and card.locator('.lw-ending-kind').inner_text() == '壞結局' and ENDING_BAD in card.inner_text()
    expect(card).to_be_in_viewport()
    assert option(page, LABEL_BAD).get_attribute('aria-pressed') == 'true'
    assert seen(page) == 5 and not page.get_by_text('……這是一張白紙。').is_visible() and not end.is_visible() and not page.locator('.lw-teaser').is_visible()
    assert page.locator('.lw-choice .lw-endings-seen').inner_text() == '已看過 1／3 個結局' and status.inner_text().endswith('這條路到這裡結束')
    page.keyboard.press('ArrowRight')
    assert seen(page) == 5 and later.get_attribute('aria-disabled') == 'true'
    again = choice.get_by_role('button', name='回到轉折點重選')
    assert again.is_visible()
    again.click()
    assert not card.is_visible() and not again.is_visible() and not page.get_by_text(ENDING_BAD).is_visible()
    assert [button.get_attribute('aria-pressed') for button in page.locator('.lw-option').all()] == ['false'] * 3 and status.inner_text().endswith('等你做決定')

    # 選真結局：繼續揭開原本的後續節拍；走到最後，結尾卡標示「真結局」，看過的結局多一個
    option(page, LABEL_TRUE).click()
    assert seen(page) == 6 and progress.inner_text() == '第 6／6 段' and page.get_by_text('……這是一張白紙。').is_visible()
    assert page.locator('.lw-beat-name:visible').all_inner_texts() == ['慶功宴', '加碼', '酒杯落地', '白紙']
    assert later.get_attribute('aria-disabled') == 'true' and end.is_visible()
    assert page.locator('.lw-end-kind').is_visible() and page.locator('.lw-end-kind').inner_text() == '真結局'
    assert page.locator('.lw-end .lw-endings-seen').inner_text() == '已看過 2／3 個結局'
    assert option(page, LABEL_TRUE).get_attribute('aria-pressed') == 'true' and not card.is_visible(), '抉擇卡留在原地，標出選了哪一個'
    assert option(page, LABEL_BAD).get_attribute('aria-disabled') == 'true', '已經往下走：要改選得先回到轉折點'
    option(page, LABEL_BAD).click(force=True)  # 標成不能按的選項：硬按下去也沒有作用
    assert seen(page) == 6 and not card.is_visible()

    # 8. 結尾卡：下集預告；靠線索看穿的底牌直接顯示，其餘按「看底牌」才顯示
    teaser = page.locator('.lw-end .lw-teaser')
    assert teaser.is_visible() and '敬請期待下集' in teaser.inner_text() and '那份讓渡書，是誰換成了白紙？' in teaser.inner_text()
    seen_through = page.locator('.lw-end .lw-known')
    assert seen_through.is_visible() and '你已經看穿的底牌' in seen_through.inner_text() and SECRET_SU in seen_through.inner_text()
    assert seen_through.locator('.lw-secret .lw-name').all_inner_texts() == ['蘇映舟']
    assert fold.is_visible() and fold.inner_text() == '看底牌' and not page.get_by_text(SECRET_LUO).is_visible(), '沒看穿的那一張：按之前不可見'
    fold.click()
    assert page.get_by_text(SECRET_LUO).is_visible() and page.locator('.lw-secrets .lw-secret:visible .lw-name').all_inner_texts() == ['羅映川']
    assert applied(page.locator('.lw-secrets .lw-secret[data-c="1"] .lw-name'), 'color') == applied(page.locator('.lw-seg[data-c="1"] .lw-who'), 'color')

    # 你站哪一邊：選了顯示那一邊的番外與給讀者的提問；可以改
    pick = page.locator('.lw-pick')
    assert pick.is_visible() and '你站哪一邊？' in pick.inner_text() and pick.get_by_role('button').all_inner_texts() == ['羅映川', '沈氏集團']
    assert not page.locator('.lw-pick-result').is_visible() and not page.locator('.lw-ask').is_visible() and not page.locator('.lw-epilogues').is_visible()
    assert not page.get_by_text(EPILOGUE_SHEN).is_visible() and not page.get_by_text(EPILOGUE_LUO).is_visible()
    pick.get_by_role('button', name='沈氏集團').click()
    assert page.locator('.lw-pick-result').inner_text() == '你選了：沈氏集團' and pick.get_by_role('button', name='沈氏集團').get_attribute('aria-pressed') == 'true'
    more = page.locator('.lw-pick-more')
    assert more.is_visible() and '番外' in more.inner_text() and EPILOGUE_SHEN in more.inner_text() and EPILOGUE_LUO not in more.inner_text()
    assert page.locator('.lw-ask').is_visible() and ASK in page.locator('.lw-ask').inner_text()
    pick.get_by_role('button', name='羅映川').click()
    assert page.locator('.lw-pick-result').inner_text() == '你選了：羅映川' and EPILOGUE_LUO in more.inner_text() and EPILOGUE_SHEN not in more.inner_text()
    assert [button.get_attribute('aria-pressed') for button in pick.get_by_role('button').all()] == ['true', 'false']

    # 「上一段」可以退回抉擇之前：先回到轉折點（可以改選），再退一段抉擇就收起來；再走到那裡要重新選
    page.keyboard.press('ArrowLeft')
    assert seen(page) == 5 and not end.is_visible() and not page.get_by_text(SECRET_LUO).is_visible() and choice.is_visible()
    assert option(page, LABEL_TRUE).get_attribute('aria-pressed') == 'true' and option(page, LABEL_PLAIN).get_attribute('aria-disabled') == 'false'
    option(page, LABEL_PLAIN).click()  # 站在轉折點上：直接改選另一個
    assert card.is_visible() and card.locator('.lw-ending-kind').inner_text() == '另一種結局' and ENDING_PLAIN in card.inner_text() and seen(page) == 5
    assert page.locator('.lw-choice .lw-endings-seen').inner_text() == '已看過 3／3 個結局'
    earlier.click()
    assert seen(page) == 4 and progress.inner_text() == '第 4／6 段' and not choice.is_visible() and not card.is_visible()
    later.click()
    assert seen(page) == 5 and choice.is_visible() and not card.is_visible()
    assert [button.get_attribute('aria-pressed') for button in page.locator('.lw-option').all()] == ['false'] * 3

    # 9. 從頭再看：回到選視角之前；偷看的次數與線索重來，看過的結局留著
    option(page, LABEL_TRUE).click()
    assert seen(page) == 6 and end.is_visible() and fold.is_visible() and not page.get_by_text(SECRET_LUO).is_visible(), '再讀到最後：底牌要重新按才看得到'
    page.get_by_role('button', name='從頭再看').click()
    assert seen(page) == 0 and entry.is_visible() and progress.inner_text() == '共 6 段' and not end.is_visible() and not choice.is_visible()
    assert page.locator('.lw-seen').count() == 0 and page.locator('.lw-clue.lw-found').count() == 0
    enter(page, 0)  # 這次旁觀
    assert seen(page) == 1 and status.inner_text() == '視角：旁觀・偷看剩 3 次・線索 0／3' and seen(page, '.lw-xray') == 0 and seen(page, '.lw-clue-note') == 0
    reveal(page, 5)
    assert page.locator('.lw-choice .lw-endings-seen').inner_text() == '已看過 3／3 個結局'
    assert page.locator('.lw-choice-lock').is_visible(), '線索重來了：真結局又要先找到線索'

    # 重新開啟：字級、深淺色、場景提示、選的陣營與看過的結局都記得；逐段從頭開始
    page.get_by_role('button', name='深色').click()
    page.get_by_role('button', name='字級放大').click()
    page.get_by_role('button', name='場景提示').click()
    assert html.get_attribute('data-theme') == 'dark' and html.get_attribute('data-size') == 'l' and html.get_attribute('data-stage') == 'off'
    page.reload()
    assert html.get_attribute('data-theme') == 'dark' and html.get_attribute('data-size') == 'l' and html.get_attribute('data-stage') == 'off'
    assert seen(page) == 0 and progress.inner_text() == '共 6 段' and entry.is_visible()
    enter(page, 2)
    reveal(page, 5)
    assert page.locator('.lw-choice .lw-endings-seen').inner_text() == '已看過 3／3 個結局', '看過的結局記在這個瀏覽器'
    page.get_by_role('button', name='全部顯示').click()
    assert seen(page) == 6 and page.locator('.lw-pick-result').inner_text() == '你選了：羅映川' and EPILOGUE_LUO in page.locator('.lw-pick-more').inner_text()
    assert not page.get_by_text(SECRET_LUO).is_visible(), '重新開啟後底牌又是收合的'
    if form == 'script':
        assert not page.locator('.lw-stage').first.is_visible(), '場景提示關掉了'

    # 10. 完全沒有連線，也沒有主控台錯誤
    assert [url for url in requests if url != target.as_uri()] == []
    assert problems == []
    context.close()


def test_a_bystander_runs_out_of_peeks_and_cannot_take_the_true_ending_before_finding_a_clue(chrome, tmp_path):
    target = tmp_path / 'play-bystander.html'
    target.write_bytes(render_play_html(drama(), '2026-11-12'))
    context, page, problems, requests = opened(chrome, target)
    status, later = page.locator('.lw-status'), page.get_by_role('button', name='下一段', exact=True)
    segments, end = page.locator('.lw-seg'), page.locator('.lw-end')

    # 旁觀：每個人的真心話都鎖著；偷看三次就用完，之後的按鈕按了也沒有用
    enter(page, 0)
    reveal(page, 2)
    assert status.inner_text() == '視角：旁觀・偷看剩 3 次・線索 0／3' and seen(page, '.lw-xray') == 0 and seen(page, '.lw-peek') == 2
    segments.nth(0).locator('.lw-peek').click()
    segments.nth(1).locator('.lw-peek').click()
    assert seen(page, '.lw-xray') == 2 and xray_items(page, 1) == ['情緒強作鎮定', '目標拖到律師趕來'] and status.inner_text().startswith('視角：旁觀・偷看剩 1 次')
    reveal(page, 4)
    assert segments.nth(3).locator('.lw-peek').inner_text() == '偷看他此刻在想什麼（剩 1 次）'
    segments.nth(3).locator('.lw-peek').click()
    assert seen(page, '.lw-xray') == 3 and status.inner_text().startswith('視角：旁觀・偷看剩 0 次')
    reveal(page, 5)
    expect(page.locator('.lw-choice')).to_be_focused()  # 走到轉折點：焦點在抉擇卡上（不在選項上，連按空白鍵不會誤選），再按 Tab 就是第一個選項
    page.keyboard.press('Tab')
    expect(option(page, LABEL_TRUE)).to_be_focused()
    page.keyboard.press('Enter')  # 還鎖著的選項：用鍵盤按也沒有作用
    assert seen(page) == 5 and option(page, LABEL_TRUE).get_attribute('aria-pressed') == 'false'
    spent = segments.nth(4).locator('.lw-peek')
    assert spent.is_visible() and spent.inner_text() == '偷看的次數用完了' and spent.get_attribute('aria-disabled') == 'true'
    spent.click(force=True)  # 標成不能按：硬按下去也不會顯示
    assert seen(page, '.lw-xray') == 3 and xray_items(page, 4) == [], '用完就不能再看'

    # 還沒找到任何線索：真結局不能選，寫著「還少一條線索——回頭找找」；另外兩個可以選
    choice, lock = page.locator('.lw-choice'), page.locator('.lw-choice-lock')
    assert choice.is_visible() and lock.is_visible() and lock.inner_text() == '還少一條線索——回頭找找'
    assert [button.get_attribute('aria-disabled') for button in page.locator('.lw-option').all()] == ['true', 'false', 'false']
    option(page, LABEL_TRUE).click(force=True)
    assert seen(page) == 5 and option(page, LABEL_TRUE).get_attribute('aria-pressed') == 'false' and not end.is_visible(), '按了沒有作用'
    assert later.get_attribute('aria-disabled') == 'true'

    # 回頭找到一條線索（羅映川那一則是他唯一的線索：同時看穿他的底牌）→ 真結局解鎖
    page.locator('.lw-clue[data-clue="k3"]').click()
    assert not lock.is_visible() and option(page, LABEL_TRUE).get_attribute('aria-disabled') == 'false'
    known = segments.nth(1).locator('.lw-seen')
    assert '你看穿了 羅映川 的底牌' in known.inner_text() and SECRET_LUO in known.inner_text() and status.inner_text().endswith('線索 1／3・等你做決定')
    option(page, LABEL_TRUE).click()
    assert seen(page) == 6 and end.is_visible() and page.locator('.lw-end-kind').inner_text() == '真結局'
    assert page.locator('.lw-end .lw-endings-seen').inner_text() == '已看過 1／3 個結局', '只走了真結局'
    assert page.locator('.lw-end .lw-known .lw-name').all_inner_texts() == ['羅映川']
    page.locator('.lw-secrets summary').click()
    assert page.locator('.lw-secrets .lw-secret:visible .lw-name').all_inner_texts() == ['蘇映舟'], '看穿的那一張不重複列在「看底牌」裡'

    # 結尾卡上也可以回到轉折點，去看別的結局；偷看的次數與線索不重來
    page.locator('.lw-end').get_by_role('button', name='回到轉折點重選').click()
    assert seen(page) == 5 and not end.is_visible() and choice.is_visible() and not page.locator('.lw-ending-card').is_visible()
    expect(choice).to_be_in_viewport()
    assert status.inner_text() == '視角：旁觀・偷看剩 0 次・線索 1／3・等你做決定' and not lock.is_visible()
    option(page, LABEL_PLAIN).click()
    assert ENDING_PLAIN in page.locator('.lw-ending-card').inner_text() and page.locator('.lw-choice .lw-endings-seen').inner_text() == '已看過 2／3 個結局'

    # 列印：不管讀到哪裡、選了什麼，印出來的是整篇原本的故事；抉擇是靜態的區塊，按鈕、偷看、選視角都不印
    page.emulate_media(media='print')
    assert seen(page) == 6 and seen(page, '.lw-beat-title') == 4 and end.is_visible() and page.locator('.lw-teaser').is_visible()
    assert page.locator('.lw-choice-list li:visible').count() == 3 and page.locator('.lw-endings summary').is_visible()
    for selector in ('.lw-choice-play', '.lw-option', '.lw-ending-card', '.lw-peek', '.lw-nav', '.lw-entry', '.lw-pick', '.lw-again', '.lw-end-kind', '.lw-end-seen', '.lw-tools'):
        assert seen(page, selector) == 0, selector
    page.emulate_media(media='screen')
    assert seen(page) == 5 and page.locator('.lw-ending-card').is_visible() and not end.is_visible()
    assert [url for url in requests if url != target.as_uri()] == []
    assert problems == []
    context.close()


def test_play_fits_a_phone_screen(chrome, tmp_path):
    """手機寬度：不會橫向捲動；選視角、逐段、抉擇、選邊的按鈕夠大；新的一段、抉擇卡與結尾卡會捲進畫面。"""
    target = tmp_path / 'play-phone.html'
    target.write_bytes(render_play_html(drama('narrative'), '2026-11-12'))
    context, page, problems, requests = opened(chrome, target, width=375, height=740)
    html = page.locator('html')

    def fits():
        return html.evaluate('element => element.scrollWidth <= element.clientWidth')

    assert fits()
    for button in page.locator('.lw-entry button').all():
        assert button.bounding_box()['height'] >= 44
    enter(page, 3)  # 蘇映舟的視角
    later, earlier = page.get_by_role('button', name='下一段', exact=True), page.get_by_role('button', name='上一段', exact=True)
    page.locator('.lw-seg').nth(0).locator('.lw-peek').click()
    page.locator('.lw-clue[data-clue="k1"]').click()
    assert fits() and page.locator('.lw-status').inner_text() == '視角：蘇映舟・偷看剩 2 次・線索 1／3'
    for number in range(2, 6):
        later.click()
        expect(page.locator('.lw-seg').nth(number - 1)).to_be_in_viewport()
        expect(later).to_be_in_viewport()
        assert fits(), number
    assert later.bounding_box()['height'] >= 44 and earlier.bounding_box()['height'] >= 44
    assert page.locator('.lw-progress').inner_text() == '第 5／6 段'
    expect(page.locator('.lw-choice')).to_be_in_viewport()  # 停下來：抉擇卡跟著最後一段進到畫面，不用猜下面還有東西
    for button in page.locator('.lw-option').all():
        assert button.bounding_box()['height'] >= 44
    option(page, LABEL_BAD).click()
    expect(page.locator('.lw-ending-card')).to_be_in_viewport()
    assert fits() and page.locator('.lw-choice').get_by_role('button', name='回到轉折點重選').bounding_box()['height'] >= 44
    page.locator('.lw-choice').get_by_role('button', name='回到轉折點重選').click()
    option(page, LABEL_TRUE).click()
    assert page.locator('.lw-progress').inner_text() == '第 6／6 段' and fits()
    expect(page.locator('.lw-seg').nth(5)).to_be_in_viewport()
    expect(page.locator('.lw-end .lw-end-kind')).to_be_in_viewport()  # 讀完：結尾卡跟著最後一段進到畫面
    page.locator('.lw-secrets summary').click()
    page.locator('.lw-pick button').first.click()
    for button in page.locator('.lw-pick button').all() + [page.get_by_role('button', name='從頭再看'), page.locator('.lw-end').get_by_role('button', name='回到轉折點重選')]:
        assert button.bounding_box()['height'] >= 44
    assert fits()
    page.get_by_role('button', name='全部顯示').click()
    assert fits() and page.locator('.lw-seg:visible').count() == 6
    assert [url for url in requests if url != target.as_uri()] == []
    assert problems == []
    context.close()


def collection(layers=(None, None)):
    """兩章的合集：第 1 章四段（兩幕）、第 2 章兩段（一幕）；每一章各有底牌；只有最後一章的預告。layers 是兩章各自的互動層。"""
    first = {**DRAMA, 'title': '第一章的標題', 'teaser': '（不該出現）第一章的預告', 'secrets': SECRETS[:1], 'interactive': layers[0],
             'beats': [BEATS[0], {**BEATS[2], 'no': 2}]}
    second = {**DRAMA, 'no': 2, 'title': '第二章的標題', 'premise': '隔天早上，會館的門還沒開。', 'secrets': SECRETS[1:], 'interactive': layers[1],
              'beats': [{**BEATS[3], 'no': 1, 'segments': [spoken(1, '沈知衡', '……這是一張白紙。', state=('錯愕', '', '')),
                                                           spoken(2, '蘇映舟', '是我換的。')]}]}
    cast = [{**member, 'secret': None} for member in PEOPLE]  # 多章節：底牌放在各章
    return {'format': 'lw-play.v2', 'title': '（測試樣張）合集', 'cast': cast, 'chapters': [first, second]}


def test_a_play_collection_keeps_going_across_chapters(chrome, tmp_path):
    """沒有互動層的合集：選了視角之後跨章連續揭開，章名跟著那一章的第一段出現；底牌依章分開；沒有抉擇。"""
    target = tmp_path / 'play-collection.html'
    target.write_bytes(render_play_html(collection(), '2026-11-12'))
    context, page, problems, requests = opened(chrome, target)
    progress, later = page.locator('.lw-progress'), page.get_by_role('button', name='下一段', exact=True)
    titles = page.locator('.lw-chapter-title:visible')

    assert page.locator('.lw-toc').is_visible() and page.locator('.lw-toc a').count() == 2
    assert progress.inner_text() == '共 6 段' and titles.count() == 0 and seen(page) == 0 and page.locator('.lw-choice').count() == 0
    enter(page, 1)
    assert titles.all_inner_texts() == ['第 1 章　第一章的標題'] and progress.inner_text() == '第 1／6 段', '章名跟著那一章的第一段出現'
    assert page.locator('.lw-status').inner_text() == '視角：羅映川・偷看剩 3 次', '沒有線索就不顯示線索計數'
    reveal(page, 4)
    assert titles.count() == 1 and not page.locator('.lw-end').is_visible(), '第 1 章讀完還不是結尾'
    later.click()
    assert seen(page) == 5 and titles.all_inner_texts() == ['第 1 章　第一章的標題', '第 2 章　第二章的標題'] and progress.inner_text() == '第 5／6 段'
    assert page.locator('#ch-2 .lw-premise').is_visible() and not page.locator('.lw-end').is_visible()
    later.click()
    assert seen(page) == 6 and page.locator('.lw-end').is_visible() and page.locator('.lw-end').count() == 1
    assert page.locator('.lw-teaser').count() == 1 and '（不該出現）' not in page.locator('body').inner_text()
    assert page.locator('.lw-end-kind').count() == 0 and page.locator('.lw-end-seen').count() == 0, '沒有抉擇：不談真結局'
    page.locator('.lw-secrets summary').click()
    assert page.locator('.lw-secrets-chapter').all_inner_texts() == ['第 1 章　第一章的標題', '第 2 章　第二章的標題'], '底牌依章分開，標明第幾章'
    assert page.get_by_text(SECRET_LUO).is_visible() and page.get_by_text(SECRET_SU).is_visible()

    # 目錄：逐段模式下點後面的章，會把到那一章第一段為止的內容都揭開，再跳過去；還沒選視角就當成旁觀
    page.get_by_role('button', name='從頭再看').click()
    assert seen(page) == 0 and page.locator('.lw-entry').is_visible()
    page.locator('.lw-toc a').nth(1).click()
    assert seen(page) == 5 and progress.inner_text() == '第 5／6 段' and page.locator('.lw-status').inner_text().startswith('視角：旁觀')
    expect(page.locator('#ch-2 .lw-chapter-title')).to_be_in_viewport()
    assert [url for url in requests if url.split('#')[0] != target.as_uri()] == []
    assert problems == []
    context.close()


def test_a_collection_stops_at_the_decision_of_a_chapter_and_only_the_true_ending_leads_to_the_next(chrome, tmp_path):
    """有互動層的合集：第 1 章自己的抉擇排在它指定的那一幕之後，選了真結局才繼續到第 2 章；線索與看穿的底牌一章一章算。"""
    first_layer = {**LAYER, 'decision': {**LAYER['decision'], 'after_beat': 2, 'after': 5},
                   'clues': [{'id': 'k1', 'no': 2, 'field': 'line', 'phrase': '墨水', 'hint': HINT_3, 'who': 1, 'name': '羅映川'}], 'question': '（不該出現）第一章的提問'}
    second_layer = {'decision': None, 'clues': [{'id': 'k1', 'no': 2, 'field': 'line', 'phrase': '換的', 'hint': HINT_1, 'who': 3, 'name': '蘇映舟'}],
                    'epilogues': [{'side': '沈氏集團', 'text': '（測試樣張）第二章的番外。'}], 'question': ASK}
    target = tmp_path / 'play-collection-choice.html'
    target.write_bytes(render_play_html(collection((first_layer, second_layer)), '2026-11-12'))
    context, page, problems, requests = opened(chrome, target)
    progress, status, choice = page.locator('.lw-progress'), page.locator('.lw-status'), page.locator('.lw-choice')
    titles = page.locator('.lw-chapter-title:visible')

    # 目錄不能跳過還沒做的抉擇：揭開到第 1 章的轉折點、停在那裡
    page.locator('.lw-toc a').nth(1).click()
    assert seen(page) == 4 and progress.inner_text() == '第 4／6 段' and titles.all_inner_texts() == ['第 1 章　第一章的標題']
    assert choice.is_visible() and status.inner_text() == '視角：旁觀・偷看剩 3 次・線索 0／2・等你做決定'
    expect(choice).to_be_in_viewport()
    assert page.locator('.lw-choice-lock').is_visible()
    page.locator('#ch-1 .lw-clue').click()
    assert '你看穿了 羅映川 的底牌' in page.locator('#ch-1 .lw-seen').inner_text() and not page.locator('.lw-choice-lock').is_visible()
    option(page, LABEL_BAD).click()
    assert ENDING_BAD in page.locator('.lw-ending-card').inner_text() and seen(page) == 4 and titles.count() == 1, '壞結局：故事停在第 1 章'
    page.locator('.lw-toc a').nth(1).click()
    assert seen(page) == 4 and titles.count() == 1, '停在另一個結局時，目錄一樣跳不過去'
    choice.get_by_role('button', name='回到轉折點重選').click()
    option(page, LABEL_TRUE).click()
    assert seen(page) == 5 and titles.all_inner_texts() == ['第 1 章　第一章的標題', '第 2 章　第二章的標題'], '真結局：繼續到第 2 章'
    assert page.locator('.lw-choice .lw-endings-seen').inner_text() == '已看過 2／3 個結局', '第 1 章走完了：它的真結局算看過'
    reveal(page, 6)
    assert page.locator('.lw-end').is_visible() and page.locator('.lw-end-kind').inner_text() == '真結局'
    # 第 2 章的線索代號和第 1 章一樣（k1），算的是第 2 章自己的：看穿的是蘇映舟在第 2 章的底牌
    page.locator('#ch-2 .lw-clue').click()
    assert status.inner_text().endswith('線索 2／2') and '你看穿了 蘇映舟 的底牌' in page.locator('#ch-2 .lw-seen').inner_text()
    known = page.locator('.lw-end .lw-known')
    assert known.locator('.lw-secret .lw-name').all_inner_texts() == ['羅映川', '蘇映舟'] and SECRET_LUO in known.inner_text() and SECRET_SU in known.inner_text()
    assert known.locator('.lw-known-chapter').all_inner_texts() == ['第 1 章　第一章的標題', '第 2 章　第二章的標題']
    assert not page.locator('.lw-secrets').is_visible(), '底牌全部看穿了：不用再按「看底牌」'
    page.locator('.lw-pick').get_by_role('button', name='沈氏集團').click()
    more = page.locator('.lw-pick-more')
    assert EPILOGUE_SHEN in more.inner_text() and '第二章的番外' in more.inner_text(), '各章寫給這一邊的番外都顯示'
    assert more.locator('.lw-epilogue-chapter').all_inner_texts() == ['第 1 章　第一章的標題', '第 2 章　第二章的標題']
    assert ASK in page.locator('.lw-ask').inner_text() and '（不該出現）' not in page.locator('body').inner_text()
    assert [url for url in requests if url.split('#')[0] != target.as_uri()] == []
    assert problems == []
    context.close()


def test_without_scripts_the_whole_story_is_readable_and_everything_secret_stays_folded(chrome, tmp_path):
    """漸進增強：不能執行程式的環境（例如預覽工具）看得到全部段落、靜態的抉擇、下集預告與提問；
    要靠程式的按鈕不出現；底牌、番外、另外兩個結局是原生的收合區塊，預設不展開。"""
    target = tmp_path / 'play-noscript.html'
    target.write_bytes(render_play_html(drama(), '2026-11-12'))
    context, page, problems, requests = opened(chrome, target, java_script_enabled=False)
    assert seen(page) == 6 and seen(page, '.lw-beat-title') == 4 and page.locator('.lw-teaser').is_visible()
    for selector in ('.lw-tools', '.lw-nav', '.lw-entry', '.lw-pick', '.lw-again', '.lw-hint', '.lw-end-kind', '.lw-end-seen', '.lw-clue-note', '.lw-peek', '.lw-option'):
        assert seen(page, selector) == 0, selector
    assert seen(page, '.lw-xray') == 0, '真心話預設不顯示'
    assert page.locator('.lw-meta .lw-name').first.get_attribute('role') is None
    assert page.locator('.lw-clue').count() == 3 and page.locator('.lw-clue').first.get_attribute('role') is None, '線索詞只是一般文字'
    assert applied(page.locator('.lw-clue'), 'border-bottom-style') == 'none'
    # 抉擇是文章裡的一段：題目、三個選項；另外兩個結局收合，接下來就是原本的故事
    choice = page.locator('.lw-choice')
    assert choice.is_visible() and page.locator('.lw-choice-question').inner_text() == QUESTION
    assert page.locator('.lw-choice-list li').all_inner_texts() == [LABEL_TRUE, LABEL_PLAIN, LABEL_BAD] and page.locator('.lw-choice-static').is_visible()
    assert choice.bounding_box()['y'] < page.get_by_text('……這是一張白紙。').bounding_box()['y'], '抉擇排在結局段落之前'
    for summary, hidden in (('.lw-endings summary', ENDING_BAD), ('.lw-secrets summary', SECRET_LUO), ('.lw-epilogues summary', EPILOGUE_SHEN)):
        fold = page.locator(summary)
        assert fold.is_visible() and not page.get_by_text(hidden).is_visible(), summary
        fold.click()  # 原生的收合區塊，不需要程式
        assert page.get_by_text(hidden).is_visible(), summary
    assert page.locator('.lw-ask').is_visible() and ASK in page.locator('.lw-ask').inner_text()
    assert [url for url in requests if url != target.as_uri()] == []
    assert problems == []
    context.close()


def test_a_work_without_an_interactive_layer_still_has_views_and_peeks_and_reads_to_the_end(chrome, tmp_path):
    """沒有互動層的作品（還沒生成，或互動層是空的）：照樣選視角、限次偷看；沒有抉擇與線索，逐段揭開到最後就是結尾卡。"""
    target = tmp_path / 'play-plain.html'
    target.write_bytes(render_play_html(drama(interactive=None), '2026-11-12'))
    context, page, problems, requests = opened(chrome, target)
    assert page.locator('.lw-choice').count() == 0 and page.locator('.lw-clue').count() == 0 and page.locator('.lw-entry').is_visible()
    enter(page, 2)  # 沈知衡的視角：第 1、6 段是他的
    assert page.locator('.lw-status').inner_text() == '視角：沈知衡・偷看剩 3 次', '沒有線索就不顯示線索計數'
    assert xray_items(page, 0) == ['情緒志在必得', '立場逼他簽字', '目標今晚拿到簽名']
    reveal(page, 2)
    assert xray_items(page, 1) == [] and page.locator('.lw-seg').nth(1).locator('.lw-peek').is_visible()
    page.locator('h1').click()
    for expected in (3, 4, 5):
        page.keyboard.press('ArrowRight')
        assert seen(page) == expected and not page.locator('.lw-end').is_visible()
    page.keyboard.press('ArrowRight')
    assert seen(page) == 6 and page.locator('.lw-progress').inner_text() == '第 6／6 段' and page.locator('.lw-end').is_visible()
    assert page.get_by_role('button', name='下一段', exact=True).get_attribute('aria-disabled') == 'true'
    page.keyboard.press('ArrowRight')  # 已經到最後：不會再往下
    assert seen(page) == 6
    assert page.locator('.lw-end-kind').count() == 0 and page.locator('.lw-end-seen').count() == 0 and page.locator('.lw-known').is_hidden()
    fold = page.locator('.lw-secrets summary')
    assert fold.is_visible() and not page.get_by_text(SECRET_LUO).is_visible()
    fold.click()
    assert page.locator('.lw-secret .lw-name').all_inner_texts() == ['羅映川', '蘇映舟'] and page.get_by_text(SECRET_SU).is_visible()
    pick = page.locator('.lw-pick')
    pick.get_by_role('button', name='沈氏集團').click()
    assert page.locator('.lw-pick-result').inner_text() == '你選了：沈氏集團' and not page.locator('.lw-pick-more').is_visible()
    assert page.locator('.lw-ask').count() == 0 and page.locator('.lw-epilogues').count() == 0
    page.get_by_role('button', name='從頭再看').click()
    assert seen(page) == 0 and page.locator('.lw-entry').is_visible()
    assert [url for url in requests if url != target.as_uri()] == []
    assert problems == []
    context.close()


def test_an_old_work_plays_without_views_xray_secrets_or_sides(chrome, tmp_path):
    """舊作品（沒有狀態、底牌、陣營、幕名與預告）：選視角沒有差別，所以不問，照舊用「開始」；結尾只有「從頭再看」。"""
    cast = [{'name': '溫若岑', 'role': '配角', 'color': 1, 'side': None, 'secret': None}, {'name': '小光', 'role': None, 'color': 2, 'side': None, 'secret': None}]
    plain = lambda no, who, line: {'no': no, 'speaker': cast[who - 1]['name'], 'color': who, 'side': None, 'who': who, 'line': line, 'action': '', 'stage': '', 'state': None}
    chapter = {'no': 1, 'title': '（測試樣張）留一條接縫', 'genre': '', 'premise': '兩人初次見面。', 'scene': '虛構的試作桌。', 'form': 'script', 'teaser': '', 'secrets': [],
               'interactive': None,
               'beats': [{'no': 1, 'title': '', 'kind': None, 'goal': '試讀標籤。', 'segments': [plain(1, 2, '這裡寫「復原」？'), plain(2, 1, '這一塊還是草稿。')]}]}
    target = tmp_path / 'play-old.html'
    target.write_bytes(render_play_html({'format': 'lw-play.v2', 'title': '（測試樣張）留一條接縫', 'cast': cast, 'chapters': [chapter]}))
    context, page, problems, requests = opened(chrome, target)
    start = page.get_by_role('button', name='開始', exact=True)
    assert page.locator('.lw-tools').is_visible() and page.locator('.lw-entry').count() == 0 and start.is_visible()
    assert page.locator('.lw-progress').inner_text() == '共 2 段' and seen(page) == 0 and seen(page, '.lw-goal') == 0
    assert not page.locator('.lw-status').is_visible() and page.locator('.lw-peek').count() == 0
    page.keyboard.press('Space')
    assert seen(page) == 1 and page.locator('.lw-goal').is_visible() and not start.is_visible(), '舊作品沒有幕名：第幾幕與目標跟著第一段出現'
    page.keyboard.press('ArrowRight')
    assert seen(page) == 2 and page.locator('.lw-end').is_visible()
    assert page.locator('.lw-secrets').count() == 0 and page.locator('.lw-pick').count() == 0 and page.locator('.lw-teaser').count() == 0
    page.get_by_role('button', name='從頭再看').click()
    assert seen(page) == 0 and start.is_visible()
    start.click()
    assert seen(page) == 1
    assert [url for url in requests if url != target.as_uri()] == []
    assert problems == []
    context.close()
