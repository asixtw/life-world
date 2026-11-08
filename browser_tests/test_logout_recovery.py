"""登出與清理故障的獨立Chromium回歸；不操作Owner視窗。"""
from playwright.sync_api import sync_playwright,expect
from test_release_a_delivery import base


def enter(page,base):
    page.goto(base);page.get_by_role('button',name='不用註冊，先開始').click();expect(page.locator('#bio')).to_be_visible()


def test_dirty_logout_offers_choice_and_does_not_delete_server(base):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page();enter(page,base)
        page.locator('#bio').fill('尚未保存的合成介紹');page.get_by_role('button',name='帳號設定').click()
        logout=page.get_by_role('button',name='登出',exact=True);expect(logout).to_be_enabled();logout.click()
        page.get_by_role('button',name='繼續編輯',exact=True).click();expect(page.locator('#bio')).to_have_value('尚未保存的合成介紹')
        page.get_by_role('button',name='帳號設定').click();page.get_by_role('button',name='登出',exact=True).click()
        page.get_by_role('button',name='捨棄未保存修改並登出',exact=True).click()
        expect(page.get_by_role('button',name='不用註冊，先開始')).to_be_visible()
        assert page.request.get(base+'/api/auth/me').status==401
        browser.close()


def test_media_cleanup_never_blocks_session_revocation(base):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page();enter(page,base)
        # 測試故障注入：只模擬本機IndexedDB永久等待，正式logout仍走真HTTP。
        page.evaluate('()=>{MediaUI.clearOwner=()=>new Promise(()=>{});}')
        page.get_by_role('button',name='帳號設定').click();page.locator('#clear-local-media').check()
        page.get_by_role('button',name='登出',exact=True).click()
        expect(page.get_by_role('button',name='不用註冊，先開始')).to_be_visible(timeout=8000)
        expect(page.locator('#notice')).to_contain_text('本機媒體',timeout=8000)
        assert page.request.get(base+'/api/auth/me').status==401
        browser.close()


def test_logout_http_failure_can_retry(base):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page();enter(page,base)
        page.route('**/api/auth/logout',lambda route:route.fulfill(status=503,json={'error':{'code':'temporary','message':'測試暫時失敗'}}))
        page.get_by_role('button',name='帳號設定').click();page.get_by_role('button',name='登出',exact=True).click()
        expect(page.get_by_role('button',name='登出',exact=True)).to_be_enabled()
        assert page.request.get(base+'/api/auth/me').status==200
        page.unroute('**/api/auth/logout');page.get_by_role('button',name='登出',exact=True).click()
        expect(page.get_by_role('button',name='不用註冊，先開始')).to_be_visible()
        browser.close()
