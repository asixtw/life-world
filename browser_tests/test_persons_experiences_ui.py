"""人物經歷（Unified Person E1）的 Chrome 畫面驗收：人物詳細頁「經歷」分頁的兩個區塊與人物經歷對話框，對象是 Local 8030 → Cloud SQL life_world_e2e。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號、人物、我的經歷與人物經歷）：

    LW_E2E_PERSONS_UI=1 .venv\\Scripts\\python.exe -m pytest -q browser_tests/test_persons_experiences_ui.py

照使用者的點法走：人物列表 → 人物頁 →「經歷」頁籤 → ＋ 新增人物經歷 → 儲存（留在原頁籤）→ 另一位人物的頁面看到同一筆 → 編輯 → 封存 → 恢復。
設定 LW_E2E_SCREENSHOT_DIR 時，會把實際畫面存成 PNG（驗收證據）。
"""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_persons_ui import BASE, page, synthetic_account  # noqa: F401（page 是 fixture）

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS_UI') != '1', reason='部署後以 LW_E2E_PERSONS_UI=1 對 Local 8030（Cloud SQL E2E）執行')

PREPARE = """async (goal) => {
  const me = await fetch('/api/auth/me', {credentials: 'same-origin'}).then(r => r.json());
  const call = async (path, method, body) => {
    const r = await fetch('/api' + path, {method, credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token}, body: JSON.stringify(body)});
    const data = await r.json().catch(() => null);
    if (!r.ok) throw new Error(path + ' ' + r.status + ' ' + JSON.stringify(data));
    return data;
  };
  const person = (key, body) => call('/persons', 'POST', {request_id: 'exp-ui-' + key, ...body});
  const zhou = await person('a', {name: '周瑜', person_subtype: 'historical', description: '東吳軍事統帥，赤壁之戰的主帥。'});
  const sun = await person('b', {name: '孫策', person_subtype: 'historical', description: '江東之主。'});
  const lu = await person('c', {name: '魯肅', person_subtype: 'historical', description: '東吳謀臣。'});
  const real = await person('d', {name: '王小明', description: '認識的同事。'});
  const draft = await call('/experiences/drafts', 'POST', {raw_text: '和王小明討論合作計畫。', occurred_at: new Date(Date.now() - 120000).toISOString(), goal_id: goal.id,
    person_id: real.id, contributions: [{action_id: goal.actions[0].id, quantity: '0.5'}]});
  await call('/drafts/' + draft.id + '/confirm', 'POST', {request_id: 'exp-ui-confirm', expected_revision: draft.revision, summary: '和王小明討論合作計畫',
    person_id: real.id, contributions: draft.contributions, tasks: []});
  const state = await fetch('/api/state', {credentials: 'same-origin'}).then(r => r.json());
  return {zhou: zhou.id, sun: sun.id, lu: lu.id, real: real.id, points: state.rewards.total};
}"""

POINTS = "fetch('/api/state', {credentials: 'same-origin'}).then(r => r.json()).then(s => s.rewards.total)"


def shot(target, name):
    folder = os.environ.get('LW_E2E_SCREENSHOT_DIR')
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        target.screenshot(path=str(Path(folder) / name))


def panel(page, person_id):
    return page.locator(f'.person-tab-panel[data-person-view="{person_id}"][data-tab="experiences"]')


def add_participant(dialog, name, press_enter):
    """在搜尋框輸入姓名，等結果換成這位人物後加入（Enter 加入第一位，或點選結果）。"""
    box, results = dialog.locator('#persons-exp-q'), dialog.locator('#persons-exp-results button')
    box.fill(name)
    expect(results).to_have_count(1)
    expect(results.first).to_contain_text(name)
    if press_enter:
        box.press('Enter')
    else:
        results.first.click()
    expect(dialog.locator('#persons-exp-chips')).to_contain_text(name)
    expect(box).to_have_value('')  # 加入後清空，可以直接輸入下一位


def test_person_experiences_in_detail_page(page):
    page.set_viewport_size({'width': 1440, 'height': 1500})
    goal = synthetic_account(page)
    ids = page.evaluate(PREPARE, goal)
    dialog = page.locator('#account-dialog')
    records, people = page.locator('[data-block="records"]'), page.locator('[data-block="person-experiences"]')
    cards = page.locator('[data-exp-card]')

    # 1. 人物列表 → 點周瑜的卡片 → 人物頁 → 「經歷」頁籤：兩個區塊
    page.goto(BASE + '/#persons')
    page.locator('.persons-list-card', has_text='東吳軍事統帥').get_by_role('link', name='編輯 周瑜').click()
    page.get_by_role('tab', name='經歷').click()
    expect(panel(page, ids['zhou'])).to_be_visible()
    expect(records.get_by_role('heading', name='我的經歷（0）')).to_be_visible()
    expect(records).to_contain_text('以這位人物為主體的經歷，請記在下方的人物經歷')  # 周瑜是歷史人物：不提供「記錄我和他的經歷」
    expect(records.get_by_role('link', name='記錄我和他的經歷')).to_have_count(0)
    expect(people.get_by_role('heading', name='人物經歷（0）')).to_be_visible()
    expect(page.locator('.person-tab-panel a[href^="#person/"]')).to_have_count(0)  # 不跳到舊的人物頁
    shot(page, 'exp_01_tab_two_blocks.png')

    # 2. ＋ 新增人物經歷：主體自動帶入、性質預設「歷史」；連續加入兩位參與人物（Enter 與點選各一次）
    people.get_by_role('button', name='＋ 新增人物經歷').click()
    expect(dialog.get_by_role('heading', name='新增人物經歷')).to_be_visible()
    expect(dialog.locator('.person-card').first).to_contain_text('周瑜')
    expect(dialog.locator('#persons-exp-type')).to_have_value('historical')
    expect(dialog.locator('#persons-exp-results button')).to_have_count(0)  # 還沒輸入關鍵字時不列出人物
    add_participant(dialog, '孫策', press_enter=True)
    add_participant(dialog, '魯肅', press_enter=False)
    expect(dialog.locator('#persons-exp-chips')).to_contain_text('已選 2／50')
    dialog.locator('#persons-exp-title').fill('平定江東')
    dialog.locator('#persons-exp-content').fill('與孫策一同平定江東，建立東吳的基業。')
    dialog.locator('#persons-exp-year').fill('208')
    dialog.locator('#persons-exp-label').fill('建安十三年')
    shot(dialog, 'exp_02_new_dialog.png')
    url = page.url
    dialog.get_by_role('button', name='儲存經歷').click()
    expect(dialog).to_be_hidden()
    assert page.url == url  # 儲存後留在原本的頁籤
    expect(people.get_by_role('heading', name='人物經歷（1）')).to_be_visible()
    card = cards.filter(has_text='平定江東')
    for text in ('歷史', '主體', '208 年 · 建安十三年', '孫策', '魯肅', '與孫策一同平定江東'):
        expect(card).to_contain_text(text)
    shot(page, 'exp_03_after_create.png')
    assert page.evaluate(POINTS) == ids['points']  # 人物經歷不計積分

    # 3. 點卡片上的孫策 → 孫策的「經歷」頁籤看到同一筆，標示「參與」
    card.get_by_role('link', name='孫策').click()
    expect(panel(page, ids['sun'])).to_be_visible()
    expect(people.get_by_role('heading', name='人物經歷（1）')).to_be_visible()
    joined = cards.filter(has_text='平定江東')
    expect(joined).to_contain_text('參與')
    expect(joined).to_contain_text('周瑜')
    shot(page, 'exp_04_participant_page.png')

    # 4. 回周瑜 → 查看／編輯：原內容都在、性質不能改；改標題、補月份、移除魯肅
    joined.get_by_role('link', name='周瑜').click()
    expect(panel(page, ids['zhou'])).to_be_visible()
    cards.filter(has_text='平定江東').get_by_role('button', name='查看／編輯').click()
    expect(dialog.get_by_role('heading', name='編輯人物經歷')).to_be_visible()
    expect(dialog.locator('#persons-exp-title')).to_have_value('平定江東')
    expect(dialog.locator('#persons-exp-year')).to_have_value('208')
    expect(dialog.locator('#persons-exp-type')).to_be_disabled()
    dialog.locator('#persons-exp-title').fill('平定江東之戰')
    dialog.locator('#persons-exp-month').fill('12')
    dialog.get_by_role('button', name='移除 魯肅').click()
    expect(dialog.locator('#persons-exp-chips')).to_contain_text('已選 1／50')
    shot(dialog, 'exp_05_edit_dialog.png')
    dialog.get_by_role('button', name='儲存經歷').click()
    expect(dialog).to_be_hidden()
    card = cards.filter(has_text='平定江東之戰')
    expect(card).to_contain_text('208 年 12 月 · 建安十三年')
    expect(card).not_to_contain_text('魯肅')

    # 5. 再新增一筆只有內容的經歷（沒有標題、時間、參與人物）：排在知道時間的後面
    people.get_by_role('button', name='＋ 新增人物經歷').click()
    dialog.locator('#persons-exp-content').fill('少年時在廬江求學，結識了許多朋友。')
    dialog.get_by_role('button', name='儲存經歷').click()
    expect(dialog).to_be_hidden()
    expect(people.get_by_role('heading', name='人物經歷（2）')).to_be_visible()
    expect(cards.nth(0)).to_contain_text('平定江東之戰')
    expect(cards.nth(1)).to_contain_text('少年時在廬江求學')
    expect(cards.nth(1)).to_contain_text('時間不詳')

    # 6. 封存 → 預設列表少一筆 → 查看已封存 → 開啟後只能查看 → 恢復
    card.get_by_role('button', name='封存').click()
    expect(people.get_by_role('heading', name='人物經歷（1）')).to_be_visible()
    people.get_by_role('link', name='查看已封存的人物經歷（1）').click()
    expect(people.get_by_role('heading', name='已封存的人物經歷（1）')).to_be_visible()
    archived = cards.filter(has_text='平定江東之戰')
    expect(archived.get_by_role('button', name='恢復')).to_be_visible()
    shot(page, 'exp_06_archived.png')
    archived.get_by_role('button', name='查看', exact=True).click()
    expect(dialog.get_by_text('此經歷已封存')).to_be_visible()
    expect(dialog.get_by_role('button', name='儲存經歷')).to_have_count(0)
    dialog.get_by_role('button', name='恢復這筆經歷').click()
    expect(dialog).to_be_hidden()
    people.get_by_role('link', name='返回使用中的人物經歷').click()
    expect(people.get_by_role('heading', name='人物經歷（2）')).to_be_visible()

    # 7. 真實人物：我的經歷有內容，「記錄我和他的經歷」帶入人物；從紀錄頁可以回到這個頁籤
    page.goto(f"{BASE}/#persons/{ids['real']}?tab=experiences")
    expect(panel(page, ids['real'])).to_be_visible()
    expect(records.get_by_role('heading', name='我的經歷（1）')).to_be_visible()
    expect(records).to_contain_text('和王小明討論合作計畫')
    shot(page, 'exp_07_real_person_records.png')
    records.get_by_role('link', name='記錄我和他的經歷').click()
    expect(page.locator('#record-form')).to_be_visible()
    assert f"person={ids['real']}" in page.url
    page.get_by_role('link', name='返回人物頁').click()
    expect(panel(page, ids['real'])).to_be_visible()

    # 8. 資料確實在 Cloud SQL：重新整理後仍在；積分沒有變；沒有自動建立關係
    page.goto(f"{BASE}/#persons/{ids['zhou']}?tab=experiences")
    page.reload()
    expect(people.get_by_role('heading', name='人物經歷（2）')).to_be_visible()
    assert page.evaluate(POINTS) == ids['points']
    detail = page.evaluate("id => fetch('/api/persons/' + id, {credentials: 'same-origin'}).then(r => r.json()).then(d => [d.connections.length, d.experiences.person_experiences])", ids['zhou'])
    assert detail == [0, 2], detail
