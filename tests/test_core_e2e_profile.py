"""M0：8030 整合版連 Cloud SQL E2E 的啟動驗證（替身連線；不連任何真實資料庫、不取 ADC）。"""
import os

import pytest
from fastapi.testclient import TestClient

from app import deployment_profile as dp
from app.errors import DomainError
from app.main import create_app
from app.postgres import PostgresDatabase
from app.runtime import RuntimeSettings

GOOD_ENV = {
    'LIFEWORLD_DEPLOYMENT_PROFILE': 'core-e2e',
    'LIFEWORLD_DB_BACKEND': 'postgresql',
    'LIFEWORLD_DB_NAME': 'life_world_e2e',
    'LIFEWORLD_DB_USER': 'lw_e2e_app',
    'LIFEWORLD_DB_SCHEMA': 'lw_core_draft',
    'LIFEWORLD_PG_CONNECTION': 'cloud_sql',
    'LIFEWORLD_INSTANCE_CONNECTION_NAME': 'life-world-513506:asia-east1:lw-pg-staging-trial',
    'LIFEWORLD_EXPECTED_DB_MARKER': 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1',
    'LIFEWORLD_DB_PASSWORD': 'synthetic-test-password',
}
GOOD_IDENTITY = {'database': 'life_world_e2e', 'user': 'lw_e2e_app', 'session_user': 'lw_e2e_app',
                 'schema': 'lw_core_draft', 'version': '180006', 'marker': 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1'}


class FakeCursor:
    def __init__(self, raw):
        self.raw, self.rows = raw, []

    def execute(self, statement, parameters=()):
        self.raw.statements.append(statement)
        if self.raw.fail_identity and 'current_database()' in statement:
            raise RuntimeError('synthetic identity failure')
        if statement.startswith('SHOW server_version_num'):
            self.rows = [(self.raw.identity['version'],)]
        elif 'current_database()' in statement:
            keys = ('database', 'user', 'session_user', 'schema', 'version', 'marker')
            self.rows = [] if self.raw.no_identity else [tuple(self.raw.identity[k] for k in keys)]
        else:
            self.rows = []

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)

    @property
    def description(self):
        return None

    def close(self):
        pass


class FakeRaw:
    def __init__(self, identity=None, fail_identity=False, no_identity=False):
        self.identity = dict(GOOD_IDENTITY, **(identity or {}))
        self.fail_identity, self.no_identity = fail_identity, no_identity
        self.statements, self.autocommit, self.closed = [], False, False
        # M0 修正 V5（F2）：與 pg8000 1.31.6 相同，明確提供 bool 的交易狀態（沒有這個屬性的連線會被拒絕）。
        self._in_transaction = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class FakeConnector:
    """模擬 Cloud SQL Connector：每次 connect 依序取出下一個替身連線。"""

    def __init__(self, raws):
        self.raws, self.calls = list(raws), []

    def __call__(self, **kwargs):
        self.factory_kwargs = kwargs
        return self

    def connect(self, instance, driver, **kwargs):
        self.calls.append((instance, driver, kwargs.get('user'), kwargs.get('db')))
        item = self.raws.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        pass


@pytest.fixture(autouse=True)
def isolated_host(monkeypatch, tmp_path):
    """測試不受本機狀態影響：映像標記與 gcloud ADC 檔都指向不存在的暫存位置，個別測試再明確建立。"""
    monkeypatch.setattr(dp, 'IMAGE_MARKER_PATH', str(tmp_path / 'no-marker' / 'deployment-profile'))
    monkeypatch.setattr(dp, 'ADC_WELL_KNOWN_FILES', (str(tmp_path / 'no-adc' / 'application_default_credentials.json'),))


def write_marker(tmp_path, monkeypatch, content='core-e2e\n'):
    marker = tmp_path / 'image' / 'deployment-profile'
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(content, encoding='ascii')
    monkeypatch.setattr(dp, 'IMAGE_MARKER_PATH', str(marker))
    return marker


@pytest.fixture
def clean_env(monkeypatch):
    for key in list(os.environ):
        upper = key.upper()
        # M0 修正 V3：審查或開發環境本身的 ADC 覆寫（例如 CLOUDSDK_CONFIG）與代理設定，不應讓測試因 guard 正確拒絕而假失敗。
        if (key.startswith('LIFEWORLD_') or key == 'K_SERVICE' or upper in dp.ADC_OVERRIDE_NAMES + dp.PROXY_NAMES
                or upper.startswith(dp.ADC_OVERRIDE_PREFIXES)):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch


def set_env(monkeypatch, **overrides):
    env = dict(GOOD_ENV, **overrides)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    return env


def good_settings():
    return RuntimeSettings(backend='postgresql', connection_mode='cloud_sql', db_name='life_world_e2e',
                           db_user='lw_e2e_app', db_schema='lw_core_draft', db_password='synthetic-test-password',
                           instance_connection_name='life-world-513506:asia-east1:lw-pg-staging-trial')


# ---------- 建連前（preflight） ----------

def test_without_profile_original_behaviour_is_unchanged():
    assert dp.preflight({}) is None
    assert dp.preflight({'LIFEWORLD_DB_BACKEND': 'sqlite'}) is None


def test_correct_e2e_settings_pass_preflight():
    assert dp.preflight(dict(GOOD_ENV)) is dp.CORE_E2E


def test_unknown_profile_is_refused():
    with pytest.raises(dp.DeploymentProfileError, match='unknown_deployment_profile'):
        dp.preflight(dict(GOOD_ENV, LIFEWORLD_DEPLOYMENT_PROFILE='core-e2E'))


@pytest.mark.parametrize('key', [k for k, _ in dp.CORE_E2E.required_env] + ['LIFEWORLD_DB_PASSWORD'])
def test_each_required_setting_must_be_explicit(key):
    env = dict(GOOD_ENV)
    env.pop(key)
    with pytest.raises(dp.DeploymentProfileError, match='missing_required_setting: ' + key):
        dp.preflight(env)
    env[key] = ''
    with pytest.raises(dp.DeploymentProfileError, match='missing_required_setting'):
        dp.preflight(env)


@pytest.mark.parametrize('key,value,code', [
    ('LIFEWORLD_DB_NAME', 'life_world_e2e_copy', 'setting_mismatch: LIFEWORLD_DB_NAME'),
    ('LIFEWORLD_DB_NAME', 'life_world_dev', 'production_database_refused'),
    ('LIFEWORLD_DB_NAME', 'life_world_alpha', 'alpha_database_refused'),
    ('LIFEWORLD_DB_NAME', 'life_world_product_staging', 'product_staging_database_refused'),
    ('LIFEWORLD_DB_USER', 'lw_other_app', 'setting_mismatch: LIFEWORLD_DB_USER'),
    ('LIFEWORLD_DB_USER', 'lw_app', 'production_user_refused'),
    ('LIFEWORLD_DB_USER', 'lw_alpha_app', 'alpha_user_refused'),
    ('LIFEWORLD_DB_SCHEMA', 'public', 'setting_mismatch: LIFEWORLD_DB_SCHEMA'),
    ('LIFEWORLD_DB_BACKEND', 'sqlite', 'sqlite_refused'),
    ('LIFEWORLD_PG_CONNECTION', 'tcp', 'setting_mismatch: LIFEWORLD_PG_CONNECTION'),
    ('LIFEWORLD_INSTANCE_CONNECTION_NAME', 'life-world-513506:asia-east1:other', 'setting_mismatch'),
    ('LIFEWORLD_EXPECTED_DB_MARKER', 'OTHER_MARKER', 'setting_mismatch: LIFEWORLD_EXPECTED_DB_MARKER'),
])
def test_wrong_settings_are_refused(key, value, code):
    with pytest.raises(dp.DeploymentProfileError, match=code):
        dp.preflight(dict(GOOD_ENV, **{key: value}))


def test_production_and_alpha_full_configurations_are_refused():
    production = dict(GOOD_ENV, LIFEWORLD_DB_NAME='life_world_dev', LIFEWORLD_DB_USER='lw_app')
    alpha = dict(GOOD_ENV, LIFEWORLD_DB_NAME='life_world_alpha', LIFEWORLD_DB_USER='lw_alpha_app')
    with pytest.raises(dp.DeploymentProfileError, match='production_database_refused'):
        dp.preflight(production)
    with pytest.raises(dp.DeploymentProfileError, match='alpha_database_refused'):
        dp.preflight(alpha)


def test_injected_database_or_settings_are_refused():
    with pytest.raises(dp.DeploymentProfileError, match='injected_dependency_refused'):
        dp.preflight(dict(GOOD_ENV), database=object())
    with pytest.raises(dp.DeploymentProfileError, match='injected_dependency_refused'):
        dp.preflight(dict(GOOD_ENV), settings=good_settings())


# 2026-11-10：AI（Gemini）與 Google 登入已在 8030 開放，改由下方 test_ai_and_google_settings_are_allowed 確認不再拒絕。
@pytest.mark.parametrize('key,value', [
    ('LIFEWORLD_TASKS_QUEUE', 'projects/p/locations/l/queues/q'),
    ('LIFEWORLD_ENVIRONMENT_ID', 'alpha'),  # 2026-11-10 P1：只接受 e2e（8445 已驗證的那組排程設定）
    ('LIFEWORLD_TASKS_WORKER_URL', 'https://lw-api-main-u5py2jttpa-de.a.run.app/internal/roleplay/tasks'),  # 正式網址不可當 Worker
    ('LIFEWORLD_TASKS_UNKNOWN', 'x'),
    ('LIFEWORLD_TEST_ACCOUNT_SEED', '{}'),
    ('LIFEWORLD_TEST_LOGIN_USERNAMES', 'tester'),
    ('LIFEWORLD_RELATIONSHIP_MEMORY_ENABLED', 'true'),
    ('LIFEWORLD_AUTH_RATE_ENABLED', 'true'),
    ('LIFEWORLD_PUBLIC_GATE_CLOSED', 'true'),
    ('LIFEWORLD_ACCESS_MODE', 'public_alpha'),
])
def test_features_not_open_in_m0_are_refused(key, value):
    with pytest.raises(dp.DeploymentProfileError, match='feature_not_open_in_m0: ' + key):
        dp.preflight(dict(GOOD_ENV, **{key: value}))


@pytest.mark.parametrize('key,value', [
    ('LIFEWORLD_AI_PROVIDER', 'gemini'),
    ('LIFEWORLD_AI_CALLS_APPROVED', 'true'),
    ('LIFEWORLD_AI_API_KEY', 'synthetic'),
    ('LIFEWORLD_GOOGLE_CLIENT_ID', 'x.apps.googleusercontent.com'),
])
def test_ai_and_google_settings_are_allowed(key, value):
    assert dp.preflight(dict(GOOD_ENV, **{key: value})) is dp.CORE_E2E


def test_explicitly_disabled_features_are_allowed():
    env = dict(GOOD_ENV, LIFEWORLD_RELATIONSHIP_MEMORY_ENABLED='false', LIFEWORLD_AUTH_RATE_ENABLED='false',
               LIFEWORLD_ACCESS_MODE='legacy')
    assert dp.preflight(env) is dp.CORE_E2E


def test_parsed_settings_are_checked_again():
    dp.check_settings(good_settings(), dp.CORE_E2E)
    from dataclasses import replace
    with pytest.raises(dp.DeploymentProfileError, match='setting_mismatch: db_name'):
        dp.check_settings(replace(good_settings(), db_name='life_world_dev'), dp.CORE_E2E)
    with pytest.raises(dp.DeploymentProfileError, match='setting_mismatch: backend'):
        dp.check_settings(replace(good_settings(), backend='sqlite'), dp.CORE_E2E)


# ---------- 建連後（實際連線的身分） ----------

def test_correct_identity_passes_and_leaves_no_open_transaction():
    raw = FakeRaw()
    dp.verify_identity(raw, dp.CORE_E2E)
    assert raw.autocommit is False  # 還原原本的交易模式


@pytest.mark.parametrize('identity,code', [
    ({'database': 'life_world_other'}, 'database_mismatch'),
    ({'database': 'life_world_dev'}, 'production_database_refused'),
    ({'database': 'life_world_alpha'}, 'alpha_database_refused'),
    ({'user': 'lw_app'}, 'user_mismatch'),
    ({'session_user': 'postgres'}, 'user_mismatch'),
    ({'schema': 'pg_catalog'}, 'schema_mismatch'),  # Schema 不存在時，current_schema() 會落到下一個
    ({'version': '180007'}, 'server_version_mismatch'),
    ({'version': '170004'}, 'server_version_mismatch'),
    ({'marker': 'OTHER_MARKER'}, 'marker_mismatch'),
    ({'marker': None}, 'marker_mismatch'),
])
def test_wrong_identity_is_refused(identity, code):
    with pytest.raises(dp.DeploymentProfileError, match=code):
        dp.verify_identity(FakeRaw(identity=identity), dp.CORE_E2E)


def test_identity_unavailable_is_refused():
    with pytest.raises(dp.DeploymentProfileError, match='identity_unavailable'):
        dp.verify_identity(FakeRaw(fail_identity=True), dp.CORE_E2E)
    with pytest.raises(dp.DeploymentProfileError, match='identity_unavailable'):
        dp.verify_identity(FakeRaw(no_identity=True), dp.CORE_E2E)


def test_guarded_database_checks_identity_through_the_real_open_path():
    raw = FakeRaw()
    connector = FakeConnector([raw])
    database = dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=connector)
    assert connector.factory_kwargs['ip_type'] == 'private'  # 只走私網，不退回 TCP
    assert connector.calls == [('life-world-513506:asia-east1:lw-pg-staging-trial', 'pg8000', 'lw_e2e_app', 'life_world_e2e')]
    assert any('current_database()' in s for s in raw.statements)
    assert not raw.closed
    database.close()


def test_connection_failure_refuses_startup():
    connector = FakeConnector([RuntimeError('synthetic network failure with secret detail')])
    with pytest.raises(dp.DeploymentProfileError, match='connection_failed') as caught:
        dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=connector)
    assert 'secret' not in str(caught.value)


def test_postgres_17_is_refused():
    connector = FakeConnector([FakeRaw(identity={'version': '170004'})])
    with pytest.raises(dp.DeploymentProfileError, match='connection_failed'):
        dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=connector)


def test_identity_mismatch_at_startup_closes_the_connection():
    raw = FakeRaw(identity={'database': 'life_world_dev'})
    with pytest.raises(dp.DeploymentProfileError, match='production_database_refused'):
        dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=FakeConnector([raw]))
    assert raw.closed


def test_reconnect_with_wrong_identity_fails_closed():
    good, wrong = FakeRaw(), FakeRaw(identity={'marker': 'OTHER_MARKER'})
    database = dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=FakeConnector([good, wrong]))
    database._available.get_nowait()  # 模擬 pool 中的連線已失效，下一個請求要建立新連線
    with pytest.raises(DomainError) as caught:
        with database.connect():
            pass
    assert caught.value.status == 503
    assert wrong.closed
    database.close()


# ---------- create_app 的實際啟動順序 ----------

def test_create_app_starts_with_e2e_profile_and_keeps_all_routes(clean_env, tmp_path):
    baseline = {(route.path, tuple(sorted(getattr(route, 'methods', None) or ()))) for route in create_app(data_dir=tmp_path / 'sqlite').routes}
    set_env(clean_env, LIFEWORLD_DATA_DIR=str(tmp_path / 'profile'))
    opened = []

    def fake_open(self):
        raw = FakeRaw()
        opened.append(raw)
        return raw

    clean_env.setattr(PostgresDatabase, '_open', fake_open)
    app = create_app()
    assert app.state.service.db.backend == 'postgresql'
    assert app.state.service.db.deployment_profile is dp.CORE_E2E
    routes = {(route.path, tuple(sorted(getattr(route, 'methods', None) or ()))) for route in app.routes}
    assert routes == baseline  # 沒有移除、也沒有新增任何路由
    assert opened and any('current_database()' in s for s in opened[0].statements)
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/api/capabilities').json().get('relationship_memory_available') is False
    assert not list((tmp_path / 'profile').rglob('*'))  # 部署設定檔下沒有建立任何資料目錄或 SQLite 檔案


@pytest.mark.parametrize('identity,code', [
    ({'database': 'life_world_dev'}, 'production_database_refused'),
    ({'user': 'lw_other'}, 'user_mismatch'),
    ({'schema': 'public'}, 'schema_mismatch'),
    ({'version': '180007'}, 'server_version_mismatch'),
    ({'marker': 'OTHER'}, 'marker_mismatch'),
])
def test_create_app_refuses_to_start_on_wrong_identity(clean_env, tmp_path, identity, code):
    set_env(clean_env, LIFEWORLD_DATA_DIR=str(tmp_path))
    clean_env.setattr(PostgresDatabase, '_open', lambda self: FakeRaw(identity=identity))
    with pytest.raises(dp.DeploymentProfileError, match=code):
        create_app()
    assert not list(tmp_path.rglob('*.sqlite*'))


def test_create_app_refuses_to_start_when_connection_fails(clean_env, tmp_path):
    set_env(clean_env, LIFEWORLD_DATA_DIR=str(tmp_path))

    def broken(self):
        raise OSError('synthetic connection reset')

    clean_env.setattr(PostgresDatabase, '_open', broken)
    with pytest.raises(dp.DeploymentProfileError, match='connection_failed'):
        create_app()
    assert not list(tmp_path.rglob('*.sqlite*'))


@pytest.mark.parametrize('overrides,code', [
    ({'LIFEWORLD_DB_NAME': None}, 'missing_required_setting'),
    ({'LIFEWORLD_DB_BACKEND': 'sqlite'}, 'sqlite_refused'),
    ({'LIFEWORLD_DB_NAME': 'life_world_dev', 'LIFEWORLD_DB_USER': 'lw_app'}, 'production_database_refused'),
    ({'LIFEWORLD_DB_NAME': 'life_world_alpha', 'LIFEWORLD_DB_USER': 'lw_alpha_app'}, 'alpha_database_refused'),
    ({'LIFEWORLD_TASKS_QUEUE': 'projects/p/locations/l/queues/q'}, 'feature_not_open_in_m0'),
])
def test_create_app_refuses_before_any_database_object(clean_env, tmp_path, overrides, code):
    set_env(clean_env, LIFEWORLD_DATA_DIR=str(tmp_path), **overrides)

    def must_not_connect(self):
        raise AssertionError('preflight must refuse before any connection')

    clean_env.setattr(PostgresDatabase, '_open', must_not_connect)
    with pytest.raises(dp.DeploymentProfileError, match=code):
        create_app()
    assert not list(tmp_path.rglob('*.sqlite*'))


def test_create_app_refuses_injected_database_under_profile(clean_env, tmp_path):
    set_env(clean_env)
    with pytest.raises(dp.DeploymentProfileError, match='injected_dependency_refused'):
        create_app(data_dir=tmp_path, database=PostgresDatabase(good_settings()))


def test_create_app_without_profile_still_uses_original_defaults(clean_env, tmp_path):
    app = create_app(data_dir=tmp_path)
    assert app.state.service.db.backend == 'sqlite'
    assert not hasattr(app.state.service.db, 'deployment_profile')


# ---------- M0 修正 F1：專用映像的標記不能被環境變數降級 ----------

def test_marker_forces_profile_even_when_variable_is_not_set(tmp_path, monkeypatch):
    write_marker(tmp_path, monkeypatch)
    env = dict(GOOD_ENV)
    env.pop('LIFEWORLD_DEPLOYMENT_PROFILE')
    assert dp.preflight(env) is dp.CORE_E2E


@pytest.mark.parametrize('value', ['', 'other', 'core-e2E', ' core-e2e'])
def test_marker_with_empty_or_conflicting_variable_is_refused(tmp_path, monkeypatch, value):
    write_marker(tmp_path, monkeypatch)
    with pytest.raises(dp.DeploymentProfileError, match='deployment_profile_conflict'):
        dp.preflight(dict(GOOD_ENV, LIFEWORLD_DEPLOYMENT_PROFILE=value))


def test_marker_with_matching_variable_is_accepted(tmp_path, monkeypatch):
    write_marker(tmp_path, monkeypatch)
    assert dp.preflight(dict(GOOD_ENV)) is dp.CORE_E2E


@pytest.mark.parametrize('content,code', [('unknown\n', 'image_marker_invalid'), ('', 'image_marker_invalid')])
def test_invalid_marker_content_is_refused(tmp_path, monkeypatch, content, code):
    write_marker(tmp_path, monkeypatch, content)
    with pytest.raises(dp.DeploymentProfileError, match=code):
        dp.preflight(dict(GOOD_ENV))


def test_marker_that_is_not_a_regular_file_is_refused(tmp_path, monkeypatch):
    directory = tmp_path / 'image-dir'
    directory.mkdir()
    monkeypatch.setattr(dp, 'IMAGE_MARKER_PATH', str(directory))
    with pytest.raises(dp.DeploymentProfileError, match='image_marker_untrusted'):
        dp.preflight(dict(GOOD_ENV))


def test_marker_with_injected_database_is_refused(tmp_path, monkeypatch):
    write_marker(tmp_path, monkeypatch)
    env = dict(GOOD_ENV)
    env.pop('LIFEWORLD_DEPLOYMENT_PROFILE')
    with pytest.raises(dp.DeploymentProfileError, match='injected_dependency_refused'):
        dp.preflight(env, database=object())


def must_not_connect(self):
    raise AssertionError('must refuse before any connection')


def test_cloud_run_empty_override_with_production_settings_cannot_start(clean_env, tmp_path):
    """Codex 重現的反例：專用映像，Cloud Run 把設定檔覆寫成空字串，並帶入正式庫的設定。"""
    write_marker(tmp_path, clean_env)
    set_env(clean_env, LIFEWORLD_DEPLOYMENT_PROFILE='', LIFEWORLD_DB_NAME='life_world_dev', LIFEWORLD_DB_USER='lw_app',
            LIFEWORLD_DATA_DIR=str(tmp_path / 'data'))
    clean_env.setattr(PostgresDatabase, '_open', must_not_connect)
    with pytest.raises(dp.DeploymentProfileError, match='deployment_profile_conflict'):
        create_app()
    assert not (tmp_path / 'data').exists()


def test_marker_without_variable_still_refuses_production_settings(clean_env, tmp_path):
    write_marker(tmp_path, clean_env)
    set_env(clean_env, LIFEWORLD_DEPLOYMENT_PROFILE=None, LIFEWORLD_DB_NAME='life_world_dev', LIFEWORLD_DB_USER='lw_app')
    clean_env.setattr(PostgresDatabase, '_open', must_not_connect)
    with pytest.raises(dp.DeploymentProfileError, match='production_database_refused'):
        create_app()


def test_marker_with_general_sqlite_defaults_cannot_start(clean_env, tmp_path):
    """專用映像中即使所有設定都被拿掉，也不會落到 SQLite 或正式庫的預設值。"""
    write_marker(tmp_path, clean_env)
    clean_env.setenv('LIFEWORLD_DATA_DIR', str(tmp_path / 'data'))
    with pytest.raises(dp.DeploymentProfileError, match='missing_required_setting'):
        create_app()
    assert not (tmp_path / 'data').exists()


def test_every_entry_point_goes_through_the_guard(clean_env, tmp_path):
    """app.serve、python -m app 與 uvicorn --factory 都以 'app.main:create_app' 作為 factory；三者都會先經過核對。"""
    import importlib
    from pathlib import Path
    import uvicorn
    from uvicorn.importer import import_from_string
    write_marker(tmp_path, clean_env)
    set_env(clean_env, LIFEWORLD_DEPLOYMENT_PROFILE='', LIFEWORLD_DATA_DIR=str(tmp_path / 'data'))
    clean_env.setattr(PostgresDatabase, '_open', must_not_connect)
    calls = []
    clean_env.setattr(uvicorn, 'run', lambda target, **kwargs: calls.append((target, kwargs)))
    importlib.import_module('app.serve').main()
    entry = (Path(__file__).resolve().parents[1] / 'app/__main__.py').read_text(encoding='utf-8')
    assert "uvicorn.run('app.main:create_app', factory=True" in entry  # python -m app 使用同一個 factory
    assert calls and calls[0][0] == 'app.main:create_app' and calls[0][1]['factory'] is True
    with pytest.raises(dp.DeploymentProfileError, match='deployment_profile_conflict'):
        import_from_string(calls[0][0])()  # uvicorn 以 --factory 載入時的行為
    assert not (tmp_path / 'data').exists()


def test_general_image_without_marker_keeps_original_behaviour(clean_env, tmp_path):
    clean_env.setenv('LIFEWORLD_DEPLOYMENT_PROFILE', '')
    app = create_app(data_dir=tmp_path)
    assert app.state.service.db.backend == 'sqlite'


# ---------- M0 修正 F2：交易模式無法還原的連線不能進 pool ----------

class StubbornRaw(FakeRaw):
    """讀回身分正確，但第 fail_on 次把交易模式設回 False 時失敗：mode='raise' 丟出 DBAPI 例外，mode='ignore' 靜默不生效。"""

    def __init__(self, mode='raise', fail_on=1, **kwargs):
        object.__setattr__(self, '_autocommit', False)
        object.__setattr__(self, 'mode', None)
        super().__init__(**kwargs)
        self._autocommit, self.fail_on, self.false_transitions = False, fail_on, 0
        self.mode = mode

    @property
    def autocommit(self):
        return self._autocommit

    @autocommit.setter
    def autocommit(self, value):
        if value is False and self._autocommit is True and self.mode:
            self.false_transitions += 1
            if self.false_transitions == self.fail_on:
                if self.mode == 'raise':
                    raise RuntimeError('synthetic driver failure')
                return
        self._autocommit = value


@pytest.mark.parametrize('mode', ['raise', 'ignore'])
def test_unrestorable_connection_state_fails_verification(mode):
    with pytest.raises(dp.DeploymentProfileError, match='connection_state_unrestorable'):
        dp.verify_identity(StubbornRaw(mode), dp.CORE_E2E)


@pytest.mark.parametrize('mode,fail_on', [('raise', 1), ('ignore', 1), ('raise', 2), ('ignore', 2)])
def test_unrestorable_connection_is_closed_and_never_pooled_at_startup(mode, fail_on):
    """fail_on=1：原有 _open 的設定就失敗；fail_on=2：身分核對之後的還原失敗。兩種都不得入池。"""
    raw = StubbornRaw(mode, fail_on)
    with pytest.raises(dp.DeploymentProfileError, match='connection_state_unrestorable|connection_failed'):
        dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=FakeConnector([raw]))
    assert raw.closed


def test_unrestorable_connection_is_closed_and_never_pooled_on_reconnect():
    good, stubborn = FakeRaw(), StubbornRaw('raise', 2)
    database = dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=FakeConnector([good, stubborn]))
    database._available.get_nowait()
    with pytest.raises(DomainError) as caught:
        with database.connect():
            pass
    assert caught.value.status == 503 and stubborn.closed
    assert database._available.empty()  # 沒有任何連線被放回 pool
    database.close()


# ---------- M0 修正 F3：只能使用 Cloud Run 綁定的 runtime service account ----------

@pytest.mark.parametrize('key', ['GOOGLE_APPLICATION_CREDENTIALS', 'GOOGLE_API_USE_CLIENT_CERTIFICATE', 'CLOUDSDK_CONFIG',
                                 'CLOUDSDK_AUTH_ACCESS_TOKEN_FILE', 'GCE_METADATA_HOST', 'GCE_METADATA_IP', 'GOOGLE_AUTH_TOKEN'])
def test_alternative_credential_sources_are_refused(key):
    with pytest.raises(dp.DeploymentProfileError, match='credential_override_refused: ' + key):
        dp.preflight(dict(GOOD_ENV, **{key: '/synthetic/path.json'}))


def test_mounted_well_known_adc_file_is_refused(tmp_path, monkeypatch):
    adc = tmp_path / 'gcloud' / 'application_default_credentials.json'
    adc.parent.mkdir()
    adc.write_text('{}', encoding='utf-8')  # 合成檔案；內容不會被讀取
    monkeypatch.setattr(dp, 'ADC_WELL_KNOWN_FILES', (str(adc),))
    with pytest.raises(dp.DeploymentProfileError, match='credential_file_refused'):
        dp.preflight(dict(GOOD_ENV))


def test_credential_variables_do_not_change_the_general_image():
    assert dp.preflight({'GOOGLE_APPLICATION_CREDENTIALS': '/synthetic/path.json'}) is None


def test_identity_query_qualifies_catalog_functions():
    for name in ('current_database()', 'current_schema()', 'current_setting(', 'shobj_description(', 'pg_database'):
        assert 'pg_catalog.' + name in dp.IDENTITY_SQL


# ---------- M0 修正 V3（F2）：沒有確認 autocommit=True，就不執行身分查詢 ----------

class AutocommitRaw(FakeRaw):
    """設定 autocommit=True 時：mode='ignore' 靜默不生效（讀回仍是 False），mode='raise' 丟出 DBAPI 例外。"""

    def __init__(self, mode, **kwargs):
        object.__setattr__(self, '_autocommit', False)
        object.__setattr__(self, 'mode', None)
        super().__init__(**kwargs)
        self._autocommit = False
        self.mode = mode

    @property
    def autocommit(self):
        return self._autocommit

    @autocommit.setter
    def autocommit(self, value):
        if value is True and self.mode == 'ignore':
            return
        if value is True and self.mode == 'raise':
            raise RuntimeError('synthetic driver failure')
        self._autocommit = value


def identity_queries(raw):
    return sum(1 for statement in raw.statements if statement == dp.IDENTITY_SQL)


@pytest.mark.parametrize('mode,code', [('ignore', 'connection_state_unconfirmed'), ('raise', 'identity_unavailable')])
def test_identity_query_never_runs_without_confirmed_autocommit(mode, code):
    raw = AutocommitRaw(mode)
    with pytest.raises(dp.DeploymentProfileError, match=code):
        dp.verify_identity(raw, dp.CORE_E2E)
    assert identity_queries(raw) == 0  # 查詢執行次數為 0


def test_silent_autocommit_failure_at_startup_closes_without_querying():
    raw = AutocommitRaw('ignore')
    with pytest.raises(dp.DeploymentProfileError, match='connection_state_unconfirmed'):
        dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=FakeConnector([raw]))
    assert raw.closed and identity_queries(raw) == 0


def test_silent_autocommit_failure_on_reconnect_closes_without_querying():
    good, bad = FakeRaw(), AutocommitRaw('ignore')
    database = dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=FakeConnector([good, bad]))
    database._available.get_nowait()
    with pytest.raises(DomainError) as caught:
        with database.connect():
            pass
    assert caught.value.status == 503 and bad.closed and identity_queries(bad) == 0
    assert database._available.empty()
    database.close()


# ---------- M0 修正 V4（F2）：基底 _open 在第一個 SQL 之前就確認 autocommit ----------

class TxCursor(FakeCursor):
    """以 pg8000 的方式模擬交易：非 autocommit 時執行任何 SQL 都會開啟交易（之後改 autocommit 也不會自動提交）。"""
    rowcount = -1

    def execute(self, statement, parameters=()):
        if not self.raw.autocommit:
            self.raw._in_transaction = True
        super().execute(statement, parameters)


class TxRaw(FakeRaw):
    """pg8000 型的替身：autocommit 設定可以指定「第 n 次設定 True 時靜默無效」，並維護 _in_transaction。"""

    def __init__(self, ignore_true_sets=(), in_transaction=False, **kwargs):
        object.__setattr__(self, '_autocommit', False)
        object.__setattr__(self, 'true_sets', 0)
        object.__setattr__(self, 'ignore_true_sets', tuple(ignore_true_sets))
        super().__init__(**kwargs)
        self._in_transaction = in_transaction

    @property
    def autocommit(self):
        return self._autocommit

    @autocommit.setter
    def autocommit(self, value):
        if value is True:
            object.__setattr__(self, 'true_sets', self.true_sets + 1)
            if self.true_sets in self.ignore_true_sets:
                return  # 靜默無效
        self._autocommit = value

    def cursor(self):
        return TxCursor(self)

    def commit(self):
        self._in_transaction = False

    def rollback(self):
        self._in_transaction = False


def test_first_autocommit_set_silently_ignored_then_working_runs_no_sql_in_base_open():
    """Codex 第三輪反例：第一次設定 True 靜默無效、第二次生效。原本基底先以交易模式送出 SHOW／SET，再由 Guard 讀回 True 而交出有交易的連線。"""
    raw = TxRaw(ignore_true_sets=(1,))
    database = PostgresDatabase(good_settings(), connector_factory=FakeConnector([raw]))
    with pytest.raises(DomainError) as caught:
        with database.connect():
            pass
    assert caught.value.status == 503
    assert raw.statements == [] and not raw._in_transaction and raw.closed  # 第一個初始化 SQL 也沒有執行
    assert database._available.empty()
    database.close()


def test_startup_refuses_first_silent_autocommit_failure_before_any_sql():
    raw = TxRaw(ignore_true_sets=(1,))
    with pytest.raises(dp.DeploymentProfileError, match='connection_state_unconfirmed'):
        dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=FakeConnector([raw]))
    assert raw.statements == [] and raw.closed and raw.true_sets == 1


def test_reconnect_after_pool_is_drained_refuses_first_silent_autocommit_failure():
    good, flaky = TxRaw(), TxRaw(ignore_true_sets=(1,))
    database = dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=FakeConnector([good, flaky]))
    database._available.get_nowait()  # pool 用盡：下一個請求會建立新的實體連線
    with pytest.raises(DomainError) as caught:
        with database.connect():
            pass
    assert caught.value.status == 503 and flaky.statements == [] and flaky.closed
    assert database._available.empty()
    database.close()


@pytest.mark.parametrize('case,code', [('transaction already open', 'connection_state_unconfirmed'),
                                       ('transaction left open by initialization', 'connection_state_unrestorable')])
def test_open_transaction_before_or_after_initialization_is_refused(case, code):
    if case == 'transaction already open':
        raw = TxRaw(in_transaction=True)
    else:
        raw = TxRaw()

        class LeakyCursor(TxCursor):
            def execute(self, statement, parameters=()):
                super().execute(statement, parameters)
                if statement.startswith('SET statement_timeout'):
                    self.raw._in_transaction = True  # 替身：驅動程式回報交易仍未結束
        raw.cursor = lambda: LeakyCursor(raw)
    with pytest.raises(dp.DeploymentProfileError, match=code):
        dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=FakeConnector([raw]))
    assert raw.closed and identity_queries(raw) == 0
    if case == 'transaction already open':
        assert raw.statements == []


def test_normal_connection_still_completes_initialization_and_identity():
    raw = TxRaw()
    database = dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=FakeConnector([raw]))
    assert raw.statements[:5] == ['SHOW server_version_num', "SELECT set_config('search_path', ?, false)", "SET TIME ZONE 'UTC'",
                                  "SET lock_timeout = '5s'", "SET statement_timeout = '15s'"]
    assert identity_queries(raw) == 1 and raw.autocommit is False and not raw._in_transaction and not raw.closed
    assert database._available.qsize() == 1
    with database.connect() as connection:  # 正常請求仍可使用
        assert connection is not None
    database.close()


# ---------- M0 修正 V3（F3）：代理設定與空值的 ADC 設定 ----------

@pytest.mark.parametrize('key', ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy', 'Https_Proxy',
                                 'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy'])
@pytest.mark.parametrize('value', ['http://proxy.synthetic.invalid:3128', ''])
def test_proxy_settings_are_refused_in_any_case_and_even_when_empty(key, value):
    with pytest.raises(dp.DeploymentProfileError, match='proxy_setting_refused: ' + key):
        dp.preflight(dict(GOOD_ENV, **{key: value}))


@pytest.mark.parametrize('key', ['GOOGLE_APPLICATION_CREDENTIALS', 'google_application_credentials', 'CLOUDSDK_CONFIG'])
def test_empty_adc_overrides_are_refused(key):
    with pytest.raises(dp.DeploymentProfileError, match='credential_override_refused: ' + key):
        dp.preflight(dict(GOOD_ENV, **{key: ''}))


def test_accepted_configuration_leaves_no_ambient_proxy_for_metadata(clean_env):
    """離線計算：guard 接受的設定之下，標準函式庫看不到任何代理，所以 metadata 請求不會被改路。不發出任何請求。"""
    import urllib.request
    for key in list(os.environ):
        if key.upper() in dp.PROXY_NAMES:
            clean_env.delenv(key, raising=False)
    set_env(clean_env)
    assert dp.preflight(dict(os.environ)) is dp.CORE_E2E
    proxies = urllib.request.getproxies_environment()
    assert proxies == {}
    assert not urllib.request.proxy_bypass_environment('169.254.169.254', proxies)
    clean_env.setenv('HTTP_PROXY', 'http://proxy.synthetic.invalid:3128')
    assert urllib.request.getproxies_environment().get('http')  # 反例：有代理時標準函式庫會採用它
    with pytest.raises(dp.DeploymentProfileError, match='proxy_setting_refused'):
        dp.preflight(dict(os.environ))  # 而 guard 會拒絕這個設定


# ---------- M0 修正 V5（F2）：交易狀態必須是驅動程式明確回報的 bool False ----------

def test_locked_pg8000_reports_a_real_bool_transaction_flag():
    """鎖定的 pg8000 1.31.6：_in_transaction 由 ReadyForQuery 的狀態計算，型別是 bool；不建立任何連線。"""
    pg8000 = pytest.importorskip('pg8000')
    from pg8000.core import IDLE, IN_FAILED_TRANSACTION, IN_TRANSACTION
    from pg8000.dbapi import Connection
    from app.postgres import _transaction_open
    lock = (dp.__file__.rsplit('app', 1)[0] + 'requirements.api.lock')
    assert 'pg8000==1.31.6' in open(lock, encoding='utf-8').read() and pg8000.__version__ == '1.31.6'
    connection = Connection.__new__(Connection)
    for status, opened in ((IDLE, False), (IN_TRANSACTION, True), (IN_FAILED_TRANSACTION, True)):
        connection._transaction_status = status
        assert type(connection._in_transaction) is bool
        assert _transaction_open(connection) is opened


class RaisingFlagRaw(FakeRaw):
    @property
    def _in_transaction(self):
        raise RuntimeError('synthetic unreadable state')

    @_in_transaction.setter
    def _in_transaction(self, value):
        pass


def raw_with_flag(case):
    if case == 'missing':
        raw = FakeRaw()
        del raw._in_transaction
        return raw
    if case == 'unreadable':
        return RaisingFlagRaw()
    raw = FakeRaw()
    raw._in_transaction = {'None': None, 'zero': 0, 'empty string': '', 'string False': 'False', 'one': 1}[case]
    return raw


FLAG_CASES = ['missing', 'unreadable', 'None', 'zero', 'empty string', 'string False', 'one']


@pytest.mark.parametrize('case', FLAG_CASES)
def test_startup_refuses_a_connection_without_a_bool_false_transaction_flag(case):
    raw = raw_with_flag(case)
    with pytest.raises(dp.DeploymentProfileError, match='connection_state_unconfirmed'):
        dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=FakeConnector([raw]))
    assert raw.statements == [] and raw.closed  # 第一個 SQL 之前就關閉


@pytest.mark.parametrize('case', FLAG_CASES)
def test_reconnect_refuses_a_connection_without_a_bool_false_transaction_flag(case):
    good, bad = FakeRaw(), raw_with_flag(case)
    database = dp.open_guarded_database(good_settings(), dp.CORE_E2E, connector_factory=FakeConnector([good, bad]))
    database._available.get_nowait()  # pool 用盡：下一個請求建立新連線
    with pytest.raises(DomainError) as caught:
        with database.connect():
            pass
    assert caught.value.status == 503 and bad.statements == [] and bad.closed
    assert database._available.empty()
    database.close()


@pytest.mark.parametrize('case', ['missing', 'None'])
def test_base_postgres_database_also_refuses_an_unknown_transaction_state(case):
    raw = raw_with_flag(case)
    database = PostgresDatabase(good_settings(), connector_factory=FakeConnector([raw]))
    with pytest.raises(DomainError) as caught:
        with database.connect():
            pass
    assert caught.value.status == 503 and raw.statements == [] and raw.closed and database._available.empty()
    database.close()


def test_e2e_task_settings_verified_by_8445_are_allowed():
    """P1 背景排程：只接受 lw-roleplay-e2e、e2e Tag 的 Worker 與 lw-api-runtime OIDC 這一組值。"""
    profile = dp.preflight({**GOOD_ENV, **dp.E2E_TASK_SETTINGS})
    assert profile is not None
    with pytest.raises(dp.DeploymentProfileError, match='feature_not_open_in_m0'):
        dp.preflight({**GOOD_ENV, **dp.E2E_TASK_SETTINGS, 'LIFEWORLD_TASKS_QUEUE': 'projects/life-world-513506/locations/asia-east1/queues/lw-roleplay-alpha'})

