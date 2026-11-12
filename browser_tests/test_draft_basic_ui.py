"""真正本機UI→草稿→確認交易；不把API種入候選當成填寫流程，不呼叫外部AI。"""
from test_journey import supplement_source
from test_journey import set_occurred
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_journey import page,BASE
from test_integration_person_details import seed

ART=Path(__file__).resolve().parents[1]/'docs/integration/2026-11-11/screenshots'


def record(page):
    page.goto(BASE+'/#record');page.reload();page.locator('#raw-text').fill('和小安一起閱讀，提到小明。');set_occurred(page,'2026-10-27T12:00')
    page.locator('[data-experience-next]').click();page.locator('#goal-id').select_option('');page.locator('[data-experience-next]').click()


def supplement(card,kind,values):
    if card.get_attribute('open') is None:card.locator('summary').first.click()
    card.locator('[data-supplement-input=dimension]').select_option(kind)
    expect(card.locator('[data-supplement-input=source_kind]')).to_have_value('')
    supplement_source(card);card.locator('[data-supplement-input=source_kind]').select_option('manual')
    for key,value in values.items():
        control=card.locator('[data-supplement-input="'+key+'"]')
        if key in ['employment_status','employment_id']:control.select_option(value)
        else:control.fill(value)
    card.get_by_role('button',name='加入待核對項目',exact=True).click()
    expect(card).not_to_have_attribute('open','')


@pytest.mark.parametrize('width',[320,390,1440])
def test_basic_fields_two_people_save_reload_preview_confirm(page,width):
    page.set_viewport_size({'width':width,'height':950});person,headers=seed(page);record(page)
    page.get_by_role('button',name='選擇既有人物',exact=True).click();page.locator('[data-workflow-pick="'+person['id']+'"]').click();page.locator('[data-workflow-role]').select_option('interaction')
    card=page.locator('[data-supplement-person="existing:'+person['id']+'"]')
    supplement(card,'birthday',{'birth_month':'4','birth_day':'12'})
    supplement(card,'employment',{'company_name':'組織甲','job_title':'研究員'})
    page.get_by_role('button',name='＋ 新增人物',exact=True).click();pending=page.locator('[data-pending-target]');pending.locator('[data-target-name]').fill('小明');pending.locator('[data-target-role]').select_option('mention');pending.locator('[data-target-start]').select_option('10')
    ref=pending.get_attribute('data-client-ref');second=page.locator('[data-supplement-person="pending:'+ref+'"]')
    supplement(second,'employment',{'company_name':'組織乙','job_title':'設計師'})
    page.locator('[data-experience-prev]').click();page.locator('[data-experience-next]').click();expect(card).to_contain_text('4 月 12 日');expect(second).to_contain_text('組織乙')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    ART.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(ART/f'{width}-basic-step3.png'),full_page=True)
    page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible()
    draft_id=page.evaluate('state.draft.id')
    assert page.request.get(BASE+'/api/people/'+person['id']+'/details').json()['birthday'] is None
    page.get_by_role('button',name='保存核對草稿並離開',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    page.goto(BASE+'/#review/'+draft_id);page.reload();expect(page.locator('#review-form')).to_be_visible()
    for key,count in [('existing:'+person['id'],2),('pending:'+ref,1)]:
        page.locator('[data-experience-preview="'+key+'"]').click()
        rows=page.locator('[data-basic-review-row]');expect(rows).to_have_count(count)
        for row in rows.all():row.locator('[data-basic-select]').check()
        expect(page.locator('.experience-preview-body')).not_to_contain_text('沒有待修改的基本資料')
        page.locator('.experience-preview-body').evaluate('(node)=>node.scrollTop=0')
        page.screenshot(path=str(ART/f'{width}-basic-preview-{count}.png'))
        page.get_by_role('button',name='完成檢視',exact=True).click()
    page.locator('#story-reviewed').check();page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    a=page.request.get(BASE+'/api/people/'+person['id']+'/details').json();assert a['birthday']['birth_month']==4 and a['birthday']['birth_year'] is None
    assert a['employments'][0]['company_name']=='組織甲'
    state=page.request.get(BASE+'/api/state').json();new=next(p for p in state['people'] if p['name']=='小明')
    assert page.request.get(BASE+'/api/people/'+new['id']+'/details').json()['employments'][0]['company_name']=='組織乙'
    assert page.request.get(BASE+'/api/people/'+new['id']+'/overview').json()['stats']['interactions']==0
    assert len(state['experiences'])==len(state['rewards']['events'])==1


def choose_existing(page,person):
    record(page);page.get_by_role('button',name='選擇既有人物',exact=True).click();page.locator('[data-workflow-pick="'+person['id']+'"]').click();page.locator('[data-workflow-role]').select_option('participant')
    card=page.locator('[data-supplement-person="existing:'+person['id']+'"]');card.locator('summary').first.click();return card


def test_existing_job_diff_failure_retry_and_version_conflict(page):
    person,h=seed(page)
    job=page.request.post(BASE+'/api/people/'+person['id']+'/employments',headers=h,data={'request_id':'prior-job','confirmed':True,'value':{'company_name':'原組織','job_title':'原職稱','employment_status':'current'},'source':{'source_kind':'manual'}}).json()
    card=choose_existing(page,person);card.locator('[data-supplement-input=dimension]').select_option('employment');supplement_source(card);card.locator('[data-supplement-input=source_kind]').select_option('manual')
    card.locator('[data-supplement-input=employment_id]').select_option(job['id'])
    expect(card.locator('[data-supplement-input=company_name]')).to_have_value('原組織')
    card.locator('[data-supplement-input=job_title]').fill('新職稱');card.get_by_role('button',name='加入待核對項目',exact=True).click()
    page.get_by_role('button',name='＋ 新增人物',exact=True).click();pending=page.locator('[data-pending-target]');pending.locator('[data-target-name]').fill('待建立人物');pending.locator('[data-target-role]').select_option('participant');ref=pending.get_attribute('data-client-ref')
    supplement(page.locator('[data-supplement-person="pending:'+ref+'"]'),'birthday',{'birth_month':'1','birth_day':'2'})
    page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible()
    page.locator('[data-experience-preview="existing:'+person['id']+'"]').click();expect(page.locator('[data-basic-prior]')).to_contain_text('原職稱')
    expect(page.locator('[data-basic-review-row]')).to_contain_text('新職稱');page.locator('[data-basic-select]').check();page.get_by_role('button',name='完成檢視',exact=True).click()
    page.locator('[data-experience-preview="pending:'+ref+'"]').click();page.locator('[data-basic-select]').check();page.get_by_role('button',name='完成檢視',exact=True).click()
    page.locator('#story-reviewed').check()
    page.route('**/api/drafts/*/confirm',lambda r:r.fulfill(status=503,json={'error':{'message':'合成失敗'}}))
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#notice')).to_contain_text('合成失敗')
    assert page.request.get(BASE+'/api/people/'+person['id']+'/details').json()['employments'][0]['job_title']=='原職稱'
    page.unroute('**/api/drafts/*/confirm')
    changed=page.request.patch(BASE+'/api/people/'+person['id']+'/employments/'+job['id'],headers=h,data={'request_id':'other-session','expected_revision':1,'confirmed':True,'value':{'job_title':'其他裝置更正'},'source':{'source_kind':'manual'}});assert changed.ok
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#notice')).to_contain_text('任職已有新版')
    rolled_back=page.request.get(BASE+'/api/state').json();assert len(rolled_back['people'])==1 and not rolled_back['experiences'] and not rolled_back['rewards']['events']
    pg_receipt(page,'late_conflict_before_retry',expected_experiences=0)
    page.locator('[data-experience-preview="existing:'+person['id']+'"]').click();expect(page.locator('[data-basic-prior]')).to_contain_text('版本已變更')
    expect(page.locator('[data-basic-select]')).not_to_be_checked();expect(page.locator('[data-basic-select]')).to_be_disabled()
    page.locator('[data-basic-exclude]').click();page.get_by_role('button',name='完成檢視',exact=True).click()
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    assert page.request.get(BASE+'/api/people/'+person['id']+'/details').json()['employments'][0]['job_title']=='其他裝置更正'
    assert len(page.request.get(BASE+'/api/state').json()['rewards']['events'])==1

    pg_receipt(page,'late_version_conflict_rollback')


@pytest.mark.parametrize('month,day,year',[('2','31',''),('','','2000'),('','12','')])
def test_invalid_date_can_be_drafted_but_must_be_excluded_and_unadded_data_is_preserved(page,month,day,year):
    person,h=seed(page);card=choose_existing(page,person)
    card.locator('[data-supplement-input=dimension]').select_option('birthday');supplement_source(card);card.locator('[data-supplement-input=source_kind]').select_option('manual');card.locator('[data-supplement-input=birth_month]').fill(month);card.locator('[data-supplement-input=birth_day]').fill(day);card.locator('[data-supplement-input=birth_year]').fill(year)
    page.locator('[data-experience-review]').click();expect(page.locator('#notice')).to_contain_text('尚未加入候選')
    card.get_by_role('button',name='加入待核對項目',exact=True).click()
    page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible()
    page.locator('[data-experience-preview]').click();page.locator('[data-basic-select]').click();expect(page.locator('[data-basic-select]')).not_to_be_checked()
    page.locator('[data-basic-exclude]').click();page.get_by_role('button',name='完成檢視',exact=True).click()
    page.locator('#story-reviewed').check();page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    assert page.request.get(BASE+'/api/people/'+person['id']+'/details').json()['birthday'] is None


def test_basic_partial_local_input_restores_without_server_write(page):
    person,h=seed(page);card=choose_existing(page,person)
    card.locator('[data-supplement-input=dimension]').select_option('birthday');supplement_source(card);card.locator('[data-supplement-input=source_kind]').select_option('manual');card.locator('[data-supplement-input=birth_month]').fill('4')
    page.get_by_role('button',name='離開記錄',exact=True).click();page.get_by_role('button',name='保留此裝置草稿並離開',exact=True).click()
    other=page.context.new_page()
    try:
        other.goto(BASE+'/#record');expect(other.locator('#raw-text')).to_have_value('和小安一起閱讀，提到小明。')
        other.locator('[data-experience-next]').click();other.locator('[data-experience-next]').click();restored=other.locator('[data-supplement-person]');restored.locator('summary').first.click()
        expect(restored.locator('[data-supplement-input=dimension]')).to_have_value('birthday');expect(restored.locator('[data-supplement-input=birth_month]')).to_have_value('4')
        assert not other.request.get(BASE+'/api/state').json()['drafts']
    finally:other.close()


def pg_receipt(page,case,expected_experiences=1):
    """只在明確本機PG設定下讀回計數/Runtime身分；不保存個人內容或憑證。"""
    import os,json,hashlib
    if not os.environ.get('LIFEWORLD_INTEGRATION_PG_CONFIG'):return
    from contextlib import closing
    from scripts.pg_integration_fixture import connect,DB
    owner=page.request.get(BASE+'/api/auth/me').json()['owner_id'];counts={}
    with closing(connect(DB,runtime=True)) as connection,closing(connection.cursor()) as cursor:
        cursor.execute('SELECT current_database(),current_user');database,role=cursor.fetchone();assert database==DB and role=='lw_e2e_app'
        cursor.execute('SHOW server_version');version=cursor.fetchone()[0]
        for table in ['people','experiences','person_basic_details','person_basic_detail_history','person_employments','person_employment_history','reward_ledger']:
            cursor.execute('SELECT count(*) FROM lw_core_draft.'+table+' WHERE owner_id=?',(owner,));counts[table]=cursor.fetchone()[0]
    assert counts['experiences']==counts['reward_ledger']==expected_experiences
    path=ART.parent/'evidence/BASIC_UI_PG_READBACK.json';data=json.loads(path.read_text()) if path.exists() else {}
    data[case]={'environment':'localhost marker PG18 only; not GCP','database':database,'server_version':version,'runtime_role':role,'owner_fingerprint':hashlib.sha256(owner.encode()).hexdigest()[:16],'counts':counts}
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


@pytest.mark.parametrize('width',[320,390,1440])
def test_two_new_people_full_basic_loop_logout_login_partial_adoption(page,width):
    page.set_viewport_size({'width':width,'height':950});_,h=seed(page);me=page.request.get(BASE+'/api/auth/me').json();record(page)
    refs=[]
    for index,name in enumerate(['小安','小明']):
        page.get_by_role('button',name='＋ 新增人物' if index==0 else '再加入一位人物',exact=True).click()
        pending=page.locator('[data-pending-target]').nth(index);pending.locator('[data-target-name]').fill(name);pending.locator('[data-target-role]').select_option('interaction' if index==0 else 'mention')
        if index:pending.locator('[data-target-start]').select_option('10')
        ref=pending.get_attribute('data-client-ref');refs.append(ref);card=page.locator('[data-supplement-person="pending:'+ref+'"]')
        supplement(card,'birthday',{'birth_month':'4' if index==0 else '2','birth_day':'12' if index==0 else '29'})
        supplement(card,'employment',{'company_name':'新組織甲' if index==0 else '新組織乙','job_title':'工程師' if index==0 else '設計師','employment_status':'current'})
        if index==0:supplement(card,'employment',{'company_name':'過去組織','job_title':'研究員','employment_status':'past','valid_from':'2018-01-01','valid_to':'2019-12-31'})
        # 額外候選將在第四步明確排除，不得因同人物其他項採用而一併保存。
        if index==1:supplement(card,'employment',{'company_name':'本次排除組織','job_title':'不應保存'})
    page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible();draft_id=page.evaluate('state.draft.id')
    assert len(page.request.get(BASE+'/api/state').json()['people'])==1
    page.get_by_role('button',name='保存核對草稿並離開',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    page.locator('#account-button').click();page.get_by_role('button',name='登出',exact=True).click();expect(page.get_by_role('heading',name='把每一步，種成自己的世界。')).to_be_visible()
    page.get_by_role('button',name='登入我的世界',exact=True).click();page.locator('#username').fill(me['username']);page.locator('#password').fill('synthetic-browser-password-2026');page.locator('#login-form button.primary').click();expect(page.locator('#world-relationships')).to_be_visible()
    assert page.request.get(BASE+'/api/auth/me').json()['owner_id']==me['owner_id']
    page.goto(BASE+'/#review/'+draft_id);page.reload();expect(page.locator('#review-form')).to_be_visible()
    for index,ref in enumerate(refs):
        page.locator('[data-experience-preview="pending:'+ref+'"]').click()
        for row in page.locator('[data-basic-review-row]').all():
            if '本次排除組織' in row.inner_text():row.locator('[data-basic-exclude]').click()
            else:row.locator('[data-basic-select]').check()
        page.get_by_role('button',name='完成檢視',exact=True).click()
    page.locator('#story-reviewed').check()
    with page.expect_response(lambda r:'/confirm' in r.url and r.request.method=='POST') as response:page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    assert response.value.status==201,response.value.text()
    repeated=page.request.post(response.value.url,headers={'X-CSRF-Token':page.request.get(BASE+'/api/auth/me').json()['csrf_token']},data=response.value.request.post_data_json);assert repeated.status==201 and repeated.json()==response.value.json()
    expect(page.locator('#review-form')).to_have_count(0)
    ids=response.value.json()['created_people']
    for index,ref in enumerate(refs):
        person_id=ids[ref];page.goto(BASE+'/#persons/'+person_id);page.reload();expect(page.locator('.person-basic-panel')).to_contain_text('4 月 12 日' if index==0 else '2 月 29 日')
        details=page.request.get(BASE+'/api/people/'+person_id+'/details').json();assert details['birthday']['birth_year'] is None
        assert len(details['employments'])==len(details['employment_history'])==(2 if index==0 else 1)
        assert all(j['company_name']!='本次排除組織' and j['source_kind']=='manual' for j in details['employments'])
        assert page.request.get(BASE+'/api/people/'+person_id+'/overview').json()['stats']['interactions']==(1 if index==0 else 0)
    pg_receipt(page,'two_new_people_'+str(width))


def test_raw_source_change_requires_recheck_while_manual_birthday_survives(page):
    person,h=seed(page);card=choose_existing(page,person)
    page.locator('[data-experience-prev]').click();page.locator('[data-experience-prev]').click();page.locator('#raw-text').fill('小安說在組織甲工作。');page.locator('[data-experience-next]').click();page.locator('[data-experience-next]').click()
    supplement(card,'birthday',{'birth_month':'2','birth_day':'29'})
    card.locator('summary').first.click();card.locator('[data-supplement-input=dimension]').select_option('employment');card.locator('[data-supplement-input=company_name]').fill('組織甲');supplement_source(card);card.locator('[data-supplement-input=source_kind]').select_option('raw');card.locator('[data-supplement-input=evidence_type]').select_option('stated_by_person');card.get_by_text('原文片段與補充說明',exact=True).click();card.locator('[data-supplement-input=quote]').fill('在組織甲工作');card.get_by_role('button',name='加入待核對項目',exact=True).click()
    page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible();page.locator('[data-experience-preview]').click()
    for row in page.locator('[data-basic-review-row]').all():row.locator('[data-basic-select]').check()
    page.get_by_role('button',name='完成檢視',exact=True).click()
    page.get_by_role('button',name='保存核對草稿並離開',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    d=page.request.get(BASE+'/api/state').json()['drafts'][0]
    page.goto(BASE+'/#review/'+d['id']);page.reload();page.get_by_role('button',name='返回修改原始草稿',exact=True).click();page.locator('#raw-text').fill('小安說在組織甲工作。補記時間。');page.locator('[data-experience-next]').click();page.locator('[data-experience-next]').click();page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible()
    changed=page.request.get(BASE+'/api/drafts/'+d['id']).json()['review'];assert changed['birthday_candidates'][0]['selected'] and not changed['birthday_candidates'][0]['needs_review']
    assert not changed['employment_candidates'][0]['selected'] and changed['employment_candidates'][0]['needs_review']
    page.locator('[data-summary-source-review]').check();page.locator('[data-experience-preview]').click()
    row=page.locator('[data-basic-review-row]').nth(1);expect(row).to_contain_text('原始經歷已修改');expect(row.locator('[data-basic-select]')).not_to_be_checked();row.locator('[data-basic-select]').check();page.get_by_role('button',name='完成檢視',exact=True).click()
    page.locator('#story-reviewed').check();page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    details=page.request.get(BASE+'/api/people/'+person['id']+'/details').json();assert details['employments'][0]['source_kind']=='raw' and details['employments'][0]['evidence_type']=='stated_by_person' and details['employments'][0]['source_experience_id']
    pg_receipt(page,'raw_source_recheck')


def test_unknown_confirm_result_retries_without_duplicate_rows(page):
    person,h=seed(page);card=choose_existing(page,person);supplement(card,'birthday',{'birth_month':'4','birth_day':'12'})
    page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible();page.locator('[data-experience-preview]').click();page.locator('[data-basic-select]').check();page.get_by_role('button',name='完成檢視',exact=True).click();page.locator('#story-reviewed').check()
    def lose_response(route):
        response=route.fetch();assert response.status==201,response.text();route.abort('failed')
    page.route('**/api/drafts/*/confirm',lose_response)
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#notice')).to_contain_text('無法連線')
    state=page.request.get(BASE+'/api/state').json();assert len(state['experiences'])==len(state['rewards']['events'])==1
    page.unroute('**/api/drafts/*/confirm',lose_response)
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    details=page.request.get(BASE+'/api/people/'+person['id']+'/details').json();assert len(details['birthday_history'])==1
    assert len(page.request.get(BASE+'/api/state').json()['rewards']['events'])==1
    pg_receipt(page,'lost_confirm_response_retry')


def test_draft_save_503_then_lost_timeout_response_preserves_and_recovers_once(page):
    person,h=seed(page);card=choose_existing(page,person);supplement(card,'birthday',{'birth_month':'4','birth_day':'12'})
    page.route('**/api/experiences/drafts',lambda route:route.fulfill(status=503,json={'error':{'message':'合成保存失敗'}}))
    page.locator('[data-experience-review]').click();expect(page.locator('#notice')).to_contain_text('合成保存失敗')
    assert not page.request.get(BASE+'/api/state').json()['drafts'];expect(card).to_contain_text('4 月 12 日')
    page.unroute('**/api/experiences/drafts')
    def lost_timeout(route):
        response=route.fetch();assert response.status==201,response.text();route.abort('timedout')
    page.route('**/api/experiences/drafts',lost_timeout)
    page.locator('[data-experience-review]').click();expect(page.locator('#notice')).to_contain_text('無法連線')
    state=page.request.get(BASE+'/api/state').json();assert len(state['drafts'])==1 and not state['experiences'] and not state['rewards']['events']
    expect(card).to_contain_text('4 月 12 日');page.unroute('**/api/experiences/drafts')
    page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible()
    assert len(page.request.get(BASE+'/api/state').json()['drafts'])==1
    page.locator('[data-experience-preview]').click();page.locator('[data-basic-select]').check();page.get_by_role('button',name='完成檢視',exact=True).click();page.locator('#story-reviewed').check()
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    assert len(page.request.get(BASE+'/api/people/'+person['id']+'/details').json()['birthday_history'])==1
    pg_receipt(page,'draft_save_503_timeout_recovery')


def test_switching_information_category_never_discards_unadded_text(page):
    person,h=seed(page);card=choose_existing(page,person)
    card.locator('[data-supplement-input=dimension]').select_option('interests');card.locator('[data-supplement-input=value]').fill('尚未加入的登山喜好');supplement_source(card);card.locator('[data-supplement-input=source_kind]').select_option('manual')
    card.locator('[data-supplement-input=dimension]').select_option('birthday')
    expect(card.locator('[data-supplement-input=dimension]')).to_have_value('interests')
    expect(card.locator('[data-supplement-status]')).to_contain_text('請先加入')
    expect(card.locator('[data-supplement-input=value]')).to_be_visible()
    expect(card.locator('[data-supplement-input=value]')).to_have_value('尚未加入的登山喜好')
    card.get_by_role('button',name='清空這次輸入',exact=True).click();expect(card.locator('[data-supplement-input=value]')).to_have_value('')
    assert not page.request.get(BASE+'/api/state').json()['drafts'] and page.request.get(BASE+'/api/people/'+person['id']+'/details').json()['birthday'] is None
