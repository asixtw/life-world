"""月曆只讀、版本用量與裝置邊界的實際瀏覽器驗收。"""
from datetime import date,timedelta
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_journey import BASE,page
from test_dashboard import seed
from test_flow_wireframe import wireframe_url


@pytest.mark.parametrize('width',[320,390,1440])
def test_month_view_read_only_record_and_restore(page,width,tmp_path):
    page.set_viewport_size({'width':width,'height':844 if width<768 else 900})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    goal,headers,today=seed(page,False)
    expect(page.get_by_role('region',name='目標儀表板')).to_be_visible()
    before=page.request.get(BASE+'/api/state').json()
    box=page.locator('.habit-schedule').first
    box.locator('summary').click()
    expect(box.locator('.hs-grid')).to_be_visible()
    assert box.locator('.hs-grid button').count()<=31
    assert box.locator('.hs-grid button').first.bounding_box()['width']>=44
    box.locator('[data-date="'+today+'"]').click()
    expect(box.get_by_text('已安排；原訂預期量：1 次',exact=True)).to_be_visible()
    expect(box.get_by_text('當日已確認投入：暫無逐日統計。')).to_be_visible()
    assert page.request.get(BASE+'/api/state').json()==before
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.evaluate("document.documentElement.style.fontSize='200%'")
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.evaluate("document.documentElement.style.fontSize=''")
    page.screenshot(path=str(tmp_path/('schedule-'+str(width)+'.png')),full_page=True)
    box.get_by_role('button',name='記錄這次投入',exact=True).click()
    expect(page.locator('#calendar-date')).to_have_value(today)
    expect(page.locator('#calendar-time')).to_have_value('')
    assert page.locator('[name^="quantity-"]').evaluate_all('(nodes)=>nodes.every(n=>n.value==="")')
    page.goto(BASE+'/#goal/'+goal['id'])
    expect(page.locator('.habit-schedule').first.locator('.hs-grid')).to_be_visible()
    assert page.locator('.habit-schedule').first.get_attribute('open') is not None
    page.reload()
    expect(page.locator('.habit-schedule').first).not_to_have_attribute('open','')
    assert errors==[]


def test_month_request_failure_and_future_day(page):
    goal,headers,today=seed(page,False)
    expect(page.get_by_role('region',name='目標儀表板')).to_be_visible()
    box=page.locator('.habit-schedule').first;box.locator('summary').click()
    expect(box.locator('.hs-grid')).to_be_visible()
    tomorrow=str(date.fromisoformat(today)+timedelta(days=1))
    if tomorrow[:7]==today[:7]:
        box.locator('[data-date="'+tomorrow+'"]').click()
        expect(box.get_by_text('這天沒有安排這項習慣')).to_be_visible()
        expect(box.get_by_role('button',name='記錄這次投入')).to_have_count(0)
    page.route('**/api/goals/*/calendar?*',lambda r:r.abort())
    if box.get_by_role('button',name='閱讀下一月').is_enabled():
        month=box.locator('.hs-month b').inner_text()
        box.get_by_role('button',name='閱讀下一月').click()
        expect(box.get_by_role('alert')).to_contain_text('保留上次已讀資料')
        expect(box.locator('.hs-month b')).to_have_text(month)
        page.unroute('**/api/goals/*/calendar?*')
        box.get_by_role('button',name='重試月份').click()
        expect(box.get_by_role('alert')).to_have_count(0)


def test_prototype_month_schedule(page,wireframe_url):
    page.goto(wireframe_url)
    page.evaluate("""()=>{const d=dateNow();s.goal={id:'month-demo',title:'示例',outcome:'閱讀',status:'進行中',start:d,deadline:shift(d,40),actions:['閱讀','整理','分享'].map((title,i)=>({id:'a'+i,title,unit:'次',quantity:'1',dates:[d],cycle:'month'}))};s.route='goal';save();render();}""")
    box=page.locator('.habit-schedule').first;box.locator('summary').click()
    expect(box.locator('.hs-grid')).to_be_visible()
    assert box.locator('.hs-grid button').count()<=31


def test_calendar_quantity_versions_and_clipped_last_month(page):
    goal,headers,today=seed(page,False)
    tomorrow=str(date.fromisoformat(today)+timedelta(days=1))
    g=page.request.get(BASE+'/api/goals/'+goal['id']).json()
    rows=[{'action_id':a['id'],'dates':[today,tomorrow],'weekdays':[],'cycle':'month'} for a in g['actions']]
    rows[0]['per_occurrence']='3'
    result=page.request.post(BASE+'/api/goals/'+g['id']+'/review',headers=headers,data={'request_id':'version-calendar','expected_revision':g['revision'],'decision':'schedule','confirmed':True,'schedules':rows})
    assert result.ok,result.text()
    page.reload();box=page.locator('.habit-schedule').first;box.locator('summary').click()
    expect(box.locator('.hs-grid')).to_be_visible()
    box.locator('[data-date="'+today+'"]').click()
    expect(box.get_by_text('已安排；原訂預期量：1 次',exact=True)).to_be_visible()
    if tomorrow[:7]!=today[:7]:box.get_by_role('button',name='閱讀下一月').click()
    box.locator('[data-date="'+tomorrow+'"]').click()
    expect(box.get_by_text('已安排；原訂預期量：3 次',exact=True)).to_be_visible()
    if box.get_by_role('button',name='閱讀下一月').is_enabled():box.get_by_role('button',name='閱讀下一月').click()
    expect(box.get_by_role('button',name='閱讀下一月')).to_be_disabled()
    last=box.locator('[data-date="'+g['deadline']+'"]').first
    expect(last).to_be_enabled()
    assert box.locator('.hs-grid button:not([disabled])').count()<=31


def test_late_month_response_cannot_reopen_other_page(page):
    import json
    goal,headers,today=seed(page,False)
    expect(page.get_by_role('region',name='目標儀表板')).to_be_visible()
    month_end=min(goal['deadline'],str(date.fromisoformat(today).replace(day=28)+timedelta(days=4))[:7]+'-01')
    # 直接HTTP準備該月份回應；瀏覽器request的晚到時機另由route控制。
    from calendar import monthrange
    current=date.fromisoformat(today)
    end=str(current.replace(day=monthrange(current.year,current.month)[1]))
    data=page.request.get(BASE+'/api/goals/'+goal['id']+'/calendar?start='+today+'&end='+min(end,goal['deadline'])).json()
    held=[]
    page.route('**/api/goals/*/calendar?*',lambda route:(held.append(route),page.evaluate("document.body.dataset.monthHeld='yes'")))
    page.locator('.habit-schedule').first.locator('summary').click()
    expect(page.locator('body')).to_have_attribute('data-month-held','yes')
    page.evaluate("location.hash='history'")
    expect(page.get_by_role('heading',name='收藏每一段真實。',exact=True)).to_be_visible()
    for route in held:route.fulfill(status=200,content_type='application/json',body=json.dumps(data))
    assert page.locator('.hs-grid').count()==0


def test_calendar_record_uses_goal_timezone_and_requires_actual_time(page):
    from datetime import datetime,timezone
    goal,headers,today=seed(page,False)
    assert page.request.put(BASE+'/api/profile',headers=headers,data={'name':'時區測試者','bio':'固定目標日期','timezone':'America/Los_Angeles'}).ok
    page.reload();box=page.locator('.habit-schedule').first;box.locator('summary').click()
    expect(box.locator('.hs-grid')).to_be_visible()
    box.locator('[data-date="'+today+'"]').click()
    box.get_by_role('button',name='記錄這次投入').click()
    expect(page.locator('#calendar-date')).to_have_value(today)
    expect(page.locator('#calendar-time')).to_have_value('')
    page.locator('#raw-text').fill('這是從月曆帶入的真實記錄測試。')
    page.get_by_role('button',name='先存草稿',exact=True).click()
    assert page.request.get(BASE+'/api/state').json()['drafts']==[]
    page.locator('#calendar-time').fill('00:01')
    page.get_by_role('button',name='先存草稿',exact=True).click()
    expect(page.get_by_role('heading',name='收藏每一段真實。',exact=True)).to_be_visible()
    state=page.request.get(BASE+'/api/state').json()
    assert len(state['drafts'])==1 and state['experiences']==[]
    assert state['drafts'][0]['occurred_at']==datetime.fromisoformat(today+'T00:01:00+08:00').astimezone(timezone.utc).isoformat()
    assert state['drafts'][0]['contributions']==[]
    assert state['rewards']['total']==0


def test_long_schedule_month_switch_does_not_grow_dom_or_history(page):
    goal,headers,today=seed(page,False)
    start=date.fromisoformat(today)
    dates=[str(start+timedelta(days=i)) for i in range(369)]
    g=page.request.get(BASE+'/api/goals/'+goal['id']).json()
    rows=[{'action_id':a['id'],'dates':dates,'weekdays':[],'cycle':'month'} for a in g['actions']]
    result=page.request.post(BASE+'/api/goals/'+g['id']+'/review',headers=headers,data={'request_id':'long-months','expected_revision':g['revision'],'decision':'extend','confirmed':True,'deadline':str(start+timedelta(days=400)),'schedules':rows})
    assert result.ok,result.text()
    page.reload();box=page.locator('.habit-schedule').first;box.locator('summary').click()
    expect(box.locator('.hs-grid')).to_be_visible()
    before=page.request.get(BASE+'/api/state').json()
    history_length=page.evaluate('history.length')
    for _ in range(6):
        month=box.locator('.hs-month b').inner_text()
        box.get_by_role('button',name='閱讀下一月').click()
        expect(box.locator('.hs-month b')).not_to_have_text(month)
        expect(box.get_by_role('button',name='閱讀下一月')).to_be_focused()
        assert box.locator('.hs-grid button').count()<=31
        assert len(box.inner_text())<2000
    assert page.evaluate('history.length')==history_length
    assert page.request.get(BASE+'/api/state').json()==before
