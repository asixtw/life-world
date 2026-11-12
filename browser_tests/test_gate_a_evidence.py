"""Gate A 實際UI/PG證據；僅合成資料，錄影不冒充UX核准或真外部AI。"""
from test_journey import supplement_source
from test_journey import set_occurred
import json
import subprocess
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright, expect
from test_journey import BASE
from test_integration_person_details import seed

import os
ART=Path(os.environ.get('LIFEWORLD_UX_ARTIFACT_DIR',str(Path(__file__).resolve().parents[1]/'docs/integration/2026-11-12_GATE_A')))


def shot(page,width,name):
    """保留完整頁面；先等短暫提示消失，避免截圖遮住主要操作。"""
    expect(page.locator('#toast')).not_to_have_class('visible')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(ART/f'{width}-{name}.png'),full_page=not name.startswith('preview'))


def add(card,kind,values,source_kind='manual',quote=None):
    if card.get_attribute('open') is None:card.locator('summary').first.click()
    card.locator('[data-supplement-input=dimension]').select_option(kind)
    supplement_source(card);card.locator('[data-supplement-input=source_kind]').select_option(source_kind)
    if quote:
        card.get_by_text('原文片段與補充說明',exact=True).click()
        card.locator('[data-supplement-input=quote]').fill(quote)
    card.locator('[data-supplement-input=evidence_type]').select_option('stated_by_person')
    for key,value in values.items():
        field=card.locator('[data-supplement-input="'+key+'"]')
        if key in ('employment_status','employment_id'):field.select_option(value)
        else:field.fill(value)
    card.get_by_role('button',name='加入資訊',exact=True).click()
    expect(card).not_to_have_attribute('open','')


@pytest.mark.parametrize('width',[320,390,1440])
def test_gate_a_full_flow_video_and_readback(width):
    ART.mkdir(parents=True,exist_ok=True)
    errors=[];model_requests=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,slow_mo=65)
        context=browser.new_context(viewport={'width':width,'height':900},locale='zh-TW',record_video_dir=str(ART/'video'),record_video_size={'width':width,'height':900})
        page=context.new_page();page.set_default_timeout(15000)
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda req:model_requests.append(req.url) if req.method=='POST' and '/api/ai/' in req.url else None)
        video=page.video
        try:
            person,headers=seed(page)
            before=page.request.get(BASE+'/api/state').json();goal=before['goals'][0];action=goal['actions'][0]
            raw='今天與人物小安閱讀並交流，也提到小明。人物小安告訴我喜歡登山、清淡飲食、擅長設計、習慣先聆聽。'
            page.goto(BASE+'/#record');page.reload()
            page.locator('#raw-text').fill(raw);set_occurred(page,'2026-10-27T12:00')
            time=page.locator('[data-moment-time]')
            if time.count() and time.get_attribute('open') is not None:time.locator('summary').first.click()
            shot(page,width,'step1')
            page.locator('[data-experience-next]').click();page.locator('#goal-id').select_option(goal['id'])
            page.locator('[name="quantity-'+action['id']+'"]').fill('0.5');shot(page,width,'step2')
            page.locator('[data-experience-next]').click()
            page.get_by_role('button',name='選擇既有人物',exact=True).click();page.locator('[data-workflow-pick="'+person['id']+'"]').click()
            page.locator('[data-workflow-role]').select_option('interaction')
            card=page.locator('[data-supplement-person="existing:'+person['id']+'"]')
            for dimension,value in [('interests','登山'),('food','清淡飲食'),('skills','設計'),('habits','先聆聽')]:
                add(card,dimension,{'value':value},source_kind='raw' if dimension=='interests' else 'manual',quote='人物小安告訴我喜歡登山' if dimension=='interests' else None)
            add(card,'birthday',{'birth_month':'4','birth_day':'12'})
            add(card,'employment',{'company_name':'合成組織甲','job_title':'研究員','employment_status':'current'})
            page.get_by_role('button',name='＋ 新增人物',exact=True).click()
            pending=page.locator('[data-pending-target]');pending.locator('[data-target-name]').fill('小明');pending.locator('[data-target-role]').select_option('mention')
            pending.locator('[data-target-start]').select_option(str(raw.index('小明')))
            ref=pending.get_attribute('data-client-ref');second=page.locator('[data-supplement-person="pending:'+ref+'"]')
            add(second,'employment',{'company_name':'合成組織乙','job_title':'設計師','employment_status':'past','valid_from':'2020-01-01','valid_to':'2024-12-31'})
            shot(page,width,'step3')
            card.locator('summary').first.click();shot(page,width,'step3-supplement');card.locator('summary').first.click()
            assert len(page.request.get(BASE+'/api/state').json()['people'])==1
            page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible()
            page.locator('#summary').fill('閱讀交流，整理人物小安親口告知的資訊；小明僅為原文提及。')
            shot(page,width,'step4-before-review')
            draft_id=page.evaluate('state.draft.id')
            page.get_by_role('button',name='保存核對草稿並離開',exact=True).click()
            page.goto(BASE+'/#review/'+draft_id);page.reload();expect(page.locator('#review-form')).to_be_visible()
            saved=page.request.get(BASE+'/api/drafts/'+draft_id).json()['review']
            assert len(saved['person_candidates'])==4 and len(saved['birthday_candidates'])==1 and len(saved['employment_candidates'])==2
            unchanged=page.request.get(BASE+'/api/state').json()
            assert not unchanged['experiences'] and not unchanged['rewards']['events'] and len(unchanged['people'])==1
            for key,is_new in [('existing:'+person['id'],False),('pending:'+ref,True)]:
                page.locator('[data-experience-preview="'+key+'"]').click()
                body=page.locator('.experience-preview-body')
                for details in body.locator('details').all():
                    if details.get_attribute('open') is None:details.locator('summary').first.click()
                if not is_new:
                    rows=page.locator('[data-candidate-row]');expect(rows).to_have_count(4)
                    for i,row in enumerate(rows.all()):
                        if i==1:row.locator('[data-candidate-exclude]').click()
                        else:row.locator('[data-candidate-select]').check()
                for row in page.locator('[data-basic-review-row]').all():row.locator('[data-basic-select]').check()
                # 滾動錄影保留長內容；底部完成按鈕始終可操作。
                for fraction in (0,.75,1):
                    body.evaluate('(node,f)=>node.scrollTop=(node.scrollHeight-node.clientHeight)*f',fraction)
                    page.wait_for_timeout(350)
                    if fraction==.75 and not is_new:shot(page,width,'preview-existing-more')
                body.evaluate('(node)=>node.scrollTop=0')
                shot(page,width,'preview-new' if is_new else 'preview-existing')
                page.get_by_role('button',name='完成檢視',exact=True).click()
            expect(page.locator('[data-experience-preview="existing:'+person['id']+'"]')).to_contain_text('已核對：採用 5 項／排除 1 項')
            expect(page.locator('[data-experience-preview="pending:'+ref+'"]')).to_contain_text('已核對：採用 1 項／排除 0 項')
            page.locator('#story-reviewed').check();shot(page,width,'step4-ready')
            with page.expect_response(lambda r:'/confirm' in r.url and r.request.method=='POST') as received:
                page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
            response=received.value;assert response.status==201,response.text()
            repeated=page.request.post(response.url,headers=headers,data=response.request.post_data_json)
            assert repeated.status==201 and repeated.json()==response.json()
            expect(page.locator('#review-form')).to_have_count(0)
            after=page.request.get(BASE+'/api/state').json();new=next(x for x in after['people'] if x['name']=='小明')
            assert len(after['people'])==2 and len(after['experiences'])==len(after['rewards']['events'])==1
            assert after['goals'][0]['actions'][0]['progress']=='0.5'
            overview=page.request.get(BASE+'/api/people/'+person['id']+'/overview').json()
            assert overview['facts']['food']==[]
            for dimension in ('interests','skills','habits'):assert len(overview['facts'][dimension])==1
            assert overview['stats']['interactions']==1
            details=page.request.get(BASE+'/api/people/'+person['id']+'/details').json()
            assert details['birthday']['birth_year'] is None and details['birthday']['birth_month']==4 and details['birthday']['birth_day']==12
            assert details['employments'][0]['company_name']=='合成組織甲' and details['employments'][0]['job_title']=='研究員'
            new_details=page.request.get(BASE+'/api/people/'+new['id']+'/details').json()
            assert new_details['employments'][0]['employment_status']=='past' and new_details['employments'][0]['company_name']=='合成組織乙'
            assert overview['facts']['interests'][0]['sources'][0]['id']==after['experiences'][0]['id']
            assert page.request.get(BASE+'/api/people/'+new['id']+'/overview').json()['stats']['interactions']==0
            page.goto(BASE+'/#persons/'+person['id']);page.reload();expect(page.locator('.person-basic-panel')).to_contain_text('合成組織甲')
            shot(page,width,'confirmed-person')
            assert not errors and not model_requests
            receipt={'width':width,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'database_scope':'isolated_local_pg18','new_people_before_confirm':0,'people_after':2,'experience_count':1,'reward_count':1,'goal_progress':'0.5','four_dimensions':{'adopted':['interests','skills','habits'],'excluded':['food']},'birthday_year':None,'employment_people':2,'duplicate_confirm_same_receipt':True,'javascript_errors':errors,'ai_post_requests':model_requests,'real_google':'NOT RUN','real_gemini':'NOT RUN'}
            (ART/f'{width}-result.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        finally:
            page.close();context.close()
            video.save_as(str(ART/f'{width}-flow.webm'));video.delete()
            browser.close()
