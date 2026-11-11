"""以實際本機API驗收人物生日/多份任職畫面；不是PG或Owner UX核准。"""
from pathlib import Path
from uuid import uuid4
import pytest
from playwright.sync_api import expect
from test_journey import page,BASE

ART=Path(__file__).resolve().parents[1]/'docs/integration/2026-11-11/screenshots'


def seed(page):
    page.goto(BASE)
    r=page.request.post(BASE+'/api/auth/guest');assert r.ok
    headers={'X-CSRF-Token':r.json()['csrf_token']}
    assert page.request.put(BASE+'/api/profile',headers=headers,data={'name':'合成測試','bio':'合成資料','timezone':'Asia/Taipei'}).ok
    goal={'request_id':uuid4().hex,'title':'隔離測試目標','outcome':'保存資料','deadline':'2026-11-30','actions':[{'title':x,'unit':'次','target':'10','level':i+1,'weekdays':[0,2,4],'dates':['2026-10-28']} for i,x in enumerate(['閱讀','筆記','分享'])]}
    r=page.request.post(BASE+'/api/goals',headers=headers,data=goal);assert r.ok,r.text()
    r=page.request.post(BASE+'/api/auth/claim',headers=headers,data={'username':'basic_'+uuid4().hex[:12],'password':'synthetic-browser-password-2026'});assert r.ok,r.text()
    headers={'X-CSRF-Token':r.json()['csrf_token']}
    p=page.request.post(BASE+'/api/people',headers=headers,data={'name':'人物小安'}).json()
    return p,headers


@pytest.mark.parametrize('width',[320,390,1440])
def test_person_details_edit_and_history(page,width):
    page.set_viewport_size({'width':width,'height':950})
    p,headers=seed(page)
    page.goto(BASE+'/#persons/'+p['id']);page.reload()
    expect(page.locator('.person-basic-panel')).to_be_visible()
    page.get_by_role('button',name='新增／更正生日').click()
    page.locator('[name=birth_month]').fill('4');page.locator('[name=birth_day]').fill('12')
    ART.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(ART/f'{width}-birthday-input.png'),full_page=True)
    page.get_by_role('button',name='核對並保存',exact=True).click()
    expect(page.locator('#account-dialog')).not_to_be_visible()
    expect(page.locator('.person-basic-panel')).to_contain_text('4 月 12 日')
    for company,title in [('組織A','研究員'),('組織B','設計師')]:
        page.get_by_role('button',name='＋ 新增一筆任職',exact=True).click()
        page.locator('[name=company_name]').fill(company);page.locator('[name=job_title]').fill(title)
        page.locator('[name=employment_status]').select_option('current')
        page.get_by_role('button',name='核對並保存',exact=True).click()
        expect(page.locator('#account-dialog')).not_to_be_visible()
    expect(page.locator('.person-basic-panel')).to_contain_text('組織A')
    expect(page.locator('.person-basic-panel')).to_contain_text('組織B')
    page.reload();expect(page.locator('.person-basic-panel')).to_contain_text('4 月 12 日')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(ART/f'{width}-person-details.png'),full_page=True)
    details=page.request.get(BASE+'/api/people/'+p['id']+'/details').json()
    assert len(details['employments'])==2 and len(details['employment_history'])==2
    assert details['birthday']['birth_year'] is None


def test_saved_draft_delete_only_clears_its_media_scope(page):
    p,headers=seed(page)
    payload={'raw_text':'可刪除合成草稿','occurred_at':'2026-10-27T00:00:00Z','contributions':[]}
    r=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data=payload);assert r.ok,r.text()
    d=r.json();me=page.request.get(BASE+'/api/auth/me').json()
    keys=[me['owner_id']+':draft:'+d['id'],me['owner_id']+':draft:another','other-owner:draft:'+d['id']]
    page.evaluate('''async keys=>{await new Promise((resolve,reject)=>{const req=indexedDB.open('lifeworld-media-local',1);req.onupgradeneeded=()=>req.result.createObjectStore('workspaces');req.onsuccess=()=>{const db=req.result,tx=db.transaction('workspaces','readwrite');for(const k of keys)tx.objectStore('workspaces').put({items:[],fields:{raw_text:'合成素材'}},k);tx.oncomplete=()=>{db.close();resolve();};tx.onerror=reject;};req.onerror=reject;});}''',keys)
    page.goto(BASE+'/#history');page.reload()
    button=page.locator('[data-action=delete-saved-draft][data-id="'+d['id']+'"]')
    expect(button).to_be_visible();button.click()
    expect(page.locator('#account-dialog')).to_contain_text('不是只捨棄未保存修改')
    page.get_by_role('button',name='保留草稿',exact=True).click()
    assert page.request.get(BASE+'/api/drafts/'+d['id']).ok
    button.click();page.get_by_role('button',name='確認刪除草稿',exact=True).click()
    expect(page.locator('#account-dialog')).not_to_be_visible()
    expect(page.locator('[data-action=delete-saved-draft][data-id="'+d['id']+'"]')).to_have_count(0)
    assert page.request.get(BASE+'/api/drafts/'+d['id']).status==404
    present=page.evaluate('''async keys=>await new Promise((resolve,reject)=>{const r=indexedDB.open('lifeworld-media-local',1);r.onsuccess=()=>{const db=r.result,tx=db.transaction('workspaces','readonly'),store=tx.objectStore('workspaces'),results=[];for(const k of keys){const q=store.get(k);q.onsuccess=()=>results.push([k,!!q.result]);}tx.oncomplete=()=>{db.close();resolve(Object.fromEntries(results));};tx.onerror=reject;};})''',keys)
    assert not present[keys[0]] and present[keys[1]] and present[keys[2]]
