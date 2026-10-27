from datetime import timedelta

from conftest import onboard, draft, confirm_payload, register


def test_raw_text_is_preserved_byte_for_byte(client):
    _, goal = onboard(client)
    original = '\n  今天的原文，包含空白與換行。\n\n'
    d = draft(client, goal, raw_text=original)
    assert d['raw_text'] == original
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 201
    assert client.get('/api/state').json()['experiences'][0]['raw_text'] == original


def test_whitespace_only_raw_text_rejected(client):
    _, goal = onboard(client)
    assert client.post('/api/experiences/drafts', json={'raw_text': ' \n ', 'occurred_at': '2026-10-26T12:00:00+08:00', 'contributions': []}).status_code == 422


def test_password_spaces_are_not_silently_removed(client):
    onboard(client)
    result = client.post('/api/auth/claim', json={'username': 'space_user', 'password': ' secret-password '})
    assert result.status_code == 200
    client.headers['X-CSRF-Token'] = result.json()['csrf_token']
    client.post('/api/auth/logout')
    assert client.post('/api/auth/login', json={'username': 'space_user', 'password': 'secret-password'}).status_code == 401
    assert client.post('/api/auth/login', json={'username': 'space_user', 'password': ' secret-password '}).status_code == 200


def test_expired_session_cannot_read_or_write(app, client):
    onboard(client)
    current = app.state.service.clock()
    app.state.service.clock = lambda: current + timedelta(hours=app.state.service.policy.session_hours + 1)
    assert client.get('/api/state').status_code == 401
    assert client.post('/api/people', json={'name': '朋友'}).status_code == 401


def test_database_does_not_store_plaintext_password_or_session(app, client):
    onboard(client); register(client)
    token = client.cookies.get('lw_session')
    with app.state.service.db.connect() as c:
        user = c.execute("SELECT * FROM users WHERE status='registered'").fetchone()
        assert user['password_hash'].startswith('$argon2')
        assert 'a-good-password-2026' not in user['password_hash']
        assert c.execute('SELECT token_hash FROM sessions').fetchone()['token_hash'] != token


def test_28_day_calendar_respects_per_action_weekdays(client):
    _, goal = onboard(client)
    response = client.get('/api/goals/' + goal['id'] + '/calendar')
    assert response.status_code == 200
    days = response.json()
    assert len(days) == 28
    assert days[0]['date'] == '2026-10-27'
    assert days[0]['action_ids'] == []
    assert set(days[1]['action_ids']) == {a['id'] for a in goal['actions']}


def test_assistant_failure_preserves_draft_and_manual_confirmation(app, client):
    class Broken:
        def suggest(self, text):
            raise TimeoutError('test provider timeout')
    _, goal = onboard(client); d = draft(client, goal)
    app.state.service.assistant = Broken()
    assert client.post('/api/drafts/' + d['id'] + '/suggest').status_code == 503
    assert client.get('/api/drafts/' + d['id']).json()['raw_text'] == d['raw_text']
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 201


def test_task_checking_does_not_award_or_complete_actions(client):
    _, goal = onboard(client); d = draft(client, goal)
    client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d))
    task = client.get('/api/state').json()['tasks'][0]
    assert client.patch('/api/tasks/' + task['id'], json={'done': True}).status_code == 200
    assert client.patch('/api/tasks/' + task['id'], json={'done': True}).status_code == 200
    state = client.get('/api/state').json()
    assert state['tasks'][0]['done'] == 1
    assert state['rewards']['total'] == 3
    assert state['goals'][0]['actions'][0]['progress'] == '0.5'
