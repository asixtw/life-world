"""本機隔離Alpha實際Chromium操作；不是外部run.app驗收。"""
from datetime import datetime,timezone
import socket,threading,time
import pytest,uvicorn
from playwright.sync_api import sync_playwright,expect
from app.main import create_app
from app.runtime import RuntimeSettings


@pytest.fixture
def alpha_url(tmp_path):
    app=create_app(tmp_path,settings=RuntimeSettings(access_mode='public_alpha',auth_rate_enabled=True,
        auth_rate_secret='synthetic-browser-key-'*3,auth_source_mode='direct'),clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))
    sock=socket.socket();sock.bind(('127.0.0.1',0));url='http://127.0.0.1:'+str(sock.getsockname()[1])
    server=uvicorn.Server(uvicorn.Config(app,log_level='error',proxy_headers=False))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    try:
        end=time.monotonic()+5
        while not server.started and time.monotonic()<end:time.sleep(.02)
        assert server.started
        yield url
    finally:
        server.should_exit=True;thread.join(5);sock.close()


@pytest.mark.parametrize('width',[390,1440])
def test_alpha_real_browser_goal_record_refresh_and_quota(alpha_url,width,tmp_path):
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        try:
            context=browser.new_context(viewport={'width':width,'height':844},locale='zh-TW')
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(alpha_url)
            expect(page.get_by_role('heading',name='Life World Public Alpha')).to_be_visible()
            expect(page.get_by_role('button',name='登入我的世界',exact=True)).to_have_count(0)
            page.get_by_role('button',name='建立我的測試世界 →').click()
            page.locator('#profile-name').fill('Alpha合成測試')
            page.locator('#bio').fill('只使用合成資料')
            page.get_by_role('button',name='接著，建立第一個目標').click()
            page.locator('#goal-title').fill('完成Alpha作品')
            page.get_by_role('button',name='下一步').click()
            page.locator('#outcome').fill('留下三段學習過程')
            page.locator('#goal-deadline').fill('2026-11-28')
            page.get_by_role('button',name='下一步').click()
            for i,name in enumerate(('閱讀','整理','分享')):
                page.locator('#action-title-'+str(i)).fill(name)
                page.get_by_role('button',name='平日',exact=True).click()
                page.get_by_role('button',name='下一步').click()
            page.get_by_role('button',name='確認設定，').click()
            expect(page.get_by_role('heading',name='目標蛋誕生了。 你好，我是 Lumi。')).to_be_visible()
            page.get_by_role('link',name='進入我的世界').click()
            expect(page.get_by_text('完成Alpha作品',exact=True).first).to_be_visible()
            page.reload()
            expect(page.get_by_text('完成Alpha作品',exact=True).first).to_be_visible()
            # 經歷必須實際操作表單，不用API寫入代替UI驗收。
            page.locator('#nav').get_by_role('link',name='紀錄',exact=True).click()
            page.get_by_role('link',name='新的經歷').click()
            state=page.request.get(alpha_url+'/api/state').json();goal=state['goals'][0]
            page.locator('#goal-id').select_option(goal['id'])
            page.locator('#raw-text').fill('今天閱讀合成文件並整理重點。')
            page.locator('#occurred-at').fill('2026-10-27T14:00')
            page.locator('#quantity-'+goal['actions'][0]['id']).fill('1')
            page.get_by_role('button',name='保存草稿並進入核對').click()
            expect(page.locator('#review-form')).to_be_visible()
            page.locator('#summary').fill('閱讀與整理合成資料')
            page.locator('#followups').fill('繼續閱讀')
            page.get_by_role('button',name='我已核對，確認保存').click()
            expect(page.get_by_text('閱讀與整理合成資料',exact=True)).to_be_visible()
            page.reload()
            expect(page.get_by_text('閱讀與整理合成資料',exact=True)).to_be_visible()
            state=page.request.get(alpha_url+'/api/state').json()
            assert len(state['experiences'])==1 and state['rewards']['total']==1
            # 觸發真實來源限流，畫面顯示429且不捏造成功。
            context.clear_cookies();page.goto(alpha_url)
            for _ in range(9):
                page.request.post(alpha_url+'/api/auth/guest');context.clear_cookies()
            page.get_by_role('button',name='建立我的測試世界 →').click()
            expect(page.locator('#notice')).to_contain_text('操作過於頻繁')
            expect(page.locator('#notice')).to_contain_text('分鐘後再試')
            assert not errors
            page.screenshot(path=str(tmp_path/('alpha-quota-'+str(width)+'.png')),full_page=True)
        finally:browser.close()
