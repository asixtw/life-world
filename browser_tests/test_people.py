"""Screenshot-backed acceptance of the original W01/W02/Person 360 flows."""  # 說明此模組的責任與實作邊界
from uuid import uuid4  # 產生不依賴名稱的唯一識別碼

import pytest  # 使用測試資源、參數化及例外斷言
from playwright.sync_api import expect  # 以實際 Chromium 操作畫面並等待狀態斷言

from test_journey import BASE, ARTIFACTS, page, onboarding  # 載入此模組需要的相依工具


def seed(page):  # 建立隔離的虛構人物、目標、經歷與來源資料
    onboarding(page)  # 以真實瀏覽器完成首次旅程並檢查 Lumi 出現時機
    csrf = page.request.get(BASE + '/api/auth/me').json()['csrf_token']  # 透過實際測試用戶端操作 API 並保留回應
    claim = page.request.post(BASE + '/api/auth/claim', headers={'X-CSRF-Token':csrf},
        data={'username':'people_' + uuid4().hex[:12], 'password':'people-test-password-2026'})  # 透過實際測試用戶端操作 API 並保留回應
    assert claim.ok  # 斷言建立隔離的虛構人物、目標、經歷與來源資料的預期結果
    headers = {'X-CSRF-Token':claim.json()['csrf_token']}  # 保存「headers」供後續驗證或回傳使用
    goal = page.request.get(BASE + '/api/state').json()['goals'][0]  # 透過實際測試用戶端操作 API 並保留回應
    p = page.request.post(BASE + '/api/people', headers=headers, data={'name':'林先生','roles':['客戶','合作夥伴'],
        'tags':['音樂'],'category':'business','common_context':'創業交流會'}).json()  # 透過實際測試用戶端操作 API 並保留回應
    other = page.request.post(BASE + '/api/people', headers=headers, data={'name':'小雅','roles':['朋友'],'category':'life'}).json()  # 透過實際測試用戶端操作 API 並保留回應
    for name, role, category in [('陳小姐','合作夥伴','business'),('阿哲','朋友','life'),('周老師','學習導師','learning'),('林教練','訓練導師','learning')]:  # 逐項處理測試資料與預期結果
        assert page.request.post(BASE + '/api/people', headers=headers, data={'name':name,'roles':[role],'category':category}).ok  # 斷言建立隔離的虛構人物、目標、經歷與來源資料的預期結果
    receipts = []  # 保存「receipts」供後續驗證或回傳使用
    for i, kind in enumerate(['in_person','call']):  # 逐項處理測試資料與預期結果
        d = page.request.post(BASE + '/api/experiences/drafts', headers=headers, data={'raw_text':'林先生提到不太吃辣，並討論作品合作。',
            'occurred_at':f'2026-01-0{i+1}T12:00:00+08:00','person_id':p['id'],'goal_id':goal['id'],'contributions':[]}).json()  # 透過實際測試用戶端操作 API 並保留回應
        r = page.request.post(BASE + '/api/drafts/' + d['id'] + '/confirm', headers=headers, data={
            'request_id':str(uuid4()),'expected_revision':d['revision'],'summary':'討論作品合作與午餐偏好。','person_id':p['id'],
            'contributions':[],'tasks':['整理合作提案'],'interaction_type':kind})  # 透過實際測試用戶端操作 API 並保留回應
        assert r.ok, r.text()  # 斷言建立隔離的虛構人物、目標、經歷與來源資料的預期結果
        receipts.append(r.json())  # 將目前資料加入結果清單
    r = page.request.post(BASE + '/api/people/' + p['id'] + '/facts', headers=headers, data={
        'request_id':'food','dimension':'food','value':'不太吃辣','description':'本人在午餐時提到。','evidence_type':'stated_by_person',
        'source_experience_ids':[receipts[0]['experience_id']],'confirmed':True})  # 透過實際測試用戶端操作 API 並保留回應
    assert r.ok, r.text()  # 斷言建立隔離的虛構人物、目標、經歷與來源資料的預期結果
    page.request.post(BASE + '/api/people/' + p['id'] + '/goals', headers=headers, data={'request_id':'goal', 'goal_id':goal['id'],'label':'建立長期合作關係'})  # 透過實際測試用戶端操作 API 並保留回應
    page.request.post(BASE + '/api/people/' + p['id'] + '/connections', headers=headers, data={'request_id':'connection',
        'other_person_id':other['id'],'label':'共同參與創業交流會','source_experience_ids':[receipts[0]['experience_id']]})  # 透過實際測試用戶端操作 API 並保留回應
    page.reload()  # 執行此模組的共用工具操作
    expect(page.get_by_role('heading',name='測試小光，歡迎回來。')).to_be_visible()  # 等待並核對目前畫面狀態
    return p, other, goal  # 回傳後續測試步驟所需資料


def shot(page, name):  # 保存目前畫面的驗收截圖
    ARTIFACTS.mkdir(exist_ok=True, parents=True)  # 執行此模組的共用工具操作
    expect(page.locator('#toast')).not_to_have_class('visible')  # 等待並核對目前畫面狀態
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')  # 斷言保存目前畫面的驗收截圖的預期結果
    page.screenshot(path=str(ARTIFACTS / name), full_page=True)  # 保存畫面供原圖資訊層級比對


def expand(page, dimension):  # 展開指定的人物資訊維度
    panel = page.locator('[data-dimension="' + dimension + '"]')  # 保存「panel」供後續驗證或回傳使用
    if panel.get_attribute('open') is None:  # 依目前條件選擇下一步處理分支
        panel.locator('summary').click()  # 依使用者動線點擊畫面入口
    expect(panel).to_have_attribute('open', '')  # 等待並核對目前畫面狀態


@pytest.mark.parametrize('width',[390,1440])  # 以同一組斷言涵蓋多種正常、異常或邊界輸入
def test_original_people_flow_views_sources_and_context(page, width):  # 驗證：手機與桌面還原人物動線、來源及返回上下文
    errors=[]; page.on('pageerror',lambda e: errors.append(str(e)))  # 準備瀏覽器執行期間捕獲的 JavaScript 錯誤
    p, other, goal = seed(page)  # 建立隔離的虛構人物、目標、經歷與來源資料
    page.set_viewport_size({'width':width,'height':844 if width==390 else 1050})  # 切換驗收用手機或桌面視窗尺寸
    assert page.locator('#nav a').count() == 4  # 斷言手機與桌面還原人物動線、來源及返回上下文的預期結果
    expect(page.get_by_role('heading',name='旅途中遇見的人')).to_be_visible()  # 等待並核對目前畫面狀態
    expect(page.locator('#world-relationships')).not_to_contain_text('林先生')  # 等待並核對目前畫面狀態
    shot(page, f'people-{width}-world.png')  # 保存目前畫面的驗收截圖
    page.locator('#nav').get_by_role('link',name='關係',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('heading',name='我的人際關係')).to_be_visible()  # 等待並核對目前畫面狀態
    page.locator('[data-person="'+p['id']+'"]').first.click()  # 依使用者動線點擊畫面入口
    expect(page.locator('.person-summary')).to_contain_text('林先生')  # 等待並核對目前畫面狀態
    shot(page, f'people-{width}-star-all.png')  # 保存目前畫面的驗收截圖
    page.get_by_role('tab',name='收藏冊',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.locator('.person-card')).to_have_count(6)  # 等待並核對目前畫面狀態
    shot(page, f'people-{width}-cards-all.png')  # 保存目前畫面的驗收截圖
    page.get_by_role('tab',name='星圖',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('tab',name='星圖',exact=True)).to_have_attribute('aria-selected','true')  # 等待並核對目前畫面狀態
    page.locator('#people-query').fill('音樂')  # 填入此步驟的虛構表單內容
    page.locator('#people-filter-form').get_by_role('button',name='搜尋',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.locator('[data-person="'+p['id']+'"]').first).to_be_visible()  # 等待並核對目前畫面狀態
    page.locator('[data-person="'+p['id']+'"]').first.click()  # 依使用者動線點擊畫面入口
    expect(page.locator('.person-summary')).to_contain_text('創業交流會')  # 等待並核對目前畫面狀態
    page.get_by_role('button',name='設為關注',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('button',name='已關注',exact=True)).to_be_visible()  # 等待並核對目前畫面狀態
    shot(page, f'people-{width}-star.png')  # 保存目前畫面的驗收截圖
    page.get_by_role('tab',name='收藏冊',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.locator('#people-query')).to_have_value('音樂')  # 等待並核對目前畫面狀態
    expect(page.locator('.person-card.selected')).to_contain_text('林先生')  # 等待並核對目前畫面狀態
    shot(page, f'people-{width}-cards.png')  # 保存目前畫面的驗收截圖
    page.get_by_role('link',name='查看人物卡',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.locator('#person-profile')).to_be_visible()  # 等待並核對目前畫面狀態
    expect(page.get_by_role('tab',name='人物總覽',exact=True)).to_have_attribute('aria-selected','true')  # 等待並核對目前畫面狀態
    assert page.locator('.dimension').count() == 4  # 斷言手機與桌面還原人物動線、來源及返回上下文的預期結果
    expect(page.locator('[data-stat="meetings"]')).to_have_text('1')  # 等待並核對目前畫面狀態
    expect(page.locator('[data-stat="interactions"]')).to_have_text('2')  # 等待並核對目前畫面狀態
    expand(page, 'food')  # 展開指定的人物資訊維度
    expect(page.locator('[data-dimension="food"]')).to_contain_text('本人在午餐時提到。')  # 等待並核對目前畫面狀態
    shot(page, f'people-{width}-overview.png')  # 保存目前畫面的驗收截圖
    if width == 390:  # 依目前條件選擇下一步處理分支
        page.locator('[data-dimension=food]').evaluate("el => el.scrollIntoView({block:'center'})")  # 執行此模組的共用工具操作
        page.screenshot(path=str(ARTIFACTS / 'people-390-food-expanded-viewport.png'))  # 保存畫面供原圖資訊層級比對
    page.locator('[data-dimension="food"]').get_by_role('link',name='查看來源',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('heading',name='人物資訊的來源')).to_be_visible()  # 等待並核對目前畫面狀態
    expect(page.locator('.raw-source')).to_have_text('林先生提到不太吃辣，並討論作品合作。')  # 等待並核對目前畫面狀態
    shot(page, f'people-{width}-source.png')  # 保存目前畫面的驗收截圖
    page.get_by_role('link',name='返回人物總覽',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.locator('[data-dimension=food]')).to_have_attribute('open', '')  # 等待並核對目前畫面狀態
    page.get_by_role('tab',name='共同經歷',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.locator('.interaction-card')).to_have_count(2)  # 等待並核對目前畫面狀態
    shot(page, f'people-{width}-history.png')  # 保存目前畫面的驗收截圖
    page.get_by_role('tab',name='合作與目標',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.locator('#person-goals')).to_contain_text('第一個作品')  # 等待並核對目前畫面狀態
    expect(page.locator('#person-goals')).to_contain_text('整理合作提案')  # 等待並核對目前畫面狀態
    shot(page, f'people-{width}-goals.png')  # 保存目前畫面的驗收截圖
    page.locator('#person-goals').get_by_role('link',name='記錄這個目標的經歷').click()  # 依使用者動線點擊畫面入口
    expect(page.locator('#person-id')).to_have_value(p['id'])  # 等待並核對目前畫面狀態
    expect(page.locator('#goal-id')).to_have_value(goal['id'])  # 等待並核對目前畫面狀態
    page.get_by_role('link',name='返回人物頁',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('tab',name='合作與目標',exact=True)).to_have_attribute('aria-selected','true')  # 等待並核對目前畫面狀態
    page.get_by_role('link',name='開啟小劇場',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('heading',name='與林先生的小劇場')).to_be_visible()  # 等待並核對目前畫面狀態
    assert page.locator('.theater-mode').count() == 4  # 斷言手機與桌面還原人物動線、來源及返回上下文的預期結果
    page.get_by_role('link',name='情境演練',exact=True).click()  # 依使用者動線點擊畫面入口
    page.locator('#theater-title').fill('下一次見面')  # 填入此步驟的虛構表單內容
    page.locator('#theater-content').fill('這是自己的練習，不是真人發言。')  # 填入此步驟的虛構表單內容
    page.locator('[name=source_ids]').first.check()  # 明確勾選使用者確認欄位
    page.get_by_role('button',name='保存私人筆記',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.get_by_role('heading',name='下一次見面',exact=True)).to_be_visible()  # 等待並核對目前畫面狀態
    shot(page, f'people-{width}-theater.png')  # 保存目前畫面的驗收截圖
    world = page.request.get(BASE+'/api/state').json()  # 透過實際測試用戶端操作 API 並保留回應
    assert world['rewards']['total'] == 2 and len(world['experiences']) == 2  # 核對積分帳本符合本案例預期
    assert world['notes'][0]['person_id'] == p['id']  # 斷言手機與桌面還原人物動線、來源及返回上下文的預期結果
    assert len(world['notes'][0]['source_experience_ids']) == 1  # 斷言手機與桌面還原人物動線、來源及返回上下文的預期結果
    page.get_by_role('link',name='返回人物頁',exact=True).click()  # 依使用者動線點擊畫面入口
    page.get_by_role('link',name='返回關係',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.locator('#people-query')).to_have_value('音樂')  # 等待並核對目前畫面狀態
    expect(page.get_by_role('tab',name='收藏冊',exact=True)).to_have_attribute('aria-selected','true')  # 等待並核對目前畫面狀態
    assert errors == []  # 斷言手機與桌面還原人物動線、來源及返回上下文的預期結果


def test_person_fact_confirmation_classification_and_merge_ui(page):  # 驗證：透過畫面處理人物資訊、互動分類、合併與衝突
    p, _, _ = seed(page)  # 建立隔離的虛構人物、目標、經歷與來源資料
    page.goto(BASE+'/#person/'+p['id']+'?tab=history')  # 開啟隔離測試網站的指定頁面
    expect(page.locator('.interaction-card')).to_have_count(2)  # 等待並核對目前畫面狀態
    page.locator('[data-classify]').first.select_option('in_person')  # 選擇此案例需要的表單選項
    expect(page.locator('[data-stat=meetings]')).to_have_text('2')  # 等待並核對目前畫面狀態
    page.locator('[name=merge_sources]').nth(1).check()  # 明確勾選使用者確認欄位
    page.get_by_role('button',name='合併同一次互動',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.locator('.interaction-card')).to_have_count(1)  # 等待並核對目前畫面狀態
    expect(page.locator('[data-stat=meetings]')).to_have_text('1')  # 等待並核對目前畫面狀態
    page.get_by_role('tab',name='人物總覽',exact=True).click()  # 依使用者動線點擊畫面入口
    page.get_by_role('button',name='從已確認經歷新增資訊',exact=True).click()  # 依使用者動線點擊畫面入口
    page.locator('#fact-dimension').select_option('food')  # 選擇此案例需要的表單選項
    page.locator('#fact-value').fill('可以吃辣')  # 填入此步驟的虛構表單內容
    page.locator('#fact-description').fill('這次本人重新說明。')  # 填入此步驟的虛構表單內容
    page.locator('[name=source_ids]').first.check()  # 明確勾選使用者確認欄位
    page.locator('#fact-conflict').select_option(label='飲食偏好：不太吃辣')  # 選擇此案例需要的表單選項
    page.locator('[name=confirmed]').check()  # 明確勾選使用者確認欄位
    page.get_by_role('button',name='確認新增人物資訊',exact=True).click()  # 依使用者動線點擊畫面入口
    expand(page, 'food')  # 展開指定的人物資訊維度
    expect(page.locator('[data-dimension=food]')).to_contain_text('資訊有衝突，請確認')  # 等待並核對目前畫面狀態
    page.locator('[data-dimension=food] .fact-detail').filter(has_text='可以吃辣').get_by_role('button',name='採用這項資訊',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.locator('[data-dimension=food] .fact-detail')).to_have_count(1)  # 等待並核對目前畫面狀態
    expect(page.locator('[data-dimension=food]')).to_have_attribute('open', '')  # 等待並核對目前畫面狀態
    page.locator('[data-dimension=food]').get_by_role('link',name='查看來源',exact=True).click()  # 依使用者動線點擊畫面入口
    page.get_by_role('button',name='撤回此來源',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.locator('#person-profile')).to_be_visible()  # 等待並核對目前畫面狀態
    expect(page.locator('[data-dimension=food]')).to_contain_text('尚未了解')  # 等待並核對目前畫面狀態
    assert page.request.get(BASE+'/api/state').json()['rewards']['total'] == 2  # 核對積分帳本符合本案例預期


def test_editing_legacy_notes_does_not_split_existing_role(page):  # 驗證：只編輯備註時保留舊角色完整文字
    seed(page)  # 建立隔離的虛構人物、目標、經歷與來源資料
    csrf = page.request.get(BASE+'/api/auth/me').json()['csrf_token']  # 透過實際測試用戶端操作 API 並保留回應
    r = page.request.post(BASE+'/api/people', headers={'X-CSRF-Token':csrf},data={'name':'舊角色人物','role':'客戶、朋友','notes':'原備註'})  # 透過實際測試用戶端操作 API 並保留回應
    assert r.ok  # 斷言只編輯備註時保留舊角色完整文字的預期結果
    p = r.json()  # 準備目前人物的完整基本資料
    assert p['roles'] == ['客戶、朋友']  # 斷言只編輯備註時保留舊角色完整文字的預期結果
    page.goto(BASE+'/#person/'+p['id'])  # 開啟隔離測試網站的指定頁面
    page.get_by_role('button',name='編輯人物',exact=True).click()  # 依使用者動線點擊畫面入口
    page.locator('#person-notes').fill('只修改備註，角色不變。')  # 填入此步驟的虛構表單內容
    page.get_by_role('button',name='保存人物',exact=True).click()  # 依使用者動線點擊畫面入口
    expect(page.locator('#account-dialog')).not_to_be_visible()  # 等待並核對目前畫面狀態
    actual = page.request.get(BASE+'/api/people/'+p['id']+'/overview').json()['person']  # 透過實際測試用戶端操作 API 並保留回應
    assert actual['roles'] == ['客戶、朋友']  # 斷言只編輯備註時保留舊角色完整文字的預期結果
    assert actual['notes'] == '只修改備註，角色不變。'  # 斷言只編輯備註時保留舊角色完整文字的預期結果
