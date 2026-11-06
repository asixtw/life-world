"""PRIVATE staging的IAP signed assertion；不把外層身分當App登入。"""
import json
import os
from urllib.parse import urlsplit
import re
import threading
import time
import urllib.request
from google.auth import jwt
from google.auth.crypt.es256 import ES256Verifier
from .errors import DomainError

def expected_audience():
    """優先明確設定；既有服務可從受控的標準 Cloud Run Origin 推導，避免公開私有雲端參數。"""
    value=os.environ.get('LIFEWORLD_IAP_AUDIENCE','')
    if not value:
        origin=urlsplit(os.environ.get('LIFEWORLD_EXTERNAL_ORIGIN',''))
        service=os.environ.get('K_SERVICE','')
        match=re.fullmatch(re.escape(service)+r'-([0-9]+)\.([a-z0-9-]+)\.run\.app',origin.hostname or '') if service else None
        if origin.scheme=='https' and not origin.path and not origin.query and not origin.fragment and not origin.username and not origin.password and match:
            value=f'/projects/{match[1]}/locations/{match[2]}/services/{service}'
    if not re.fullmatch(r'/projects/[0-9]+/locations/[a-z0-9-]+/services/[a-z][a-z0-9-]+',value):
        raise ValueError('Explicit valid IAP audience or canonical Cloud Run Origin required')
    return value
ISSUER='https://cloud.google.com/iap'
KEY_URL='https://www.gstatic.com/iap/verify/public_key'


def denied():
    return DomainError(401,'iap_identity_required','請使用已獲授權的IAP帳號進入。')


def unavailable():
    return DomainError(503,'iap_verification_unavailable','身分驗證暫時不可用，請稍後重試。')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """公鑰只能來自固定HTTPS端點，不跟隨redirect或token提供的URL。"""
    def redirect_request(self,*args,**kwargs):return None


def fetch_keys():
    """固定端點、有限timeout／大小；不傳憑證、不記錄回應本文。"""
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(KEY_URL,timeout=3) as response:
        data=response.read(65537)
        if len(data)>65536:raise ValueError('Key response too large')
    return json.loads(data)


class IAPVerifier:
    """google-auth負責ES256／iat／exp；cache只存公鑰，不存token或subject。"""
    def __init__(self,fetch=fetch_keys,monotonic=time.monotonic,audience=None):
        self.audience=audience or expected_audience()
        self.fetch,self.monotonic=fetch,monotonic
        self.lock=threading.Lock();self.keys={};self.deadline=0;self.next_refresh=0

    def _keys(self,kid):
        with self.lock:
            now=self.monotonic()
            if now<self.deadline and kid in self.keys:return self.keys
            # 限制未知kid／故障造成的外部抓取風暴；過期鍵絕不當有效鍵使用。
            if now<self.next_refresh:
                if now>=self.deadline:raise unavailable()
                raise denied()
            self.next_refresh=now+30
            try:
                keys=self.fetch()
                if not isinstance(keys,dict) or not 1<=len(keys)<=64:raise ValueError('Invalid keys')
                for key,value in keys.items():
                    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',key) or not isinstance(value,str) or len(value)>8192:raise ValueError('Invalid key')
                    ES256Verifier.from_string(value) # 使用現成套件檢查公鑰，不自製密碼學。
                self.keys=keys;self.deadline=now+300
            except Exception:raise unavailable() from None
            if kid not in self.keys:raise denied()
            return self.keys

    def verify(self,token):
        """回傳穩定來源字串；任何錯誤不回顯token／claims。"""
        if not isinstance(token,str) or not 1<=len(token)<=16384:raise denied()
        try:
            header=jwt.decode_header(token)
            if header.get('alg')!='ES256' or not isinstance(header.get('kid'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',header['kid']):raise ValueError('Invalid header')
            if any(k in header for k in ('jku','jwk','x5u','crit')):raise ValueError('Unaccepted header')
        except Exception:raise denied() from None
        keys=self._keys(header['kid'])
        try:
            claims=jwt.decode(token,certs=keys,audience=self.audience,clock_skew_in_seconds=30)
            if claims.get('iss')!=ISSUER or claims.get('aud')!=self.audience:raise ValueError('Invalid issuer/audience')
            if any(type(claims.get(k)) is not int for k in ('iat','exp')) or claims['exp']<=claims['iat']:raise ValueError('Invalid times')
            sub=claims.get('sub')
            if not isinstance(sub,str) or not sub.strip() or len(sub)>255:raise ValueError('Invalid subject')
            return 'iap:'+ISSUER+':'+sub
        except Exception:raise denied() from None
