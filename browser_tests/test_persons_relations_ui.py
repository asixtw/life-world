"""Unified Person P4 的 Chrome 畫面驗收：人物詳細頁「關係」分頁的新增、編輯、封存、恢復，對象是 Local 8030 → Cloud SQL life_world_e2e。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號、人物、我的紀錄與關係）：

    LW_E2E_PERSONS_UI=1 .venv\\Scripts\\python.exe -m pytest -q browser_tests/test_persons_relations_ui.py

設定 LW_E2E_SCREENSHOT_DIR 時，會把實際畫面存成 PNG（驗收證據）。
"""
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_persons_ui import BASE, page, synthetic_account  # noqa: F401（page 是 fixture）

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS_UI') != '1', reason='部署後以 LW_E2E_PERSONS_UI=1 對 Local 8030（Cloud SQL E2E）執行')
HINT = '這段關係由雙方共用，請描述兩人之間的關係，不是單方面的人物備註。'

PREPARE = """async (goal) => {
  const me = await fetch('/api/auth/me', {credentials: 'same-origin'}).then(r => r.json());
  const call = async (path, method, body) => {
    const r = await fetch('/api' + path, {method, credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token}, body: JSON.stringify(body)});
    const data = await r.json().catch(() => null);
    if (!r.ok) throw new Error(path + ' ' + r.status + ' ' + JSON.stringify(data));
    return data;
  };
  const person = (key, body) => call('/persons', 'POST', {request_id: 'rel-ui-' + key, ...body});
  const a = await person('a', {name: '周瑜', person_subtype: 'historical', description: '東吳軍事統帥，赤壁之戰的主帥。', tags: ['正史三國']});
  const b = await person('b', {name: '孫策', person_subtype: 'historical', description: '江東之主。'});
  const twin = await person('twin', {name: '周瑜', person_type: 'fictional', description: '架空三國的現代企業家。'});
  const d = await person('d', {name: '諸葛亮', person_subtype: 'historical', description: '蜀漢丞相。'});
  const moment = new Date(Date.now() - 120000).toISOString();
  for (const [index, text] of [[1, '與孫策商議平定江東的計畫。'], [2, '赤壁之戰前的軍事會議。']]) {
    const draft = await call('/experiences/drafts', 'POST', {raw_text: text, occurred_at: moment, goal_id: goal.id, person_id: a.id,
      contributions: [{action_id: goal.actions[0].id, quantity: '0.5'}]});
    await call('/drafts/' + draft.id + '/confirm', 'POST', {request_id: 'rel-ui-confirm-' + index, expected_revision: draft.revision, summary: text,
      person_id: a.id, contributions: draft.contributions, tasks: []});
  }
  return {a: a.id, b: b.id, twin: twin.id, d: d.id};
}"""

ARCHIVE_PERSON = """async (id) => {
  const me = await fetch('/api/auth/me', {credentials: 'same-origin'}).then(r => r.json());
  const current = await fetch('/api/persons/' + id, {credentials: 'same-origin'}).then(r => r.json());
  const r = await fetch('/api/persons/' + id + '/status', {method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token},
    body: JSON.stringify({request_id: 'rel-ui-archive-person', expected_revision: current.person.revision, status: 'archived'})});
  if (!r.ok) throw new Error('archive ' + r.status);
}"""


def shot(target, name):
    """把實際畫面存成證據（target 可以是整頁或單一元件）。"""
    folder = os.environ.get('LW_E2E_SCREENSHOT_DIR')
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        target.screenshot(path=str(Path(folder) / name))


def open_relations(page, person_id):
    """切到這位人物的關係分頁，並等畫面確實換成這位人物（同名人物多，不能只看姓名）。"""
    page.goto(f'{BASE}/#persons/{person_id}?tab=relations')
    expect(page.locator(f'.person-tab-panel[data-person-view="{person_id}"][data-tab="relations"]')).to_be_visible()


def cards(page):
    return page.locator('.person-tab-panel article.card')


def card_of(page, name):
    """以卡片標題的人物姓名找關係卡片（不比對內文，避免被來源摘要裡的姓名誤配）。"""
    return cards(page).filter(has=page.get_by_role('link', name=name, exact=True))


def search_and_pick(dialog, results, query, expected):
    """在選擇器輸入關鍵字，等結果確實換成要找的人物後再點選（搜尋是非同步的，舊結果可能還在畫面上）。"""
    dialog.locator('#persons-relation-q').fill(query)
    expect(results).to_have_count(1)
    expect(results.first).to_contain_text(expected)
    return results.first


def test_person_relations_in_detail_page(page):
    page.set_viewport_size({'width': 1440, 'height': 1500})  # 視窗夠高，關係表單可以完整截圖
    goal = synthetic_account(page)
    ids = page.evaluate(PREPARE, goal)
    dialog = page.locator('#account-dialog')
    results = dialog.locator('#persons-relation-results button')

    # 1. 關係分頁：一開始沒有關係（共同紀錄不會自動建立），可以直接新增
    open_relations(page, ids['a'])
    expect(page.get_by_role('heading', name='人物關係（0）')).to_be_visible()
    expect(page.locator('.person-tab-panel a[href^="#person/"]')).to_have_count(0)  # 不需要回舊的關係頁
    page.get_by_role('button', name='＋ 新增關係').click()
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role('heading', name='新增人物關係')).to_be_visible()
    expect(dialog.get_by_text(HINT)).to_be_visible()
    expect(dialog.locator('input[name=relation_kind]')).to_have_count(12)
    expect(results).to_have_count(3)  # 孫策、同名的周瑜、諸葛亮；不含目前人物

    # 2. 搜尋式選擇器：同名人物靠類型與簡介分辨
    twin_option = search_and_pick(dialog, results, '周瑜', '虛構人物')
    expect(twin_option).to_contain_text('架空三國的現代企業家')
    shot(dialog, '01_selector_same_name.png')
    search_and_pick(dialog, results, '孫策', '孫策').click()
    expect(dialog.get_by_role('button', name='更換人物')).to_be_visible()
    expect(dialog.locator('.person-card')).to_contain_text('江東之主')

    # 3. 類型多選、共用描述、來源（只列與這兩位人物有關的我的紀錄）
    expect(dialog.locator('input[name=relation_source]')).to_have_count(2)
    dialog.locator('input[name=relation_source]').first.check()
    dialog.get_by_label('朋友', exact=True).check()
    dialog.get_by_label('同事', exact=True).check()
    dialog.locator('#persons-relation-description').fill('兩人共同平定江東，建立長期合作及信任關係。')
    shot(dialog, '02_new_relation_form.png')
    dialog.get_by_role('button', name='儲存關係').click()
    expect(dialog).to_be_hidden()
    expect(page.get_by_role('heading', name='人物關係（1）')).to_be_visible()
    card = card_of(page, '孫策')
    expect(card).to_contain_text('歷史人物')
    expect(card).to_contain_text('朋友')
    expect(card).to_contain_text('同事')
    expect(card).to_contain_text('兩人共同平定江東，建立長期合作及信任關係。')
    expect(card).to_contain_text('來源：1 筆我的紀錄')
    shot(page, '03_relations_tab_after_create.png')

    # 4. 雙方共用：孫策的人物頁看到同一段描述
    open_relations(page, ids['b'])
    expect(page.get_by_role('heading', name='孫策', exact=True)).to_be_visible()
    expect(card_of(page, '周瑜')).to_contain_text('兩人共同平定江東，建立長期合作及信任關係。')
    expect(card_of(page, '周瑜')).to_contain_text('歷史人物')
    shot(page, '04_other_person_sees_same_relation.png')

    # 5. 選到已有關係的人物：自動切換為編輯並載入原內容，不覆蓋
    open_relations(page, ids['a'])
    page.get_by_role('button', name='＋ 新增關係').click()
    search_and_pick(dialog, results, '孫策', '已有關係，選取後改為編輯').click()
    expect(dialog.get_by_role('heading', name='編輯人物關係')).to_be_visible()
    expect(dialog.get_by_text('已經有關係')).to_be_visible()
    expect(dialog.locator('#persons-relation-description')).to_have_value('兩人共同平定江東，建立長期合作及信任關係。')
    expect(dialog.get_by_label('朋友', exact=True)).to_be_checked()
    expect(dialog.locator('input[name=relation_source]:checked')).to_have_count(1)
    dialog.get_by_label('同事', exact=True).uncheck()
    dialog.get_by_label('師徒', exact=True).check()
    dialog.locator('#persons-relation-description').fill('兩人共同平定江東，情同手足。')
    shot(dialog, '05_existing_relation_switches_to_edit.png')
    dialog.get_by_role('button', name='儲存關係').click()
    expect(dialog).to_be_hidden()
    expect(page.get_by_role('heading', name='人物關係（1）')).to_be_visible()  # 沒有另外建立
    card = card_of(page, '孫策')
    expect(card).to_contain_text('兩人共同平定江東，情同手足。')
    expect(card).to_contain_text('師徒')
    expect(card).not_to_contain_text('同事')
    expect(card).to_contain_text('來源：1 筆我的紀錄')  # 只改描述與類型，原本的來源保留

    # 6. 卡片上的「編輯」：載入原資料（含已勾選的來源），取消不變更
    card.get_by_role('button', name='編輯').click()
    expect(dialog.locator('#persons-relation-description')).to_have_value('兩人共同平定江東，情同手足。')
    expect(dialog.locator('input[name=relation_source]')).to_have_count(2)
    expect(dialog.locator('input[name=relation_source]:checked')).to_have_count(1)
    expect(dialog.get_by_label('師徒', exact=True)).to_be_checked()
    shot(dialog, '05b_edit_from_card.png')
    dialog.get_by_role('button', name='取消').click()
    expect(dialog).to_be_hidden()
    expect(card_of(page, '孫策')).to_contain_text('兩人共同平定江東，情同手足。')

    # 7. 封存：不出現在預設列表；切換查看已封存；重新選到這位人物時提示並提供恢復
    card.get_by_role('button', name='封存').click()
    expect(page.get_by_role('heading', name='人物關係（0）')).to_be_visible()
    page.get_by_role('link', name='查看已封存的關係（1）').click()
    expect(page.get_by_role('heading', name='已封存的關係（1）')).to_be_visible()
    archived = card_of(page, '孫策')
    expect(archived.get_by_role('button', name='恢復')).to_be_visible()
    expect(archived.get_by_role('button', name='編輯')).to_have_count(0)  # 已封存的關係唯讀
    shot(page, '06_archived_relations.png')
    open_relations(page, ids['a'])
    page.get_by_role('button', name='＋ 新增關係').click()
    search_and_pick(dialog, results, '孫策', '已有關係（已封存）').click()
    expect(dialog.get_by_text('此關係已封存')).to_be_visible()
    expect(dialog.get_by_role('button', name='儲存關係')).to_have_count(0)
    shot(dialog, '07_archived_relation_offers_restore.png')
    dialog.get_by_role('button', name='恢復這段關係').click()
    expect(dialog).to_be_hidden()
    expect(page.get_by_role('heading', name='人物關係（1）')).to_be_visible()
    expect(card_of(page, '孫策')).to_contain_text('兩人共同平定江東，情同手足。')  # 恢復後內容不變
    expect(card_of(page, '孫策')).to_contain_text('來源：1 筆我的紀錄')

    # 8. 與同名人物建立關係；總覽顯示重要關係
    page.get_by_role('button', name='＋ 新增關係').click()
    search_and_pick(dialog, results, '周瑜', '虛構人物').click()
    expect(dialog.locator('.person-card')).to_contain_text('架空三國的現代企業家')
    dialog.get_by_label('對手', exact=True).check()
    dialog.get_by_role('button', name='儲存關係').click()
    expect(dialog).to_be_hidden()
    expect(page.get_by_role('heading', name='人物關係（2）')).to_be_visible()
    expect(cards(page).filter(has_text='虛構人物')).to_contain_text('對手')
    shot(page, '08_relations_tab_two_relations.png')
    page.goto(f"{BASE}/#persons/{ids['a']}")
    expect(page.locator(f'.person-tab-panel[data-person-view="{ids["a"]}"][data-tab="overview"]')).to_be_visible()
    expect(page.get_by_role('heading', name='重要關係')).to_be_visible()
    expect(page.locator('.person-tab-panel')).to_contain_text('孫策')
    shot(page, '09_overview_important_relations.png')

    # 9. 其中一位人物已封存：這段關係只能查看
    page.evaluate(ARCHIVE_PERSON, ids['twin'])
    open_relations(page, ids['a'])
    page.reload()
    locked = cards(page).filter(has_text='人物已封存')
    expect(locked).to_have_count(1)
    expect(locked.get_by_role('button')).to_have_count(0)
    expect(card_of(page, '孫策').get_by_role('button', name='編輯')).to_be_visible()
    shot(page, '10_archived_person_locks_relation.png')

    # 10. 資料確實在 Cloud SQL：重新整理後關係仍在，且沒有產生角色卡
    page.reload()
    expect(page.get_by_role('heading', name='人物關係（2）')).to_be_visible()
    relations = page.evaluate("id => fetch('/api/persons/' + id, {credentials: 'same-origin'}).then(r => r.json()).then(d => d.connections.map(x => [x.person.name, x.status, x.confirmation_status, x.relation_types.map(t => t.kind).join('+')]))", ids['a'])
    assert sorted(relations) == sorted([['孫策', 'active', 'confirmed', 'friend+mentor'], ['周瑜', 'active', 'confirmed', 'rival']]), relations
    assert re.search(r'#persons/[0-9a-f-]+\?tab=relations$', page.url)
