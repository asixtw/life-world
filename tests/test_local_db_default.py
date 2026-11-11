"""P0-8／P0-9：Local 8030 與 Cloud Run 一律用 Cloud SQL；伺服器模式不得因為沒設定就默默改用 SQLite 或正式庫。

SQLite 仍保留給「明確指定」的單元測試與獨立工具（程式內傳入 data_dir，或 LIFEWORLD_DB_BACKEND=sqlite）。
Local 8030 的部署設定檔（core-e2e）另有連線身分核對，見 tests/test_core_e2e_profile.py。
"""
import os

import pytest
from uvicorn.importer import import_from_string

from app.main import create_app
from app.runtime import RuntimeSettings


@pytest.fixture
def server_env(monkeypatch, tmp_path):
    """模擬乾淨的伺服器啟動環境：拿掉所有 LIFEWORLD_ 設定，只留資料目錄。"""
    for key in list(os.environ):
        if key.startswith('LIFEWORLD_') or key == 'K_SERVICE':
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('LIFEWORLD_DATA_DIR', str(tmp_path / 'data'))
    return monkeypatch


def test_server_mode_without_backend_refuses_instead_of_sqlite(server_env, tmp_path):
    with pytest.raises(ValueError, match='database_backend_required'):
        create_app()
    assert not (tmp_path / 'data').exists()  # 沒有建立資料目錄，也沒有 SQLite 檔


def test_uvicorn_factory_without_backend_refuses(server_env, tmp_path):
    """uvicorn --factory 與 python -m app 走同一個入口。"""
    with pytest.raises(ValueError, match='database_backend_required'):
        import_from_string('app.main:create_app')()
    assert not list(tmp_path.rglob('*.sqlite*'))


def test_empty_backend_is_not_a_choice(server_env, tmp_path):
    server_env.setenv('LIFEWORLD_DB_BACKEND', '')
    with pytest.raises(ValueError, match='database_backend_required'):
        create_app()
    assert not (tmp_path / 'data').exists()


def test_explicit_sqlite_is_still_available_for_isolated_tools(server_env, tmp_path):
    server_env.setenv('LIFEWORLD_DB_BACKEND', 'sqlite')
    app = create_app()
    assert app.state.service.db.backend == 'sqlite'
    assert (tmp_path / 'data' / 'lifeworld.sqlite3').exists()


def test_unit_tests_that_pass_data_dir_keep_sqlite(server_env, tmp_path):
    app = create_app(data_dir=tmp_path / 'unit')
    assert app.state.service.db.backend == 'sqlite'


@pytest.mark.parametrize('missing', ['LIFEWORLD_DB_NAME', 'LIFEWORLD_DB_USER'])
def test_postgres_requires_explicit_database_and_user(server_env, tmp_path, missing):
    """不再預設成正式庫 life_world_dev／lw_app；少一項就拒絕，也不會退回 SQLite。"""
    server_env.setenv('LIFEWORLD_DB_BACKEND', 'postgresql')
    server_env.setenv('LIFEWORLD_DB_PASSWORD', 'synthetic-local-only')
    server_env.setenv('LIFEWORLD_DB_NAME', 'life_world_e2e')
    server_env.setenv('LIFEWORLD_DB_USER', 'lw_e2e_app')
    server_env.delenv(missing)
    with pytest.raises(ValueError, match='Incomplete PostgreSQL configuration'):
        create_app()
    assert not (tmp_path / 'data').exists()


def test_postgres_settings_use_only_what_was_given(server_env):
    server_env.setenv('LIFEWORLD_DB_BACKEND', 'postgresql')
    server_env.setenv('LIFEWORLD_DB_PASSWORD', 'synthetic-local-only')
    server_env.setenv('LIFEWORLD_DB_NAME', 'life_world_e2e')
    server_env.setenv('LIFEWORLD_DB_USER', 'lw_e2e_app')
    settings = RuntimeSettings.from_env()
    assert (settings.backend, settings.db_name, settings.db_user, settings.db_schema) == ('postgresql', 'life_world_e2e', 'lw_e2e_app', 'lw_core_draft')


def test_closed_gate_has_no_production_default(server_env):
    server_env.setenv('LIFEWORLD_DB_BACKEND', 'postgresql')
    server_env.setenv('LIFEWORLD_PUBLIC_GATE_CLOSED', 'true')
    server_env.setenv('LIFEWORLD_ENABLE_BUSINESS_API', 'false')  # 關閉的公開 Gate 不開業務 API
    settings = RuntimeSettings.from_env()
    assert settings.db_name == '' and settings.db_user == ''  # 不會出現 life_world_dev／lw_app
