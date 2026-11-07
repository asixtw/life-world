"""人工確認後跨 App 實例讀回；正常、失敗與重送由既有經歷案例補足。"""
from fastapi.testclient import TestClient
from app.main import create_app
from conftest import onboard, draft, confirm_payload


def test_confirmed_world_survives_new_app_instance(sqlite_app, sqlite_client):
    """重建服務及用戶端仍由同一資料庫讀回，非前端快取；此案例僅 SQLite。"""
    _, goal = onboard(sqlite_client)
    d = draft(sqlite_client, goal)
    before = sqlite_client.get('/api/state').json()
    assert before['experiences'] == []
    assert before['goals'][0]['actions'][0]['progress'] == '0'
    path = '/api/drafts/' + d['id'] + '/confirm'
    body = confirm_payload(d)
    receipt = sqlite_client.post(path, json=body)
    assert receipt.status_code == 201
    recreated = create_app(database=sqlite_app.state.service.db, policy=sqlite_app.state.service.policy,
                           clock=sqlite_app.state.service.clock)
    with TestClient(recreated) as returning:
        returning.cookies.update(sqlite_client.cookies)
        returning.headers.update(sqlite_client.headers)
        state = returning.get('/api/state').json()
        assert state['goals'][0]['actions'][0]['progress'] == '0.5'
        assert len(state['experiences']) == len(state['tasks']) == 1
        assert state['rewards']['total'] == 3
        assert returning.post(path, json=body).json() == receipt.json()
        assert returning.get('/api/state').json()['rewards']['total'] == 3
