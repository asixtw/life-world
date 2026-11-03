"""明確的本機／Cloud Run 設定；不讀 .env、不將秘密寫入 repr。"""
from dataclasses import dataclass, field
import os
import re
from urllib.parse import urlsplit


def flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    if value.lower() not in ('true', 'false'):
        raise ValueError(name + ' must be true or false')
    return value.lower() == 'true'


@dataclass(frozen=True)
class RuntimeSettings:
    backend: str = 'sqlite'
    connection_mode: str = 'tcp'
    db_host: str = '127.0.0.1'
    db_port: int = 5432
    pg_tls: str = 'auto'
    db_name: str = 'life_world_dev'
    db_schema: str = 'lw_core_draft'
    db_user: str = 'lw_app'
    db_password: str = field(default='', repr=False)
    instance_connection_name: str = ''
    pool_size: int = 4
    pool_timeout: float = 5.0
    trusted_hosts: tuple = ('127.0.0.1', 'localhost', 'testserver', '[::1]')
    secure_cookies: bool = False
    external_origin: str = ''
    cloud_run: bool = False
    business_enabled: bool = True

    def __post_init__(self):
        # 直接注入設定與環境變數同樣驗證，避免測試／其他入口繞過邊界。
        if self.backend not in ('sqlite', 'postgresql'):
            raise ValueError('Unknown database backend')
        if not re.fullmatch(r'[a-z_][a-z0-9_]{0,62}', self.db_schema):
            raise ValueError('Invalid PostgreSQL schema identifier')
        if not 1 <= self.pool_size <= 32 or not 1 <= self.db_port <= 65535 or self.pool_timeout <= 0:
            raise ValueError('Invalid PostgreSQL pool/port configuration')
        if self.pg_tls not in ('auto', 'verify', 'disable'):
            raise ValueError('Invalid PostgreSQL TLS configuration')
        if self.pg_tls == 'disable' and self.db_host not in ('127.0.0.1', 'localhost', '::1', 'lw-pg18-tests'):
            raise ValueError('TLS cannot be disabled for remote PostgreSQL')
        if not self.trusted_hosts or any('*' in h or '/' in h for h in self.trusted_hosts):
            raise ValueError('Trusted Hosts must be explicit hostnames')
        if self.backend == 'postgresql' and (self.connection_mode not in ('tcp','cloud_sql') or not self.db_password
                or (self.connection_mode == 'cloud_sql' and not self.instance_connection_name)):
            raise ValueError('Incomplete PostgreSQL configuration')

    @classmethod
    def from_env(cls):
        """拒絕未知 backend／不完整 PG 設定，不允許退回 SQLite。"""
        cloud = bool(os.environ.get('K_SERVICE'))
        hosts = tuple(x.strip() for x in os.environ.get('LIFEWORLD_TRUSTED_HOSTS', '').split(',') if x.strip())
        if not hosts and cloud:
            raise ValueError('Cloud Run requires explicit Trusted Hosts')
        hosts = hosts or cls.trusted_hosts
        if any('*' in host or '/' in host for host in hosts):
            raise ValueError('Trusted Hosts must be explicit hostnames')
        backend = os.environ.get('LIFEWORLD_DB_BACKEND', 'sqlite')
        if backend not in ('sqlite', 'postgresql'):
            raise ValueError('Unknown database backend')
        secure = flag('LIFEWORLD_SECURE_COOKIES', cloud)
        if cloud and not secure:
            raise ValueError('Cloud Run requires Secure cookies')
        if cloud and backend != 'postgresql':
            raise ValueError('Cloud Run requires PostgreSQL backend')
        mode = os.environ.get('LIFEWORLD_PG_CONNECTION', 'tcp')
        password = os.environ.get('LIFEWORLD_DB_PASSWORD', '')
        instance = os.environ.get('LIFEWORLD_INSTANCE_CONNECTION_NAME', '')
        schema = os.environ.get('LIFEWORLD_DB_SCHEMA', 'lw_core_draft')
        if not re.fullmatch(r'[a-z_][a-z0-9_]{0,62}', schema):
            raise ValueError('Invalid PostgreSQL schema identifier')
        if backend == 'postgresql' and (mode not in ('tcp', 'cloud_sql') or not password or (mode == 'cloud_sql' and not instance)):
            raise ValueError('Incomplete PostgreSQL configuration')
        origin = os.environ.get('LIFEWORLD_EXTERNAL_ORIGIN', '').rstrip('/')
        if origin:
            parsed = urlsplit(origin)
            if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
                raise ValueError('Invalid external origin')
            if cloud and parsed.scheme != 'https':
                raise ValueError('Cloud Run external origin must use HTTPS')
        size = int(os.environ.get('LIFEWORLD_DB_POOL_SIZE', '4'))
        port = int(os.environ.get('LIFEWORLD_DB_PORT', '5432'))
        if not 1 <= size <= 32 or not 1 <= port <= 65535:
            raise ValueError('Invalid PostgreSQL pool/port configuration')
        return cls(backend=backend, connection_mode=mode,
                   db_host=os.environ.get('LIFEWORLD_DB_HOST', '127.0.0.1'), db_port=port,
                   pg_tls=os.environ.get('LIFEWORLD_PG_TLS', 'auto'),
                   db_name=os.environ.get('LIFEWORLD_DB_NAME', 'life_world_dev'), db_schema=schema,
                   db_user=os.environ.get('LIFEWORLD_DB_USER', 'lw_app'), db_password=password,
                   instance_connection_name=instance, pool_size=size,
                   trusted_hosts=hosts, secure_cookies=secure, external_origin=origin,
                   cloud_run=cloud, business_enabled=flag('LIFEWORLD_ENABLE_BUSINESS_API', not cloud))
