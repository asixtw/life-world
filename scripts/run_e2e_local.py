"""實際 PG18.6＋兩個 HTTPS API 的合成驗證；不接受雲端目標、不呼叫 GCP。"""
import argparse
import base64
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4

import pg8000.dbapi as driver
import uvicorn

from app.main import create_app
from app.runtime import RuntimeSettings
from scripts.e2e_flow import run_acceptance
from scripts.e2e_sql import schema_sql, audit_sql
from scripts.e2e_safety import SOURCE_KEYS, source_digest

ROOT = Path(__file__).resolve().parent.parent
DBA = 'lw_e2e_local_dba'  # 本機合成容器內的非 superuser 管理者，模擬 Cloud SQL DBA 權限
driver.paramstyle = 'qmark'


class LocalGate:
    """只模擬 edge 拒絕未授權 HTTP；不能作 Google IAM 驗收證據。"""
    def __init__(self, app, token):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope['type']=='http':
            value = dict(scope['headers']).get(b'x-serverless-authorization',b'')
            if not hmac.compare_digest(value,('Bearer '+self.token).encode()):
                await send({'type':'http.response.start','status':403,'headers':[(b'content-type',b'text/plain')]})
                await send({'type':'http.response.body','body':b'local IAM model denied'})
                return
        await self.app(scope,receive,send)


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def local_evidence(plan):
    """本機模型四份 JSON 的合成匯出證據；不代表已向 Google 取得任何快照。"""
    stamp = datetime.now(timezone.utc).isoformat(); batch = uuid4().hex
    plan['captured_at'] = stamp
    plan['snapshot_evidence'] = {'version':1,'batch_id':batch,'started_at':stamp,'completed_at':stamp,
        'sources':{key:{'filename':key+'.json','batch_id':batch,'export_started_at':stamp,'exported_at':stamp,
                        'sha256':source_digest(plan[key]),'content_sha256':source_digest(plan[key])} for key in SOURCE_KEYS}}
    return plan


def local_plan(main_url, tag_url):
    """同一 v1 snapshot 形狀；local 模式只允許 loopback HTTPS，CLI 不接受此模式。"""
    def revision(name, enabled, database, user, url):
        env = {'LIFEWORLD_DB_BACKEND':'postgresql','LIFEWORLD_DB_NAME':database,'LIFEWORLD_DB_SCHEMA':'lw_core_draft',
               'LIFEWORLD_DB_USER':user,'LIFEWORLD_ENABLE_BUSINESS_API':enabled,'LIFEWORLD_SECURE_COOKIES':'true',
               'LIFEWORLD_TRUSTED_HOSTS':'127.0.0.1,localhost','LIFEWORLD_EXTERNAL_ORIGIN':url}
        return {'metadata':{'name':name,'namespace':'123456','labels':{'cloud.googleapis.com/location':'asia-east1'}},
                'spec':{'containers':[{'env':[{'name':k,'value':v} for k,v in env.items()]}]},
                'status':{'conditions':[{'type':'Ready','status':'True'}]}}
    routes = [{'revisionName':'lw-api-main-stable','percent':100},
              {'revisionName':'lw-api-main-e2e','tag':'e2e','url':tag_url}]
    return local_evidence({'mode':'local-simulation','project_id':'life-world-513506','project_number':'123456',
            'captured_at':datetime.now(timezone.utc).isoformat(),
            'service':{'metadata':{'name':'lw-api-main','namespace':'123456','labels':{'cloud.googleapis.com/location':'asia-east1'}},
                       'spec':{'traffic':routes},'status':{'url':main_url,'traffic':routes,'conditions':[{'type':'Ready','status':'True'}]}},
            'main_revision':revision('lw-api-main-stable','false','life_world_dev','lw_app',main_url),
            'tag_revision':revision('lw-api-main-e2e','true','life_world_e2e','lw_e2e_app',tag_url),
            'iam_policy':{'bindings':[{'role':'roles/run.invoker','members':['synthetic-local-only']}]}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',required=True)
    parser.add_argument('--openssl',default=shutil.which('openssl'))
    args = parser.parse_args()
    docker = json.loads(os.environ.get('LIFEWORLD_TEST_DOCKER_ARGV','["docker"]'))
    name = 'lw-step18-e2e-'+uuid4().hex[:12]
    password = secrets.token_urlsafe(32)
    (ROOT/'.test-runs').mkdir(exist_ok=True)
    def run(*argv, **kw):
        return subprocess.run(docker+list(argv),check=True,capture_output=True,**kw)
    def mount(path):
        path = Path(path).resolve()
        return '/mnt/'+path.drive[0].lower()+path.as_posix()[2:] if docker[0].lower() in ('wsl','wsl.exe') else str(path)
    def connection(database='life_world_e2e', user='lw_step10_admin'):
        raw = driver.connect(host='127.0.0.1',port=55438,user=user,password=password,database=database,ssl_context=False)
        raw.autocommit = True
        with closing(raw.cursor()) as c:
            c.execute('SHOW cluster_name')
            assert c.fetchone()[0]=='lifeworld-step10-4-synthetic'
        return raw
    def fingerprint():
        with connection('life_world_dev') as raw, closing(raw.cursor()) as c:
            c.execute("SELECT tablename FROM pg_tables WHERE schemaname='lw_core_draft' ORDER BY tablename")
            tables = [r[0] for r in c.fetchall()]; records = []
            for table in tables:
                c.execute('SELECT row_to_json(t)::text FROM lw_core_draft."'+table+'" t ORDER BY row_to_json(t)::text')
                records.append((table,c.fetchall()))
        return hashlib.sha256(json.dumps(records).encode()).hexdigest()
    result, servers, stage = None,[], 'start_postgres'
    with tempfile.TemporaryDirectory(prefix='step18-',dir=ROOT/'.test-runs') as temp:
        tmp = Path(temp)
        try:
            envfile = tmp/'synthetic.env'
            envfile.write_text('POSTGRES_USER=lw_step10_admin\nPOSTGRES_DB=postgres\nPOSTGRES_PASSWORD='+password+'\n',encoding='utf-8')
            run('run','-d','--rm','--name',name,'--network','host','--env-file',mount(envfile),
                '-v',mount(ROOT)+':/workspace:ro','postgres:18.6','-c','port=55438','-c','listen_addresses=127.0.0.1',
                '-c','cluster_name=lifeworld-step10-4-synthetic')
            stage = 'bootstrap_synthetic_dev'
            env = dict(os.environ,PYTHONUTF8='1',LIFEWORLD_TEST_PG_PASSWORD=password,LIFEWORLD_TEST_PG_HOST='127.0.0.1',LIFEWORLD_TEST_PG_PORT='55438')
            subprocess.run([sys.executable,'-X','utf8','-m','scripts.pg_test_bootstrap'],cwd=ROOT,env=env,check=True,capture_output=True)
            version = run('exec',name,'postgres','--version').stdout.decode().strip()
            assert '18.6' in version
            def sql(database, text, user='lw_step10_admin', stop=True):
                # psql 不加 -a/-e，密碼只由本機 socket／短期 env 持有；stop=False 模擬未設 ON_ERROR_STOP 的 client。
                argv = ['exec','-i',name,'psql','-X','-p','55438','-v','VERBOSITY=sqlstate','-U',user,'-d',database]
                if stop: argv[7:7] = ['-v','ON_ERROR_STOP=1']
                return run(*argv,input=text.encode()).stdout.decode()
            def rejected(database, text, user=DBA):
                # 守門必須以錯誤停止；不能只看錯誤訊息而讓 psql 回傳成功。
                try:
                    sql(database,text,user)
                except subprocess.CalledProcessError:
                    return True
                raise RuntimeError('SQL guard did not reject')
            e2e_sql = lambda file: (ROOT/'deploy/postgres/e2e'/file).read_text(encoding='utf-8')
            stage = 'dev_sentinel'
            sql('life_world_dev',"INSERT INTO lw_core_draft.users(id,status,created_at) VALUES ('step18-dev-sentinel','guest',now());")
            # Cloud SQL 管理者不是 superuser：以 CREATEDB／CREATEROLE＋pg_signal_backend 身分執行交付 SQL。
            sql('postgres','CREATE ROLE '+DBA+' LOGIN NOSUPERUSER CREATEDB CREATEROLE NOBYPASSRLS; GRANT pg_signal_backend TO '+DBA+';')
            stage = 'dev_fingerprint'
            before = fingerprint()
            stage = 'create_e2e_database'
            sql('postgres',e2e_sql('00_database.sql'),DBA)
            stage = 'create_31_tables'
            sql('life_world_e2e',schema_sql(),DBA)
            stage = 'grant_e2e_runtime'
            sql('life_world_e2e',e2e_sql('02_grants.sql'),DBA)
            sql('life_world_e2e',e2e_sql('03_verify_permissions.sql'),DBA)
            probe = sql('life_world_dev',e2e_sql('04_dev_role_probe.sql'),DBA)
            assert 'E2E_DEV_ROLE_ISOLATION_PASS' in probe
            stage = 'sql_guard_negative'
            # 重複建立不得接管既有物件；PUBLIC 額外權限必須被核對擋下，且未設 ON_ERROR_STOP 也不得印出 PASS。
            rejected('postgres',e2e_sql('00_database.sql'))
            for script in ('02_grants.sql','03_verify_permissions.sql','20_enable.sql'):
                rejected('life_world_dev',e2e_sql(script))
            sql('life_world_e2e','GRANT TRIGGER ON lw_core_draft.users TO PUBLIC;')
            rejected('life_world_e2e',e2e_sql('03_verify_permissions.sql'))
            assert 'E2E_PERMISSIONS_PASS' not in sql('life_world_e2e',e2e_sql('03_verify_permissions.sql'),DBA,stop=False)
            sql('life_world_e2e','REVOKE TRIGGER ON lw_core_draft.users FROM PUBLIC;')
            sql('life_world_e2e',e2e_sql('03_verify_permissions.sql'),DBA)
            with connection() as raw, closing(raw.cursor()) as c:
                c.execute("SELECT format('ALTER ROLE lw_e2e_app PASSWORD %L', ?::text)",(password,)); c.execute(c.fetchone()[0])
            # 真正 SQL guard：在 dev 執行清理必須在任何資料變更前拒絕，未設 ON_ERROR_STOP 也不得印出 PASS。
            rejected('life_world_dev',e2e_sql('90_cleanup.sql'))
            assert 'E2E_CLEANUP_PASS' not in sql('life_world_dev',e2e_sql('90_cleanup.sql'),DBA,stop=False)
            assert fingerprint()==before
            stage = 'enable_e2e_runtime'
            sql('life_world_e2e',e2e_sql('20_enable.sql'),DBA)
            with connection('life_world_dev','lw_e2e_app') as raw, closing(raw.cursor()) as c:
                try:
                    c.execute('INSERT INTO lw_core_draft.users(id,status,created_at) VALUES (\'forbidden\',\'guest\',now())')
                    raise RuntimeError('E2E user can write dev')
                except driver.DatabaseError as error:
                    assert error.args[0]['C']=='42501'
            stage = 'create_local_tls'
            cert,key = tmp/'tls-cert.pem',tmp/'tls-key.pem'
            cert_config = tmp/'tls.cnf'
            cert_config.write_text('[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=v3\n'
                '[dn]\nCN=localhost\n[v3]\nsubjectAltName=IP:127.0.0.1,DNS:localhost\n'
                'basicConstraints=critical,CA:TRUE\nkeyUsage=digitalSignature,keyEncipherment,keyCertSign\n'
                'extendedKeyUsage=serverAuth\n',encoding='utf-8')
            subprocess.run([args.openssl,'req','-x509','-newkey','rsa:2048','-nodes','-days','1','-keyout',str(key),'-out',str(cert),
                '-config',str(cert_config)],check=True,capture_output=True)
            main_port,tag_port = free_port(),free_port()
            main_url,tag_url = 'https://127.0.0.1:'+str(main_port),'https://127.0.0.1:'+str(tag_port)
            encode = lambda data: base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b'=').decode()
            signing = encode({'alg':'HS256'})+'.'+encode({'aud':main_url,'exp':time.time()+1800})
            token = signing+'.'+base64.urlsafe_b64encode(hmac.digest(secrets.token_bytes(32),signing.encode(),'sha256')).rstrip(b'=').decode()
            stage = 'start_local_https'
            for database,user,enabled,url,port in [('life_world_dev','lw_app',False,main_url,main_port),('life_world_e2e','lw_e2e_app',True,tag_url,tag_port)]:
                settings = RuntimeSettings(backend='postgresql',db_host='127.0.0.1',db_port=55438,db_name=database,
                    db_user=user,db_password=password,pg_tls='disable',secure_cookies=True,cloud_run=True,business_enabled=enabled,
                    external_origin=url,trusted_hosts=('127.0.0.1','localhost'))
                app = LocalGate(create_app(data_dir=tmp/database,settings=settings),token)
                server = uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,ssl_keyfile=str(key),ssl_certfile=str(cert),
                    log_level='critical',access_log=False))
                thread = threading.Thread(target=server.run,daemon=True); thread.start(); servers.append((server,thread))
                for attempt in range(200):
                    if server.started: break
                    if not thread.is_alive(): raise RuntimeError('local HTTPS server failed')
                    time.sleep(.05)
                assert server.started
            plan = local_plan(main_url,tag_url)
            stage = 'http_acceptance'
            result = run_acceptance(plan,token,ca_file=str(cert),allow_local=True)
            result['local_iam_model'] = 'HMAC gate only; NOT Google IAM validation'
            if not result['passed']:
                raise RuntimeError('HTTP acceptance failed')
            stage = 'database_audit'
            assert 'E2E_DATABASE_AUDIT_PASS' in sql('life_world_e2e',audit_sql(result['run_id']),DBA)
            # 稽核 SQL 在錯誤 DB 也必須拒絕，且不得印出 PASS。
            rejected('life_world_dev',audit_sql(result['run_id']))
            assert 'E2E_DATABASE_AUDIT_PASS' not in sql('life_world_dev',audit_sql(result['run_id']),DBA,stop=False)
            # 獨立 DB 連線查持久化、角色／sequence 限制；不依賴 API 內記憶體。
            with connection() as raw, closing(raw.cursor()) as c:
                counts = {}
                for privilege in ('SELECT','INSERT','UPDATE','DELETE'):
                    c.execute("SELECT count(*) FROM information_schema.role_table_grants WHERE grantee='lw_e2e_app' AND table_schema='lw_core_draft' AND privilege_type=?",(privilege,))
                    counts[privilege]=c.fetchone()[0]
                assert counts=={'SELECT':30,'INSERT':30,'UPDATE':17,'DELETE':6}
                c.execute("SELECT count(*) FROM pg_tables WHERE schemaname='lw_core_draft'"); assert c.fetchone()[0]==31
                c.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='lw_core_draft' AND is_identity='YES'"); assert c.fetchone()[0]==2
                c.execute("SELECT has_database_privilege('lw_e2e_app','life_world_dev','CONNECT'),has_database_privilege('lw_e2e_app','life_world_dev','TEMP')")
                dev_connect, dev_temp = c.fetchone()
            result['local_database_audit'] = {'passed':True,'tables':31,'privileges':counts,'independent_connection_read':True,
                'wrong_database_cleanup_rejected':True,'e2e_runtime_dev_write_denied':True,
                'sql_runner':'non_superuser_createdb_createrole_dba','repeat_create_rejected':True,
                'wrong_database_scripts_rejected':True,'public_trigger_grant_rejected_without_false_pass':True,
                # dev 既有 PUBLIC CONNECT／TEMP 只回報，不由工具修改。
                'dev_connect_possible':dev_connect,'dev_temp_possible':dev_temp}
            # 新 Runtime 身分實際走 Identity INSERT，再 rollback；不授予 sequence 操作權。
            with connection(user='lw_e2e_app') as raw, closing(raw.cursor()) as c:
                raw.autocommit = False
                c.execute("INSERT INTO lw_core_draft.goal_reviews(id,owner_id,goal_id,decision,previous_state,new_state,reflection,created_at) "
                          "SELECT 'e2e-identity-probe',owner_id,id,'test','{}','{}','',now() FROM lw_core_draft.goals LIMIT 1 RETURNING audit_seq")
                assert c.fetchone()[0]>=1; raw.rollback()
                for sequence in ('goal_reviews_audit_seq_seq','story_history_audit_seq_seq'):
                    try:
                        c.execute("SELECT nextval('lw_core_draft."+sequence+"')")
                        raise RuntimeError('unexpected direct sequence access')
                    except driver.DatabaseError as error:
                        assert error.args[0]['C']=='42501'; raw.rollback()
            result['local_database_audit']['identity_insert_rollback_and_direct_sequence_denied']=True
            # 先模擬移除 tag，驗收退休模式只 GET main，再停 API，最後清理資料。
            for field in ('spec','status'): plan['service'][field]['traffic'] = plan['service'][field]['traffic'][:1]
            local_evidence(plan)  # 模型已移除 tag，重新取得此時的本機模型快照；非雲端證據。
            retired = run_acceptance(plan,token,ca_file=str(cert),allow_local=True,retired=True)
            assert retired['passed']; result['local_retirement_checks']=len(retired['checks'])
            for server,thread in servers:
                server.should_exit=True; thread.join(timeout=10); assert not thread.is_alive()
            servers.clear()
            stage = 'cleanup_and_verify'
            cleanup = sql('life_world_e2e',e2e_sql('90_cleanup.sql'),DBA)
            assert 'E2E_CLEANUP_PASS' in cleanup
            assert fingerprint()==before
            result['database_cleanup']='verified_local_all_30_business_tables_empty_runtime_nologin'
            result['local_dev_fingerprint_unchanged']=True; result['postgres_version']=version
        except Exception as error:
            if result is None: result={'passed':False,'checks':[],'mode':'local-simulation'}
            result['passed']=False; result['harness_failure']='local_setup_http_or_database_verification_failed'
            result['harness_stage']=stage
            result['failure_type']=type(error).__name__
            if isinstance(error,driver.Error) and error.args and isinstance(error.args[0],dict):
                result['sqlstate']=error.args[0].get('C','unknown')
            if isinstance(error,subprocess.CalledProcessError):
                state = re.search(rb'(?:ERROR|FATAL):\s+([0-9A-Z]{5})',error.stderr or b'')
                if state: result['sqlstate']=state[1].decode()
        finally:
            for server,thread in servers:
                server.should_exit=True; thread.join(timeout=10)
            subprocess.run(docker+['rm','-f','-v',name],capture_output=True)
    Path(args.report).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
