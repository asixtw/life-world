"""真瀏覽器／本機API，GIS是明示替身；不等於真Google驗收。"""
from test_journey import set_occurred
import os,uuid
import pytest
from playwright.sync_api import expect
from test_journey import page
BASE=os.environ.get('GOOGLE_TRANSITION_TEST_URL','http://127.0.0.1:8010')
SDK="""window.google={accounts:{id:{initialize:c=>window.fixtureGIS=c,renderButton:node=>{node.innerHTML='<button type="button" id="fixture-google">明示Google驗證替身</button>';node.firstChild.onclick=()=>window.fixtureGIS.callback({credential:'fixture:'+window.fixtureSubject+':'+window.fixtureGIS.nonce});},cancel:()=>{}}}};"""


def world(page,title):
    page.goto(BASE);r=page.request.post(BASE+'/api/auth/guest');me=r.json();h={'X-CSRF-Token':me['csrf_token'],'Origin':BASE}
    assert page.request.put(BASE+'/api/profile',headers=h,data={'name':title,'bio':'合成','timezone':'Asia/Taipei'}).status==200
    goal=page.request.post(BASE+'/api/goals',headers=h,data={'request_id':uuid.uuid4().hex,'title':title,'outcome':'合成作品','deadline':'2026-11-30','actions':[{'title':s,'dates':['2026-10-27']} for s in ['閱讀','整理','練習']]}).json()
    page.reload();return me,goal,h


def sdk(page,subject):
    page.evaluate('(value)=>window.fixtureSubject=value',subject);page.route('https://accounts.google.com/gsi/client',lambda route:route.fulfill(body=SDK,content_type='application/javascript'))


@pytest.mark.parametrize('width',[390,1440])
def test_upgrade_stays_on_unsaved_record_and_keeps_owner(page,width):
    page.set_viewport_size({'width':width,'height':1000});me,g,h=world(page,'原訪客世界');page.goto(BASE+'/#record');page.locator('#raw-text').fill('尚未保存的碎片文字與原本選擇')
    sdk(page,'upgrade-'+uuid.uuid4().hex);page.locator('#account-button').click();page.get_by_role('button',name='保存目前世界',exact=True).click();page.locator('#fixture-google').click()
    expect(page.locator('#account-dialog')).not_to_be_visible();expect(page.locator('#raw-text')).to_have_value('尚未保存的碎片文字與原本選擇');assert page.url.endswith('/#record')
    after=page.request.get(BASE+'/api/auth/me').json();assert after['owner_id']==me['owner_id'] and after['status']=='registered'
    assert page.request.get(BASE+'/api/state').json()['goals'][0]['id']==g['id']


def test_cancel_and_unknown_login_preserve_guest(page):
    me,_,_=world(page,'保留訪客');sdk(page,'missing-'+uuid.uuid4().hex);page.locator('#account-button').click();page.get_by_role('button',name='登入以前的世界',exact=True).click()
    expect(page.locator('#account-dialog')).to_contain_text('至少14天')
    page.locator('[data-action="google-start"]').click();expect(page.locator('#dialog-error')).to_contain_text('先確認')
    page.locator('#google-discard').check();page.locator('[data-action="google-start"]').click();page.locator('[data-action="google-cancel"]').click()
    assert page.request.get(BASE+'/api/auth/me').json()['owner_id']==me['owner_id']
    page.locator('[data-action="google-start"]').click();page.locator('#fixture-google').click();expect(page.locator('#dialog-error')).to_contain_text('尚無既有世界')
    assert page.request.get(BASE+'/api/auth/me').json()['owner_id']==me['owner_id']


@pytest.mark.parametrize('lost_response',[False,True])
def test_existing_world_switch_and_local_cleanup_are_owner_scoped(page,lost_response):
    # 先在另一瀏覽器建立已綁定的合成世界；同一subject稍後只可回到此Owner。
    target_context=page.context.browser.new_context();target=target_context.new_page();me,g,h=world(target,'既有正式世界');subject='return-'+uuid.uuid4().hex
    ch=target.request.post(BASE+'/api/auth/external/challenge',headers=h,data={'mode':'upgrade'}).json();r=target.request.post(BASE+'/api/auth/external/exchange',headers=h,data={'challenge_id':ch['challenge_id'],'credential':'fixture:'+subject+':'+ch['nonce']});assert r.status==200
    source,_,_=world(page,'將被放棄的訪客');page.goto(BASE+'/#record');page.locator('#raw-text').fill('不能帶入正式世界的訪客內容')
    page.evaluate('''async owners=>new Promise((resolve,reject)=>{const q=indexedDB.open('lifeworld-media-local',1);q.onupgradeneeded=()=>q.result.createObjectStore('workspaces');q.onsuccess=()=>{const db=q.result,tx=db.transaction('workspaces','readwrite');for(const owner of owners)tx.objectStore('workspaces').put({items:[],fields:[]},owner+':sentinel');tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>reject(tx.error);};})''',[source['owner_id'],me['owner_id'],'unrelated-owner'])
    sdk(page,subject);calls=[]
    def exchange(route):
        calls.append(1);response=route.fetch()
        # 模擬Cookie已輪替、JSON回應中斷；必須讀Session及收據，不重送交換。
        route.fulfill(response=response,body='{invalid-json' if lost_response else response.body())
    page.route('**/api/auth/external/exchange',exchange)
    page.locator('#account-button').click();page.get_by_role('button',name='登入以前的世界',exact=True).click();page.locator('#google-discard').check();page.locator('[data-action="google-start"]').click();page.locator('#fixture-google').click()
    expect(page.locator('#account-dialog')).not_to_be_visible();expect(page.locator('.home-lumi')).to_be_visible();assert page.request.get(BASE+'/api/auth/me').json()['owner_id']==me['owner_id'];assert page.request.get(BASE+'/api/state').json()['goals'][0]['id']==g['id'];assert len(calls)==1
    page.wait_for_function('''async owner=>new Promise(resolve=>{const q=indexedDB.open('lifeworld-media-local',1);q.onsuccess=()=>{const db=q.result,tx=db.transaction('workspaces'),r=tx.objectStore('workspaces').getAllKeys();r.onsuccess=()=>{db.close();resolve(!r.result.includes(owner+':sentinel'));};};})''',arg=source['owner_id'])
    remaining=page.evaluate('''async()=>new Promise(resolve=>{const q=indexedDB.open('lifeworld-media-local',1);q.onsuccess=()=>{const db=q.result,r=db.transaction('workspaces').objectStore('workspaces').getAllKeys();r.onsuccess=()=>{db.close();resolve(r.result);};};})''')
    assert me['owner_id']+':sentinel' in remaining and 'unrelated-owner:sentinel' in remaining
    target_context.close()

@pytest.mark.parametrize('width',[390,1440])
def test_step3_upgrade_unlocks_people_without_changing_choice_or_form(page,width):
    page.set_viewport_size({'width':width,'height':950})
    me,g,h=world(page,'第三步保留世界')
    page.goto(BASE+'/#record');page.locator('#raw-text').fill('尚未保存，沒有關聯人物。')
    set_occurred(page,'2026-10-27T12:00')
    page.locator('[data-experience-next]').click();page.locator('[name^="quantity-"]').first.fill('2')
    page.locator('[data-experience-next]').click()
    page.evaluate('window.originalRecordForm=document.querySelector("#record-form");window.originalRaw=document.querySelector("#raw-text")')
    sdk(page,'step3-'+uuid.uuid4().hex)
    page.locator('#account-button').click();page.get_by_role('button',name='保存目前世界',exact=True).click();page.locator('#fixture-google').click()
    expect(page.locator('#account-dialog')).not_to_be_visible()
    expect(page.locator('[data-experience-step="3"] [data-story-editor]')).to_be_visible()
    expect(page.locator('#include-story')).not_to_be_checked()
    assert page.evaluate('window.originalRecordForm===document.querySelector("#record-form")&&window.originalRaw===document.querySelector("#raw-text")')
    expect(page.locator('#raw-text')).to_have_value('尚未保存，沒有關聯人物。')
    expect(page.locator('[name^="quantity-"]').first).to_have_value('2')
    assert page.request.get(BASE+'/api/auth/me').json()['owner_id']==me['owner_id']
    from pathlib import Path
    art=Path(__file__).resolve().parents[1]/'docs/integration/2026-11-11/screenshots'
    art.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(art/f'{width}-step3-upgrade-unlocked.png'),full_page=True)
    page.locator('[data-experience-review]').click()
    expect(page.locator('#review-form')).to_be_visible()
    expect(page.locator('#review-form [name=summary]')).to_have_value('尚未保存，沒有關聯人物。')


def test_step3_upgrade_cancel_and_rejected_exchange_preserve_inputs(page):
    me,g,h=world(page,'取消保留第三步');page.goto(BASE+'/#record')
    page.locator('#raw-text').fill('取消或失敗仍保留這段內容。');set_occurred(page,'2026-10-27T12:00')
    page.locator('[data-experience-next]').click();page.locator('[data-experience-next]').click()
    sdk(page,'reject-step3-'+uuid.uuid4().hex)
    page.locator('#account-button').click();page.get_by_role('button',name='保存目前世界',exact=True).click()
    page.locator('[data-action="google-cancel"]').click()
    expect(page.locator('#raw-text')).to_have_value('取消或失敗仍保留這段內容。')
    expect(page.locator('[data-experience-step="3"]')).to_be_visible()
    # 明示錯誤Token，不把GIS替身測試當成真Google驗證。
    page.locator('[data-action="google-start"]').click()
    expect(page.locator('#fixture-google')).to_be_visible()
    page.evaluate("window.fixtureGIS.callback({credential:'invalid-fixture'})")
    expect(page.locator('#dialog-error')).to_contain_text('拒絕')
    after=page.request.get(BASE+'/api/auth/me').json()
    assert after['owner_id']==me['owner_id'] and after['status']=='guest'
    expect(page.locator('#raw-text')).to_have_value('取消或失敗仍保留這段內容。')
    expect(page.locator('[data-experience-step="3"][data-guest-locked="true"]')).to_be_visible()
