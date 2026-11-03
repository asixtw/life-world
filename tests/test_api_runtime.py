"""部署入口必須可觀測、明確選擇 backend，且預設阻止雲端業務流量。"""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_process_and_database_health_have_separate_semantics(tmp_path):
    """程序健康不碰 DB；readiness 失敗只能回通用錯誤。"""
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        assert client.get('/health').json() == {'status': 'ok'}
        assert client.get('/ready').status_code == 200
        app.state.service.db.check_ready = lambda: (_ for _ in ()).throw(RuntimeError('private-dsn'))
        response = client.get('/ready')
        assert response.status_code == 503
        assert 'private-dsn' not in response.text
        assert client.get('/health').status_code == 200
        assert client.get('/api/health').status_code == 200


def test_unknown_backend_never_falls_back_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv('LIFEWORLD_DB_BACKEND', 'postgre_typo')
    with pytest.raises(ValueError, match='backend'):
        create_app(data_dir=tmp_path)
    assert not (tmp_path / 'lifeworld.sqlite3').exists()


def test_postgres_configuration_failure_never_creates_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv('LIFEWORLD_DB_BACKEND', 'postgresql')
    monkeypatch.delenv('LIFEWORLD_DB_PASSWORD', raising=False)
    with pytest.raises(ValueError, match='PostgreSQL'):
        create_app(data_dir=tmp_path)
    assert not (tmp_path / 'lifeworld.sqlite3').exists()


def test_cloud_runtime_is_fail_closed_and_hosts_are_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv('K_SERVICE', 'lw-api-main')
    monkeypatch.setenv('LIFEWORLD_TRUSTED_HOSTS', 'testserver,api.example.test')
    monkeypatch.setenv('LIFEWORLD_DB_BACKEND', 'postgresql')
    monkeypatch.setenv('LIFEWORLD_DB_PASSWORD', 'synthetic-local-only')
    with TestClient(create_app(data_dir=tmp_path)) as client:
        assert client.get('/health').status_code == 200
        assert client.post('/api/auth/guest').status_code == 503
        assert client.get('/api/state').status_code == 503
        assert client.get('/health', headers={'host': 'evil.test'}).status_code == 400


def test_wildcard_hosts_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv('LIFEWORLD_TRUSTED_HOSTS', '*')
    with pytest.raises(ValueError, match='Host'):
        create_app(data_dir=tmp_path)


def test_cloud_requires_explicit_hosts(tmp_path, monkeypatch):
    monkeypatch.setenv('K_SERVICE', 'lw-api-main')
    monkeypatch.delenv('LIFEWORLD_TRUSTED_HOSTS', raising=False)
    with pytest.raises(ValueError, match='Host'):
        create_app(data_dir=tmp_path)


def test_cloud_never_uses_ephemeral_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv('K_SERVICE', 'lw-api-main')
    monkeypatch.setenv('LIFEWORLD_TRUSTED_HOSTS', 'testserver')
    with pytest.raises(ValueError, match='PostgreSQL'):
        create_app(data_dir=tmp_path)
