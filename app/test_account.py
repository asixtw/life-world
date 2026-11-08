"""僅啟動時建立Owner授權的單一測試帳號；不提供HTTP建帳號入口。"""
import re
from uuid import UUID


def provision(service,settings,payload,*,allow_sqlite_test=False):
    """僅新增指定Owner；同設定可重啟，既有不同帳號或密碼一律不覆寫。"""
    username=payload.get('username','');owner=payload.get('owner_id','');password_hash=payload.get('password_hash','')
    UUID(owner)
    if username not in settings.test_login_usernames or not re.fullmatch(r'[a-z0-9_]{3,30}',username) or not password_hash.startswith('$argon2id$'):
        raise ValueError('Invalid explicit test account seed')
    db=service.db
    if db.backend!='postgresql' and not allow_sqlite_test:raise ValueError('Test account seed requires Product PostgreSQL')
    if db.backend=='postgresql' and (settings.db_name!='life_world_product_staging' or settings.db_schema!='lw_core_draft' or settings.db_user!='lw_product_staging_app'):
        raise ValueError('Wrong test account target')
    with db.connect(write=True) as c:
        if db.backend=='postgresql':
            c.execute('SELECT pg_advisory_xact_lock(?)',(155001001,))
            marker=c.execute("SELECT shobj_description(oid,'pg_database') AS marker FROM pg_database WHERE datname=current_database()").fetchone()
            if not marker or marker['marker']!='LIFEWORLD_PRODUCT_STAGING_GCP130_V1':raise ValueError('Wrong Product marker')
        existing=c.execute('SELECT id,password_hash,status FROM users WHERE username=? OR id=?',(username,owner)).fetchall()
        if existing:
            if len(existing)!=1 or existing[0]['id']!=owner or existing[0]['password_hash']!=password_hash or existing[0]['status']!='registered':
                raise ValueError('Existing test account differs; refusing overwrite')
            return False
        c.execute("INSERT INTO users(id,status,username,password_hash,created_at) VALUES (?,'registered',?,?,?)",(owner,username,password_hash,service.now().isoformat()))
    return True
