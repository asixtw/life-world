from functools import partial
from dataclasses import replace
import os
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient as HTTPClient
from app.main import create_app
from app.runtime import RuntimeSettings
TestClient = partial(HTTPClient, client=('127.0.0.1', 50000))

@pytest.fixture
def app(tmp_path):
    # 模組覆寫fixture仍須遵守合成PG路由，不能默默回退SQLite。
    database = None
    settings = RuntimeSettings()
    if os.environ.get('LIFEWORLD_TEST_BACKEND') == 'postgresql':
        from pg_support import database as pg_database
        database = pg_database()
        settings = database.settings
    settings = replace(settings, auth_rate_enabled=True,
        auth_rate_secret='synthetic-only-key-' * 3, auth_source_mode='direct')
    return create_app(tmp_path, database=database, settings=settings,
        clock=lambda: datetime(2026,10,27,7,tzinfo=timezone.utc))

@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c
from conftest import onboard, register


def test_failed_logins_are_limited(client):
    onboard(client)
    register(client)
    assert client.post('/api/auth/logout').status_code == 204

    wrong = {
        'username': 'lumi_user',
        'password': 'wrong-password'
    }
    for _ in range(5):
        assert client.post('/api/auth/login', json=wrong).status_code == 401

    blocked = client.post('/api/auth/login', json=wrong)
    assert blocked.status_code == 429
    assert int(blocked.headers['Retry-After']) > 0


def test_new_guest_creation_is_limited(app):
    # 同一服務生命週期、獨立訪客cookie；不得重用已關閉的PG連線池。
    with TestClient(app):
        for _ in range(10):
            with TestClient(app) as visitor:
                assert visitor.post('/api/auth/guest').status_code == 201

        with TestClient(app) as visitor:
            blocked = visitor.post('/api/auth/guest')

        assert blocked.status_code == 429
        assert int(blocked.headers['Retry-After']) > 0
