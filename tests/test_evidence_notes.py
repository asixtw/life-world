import base64  # 解碼虛構的測試圖片

import pytest  # 使用測試資源、參數化及例外斷言
from fastapi.testclient import TestClient  # 載入此模組需要的相依工具

from conftest import onboard, register, draft, confirm_payload  # 共用測試資料與前置流程

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGNkaGBgYGBgYmBgYGBgAAAGKgCE5tEtPAAAAABJRU5ErkJggg==')  # 準備供上傳驗收使用的有效虛構圖片


def upload(client, goal, content=PNG, name='成果.png', mime='image/png'):  # 驗證權限與圖片內容後保存目標佐證
    return client.post('/api/goals/' + goal['id'] + '/evidence', files={'file': (name, content, mime)})  # 回傳後續測試步驟所需資料


def test_goal_needs_evidence_and_explicit_human_confirmation(client):  # 驗證：完成成果須有佐證與使用者明確確認
    _, goal = onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    path = '/api/goals/' + goal['id'] + '/complete'  # 保存「path」供後續驗證或回傳使用
    assert client.post(path, json={'request_id': 'done-1', 'evidence_ids': [], 'confirmed': True}).status_code == 422  # 核對 HTTP 狀態，避免失敗請求被當成成功
    evidence = upload(client, goal)  # 驗證權限與圖片內容後保存目標佐證
    assert evidence.status_code == 201, evidence.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    eid = evidence.json()['id']  # 保存「eid」供後續驗證或回傳使用
    assert client.post(path, json={'request_id': 'done-1', 'evidence_ids': [eid], 'confirmed': False}).status_code == 422  # 核對 HTTP 狀態，避免失敗請求被當成成功
    body = {'request_id': 'done-1', 'evidence_ids': [eid], 'confirmed': True, 'reflection': '我確認已完成成果'}  # 保存「body」供後續驗證或回傳使用
    result = client.post(path, json=body)  # 透過實際測試用戶端操作 API 並保留回應
    assert result.status_code == 200, result.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.post(path, json=body).json() == result.json()  # 斷言完成成果須有佐證與使用者明確確認的預期結果
    assert client.get('/api/state').json()['goals'][0]['status'] == 'completed'  # 斷言完成成果須有佐證與使用者明確確認的預期結果
    assert client.get('/api/state').json()['rewards']['total'] == 0  # 核對積分帳本符合本案例預期
    assert client.get('/api/evidence/' + eid).content == PNG  # 斷言完成成果須有佐證與使用者明確確認的預期結果


def test_duplicate_upload_reuses_evidence(client):  # 驗證：相同圖片重傳沿用原佐證
    _, goal = onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    a = upload(client, goal); b = upload(client, goal)  # 驗證權限與圖片內容後保存目標佐證
    assert a.json()['id'] == b.json()['id']  # 斷言相同圖片重傳沿用原佐證的預期結果
    assert len(client.get('/api/goals/' + goal['id']).json()['evidence']) == 1  # 斷言相同圖片重傳沿用原佐證的預期結果


@pytest.mark.parametrize('content,name,mime,code', [(b'', 'empty.png', 'image/png', 422), (b'x' * 4097, 'large.png', 'image/png', 413), (b'<script>bad</script>', 'fake.png', 'image/png', 415), (PNG, '../../secret.png', 'image/png', 422), (PNG, 'file.svg', 'image/svg+xml', 415), (PNG[:30], 'broken.png', 'image/png', 415)])  # 以同一組斷言涵蓋多種正常、異常或邊界輸入
def test_invalid_upload(client, content, name, mime, code):  # 驗證：拒絕空檔、過大、偽造或損毀圖片
    _, goal = onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    assert upload(client, goal, content, name, mime).status_code == code  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.get('/api/goals/' + goal['id']).json()['evidence'] == []  # 斷言拒絕空檔、過大、偽造或損毀圖片的預期結果


def test_other_goal_and_other_owner_evidence_rejected(app, client):  # 驗證：拒絕引用其他目標或帳號的佐證
    _, goal = onboard(client); evidence = upload(client, goal).json()  # 完成訪客、Bio 與第一目標的測試前置流程
    from conftest import goal_payload  # 共用測試資料與前置流程
    second = client.post('/api/goals', json=goal_payload('goal-2')).json()  # 透過實際測試用戶端操作 API 並保留回應
    assert client.post('/api/goals/' + second['id'] + '/complete', json={'request_id': 'done', 'evidence_ids': [evidence['id']], 'confirmed': True}).status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功
    with TestClient(app) as other:  # 以區塊生命週期確保資源在結束時關閉
        _, g = onboard(other)  # 完成訪客、Bio 與第一目標的測試前置流程
        assert other.get('/api/evidence/' + evidence['id']).status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功
        assert upload(other, goal).status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功
        assert other.post('/api/goals/' + g['id'] + '/complete', json={'request_id': 'done', 'evidence_ids': [evidence['id']], 'confirmed': True}).status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功


def test_completed_goal_contribution_policy_is_explicit_and_preserves_draft(client):  # 驗證：已完成目標的貢獻更正被明確限制且草稿保留
    _, goal = onboard(client); d = draft(client, goal); e = upload(client, goal).json()  # 完成訪客、Bio 與第一目標的測試前置流程
    assert client.post('/api/goals/' + goal['id'] + '/complete', json={'request_id': 'done', 'evidence_ids': [e['id']], 'confirmed': True}).status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    result = client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d))  # 透過實際測試用戶端操作 API 並保留回應
    assert result.status_code == 409  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert result.json()['error']['code'] == 'policy_required'  # 斷言已完成目標的貢獻更正被明確限制且草稿保留的預期結果
    assert client.get('/api/drafts/' + d['id']).json()['status'] == 'draft'  # 斷言已完成目標的貢獻更正被明確限制且草稿保留的預期結果


@pytest.mark.parametrize('kind', ['preparation', 'simulation', 'message'])  # 以同一組斷言涵蓋多種正常、異常或邊界輸入
def test_creative_notes_never_change_reality(client, kind):  # 驗證：準備、模擬與訊息筆記不改正式事實或積分
    onboard(client); register(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    p = client.post('/api/people', json={'name': '朋友'}).json()  # 透過實際測試用戶端操作 API 並保留回應
    result = client.post('/api/notes', json={'person_id': p['id'], 'kind': kind, 'title': '先練習表達', 'content': '模擬台詞，非真人發言'})  # 透過實際測試用戶端操作 API 並保留回應
    assert result.status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    state = client.get('/api/state').json()  # 透過實際測試用戶端操作 API 並保留回應
    assert len(state['notes']) == 1  # 斷言準備、模擬與訊息筆記不改正式事實或積分的預期結果
    assert state['experiences'] == []  # 斷言準備、模擬與訊息筆記不改正式事實或積分的預期結果
    assert state['rewards']['total'] == 0  # 核對積分帳本符合本案例預期
    assert state['people'][0]['interaction_count'] == 0  # 斷言準備、模擬與訊息筆記不改正式事實或積分的預期結果


def test_data_survives_new_app_instance(app, client, tmp_path):  # 驗證：重建服務後仍可讀已保存資料
    from app.main import create_app  # 使用正式 App 工廠建立服務或測試實例
    _, goal = onboard(client); d = draft(client, goal)  # 完成訪客、Bio 與第一目標的測試前置流程
    client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d))  # 透過實際測試用戶端操作 API 並保留回應
    register(client)  # 升級測試帳號並更新 CSRF 標頭
    with TestClient(create_app(data_dir=tmp_path, policy=app.state.service.policy, clock=app.state.service.clock)) as restarted:  # 以區塊生命週期確保資源在結束時關閉
        assert restarted.post('/api/auth/login', json={'username': 'lumi_user', 'password': 'a-good-password-2026'}).status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
        state = restarted.get('/api/state').json()  # 透過實際測試用戶端操作 API 並保留回應
        assert state['rewards']['total'] == 3  # 核對積分帳本符合本案例預期
        assert state['goals'][0]['actions'][0]['progress'] == '0.5'  # 斷言重建服務後仍可讀已保存資料的預期結果
        assert len(state['experiences']) == 1  # 斷言重建服務後仍可讀已保存資料的預期結果
