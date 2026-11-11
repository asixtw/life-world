"""隔離 Chromium 四步與人物複用；沒有呼叫真實模型。"""
from pathlib import Path
from uuid import uuid4
import pytest
from playwright.sync_api import expect
from test_journey import BASE, page, onboarding

ART = Path(__file__).parents[1] / 'docs/integration/2026-11-11/screenshots/four-step-regression'


def setup(page, registered=True):
    onboarding(page)
    me=page.request.get(BASE+'/api/auth/me').json()
    if registered:
        r=page.request.post(BASE+'/api/auth/claim',headers={'X-CSRF-Token':me['csrf_token']},data={'username':'flow_'+uuid4().hex[:12],'password':'synthetic-flow-password-2026'})
        assert r.ok, r.text()
        me=r.json();page.reload()
        expect(page.locator('#world-relationships')).to_be_visible()
    return {'X-CSRF-Token':me['csrf_token']}


def shot(page,name):
    ART.mkdir(parents=True,exist_ok=True)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    expect(page.locator('#toast')).not_to_have_class('visible')
    page.screenshot(path=str(ART/name),full_page=True)


@pytest.mark.parametrize('width',[320,390,1440])
def test_pending_four_steps_and_choices(page,width):
    page.set_viewport_size({'width':width,'height':900})
    headers=setup(page)
    r=page.request.post(BASE+'/api/people',headers=headers,data={'name':'人物甲','roles':['合作夥伴','舊、完整角色'],'tags':['學校專題'],'common_context':'資訊管理課'})
    assert r.ok
    p=r.json()
    page.goto(BASE+'/#people?view=cards');page.reload()
    page.get_by_role('button',name='＋ 新增人物',exact=True).click()
    expect(page.locator('[name=tags_selected]')).to_have_count(1)
    page.locator('[name=roles_selected]').first.check()
    page.locator('[name=tags_selected]').check()
    page.locator('#person-name').fill('人物乙')
    page.locator('#common-context').fill('資訊管理課')
    shot(page,f'{width}-person-choices.png')
    page.get_by_role('button',name='保存人物',exact=True).click()
    expect(page.locator('#account-dialog')).not_to_be_visible()
    people=page.request.get(BASE+'/api/state').json()['people']
    assert len(people)==2 and people[1]['tags']==['學校專題']
    page.goto(BASE+'/#record')
    expect(page.locator('#experience-step-title')).to_have_text('記錄經歷')
    page.locator('#raw-text').fill('今天與小安一起讀書，也提到人物甲。')
    # 合成服務固定時鐘；不使用瀏覽器實際今日，仍保留後端禁止未來經歷的規則。
    page.locator('#occurred-at').fill('2026-10-27T12:00')
    shot(page,f'{width}-step1.png')
    page.get_by_role('button',name='下一步',exact=True).click()
    expect(page.locator('#experience-step-title')).to_have_text('目標活動數量')
    page.locator('[name=goal_id]').select_option('')
    shot(page,f'{width}-step2.png')
    page.get_by_role('button',name='下一步',exact=True).click()
    page.get_by_role('button',name='＋ 新增人物',exact=True).click()
    page.locator('[data-pending-target]').first.locator('[data-target-name]').fill('小安')
    page.locator('[data-pending-target]').first.locator('[data-target-role]').select_option('interaction')
    # 新版以逐人卡片明確選角色；維持原測試的共同參與契約，不由原文推論。
    page.get_by_role('button',name='選擇既有人物',exact=True).click()
    page.locator('[data-workflow-pick="'+p['id']+'"]').click()
    page.locator('[data-workflow-person]').first.locator('[data-workflow-role]').select_option('participant')
    page.get_by_role('button',name='上一步',exact=True).click()
    page.get_by_role('button',name='下一步',exact=True).click()
    expect(page.locator('[data-pending-target]').first.locator('[data-target-name]')).to_have_value('小安')
    assert len(page.request.get(BASE+'/api/state').json()['people'])==2
    shot(page,f'{width}-step3.png')
    page.get_by_role('button',name='檢視並確認 →',exact=True).click()
    expect(page.locator('#review-form')).to_be_visible()
    expect(page.locator('[data-pending-target]').first.locator('[data-target-name]')).to_have_value('小安')
    page.locator('#summary').fill('一起閱讀並討論。')
    page.locator('#story-reviewed').check()
    shot(page,f'{width}-step4.png')
    with page.expect_response(lambda r:'/confirm' in r.url and r.request.method=='POST') as completed:
        page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    # 重送瀏覽器實際payload，證明不重複建人或發獎，並非另一份手工契約。
    original=completed.value
    repeated=page.request.post(original.url,headers=headers,data=original.request.post_data_json)
    assert repeated.status==201 and repeated.json()==original.json()
    expect(page.get_by_role('heading',name='收藏每一段真實。')).to_be_visible()
    data=page.request.get(BASE+'/api/state').json()
    assert len(data['people'])==3 and len(data['experiences'])==1 and len(data['rewards']['events'])==1
    story=page.request.get(BASE+'/api/connections/stories/'+data['experiences'][0]['id']).json()
    assert len(story['participants'])==2 and not story['mentions']
    assert {x['name']:x['interacted'] for x in story['participants']}=={'人物甲':False,'小安':True}
    page.reload()
    expect(page.locator('.record-content')).to_contain_text('一起閱讀並討論。')
    assert page.request.get(BASE+'/api/connections').json()['total']==1
    assert not page.request.get(BASE+'/api/connections?involvement=legacy').json()['items']


def test_guest_diary_and_failure_preserves_input(page):
    setup(page,False)
    page.goto(BASE+'/#record')
    expect(page.locator('#media-panel')).to_have_count(0)
    page.locator('#raw-text').fill('今天獨自散步。')
    # 合成服務固定時鐘；不使用瀏覽器實際今日，仍保留後端禁止未來經歷的規則。
    page.locator('#occurred-at').fill('2026-10-27T12:00')
    page.get_by_role('button',name='下一步',exact=True).click()
    page.locator('[name=goal_id]').select_option('')
    page.get_by_role('button',name='下一步',exact=True).click()
    expect(page.locator('[name=pending_person_enabled]')).to_have_count(0)
    page.get_by_role('button',name='檢視並確認 →',exact=True).click()
    expect(page.locator('#review-form')).to_be_visible()
    page.route('**/api/drafts/*/confirm',lambda route:route.fulfill(status=503,json={'error':{'message':'合成暫時失敗'}}))
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    expect(page.locator('#summary')).to_have_value('今天獨自散步。')
    page.unroute('**/api/drafts/*/confirm')
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    expect(page.get_by_role('heading',name='收藏每一段真實。')).to_be_visible()
    assert page.request.get(BASE+'/api/connections?involvement=legacy').json()['total']==0


def test_cancel_pending_person_leaves_no_orphan(page):
    setup(page)
    page.goto(BASE+'/#record')
    page.locator('#raw-text').fill('還未決定是否保存的經歷。')
    # 合成服務固定時鐘；不使用瀏覽器實際今日，仍保留後端禁止未來經歷的規則。
    page.locator('#occurred-at').fill('2026-10-27T12:00')
    page.get_by_role('button',name='下一步',exact=True).click()
    page.get_by_role('button',name='下一步',exact=True).click()
    page.get_by_role('button',name='＋ 新增人物',exact=True).click()
    page.locator('[data-pending-target]').first.locator('[data-target-name]').fill('尚未建立的人物')
    page.get_by_role('button',name='離開記錄',exact=True).click()
    page.get_by_role('button',name='繼續編輯',exact=True).click()
    expect(page.locator('[data-pending-target]').first.locator('[data-target-name]')).to_have_value('尚未建立的人物')
    page.get_by_role('button',name='離開記錄',exact=True).click()
    page.get_by_role('button',name='捨棄未保存修改並離開',exact=True).click()
    # 專注流程的離開入口回到紀錄；恢復全域導覽後仍能返回世界。
    expect(page.get_by_role('heading',name='收藏每一段真實。')).to_be_visible()
    expect(page.locator('#nav')).to_be_visible()
    page.locator('#nav').get_by_role('link',name='世界',exact=True).click()
    expect(page.locator('#world-relationships')).to_be_visible()
    state=page.request.get(BASE+'/api/state').json()
    assert not state['people'] and not state['experiences'] and not state['drafts']


def test_goal_quantity_and_media_survive_steps(page):
    """本機影像不經模型，換步保留；數量只在最後確認入帳。"""
    from test_journey import PNG
    setup(page)
    before=page.request.get(BASE+'/api/state').json()
    goal=before['goals'][0];action=goal['actions'][0]
    page.goto(BASE+'/#record')
    page.locator('#raw-text').fill('完成半小時練習，附上合成圖片。')
    # 合成服務固定時鐘；不使用瀏覽器實際今日，仍保留後端禁止未來經歷的規則。
    page.locator('#occurred-at').fill('2026-10-27T12:00')
    page.locator('[data-media-file=image]').set_input_files({'name':'synthetic.png','mimeType':'image/png','buffer':PNG})
    expect(page.locator('.media-item')).to_have_count(1)
    page.get_by_role('button',name='下一步',exact=True).click()
    page.locator('[name=goal_id]').select_option(goal['id'])
    page.locator('[name="quantity-'+action['id']+'"]').fill('0.5')
    page.get_by_role('button',name='上一步',exact=True).click()
    expect(page.locator('.media-item')).to_have_count(1)
    expect(page.locator('#raw-text')).to_have_value('完成半小時練習，附上合成圖片。')
    page.get_by_role('button',name='下一步',exact=True).click()
    expect(page.locator('[name="quantity-'+action['id']+'"]')).to_have_value('0.5')
    assert page.request.get(BASE+'/api/state').json()['rewards']==before['rewards']
    page.get_by_role('button',name='下一步',exact=True).click()
    page.get_by_role('button',name='檢視並確認 →',exact=True).click()
    expect(page.locator('#review-form')).to_be_visible()
    expect(page.locator('[name="quantity-'+action['id']+'"]')).to_have_value('0.5')
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    expect(page.get_by_role('heading',name='收藏每一段真實。')).to_be_visible()
    result=page.request.get(BASE+'/api/state').json()
    assert result['goals'][0]['actions'][0]['progress']=='0.5'
    assert len(result['rewards']['events'])==1
