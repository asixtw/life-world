from datetime import timedelta  # 處理 UTC、發生時間與期限

from conftest import onboard, draft, confirm_payload, register  # 共用測試資料與前置流程


def test_raw_text_is_preserved_byte_for_byte(client):  # 驗證：原文空白與換行逐字保留
    _, goal = onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    original = '\n  今天的原文，包含空白與換行。\n\n'  # 保存「original」供後續驗證或回傳使用
    d = draft(client, goal, raw_text=original)  # 讀取原始草稿與人工貢獻設定
    assert d['raw_text'] == original  # 斷言原文空白與換行逐字保留的預期結果
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/api/state').json()['experiences'][0]['raw_text'] == original  # 斷言原文空白與換行逐字保留的預期結果


def test_whitespace_only_raw_text_rejected(client):  # 驗證：拒絕純空白的原始經歷
    _, goal = onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    assert client.post('/api/experiences/drafts', json={'raw_text': ' \n ', 'occurred_at': '2026-10-26T12:00:00+08:00', 'contributions': []}).status_code == 422  # 核對 HTTP 狀態，避免失敗請求被當成成功


def test_password_spaces_are_not_silently_removed(client):  # 驗證：密碼首尾空白不被自動裁切
    onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    result = client.post('/api/auth/claim', json={'username': 'space_user', 'password': ' secret-password '})  # 透過實際測試用戶端操作 API 並保留回應
    assert result.status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    client.headers['X-CSRF-Token'] = result.json()['csrf_token']  # 保存「client.headers['X-CSRF-Token']」供後續驗證或回傳使用
    client.post('/api/auth/logout')  # 透過實際測試用戶端操作 API 並保留回應
    assert client.post('/api/auth/login', json={'username': 'space_user', 'password': 'secret-password'}).status_code == 401  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.post('/api/auth/login', json={'username': 'space_user', 'password': ' secret-password '}).status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功


def test_expired_session_cannot_read_or_write(app, client):  # 驗證：已過期工作階段無法讀寫
    onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    current = app.state.service.clock()  # 準備交易內重新讀取的帳號狀態
    app.state.service.clock = lambda: current + timedelta(hours=app.state.service.policy.session_hours + 1)  # 保存「app.state.service.clock」供後續驗證或回傳使用
    assert client.get('/api/state').status_code == 401  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.post('/api/people', json={'name': '朋友'}).status_code == 401  # 核對 HTTP 狀態，避免失敗請求被當成成功


def test_database_does_not_store_plaintext_password_or_session(app, client):  # 驗證：資料庫不保存明文密碼或工作階段代碼
    onboard(client); register(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    token = client.cookies.get('lw_session')  # 透過實際測試用戶端操作 API 並保留回應
    with app.state.service.db.connect() as c:  # 在同一讀取交易取得一致資料
        user = c.execute("SELECT * FROM users WHERE status='registered'").fetchone()  # 執行目前交易中的參數化查詢
        assert user['password_hash'].startswith('$argon2')  # 斷言資料庫不保存明文密碼或工作階段代碼的預期結果
        assert 'a-good-password-2026' not in user['password_hash']  # 斷言資料庫不保存明文密碼或工作階段代碼的預期結果
        assert c.execute('SELECT token_hash FROM sessions').fetchone()['token_hash'] != token  # 斷言資料庫不保存明文密碼或工作階段代碼的預期結果


def test_28_day_calendar_respects_per_action_weekdays(client):  # 驗證：現有 28 日預覽遵守各行動每週規律
    _, goal = onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    response = client.get('/api/goals/' + goal['id'] + '/calendar')  # 透過實際測試用戶端操作 API 並保留回應
    assert response.status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    days = response.json()  # 保存「days」供後續驗證或回傳使用
    assert len(days) == 28  # 斷言現有 28 日預覽遵守各行動每週規律的預期結果
    assert days[0]['date'] == '2026-10-27'  # 斷言現有 28 日預覽遵守各行動每週規律的預期結果
    assert days[0]['action_ids'] == []  # 斷言現有 28 日預覽遵守各行動每週規律的預期結果
    assert set(days[1]['action_ids']) == {a['id'] for a in goal['actions']}  # 斷言現有 28 日預覽遵守各行動每週規律的預期結果


def test_assistant_failure_preserves_draft_and_manual_confirmation(app, client):  # 驗證：整理服務失敗仍保留原文且可手動確認
    class Broken:  # 刻意失敗的測試替身
        def suggest(self, text):  # 建立可手動審閱的整理候選，不寫入正式事實
            raise TimeoutError('test provider timeout')  # 中止目前操作並向呼叫端傳遞錯誤
    _, goal = onboard(client); d = draft(client, goal)  # 完成訪客、Bio 與第一目標的測試前置流程
    app.state.service.assistant = Broken()  # 保存「app.state.service.assistant」供後續驗證或回傳使用
    assert client.post('/api/drafts/' + d['id'] + '/suggest').status_code == 503  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/api/drafts/' + d['id']).json()['raw_text'] == d['raw_text']  # 斷言整理服務失敗仍保留原文且可手動確認的預期結果
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功


def test_task_checking_does_not_award_or_complete_actions(client):  # 驗證：勾選待辦不會增發積分或累計行動
    _, goal = onboard(client); d = draft(client, goal)  # 完成訪客、Bio 與第一目標的測試前置流程
    client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d))  # 透過實際測試用戶端操作 API 並保留回應
    task = client.get('/api/state').json()['tasks'][0]  # 透過實際測試用戶端操作 API 並保留回應
    assert client.patch('/api/tasks/' + task['id'], json={'done': True}).status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.patch('/api/tasks/' + task['id'], json={'done': True}).status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    state = client.get('/api/state').json()  # 透過實際測試用戶端操作 API 並保留回應
    assert state['tasks'][0]['done'] == 1  # 斷言勾選待辦不會增發積分或累計行動的預期結果
    assert state['rewards']['total'] == 3  # 核對積分帳本符合本案例預期
    assert state['goals'][0]['actions'][0]['progress'] == '0.5'  # 斷言勾選待辦不會增發積分或累計行動的預期結果
