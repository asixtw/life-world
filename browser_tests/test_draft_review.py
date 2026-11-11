"""實際本機API保存核對草稿；不是外部AI或Alpha驗收。"""
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
