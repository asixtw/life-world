"""僅初始化帶專用 cluster_name 的本機合成 PG18，不接受 Cloud SQL 目標。"""
from contextlib import closing
from pathlib import Path
import os
import time

import pg8000.dbapi as driver

ROOT = Path(__file__).resolve().parent.parent
MARKER = 'lifeworld-step10-4-synthetic'
driver.paramstyle = 'qmark'


def test_config():
    host = os.environ.get('LIFEWORLD_TEST_PG_HOST', '127.0.0.1')
    # cloudbuild 是 Docker 內部網路別名；不允許任意位址／10.129.0.3。
    if host not in ('127.0.0.1', 'localhost', 'lw-pg18-tests'):
        raise ValueError('Only dedicated local synthetic PostgreSQL is allowed')
    password = os.environ.get('LIFEWORLD_TEST_PG_PASSWORD')
    if not password:
        raise ValueError('Synthetic PostgreSQL password is required')
    return dict(host=host, port=int(os.environ.get('LIFEWORLD_TEST_PG_PORT', '55432')),
                password=password, ssl_context=False, timeout=5)


def admin_connection(database='life_world_dev'):
    raw = driver.connect(user='lw_step10_admin', database=database, **test_config())
    raw.autocommit = True
    with closing(raw.cursor()) as c:
        c.execute('SHOW cluster_name')
        if c.fetchone()[0] != MARKER:
            raw.close()
            raise ValueError('Refusing an unmarked PostgreSQL cluster')
        c.execute('SHOW server_version_num')
        if int(c.fetchone()[0]) // 10000 != 18:
            raw.close()
            raise ValueError('PostgreSQL 18 required')
    return raw


def bootstrap():
    """明確的 migration 身分建 schema，runtime 使用者不參與 DDL。"""
    password = test_config()['password']
    raw = None
    for attempt in range(60):
        try:
            raw = admin_connection('postgres')
            break
        except driver.InterfaceError:
            time.sleep(1)
    if raw is None:
        raise RuntimeError('Local PostgreSQL did not become ready')
    with raw, closing(raw.cursor()) as c:
        c.execute("SELECT 1 FROM pg_database WHERE datname='life_world_dev'")
        if c.fetchone() is None:
            c.execute('CREATE DATABASE life_world_dev')
        for role in ('lw_migration_role', 'lw_app_role'):
            c.execute('SELECT 1 FROM pg_roles WHERE rolname=?', (role,))
            if c.fetchone() is None:
                c.execute('CREATE ROLE ' + role + ' NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS')
        for user in ('lw_migrator', 'lw_app'):
            c.execute('SELECT 1 FROM pg_roles WHERE rolname=?', (user,))
            if c.fetchone() is None:
                c.execute('CREATE ROLE ' + user + ' LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS')
            # Utility DDL 不接受 bind；讓伺服器 format(%I/%L) 安全產生識別字／literal。
            c.execute("SELECT format('ALTER ROLE %I PASSWORD %L', ?::text, ?::text)", (user, password))
            c.execute(c.fetchone()[0])
        c.execute('GRANT lw_migration_role TO lw_migrator')
        c.execute('GRANT lw_app_role TO lw_app')
        c.execute('GRANT CREATE ON DATABASE life_world_dev TO lw_migration_role')
    with driver.connect(user='lw_migrator', database='life_world_dev', **test_config()) as migrator:
        migrator.autocommit = True
        with closing(migrator.cursor()) as c:
            c.execute('SET ROLE lw_migration_role')
            c.execute((ROOT / 'docs/database/schema-2026-11-02/POSTGRESQL_CORE_DRAFT.sql').read_text(encoding='utf-8'))
            c.execute((ROOT / 'deploy/postgres/app_dml_grants.review.sql').read_text(encoding='utf-8'))
    with admin_connection() as raw, closing(raw.cursor()) as c:
        c.execute("COMMENT ON DATABASE life_world_dev IS 'STEP10_LOCAL_SYNTHETIC_ONLY'")
        c.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='lw_core_draft'")
        assert c.fetchone()[0] == 31
    print('Local PG18 initialized: 31 core tables; no theater schema; no cloud operations')


if __name__ == '__main__':
    bootstrap()
