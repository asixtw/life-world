"""人物交會顯示回歸；只使用隔離合成資料與既有 API。"""
from fastapi.testclient import TestClient
import pytest
from conftest import onboard, register, draft, confirm_payload
from test_connections import people, saved_story, detail


def legacy(client, person=None, key='plain'):
    """建立既有 API 的普通／單一人物來源，不自行核准參與。"""
    goal = client.get('/api/state').json()['goals'][0]
    d = draft(client, goal, raw_text='獨自閱讀一本書', person_id=person, contributions=[])
    body = confirm_payload(d, request_id=key, contributions=[], tasks=[])
    response = client.post('/api/drafts/' + d['id'] + '/confirm', json=body)
    assert response.status_code == 201, response.text
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=body).json() == response.json()
    return response.json()['experience_id']


def test_plain_goal_and_empty_review_never_enter_connections(client):
    p = people(client)
    plain = legacy(client)
    assert client.get('/api/connections?involvement=legacy').json()['total'] == 0
    assert any(x['id'] == plain for x in client.get('/api/state').json()['experiences'])
    empty, _, _ = saved_story(client, p, participants=[], mentions=[])
    assert client.get('/api/connections').json()['total'] == 0
    assert detail(client, empty['experience_id'])['participants'] == []


def test_person_pending_pagination_focus_and_owner(client, app):
    p = people(client)
    legacy(client, key='plain')
    ids = {legacy(client, p[0]['id'], 'person-a'), legacy(client, p[0]['id'], 'person-b')}
    before = client.get('/api/state').json()
    pages = [client.get('/api/connections', params={'involvement': 'legacy', 'limit': 1, 'offset': i}).json() for i in range(2)]
    assert all(x['total'] == 2 for x in pages)
    assert {x['items'][0]['id'] for x in pages} == ids
    assert client.get('/api/connections', params={'involvement': 'legacy', 'person_id': p[1]['id']}).json()['total'] == 0
    with TestClient(app) as other:
        onboard(other); register(other, 'different_owner')
        assert other.get('/api/connections?involvement=legacy').json()['total'] == 0
        assert other.get('/api/connections', params={'person_id': p[0]['id']}).status_code == 404
    assert client.get('/api/state').json() == before


@pytest.mark.parametrize('role', ['participant', 'interaction', 'mention'])
def test_human_review_routes_roles_without_reaward(client, role):
    p = people(client)
    x = legacy(client, p[0]['id'])
    s = detail(client, x, manage=True)
    before = client.get('/api/state').json()
    story = {'title': '閱讀記錄', 'participants': [], 'mentions': []}
    if role == 'mention':
        story['mentions'] = [{'name': '閱讀', 'start': 2, 'end': 4, 'person_id': p[0]['id']}]
    else:
        story['participants'] = [{'person_id': p[0]['id'], 'interacted': role == 'interaction'}]
    body = {'request_id': 'review-person', 'expected_revision': s['revision'], 'confirmed': True, 'story': story}
    response = client.put('/api/connections/stories/' + x + '/people', json=body)
    assert response.status_code == 200, response.text
    assert client.put('/api/connections/stories/' + x + '/people', json=body).json() == response.json()
    assert client.get('/api/connections?involvement=legacy').json()['total'] == 0
    assert client.get('/api/connections').json()['total'] == (role != 'mention')
    assert client.get('/api/connections?involvement=mention').json()['total'] == (role == 'mention')
    stats = client.get('/api/people/' + p[0]['id'] + '/overview').json()['stats']
    assert stats['interactions'] == (role == 'interaction')
    assert stats['meetings'] == 0
    assert client.get('/api/state').json()['rewards'] == before['rewards']
    s = detail(client, x)
    response = client.post('/api/connections/stories/' + x + '/availability', json={'request_id': 'withdraw-role', 'expected_revision': s['revision'], 'available': False})
    assert response.status_code == 200
    assert client.get('/api/connections').json()['total'] == 0
    assert client.get('/api/connections?involvement=mention').json()['total'] == 0
    assert client.get('/api/state').json()['experiences'] == before['experiences']


def test_reusable_labels_contract_preserves_legacy_and_rejects_stale_repeat(client, app):
    """複用不改他人資料；空白／超長仍遵循原 Schema。"""
    people(client)
    body={'name':'甲','roles':['合作','合作','舊、完整角色'],'tags':['學校專題','學校專題'],'common_context':'資訊管理課'}
    a=client.post('/api/people',json=body).json()
    b=client.post('/api/people',json={**body,'name':'乙'}).json()
    assert b['roles']==['合作','舊、完整角色'] and b['tags']==['學校專題']
    patch={'expected_revision':b['revision'],'notes':'只修改備註'}
    assert client.patch('/api/people/'+b['id'],json=patch).status_code==200
    assert client.patch('/api/people/'+b['id'],json=patch).status_code==409
    assert client.get('/api/people/'+a['id']+'/overview').json()['person']==a
    for invalid in [{'roles':[' ']},{'tags':['字'*101]},{'common_context':'字'*1001}]:
        assert client.post('/api/people',json={**body,**invalid}).status_code==422
    with TestClient(app) as other:
        onboard(other);register(other,'label_other')
        assert other.get('/api/state').json()['people']==[]
        assert other.patch('/api/people/'+a['id'],json={'expected_revision':1,'tags':['外來']}).status_code==404
