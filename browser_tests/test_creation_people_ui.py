"""「作品 → 建立新作品」可以選人物的 Chrome 畫面驗收。對象是 Local 8030 → Cloud SQL life_world_e2e。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號）：

    LW_E2E_PERSONS_UI=1 .venv\\Scripts\\python.exe -m pytest -q browser_tests/test_creation_people_ui.py

這個環境的生成服務是真實模型，所以這個測試不按「開始生成」：驗收到「可以開始」為止，
另外從瀏覽器直接打 API 確認沒有人物設定的人物會被後端拒絕、沒有建立作品。

驗收順序：
1 作品 → ＋ 建立新作品 → 2 ① 人物先列「人物」，每位標出類型與人物設定版本 → 3 沒有人物設定的人物不能勾，並指向人物頁 →
4 搜尋人物 → 5 勾選兩位、取消「包含我」，人數與單人／多人的判斷跟著變 → 6 設定角色定位 → 7 填場景後「開始生成」可以按（不按）→
8 重新整理後草稿還在 → 9 繞過畫面直接送出沒有人物設定的人物，後端拒絕。
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
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token}, body: JSON.stringify({request_id: 'create-ui-' + key, ...body})});
    if (!r.ok) throw new Error('persons ' + r.status + ' ' + await r.text());
    return (await r.json()).id;
  };
  const profile = name => ({background: name + '的背景。', personality: '做事前先確認依據。', expression: '說話具體，常舉手邊的例子。'});
  for (let i = 1; i <= 7; i++) await person('extra' + i, {name: '路人' + i, person_subtype: 'original', description: '第 ' + i + ' 位陪襯人物。', profile: profile('路人' + i)});
  const hist = await person('hist', {name: '周瑜', person_subtype: 'historical', description: '東吳軍事統帥。'});          // 沒有人物設定：不能選
  await person('real', {name: '阿哲', roles: ['大學同學'], profile: profile('阿哲')});                                      // 真實人物、沒有簡介：顯示身分
  await person('wen', {name: '溫若岑', person_subtype: 'original', description: '願意讓手藝留下接縫。', profile: profile('溫若岑')});
  return hist;
}"""

BYPASS = """async (personId) => {  // 不經過畫面的勾選，直接送出沒有人物設定的人物
  const me = await fetch('/api/auth/me', {credentials: 'same-origin'}).then(r => r.json());
  const r = await fetch('/api/generation/runs', {method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token},
    body: JSON.stringify({request_id: 'create-ui-bypass', setup: {participants: [{source: 'person', ref: {person_id: personId}}], include_me: false,
      scene_context: {description: '繞過畫面的測試。'}, output: {type: 'text', text: {length: 'short', form: 'script'}}}})});
  const works = await fetch('/api/works?kind=generated_work', {credentials: 'same-origin'}).then(x => x.json());
  return {status: r.status, code: ((await r.json()).error || {}).code, works: works.total};
}"""


def shot(target, name):
    folder = os.environ.get('LW_E2E_SCREENSHOT_DIR')
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        target.screenshot(path=str(Path(folder) / name))


def choice(page, name):
    return page.locator('label.play-choice[data-person-choice]').filter(has=page.get_by_text(name, exact=True))


def test_create_a_work_by_picking_people(page):
    page.set_viewport_size({'width': 1440, 'height': 1500})
    synthetic_account(page)
    hist = page.evaluate(PEOPLE)

    # 1. 作品 → ＋ 建立新作品
    page.locator('#nav').get_by_role('link', name='作品').click()
    page.get_by_role('link', name='＋ 建立新作品').first.click()
    expect(page.get_by_role('heading', name='建立新作品')).to_be_visible()
    people = page.locator('fieldset', has=page.get_by_text('人物（可多選）', exact=True))

    # 2. ① 人物先列「人物」；每位標出類型與人物設定版本；補人物的入口是「人物」
    expect(people).to_be_visible()
    expect(choice(page, '溫若岑')).to_contain_text('虛構人物・人物設定第 1 版')
    expect(choice(page, '溫若岑')).to_contain_text('願意讓手藝留下接縫。')
    expect(choice(page, '阿哲')).to_contain_text('真實人物・人物設定第 1 版')
    expect(choice(page, '阿哲')).to_contain_text('大學同學')
    expect(page.get_by_role('link', name='前往人物 →')).to_be_visible()
    expect(page.get_by_text('我的角色卡（可多選）')).to_have_count(0)
    expect(page.get_by_text('舊角色卡')).to_have_count(0)  # 這個帳號沒有角色卡：不顯示舊角色卡區塊
    shot(page, 'create-01-people-list.png')

    # 3. 沒有人物設定的人物：列出但不能勾，並指向人物頁
    zhou = choice(page, '周瑜')
    expect(zhou).to_contain_text('歷史人物・還沒有人物設定')
    expect(zhou.locator('input[type=checkbox]')).to_be_disabled()
    expect(zhou.get_by_role('link', name='到人物頁填寫人物設定 →')).to_have_attribute('href', '#persons/' + hist)

    # 4. 搜尋人物（超過 8 位才出現搜尋框）
    search = page.get_by_label('搜尋人物')
    search.fill('溫')
    expect(choice(page, '溫若岑')).to_be_visible()
    expect(choice(page, '路人1')).to_be_hidden()
    search.fill('')
    expect(choice(page, '路人1')).to_be_visible()

    # 5. 「包含我」預設勾選但這個帳號還沒有我的設定；取消後勾選人物，人數與單人／多人的判斷跟著變
    expect(page.get_by_text('AI 參與人物：1 位')).to_be_visible()
    page.get_by_role('checkbox', name='包含我').uncheck()
    expect(page.get_by_text('請在 ① 人物至少選擇 1 位（人物或「包含我」）。')).to_be_visible()
    choice(page, '溫若岑').locator('input[type=checkbox]').check()
    expect(page.get_by_text('AI 參與人物：1 位（單人文字）')).to_be_visible()
    choice(page, '阿哲').locator('input[type=checkbox]').check()
    expect(page.get_by_text('AI 參與人物：2 位（多人文字）')).to_be_visible()

    # 6. 角色定位：人物也可以設定
    page.get_by_role('button', name='角色定位（選用）').click()
    page.get_by_label('溫若岑的角色定位').select_option(label='配角')
    shot(page, 'create-02-two-people-picked.png')

    # 7. 填場景；開始生成區列出兩位人物，按鈕可以按（這裡不按：這個環境會呼叫真實模型）
    page.get_by_role('button', name='下一步：場景').click()
    page.locator('#create-scene').fill('週六午後，虛構的社區展覽試作桌。兩人初次見面。')
    start = page.locator('.create-start')
    expect(start).to_contain_text('溫若岑、阿哲（2 位）')
    expect(start).to_contain_text('自動判斷：多人文字（2 位）')
    expect(start.get_by_role('button', name='開始生成')).to_be_enabled()
    shot(page, 'create-03-ready-to-start.png')

    # 8. 重新整理：草稿還在（同一個分頁、同一個帳號）
    page.reload()
    expect(page.get_by_role('heading', name='建立新作品')).to_be_visible()
    expect(page.locator('.create-start')).to_contain_text('溫若岑、阿哲（2 位）')
    page.get_by_role('button', name='① 人物').click()
    expect(choice(page, '溫若岑').locator('input[type=checkbox]')).to_be_checked()
    expect(choice(page, '阿哲').locator('input[type=checkbox]')).to_be_checked()
    expect(page.get_by_label('溫若岑的角色定位')).to_have_value('supporting')

    # 9. 繞過畫面：沒有人物設定的人物由後端拒絕，沒有建立作品
    assert page.evaluate(BYPASS, hist) == {'status': 409, 'code': 'person_profile_required', 'works': 0}
    shot(page, 'create-04-after-reload.png')
