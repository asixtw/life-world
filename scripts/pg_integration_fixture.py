"""只接受本機專用marker的PG18，從Owner唯讀目錄建立空結構副本，絕不連Cloud SQL。

這是結構重建，不是備份還原；不複製業務資料或偽造010執行收據。原Sequence參數未提供，採本機預設並單獨標示。
"""
from contextlib import closing
from pathlib import Path
import hashlib
import json
import os
import re
import pg8000.dbapi as driver

driver.paramstyle='qmark'
ROOT=Path(__file__).resolve().parents[1]
MARKER='lifeworld-integration-20261111-synthetic'
DB='life_world_e2e'
DB_MARKER='LW_INTEGRATION_STRUCTURAL_COPY_ONLY'
OWNER='lw_e2e_owner'
APP='lw_e2e_app'
SCHEMA='lw_core_draft'


def ident(value):
    if not re.fullmatch(r'[a-z_][a-z0-9_]*',value):raise ValueError('Unexpected fixture identifier')
    return '"'+value+'"'


def config():
    path=Path(os.environ['LIFEWORLD_INTEGRATION_PG_CONFIG'])
    data=json.loads(path.read_text())
    if data['host']!='127.0.0.1' or data['cluster_name']!=MARKER or data['port']!=57518:
        raise ValueError('Refusing non-local integration fixture')
    return data


def connect(database='postgres',runtime=False):
    data=config()
    raw=driver.connect(host=data['host'],port=data['port'],user=APP if runtime else data['admin_user'],password=data['password'],database=database,ssl_context=False,timeout=10)
    raw.autocommit=True
    with closing(raw.cursor()) as c:
        c.execute('SHOW cluster_name')
        if c.fetchone()[0]!=MARKER:raw.close();raise ValueError('Refusing unmarked cluster')
        c.execute('SHOW server_version_num')
        if int(c.fetchone()[0])//10000!=18:raw.close();raise ValueError('PG18 required')
        if database==DB:
            c.execute("SELECT pg_catalog.shobj_description(oid,'pg_database') FROM pg_catalog.pg_database WHERE datname=current_database()")
            if c.fetchone()[0]!=DB_MARKER:raw.close();raise ValueError('Refusing unmarked database')
    return raw


def create_from_snapshot():
    source=json.loads((ROOT/'docs/integration/2026-11-11/evidence/schema/life_world_e2e.json').read_text())
    structure=source['structure']
    if source['database']!=DB or structure['functions'] or structure['triggers'] or structure['views']:
        raise ValueError('Unsupported snapshot objects require manual review')
    with closing(connect()) as raw,closing(raw.cursor()) as c:
        c.execute('SELECT 1 FROM pg_database WHERE datname=?',(DB,))
        if c.fetchone():raise ValueError('Fixture exists: no automatic database overwrite')
        for role in (OWNER,APP):
            c.execute('SELECT 1 FROM pg_roles WHERE rolname=?',(role,))
            if c.fetchone():raise ValueError('Fixture role already exists')
        c.execute('CREATE ROLE '+OWNER+' NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS')
        c.execute("SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD %L',?::text,?::text)",(APP,config()['password']))
        c.execute(c.fetchone()[0])
        c.execute('CREATE DATABASE '+DB+' OWNER '+OWNER)
        c.execute("SELECT format('COMMENT ON DATABASE %I IS %L',?::text,?::text)",(DB,DB_MARKER));c.execute(c.fetchone()[0])
        c.execute('REVOKE ALL ON DATABASE '+DB+' FROM PUBLIC')
        c.execute('GRANT CONNECT ON DATABASE '+DB+' TO '+APP)
    with closing(connect(DB)) as raw,closing(raw.cursor()) as c:
        c.execute('SET ROLE '+OWNER)
        c.execute('CREATE SCHEMA '+SCHEMA+' AUTHORIZATION '+OWNER)
        c.execute('SET search_path TO '+SCHEMA+',pg_catalog')
        c.execute('BEGIN')
        try:
            for table in [r['name'] for r in structure['relations'] if r['kind']=='r']:
                fields=[]
                for col in [x for x in structure['columns'] if x['table']==table]:
                    item=ident(col['name'])+' '+col['type']
                    if col['identity']:
                        item+=' GENERATED '+('ALWAYS' if col['identity']=='a' else 'BY DEFAULT')+' AS IDENTITY'
                    elif col['default'] is not None:item+=' DEFAULT '+col['default']
                    if not col['nullable']:
                        expected=next(k['name'] for k in structure['constraints'] if k['table']==table and k['kind']=='n' and k['definition'].removeprefix('NOT NULL ').strip('"')==col['name'])
                        item+=' CONSTRAINT '+ident(expected)+' NOT NULL'
                    fields.append(item)
                c.execute('CREATE TABLE '+ident(table)+'('+','.join(fields)+')')
            for kinds in [('p','u','c'),('f',)]:
                for k in structure['constraints']:
                    if k['kind'] in kinds:c.execute('ALTER TABLE '+ident(k['table'])+' ADD CONSTRAINT '+ident(k['name'])+' '+k['definition'])
            automatic={k['name'] for k in structure['constraints'] if k['kind'] in ('p','u')}
            for index in structure['indexes']:
                if index['name'] not in automatic:c.execute(index['definition'])
            c.execute('COMMIT')
        except BaseException:
            c.execute('ROLLBACK');raise
        # 先鏡像實際E2E Runtime權限，讓權限缺口可被測試重現；不直接給ALL。
        c.execute('GRANT USAGE ON SCHEMA '+SCHEMA+' TO '+APP)
        for row in source['effective_runtime_privileges']:
            if row['role']==APP:
                permissions=[k.upper() for k in ('select','insert','update','delete') if row[k]]
                if permissions:c.execute('GRANT '+','.join(permissions)+' ON '+ident(row['table'])+' TO '+APP)
        for row in source['column_acl']:
            match=re.search(r'(?:\{|,)'+APP+r'=([a-zA-Z*]+)/',row['acl'])
            if match:
                for char,permission in [('r','SELECT'),('a','INSERT'),('w','UPDATE'),('x','REFERENCES')]:
                    if char in match.group(1):c.execute('GRANT '+permission+'('+ident(row['column'])+') ON '+ident(row['table'])+' TO '+APP)
    return {'baseline_source':'Owner E2E schema snapshot','business_rows_copied':0,'migration_receipts_copied':0,'sequence_parameters':'not supplied; local defaults only'}


def snapshot():
    sql=(ROOT/'docs/integration/2026-11-11/READ_ONLY_SCHEMA_SNAPSHOT.sql').read_text()
    query=sql[sql.index('WITH ns AS'):sql.rindex('COMMIT;')].strip().rstrip(';')
    with closing(connect(DB)) as raw,closing(raw.cursor()) as c:
        c.execute('BEGIN READ ONLY');c.execute('SET LOCAL ROLE '+OWNER)
        c.execute(query);data=c.fetchone()[0]
        c.execute('ROLLBACK')
    return json.loads(data) if isinstance(data,str) else data


def apply_candidate():
    """只在marker合成副本套用REVIEW草案；不是GCP E2E/Alpha套用授權。"""
    path=ROOT/'docs/integration/2026-11-11/migrations/011_person_basic_details.review.sql'
    with closing(connect(DB)) as raw,closing(raw.cursor()) as c:
        c.execute('SET ROLE '+OWNER)
        c.execute(path.read_text())
    return {'file':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'environment':'local synthetic structural copy','applied':True}


def grant_candidate_permissions():
    """本機正向測試提議的最小差異；真實兩庫仍未GRANT。"""
    with closing(connect(DB)) as raw,closing(raw.cursor()) as c:
        c.execute('SET ROLE '+OWNER)
        c.execute('GRANT DELETE ON '+SCHEMA+'.drafts TO '+APP)
        # UPDATE只允許服務實際變更的值/來源/版本；Owner、subject、主鍵及created_at不可重派。
        common=['source_kind','source_experience_id','evidence_type','source_quote','source_status','confirmed_at','revision','updated_at']
        for table,values in [('person_basic_details',['birth_year','birth_month','birth_day']),('person_employments',['company_name','job_title','employment_status','valid_from','valid_to'])]:
            c.execute('REVOKE UPDATE ON '+SCHEMA+'.'+table+' FROM '+APP)
            c.execute('GRANT SELECT,INSERT ON '+SCHEMA+'.'+table+' TO '+APP)
            c.execute('GRANT UPDATE('+','.join(ident(k) for k in values+common)+') ON '+SCHEMA+'.'+table+' TO '+APP)
        for table in ['person_basic_detail_history','person_employment_history']:
            c.execute('GRANT SELECT,INSERT ON '+SCHEMA+'.'+table+' TO '+APP)
    return {'environment':'local only','production_grants_modified':False,'status':'column-level proposal tested, formal review required'}
