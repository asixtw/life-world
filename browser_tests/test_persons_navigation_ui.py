"""人物頁換頁不跳動的 Chrome 驗收：Local 8030 → Cloud SQL life_world_e2e。

2026-11-11 Jerry 回報：人物列表 → 人物詳細頁 → 編輯人物，編輯頁直接停在表單底部（上次離開的位置）。
Jerry 指定的流程：人物列表 → 點人物卡片（或卡片上的「編輯」）→ 人物詳細頁（#persons/{id}）→ 點「編輯人物」→ 編輯頁（#persons-edit/{id}）。
卡片整理：整張卡片可點、每張卡片只有一個連結；「封存」是獨立按鈕，按了不換頁。
驗收：上述流程；新頁面從頂端開始；同一位人物切換分頁維持位置；回到列表時回到原本的位置並保留搜尋條件。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號與人物）：

    LW_E2E_PERSONS_UI=1 .venv\\Scripts\\python.exe -m pytest -q browser_tests/test_persons_navigation_ui.py
"""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_persons_ui import BASE, page, synthetic_account  # noqa: F401（page 是 fixture）

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS_UI') != '1', reason='部署後以 LW_E2E_PERSONS_UI=1 對 Local 8030（Cloud SQL E2E）執行')

FILL = """async () => {
  const me = await fetch('/api/auth/me', {credentials: 'same-origin'}).then(r => r.json());
  const ids = [];
  for (let i = 1; i <= 24; i++) {
    const r = await fetch('/api/persons', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token},
      body: JSON.stringify({request_id: 'nav-' + i, name: '導覽人物' + String(i).padStart(2, '0'), description: '換頁位置驗收用的第 ' + i + ' 位人物。'})});
    if (r.status !== 201) throw new Error('create ' + r.status);
    ids.push((await r.json()).id);
  }
  return ids;
}"""


def scroll_y(page):
    return page.evaluate('Math.round(window.scrollY)')


def shot(page, name):
    folder = os.environ.get('LW_E2E_SCREENSHOT_DIR')
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(folder) / name))


def test_list_detail_edit_navigation_does_not_jump(page):
    page.set_viewport_size({'width': 1280, 'height': 800})
    synthetic_account(page)
    ids = page.evaluate(FILL)
    first = ids[0]  # 最早建立：預設排序（最近新增）排在列表最後面
    edit_form = page.locator('#persons-edit-form')
    detail = page.locator(f'.person-tab-panel[data-person-view="{first}"]')

    # 1. 列表捲到最底下，點最後一位人物卡片上的「編輯」→ 先進入人物詳細頁（不直接跳進編輯表單），從頂端開始
    page.goto(BASE + '/#world')
    page.goto(BASE + '/#persons')
    expect(page.get_by_role('heading', name='人物（24）')).to_be_visible()
    page.evaluate('window.scrollTo(0, document.documentElement.scrollHeight)')
    list_y = scroll_y(page)
    assert list_y > 500, list_y
    card = page.locator('.persons-list-card', has_text='導覽人物01')
    expect(card.get_by_role('link')).to_have_count(1)  # 每張卡片只有一個連結
    expect(card.get_by_role('link', name='編輯 導覽人物01')).to_have_attribute('href', f'#persons/{first}')
    shot(page, 'nav_00_list.png')
    # 用真實滑鼠點在卡片內文上：整張卡片由「編輯」連結接手點擊（Playwright 的元素點擊會因為被連結覆蓋而拒絕點，所以改用座標）
    box = card.locator('.char-summary').bounding_box()
    page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    expect(detail).to_be_visible()
    assert page.url.endswith(f'#persons/{first}'), page.url
    assert scroll_y(page) == 0
    shot(page, 'nav_01_detail_from_list_edit.png')

    # 2. 編輯人物 → 編輯頁從頂端開始；在底部按「返回人物」後再開一次，仍從頂端開始（原本會停在表單底部）
    page.get_by_role('link', name='編輯人物').click()
    expect(edit_form).to_be_visible()
    assert page.url.endswith(f'#persons-edit/{first}'), page.url
    assert scroll_y(page) == 0
    page.get_by_role('link', name='返回人物', exact=True).click()  # 按鈕在表單底部：點擊前會捲到底
    expect(detail).to_be_visible()
    assert scroll_y(page) == 0
    page.get_by_role('link', name='編輯人物').click()
    expect(edit_form).to_be_visible()
    assert scroll_y(page) == 0
    expect(page.locator('#person-name')).to_be_in_viewport()
    shot(page, 'nav_02_edit_page_opens_at_top.png')

    # 3. 在底部儲存 → 詳細頁從頂端開始
    page.locator('#person-description').fill('換頁位置驗收：已修改。')
    page.get_by_role('button', name='儲存人物').click()
    expect(detail).to_be_visible()
    expect(page.get_by_text('換頁位置驗收：已修改。').first).to_be_visible()
    assert scroll_y(page) == 0

    # 4. 同一位人物切換分頁：位置不動，分頁列不跳
    page.evaluate('window.scrollTo(0, 120)')
    before = scroll_y(page)
    page.get_by_role('tab', name='人物設定').click()
    expect(page.locator(f'.person-tab-panel[data-person-view="{first}"][data-tab="profile"]')).to_be_visible()
    limit = page.evaluate('Math.max(0, document.documentElement.scrollHeight - window.innerHeight)')
    assert scroll_y(page) == min(before, limit), (before, limit, scroll_y(page))

    # 5. 返回人物列表 → 回到原本捲到的位置
    page.get_by_role('link', name='← 返回人物列表').click()
    expect(page.get_by_role('heading', name='人物（24）')).to_be_visible()
    assert abs(scroll_y(page) - list_y) <= 2, (scroll_y(page), list_y)
    expect(page.locator('.persons-list-card', has_text='導覽人物01')).to_be_in_viewport()
    shot(page, 'nav_03_back_to_list_keeps_position.png')

    # 6. 搜尋後進入人物再返回：搜尋條件保留
    page.locator('#persons-q').fill('導覽人物2')
    page.get_by_role('button', name='套用').click()
    expect(page.get_by_role('heading', name='人物（5）')).to_be_visible()  # 20～24
    page.locator('.persons-list-card', has_text='導覽人物22').get_by_role('link', name='編輯 導覽人物22').click()
    expect(page.locator(f'.person-tab-panel[data-person-view="{ids[21]}"]')).to_be_visible()
    page.get_by_role('link', name='← 返回人物列表').click()
    expect(page.get_by_role('heading', name='人物（5）')).to_be_visible()
    expect(page.locator('#persons-q')).to_have_value('導覽人物2')

    # 7. 卡片上的「封存」：只封存、不換頁（按鈕在整張可點的卡片上層）
    url = page.url
    page.locator('.persons-list-card', has_text='導覽人物24').get_by_role('button', name='封存').click()
    expect(page.get_by_role('heading', name='人物（4）')).to_be_visible()
    assert page.url == url, page.url
    page.locator('select[name=status]').select_option('archived')
    page.get_by_role('button', name='套用').click()
    archived = page.locator('.persons-list-card', has_text='導覽人物24')
    expect(archived.get_by_role('link', name='查看 導覽人物24')).to_be_visible()  # 已封存：連結是「查看」
    expect(archived.get_by_role('button', name='恢復')).to_be_visible()
    shot(page, 'nav_04_archived_card_view_and_restore.png')
