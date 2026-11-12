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
    """以 PG catalog 核對測試庫就是 alpha 010 快照＋011（表規格與擬真資料交接 v1.1），而非只解析 SQL 檔案。
    2026-11-12 之前這裡核對 11-02 的 31 表核心草稿；Cloud Run 改連 alpha 後，測試庫改用 alpha 的實際結構。"""
    assert app.state.service.db.backend == 'postgresql'
    assert not list(tmp_path.glob('*.sqlite*'))
    snapshot = bootstrap.alpha_snapshot()['structure']
    alpha_tables = {r['name'] for r in snapshot['relations'] if r['kind'] == 'r'}
    new_011 = set(bootstrap.GRANTS_011)
    with closing(bootstrap.admin_connection()) as raw, closing(raw.cursor()) as c:
        c.execute("SELECT tablename FROM pg_tables WHERE schemaname='lw_core_draft'")
        assert {r[0] for r in c.fetchall()} == alpha_tables | new_011 and len(alpha_tables) == 42
        assert not (alpha_tables | new_011) & {'relationship_features', 'relationship_memory_preferences'}  # 這一輪 PG 不建
        # 逐欄型別與 NOT NULL 跟 alpha 快照一致（format_type 與快照同一種表示法）。
        c.execute("""SELECT t.relname,a.attname,format_type(a.atttypid,a.atttypmod),NOT a.attnotnull FROM pg_attribute a
            JOIN pg_class t ON t.oid=a.attrelid WHERE t.relnamespace='lw_core_draft'::regnamespace AND t.relkind='r'
            AND a.attnum>0 AND NOT a.attisdropped""")
        columns = {(r[0], r[1]): (r[2], r[3]) for r in c.fetchall()}
        expected = {(x['table'], x['name']): (x['type'], x['nullable']) for x in snapshot['columns'] if x['table'] in alpha_tables}
        assert {k: v for k, v in columns.items() if k[0] in alpha_tables} == expected
        assert sum(1 for k in columns if k[0] in new_011) == 63  # 011 四表共 63 欄（與 011 套用後的核對相同）
        # 外鍵：alpha 的 81 個定義逐字相同（含連動刪除行為），再加 011 的 9 個（沒有連動，NO ACTION）；全部已驗證。
        c.execute("""SELECT conname,convalidated,pg_get_constraintdef(oid),confupdtype,confdeltype FROM pg_constraint
            WHERE connamespace='lw_core_draft'::regnamespace AND contype='f'""")
        fks = {r[0]: r for r in c.fetchall()}
        unqualified = lambda text: text.replace('lw_core_draft.', '')  # 定義是否帶 schema 取決於 search_path，不影響內容
        alpha_fks = {k['name']: unqualified(k['definition']) for k in snapshot['constraints'] if k['kind'] == 'f'}
        assert len(alpha_fks) == 81 and len(fks) == 81 + 9 and all(r[1] for r in fks.values())
        assert {name: unqualified(fks[name][2]) for name in alpha_fks} == alpha_fks
        assert all(r[3] == r[4] == 'a' for name, r in fks.items() if name not in alpha_fks)
        c.execute("SELECT table_name,column_name,identity_generation FROM information_schema.columns WHERE table_schema='lw_core_draft' AND is_identity='YES'")
        assert {tuple(r) for r in c.fetchall()} == {('goal_reviews','audit_seq','ALWAYS'),('story_history','audit_seq','ALWAYS')}
        c.execute("SELECT count(*) FROM pg_class WHERE relnamespace='lw_core_draft'::regnamespace AND relkind='S'")
        assert c.fetchone()[0] == 2
        c.execute("SELECT bool_and(relowner='lw_migration_role'::regrole) FROM pg_class WHERE relnamespace='lw_core_draft'::regnamespace AND relkind IN ('r','S')")
        assert c.fetchone()[0] is True
        # 約束以外的索引：alpha 的 23 個加上 011 的 4 個。
        c.execute("SELECT count(*) FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid LEFT JOIN pg_constraint c ON c.conindid=i.indexrelid WHERE t.relnamespace='lw_core_draft'::regnamespace AND c.oid IS NULL")
        assert c.fetchone()[0] == 23 + 4
        # 劇場提案（lw_theater_draft）沒有建立。
        c.execute("SELECT to_regnamespace('lw_theater_draft') IS NULL")
        assert c.fetchone()[0] is True
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
