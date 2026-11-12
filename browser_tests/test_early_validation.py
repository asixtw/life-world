"""四步最早可判定時防呆；真本機API/PG，保留錯誤輸入與最後伺服器防線。"""
import os
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_journey import page,BASE,set_occurred,supplement_source
from test_integration_person_details import seed
from test_draft_basic_ui import choose_existing

ART=Path(os.environ.get('LIFEWORLD_UX_ARTIFACT_DIR','/private/tmp/lw-validation-evidence'))
def shot(page,width,name):
 ART.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(ART/f'{width}-{name}.png'),full_page=True)

@pytest.mark.parametrize('width',[320,390,1440])
def test_birthday_input_errors_before_add_preserve_text(page,width):
 page.set_viewport_size({'width':width,'height':900});person,h=seed(page);card=choose_existing(page,person)
 card.locator('[data-supplement-input=dimension]').select_option('birthday');month=card.locator('[data-supplement-input=birth_month]');day=card.locator('[data-supplement-input=birth_day]')
 month.fill('4');day.fill('31');expect(card.locator('[data-field-error=birth_day]')).to_contain_text('4 月沒有 31 日');shot(page,width,'birthday-error')
 supplement_source(card);card.locator('[data-supplement-input=source_kind]').select_option('manual');card.get_by_role('button',name='加入資訊',exact=True).click()
 expect(card).to_have_attribute('open','');expect(day).to_have_value('31');assert page.evaluate('ExperienceUI.getState().birthdayCandidates.length')==0
 day.fill('30');expect(card.locator('[data-field-error=birth_day]')).to_have_text('');card.get_by_role('button',name='加入資訊',exact=True).click();expect(card).not_to_have_attribute('open','')
 assert page.evaluate('ExperienceUI.getState().birthdayCandidates[0].value.birth_year') is None
 page.locator('[data-experience-prev]').click();page.locator('[data-experience-next]').click();expect(card).to_contain_text('4 月 30 日')
 assert page.request.get(BASE+'/api/people/'+person['id']+'/details').json()['birthday'] is None

@pytest.mark.parametrize('width',[320,390,1440])
def test_goal_period_early_warning_and_explicit_omit_keeps_values(page,width):
 page.set_viewport_size({'width':width,'height':900});seed(page);goal=page.request.get(BASE+'/api/state').json()['goals'][0];action=goal['actions'][0]
 page.goto(BASE+'/#record');page.reload();expect(page.locator('#goal-id')).to_have_value('');page.locator('#raw-text').fill('期間前的真實經歷，仍應保存。');set_occurred(page,'2026-10-26T12:00');page.locator('[data-experience-next]').click();page.locator('#goal-id').select_option(goal['id'])
 quantity=page.locator('[name="quantity-'+action['id']+'"]');quantity.fill('0.5');expect(page.locator('[data-goal-period-status]')).to_contain_text('2026-10-26');expect(page.locator('[data-goal-period-status]')).to_contain_text(goal['start_date']);shot(page,width,'goal-period-error')
 page.locator('[data-experience-next]').click();expect(page.locator('#experience-step-title')).to_have_text('目標活動數量');expect(quantity).to_have_value('0.5')
 page.get_by_role('button',name='保留經歷但不計入目標',exact=True).click();expect(page.locator('#goal-id')).to_have_value('');expect(page.locator('[data-goal-retained]')).to_contain_text('0.5')
 page.locator('#goal-id').select_option(goal['id']);expect(quantity).to_have_value('0.5');quantity.fill('0');page.locator('[data-experience-next]').click();expect(page.locator('#experience-step-title')).to_have_text('人物關聯')
 page.locator('[data-experience-prev]').click();page.get_by_role('button',name='保留經歷但不計入目標',exact=True).click();page.locator('[data-experience-next]').click();page.locator('[data-experience-review]').click();page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
 state=page.request.get(BASE+'/api/state').json();assert len(state['experiences'])==len(state['rewards']['events'])==1;assert state['experiences'][0]['goal_id'] is None;assert state['goals'][0]['actions'][0]['progress']=='0'

@pytest.mark.parametrize('month,day,year,valid',[('0','1','',False),('13','1','',False),('1','0','',False),('1','32','',False),('2','29','',True),('2','29','2024',True),('2','29','2023',False),('4','31','',False),('1','','',False),('','','',False)])
def test_birthday_calendar_matrix_and_no_early_write(page,month,day,year,valid):
 person,h=seed(page);card=choose_existing(page,person);card.locator('[data-supplement-input=dimension]').select_option('birthday')
 for key,value in [('birth_month',month),('birth_day',day),('birth_year',year)]:card.locator('[data-supplement-input='+key+']').fill(value)
 supplement_source(card);card.locator('[data-supplement-input=source_kind]').select_option('manual');card.get_by_role('button',name='加入資訊',exact=True).click()
 if valid:expect(card).not_to_have_attribute('open','')
 else:expect(card.locator('[data-supplement-status]')).not_to_have_text('')
 assert page.evaluate('ExperienceUI.getState().birthdayCandidates.length')==(1 if valid else 0)
 if valid:
  assert page.evaluate('ExperienceUI.getState().birthdayCandidates[0].value.birth_year')==(int(year) if year else None)
 else:assert any(card.locator('[data-field-error]').all_text_contents())
 assert page.request.get(BASE+'/api/people/'+person['id']+'/details').json()['birthday'] is None


def test_employment_quantity_role_and_source_errors_stay_at_origin(page):
 person,h=seed(page);card=choose_existing(page,person);card.locator('[data-supplement-input=dimension]').select_option('employment');card.locator('[data-supplement-input=company_name]').fill('測試組織');card.locator('[data-supplement-input=valid_from]').fill('2025-05-01');card.locator('[data-supplement-input=valid_to]').fill('2025-04-30')
 expect(card.locator('[data-field-error=valid_to]')).to_contain_text('不能早於');card.get_by_role('button',name='加入資訊',exact=True).click();assert page.evaluate('ExperienceUI.getState().employmentCandidates.length')==0
 card.locator('[data-supplement-input=valid_to]').fill('2025-05-02');card.get_by_role('button',name='加入資訊',exact=True).click();expect(card.locator('[data-source-validation]')).to_contain_text('資訊');expect(card.locator('[data-supplement-input=company_name]')).to_have_value('測試組織')
 card.get_by_role('button',name='清空這次輸入',exact=True).click();page.locator('[data-workflow-role]').select_option('');page.locator('[data-experience-review]').click();expect(page.locator('[data-role-error]')).to_contain_text('人物小安');expect(page.locator('#record-form')).to_be_visible()
 page.locator('[data-experience-prev]').click();goal=page.request.get(BASE+'/api/state').json()['goals'][0];page.locator('#goal-id').select_option(goal['id']);quantity=page.locator('[data-quantity-input]').first;quantity.fill('0.1234567');expect(page.locator('[data-quantity-status]').first).to_contain_text('6 位');page.locator('[data-experience-next]').click();expect(page.locator('#experience-step-title')).to_have_text('目標活動數量');expect(quantity).to_have_value('0.1234567')


def test_api_validation_path_readable_retry_unknown_year_leap_day(page):
 person,h=seed(page);card=choose_existing(page,person);card.locator('[data-supplement-input=dimension]').select_option('birthday');card.locator('[data-supplement-input=birth_month]').fill('2');card.locator('[data-supplement-input=birth_day]').fill('29');supplement_source(card);card.locator('[data-supplement-input=source_kind]').select_option('manual');card.get_by_role('button',name='加入資訊',exact=True).click()
 page.route('**/api/experiences/drafts',lambda r:r.fulfill(status=422,json={'error':{'code':'validation_error','message':'請檢查欄位內容與格式。','fields':['review.birthday_candidates.0.value.birth_day']}}))
 page.locator('[data-experience-review]').click();expect(page.locator('#notice')).to_contain_text('生日日期');expect(page.locator('#notice')).not_to_contain_text('review.');expect(card).to_contain_text('2 月 29 日');assert page.request.get(BASE+'/api/state').json()['drafts']==[]
 page.unroute('**/api/experiences/drafts');page.locator('[data-experience-review]').click();page.locator('[data-experience-preview="existing:'+person['id']+'"]').click();page.locator('[data-basic-select]').check();page.get_by_role('button',name='完成檢視',exact=True).click();page.locator('#story-reviewed').check();page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
 b=page.request.get(BASE+'/api/people/'+person['id']+'/details').json()['birthday'];assert (b['birth_year'],b['birth_month'],b['birth_day'])==(None,2,29)


def test_backend_range_rejection_guides_step2_and_preserves_summary(page):
 seed(page);goal=page.request.get(BASE+'/api/state').json()['goals'][0];a=goal['actions'][0];h={'X-CSRF-Token':page.request.get(BASE+'/api/auth/me').json()['csrf_token']}
 r=page.request.post(BASE+'/api/experiences/drafts',headers=h,data={'raw_text':'繞過前端仍有伺服器日期防線。','occurred_at':'2026-10-26T04:00:00Z','goal_id':goal['id'],'contributions':[{'action_id':a['id'],'quantity':'0.5'}]});assert r.ok,r.text();d=r.json()
 page.goto(BASE+'/#review/'+d['id']);page.reload();page.locator('#summary').fill('保留人工修改的摘要');page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#notice')).to_contain_text('不在目標挑戰期間');assert page.request.get(BASE+'/api/state').json()['experiences']==[]
 page.get_by_role('button',name='返回第二步修正目標與數量',exact=True).click();expect(page.locator('#experience-step-title')).to_have_text('目標活動數量');expect(page.locator('[data-quantity-input]').first).to_have_value('0.5');page.get_by_role('button',name='保留經歷但不計入目標',exact=True).click();page.locator('[data-experience-next]').click();page.locator('[data-experience-review]').click();expect(page.locator('#summary')).to_have_value('保留人工修改的摘要')
 page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0);s=page.request.get(BASE+'/api/state').json();assert len(s['experiences'])==len(s['rewards']['events'])==1 and s['goals'][0]['actions'][0]['progress']=='0'


def test_goal_switch_reload_and_date_change_revalidate(page):
 seed(page);g=page.request.get(BASE+'/api/state').json()['goals'][0];page.goto(BASE+'/#record?goal='+g['id']);page.reload();expect(page.locator('#goal-id')).to_have_value(g['id']);page.locator('#raw-text').fill('切換與回復不丟數量。');page.locator('[data-experience-next]').click();page.locator('[data-quantity-input]').first.fill('1.25');page.locator('#goal-id').select_option('');page.reload();page.locator('[data-experience-next]').click();page.locator('#goal-id').select_option(g['id']);expect(page.locator('[data-quantity-input]').first).to_have_value('1.25')
 page.locator('[data-experience-prev]').click();set_occurred(page,'2026-10-26T12:00');page.locator('[data-experience-next]').click();expect(page.locator('[data-goal-period-status]')).to_contain_text('不在目標挑戰期間');page.locator('[data-experience-prev]').click();set_occurred(page,'2026-10-27T12:00');page.locator('[data-experience-next]').click();expect(page.locator('[data-goal-period-status]')).not_to_contain_text('不在目標挑戰期間');page.locator('[data-experience-next]').click();expect(page.locator('#experience-step-title')).to_have_text('人物關聯')


def test_two_goals_keep_independent_quantities(page):
 _,h=seed(page);a=page.request.get(BASE+'/api/state').json()['goals'][0]
 # 沿用單一進行中挑戰：明確結束合成舊目標後才建立新目標。
 ended=page.request.post(BASE+'/api/goals/'+a['id']+'/review',headers=h,data={'request_id':'end-validation-goal','expected_revision':a['revision'],'decision':'end','confirmed':True})
 assert ended.ok,ended.text()
 r=page.request.post(BASE+'/api/goals',headers=h,data={'request_id':'second-validation-goal','title':'另一個測試目標','outcome':'不同單位','deadline':'2026-11-15','actions':[{'title':'距離'+str(i),'unit':'公里','target':'10','level':i+1,'dates':['2026-10-28'],'weekdays':[2]} for i in range(3)]});assert r.ok,r.text();b=r.json()
 page.goto(BASE+'/#record');page.reload();page.locator('#raw-text').fill('切換目標，不覆蓋原數量。');page.locator('[data-experience-next]').click();page.locator('#goal-id').select_option(a['id']);page.locator('[data-quantity-input]').first.fill('1.25');page.locator('#goal-id').select_option(b['id']);page.locator('[data-quantity-input]').first.fill('2.75');expect(page.locator('[data-goal-period-status]')).to_contain_text('2026-11-15');page.locator('#goal-id').select_option(a['id']);expect(page.locator('[data-quantity-input]').first).to_have_value('1.25');page.locator('#goal-id').select_option(b['id']);expect(page.locator('[data-quantity-input]').first).to_have_value('2.75')
 assert not page.request.get(BASE+'/api/state').json()['experiences']


def test_goal_period_uses_goal_timezone_at_real_ui_boundary(page):
 _,h=seed(page);g=page.request.get(BASE+'/api/state').json()['goals'][0]
 assert page.request.put(BASE+'/api/profile',headers=h,data={'name':'跨時區合成測試','bio':'只測本機','timezone':'America/Los_Angeles'}).ok
 page.goto(BASE+'/#record');page.reload();page.locator('#raw-text').fill('洛杉磯還是前一天，目標依台北時間計算。');set_occurred(page,'2026-10-26T09:00');page.locator('[data-experience-next]').click();page.locator('#goal-id').select_option(g['id']);page.locator('[data-quantity-input]').first.fill('0.5');expect(page.locator('[data-goal-period-status]')).to_contain_text('本次經歷：2026-10-27');page.locator('[data-experience-next]').click();expect(page.locator('#experience-step-title')).to_have_text('人物關聯')
 page.locator('[data-experience-prev]').click();page.locator('[data-experience-prev]').click();set_occurred(page,'2026-10-26T08:59');page.locator('[data-experience-next]').click();expect(page.locator('[data-goal-period-status]')).to_contain_text('本次經歷：2026-10-26');page.locator('[data-experience-next]').click();expect(page.locator('#experience-step-title')).to_have_text('目標活動數量');expect(page.locator('[data-quantity-input]').first).to_have_value('0.5')


def test_server_race_rejection_always_has_visible_return_to_step2(page):
 """前端快照仍合法、伺服器競態拒絕時，隱藏的預警按鈕不可抑制錯誤退路。"""
 _,h=seed(page);g=page.request.get(BASE+'/api/state').json()['goals'][0]
 r=page.request.post(BASE+'/api/experiences/drafts',headers=h,data={'raw_text':'合法日期仍可能遇到目標版本變更。','occurred_at':'2026-10-27T04:00:00Z','goal_id':g['id'],'contributions':[{'action_id':g['actions'][0]['id'],'quantity':'0.5'}]});assert r.ok,r.text()
 page.goto(BASE+'/#review/'+r.json()['id']);page.reload();page.locator('#summary').fill('保留這段人工摘要')
 expect(page.locator('[data-review-goal-validation]')).to_be_hidden()
 page.route('**/api/drafts/*/confirm',lambda route:route.fulfill(status=422,json={'error':{'code':'contribution_out_of_range','message':'這段經歷不在目標挑戰期間；請移除貢獻後保存經歷。'}}))
 page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
 button=page.get_by_role('button',name='返回第二步修正目標與數量',exact=True);expect(button).to_be_visible();button.click()
 expect(page.locator('#experience-step-title')).to_have_text('目標活動數量');expect(page.locator('[data-quantity-input]').first).to_have_value('0.5')
 assert not page.request.get(BASE+'/api/state').json()['experiences']
