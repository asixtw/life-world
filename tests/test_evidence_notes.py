import base64

import pytest
from fastapi.testclient import TestClient

from conftest import onboard, register, draft, confirm_payload

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGNkaGBgYGBgYmBgYGBgAAAGKgCE5tEtPAAAAABJRU5ErkJggg==')


def upload(client, goal, content=PNG, name='成果.png', mime='image/png'):
    return client.post('/api/goals/' + goal['id'] + '/evidence', files={'file': (name, content, mime)})


def test_goal_needs_evidence_and_explicit_human_confirmation(client):
    _, goal = onboard(client)
    path = '/api/goals/' + goal['id'] + '/complete'
    assert client.post(path, json={'request_id': 'done-1', 'evidence_ids': [], 'confirmed': True}).status_code == 422
    evidence = upload(client, goal)
    assert evidence.status_code == 201, evidence.text
    eid = evidence.json()['id']
    assert client.post(path, json={'request_id': 'done-1', 'evidence_ids': [eid], 'confirmed': False}).status_code == 422
    body = {'request_id': 'done-1', 'evidence_ids': [eid], 'confirmed': True, 'reflection': '我確認已完成成果'}
    result = client.post(path, json=body)
    assert result.status_code == 200, result.text
    assert client.post(path, json=body).json() == result.json()
    assert client.get('/api/state').json()['goals'][0]['status'] == 'completed'
    assert client.get('/api/state').json()['rewards']['total'] == 0
    assert client.get('/api/evidence/' + eid).content == PNG


def test_duplicate_upload_reuses_evidence(client):
    _, goal = onboard(client)
    a = upload(client, goal); b = upload(client, goal)
    assert a.json()['id'] == b.json()['id']
    assert len(client.get('/api/goals/' + goal['id']).json()['evidence']) == 1


@pytest.mark.parametrize('content,name,mime,code', [(b'', 'empty.png', 'image/png', 422), (b'x' * 4097, 'large.png', 'image/png', 413), (b'<script>bad</script>', 'fake.png', 'image/png', 415), (PNG, '../../secret.png', 'image/png', 422), (PNG, 'file.svg', 'image/svg+xml', 415), (PNG[:30], 'broken.png', 'image/png', 415)])
def test_invalid_upload(client, content, name, mime, code):
    _, goal = onboard(client)
    assert upload(client, goal, content, name, mime).status_code == code
    assert client.get('/api/goals/' + goal['id']).json()['evidence'] == []


def test_other_goal_and_other_owner_evidence_rejected(app, client):
    _, goal = onboard(client); evidence = upload(client, goal).json()
    from conftest import goal_payload
    second = client.post('/api/goals', json=goal_payload('goal-2')).json()
    assert client.post('/api/goals/' + second['id'] + '/complete', json={'request_id': 'done', 'evidence_ids': [evidence['id']], 'confirmed': True}).status_code == 404
    with TestClient(app) as other:
        _, g = onboard(other)
        assert other.get('/api/evidence/' + evidence['id']).status_code == 404
        assert upload(other, goal).status_code == 404
        assert other.post('/api/goals/' + g['id'] + '/complete', json={'request_id': 'done', 'evidence_ids': [evidence['id']], 'confirmed': True}).status_code == 404


def test_completed_goal_contribution_policy_is_explicit_and_preserves_draft(client):
    _, goal = onboard(client); d = draft(client, goal); e = upload(client, goal).json()
    assert client.post('/api/goals/' + goal['id'] + '/complete', json={'request_id': 'done', 'evidence_ids': [e['id']], 'confirmed': True}).status_code == 200
    result = client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d))
    assert result.status_code == 409
    assert result.json()['error']['code'] == 'policy_required'
    assert client.get('/api/drafts/' + d['id']).json()['status'] == 'draft'


@pytest.mark.parametrize('kind', ['preparation', 'simulation', 'message'])
def test_creative_notes_never_change_reality(client, kind):
    onboard(client); register(client)
    p = client.post('/api/people', json={'name': '朋友'}).json()
    result = client.post('/api/notes', json={'person_id': p['id'], 'kind': kind, 'title': '先練習表達', 'content': '模擬台詞，非真人發言'})
    assert result.status_code == 201
    state = client.get('/api/state').json()
    assert len(state['notes']) == 1
    assert state['experiences'] == []
    assert state['rewards']['total'] == 0
    assert state['people'][0]['interaction_count'] == 0


def test_data_survives_new_app_instance(app, client, tmp_path):
    from app.main import create_app
    _, goal = onboard(client); d = draft(client, goal)
    client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d))
    register(client)
    with TestClient(create_app(data_dir=tmp_path, policy=app.state.service.policy, clock=app.state.service.clock)) as restarted:
        assert restarted.post('/api/auth/login', json={'username': 'lumi_user', 'password': 'a-good-password-2026'}).status_code == 200
        state = restarted.get('/api/state').json()
        assert state['rewards']['total'] == 3
        assert state['goals'][0]['actions'][0]['progress'] == '0.5'
        assert len(state['experiences']) == 1
