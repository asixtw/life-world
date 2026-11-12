# 2026-11-10 自 8445（life-world-react-integrated/app/environment.py）原樣移植。
"""排程生成的環境白名單：環境代號固定對應資料庫、Schema、資料庫標記、Cloud Tasks Queue 與作品檔案的 bucket。

Local E2E、Alpha 與正式環境使用不同的 Cloud SQL 資料庫，必須互相隔離：
- 對應關係寫在程式內，不由環境變數或 Task 內容決定；設定與白名單不一致時，排程生成不啟用。
- 正式環境（life_world_dev）不在白名單內，所以正式 Revision 永遠不會執行排程生成。
- Alpha 由管理者建置中：只登記已確認的資料庫與 Queue 名稱；Schema 與資料庫標記未確認前不比對。
- Worker 每次執行前，以實際連線查詢 current_database()、current_schema() 與資料庫標記，和白名單比對。
"""
import json  # 結構化診斷紀錄
from pathlib import Path  # SQLite 測試檔名
import sys  # 診斷紀錄寫到 stdout，由 Cloud Run 解析成結構化日誌

ENVIRONMENTS = {
    'e2e': {'backend': 'postgresql', 'database': 'life_world_e2e', 'schema': 'lw_core_draft',
            'marker': 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1', 'queue': 'lw-roleplay-e2e', 'worker_host_prefix': 'e2e---lw-api-main-',
            'works_bucket': 'lw-works-e2e-513506'},  # 作品檔案（匯出的 HTML、之後的圖片）只能寫進這個環境自己的 bucket
    'alpha': {'backend': 'postgresql', 'database': 'life_world_alpha', 'schema': None, 'marker': None,
              'queue': 'lw-roleplay-alpha', 'worker_host_prefix': None, 'works_bucket': None},  # Alpha 還沒有 bucket：匯出不開放
    # 只供隔離自動測試（SQLite＋記憶體佇列）；雲端設定不可使用。
    'local-test': {'backend': 'sqlite', 'database': 'lifeworld.sqlite3', 'schema': 'main', 'marker': None,
                   'queue': 'memory', 'worker_host_prefix': None, 'works_bucket': 'memory'},
}
ROLEPLAY_TABLES = ('data_consents', 'session_turns')  # 008a 建立的資料表；不存在時拒絕執行（例如 Migration 尚未套用）

# 實際連線的身分：資料庫、Schema、標記、owner、登入角色、資料表數，以及 008a 的表、索引與最小權限。
# 只讀系統目錄；不讀任何使用者資料。
PG_IDENTITY_SQL = (
    "SELECT current_database() AS database_name, current_schema() AS database_schema, "
    "shobj_description((SELECT oid FROM pg_database WHERE datname = current_database()), 'pg_database') AS marker, "
    "pg_get_userbyid((SELECT datdba FROM pg_database WHERE datname = current_database())) AS owner, current_user AS db_user, "
    "(SELECT count(*) FROM pg_tables WHERE schemaname = current_schema()) AS table_count, "
    "to_regclass('data_consents') IS NOT NULL AS has_data_consents, to_regclass('session_turns') IS NOT NULL AS has_session_turns, "
    "(SELECT count(*) FROM pg_indexes WHERE schemaname = current_schema() AND indexname IN "
    "('data_consents_one_active_uq','data_consents_owner_idx','works_one_active_self_persona_uq','session_turns_owner_work_idx')) AS roleplay_indexes, "
    "has_table_privilege(to_regclass('session_turns'), 'INSERT') AS turns_insert, "
    "has_table_privilege(to_regclass('session_turns'), 'UPDATE') AS turns_update, "
    "has_table_privilege(to_regclass('session_turns'), 'DELETE') AS turns_delete, "
    "has_table_privilege(to_regclass('data_consents'), 'DELETE') AS consents_delete")


def emit_diagnostic(record):
    """一行 ASCII JSON；不含 Secret、Token、Prompt 或使用者內容。"""
    try:
        sys.stdout.write(json.dumps(record, ensure_ascii=True, separators=(',', ':'), default=str) + '\n')
        sys.stdout.flush()
    except Exception:
        pass  # 日誌失敗不影響主流程


BASE = object()  # 沿用白名單的值


def expected_for(environment_id, database=None, schema=None, marker=BASE):
    """白名單中的期望值；自動測試可覆寫（以 SQLite 模擬雲端連線，或模擬不一致）。marker=None 表示不比對標記。"""
    base = ENVIRONMENTS[environment_id]
    return {'backend': base['backend'], 'database': database or base['database'],
            'schema': base['schema'] if schema is None else schema, 'marker': base['marker'] if marker is BASE else marker}


def connected_identity(db):
    """回傳實際連線的資料庫身分；PostgreSQL 查系統目錄，SQLite（只供測試）用檔名。"""
    if db.backend == 'postgresql':
        with db.connect() as c:
            return dict(c.execute(PG_IDENTITY_SQL).fetchone())  # Row 是 Mapping；布林值會轉成 0／1
    with db.connect() as c:
        tables = {row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    return {'database_name': Path(db.path).name, 'database_schema': 'main', 'marker': None,
            'has_data_consents': 'data_consents' in tables, 'has_session_turns': 'session_turns' in tables}


def identity_mismatch(expected, identity):
    """比對期望與實際；一致回 None，否則回固定原因代碼。"""
    if identity.get('database_name') != expected['database']:
        return 'database_mismatch'
    if expected['schema'] is not None and identity.get('database_schema') != expected['schema']:
        return 'schema_mismatch'
    if expected['marker'] is not None and identity.get('marker') != expected['marker']:
        return 'marker_mismatch'
    if not (identity.get('has_data_consents') and identity.get('has_session_turns')):
        return 'roleplay_tables_missing'
    return None
