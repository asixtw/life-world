"""Offline preflight contract checks; do not claim real PostgreSQL DDL execution."""
from unittest.mock import patch
import pytest
from scripts import pg_owner_matrix_fixture as f

class Cursor:
    def __init__(self, defect=None):self.defect=defect;self.result=None
    def close(self):pass
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,sql,args=()):
        if 'shobj_description' in sql:self.result=('life_world_dev','wrong' if self.defect=='marker' else 'STEP10_LOCAL_SYNTHETIC_ONLY')
        elif sql=='SELECT current_user':self.result=('lw_app',)
        elif 'rolsuper' in sql:self.result=(self.defect=='super',False)
        elif 'has_schema_privilege' in sql:self.result=(self.defect=='schema_create',)
        elif 'information_schema.columns' in sql:
            self.result=list(f.COLUMNS[args[0]].items())
            if self.defect=='missing_table':self.result=[]
            if self.defect=='wrong_type':self.result=[(k,'text' if k=='enabled' else v) for k,v in self.result]
        elif 'pg_get_userbyid' in sql:self.result=('lw_app' if self.defect=='owner' else 'lw_migration_role',)
        elif 'has_table_privilege' in sql:
            allowed=args[1] in {'SELECT','INSERT','UPDATE'} or (args[0].endswith('relationship_features') and args[1]=='DELETE')
            if self.defect=='grant_option' and args[1]=='SELECT WITH GRANT OPTION':allowed=True
            if self.defect=='maintain' and args[1]=='MAINTAIN':allowed=True
            if self.defect=='extra_delete' and args[0].endswith('preferences') and args[1]=='DELETE':allowed=True
            if self.defect=='missing_delete' and args[1]=='DELETE':allowed=False
            self.result=(allowed,)
        elif 'LIMIT 0' in sql:self.result=[]
        else:raise AssertionError(sql)
    def fetchone(self):return self.result
    def fetchall(self):return self.result

class Connection:
    def __init__(self,defect=None):self.c=Cursor(defect)
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def cursor(self):return self.c

@pytest.mark.parametrize('defect',[None,'marker','super','schema_create','missing_table','wrong_type','owner','extra_delete','missing_delete','maintain','grant_option'])
def test_runtime_schema_preflight_rejects_incomplete_or_excess_grants(monkeypatch,defect):
    monkeypatch.setattr(f.bootstrap,'admin_connection',lambda:Connection(defect))
    monkeypatch.setattr(f.bootstrap,'test_config',lambda:{})
    monkeypatch.setattr(f.bootstrap.driver,'connect',lambda **kwargs:Connection(defect))
    if defect is None:f.verify()
    else:
        with pytest.raises((ValueError,AssertionError)):f.verify()

def test_fixture_sql_is_local_guarded_and_minimal():
    sql=f.DDL
    for text in ["current_database()<>'life_world_dev'","current_setting('cluster_name')",'STEP10_LOCAL_SYNTHETIC_ONLY','STOP existing or partial memory fixture','SET LOCAL ROLE lw_migration_role']:
        assert text in sql
    assert sql.index('DO $guard$')<sql.index('CREATE TABLE')
    assert 'GRANT SELECT,INSERT,UPDATE ON relationship_memory_preferences TO lw_app_role' in sql
    assert 'GRANT SELECT,INSERT,UPDATE,DELETE ON relationship_features TO lw_app_role' in sql
    assert 'TO lw_alpha' not in sql and 'TO lw_e2e' not in sql
    assert 'DROP ' not in sql and 'TRUNCATE ' not in sql
