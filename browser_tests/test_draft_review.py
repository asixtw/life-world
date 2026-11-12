"""實際本機API保存核對草稿；不是外部AI或Alpha驗收。"""
from test_journey import supplement_source
from test_journey import set_occurred
import hashlib
import pytest
from playwright.sync_api import expect
from test_journey import page,BASE
from test_integration_person_details import seed,ART


@pytest.mark.parametrize('width',[320,390,1440])
def test_review_summary_tasks_survive_save_reload_and_confirm(page,width):
    page.set_viewport_size({'width':width,'height':950})
    _,headers=seed(page);raw='手動記錄原始經歷。'
    r=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data={'raw_text':raw,'occurred_at':'2026-10-27T00:00:00Z','contributions':[],'review':{'summary':'已保存的人工摘要','summary_source_sha256':hashlib.sha256(raw.encode()).hexdigest(),'tasks':['已保存任務']}})
    assert r.ok,r.text();d=r.json()
    page.goto(BASE+'/#review/'+d['id']);page.reload()
    expect(page.locator('#summary')).to_have_value('已保存的人工摘要')
    page.locator('[data-review-tasks] summary').click()
    expect(page.locator('[name=tasks]')).to_have_value('已保存任務')
    page.locator('#summary').fill('再次修改的摘要');page.locator('[name=tasks]').fill('再次修改的任務')
    page.get_by_role('button',name='保存核對草稿並離開',exact=True).click()
    expect(page.locator('#review-form')).to_have_count(0)
    read=page.request.get(BASE+'/api/drafts/'+d['id']).json()
    assert read['review']['summary']=='再次修改的摘要' and read['review']['tasks']==['再次修改的任務']
    state=page.request.get(BASE+'/api/state').json();assert not state['experiences'] and not state['tasks'] and not state['rewards']['events']
    page.goto(BASE+'/#review/'+d['id']);page.reload()
    expect(page.locator('#summary')).to_have_value('再次修改的摘要')
    ART.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(ART/f'{width}-saved-review-roundtrip.png'),full_page=True)
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    expect(page.locator('#review-form')).to_have_count(0)
    state=page.request.get(BASE+'/api/state').json()
    assert len(state['experiences'])==len(state['tasks'])==len(state['rewards']['events'])==1
    assert state['experiences'][0]['summary']=='再次修改的摘要'


def test_review_save_failure_keeps_inputs_and_source_recheck_survives_reload(page):
    _,headers=seed(page);raw='舊原文。'
    r=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data={'raw_text':raw,'occurred_at':'2026-10-27T00:00:00Z','contributions':[],'review':{'summary':'人工保留摘要','summary_source_sha256':hashlib.sha256(raw.encode()).hexdigest(),'tasks':[]}});assert r.ok
    d=r.json()
    changed=page.request.put(BASE+'/api/drafts/'+d['id'],headers=headers,data={'raw_text':'新原文。','occurred_at':d['occurred_at'],'expected_revision':d['revision'],'contributions':[]});assert changed.ok
    page.goto(BASE+'/#review/'+d['id']);page.reload()
    expect(page.locator('#summary')).to_have_value('人工保留摘要')
    expect(page.locator('[data-summary-source-review]')).not_to_be_checked()
    page.locator('#summary').fill('失敗時也應保留的摘要')
    page.route('**/api/drafts/'+d['id'],lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":{"code":"temporarily_unavailable","message":"隔離測試暫時失敗"}}') if route.request.method=='PUT' else route.continue_())
    page.get_by_role('button',name='保存核對草稿並離開',exact=True).click()
    expect(page.locator('#summary')).to_have_value('失敗時也應保留的摘要')
    assert page.request.get(BASE+'/api/drafts/'+d['id']).json()['review']['summary']=='人工保留摘要'
    page.unroute('**/api/drafts/'+d['id'])
    page.locator('[data-summary-source-review]').check()
    page.get_by_role('button',name='離開記錄',exact=True).click()
    expect(page.locator('#account-dialog')).to_be_visible()
    page.get_by_role('button',name='先存草稿並離開',exact=True).click()
    expect(page.locator('#review-form')).to_have_count(0)
    page.goto(BASE+'/#review/'+d['id']);page.reload()
    expect(page.locator('#summary')).to_have_value('失敗時也應保留的摘要')
    expect(page.locator('[data-summary-source-review]')).to_have_count(0)


def test_saving_unreviewed_summary_does_not_silently_accept_missing_source_hash(page):
    _,headers=seed(page)
    r=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data={'raw_text':'原始內容。','occurred_at':'2026-10-27T00:00:00Z','contributions':[],'review':{'summary':'尚待核對摘要','tasks':[]}});assert r.ok
    d=r.json();assert d['review']['summary_needs_review']
    page.goto(BASE+'/#review/'+d['id']);page.reload()
    expect(page.locator('[data-summary-source-review]')).not_to_be_checked()
    page.get_by_role('button',name='保存核對草稿並離開',exact=True).click()
    expect(page.locator('#review-form')).to_have_count(0)
    read=page.request.get(BASE+'/api/drafts/'+d['id']).json()
    assert read['review']['summary_needs_review'], '保存草稿不得等同來源核對'
    page.goto(BASE+'/#review/'+d['id']);page.reload()
    expect(page.locator('[data-summary-source-review]')).not_to_be_checked()


@pytest.mark.parametrize('width',[320,390,1440])
def test_two_person_review_candidates_are_checked_independently_before_confirm(page,width):
    page.set_viewport_size({'width':width,'height':950})
    person,headers=seed(page);raw='小安說喜歡登山，小明只在原文被提到。'
    review={'summary':'人工摘要','summary_source_sha256':hashlib.sha256(raw.encode()).hexdigest(),'tasks':[],'person_candidates':[
        {'candidate_ref':'fact-a','target':{'person_id':person['id']},'expected_person_revision':person['revision'],'dimension':'interests','value':'登山','source_kind':'manual','evidence_type':'stated_by_person'},
        {'candidate_ref':'fact-b','target':{'client_ref':'new-b'},'dimension':'food','value':'清淡','source_kind':'manual','evidence_type':'observed_by_user'}]}
    r=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data={'raw_text':raw,'occurred_at':'2026-10-27T00:00:00Z','contributions':[],'story':{'participants':[{'person_id':person['id'],'interacted':True}],'pending_people':[{'client_ref':'new-b','name':'小明','relation':'mention','start':raw.index('小明')}]},'review':review});assert r.ok,r.text();d=r.json()
    page.goto(BASE+'/#review/'+d['id']);page.reload()
    page.locator('[data-experience-preview="existing:'+person['id']+'"]').click()
    expect(page.locator('#experience-person-preview')).to_contain_text('登山')
    expect(page.locator('#experience-person-preview')).not_to_contain_text('清淡')
    page.locator('[data-candidate-select="fact-a"]').check()
    page.get_by_role('button',name='完成檢視',exact=True).click()
    page.locator('[data-experience-preview="pending:new-b"]').click()
    expect(page.locator('#experience-person-preview')).to_contain_text('清淡')
    page.locator('[data-candidate-exclude="fact-b"]').click()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    ART.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(ART/f'{width}-targeted-candidate-review.png'))
    page.get_by_role('button',name='完成檢視',exact=True).click()
    page.get_by_role('button',name='保存核對草稿並離開',exact=True).click()
    expect(page.locator('#review-form')).to_have_count(0)
    saved=page.request.get(BASE+'/api/drafts/'+d['id']).json()['review']['person_candidates']
    assert saved[0]['selected'] and saved[1]['excluded']
    page.goto(BASE+'/#review/'+d['id']);page.reload()
    page.locator('#story-reviewed').check()
    assert not page.request.get(BASE+'/api/people/'+person['id']+'/overview').json()['facts']['interests']
    if width==390:
        page.route('**/api/drafts/'+d['id']+'/confirm',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":{"code":"temporarily_unavailable","message":"合成確認失敗"}}'))
        page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
        expect(page.locator('#notice')).to_contain_text('合成確認失敗')
        assert not page.request.get(BASE+'/api/state').json()['experiences']
        page.unroute('**/api/drafts/'+d['id']+'/confirm')
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    expect(page.locator('#review-form')).to_have_count(0)
    state=page.request.get(BASE+'/api/state').json();new=next(p for p in state['people'] if p['name']=='小明')
    a=page.request.get(BASE+'/api/people/'+person['id']+'/overview').json()['facts']
    b=page.request.get(BASE+'/api/people/'+new['id']+'/overview').json()['facts']
    assert a['interests'][0]['value']=='登山' and not b['food']
    assert len(state['experiences'])==len(state['rewards']['events'])==1


def test_raw_candidate_recheck_and_missing_evidence_do_not_guess_or_write_early(page):
    person,headers=seed(page);raw='本人說喜歡閱讀。';digest=hashlib.sha256(raw.encode()).hexdigest()
    r=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data={'raw_text':raw,'occurred_at':'2026-10-27T00:00:00Z','contributions':[],'story':{'participants':[{'person_id':person['id'],'interacted':True}]},'review':{'summary':raw,'summary_source_sha256':digest,'tasks':[],'person_candidates':[{'candidate_ref':'needs-evidence','target':{'person_id':person['id']},'expected_person_revision':person['revision'],'dimension':'interests','value':'閱讀','source_kind':'raw','source_sha256':'0'*64,'quote':'喜歡閱讀'}]}});assert r.ok,r.text();d=r.json()
    page.goto(BASE+'/#review/'+d['id']);page.reload()
    card=page.locator('[data-experience-preview="existing:'+person['id']+'"]');card.click()
    evidence=page.locator('[data-candidate-evidence="needs-evidence"]')
    expect(evidence).to_have_value('')
    # 缺證據不能採用；不是把manual/raw當成本人告知或觀察。
    page.locator('[data-candidate-select="needs-evidence"]').click()
    expect(page.locator('[data-candidate-select="needs-evidence"]')).not_to_be_checked()
    evidence.select_option('stated_by_person')
    page.locator('[data-candidate-select="needs-evidence"]').check()
    expect(page.locator('[data-candidate-result]')).to_have_text('確認後會保存')
    page.get_by_role('button',name='完成檢視',exact=True).click();expect(card).to_be_focused()
    assert not page.request.get(BASE+'/api/people/'+person['id']+'/overview').json()['facts']['interests']
    page.locator('#story-reviewed').check()
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    expect(page.locator('#review-form')).to_have_count(0)
    assert page.request.get(BASE+'/api/people/'+person['id']+'/overview').json()['facts']['interests'][0]['value']=='閱讀'


@pytest.mark.parametrize('width',[320,390,1440])
def test_existing_person_preview_shows_prior_facts_without_overwriting_them(page,width):
    page.set_viewport_size({'width':width,'height':950});person,headers=seed(page)
    old=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data={'raw_text':'先前本人告知喜歡閱讀。','occurred_at':'2026-10-27T00:00:00Z','contributions':[]}).json()
    r=page.request.post(BASE+'/api/drafts/'+old['id']+'/confirm',headers=headers,data={'request_id':'prior-fact','expected_revision':old['revision'],'summary':'先前喜歡閱讀','contributions':[],'tasks':[],'story_reviewed':True,'story':{'participants':[{'person_id':person['id'],'interacted':True}]},'targeted_person_updates':[{'target':{'person_id':person['id']},'expected_person_revision':person['revision'],'dimension':'interests','value':'閱讀','evidence_type':'stated_by_person','selected':True,'source_kind':'manual','source_revision':old['revision']}]});assert r.ok,r.text()
    prior=page.request.get(BASE+'/api/people/'+person['id']+'/overview').json();raw='這次本人說也喜歡登山。'
    r=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data={'raw_text':raw,'occurred_at':'2026-10-27T00:00:00Z','contributions':[],'story':{'participants':[{'person_id':person['id'],'interacted':True}]},'review':{'summary':raw,'summary_source_sha256':hashlib.sha256(raw.encode()).hexdigest(),'tasks':[],'person_candidates':[{'candidate_ref':'new-interest','target':{'person_id':person['id']},'expected_person_revision':prior['person']['revision'],'dimension':'interests','value':'登山','source_kind':'manual','evidence_type':'stated_by_person'}]}});assert r.ok,r.text();d=r.json()
    page.goto(BASE+'/#review/'+d['id']);page.reload();page.locator('[data-experience-preview="existing:'+person['id']+'"]').click()
    expect(page.locator('[data-prior-facts]')).to_contain_text('閱讀')
    expect(page.locator('[data-person-candidate-review]')).to_contain_text('本次新增：登山')
    page.locator('[data-candidate-select="new-interest"]').check()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    ART.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(ART/f'{width}-prior-and-candidate-facts.png'))
    assert page.request.get(BASE+'/api/people/'+person['id']+'/overview').json()['facts']==prior['facts']


def test_candidate_person_version_conflict_keeps_review_and_does_not_write(page):
    person,headers=seed(page);raw='手動補充。'
    r=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data={'raw_text':raw,'occurred_at':'2026-10-27T00:00:00Z','contributions':[],'story':{'participants':[{'person_id':person['id'],'interacted':True}]},'review':{'summary':raw,'summary_source_sha256':hashlib.sha256(raw.encode()).hexdigest(),'tasks':[],'person_candidates':[{'candidate_ref':'stale-version','target':{'person_id':person['id']},'expected_person_revision':person['revision']+1,'dimension':'habits','value':'先傳訊息','source_kind':'manual','evidence_type':'stated_by_person'}]}});assert r.ok,r.text();d=r.json()
    page.goto(BASE+'/#review/'+d['id']);page.reload();page.locator('[data-experience-preview="existing:'+person['id']+'"]').click()
    expect(page.locator('[data-prior-facts]')).to_contain_text('候選不會自動套用到新版')
    page.locator('[data-candidate-select="stale-version"]').check();page.get_by_role('button',name='完成檢視',exact=True).click()
    page.locator('#story-reviewed').check()
    with page.expect_response(lambda r:r.url.endswith('/api/drafts/'+d['id']+'/confirm')) as result:
        page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    assert result.value.status==409
    expect(page.locator('#review-form')).to_be_visible()
    assert not page.request.get(BASE+'/api/state').json()['experiences']
    assert not page.request.get(BASE+'/api/people/'+person['id']+'/overview').json()['facts']['habits']


@pytest.mark.parametrize('width',[320,390,1440])
def test_step3_manual_supplement_to_review_confirm_without_seeded_candidates(page,width):
    page.set_viewport_size({'width':width,'height':950});person,headers=seed(page)
    page.goto(BASE+'/#record');page.reload()
    page.locator('#raw-text').fill('和小安閱讀，提到小明。');set_occurred(page,'2026-10-27T12:00')
    page.locator('[data-experience-next]').click();page.locator('#goal-id').select_option('');page.locator('[data-experience-next]').click()
    page.locator('#include-story').check();page.get_by_role('button',name='選擇既有人物',exact=True).click();page.locator('[data-workflow-pick="'+person['id']+'"]').click();page.locator('[data-workflow-person]').first.locator('[data-workflow-role]').select_option('participant')
    card=page.locator('[data-supplement-person="existing:'+person['id']+'"]')
    card.locator('summary').first.click();supplement_source(card);card.locator('[data-supplement-input=source_kind]').select_option('manual');card.locator('[data-supplement-input=dimension]').select_option('interests');card.locator('[data-supplement-input=value]').fill('登山')
    card.locator('[data-supplement-input=evidence_type]').select_option('stated_by_person')
    card.get_by_role('button',name='加入待核對項目',exact=True).click()
    page.get_by_role('button',name='＋ 新增人物',exact=True).click();pending=page.locator('[data-pending-target]').first;pending.locator('[data-target-name]').fill('小明');pending.locator('[data-target-role]').select_option('mention');pending.locator('[data-target-start]').select_option('8');new_ref=pending.get_attribute('data-client-ref')
    second=page.locator('[data-supplement-person="pending:'+new_ref+'"]');second.locator('summary').first.click()
    supplement_source(second);second.locator('[data-supplement-input=source_kind]').select_option('manual');second.locator('[data-supplement-input=dimension]').select_option('food');second.locator('[data-supplement-input=value]').fill('清淡');second.locator('[data-supplement-input=evidence_type]').select_option('observed_by_user');second.get_by_role('button',name='加入待核對項目',exact=True).click()
    page.locator('[data-experience-prev]').click();page.locator('[data-experience-next]').click()
    expect(card).to_contain_text('登山');expect(second).to_contain_text('清淡')
    expect(page.locator('#toast')).not_to_have_class('visible')
    ART.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(ART/f'{width}-step3-supplement-input.png'),full_page=True)
    page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible()
    state=page.request.get(BASE+'/api/state').json();assert len(state['people'])==1 and not state['experiences']
    for key in ['existing:'+person['id'],'pending:'+new_ref]:
        page.locator('[data-experience-preview="'+key+'"]').click();page.locator('[data-candidate-select]').check();page.get_by_role('button',name='完成檢視',exact=True).click()
    page.locator('#story-reviewed').check();page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    page.wait_for_function("()=>!document.querySelector('#review-form') || !!document.querySelector('#notice .error-message')")
    assert page.locator('#review-form').count()==0,page.locator('#notice').inner_text()
    state=page.request.get(BASE+'/api/state').json();new=next(p for p in state['people'] if p['name']=='小明')
    assert page.request.get(BASE+'/api/people/'+person['id']+'/overview').json()['facts']['interests'][0]['value']=='登山'
    assert page.request.get(BASE+'/api/people/'+new['id']+'/overview').json()['facts']['food'][0]['value']=='清淡'
    assert page.request.get(BASE+'/api/people/'+new['id']+'/overview').json()['stats']['interactions']==0
    assert len(state['experiences'])==len(state['rewards']['events'])==1


def test_step3_unadded_input_is_protected_and_local_draft_restores_both_stages(page):
    person,headers=seed(page);page.goto(BASE+'/#record');page.reload()
    page.locator('#raw-text').fill('沒有AI的手動記錄。');set_occurred(page,'2026-10-27T12:00');page.locator('[data-experience-next]').click();page.locator('#goal-id').select_option('');page.locator('[data-experience-next]').click()
    page.locator('#include-story').check();page.get_by_role('button',name='選擇既有人物',exact=True).click();page.locator('[data-workflow-pick="'+person['id']+'"]').click();page.locator('[data-workflow-person]').first.locator('[data-workflow-role]').select_option('participant')
    row=page.locator('[data-supplement-person="existing:'+person['id']+'"]');row.locator('summary').first.click();supplement_source(row);row.locator('[data-supplement-input=source_kind]').select_option('manual');row.locator('[data-supplement-input=dimension]').select_option('skills');row.locator('[data-supplement-input=value]').fill('繪圖')
    page.locator('[data-experience-review]').click();expect(page.locator('#notice')).to_contain_text('尚未加入候選')
    assert not page.request.get(BASE+'/api/state').json()['drafts']
    row.get_by_role('button',name='加入待核對項目',exact=True).click()
    row.locator('summary').first.click();row.locator('[data-supplement-input=dimension]').select_option('food');row.locator('[data-supplement-input=value]').fill('未完成的偏好輸入')
    page.locator('#nav').get_by_role('link',name='世界',exact=True).click();page.get_by_role('button',name='保留此裝置草稿並離開',exact=True).click()
    expect(page.locator('#world-relationships')).to_be_visible()
    other=page.context.new_page()
    try:
        other.goto(BASE+'/#record');expect(other.locator('#raw-text')).to_have_value('沒有AI的手動記錄。')
        other.locator('[data-experience-next]').click();other.locator('[data-experience-next]').click()
        restored=other.locator('[data-supplement-person="existing:'+person['id']+'"]');restored.locator('summary').first.click()
        expect(restored.locator('[data-supplement-input=value]')).to_have_value('未完成的偏好輸入')
        expect(restored.locator('[data-supplement-candidates]')).to_contain_text('繪圖')
        restored.get_by_role('button',name='清空這次輸入',exact=True).click()
        expect(restored.locator('[data-supplement-candidates]')).to_contain_text('繪圖')
        other.locator('[data-experience-review]').click();expect(other.locator('#review-form')).to_be_visible()
        d=other.request.get(BASE+'/api/state').json()['drafts'][0]
        assert len(d['review']['person_candidates'])==1 and d['review']['person_candidates'][0]['evidence_type'] is None
    finally:other.close()


def test_step3_compact_picker_has_explicit_role_and_keeps_plain_diary_path(page):
    person,headers=seed(page);page.goto(BASE+'/#record');page.reload()
    page.locator('#raw-text').fill('今天寫了一段日記。');set_occurred(page,'2026-10-27T12:00');page.locator('[data-experience-next]').click();page.locator('#goal-id').select_option('');page.locator('[data-experience-next]').click()
    expect(page.locator('[data-workflow-picker]')).to_be_hidden()
    page.locator('#include-story').check();page.get_by_role('button',name='選擇既有人物',exact=True).click()
    page.locator('[data-workflow-pick="'+person['id']+'"]').click()
    row=page.locator('[data-workflow-person]').first;expect(row.locator('[data-workflow-role]')).to_have_value('')
    page.locator('[data-experience-review]').click();expect(page.locator('#notice')).to_contain_text('本次角色')
    assert not page.request.get(BASE+'/api/state').json()['drafts']
    row.locator('[data-workflow-remove]').click();page.locator('#include-story').uncheck()
    page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible()
    expect(page.locator('[data-experience-preview]')).to_have_count(0)
