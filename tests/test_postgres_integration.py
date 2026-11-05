"""只有實際 PG18 執行才算通過；共用 API 案例另由 PG fixture 全量執行。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
import hashlib
import json
import os
import threading

import pg8000.dbapi as driver
import pytest
from fastapi.testclient import TestClient

from app.errors import DomainError
from app.db import Database
from app.main import create_app
from app.postgres import PostgresDatabase
from app.service import encoded
from conftest import onboard, register, draft, confirm_payload
from pg_support import bootstrap, settings

pytestmark = pytest.mark.skipif(os.environ.get('LIFEWORLD_TEST_BACKEND') != 'postgresql',
                                reason='requires dedicated synthetic PostgreSQL 18 container')


def app_raw():
    raw = driver.connect(user='lw_app', database='life_world_dev', **bootstrap.test_config())
    raw.autocommit = True
    with closing(raw.cursor()) as c:
        c.execute('SET search_path TO lw_core_draft,pg_catalog')
    return raw


def test_catalog_types_constraints_ownership_and_no_theater(app, tmp_path):
    """以 PG catalog 核對，而非只解析 SQL 檔案。"""
    assert app.state.service.db.backend == 'postgresql'
    assert not list(tmp_path.glob('*.sqlite*'))
    with bootstrap.admin_connection() as raw, closing(raw.cursor()) as c:
        c.execute("SELECT count(*) FROM pg_tables WHERE schemaname='lw_core_draft'")
        assert c.fetchone()[0] == 32
        c.execute("SELECT count(*), bool_and(convalidated) FROM pg_constraint WHERE connamespace='lw_core_draft'::regnamespace AND contype='f'")
        assert c.fetchone() == [60, True]
        c.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='lw_core_draft'")
        assert c.fetchone()[0] == 207
        c.execute("SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='lw_core_draft'")
        types = {(t, n): d for t, n, d in c.fetchall()}
        # 32表逐欄與既有 SQLite migration 的全新合成參照比對，不能只驗六個樣本。
        numeric = {('actions','target'),('actions','per_occurrence'),('contributions','quantity'),
                   ('habit_quantity_versions','quantity'),('pending_contributions','quantity'),
                   ('pending_contributions','accepted_quantity')}
        jsonb = {('actions','weekdays'),('actions','schedule_dates'),('completions','evidence_ids'),
                 ('draft_stories','payload'),('drafts','contributions'),('goal_reviews','previous_state'),
                 ('goal_reviews','new_state'),('people','roles'),('people','tags'),
                 ('person_connections','source_experience_ids'),('requests','response'),
                 ('story_history','before_json'),('story_history','after_json')}
        boolean = {('actions','target_is_derived'),('experience_participants','interacted'),
                   ('experience_stories','reviewed'),('experience_stories','available'),
                   ('people','followed'),('tasks','done')}
        dates = {('goals','start_date'),('goals','deadline'),('habit_quantity_versions','effective_from')}
        expected_types, expected_not_null, expected_fk = {},set(),set()
        with Database(tmp_path / 'explicit-sqlite-schema-reference').connect() as reference:
            tables = [r[0] for r in reference.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            assert len(tables) == 32
            for table in tables:
                for col in reference.execute('PRAGMA table_info("' + table + '")'):
                    key = (table,col['name'])
                    expected_types[key] = ('numeric' if key in numeric else 'jsonb' if key in jsonb else
                        'boolean' if key in boolean else 'date' if key in dates else
                        'timestamp with time zone' if col['name'].endswith('_at') else
                        {'TEXT':'text','INTEGER':'bigint','BLOB':'bytea'}[col['type']])
                    if col['notnull'] or col['pk']:
                        expected_not_null.add(key)
                for fk in reference.execute('PRAGMA foreign_key_list("' + table + '")'):
                    assert fk['on_update'] == fk['on_delete'] == 'NO ACTION'
                    expected_fk.add((table,fk['from'],fk['table'],fk['to']))
        for table in ('goal_reviews','story_history'):
            expected_types[table,'audit_seq'] = 'bigint'
            expected_not_null.add((table,'audit_seq'))
        assert types == expected_types
        c.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='lw_core_draft' AND is_nullable='NO'")
        assert {tuple(r) for r in c.fetchall()} == expected_not_null
        c.execute("SELECT table_name,column_name,identity_generation FROM information_schema.columns WHERE table_schema='lw_core_draft' AND is_identity='YES'")
        assert {tuple(r) for r in c.fetchall()} == {('goal_reviews','audit_seq','ALWAYS'),('story_history','audit_seq','ALWAYS')}
        c.execute("""SELECT t.relname,a.attname,r.relname,b.attname
            FROM pg_constraint f JOIN pg_class t ON t.oid=f.conrelid JOIN pg_class r ON r.oid=f.confrelid
            CROSS JOIN LATERAL unnest(f.conkey,f.confkey) k(src,dst)
            JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.src
            JOIN pg_attribute b ON b.attrelid=r.oid AND b.attnum=k.dst
            WHERE f.connamespace='lw_core_draft'::regnamespace AND f.contype='f'
            AND f.confupdtype='a' AND f.confdeltype='a'""")
        assert {tuple(r) for r in c.fetchall()} == expected_fk
        for key, expected in {('actions','target'): 'numeric', ('drafts','contributions'): 'jsonb',
                              ('drafts','occurred_at'): 'timestamp with time zone',
                              ('goals','deadline'): 'date', ('tasks','done'): 'boolean',
                              ('evidence','content'): 'bytea'}.items():
            assert types[key] == expected
        c.execute("SELECT count(*) FROM pg_class WHERE relnamespace='lw_core_draft'::regnamespace AND relkind='S'")
        assert c.fetchone()[0] == 2
        c.execute("SELECT bool_and(relowner='lw_migration_role'::regrole) FROM pg_class WHERE relnamespace='lw_core_draft'::regnamespace AND relkind IN ('r','S')")
        assert c.fetchone()[0] is True
        c.execute("SELECT count(*) FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid LEFT JOIN pg_constraint c ON c.conindid=i.indexrelid WHERE t.relnamespace='lw_core_draft'::regnamespace AND c.oid IS NULL")
        assert c.fetchone()[0] == 11
        c.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname='lw_app'")
        assert c.fetchone() == [False] * 4
        c.execute("SELECT pg_has_role('lw_app','lw_migration_role','MEMBER')")
        assert c.fetchone()[0] is False
        c.execute("SELECT has_schema_privilege('lw_app','lw_core_draft','CREATE')")
        assert c.fetchone()[0] is False
        for sequence in ('goal_reviews_audit_seq_seq','story_history_audit_seq_seq'):
            for privilege in ('USAGE','SELECT','UPDATE'):
                c.execute('SELECT has_sequence_privilege(?, ?, ?)',('lw_app','lw_core_draft.'+sequence,privilege))
                assert c.fetchone()[0] is False


@pytest.mark.parametrize('statement,code', [
    ("INSERT INTO users(id,status,name,bio,timezone,created_at) VALUES ('bad','guest',NULL,'','UTC',now())", '23502'),
    ("INSERT INTO users(id,status,name,bio,timezone,created_at) VALUES ('bad','invalid','','','UTC',now())", '23514'),
    ("INSERT INTO users SELECT * FROM users LIMIT 1", '23505'),
    ("INSERT INTO sessions(token_hash,owner_id,csrf_token,created_at,expires_at) VALUES ('orphan','missing','csrf',now(),now())", '23503'),
])
def test_actual_constraints_reject_invalid_rows(client, statement, code):
    onboard(client)
    with app_raw() as raw, closing(raw.cursor()) as c:
        with pytest.raises(driver.DatabaseError) as error:
            c.execute(statement)
        assert error.value.args[0]['C'] == code
    assert client.get('/api/state').status_code == 200


def test_least_privilege_and_identity_without_sequence_grant(app, client):
    me, goal = onboard(client)
    d = draft(client, goal)
    e = client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).json()
    with app_raw() as raw, closing(raw.cursor()) as c:
        c.execute('SELECT current_user,current_schema()')
        assert c.fetchone() == ['lw_app', 'lw_core_draft']
        for forbidden in ('SELECT * FROM schema_migrations', 'CREATE TABLE forbidden(id text)',
                          'TRUNCATE users', "SELECT nextval('goal_reviews_audit_seq_seq')"):
            with pytest.raises(driver.DatabaseError) as error:
                c.execute(forbidden)
            assert error.value.args[0]['C'] == '42501'
        c.execute('INSERT INTO goal_reviews(id,owner_id,goal_id,decision,previous_state,new_state,reflection,created_at) VALUES (?,?,?,\'test\',\'{}\',\'{}\',\'\',now()) RETURNING audit_seq', ('review-test',me['owner_id'],goal['id']))
        assert c.fetchone()[0] == 1
        c.execute('INSERT INTO story_history(id,owner_id,experience_id,action,before_json,after_json,created_at) VALUES (?,?,?,\'test\',\'{}\',\'{}\',now()) RETURNING audit_seq', ('history-test',me['owner_id'],e['experience_id']))
        assert c.fetchone()[0] == 1
    assert client.get('/ready').status_code == 200


def test_decimal_jsonb_timezone_and_original_fingerprint(app, client):
    me, goal = onboard(client)
    d = draft(client, goal, contributions=[{'action_id':goal['actions'][0]['id'], 'quantity':'0.123456'}])
    body = confirm_payload(d)
    response = client.post('/api/drafts/' + d['id'] + '/confirm', json=body)
    assert response.status_code == 201, response.text
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=body).json() == response.json()
    with app.state.service.db.connect() as c:
        assert c.execute('SELECT quantity FROM contributions').fetchone()[0] == '0.123456'
        assert c.execute('SELECT ?::numeric', ('999999999999999.1234567890123456789',)).fetchone()[0] == '999999999999999.1234567890123456789'
        assert c.execute("SELECT '?'::text, ?::text", ("合成 ' ; DROP TABLE users; -- ?",)).fetchone()[1] == "合成 ' ; DROP TABLE users; -- ?"
        row = c.execute("SELECT fingerprint,response FROM requests WHERE owner_id=? AND operation='confirm'", (me['owner_id'],)).fetchone()
        payload = dict(body, draft_id=d['id'])
        assert row['fingerprint'] == hashlib.sha256(encoded(payload).encode()).hexdigest()
        assert json.loads(row['response']) == response.json()
    assert client.get('/api/drafts/' + d['id']).json()['occurred_at'] == '2026-10-26T16:10:00+00:00'


@pytest.mark.parametrize('same_request', [True, False])
def test_two_app_instances_confirm_once(app, client, tmp_path, same_request):
    """獨立 pool 模擬兩個 Cloud Run instance，不能只用 Python mutex 過關。"""
    me, goal = onboard(client)
    d = draft(client, goal)
    gate = threading.Barrier(2)

    def submit(number):
        database = PostgresDatabase(settings())
        other_app = create_app(data_dir=tmp_path, database=database,
                               policy=app.state.service.policy, clock=app.state.service.clock)
        with TestClient(other_app) as other:
            other.cookies.update(client.cookies)
            other.headers['X-CSRF-Token'] = me['csrf_token']
            gate.wait(timeout=10)
            return other.post('/api/drafts/' + d['id'] + '/confirm',
                              json=confirm_payload(d, 'race' if same_request else 'race-' + str(number)))
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(submit, (1, 2)))
    assert sorted(r.status_code for r in results) == ([201,201] if same_request else [201,409])
    if same_request:
        assert results[0].json() == results[1].json()
    state = client.get('/api/state').json()
    assert len(state['experiences']) == 1
    assert state['rewards']['total'] == 3


def test_revision_conflict_between_instances(app, client, tmp_path):
    me, goal = onboard(client)
    register(client)
    p = client.post('/api/people', json={'name':'合成人物'}).json()
    gate = threading.Barrier(2)
    def change(number):
        other_app = create_app(data_dir=tmp_path, database=PostgresDatabase(settings()),
                               policy=app.state.service.policy, clock=app.state.service.clock)
        with TestClient(other_app) as other:
            other.cookies.update(client.cookies)
            other.headers.update(client.headers)
            gate.wait(timeout=10)
            return other.patch('/api/people/' + p['id'], json={'expected_revision':p['revision'], 'name':'修訂' + str(number)})
    with ThreadPoolExecutor(2) as executor:
        responses = list(executor.map(change, (1,2)))
    assert sorted(r.status_code for r in responses) == [200,409]


def test_failed_receipt_rolls_back_all_domain_writes(app, client, monkeypatch):
    _, goal = onboard(client)
    d = draft(client, goal)
    original = app.state.service._remember
    def fail(*args):
        raise DomainError(503, 'injected_failure', 'synthetic failure after ledger')
    monkeypatch.setattr(app.state.service, '_remember', fail)
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 503
    with app.state.service.db.connect() as c:
        for table in ('experiences','reward_ledger','contributions','tasks','experience_stories'):
            assert c.execute('SELECT count(*) FROM ' + table).fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM requests WHERE operation='confirm'").fetchone()[0] == 0
    assert client.get('/api/drafts/' + d['id']).json()['status'] == 'draft'
    monkeypatch.setattr(app.state.service, '_remember', original)
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 201


def test_database_outage_does_not_fall_back_or_leak(tmp_path):
    s = replace(settings(), db_port=1)
    with TestClient(create_app(data_dir=tmp_path, settings=s), raise_server_exceptions=False) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/ready').status_code == 503
        response = client.post('/api/auth/guest')
        assert response.status_code == 503
        assert s.db_password not in response.text
    assert not list(tmp_path.glob('*.sqlite*'))


def test_statement_timeout_rolls_back_and_pool_is_reusable(app):
    database = app.state.service.db
    with pytest.raises(DomainError) as error:
        with database.connect(write=True, owner='synthetic-timeout') as c:
            c.execute("SET LOCAL statement_timeout = '50ms'")
            c.execute('SELECT pg_sleep(0.2)')
    assert error.value.status == 409 and error.value.code == 'transaction_conflict'
    database.check_ready()  # 失敗交易已 rollback，不能留下 aborted connection。


def test_bounded_pool_and_read_only_grants_fail_explicitly(app, tmp_path):
    limited = PostgresDatabase(replace(settings(),pool_size=1,pool_timeout=.1))
    try:
        with limited.connect():
            with pytest.raises(DomainError) as error:
                with limited.connect():
                    pass
            assert error.value.code == 'database_busy'
        limited.check_ready()
    finally:
        limited.close()
    # 模擬目前雲端仍只有 SELECT：readiness 可讀不等於已准許業務寫入。
    with bootstrap.admin_connection() as raw, closing(raw.cursor()) as c:
        c.execute('REVOKE INSERT ON lw_core_draft.users FROM lw_app_role')
    try:
        with TestClient(create_app(data_dir=tmp_path,database=PostgresDatabase(settings()))) as client:
            assert client.get('/ready').status_code == 200
            response = client.post('/api/auth/guest')
            assert response.status_code == 503
            assert response.json()['error']['code'] == 'database_permission_unavailable'
    finally:
        with bootstrap.admin_connection() as raw, closing(raw.cursor()) as c:
            c.execute('GRANT INSERT ON lw_core_draft.users TO lw_app_role')
