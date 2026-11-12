"""只用合成連線驗證 shutdown 與尚未開啟的借用競態。"""
from threading import Event, Thread, local
from unittest.mock import Mock

import pytest
from app.errors import DomainError
from test_shutdown_support import database, raw_connection, assert_capacity


def test_repeated_close_claims_connector_once():
    """關閉責任只能交付一次，重試不能重複關閉同一 Connector。"""
    db = database()
    connector = Mock()
    db._connector = connector
    db.close()
    db.close()
    connector.close.assert_called_once()


def test_concurrent_close_claims_connector_once():
    """第一個 close 尚在外部清理時，第二個不得再次取得資源。"""
    db = database()
    entered, release = Event(), Event()
    connector = Mock()
    errors = []
    def slow_close():
        entered.set()
        assert release.wait(3)
    connector.close.side_effect = slow_close
    db._connector = connector
    def close():
        try:
            db.close()
        except BaseException as exc:
            errors.append(exc)
    first = Thread(target=close, daemon=True)
    first.start()
    try:
        assert entered.wait(3)
        second = Thread(target=close, daemon=True)
        second.start()
        second.join(.2)
    finally:
        release.set()
        first.join(3)
        if 'second' in locals():
            second.join(3)
    assert not errors
    assert not first.is_alive() and not second.is_alive()
    connector.close.assert_called_once()


def test_open_after_shutdown_never_creates_connector():
    """借用通過早期檢查後被關閉，不可再建立持續存活的 Connector。"""
    db = database()
    db.settings.connection_mode = 'cloud_sql'
    db.close()
    with pytest.raises(DomainError):
        db._open()
    db._connector_factory.assert_not_called()


def test_shutdown_during_open_never_yields_transaction(monkeypatch):
    """開連線期間關閉時，歸來的 raw 只清理、不交給新交易。"""
    db, raw = database(), raw_connection()
    def opening():
        db.close()
        return raw
    monkeypatch.setattr(db, '_open', opening)
    with pytest.raises(DomainError):
        with db.connect():
            pytest.fail('shutdown 後仍交出新交易')
    raw.close.assert_called_once()
    raw.commit.assert_not_called()
    assert_capacity(db, 1)


def cloud_database(pool_size=1):
    """提供完全合成的 Cloud SQL 設定；不建立實際 ADC 或連線。"""
    db = database(pool_size)
    db.settings.connection_mode = 'cloud_sql'
    db.settings.instance_connection_name = 'synthetic:region:instance'
    db.settings.db_user = 'synthetic'
    db.settings.db_password = ''
    db.settings.db_name = 'synthetic'
    return db


@pytest.mark.parametrize('borrowers', [1, 2])
def test_connector_shutdown_waits_for_openers_without_blocking_close(borrowers):
    """close 本身不等網路，最後一個 opener 負責唯一的 Connector 清理。"""
    db = cloud_database(borrowers)
    entered = [Event() for _ in range(borrowers)]
    release = [Event() for _ in range(borrowers)]
    completed = [Event() for _ in range(borrowers)]
    borrower_state = local()
    close_errors = []
    raws = [raw_connection() for _ in range(borrowers)]
    connector = Mock()
    errors, yielded = [], []
    for raw in raws:
        raw.cursor.return_value.fetchone.return_value = (180000,)
    from threading import Lock
    lock, index = Lock(), [0]
    def opening(*args, **kwargs):
        with lock:
            i = index[0]
            index[0] += 1
        borrower_state.index = i
        entered[i].set()
        assert release[i].wait(3)
        return raws[i]
    connector.connect.side_effect = opening
    db._connector_factory = Mock(return_value=connector)
    def borrow():
        try:
            with db.connect():
                yielded.append(True)
        except BaseException as exc:
            errors.append(exc)
        finally:
            if hasattr(borrower_state, 'index'):
                completed[borrower_state.index].set()
    threads = [Thread(target=borrow, daemon=True) for _ in range(borrowers)]
    close_done = Event()
    def close():
        try:
            db.close()
            db.close()
        except BaseException as exc:
            close_errors.append(exc)
        finally:
            close_done.set()
    closer = Thread(target=close, daemon=True)
    for thread in threads:
        thread.start()
    try:
        assert all(event.wait(3) for event in entered)
        closer.start()
        assert close_done.wait(.5), 'close 不得等待 provider connect'
        assert not close_errors, close_errors
        connector.close.assert_not_called()
        if borrowers == 2:
            release[0].set()
            assert completed[0].wait(3), '第一個 opener 未完成退出'
            # 以 provider 分配的識別碼確認退出，不假設 thread 啟動順序。
            connector.close.assert_not_called()
    finally:
        for event in release:
            event.set()
        for thread in threads:
            thread.join(3)
        if closer.ident is not None:
            closer.join(3)
    assert not any(t.is_alive() for t in threads) and not closer.is_alive()
    assert not close_errors, close_errors
    assert len(errors) == borrowers and all(isinstance(e, DomainError) for e in errors)
    assert not yielded
    connector.close.assert_called_once()
    db._connector_factory.assert_called_once()
    for raw in raws:
        raw.close.assert_called_once()
    assert_capacity(db, borrowers)


def test_provider_error_preserved_when_deferred_cleanup_also_fails():
    """開啟本身已失敗時，延後的關閉錯誤不能覆蓋第一個錯誤。"""
    db = cloud_database()
    connector = Mock()
    original = ValueError('synthetic connect failure')
    def opening(*args, **kwargs):
        db.close()
        connector.close.assert_not_called()
        raise original
    connector.connect.side_effect = opening
    connector.close.side_effect = RuntimeError('synthetic close failure')
    db._connector_factory = Mock(return_value=connector)
    with pytest.raises(ValueError) as exc:
        db._open()
    assert exc.value is original
    connector.close.assert_called_once()
    db.close()
    connector.close.assert_called_once()


def test_deferred_cleanup_failure_closes_unreturned_raw():
    """Connector 清理失敗阻止 _open 返回時，不得遺失已取得的 raw。"""
    db, raw = cloud_database(), raw_connection()
    connector = Mock()
    original = RuntimeError('synthetic connector close')
    def opening(*args, **kwargs):
        db.close()
        connector.close.assert_not_called()
        return raw
    connector.connect.side_effect = opening
    connector.close.side_effect = original
    db._connector_factory = Mock(return_value=connector)
    with pytest.raises(RuntimeError) as exc:
        db._open()
    assert exc.value is original
    raw.close.assert_called_once()
    connector.close.assert_called_once()
