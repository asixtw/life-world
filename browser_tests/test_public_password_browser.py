"""無IAP隔離公開模式的真實Chromium帳密流程；不連雲端、不控制Owner Chrome。"""
import os,socket,subprocess,time,urllib.request
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright,expect

@pytest.fixture(scope='module')
def public_base(tmp_path_factory):
    root=Path(__file__).resolve().parents[1];directory=tmp_path_factory.mktemp('public-browser')
    # 測試伺服器只建隔離SQLite帳號；不使用或輸出正式帳密。
    (directory/'public_server.py').write_text('''from app.main import create_app
from app.runtime import RuntimeSettings
from app.security import PASSWORDS
from uuid import uuid4
import os

def factory():
    settings=RuntimeSettings(access_mode="public_alpha",auth_source_mode="shared",auth_rate_enabled=True,auth_rate_secret="synthetic-public-browser-key-"*3,registration_enabled=False,password_login_enabled=False,test_login_usernames=("browser_test",))
    app=create_app(os.environ["LIFEWORLD_DATA_DIR"],settings=settings)
    with app.state.service.db.connect(write=True) as db:
        db.execute("INSERT INTO users(id,status,username,password_hash,name,bio,created_at) VALUES (?,'registered',?,?,?,'合成',?)",(uuid4().hex,"browser_test",PASSWORDS.hash("synthetic-browser-only-password"),"合成測試",app.state.service.now().isoformat()))
    return app
''')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env={k:v for k,v in os.environ.items() if not k.startswith(('LIFEWORLD_','K_SERVICE','K_REVISION'))}
    env.update(LIFEWORLD_DATA_DIR=str(directory/'data'),LIFEWORLD_AI_ENABLED='false',PYTHONPATH=str(directory)+os.pathsep+str(root))
    log=(directory/'server.log').open('w');process=subprocess.Popen(['/private/tmp/lw-alpha-py312/bin/python','-m','uvicorn','public_server:factory','--factory','--host','127.0.0.1','--port',str(port)],cwd=root,env=env,stdout=log,stderr=log);url=f'http://127.0.0.1:{port}'
    try:
        for _ in range(80):
            if process.poll() is not None:raise RuntimeError('isolated public server failed')
            try:urllib.request.urlopen(url+'/health',timeout=.2);break
            except Exception:time.sleep(.1)
        yield url
    finally:process.terminate();process.wait(timeout=10);log.close()


def test_public_password_login_onboard_logout_and_revisit(public_base):
    with sync_playwright() as pw:
        browser=pw.chromium.launch();page=browser.new_page(locale='zh-TW');page.set_default_timeout(8000)
        page.goto(public_base);expect(page.get_by_role('button',name='登入預建帳號',exact=True)).to_be_visible()
        assert page.request.get(public_base+'/api/state').status==401
        def login():
            page.get_by_role('button',name='登入預建帳號',exact=True).click();page.locator('#username').fill('browser_test');page.locator('#password').fill('synthetic-browser-only-password');page.get_by_role('button',name='登入我的世界',exact=True).click()
        login();expect(page.locator('#goal-title')).to_be_visible()
        page.locator('#goal-title').fill('合成閱讀目標');page.get_by_role('button',name='下一步').click();page.locator('#outcome').fill('整理心得');page.get_by_role('button',name='一週後',exact=True).click();page.get_by_role('button',name='下一步').click()
        for i,name in enumerate(['閱讀','心得','整理']):
            page.locator(f'#action-title-{i}').fill(name);page.get_by_role('button',name='每天',exact=True).click();page.get_by_role('button',name='下一步').click()
        page.get_by_role('button',name='確認設定，建立目標蛋').click()
        for stage in range(1,4):page.locator('[data-birth-egg]').click();expect(page.locator('[data-birth]')).to_have_attribute('data-stage',str(stage))
        page.locator('[data-birth-enter]').click();expect(page.locator('.home-lumi')).to_be_visible()
        before=page.request.get(public_base+'/api/state').json();assert len(before['goals'])==1 and len(before['goals'][0]['actions'])==3
        page.get_by_role('button',name='帳號設定').click();page.get_by_role('button',name='登出',exact=True).click();expect(page.get_by_role('button',name='登入預建帳號',exact=True)).to_be_visible();assert page.request.get(public_base+'/api/state').status==401
        login();expect(page.locator('.home-lumi')).to_be_visible();page.reload();expect(page.locator('.home-lumi')).to_be_visible()
        after=page.request.get(public_base+'/api/state').json();assert after['goals'][0]['id']==before['goals'][0]['id']
        page.screenshot(path='/private/tmp/GCP144_v55/PUBLIC_PASSWORD_WORLD.png',full_page=True);browser.close()
