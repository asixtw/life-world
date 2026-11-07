"""單一RC的完整瀏覽器閉環；必須搭配明示AI Fixture隔離服務，非真實OAuth/AI。"""
from uuid import uuid4
import pytest
from playwright.sync_api import expect
from test_journey import page,onboarding,BASE

@pytest.mark.parametrize('width',[390,1440])
def test_rc_goal_ai_review_progress_reward_reload(page,width):
    """三次孵化、Guest安全、AI草稿編輯、確認、重送與回讀。"""
    page.set_viewport_size({'width':width,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    onboarding(page)
    goal=page.request.get(BASE+'/api/state').json()['goals'][0]
    page.get_by_role('link',name='記錄新經歷',exact=True).click()
    page.locator('#raw-text').fill('合成測試：今天閱讀15分鐘，整理一個重點。')
    page.locator('#occurred-at').fill('2026-10-27T10:00')
    page.locator('#goal-id').select_option(goal['id'])
    page.locator('#quantity-'+goal['actions'][0]['id']).fill('0.5')
    page.get_by_role('button',name='保存草稿並進入核對').click()
    expect(page.locator('#review-form')).to_be_visible()
    expect(page.get_by_role('button',name='使用 AI 整理本篇原文')).to_have_count(0)
    # 測試帳號僅此隔離服務；登入方式不冒充Google真實登入。
    claimed=page.evaluate("async name=>api('/auth/claim',{method:'POST',body:{username:name,password:'rc-synthetic-password-only'}})",'rc_'+uuid4().hex[:12])
    assert claimed['status']=='registered'
    page.reload()
    expect(page.get_by_role('button',name='使用 AI 整理本篇原文')).to_be_visible()
    with page.expect_response(lambda r:'/suggest' in r.url and r.request.method=='POST') as candidate:
        page.get_by_role('button',name='使用 AI 整理本篇原文').click()
    assert candidate.value.status==200
    assert '測試替身' in candidate.value.json()['notice']
    state=page.request.get(BASE+'/api/state').json()
    assert state['experiences']==[] and state['rewards']['total']==0
    assert state['goals'][0]['actions'][0]['progress']=='0'
    page.get_by_role('button',name='套用摘要與任務草稿').click()
    expect(page.locator('#summary')).to_have_value('合成Fixture：今天閱讀15分鐘，整理一個重點。')
    page.locator('#summary').fill('由測試者人工修改並確認的閱讀摘要。')
    page.locator('#followups').fill('明天再閱讀15分鐘')
    assert page.request.get(BASE+'/api/state').json()['rewards']['total']==0
    with page.expect_response(lambda r:r.url.endswith('/confirm') and r.request.method=='POST') as confirmation:
        page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    response=confirmation.value;assert response.status==201
    receipt=response.json();body=response.request.post_data_json
    expect(page.locator('#toast')).to_contain_text('已確認保存')
    # 原request_id與內容重送，直接走正式API交易去重。
    replay=page.evaluate("async x=>api(x.path,{method:'POST',body:x.body})",{'path':response.url.split('/api')[1],'body':body})
    assert replay==receipt
    page.reload()
    expect(page.get_by_text('由測試者人工修改並確認的閱讀摘要。',exact=True)).to_be_visible()
    saved=page.request.get(BASE+'/api/state').json()
    assert len(saved['experiences'])==len(saved['tasks'])==1
    assert saved['rewards']['total']==receipt['points_awarded']
    assert saved['goals'][0]['actions'][0]['progress']=='0.5'
    page.locator('#nav').get_by_role('link',name='世界',exact=True).click()
    expect(page.get_by_role('heading',name='Lumi',exact=True)).to_be_visible()
    expect(page.get_by_text('照自己的步調，慢慢前進。',exact=True)).to_be_visible()
    expect(page.locator('#app-loading')).to_be_hidden()
    assert not errors,errors
