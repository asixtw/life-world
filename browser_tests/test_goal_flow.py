"""單一目標與日期排程的真實手機及桌面驗收。"""  # 不以 API 綠燈代替介面操作。
from pathlib import Path  # 保存虛構資料截圖。
import pytest  # 參數化手機及桌面。
from playwright.sync_api import expect  # 等待實際畫面結果。
from test_journey import BASE, page  # 使用隔離 Chromium 視窗。


def begin(page):  # 首次引導到目標命名。
    page.goto(BASE)  # 使用隔離服務。
    page.get_by_role('button', name='不用註冊，先開始').click()  # 建立訪客。
    page.locator('#profile-name').fill('習慣體驗者')  # 使用虛構名稱。
    page.locator('#bio').fill('一次專注一個目標')  # 完成必要自介。
    page.get_by_role('button', name='接著，建立第一個目標').click()  # 開始逐步設定。
    expect(page.locator('#goal-form')).to_have_attribute('data-step', '0')  # 現版應因缺少逐步建立而失敗。


def fill_wizard(page, title='我的習慣挑戰'):  # 完整使用者操作，非注入假完成狀態。
    page.locator('#goal-title').fill(title)  # 為目標命名。
    page.get_by_role('button', name='下一步').click()  # 進入成果與期限。
    page.locator('#outcome').fill('完成作品並留下照片')  # 設定達成的樣子。
    assert page.locator('#goal-deadline').input_value() == ''  # 不預填一個月。
    page.locator('#goal-deadline').fill('2026-11-30')  # 明確選期限。
    page.get_by_role('button', name='下一步').click()  # 設定第一個習慣。
    for i, name in enumerate(['閱讀', '整理', '分享']):  # 三個習慣逐一確認。
        page.locator('#action-title-' + str(i)).fill(name)  # 使用具體習慣名稱。
        page.get_by_role('button', name='平日', exact=True).click()  # 快速套用星期。
        expect(page.locator('[data-gj="toggle-day"][aria-pressed="true"]').first).to_be_visible()  # 所選日期明確可見。
        if i == 0:  # 日期格是原設計的關鍵驗收畫面。
            Path('docs/artifacts/goals').mkdir(parents=True, exist_ok=True)  # 先建立本輪證據區。
            page.screenshot(path='docs/artifacts/goals/calendar-' + str(page.viewport_size['width']) + '.png', full_page=True)  # 保存實際月曆與快選。
        page.get_by_role('button', name='下一步').click()  # 檢視下一個習慣或總覽。
    expect(page.get_by_role('heading', name='檢查這次挑戰')).to_be_visible()  # 三個習慣之後才可提交。


@pytest.mark.parametrize('viewport', [{'width': 390, 'height': 844}, {'width': 1440, 'height': 1050}])  # 同一流程驗證兩種尺寸。
def test_wizard_single_goal_end_and_history(page, viewport):  # 從建立走到歷史與下一次挑戰。
    page.set_viewport_size(viewport)  # 切換真實 viewport。
    errors = []  # 收集 JavaScript 例外。
    page.on('pageerror', lambda error: errors.append(str(error)))  # 不忽略執行問題。
    begin(page)  # 進入建立流程。
    if viewport['width'] == 390: assert not page.locator('.sidebar').is_visible()  # 首次引導不能被空白底部導覽遮住。
    fill_wizard(page)  # 完成三個習慣。
    assert not page.request.get(BASE + '/api/auth/me').json()['lumi_hatched']  # 確認前不孵化。
    artifacts = Path('docs/artifacts/goals')  # 本輪圖片與舊證據分開。
    artifacts.mkdir(parents=True, exist_ok=True)  # 建立虛構截圖目錄。
    page.screenshot(path=str(artifacts / ('summary-' + str(viewport['width']) + '.png')), full_page=True)  # 保存資訊層級。
    page.get_by_role('button', name='確認設定，建立目標蛋').click()  # 明確開始挑戰。
    page.get_by_role('link', name='進入我的世界').click()  # Lumi 首次出現後進世界。
    page.locator('#nav').get_by_role('link', name='目標', exact=True).click()  # 查看目前挑戰。
    expect(page.get_by_role('heading', name='目前挑戰')).to_be_visible()  # 聚焦唯一目標。
    expect(page.get_by_role('link', name='新的目標')).to_have_count(0)  # 不能新增第二個。
    page.get_by_role('link', name='查看目標').click()  # 進入詳細頁。
    page.get_by_role('button', name='確認完成成果', exact=True).click()  # 主要操作要能帶到成果確認區。
    expect(page.locator('#goal-completion')).to_be_in_viewport()  # 不能只有網址改變而沒有可見回饋。
    expect(page.locator('#goal-completion')).to_be_focused()  # 鍵盤使用者可接續成果操作。
    page.get_by_role('button', name='結束這次挑戰', exact=True).click()  # 明確選擇提前結束。
    page.locator('#goal-end-confirmed').check()  # 二次確認避免誤操作。
    page.get_by_role('button', name='確認結束並收藏').click()  # 將旅程收藏。
    expect(page.get_by_text('提前結束', exact=True).first).to_be_visible()  # 不是一律標為失敗。
    page.locator('#nav').get_by_role('link', name='目標', exact=True).click()  # 回到目標頁。
    page.get_by_role('button', name='曾經挑戰', exact=True).click()  # 查看歷史分類。
    expect(page.get_by_role('heading', name='我的習慣挑戰')).to_be_visible()  # 舊挑戰保留可查。
    expect(page.get_by_role('link', name='新的目標')).to_be_visible()  # 結束後才解鎖。
    page.screenshot(path=str(artifacts / ('history-' + str(viewport['width']) + '.png')), full_page=True)  # 保存歷史畫面。
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')  # 手機沒有水平溢出。
    assert errors == []  # 沒有 JavaScript 錯誤。


def test_wizard_survives_refresh_and_cancel(page):  # 建立草稿不因返回或重新整理遺失。
    begin(page)  # 使用新帳號隔離草稿。
    page.locator('#goal-title').fill('保留我的設定')  # 輸入草稿名稱。
    page.reload()  # 尚未下一步仍要保留。
    expect(page.locator('#goal-title')).to_have_value('保留我的設定')  # 即時保存有效。
    page.get_by_role('button', name='下一步').click()  # 進入期限。
    page.locator('#outcome').fill('一份保留的成果描述')  # 填寫成果。
    page.locator('#goal-deadline').fill('2026-11-30')  # 填寫期限。
    page.get_by_role('button', name='下一步').click()  # 進入習慣。
    page.locator('#action-title-0').fill('閱讀')  # 寫入第一個習慣。
    page.get_by_role('button', name='每天', exact=True).click()  # 建立排程。
    expect(page.locator('[data-gj="toggle-day"][aria-pressed="true"]').first).to_be_visible()  # 等待非同步重繪，不讀取舊畫面數量。
    before = page.locator('[data-gj="toggle-day"][aria-pressed="true"]').count()  # 保存已選日期數。
    page.get_by_role('button', name='按週檢視', exact=True).click()  # 切換顯示不改資料。
    page.get_by_role('button', name='按月檢視', exact=True).click()  # 回到原顯示。
    expect(page.get_by_role('button', name='按月檢視', exact=True)).to_have_attribute('aria-pressed', 'true')  # 月畫面完成後才核對數量。
    assert page.locator('[data-gj="toggle-day"][aria-pressed="true"]').count() == before  # 安排保持一致。
    page.get_by_role('button', name='稍後繼續', exact=True).click()  # 不丟棄草稿。
    page.get_by_role('link', name='繼續建立目標').click()  # 從暫存頁接續。
    expect(page.locator('#action-title-0')).to_have_value('閱讀')  # 保留目前步驟。
    page.get_by_role('button', name='上一步', exact=True).click()  # 返回前一步。
    expect(page.locator('#outcome')).to_have_value('一份保留的成果描述')  # 前一步內容完整。


def test_create_failure_keeps_summary_and_retries_once(page):  # 網路失敗不清除建立草稿。
    begin(page)  # 使用獨立訪客。
    fill_wizard(page, '可以重試的挑戰')  # 準備完整草稿。
    page.route('**/api/goals', lambda route: route.abort('failed'))  # 僅模擬一次建立網路失敗。
    page.get_by_role('button', name='確認設定，建立目標蛋').click()  # 嘗試保存。
    expect(page.locator('#notice')).to_contain_text('目前無法連線')  # 明確說明尚未保存。
    expect(page.get_by_role('heading', name='檢查這次挑戰')).to_be_visible()  # 保留原頁面。
    assert not page.request.get(BASE + '/api/auth/me').json()['lumi_hatched']  # 不提前孵化。
    page.unroute('**/api/goals')  # 恢復真實 API。
    page.reload()  # 跨刷新仍可重試同份草稿。
    expect(page.get_by_role('heading', name='檢查這次挑戰')).to_be_visible()  # 保留最後步驟。
    page.get_by_role('button', name='確認設定，建立目標蛋').click()  # 重試建立。
    page.get_by_role('link', name='進入我的世界').click()  # 只有成功才出現 Lumi。
    goals = page.request.get(BASE + '/api/state').json()['goals']  # 核對真正伺服器狀態。
    assert len(goals) == 1 and goals[0]['title'] == '可以重試的挑戰'  # 恰好一個正式挑戰。


def test_expiry_extend_and_apply_pending_in_real_browser(page):  # 實際 API 與畫面驗證到期後採計。
    import os  # 測試專用時鐘位置由執行者明確提供。
    from datetime import date, datetime, timedelta, timezone  # 驗證翌日，不等待一天。
    filename = os.environ.get('LIFEWORLD_TEST_CLOCK_FILE')  # 不對任意服務改時間。
    if not filename: pytest.skip('需明確指定隔離測試服務的時鐘控制檔')  # 未提供就據實標示未執行。
    clock = Path(filename)  # 只操作指定暫存檔。
    original = clock.read_text()  # 保留原模式。
    try:  # 無論成功或失敗都恢復測試時鐘。
        begin(page)  # 建立合法身分與 Bio。
        me = page.request.get(BASE + '/api/auth/me').json()  # 讀取伺服器日期。
        today = date.fromisoformat(me['today'])  # 不使用主機時區猜測。
        headers = {'X-CSRF-Token': me['csrf_token']}  # API 寫入仍經 CSRF。
        body = {'request_id': 'expiry-ui', 'title': '到期回顧體驗', 'outcome': '練習回顧', 'deadline': today.isoformat(), 'actions': [{'title': name, 'unit': '次', 'dates': [today.isoformat()]} for name in ['閱讀', '整理', '分享']]}  # API 準備短目標，建立 UI 已由其他案例驗證。
        created = page.request.post(BASE + '/api/goals', headers=headers, data=body)  # 使用正式交易。
        assert created.ok, created.text()  # 前置不能失敗。
        goal = created.json()  # 使用正式行動 ID。
        tomorrow = today + timedelta(days=1)  # 測試跨日。
        instant = datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)  # 台北已跨過截止日。
        clock.write_text(instant.isoformat())  # 只推進隔離服務時鐘。
        d = page.request.post(BASE + '/api/experiences/drafts', headers=headers, data={'raw_text': '到期後的真實閱讀', 'occurred_at': (instant-timedelta(hours=1)).isoformat(), 'goal_id': goal['id'], 'contributions': [{'action_id': goal['actions'][0]['id'], 'quantity': '0.5'}]}).json()  # 新經歷仍可保存。
        result = page.request.post(BASE + '/api/drafts/' + d['id'] + '/confirm', headers=headers, data={'request_id': 'expiry-confirm', 'expected_revision': d['revision'], 'summary': '到期後的真實閱讀', 'contributions': d['contributions'], 'tasks': []})  # 人工確認經歷。
        assert result.ok, result.text()  # 經歷不被到期阻擋。
        points = page.request.get(BASE + '/api/state').json()['rewards']['total']  # 保存一次獎勵。
        page.goto(BASE + '/#goal/' + goal['id'])  # 重新進入取得到期狀態。
        expect(page.get_by_role('heading', name='這次挑戰到期了，先回顧一下。')).to_be_visible()  # 不自動判失敗。
        page.get_by_role('button', name='延長挑戰', exact=True).click()  # 使用者選擇延長。
        page.locator('#review-deadline').fill((tomorrow+timedelta(days=2)).isoformat())  # 重新選期限。
        for i in range(3):  # 三個習慣逐一檢視。
            details = page.locator('#goal-review-form > details').nth(i)  # 對應目前習慣。
            if details.get_attribute('open') is None: details.locator('summary').click()  # 展開未檢視安排。
            details.get_by_role('button', name='每天', exact=True).click()  # 明確安排延長期間。
        page.locator('#goal-review-form [name=confirmed]').check()  # 人工確認全部安排。
        page.get_by_role('button', name='確認保存安排').click()  # 真正提交延長。
        expect(page.get_by_role('heading', name='待處理與未採計貢獻')).to_be_visible()  # 不自動補算。
        current = page.request.get(BASE + '/api/goals/' + goal['id']).json()  # 檢查進度仍零。
        assert current['actions'][0]['progress'] == '0'  # 延長本身不採計。
        page.locator('.pending-accept-form [name=confirmed]').check()  # 逐筆核對來源。
        page.get_by_role('button', name='確認採計這筆貢獻').click()  # 人工採計。
        expect(page.get_by_text('已採計 0.5', exact=False)).to_be_visible()  # 顯示採計結果。
        current = page.request.get(BASE + '/api/state').json()  # 核對正式保存。
        assert current['goals'][0]['actions'][0]['progress'] == '0.5' and current['rewards']['total'] == points  # 不重複發獎。
        page.set_viewport_size({'width': 390, 'height': 844})  # 手機查看回顧完成後畫面。
        page.screenshot(path='docs/artifacts/goals/extended-pending-mobile.png', full_page=True)  # 保存真實操作證據。
    finally:  # 測試結束恢復真實時間模式。
        clock.write_text(original)  # 不影響後續其他案例。
