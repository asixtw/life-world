"""M0：8030 整合版連 Cloud SQL E2E 的部署設定檔與啟動驗證。

啟用的依據（M0 修正 F1）：
- 專用映像（deploy/Dockerfile.core-e2e）內有一個 root 擁有、唯讀的映像標記檔 IMAGE_MARKER_PATH。
  標記存在時一定強制驗證；Cloud Run 的環境變數無法移除或改寫它。LIFEWORLD_DEPLOYMENT_PROFILE
  若同時設定（包括空字串），必須等於標記，否則拒絕啟動，所以不會因為覆寫成空值而降級。
- 一般映像沒有標記：只有明確設定 LIFEWORLD_DEPLOYMENT_PROFILE 時才啟用；沒有設定時，Public Core 原有的行為完全不變。

啟用時，依 create_app 的實際初始化順序執行：
1. 建連前（preflight）：讀取任何設定物件之前，核對必要的環境變數都明確存在而且等於核准值；
   拒絕 SQLite、正式庫、Alpha；拒絕注入的資料庫或設定物件；拒絕開啟 M0 尚未開放的功能。
2. 建連後：每一條新建立的實體連線（包括 pool 之後重新連線），在交給程式使用之前，
   核對 current_database()、current_user、session_user、current_schema()、server_version_num 與資料庫標記；
   任何一項不符或查不到，就關閉這條連線並拒絕。
3. 啟動時先建立一條連線完成上述核對；失敗就讓 create_app 丟出例外，服務不會啟動。

錯誤訊息只含固定代碼與欄位名稱，不含密碼或連線細節。
"""
from contextlib import closing
from dataclasses import dataclass
import os
import stat

PROFILE_ENV = 'LIFEWORLD_DEPLOYMENT_PROFILE'
# 專用映像的標記檔：由 Dockerfile.core-e2e 以 root 建立、權限 0444，runtime UID 10001 無法修改。
IMAGE_MARKER_PATH = '/etc/lifeworld/deployment-profile'

# M0 修正 F3：Cloud SQL Connector 使用 ADC。專用服務只能使用 Cloud Run 綁定的 runtime service account，
# 所以拒絕會改變 ADC 來源的設定：憑證檔、gcloud 設定目錄、metadata server 位址與用戶端憑證。
ADC_OVERRIDE_NAMES = ('GOOGLE_APPLICATION_CREDENTIALS', 'GOOGLE_API_USE_CLIENT_CERTIFICATE', 'GOOGLE_AUTH_TOKEN',
                      'CLOUDSDK_CONFIG')
ADC_OVERRIDE_PREFIXES = ('GCE_METADATA_', 'CLOUDSDK_AUTH_')
# gcloud 的「使用者 ADC 檔」在 Linux 的預設位置；存在就代表有人掛載或放入了替代憑證。
ADC_WELL_KNOWN_FILES = ('~/.config/gcloud/application_default_credentials.json',)
# M0 修正 V3（F3）：代理設定會改變 metadata server 請求的路徑；core-e2e 不接受任何代理設定（不分大小寫，空值也拒絕）。
PROXY_NAMES = ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY')


class DeploymentProfileError(RuntimeError):
    """部署設定檔或實際資料庫身分不符；服務必須拒絕啟動。"""

    def __init__(self, code, detail=''):
        self.code = code
        super().__init__(code if not detail else f'{code}: {detail}')


@dataclass(frozen=True)
class DeploymentProfile:
    name: str
    required_env: tuple  # ((環境變數, 核准值), ...)：一定要明確存在，不接受預設值
    database: str
    user: str
    schema: str
    server_version_num: str
    marker: str


CORE_E2E = DeploymentProfile(
    name='core-e2e',
    required_env=(
        ('LIFEWORLD_DB_BACKEND', 'postgresql'),
        ('LIFEWORLD_DB_NAME', 'life_world_e2e'),
        ('LIFEWORLD_DB_USER', 'lw_e2e_app'),
        ('LIFEWORLD_DB_SCHEMA', 'lw_core_draft'),
        ('LIFEWORLD_PG_CONNECTION', 'cloud_sql'),
        ('LIFEWORLD_INSTANCE_CONNECTION_NAME', 'life-world-513506:asia-east1:lw-pg-staging-trial'),
        ('LIFEWORLD_EXPECTED_DB_MARKER', 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1'),
    ),
    database='life_world_e2e',
    user='lw_e2e_app',
    schema='lw_core_draft',
    server_version_num='180006',  # PostgreSQL 18.6；Cloud SQL 小版本升級後要更新這裡，否則服務會拒絕啟動
    marker='LIFEWORLD_E2E_SYNTHETIC_ONLY_v1',
)

PROFILES = {CORE_E2E.name: CORE_E2E}

# 明確拒絕的資料庫與帳號：正式庫、Alpha、Product Staging 一律不得作為 8030 整合版的目標。
REFUSED_DATABASES = {'life_world_dev': 'production_database_refused', 'life_world_alpha': 'alpha_database_refused',
                     'life_world_product_staging': 'product_staging_database_refused'}
REFUSED_USERS = {'lw_app': 'production_user_refused', 'lw_alpha_app': 'alpha_user_refused',
                 'lw_product_staging_app': 'product_staging_user_refused'}

# M0 尚未開放的功能：設定了就拒絕啟動，避免新增或沿用的環境變數連帶打開 AI、Google、排程或測試帳號工具。
# 2026-11-10：8030 開放 Gemini 生成（LIFEWORLD_AI_*）與 Google 登入（LIFEWORLD_GOOGLE_CLIENT_ID）。
# 2026-11-10 P1：開放 E2E 背景排程，只接受 8445 已驗證的那一組值（lw-roleplay-e2e、e2e Tag 的 Worker、lw-api-runtime OIDC）；
# 其他排程設定（別的 Queue、別的 Worker 網址或未知的 LIFEWORLD_TASKS_* 名稱）仍拒絕啟動。
E2E_TASK_SETTINGS = {
    'LIFEWORLD_ENVIRONMENT_ID': 'e2e',
    'LIFEWORLD_TASKS_QUEUE': 'projects/life-world-513506/locations/asia-east1/queues/lw-roleplay-e2e',
    'LIFEWORLD_TASKS_WORKER_URL': 'https://e2e---lw-api-main-u5py2jttpa-de.a.run.app/internal/roleplay/tasks',
    'LIFEWORLD_TASKS_INVOKER_SA': 'lw-api-runtime@life-world-513506.iam.gserviceaccount.com',
    'LIFEWORLD_TASKS_AUDIENCE': 'https://lw-api-main-u5py2jttpa-de.a.run.app',
}
M0_FORBIDDEN_PREFIXES = ('LIFEWORLD_TASKS_',)
M0_FORBIDDEN_NAMES = ('LIFEWORLD_ENVIRONMENT_ID', 'LIFEWORLD_TEST_ACCOUNT_SEED',
                      'LIFEWORLD_TEST_LOGIN_USERNAMES')
M0_FALSE_ONLY = ('LIFEWORLD_RELATIONSHIP_MEMORY_ENABLED', 'LIFEWORLD_AUTH_RATE_ENABLED', 'LIFEWORLD_PUBLIC_GATE_CLOSED')
M0_ALLOWED_ACCESS_MODES = ('legacy',)

# 函式與系統表一律寫明 pg_catalog：連線的 search_path 是 "lw_core_draft",pg_catalog，避免被同名物件遮蔽。
IDENTITY_SQL = (
    "SELECT pg_catalog.current_database(), current_user, session_user, pg_catalog.current_schema(), "
    "pg_catalog.current_setting('server_version_num'), "
    "pg_catalog.shobj_description((SELECT d.oid FROM pg_catalog.pg_database d "
    "WHERE d.datname = pg_catalog.current_database()), 'pg_database')"
)


def _present(environ, name):
    value = environ.get(name)
    return value is not None and value != ''


def read_image_marker(path=None):
    """讀取專用映像的標記。沒有標記回傳 None；標記不是一般檔案、可被他人寫入、不是 root 擁有，或內容不是已知設定檔，就拒絕啟動。"""
    path = IMAGE_MARKER_PATH if path is None else path
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError:
        raise DeploymentProfileError('image_marker_unreadable') from None
    if not stat.S_ISREG(info.st_mode):  # 符號連結、目錄或特殊檔都不接受
        raise DeploymentProfileError('image_marker_untrusted')
    if hasattr(os, 'getuid') and (info.st_uid != 0 or info.st_mode & 0o022):  # Linux：只接受 root 擁有、其他人不可寫
        raise DeploymentProfileError('image_marker_untrusted')
    try:
        with open(path, encoding='ascii') as handle:
            value = handle.read(64).strip()
    except (OSError, UnicodeDecodeError):
        raise DeploymentProfileError('image_marker_unreadable') from None
    if value not in PROFILES:
        raise DeploymentProfileError('image_marker_invalid')
    return value


def select_profile(environ, marker_path=None):
    """決定部署設定檔。標記存在時一定使用標記；環境變數只能「不設定」或「與標記相同」，其他（包括空字串）都拒絕。"""
    marker = read_image_marker(marker_path)
    requested = environ.get(PROFILE_ENV)
    if marker is not None:
        if requested is not None and requested != marker:
            raise DeploymentProfileError('deployment_profile_conflict')
        return PROFILES[marker]
    if requested is None or requested == '':
        return None  # 一般映像、沒有設定檔：原有行為
    profile = PROFILES.get(requested)
    if profile is None:
        raise DeploymentProfileError('unknown_deployment_profile', requested[:40])
    return profile


def preflight(environ, database=None, settings=None, marker_path=None):
    """建連前的核對。沒有設定檔時回傳 None（原有行為不變）；否則回傳設定檔，不符就丟出例外。"""
    profile = select_profile(environ, marker_path)
    if profile is None:
        return None
    if database is not None or settings is not None:
        # 部署設定檔只接受由環境變數建立、受本模組核對的資料庫；注入的物件可能繞過核對。
        raise DeploymentProfileError('injected_dependency_refused')
    for key, expected in profile.required_env:
        actual = environ.get(key)
        if actual is None or actual == '':
            raise DeploymentProfileError('missing_required_setting', key)
        if actual == expected:
            continue
        if key == 'LIFEWORLD_DB_BACKEND' and actual == 'sqlite':
            raise DeploymentProfileError('sqlite_refused')
        if key == 'LIFEWORLD_DB_NAME' and actual in REFUSED_DATABASES:
            raise DeploymentProfileError(REFUSED_DATABASES[actual])
        if key == 'LIFEWORLD_DB_USER' and actual in REFUSED_USERS:
            raise DeploymentProfileError(REFUSED_USERS[actual])
        raise DeploymentProfileError('setting_mismatch', key)
    if not _present(environ, 'LIFEWORLD_DB_PASSWORD'):
        raise DeploymentProfileError('missing_required_setting', 'LIFEWORLD_DB_PASSWORD')
    for key in sorted(environ):
        if key.startswith(M0_FORBIDDEN_PREFIXES) and _present(environ, key) and environ[key] != E2E_TASK_SETTINGS.get(key):
            raise DeploymentProfileError('feature_not_open_in_m0', key)
    for key in M0_FORBIDDEN_NAMES:
        if _present(environ, key) and environ[key] != E2E_TASK_SETTINGS.get(key):
            raise DeploymentProfileError('feature_not_open_in_m0', key)
    for key in M0_FALSE_ONLY:
        if _present(environ, key) and environ[key].lower() != 'false':
            raise DeploymentProfileError('feature_not_open_in_m0', key)
    if _present(environ, 'LIFEWORLD_ACCESS_MODE') and environ['LIFEWORLD_ACCESS_MODE'] not in M0_ALLOWED_ACCESS_MODES:
        raise DeploymentProfileError('feature_not_open_in_m0', 'LIFEWORLD_ACCESS_MODE')
    check_credential_source(environ)
    return profile


def check_credential_source(environ, well_known_files=None):
    """M0 修正 F3：只允許 Cloud Run 綁定的 runtime service account 作為 ADC；設定了替代憑證來源就拒絕啟動。"""
    for key in sorted(environ):
        upper = key.upper()  # Linux 的環境變數分大小寫，http_proxy 與 HTTP_PROXY 都要擋
        # 只要設定了（包括空字串）就拒絕，讓 ADC 的查找順序固定為 Cloud Run 的 metadata server。
        if upper in ADC_OVERRIDE_NAMES or upper.startswith(ADC_OVERRIDE_PREFIXES):
            raise DeploymentProfileError('credential_override_refused', key)
        if upper in PROXY_NAMES:
            raise DeploymentProfileError('proxy_setting_refused', key)
    for candidate in (ADC_WELL_KNOWN_FILES if well_known_files is None else well_known_files):
        if os.path.lexists(os.path.expanduser(candidate)):
            raise DeploymentProfileError('credential_file_refused')


def check_settings(settings, profile):
    """RuntimeSettings 建立之後再核對一次，避免設定解析的預設值與環境變數不一致。"""
    expected = {'backend': 'postgresql', 'connection_mode': 'cloud_sql', 'db_name': profile.database,
                'db_user': profile.user, 'db_schema': profile.schema,
                'instance_connection_name': dict(profile.required_env)['LIFEWORLD_INSTANCE_CONNECTION_NAME']}
    for field, value in expected.items():
        if getattr(settings, field) != value:
            raise DeploymentProfileError('setting_mismatch', field)
    if settings.google_client_id or settings.test_login_usernames or settings.access_mode != 'legacy' \
            or settings.auth_rate_enabled or settings.public_gate_closed:
        raise DeploymentProfileError('feature_not_open_in_m0', 'settings')


def verify_identity(raw, profile):
    """以實際連線核對資料庫身分。raw 是 DBAPI 連線；查詢不到或任何一項不符都丟出例外。"""
    try:
        previous = raw.autocommit
    except Exception:
        raise DeploymentProfileError('connection_state_unreadable') from None
    row, failure = None, None
    try:
        raw.autocommit = True  # 不留下未結束的交易，之後的寫入交易才能設定隔離等級
        # M0 修正 V3（F2）：先讀回確認真的是 autocommit，才執行身分查詢；setter 失敗或靜默無效，就不查詢。
        if raw.autocommit is not True:
            failure = 'connection_state_unconfirmed'
        else:
            with closing(raw.cursor()) as cursor:
                cursor.execute(IDENTITY_SQL)
                row = cursor.fetchone()
    except Exception:
        failure = failure or 'identity_unavailable'
    # M0 修正 F2：一定要把交易模式還原成原狀，並讀回確認；做不到就視為驗證失敗，
    # 呼叫端（GuardedPostgresDatabase._open）會關閉這條連線，絕不放回 pool 或交給業務交易。
    try:
        raw.autocommit = previous
        restored = raw.autocommit == previous
    except Exception:
        restored = False
    if not restored:
        raise DeploymentProfileError('connection_state_unrestorable')
    if failure:
        raise DeploymentProfileError(failure)
    if row is None or len(row) != 6:
        raise DeploymentProfileError('identity_unavailable')
    database, user, session_user, schema, version, marker = (None if value is None else str(value) for value in row)
    if database in REFUSED_DATABASES:
        raise DeploymentProfileError(REFUSED_DATABASES[database])
    if database != profile.database:
        raise DeploymentProfileError('database_mismatch')
    if user != profile.user or session_user != profile.user:
        raise DeploymentProfileError('user_mismatch')
    if schema != profile.schema:
        raise DeploymentProfileError('schema_mismatch')
    if version != profile.server_version_num:
        raise DeploymentProfileError('server_version_mismatch')
    if marker != profile.marker:
        raise DeploymentProfileError('marker_mismatch')


def open_guarded_database(settings, profile, connector_factory=None):
    """建立受核對的 PostgreSQL 資料庫物件，並在啟動時先完成一次實際連線的核對。"""
    check_settings(settings, profile)
    from .postgres import ConnectionStateError, PostgresDatabase

    class GuardedPostgresDatabase(PostgresDatabase):
        """每一條新的實體連線都先核對身分；不符就關閉連線，絕不交給程式使用。"""
        deployment_profile = profile

        def _open(self):
            try:
                raw = super()._open()  # 基底已在第一個 SQL 之前確認 autocommit；失敗時已關閉連線
            except ConnectionStateError as exc:
                raise DeploymentProfileError('connection_state_' + exc.code) from None
            try:
                verify_identity(raw, profile)
                # 原有的 _open 交出的連線一定是 autocommit=False（寫入交易與 owner 鎖依賴它）；不是就不交出去。
                if raw.autocommit is not False:
                    raise DeploymentProfileError('connection_state_unrestorable')
            except BaseException:
                try:
                    raw.close()
                except Exception:
                    pass
                raise
            return raw

    database = GuardedPostgresDatabase(settings, connector_factory=connector_factory)
    try:
        raw = database._open()
    except DeploymentProfileError:
        database.close()
        raise
    except Exception:
        database.close()
        raise DeploymentProfileError('connection_failed') from None
    database._available.put(raw)  # 已核對的連線放回 pool，供第一個請求使用
    return database
