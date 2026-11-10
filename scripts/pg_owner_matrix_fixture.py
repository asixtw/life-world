"""Only the disposable local PG18 owner-matrix fixture. Never a cloud migration."""
from contextlib import closing
from scripts import pg_test_bootstrap as bootstrap

DDL = """
BEGIN;
DO $guard$ BEGIN
 IF current_database()<>'life_world_dev'
 OR current_setting('cluster_name')<>'lifeworld-step10-4-synthetic'
 OR current_setting('server_version_num')::int/10000<>18 THEN
  RAISE EXCEPTION 'STOP wrong synthetic target'; END IF;
 IF (SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database())
 IS DISTINCT FROM 'STEP10_LOCAL_SYNTHETIC_ONLY' THEN
  RAISE EXCEPTION 'STOP missing synthetic database marker'; END IF;
 IF to_regclass('lw_core_draft.relationship_features') IS NOT NULL
 OR to_regclass('lw_core_draft.relationship_memory_preferences') IS NOT NULL THEN
  RAISE EXCEPTION 'STOP existing or partial memory fixture'; END IF;
END $guard$;
SET LOCAL ROLE lw_migration_role;
SET LOCAL search_path=lw_core_draft,pg_catalog;
CREATE TABLE relationship_memory_preferences (
 owner_id TEXT PRIMARY KEY REFERENCES users(id), enabled BOOLEAN NOT NULL DEFAULT FALSE,
 preferences TEXT NOT NULL DEFAULT '{}', revision INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE relationship_features (
 owner_id TEXT NOT NULL REFERENCES users(id), subject_type TEXT NOT NULL CHECK(subject_type IN ('user','person','relationship','context')),
 subject_id TEXT NOT NULL, feature_key TEXT NOT NULL, value TEXT NOT NULL, source_refs TEXT NOT NULL,
 context_scope TEXT NOT NULL, epistemic_status TEXT NOT NULL, model_version TEXT NOT NULL,
 profile_version INTEGER NOT NULL, revocation_state TEXT NOT NULL CHECK(revocation_state IN ('active','withdrawn')),
 PRIMARY KEY(owner_id,subject_type,subject_id,feature_key)
);
REVOKE ALL ON relationship_memory_preferences,relationship_features FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON relationship_memory_preferences TO lw_app_role;
GRANT SELECT,INSERT,UPDATE,DELETE ON relationship_features TO lw_app_role;
COMMIT;
"""
COLUMNS = {
 'relationship_memory_preferences': {'owner_id':'text','enabled':'boolean','preferences':'text','revision':'integer'},
 'relationship_features': {'owner_id':'text','subject_type':'text','subject_id':'text','feature_key':'text','value':'text',
   'source_refs':'text','context_scope':'text','epistemic_status':'text','model_version':'text','profile_version':'integer','revocation_state':'text'},
}


def install():
    # admin_connection verifies cluster_name and version before any DDL.
    with bootstrap.admin_connection() as raw, closing(raw.cursor()) as c:
        c.execute(DDL)
    verify()


def verify():
    # Recheck cluster/database guards; never infer safety from host alone.
    with bootstrap.admin_connection() as raw, closing(raw.cursor()) as c:
        c.execute("SELECT current_database(), shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
        if tuple(c.fetchone())!=('life_world_dev','STEP10_LOCAL_SYNTHETIC_ONLY'):
            raise ValueError('STOP synthetic fixture marker mismatch')
    with bootstrap.driver.connect(user='lw_app',database='life_world_dev',**bootstrap.test_config()) as raw, closing(raw.cursor()) as c:
        c.execute('SELECT current_user')
        if c.fetchone()[0]!='lw_app':raise ValueError('STOP wrong runtime identity')
        c.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
        if tuple(c.fetchone())!=(False,False):raise ValueError('STOP privileged runtime role')
        c.execute("SELECT has_schema_privilege(current_user,'lw_core_draft','CREATE')")
        if c.fetchone()[0] is not False:raise ValueError('STOP runtime schema CREATE privilege')
        for table,expected in COLUMNS.items():
            c.execute("SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='lw_core_draft' AND table_name=?",(table,))
            if dict(c.fetchall())!=expected:raise ValueError('STOP memory fixture column/type mismatch: '+table)
            c.execute("SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid=to_regclass(?)",('lw_core_draft.'+table,))
            if c.fetchone()[0]!='lw_migration_role':raise ValueError('STOP unexpected fixture owner')
            allowed={'SELECT','INSERT','UPDATE'} | ({'DELETE'} if table=='relationship_features' else set())
            for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN'):
                c.execute('SELECT has_table_privilege(current_user,?,?)',('lw_core_draft.'+table,privilege))
                if bool(c.fetchone()[0])!=(privilege in allowed):raise ValueError('STOP memory fixture privilege mismatch: '+table+'/'+privilege)
                c.execute('SELECT has_table_privilege(current_user,?,?)',('lw_core_draft.'+table,privilege+' WITH GRANT OPTION'))
                if c.fetchone()[0]:raise ValueError('STOP unexpected runtime grant option: '+table+'/'+privilege)
            # Only metadata/empty projection, never inspect rows.
            c.execute('SELECT * FROM lw_core_draft.'+table+' LIMIT 0')
    print('Owner matrix schema preflight passed: synthetic dev, two tables, runtime minimum grants; no business rows read')

if __name__=='__main__':install()
