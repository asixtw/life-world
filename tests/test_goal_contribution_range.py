"""貢獻按目標固定時區檢查，期外經歷仍可移除貢獻後保存。"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest
from conftest import draft, confirm_payload
from test_goal_journey import setup_user, create, advance


@pytest.mark.parametrize('zone', ['Asia/Taipei', 'America/Los_Angeles', 'UTC'])
def test_before_start_is_rejected_atomically_and_can_save_without_credit(app, client, zone):
    setup_user(client, zone)
    goal=create(client)
    instant=datetime(2026,10,26,23,59,59,tzinfo=ZoneInfo(zone)).isoformat()
    d=draft(client, goal, occurred_at=instant)
    before=client.get('/api/state').json()
    body=confirm_payload(d, request_id='outside-confirm')
    result=client.post('/api/drafts/'+d['id']+'/confirm', json=body)
    assert result.status_code==422, result.text
    assert result.json()['error']['code']=='contribution_out_of_range'
    after=client.get('/api/state').json()
    for key in ['experiences','tasks','rewards','goals','people']:
        assert after[key]==before[key], key
    assert client.get('/api/drafts/'+d['id']).json()['status']=='draft'
    body['contributions']=[]
    saved=client.post('/api/drafts/'+d['id']+'/confirm', json=body)
    assert saved.status_code==201, saved.text
    assert client.post('/api/drafts/'+d['id']+'/confirm', json=body).json()==saved.json()
    state=client.get('/api/state').json()
    assert len(state['experiences'])==1 and state['goals'][0]['actions'][0]['progress']=='0'
    assert state['rewards']['total']==3


@pytest.mark.parametrize('when', ['2026-10-27T00:00:00+08:00','2026-10-28T23:59:59+08:00'])
def test_start_and_deadline_dates_are_inclusive(app,client,when):
    setup_user(client)
    goal=create(client)
    app.state.service.clock=lambda:datetime.fromisoformat(when).astimezone(timezone.utc)
    d=draft(client,goal,occurred_at=when)
    body=confirm_payload(d)
    result=client.post('/api/drafts/'+d['id']+'/confirm',json=body)
    assert result.status_code==201,result.text
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=body).json()==result.json()
    assert client.get('/api/goals/'+goal['id']).json()['actions'][0]['progress']=='0.5'


@pytest.mark.parametrize('when,expected', [('2026-10-26T20:00:00+00:00',201),('2026-10-26T15:59:59+00:00',422)])
def test_account_timezone_change_does_not_move_goal_boundary(app,client,when,expected):
    setup_user(client)
    goal=create(client)
    assert client.put('/api/profile',json={'name':'時區測試者','bio':'固定目標時區','timezone':'Pacific/Auckland'}).status_code==200
    d=draft(client,goal,occurred_at=when)
    result=client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d))
    assert result.status_code==expected,result.text
    assert client.get('/api/goals/'+goal['id']).json()['schedule_timezone']=='Asia/Taipei'


def test_after_deadline_remains_pending_until_extension(app,client):
    setup_user(client)
    goal=create(client)
    advance(app,'2026-10-29T02:00:00+00:00')
    d=draft(client,goal,occurred_at='2026-10-29T00:00:00+08:00')
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d)).status_code==201
    current=client.get('/api/goals/'+goal['id']).json()
    assert current['actions'][0]['progress']=='0'
    assert len(current['pending_contributions'])==1


def test_legacy_unknown_period_is_pending_not_inferred(app,client):
    setup_user(client)
    goal=create(client)
    with app.state.service.db.connect(write=True) as c:
        c.execute('UPDATE goals SET start_date=NULL,deadline=NULL,schedule_timezone=NULL WHERE id=?',(goal['id'],))
    d=draft(client,goal,occurred_at='2026-10-26T12:00:00+08:00')
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d)).status_code==201
    current=client.get('/api/goals/'+goal['id']).json()
    assert current['status']=='needs_setup' and current['start_date'] is None
    assert current['actions'][0]['progress']=='0' and len(current['pending_contributions'])==1
