from datetime import datetime, timezone  # 處理 UTC、發生時間與期限

import pytest  # 使用測試資源、參數化及例外斷言
from fastapi.testclient import TestClient  # 載入此模組需要的相依工具

from app.main import create_app  # 使用正式 App 工廠建立服務或測試實例
from app.config import DemoPolicy  # 載入本機開發設定


@pytest.fixture  # 註冊可由 pytest 注入並清理的測試資源
def app(tmp_path):  # 建立使用暫存資料庫與固定時鐘的測試 App
    return create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                      clock=lambda: datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc))  # 回傳後續測試步驟所需資料


@pytest.fixture  # 註冊可由 pytest 注入並清理的測試資源
def client(app):  # 提供自動關閉的 FastAPI 測試用戶端
    with TestClient(app) as client:  # 以區塊生命週期確保資源在結束時關閉
        yield client  # 提供區塊或測試使用的資源，之後繼續清理


def guest(client):  # 取得既有訪客身分或建立新的訪客世界
    result = client.post('/api/auth/guest')  # 透過實際測試用戶端操作 API 並保留回應
    assert result.status_code in (200, 201), result.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    client.headers['X-CSRF-Token'] = result.json()['csrf_token']  # 保存「client.headers['X-CSRF-Token']」供後續驗證或回傳使用
    return result.json()  # 回傳後續測試步驟所需資料


def goal_payload(request_id='goal-1'):  # 建立含三項行動的目標測試資料
    return {'request_id': request_id, 'title': '靠近更好的自己', 'outcome': '完成一個自己的作品',
            'actions': [{'title': title, 'unit': unit, 'target': '10', 'level': i + 1, 'weekdays': [0, 2, 4]}
                        for i, (title, unit) in enumerate([('練習', '小時'), ('記錄', '篇'), ('交流', '次')])]}  # 回傳後續測試步驟所需資料


def onboard(client):  # 完成訪客、Bio 與第一目標的測試前置流程
    me = guest(client)  # 取得既有訪客身分或建立新的訪客世界
    assert client.put('/api/profile', json={'name': '小光', 'bio': '每天前進一點', 'timezone': 'Asia/Taipei'}).status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    response = client.post('/api/goals', json=goal_payload())  # 透過實際測試用戶端操作 API 並保留回應
    assert response.status_code == 201, response.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    return me, response.json()  # 回傳後續測試步驟所需資料


def register(client, username='lumi_user'):  # 升級測試帳號並更新 CSRF 標頭
    result = client.post('/api/auth/claim', json={'username': username, 'password': 'a-good-password-2026'})  # 透過實際測試用戶端操作 API 並保留回應
    assert result.status_code == 200, result.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    client.headers['X-CSRF-Token'] = result.json()['csrf_token']  # 保存「client.headers['X-CSRF-Token']」供後續驗證或回傳使用
    return result.json()  # 回傳後續測試步驟所需資料


def draft(client, goal, **overrides):  # 建立可覆寫欄位的虛構經歷草稿
    payload = {'raw_text': '今天練習了半小時，感到很充實。', 'occurred_at': '2026-10-26T23:50:00+08:00',
               'goal_id': goal['id'], 'contributions': [{'action_id': goal['actions'][0]['id'], 'quantity': '0.5'}]}  # 準備將送出或用於指紋比對的完整內容
    payload.update(overrides)  # 合併本次明確設定的欄位
    response = client.post('/api/experiences/drafts', json=payload)  # 透過實際測試用戶端操作 API 並保留回應
    assert response.status_code == 201, response.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    return response.json()  # 回傳後續測試步驟所需資料


def confirm_payload(d, request_id='confirm-1', **overrides):  # 建立攜帶版本與提交代碼的人工確認測試資料
    result = {'request_id': request_id, 'expected_revision': d['revision'], 'summary': '練習了半小時。',
              'person_id': d.get('person_id'), 'contributions': d['contributions'], 'tasks': ['明天繼續練習']}  # 透過實際測試用戶端操作 API 並保留回應
    result.update(overrides)  # 合併本次明確設定的欄位
    return result  # 回傳後續測試步驟所需資料
