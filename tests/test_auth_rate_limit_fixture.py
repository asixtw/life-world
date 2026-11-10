"""僅驗fixture路由契約：PG為合成替身，不連PostgreSQL或網路。"""
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.runtime import RuntimeSettings
import test_auth_rate_limit as target


def test_pg_route_injects_database_and_preserves_pg_settings(monkeypatch, tmp_path):
    settings = RuntimeSettings(backend='postgresql', db_host='127.0.0.1', db_port=55432,
        db_password='synthetic-only', pool_size=3, pg_tls='disable')
    database = SimpleNamespace(backend='postgresql', settings=settings)
    factory = Mock(return_value=database)
    monkeypatch.setitem(sys.modules, 'pg_support', SimpleNamespace(database=factory))
    monkeypatch.setenv('LIFEWORLD_TEST_BACKEND', 'postgresql')
    captured = {}
    def create_app(*args, **kwargs):
        captured.update(kwargs)
        assert kwargs.get('database') is database, 'PG fixture must inject its actual database'
        assert kwargs['settings'].backend == 'postgresql', 'No SQLite fallback'
        return SimpleNamespace(state=SimpleNamespace(service=SimpleNamespace(db=database)))
    monkeypatch.setattr(target, 'create_app', create_app)
    result = target.app.__wrapped__(tmp_path)
    factory.assert_called_once_with()
    assert result.state.service.db is database
    actual = captured['settings']
    from dataclasses import replace
    assert actual == replace(settings, auth_rate_enabled=True,
        auth_rate_secret='synthetic-only-key-' * 3, auth_source_mode='direct')
    assert settings.auth_rate_enabled is False  # 不改動原始連線設定物件。


def test_pg_initialization_failure_never_falls_back(monkeypatch, tmp_path):
    failure = RuntimeError('synthetic PG unavailable')
    factory = Mock(side_effect=failure)
    monkeypatch.setitem(sys.modules, 'pg_support', SimpleNamespace(database=factory))
    monkeypatch.setenv('LIFEWORLD_TEST_BACKEND', 'postgresql')
    create = Mock()
    monkeypatch.setattr(target, 'create_app', create)
    with pytest.raises(RuntimeError, match='^synthetic PG unavailable$') as caught:
        target.app.__wrapped__(tmp_path)
    assert caught.value is failure
    factory.assert_called_once_with()
    create.assert_not_called()


@pytest.mark.parametrize('backend', [None, 'sqlite'])
def test_sqlite_route_does_not_initialize_pg(monkeypatch, tmp_path, backend):
    if backend is None:
        monkeypatch.delenv('LIFEWORLD_TEST_BACKEND', raising=False)
    else:
        monkeypatch.setenv('LIFEWORLD_TEST_BACKEND', backend)
    factory = Mock(side_effect=AssertionError('PG must not be initialized'))
    monkeypatch.setitem(sys.modules, 'pg_support', SimpleNamespace(database=factory))
    create = Mock(return_value=object())
    monkeypatch.setattr(target, 'create_app', create)
    assert target.app.__wrapped__(tmp_path) is create.return_value
    factory.assert_not_called()
    args, kwargs = create.call_args
    assert args == (tmp_path,)
    assert kwargs.get('database') is None
    assert kwargs['settings'].backend == 'sqlite'
    assert kwargs['settings'].auth_rate_enabled is True
    assert kwargs['settings'].auth_source_mode == 'direct'
    assert kwargs['settings'].auth_rate_secret == 'synthetic-only-key-' * 3


def test_guest_rate_limit_journey_keeps_one_service_lifespan(monkeypatch):
    """受控生命週期替身：最後client退出時模擬關閉PG連線池。"""
    state = SimpleNamespace(active=0, closed=False, close_count=0, requests=0,
                            entered=[], request_clients=[], max_active=0)
    service = object()
    class Client:
        def __init__(self, app):
            assert app is service
            self.cookies = {}  # 每個訪客從獨立cookie jar開始。
            self.requested = False
        def __enter__(self):
            if state.closed:
                raise RuntimeError('synthetic pool already closed before next visitor')
            state.active += 1
            state.max_active = max(state.max_active, state.active)
            state.entered.append(self)
            return self
        def __exit__(self, *args):
            state.active -= 1
            if state.active == 0:
                state.closed = True
                state.close_count += 1
        def post(self, path):
            assert path == '/api/auth/guest'
            assert not state.closed and state.active > 0
            assert not self.requested and not self.cookies
            self.requested = True
            state.requests += 1
            state.request_clients.append(self)
            self.cookies['session'] = 'synthetic-' + str(state.requests)
            return SimpleNamespace(status_code=201 if state.requests <= 10 else 429,
                                   headers={'Retry-After': '60'})
    monkeypatch.setattr(target, 'TestClient', Client)
    target.test_new_guest_creation_is_limited(service)
    assert state.requests == 11
    assert len(state.entered) == 12  # 一個閒置生命週期anchor加十一個獨立訪客。
    assert len({id(client.cookies) for client in state.request_clients}) == 11
    assert state.max_active == 2
    assert state.active == 0 and state.closed and state.close_count == 1
