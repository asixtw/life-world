from concurrent.futures import ThreadPoolExecutor  # 同時提交重送請求以驗證交易去重

import pytest  # 使用測試資源、參數化及例外斷言
from fastapi.testclient import TestClient  # 載入此模組需要的相依工具

from conftest import onboard, draft, confirm_payload, register  # 共用測試資料與前置流程


def test_draft_and_suggestion_never_award_or_overwrite_raw(client):  # 驗證：草稿與候選不計分且不覆蓋原文
    _, goal = onboard(client); d = draft(client, goal)  # 完成訪客、Bio 與第一目標的測試前置流程
    response = client.post('/api/drafts/' + d['id'] + '/suggest')  # 透過實際測試用戶端操作 API 並保留回應
    assert response.status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert response.json()['applied'] is False  # 斷言草稿與候選不計分且不覆蓋原文的預期結果
    state = client.get('/api/state').json()  # 透過實際測試用戶端操作 API 並保留回應
    assert state['rewards']['total'] == 0  # 核對積分帳本符合本案例預期
    assert state['experiences'] == []  # 斷言草稿與候選不計分且不覆蓋原文的預期結果
    assert state['drafts'][0]['raw_text'] == d['raw_text']  # 斷言草稿與候選不計分且不覆蓋原文的預期結果


def test_confirm_partial_contribution_backdate_tasks_and_idempotency(client):  # 驗證：人工部分貢獻、補記日期、下一步及確認去重
    _, goal = onboard(client); d = draft(client, goal)  # 完成訪客、Bio 與第一目標的測試前置流程
    body = confirm_payload(d)  # 建立攜帶版本與提交代碼的人工確認測試資料
    result = client.post('/api/drafts/' + d['id'] + '/confirm', json=body)  # 透過實際測試用戶端操作 API 並保留回應
    assert result.status_code == 201, result.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    receipt = result.json()  # 保存「receipt」供後續驗證或回傳使用
    assert receipt['points_awarded'] == 3  # 核對積分帳本符合本案例預期
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=body).json() == receipt  # 斷言人工部分貢獻、補記日期、下一步及確認去重的預期結果
    state = client.get('/api/state').json()  # 透過實際測試用戶端操作 API 並保留回應
    assert state['rewards']['total'] == 3  # 核對積分帳本符合本案例預期
    assert len(state['experiences']) == 1  # 斷言人工部分貢獻、補記日期、下一步及確認去重的預期結果
    assert len(state['tasks']) == 1  # 斷言人工部分貢獻、補記日期、下一步及確認去重的預期結果
    assert state['goals'][0]['actions'][0]['progress'] == '0.5'  # 斷言人工部分貢獻、補記日期、下一步及確認去重的預期結果
    exp = state['experiences'][0]  # 保存「exp」供後續驗證或回傳使用
    assert exp['occurred_at'] == '2026-10-26T15:50:00+00:00'  # 斷言人工部分貢獻、補記日期、下一步及確認去重的預期結果
    assert exp['created_at'] == '2026-10-27T07:00:00+00:00'  # 斷言人工部分貢獻、補記日期、下一步及確認去重的預期結果
    assert exp['person_id'] is None  # 斷言人工部分貢獻、補記日期、下一步及確認去重的預期結果
    assert exp['raw_text'] == d['raw_text']  # 斷言人工部分貢獻、補記日期、下一步及確認去重的預期結果
    assert exp['summary'] == body['summary']  # 斷言人工部分貢獻、補記日期、下一步及確認去重的預期結果


def test_new_request_cannot_confirm_same_draft_twice(client):  # 驗證：不同提交代碼仍不能重複確認同一草稿
    _, goal = onboard(client); d = draft(client, goal)  # 完成訪客、Bio 與第一目標的測試前置流程
    path = '/api/drafts/' + d['id'] + '/confirm'  # 保存「path」供後續驗證或回傳使用
    assert client.post(path, json=confirm_payload(d)).status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.post(path, json=confirm_payload(d, request_id='another-key')).status_code == 409  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/api/state').json()['rewards']['total'] == 3  # 核對積分帳本符合本案例預期


def test_same_key_changed_payload_is_conflict(client):  # 驗證：相同提交代碼改內容時回報衝突
    _, goal = onboard(client); d = draft(client, goal)  # 完成訪客、Bio 與第一目標的測試前置流程
    path = '/api/drafts/' + d['id'] + '/confirm'  # 保存「path」供後續驗證或回傳使用
    assert client.post(path, json=confirm_payload(d)).status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.post(path, json=confirm_payload(d, summary='不同內容')).status_code == 409  # 核對 HTTP 狀態，避免失敗請求被當成成功


@pytest.mark.parametrize('quantity', ['0', '-1', 'NaN', 'Infinity', '0.0000001', '1000000000001'])  # 以同一組斷言涵蓋多種正常、異常或邊界輸入
def test_bad_contribution_has_no_side_effects(client, quantity):  # 驗證：不合法貢獻不得造成部分寫入
    _, goal = onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    payload = {'raw_text': '真實紀錄', 'occurred_at': '2026-10-26T12:00:00+08:00', 'goal_id': goal['id'],
               'contributions': [{'action_id': goal['actions'][0]['id'], 'quantity': quantity}]}  # 準備將送出或用於指紋比對的完整內容
    assert client.post('/api/experiences/drafts', json=payload).status_code == 422  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/api/state').json()['rewards']['total'] == 0  # 核對積分帳本符合本案例預期


@pytest.mark.parametrize('when', ['2026-10-28T12:00:00+08:00', '2026-10-26T12:00:00', 'not-a-date'])  # 以同一組斷言涵蓋多種正常、異常或邊界輸入
def test_invalid_event_time(client, when):  # 驗證：拒絕未來時間或無時區時間
    _, goal = onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    assert client.post('/api/experiences/drafts', json={'raw_text': '紀錄', 'occurred_at': when, 'goal_id': goal['id'], 'contributions': []}).status_code == 422  # 核對 HTTP 狀態，避免失敗請求被當成成功


def test_very_old_event_is_allowed_and_gets_points(client):  # 驗證：允許補記很久以前的真實經歷並正常計分
    _, goal = onboard(client); d = draft(client, goal, occurred_at='2001-01-01T00:01:00+08:00')  # 完成訪客、Bio 與第一目標的測試前置流程
    result = client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d))  # 透過實際測試用戶端操作 API 並保留回應
    assert result.status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert result.json()['points_awarded'] == 3  # 核對積分帳本符合本案例預期


def test_decimal_sum_is_exact_and_never_completes_goal(client):  # 驗證：十進位精確累計且不自動宣告成果完成
    _, goal = onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    for i, quantity in enumerate(['0.1', '0.2', '12']):  # 逐項處理測試資料與預期結果
        d = draft(client, goal, contributions=[{'action_id': goal['actions'][0]['id'], 'quantity': quantity}])  # 讀取原始草稿與人工貢獻設定
        assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d, request_id='req-' + str(i))).status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    state = client.get('/api/state').json()  # 透過實際測試用戶端操作 API 並保留回應
    assert state['goals'][0]['actions'][0]['progress'] == '12.3'  # 斷言十進位精確累計且不自動宣告成果完成的預期結果
    assert state['goals'][0]['status'] == 'active'  # 斷言十進位精確累計且不自動宣告成果完成的預期結果


def test_unlinked_event_is_valid_after_first_goal(client):  # 驗證：首目標建立後可保存無目標的經歷
    _, goal = onboard(client); d = draft(client, goal, goal_id=None, contributions=[])  # 完成訪客、Bio 與第一目標的測試前置流程
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/api/state').json()['goals'][0]['actions'][0]['progress'] == '0'  # 斷言首目標建立後可保存無目標的經歷的預期結果


def test_draft_edit_revision_and_confirm_conflict(client):  # 驗證：編輯與確認草稿均檢查版本衝突
    _, goal = onboard(client); d = draft(client, goal)  # 完成訪客、Bio 與第一目標的測試前置流程
    body = {k: d[k] for k in ['raw_text', 'occurred_at', 'goal_id', 'person_id', 'contributions']}  # 保存「body」供後續驗證或回傳使用
    body.update(expected_revision=d['revision'], raw_text='修改後原文')  # 合併本次明確設定的欄位
    updated = client.put('/api/drafts/' + d['id'], json=body)  # 透過實際測試用戶端操作 API 並保留回應
    assert updated.status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert updated.json()['revision'] == d['revision'] + 1  # 核對資料版本或版本衝突結果
    assert client.put('/api/drafts/' + d['id'], json=body).status_code == 409  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 409  # 核對 HTTP 狀態，避免失敗請求被當成成功


def test_guest_person_gate_preserves_draft_and_claim_resumes(client):  # 驗證：人物升級限制保留草稿且可接續操作
    _, goal = onboard(client); d = draft(client, goal)  # 完成訪客、Bio 與第一目標的測試前置流程
    assert client.post('/api/people', json={'name': '朋友'}).status_code == 403  # 核對 HTTP 狀態，避免失敗請求被當成成功
    path = '/api/drafts/' + d['id'] + '/confirm'  # 保存「path」供後續驗證或回傳使用
    assert client.post(path, json=confirm_payload(d, person_id='any-person')).status_code == 403  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/api/drafts/' + d['id']).json()['raw_text'] == d['raw_text']  # 斷言人物升級限制保留草稿且可接續操作的預期結果
    register(client)  # 升級測試帳號並更新 CSRF 標頭
    person = client.post('/api/people', json={'name': '朋友', 'role': '同學'}).json()  # 透過實際測試用戶端操作 API 並保留回應
    assert client.post(path, json=confirm_payload(d, person_id=person['id'])).status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    state = client.get('/api/state').json()  # 透過實際測試用戶端操作 API 並保留回應
    assert state['people'][0]['interaction_count'] == 1  # 斷言人物升級限制保留草稿且可接續操作的預期結果
    assert state['experiences'][0]['person_id'] == person['id']  # 斷言人物升級限制保留草稿且可接續操作的預期結果


def test_cross_owner_access_and_action_injection(app, client):  # 驗證：拒絕跨帳號資料與不相干行動注入
    _, goal = onboard(client); d = draft(client, goal); register(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    p = client.post('/api/people', json={'name': '朋友'}).json()  # 透過實際測試用戶端操作 API 並保留回應
    with TestClient(app) as other:  # 以區塊生命週期確保資源在結束時關閉
        _, second = onboard(other); register(other, 'other_user')  # 完成訪客、Bio 與第一目標的測試前置流程
        assert other.get('/api/drafts/' + d['id']).status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功
        assert other.get('/api/goals/' + goal['id']).status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功
        assert other.post('/api/experiences/drafts', json={'raw_text': '紀錄', 'occurred_at': '2026-10-26T12:00:00+08:00', 'goal_id': second['id'], 'person_id': p['id'], 'contributions': []}).status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功
        own = draft(other, second)  # 讀取原始草稿與人工貢獻設定
        result = other.post('/api/drafts/' + own['id'] + '/confirm', json=confirm_payload(own, contributions=[{'action_id': goal['actions'][0]['id'], 'quantity': '1'}]))  # 透過實際測試用戶端操作 API 並保留回應
        assert result.status_code == 422  # 核對 HTTP 狀態，避免失敗請求被當成成功
        assert other.get('/api/state').json()['rewards']['total'] == 0  # 核對積分帳本符合本案例預期


def test_confirmation_rolls_back_all_writes_on_database_failure(app, client, monkeypatch):  # 驗證：資料庫失敗時經歷、任務與積分全數回滾
    _, goal = onboard(client); d = draft(client, goal)  # 完成訪客、Bio 與第一目標的測試前置流程
    def fail(*args, **kwargs):  # 注入測試用失敗以驗證交易整體回滾
        raise RuntimeError('injected ledger failure')  # 中止目前操作並向呼叫端傳遞錯誤
    monkeypatch.setattr(app.state.service, '_award', fail)  # 注入替代行為，驗證失敗時不會部分寫入
    with TestClient(app, raise_server_exceptions=False) as safe:  # 以區塊生命週期確保資源在結束時關閉
        safe.cookies.update(client.cookies); safe.headers.update(client.headers)  # 合併本次明確設定的欄位
        result = safe.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d))  # 透過實際測試用戶端操作 API 並保留回應
    assert result.status_code == 500  # 核對 HTTP 狀態，避免失敗請求被當成成功
    state = client.get('/api/state').json()  # 透過實際測試用戶端操作 API 並保留回應
    assert state['experiences'] == []  # 斷言資料庫失敗時經歷、任務與積分全數回滾的預期結果
    assert state['tasks'] == []  # 斷言資料庫失敗時經歷、任務與積分全數回滾的預期結果
    assert state['rewards']['total'] == 0  # 核對積分帳本符合本案例預期
    assert state['drafts'][0]['status'] == 'draft'  # 斷言資料庫失敗時經歷、任務與積分全數回滾的預期結果


def test_concurrent_retries_commit_once(app, client):  # 驗證：併發重送仍只寫入一份經歷與積分
    _, goal = onboard(client); d = draft(client, goal)  # 完成訪客、Bio 與第一目標的測試前置流程
    cookie = client.cookies.get('lw_session'); csrf = client.headers['X-CSRF-Token']  # 透過實際測試用戶端操作 API 並保留回應
    def submit(_):  # 送出併發重試以驗證只提交一次
        with TestClient(app) as concurrent:  # 以區塊生命週期確保資源在結束時關閉
            concurrent.cookies.set('lw_session', cookie)  # 執行此模組的共用工具操作
            return concurrent.post('/api/drafts/' + d['id'] + '/confirm', headers={'X-CSRF-Token': csrf}, json=confirm_payload(d))  # 回傳後續測試步驟所需資料
    with ThreadPoolExecutor(max_workers=4) as pool:  # 以區塊生命週期確保資源在結束時關閉
        results = list(pool.map(submit, range(4)))  # 保存「results」供後續驗證或回傳使用
    assert [r.status_code for r in results] == [201] * 4  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert len({r.json()['experience_id'] for r in results}) == 1  # 斷言併發重送仍只寫入一份經歷與積分的預期結果
    state = client.get('/api/state').json()  # 透過實際測試用戶端操作 API 並保留回應
    assert state['rewards']['total'] == 3  # 核對積分帳本符合本案例預期
    assert state['goals'][0]['actions'][0]['progress'] == '0.5'  # 斷言併發重送仍只寫入一份經歷與積分的預期結果
