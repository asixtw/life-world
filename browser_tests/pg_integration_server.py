"""受限本機PG18瀏覽器服務；驗marker後才連線，不DDL/GRANT/清資料，更不連Cloud SQL。"""
from contextlib import closing
from datetime import datetime,timezone
import os
from scripts.pg_integration_fixture import connect,config,DB
from app.main import create_app
from app.postgres import PostgresDatabase
from app.runtime import RuntimeSettings

# connect逐一確認127.0.0.1/專用port/PG18/cluster與database marker；秘密只在記憶體使用。
with closing(connect(DB,runtime=True)):
    pass
settings=RuntimeSettings(backend='postgresql',db_host='127.0.0.1',db_port=57518,db_name=DB,db_user='lw_e2e_app',db_password=config()['password'],pg_tls='disable',relation_source_store='link_table')
app=create_app(data_dir=os.environ['LIFEWORLD_DATA_DIR'],database=PostgresDatabase(settings),settings=settings,clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))
