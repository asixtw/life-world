"""PG18 DBAPI adapter：有界 pool、owner 交易鎖與既有 API 型別邊界。

不執行 DDL、不讀 migration role、不在遠端呼叫外包住領域交易。
qmark 交由 pg8000 原生參數解析器處理，絕不以字串取代資料或 SQL 方言。
"""
from contextlib import closing
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import queue
import ssl
import threading

import pg8000.dbapi as driver

from .errors import DomainError
from .schemas import format_decimal

driver.paramstyle = 'qmark'


def legacy_value(value, type_code=None):
    """保留既有 JSON／Decimal／ISO 字串契約，不重算歷史 fingerprint。"""
    if value is None:
        return None
    if type_code in (114, 3802):  # JSON／JSONB 的值由 driver 解碼後再回既有 service 字串介面。
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format_decimal(value)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    return value


class Row(Mapping):
    """兼容 dict(row)、row['name'] 及既有單欄 row[0]。"""
    def __init__(self, names, values):
        self.names, self.values = names, tuple(values)
        self.mapping = dict(zip(names, self.values))

    def __getitem__(self, key):
        return self.values[key] if isinstance(key, int) else self.mapping[key]

    def __iter__(self):
        return iter(self.mapping)

    def __len__(self):
        return len(self.mapping)


class Result:
    """交易內即時取回資料並關閉 cursor，避免 pool 留下跨請求游標。"""
    def __init__(self, cursor):
        self.rowcount = cursor.rowcount
        description = cursor.description
        self.rows = [] if description is None else [
            Row(tuple(d[0] for d in description),
                [legacy_value(v, d[1]) for v, d in zip(values, description)])
            for values in cursor.fetchall()]
        self.position = 0

    def fetchone(self):
        if self.position == len(self.rows):
            return None
        value = self.rows[self.position]
        self.position += 1
        return value

    def fetchall(self):
        values = self.rows[self.position:]
        self.position = len(self.rows)
        return values

    def __iter__(self):
        return iter(self.fetchall())


class Connection:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, statement, parameters=()):
        # 識別字只能由受控程式／驗證過 schema 產生；值始終走 driver bind。
        with closing(self.raw.cursor()) as cursor:
            cursor.execute(statement, tuple(parameters))
            return Result(cursor)


def translated_error(exc):
    """只輸出固定領域碼，不回傳 server detail／SQL／密碼。"""
    info = exc.args[0] if exc.args and isinstance(exc.args[0], dict) else {}
    state, constraint = info.get('C'), info.get('n', '')
    if state == '23505':
        code = 'username_taken' if constraint == 'users_username_key' else 'write_conflict'
        if constraint == 'one_open_goal_per_owner':
            code = 'open_goal_exists'
        return DomainError(409, code, '資料已由另一提交更新，請重新讀取或核對原提交回執。')
    if state in ('40001', '40P01', '55P03', '57014'):
        return DomainError(409, 'transaction_conflict', '交易發生衝突，請沿用原提交代碼重新核對。')
    if state == '42501':
        return DomainError(503, 'database_permission_unavailable', '資料服務權限尚未就緒。')
    return DomainError(503, 'database_unavailable', '資料服務暫時不可用，請保留內容並沿用原提交代碼重試。')


class PostgresDatabase:
    backend = 'postgresql'

    def __init__(self, settings, connector_factory=None):
        self.settings = settings
        self._available = queue.LifoQueue()
        self._slots = threading.BoundedSemaphore(settings.pool_size)
        self._mutex = threading.Lock()
        self._connector = None
        self._connector_factory = connector_factory
        self._closed = False

    def _open(self):
        """TCP 僅是明確模式；cloud_sql 只在首次取連線時才取得 ADC。"""
        s = self.settings
        if s.connection_mode == 'tcp':
            local = s.db_host in ('127.0.0.1', 'localhost', '::1')
            raw = driver.connect(user=s.db_user, password=s.db_password,
                                 database=s.db_name, host=s.db_host, port=s.db_port,
                                 ssl_context=False if s.pg_tls == 'disable' or (local and s.pg_tls == 'auto') else ssl.create_default_context(),
                                 timeout=s.pool_timeout, application_name='lifeworld-api')
        else:
            with self._mutex:
                if self._connector is None:
                    if self._connector_factory is None:
                        from google.cloud.sql.connector import Connector
                        self._connector_factory = Connector
                    # 使用執行服務的 ADC；不接受 SA JSON、不切到 public IP。
                    self._connector = self._connector_factory(ip_type='private', refresh_strategy='lazy', timeout=s.pool_timeout)
            raw = self._connector.connect(s.instance_connection_name, 'pg8000',
                                          user=s.db_user, password=s.db_password, db=s.db_name)
        try:
            raw.autocommit = True
            with closing(raw.cursor()) as cursor:
                cursor.execute('SHOW server_version_num')
                if int(cursor.fetchone()[0]) // 10000 != 18:
                    raise ValueError('PostgreSQL 18 required')
                cursor.execute("SELECT set_config('search_path', ?, false)", (f'"{s.db_schema}",pg_catalog',))
                cursor.execute("SET TIME ZONE 'UTC'")
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SET statement_timeout = '15s'")
            raw.autocommit = False
            return raw
        except BaseException:
            raw.close()
            raise

    @contextmanager
    def connect(self, write=False, owner=None):
        """同 owner 的寫交易跨執行個體序列化；不同 owner 可並行。

        先取得 advisory lock 才讀 revision／request receipt。每個 statement
        使用 READ COMMITTED 的新快照，等待鎖後不沿用過期資料。
        """
        if not self._slots.acquire(timeout=self.settings.pool_timeout):
            raise DomainError(503, 'database_busy', '資料服務忙碌，請稍後重試。')
        raw, reusable = None, True
        try:
            if self._closed:
                raise DomainError(503, 'database_unavailable', '資料服務已關閉。')
            try:
                raw = self._available.get_nowait()
            except queue.Empty:
                try:
                    raw = self._open()
                except Exception:
                    # ADC／網路／TLS／版本錯誤也不把 provider detail 傳給呼叫端。
                    raise DomainError(503, 'database_unavailable', '資料服務連線尚未就緒。') from None
            c = Connection(raw)
            if write:
                c.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
                namespace = self.settings.db_schema + '\0' + (owner or 'identity')
                key = int.from_bytes(hashlib.sha256(namespace.encode()).digest()[:8], 'big', signed=True)
                c.execute('SELECT pg_advisory_xact_lock(?)', (key,))
            else:
                c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            yield c
            raw.commit()
        except BaseException as exc:
            if raw is not None:
                try:
                    raw.rollback()
                except Exception:
                    reusable = False
            if isinstance(exc, driver.Error):
                raise translated_error(exc) from None
            raise
        finally:
            if raw is not None:
                if reusable and not self._closed:
                    self._available.put(raw)
                else:
                    raw.close()
            self._slots.release()

    @staticmethod
    def audit_column(table):
        if table not in ('goal_reviews', 'story_history'):
            raise ValueError('Unknown audit table')
        return 'audit_seq'

    def check_ready(self):
        with self.connect() as connection:
            connection.execute('SELECT id FROM users LIMIT 0')
            connection.execute('SELECT id FROM goals LIMIT 0')

    def close(self):
        self._closed = True
        while True:
            try:
                self._available.get_nowait().close()
            except queue.Empty:
                break
        if self._connector is not None:
            self._connector.close()
