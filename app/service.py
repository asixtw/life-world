"""Domain operations. Every confirmation is one SQLite transaction."""  # 說明此模組的責任與實作邊界
from datetime import datetime, timedelta, timezone  # 處理 UTC、發生時間與期限
from decimal import Decimal  # 以精確十進位處理貢獻量，避免浮點誤差
from io import BytesIO  # 將圖片內容包裝成記憶體檔案
from pathlib import PurePath  # 以跨平台方式組合檔案路徑
from uuid import uuid4  # 產生不依賴名稱的唯一識別碼
from zoneinfo import ZoneInfo  # 使用 IANA 時區轉換日期與時間
import hashlib  # 計算工作階段、圖片或請求內容的雜湊
import json  # 序列化資料與還原資料庫中的清單
import secrets  # 產生隨機驗證代碼並進行固定時間比較
import sqlite3  # 讀寫 SQLite、執行遷移與一致性備份
import warnings  # 將過大圖片的解壓縮警告改為拒絕

from PIL import Image, UnidentifiedImageError  # 解析並驗證實際圖片內容

from .ai import ManualAssistant  # 使用保留原文的手動整理提供者
from .errors import DomainError, require  # 共用領域錯誤與條件檢查
from .schemas import format_decimal  # 載入領域輸入模型或十進位格式工具
from .security import PASSWORDS, DUMMY_HASH, digest, new_session, require_registered  # 共用密碼、工作階段與帳號權限檢查
from .people import PeopleMixin  # 載入人物來源與互動事件服務擴充
from .connections import ConnectionsMixin  # 載入逐經歷人物角色與故事探索服務


def uid():  # 產生不依賴名稱的固定唯一識別碼
    return str(uuid4())  # 回傳產生不依賴名稱的固定唯一識別碼的結果


def encoded(value):  # 以穩定鍵序序列化 JSON，供指紋與資料保存使用
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))  # 回傳以穩定鍵序序列化 JSON，供指紋與資料保存使用的結果


class LifeWorld(ConnectionsMixin, PeopleMixin):  # 目標、故事、人物、積分與身分共用交易服務
    def __init__(self, db, policy, clock=None, assistant=None):  # 注入資料庫、設定、時鐘與整理提供者
        self.db = db  # 保存「self.db」供後續驗證或回傳使用
        self.policy = policy  # 保存「self.policy」供後續驗證或回傳使用
        self.clock = clock or (lambda: datetime.now(timezone.utc))  # 保存「self.clock」供後續驗證或回傳使用
        self.assistant = assistant or ManualAssistant()  # 保存「self.assistant」供後續驗證或回傳使用

    def now(self):  # 取得可注入測試時鐘的 UTC 時間
        return self.clock().astimezone(timezone.utc)  # 回傳取得可注入測試時鐘的 UTC 時間的結果

    def session(self, token, csrf=None, write=False):  # 核對登入期限，寫入操作另檢查 CSRF
        require(bool(token), 401, 'session_required', '請先開始訪客旅程或登入。')  # 驗證限制：請先開始訪客旅程或登入。
        with self.db.connect() as c:  # 在同一讀取交易取得一致資料
            session = c.execute('SELECT * FROM sessions WHERE token_hash=?', (digest(token),)).fetchone()  # 執行目前交易中的參數化查詢
            require(session is not None and datetime.fromisoformat(session['expires_at']) > self.now(),
                    401, 'session_expired', '登入狀態已失效，請重新登入。')  # 驗證限制：登入狀態已失效，請重新登入。
            if write:  # 依目前條件選擇下一步處理分支
                require(bool(csrf) and secrets.compare_digest(csrf, session['csrf_token']),
                        403, 'csrf_failed', '安全驗證已失效，請重新整理後再試。')  # 驗證限制：安全驗證已失效，請重新整理後再試。
            user = dict(c.execute('SELECT * FROM users WHERE id=?', (session['owner_id'],)).fetchone())  # 執行目前交易中的參數化查詢
            return user, session['csrf_token']  # 回傳核對登入期限，寫入操作另檢查 CSRF的結果

    @staticmethod  # 此共用檢查不需要讀取物件狀態
    def public_user(user, csrf=None):  # 只回傳介面需要的公開帳號欄位
        result = {k: user[k] for k in ('status', 'username', 'name', 'bio', 'timezone')}  # 準備本次操作的回傳資料
        result.update(owner_id=user['id'], lumi_hatched=bool(user['hatched_at']))  # 合併本次明確設定的欄位
        if csrf:  # 依目前條件選擇下一步處理分支
            result['csrf_token'] = csrf  # 保存「result['csrf_token']」供後續驗證或回傳使用
        return result  # 回傳只回傳介面需要的公開帳號欄位的結果

    def guest(self, token):  # 取得既有訪客身分或建立新的訪客世界
        if token:  # 依目前條件選擇下一步處理分支
            try:  # 保護可能失敗的操作，交由下方例外分支處理
                user, csrf = self.session(token)  # 核對登入期限，寫入操作另檢查 CSRF
                return self.public_user(user, csrf), None, False  # 回傳取得既有訪客身分或建立新的訪客世界的結果
            except DomainError as exc:  # 處理此類預期例外並保留明確失敗結果
                if exc.status != 401:  # 依目前條件選擇下一步處理分支
                    raise  # 中止目前操作並向呼叫端傳遞錯誤
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            owner = uid()  # 準備目前資料所屬帳號識別碼
            c.execute("INSERT INTO users (id,status,created_at) VALUES (?,'guest',?)", (owner, self.now().isoformat()))  # 新增帳號與個人介紹；值以參數傳入
            token, csrf = new_session(c, owner, self.now(), self.policy)  # 產生隨機工作階段及 CSRF 代碼，資料庫僅存工作階段雜湊
            user = c.execute('SELECT * FROM users WHERE id=?', (owner,)).fetchone()  # 執行目前交易中的參數化查詢
            return self.public_user(user, csrf), token, True  # 回傳取得既有訪客身分或建立新的訪客世界的結果

    def profile(self, owner, data):  # 保存個人介紹與時區
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            c.execute('UPDATE users SET name=?,bio=?,timezone=? WHERE id=?', (data.name, data.bio, data.timezone, owner))  # 更新帳號與個人介紹；值以參數傳入
            return self.public_user(c.execute('SELECT * FROM users WHERE id=?', (owner,)).fetchone())  # 執行目前交易中的參數化查詢

    def claim(self, user, data):  # 將原訪客世界升級為本機帳號並輪換工作階段
        require(user['status'] == 'guest', 409, 'already_registered', '目前已是本機帳號。')  # 驗證限制：目前已是本機帳號。
        password_hash = PASSWORDS.hash(data.password)  # 以密碼雜湊保存認證資料，不儲存明文
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            current = self._owned_user(c, user['id'])  # 準備交易內重新讀取的帳號狀態
            require(current['status'] == 'guest', 409, 'already_registered', '帳號狀態已變更，請重新整理。')  # 驗證限制：帳號狀態已變更，請重新整理。
            require(not c.execute('SELECT 1 FROM users WHERE username=?', (data.username,)).fetchone(),
                    409, 'username_taken', '此帳號名稱已使用；請改名，或登入既有帳號。')  # 驗證限制：此帳號名稱已使用；請改名，或登入既有帳號。
            c.execute("UPDATE users SET status='registered',username=?,password_hash=? WHERE id=?",
                      (data.username, password_hash, user['id']))  # 更新帳號與個人介紹；值以參數傳入
            c.execute('DELETE FROM sessions WHERE owner_id=?', (user['id'],))  # 刪除登入工作階段；值以參數傳入
            token, csrf = new_session(c, user['id'], self.now(), self.policy)  # 產生隨機工作階段及 CSRF 代碼，資料庫僅存工作階段雜湊
            return self.public_user(self._owned_user(c, user['id']), csrf), token  # 回傳將原訪客世界升級為本機帳號並輪換工作階段的結果

    def login(self, data, existing_token=None):  # 核對密碼並建立工作階段，不合併訪客資料
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            user = c.execute('SELECT * FROM users WHERE username=?', (data.username.lower(),)).fetchone()  # 執行目前交易中的參數化查詢
            valid = PASSWORDS.verify(data.password, user['password_hash'] if user else DUMMY_HASH)  # 核對雜湊密碼；未知帳號仍使用替代雜湊
            require(user is not None and valid, 401, 'invalid_credentials', '帳號或密碼不正確。')  # 驗證限制：帳號或密碼不正確。
            if existing_token:  # 依目前條件選擇下一步處理分支
                old = c.execute('SELECT s.*,u.status FROM sessions s JOIN users u ON u.id=s.owner_id WHERE token_hash=?',
                                (digest(existing_token),)).fetchone()  # 查詢登入工作階段；值以參數傳入
                if old and datetime.fromisoformat(old['expires_at']) > self.now() and old['owner_id'] != user['id'] and old['status'] == 'guest':  # 依目前條件選擇下一步處理分支
                    require(data.discard_guest, 409, 'guest_conflict',
                            '此裝置有訪客世界。登入不會合併資料；若離開訪客身分，可能無法再次取回。')  # 驗證限制：此裝置有訪客世界。登入不會合併資料；若離開訪客身分，可能無法再次取回。
                c.execute('DELETE FROM sessions WHERE token_hash=?', (digest(existing_token),))  # 刪除登入工作階段；值以參數傳入
            token, csrf = new_session(c, user['id'], self.now(), self.policy)  # 產生隨機工作階段及 CSRF 代碼，資料庫僅存工作階段雜湊
            return self.public_user(user, csrf), token  # 回傳核對密碼並建立工作階段，不合併訪客資料的結果

    def logout(self, token):  # 撤銷目前工作階段
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            c.execute('DELETE FROM sessions WHERE token_hash=?', (digest(token),))  # 刪除登入工作階段；值以參數傳入

    @staticmethod  # 此共用檢查不需要讀取物件狀態
    def _owned_user(c, owner):  # 要求帳號存在
        user = c.execute('SELECT * FROM users WHERE id=?', (owner,)).fetchone()  # 執行目前交易中的參數化查詢
        require(user is not None, 401, 'session_required', '使用者不存在。')  # 驗證限制：使用者不存在。
        return user  # 回傳要求帳號存在的結果

    def _onboarded(self, c, owner):  # 要求先建立 Bio 與第一個目標蛋
        user = self._owned_user(c, owner)  # 準備目前帳號及其身分資料
        require(bool(user['hatched_at']), 409, 'first_goal_required', '請先填寫 Bio 並建立第一個目標蛋。')  # 驗證限制：請先填寫 Bio 並建立第一個目標蛋。
        return user  # 回傳要求先建立 Bio 與第一個目標蛋的結果

    @staticmethod  # 此共用檢查不需要讀取物件狀態
    def _owned(c, table, item_id, owner):  # 限制查詢資料表並核對資源所屬帳號
        assert table in {'goals', 'people', 'drafts', 'evidence', 'notes', 'tasks'}  # 限制動態資料表或欄位名稱為程式內白名單
        row = c.execute('SELECT * FROM ' + table + ' WHERE id=? AND owner_id=?', (item_id, owner)).fetchone()  # 依白名單資料表、識別碼與所屬帳號查詢資源
        require(row is not None, 404, 'not_found', '找不到可存取的資料。')  # 驗證限制：找不到可存取的資料。
        return row  # 回傳限制查詢資料表並核對資源所屬帳號的結果

    @staticmethod  # 此共用檢查不需要讀取物件狀態
    def _cached(c, owner, operation, request_id, payload):  # 比較請求指紋，重送時回傳先前結果
        fingerprint = hashlib.sha256(encoded(payload).encode()).hexdigest()  # 準備穩定內容指紋
        row = c.execute('SELECT * FROM requests WHERE owner_id=? AND operation=? AND request_id=?',
                        (owner, operation, request_id)).fetchone()  # 執行目前交易中的參數化查詢
        if row:  # 依目前條件選擇下一步處理分支
            require(row['fingerprint'] == fingerprint, 409, 'idempotency_conflict', '同一提交代碼不能用於不同內容。')  # 驗證限制：同一提交代碼不能用於不同內容。
            return json.loads(row['response']), fingerprint  # 回傳比較請求指紋，重送時回傳先前結果的結果
        return None, fingerprint  # 回傳比較請求指紋，重送時回傳先前結果的結果

    @staticmethod  # 此共用檢查不需要讀取物件狀態
    def _remember(c, owner, operation, request_id, fingerprint, response):  # 在目前交易記錄提交代碼、指紋與回應
        c.execute('INSERT INTO requests VALUES (?,?,?,?,?)', (owner, operation, request_id, fingerprint, encoded(response)))  # 新增去重請求；值以參數傳入

    def create_goal(self, owner, data):  # 在同一交易建立目標、行動並孵化 Lumi
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            user = self._owned_user(c, owner)  # 準備目前帳號及其身分資料
            require(bool(user['bio'] and user['name']), 409, 'bio_required', '請先完成 Bio。')  # 驗證限制：請先完成 Bio。
            cached, fingerprint = self._cached(c, owner, 'goal:create', data.request_id, data.model_dump(mode='json'))  # 比較請求指紋，重送時回傳先前結果
            if cached:  # 若為相同提交重送，沿用已保存結果
                return cached  # 回傳先前成功結果，避免重送造成重複寫入
            goal_id, now = uid(), self.now().isoformat()  # 保存「(goal_id, now)」供後續驗證或回傳使用
            c.execute("INSERT INTO goals (id,owner_id,title,outcome,status,created_at) VALUES (?,?,?,?,'active',?)",
                      (goal_id, owner, data.title, data.outcome, now))  # 新增目標；值以參數傳入
            for position, action in enumerate(data.actions):  # 逐項處理清單中的資料，保留目前交易或查詢條件
                c.execute('INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?)',
                          (uid(), goal_id, owner, action.title, action.unit, action.target, action.level, encoded(action.weekdays), position))  # 新增目標行動；值以參數傳入
            c.execute('UPDATE users SET hatched_at=COALESCE(hatched_at,?) WHERE id=?', (now, owner))  # 更新帳號與個人介紹；值以參數傳入
            result = self._goal(c, goal_id, owner)  # 準備本次操作的回傳資料
            self._remember(c, owner, 'goal:create', data.request_id, fingerprint, result)  # 把成功回應與去重提交代碼一起記入交易
            return result  # 回傳在同一交易建立目標、行動並孵化 Lumi的結果

    def _goal(self, c, goal_id, owner):  # 組合目標、行動與精確十進位累計
        goal = dict(self._owned(c, 'goals', goal_id, owner))  # 準備目前選定的目標資料
        actions = []  # 準備依畫面順序組合的目標行動清單
        for row in c.execute('SELECT * FROM actions WHERE goal_id=? AND owner_id=? ORDER BY position', (goal_id, owner)):  # 執行目前交易中的參數化查詢
            action = dict(row)  # 準備目前行動與其精確累計
            action['weekdays'] = json.loads(action['weekdays'])  # 保存「action['weekdays']」供後續驗證或回傳使用
            quantities = c.execute('SELECT quantity FROM contributions WHERE action_id=? AND owner_id=?', (action['id'], owner)).fetchall()  # 查詢行動貢獻；值以參數傳入
            action['progress'] = format_decimal(sum((Decimal(v['quantity']) for v in quantities), Decimal(0)))  # 輸出無科學記號且去除多餘尾零的十進位字串
            actions.append(action)  # 將目前資料加入結果清單
        goal['actions'] = actions  # 保存「goal['actions']」供後續驗證或回傳使用
        goal['evidence'] = [dict(r) for r in c.execute('SELECT id,filename,mime,size,created_at FROM evidence WHERE goal_id=? AND owner_id=? ORDER BY created_at,id', (goal_id, owner))]  # 查詢圖片佐證；值以參數傳入
        return goal  # 回傳組合目標、行動與精確十進位累計的結果

    def goal(self, owner, goal_id):  # 讀取目標及其行動累計
        with self.db.connect() as c:  # 在同一讀取交易取得一致資料
            self._onboarded(c, owner)  # 要求先建立 Bio 與第一個目標蛋
            return self._goal(c, goal_id, owner)  # 回傳讀取目標及其行動累計的結果

    def calendar(self, owner, goal_id):  # 依目前每週規律產生 28 日預覽；月週期另項實作
        with self.db.connect() as c:  # 在同一讀取交易取得一致資料
            user = self._onboarded(c, owner)  # 準備目前帳號及其身分資料
            goal = self._goal(c, goal_id, owner)  # 準備目前選定的目標資料
            start = self.now().astimezone(ZoneInfo(user['timezone'])).date()  # 準備帳號當地時區的排程預覽起始日期
            return [{'date': (start + timedelta(days=i)).isoformat(),
                     'action_ids': [a['id'] for a in goal['actions'] if (start + timedelta(days=i)).weekday() in a['weekdays']]}
                    for i in range(28)]  # 回傳依目前每週規律產生 28 日預覽；月週期另項實作的結果

    def _related(self, c, user, goal_id, person_id, contributions):  # 驗證目標、人物與行動貢獻的權限及相互關聯
        if goal_id:  # 依目標是否存在及其狀態選擇處理方式
            self._owned(c, 'goals', goal_id, user['id'])  # 限制查詢資料表並核對資源所屬帳號
        if person_id:  # 依人物選擇或人物資料狀態套用限制
            require_registered(user)  # 驗證限制：條件不成立即拒絕操作，避免部分寫入
            self._owned(c, 'people', person_id, user['id'])  # 限制查詢資料表並核對資源所屬帳號
        for contribution in contributions:  # 逐項處理清單中的資料，保留目前交易或查詢條件
            action = c.execute('SELECT * FROM actions WHERE id=? AND owner_id=?', (contribution.action_id, user['id'])).fetchone()  # 執行目前交易中的參數化查詢
            require(action is not None and action['goal_id'] == goal_id, 422, 'invalid_action', '貢獻行動必須屬於本次選擇的目標。')  # 驗證限制：貢獻行動必須屬於本次選擇的目標。

    def _valid_time(self, occurred_at):  # 拒絕尚未發生的真實經歷
        require(occurred_at.astimezone(timezone.utc) <= self.now(), 422, 'future_event', '真實經歷的發生時間不能在未來。')  # 驗證限制：真實經歷的發生時間不能在未來。

    def create_draft(self, owner, data):  # 保存尚未確認、不計分的原始經歷草稿
        self._valid_time(data.occurred_at)  # 拒絕尚未發生的真實經歷
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            user = self._onboarded(c, owner)  # 準備目前帳號及其身分資料
            self._related(c, user, data.goal_id, data.person_id, data.contributions)  # 驗證目標、人物與行動貢獻的權限及相互關聯
            draft_id, now = uid(), self.now().isoformat()  # 保存「(draft_id, now)」供後續驗證或回傳使用
            c.execute("INSERT INTO drafts VALUES (?,?,?,?,?,?,?,'draft',1,?,?)",
                      (draft_id, owner, data.goal_id, data.person_id, data.raw_text,
                       data.occurred_at.astimezone(timezone.utc).isoformat(), encoded([v.model_dump() for v in data.contributions]), now, now))  # 新增經歷草稿；值以參數傳入
            self._store_draft_story(c, owner, draft_id, data.raw_text, data.story)  # 同交易保存未確認的人物整理
            return self._draft(c, owner, draft_id)  # 回傳保存尚未確認、不計分的原始經歷草稿的結果

    def _draft(self, c, owner, draft_id):  # 讀取有權限的草稿並還原貢獻清單
        result = dict(self._owned(c, 'drafts', draft_id, owner))  # 準備本次操作的回傳資料
        result['contributions'] = json.loads(result['contributions'])  # 保存「result['contributions']」供後續驗證或回傳使用
        story = c.execute('SELECT payload FROM draft_stories WHERE draft_id=?', (draft_id,)).fetchone()  # 回讀未確認的多人整理
        result['story'] = json.loads(story[0]) if story else None  # 舊草稿仍可正常讀取
        return result  # 回傳讀取有權限的草稿並還原貢獻清單的結果

    def draft(self, owner, draft_id):  # 讀取原始草稿與人工貢獻設定
        with self.db.connect() as c:  # 在同一讀取交易取得一致資料
            self._onboarded(c, owner)  # 要求先建立 Bio 與第一個目標蛋
            return self._draft(c, owner, draft_id)  # 回傳讀取原始草稿與人工貢獻設定的結果

    def edit_draft(self, owner, draft_id, data):  # 檢查版本後更新尚未確認的草稿
        self._valid_time(data.occurred_at)  # 拒絕尚未發生的真實經歷
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            user = self._onboarded(c, owner)  # 準備目前帳號及其身分資料
            draft = self._draft(c, owner, draft_id)  # 準備目前尚未確認的原始經歷
            require(draft['status'] == 'draft', 409, 'already_confirmed', '已確認的原始紀錄不可用草稿方式修改。')  # 驗證限制：已確認的原始紀錄不可用草稿方式修改。
            require(draft['revision'] == data.expected_revision, 409, 'revision_conflict', '草稿已有新版，請重新載入。')  # 驗證限制：草稿已有新版，請重新載入。
            self._related(c, user, data.goal_id, data.person_id, data.contributions)  # 驗證目標、人物與行動貢獻的權限及相互關聯
            if 'story' in data.model_fields_set: self._store_draft_story(c, owner, draft_id, data.raw_text, data.story)  # 明確送出時才取代角色整理
            elif draft['story'] is not None:  # 舊客戶端編輯原文時仍需保護來源位置
                from .schemas import StoryInput  # 僅為相容更新還原已保存型別
                self._validate_story(c, owner, data.raw_text, StoryInput.model_validate(draft['story']))  # 不默默保留失效片段
            c.execute('UPDATE drafts SET raw_text=?,occurred_at=?,goal_id=?,person_id=?,contributions=?,revision=revision+1,updated_at=? WHERE id=? AND owner_id=?',
                      (data.raw_text, data.occurred_at.astimezone(timezone.utc).isoformat(), data.goal_id, data.person_id,
                       encoded([v.model_dump() for v in data.contributions]), self.now().isoformat(), draft_id, owner))  # 更新經歷草稿；值以參數傳入
            return self._draft(c, owner, draft_id)  # 回傳檢查版本後更新尚未確認的草稿的結果

    def suggest(self, owner, draft_id):  # 建立可手動審閱的整理候選，不寫入正式事實
        draft = self.draft(owner, draft_id)  # 準備目前尚未確認的原始經歷
        require(draft['status'] == 'draft', 409, 'already_confirmed', '這份草稿已經確認。')  # 驗證限制：這份草稿已經確認。
        try:  # 保護可能失敗的操作，交由下方例外分支處理
            return self.assistant.suggest(draft['raw_text'])  # 回傳建立可手動審閱的整理候選，不寫入正式事實的結果
        except Exception:  # 處理此類預期例外並保留明確失敗結果
            raise DomainError(503, 'assistant_unavailable', '整理服務暫時不可用；原文已保存，可手動完成。')  # 中止目前操作並向呼叫端傳遞錯誤

    def _award(self, c, owner, experience_id, now):  # 新增唯一經歷積分帳目
        event_id = uid()  # 準備互動或積分事件的唯一識別碼
        c.execute('INSERT INTO reward_ledger VALUES (?,?,?,?,?,?)',
                  (event_id, owner, experience_id, self.policy.points_per_experience, self.policy.rule_version, now))  # 新增積分帳本；值以參數傳入
        return event_id  # 回傳新增唯一經歷積分帳目的結果

    def confirm(self, owner, draft_id, data):  # 以單一交易保存經歷、貢獻、人物更新與一次積分
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            user = self._onboarded(c, owner)  # 準備目前帳號及其身分資料
            draft = self._draft(c, owner, draft_id)  # 準備目前尚未確認的原始經歷
            payload = data.model_dump(mode='json')  # 準備將送出或用於指紋比對的完整內容
            for key in ('interaction_type', 'interaction_event_id', 'person_updates', 'story', 'story_reviewed'):  # 省略新版預設以維持舊提交指紋
                if payload[key] is None or payload[key] is False or payload[key] == 'unknown' or payload[key] == []:  # 僅移除未指定的新欄位
                    payload.pop(key)  # 移除未指定的新欄位，避免相同舊請求被誤判為內容衝突
            payload['draft_id'] = draft_id  # 保存「payload['draft_id']」供後續驗證或回傳使用
            cached, fingerprint = self._cached(c, owner, 'confirm', data.request_id, payload)  # 比較請求指紋，重送時回傳先前結果
            if cached:  # 若為相同提交重送，沿用已保存結果
                return cached  # 回傳先前成功結果，避免重送造成重複寫入
            require(draft['status'] == 'draft', 409, 'already_confirmed', '這份草稿已確認，不能重複計入。')  # 驗證限制：這份草稿已確認，不能重複計入。
            require(draft['revision'] == data.expected_revision, 409, 'revision_conflict', '草稿已有新版，請重新核對。')  # 驗證限制：草稿已有新版，請重新核對。
            self._related(c, user, draft['goal_id'], data.person_id, data.contributions)  # 驗證目標、人物與行動貢獻的權限及相互關聯
            if data.story is not None:  # 新版明確區分參與與提及
                require(data.story_reviewed, 422, 'story_review_required', '請先核對這段故事的人物參與及提及。')  # 不將候選直接轉成正式角色
                self._validate_story(c, owner, draft['raw_text'], data.story)  # 先核對全部來源與所有權
                require(not data.person_id or data.person_id in [p.person_id for p in data.story.participants], 422, 'primary_not_participant', '主要關聯人物必須是本次參與者；提及者請在提及區配對。')  # 避免舊主要人物欄位誤用身分
            if data.contributions and draft['goal_id']:  # 依目標是否存在及其狀態選擇處理方式
                goal = self._owned(c, 'goals', draft['goal_id'], owner)  # 準備目前選定的目標資料
                require(goal['status'] == 'active', 409, 'policy_required', '完成後的貢獻更正規則尚未定案；草稿已保留，可移除貢獻後只保存經歷。')  # 驗證限制：完成後的貢獻更正規則尚未定案；草稿已保留，可移除貢獻後只保存經歷。
            experience_id, now = uid(), self.now().isoformat()  # 保存「(experience_id, now)」供後續驗證或回傳使用
            c.execute('INSERT INTO experiences VALUES (?,?,?,?,?,?,?,?,?)',
                      (experience_id, owner, draft_id, draft['goal_id'], data.person_id,
                       draft['raw_text'], data.summary, draft['occurred_at'], now))  # 新增已確認經歷；值以參數傳入
            for item in data.contributions:  # 逐項處理清單中的資料，保留目前交易或查詢條件
                c.execute('INSERT INTO contributions VALUES (?,?,?,?,?)', (uid(), owner, experience_id, item.action_id, item.quantity))  # 新增行動貢獻；值以參數傳入
            for title in data.tasks:  # 逐項處理清單中的資料，保留目前交易或查詢條件
                c.execute('INSERT INTO tasks (id,owner_id,experience_id,title) VALUES (?,?,?,?)', (uid(), owner, experience_id, title))  # 新增下一步待辦；值以參數傳入
            c.execute('INSERT INTO experience_stories(experience_id,owner_id) VALUES (?,?)', (experience_id, owner))  # 舊 API 先保留待核對狀態
            if data.story is not None: self._write_story(c, owner, experience_id, draft['raw_text'], data.story)  # 正式保存逐經歷角色
            event_id = self._attach_story_event(c, owner, experience_id, data.story, data, draft['occurred_at']) if data.story is not None else self._attach_interaction(c, owner, experience_id, data.person_id, data, draft['occurred_at'])  # 新角色只計直接互動，舊行為相容
            self._apply_person_updates(c, owner, data.person_id, experience_id, data.person_updates)  # 僅套用明確勾選的人物更新；任何失敗皆回滾
            reward_id = self._award(c, owner, experience_id, now)  # 只為本次已確認經歷新增一次積分帳目
            c.execute("UPDATE drafts SET status='confirmed',updated_at=? WHERE id=? AND owner_id=?", (now, draft_id, owner))  # 更新經歷草稿；值以參數傳入
            result = {'experience_id': experience_id, 'reward_event_id': reward_id, 'points_awarded': self.policy.points_per_experience,
                      'rule_version': self.policy.rule_version, 'confirmed_at': now}  # 準備本次操作的回傳資料
            if event_id:  # 依目前條件選擇下一步處理分支
                result['interaction_event_id'] = event_id  # 保存「result['interaction_event_id']」供後續驗證或回傳使用
            self._remember(c, owner, 'confirm', data.request_id, fingerprint, result)  # 把成功回應與去重提交代碼一起記入交易
            return result  # 回傳以單一交易保存經歷、貢獻、人物更新與一次積分的結果

    def create_person(self, owner, data):  # 建立人物並保留舊角色欄位的相容性
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            user = self._onboarded(c, owner)  # 準備目前帳號及其身分資料
            require_registered(user)  # 驗證限制：條件不成立即拒絕操作，避免部分寫入
            person_id = uid()  # 準備新人物的唯一識別碼
            roles = data.roles or ([data.role] if data.role else [])  # 準備多角色清單；未提供新欄位時沿用舊角色完整文字
            c.execute('''INSERT INTO people(id,owner_id,name,role,notes,created_at,roles,tags,category,followed,common_context)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                      (person_id, owner, data.name, data.role or '、'.join(roles), data.notes, self.now().isoformat(),
                       encoded(roles), encoded(data.tags), data.category, int(data.followed), data.common_context))  # 新增人物基本資料；值以參數傳入
            return self._person(c, owner, person_id)  # 回傳建立人物並保留舊角色欄位的相容性的結果

    def upload(self, owner, goal_id, filename, mime, content):  # 驗證權限與圖片內容後保存目標佐證
        # Authorize before parsing the content, and recheck within the write transaction.
        self.goal(owner, goal_id)  # 讀取目標及其行動累計
        require(bool(filename) and '\\' not in filename and PurePath(filename).name == filename and len(filename) <= 200,
                422, 'invalid_filename', '請使用不含路徑的圖片檔名。')  # 驗證限制：請使用不含路徑的圖片檔名。
        require(bool(content), 422, 'empty_upload', '圖片不可為空。')  # 驗證限制：圖片不可為空。
        require(len(content) <= self.policy.max_upload_bytes, 413, 'upload_too_large', '圖片超過開發設定的上限。')  # 驗證限制：圖片超過開發設定的上限。
        accepted = {'image/png': 'PNG', 'image/jpeg': 'JPEG'}  # 準備上傳 MIME 類型與實際圖片格式的對照
        require(mime in accepted, 415, 'unsupported_media', '目前支援 PNG 與 JPEG 圖片。')  # 驗證限制：目前支援 PNG 與 JPEG 圖片。
        try:  # 保護可能失敗的操作，交由下方例外分支處理
            with warnings.catch_warnings():  # 以區塊生命週期確保資源在結束時關閉
                warnings.simplefilter('error', Image.DecompressionBombWarning)  # 執行此模組的共用工具操作
                with Image.open(BytesIO(content)) as image:  # 以區塊生命週期確保資源在結束時關閉
                    if image.format != accepted[mime] or image.width * image.height > 16000000:  # 依目前條件選擇下一步處理分支
                        raise ValueError('Image format or dimensions rejected')  # 中止目前操作並向呼叫端傳遞錯誤
                    image.verify()  # 檢查實際圖片結構，拒絕只有副檔名或 MIME 看似正確的損毀檔案
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):  # 處理此類預期例外並保留明確失敗結果
            raise DomainError(415, 'invalid_image', '圖片格式不符或檔案已損毀。')  # 中止目前操作並向呼叫端傳遞錯誤
        checksum = hashlib.sha256(content).hexdigest()  # 準備上傳內容的 SHA-256 指紋
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            goal = self._owned(c, 'goals', goal_id, owner)  # 準備目前選定的目標資料
            require(goal['status'] == 'active', 409, 'goal_completed', '完成後新增佐證的規則尚未開放。')  # 驗證限制：完成後新增佐證的規則尚未開放。
            old = c.execute('SELECT id,filename,mime,size,created_at FROM evidence WHERE owner_id=? AND goal_id=? AND digest=?',
                            (owner, goal_id, checksum)).fetchone()  # 查詢圖片佐證；值以參數傳入
            if old:  # 依目前條件選擇下一步處理分支
                return dict(old)  # 回傳驗證權限與圖片內容後保存目標佐證的結果
            evidence_id, now = uid(), self.now().isoformat()  # 保存「(evidence_id, now)」供後續驗證或回傳使用
            c.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?)',
                      (evidence_id, owner, goal_id, filename, mime, checksum, content, len(content), now))  # 新增圖片佐證；值以參數傳入
            return {'id': evidence_id, 'filename': filename, 'mime': mime, 'size': len(content), 'created_at': now}  # 回傳驗證權限與圖片內容後保存目標佐證的結果

    def evidence(self, owner, evidence_id):  # 讀取所屬帳號可存取的佐證內容
        with self.db.connect() as c:  # 在同一讀取交易取得一致資料
            self._onboarded(c, owner)  # 要求先建立 Bio 與第一個目標蛋
            return dict(self._owned(c, 'evidence', evidence_id, owner))  # 回傳讀取所屬帳號可存取的佐證內容的結果

    def complete(self, owner, goal_id, data):  # 檢查佐證與人工確認後收藏目標成果
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            self._onboarded(c, owner)  # 要求先建立 Bio 與第一個目標蛋
            goal = self._owned(c, 'goals', goal_id, owner)  # 準備目前選定的目標資料
            payload = dict(data.model_dump(mode='json'), goal_id=goal_id)  # 準備將送出或用於指紋比對的完整內容
            cached, fingerprint = self._cached(c, owner, 'goal:complete', data.request_id, payload)  # 比較請求指紋，重送時回傳先前結果
            if cached:  # 若為相同提交重送，沿用已保存結果
                return cached  # 回傳先前成功結果，避免重送造成重複寫入
            require(goal['status'] == 'active', 409, 'already_completed', '這個目標已完成。')  # 驗證限制：這個目標已完成。
            for evidence_id in data.evidence_ids:  # 逐項處理清單中的資料，保留目前交易或查詢條件
                evidence = self._owned(c, 'evidence', evidence_id, owner)  # 限制查詢資料表並核對資源所屬帳號
                require(evidence['goal_id'] == goal_id, 404, 'not_found', '找不到此目標的佐證。')  # 驗證限制：找不到此目標的佐證。
            completion_id, now = uid(), self.now().isoformat()  # 保存「(completion_id, now)」供後續驗證或回傳使用
            c.execute('INSERT INTO completions VALUES (?,?,?,?,?,?)',
                      (completion_id, owner, goal_id, encoded(data.evidence_ids), data.reflection, now))  # 新增目標完成紀錄；值以參數傳入
            c.execute("UPDATE goals SET status='completed',completed_at=?,reflection=? WHERE id=? AND owner_id=?", (now, data.reflection, goal_id, owner))  # 更新目標；值以參數傳入
            result = {'completion_id': completion_id, 'goal_id': goal_id, 'status': 'completed', 'evidence_ids': data.evidence_ids, 'confirmed_at': now}  # 準備本次操作的回傳資料
            self._remember(c, owner, 'goal:complete', data.request_id, fingerprint, result)  # 把成功回應與去重提交代碼一起記入交易
            return result  # 回傳檢查佐證與人工確認後收藏目標成果的結果

    def create_note(self, owner, data):  # 保存私人準備、模擬或訊息草稿，不改正式成果
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            user = self._onboarded(c, owner)  # 準備目前帳號及其身分資料
            if data.person_id:  # 依人物選擇或人物資料狀態套用限制
                require_registered(user)  # 驗證限制：條件不成立即拒絕操作，避免部分寫入
                self._owned(c, 'people', data.person_id, owner)  # 限制查詢資料表並核對資源所屬帳號
            for source_id in data.source_experience_ids:  # 逐項處理清單中的資料，保留目前交易或查詢條件
                self._source_experience(c, owner, source_id, [data.person_id] if data.person_id else None)  # 驗證引用來源確屬此帳號及相關人物
            note_id, now = uid(), self.now().isoformat()  # 保存「(note_id, now)」供後續驗證或回傳使用
            c.execute('INSERT INTO notes VALUES (?,?,?,?,?,?,?)', (note_id, owner, data.person_id, data.kind, data.title, data.content, now))  # 新增私人筆記；值以參數傳入
            for source_id in set(data.source_experience_ids):  # 逐項處理清單中的資料，保留目前交易或查詢條件
                c.execute('INSERT INTO note_sources VALUES (?,?)', (note_id, source_id))  # 新增私人筆記引用來源；值以參數傳入
            return dict(self._owned(c, 'notes', note_id, owner), source_experience_ids=data.source_experience_ids)  # 回傳保存私人準備、模擬或訊息草稿，不改正式成果的結果

    def edit_task(self, owner, task_id, data):  # 更新待辦，不重複增加積分或行動進度
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            self._onboarded(c, owner)  # 要求先建立 Bio 與第一個目標蛋
            self._owned(c, 'tasks', task_id, owner)  # 限制查詢資料表並核對資源所屬帳號
            c.execute('UPDATE tasks SET done=? WHERE id=? AND owner_id=?', (int(data.done), task_id, owner))  # 更新下一步待辦；值以參數傳入
            return dict(self._owned(c, 'tasks', task_id, owner))  # 回傳更新待辦，不重複增加積分或行動進度的結果

    def state(self, owner):  # 組合目前帳號的世界資料與開發設定
        with self.db.connect() as c:  # 在同一讀取交易取得一致資料
            user = self._onboarded(c, owner)  # 準備目前帳號及其身分資料
            goals = [self._goal(c, r['id'], owner) for r in c.execute('SELECT id FROM goals WHERE owner_id=? ORDER BY created_at,id', (owner,)).fetchall()]  # 查詢目標；值以參數傳入
            people = []  # 準備經權限或篩選條件限制的人物清單
            for row in c.execute('SELECT id FROM people WHERE owner_id=? ORDER BY created_at,id', (owner,)).fetchall():  # 查詢人物基本資料；值以參數傳入
                people.append(self._person(c, owner, row['id']))  # 將目前資料加入結果清單
            rewards = [dict(r) for r in c.execute('SELECT * FROM reward_ledger WHERE owner_id=? ORDER BY created_at,id', (owner,))]  # 執行目前交易中的參數化查詢
            return {'user': self.public_user(user), 'lumi': {'hatched': True, 'hatched_at': user['hatched_at'], 'care_state': 'neutral'},
                    'goals': goals, 'people': people,
                    'drafts': [self._draft(c, owner, r['id']) for r in c.execute("SELECT id FROM drafts WHERE owner_id=? AND status='draft' ORDER BY updated_at DESC,id", (owner,)).fetchall()],
                    'experiences': [dict(r) for r in c.execute('SELECT * FROM experiences WHERE owner_id=? ORDER BY occurred_at DESC,id', (owner,))],
                    'tasks': [dict(r) for r in c.execute('SELECT * FROM tasks WHERE owner_id=? ORDER BY id', (owner,))],
                    'notes': self._notes(c, owner),
                    'rewards': {'total': sum(r['points'] for r in rewards), 'events': rewards},
                    'policy': {'mode': 'local-development', 'rule_version': self.policy.rule_version,
                               'points_per_experience': self.policy.points_per_experience, 'max_upload_bytes': self.policy.max_upload_bytes,
                               'allowed_mime_types': ['image/png', 'image/jpeg'], 'negative_decay': False, 'ai_provider': 'local-manual'}}  # 查詢經歷草稿；值以參數傳入
