"""儀表板唯讀口徑：採計、時區與 owner 邊界。"""
from fastapi.testclient import TestClient
from conftest import draft as create_draft, confirm_payload
from test_goal_journey import setup_user, create, advance, review


def draft(client, goal, **values):
    """本案例明確指定目標首日，不依不同工作樹的歷史fixture預設日期。"""
    values.setdefault('occurred_at', goal['start_date']+'T00:10:00+08:00')
    return create_draft(client, goal, **values)


def dashboard(client, goal):
    result = client.get('/api/goals/' + goal['id'] + '/dashboard')
    assert result.status_code == 200, result.text
    return result.json()


def test_empty_dashboard_is_read_only_and_preserves_exact_numbers(client):
    setup_user(client)
    g = create(client)
    before = client.get('/api/state').json()
    vm = dashboard(client, g)
    assert vm['today'] == '2026-10-27' and vm['timezone'] == 'Asia/Taipei'
    assert len(vm['habits']) == 3 and vm['habits'][0]['progress'] == '0'
    assert vm['habits'][0]['target'] == '2'
    assert all(a['plannedToday'] and a['plannedQuantityToday'] == '1' for a in vm['habits'])
    assert [d['date'] for d in vm['trend']['days']] == ['2026-10-21','2026-10-22','2026-10-23','2026-10-24','2026-10-25','2026-10-26','2026-10-27']
    assert sum(d['confirmedExperienceCount'] for d in vm['trend']['days']) == 0
    assert client.get('/api/state').json() == before


def test_multiple_contributions_deduplicate_and_link_tasks_drafts(client):
    setup_user(client)
    g = create(client)
    d = draft(client, g, contributions=[{'action_id':a['id'],'quantity':'2.125'} for a in g['actions']])
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d)).status_code == 201
    unconfirmed = draft(client,g)
    vm = dashboard(client,g)
    assert vm['habits'][0]['progress'] == '2.125'
    assert vm['trend']['days'][-1]['confirmedExperienceCount'] == 1
    assert len(vm['trend']['days'][-1]['experiences']) == 1
    assert len(vm['openTasks']) == 1 and vm['drafts'][0]['id'] == unconfirmed['id']
    assert vm['habits'][0]['confirmedToday'] is True
    assert vm['unconfirmedDraftCount'] == 1


def test_fixed_timezone_midnight_and_pending_acceptance(app,client):
    setup_user(client)
    g = create(client)
    advance(app,'2026-10-29T01:00:00+00:00')
    d = draft(client,g,occurred_at='2026-10-27T16:01:00+00:00')
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d)).status_code == 201
    vm = dashboard(client,g)
    assert vm['goal']['status'] == 'awaiting_review'
    assert len(vm['pendingContributions']) == 1
    assert sum(x['confirmedExperienceCount'] for x in vm['trend']['days']) == 0
    schedules=[{'action_id':a['id'],'dates':['2026-10-29','2026-10-30'],'weekdays':[],'cycle':'month'} for a in g['actions']]
    extended=review(client,client.get('/api/goals/'+g['id']).json(),decision='extend',deadline='2026-10-30',schedules=schedules).json()
    pending=extended['pending_contributions'][0]
    result=client.post('/api/goals/'+g['id']+'/pending/'+pending['id']+'/accept',json={'request_id':'accept-dash','expected_revision':extended['revision'],'confirmed':True,'quantity':'0.5'})
    assert result.status_code == 200, result.text
    client.put('/api/profile',json={'name':'測試者','bio':'時區','timezone':'America/Los_Angeles'})
    vm=dashboard(client,g)
    assert vm['today']=='2026-10-29' and vm['timezone']=='Asia/Taipei'
    assert next(x for x in vm['trend']['days'] if x['date']=='2026-10-28')['confirmedExperienceCount']==1


def test_dashboard_filters_goal_and_rejects_foreign_owner(app,client):
    setup_user(client)
    old=create(client)
    d=draft(client,old)
    client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d))
    assert review(client,client.get('/api/goals/'+old['id']).json()).status_code==200
    new=create(client,key='next')
    vm=dashboard(client,new)
    assert vm['openTasks']==[] and vm['unconfirmedDraftCount']==0
    assert sum(x['confirmedExperienceCount'] for x in vm['trend']['days'])==0
    with TestClient(app) as other:
        setup_user(other)
        assert other.get('/api/goals/'+new['id']+'/dashboard').status_code==404
    client.post('/api/auth/logout')
    assert client.get('/api/goals/'+new['id']+'/dashboard').status_code==401


def test_versions_today_quantity_and_legacy_unknown_period(app,client):
    from test_habit_versions import change
    setup_user(client)
    g=create(client)
    changed=change(client,g,per_occurrence='3').json()
    assert dashboard(client,g)['habits'][0]['plannedQuantityToday']=='1'
    advance(app,'2026-10-27T16:00:00+00:00')
    vm=dashboard(client,g)
    assert vm['habits'][0]['plannedQuantityToday']=='3'
    assert vm['habits'][0]['target']=='4'
    with app.state.service.db.connect(write=True) as c:
        c.execute('UPDATE goals SET start_date=NULL,deadline=NULL,schedule_timezone=NULL WHERE id=?',(g['id'],))
    vm=dashboard(client,g)
    assert vm['goal']['status']=='needs_setup'
    assert not any(a['plannedToday'] for a in vm['habits'])


def test_seven_days_cutoff_and_read_only_archived_goal(app,client):
    setup_user(client)
    g=create(client,deadline='2026-11-15',dates=['2026-10-27','2026-11-02'])
    d=draft(client,g)
    assert client.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d)).status_code==201
    advance(app,'2026-11-02T07:00:00+00:00')
    assert sum(x['confirmedExperienceCount'] for x in dashboard(client,g)['trend']['days'])==1
    # 此例只驗七日統計，延長隔離測試session避免訪客到期遮蔽日期斷言。
    with app.state.service.db.connect(write=True) as c:
        c.execute("UPDATE sessions SET expires_at='2026-12-01T00:00:00+00:00'")
    advance(app,'2026-11-03T07:00:00+00:00')
    assert sum(x['confirmedExperienceCount'] for x in dashboard(client,g)['trend']['days'])==0
    fresh=client.get('/api/goals/'+g['id']).json()
    assert review(client,fresh).status_code==200
    before=client.get('/api/state').json()
    assert dashboard(client,g)['goal']['status']=='ended'
    assert dashboard(client,g)['habits'][0]['progress']=='0.5'
    assert client.get('/api/state').json()==before


def test_completed_dashboard_preserves_progress_and_no_sources_are_invented(client):
    from test_evidence_notes import upload
    setup_user(client)
    g=create(client)
    evidence=upload(client,g).json()
    fresh=client.get('/api/goals/'+g['id']).json()
    result=client.post('/api/goals/'+g['id']+'/complete',json={'request_id':'done-dashboard','expected_revision':fresh['revision'],'evidence_ids':[evidence['id']],'confirmed':True})
    assert result.status_code==200,result.text
    vm=dashboard(client,g)
    assert vm['goal']['status']=='completed'
    assert vm['habits'][0]['progress']=='0'
    assert sum(x['confirmedExperienceCount'] for x in vm['trend']['days'])==0


def test_detail_habits_expose_schedule_count_next_date_and_versions(client):
    setup_user(client)
    g=create(client)
    vm=dashboard(client,g)
    for a in vm['habits']:
        assert a['scheduledDayCount']==2
        assert a['nextScheduledDate']=='2026-10-27'
        assert a['scheduleDates']==['2026-10-27','2026-10-28']
        assert a['quantityVersions'][0]['quantity']=='1'


def test_postgresql_dashboard_uses_native_timestamp_and_boolean_sql():
    """驗證方言契約；此 stub 不冒充真 PostgreSQL 連線驗收。"""
    from contextlib import contextmanager
    from datetime import datetime, timezone
    from app.goals import GoalsMixin
    statements=[]
    class Connection:
        def execute(self,sql,args=()):
            statements.append(sql)
            return []
    class Database:
        backend='postgresql'
        @contextmanager
        def connect(self):
            yield Connection()
    class Service(GoalsMixin):
        db=Database()
        def _owned_user(self,c,owner):return {'timezone':'Asia/Taipei'}
        def _goal(self,c,id,owner):return {'id':id,'title':'測試','outcome':'完成','status':'active','start_date':'2026-10-01','deadline':'2026-11-30','revision':1,'today':'2026-10-27','schedule_timezone':'Asia/Taipei','actions':[],'pending_contributions':[]}
        def now(self):return datetime(2026,10,27,tzinfo=timezone.utc)
    Service().goal_dashboard('owner','goal')
    assert any('e.occurred_at>=CAST(? AS timestamptz)' in sql for sql in statements)
    assert all('julianday' not in sql and 't.done=0' not in sql for sql in statements)
    assert any('NOT t.done' in sql for sql in statements)
