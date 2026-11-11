"""僅127.0.0.1合成Google交換驗收；不連Google、不用正式DB/Secrets。"""
import argparse
from pathlib import Path
from datetime import datetime,timezone
import uvicorn
from app.main import create_app
from app.runtime import RuntimeSettings
from app.security import digest
from app.errors import DomainError


class FixtureVerifier:
    client_id='synthetic-google-transition.apps.googleusercontent.com'
    def verify(self,credential,nonce_hash):
        parts=credential.split(':')
        if len(parts)!=3 or parts[0]!='fixture' or digest(parts[2])!=nonce_hash:raise DomainError(401,'fixture_rejected','明示Google測試替身拒絕')
        return 'https://accounts.google.com',parts[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',required=True,type=Path);p.add_argument('--port',type=int,default=8010);a=p.parse_args()
    if not a.data_dir.resolve().is_relative_to(Path('/private/tmp')):p.error('必須使用本機暫存資料')
    app=create_app(data_dir=a.data_dir,settings=RuntimeSettings(google_client_id=FixtureVerifier.client_id,password_login_enabled=False,registration_enabled=False),google_verifier=FixtureVerifier(),clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))
    with app.state.service.db.connect(write=True) as c:
        c.execute('CREATE TABLE IF NOT EXISTS external_identities(provider TEXT,issuer TEXT,subject TEXT,owner_id TEXT REFERENCES users(id),created_at TEXT,PRIMARY KEY(provider,issuer,subject))')
        c.execute("CREATE TABLE IF NOT EXISTS guest_abandonments(owner_id TEXT PRIMARY KEY,abandoned_at TEXT,purge_after TEXT,status TEXT,attempts INTEGER DEFAULT 0,last_error_code TEXT,completed_at TEXT,media_state TEXT DEFAULT 'pending',media_attempts INTEGER DEFAULT 0)")
    uvicorn.run(app,host='127.0.0.1',port=a.port,access_log=False)


if __name__=='__main__':main()
