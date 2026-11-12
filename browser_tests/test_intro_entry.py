"""產品首次選擇、公開介紹與同瀏覽器偏好；使用本機隔離世界。"""
import os
import pytest
from playwright.sync_api import sync_playwright,expect

URL=os.environ.get('INTRO_PRODUCT_URL','http://127.0.0.1:8215')
KEY='lifeworld:intro:v1'


@pytest.fixture
def page():
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':390,'height':1000})
        yield page
        browser.close()


def marker(page):return page.evaluate('(key)=>JSON.parse(localStorage.getItem(key)||"null")',KEY)


def test_first_choice_and_direct_start_do_not_create_world(page):
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD'] else None)
    page.goto(URL+'/#welcome')
    expect(page.locator('#intro-choice')).to_be_visible()
    assert marker(page) is None
    page.get_by_role('button',name='直接開始',exact=True).click()
    expect(page.locator('#intro-choice')).to_have_count(0)
    expect(page.locator('[data-action=guest]')).to_be_visible()
    assert marker(page)=={'version':1,'outcome':'skipped'}
    page.reload();expect(page.locator('[data-action=guest]')).to_be_visible()
    assert writes==[]


def test_merely_opening_intro_does_not_mark_seen_and_skip_returns_to_welcome(page):
    page.goto(URL+'/#welcome');page.get_by_role('link',name='先認識 Life World',exact=True).click()
    expect(page.locator('.lw-preview')).to_have_attribute('data-phase','welcome')
    assert marker(page) is None
    page.go_back();expect(page.locator('#intro-choice')).to_be_visible()
    page.get_by_role('link',name='先認識 Life World',exact=True).click()
    page.locator('#welcome-copy [data-action=skip]').click()
    assert marker(page)=={'version':1,'outcome':'skipped'}
    expect(page.locator('#product-entry')).to_have_text('開始我的故事')
    page.locator('#product-entry').click()
    expect(page).to_have_url(URL+'/#welcome')
    expect(page.locator('[data-action=guest]')).to_be_visible()
    expect(page.locator('#intro-choice')).to_have_count(0)


def test_complete_demo_marks_only_preference_and_remains_replayable(page):
    writes=[];api_requests=[]
    page.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD'] else None)
    page.on('request',lambda r:api_requests.append(r.url) if '/api/' in r.url else None)
    page.emulate_media(reduced_motion='reduce');page.goto(URL+'/intro?return=https://example.com')
    page.locator('#start').click()
    for _ in range(3):
        page.locator('#advance').click();expect(page.locator('.lw-preview')).to_have_attribute('data-busy','false')
    assert marker(page)=={'version':1,'outcome':'completed'}
    assert page.locator('#product-entry').get_attribute('href')==URL+'/#welcome'
    page.locator('#summary-copy [data-action=restart]').click()
    expect(page.locator('.lw-preview')).to_have_attribute('data-phase','welcome')
    assert marker(page)['outcome']=='completed'
    assert writes==[]
    assert api_requests==[]


def test_menu_reopens_intro_in_new_tab_and_keeps_product_page(page):
    page.goto(URL+'/#welcome');page.get_by_role('button',name='直接開始',exact=True).click()
    page.locator('.intro-menu summary').click()
    with page.expect_popup() as popup:
        page.locator('.intro-menu a').click()
    intro=popup.value;intro.wait_for_load_state()
    expect(intro.locator('#start')).to_be_visible()
    expect(page.locator('[data-action=guest]')).to_be_visible()
    assert marker(page)['outcome']=='skipped'
    intro.close()


@pytest.mark.parametrize('width',[320,390,768,1440])
def test_responsive_intro_keeps_fixed_egg_anchor_and_full_timeline(page,width):
    page.set_viewport_size({'width':width,'height':1000});page.clock.install();page.goto(URL+'/intro')
    page.locator('#start').click()
    def anchor(selector):
        return page.locator(selector).evaluate('e=>{const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+scrollY}}')
    baseline=anchor('#egg')
    for duration in [800,1000]:
        page.locator('#advance').evaluate('e=>e.click()')
        page.locator('#egg').evaluate('e=>e.getAnimations().forEach(a=>{a.pause();a.currentTime=300})')
        assert abs(anchor('#egg')['x']-baseline['x'])<8
        page.clock.run_for(duration)
        assert abs(anchor('#egg')['y']-baseline['y'])<1
    page.locator('#advance').evaluate('e=>e.click()')
    for elapsed,frame in [(650,'shell'),(1000,'peek'),(900,'closed'),(700,'open'),(950,'settled')]:
        page.clock.run_for(elapsed)
        expect(page.locator('.lw-preview')).to_have_attribute('data-reveal',frame)
        assert abs(anchor('#reveal-scene')['y']-baseline['y'])<1
    page.clock.run_for(599);expect(page.locator('#summary-copy')).to_be_hidden()
    page.clock.run_for(1);expect(page.locator('#summary-copy')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')


def test_existing_guest_replay_keeps_unsaved_profile_and_does_not_reprompt(page):
    page.goto(URL+'/#welcome');page.get_by_role('button',name='直接開始',exact=True).click()
    page.locator('[data-action=guest]').click();expect(page.locator('#profile-form')).to_be_visible()
    page.locator('#bio').fill('合成測試：這份尚未保存的介紹要保留')
    # 即使清掉介紹偏好，已有世界仍依既有Bio流程，不插入介紹。
    page.evaluate('(key)=>localStorage.removeItem(key)',KEY)
    page.locator('.intro-menu summary').click()
    with page.expect_popup() as popup:page.locator('.intro-menu a').click()
    intro=popup.value;intro.wait_for_load_state();intro.locator('[data-intro-exit]').click()
    expect(intro.locator('#profile-form')).to_be_visible()
    expect(page.locator('#bio')).to_have_value('合成測試：這份尚未保存的介紹要保留')
    expect(page.locator('#intro-choice')).to_have_count(0)
    intro.close()


@pytest.mark.parametrize('storage',['local','both','corrupt'])
def test_storage_failure_and_corruption_do_not_block_entry(page,storage):
    if storage=='corrupt':
        page.add_init_script("localStorage.setItem('lifeworld:intro:v1','{broken');")
    else:
        names=['localStorage'] if storage=='local' else ['localStorage','sessionStorage']
        page.add_init_script('for(const name of '+str(names).replace("'",'"')+"){Object.defineProperty(window,name,{get(){throw new DOMException('synthetic blocked','SecurityError')}})}")
    page.goto(URL+'/#welcome');page.get_by_role('button',name='直接開始',exact=True).click()
    expect(page.locator('[data-action=guest]')).to_be_visible()
    expect(page.locator('#intro-choice')).to_have_count(0)
    if storage=='local':
        assert page.evaluate('(key)=>JSON.parse(sessionStorage.getItem(key)).outcome',KEY)=='skipped'
        page.reload();expect(page.locator('[data-action=guest]')).to_be_visible()


def test_keyboard_and_200_percent_text_remain_usable(page):
    page.set_viewport_size({'width':320,'height':1000});page.goto(URL+'/#welcome')
    expect(page.locator('#intro-choice')).to_be_visible()
    # 先讀完原字級再逐項加倍，避免巢狀200%造成非預期的指數放大。
    page.evaluate("() => {const sizes=[...document.querySelectorAll('body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);for(const [e,size] of sizes)e.style.fontSize=(size*2)+'px';}")
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.get_by_role('link',name='先認識 Life World',exact=True).focus();page.keyboard.press('Enter')
    expect(page.locator('#start')).to_be_visible()
    page.locator('#welcome-copy [data-action=skip]').focus();page.keyboard.press('Enter')
    page.locator('#product-entry').focus();page.keyboard.press('Enter')
    expect(page.locator('[data-action=guest]')).to_be_visible()


@pytest.mark.parametrize('width',[320,390,1440])
def test_slow_script_load_does_not_accept_a_lost_first_click(page,width):
    """延後主程式，模擬手機首次下載；準備好之前不可接受會落空的操作。"""
    page.set_viewport_size({'width':width,'height':1000});held=[]
    page.route('**/intro/preview.js',lambda route:held.append(route))
    with page.expect_request('**/intro/preview.js'):
        page.goto(URL+'/intro',wait_until='commit')
    expect(page.locator('#start')).to_be_disabled()
    expect(page.locator('#welcome-copy [data-action=skip]')).to_be_disabled()
    expect(page.locator('#music-toggle')).to_be_disabled()
    assert len(held)==1
    held[0].continue_()
    expect(page.locator('#start')).to_be_enabled()
    expect(page.locator('.lw-preview')).to_have_attribute('data-ready','true')
    page.locator('#start').click()
    expect(page.locator('.lw-preview')).to_have_attribute('data-phase','story')
    expect(page.locator('#advance')).to_be_visible()
