"""部署候選契約必須阻止跨環境授權；不執行雲端DDL。"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def test_alpha_grants_use_explicit_database_and_dedicated_roles():
    sql=(ROOT/'deploy/postgres/alpha_app_grants.review.sql').read_text()
    assert "current_database() <> 'life_world_alpha'" in sql
    assert 'TO lw_alpha_app_role' in sql
    assert 'TO lw_app_role' not in sql
    assert "pg_has_role('lw_alpha_app', 'lw_app_role', 'MEMBER')" in sql
    assert 'auth_rate_buckets' in sql
    assert 'GRANT DELETE ON TABLE lw_core_draft.auth_rate_buckets' not in sql


def test_dev_increment_cannot_run_in_alpha_database():
    sql=(ROOT/'deploy/postgres/auth_rate_limit.review.sql').read_text()
    assert "current_database() <> 'life_world_dev'" in sql
    assert 'TO lw_app_role' in sql


def test_alpha_configuration_lists_unresolved_proxy_without_fake_values():
    text=(ROOT/'deploy/README.alpha-candidate.md').read_text()
    for name in ('LIFEWORLD_AUTH_TRUSTED_PROXIES','LIFEWORLD_EXTERNAL_ORIGIN','LIFEWORLD_AUTH_RATE_SECRET','life_world_alpha','lw_alpha_app'):
        assert name in text
    assert 'NOT_READY' in text
    assert '0.0.0.0/0' not in text


def test_alpha_pg_grants_context_rollback_and_bidirectional_isolation(app):
    """只在已標記的合成PG18；不連CloudSQL，失敗不清空任何資料庫。"""
    import pytest
    from contextlib import closing
    if app.state.service.db.backend!='postgresql':
        pytest.skip('dedicated synthetic PG18 required')
    import pg8000.dbapi as driver
    from scripts.pg_test_bootstrap import admin_connection,test_config
    grants=(ROOT/'deploy/postgres/alpha_app_grants.review.sql').read_text()
    alpha_ddl=(ROOT/'deploy/postgres/alpha_auth_rate_limit.review.sql').read_text()
    dev_ddl=(ROOT/'deploy/postgres/auth_rate_limit.review.sql').read_text()
    role_ddl=(ROOT/'deploy/postgres/alpha_roles_database.review.sql').read_text()
    # 錯誤DB context必須在任何CREATE／GRANT之前中止。
    with admin_connection() as raw,closing(raw.cursor()) as c:
        for sql in (grants,alpha_ddl,role_ddl):
            with pytest.raises(driver.DatabaseError):c.execute(sql)
            c.execute('ROLLBACK')
    with admin_connection('life_world_alpha') as raw,closing(raw.cursor()) as c:
        c.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
        assert c.fetchone()[0]=='STEP10_LOCAL_SYNTHETIC_ONLY'
        c.execute('REVOKE CONNECT, TEMPORARY ON DATABASE life_world_alpha FROM PUBLIC')
        c.execute('GRANT CONNECT ON DATABASE life_world_alpha TO lw_alpha_app_role')
        c.execute(grants)
        for sql in (dev_ddl,alpha_ddl,role_ddl):
            # dev錯context、Alpha既有表重播均失敗；rollback後原表內容與權限仍存在。
            c.execute('SELECT count(*) FROM lw_core_draft.users');before=c.fetchone()[0]
            with pytest.raises(driver.DatabaseError):c.execute(sql)
            c.execute('ROLLBACK')
            c.execute('SELECT count(*) FROM lw_core_draft.users');assert c.fetchone()[0]==before
        c.execute("SELECT has_database_privilege('lw_app','life_world_alpha','CONNECT')")
        assert c.fetchone()[0] is False
    with driver.connect(user='lw_alpha_app',database='life_world_alpha',**test_config()) as raw,closing(raw.cursor()) as c:
        for sql in ('DELETE FROM lw_core_draft.auth_rate_buckets',
                    'SELECT * FROM lw_core_draft.schema_migrations',
                    'CREATE TABLE lw_core_draft.forbidden_alpha_table(id integer)'):
            with pytest.raises(driver.DatabaseError) as e:c.execute(sql)
            assert e.value.args[0]['C']=='42501'
            raw.rollback()
        c.execute('SELECT count(*) FROM lw_core_draft.auth_rate_buckets');assert c.fetchone()[0]>=0
    with driver.connect(user='lw_alpha_app',database='life_world_dev',**test_config()) as raw,closing(raw.cursor()) as c:
        with pytest.raises(driver.DatabaseError) as e:c.execute('SELECT count(*) FROM lw_core_draft.users')
        assert e.value.args[0]['C']=='42501'
    with pytest.raises(driver.DatabaseError) as e:
        driver.connect(user='lw_app',database='life_world_alpha',**test_config())
    assert e.value.args[0]['C']=='42501'
