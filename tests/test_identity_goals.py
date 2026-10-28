import copy  # 載入此模組需要的相依工具

import pytest  # 使用測試資源、參數化及例外斷言
from fastapi.testclient import TestClient  # 載入此模組需要的相依工具

from conftest import guest, goal_payload, onboard, register  # 共用測試資料與前置流程


def test_unauthenticated_access(client):  # 驗證：未登入時拒絕讀寫受保護資料
    assert client.get('/api/auth/me').status_code == 401  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/api/state').status_code == 401  # 核對 HTTP 狀態，避免失敗請求被當成成功


def test_first_goal_is_mandatory_and_lumi_is_born_after_commit(client):  # 驗證：首個目標是必要步驟且提交成功後才孵化 Lumi
    me = guest(client)  # 取得既有訪客身分或建立新的訪客世界
    assert me['lumi_hatched'] is False  # 斷言首個目標是必要步驟且提交成功後才孵化 Lumi的預期結果
    assert client.get('/api/state').status_code == 409  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.post('/api/people', json={'name': '朋友'}).status_code == 409  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.post('/api/goals', json=goal_payload()).status_code == 409  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.put('/api/profile', json={'name': '小光', 'bio': '認真生活', 'timezone': 'Asia/Taipei'}).status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    result = client.post('/api/goals', json=goal_payload())  # 透過實際測試用戶端操作 API 並保留回應
    assert result.status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    state = client.get('/api/state').json()  # 透過實際測試用戶端操作 API 並保留回應
    assert state['lumi']['hatched'] is True  # 斷言首個目標是必要步驟且提交成功後才孵化 Lumi的預期結果
    assert len(state['goals'][0]['actions']) == 3  # 斷言首個目標是必要步驟且提交成功後才孵化 Lumi的預期結果
    assert [a['level'] for a in state['goals'][0]['actions']] == [1, 2, 3]  # 斷言首個目標是必要步驟且提交成功後才孵化 Lumi的預期結果


def test_guest_start_is_idempotent_and_goal_request_retries(client):  # 驗證：訪客開始與目標建立重送不會重複建立
    me, goal = onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    assert guest(client)['owner_id'] == me['owner_id']  # 斷言訪客開始與目標建立重送不會重複建立的預期結果
    again = client.post('/api/goals', json=goal_payload())  # 透過實際測試用戶端操作 API 並保留回應
    assert again.status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert again.json()['id'] == goal['id']  # 斷言訪客開始與目標建立重送不會重複建立的預期結果
    changed = goal_payload(); changed['title'] = '另一個目標'  # 建立含三項行動的目標測試資料
    assert client.post('/api/goals', json=changed).status_code == 409  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert len(client.get('/api/state').json()['goals']) == 1  # 斷言訪客開始與目標建立重送不會重複建立的預期結果


@pytest.mark.parametrize('mutation', ['two_actions', 'four_actions', 'empty_title', 'bad_level', 'bad_day', 'repeated_day', 'zero_target', 'nonfinite'])  # 以同一組斷言涵蓋多種正常、異常或邊界輸入
def test_invalid_goal_does_not_hatch_lumi(client, mutation):  # 驗證：不合法目標不孵化 Lumi
    guest(client)  # 取得既有訪客身分或建立新的訪客世界
    client.put('/api/profile', json={'name': '小光', 'bio': '生活', 'timezone': 'Asia/Taipei'})  # 透過實際測試用戶端操作 API 並保留回應
    data = copy.deepcopy(goal_payload())  # 保存「data」供後續驗證或回傳使用
    if mutation == 'two_actions': data['actions'].pop()  # 依目前條件選擇下一步處理分支
    if mutation == 'four_actions': data['actions'].append(data['actions'][0])  # 依目前條件選擇下一步處理分支
    if mutation == 'empty_title': data['title'] = '   '  # 依目前條件選擇下一步處理分支
    if mutation == 'bad_level': data['actions'][0]['level'] = 4  # 依目前條件選擇下一步處理分支
    if mutation == 'bad_day': data['actions'][0]['weekdays'] = [7]  # 依目前條件選擇下一步處理分支
    if mutation == 'repeated_day': data['actions'][0]['weekdays'] = [0, 0]  # 依目前條件選擇下一步處理分支
    if mutation == 'zero_target': data['actions'][0]['target'] = '0'  # 依目前條件選擇下一步處理分支
    if mutation == 'nonfinite': data['actions'][0]['target'] = 'NaN'  # 依目前條件選擇下一步處理分支
    assert client.post('/api/goals', json=data).status_code == 422  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/api/auth/me').json()['lumi_hatched'] is False  # 斷言不合法目標不孵化 Lumi的預期結果


def test_profile_validation(client):  # 驗證：個人介紹欄位與時區格式驗證
    guest(client)  # 取得既有訪客身分或建立新的訪客世界
    assert client.put('/api/profile', json={'name': ' ', 'bio': '', 'timezone': 'No/SuchZone'}).status_code == 422  # 核對 HTTP 狀態，避免失敗請求被當成成功


def test_csrf_and_cross_origin_writes_rejected(client):  # 驗證：缺少 CSRF 與跨來源寫入遭拒絕
    guest(client)  # 取得既有訪客身分或建立新的訪客世界
    del client.headers['X-CSRF-Token']  # 執行此模組的共用工具操作
    assert client.put('/api/profile', json={'name': 'x', 'bio': 'y', 'timezone': 'Asia/Taipei'}).status_code == 403  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.post('/api/auth/guest', headers={'Origin': 'https://evil.example'}).status_code == 403  # 核對 HTTP 狀態，避免失敗請求被當成成功


def test_claim_rotates_session_and_keeps_owner_and_goal(client):  # 驗證：升級輪換工作階段並保留世界所屬及目標
    me, goal = onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    old_cookie = client.cookies.get('lw_session')  # 透過實際測試用戶端操作 API 並保留回應
    claimed = register(client)  # 升級測試帳號並更新 CSRF 標頭
    assert claimed['owner_id'] == me['owner_id']  # 斷言升級輪換工作階段並保留世界所屬及目標的預期結果
    assert claimed['status'] == 'registered'  # 斷言升級輪換工作階段並保留世界所屬及目標的預期結果
    assert client.cookies.get('lw_session') != old_cookie  # 斷言升級輪換工作階段並保留世界所屬及目標的預期結果
    assert client.get('/api/state').json()['goals'][0]['id'] == goal['id']  # 斷言升級輪換工作階段並保留世界所屬及目標的預期結果
    assert client.get('/api/auth/me', headers={'Cookie': 'lw_session=' + old_cookie}).status_code == 401  # 核對 HTTP 狀態，避免失敗請求被當成成功


@pytest.mark.parametrize('username,password', [('x', 'short'), ('bad name', 'a-good-password'), ('valid_name', 'short')])  # 以同一組斷言涵蓋多種正常、異常或邊界輸入
def test_claim_validation(client, username, password):  # 驗證：建立帳號時的名稱與密碼邊界
    onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    assert client.post('/api/auth/claim', json={'username': username, 'password': password}).status_code == 422  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/api/auth/me').json()['status'] == 'guest'  # 斷言建立帳號時的名稱與密碼邊界的預期結果


def test_logout_revokes_and_login_restores(client):  # 驗證：登出撤銷工作階段，登入可恢復已保存資料
    _, goal = onboard(client); register(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    old_cookie = client.cookies.get('lw_session')  # 透過實際測試用戶端操作 API 並保留回應
    assert client.post('/api/auth/logout').status_code == 204  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/api/state').status_code == 401  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/api/auth/me', headers={'Cookie': 'lw_session=' + old_cookie}).status_code == 401  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.post('/api/auth/login', json={'username': 'lumi_user', 'password': 'wrong'}).status_code == 401  # 核對 HTTP 狀態，避免失敗請求被當成成功
    result = client.post('/api/auth/login', json={'username': 'lumi_user', 'password': 'a-good-password-2026'})  # 透過實際測試用戶端操作 API 並保留回應
    assert result.status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/api/state').json()['goals'][0]['id'] == goal['id']  # 斷言登出撤銷工作階段，登入可恢復已保存資料的預期結果


def test_existing_account_conflict_never_merges_guest_data(app, client):  # 驗證：登入既有帳號不會暗中合併訪客世界
    onboard(client); register(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    with TestClient(app) as other:  # 以區塊生命週期確保資源在結束時關閉
        _, other_goal = onboard(other)  # 完成訪客、Bio 與第一目標的測試前置流程
        login = {'username': 'lumi_user', 'password': 'a-good-password-2026'}  # 保存「login」供後續驗證或回傳使用
        assert other.post('/api/auth/login', json=login).status_code == 409  # 核對 HTTP 狀態，避免失敗請求被當成成功
        result = other.post('/api/auth/login', json=dict(login, discard_guest=True))  # 透過實際測試用戶端操作 API 並保留回應
        assert result.status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
        assert other_goal['id'] not in [g['id'] for g in other.get('/api/state').json()['goals']]  # 斷言登入既有帳號不會暗中合併訪客世界的預期結果


def test_page_and_static_assets_are_available(client):  # 驗證：首頁及必要靜態資源可讀取
    assert client.get('/').status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/static/app.js').status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/static/styles.css').status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/api/health').json()['status'] == 'ok'  # 斷言首頁及必要靜態資源可讀取的預期結果
