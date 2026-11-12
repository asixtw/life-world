"""僅初始化帶專用 cluster_name 的本機合成 PG18，不接受 Cloud SQL 目標。"""
from contextlib import closing
from pathlib import Path
import json
import os
import re
import time

import pg8000.dbapi as driver

ROOT = Path(__file__).resolve().parent.parent
MARKER = 'lifeworld-step10-4-synthetic'
driver.paramstyle = 'qmark'
SCHEMA = 'lw_core_draft'
# 規格（《表規格與擬真資料交接》v1.1，2026-11-12）：e2e／alpha 是同一套 010 結構，Cloud Run 連 alpha；011 是生日／任職四表。
ALPHA_SNAPSHOT = ROOT / 'docs/integration/2026-11-11/evidence/schema/life_world_alpha.json'
REVIEW_011 = ROOT / 'docs/integration/2026-11-11/migrations/011_person_basic_details.review.sql'
# 011 四表的 Runtime 權限，與 e2e 已執行的四表 GRANT 相同：目前值只開放列出的欄位更新，History 只能新增。
GRANTS_011 = {'person_basic_details': ('birth_year', 'birth_month', 'birth_day'),
              'person_basic_detail_history': (),
              'person_employments': ('company_name', 'job_title', 'employment_status', 'valid_from', 'valid_to'),
              'person_employment_history': ()}
SOURCE_COLUMNS_011 = ('source_kind', 'source_experience_id', 'evidence_type', 'source_quote', 'source_status',
                      'confirmed_at', 'revision', 'updated_at')
ACL_PRIVILEGES = {'r': 'SELECT', 'a': 'INSERT', 'w': 'UPDATE', 'x': 'REFERENCES'}
# alpha 待套用的權限：2026-11-12 Jerry 核准列入（刪除已存草稿需要），與 011 一起等 Owner 核准後才在真實 alpha 執行。
# 測試庫先照「套用後」的 alpha 驗證；清單之外不補任何 alpha 沒有的權限。
PENDING_ALPHA_GRANTS = ('GRANT DELETE ON "drafts" TO lw_app_role',)


def quote(name):
    if not re.fullmatch(r'[a-z_][a-z0-9_]*', name):
        raise ValueError('Unexpected snapshot identifier')
    return '"' + name + '"'


def alpha_snapshot():
    """alpha 010 的唯讀結構快照（2026-11-11）：只有結構與權限，沒有業務資料。"""
    return json.loads(ALPHA_SNAPSHOT.read_text(encoding='utf-8'))


def snapshot_statements(structure):
    """依快照重建表、約束與索引：先主鍵／唯一／檢查，再外鍵，最後是約束以外的索引。"""
    if structure['functions'] or structure['triggers'] or structure['views'] or structure['policies']:
        raise ValueError('Unsupported snapshot objects require manual review')
    statements = []
    for table in [r['name'] for r in structure['relations'] if r['kind'] == 'r']:
        fields = []
        for column in [x for x in structure['columns'] if x['table'] == table]:
            item = quote(column['name']) + ' ' + column['type']
            if column['identity']:
                item += ' GENERATED ' + ('ALWAYS' if column['identity'] == 'a' else 'BY DEFAULT') + ' AS IDENTITY'
            elif column['default'] is not None:
                item += ' DEFAULT ' + column['default']
            if not column['nullable']:
                # PG18 的 NOT NULL 是具名約束；沿用快照的名稱，目錄才會和 alpha 一致。
                name = next(k['name'] for k in structure['constraints'] if k['table'] == table and k['kind'] == 'n'
                            and k['definition'].removeprefix('NOT NULL ').strip('"') == column['name'])
                item += ' CONSTRAINT ' + quote(name) + ' NOT NULL'
            fields.append(item)
        statements.append('CREATE TABLE ' + quote(table) + '(' + ','.join(fields) + ')')
    for kinds in (('p', 'u', 'c'), ('f',)):
        statements += ['ALTER TABLE ' + quote(k['table']) + ' ADD CONSTRAINT ' + quote(k['name']) + ' ' + k['definition']
                       for k in structure['constraints'] if k['kind'] in kinds]
    automatic = {k['name'] for k in structure['constraints'] if k['kind'] in ('p', 'u')}
    return statements + [index['definition'] for index in structure['indexes'] if index['name'] not in automatic]


def reviewed_011_ddl(source=None):
    """011 審查稿去掉只適用真實 e2e／alpha 的環境關卡（DB 名稱、marker、Owner 角色）和外層交易，其餘逐字執行。
    關卡不是預期的唯一一段就停止，避免審查稿改版後被默默剝錯。"""
    source = REVIEW_011.read_text(encoding='utf-8') if source is None else source
    gate = re.findall(r'DO \$gate\$.*?END \$gate\$;\n', source, re.S)
    if len(gate) != 1 or source.count('$gate$') != 2 or source.count('BEGIN;\n') != 1 or source.count('COMMIT;') != 1:
        raise ValueError('Unexpected 011 review file structure; refusing to strip its environment gate')
    return source.replace(gate[0], '').replace('BEGIN;\n', '', 1).replace('COMMIT;', '', 1)


def schema_statements():
    """Step 3 測試庫的完整 DDL：alpha 010 快照＋011 審查稿。"""
    return snapshot_statements(alpha_snapshot()['structure']) + [reviewed_011_ddl()]


def runtime_grants(snapshot=None):
    """Runtime 權限照 alpha 的 lw_alpha_app 實際權限鏡像到測試用的 lw_app_role，再加 011 四表的最小權限。
    不給 ALL／TRUNCATE，也不補 alpha 沒有的權限：缺權限的程式路徑要在測試失敗，不能被測試庫掩蓋。"""
    snapshot = snapshot or alpha_snapshot()
    grants = ['GRANT USAGE ON SCHEMA ' + SCHEMA + ' TO lw_app_role']
    for row in snapshot['effective_runtime_privileges']:
        if row['role'] == 'lw_alpha_app':
            grants += ['GRANT ' + p.upper() + ' ON ' + quote(row['table']) + ' TO lw_app_role'
                       for p in ('select', 'insert', 'update', 'delete') if row[p]]
    for row in snapshot['column_acl']:
        for _, chars in re.findall(r'(?:\{|,)(lw_alpha_app(?:_role)?)=([a-zA-Z*]+)/', row['acl']):
            grants += ['GRANT ' + ACL_PRIVILEGES[ch] + ' (' + quote(row['column']) + ') ON ' + quote(row['table'])
                       + ' TO lw_app_role' for ch in chars if ch in ACL_PRIVILEGES]
    for table, values in GRANTS_011.items():
        grants.append('GRANT SELECT, INSERT ON ' + quote(table) + ' TO lw_app_role')
        if values:
            grants.append('GRANT UPDATE (' + ', '.join(quote(c) for c in values + SOURCE_COLUMNS_011) + ') ON '
                          + quote(table) + ' TO lw_app_role')
    return list(dict.fromkeys(grants + list(PENDING_ALPHA_GRANTS)))


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
            # 2026-11-12 起與 Cloud Run 的 alpha 同一套結構（010 快照＋011），不再用 11-02 的 31 表核心草稿。
            c.execute('CREATE SCHEMA ' + SCHEMA + ' AUTHORIZATION lw_migration_role')
            c.execute('SET search_path TO ' + SCHEMA + ',pg_catalog')
            c.execute('BEGIN')
            try:
                for statement in schema_statements() + runtime_grants():
                    c.execute(statement)
                c.execute('COMMIT')
            except BaseException:
                c.execute('ROLLBACK')
                raise
    with admin_connection() as raw, closing(raw.cursor()) as c:
        c.execute("COMMENT ON DATABASE life_world_dev IS 'STEP10_LOCAL_SYNTHETIC_ONLY'")
        c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=? AND table_type='BASE TABLE'", (SCHEMA,))
        expected = {r['name'] for r in alpha_snapshot()['structure']['relations'] if r['kind'] == 'r'} | set(GRANTS_011)
        if {row[0] for row in c.fetchall()} != expected:
            raise RuntimeError('Synthetic schema does not match alpha 010 + 011')
    bootstrap_alpha()
    print('Local PG18 initialized: dev and isolated Alpha synthetic fixtures; no cloud operations')


def bootstrap_alpha():
    """專用本機cluster建立Alpha合成fixture；既有庫必須有marker，不覆寫資料。"""
    with admin_connection('postgres') as raw, closing(raw.cursor()) as c:
        c.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname='life_world_alpha'")
        existing=c.fetchone()
        if existing is not None:
            if existing[0]!='STEP10_LOCAL_SYNTHETIC_ONLY':
                raise ValueError('Refusing existing unmarked Alpha database')
            return
        for role in ('lw_alpha_owner','lw_alpha_migrator','lw_alpha_app_role','lw_alpha_app'):
            c.execute('SELECT 1 FROM pg_roles WHERE rolname=?',(role,))
            if c.fetchone() is not None:
                raise ValueError('Refusing pre-existing Alpha roles without marked database')
        c.execute('CREATE DATABASE life_world_alpha')
    with admin_connection('life_world_alpha') as raw, closing(raw.cursor()) as c:
        c.execute((ROOT/'deploy/postgres/alpha_roles_database.review.sql').read_text(encoding='utf-8'))
        for role in ('lw_alpha_migrator','lw_alpha_app'):
            c.execute("SELECT format('ALTER ROLE %I PASSWORD %L', ?::text, ?::text)",(role,test_config()['password']))
            c.execute(c.fetchone()[0])
    with driver.connect(user='lw_alpha_migrator', database='life_world_alpha', **test_config()) as raw:
        raw.autocommit=True
        with closing(raw.cursor()) as c:
            c.execute('SET ROLE lw_alpha_owner')
            for name in ('docs/database/schema-2026-11-02/POSTGRESQL_CORE_DRAFT.sql',
                         'deploy/postgres/alpha_auth_rate_limit.review.sql',
                         'deploy/postgres/alpha_app_grants.review.sql'):
                c.execute((ROOT/name).read_text(encoding='utf-8'))
    with admin_connection('life_world_alpha') as raw, closing(raw.cursor()) as c:
        c.execute("COMMENT ON DATABASE life_world_alpha IS 'STEP10_LOCAL_SYNTHETIC_ONLY'")


if __name__ == '__main__':
    bootstrap()
