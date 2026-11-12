"""重現並防止清理例外耗盡連線池；所有 raw 都是 Mock。"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.errors import DomainError
from app.postgres import PostgresDatabase, driver


def database(pool_size=1):
    settings = SimpleNamespace(pool_size=pool_size, pool_timeout=.001,
                               db_schema="synthetic_pool_test")
    return PostgresDatabase(settings, connector_factory=Mock(
        side_effect=AssertionError("不得取得 Connector")))


def raw_connection(*, rollback_error=False, close_error=False):
    raw = Mock()
    raw.cursor.return_value = Mock(description=None, rowcount=-1)
    if rollback_error:
        raw.rollback.side_effect = RuntimeError("synthetic rollback failure")
    if close_error:
        raw.close.side_effect = RuntimeError("synthetic close failure")
    return raw


def assert_capacity(db, expected):
    count = 0
    try:
        while db._slots.acquire(blocking=False):
            count += 1
        assert count == expected, "cleanup error leaked a pool slot"
    finally:
        for _ in range(count):
            db._slots.release()


@pytest.mark.parametrize("pool_size", [1, 3])
def test_repeated_cleanup_failures_do_not_leak_or_reuse_bad_connections(monkeypatch, pool_size):
    db = database(pool_size)
    attempts = 3 * pool_size + 10
    broken = [raw_connection(rollback_error=True, close_error=True) for _ in range(attempts)]
    healthy = raw_connection()
    opening = Mock(side_effect=[*broken, healthy])
    monkeypatch.setattr(db, "_open", opening)
    for raw in broken:
        with pytest.raises(RuntimeError, match="synthetic close failure"):
            with db.connect():
                raise ValueError("synthetic transaction failure")
        raw.close.assert_called_once()
        assert db._available.empty()
        assert_capacity(db, pool_size)
    for _ in range(2):
        with db.connect() as connection:
            assert connection.raw is healthy
    assert opening.call_count == attempts + 1
    assert healthy.commit.call_count == 2
    assert_capacity(db, pool_size)
    db.close()


def test_shutdown_close_error_still_releases_slot(monkeypatch):
    db, raw = database(), raw_connection(close_error=True)
    monkeypatch.setattr(db, "_open", lambda: raw)
    with pytest.raises(RuntimeError, match="synthetic close failure"):
        with db.connect():
            db._closed = True
    assert db._available.empty()
    assert_capacity(db, 1)


def test_rollback_failure_and_successful_close_control(monkeypatch):
    db, raw = database(), raw_connection(rollback_error=True)
    monkeypatch.setattr(db, "_open", lambda: raw)
    with pytest.raises(ValueError, match="synthetic transaction failure"):
        with db.connect():
            raise ValueError("synthetic transaction failure")
    raw.close.assert_called_once()
    assert db._available.empty()
    assert_capacity(db, 1)


def test_open_failure_is_sanitized_and_releases_slot(monkeypatch):
    db = database()
    monkeypatch.setattr(db, "_open", Mock(side_effect=RuntimeError("synthetic provider detail")))
    with pytest.raises(DomainError) as exc:
        with db.connect():
            pytest.fail("failed open must not yield")
    assert exc.value.code == "database_unavailable"
    assert "provider detail" not in str(exc.value)
    assert db._available.empty()
    assert_capacity(db, 1)


def test_normal_write_uses_lock_commits_and_reuses_once(monkeypatch):
    db, raw = database(), raw_connection()
    opening = Mock(return_value=raw)
    monkeypatch.setattr(db, "_open", opening)
    with db.connect(write=True, owner="synthetic-owner") as connection:
        assert connection.raw is raw
    statements = [call.args[0] for call in raw.cursor.return_value.execute.call_args_list]
    assert statements == ["SET TRANSACTION ISOLATION LEVEL READ COMMITTED", "SELECT pg_advisory_xact_lock(?)"]
    with db.connect() as connection:
        assert connection.raw is raw
    assert opening.call_count == 1
    assert raw.commit.call_count == 2
    raw.close.assert_not_called()
    assert_capacity(db, 1)


def test_transaction_driver_error_translation_preserved(monkeypatch):
    db, raw = database(), raw_connection()
    monkeypatch.setattr(db, "_open", lambda: raw)
    with pytest.raises(DomainError) as exc:
        with db.connect():
            raise driver.Error({"C": "42501", "M": "synthetic server detail"})
    assert exc.value.code == "database_permission_unavailable"
    assert "server detail" not in str(exc.value)
    raw.rollback.assert_called_once()
    raw.close.assert_not_called()
    assert_capacity(db, 1)


def test_pool_exhaustion_does_not_overrelease(monkeypatch):
    db = database()
    opening = Mock(side_effect=AssertionError("pool exhausted must not open"))
    monkeypatch.setattr(db, "_open", opening)
    assert db._slots.acquire(blocking=False)
    try:
        with pytest.raises(DomainError) as exc:
            with db.connect():
                pytest.fail("exhausted pool must not yield")
        assert exc.value.code == "database_busy"
        assert_capacity(db, 0)
        opening.assert_not_called()
    finally:
        db._slots.release()
    assert_capacity(db, 1)


def test_closed_pool_preserves_capacity_without_open(monkeypatch):
    db = database()
    db._closed = True
    opening = Mock(side_effect=AssertionError("closed pool must not open"))
    monkeypatch.setattr(db, "_open", opening)
    with pytest.raises(DomainError) as exc:
        with db.connect():
            pytest.fail("closed pool must not yield")
    assert exc.value.code == "database_unavailable"
    opening.assert_not_called()
    assert_capacity(db, 1)
