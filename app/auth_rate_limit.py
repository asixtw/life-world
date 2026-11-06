"""DB共用限流與Alpha配額；識別經HMAC，不讀取或記錄憑證。"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
import logging
from .errors import DomainError

log=logging.getLogger(__name__)


def protection_unavailable():
    return DomainError(503,'auth_protection_unavailable','登入保護暫時不可用，請保留內容並稍後重試。')


class AuthRateLimiter:
    """傳入同一寫交易；錯誤以值回傳，使登入失敗記次可先提交再回401。"""
    def __init__(self, settings, clock):
        self.settings,self.clock=settings,clock
        self.backend='sqlite'

    @property
    def enabled(self):
        return self.settings.auth_rate_enabled or self.settings.access_mode=='public_alpha'

    def ready(self,db):
        if not self.enabled:return
        self._check_config()
        try:
            with db.connect() as c:c.execute('SELECT scope,key_hash,window_started_at,attempts FROM auth_rate_buckets LIMIT 0')
        except Exception:raise protection_unavailable() from None

    def _check_config(self):
        s=self.settings
        if (len(s.auth_rate_secret.encode())<32 or s.auth_source_mode=='unconfigured'
                or (s.auth_source_mode=='proxy' and not s.auth_trusted_proxies)):
            raise protection_unavailable()

    def source(self,request):
        """僅原始peer直連或已明確信任的代理鏈；不接受任意最左XFF。"""
        self._check_config()
        if self.settings.auth_source_mode=='iap':
            subject=getattr(request.state,'lw_iap_subject',None)
            if not isinstance(subject,str) or not subject.startswith('iap:https://cloud.google.com/iap:'):raise protection_unavailable()
            return subject
        try:
            peer=ipaddress.ip_address(request.client.host)
            def canonical(ip):return str(ip.ipv4_mapped or ip) if isinstance(ip,ipaddress.IPv6Address) else str(ip)
            if self.settings.auth_source_mode=='direct':return canonical(peer)
            networks=[ipaddress.ip_network(n) for n in self.settings.auth_trusted_proxies]
            def trusted(ip):return any(ip in net for net in networks)
            if not trusted(peer):raise ValueError('untrusted peer')
            values=request.headers.getlist('x-forwarded-for')
            if len(values)!=1 or len(values[0])>2048:raise ValueError('invalid chain')
            chain=[ipaddress.ip_address(v.strip()) for v in values[0].split(',')]
            if len(chain)>16:raise ValueError('long chain')
            while chain and trusted(chain[-1]):chain.pop()
            if not chain:raise ValueError('no source')
            return canonical(chain[-1])
        except (ValueError,AttributeError):raise protection_unavailable() from None

    def take(self,c,scope,identifier,limit,seconds=None,capacity=False):
        """列鎖／SQLite寫鎖包住首次插入及門檻，拒絕不延長首次起算視窗。"""
        now=self.clock().astimezone(timezone.utc)
        key=hmac.new(self.settings.auth_rate_secret.encode(),(scope+'\0'+identifier).encode(),hashlib.sha256).hexdigest()
        c.execute('INSERT INTO auth_rate_buckets(scope,key_hash,window_started_at,attempts) VALUES (?,?,?,0) ON CONFLICT(scope,key_hash) DO NOTHING',(scope,key,now.isoformat()))
        suffix=' FOR UPDATE' if self.backend=='postgresql' else ''
        row=c.execute('SELECT window_started_at,attempts FROM auth_rate_buckets WHERE scope=? AND key_hash=?'+suffix,(scope,key)).fetchone()
        started=datetime.fromisoformat(row['window_started_at'])
        used=row['attempts']
        if seconds is not None and (now-started).total_seconds()>=seconds:started,used=now,0
        if used>=limit:
            if capacity:return DomainError(409,'alpha_capacity_reached','本輪 Alpha 測試額度已滿；已保存內容仍可查看，請留意後續開放。')
            error=DomainError(429,'rate_limited','操作過於頻繁，請稍後再試。')
            error.headers={'Retry-After':str(max(1,int(seconds-(now-started).total_seconds()+.999))), 'Cache-Control':'no-store'}
            return error
        c.execute('UPDATE auth_rate_buckets SET window_started_at=?,attempts=? WHERE scope=? AND key_hash=?',(started.isoformat(),used+1,scope,key))
        return None

    def reset_account(self,c,username):
        key=hmac.new(self.settings.auth_rate_secret.encode(),('login_account_fail\0'+username.lower()).encode(),hashlib.sha256).hexdigest()
        c.execute('UPDATE auth_rate_buckets SET attempts=0,window_started_at=? WHERE scope=? AND key_hash=?',(self.clock().isoformat(),'login_account_fail',key))

    def login_admission(self,c,request):
        if not self.enabled:return None
        source=self.source(request)
        return (self.take(c,'login_global_attempt','all',3000,86400)
                or self.take(c,'login_source_attempt',source,30,900))

    def failure(self,c,username):
        if not self.enabled:return None
        return self.take(c,'login_account_fail',username.lower(),5,900)

    def guest_admission(self,c,request):
        if not self.enabled:return
        source=self.source(request)
        if self.settings.access_mode=='public_alpha':
            if not self.settings.alpha_writes_enabled:raise DomainError(503,'alpha_paused','Alpha 暫停新增，已保存內容仍可查看。')
            for scope,limit,seconds in [('alpha_worlds_total',self.settings.alpha_worlds_total,None),('alpha_worlds_daily',self.settings.alpha_worlds_daily,86400)]:
                error=self.take(c,scope,'all',limit,seconds,capacity=seconds is None)
                if error:raise error
        error=self.take(c,'guest_source_create',source,10,3600)
        if error:raise error


class AlphaDatabase:
    """所有owner寫交易都有原子總額度，避免只限制建立世界卻無界寫其他表。"""
    def __init__(self,db,limiter):
        self.inner,self.limiter=db,limiter
        self.backend=db.backend

    def __getattr__(self,name):return getattr(self.inner,name)

    def logical_bytes(self,c):
        # Application row payload budget, not Cloud SQL physical/index/backup quota.
        import json,re
        if self.backend=='postgresql':
            tables=[r['name'] for r in c.execute("SELECT relname AS name FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relkind='r'").fetchall()]
        else:tables=[r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
        total=0
        for table in tables:
            if table=='schema_migrations':continue # immutable deployment receipts, runtime has no access
            if not re.fullmatch('[a-z_][a-z0-9_]*',table):raise protection_unavailable()
            if self.backend=='postgresql':
                total+=int(c.execute('SELECT COALESCE(sum(octet_length(to_jsonb(budget_row)::text)),0) AS bytes FROM "'+table+'" budget_row').fetchone()['bytes'])
            else:
                total+=sum(len(json.dumps(dict(row),ensure_ascii=False,default=str,separators=(',',':')).encode()) for row in c.execute('SELECT * FROM "'+table+'"').fetchall())
        return total

    def storage_gate(self,c):
        if self.logical_bytes(c)>self.limiter.settings.alpha_storage_bytes:
            raise DomainError(409,'storage_capacity_reached','目前保存容量已滿；既有資料仍可讀取，請聯絡測試支援。')

    @contextmanager
    def connect(self,write=False,owner=None):
        with self.inner.connect(write=write,owner=owner) as c:
            if write:
                if self.backend=='postgresql':c.execute('SELECT pg_advisory_xact_lock(?)',(1420000001,))
                before_bytes=self.logical_bytes(c)
            if write and owner:
                self.limiter._check_config()
                s=self.limiter.settings
                if not s.alpha_writes_enabled:raise DomainError(503,'alpha_paused','Alpha 暫停寫入，已保存內容仍可查看。')
                for scope,key,limit in [('alpha_writes_total','all',s.alpha_global_writes),('alpha_owner_writes',owner,s.alpha_owner_writes)]:
                    error=self.limiter.take(c,scope,key,limit,capacity=True)
                    if error:raise error
            yield c
            if write:
                after_bytes=self.logical_bytes(c)
                # Allow revocation/shrinking if an operator lowered the cap below existing usage.
                if after_bytes>self.limiter.settings.alpha_storage_bytes and after_bytes>=before_bytes:
                    raise DomainError(409,'storage_capacity_reached','目前保存容量已滿；既有資料仍可讀取，請聯絡測試支援。')


class AlphaBodyLimit:
    """在解析前限制所有Alpha寫入本文，包括無Content-Length的串流。"""
    def __init__(self,app,max_bytes=65536):self.app,self.max_bytes=app,max_bytes

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or not scope['path'].startswith('/api/') or scope['method'] in ('GET','HEAD','OPTIONS'):
            return await self.app(scope,receive,send)
        from starlette.responses import JSONResponse
        chunks=[];size=0
        while True:
            event=await receive()
            if event['type']=='http.disconnect':return
            chunk=event.get('body',b'');size+=len(chunk)
            if size>self.max_bytes:
                return await JSONResponse({'error':{'code':'alpha_body_too_large','message':'Alpha單次輸入超過64KiB，請縮短後重試。'}},status_code=413,headers={'Cache-Control':'no-store'})(scope,receive,send)
            chunks.append(chunk)
            if not event.get('more_body',False):break
        sent=False
        async def bounded():
            nonlocal sent
            if not sent:
                sent=True
                return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await receive()
        await self.app(scope,bounded,send)
