"""Google-only ID token驗證；SDK負責簽章，不把email當外部身分。"""
import json
import re
import secrets
import threading
import time
import urllib.request
from types import SimpleNamespace
from google.auth import jwt
from google.oauth2 import id_token
from .errors import DomainError
from .security import digest

CERTS='https://www.googleapis.com/oauth2/v1/certs'
ISSUER='https://accounts.google.com'


class FixedCertificates:
    """固定公鑰URL、有限回應與timeout；不跟隨redirect，不讀SA憑證。"""
    def __init__(self):
        self.lock=threading.Lock();self.data=None;self.until=0;self.retry=0

    def __call__(self,url,method='GET',**kwargs):
        if url!=CERTS or method!='GET':raise DomainError(503,'google_keys_unavailable','登入驗證暫時不可用。')
        with self.lock:
            now=time.monotonic()
            if self.data is not None and now<self.until:return SimpleNamespace(status=200,data=self.data)
            if now<self.retry:raise DomainError(503,'google_keys_unavailable','登入驗證暫時不可用。')
            self.retry=now+30
            try:
                class NoRedirect(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self,*a,**k):return None
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
                with opener.open(CERTS,timeout=3) as response:data=response.read(65537)
                if len(data)>65536 or not isinstance(json.loads(data),dict):raise ValueError('Invalid certificates')
                self.data=data;self.until=now+300
                return SimpleNamespace(status=200,data=data)
            except Exception:raise DomainError(503,'google_keys_unavailable','登入驗證暫時不可用，請稍後重試。') from None


class GoogleVerifier:
    """回傳canonical issuer/sub；mock只在測試注入，Runtime永遠走google-auth。"""
    def __init__(self,client_id,request=None,clock=time.time):
        if not re.fullmatch(r'[A-Za-z0-9._-]+\.apps\.googleusercontent\.com',client_id):raise ValueError('Explicit Google OAuth client required')
        self.client_id=client_id;self.request=request or FixedCertificates();self.clock=clock

    def verify(self,token,nonce_hash):
        try:
            if not isinstance(token,str) or not 1<=len(token)<=16384:raise ValueError('Invalid credential')
            header=jwt.decode_header(token)
            if header.get('alg')!='RS256' or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',header.get('kid','')):raise ValueError('Invalid algorithm/key')
            if any(k in header for k in ('jku','jwk','x5u','crit')):raise ValueError('Invalid header')
            claims=id_token.verify_oauth2_token(token,self.request,audience=self.client_id,clock_skew_in_seconds=30)
            now=self.clock()
            if claims.get('iss') not in (ISSUER,'accounts.google.com') or claims.get('aud')!=self.client_id:raise ValueError('Invalid issuer/audience')
            iat,exp=claims.get('iat'),claims.get('exp')
            if type(iat) is not int or type(exp) is not int or iat>now+30 or exp<=now-30 or not 0<exp-iat<=7200:raise ValueError('Invalid time')
            nonce=claims.get('nonce');sub=claims.get('sub')
            if not isinstance(nonce,str) or not secrets.compare_digest(digest(nonce),nonce_hash):raise ValueError('Invalid nonce')
            if not isinstance(sub,str) or not sub or sub!=sub.strip() or len(sub)>255:raise ValueError('Invalid subject')
            return ISSUER,sub
        except DomainError:raise
        except Exception:raise DomainError(401,'google_identity_rejected','Google登入驗證失敗，請重新開始。') from None
