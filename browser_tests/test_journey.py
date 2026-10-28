"""Actual Chromium journeys; run explicitly against an isolated local server."""  # 說明此模組的責任與實作邊界
import base64  # 解碼虛構的測試圖片
import os  # 讀取資料目錄或測試網址等環境設定
from pathlib import Path  # 以跨平台方式組合檔案路徑
from uuid import uuid4  # 產生不依賴名稱的唯一識別碼

import pytest  # 使用測試資源、參數化及例外斷言
from playwright.sync_api import sync_playwright, expect  # 以實際 Chromium 操作畫面並等待狀態斷言

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGNkaGBgYGBgYmBgYGBgAAAGKgCE5tEtPAAAAABJRU5ErkJggg==')  # 準備供上傳驗收使用的有效虛構圖片
BASE = os.environ.get('LIFEWORLD_TEST_URL', 'http://127.0.0.1:8001')  # 透過實際測試用戶端操作 API 並保留回應
ARTIFACTS = Path(__file__).resolve().parent.parent / 'docs' / 'artifacts' / 'connections' / 'regression'  # 準備手機與桌面驗收截圖的輸出目錄


@pytest.fixture  # 註冊可由 pytest 注入並清理的測試資源
def page():  # 啟動隔離 Chromium 視窗並於測試後關閉
    with sync_playwright() as p:  # 以區塊生命週期確保資源在結束時關閉
        browser = p.chromium.launch(headless=True)  # 準備本次實際啟動的 Chromium 瀏覽器
        context = browser.new_context(viewport={'width': 1440, 'height': 1050}, locale='zh-TW')  # 準備不共用 Cookie 的瀏覽器測試環境
        page = context.new_page()  # 準備本次驗收使用的瀏覽器分頁
        page.set_default_timeout(10000)  # 執行此模組的共用工具操作
        yield page  # 提供區塊或測試使用的資源，之後繼續清理
        context.close()  # 關閉已使用完畢的資源
        browser.close()  # 關閉已使用完畢的資源


def create_goal(page, title):  # 透過畫面填寫三項行動並建立目標
    page.locator('#goal-title').fill(title)  # 填入此步驟的虛構表單內容
    page.locator('#outcome').fill('完成一個自己的作品，並提供照片佐證。')  # 填入此步驟的虛構表單內容
    for i, (action, unit) in enumerate([('練習', '小時'), ('記錄', '篇'), ('交流', '次')]):  # 逐項處理測試資料與預期結果
        page.locator('#action-title-' + str(i)).fill(action)  # 填入此步驟的虛構表單內容
        page.locator('#target-' + str(i)).fill('10')  # 填入此步驟的虛構表單內容
        page.locator('#unit-' + str(i)).fill(unit)  # 填入此步驟的虛構表單內容
    page.get_by_role('button', name='確認設定，建立目標蛋').click()  # 依使用者動線點擊畫面入口


def onboarding(page):  # 以真實瀏覽器完成首次旅程並檢查 Lumi 出現時機
    page.goto(BASE)  # 開啟隔離測試網站的指定頁面
    expect(page.get_by_role('heading', name='把每一步，種成自己的世界。')).to_be_visible()  # 等待並核對目前畫面狀態
    expect(page.locator('.lumi')).to_have_count(0)  # 等待並核對目前畫面狀態
    page.get_by_role('button', name='不用註冊，先開始').click()  # 依使用者動線點擊畫面入口
    page.locator('#profile-name').fill('測試小光')  # 填入此步驟的虛構表單內容
    page.locator('#bio').fill('以真實的一小步，建立自己的世界。')  # 填入此步驟的虛構表單內容
    page.get_by_role('button', name='接著，建立第一個目標').click()  # 依使用者動線點擊畫面入口
    expect(page.locator('#goal-form')).to_be_visible()  # 等待並核對目前畫面狀態
    expect(page.locator('.lumi')).to_have_count(0)  # 等待並核對目前畫面狀態
    create_goal(page, '第一個作品')  # 在同一交易建立目標、行動並孵化 Lumi
    expect(page.get_by_role('heading', name='目標蛋誕生了。 你好，我是 Lumi。')).to_be_visible()  # 等待並核對目前畫面狀態
    page.get_by_role('link', name='進入我的世界').click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('heading', name='測試小光，歡迎回來。')).to_be_visible()  # 等待並核對目前畫面狀態


def new_record(page):  # 經由紀錄主分頁進入新經歷表單
    page.locator('#nav').get_by_role('link', name='紀錄', exact=True).click()  # 依使用者動線點擊畫面入口
    page.get_by_role('link', name='新的經歷').click()  # 依使用者動線點擊畫面入口


def test_complete_browser_journey_with_upgrade_preserves_selected_goal_and_contribution(page):  # 驗證：真實瀏覽器完成升級旅程並保留所選目標與貢獻
    errors = []  # 準備瀏覽器執行期間捕獲的 JavaScript 錯誤
    page.on('pageerror', lambda error: errors.append(str(error)))  # 將目前資料加入結果清單
    onboarding(page)  # 以真實瀏覽器完成首次旅程並檢查 Lumi 出現時機
    page.locator('#nav').get_by_role('link', name='目標', exact=True).click()  # 依使用者動線點擊畫面入口
    page.get_by_role('link', name='新的目標').click()  # 依使用者動線點擊畫面入口
    create_goal(page, '第二個作品')  # 在同一交易建立目標、行動並孵化 Lumi
    expect(page.get_by_role('heading', name='第二個作品')).to_be_visible()  # 等待並核對目前畫面狀態
    goals = page.request.get(BASE + '/api/state').json()['goals']  # 透過實際測試用戶端操作 API 並保留回應
    goal = next(g for g in goals if g['title'] == '第二個作品')  # 準備目前選定的目標資料
    action_id = goal['actions'][0]['id']  # 保存「action_id」供後續驗證或回傳使用
    new_record(page)  # 經由紀錄主分頁進入新經歷表單
    page.locator('#goal-id').select_option(goal['id'])  # 選擇此案例需要的表單選項
    page.locator('#raw-text').fill('這一份原文，需要在升級帳號後完整保留。')  # 填入此步驟的虛構表單內容
    page.locator('#occurred-at').fill('2001-01-01T23:50')  # 填入此步驟的虛構表單內容
    page.locator('#quantity-' + action_id).fill('0.25')  # 填入此步驟的虛構表單內容
    page.get_by_role('button', name='新增人物').click()  # 依使用者動線點擊畫面入口
    page.locator('#username').fill('browser_' + uuid4().hex[:12])  # 填入此步驟的虛構表單內容
    page.locator('#password').fill('browser-test-password-2026')  # 填入此步驟的虛構表單內容
    page.get_by_role('button', name='建立帳號，繼續原本的操作').click()  # 依使用者動線點擊畫面入口
    expect(page.locator('#account-dialog')).not_to_be_visible()  # 等待並核對目前畫面狀態
    expect(page.locator('#raw-text')).to_have_value('這一份原文，需要在升級帳號後完整保留。')  # 等待並核對目前畫面狀態
    expect(page.locator('#occurred-at')).to_have_value('2001-01-01T23:50')  # 等待並核對目前畫面狀態
    expect(page.locator('#goal-id')).to_have_value(goal['id'])  # 等待並核對目前畫面狀態
    expect(page.locator('#quantity-' + action_id)).to_have_value('0.25')  # 等待並核對目前畫面狀態
    page.get_by_role('button', name='新增人物').click()  # 依使用者動線點擊畫面入口
    page.locator('#person-name').fill('虛構的同行朋友')  # 填入此步驟的虛構表單內容
    page.locator('#person-role').fill('一起創作')  # 填入此步驟的虛構表單內容
    page.get_by_role('button', name='保存人物').click()  # 依使用者動線點擊畫面入口
    expect(page.locator('#quantity-' + action_id)).to_have_value('0.25')  # 等待並核對目前畫面狀態
    page.get_by_role('button', name='保存草稿並進入核對').click()  # 依使用者動線點擊畫面入口
    expect(page.locator('#review-form')).to_be_visible()  # 等待並核對目前畫面狀態
    page.locator('#summary').fill('由我確認的四分之一小時練習。')  # 填入此步驟的虛構表單內容
    page.locator('#followups').fill('明天再練習')  # 填入此步驟的虛構表單內容
    page.get_by_role('button', name='我已核對，確認保存').click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_text('由我確認的四分之一小時練習。', exact=True)).to_be_visible()  # 等待並核對目前畫面狀態
    world = page.request.get(BASE + '/api/state').json()  # 透過實際測試用戶端操作 API 並保留回應
    assert world['rewards']['total'] == 1  # 核對積分帳本符合本案例預期
    assert next(g for g in world['goals'] if g['id'] == goal['id'])['actions'][0]['progress'] == '0.25'  # 斷言真實瀏覽器完成升級旅程並保留所選目標與貢獻的預期結果
    assert world['experiences'][0]['person_id'] == world['people'][0]['id']  # 斷言真實瀏覽器完成升級旅程並保留所選目標與貢獻的預期結果
    new_record(page)  # 經由紀錄主分頁進入新經歷表單
    expect(page.locator('#raw-text')).to_have_value('')  # 等待並核對目前畫面狀態
    page.locator('#nav').get_by_role('link', name='目標', exact=True).click()  # 依使用者動線點擊畫面入口
    page.locator('a[href="#goal/' + goal['id'] + '"]').click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('button', name='確認完成並收藏成果')).to_be_disabled()  # 等待並核對目前畫面狀態
    page.locator('#evidence-file').set_input_files({'name':'作品.png','mimeType':'image/png','buffer':PNG})  # 執行此模組的共用工具操作
    page.get_by_role('button', name='上傳佐證').click()  # 依使用者動線點擊畫面入口
    expect(page.locator('.photo-grid img')).to_have_count(1)  # 等待並核對目前畫面狀態
    page.locator('[name=confirmed]').check()  # 明確勾選使用者確認欄位
    page.locator('#reflection').fill('已達成自己的作品成果。')  # 填入此步驟的虛構表單內容
    page.get_by_role('button', name='確認完成並收藏成果').click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('heading', name='這段成果，已經收藏。')).to_be_visible()  # 等待並核對目前畫面狀態
    page.locator('#nav').get_by_role('link', name='紀錄', exact=True).click()  # 依使用者動線點擊畫面入口
    page.get_by_role('link', name='私人筆記／草稿箱', exact=True).click()  # 依使用者動線點擊畫面入口
    page.locator('#note-kind').select_option('simulation')  # 選擇此案例需要的表單選項
    page.locator('#note-title').fill('下一次見面的練習')  # 填入此步驟的虛構表單內容
    page.locator('#note-content').fill('這是模擬，不是真人發言。')  # 填入此步驟的虛構表單內容
    page.get_by_role('button', name='保存私人筆記').click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('heading', name='下一次見面的練習')).to_be_visible()  # 等待並核對目前畫面狀態
    assert page.request.get(BASE + '/api/state').json()['rewards']['total'] == 1  # 核對積分帳本符合本案例預期
    page.locator('#nav').get_by_role('link', name='世界', exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('heading', name='測試小光，歡迎回來。')).to_be_visible()  # 等待並核對目前畫面狀態
    expect(page.locator('#toast')).not_to_have_class('visible')  # 等待並核對目前畫面狀態
    ARTIFACTS.mkdir(parents=True, exist_ok=True)  # 執行此模組的共用工具操作
    page.screenshot(path=str(ARTIFACTS / 'desktop-world.png'), full_page=True)  # 保存畫面供原圖資訊層級比對
    page.set_viewport_size({'width':390,'height':844})  # 切換驗收用手機或桌面視窗尺寸
    expect(page.get_by_role('heading', name='測試小光，歡迎回來。')).to_be_visible()  # 等待並核對目前畫面狀態
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')  # 斷言真實瀏覽器完成升級旅程並保留所選目標與貢獻的預期結果
    page.screenshot(path=str(ARTIFACTS / 'mobile-world.png'), full_page=True)  # 保存畫面供原圖資訊層級比對
    assert errors == []  # 斷言真實瀏覽器完成升級旅程並保留所選目標與貢獻的預期結果


def test_saved_draft_survives_refresh_and_logout_login(page):  # 驗證：瀏覽器刷新及登出登入後草稿仍在
    onboarding(page)  # 以真實瀏覽器完成首次旅程並檢查 Lumi 出現時機
    new_record(page)  # 經由紀錄主分頁進入新經歷表單
    page.locator('#raw-text').fill('先保存，稍後再確認。')  # 填入此步驟的虛構表單內容
    page.get_by_role('button', name='先存草稿').click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('link', name='繼續核對')).to_be_visible()  # 等待並核對目前畫面狀態
    page.reload()  # 執行此模組的共用工具操作
    expect(page.get_by_role('link', name='繼續核對')).to_be_visible()  # 等待並核對目前畫面狀態
    page.locator('#account-button').click()  # 依使用者動線點擊畫面入口
    page.get_by_role('button', name='建立帳號，保存世界').click()  # 依使用者動線點擊畫面入口
    username = 'return_' + uuid4().hex[:12]  # 保存「username」供後續驗證或回傳使用
    page.locator('#username').fill(username)  # 填入此步驟的虛構表單內容
    page.locator('#password').fill('return-password-2026')  # 填入此步驟的虛構表單內容
    page.get_by_role('button', name='建立帳號，繼續原本的操作').click()  # 依使用者動線點擊畫面入口
    expect(page.locator('#account-dialog')).not_to_be_visible()  # 等待並核對目前畫面狀態
    page.locator('#account-button').click()  # 依使用者動線點擊畫面入口
    page.get_by_role('button', name='登出', exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('button', name='登入我的世界')).to_be_visible()  # 等待並核對目前畫面狀態
    page.get_by_role('button', name='登入我的世界').click()  # 依使用者動線點擊畫面入口
    page.locator('#username').fill(username)  # 填入此步驟的虛構表單內容
    page.locator('#password').fill('return-password-2026')  # 填入此步驟的虛構表單內容
    page.locator('#login-form').get_by_role('button', name='登入我的世界', exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('heading', name='測試小光，歡迎回來。')).to_be_visible()  # 等待並核對目前畫面狀態
    page.locator('#nav').get_by_role('link', name='紀錄', exact=True).click()  # 依使用者動線點擊畫面入口
    page.get_by_role('link', name='繼續核對').click()  # 依使用者動線點擊畫面入口
    expect(page.locator('.raw-source')).to_have_text('先保存，稍後再確認。')  # 等待並核對目前畫面狀態
    assert page.request.get(BASE + '/api/state').json()['rewards']['total'] == 0  # 核對積分帳本符合本案例預期


def test_unsaved_record_can_be_saved_before_navigation(page):  # 驗證：切頁前可先保存未送出的經歷
    onboarding(page)  # 以真實瀏覽器完成首次旅程並檢查 Lumi 出現時機
    new_record(page)  # 經由紀錄主分頁進入新經歷表單
    page.locator('#raw-text').fill('導覽離開前，這段原文需要先保存。')  # 填入此步驟的虛構表單內容
    page.locator('#nav').get_by_role('link', name='目標', exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('heading', name='離開前，留住這段內容。')).to_be_visible()  # 等待並核對目前畫面狀態
    page.get_by_role('button', name='先存草稿並離開').click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('heading', name='照顧你的目標花園。')).to_be_visible()  # 等待並核對目前畫面狀態
    page.locator('#nav').get_by_role('link', name='紀錄', exact=True).click()  # 依使用者動線點擊畫面入口
    page.get_by_role('link', name='繼續核對').click()  # 依使用者動線點擊畫面入口
    expect(page.locator('.raw-source')).to_have_text('導覽離開前，這段原文需要先保存。')  # 等待並核對目前畫面狀態
