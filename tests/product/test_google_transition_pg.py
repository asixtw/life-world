"""真PG18合成Alpha轉換及清除；只允許本機marker cluster，無雲端或真OAuth。"""
import os,json
from datetime import datetime,timedelta,timezone
from contextlib import closing
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.runtime import RuntimeSettings
from app.postgres import PostgresDatabase
from app.guest_lifecycle import GuestPurger
from app.guest_maintenance import run_batch
from test_google_exchange import Verifier,challenge
from conftest import onboard,draft,confirm_payload,guest

pytestmark=pytest.mark.skipif(os.environ.get('LIFEWORLD_GOOGLE_TRANSITION_PG')!='1',reason='requires dedicated local Google transition PG18 fixture')


@pytest.fixture(scope='module')
def pg_contract():
    from pg_support import bootstrap
    with bootstrap.admin_connection('life_world_alpha') as raw,closing(raw.cursor()) as c:
        c.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
        assert c.fetchone()[0]=='STEP10_LOCAL_SYNTHETIC_ONLY'
        c.execute('SET search_path TO lw_core_draft,pg_catalog')
        c.execute('CREATE TABLE IF NOT EXISTS external_identities(provider TEXT NOT NULL,issuer TEXT NOT NULL,subject TEXT NOT NULL,owner_id TEXT NOT NULL REFERENCES users(id),created_at TIMESTAMPTZ NOT NULL,PRIMARY KEY(provider,issuer,subject))')
        c.execute("CREATE TABLE IF NOT EXISTS guest_abandonments(owner_id TEXT PRIMARY KEY,abandoned_at TIMESTAMPTZ NOT NULL,purge_after TIMESTAMPTZ NOT NULL,status TEXT NOT NULL CHECK(status IN ('pending','retry','completed')),attempts BIGINT NOT NULL DEFAULT 0,last_error_code TEXT,completed_at TIMESTAMPTZ,media_state TEXT NOT NULL DEFAULT 'pending',media_attempts BIGINT NOT NULL DEFAULT 0)")
        c.execute('ALTER TABLE external_identities OWNER TO lw_alpha_owner');c.execute('ALTER TABLE guest_abandonments OWNER TO lw_alpha_owner')
        c.execute('GRANT SELECT,INSERT ON external_identities,guest_abandonments TO lw_alpha_app_role')
        c.execute("SELECT rolname FROM pg_roles WHERE rolname='lw_alpha_maintenance'")
        role_exists=c.fetchone() is not None
        if not role_exists:
            c.execute("SELECT format('CREATE ROLE lw_alpha_maintenance LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',?::text)",(bootstrap.test_config()['password'],));c.execute(c.fetchone()[0])
        c.execute('GRANT CONNECT ON DATABASE life_world_alpha TO lw_alpha_maintenance');c.execute('GRANT USAGE ON SCHEMA lw_core_draft TO lw_alpha_maintenance')
        # Worker只讀清除範圍判斷所需欄位；不授予讀取經歷原文／媒體內容或DDL。
        from app.guest_fk import catalog
        from pathlib import Path
        graph=json.loads(Path('app/guest_fk_contract.json').read_text());cols={}
        for child,columns,parent,targets in graph:
            cols.setdefault(child,set()).update(columns);cols.setdefault(parent,set()).update(targets)
        c.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='lw_core_draft' AND column_name='owner_id'")
        for table,column in c.fetchall():cols.setdefault(table,set()).add(column)
        cols.setdefault('users',set()).update(['id','status'])
        excluded={'schema_migrations','auth_rate_buckets','guest_abandonments'}
        for table,columns in cols.items():
            if table in excluded:continue
            c.execute('GRANT SELECT('+','.join('"'+x+'"' for x in sorted(columns))+') ON "'+table+'" TO lw_alpha_maintenance')
        c.execute('GRANT SELECT ON guest_abandonments TO lw_alpha_maintenance')
        c.execute('GRANT UPDATE(status,attempts,last_error_code,completed_at,media_state,media_attempts) ON guest_abandonments TO lw_alpha_maintenance')
        c.execute("SELECT tablename FROM pg_tables WHERE schemaname='lw_core_draft'")
        for row in c.fetchall():
            if row[0] not in excluded|{'external_identities'}:c.execute('GRANT DELETE ON "'+row[0]+'" TO lw_alpha_maintenance')
    yield bootstrap


@pytest.fixture
def transition(pg_contract,tmp_path):
    from app.config import DemoPolicy
    from dataclasses import replace
    cfg=pg_contract.test_config()
    with pg_contract.admin_connection('life_world_alpha') as raw,closing(raw.cursor()) as c:
        c.execute("SELECT tablename FROM pg_tables WHERE schemaname='lw_core_draft' AND tablename<>'schema_migrations'")
        c.execute('TRUNCATE '+','.join('lw_core_draft."'+r[0]+'"' for r in c.fetchall())+' RESTART IDENTITY CASCADE')
    settings=RuntimeSettings(backend='postgresql',db_name='life_world_alpha',db_user='lw_alpha_app',db_host=cfg['host'],db_port=cfg['port'],db_password=cfg['password'],pg_tls='disable',google_client_id=Verifier.client_id,registration_enabled=False,password_login_enabled=False)
    db=PostgresDatabase(settings);verifier=Verifier();now=[datetime(2026,10,27,7,tzinfo=timezone.utc)]
    app=create_app(tmp_path,database=db,settings=settings,google_verifier=verifier,clock=lambda:now[0],policy=DemoPolicy(points_per_experience=3))
    worker=PostgresDatabase(replace(settings,db_user='lw_alpha_maintenance'))
    def client():
        c=TestClient(app);c.headers['Origin']='http://testserver';return c
    yield app,verifier,now,worker,client
    worker.close();db.close()


def pair(transition):
    app,v,now,worker,client=transition;a=client();target,g=onboard(a);d=draft(a,g);assert a.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d)).status_code==201
    r=a.post('/api/auth/external/exchange',json=challenge(a,v));assert r.status_code==200;a.headers['X-CSRF-Token']=r.json()['csrf_token']
    b=client();source,sg=onboard(b);d=draft(b,sg);assert b.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d)).status_code==201;draft(b,sg,raw_text='仍待確認的原文')
    body=challenge(b,v,mode='login',discard_guest=True,token='switch-pg');r=b.post('/api/auth/external/exchange',json=body);assert r.status_code==200,r.text;b.headers['X-CSRF-Token']=r.json()['csrf_token']
    return a,b,target,source


def owner_snapshot(db,owner):
    """只回傳合成資料列雜湊，失敗日誌也不輸出Session／內容。"""
    import hashlib
    with db.connect() as c:
        tables=c.execute("SELECT table_name FROM information_schema.columns WHERE table_schema='lw_core_draft' AND column_name='owner_id'").fetchall();result={}
        for table in tables:
            name=table['table_name']
            if name=='guest_abandonments':continue
            rows=[dict(row) for row in c.execute('SELECT * FROM "'+name+'" WHERE owner_id=?',(owner,)).fetchall()]
            encoded=sorted(json.dumps(row,sort_keys=True,default=str) for row in rows);result[name]=hashlib.sha256(json.dumps(encoded).encode()).hexdigest()
        return result


def test_pg_switch_then_due_purge_preserves_other_owner(transition):
    app,v,now,worker,client=transition;a,b,target,source=pair(transition);saved=b.get('/api/state').json();snapshot=owner_snapshot(app.state.service.db,target['owner_id']);purger=GuestPurger(worker,lambda:now[0])
    assert purger.purge(source['owner_id'])=='not_due'
    now[0]+=timedelta(days=14);assert purger.purge(source['owner_id'])=='completed'
    assert purger.purge(source['owner_id'])=='noop'
    assert owner_snapshot(app.state.service.db,target['owner_id'])==snapshot
    with app.state.service.db.connect() as db:
        assert db.execute('SELECT id FROM users WHERE id=?',(source['owner_id'],)).fetchone() is None
        assert db.execute('SELECT status FROM guest_abandonments WHERE owner_id=?',(source['owner_id'],)).fetchone()['status']=='completed'
        assert db.execute('SELECT owner_id FROM external_identities').fetchone()['owner_id']==target['owner_id']
    # 14天後舊Session過期是正常狀態；直接比對正式資料，不用過期Cookie冒稱回訪。
    with app.state.service.db.connect() as db:
        assert db.execute('SELECT count(*) AS n FROM experiences WHERE owner_id=?',(target['owner_id'],)).fetchone()['n']==len(saved['experiences'])
        assert db.execute('SELECT count(*) AS n FROM reward_ledger WHERE owner_id=?',(target['owner_id'],)).fetchone()['n']==1


@pytest.mark.parametrize('changed',['registered','bound'])
def test_pg_registered_target_is_never_purged(transition,changed):
    app,v,now,worker,client=transition;_,_,target,source=pair(transition);now[0]+=timedelta(days=14)
    from pg_support import bootstrap
    with bootstrap.admin_connection('life_world_alpha') as raw,closing(raw.cursor()) as db:
        if changed=='registered':db.execute("UPDATE lw_core_draft.users SET status='registered' WHERE id=?",(source['owner_id'],))
        else:db.execute("INSERT INTO lw_core_draft.external_identities VALUES ('google','https://accounts.google.com','source-bound',?,now())",(source['owner_id'],))
    assert GuestPurger(worker,lambda:now[0]).purge(source['owner_id'])=='owner_changed'
    with app.state.service.db.connect() as db:assert db.execute('SELECT id FROM users WHERE id=?',(source['owner_id'],)).fetchone()


def test_pg_media_failure_retries_and_exhaustion_is_durable(transition):
    app,v,now,worker,client=transition;_,_,target,source=pair(transition);now[0]+=timedelta(days=14);calls=[]
    def fail(owner):calls.append(owner);raise RuntimeError('synthetic interruption')
    purger=GuestPurger(worker,lambda:now[0],fail)
    for _ in range(5):assert purger.purge(source['owner_id'])=='cleanup_failed'
    assert purger.purge(source['owner_id'])=='media_retry_exhausted'
    assert calls==[source['owner_id']]*5
    with app.state.service.db.connect() as db:
        row=db.execute('SELECT * FROM guest_abandonments').fetchone();assert row['status']=='retry' and row['last_error_code']=='media_failed' and row['media_attempts']==5
    result,failed=run_batch(worker,lambda:now[0]);assert failed and result=={'retry_exhausted':1}


def test_pg_interrupted_worker_retries_to_completion(transition):
    app,v,now,worker,client=transition;_,_,target,source=pair(transition);now[0]+=timedelta(days=14)
    def crash(owner):raise RuntimeError('synthetic interruption')
    assert GuestPurger(worker,lambda:now[0],crash).purge(source['owner_id'])=='cleanup_failed'
    assert GuestPurger(worker,lambda:now[0]).purge(source['owner_id'])=='completed'


def test_pg_cross_owner_reference_stops_before_cleanup(transition):
    app,v,now,worker,client=transition;_,_,target,source=pair(transition);now[0]+=timedelta(days=14)
    from pg_support import bootstrap
    with bootstrap.admin_connection('life_world_alpha') as raw,closing(raw.cursor()) as db:
        db.execute('SELECT id FROM lw_core_draft.goals WHERE owner_id=?',(target['owner_id'],));goal=db.fetchone()[0]
        db.execute('UPDATE lw_core_draft.drafts SET goal_id=? WHERE owner_id=?',(goal,source['owner_id']))
    calls=[];assert GuestPurger(worker,lambda:now[0],lambda owner:calls.append(owner)).purge(source['owner_id'])=='cross_owner_reference';assert not calls
    with app.state.service.db.connect() as db:assert db.execute('SELECT last_error_code FROM guest_abandonments').fetchone()['last_error_code']=='cross_owner_reference'


def test_pg_upgrade_preserves_rows_and_original_owner(transition):
    app,v,now,worker,client=transition;c=client();me,g=onboard(c);d=draft(c,g);c.post('/api/drafts/'+d['id']+'/confirm',json=confirm_payload(d));draft(c,g,raw_text='未確認草稿')
    before=c.get('/api/state').json();r=c.post('/api/auth/external/exchange',json=challenge(c,v));assert r.status_code==200 and r.json()['owner_id']==me['owner_id'];after=c.get('/api/state').json()
    assert {k:x for k,x in before.items() if k!='user'}=={k:x for k,x in after.items() if k!='user'}
    with app.state.service.db.connect() as db:
        assert db.execute('SELECT count(*) AS n FROM users').fetchone()['n']==1
        assert db.execute('SELECT count(*) AS n FROM guest_abandonments').fetchone()['n']==0


def test_pg_process_interruption_before_media_done_is_retryable(transition):
    app,v,now,worker,client=transition;_,_,target,source=pair(transition);now[0]+=timedelta(days=14)
    def interrupted(owner):raise SystemExit('synthetic process death')
    with pytest.raises(SystemExit):GuestPurger(worker,lambda:now[0],interrupted).purge(source['owner_id'])
    with app.state.service.db.connect() as db:
        row=db.execute('SELECT * FROM guest_abandonments').fetchone();assert row['status']=='pending' and row['media_attempts']==1
    assert GuestPurger(worker,lambda:now[0]).purge(source['owner_id'])=='completed'


def test_pg_switch_receipt_replay_and_worker_cannot_read_media(transition):
    app,v,now,worker,client=transition;a,b,target,source=pair(transition)
    with app.state.service.db.connect() as db:
        row=db.execute("SELECT request_id FROM requests WHERE owner_id=? AND operation='google_exchange_v1'",(source['owner_id'],)).fetchone()
    r=b.post('/api/auth/external/status',json={'challenge_id':row['request_id']});assert r.status_code==200 and r.json()['guest_abandoned'] and r.json()['owner_id']==target['owner_id']
    from app.errors import DomainError
    with pytest.raises(DomainError) as denied:
        with worker.connect() as db:db.execute('SELECT content FROM evidence LIMIT 0')
    assert denied.value.status==503 and denied.value.code=='database_permission_unavailable'


def test_pg_two_devices_return_to_one_registered_owner(transition):
    from concurrent.futures import ThreadPoolExecutor
    app,v,now,worker,client=transition;a=client();target,_=onboard(a);assert a.post('/api/auth/external/exchange',json=challenge(a,v)).status_code==200
    clients=[client(),client()];bodies=[]
    for i,c in enumerate(clients):
        guest(c);bodies.append(challenge(c,v,mode='login',discard_guest=True,token='pg-device-'+str(i)))
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda pair:pair[0].post('/api/auth/external/exchange',json=pair[1]),zip(clients,bodies)))
    assert all(r.status_code==200 and r.json()['owner_id']==target['owner_id'] for r in results)
    with app.state.service.db.connect() as db:
        assert db.execute('SELECT count(*) AS n FROM users').fetchone()['n']==3
        assert db.execute('SELECT count(*) AS n FROM external_identities').fetchone()['n']==1
        assert db.execute('SELECT count(*) AS n FROM guest_abandonments').fetchone()['n']==2
