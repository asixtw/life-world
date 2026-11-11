"""Google交換與Guest原地升級；既有requests收據＋新身份映射表，Runtime不執行DDL。"""
from datetime import datetime,timedelta
import json
import secrets
from uuid import uuid4
import hashlib
from .errors import DomainError,require
from .security import digest,new_session

CHALLENGE='google_challenge_v1'
EXCHANGE='google_exchange_v1'


class ExternalAuth:
    """驗證器外呼不持DB鎖；交易內重新驗Session、身份與一次性消費。"""
    def __init__(self,service,verifier,limiter):
        self.service=service;self.db=service.db;self.verifier=verifier;self.limiter=limiter

    def _write(self,owner=None):
        # 身分交換不消耗業務寫入容量；仍保留來源、Session、帳號與全域登入保護。
        if hasattr(self.db,'authentication_connect'):return self.db.authentication_connect(owner)
        return self.db.connect(write=True,owner=owner)

    def _session(self,c,token,csrf):
        r=c.execute('SELECT * FROM sessions WHERE token_hash=?',(digest(token or ''),)).fetchone()
        require(r is not None and datetime.fromisoformat(r['expires_at'])>self.service.now(),401,'session_expired','工作階段已失效，請重新開始。')
        require(bool(csrf) and secrets.compare_digest(csrf,r['csrf_token']),403,'csrf_rejected','請重新整理後再試。')
        return c.execute('SELECT * FROM users WHERE id=?',(r['owner_id'],)).fetchone(),r

    def _limit(self,c,user):
        # 只重用既有scope，沒有擴大DB CHECK；公開來源/總容量仍是獨立部署Gate。
        if self.limiter.enabled:
            for scope,key,limit,seconds in [('login_source_attempt','google:'+user['id'],30,900),('login_global_attempt','all',3000,86400)]:
                error=self.limiter.take(c,scope,key,limit,seconds)
                if error:raise error

    def challenge(self,token,csrf,mode,discard_guest=False):
        user,_=self.service.session(token,csrf,True)
        require(mode in ('login','upgrade'),422,'invalid_login_mode','請選擇登入方式。')
        require(mode!='upgrade' or user['status']=='guest',409,'already_registered','目前已是帳號；不自動連結其他Google身分。')
        nonce=secrets.token_urlsafe(32);identifier=str(uuid4())
        with self._write(user['id']) as c:
            user,_=self._session(c,token,csrf);self._limit(c,user)
            c.execute('SELECT provider FROM external_identities LIMIT 0') # 未批准初始化時fail-closed，不自動建表。
            cutoff=self.service.now()-timedelta(days=1)
            rows=c.execute('SELECT response FROM requests WHERE owner_id=? AND operation=?',(user['id'],CHALLENGE)).fetchall()
            require(sum(datetime.fromisoformat(json.loads(r['response'])['created_at'])>cutoff for r in rows)<100,429,'google_challenge_limit','今天的登入嘗試已達上限，請稍後再試。')
            payload={'binding':digest(token),'mode':mode,'discard_guest':discard_guest,'created_at':self.service.now().isoformat(),'expires_at':(self.service.now()+timedelta(minutes=5)).isoformat()}
            c.execute('INSERT INTO requests(owner_id,operation,request_id,fingerprint,response) VALUES (?,?,?,?,?)',(user['id'],CHALLENGE,identifier,digest(nonce),json.dumps(payload)))
        return {'challenge_id':identifier,'nonce':nonce,'expires_in':300,'client_id':self.verifier.client_id}

    def exchange(self,token,csrf,identifier,credential):
        user,_=self.service.session(token,csrf,True)
        # 憑證無論正誤均先消耗既有共享嘗試額度；不以email作來源。
        with self._write(user['id']) as c:self._limit(c,user)
        with self.db.connect() as c:
            row=c.execute('SELECT * FROM requests WHERE operation=? AND request_id=?',(CHALLENGE,identifier)).fetchone()
        require(row is not None,401,'challenge_required','請重新開始Google登入。')
        details=json.loads(row['response'])
        require(datetime.fromisoformat(details['expires_at'])>self.service.now(),401,'challenge_expired','登入請求已過期，請重新開始。')
        issuer,subject=self.verifier.verify(credential,row['fingerprint'])
        with self._write(user['id']) as c:
            user,_=self._session(c,token,csrf)
            if self.db.backend=='postgresql':
                # 跨owner爭同一Google身分也序列化；SQLite BEGIN IMMEDIATE已序列化所有寫入。
                key=int.from_bytes(hashlib.sha256((issuer+'\0'+subject).encode()).digest()[:8],'big',signed=True)
                c.execute('SELECT pg_advisory_xact_lock(?)',(key,))
            consumed=c.execute('SELECT response FROM requests WHERE owner_id=? AND operation=? AND request_id=?',(row['owner_id'],EXCHANGE,identifier)).fetchone()
            if consumed:
                saved=json.loads(consumed['response'])
                require(saved['owner_id']==user['id'] and saved['session_hash']==digest(token) and saved['credential_hash']==digest(credential),409,'challenge_used','此登入請求已使用，請重新開始。')
                return self.service.public_user(user,csrf),None,True
            # 驗簽或等待跨裝置鎖期間也可能逾時；提交前必須再驗到期，拒絕晚到交換。
            require(datetime.fromisoformat(details['expires_at'])>self.service.now(),401,'challenge_expired','登入請求已過期，請重新開始。')
            require(user['id']==row['owner_id'] and secrets.compare_digest(details['binding'],digest(token)),403,'challenge_binding','登入請求不屬於此工作階段。')
            identity=c.execute('SELECT owner_id FROM external_identities WHERE provider=? AND issuer=? AND subject=?',('google',issuer,subject)).fetchone()
            if details['mode']=='upgrade':
                require(user['status']=='guest',409,'already_registered','帳號已變更，請重新開始。')
                require(identity is None or identity['owner_id']==user['id'],409,'external_owner_conflict','此Google帳號已有另一個世界；不會自動合併。')
                owner=user['id']
                c.execute("UPDATE users SET status='registered' WHERE id=?",(owner,))
            else:
                # 「登入以前的世界」只接受既有身分；新使用者必須明確upgrade原訪客世界。
                require(identity is not None,404,'google_world_not_found','此Google帳號尚無既有世界；請選擇保存目前世界，不會建立或清除任何世界。')
                owner=identity['owner_id']
                require(user['status']!='guest' or owner==user['id'] or details['discard_guest'],409,'guest_conflict','登入以前的世界前，請明確同意放棄目前訪客資料；不會合併，至少14天後才符合永久清除條件。')
            if identity is None:c.execute('INSERT INTO external_identities(provider,issuer,subject,owner_id,created_at) VALUES (?,?,?,?,?)',('google',issuer,subject,owner,self.service.now().isoformat()))
            if details['mode']=='login' and details['discard_guest'] and user['status']=='guest' and owner!=user['id']:
                from .guest_lifecycle import abandon
                abandon(c,user['id'],self.service.now())
            # 未明確放棄時，只輪替當前瀏覽器的Session。
            c.execute('DELETE FROM sessions WHERE token_hash=?',(digest(token),))
            session,new_csrf=new_session(c,owner,self.service.now(),self.service.policy)
            receipt={'owner_id':owner,'mode':details['mode'],'source_owner_id':user['id'],'guest_abandoned':details['mode']=='login' and bool(details['discard_guest']) and user['status']=='guest' and owner!=user['id'],'credential_hash':digest(credential),'session_hash':digest(session)}
            c.execute('INSERT INTO requests(owner_id,operation,request_id,fingerprint,response) VALUES (?,?,?,?,?)',(row['owner_id'],EXCHANGE,identifier,digest(credential),json.dumps(receipt)))
            result=self.service.public_user(c.execute('SELECT * FROM users WHERE id=?',(owner,)).fetchone(),new_csrf)
        return result,session,False

    def status(self,token,csrf,identifier):
        """讀取本次交換是否已提交；只授權當前Session，永不重做交換或放棄。"""
        current,_=self.service.session(token,csrf,True)
        # 與交換共用owner交易鎖；到期且無收據時，不能有舊交易稍後才提交。
        with self._write(current['id']) as c:
            user,_=self._session(c,token,csrf)
            challenge=c.execute('SELECT * FROM requests WHERE operation=? AND request_id=?',(CHALLENGE,identifier)).fetchone()
            require(challenge is not None,404,'challenge_required','找不到此登入請求。')
            done=c.execute('SELECT response FROM requests WHERE owner_id=? AND operation=? AND request_id=?',(challenge['owner_id'],EXCHANGE,identifier)).fetchone()
            if done:
                receipt=json.loads(done['response'])
                require(receipt['owner_id']==user['id'] and secrets.compare_digest(receipt['session_hash'],digest(token)),403,'challenge_binding','登入結果不屬於此工作階段。')
                details=json.loads(challenge['response'])
                return {'status':'committed','mode':receipt.get('mode',details['mode']),'source_owner_id':challenge['owner_id'],'owner_id':user['id'],'guest_abandoned':receipt.get('guest_abandoned',False)}
            require(challenge['owner_id']==user['id'] and secrets.compare_digest(json.loads(challenge['response'])['binding'],digest(token)),403,'challenge_binding','登入請求不屬於此工作階段。')
            return {'status':'not_committed','owner_id':user['id'],'expired':datetime.fromisoformat(json.loads(challenge['response'])['expires_at'])<=self.service.now()}
