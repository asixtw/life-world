"""以受控事件驗證 shutdown，僅使用合成連線與隔離執行緒。"""
import queue
from threading import Event, Lock, Thread, current_thread
from unittest.mock import Mock

import pytest

from test_shutdown_support import database, raw_connection, assert_capacity


class ObservedLock:
    """觀察 close 開始等鎖，不要求 close 穿過尚未完成的歸還臨界區。"""
    def __init__(self, close_reached):
        self.lock = Lock()
        self.close_reached = close_reached

    def __enter__(self):
        if current_thread().name == 'pool-close':
            self.close_reached.set()
        self.lock.acquire()
        return self

    def __exit__(self, *args):
        self.lock.release()


def test_shutdown_racing_with_return_does_not_retain_connection(monkeypatch):
    """舊碼先 close 完，新碼先等待歸還短鎖，兩種路徑都可明確放行。"""
    db, raw = database(), raw_connection()
    monkeypatch.setattr(db, '_open', lambda: raw)
    entering_put, release_put, close_reached = Event(), Event(), Event()
    db._mutex = ObservedLock(close_reached)
    real_put = db._available.put
    errors = []

    def delayed_put(value):
        entering_put.set()
        if not release_put.wait(3):
            raise AssertionError('return probe timed out')
        real_put(value)

    monkeypatch.setattr(db._available, 'put', delayed_put)

    def borrower():
        try:
            with db.connect():
                pass
        except BaseException as exc:
            errors.append(exc)

    def shutdown():
        try:
            db.close()
        except BaseException as exc:
            errors.append(exc)
        finally:
            # 舊碼未取 mutex，故以 close 返回作為可放行的事件。
            close_reached.set()

    worker = Thread(target=borrower, daemon=True)
    closer = Thread(target=shutdown, name='pool-close', daemon=True)
    worker.start()
    try:
        assert entering_put.wait(3), 'return probe not reached'
        closer.start()
        assert close_reached.wait(3), 'close neither reached lock nor returned'
    finally:
        release_put.set()
        worker.join(3)
        if closer.ident is not None:
            closer.join(3)
    assert not worker.is_alive() and not closer.is_alive(), 'shutdown deadlock'
    assert not errors, errors
    assert_capacity(db, 1)
    assert (db._available.qsize(), raw.close.call_count) == (0, 1)


def test_shutdown_close_error_does_not_abandon_remaining_resources():
    """LIFO 第一條關閉失敗仍清完其餘 raw 與 Connector，重拋同一例外。"""
    db = database(2)
    healthy, broken = raw_connection(), raw_connection(close_error=True)
    connector = Mock()
    db._connector = connector
    first_error = broken.close.side_effect
    db._available.put(healthy)
    db._available.put(broken)
    caught = None
    try:
        db.close()
    except BaseException as exc:
        caught = exc
    assert (healthy.close.call_count, connector.close.call_count, db._available.qsize()) == (1, 1, 0)
    assert caught is first_error


@pytest.mark.parametrize('first_error', [RuntimeError('first raw'), queue.Empty('raw close'), KeyboardInterrupt('first raw')])
def test_shutdown_keeps_first_error_after_all_cleanup_attempts(first_error):
    """清理失敗不是出列失敗；不中途吞錯，也不讓後續錯誤取代首錯。"""
    db = database(3)
    healthy, second, first = raw_connection(), raw_connection(), raw_connection()
    second.close.side_effect = ValueError('second raw')
    first.close.side_effect = first_error
    connector = Mock()
    connector.close.side_effect = RuntimeError('connector')
    db._connector = connector
    for raw in (healthy, second, first):
        db._available.put(raw)
    caught = None
    try:
        db.close()
    except BaseException as exc:
        caught = exc
    assert [raw.close.call_count for raw in (first, second, healthy)] == [1, 1, 1]
    connector.close.assert_called_once()
    assert db._available.empty()
    assert caught is first_error
    assert_capacity(db, 3)


def test_connector_only_error_is_not_swallowed():
    db = database()
    connector = Mock()
    original = RuntimeError('connector close')
    connector.close.side_effect = original
    db._connector = connector
    with pytest.raises(RuntimeError) as exc:
        db.close()
    assert exc.value is original
    assert db._closed
    assert db._available.empty()


def test_shutdown_closes_resources_outside_mutex():
    """外部 close 不能持鎖，避免 driver／Connector 回呼或慢 I/O 阻塞歸還。"""
    db, raw = database(), raw_connection()
    connector = Mock()
    db._connector = connector
    db._available.put(raw)

    def check_lock():
        acquired = db._mutex.acquire(blocking=False)
        assert acquired, 'foreign close called while pool mutex held'
        db._mutex.release()

    raw.close.side_effect = check_lock
    connector.close.side_effect = check_lock
    db.close()
    raw.close.assert_called_once()
    connector.close.assert_called_once()


def test_active_borrower_can_close_pool_without_waiting_for_itself(monkeypatch):
    """保留既有非等待式 shutdown；active raw 由借用者退出時關閉。"""
    db, raw = database(), raw_connection()
    monkeypatch.setattr(db, '_open', lambda: raw)
    with db.connect():
        db.close()
        raw.close.assert_not_called()
    raw.commit.assert_called_once()
    raw.close.assert_called_once()
    assert db._available.empty()
    assert_capacity(db, 1)


def test_slow_idle_close_does_not_block_active_return(monkeypatch):
    """用真執行緒驗證外部慢 close 不會把歸還或重入鎖住。"""
    db = database(2)
    active, idle = raw_connection(), raw_connection()
    monkeypatch.setattr(db, '_open', lambda: active)
    entered, release = Event(), Event()
    errors = []

    def slow_close():
        entered.set()
        if not release.wait(3):
            raise AssertionError('slow close probe timed out')

    idle.close.side_effect = slow_close

    def shutdown():
        try:
            db.close()
        except BaseException as exc:
            errors.append(exc)

    thread = Thread(target=shutdown, daemon=True)
    try:
        with db.connect():
            db._available.put(idle)
            thread.start()
            assert entered.wait(3)
        active.close.assert_called_once()
        assert_capacity(db, 2)
    finally:
        release.set()
        if thread.ident is not None:
            thread.join(3)
    assert not thread.is_alive()
    assert not errors, errors
    assert db._available.empty()
