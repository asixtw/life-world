"""App Shell 載入與失敗回復只測隔離服務，不接正式帳號或外部 API。"""
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from lw_pwa_support import running


def test_initial_shell_has_neutral_reserved_content(client):
    html=client.get('/').text
    assert 'viewport-fit=cover' in html
    assert 'class="app-booting"' in html
    assert 'class="boot-skeleton"' in html
    assert 'id="app" class="content" aria-busy="true"' in html
    assert 'id="public-account-code"' in html


def test_failed_initial_read_exits_loading_and_can_retry(app):
    with running(app) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':390,'height':844},reduced_motion='reduce')
        pending=[]
        page.route('**/api/capabilities',lambda route:pending.append(route))
        page.goto(base+'/#world',wait_until='domcontentloaded')
        expect(page.locator('.boot-skeleton')).to_be_visible()
        out=Path(__file__).resolve().parents[1]/'docs/pwa/LW-PWA-001/2026-11-18/candidate'
        out.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(out/'390-boot.png'))
        page.wait_for_timeout(100)
        assert len(pending)==1
        pending[0].fulfill(status=503,content_type='application/json',body='{"detail":"合成暫時無法使用"}')
        expect(page.locator('#notice')).not_to_be_empty()
        expect(page.locator('body')).not_to_have_class('app-booting')
        expect(page.locator('#app')).to_have_attribute('aria-busy','false')
        expect(page.locator('.boot-skeleton')).to_have_count(0)
        expect(page.locator('#app-loading')).to_be_hidden()
        expect(page.locator('.sidebar')).to_be_hidden()
        page.screenshot(path=str(out/'390-boot-error.png'))
        page.unroute('**/api/capabilities')
        page.locator('[data-shell-retry]').click()
        expect(page.locator('#app .welcome')).to_be_visible()
        browser.close()


import pytest
from conftest import app,client,onboard,register


@pytest.mark.parametrize('width',[320,390,1440])
def test_shell_preserves_four_step_confirmation_and_navigation(client,app,width):
    _,goal=onboard(client);me=register(client)
    person=client.post('/api/people',json={'name':'合成小安','role':'朋友'}).json()
    before=client.get('/api/state').json()
    with running(app) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':width,'height':844},reduced_motion='reduce')
        context.add_cookies([{'name':'lw_session','value':client.cookies.get('lw_session'),'url':base}])
        page=context.new_page();errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base+'/#world');expect(page.locator('.home-lumi')).to_be_visible()
        normal_padding=page.locator('footer').evaluate('e=>parseFloat(getComputedStyle(e).paddingBottom)')
        page.goto(base+'/#record');expect(page.locator('#raw-text')).to_be_visible()
        if width<=680:
            expect(page.locator('.sidebar')).to_be_hidden()
            assert normal_padding==96
            assert page.locator('footer').evaluate('e=>parseFloat(getComputedStyle(e).paddingBottom)')==24
        page.locator('#raw-text').fill('合成原文：今天和小安練習半小時。')
        page.locator('[data-experience-next]').click()
        page.locator('[name=goal_id]').select_option(goal['id'])
        page.locator('[name="quantity-'+goal['actions'][0]['id']+'"]').fill('0.5')
        page.locator('[data-experience-next]').click()
        page.get_by_role('button',name='選擇既有人物',exact=True).click()
        page.locator('[data-workflow-pick="'+person['id']+'"]').click()
        page.locator('[data-workflow-role]').first.select_option('interaction')
        # 開關頁首選單不能重建表單；關閉後繼續原人物與活動量。
        page.locator('#audio-preferences summary').click()
        page.locator('#audio-preferences summary').click()
        expect(page.locator('#raw-text')).to_have_value('合成原文：今天和小安練習半小時。')
        page.locator('[data-experience-review]').click()
        expect(page.locator('#review-form')).to_be_visible()
        if width==390:
            # 重新載入從同一Session回讀伺服器草稿，不用本機假資料替代。
            draft_id=page.url.split('#review/')[1].split('?')[0]
            persisted=client.get('/api/drafts/'+draft_id).json()
            page.reload()
            expect(page.locator('#review-form')).to_be_visible()
            assert page.url.split('#review/')[1].split('?')[0]==draft_id
            assert client.get('/api/drafts/'+draft_id).json()==persisted
            assert client.get('/api/auth/me').json()['owner_id']==me['owner_id']
        page.locator('#summary').fill('與小安練習半小時。')
        page.locator('#story-reviewed').check()
        assert len(client.get('/api/state').json()['experiences'])==0
        out=Path(__file__).resolve().parents[1]/'docs/pwa/LW-PWA-001/2026-11-18/candidate'
        out.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(out/f'{width}-confirm.png'))
        with page.expect_response(lambda r:'/confirm' in r.url and r.request.method=='POST') as response:
            page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
        saved=response.value
        assert saved.status==201,saved.text()
        repeated=client.post('/api/drafts/'+saved.url.split('/drafts/')[1],json=saved.request.post_data_json)
        assert repeated.status_code==201 and repeated.json()==saved.json()
        expect(page.get_by_role('heading',name='收藏每一段真實。')).to_be_visible()
        expect(page.locator('.sidebar')).to_be_visible()
        expect(page.locator('#app')).to_have_attribute('aria-busy','false')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        data=client.get('/api/state').json()
        assert len(data['people'])==1 and len(data['experiences'])==1 and len(data['rewards']['events'])==1
        assert data['experiences'][0]['raw_text']=='合成原文：今天和小安練習半小時。'
        assert float(data['goals'][0]['actions'][0]['progress'])==float(before['goals'][0]['actions'][0]['progress'])+.5
        story=client.get('/api/connections/stories/'+data['experiences'][0]['id']).json()
        assert len(story['participants'])==1 and story['participants'][0]['id']==person['id'] and story['participants'][0]['interacted'] is True
        assert not errors,errors
        context.close();browser.close()


@pytest.mark.parametrize('ua,expected',[
 ('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile Safari/604.1','在 Safari 開啟 Life World'),
 ('Mozilla/5.0 (Linux; Android 15) Chrome/130.0 Mobile Safari/537.36','在 Android 的 Chrome 開啟 Life World'),
 ('Mozilla/5.0 (iPhone) Instagram 350.0','你目前可能在 IG、FB'),
 ('Mozilla/5.0 (Linux; Android 15) FBAN/FB4A','你目前可能在 IG、FB'),
])
def test_existing_install_help_is_optional_and_platform_specific(app,ua,expected):
    """只從產品關於入口驗證既有引導，不引入原介紹頁或宣稱真機安裝。"""
    with running(app) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':390,'height':844},user_agent=ua,reduced_motion='reduce')
        page=context.new_page();calls=[];errors=[]
        page.on('request',lambda r:calls.append(r.url) if '/api/' in r.url else None)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base+'/');expect(page.locator('#app .welcome')).to_be_visible()
        expect(page.locator('#app')).to_have_attribute('aria-busy','false')
        calls.clear()
        page.locator('.intro-menu summary').click()
        page.locator('[data-pwa-open]').click()
        dialog=page.locator('#pwa-install-dialog')
        expect(dialog).to_be_visible();expect(dialog).to_contain_text(expected)
        expect(dialog).to_contain_text('訪客資料不會自動轉移')
        expect(dialog.locator('[data-pwa-prompt]')).to_have_count(0)
        page.keyboard.press('Escape')
        expect(dialog).not_to_be_visible()
        expect(page.locator('[data-pwa-open]')).to_be_focused()
        assert calls==[] and errors==[]
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        context.close();browser.close()


@pytest.mark.parametrize('outcome,message',[
 ('accepted','尚未收到安裝完成回報'),('dismissed','你已取消安裝'),('error','目前無法開啟安裝視窗')])
def test_existing_native_prompt_requires_click_and_never_fakes_success(app,outcome,message):
    with running(app) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':390,'height':844},user_agent='Android Chrome',reduced_motion='reduce')
        page=context.new_page();page.goto(base+'/')
        expect(page.locator('#app .welcome')).to_be_visible()
        # 瀏覽器事件替身只檢查狀態轉換，不能代表外部瀏覽器已完成安裝。
        page.evaluate('''outcome=>{
            window.promptCount=0;const event=new Event('beforeinstallprompt',{cancelable:true});
            event.prompt=()=>{window.promptCount++;if(outcome==='error')throw new Error('synthetic prompt failure');return Promise.resolve();};
            event.userChoice=Promise.resolve({outcome});dispatchEvent(event);
        }''',outcome)
        page.locator('.intro-menu summary').click();page.locator('[data-pwa-open]').click()
        assert page.evaluate('promptCount')==0
        page.locator('[data-pwa-prompt]').click()
        expect(page.locator('[data-pwa-status]')).to_contain_text(message)
        assert page.evaluate('promptCount')==1
        assert not context.cookies()
        page.keyboard.press('Escape')
        expect(page.locator('#pwa-install-dialog')).not_to_be_visible()
        context.close();browser.close()
