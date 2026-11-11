"""P0：Unified Schema 010 前的程式相容性修正（統一人物系統）。

驗證：
1. SQLite 010 等價遷移的表與欄位與 PG 010 目標一致（42 表＋SQLite 專有的 2 張關係記憶表）。
2. 程式不再有位置式 INSERT，也不以 SELECT * 對外輸出會在 010 增加欄位的人物、關係、作品資料。
3. 人物建立支援 request_id 防重送；不帶 request_id 的舊用法仍可用。
4. 人物、關係的 API 回應欄位固定，不因 010 新增欄位而改變（新欄位等 P1 正式開放）。
5. GuestPurger 只接受已審核的資料表形狀（Alpha 現況 34 表、010 的 42 表），依各自外鍵契約檢查並清除；
   保留限流、遷移台帳、清除收據，並排除外部身分。
6. 人物、經歷、關係的帳號隔離。

只用隔離 SQLite；不連任何雲端資料庫。
"""
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from conftest import confirm_payload, draft, onboard, register
from app import guest_fk, guest_lifecycle
from app.guest_lifecycle import GuestPurger, abandon

APP = Path(__file__).resolve().parents[1] / 'app'
UNIFIED_010 = {'actions', 'ai_generations', 'auth_rate_buckets', 'completions', 'contributions', 'data_consents', 'draft_stories', 'drafts',
               'evidence', 'experience_mentions', 'experience_participants', 'experience_stories', 'experiences', 'external_identities',
               'fact_sources', 'goal_reviews', 'goals', 'guest_abandonments', 'habit_quantity_versions', 'interaction_events',
               'interaction_experiences', 'interaction_people', 'note_sources', 'notes', 'pending_contributions', 'people',
               'person_connection_experience_sources', 'person_connections', 'person_facts', 'person_goals', 'requests', 'reward_ledger',
               'schema_migrations', 'session_turns', 'sessions', 'story_history', 'subject_experience_people', 'subject_experiences', 'tasks',
               'users', 'work_versions', 'works'}
SQLITE_ONLY = {'relationship_features', 'relationship_memory_preferences'}
# P0 期間人物的對外欄位固定為 010 之前的契約；新欄位在 P1 才開放。
# 關係在 link_table 模式（SQLite 預設）多了 revision 與人物經歷來源，兩種來源都是 ID 陣列（E2E 010 前置切換）。
PERSON_KEYS = {'id', 'owner_id', 'name', 'role', 'notes', 'created_at', 'roles', 'tags', 'category', 'followed', 'revision', 'common_context',
               'stats', 'interaction_count', 'last_interaction_at', 'has_active_goal', 'goal_titles'}
CONNECTION_KEYS = {'id', 'owner_id', 'person_a', 'person_b', 'label', 'revision', 'source_experience_ids', 'source_person_experience_ids',
                   'relation_types', 'description', 'confirmation_status'}  # P4：關係類型、共用描述與狀態


def ready(client, username):
    _, goal = onboard(client)
    register(client, username)
    return goal


def tables(client):
    with client.app.state.service.db.connect() as c:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def test_sqlite_010_matches_unified_target(client):
    assert tables(client) == UNIFIED_010 | SQLITE_ONLY
    with client.app.state.service.db.connect() as c:
        people = [r[1] for r in c.execute('PRAGMA table_info(people)')]
        connections = [r[1] for r in c.execute('PRAGMA table_info(person_connections)')]
        works = [r[1] for r in c.execute('PRAGMA table_info(works)')]
        subject_people = [r[1] for r in c.execute('PRAGMA table_info(subject_experience_people)')]
        version = c.execute("SELECT 1 FROM schema_migrations WHERE version='010_unified_schema.sql'").fetchone()
    assert people[-6:] == ['person_type', 'person_subtype', 'aliases', 'description', 'origin_type', 'status']
    assert connections[-4:] == ['relation_types', 'description', 'confirmation_status', 'revision']
    assert works[-1] == 'profile_person_id' and 'interacted' in subject_people and version is not None


def test_no_positional_insert_or_select_star_on_changed_tables():
    """位置式 INSERT 依賴欄序；SELECT * 會把 010 新欄位帶進回應或快取。"""
    positional, star = [], []
    for path in APP.glob('*.py'):
        text = path.read_text(encoding='utf-8')
        positional += [f'{path.name}:{m.group(0)}' for m in re.finditer(r'INSERT INTO [a-z_]+ (VALUES|SELECT)', text)]
        star += [f'{path.name}:{m.group(0)}' for m in re.finditer(r"SELECT \* FROM (people|person_connections|works)\b|SELECT \* FROM ' \+", text)]
    assert positional == [], positional
    assert star == [], star


def test_person_create_request_id_is_idempotent_and_optional(client):
    ready(client, 'p0_people')
    body = {'request_id': 'person-1', 'name': '林先生', 'roles': ['同事']}
    first = client.post('/api/people', json=body)
    again = client.post('/api/people', json=body)
    assert first.status_code == 201 and again.status_code == 201, (first.text, again.text)
    assert again.json()['id'] == first.json()['id'], '同一 request_id 重送只建立一筆'
    conflict = client.post('/api/people', json={**body, 'name': '王小姐'})
    assert conflict.status_code == 409 and conflict.json()['error']['code'] == 'idempotency_conflict'
    legacy = client.post('/api/people', json={'name': '舊用法'})
    assert legacy.status_code == 201, '不帶 request_id 的舊用戶端仍可建立'
    with client.app.state.service.db.connect() as c:
        assert c.execute("SELECT COUNT(*) FROM people WHERE name='林先生'").fetchone()[0] == 1


def test_person_and_connection_dto_do_not_leak_010_columns(client):
    ready(client, 'p0_dto')
    a = client.post('/api/people', json={'name': '甲'}).json()
    b = client.post('/api/people', json={'name': '乙'}).json()
    assert set(a) == PERSON_KEYS
    edited = client.patch(f"/api/people/{a['id']}", json={'expected_revision': a['revision'], 'followed': True})
    assert edited.status_code == 200 and set(edited.json()) == PERSON_KEYS
    listing = client.get('/api/people').json()
    items = listing['items'] if isinstance(listing, dict) else listing
    assert items and all(set(item) == PERSON_KEYS for item in items)
    connection = client.post(f"/api/people/{a['id']}/connections", json={'request_id': 'c-1', 'other_person_id': b['id'], 'label': '同事'})
    assert connection.status_code == 201, connection.text
    assert set(connection.json()) == CONNECTION_KEYS
    overview = client.get(f"/api/people/{a['id']}/overview").json()
    assert set(overview['person']) == PERSON_KEYS
    assert set(overview['connections'][0]) == {'id', 'label', 'person', 'revision', 'source_experience_ids', 'source_person_experience_ids'}
    assert set(overview['connections'][0]['person']) == PERSON_KEYS


def _seed_guest_world(client):
    """訪客世界加上 010 新表的資料（訪客沒有對應 API，直接寫入合成資料）。"""
    me, goal = onboard(client)
    owner, now = me['owner_id'], '2026-10-27T07:00:00+00:00'
    d = draft(client, goal)
    confirmed = client.post(f"/api/drafts/{d['id']}/confirm", json=confirm_payload(d, request_id='guest-confirm'))
    assert confirmed.status_code == 201, confirmed.text
    experience_id = confirmed.json()['experience_id']
    db = client.app.state.service.db
    with db.connect(write=True) as c:
        for pid, name in (('g-p1', '甲'), ('g-p2', '乙')):
            c.execute('INSERT INTO people(id,owner_id,name,created_at) VALUES (?,?,?,?)', (pid, owner, name, now))
        c.execute("INSERT INTO person_connections(id,owner_id,person_a,person_b,label,source_experience_ids) VALUES ('g-c',?,'g-p1','g-p2','同事','[]')", (owner,))
        c.execute('INSERT INTO subject_experiences(id,owner_id,experience_type,origin_type,raw_text,created_at,updated_at) VALUES (?,?,?,?,?,?,?)',
                  ('g-s', owner, 'real', 'manual', '甲的經歷', now, now))
        c.execute('INSERT INTO subject_experience_people(subject_experience_id,owner_id,person_id,role,created_at,interacted) VALUES (?,?,?,?,?,?)',
                  ('g-s', owner, 'g-p1', 'participant', now, 1))
        c.execute('INSERT INTO person_connection_experience_sources(connection_id,owner_id,subject_experience_id) VALUES (?,?,?)', ('g-c', owner, 'g-s'))
        # 第 81 條 FK：來源也可以是我的紀錄（experiences）；清除時要先刪來源連結，再刪經歷。
        c.execute('INSERT INTO person_connection_experience_sources(connection_id,owner_id,experience_id,source_position) VALUES (?,?,?,1)',
                  ('g-c', owner, experience_id))
        c.execute("INSERT INTO works(id,owner_id,kind,title,status,current_version,revision,created_at,updated_at,profile_person_id) "
                  "VALUES ('g-w',?,'character_card','卡','active',1,1,?,?,'g-p1')", (owner, now, now))
        c.execute("INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) "
                  "VALUES ('g-w',?,1,NULL,'human','character_card.v2','{}',NULL,?)", (owner, now))
        c.execute("INSERT INTO auth_rate_buckets(scope,key_hash,window_started_at,attempts) VALUES ('guest_source_create',?,?,1)", ('a' * 64, now))
    return owner


def test_guest_purger_clears_unified_tables_and_keeps_receipts(client):
    owner = _seed_guest_world(client)
    other = TestClient(client.app)
    ready(other, 'p0_survivor')
    other_person = other.post('/api/people', json={'name': '不受影響'}).json()
    db = client.app.state.service.db
    start = datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc)
    with db.connect(write=True, owner=owner) as c:
        abandon(c, owner, start)
    migrations_before = tables_snapshot(db, 'schema_migrations')
    result = GuestPurger(db, lambda: start + timedelta(days=15)).purge(owner)
    assert result == 'completed', result
    with db.connect() as c:
        leftovers = {t: c.execute(f'SELECT COUNT(*) FROM "{t}" WHERE owner_id=?', (owner,)).fetchone()[0]
                     for t in UNIFIED_010 | SQLITE_ONLY if 'owner_id' in [r[1] for r in c.execute(f'PRAGMA table_info("{t}")')]}
        receipt = c.execute('SELECT status FROM guest_abandonments WHERE owner_id=?', (owner,)).fetchone()
        rate = c.execute('SELECT COUNT(*) FROM auth_rate_buckets').fetchone()[0]
        user = c.execute('SELECT 1 FROM users WHERE id=?', (owner,)).fetchone()
        survivor = c.execute('SELECT 1 FROM people WHERE id=?', (other_person['id'],)).fetchone()
    assert {t: n for t, n in leftovers.items() if n and t != 'guest_abandonments'} == {}, leftovers
    assert receipt['status'] == 'completed' and rate == 1 and user is None and survivor is not None
    assert tables_snapshot(db, 'schema_migrations') == migrations_before


def tables_snapshot(db, table):
    with db.connect() as c:
        return sorted(tuple(r) for r in c.execute(f'SELECT * FROM "{table}"'))


def test_guest_purger_rejects_unreviewed_shape(client):
    owner = _seed_guest_world(client)
    db = client.app.state.service.db
    with db.connect(write=True) as c:
        c.execute('CREATE TABLE unreviewed_extra (id TEXT PRIMARY KEY, owner_id TEXT)')
        abandon(c, owner, datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc))
    result = GuestPurger(db, lambda: datetime(2026, 11, 20, tzinfo=timezone.utc)).purge(owner)
    assert result == 'unreviewed_table'
    with db.connect() as c:
        assert c.execute('SELECT 1 FROM users WHERE id=?', (owner,)).fetchone() is not None, '未審核的形狀不得刪除任何資料'


def test_reviewed_shapes_and_fk_contracts():
    alpha = guest_lifecycle.ALPHA_034
    assert len(alpha) == 34 and len(guest_lifecycle.UNIFIED_010) == 42 and guest_lifecycle.UNIFIED_010 == UNIFIED_010
    assert guest_lifecycle.reviewed_shape(set(alpha), 'postgresql') == 'alpha_034'
    assert guest_lifecycle.reviewed_shape(set(UNIFIED_010), 'postgresql') == 'unified_010'
    assert guest_lifecycle.reviewed_shape(UNIFIED_010 | SQLITE_ONLY, 'sqlite') == 'unified_010'
    e2e_038 = (set(alpha) - {'auth_rate_buckets'}) | {'ai_generations', 'data_consents', 'session_turns', 'works', 'work_versions'}
    for shape, backend in ((e2e_038, 'postgresql'), (UNIFIED_010 | SQLITE_ONLY, 'postgresql')):
        with pytest.raises(ValueError, match='unreviewed_table'):
            guest_lifecycle.reviewed_shape(shape, backend)
    for shape, name, size in (('alpha_034', 'guest_fk_contract.json', 61), ('unified_010', 'guest_fk_contract_010.json', 81)):
        contract = json.loads((APP / name).read_text(encoding='utf-8'))
        assert len(contract) == size
        if shape == 'unified_010':
            assert ['person_connection_experience_sources', ['experience_id', 'owner_id'], 'experiences', ['id', 'owner_id']] in contract
        groups = [(a, tuple(b), c, tuple(d)) for a, b, c, d in contract]
        guest_fk.verify_graph(groups, shape)  # 依形狀選對契約即通過
        other = 'unified_010' if shape == 'alpha_034' else 'alpha_034'
        with pytest.raises(ValueError, match='unreviewed_fk'):
            guest_fk.verify_graph(groups, other)


def test_people_relations_and_records_are_owner_isolated(client):
    goal = ready(client, 'p0_owner_a')
    mine = client.post('/api/people', json={'name': '甲'}).json()
    d = draft(client, goal, person_id=mine['id'])
    confirmed = client.post(f"/api/drafts/{d['id']}/confirm", json=confirm_payload(d, request_id='own-1'))
    assert confirmed.status_code == 201, confirmed.text
    experience_id = confirmed.json()['experience_id']
    other = TestClient(client.app)
    other_goal = ready(other, 'p0_owner_b')
    theirs = other.post('/api/people', json={'name': '乙'}).json()
    assert other.get(f"/api/people/{mine['id']}/overview").status_code == 404
    assert other.patch(f"/api/people/{mine['id']}", json={'expected_revision': mine['revision'], 'name': 'x'}).status_code == 404
    link = other.post(f"/api/people/{theirs['id']}/connections", json={'request_id': 'x-1', 'other_person_id': mine['id'], 'label': '盜連'})
    assert link.status_code == 404, link.text
    source = other.post(f"/api/people/{theirs['id']}/connections",
                        json={'request_id': 'x-2', 'other_person_id': other.post('/api/people', json={'name': '丙'}).json()['id'],
                              'label': '盜用來源', 'source_experience_ids': [experience_id]})
    assert source.status_code in (404, 422), source.text
    foreign_draft = other.post('/api/experiences/drafts', json={'raw_text': '盜用人物', 'occurred_at': '2026-10-27T00:10:00+08:00',
                                                                'goal_id': other_goal['id'], 'person_id': mine['id'], 'contributions': []})
    assert foreign_draft.status_code == 404, foreign_draft.text
    assert other.get(f'/api/connections/stories/{experience_id}').status_code == 404
    with client.app.state.service.db.connect() as c:
        assert c.execute("SELECT name FROM people WHERE id=?", (mine['id'],)).fetchone()['name'] == '甲'


def _world_counters(client, person_id):
    """積分、目標、真人互動統計的快照（P0 只讀現有 API 與表）。"""
    state = client.get('/api/state')
    assert state.status_code == 200, state.text
    overview = client.get(f'/api/people/{person_id}/overview')
    assert overview.status_code == 200, overview.text
    person = overview.json().get('person', overview.json())
    with client.app.state.service.db.connect() as c:
        counts = {t: c.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]
                  for t in ('reward_ledger', 'contributions', 'interaction_events', 'interaction_people', 'experiences', 'experience_participants', 'goals')}
    return {'state': state.json(), 'interaction_count': person.get('interaction_count'), 'last_interaction_at': person.get('last_interaction_at'),
            'stats': person.get('stats'), 'counts': counts}


def test_subject_experience_without_owner_does_not_touch_points_goals_or_interactions(client):
    """不涉及使用者本人的人物經歷（含參與者直接互動）不觸發積分、目標及真人互動統計。

    P0 尚未開放人物經歷 API；這裡直接寫入 010 的兩張表，確認現有積分／目標／互動流程完全不讀它們。
    """
    ready(client, 'p0_subject')
    a = client.post('/api/people', json={'name': '主角'}).json()
    b = client.post('/api/people', json={'name': '同伴'}).json()
    before = _world_counters(client, b['id'])
    owner = a['owner_id']
    now = '2026-10-27T07:00:00+00:00'
    with client.app.state.service.db.connect(write=True) as c:
        c.execute('INSERT INTO subject_experiences(id,owner_id,experience_type,origin_type,title,raw_text,creator_person_id,owner_participates,'
                  'created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                  ('se-1', owner, 'fictional', 'manual', '兩人的冒險', '主角與同伴一起出發。', a['id'], 0, now, now))
        c.execute('INSERT INTO subject_experience_people(subject_experience_id,owner_id,person_id,role,created_at,interacted) VALUES (?,?,?,?,?,?)',
                  ('se-1', owner, a['id'], 'subject', now, 0))
        c.execute('INSERT INTO subject_experience_people(subject_experience_id,owner_id,person_id,role,created_at,interacted) VALUES (?,?,?,?,?,?)',
                  ('se-1', owner, b['id'], 'participant', now, 1))
    assert _world_counters(client, b['id']) == before


def test_only_the_person_experiences_module_writes_subject_experiences():
    """人物經歷（2026-11-11 E1 起開放）：只有 person_experiences.py 寫入 subject_experiences／subject_experience_people，
    其他模組（含我的紀錄的草稿／確認流程）都不寫入，兩種經歷不混用。P0 時這裡的期望是「沒有任何模組寫入」。

    E2E 010 前置切換後，關聯表 person_connection_experience_sources 只由 relation_sources.py 寫入；
    人物模組透過它替換來源，readiness 只做 LIMIT 0 讀取，訪客清除以動態表名刪除。
    """
    write_person_experience = re.compile(r'(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(subject_experiences|subject_experience_people)\b')
    assert [p.name for p in APP.glob('*.py') if write_person_experience.search(p.read_text(encoding='utf-8'))] == ['person_experiences.py']
    users = sorted(p.name for p in APP.glob('*.py') if 'person_connection_experience_sources' in p.read_text(encoding='utf-8'))
    assert users == ['guest_lifecycle.py', 'main.py', 'relation_sources.py'], users
    replacers = sorted(p.name for p in APP.glob('*.py') if 'relation_sources.replace(' in p.read_text(encoding='utf-8'))
    assert replacers == ['people.py'], replacers
