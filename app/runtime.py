"""明確的本機／Cloud Run 設定；不讀 .env、不將秘密寫入 repr。"""
from dataclasses import dataclass, field
import os
import re
import ipaddress
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

    google_client_id: str = ''  # 明確配置才啟用GIS；既有IAP部署預設不變。
    access_mode: str = 'legacy'
    auth_rate_enabled: bool = False
    auth_rate_secret: str = field(default='', repr=False)
    auth_source_mode: str = 'unconfigured'
    auth_trusted_proxies: tuple = ()
    alpha_worlds_total: int = 30
    alpha_worlds_daily: int = 20
    alpha_owner_writes: int = 100
    alpha_global_writes: int = 3000
    alpha_source_writes: int = 200
    alpha_storage_bytes: int = 100_000_000
    alpha_writes_enabled: bool = True
    alpha_login_enabled: bool = False

    def __post_init__(self):
        if self.google_client_id and not re.fullmatch(r'[A-Za-z0-9._-]+\.apps\.googleusercontent\.com',self.google_client_id):
            raise ValueError('Explicit Google OAuth client required')
        if self.access_mode not in ('legacy','public_alpha') or self.auth_source_mode not in ('unconfigured','direct','proxy','iap'):
            raise ValueError('Invalid access/source mode')
        if self.cloud_run and (self.auth_rate_enabled or self.access_mode=='public_alpha') and self.auth_source_mode=='direct':
            raise ValueError('Cloud Run requires verified proxy source policy')
        if self.auth_source_mode=='iap' and (not self.auth_rate_enabled or len(self.auth_rate_secret.encode())<32):
            raise ValueError('IAP staging requires shared rate protection')
        for n in self.auth_trusted_proxies:
            if ipaddress.ip_network(n).prefixlen==0:raise ValueError('Wildcard proxies are forbidden')
        for value in (self.alpha_worlds_total,self.alpha_worlds_daily,self.alpha_owner_writes,self.alpha_global_writes,self.alpha_source_writes):
            if not isinstance(value,int) or isinstance(value,bool) or not 1<=value<=1000000:raise ValueError('Invalid Alpha quota')
        if not isinstance(self.alpha_storage_bytes,int) or isinstance(self.alpha_storage_bytes,bool) or not 1<=self.alpha_storage_bytes<=1_000_000_000:raise ValueError('Invalid storage byte cap')
        if self.access_mode=='public_alpha' and self.backend=='postgresql' and (self.db_name!='life_world_alpha' or self.db_user!='lw_alpha_app'):
            raise ValueError('Public Alpha must use isolated database and runtime role')
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
        # IAP audience 在驗證器依受控 Origin／明確設定核對，不公開固定專案參數。
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
                   google_client_id=os.environ.get('LIFEWORLD_GOOGLE_CLIENT_ID',''),
                   access_mode=os.environ.get('LIFEWORLD_ACCESS_MODE','legacy'),
                   auth_rate_enabled=flag('LIFEWORLD_AUTH_RATE_ENABLED',False),
                   auth_rate_secret=os.environ.get('LIFEWORLD_AUTH_RATE_SECRET',''),
                   auth_source_mode=os.environ.get('LIFEWORLD_AUTH_SOURCE_MODE','unconfigured'),
                   auth_trusted_proxies=tuple(x.strip() for x in os.environ.get('LIFEWORLD_AUTH_TRUSTED_PROXIES','').split(',') if x.strip()),
                   alpha_worlds_total=int(os.environ.get('LIFEWORLD_ALPHA_WORLDS_TOTAL','30')),
                   alpha_worlds_daily=int(os.environ.get('LIFEWORLD_ALPHA_WORLDS_DAILY','20')),
                   alpha_owner_writes=int(os.environ.get('LIFEWORLD_ALPHA_OWNER_WRITES','100')),
                   alpha_global_writes=int(os.environ.get('LIFEWORLD_ALPHA_GLOBAL_WRITES','3000')),
                   alpha_source_writes=int(os.environ.get('LIFEWORLD_ALPHA_SOURCE_WRITES','200')),
                   alpha_storage_bytes=int(os.environ.get('LIFEWORLD_ALPHA_STORAGE_BYTES','100000000')),
                   alpha_writes_enabled=flag('LIFEWORLD_ALPHA_WRITES_ENABLED',True),
                   alpha_login_enabled=flag('LIFEWORLD_ALPHA_LOGIN_ENABLED',False),
                   cloud_run=cloud, business_enabled=flag('LIFEWORLD_ENABLE_BUSINESS_API', not cloud))
