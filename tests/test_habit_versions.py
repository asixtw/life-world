"""習慣用量按日期生效；排程變更不得改寫真實投入。"""
from datetime import datetime
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.db import Database
from app.main import create_app
from test_goal_journey import setup_user, create, review, advance
from conftest import draft, confirm_payload


def schedules(goal, **changes):
    """只改第一個習慣，其他習慣沿用舊 API 格式。"""
    rows = [dict(action_id=a['id'], dates=a['dates'], weekdays=a['weekdays'], cycle=a['cycle']) for a in goal['actions']]
    rows[0].update(changes)
    return rows


def change(client, goal, key='edit-1', **changes):
    return review(client, goal, decision='schedule', key=key, schedules=schedules(goal, **changes))


def test_quantity_versions_start_tomorrow_and_latest_same_day_wins(app, client):
    setup_user(client)
    goal = create(client)
    first = change(client, goal, title='每日練習', per_occurrence='2')
    assert first.status_code == 200, first.text
    a = first.json()['actions'][0]
    assert a['title'] == '每日練習' and a['unit'] == '次'
    assert a['per_occurrence'] == '1' and a['target'] == '3'
    assert [(v['effective_from'], v['quantity']) for v in a['quantity_versions']] == [('2026-10-27', '1'), ('2026-10-28', '2')]
    assert client.post('/api/goals/' + goal['id'] + '/review', json={
        'request_id': 'edit-1', 'expected_revision': goal['revision'], 'decision': 'schedule',
        'confirmed': True, 'schedules': schedules(goal, title='每日練習', per_occurrence='2')}).json() == first.json()
    second = change(client, first.json(), key='edit-2', per_occurrence='3')
    assert second.status_code == 200, second.text
    assert second.json()['actions'][0]['target'] == '4'
    assert len(second.json()['actions'][0]['quantity_versions']) == 2
    assert len(second.json()['reviews']) == 2
    prior = json.loads(second.json()['reviews'][1]['previous_state'])
    assert prior['actions'][0]['quantity_versions'][-1]['quantity'] == '2'
    advance(app, '2026-10-27T16:00:00+00:00')
    assert client.get('/api/goals/' + goal['id']).json()['actions'][0]['per_occurrence'] == '3'


def test_quantity_keeps_progress_rewards_and_earlier_day_standards(app, client):
    setup_user(client)
    goal = create(client, deadline='2026-10-30', dates=['2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'])
    d = draft(client, goal, occurred_at='2026-10-27T12:00:00+08:00')
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 201
    current = client.get('/api/goals/' + goal['id']).json()
    points = client.get('/api/state').json()['rewards']['total']
    first = change(client, current, per_occurrence='2').json()
    advance(app, '2026-10-28T16:00:00+00:00')
    current = client.get('/api/goals/' + goal['id']).json()
    result = change(client, current, key='later', per_occurrence='4')
    assert result.status_code == 200, result.text
    a = result.json()['actions'][0]
    assert a['target'] == '9' and a['progress'] == '0.5'
    assert a['per_occurrence'] == '2'
    assert client.get('/api/state').json()['rewards']['total'] == points
    assert first['actions'][0]['quantity_versions'][0]['quantity'] == '1'
    days = client.get('/api/goals/' + goal['id'] + '/calendar?start=2026-10-27&end=2026-10-30').json()
    assert [r['planned_quantities'][a['id']] for r in days] == ['1', '2', '2', '4']


@pytest.mark.parametrize('field,value', [('per_occurrence', '0'), ('per_occurrence', 'NaN'), ('per_occurrence', '-1'), ('per_occurrence', True), ('per_occurrence', '1000000000001'), ('per_occurrence', '0.0000001'), ('title', '  '), ('unit', '分鐘')])
def test_invalid_habit_edit_is_atomic(client, field, value):
    setup_user(client)
    goal = create(client)
    result = change(client, goal, **{field: value})
    assert result.status_code == 422, result.text
    assert client.get('/api/goals/' + goal['id']).json() == goal


def test_last_day_or_no_future_scheduled_date_rejects_quantity_but_allows_name(app, client):
    setup_user(client)
    goal = create(client, deadline='2026-10-27', dates=['2026-10-27'])
    result = change(client, goal, per_occurrence='2')
    assert result.status_code == 422 and result.json()['error']['code'] == 'no_future_occurrence'
    assert change(client, goal, key='name-only', title='練習（更正名稱）').status_code == 200


def test_fixed_goal_zone_controls_effective_date_even_after_profile_change(app, client):
    advance(app, '2026-10-28T02:00:00+00:00')
    setup_user(client, 'America/New_York')
    goal = create(client, deadline='2026-10-30', dates=['2026-10-28', '2026-10-29'])
    client.put('/api/profile', json={'name': '測試者', 'bio': '時區切換', 'timezone': 'Asia/Taipei'})
    result = change(client, goal, per_occurrence='2')
    assert result.status_code == 200, result.text
    assert result.json()['actions'][0]['quantity_versions'][-1]['effective_from'] == '2026-10-28'


def test_conflict_foreign_owner_and_closed_goal_are_rejected(app, client):
    setup_user(client)
    goal = create(client)
    changed = change(client, goal, title='練習名稱更正').json()
    assert change(client, goal, key='stale', per_occurrence='2').status_code == 409
    with TestClient(app) as other:
        setup_user(other)
        assert change(other, changed, key='foreign', per_occurrence='2').status_code == 404
    ended = review(client, changed, key='end').json()
    assert change(client, ended, key='closed', per_occurrence='2').status_code == 409


def test_explicit_legacy_total_remains_fixed(client):
    from conftest import onboard
    _, goal = onboard(client)
    result = change(client, goal, per_occurrence='2')
    assert result.status_code == 200, result.text
    assert result.json()['actions'][0]['target'] == '10'


def test_same_day_reset_to_current_quantity_cancels_pending_amount(client):
    setup_user(client)
    goal = create(client)
    changed = change(client, goal, per_occurrence='3').json()
    result = change(client, changed, key='reset', per_occurrence='1')
    assert result.status_code == 200, result.text
    assert result.json()['actions'][0]['target'] == '2'
    assert len(result.json()['reviews']) == 2


def test_midnight_requires_reconfirmation_of_effective_date(app, client):
    setup_user(client)
    goal = create(client, deadline='2026-10-30', dates=['2026-10-27', '2026-10-28', '2026-10-29'])
    advance(app, '2026-10-27T16:00:00+00:00')
    result = change(client, goal, per_occurrence='2', expected_effective_from='2026-10-28')
    assert result.status_code == 409 and result.json()['error']['code'] == 'effective_date_changed'
    assert client.get('/api/goals/' + goal['id']).json()['revision'] == goal['revision']


def test_validation_of_later_habit_rolls_back_earlier_quantity_write(client):
    setup_user(client)
    goal = create(client)
    rows = schedules(goal, per_occurrence='2')
    rows[-1].update(dates=['2026-10-27'], per_occurrence='2')
    result = review(client, goal, decision='schedule', schedules=rows)
    assert result.status_code == 422 and result.json()['error']['code'] == 'no_future_occurrence'
    assert client.get('/api/goals/' + goal['id']).json() == goal


def test_same_revision_concurrent_changes_only_one_commits(app, client):
    from concurrent.futures import ThreadPoolExecutor
    setup_user(client)
    goal = create(client)
    token, csrf = client.cookies.get('lw_session'), client.headers['X-CSRF-Token']
    def submit(quantity):
        with TestClient(app) as other:
            other.cookies.set('lw_session', token)
            other.headers['X-CSRF-Token'] = csrf
            return change(other, goal, key='concurrent-' + quantity, per_occurrence=quantity).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit, ['2', '3'])) == [200, 409]
    assert len(client.get('/api/goals/' + goal['id']).json()['reviews']) == 1


def test_migration_backfills_old_actions_without_altering_original_columns(tmp_path):
    """在舊結構副本上遷移，逐欄核對所有既有表。"""
    old_dir = tmp_path / 'old'
    old_dir.mkdir()
    db_path = old_dir / 'lifeworld.sqlite3'
    with sqlite3.connect(db_path) as c:
        c.execute('CREATE TABLE schema_migrations(version TEXT PRIMARY KEY)')
        for path in sorted(Path('app/migrations').glob('*.sql')):
            if path.name >= '005': break
            c.executescript(path.read_text())
            c.execute('INSERT INTO schema_migrations VALUES (?)', (path.name,))
        c.commit()
    with TestClient(create_app(data_dir=tmp_path / 'seed', clock=lambda: datetime.fromisoformat('2026-10-27T07:00:00+00:00'))) as seed:
        setup_user(seed)
        goal = create(seed)
        with sqlite3.connect(tmp_path / 'seed' / 'lifeworld.sqlite3') as src, sqlite3.connect(db_path) as dst:
            # 以新程式建立正常舊欄位資料，再移除新表，重播 005。
            src.backup(dst)
    with sqlite3.connect(db_path) as c:
        for name, in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'habit_%'").fetchall():
            c.execute('DROP TABLE ' + name)
        c.execute("DELETE FROM schema_migrations WHERE version >= '005'")
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'schema_migrations'")]
        before = {t: c.execute('SELECT * FROM ' + t).fetchall() for t in tables}
    db = Database(old_dir)
    with db.connect() as c:
        assert {t: [tuple(r) for r in c.execute('SELECT * FROM ' + t)] for t in tables} == before
        versions = c.execute('SELECT action_id,quantity FROM habit_quantity_versions').fetchall()
        assert len(versions) == 3 and {v['action_id'] for v in versions} == {a['id'] for a in goal['actions']}
        assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert c.execute('PRAGMA foreign_key_check').fetchall() == []
