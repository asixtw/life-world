"""公開安全Gate的桌面／手機實際畫面，不連DB、不呼叫模型。"""
import os,socket,subprocess,time,urllib.request
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright,expect

@pytest.fixture(scope='module')
def closed_base(tmp_path_factory):
    root=Path(__file__).resolve().parents[1]
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    env={k:v for k,v in os.environ.items() if not k.startswith(('LIFEWORLD_','K_SERVICE','K_REVISION'))}
    env.update(LIFEWORLD_DATA_DIR=str(tmp_path_factory.mktemp('closed-public')),LIFEWORLD_DB_BACKEND='postgresql',LIFEWORLD_DB_NAME='life_world_public',LIFEWORLD_DB_USER='lw_public_app',LIFEWORLD_PUBLIC_GATE_CLOSED='true',LIFEWORLD_ENABLE_BUSINESS_API='false',LIFEWORLD_ACCESS_MODE='public_alpha')
    log=Path('/private/tmp/GCP144_v58/BROWSER_SERVER.txt').open('w');process=subprocess.Popen(['/private/tmp/lw-alpha-py312/bin/python','-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port',str(port)],cwd=root,env=env,stdout=log,stderr=log);url=f'http://127.0.0.1:{port}'
    try:
        for _ in range(80):
            if process.poll() is not None:raise RuntimeError('public gate startup failed')
            try:urllib.request.urlopen(url+'/health',timeout=.2);break
            except Exception:time.sleep(.1)
        yield url
    finally:process.terminate();process.wait(timeout=10);log.close()

@pytest.mark.parametrize('width',[390,1280])
def test_closed_public_page_is_honest_and_operable(closed_base,width):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':width,'height':900});page.goto(closed_base)
        expect(page.get_by_role('heading',name='Life World',exact=True)).to_be_visible()
        expect(page.locator('#app')).to_contain_text('目前不接受個人資料')
        expect(page.locator('[data-lumi-art]')).to_be_visible();assert page.locator('[data-lumi-art]').evaluate('(img)=>img.complete&&img.naturalWidth>0')
        expect(page.get_by_role('button',name='帳號設定')).to_be_visible()
        assert page.request.get(closed_base+'/api/state').status==401
        assert page.request.get(closed_base+'/ready').status==503
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=f'/private/tmp/GCP144_v58/public-{width}.png',full_page=True);browser.close()


def test_closed_gate_shows_entry_choices_and_safe_retry(closed_base):
    """入口可操作，但DB未接通前不送帳密／訪客寫入，也不假裝已登入。"""
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page();mutations=[]
        page.on('request',lambda req:mutations.append(req.url) if req.method in ('POST','PUT','DELETE','PATCH') else None)
        page.goto(closed_base)
        page.get_by_role('button',name='Google 登入',exact=True).click()
        expect(page.get_by_role('heading',name='Google 登入',exact=True)).to_be_visible()
        expect(page.get_by_role('button',name='繼續使用 Google 登入',exact=True)).to_be_disabled()
        page.get_by_role('button',name='重試服務連線',exact=True).click()
        expect(page.locator('#entry-state')).to_contain_text('尚未開放')
        expect(page.get_by_role('button',name='重試服務連線',exact=True)).to_be_enabled()
        page.get_by_role('button',name='關閉入口',exact=True).click()
        page.get_by_role('button',name='不用註冊，先開始',exact=True).click()
        expect(page.get_by_role('heading',name='訪客體驗',exact=True)).to_be_visible()
        expect(page.locator('#account-content')).to_contain_text('跨裝置')
        page.get_by_role('button',name='關閉入口',exact=True).click()
        page.get_by_role('button',name='Email 註冊／登入',exact=True).click()
        expect(page.locator('#account-content')).to_contain_text('尚未開放')
        page.get_by_role('button',name='關閉入口',exact=True).click()
        page.get_by_role('button',name='專用測試帳密登入',exact=True).click()
        expect(page.locator('#entry-username')).to_be_disabled();expect(page.locator('#entry-password')).to_be_disabled()
        assert mutations==[]
        browser.close()
