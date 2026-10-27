"""Local-development authentication; replace with managed identity for deployment."""
from datetime import timedelta
import hashlib
import secrets

from pwdlib import PasswordHash

from .errors import require

PASSWORDS = PasswordHash.recommended()
DUMMY_HASH = PASSWORDS.hash('invalid-account-placeholder-2026')


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_session(connection, owner_id, now, policy):
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    connection.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',
                       (digest(token), owner_id, csrf, (now + timedelta(hours=policy.session_hours)).isoformat(), now.isoformat()))
    return token, csrf


def require_registered(user):
    require(user['status'] == 'registered', 403, 'upgrade_required', '人物操作需要先建立本機帳號；目前草稿會保留。')
