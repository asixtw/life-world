"""Local-development authentication; replace with managed identity for deployment."""  # 說明此模組的責任與實作邊界
from datetime import timedelta  # 處理 UTC、發生時間與期限
import hashlib  # 計算工作階段、圖片或請求內容的雜湊
import secrets  # 產生隨機驗證代碼並進行固定時間比較

from pwdlib import PasswordHash  # 使用建議的密碼雜湊方案

from .errors import require  # 共用領域錯誤與條件檢查

PASSWORDS = PasswordHash.recommended()  # 準備密碼雜湊與驗證工具
DUMMY_HASH = PASSWORDS.hash('invalid-account-placeholder-2026')  # 以密碼雜湊保存認證資料，不儲存明文


def digest(token):  # 將工作階段代碼雜湊後再用於資料庫查詢
    return hashlib.sha256(token.encode()).hexdigest()  # 回傳將工作階段代碼雜湊後再用於資料庫查詢的結果


def new_session(connection, owner_id, now, policy):  # 產生隨機工作階段及 CSRF 代碼，資料庫僅存工作階段雜湊
    token = secrets.token_urlsafe(32)  # 準備隨機登入工作階段代碼
    csrf = secrets.token_urlsafe(32)  # 準備寫入請求的 CSRF 驗證代碼
    connection.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',
                       (digest(token), owner_id, csrf, (now + timedelta(hours=policy.session_hours)).isoformat(), now.isoformat()))  # 新增登入工作階段；值以參數傳入
    return token, csrf  # 回傳產生隨機工作階段及 CSRF 代碼，資料庫僅存工作階段雜湊的結果


def require_registered(user):  # 在人物操作前要求本機帳號
    require(user['status'] == 'registered', 403, 'upgrade_required', '人物操作需要先建立本機帳號；目前草稿會保留。')  # 驗證限制：人物操作需要先建立本機帳號；目前草稿會保留。
