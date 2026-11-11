"""人物經歷 E2／E3 的 Chrome 畫面驗收：紀錄頁的三個頁籤、雙入口共用同一筆資料、關係引用人物經歷。對象是 Local 8030 → Cloud SQL life_world_e2e。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號、人物、我的紀錄、人物經歷與關係）：

    LW_E2E_PERSONS_UI=1 .venv\\Scripts\\python.exe -m pytest -q browser_tests/test_records_page_ui.py

照 2026-11-11 指令的驗收順序走：
1 從人物頁新增人物經歷 → 2 從紀錄頁找到同一筆 → 3 從紀錄頁新增另一筆（先選主體）→ 4 回人物頁確認兩筆都在 →
5 編輯及封存（含恢復）→ 6 從關係表單引用人物經歷 → 7 雙方人物頁都讀得到來源 → 8 我的紀錄不受影響。
（9 Owner 隔離由 tests/test_person_experiences_records_cloudsql_e2e.py 在 Cloud SQL 上驗收。）
設定 LW_E2E_SCREENSHOT_DIR 時，會把實際畫面存成 PNG。
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
  const person = (key, body) => call('/persons', 'POST', {request_id: 'rec-ui-' + key, ...body});
  const zhou = await person('a', {name: '周瑜', person_subtype: 'historical', description: '東吳軍事統帥，赤壁之戰的主帥。'});
  const sun = await person('b', {name: '孫策', person_subtype: 'historical', description: '江東之主。'});
  const draft = await call('/experiences/drafts', 'POST', {raw_text: '和朋友討論周瑜的策略。', occurred_at: new Date(Date.now() - 120000).toISOString(), goal_id: goal.id,
    person_id: zhou.id, contributions: [{action_id: goal.actions[0].id, quantity: '0.5'}]});
  await call('/drafts/' + draft.id + '/confirm', 'POST', {request_id: 'rec-ui-confirm', expected_revision: draft.revision, summary: '和朋友討論周瑜的策略',
    person_id: zhou.id, contributions: draft.contributions, tasks: []});
  const state = await fetch('/api/state', {credentials: 'same-origin'}).then(r => r.json());
  return {zhou: zhou.id, sun: sun.id, points: state.rewards.total, records: state.experiences.length};
}"""

STATE = "fetch('/api/state', {credentials: 'same-origin'}).then(r => r.json()).then(s => [s.rewards.total, s.experiences.length])"


def shot(target, name):
    folder = os.environ.get('LW_E2E_SCREENSHOT_DIR')
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        target.screenshot(path=str(Path(folder) / name))


def person_tab(page, person_id, tab):
    page.goto(f'{BASE}/#persons/{person_id}?tab={tab}')
    expect(page.locator(f'.person-tab-panel[data-person-view="{person_id}"][data-tab="{tab}"]')).to_be_visible()


def test_records_page_and_relation_sources(page):
    page.set_viewport_size({'width': 1440, 'height': 1500})
    goal = synthetic_account(page)
    ids = page.evaluate(PREPARE, goal)
    page.reload()  # 剛才直接用 API 建立了我的紀錄；重新整理後 App 才會讀到（實際操作時紀錄流程會自己更新）
    dialog = page.locator('#account-dialog')
    people = page.locator('[data-block="person-experiences"]')
    cards = page.locator('[data-exp-card]')

    # 1. 從人物頁新增人物經歷（主體自動帶入周瑜，參與人物孫策）
    person_tab(page, ids['zhou'], 'experiences')
    people.get_by_role('button', name='＋ 新增人物經歷').click()
    box = dialog.locator('#persons-exp-q')
    box.fill('孫策')
    expect(dialog.locator('#persons-exp-results button')).to_have_count(1)
    box.press('Enter')
    expect(dialog.locator('#persons-exp-chips')).to_contain_text('已選 1／50')
    dialog.locator('#persons-exp-title').fill('平定江東')
    dialog.locator('#persons-exp-content').fill('與孫策一同平定江東，建立東吳的基業。')
    dialog.locator('#persons-exp-year').fill('199')
    dialog.get_by_role('button', name='儲存經歷').click()
    expect(dialog).to_be_hidden()
    expect(people.get_by_role('heading', name='人物經歷（1）')).to_be_visible()

    # 2. 左側「紀錄」→「人物經歷」頁籤：找到同一筆，顯示主體與參與人物
    page.locator('#nav').get_by_role('link', name='紀錄').click()
    expect(page.get_by_role('tab', name='我的紀錄')).to_be_visible()
    expect(page.get_by_text('和朋友討論周瑜的策略').first).to_be_visible()  # 預設是我的紀錄，原本的內容都在
    page.get_by_role('tab', name='人物經歷').click()
    expect(people.get_by_role('heading', name='人物經歷（1）')).to_be_visible()
    card = cards.filter(has_text='平定江東')
    for text in ('主體：周瑜', '參與：孫策', '歷史', '199 年', '與孫策一同平定江東'):
        expect(card).to_contain_text(text)
    shot(page, 'rec_01_records_page_people_tab.png')

    # 3. 從紀錄頁新增另一筆：先搜尋選擇主體（孫策），性質跟著人物類型，其餘是同一個表單
    page.get_by_role('button', name='＋ 新增人物經歷').click()
    expect(dialog.get_by_role('heading', name='新增人物經歷')).to_be_visible()
    subject = dialog.locator('#persons-exp-subject-q')
    subject.fill('孫策')
    expect(dialog.locator('#persons-exp-subject-results button')).to_have_count(1)
    shot(dialog, 'rec_02_new_from_records_pick_subject.png')
    subject.press('Enter')
    expect(dialog.locator('#persons-exp-subject')).to_contain_text('江東之主')
    expect(dialog.get_by_role('button', name='更換主體')).to_be_visible()
    expect(dialog.locator('#persons-exp-type')).to_have_value('historical')
    dialog.locator('#persons-exp-content').fill('孫策少年時在壽春結交名士。')
    dialog.get_by_role('button', name='儲存經歷').click()
    expect(dialog).to_be_hidden()
    expect(people.get_by_role('heading', name='人物經歷（2）')).to_be_visible()
    expect(cards.nth(0)).to_contain_text('平定江東')  # 知道時間的在前
    expect(cards.nth(1)).to_contain_text('孫策少年時在壽春結交名士')

    # 4. 點卡片上的孫策 → 孫策的經歷頁籤：兩筆都在（一筆參與、一筆主體）
    cards.nth(0).get_by_role('link', name='孫策').click()
    expect(page.locator(f'.person-tab-panel[data-person-view="{ids["sun"]}"][data-tab="experiences"]')).to_be_visible()
    expect(people.get_by_role('heading', name='人物經歷（2）')).to_be_visible()
    expect(cards.filter(has_text='平定江東')).to_contain_text('參與')
    expect(cards.filter(has_text='孫策少年時')).to_contain_text('主體')
    shot(page, 'rec_03_person_page_shows_both.png')

    # 5. 回紀錄頁：編輯（改標題）→ 封存 → 查看已封存 → 恢復
    page.goto(BASE + '/#history?view=people')
    cards.filter(has_text='孫策少年時').get_by_role('button', name='查看／編輯').click()
    expect(dialog.get_by_role('heading', name='編輯人物經歷')).to_be_visible()
    expect(dialog.get_by_role('button', name='更換主體')).to_have_count(0)  # 既有經歷的主體固定
    dialog.locator('#persons-exp-title').fill('壽春結交名士')
    dialog.get_by_role('button', name='儲存經歷').click()
    expect(dialog).to_be_hidden()
    edited = cards.filter(has_text='壽春結交名士')
    expect(edited).to_have_count(1)
    edited.get_by_role('button', name='封存').click()
    expect(people.get_by_role('heading', name='人物經歷（1）')).to_be_visible()
    people.get_by_role('link', name='查看已封存的人物經歷（1）').click()
    expect(people.get_by_role('heading', name='已封存的人物經歷（1）')).to_be_visible()
    cards.filter(has_text='壽春結交名士').get_by_role('button', name='恢復').click()
    expect(people.get_by_role('heading', name='已封存的人物經歷（0）')).to_be_visible()
    people.get_by_role('link', name='返回使用中的人物經歷').click()
    expect(people.get_by_role('heading', name='人物經歷（2）')).to_be_visible()

    # 6. 關係表單引用人物經歷：周瑜 → 關係 → 新增關係 → 孫策；來源有我的紀錄與人物經歷兩組
    person_tab(page, ids['zhou'], 'relations')
    page.get_by_role('button', name='＋ 新增關係').click()
    dialog.locator('#persons-relation-q').fill('孫策')
    results = dialog.locator('#persons-relation-results button')
    expect(results).to_have_count(1)
    results.first.click()
    expect(dialog.locator('input[name=relation_source]')).to_have_count(1)
    expect(dialog.locator('input[name=relation_person_source]')).to_have_count(2)
    dialog.get_by_label('朋友', exact=True).check()
    dialog.locator('#persons-relation-description').fill('兩人一同平定江東。')
    dialog.locator('input[name=relation_source]').first.check()
    dialog.locator('label', has_text='平定江東').locator('input[name=relation_person_source]').check()
    shot(dialog, 'rec_04_relation_sources_two_kinds.png')
    dialog.get_by_role('button', name='儲存關係').click()
    expect(dialog).to_be_hidden()
    relation = page.locator('.person-tab-panel article.card').filter(has=page.get_by_role('link', name='孫策', exact=True))
    expect(relation).to_contain_text('來源：1 筆我的紀錄、1 筆人物經歷')

    # 7. 孫策的人物頁讀到同一組來源；重新編輯時原本的來源仍勾選
    person_tab(page, ids['sun'], 'relations')
    other_side = page.locator('.person-tab-panel article.card').filter(has=page.get_by_role('link', name='周瑜', exact=True))
    expect(other_side).to_contain_text('來源：1 筆我的紀錄、1 筆人物經歷')
    other_side.locator('summary').click()
    expect(other_side).to_contain_text('平定江東')
    shot(page, 'rec_05_other_side_reads_sources.png')
    other_side.get_by_role('button', name='編輯').click()
    expect(dialog.locator('input[name=relation_person_source]:checked')).to_have_count(1)
    expect(dialog.locator('input[name=relation_source]:checked')).to_have_count(1)
    dialog.get_by_role('button', name='取消').click()
    expect(dialog).to_be_hidden()

    # 8. 我的紀錄不受影響：紀錄頁的我的紀錄還是原本那一筆、積分沒有變；「全部」頁籤兩種都在並標示類型
    page.goto(BASE + '/#history')
    expect(page.get_by_text('和朋友討論周瑜的策略').first).to_be_visible()
    assert page.evaluate(STATE) == [ids['points'], ids['records']]
    page.get_by_role('tab', name='全部').click()
    block = page.locator('[data-block="all-records"]')
    expect(block.get_by_role('heading', name='全部（3）')).to_be_visible()
    expect(block.locator('article').nth(0)).to_contain_text('我的紀錄')  # 今天的紀錄最新，排最前面
    expect(block.locator('[data-exp-card]')).to_have_count(2)
    expect(block.locator('[data-exp-card]').first).to_contain_text('人物經歷')
    shot(page, 'rec_06_all_tab.png')
    page.reload()
    expect(block.get_by_role('heading', name='全部（3）')).to_be_visible()  # 重新整理後仍在：資料在 Cloud SQL
