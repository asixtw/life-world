import copy

import pytest
from fastapi.testclient import TestClient

from conftest import guest, goal_payload, onboard, register


def test_unauthenticated_access(client):
    assert client.get('/api/auth/me').status_code == 401
    assert client.get('/api/state').status_code == 401


def test_first_goal_is_mandatory_and_lumi_is_born_after_commit(client):
    me = guest(client)
    assert me['lumi_hatched'] is False
    assert client.get('/api/state').status_code == 409
    assert client.post('/api/people', json={'name': '朋友'}).status_code == 409
    assert client.post('/api/goals', json=goal_payload()).status_code == 409
    assert client.put('/api/profile', json={'name': '小光', 'bio': '認真生活', 'timezone': 'Asia/Taipei'}).status_code == 200
    result = client.post('/api/goals', json=goal_payload())
    assert result.status_code == 201
    state = client.get('/api/state').json()
    assert state['lumi']['hatched'] is True
    assert len(state['goals'][0]['actions']) == 3
    assert [a['level'] for a in state['goals'][0]['actions']] == [1, 2, 3]


def test_guest_start_is_idempotent_and_goal_request_retries(client):
    me, goal = onboard(client)
    assert guest(client)['owner_id'] == me['owner_id']
    again = client.post('/api/goals', json=goal_payload())
    assert again.status_code == 201
    assert again.json()['id'] == goal['id']
    changed = goal_payload(); changed['title'] = '另一個目標'
    assert client.post('/api/goals', json=changed).status_code == 409
    assert len(client.get('/api/state').json()['goals']) == 1


@pytest.mark.parametrize('mutation', ['two_actions', 'four_actions', 'empty_title', 'bad_level', 'bad_day', 'repeated_day', 'zero_target', 'nonfinite'])
def test_invalid_goal_does_not_hatch_lumi(client, mutation):
    guest(client)
    client.put('/api/profile', json={'name': '小光', 'bio': '生活', 'timezone': 'Asia/Taipei'})
    data = copy.deepcopy(goal_payload())
    if mutation == 'two_actions': data['actions'].pop()
    if mutation == 'four_actions': data['actions'].append(data['actions'][0])
    if mutation == 'empty_title': data['title'] = '   '
    if mutation == 'bad_level': data['actions'][0]['level'] = 4
    if mutation == 'bad_day': data['actions'][0]['weekdays'] = [7]
    if mutation == 'repeated_day': data['actions'][0]['weekdays'] = [0, 0]
    if mutation == 'zero_target': data['actions'][0]['target'] = '0'
    if mutation == 'nonfinite': data['actions'][0]['target'] = 'NaN'
    assert client.post('/api/goals', json=data).status_code == 422
    assert client.get('/api/auth/me').json()['lumi_hatched'] is False


def test_profile_validation(client):
    guest(client)
    assert client.put('/api/profile', json={'name': ' ', 'bio': '', 'timezone': 'No/SuchZone'}).status_code == 422


def test_csrf_and_cross_origin_writes_rejected(client):
    guest(client)
    del client.headers['X-CSRF-Token']
    assert client.put('/api/profile', json={'name': 'x', 'bio': 'y', 'timezone': 'Asia/Taipei'}).status_code == 403
    assert client.post('/api/auth/guest', headers={'Origin': 'https://evil.example'}).status_code == 403


def test_claim_rotates_session_and_keeps_owner_and_goal(client):
    me, goal = onboard(client)
    old_cookie = client.cookies.get('lw_session')
    claimed = register(client)
    assert claimed['owner_id'] == me['owner_id']
    assert claimed['status'] == 'registered'
    assert client.cookies.get('lw_session') != old_cookie
    assert client.get('/api/state').json()['goals'][0]['id'] == goal['id']
    assert client.get('/api/auth/me', headers={'Cookie': 'lw_session=' + old_cookie}).status_code == 401


@pytest.mark.parametrize('username,password', [('x', 'short'), ('bad name', 'a-good-password'), ('valid_name', 'short')])
def test_claim_validation(client, username, password):
    onboard(client)
    assert client.post('/api/auth/claim', json={'username': username, 'password': password}).status_code == 422
    assert client.get('/api/auth/me').json()['status'] == 'guest'


def test_logout_revokes_and_login_restores(client):
    _, goal = onboard(client); register(client)
    old_cookie = client.cookies.get('lw_session')
    assert client.post('/api/auth/logout').status_code == 204
    assert client.get('/api/state').status_code == 401
    assert client.get('/api/auth/me', headers={'Cookie': 'lw_session=' + old_cookie}).status_code == 401
    assert client.post('/api/auth/login', json={'username': 'lumi_user', 'password': 'wrong'}).status_code == 401
    result = client.post('/api/auth/login', json={'username': 'lumi_user', 'password': 'a-good-password-2026'})
    assert result.status_code == 200
    assert client.get('/api/state').json()['goals'][0]['id'] == goal['id']


def test_existing_account_conflict_never_merges_guest_data(app, client):
    onboard(client); register(client)
    with TestClient(app) as other:
        _, other_goal = onboard(other)
        login = {'username': 'lumi_user', 'password': 'a-good-password-2026'}
        assert other.post('/api/auth/login', json=login).status_code == 409
        result = other.post('/api/auth/login', json=dict(login, discard_guest=True))
        assert result.status_code == 200
        assert other_goal['id'] not in [g['id'] for g in other.get('/api/state').json()['goals']]


def test_page_and_static_assets_are_available(client):
    assert client.get('/').status_code == 200
    assert client.get('/static/app.js').status_code == 200
    assert client.get('/static/styles.css').status_code == 200
    assert client.get('/api/health').json()['status'] == 'ok'
