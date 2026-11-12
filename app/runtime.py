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
    relation_source_store: str = ''  # 010驗收後才可對PG設link_table；空值沿用舊模式。
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
    write_origins: tuple = ()  # 額外受保護Tag僅允許自己的同源寫入，不改OAuth來源。
    cloud_run: bool = False
    business_enabled: bool = True
    public_gate_closed: bool = False  # 公開候選尚缺DB／登入Gate時，只開放非敏感頁面。

    google_client_id: str = ''  # 明確配置才啟用GIS；既有IAP部署預設不變。
    test_login_usernames: tuple = ()  # 既有授權測試帳密白名單，與Google共用Owner能力。
    registration_enabled: bool = True
    password_login_enabled: bool = True
    access_mode: str = 'legacy'
    auth_rate_enabled: bool = False
    auth_rate_secret: str = field(default='', repr=False)
    auth_source_mode: str = 'unconfigured'
    auth_trusted_proxies: tuple = ()
    alpha_worlds_total: int = 30
    alpha_worlds_daily: int = 20
    alpha_write_quota_enforced: bool = True  # 封測可只記錄累計寫入；不影響短時間限流。
    alpha_owner_writes: int = 100
    alpha_global_writes: int = 3000
    alpha_source_writes: int = 200
    alpha_storage_bytes: int = 100_000_000
    alpha_writes_enabled: bool = True
    alpha_login_enabled: bool = False

    @property
    def password_login_available(self):
        """登入管道開放由政策決定；不由Google Client設定決定。"""
        return bool(self.test_login_usernames) or (self.alpha_login_enabled if self.access_mode=='public_alpha' else self.password_login_enabled)

    def __post_init__(self):
        if self.relation_source_store not in ('','legacy_jsonb','link_table'):
            raise ValueError('Unknown relation source store')
        if self.public_gate_closed and (self.business_enabled or self.google_client_id or self.test_login_usernames):
            raise ValueError('Closed public gate cannot enable business or authentication')
        if any(not re.fullmatch(r"[a-z0-9_]{3,30}",x) for x in self.test_login_usernames):
            raise ValueError("Explicit test usernames required")
        for origin in self.write_origins:
            parsed = urlsplit(origin)
            if (parsed.scheme != 'https' or not parsed.netloc or parsed.hostname not in self.trusted_hosts
                    or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password
                    or parsed.port not in (None, 443) or origin != 'https://' + parsed.netloc):
                raise ValueError('Write origins must be exact HTTPS Trusted Hosts')
        if self.google_client_id and not re.fullmatch(r'[A-Za-z0-9._-]+\.apps\.googleusercontent\.com',self.google_client_id):
            raise ValueError('Explicit Google OAuth client required')
        if self.access_mode not in ('legacy','public_alpha') or self.auth_source_mode not in ('unconfigured','direct','proxy','iap','shared'):
            raise ValueError('Invalid access/source mode')
        if self.auth_source_mode=='shared' and (self.access_mode!='public_alpha' or self.registration_enabled or not self.auth_rate_enabled or len(self.auth_rate_secret.encode())<32):
            raise ValueError('Shared public source requires closed registration and enforced global quotas')
        if self.cloud_run and (self.auth_rate_enabled or self.access_mode=='public_alpha') and self.auth_source_mode=='direct':
            raise ValueError('Cloud Run requires verified proxy source policy')
        if self.auth_source_mode=='iap' and (not self.auth_rate_enabled or len(self.auth_rate_secret.encode())<32):
            raise ValueError('IAP staging requires shared rate protection')
        for n in self.auth_trusted_proxies:
            if ipaddress.ip_network(n).prefixlen==0:raise ValueError('Wildcard proxies are forbidden')
        if type(self.alpha_write_quota_enforced) is not bool:raise ValueError('Invalid Alpha write quota mode')
        for value in (self.alpha_worlds_total,self.alpha_worlds_daily,self.alpha_owner_writes,self.alpha_global_writes,self.alpha_source_writes):
            if not isinstance(value,int) or isinstance(value,bool) or not 1<=value<=1000000:raise ValueError('Invalid Alpha quota')
        if not isinstance(self.alpha_storage_bytes,int) or isinstance(self.alpha_storage_bytes,bool) or not 1<=self.alpha_storage_bytes<=1_000_000_000:raise ValueError('Invalid storage byte cap')
        if self.access_mode=='public_alpha' and self.backend=='postgresql' and not self.public_gate_closed:
            isolated=self.db_name=='life_world_alpha' and self.db_user=='lw_alpha_app'
            # Product公開候選沿用現有DB，只有明確Google-only與來源/容量護欄才可配置。
            product=(self.db_name=='life_world_product_staging' and self.db_user=='lw_product_staging_app'
                     and (bool(self.google_client_id) or bool(self.test_login_usernames) or (self.auth_source_mode=='shared' and not self.registration_enabled)) and self.secure_cookies
                     and self.external_origin.startswith('https://') and self.auth_rate_enabled
                     and len(self.auth_rate_secret.encode())>=32
                     and (self.auth_source_mode in ('iap','shared') or (self.auth_source_mode=='proxy' and bool(self.auth_trusted_proxies))))
            if not (isolated or product):
                raise ValueError('Public Alpha must use isolated database or guarded Product Staging profile')
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
        if self.backend == 'postgresql' and not self.public_gate_closed and (self.connection_mode not in ('tcp','cloud_sql') or not self.db_password
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
        closed = flag('LIFEWORLD_PUBLIC_GATE_CLOSED',False)
        if backend == 'postgresql' and not closed and (mode not in ('tcp', 'cloud_sql') or not password or (mode == 'cloud_sql' and not instance)):
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
        return cls(backend=backend, connection_mode=mode, relation_source_store=os.environ.get('LIFEWORLD_RELATION_SOURCE_STORE',''),
                   db_host=os.environ.get('LIFEWORLD_DB_HOST', '127.0.0.1'), db_port=port,
                   pg_tls=os.environ.get('LIFEWORLD_PG_TLS', 'auto'),
                   db_name=os.environ.get('LIFEWORLD_DB_NAME', 'life_world_dev'), db_schema=schema,
                   db_user=os.environ.get('LIFEWORLD_DB_USER', 'lw_app'), db_password=password,
                   instance_connection_name=instance, pool_size=size,
                   trusted_hosts=hosts, secure_cookies=secure, external_origin=origin,
                   write_origins=tuple(x.strip() for x in os.environ.get('LIFEWORLD_WRITE_ORIGINS','').split(',') if x.strip()),
                   google_client_id=os.environ.get('LIFEWORLD_GOOGLE_CLIENT_ID',''),
                   test_login_usernames=tuple(x.strip().lower() for x in os.environ.get('LIFEWORLD_TEST_LOGIN_USERNAMES','').split(',') if x.strip()),
                   registration_enabled=flag('LIFEWORLD_REGISTRATION_ENABLED',not cloud and not bool(os.environ.get('LIFEWORLD_GOOGLE_CLIENT_ID'))),
                   password_login_enabled=flag('LIFEWORLD_PASSWORD_LOGIN_ENABLED',not cloud),
                   access_mode=os.environ.get('LIFEWORLD_ACCESS_MODE','legacy'),
                   auth_rate_enabled=flag('LIFEWORLD_AUTH_RATE_ENABLED',False),
                   auth_rate_secret=os.environ.get('LIFEWORLD_AUTH_RATE_SECRET',''),
                   auth_source_mode=os.environ.get('LIFEWORLD_AUTH_SOURCE_MODE','unconfigured'),
                   auth_trusted_proxies=tuple(x.strip() for x in os.environ.get('LIFEWORLD_AUTH_TRUSTED_PROXIES','').split(',') if x.strip()),
                   alpha_worlds_total=int(os.environ.get('LIFEWORLD_ALPHA_WORLDS_TOTAL','30')),
                   alpha_worlds_daily=int(os.environ.get('LIFEWORLD_ALPHA_WORLDS_DAILY','20')),
                   alpha_write_quota_enforced=flag('LIFEWORLD_ALPHA_WRITE_QUOTA_ENFORCED',True),
                   alpha_owner_writes=int(os.environ.get('LIFEWORLD_ALPHA_OWNER_WRITES','100')),
                   alpha_global_writes=int(os.environ.get('LIFEWORLD_ALPHA_GLOBAL_WRITES','3000')),
                   alpha_source_writes=int(os.environ.get('LIFEWORLD_ALPHA_SOURCE_WRITES','200')),
                   alpha_storage_bytes=int(os.environ.get('LIFEWORLD_ALPHA_STORAGE_BYTES','100000000')),
                   alpha_writes_enabled=flag('LIFEWORLD_ALPHA_WRITES_ENABLED',True),
                   alpha_login_enabled=flag('LIFEWORLD_ALPHA_LOGIN_ENABLED',False),
                   cloud_run=cloud, business_enabled=flag('LIFEWORLD_ENABLE_BUSINESS_API', not cloud),public_gate_closed=closed)
