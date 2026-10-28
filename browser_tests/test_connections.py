"""交會取代星圖後的真實手機／桌面旅程。"""  # 不使用固定示例畫面冒充正式資料
from pathlib import Path  # 讓交會截圖與舊驗收圖片分開
from uuid import uuid4  # 產生隔離測試帳號與提交 ID
import pytest  # 參數化不同裝置尺寸
from playwright.sync_api import expect  # 對真實 Chromium 畫面斷言
from test_journey import BASE, page, onboarding  # 沿用已驗證的首次旅程及隔離視窗


def seed_stories(page):  # 建立真實 API 的虛構故事路徑
    onboarding(page)  # 確認第一個目標後才出現世界
    csrf = page.request.get(BASE + '/api/auth/me').json()['csrf_token']  # 取得目前安全驗證
    claim = page.request.post(BASE + '/api/auth/claim', headers={'X-CSRF-Token': csrf}, data={'username': 'cx_' + uuid4().hex[:12], 'password': 'connections-test-2026'})  # 保留原世界並升級
    assert claim.ok, claim.text()  # 前置失敗不可當功能成功
    headers = {'X-CSRF-Token': claim.json()['csrf_token']}  # 使用輪換後 CSRF
    people = [page.request.post(BASE + '/api/people', headers=headers, data={'name': n, 'roles': [r]}).json() for n, r in [('小安', '朋友'), ('怡君', '攝影朋友'), ('怡君', '工作夥伴'), ('阿哲', '同學')]]  # 以角色區分同名候選
    receipts = []  # 保存每份正式故事 ID
    for i, (title, raw, ids, mention) in enumerate([('那天的午餐', '今天與小安吃飯，小安提到怡君。', [0, 3], True), ('河邊的攝影散步', '和怡君一起在河邊拍照。', [1], False), ('下次一起看海', '小安和阿哲一起去看海。', [0, 3], False)]):  # 多個故事可由人物自然延伸
        story = {'title': title, 'participants': [{'person_id': people[j]['id'], 'interacted': True} for j in ids], 'mentions': []}  # 明確核對參與與互動
        if mention: story['mentions'] = [{'name': '怡君', 'start': raw.index('怡君'), 'end': raw.index('怡君') + 2}]  # 未配對同名提及
        d = page.request.post(BASE + '/api/experiences/drafts', headers=headers, data={'raw_text': raw, 'occurred_at': f'2026-01-0{i + 1}T12:00:00+08:00', 'story': story}).json()  # 保存候選草稿
        response = page.request.post(BASE + '/api/drafts/' + d['id'] + '/confirm', headers=headers, data={'request_id': str(uuid4()), 'expected_revision': d['revision'], 'summary': raw, 'story': story, 'story_reviewed': True, 'interaction_type': 'in_person'})  # 由人工確認交易建立正式來源
        assert response.ok, response.text()  # 必須真的保存成功
        receipts.append(response.json())  # 保留原文與事件 ID
    page.reload()  # 排除初始化舊狀態
    expect(page.get_by_role('heading', name='測試小光，歡迎回來。')).to_be_visible()  # 等待世界載入
    return people, receipts  # 提供旅程目標


def screenshot(page, name):  # 保存本輪獨立的虛構畫面證據
    folder = Path(__file__).resolve().parent.parent / 'docs' / 'artifacts' / 'connections'  # 與先前星圖驗收分開
    folder.mkdir(parents=True, exist_ok=True)  # 建立截圖目錄
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')  # 不容許手機橫向溢位
    page.screenshot(path=str(folder / name), full_page=True)  # 保留故事與來源資訊層級


@pytest.mark.parametrize('width', [390, 1440])  # 手機與桌面使用相同規則
def test_connections_source_matching_persistence_and_return(page, width):  # 正常：來源配對、延伸與返回都使用正式資料
    errors = []; page.on('pageerror', lambda e: errors.append(str(e)))  # 監測前端執行錯誤
    people, receipts = seed_stories(page)  # 建立可延伸故事
    page.set_viewport_size({'width': width, 'height': 844 if width == 390 else 1050})  # 檢查原型規格尺寸
    page.locator('#nav').get_by_role('link', name='關係', exact=True).click()  # 從四主導覽進入交會
    expect(page.locator('#connections-explorer')).to_be_visible()  # 星圖已由交會取代
    expect(page.get_by_role('tab', name='星圖', exact=True)).to_have_count(0)  # 不再並列舊星圖
    page.goto(BASE + '/#people?story=' + receipts[0]['experience_id'] + '&focus=' + people[0]['id'])  # 從指定真實故事繼續探索
    expect(page.locator('#connection-story')).to_contain_text('那天的午餐')  # 中央是事件而非人物清單
    screenshot(page, f'{width}-story.png')  # 保存主要故事畫面
    page.get_by_role('button', name='查看怡君的提及來源', exact=True).click()  # 點原文線索，不直接跳人物
    expect(page.locator('#source-dialog mark')).to_have_text('怡君')  # 來源精確定位此處提及
    expect(page.locator('#source-dialog')).to_contain_text('待核對人物')  # 尚未確認同名身分
    page.get_by_role('button', name='核對人物', exact=True).click()  # 明確進入人工核對
    page.locator('#match-person').select_option(people[1]['id'])  # 人工選正確的同名者
    page.locator('#mention-match-form [name=confirmed]').check()  # 配對與參與分開明確確認，不繞過驗收門檻
    page.get_by_role('button', name='確認對應人物', exact=True).click()  # 保存正式配對
    expect(page.locator('#source-dialog')).to_contain_text('已配對')  # 只有 API 成功後才顯示已保存
    screenshot(page, f'{width}-source.png')  # 保存來源與身分界線
    page.get_by_role('button', name='探索怡君的故事', exact=True).click()  # 配對後延伸另一段實際參與故事
    expect(page.locator('#connection-story')).to_contain_text('河邊的攝影散步')  # 不把她加進原午餐
    expect(page.locator('.connection-origin')).to_contain_text('不代表參與原故事')  # 保持線索種類
    page.get_by_role('button', name='上一步', exact=True).click()  # 返回來源故事
    expect(page.locator('#connection-story')).to_contain_text('那天的午餐')  # 返回正確事件
    page.reload()  # 排除僅頁面暫存的配對
    page.get_by_role('button', name='查看怡君的提及來源', exact=True).click()  # 重新查伺服器來源
    expect(page.locator('#source-dialog')).to_contain_text('已配對')  # 配對仍在
    page.get_by_role('button', name='關閉來源', exact=True).click()  # 返回當前閱讀位置
    page.get_by_role('tab', name='收藏冊', exact=True).click()  # 找人物而非探索故事
    page.locator('#people-query').fill('小安')  # 使用既有姓名搜尋
    page.get_by_role('button', name='搜尋', exact=True).click()  # 確認條件
    page.get_by_role('button', name='選取小安', exact=True).click()  # 顯示人物摘要
    page.get_by_role('link', name='查看人物卡', exact=True).click()  # 與既有完整人物流程連通
    expect(page.locator('#person-profile')).to_contain_text('小安')  # 人物頁可操作
    page.get_by_role('link', name='返回關係', exact=True).click()  # 返回原收藏冊條件
    expect(page.locator('#people-query')).to_have_value('小安')  # 條件未遺失
    assert page.request.get(BASE + '/api/state').json()['rewards']['total'] == 3  # 配對與探索不發分
    assert errors == []  # 全旅程不得有 JavaScript 例外


def test_story_editor_draft_correction_withdrawal_and_restore(page):  # 邊界：透過 UI 確認人物、更正與撤回來源
    people, receipts = seed_stories(page)  # 使用既有人物與真實來源
    page.goto(BASE + '/#record')  # 新經歷沿用既有表單
    page.locator('#raw-text').fill('🌱今天與小安散步，提到怡君。')  # 包含 emoji 的原文
    page.locator('#include-story').check()  # 明確選擇整理故事人物
    page.locator('[name=story_participant][value="' + people[0]['id'] + '"]').check()  # 選參與者
    page.locator('[name=story_interacted][value="' + people[0]['id'] + '"]').check()  # 分開確認直接互動
    page.locator('#story-title').fill('午後散步')  # 顯示使用者的標題
    page.get_by_role('button', name='新增提及', exact=True).click()  # 保留尚未配對的原名
    page.locator('[name=mention_name]').fill('怡君')  # 指定原文出現名字
    page.locator('[name=mention_name]').blur()  # 產生可選原文位置
    page.get_by_role('button', name='保存草稿並進入核對').click()  # 草稿需真的保存
    expect(page.locator('#story-title')).to_have_value('午後散步')  # 候選資料可回讀
    page.locator('#story-reviewed').check()  # 角色需明確審閱後才入正式探索
    page.get_by_role('button', name='我已核對，確認保存', exact=True).click()  # 原子保存原文與角色
    expect(page.get_by_role('heading', name='收藏每一段真實。')).to_be_visible()  # 等待完成後頁面，不能把核對頁同一段原文當成功
    expect(page.get_by_text('🌱今天與小安散步，提到怡君。', exact=True).first).to_be_visible()  # 完成正式確認
    world = page.request.get(BASE + '/api/state').json()  # 核對伺服器結果
    x = next(x for x in world['experiences'] if '🌱' in x['raw_text'])  # 定位新資料
    page.goto(BASE + '/#people?story=' + x['id'])  # 正式交會可探索
    expect(page.locator('#connection-story')).to_contain_text('午後散步')  # 正式標題保存
    page.get_by_role('button', name='查看完整來源', exact=True).click()  # 本人可管理來源
    page.get_by_role('button', name='撤回交會展示', exact=True).click()  # 撤回派生探索，不刪原文
    expect(page.locator('#source-dialog')).to_contain_text('已撤回交會展示')  # 有明確成功回饋
    page.get_by_role('button', name='恢復交會展示', exact=True).click()  # 必須能恢復本人資料
    expect(page.locator('#source-dialog')).to_contain_text('使用者已審閱')  # 恢復正式展示
    assert page.request.get(BASE + '/api/state').json()['rewards']['total'] == 4  # 往返管理不發新分


def test_review_edits_survive_return_and_slow_source_failure(page):  # 體驗：核對返回不丟摘要，來源失敗有退路
    people, receipts = seed_stories(page)  # 建立來源與帳號
    page.goto(BASE + '/#record')  # 新增原文
    page.locator('#raw-text').fill('核對返回測試原文。')  # 保存待確認內容
    page.get_by_role('button', name='保存草稿並進入核對').click()  # 進入人工核對
    page.locator('#summary').fill('我改過的摘要')  # 人工修改不能因返回丟失
    page.locator('#followups').fill('我留下的下一步')  # 任務也應保存暫存
    page.get_by_role('button', name='返回修改原始草稿', exact=True).click()  # 允許回頭檢查原始文字
    expect(page.locator('#raw-text')).to_have_value('核對返回測試原文。')  # 原文仍在
    page.get_by_role('button', name='保存草稿並進入核對').click()  # 回到核對
    expect(page.locator('#summary')).to_have_value('我改過的摘要')  # 不允許重設成人工修改前內容
    expect(page.locator('#followups')).to_have_value('我留下的下一步')  # 下一步不應被清空
    page.locator('#nav').get_by_role('link', name='關係', exact=True).click()  # 測試未保存導覽保護
    page.get_by_role('button', name='捨棄未保存修改並離開', exact=True).click()  # 明確離開核對頁
    expect(page.locator('#connections-explorer')).to_be_visible()  # 回到交會起點
    page.route('**/api/connections/stories/*', lambda route: route.abort())  # 模擬來源網路失敗
    page.get_by_role('button', name='查看完整來源', exact=True).click()  # 失敗不應假裝成功
    expect(page.locator('#source-dialog')).to_contain_text('重試')  # 有可理解的退路
    page.unroute('**/api/connections/stories/*')  # 恢復連線
    page.get_by_role('button', name='重試來源', exact=True).click()  # 使用者可重試
    page.get_by_text('查看完整原始紀錄', exact=True).click()  # 依介面展開完整來源，而非要求預設攤開長文
    expect(page.locator('#source-dialog .raw-source')).to_be_visible()  # 真實來源重新可讀


def test_slow_navigation_has_feedback_and_recovers(page):  # 體驗：網路等待不呈現無回饋的凍結畫面
    seed_stories(page)  # 建立可查詢故事
    held = []  # 暫時保留請求以模擬等待
    page.route('**/api/connections?*', lambda route: held.append(route))  # 不阻塞瀏覽器主執行緒
    page.locator('#nav').get_by_role('link', name='關係', exact=True).click()  # 開始較慢的切頁
    expect(page.locator('#app-loading')).to_be_visible()  # 明確顯示正在載入，不能只鎖住欄位
    assert page.locator('#app').get_attribute('aria-busy') == 'true'  # 輔助工具也知道等待狀態
    for route in held: route.continue_()  # 恢復請求，驗證可完成而非永久卡住
    page.unroute('**/api/connections?*')  # 不影響後續查詢
    expect(page.locator('#connections-explorer')).to_be_visible()  # 完成載入
    expect(page.locator('#app-loading')).not_to_be_visible()  # 正確清除等待回饋


def test_source_edit_close_requires_discard_and_preserves_rewards(page):  # 體驗：來源更正不能被關閉操作直接丟掉
    _, receipts = seed_stories(page)  # 建立人工核對的真實來源
    page.goto(BASE + '/#people?story=' + receipts[0]['experience_id'])  # 指定一份經歷
    page.get_by_role('button', name='查看完整來源', exact=True).click()  # 開啟來源
    page.get_by_role('button', name='核對／更正人物', exact=True).click()  # 進入編輯
    page.locator('#story-title').fill('尚未保存的標題')  # 製造未提交的更正
    page.get_by_role('button', name='關閉來源', exact=True).click()  # 關閉前必須保護修改
    expect(page.locator('#source-dialog')).to_be_visible()  # 沒有直接丟棄內容
    expect(page.locator('#story-title')).to_have_value('尚未保存的標題')  # 原輸入保留
    page.get_by_role('button', name='捨棄更正並關閉', exact=True).click()  # 使用者明確選擇才離開
    expect(page.locator('#source-dialog')).not_to_be_visible()  # 可以安全關閉
    expect(page.locator('#connection-story')).to_contain_text('那天的午餐')  # 不把未保存標題顯示成成功
    page.get_by_role('button', name='查看怡君的提及來源', exact=True).click()  # 同一來源仍可繼續人工核對
    page.get_by_role('button', name='核對人物', exact=True).click()  # 進入身分校對
    page.get_by_role('button', name='拒絕這次配對', exact=True).click()  # 不強迫使用者配對同名人物
    expect(page.locator('#source-dialog')).to_contain_text('已拒絕配對')  # 來源顯示正式拒絕狀態
    page.get_by_role('button', name='關閉來源', exact=True).click()  # 返回主故事
    expect(page.locator('.mention-row')).to_contain_text('已拒絕配對')  # 主列表與來源狀態一致
    assert page.request.get(BASE + '/api/state').json()['rewards']['total'] == 3  # 編輯與取消不發分


def test_failed_story_list_recovers_and_empty_focus_has_exit(page):  # 異常：清單斷線及無故事人物都有退路
    people, _ = seed_stories(page)  # 使用原有虛構人物
    page.route('**/api/connections?*', lambda route: route.abort())  # 模擬清單載入失敗
    page.locator('#nav').get_by_role('link', name='關係', exact=True).click()  # 使用正常導覽
    expect(page.get_by_role('button', name='重新載入交會', exact=True)).to_be_visible()  # 不停在無回饋舊畫面
    page.unroute('**/api/connections?*')  # 恢復網路
    page.get_by_role('button', name='重新載入交會', exact=True).click()  # 可重試相同條件
    expect(page.locator('#connection-story')).to_be_visible()  # 真正載入成功
    page.goto(BASE + '/#people?focus=' + people[2]['id'])  # 另一位同名者沒有參與故事
    expect(page.locator('#connections-explorer')).to_contain_text('還沒有這位人物實際參與的故事')  # 不把名字相同的人混入故事
    expect(page.get_by_role('button', name='從最近故事開始', exact=True)).to_be_visible()  # 無故事也能回到起點
