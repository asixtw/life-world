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


@pytest.mark.parametrize('width',[390,1440])
def test_source_withdrawal_cancel_and_confirm_keep_history(page,width):
    page.set_viewport_size({'width':width,'height':950})
    p,headers=seed(page);prefix=BASE+'/api/people/'+p['id']
    r=page.request.patch(prefix+'/basic-details',headers=headers,data={'request_id':uuid4().hex,'expected_revision':0,'confirmed':True,'value':{'birth_month':4,'birth_day':12},'source':{'source_kind':'manual'}});assert r.ok,r.text()
    page.goto(BASE+'/#persons/'+p['id']);page.reload()
    page.get_by_role('button',name='撤回這筆資訊的來源',exact=True).click()
    page.get_by_role('button',name='保留來源',exact=True).click()
    assert page.request.get(prefix+'/details').json()['birthday']['source_status']=='active'
    page.get_by_role('button',name='撤回這筆資訊的來源',exact=True).click()
    page.get_by_role('button',name='確認撤回來源',exact=True).click()
    expect(page.locator('#account-dialog')).not_to_be_visible()
    expect(page.locator('.person-basic-panel')).to_contain_text('來源已撤回，待核對')
    d=page.request.get(prefix+'/details').json()
    assert d['birthday']['birth_month']==4 and len(d['birthday_history'])==2
    assert d['birthday_history'][-1]['change_kind']=='source_withdrawn'
    ART.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(ART/f'{width}-source-withdrawn.png'),full_page=True)


def test_saved_multi_person_draft_roundtrip_and_confirm_do_not_drop_targets(page):
    p,headers=seed(page)
    pending=[{'client_ref':'p1','name':'小安','relation':'interaction'},{'client_ref':'p2','name':'小明','relation':'mention','start':8}]
    r=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data={'raw_text':'和小安閱讀，提到小明。','occurred_at':'2026-10-27T00:00:00Z','contributions':[],'story':{'pending_people':pending}});assert r.ok,r.text()
    d=r.json();page.goto(BASE+'/#review/'+d['id']);page.reload()
    expect(page.locator('.pending-people-summary')).to_contain_text('小安')
    expect(page.locator('.pending-people-summary')).to_contain_text('僅在原文中提及')
    collected=page.evaluate('ConnectionsUI.collectEditor(document.querySelector("#review-form"))')
    assert collected['pending_people']==pending
    # 返回原文後保存，名單及client_ref仍在；未確認時沒有新增人物。
    page.get_by_role('button',name='返回修改原始草稿',exact=True).click()
    page.locator('[data-experience-next]').click();page.locator('[data-experience-next]').click()
    page.locator('[data-experience-review]').click()
    expect(page.locator('#review-form')).to_be_visible()
    read=page.request.get(BASE+'/api/drafts/'+d['id']).json();assert read['story']['pending_people']==pending
    assert len(page.request.get(BASE+'/api/state').json()['people'])==1
    page.locator('#story-reviewed').check();page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    expect(page.locator('#review-form')).to_have_count(0)
    world=page.request.get(BASE+'/api/state').json()
    assert len(world['people'])==3 and len(world['experiences'])==1


@pytest.mark.parametrize('changed',[False,True])
def test_manual_summary_survives_return_and_requires_review_when_raw_changes(page,changed):
    p,headers=seed(page)
    r=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data={'raw_text':'今天閱讀了一章。','occurred_at':'2026-10-27T00:00:00Z','contributions':[]});assert r.ok
    d=r.json();page.goto(BASE+'/#review/'+d['id']);page.reload()
    page.locator('#summary').fill('這是我手動整理的摘要。')
    page.get_by_role('button',name='返回修改原始草稿',exact=True).click()
    if changed:page.locator('#raw-text').fill('今天閱讀了兩章，仍有問題待釐清。')
    page.locator('[data-experience-next]').click();page.locator('[data-experience-next]').click();page.locator('[data-experience-review]').click()
    expect(page.locator('#summary')).to_have_value('這是我手動整理的摘要。')
    review=page.locator('[data-summary-source-review]')
    if changed:
        expect(review).to_be_visible()
        expect(review).not_to_be_checked()
        page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
        assert not page.request.get(BASE+'/api/state').json()['experiences']
        review.check()
        # 重核對後只返回查看、不再改原文，不應重新索取同一次核對。
        page.get_by_role('button',name='返回修改原始草稿',exact=True).click()
        page.locator('[data-experience-next]').click();page.locator('[data-experience-next]').click();page.locator('[data-experience-review]').click()
        expect(page.locator('[data-summary-source-review]')).to_have_count(0)
        expect(page.locator('#summary')).to_have_value('這是我手動整理的摘要。')
    else:expect(review).to_have_count(0)
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    expect(page.locator('#review-form')).to_have_count(0)
    result=page.request.get(BASE+'/api/state').json()['experiences']
    assert len(result)==1 and result[0]['summary']=='這是我手動整理的摘要。'



def test_unsaved_summary_does_not_leak_into_another_draft(page):
    p,headers=seed(page)
    def create(text):
        r=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data={'raw_text':text,'occurred_at':'2026-10-27T00:00:00Z','contributions':[]});assert r.ok;return r.json()
    first=create('第一份原文');second=create('第二份不同原文')
    page.goto(BASE+'/#review/'+first['id']);page.reload();page.locator('#summary').fill('只屬於第一份的摘要')
    page.locator('#nav').get_by_role('link',name='紀錄',exact=True).click()
    page.get_by_role('button',name='捨棄未保存修改並離開',exact=True).click()
    page.locator('a[href="#review/'+second['id']+'"]').click()
    expect(page.locator('#summary')).to_have_value('第二份不同原文')
    expect(page.locator('[data-summary-source-review]')).to_have_count(0)


@pytest.mark.parametrize('width',[320,390,1440])
def test_two_pending_people_can_be_added_with_independent_roles_before_confirm(page,width):
    page.set_viewport_size({'width':width,'height':950})
    p,headers=seed(page);page.goto(BASE+'/#record');page.reload()
    page.locator('#raw-text').fill('和小安閱讀，提到小明。');page.locator('#occurred-at').fill('2026-10-27T12:00')
    page.locator('[data-experience-next]').click();page.locator('#goal-id').select_option('');page.locator('[data-experience-next]').click()
    page.get_by_role('button',name='＋ 新增人物',exact=True).click();page.locator('#pending-person-name').fill('小安');page.locator('#pending-person-relation').select_option('interaction')
    page.get_by_role('button',name='再加入一位人物',exact=True).click()
    rows=page.locator('[data-pending-target]');expect(rows).to_have_count(2)
    rows.nth(1).locator('[data-target-name]').fill('小明')
    page.locator('[data-experience-review]').click()
    expect(page.locator('#notice')).to_contain_text('稱呼與角色')
    expect(page.locator('[data-experience-step="3"]')).to_be_visible()
    assert not page.request.get(BASE+'/api/state').json()['drafts']
    rows.nth(1).locator('[data-target-role]').select_option('mention');rows.nth(1).locator('[data-target-start]').select_option('8')
    page.get_by_role('button',name='再加入一位人物',exact=True).click()
    expect(rows).to_have_count(3);rows.nth(2).get_by_role('button',name='移除這位待建人物',exact=True).click();expect(rows).to_have_count(2)
    expect(rows.nth(0).locator('[data-target-name]')).to_have_value('小安')
    expect(rows.nth(1).locator('[data-target-name]')).to_have_value('小明')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    ART.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(ART/f'{width}-step3-two-pending.png'),full_page=True)
    assert len(page.request.get(BASE+'/api/state').json()['people'])==1
    page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible()
    pending=page.request.get(BASE+'/api/drafts/'+page.evaluate('state.draft.id')).json()['story']['pending_people']
    assert [x['relation'] for x in pending]==['interaction','mention'] and len({x['client_ref'] for x in pending})==2
    page.locator('#story-reviewed').check()
    page.route('**/api/drafts/*/confirm',lambda route:route.fulfill(status=503,json={'error':{'code':'synthetic_failure','message':'合成確認失敗'}}))
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    expect(page.locator('#notice')).to_contain_text('合成確認失敗')
    expect(rows).to_have_count(2)
    assert len(page.request.get(BASE+'/api/state').json()['people'])==1
    page.unroute('**/api/drafts/*/confirm')
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    world=page.request.get(BASE+'/api/state').json();assert len(world['people'])==3 and len(world['experiences'])==1
    for name,count in [('小安',1),('小明',0)]:
        person=next(x for x in world['people'] if x['name']==name)
        assert page.request.get(BASE+'/api/people/'+person['id']+'/overview').json()['stats']['interactions']==count


@pytest.mark.parametrize('related',[False,True])
def test_partial_multi_person_local_draft_survives_leaving_and_new_page(page,related):
    p,h=seed(page);page.goto(BASE+'/#record');page.reload()
    page.locator('#raw-text').fill('尚未完成的人物草稿。');page.locator('#occurred-at').fill('2026-10-27T12:00')
    page.locator('[data-experience-next]').click();page.locator('[data-experience-next]').click()
    page.get_by_role('button',name='＋ 新增人物',exact=True).click();page.locator('#pending-person-name').fill('待建甲')
    page.get_by_role('button',name='再加入一位人物',exact=True).click();page.locator('[data-pending-target]').nth(1).locator('[data-target-name]').fill('待建乙')
    refs=page.locator('[data-pending-target]').evaluate_all('(rows)=>rows.map(r=>r.dataset.clientRef)')
    if not related:page.locator('#include-story').uncheck()
    page.locator('#nav').get_by_role('link',name='世界',exact=True).click();page.get_by_role('button',name='保留此裝置草稿並離開',exact=True).click()
    expect(page.locator('#world-relationships')).to_be_visible()
    restored=page.context.new_page()
    try:
        restored.goto(BASE+'/#record');expect(restored.locator('#raw-text')).to_have_value('尚未完成的人物草稿。')
        restored.locator('[data-experience-next]').click();restored.locator('[data-experience-next]').click()
        rows=restored.locator('[data-pending-target]');expect(rows).to_have_count(2)
        assert rows.evaluate_all('(rows)=>rows.map(r=>r.dataset.clientRef)')==refs
        assert restored.locator('#include-story').is_checked()==related
        expect(rows.nth(0).locator('[data-target-name]')).to_have_value('待建甲')
        expect(rows.nth(1).locator('[data-target-name]')).to_have_value('待建乙')
        expect(rows.nth(1).locator('[data-target-role]')).to_have_value('')
        assert len(restored.request.get(BASE+'/api/state').json()['people'])==1
    finally:restored.close()


@pytest.mark.parametrize('width',[320,390])
def test_mobile_record_focus_has_explicit_exit_and_restores_navigation(page,width):
    page.set_viewport_size({'width':width,'height':950});p,h=seed(page);page.goto(BASE+'/#record');page.reload()
    expect(page.locator('#nav')).not_to_be_visible()
    page.locator('#raw-text').fill('手機專注記錄，不遺失內容。');page.locator('#occurred-at').fill('2026-10-27T12:00')
    page.get_by_role('button',name='離開記錄',exact=True).click();expect(page.locator('#account-dialog')).to_contain_text('尚未保存')
    page.get_by_role('button',name='繼續編輯',exact=True).click();expect(page.locator('#raw-text')).to_have_value('手機專注記錄，不遺失內容。')
    page.locator('[data-experience-next]').click();page.locator('#goal-id').select_option('');page.locator('[data-experience-next]').click();page.locator('[data-experience-review]').click()
    expect(page.locator('#review-form')).to_be_visible();expect(page.locator('#nav')).not_to_be_visible()
    d=page.evaluate('state.draft.id')
    page.get_by_role('button',name='離開記錄',exact=True).click()
    expect(page.locator('#nav')).to_be_visible();assert page.request.get(BASE+'/api/drafts/'+d).ok


def test_pending_person_capacity_refuses_extra_without_losing_existing_names(page):
    p,h=seed(page)
    pending=[{'client_ref':'capacity-'+str(i),'name':'待建'+str(i),'relation':'participant'} for i in range(100)]
    r=page.request.post(BASE+'/api/experiences/drafts',headers=h,data={'raw_text':'容量合成測試','occurred_at':'2026-10-27T00:00:00Z','contributions':[],'story':{'pending_people':pending}});assert r.ok
    d=r.json();page.goto(BASE+'/#review/'+d['id']);page.reload()
    expect(page.locator('[data-pending-target]')).to_have_count(100)
    page.locator('[data-review-people-editor] > summary').click() # 修改區預設收合，使用者明確展開後才操作。
    page.get_by_role('button',name='＋ 新增人物',exact=True).click()
    expect(page.locator('#notice')).to_contain_text('最多100位待建人物')
    expect(page.locator('[data-pending-target]')).to_have_count(100)
    assert len(page.request.get(BASE+'/api/drafts/'+d['id']).json()['story']['pending_people'])==100
    assert len(page.request.get(BASE+'/api/state').json()['people'])==1


@pytest.mark.parametrize('width',[320,390,1440])
def test_step4_relationship_preview_is_read_only_and_keeps_people_separate(page,width):
    page.set_viewport_size({'width':width,'height':950});p,h=seed(page)
    pending=[{'client_ref':'first','name':'待建甲','relation':'interaction'},{'client_ref':'second','name':'待建乙','relation':'mention','start':5}]
    raw='甲談到：待建乙。'
    # 引文位置以Unicode字元索引為準，不靠同名配對。
    pending[1]['start']=raw.index('待建乙')
    r=page.request.post(BASE+'/api/experiences/drafts',headers=h,data={'raw_text':raw,'occurred_at':'2026-10-27T00:00:00Z','contributions':[],'story':{'participants':[{'person_id':p['id'],'interacted':False}],'pending_people':pending}});assert r.ok,r.text()
    d=r.json();page.goto(BASE+'/#review/'+d['id']);page.reload()
    expect(page.locator('[data-review-people-editor]')).not_to_have_attribute('open','')
    expect(page.locator('#media-panel')).not_to_be_visible()
    page.locator('[data-review-raw] > summary').click();expect(page.locator('#media-panel')).to_be_visible()
    page.locator('[data-review-raw] > summary').click()
    cards=page.locator('[data-experience-preview]');expect(cards).to_have_count(3)
    writes=[];page.on('request',lambda req:writes.append(req.url) if req.method in ['POST','PUT','PATCH','DELETE'] else None)
    before=page.request.get(BASE+'/api/state').json()
    cards.filter(has_text='待建乙').click()
    preview=page.locator('#experience-person-preview');expect(preview).to_be_visible()
    expect(preview).to_contain_text('待建乙');expect(preview).to_contain_text('僅在原文中提及')
    expect(preview).not_to_contain_text('待建甲')
    expect(preview).to_contain_text('尚未正式保存')
    ART.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(ART/f'{width}-step4-person-preview.png'),full_page=False)
    footer=preview.get_by_role('button',name='完成檢視',exact=True);assert footer.bounding_box()['y']+footer.bounding_box()['height']<=950
    footer.click();expect(preview).not_to_be_visible()
    expect(cards.filter(has_text='待建乙')).to_be_focused()
    cards.filter(has_text=p['name']).click();expect(preview).to_contain_text('這次只關聯人物')
    page.keyboard.press('Escape');expect(preview).not_to_be_visible()
    assert writes==[] and page.request.get(BASE+'/api/state').json()==before
    ART.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(ART/f'{width}-step4-summary.png'),full_page=True)



@pytest.mark.parametrize('width',[320,390,1440])
def test_person_preview_long_source_scrolls_without_moving_footer(page,width):
    page.set_viewport_size({'width':width,'height':850});p,h=seed(page)
    raw='合成長原文，僅供捲動驗收。\n'*500
    r=page.request.post(BASE+'/api/experiences/drafts',headers=h,data={'raw_text':raw,'occurred_at':'2026-10-27T00:00:00Z','contributions':[],'story':{'participants':[{'person_id':p['id'],'interacted':True}]}});assert r.ok
    page.goto(BASE+'/#review/'+r.json()['id']);page.reload();page.locator('[data-experience-preview]').click()
    preview=page.locator('#experience-person-preview');preview.locator('summary').click()
    body=preview.locator('.experience-preview-body');footer=preview.get_by_role('button',name='完成檢視',exact=True)
    first=footer.bounding_box();body.evaluate('(e)=>{e.scrollTop=e.scrollHeight}')
    assert body.evaluate('(e)=>e.scrollTop>0')
    assert abs(footer.bounding_box()['y']-first['y'])<1
    assert footer.bounding_box()['y']+footer.bounding_box()['height']<=850
    preview.evaluate('(e)=>e.style.fontSize="24px"')
    assert preview.evaluate('(e)=>getComputedStyle(e).fontSize')=='24px'
    assert footer.bounding_box()['y']+footer.bounding_box()['height']<=850
    footer.click();expect(preview).not_to_be_visible()


@pytest.mark.parametrize('change_role',[False,True])
def test_person_review_is_unique_and_resets_only_after_relationship_change(page,change_role):
    p,h=seed(page)
    r=page.request.post(BASE+'/api/experiences/drafts',headers=h,data={'raw_text':'與人物小安一起閱讀。','occurred_at':'2026-10-27T00:00:00Z','contributions':[],'story':{'participants':[{'person_id':p['id'],'interacted':True}]}});assert r.ok
    page.goto(BASE+'/#review/'+r.json()['id']);page.reload()
    page.locator('#story-reviewed').check();page.get_by_role('button',name='返回修改原始草稿',exact=True).click()
    page.locator('[data-experience-next]').click();page.locator('[data-experience-next]').click()
    if change_role:page.locator('[name=story_interacted]').uncheck()
    page.locator('[data-experience-review]').click()
    checkbox=page.locator('#story-reviewed');expect(checkbox).to_have_count(1)
    assert checkbox.is_checked()==(not change_role)
    if change_role:
        page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
        assert not page.request.get(BASE+'/api/state').json()['experiences']
        checkbox.check()
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    assert page.request.get(BASE+'/api/people/'+p['id']+'/overview').json()['stats']['interactions']==(0 if change_role else 1)


def test_new_draft_revision_keeps_edited_goal_quantity_in_summary_and_confirm(page):
    p,h=seed(page);world=page.request.get(BASE+'/api/state').json();goal=world['goals'][0];action=goal['actions'][0]
    r=page.request.post(BASE+'/api/experiences/drafts',headers=h,data={'raw_text':'完成一次閱讀。','occurred_at':'2026-10-27T00:00:00Z','goal_id':goal['id'],'contributions':[{'action_id':action['id'],'quantity':'0.5'}]});assert r.ok,r.text()
    d=r.json();page.goto(BASE+'/#review/'+d['id']);page.reload()
    page.get_by_role('button',name='返回修改原始草稿',exact=True).click();page.locator('[data-experience-next]').click()
    page.locator('[name="quantity-'+action['id']+'"]').fill('0.75');page.locator('[data-experience-next]').click();page.locator('[data-experience-review]').click()
    expect(page.locator('#experience-review-overview')).to_contain_text('0.75')
    expect(page.locator('[name="quantity-'+action['id']+'"]')).to_have_value('0.75')
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    after=page.request.get(BASE+'/api/state').json()
    assert after['goals'][0]['actions'][0]['progress']=='0.75' and len(after['rewards']['events'])==1
