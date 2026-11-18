"""正常 App 入口上的合成資料驗收；Chromium 不代表 iPhone／IG 真機。"""
from datetime import datetime,timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright,expect
from app.main import create_app
from app.runtime import RuntimeSettings
from conftest import onboard
from lw_pwa_support import running

OUT=Path('/private/tmp/lw-onboarding-evidence-20261118')

@pytest.fixture
def guide_app(tmp_path):
    return create_app(tmp_path,settings=RuntimeSettings(backend='sqlite',auth_source_mode='direct'),clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))


def shots(page,name):
    for image in page.locator('.guide-scene img').all():
        image.evaluate('async e=>{await e.decode();if(!e.naturalWidth)throw new Error("guide image unavailable")}')
    OUT.mkdir(exist_ok=True);page.screenshot(path=str(OUT/name))


@pytest.mark.parametrize('width',[320,390,768,1440])
def test_first_entry_three_acts_skip_replay_and_no_business_writes(guide_app,width):
    with running(guide_app) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':width,'height':900},reduced_motion='reduce')
        page=context.new_page();page.set_default_timeout(6000);writes=[];errors=[]
        page.on('request',lambda r:writes.append(r.url) if '/api/' in r.url and r.method not in ('GET','HEAD') else None)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base)
        expect(page.get_by_role('heading',name='你明明做了很多事，卻常常覺得自己沒什麼進步。')).to_be_visible()
        assert page.locator('.guide-intro input,.guide-intro textarea').count()==0
        expect(page.locator('.guide-intro')).to_contain_text('連自己都忘了')
        assert 'AI' not in page.locator('.guide-intro').inner_text() and 'Lumi' not in page.locator('.guide-intro').inner_text()
        shots(page,f'{width}-intro-1.png')
        page.get_by_role('button',name='下一步').click()
        expect(page.get_by_role('heading',name='不用寫日記，一句話就能記下今天。')).to_be_visible()
        expect(page.locator('[data-intro-example]')).to_contain_text('虛構示例')
        expect(page.locator('[data-intro-example]')).to_contain_text('簡報')
        shots(page,f'{width}-intro-benefits.png')
        page.get_by_role('button',name='看看接下來會發生什麼').click()
        expect(page.get_by_role('heading',name='原來，你已經走了這麼遠。')).to_be_visible()
        if width in (390,1440):shots(page,f'{width}-intro-world.png')
        page.get_by_role('button',name='開始我的世界',exact=True).click()
        expect(page.get_by_role('heading',name='把每一步，種成自己的世界。')).to_be_visible()
        page.reload();expect(page.get_by_role('heading',name='把每一步，種成自己的世界。')).to_be_visible()
        page.locator('.intro-menu > summary').click()
        page.get_by_role('button',name='認識 Life World',exact=True).click()
        expect(page.get_by_role('heading',name='你明明做了很多事，卻常常覺得自己沒什麼進步。')).to_be_visible()
        page.get_by_role('button',name='跳過',exact=True).click()
        page.locator('.intro-menu > summary').click();page.get_by_role('button',name='使用教學',exact=True).click()
        expect(page.get_by_role('heading',name='照自己的步調，認識 Life World')).to_be_visible()
        shots(page,f'{width}-tutorial.png')
        assert page.evaluate('document.documentElement.scrollWidth-innerWidth')<=0
        assert writes==[] and errors==[]
        context.close();browser.close()


def test_storage_blocked_still_allows_real_guest_setup(guide_app):
    with running(guide_app) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':390,'height':900},reduced_motion='reduce')
        context.add_init_script("Storage.prototype.getItem=Storage.prototype.setItem=function(){throw new Error('synthetic storage blocked')}")
        page=context.new_page();page.set_default_timeout(6000);page.goto(base)
        page.get_by_role('button',name='跳過',exact=True).click()
        page.get_by_role('button',name='不用註冊，先開始 →',exact=True).click()
        expect(page.locator('#profile-form')).to_be_visible()
        page.locator('#profile-name').fill('合成新使用者');page.locator('#bio').fill('想建立閱讀習慣')
        page.locator('#profile-form button').click()
        expect(page.locator('#goal-title')).to_be_visible()
        expect(page.locator('[data-guide-context]')).to_contain_text('先選擇一件')
        assert page.locator('#goal-title').input_value()==''
        context.close();browser.close()


def test_context_guide_is_owner_scoped_and_does_not_erase_record(guide_app):
    with TestClient(guide_app) as a,TestClient(guide_app) as b:
        onboard(a);onboard(b)
        with running(guide_app) as base,sync_playwright() as pw:
            browser=pw.chromium.launch(channel='chrome',headless=True)
            context=browser.new_context(viewport={'width':390,'height':900},reduced_motion='reduce')
            context.add_cookies([{'name':'lw_session','value':a.cookies.get('lw_session'),'url':base}])
            page=context.new_page();page.set_default_timeout(6000);page.goto(base+'/#record')
            expect(page.locator('[data-guide-context]')).to_contain_text('記下真實發生的事')
            page.locator('#raw-text').fill('真實表單暫存，不能被教學清除')
            page.locator('[data-guide-context] [data-guide-dismiss]').click()
            expect(page.locator('#raw-text')).to_have_value('真實表單暫存，不能被教學清除')
            page.reload();expect(page.locator('[data-guide-context]')).to_have_count(0)
            context.add_cookies([{'name':'lw_session','value':b.cookies.get('lw_session'),'url':base}]);page.reload()
            expect(page.locator('[data-guide-context]')).to_contain_text('記下真實發生的事')
            assert page.locator('#nav a').count()==4
            context.close();browser.close()


@pytest.mark.parametrize('agent,expected',[
 ('Mozilla/5.0 (iPhone) Safari','Safari'),
 ('Mozilla/5.0 Android Chrome','Android'),
 ('Mozilla/5.0 iPhone Instagram','IG、FB'),
 ('Mozilla/5.0 Android FBAN/FB4A','IG、FB')])
def test_installation_help_routes_and_copy_are_optional(guide_app,agent,expected):
    with running(guide_app) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':390,'height':900},user_agent=agent,reduced_motion='reduce')
        context.add_init_script("Object.defineProperty(navigator,'clipboard',{value:{writeText:async value=>{window.guideCopied=value;}}})")
        page=context.new_page();page.set_default_timeout(6000);writes=[]
        page.on('request',lambda r:writes.append(r.url) if '/api/' in r.url and r.method not in ('GET','HEAD') else None)
        page.goto(base);page.locator('.intro-menu > summary').click();page.get_by_role('button',name='加到手機主畫面',exact=True).click()
        dialog=page.locator('#pwa-install-dialog');expect(dialog).to_be_visible();expect(dialog.locator('.pwa-body')).to_contain_text(expected)
        expect(dialog).to_contain_text('訪客資料不會自動轉移');expect(dialog).to_contain_text('不代表離線可用')
        dialog.get_by_role('button',name='複製網址',exact=True).click();assert page.evaluate('window.guideCopied')==base+'/'
        expect(dialog.locator('[data-pwa-status]')).to_contain_text('已複製')
        shots(page,'390-install-'+('ios' if 'iPhone' in agent and 'Instagram' not in agent else 'ig' if 'Instagram' in agent else 'fb' if 'FBAN' in agent else 'android')+'.png')
        dialog.get_by_role('button',name='稍後再說',exact=True).click();expect(dialog).not_to_be_visible()
        expect(page.locator('.intro-menu > summary')).to_be_focused()
        assert page.evaluate("localStorage.getItem('lifeworld:install-hint:v1')")=='later'
        page.locator('.intro-menu > summary').click();page.get_by_role('button',name='加到手機主畫面',exact=True).click()
        expect(dialog).to_be_visible();dialog.press('Escape');expect(dialog).not_to_be_visible()
        assert writes==[]
        context.close();browser.close()


@pytest.mark.parametrize('outcome',['accepted','dismissed','error'])
def test_native_install_event_is_not_faked_as_completed(guide_app,outcome):
    with running(guide_app) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':390,'height':900},user_agent='Android Chrome')
        page=context.new_page();page.goto(base);expect(page.locator('.guide-intro')).to_be_visible()
        page.evaluate('''outcome=>{window.promptCalls=0;const event=new Event('beforeinstallprompt',{cancelable:true});event.prompt=async()=>{window.promptCalls++;if(outcome==='error')throw new Error('synthetic rejected')};event.userChoice=Promise.resolve({outcome});dispatchEvent(event);}''',outcome)
        page.locator('.intro-menu > summary').click();page.get_by_role('button',name='加到手機主畫面',exact=True).click()
        dialog=page.locator('#pwa-install-dialog');dialog.locator('[data-pwa-prompt]').click()
        expect(dialog.locator('[data-pwa-status]')).to_contain_text({'accepted':'尚未收到安裝完成回報','dismissed':'取消','error':'無法開啟'}[outcome])
        assert page.evaluate('window.promptCalls')==1
        if outcome=='accepted':
            page.evaluate("dispatchEvent(new Event('appinstalled'))")
            expect(dialog.locator('[data-pwa-status]')).to_contain_text('瀏覽器已回報完成安裝')
        context.close();browser.close()


def test_installed_and_copy_failure_have_honest_fallbacks(guide_app):
    with running(guide_app) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':390,'height':900})
        context.add_init_script("Object.defineProperty(navigator,'standalone',{value:true});Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{throw new Error('synthetic denied')}}})")
        page=context.new_page();page.goto(base);page.locator('.intro-menu > summary').click();page.get_by_role('button',name='加到手機主畫面',exact=True).click()
        dialog=page.locator('#pwa-install-dialog');expect(dialog).to_contain_text('已從主畫面開啟');assert dialog.locator('[data-pwa-prompt]').count()==0
        context.close()
        context=browser.new_context(viewport={'width':390,'height':900})
        context.add_init_script("Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{throw new Error('synthetic denied')}}})")
        page=context.new_page();page.goto(base);page.locator('.intro-menu > summary').click();page.get_by_role('button',name='加到手機主畫面',exact=True).click()
        dialog=page.locator('#pwa-install-dialog');dialog.get_by_role('button',name='複製網址',exact=True).click()
        expect(dialog.locator('[data-pwa-status]')).to_contain_text('系統的複製功能')
        assert dialog.locator('#pwa-url').evaluate('e=>e.selectionStart===0&&e.selectionEnd===e.value.length')
        context.close();browser.close()


def test_tutorial_menu_protects_dirty_experience(guide_app):
    with TestClient(guide_app) as c:
        onboard(c)
        with running(guide_app) as base,sync_playwright() as pw:
            browser=pw.chromium.launch(channel='chrome',headless=True);context=browser.new_context(viewport={'width':390,'height':900})
            context.add_cookies([{'name':'lw_session','value':c.cookies.get('lw_session'),'url':base}])
            page=context.new_page();page.goto(base+'/#record');page.locator('#raw-text').fill('未保存的真實表單不應被教學覆蓋')
            page.locator('.intro-menu > summary').click();page.get_by_role('button',name='使用教學',exact=True).click()
            expect(page.locator('#account-dialog')).to_be_visible();expect(page.locator('#raw-text')).to_have_value('未保存的真實表單不應被教學覆蓋')
            page.get_by_role('button',name='繼續編輯',exact=True).click()
            expect(page.locator('#raw-text')).to_have_value('未保存的真實表單不應被教學覆蓋')
            assert c.get('/api/state').json()['experiences']==[]
            context.close();browser.close()


def test_full_new_user_goal_record_confirm_and_install_offer(guide_app):
    from datetime import date,timedelta
    with running(guide_app) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':390,'height':900},reduced_motion='reduce')
        page=context.new_page();page.set_default_timeout(6000);posts=[]
        page.on('request',lambda r:posts.append(r.url) if r.method=='POST' and '/api/' in r.url else None)
        page.goto(base)
        for label in ['下一步','看看接下來會發生什麼','開始我的世界']:page.get_by_role('button',name=label,exact=True).click()
        page.get_by_role('button',name='不用註冊，先開始 →',exact=True).click()
        page.locator('#profile-name').fill('合成閱讀者');page.locator('#bio').fill('為自己的閱讀留下記錄')
        page.locator('#profile-form button').click();expect(page.locator('[data-guide-context]')).to_contain_text('先選擇一件')
        page.locator('#goal-title').fill('合成目標：讀完一本書');page.locator('#goal-form button[type=submit]').click()
        page.locator('#outcome').fill('整理一段真正讀過的內容')
        today=page.request.get(base+'/api/auth/me').json()['today'];page.locator('#goal-deadline').fill((date.fromisoformat(today)+timedelta(days=30)).isoformat())
        page.locator('#goal-form button[type=submit]').click()
        for i,title in enumerate(['閱讀','寫一句心得','回想下一步']):
            page.locator('#action-title-'+str(i)).fill(title)
            page.get_by_role('button',name='平日',exact=True).click();page.locator('#goal-form button[type=submit]').click()
        # 尚未建第一個目標時，正式 state API 依原契約拒絕；以隔離 DB 唯讀確認未提前寫入。
        state_response=page.request.get(base+'/api/state')
        assert state_response.status==409 and state_response.json()['error']['code']=='first_goal_required'
        with guide_app.state.service.db.connect() as connection:
            assert connection.execute('SELECT count(*) FROM goals').fetchone()[0]==0
            assert connection.execute('SELECT count(*) FROM experiences').fetchone()[0]==0
        page.locator('#goal-form button[type=submit]').click()
        expect(page.locator('[data-birth-egg]')).to_be_visible()
        for _ in range(3):page.locator('[data-birth-egg]').click()
        page.locator('[data-birth-enter]').click()
        expect(page.locator('#nav a')).to_have_count(4)
        assert page.locator('[data-pwa-nudge]').count()==0
        page.get_by_role('link',name='記錄新經歷',exact=True).first.click()
        expect(page.locator('[data-guide-context]')).to_contain_text('記下真實發生的事')
        raw='合成資料：今天真的讀了十分鐘，留下自己的心得。';page.locator('#raw-text').fill(raw)
        page.locator('[data-experience-next]').click()
        world=page.request.get(base+'/api/state').json();goal=world['goals'][0]
        page.locator('#goal-id').select_option(goal['id'])
        page.locator('[name="quantity-'+goal['actions'][0]['id']+'"]').fill('1')
        page.locator('[data-experience-next]').click()
        page.locator('[data-experience-review]').click()
        expect(page.locator('#review-form')).to_be_visible();expect(page.locator('[data-guide-context]')).to_contain_text('可編輯草稿')
        draft_state=page.request.get(base+'/api/state').json();assert draft_state['experiences']==[] and draft_state['rewards']['total']==0
        page.locator('#summary').fill('合成資料：閱讀後留下自己的想法。')
        page.locator('[data-review-tasks] summary').click();page.locator('#followups').fill('下次繼續閱讀')
        shots(page,'390-actual-confirm.png')
        page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
        expect(page.locator('#review-form')).to_have_count(0)
        saved=page.request.get(base+'/api/state').json()
        assert len(saved['experiences'])==1 and saved['experiences'][0]['raw_text']==raw
        assert saved['rewards']['total']==saved['policy']['points_per_experience']
        assert len(saved['tasks'])==1 and saved['goals'][0]['actions'][0]['progress']=='1'
        page.locator('#nav a[href="#world"]').click()
        expect(page.locator('[data-pwa-nudge]')).to_be_visible();expect(page.locator('[data-pwa-nudge]')).to_contain_text('訪客')
        shots(page,'390-world-install-offer.png')
        assert not any('/api/ai/' in u or '/api/media/recognize' in u for u in posts)
        context.close();browser.close()


def test_partial_storage_failure_and_reduced_motion_are_safe(guide_app):
    with running(guide_app) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':390,'height':900},reduced_motion='reduce')
        context.add_init_script("""const originalSet=Storage.prototype.setItem;originalSet.call(localStorage,'lifeworld:intro:v2',JSON.stringify({version:1,seen:false,updatedAt:1}));Storage.prototype.setItem=function(key,value){if(this===localStorage)throw new Error('synthetic quota');return originalSet.call(this,key,value)};window.audioStarts=0;HTMLMediaElement.prototype.play=function(){window.audioStarts++;return Promise.resolve()};""")
        page=context.new_page();page.goto(base);expect(page.locator('.guide-intro')).to_be_visible()
        assert page.locator('.guide-scene img').count()==0
        assert page.evaluate('window.audioStarts')==0
        page.get_by_role('button',name='下一步',exact=True).focus();page.keyboard.press('Enter')
        expect(page.locator('#guide-intro-title')).to_be_focused()
        assert page.locator('.guide-demo-next').evaluate('e=>getComputedStyle(e).animationName')=='none'
        assert page.locator('.guide-demo-next').evaluate('e=>getComputedStyle(e).opacity')=='1'
        page.get_by_role('button',name='上一步',exact=True).click()
        page.get_by_role('button',name='跳過',exact=True).click();page.reload()
        expect(page.locator('.welcome')).to_be_visible()
        assert page.evaluate("JSON.parse(sessionStorage.getItem('lifeworld:intro:v2')).seen") is True
        context.close();browser.close()


def test_paused_teaching_resumes_without_repeating_acknowledged_steps(guide_app):
    from conftest import register
    with TestClient(guide_app) as c:
        onboard(c);register(c,'synthetic_guide_reader')
        with running(guide_app) as base,sync_playwright() as pw:
            browser=pw.chromium.launch(channel='chrome',headless=True)
            context=browser.new_context(viewport={'width':390,'height':900})
            context.add_cookies([{'name':'lw_session','value':c.cookies.get('lw_session'),'url':base}])
            page=context.new_page();page.goto(base+'/#record')
            page.locator('[data-guide-dismiss=record]').click();page.goto(base+'/#world')
            page.locator('[data-guide-pause]').click()
            assert page.locator('[data-guide-context]').count()==0
            page.locator('.intro-menu > summary').click();page.get_by_role('button',name='使用教學',exact=True).click()
            page.get_by_role('button',name='回到操作，邊做邊看',exact=True).click()
            expect(page.locator('#record-form')).to_be_visible();assert page.locator('[data-guide-context]').count()==0
            page.reload();expect(page.locator('#record-form')).to_be_visible();assert page.locator('.guide-intro').count()==0
            assert c.get('/api/state').json()['experiences']==[]
            context.close();browser.close()


def test_returning_registered_user_logs_in_without_repeated_intro(guide_app):
    from conftest import register
    with TestClient(guide_app) as client:
        onboard(client);register(client,'synthetic_return_reader')
        with running(guide_app) as base,sync_playwright() as pw:
            browser=pw.chromium.launch(channel='chrome',headless=True);context=browser.new_context(viewport={'width':1440,'height':900})
            page=context.new_page();page.set_default_timeout(6000);page.goto(base+'/#welcome')
            page.get_by_role('button',name='登入我的世界',exact=True).click()
            page.locator('#username').fill('synthetic_return_reader');page.locator('#password').fill('a-good-password-2026')
            page.locator('#login-form button.primary').click();expect(page.locator('#nav a')).to_have_count(4)
            assert page.locator('.guide-intro').count()==0
            page.goto(base);expect(page.locator('#nav a')).to_have_count(4);assert page.locator('.guide-intro').count()==0
            before=page.request.get(base+'/api/state').json();page.locator('.intro-menu > summary').click();page.get_by_role('button',name='使用教學',exact=True).click()
            expect(page.locator('.guide-tutorial')).to_be_visible();after=page.request.get(base+'/api/state').json()
            assert before['experiences']==after['experiences']==[] and before['rewards']==after['rewards']
            context.close();browser.close()


def test_fixed_example_reveals_without_ai_or_writes(guide_app):
    """正常動畫只整理固定示例；不用等待播完才能前進，也不冒充供應商輸出。"""
    with running(guide_app) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        OUT.mkdir(exist_ok=True)
        context=browser.new_context(viewport={'width':390,'height':900},reduced_motion='no-preference',record_video_dir=str(OUT/'video'))
        page=context.new_page();posts=[]
        page.on('request',lambda r:posts.append(r.url) if '/api/' in r.url and r.method not in ('GET','HEAD') else None)
        page.goto(base);page.get_by_role('button',name='下一步',exact=True).click()
        row=page.locator('.guide-demo-next');assert float(row.evaluate('e=>getComputedStyle(e).opacity'))==0
        expect(page.get_by_role('button',name='看看接下來會發生什麼',exact=True)).to_be_enabled()
        page.wait_for_timeout(6100)
        assert float(row.evaluate('e=>getComputedStyle(e).opacity'))==1
        expect(row).to_contain_text('準備分享或發表')
        shots(page,'390-example-revealed.png')
        page.get_by_role('button',name='看看接下來會發生什麼',exact=True).click()
        expect(page.locator('.guide-room')).to_be_visible()
        page.get_by_role('button',name='開始我的世界',exact=True).click()
        assert posts==[]
        video=page.video;context.close();video.save_as(str(OUT/'product-guide-example.webm'));browser.close()
