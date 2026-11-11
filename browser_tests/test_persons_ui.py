"""Unified Person 新人物系統的 Chrome 畫面驗收（第一、二階段），對象是 Local 8030 → Cloud SQL life_world_e2e。

只在明確開啟時執行（會在 life_world_e2e 建立 persons_ui_ 開頭的合成帳號與人物）：

    LW_E2E_PERSONS_UI=1 .venv\\Scripts\\python.exe -m pytest -q browser_tests/test_persons_ui.py

前提：含新人物系統的版本已部署到 e2e 標籤，/api/capabilities 的 unified_people 是 true，而且 Jerry 已同意在停寫期間做合成帳號驗收。
Playwright 的 Node 端解析不到 *.localhost，所以帳號準備在頁面內以同源 fetch 完成；密碼只在記憶體。
"""
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get('LIFEWORLD_TEST_URL', 'https://lw-core-compare.localhost:8030').rstrip('/')
pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS_UI') != '1', reason='部署後以 LW_E2E_PERSONS_UI=1 對 Local 8030（Cloud SQL E2E）執行')

SETUP = """async ({username, password, today, days, deadline}) => {
  const call = async (path, method, body, csrf) => {
    const r = await fetch('/api' + path, {method, credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', ...(csrf ? {'X-CSRF-Token': csrf} : {})}, body: body ? JSON.stringify(body) : undefined});
    const data = await r.json().catch(() => null);
    if (!r.ok) throw new Error(path + ' ' + r.status + ' ' + JSON.stringify(data));
    return data;
  };
  const capabilities = await call('/capabilities', 'GET');
  if (!capabilities.unified_people) throw new Error('unified_people is not enabled on this revision');
  let me = await call('/auth/guest', 'POST');
  me = await call('/auth/claim', 'POST', {username, password}, me.csrf_token);
  await call('/profile', 'PUT', {name: '人物驗收', bio: 'Cloud SQL E2E 合成帳號', timezone: 'Asia/Taipei'}, me.csrf_token);
  return await call('/goals', 'POST', {request_id: username + '-goal', title: '人物驗收', outcome: '確認新人物系統', deadline,
    actions: [['練習', '小時'], ['記錄', '篇'], ['交流', '次']].map(([title, unit], i) => ({title, unit, target: '3', level: i + 1, weekdays: [0, 2, 4], dates: days}))}, me.csrf_token);
}"""


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        chrome = Path(os.environ.get('ProgramFiles', '')) / 'Google/Chrome/Application/chrome.exe'
        browser = playwright.chromium.launch(headless=True, **({'executable_path': str(chrome)} if chrome.is_file() else {}))
        context = browser.new_context(viewport={'width': 1440, 'height': 1050}, locale='zh-TW')
        page = context.new_page()
        page.set_default_timeout(20000)
        yield page
        context.close()
        browser.close()


def synthetic_account(page):
    page.goto(BASE)
    today = datetime.now().date()
    goal = page.evaluate(SETUP, {'username': 'persons_ui_' + secrets.token_hex(5), 'password': 'Syn-' + secrets.token_hex(16),
                                 'today': today.isoformat(), 'days': [(today + timedelta(days=n)).isoformat() for n in (1, 3)],
                                 'deadline': (today + timedelta(days=60)).isoformat()})
    page.goto(BASE + '/#persons')
    page.reload()  # 只改 # 不會重新載入；重新整理後 App 才會讀到剛建立的登入狀態
    return goal  # 目標（含行動）：關係驗收建立我的紀錄時使用


def create_person(page, name, type_label, description, **extra):
    """單頁新增人物（規格 2.0）：同一張表單填基本資料、背景與世界觀、人物設定、其他人物資料，按一次「儲存人物」。"""
    page.get_by_role('link', name='新增人物').first.click()
    expect(page.get_by_role('heading', name='新增人物', exact=True)).to_be_visible()
    for title in ('01｜基本資料', '02｜背景與世界觀', '03｜人物設定', '04｜其他人物資料',
                  'A｜人物背景', 'B｜人格特質', 'C｜能力與知識', 'D｜行為與表達', 'E｜個人弱點'):
        expect(page.get_by_role('heading', name=title)).to_be_visible()
    page.locator('#person-name').fill(name)
    page.locator('#person-type').select_option(label=type_label)
    page.locator('#person-description').fill(description)
    for selector, value in extra.items():
        page.locator(selector).fill(value)
    page.get_by_role('button', name='儲存人物').click()
    expect(page.get_by_role('heading', name=name, exact=True)).to_be_visible()
    return page.url.split('#persons/')[1].split('?')[0]


def generate_ai(page, keep_background):
    """在編輯表單的「人物特質與設定」區塊用 AI 產生；只勾選部分欄位。Gemini 偶發 503 時照畫面提示重試（伺服器端也會自動重試一次）。"""
    page.locator('#persons-ai-fields input[value=background]').uncheck()  # 未勾選的欄位必須保留原內容
    page.locator('#persons-ai-guidance').fill('著重說話方式')
    page.locator('#persons-ai-consent').check()
    for attempt in range(1, 4):
        page.locator('#persons-ai-panel').get_by_role('button').click()
        expect(page.locator('#persons-ai-notice:not([hidden]), #notice:has-text("重新生成")').first).to_be_visible(timeout=90000)
        if page.locator('#persons-ai-notice').is_visible():
            break
        page.wait_for_timeout(10000)
    print(f'AI 產生嘗試次數：{attempt}')
    expect(page.locator('#persons-ai-notice')).to_be_visible()
    expect(page.locator('#profile-background')).to_have_value(keep_background)
    expect(page.locator('#profile-motivation')).not_to_have_value('')


def test_persons_list_create_profile_edit_archive(page):
    synthetic_account(page)
    expect(page.locator('#nav').get_by_role('link', name='人物', exact=True)).to_be_visible()
    expect(page.get_by_role('heading', name='人物', exact=True)).to_be_visible()

    first = create_person(page, '王小明', '虛構人物', '第一位王小明',
                          **{'#profile-background': '在台南長大', '#profile-personality': '溫和', '#person-notes': '人物備註甲',
                             '#person-common-context': '大學社團'})
    page.goto(BASE + '/#persons')
    second = create_person(page, '王小明', '虛構人物', '第一位王小明')  # 同名同內容：仍是另一筆人物
    assert first != second
    page.goto(BASE + '/#persons')
    expect(page.locator('.char-card', has_text='王小明')).to_have_count(2)

    page.goto(f'{BASE}/#persons/{first}?tab=profile')  # 新增時一次儲存的人物設定：第 1 版
    expect(page.get_by_text('第 1 版 ·')).to_be_visible()
    page.reload()
    expect(page.get_by_text('在台南長大')).to_be_visible()  # 回讀
    page.goto(f'{BASE}/#persons/{first}')
    expect(page.get_by_text('人物備註甲')).to_be_visible()
    expect(page.get_by_text('大學社團')).to_be_visible()

    page.goto(f'{BASE}/#persons-edit/{first}')  # 同一張表單編輯：基本資料、舊欄位、人物設定，一次儲存
    page.locator('#person-description').fill('改過的簡介')
    page.locator('#person-followed').check()
    page.locator('#profile-personality').fill('溫和但堅定')
    page.get_by_role('button', name='儲存人物').click()
    expect(page.get_by_text('改過的簡介').first).to_be_visible()
    expect(page.get_by_text('已關注').first).to_be_visible()
    page.goto(f'{BASE}/#persons/{first}?tab=profile')
    expect(page.get_by_text('第 2 版 ·')).to_be_visible()

    page.goto(f'{BASE}/#persons-edit/{first}')  # AI：只回填勾選的欄位，修改後儲存為新版本
    generate_ai(page, keep_background='在台南長大')
    page.locator('#profile-stance').fill('使用者自己改寫的立場')
    page.get_by_role('button', name='儲存人物').click()
    expect(page.get_by_role('heading', name='王小明', exact=True)).to_be_visible()
    page.goto(f'{BASE}/#persons/{first}?tab=profile')
    expect(page.get_by_text('第 3 版 · AI 產生後修改')).to_be_visible()
    expect(page.get_by_text('使用者自己改寫的立場')).to_be_visible()

    page.goto(f'{BASE}/#persons/{second}')
    expect(page.get_by_text('第一位王小明').first).to_be_visible()  # 另一位同名人物沒被改到
    page.goto(f'{BASE}/#persons/{second}?tab=profile')
    expect(page.get_by_text('尚未填寫人物設定。')).to_be_visible()

    page.goto(f'{BASE}/#persons/{first}')
    page.get_by_role('button', name='封存').click()
    expect(page.get_by_text('已封存').first).to_be_visible()
    page.goto(f'{BASE}/#persons-edit/{first}')  # 直接開啟已封存人物的編輯網址：沒有可提交的表單
    expect(page.get_by_text('這位人物已封存，不能修改。')).to_be_visible()
    expect(page.locator('#persons-edit-form')).to_have_count(0)
    page.goto(BASE + '/#persons')
    expect(page.locator('.char-card', has_text='王小明')).to_have_count(1)
    page.locator('select[name=status]').select_option('archived')
    page.get_by_role('button', name='套用').click()
    expect(page.locator('.char-card', has_text='王小明')).to_have_count(1)
    page.goto(f'{BASE}/#persons/{first}')
    page.get_by_role('button', name='恢復人物').click()
    page.goto(BASE + '/#persons')
    expect(page.locator('.char-card', has_text='王小明')).to_have_count(2)

    page.locator('#persons-q').fill('改過')
    page.get_by_role('button', name='套用').click()
    expect(page.locator('.char-card')).to_have_count(1)
    cards = page.evaluate("fetch('/api/characters?status=active',{credentials:'same-origin'}).then(r=>r.json()).then(d=>d.items.length)")
    assert cards == 0  # 人物設定不建立作品角色卡

    # 分頁：再建立 50 位，共 52 位 → 第 1 頁 50 位、第 2 頁 2 位；搜尋條件在翻頁時保留。
    page.evaluate(PAGE_FILL)
    page.goto(BASE + '/#persons')
    expect(page.get_by_text('共 52 位 · 第 1／2 頁')).to_be_visible()
    expect(page.locator('.char-card')).to_have_count(50)
    page.get_by_role('link', name='下一頁').click()
    expect(page.get_by_text('共 52 位 · 第 2／2 頁')).to_be_visible()
    expect(page.locator('.char-card')).to_have_count(2)
    page.get_by_role('link', name='上一頁').click()
    expect(page.get_by_text('共 52 位 · 第 1／2 頁')).to_be_visible()
    page.locator('#persons-q').fill('分頁')
    page.get_by_role('button', name='套用').click()
    expect(page.get_by_text('共 50 位 · 第 1／1 頁')).to_be_visible()
    expect(page.get_by_role('link', name='下一頁')).to_have_count(0)


PAGE_FILL = """async () => {
  const me = await fetch('/api/auth/me', {credentials: 'same-origin'}).then(r => r.json());
  for (let i = 0; i < 50; i++) {
    const r = await fetch('/api/persons', {method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token},
      body: JSON.stringify({request_id: 'page-' + i, name: '分頁人物' + String(i).padStart(2, '0')})});
    if (r.status !== 201) throw new Error('create ' + r.status);
  }
}"""
