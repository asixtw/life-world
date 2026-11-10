"""待新增人物只在最終確認交易內建立。"""
import pytest
from conftest import onboard, register, draft, confirm_payload


@pytest.mark.parametrize('relation', ['participant', 'interaction', 'mention'])
def test_pending_person_atomic_confirm_and_retry(client, relation):
    onboard(client); register(client)
    goal = client.get('/api/state').json()['goals'][0]
    pending = {'name': '小安', 'relation': relation}
    if relation == 'mention': pending['start'] = 2
    story = {'title': '一起閱讀', 'participants': [], 'mentions': [], 'pending_person': pending}
    d = draft(client, goal, raw_text='提到小安閱讀', story=story, contributions=[])
    assert d['story']['pending_person'] == pending
    assert client.get('/api/state').json()['people'] == []
    body = confirm_payload(d, contributions=[], story=story, story_reviewed=True)
    response = client.post('/api/drafts/' + d['id'] + '/confirm', json=body)
    assert response.status_code == 201, response.text
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=body).json() == response.json()
    state = client.get('/api/state').json()
    assert len(state['people']) == 1
    p = state['people'][0]
    assert p['name'] == '小安'
    assert client.get('/api/people/' + p['id'] + '/overview').json()['stats']['interactions'] == (relation == 'interaction')
    assert client.get('/api/connections').json()['total'] == (relation != 'mention')


def test_pending_invalid_guest_and_rollback(client):
    onboard(client)
    payload = {'raw_text': '提到小安', 'occurred_at': '2026-01-01T00:00:00Z', 'story': {'pending_person': {'name': '小安', 'relation': 'participant'}}}
    assert client.post('/api/experiences/drafts', json=payload).status_code == 403
    register(client)
    for name in ['', '  ', '長' * 101]:
        payload['story']['pending_person']['name'] = name
        assert client.post('/api/experiences/drafts', json=payload).status_code == 422
    payload['story']['pending_person']['name'] = '小安'
    d = client.post('/api/experiences/drafts', json=payload).json()
    body = confirm_payload(d, story=d['story'], story_reviewed=False, contributions=[])
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=body).status_code == 422
    assert client.get('/api/state').json()['people'] == []
    body.update(story_reviewed=True, person_updates=[{'dimension': 'food', 'value': '辣', 'evidence_type': 'observed_by_user', 'selected': True, 'conflicts_with': 'missing'}])
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=body).status_code in (404,422)
    state = client.get('/api/state').json()
    assert not state['people'] and not state['experiences'] and state['rewards']['total'] == 0


def test_pending_cross_owner_and_duplicate_span(client, app):
    """候選歸屬於草稿 Owner；提及不能與既有來源重複。"""
    from fastapi.testclient import TestClient
    onboard(client); register(client)
    payload = {'raw_text': '提到小安', 'occurred_at': '2026-01-01T00:00:00Z', 'story': {'pending_person': {'name': '小安', 'relation': 'mention', 'start': 2}}}
    d = client.post('/api/experiences/drafts', json=payload).json()
    with TestClient(app) as other:
        onboard(other); register(other, 'other_pending')
        body = confirm_payload(d, story=d['story'], story_reviewed=True, contributions=[])
        assert other.post('/api/drafts/' + d['id'] + '/confirm', json=body).status_code == 404
        assert not other.get('/api/state').json()['people']
    payload['story']['mentions'] = [{'name': '小安', 'start': 2, 'end': 4}]
    assert client.post('/api/experiences/drafts', json=payload).status_code == 422
    assert not client.get('/api/state').json()['people']
