"""候選／正式站唯讀驗收：只操作介紹與瀏覽器偏好，不建立正式世界或呼叫AI。"""
import hashlib,json,os,ssl
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
import certifi
import pytest
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
URL=os.environ.get('LIVE_INTRO_URL','').rstrip('/')
pytestmark=pytest.mark.skipif(not URL,reason='須明確指定候選或正式站網址')


def get(path):
    """使用完整TLS驗證，不攜帶登入Cookie或任何授權憑證。"""
    try:
        with urlopen(URL+path,timeout=30,context=ssl.create_default_context(cafile=certifi.where())) as response:return response.status,response.headers,response.read()
    except HTTPError as error:return error.code,error.headers,error.read()


def test_published_routes_and_all_static_bytes_match_reviewed_release():
    assert get('/health')[0]==200
    intro=get('/intro');assert intro[0]==200 and "connect-src 'none'" in intro[1]['Content-Security-Policy']
    assert intro[2]==(ROOT/'app/static/intro/index.html').read_bytes()
    assert get('/intro/')[2]==intro[2]
    for file in ['index.html','app.js','intro-entry.css','intro-entry.js','intro-preference.js']:
        status,headers,body=get('/static/'+file);assert status==200
        assert body==(ROOT/'app/static'/file).read_bytes(),file
        assert 'Set-Cookie' not in headers
    for file in (ROOT/'app/static/intro').rglob('*'):
        if not file.is_file():continue
        path=str(file.relative_to(ROOT/'app/static'));status,headers,body=get('/static/'+path)
        assert status==200 and hashlib.sha256(body).digest()==hashlib.sha256(file.read_bytes()).digest(),path
    # 私人資料仍維持未登入契約，沒有因介紹入口而放寬。
    assert get('/api/auth/me')[0]==401
    assert get('/api/state')[0]==401
    assert get('/intro/private')[0]!=200


@pytest.mark.parametrize('width',[320,390,1440])
def test_live_intro_and_welcome_preference_without_product_writes(width):
    with sync_playwright() as p:
        browser=p.chromium.launch();context=browser.new_context(viewport={'width':width,'height':1000},reduced_motion='reduce');page=context.new_page()
        blocked=[];errors=[];api_on_intro=[]
        def guard(route):
            if route.request.method not in ['GET','HEAD','OPTIONS']:
                blocked.append(route.request.url);route.abort()
            else:route.continue_()
        context.route('**/api/**',guard)  # 即使意外回歸，也在送出前攔截正式寫入。
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:api_on_intro.append(request.url) if '/api/' in request.url and '/intro' in page.url else None)
        page.goto(URL+'/#welcome');expect(page.locator('#intro-choice')).to_be_visible(timeout=20000)
        page.get_by_role('link',name='先認識 Life World',exact=True).click();expect(page.locator('#start')).to_be_visible()
        page.locator('#start').click()
        for _ in range(3):
            page.locator('#advance').click();expect(page.locator('.lw-preview')).to_have_attribute('data-busy','false')
        expect(page.locator('#product-entry')).to_have_text('開始我的故事')
        assert page.evaluate("JSON.parse(localStorage.getItem('lifeworld:intro:v1')).outcome")=='completed'
        assert page.locator('img').evaluate_all('items=>items.every(e=>e.complete&&e.naturalWidth>0)')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.locator('#product-entry').click();expect(page).to_have_url(URL+'/#welcome')
        expect(page.locator('#app .hero')).to_be_visible(timeout=20000)
        expect(page.locator('#intro-choice')).to_have_count(0)
        page.reload();expect(page.locator('#app .hero')).to_be_visible(timeout=20000)
        expect(page.locator('#intro-choice')).to_have_count(0)
        page.locator('.intro-menu summary').click()
        with page.expect_popup() as popup:page.locator('.intro-menu a').click()
        replay=popup.value;replay.wait_for_load_state();expect(replay.locator('#start')).to_be_visible()
        assert blocked==[] and errors==[] and api_on_intro==[]
        context.close();browser.close()
