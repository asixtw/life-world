"""「人物 → 我的設定」與「紀錄 → 我的經歷」的 Chrome 畫面驗收。對象是 Local 8030 → Cloud SQL life_world_e2e。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號）：

    LW_E2E_PERSONS_UI=1 .venv\\Scripts\\python.exe -m pytest -q browser_tests/test_self_persona_entry_ui.py

驗收順序（2026-11-11 指示）：
1 左側導覽只有 世界／目標／紀錄／人物／作品 → 2 進入「人物」，最上方是「我的設定」（還沒建立）→
3 建立我的設定（與人物設定相同的 A～E 分區）→ 4 回人物首頁看到摘要 → 5 從右上角帳號視窗的「我的設定」再進去，存成第 2 版並同意 →
6 紀錄的第一個頁籤是「我的經歷」，上面沒有我的設定 → 7 記下經歷時「關聯人物」與「整理這段故事的人物」只列真實人物 →
8 離開未保存的表單（App 會先詢問）回到人物首頁，重新整理後仍在。
設定 LW_E2E_SCREENSHOT_DIR 時，會把實際畫面存成 PNG。
"""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_persons_ui import BASE, page, synthetic_account  # noqa: F401（page 是 fixture）

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS_UI') != '1', reason='部署後以 LW_E2E_PERSONS_UI=1 對 Local 8030（Cloud SQL E2E）執行')

PEOPLE = """async () => {
  const me = await fetch('/api/auth/me', {credentials: 'same-origin'}).then(r => r.json());
  const person = async (key, body) => {
    const r = await fetch('/api/persons', {method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token}, body: JSON.stringify({request_id: 'self-ui-' + key, ...body})});
    if (!r.ok) throw new Error('persons ' + r.status + ' ' + await r.text());
  };
  await person('a', {name: '王小明', description: '大學同學。'});                                  // 真實人物：可以關聯我的經歷
  await person('b', {name: '周瑜', person_subtype: 'historical', description: '東吳軍事統帥。'});  // 歷史人物：不列
  await person('c', {name: '沈知衡', person_subtype: 'original', description: '原創人物。'});      // 虛構人物：不列
}"""


def shot(target, name):
    folder = os.environ.get('LW_E2E_SCREENSHOT_DIR')
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        target.screenshot(path=str(Path(folder) / name))


def test_my_settings_under_persons_and_my_experiences_under_records(page):
    page.set_viewport_size({'width': 1440, 'height': 1500})
    synthetic_account(page)  # 完成後停在人物首頁
    nav = page.locator('#nav')
    card = page.locator('[data-block="self-persona"]')
    form = page.locator('#persona-form')
    dialog = page.locator('#account-dialog')

    # 1. 左側導覽：人物取代了舊的「關係」「角色」
    expect(nav.get_by_role('link')).to_have_text(['⌂世界', '♧目標', '▤紀錄', '◎人物', '▣作品'])

    # 2. 人物首頁：最上方是「我的設定」，在搜尋與人物列表之前；還沒建立
    expect(card.get_by_role('heading', name='我的設定')).to_be_visible()
    expect(card).to_contain_text('尚未建立')
    expect(card.get_by_role('link', name='我的經歷')).to_be_visible()
    assert card.bounding_box()['y'] < page.locator('#persons-filter-form').bounding_box()['y']
    shot(page, 'me_01_persons_home_with_empty_my_settings.png')

    # 3. 建立我的設定：A～E 分區；頁面歸在「人物」底下
    card.get_by_role('link', name='建立我的設定').click()
    expect(page.get_by_role('heading', name='我的設定', exact=True)).to_be_visible()
    for title in ('A｜基本資料', 'B｜人格特質', 'C｜能力與知識', 'D｜行為與表達', 'E｜關係與界線'):
        expect(form.get_by_role('heading', name=title)).to_be_visible()
    expect(nav.locator('a.active')).to_have_text('◎人物')
    expect(page.get_by_text('就是作品裡 AI 扮演你時使用的「我的人設」')).to_be_visible()
    form.locator('#persona-display_name').fill('合成測試者')
    form.locator('#persona-public_profile').fill('喜歡桌遊與慢跑的工程師。')
    form.locator('#persona-personality').fill('慢熟、好奇，遇到問題會先觀察。')
    form.locator('#persona-speaking_style').fill('語速慢，常先確認對方的意思。')
    form.locator('#persona-motivation').fill('想把生活過得明白。')
    form.locator('#persona-sample_lines').fill('先聽我說完。\n這個我想一下。')
    form.locator('#persona-truth').select_option('real')
    shot(page, 'me_02_my_settings_form.png')
    form.get_by_role('button', name='建立我的設定').click()
    expect(page.get_by_text('目前第 1 版')).to_be_visible()

    # 4. 回人物首頁：卡片顯示摘要
    page.get_by_role('link', name='← 人物').click()
    expect(card).to_contain_text('合成測試者')
    expect(card).to_contain_text('第 1 版')
    expect(card).to_contain_text('真實的我')
    expect(card).to_contain_text('已填 6／12 欄')
    expect(card).to_contain_text('尚未同意 AI 使用')
    expect(card).to_contain_text('喜歡桌遊與慢跑的工程師。')
    shot(page, 'me_03_persons_home_with_my_settings.png')

    # 5. 右上角帳號視窗也能進「我的設定」；內容帶回表單，保存成第 2 版並同意
    page.locator('#account-button').click()
    expect(dialog).to_be_visible()
    shot(page, 'me_04_account_dialog_entry.png')
    dialog.get_by_role('button', name='我的設定').click()
    expect(dialog).to_be_hidden()
    expect(page.get_by_role('heading', name='我的設定', exact=True)).to_be_visible()
    expect(form.locator('#persona-personality')).to_have_value('慢熟、好奇，遇到問題會先觀察。')
    expect(form.locator('#persona-sample_lines')).to_have_value('先聽我說完。\n這個我想一下。')
    form.locator('#persona-values').fill('說到做到。')
    form.get_by_role('button', name='保存新版本').click()
    expect(page.get_by_text('目前第 2 版')).to_be_visible()
    page.get_by_role('button', name='我同意').click()
    expect(page.get_by_role('button', name='撤回同意')).to_be_visible()
    shot(page, 'me_05_my_settings_saved_and_consented.png')

    # 6. 紀錄：第一個頁籤是「我的經歷」；我的設定不在這裡
    page.evaluate(PEOPLE)
    page.reload()  # 剛才直接用 API 建立了人物；重新整理後 App 才會讀到
    nav.get_by_role('link', name='紀錄').click()
    tabs = page.locator('.record-tabs')
    expect(tabs.get_by_role('tab')).to_have_text(['我的經歷', '人物經歷', '全部'])
    expect(tabs.get_by_role('tab', name='我的經歷')).to_have_attribute('aria-selected', 'true')
    expect(card).to_have_count(0)
    shot(page, 'me_06_records_my_experiences_tab.png')

    # 7. 記下經歷：「關聯人物」只列真實人物（不含歷史人物與虛構人物）
    page.get_by_role('link', name='＋ 新的經歷').click()
    expect(page.locator('#person-id option')).to_have_text(['不關聯人物', '王小明'])
    expect(page.get_by_text('只列出真實人物')).to_be_visible()
    page.locator('#include-story').check()  # 「整理這段故事的人物」也只列真實人物
    expect(page.locator('.participant-option')).to_have_count(1)
    expect(page.locator('.participant-option')).to_contain_text('王小明')
    shot(page, 'me_07_record_form_real_people_only.png')

    # 8. 剛才動過表單，離開時 App 會先問要不要保存；捨棄後回到人物首頁，重新整理後仍在
    nav.get_by_role('link', name='人物').click()
    dialog.get_by_role('button', name='捨棄未保存修改並離開').click()
    expect(card).to_contain_text('第 2 版')
    page.reload()
    expect(card).to_contain_text('第 2 版')
    expect(card).to_contain_text('已填 7／12 欄')
    expect(card).to_contain_text('已同意 AI 使用')
    expect(page.get_by_role('heading', name='人物（3）')).to_be_visible()
    shot(page, 'me_08_after_reload.png')
