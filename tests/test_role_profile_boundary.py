"""未核准角色設定不可透過正式 HTTP 入口寫入；保留歷史讀取另測。"""
from conftest import onboard, register


def test_role_profile_write_not_registered(client):
    onboard(client)
    register(client, 'role_boundary')
    person = client.post('/api/persons', json={'request_id': 'boundary-person', 'name': '合成人物'}).json()
    with client.app.state.service.db.connect() as c:
        before = {t: c.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0] for t in ('people', 'notes', 'requests')}
    response = client.put(f"/api/persons/{person['id']}/profile", json={
        'request_id': 'unapproved-profile', 'fields': {'personality': '不得寫入'}})
    assert response.status_code == 404
    with client.app.state.service.db.connect() as c:
        after = {t: c.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0] for t in before}
    assert after == before


def test_role_profile_absent_from_openapi(client):
    assert '/api/persons/{person_id}/profile' not in client.app.openapi()['paths']
    assert '/api/profile' in client.app.openapi()['paths']  # 本人基本資料 API 不受影響。
