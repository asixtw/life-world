"""透過真本機授權API與明示Provider替身測UI；不可當真Gemini/Google/Alpha收據。"""
import pytest
from playwright.sync_api import expect
from test_journey import page,BASE
from test_integration_person_details import seed,ART


def review(page,raw='合成原始經歷。'):
    p,headers=seed(page)
    response=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data={'raw_text':raw,'occurred_at':'2026-10-27T00:00:00Z','contributions':[]});assert response.ok,response.text();d=response.json()
    page.goto(BASE+'/#review/'+d['id']);page.reload()
    return d,headers


@pytest.mark.parametrize('width',[320,390,1440])
def test_manual_default_first_consent_cancel_and_reuse_keep_candidate_editable(page,width):
    page.set_viewport_size({'width':width,'height':950});d,headers=review(page)
    manual=page.locator('[name=draft_ai_mode][value=manual]');ai=page.locator('[name=draft_ai_mode][value=ai]')
    expect(manual).to_be_checked();expect(ai).to_be_enabled()
    expect(page.locator('[data-draft-ai-retry]')).to_be_hidden()
    expect(page.locator('[data-draft-ai-receipts]')).to_be_hidden()
    # radio不能繼承文字輸入100%寬，否則手機選項文字會逐字直排。
    bounds=manual.bounding_box();assert bounds and bounds['width']<=24 and bounds['height']<=24
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert page.request.get(BASE+'/api/ai/usage').json()['calls']==0
    page.locator('#summary').fill('自己編輯的摘要')
    ART.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(ART/f'{width}-draft-ai-manual.png'),full_page=True)
    ai.check();expect(page.locator('#draft-ai-consent-dialog')).to_be_visible()
    expect(page.locator('#draft-ai-consent-dialog')).to_contain_text('測試替身')
    ART.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(ART/f'{width}-draft-ai-first-consent.png'))
    page.get_by_role('button',name='維持手動',exact=True).click()
    expect(manual).to_be_checked();expect(page.locator('#summary')).to_have_value('自己編輯的摘要')
    assert page.request.get(BASE+'/api/ai/usage').json()['calls']==0
    ai.check();page.get_by_role('button',name='同意並整理',exact=True).click()
    expect(page.locator('#candidate-panel')).to_contain_text('合成AI整理候選')
    expect(page.locator('#summary')).to_have_value('自己編輯的摘要')
    assert not page.request.get(BASE+'/api/state').json()['experiences']
    assert page.request.get(BASE+'/api/ai/usage').json()['calls']==1
    page.get_by_role('button',name='套用摘要與任務草稿',exact=True).click()
    expect(page.locator('#summary')).to_have_value('合成AI整理候選')
    manual.check();ai.check()
    expect(page.locator('#candidate-panel')).to_contain_text('合成AI整理候選')
    expect(page.locator('#draft-ai-consent-dialog')).not_to_be_visible()
    assert page.request.get(BASE+'/api/ai/usage').json()['calls']==2
    page.locator('#summary').fill('人工確認前再修改')
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    expect(page.locator('#review-form')).to_have_count(0)
    state=page.request.get(BASE+'/api/state').json();assert state['experiences'][0]['summary']=='人工確認前再修改' and len(state['rewards']['events'])==1


def test_revoke_is_real_and_next_selection_requires_consent_again(page):
    _,headers=review(page)
    page.locator('[name=draft_ai_mode][value=ai]').check();page.get_by_role('button',name='同意並整理',exact=True).click()
    expect(page.locator('#candidate-panel')).to_contain_text('合成AI整理候選')
    page.locator('[data-draft-ai-manage]').click();expect(page.locator('#draft-ai-consent-dialog')).to_contain_text('授權有效')
    page.get_by_role('button',name='撤回這項授權',exact=True).click()
    expect(page.locator('[name=draft_ai_mode][value=manual]')).to_be_checked()
    assert not page.request.get(BASE+'/api/ai/draft-consent').json()['granted']
    page.locator('[name=draft_ai_mode][value=ai]').check();expect(page.locator('#draft-ai-consent-dialog')).to_be_visible()
    page.get_by_role('button',name='維持手動',exact=True).click()
    assert page.request.get(BASE+'/api/ai/usage').json()['calls']==1


def test_provider_failure_preserves_manual_and_failure_receipts(page):
    _,headers=review(page,'fixture:failure 合成原文')
    page.locator('#summary').fill('失敗時保留的人工摘要')
    page.locator('[name=draft_ai_mode][value=ai]').check();page.get_by_role('button',name='同意並整理',exact=True).click()
    expect(page.locator('[data-draft-ai-status]')).to_contain_text('失敗或未知費用不當作零')
    expect(page.locator('#summary')).to_have_value('失敗時保留的人工摘要')
    usage=page.request.get(BASE+'/api/ai/usage').json();assert usage['calls']==1 and usage['reserved_microusd']==100 and usage['unknown_cost_calls']==1
    with page.expect_response(lambda r:'/suggest' in r.url):
        page.locator('[data-draft-ai-retry]').click()
    expect(page.locator('[data-draft-ai-status]')).to_contain_text('失敗或未知費用不當作零')
    usage=page.request.get(BASE+'/api/ai/usage').json();assert usage['calls']==2 and usage['reserved_microusd']==200
    page.locator('[name=draft_ai_mode][value=manual]').check()
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    expect(page.locator('#review-form')).to_have_count(0)
    assert page.request.get(BASE+'/api/state').json()['experiences'][0]['summary']=='失敗時保留的人工摘要'


def test_late_response_after_manual_switch_is_not_applied(page):
    _,headers=review(page,'fixture:delay 合成原文')
    page.locator('#summary').fill('保留手動內容')
    page.locator('[name=draft_ai_mode][value=ai]').check()
    with page.expect_response(lambda r:'/suggest' in r.url):
        page.get_by_role('button',name='同意並整理',exact=True).click()
        expect(page.locator('[data-draft-ai-status]')).to_contain_text('AI整理中')
        page.locator('[name=draft_ai_mode][value=manual]').check()
    expect(page.locator('#candidate-panel')).to_be_empty()
    expect(page.locator('#summary')).to_have_value('保留手動內容')
    assert page.request.get(BASE+'/api/ai/usage').json()['calls']==1


def test_unknown_transport_retry_reuses_reservation_and_preserves_input(page):
    review(page);page.locator('#summary').fill('未知結果仍保留')
    def lose_response(route):
        response=route.fetch();assert response.status==200,response.text();route.abort('failed')
    page.route('**/api/drafts/*/suggest',lose_response)
    page.locator('[name=draft_ai_mode][value=ai]').check();page.get_by_role('button',name='同意並整理',exact=True).click()
    expect(page.locator('[data-draft-ai-status]')).to_contain_text('失敗或未知費用不當作零')
    expect(page.locator('[data-draft-ai-retry]')).to_be_visible()
    assert page.request.get(BASE+'/api/ai/usage').json()['calls']==1
    page.unroute('**/api/drafts/*/suggest',lose_response)
    with page.expect_response(lambda r:'/suggest' in r.url) as response:
        page.locator('[data-draft-ai-retry]').click()
    assert response.value.status==409
    expect(page.locator('[data-draft-ai-receipts]')).to_be_visible()
    assert page.request.get(BASE+'/api/ai/usage').json()['calls']==1
    expect(page.locator('#summary')).to_have_value('未知結果仍保留')
    expect(page.locator('#candidate-panel')).to_be_empty()


def test_unavailable_capability_keeps_manual_and_does_not_call_provider(page):
    # 只替換能力回應以驗證fail-closed畫面，不冒稱後端權限驗收。
    page.route('**/api/ai/draft-consent',lambda route:route.fulfill(json={'available':False,'granted':False,'has_consent':None,'consent_status':'unavailable'}))
    review(page)
    expect(page.locator('[name=draft_ai_mode][value=ai]')).to_be_disabled()
    expect(page.locator('[name=draft_ai_mode][value=manual]')).to_be_checked()
    expect(page.locator('[data-draft-ai-status]')).to_contain_text('目前未開放')
    assert page.request.get(BASE+'/api/ai/usage').json()['calls']==0
