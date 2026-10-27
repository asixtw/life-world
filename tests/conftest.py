from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.config import DemoPolicy


@pytest.fixture
def app(tmp_path):
    return create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                      clock=lambda: datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc))


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


def guest(client):
    result = client.post('/api/auth/guest')
    assert result.status_code in (200, 201), result.text
    client.headers['X-CSRF-Token'] = result.json()['csrf_token']
    return result.json()


def goal_payload(request_id='goal-1'):
    return {'request_id': request_id, 'title': '靠近更好的自己', 'outcome': '完成一個自己的作品',
            'actions': [{'title': title, 'unit': unit, 'target': '10', 'level': i + 1, 'weekdays': [0, 2, 4]}
                        for i, (title, unit) in enumerate([('練習', '小時'), ('記錄', '篇'), ('交流', '次')])]}


def onboard(client):
    me = guest(client)
    assert client.put('/api/profile', json={'name': '小光', 'bio': '每天前進一點', 'timezone': 'Asia/Taipei'}).status_code == 200
    response = client.post('/api/goals', json=goal_payload())
    assert response.status_code == 201, response.text
    return me, response.json()


def register(client, username='lumi_user'):
    result = client.post('/api/auth/claim', json={'username': username, 'password': 'a-good-password-2026'})
    assert result.status_code == 200, result.text
    client.headers['X-CSRF-Token'] = result.json()['csrf_token']
    return result.json()


def draft(client, goal, **overrides):
    payload = {'raw_text': '今天練習了半小時，感到很充實。', 'occurred_at': '2026-10-26T23:50:00+08:00',
               'goal_id': goal['id'], 'contributions': [{'action_id': goal['actions'][0]['id'], 'quantity': '0.5'}]}
    payload.update(overrides)
    response = client.post('/api/experiences/drafts', json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def confirm_payload(d, request_id='confirm-1', **overrides):
    result = {'request_id': request_id, 'expected_revision': d['revision'], 'summary': '練習了半小時。',
              'person_id': d.get('person_id'), 'contributions': d['contributions'], 'tasks': ['明天繼續練習']}
    result.update(overrides)
    return result
