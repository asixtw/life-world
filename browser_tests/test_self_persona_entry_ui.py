"""左側導覽與「我的人設」入口的 Chrome 畫面驗收。對象是 Local 8030 → Cloud SQL life_world_e2e。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號）：

    LW_E2E_PERSONS_UI=1 .venv\\Scripts\\python.exe -m pytest -q browser_tests/test_self_persona_entry_ui.py

驗收順序（2026-11-11 指示）：
1 左側導覽只有 世界／目標／紀錄／人物／作品，不再列「關係」「角色」 → 2 紀錄 → 我的紀錄上方有「我的人設」→
3 建立人設（與人物設定相同的 A～E 分區）→ 4 回我的紀錄看到摘要 → 5 再編輯存成第 2 版 → 6 同意讓 AI 使用 → 7 重新整理後仍在。
設定 LW_E2E_SCREENSHOT_DIR 時，會把實際畫面存成 PNG。
"""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_persons_ui import BASE, page, synthetic_account  # noqa: F401（page 是 fixture）

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS_UI') != '1', reason='部署後以 LW_E2E_PERSONS_UI=1 對 Local 8030（Cloud SQL E2E）執行')


def shot(target, name):
    folder = os.environ.get('LW_E2E_SCREENSHOT_DIR')
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        target.screenshot(path=str(Path(folder) / name))


def test_nav_without_legacy_entries_and_self_persona_from_my_records(page):
    page.set_viewport_size({'width': 1440, 'height': 1500})
    synthetic_account(page)
    nav = page.locator('#nav')
    card = page.locator('[data-block="self-persona"]')
    form = page.locator('#persona-form')

    # 1. 左側導覽：人物取代了舊的「關係」「角色」
    expect(nav.get_by_role('link')).to_have_text(['⌂世界', '♧目標', '▤紀錄', '◎人物', '▣作品'])
    expect(nav.get_by_role('link', name='關係', exact=True)).to_have_count(0)
    expect(nav.get_by_role('link', name='角色', exact=True)).to_have_count(0)
    shot(page, 'self_01_nav_without_relations_and_characters.png')

    # 2. 紀錄 → 我的紀錄：上方有「我的人設」，還沒建立
    nav.get_by_role('link', name='紀錄').click()
    expect(card.get_by_role('heading', name='我的人設')).to_be_visible()
    expect(card).to_contain_text('尚未建立')
    shot(page, 'self_02_my_records_with_empty_self_persona.png')

    # 3. 建立人設：A～E 分區，必填四欄
    card.get_by_role('link', name='建立我的人設').click()
    expect(page.get_by_role('heading', name='我的人設', exact=True)).to_be_visible()
    for title in ('A｜基本資料', 'B｜人格特質', 'C｜能力與知識', 'D｜行為與表達', 'E｜關係與界線'):
        expect(form.get_by_role('heading', name=title)).to_be_visible()
    expect(nav.locator('a.active')).to_have_text('▤紀錄')  # 人設頁歸在「紀錄」底下
    form.locator('#persona-display_name').fill('合成測試者')
    form.locator('#persona-public_profile').fill('喜歡桌遊與慢跑的工程師。')
    form.locator('#persona-personality').fill('慢熟、好奇，遇到問題會先觀察。')
    form.locator('#persona-speaking_style').fill('語速慢，常先確認對方的意思。')
    form.locator('#persona-motivation').fill('想把生活過得明白。')
    form.locator('#persona-sample_lines').fill('先聽我說完。\n這個我想一下。')
    form.locator('#persona-truth').select_option('real')
    shot(page, 'self_03_persona_form_blocks.png')
    form.get_by_role('button', name='建立人設').click()
    expect(page.get_by_text('目前 v1')).to_be_visible()

    # 4. 回我的紀錄：卡片顯示摘要
    page.get_by_role('link', name='← 我的紀錄').click()
    expect(card).to_contain_text('合成測試者')
    expect(card).to_contain_text('第 1 版')
    expect(card).to_contain_text('真實的我')
    expect(card).to_contain_text('已填 6／12 欄')
    expect(card).to_contain_text('尚未同意 AI 使用')
    expect(card).to_contain_text('喜歡桌遊與慢跑的工程師。')
    shot(page, 'self_04_my_records_with_self_persona.png')

    # 5. 再編輯：內容帶回表單，保存成第 2 版
    card.get_by_role('link', name='編輯我的人設').click()
    expect(form.locator('#persona-personality')).to_have_value('慢熟、好奇，遇到問題會先觀察。')
    expect(form.locator('#persona-sample_lines')).to_have_value('先聽我說完。\n這個我想一下。')
    form.locator('#persona-values').fill('說到做到。')
    form.get_by_role('button', name='保存新版本').click()
    expect(page.get_by_text('目前 v2')).to_be_visible()

    # 6. 同意讓 AI 使用
    page.get_by_role('button', name='我同意').click()
    expect(page.get_by_role('button', name='撤回同意')).to_be_visible()
    shot(page, 'self_05_persona_saved_and_consented.png')

    # 7. 重新整理後仍在
    page.goto(f'{BASE}/#history')
    page.reload()
    expect(card).to_contain_text('第 2 版')
    expect(card).to_contain_text('已填 7／12 欄')
    expect(card).to_contain_text('已同意 AI 使用')
    shot(page, 'self_06_after_reload.png')
