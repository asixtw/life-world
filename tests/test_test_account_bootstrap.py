"""測試帳號建立不覆寫既有Owner，不需要DDL。"""
from dataclasses import replace
from uuid import uuid4
import pytest
from app.main import create_app
from app.runtime import RuntimeSettings
from app.security import PASSWORDS
from app.test_account import provision


def test_explicit_seed_idempotent_and_no_overwrite(tmp_path):
    settings=replace(RuntimeSettings(),test_login_usernames=('invited_test',),password_login_enabled=False,registration_enabled=False)
    app=create_app(tmp_path,settings=settings)
    data={'username':'invited_test','owner_id':str(uuid4()),'password_hash':PASSWORDS.hash('synthetic-bootstrap-2026')}
    assert provision(app.state.service,settings,data,allow_sqlite_test=True)
    assert not provision(app.state.service,settings,data,allow_sqlite_test=True)
    with pytest.raises(ValueError):provision(app.state.service,settings,{**data,'owner_id':str(uuid4())},allow_sqlite_test=True)
    with app.state.service.db.connect() as c:assert c.execute('SELECT count(*) AS n FROM users').fetchone()['n']==1


def test_seed_refuses_default_or_unlisted_target(tmp_path):
    settings=replace(RuntimeSettings(),test_login_usernames=('invited_test',))
    app=create_app(tmp_path,settings=settings)
    data={'username':'invited_test','owner_id':str(uuid4()),'password_hash':PASSWORDS.hash('synthetic-bootstrap-2026')}
    with pytest.raises(ValueError):provision(app.state.service,settings,data)
    with pytest.raises(ValueError):provision(app.state.service,settings,{**data,'username':'uninvited'},allow_sqlite_test=True)
