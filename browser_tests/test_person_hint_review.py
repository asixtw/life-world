"""人物候選只能經人工勾選保存；模型為明示替身，與真模型驗收分開。"""
from playwright.sync_api import expect
from test_journey import BASE,page
from test_media_flow import prepare


def test_person_hint_needs_matching_person_and_explicit_confirmation(page):
    prepare(page)
    me=page.request.get(BASE+'/api/auth/me').json()
    person=page.request.post(BASE+'/api/people',headers={'X-CSRF-Token':me['csrf_token']},data={'name':'合成小林','category':'other'}).json()
    page.reload();page.locator('#raw-text').fill('合成小林說他不吃辣。')
    page.get_by_role('button',name='保存草稿並進入核對',exact=False).click()
    page.route('**/suggest',lambda route:route.fulfill(json={'provider':'gemini','model':'fixture-explicit','summary':'合成小林表示不吃辣。','tasks':[],'people':[{'person_name':'合成小林','dimension':'food','value':'不吃辣','evidence_type':'stated_by_person','source_quote':'合成小林說他不吃辣。'}],'applied':False}))
    page.locator('[data-action="suggest"]').click();expect(page.locator('#ai-people-panel')).to_contain_text('合成小林')
    page.locator('[data-action="apply-person-hint"]').click();expect(page.locator('#notice')).to_contain_text('先選擇')
    page.locator('#person-id').select_option(person['id']);expect(page.locator('[name="fact_value_food"]')).to_be_visible()
    page.locator('[data-action="apply-person-hint"]').click();expect(page.locator('[name="fact_value_food"]')).to_have_value('不吃辣');expect(page.locator('[name="fact_selected_food"]')).not_to_be_checked()
    assert not page.request.get(BASE+'/api/people/'+person['id']+'/overview').json()['facts']['food']
    page.locator('[name="fact_selected_food"]').check();page.locator('[data-action="apply-candidate"]').click()
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    facts=page.request.get(BASE+'/api/people/'+person['id']+'/overview').json()['facts']['food'];assert facts[0]['value']=='不吃辣' and facts[0]['sources']
