"""PG 測試必須指向獨立且帶 marker 的合成 cluster。"""
from contextlib import closing
from pathlib import Path
import importlib.util
import os

from app.postgres import PostgresDatabase
from app.runtime import RuntimeSettings

_spec = importlib.util.spec_from_file_location('pg_bootstrap', Path(__file__).resolve().parent.parent / 'scripts/pg_test_bootstrap.py')
bootstrap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bootstrap)


def settings():
    config = bootstrap.test_config()
    # 測試庫與 alpha 同一套 010 結構，關係來源跟 alpha 上的 010 程式一樣用 link_table。
    return RuntimeSettings(backend='postgresql', db_host=config['host'], db_port=config['port'],
                           db_password=config['password'], pool_size=8, pg_tls='disable',
                           relation_source_store='link_table')


def reset():
    """只清理 marker cluster 的30張業務表；不改正式資料或 migration metadata。"""
    with bootstrap.admin_connection() as raw, closing(raw.cursor()) as c:
        c.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
        if c.fetchone()[0] != 'STEP10_LOCAL_SYNTHETIC_ONLY':
            raise ValueError('Refusing reset of unmarked test database')
        c.execute("SELECT tablename FROM pg_tables WHERE schemaname='lw_core_draft' AND tablename<>'schema_migrations'")
        tables = c.fetchall()
        # 名稱只來自專用 schema 的系統目錄，識別字仍逐一 quote。
        quoted = ','.join('lw_core_draft."' + row[0].replace('"', '""') + '"' for row in tables)
        c.execute('TRUNCATE TABLE ' + quoted + ' RESTART IDENTITY CASCADE')


def database():
    reset()
    return PostgresDatabase(settings())
