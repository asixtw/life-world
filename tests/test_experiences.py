from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from conftest import onboard, draft, confirm_payload, register


def test_draft_and_suggestion_never_award_or_overwrite_raw(client):
    _, goal = onboard(client); d = draft(client, goal)
    response = client.post('/api/drafts/' + d['id'] + '/suggest')
    assert response.status_code == 200
    assert response.json()['applied'] is False
    state = client.get('/api/state').json()
    assert state['rewards']['total'] == 0
    assert state['experiences'] == []
    assert state['drafts'][0]['raw_text'] == d['raw_text']


def test_confirm_partial_contribution_backdate_tasks_and_idempotency(client):
    _, goal = onboard(client); d = draft(client, goal)
    body = confirm_payload(d)
    result = client.post('/api/drafts/' + d['id'] + '/confirm', json=body)
    assert result.status_code == 201, result.text
    receipt = result.json()
    assert receipt['points_awarded'] == 3
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=body).json() == receipt
    state = client.get('/api/state').json()
    assert state['rewards']['total'] == 3
    assert len(state['experiences']) == 1
    assert len(state['tasks']) == 1
    assert state['goals'][0]['actions'][0]['progress'] == '0.5'
    exp = state['experiences'][0]
    assert exp['occurred_at'] == '2026-10-26T15:50:00+00:00'
    assert exp['created_at'] == '2026-10-27T07:00:00+00:00'
    assert exp['person_id'] is None
    assert exp['raw_text'] == d['raw_text']
    assert exp['summary'] == body['summary']


def test_new_request_cannot_confirm_same_draft_twice(client):
    _, goal = onboard(client); d = draft(client, goal)
    path = '/api/drafts/' + d['id'] + '/confirm'
    assert client.post(path, json=confirm_payload(d)).status_code == 201
    assert client.post(path, json=confirm_payload(d, request_id='another-key')).status_code == 409
    assert client.get('/api/state').json()['rewards']['total'] == 3


def test_same_key_changed_payload_is_conflict(client):
    _, goal = onboard(client); d = draft(client, goal)
    path = '/api/drafts/' + d['id'] + '/confirm'
    assert client.post(path, json=confirm_payload(d)).status_code == 201
    assert client.post(path, json=confirm_payload(d, summary='不同內容')).status_code == 409


@pytest.mark.parametrize('quantity', ['0', '-1', 'NaN', 'Infinity', '0.0000001', '1000000000001'])
def test_bad_contribution_has_no_side_effects(client, quantity):
    _, goal = onboard(client)
    payload = {'raw_text': '真實紀錄', 'occurred_at': '2026-10-26T12:00:00+08:00', 'goal_id': goal['id'],
               'contributions': [{'action_id': goal['actions'][0]['id'], 'quantity': quantity}]}
    assert client.post('/api/experiences/drafts', json=payload).status_code == 422
    assert client.get('/api/state').json()['rewards']['total'] == 0


@pytest.mark.parametrize('when', ['2026-10-28T12:00:00+08:00', '2026-10-26T12:00:00', 'not-a-date'])
def test_invalid_event_time(client, when):
    _, goal = onboard(client)
    assert client.post('/api/experiences/drafts', json={'raw_text': '紀錄', 'occurred_at': when, 'goal_id': goal['id'], 'contributions': []}).status_code == 422


def test_very_old_event_is_allowed_and_gets_points(client):
    _, goal = onboard(client); d = draft(client, goal, occurred_at='2001-01-01T00:01:00+08:00')
    result = client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d))
    assert result.status_code == 201
    assert result.json()['points_awarded'] == 3


def test_decimal_sum_is_exact_and_never_completes_goal(client):
    _, goal = onboard(client)
    for i, quantity in enumerate(['0.1', '0.2', '12']):
        d = draft(client, goal, contributions=[{'action_id': goal['actions'][0]['id'], 'quantity': quantity}])
        assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d, request_id='req-' + str(i))).status_code == 201
    state = client.get('/api/state').json()
    assert state['goals'][0]['actions'][0]['progress'] == '12.3'
    assert state['goals'][0]['status'] == 'active'


def test_unlinked_event_is_valid_after_first_goal(client):
    _, goal = onboard(client); d = draft(client, goal, goal_id=None, contributions=[])
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 201
    assert client.get('/api/state').json()['goals'][0]['actions'][0]['progress'] == '0'


def test_draft_edit_revision_and_confirm_conflict(client):
    _, goal = onboard(client); d = draft(client, goal)
    body = {k: d[k] for k in ['raw_text', 'occurred_at', 'goal_id', 'person_id', 'contributions']}
    body.update(expected_revision=d['revision'], raw_text='修改後原文')
    updated = client.put('/api/drafts/' + d['id'], json=body)
    assert updated.status_code == 200
    assert updated.json()['revision'] == d['revision'] + 1
    assert client.put('/api/drafts/' + d['id'], json=body).status_code == 409
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 409


def test_guest_person_gate_preserves_draft_and_claim_resumes(client):
    _, goal = onboard(client); d = draft(client, goal)
    assert client.post('/api/people', json={'name': '朋友'}).status_code == 403
    path = '/api/drafts/' + d['id'] + '/confirm'
    assert client.post(path, json=confirm_payload(d, person_id='any-person')).status_code == 403
    assert client.get('/api/drafts/' + d['id']).json()['raw_text'] == d['raw_text']
    register(client)
    person = client.post('/api/people', json={'name': '朋友', 'role': '同學'}).json()
    assert client.post(path, json=confirm_payload(d, person_id=person['id'])).status_code == 201
    state = client.get('/api/state').json()
    assert state['people'][0]['interaction_count'] == 1
    assert state['experiences'][0]['person_id'] == person['id']


def test_cross_owner_access_and_action_injection(app, client):
    _, goal = onboard(client); d = draft(client, goal); register(client)
    p = client.post('/api/people', json={'name': '朋友'}).json()
    with TestClient(app) as other:
        _, second = onboard(other); register(other, 'other_user')
        assert other.get('/api/drafts/' + d['id']).status_code == 404
        assert other.get('/api/goals/' + goal['id']).status_code == 404
        assert other.post('/api/experiences/drafts', json={'raw_text': '紀錄', 'occurred_at': '2026-10-26T12:00:00+08:00', 'goal_id': second['id'], 'person_id': p['id'], 'contributions': []}).status_code == 404
        own = draft(other, second)
        result = other.post('/api/drafts/' + own['id'] + '/confirm', json=confirm_payload(own, contributions=[{'action_id': goal['actions'][0]['id'], 'quantity': '1'}]))
        assert result.status_code == 422
        assert other.get('/api/state').json()['rewards']['total'] == 0


def test_confirmation_rolls_back_all_writes_on_database_failure(app, client, monkeypatch):
    _, goal = onboard(client); d = draft(client, goal)
    def fail(*args, **kwargs):
        raise RuntimeError('injected ledger failure')
    monkeypatch.setattr(app.state.service, '_award', fail)
    with TestClient(app, raise_server_exceptions=False) as safe:
        safe.cookies.update(client.cookies); safe.headers.update(client.headers)
        result = safe.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d))
    assert result.status_code == 500
    state = client.get('/api/state').json()
    assert state['experiences'] == []
    assert state['tasks'] == []
    assert state['rewards']['total'] == 0
    assert state['drafts'][0]['status'] == 'draft'


def test_concurrent_retries_commit_once(app, client):
    _, goal = onboard(client); d = draft(client, goal)
    cookie = client.cookies.get('lw_session'); csrf = client.headers['X-CSRF-Token']
    def submit(_):
        with TestClient(app) as concurrent:
            concurrent.cookies.set('lw_session', cookie)
            return concurrent.post('/api/drafts/' + d['id'] + '/confirm', headers={'X-CSRF-Token': csrf}, json=confirm_payload(d))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, range(4)))
    assert [r.status_code for r in results] == [201] * 4
    assert len({r.json()['experience_id'] for r in results}) == 1
    state = client.get('/api/state').json()
    assert state['rewards']['total'] == 3
    assert state['goals'][0]['actions'][0]['progress'] == '0.5'
