"""正式 App／原型的儀表板操作，不用展示截圖代替數據斷言。"""
from datetime import date, timedelta
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_journey import BASE, page
from test_flow_wireframe import wireframe_url


def seed(page, with_record=True):
    page.goto(BASE)
    me=page.request.post(BASE+'/api/auth/guest').json()
    headers={'X-CSRF-Token':me['csrf_token']}
    assert page.request.put(BASE+'/api/profile',headers=headers,data={'name':'儀表測試者','bio':'真實投入','timezone':'Asia/Taipei'}).ok
    today=page.request.get(BASE+'/api/auth/me').json()['today']
    goal=page.request.post(BASE+'/api/goals',headers=headers,data={'request_id':'dashboard','title':'儀表板挑戰','outcome':'完成作品','deadline':str(date.fromisoformat(today)+timedelta(days=30)),'actions':[{'title':title,'unit':'次','dates':[today],'per_occurrence':'1','weekdays':[],'cycle':'month'} for title in ['閱讀','整理','分享']]}).json()
    if with_record:
        d=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data={'raw_text':'儀表板來源原文','occurred_at':today+'T00:00:00+08:00','goal_id':goal['id'],'contributions':[{'action_id':a['id'],'quantity':'1.25'} for a in goal['actions']]}).json()
        result=page.request.post(BASE+'/api/drafts/'+d['id']+'/confirm',headers=headers,data={'request_id':'confirm','expected_revision':d['revision'],'summary':'已確認的閱讀來源','contributions':d['contributions'],'tasks':['繼續整理作品']})
        assert result.ok, result.text()
    page.goto(BASE+'/#goal/'+goal['id'])
    page.reload()  # API準備帳號後，重新啟動頁面身分讀取。
    return goal,headers,today


@pytest.mark.parametrize('width',[390,1440])
def test_dashboard_sources_task_record_and_retry(page,width,tmp_path):
    page.set_viewport_size({'width':width,'height':844 if width==390 else 900})
    page.emulate_media(reduced_motion='reduce')
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    goal,headers,today=seed(page)
    panel=page.get_by_role('region',name='目標儀表板')
    expect(panel).to_be_visible()
    expect(panel.get_by_text('已確認投入：1.25 次',exact=True)).to_have_count(3)
    expect(panel.get_by_text('已安排 1 天',exact=True)).to_have_count(3)
    assert panel.locator('.dash-habits > article').count()==3
    assert panel.locator('.dash-week > .dash-day').count()==7
    assert panel.locator('.dash-day-sources > details').count()==1
    panel.get_by_role('button',name='查看 '+today+' 的 1 筆經歷').focus()
    page.keyboard.press('Enter')
    expect(panel.get_by_text('儀表板來源原文',exact=True)).to_be_visible()
    page.screenshot(path=str(tmp_path/('dashboard-sources-'+str(width)+'.png')),full_page=True)
    panel.get_by_label('繼續整理作品',exact=True).check()
    expect(panel.get_by_text('目前沒有未完成的後續任務。')).to_be_visible()
    panel.get_by_role('link',name='記錄閱讀',exact=True).click()
    expect(page.locator('#goal-id')).to_have_value(goal['id'])
    expect(page.get_by_text('本次記錄：閱讀；請自行填寫實際投入量。')).to_be_visible()
    page.goto(BASE+'/#goal/'+goal['id'])
    expect(panel).to_be_visible()
    page.route('**/api/goals/*/dashboard',lambda route:route.abort())
    page.reload()
    # 重載會清除記憶體快照；沒有資料時不能顯示零筆假圖。
    expect(page.get_by_text('部分資料暫時無法讀取；已讀取的目標仍保留，缺值不是零。')).to_be_visible()
    page.unroute('**/api/goals/*/dashboard')
    page.get_by_role('button',name='重新讀取進度').click()
    expect(panel).to_be_visible()
    expect(page.get_by_text('部分資料暫時無法讀取；已讀取的目標仍保留，缺值不是零。')).to_have_count(0)
    page.route('**/api/goals/*/dashboard',lambda route:route.abort())
    page.evaluate('render()')
    expect(panel.get_by_text('暫時無法讀取最新進度，以下為上次資料，可能非最新。')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(tmp_path/('dashboard-'+str(width)+'.png')),full_page=True)
    assert errors==[]


def test_prototype_dashboard_uses_confirmed_sources(page,wireframe_url):
    page.goto(wireframe_url)
    page.evaluate("""() => {const day=dateNow();s.name='虛構測試';s.goal={id:'dash',title:'示例挑戰',outcome:'作品',start:day,deadline:shift(day,20),status:'進行中',actions:['閱讀','整理','分享'].map((title,i)=>({id:'a'+i,title,quantity:'1',unit:'次',dates:[day]}))};s.records=[{id:'r',goalId:'dash',actionId:'a0',quantity:'0.5',occurred:day+'T10:00',summary:'已採計故事',contribution:true},{id:'pending',goalId:'dash',actionId:'a0',quantity:'8',occurred:day+'T10:00',summary:'待核對故事',pending:true}];s.route='goal';save();render();}""")
    panel=page.get_by_role('region',name='目標儀表板')
    expect(panel.get_by_text('已確認投入：0.5 次',exact=True)).to_be_visible()
    expect(panel.get_by_text('1 筆已採計經歷',exact=False)).to_have_count(1)
    panel.locator('details').last.locator('summary').click()
    expect(panel.get_by_text('已採計故事',exact=False)).to_be_visible()
    expect(panel.get_by_text('待核對故事',exact=False)).to_have_count(0)


def test_dashboard_late_response_and_expired_session(page):
    import json
    goal,headers,today=seed(page)
    expect(page.get_by_role('region',name='目標儀表板')).to_be_visible()
    data=page.request.get(BASE+'/api/goals/'+goal['id']+'/dashboard').json()
    held=[]
    page.route('**/api/goals/*/dashboard',lambda route:(held.append(route),page.evaluate("document.body.dataset.dashHeld='yes'")))
    page.evaluate('() => {void render();}')
    expect(page.locator('body')).to_have_attribute('data-dash-held','yes')
    assert len(held)==1
    page.evaluate("location.hash='history'")
    expect(page.get_by_role('heading',name='收藏每一段真實。',exact=True)).to_be_visible()
    held[0].fulfill(status=200,content_type='application/json',body=json.dumps(data))
    expect(page.get_by_role('region',name='目標儀表板')).to_have_count(0)
    page.unroute('**/api/goals/*/dashboard')
    assert page.request.post(BASE+'/api/auth/logout',headers=headers).ok
    page.goto(BASE+'/#goal/'+goal['id'])
    expect(page.get_by_role('button',name='不用註冊，先開始',exact=False)).to_be_visible()
    expect(page.get_by_role('region',name='目標儀表板')).to_have_count(0)


@pytest.mark.parametrize('width',[320,390,1440])
def test_goal_detail_order_long_schedule_and_zero_sources(page,width,tmp_path):
    page.set_viewport_size({'width':width,'height':844 if width<768 else 900})
    goal,headers,today=seed(page,with_record=False)
    start=date.fromisoformat(today)
    dates=[str(start+timedelta(days=i)) for i in range(369)]
    current=page.request.get(BASE+'/api/goals/'+goal['id']).json()
    result=page.request.post(BASE+'/api/goals/'+goal['id']+'/review',headers=headers,data={'request_id':'long-schedule','expected_revision':current['revision'],'decision':'extend','confirmed':True,'deadline':str(start+timedelta(days=400)),'schedules':[{'action_id':a['id'],'dates':dates,'weekdays':[],'cycle':'month'} for a in current['actions']]})
    assert result.ok,result.text()
    page.reload()
    panel=page.get_by_role('region',name='目標儀表板')
    expect(panel.get_by_role('heading',name='儀表板挑戰',exact=True)).to_be_visible()
    expect(panel.get_by_text('已安排 369 天',exact=True)).to_have_count(3)
    expect(panel.get_by_text('已確認投入：0 次',exact=True)).to_have_count(3)
    assert panel.locator('.dash-habits > article').count()==3
    assert panel.locator('.dash-day-sources details').count()==0
    assert panel.locator('[data-dashboard-day]').count()==0
    assert page.locator('h1').count()==1
    positions=panel.locator('h1, #gd-overview, #gd-today, .dash-habits, #gd-week').evaluate_all('(nodes)=>nodes.map(n=>n.getBoundingClientRect().top)')
    assert positions==sorted(positions)
    assert not page.locator('#gd-schedule').evaluate('(e)=>e.open')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(tmp_path/('goal-detail-v02-'+str(width)+'.png')),full_page=True)
    # 字體放大時仍可換行，不截斷Goal或遮住操作。
    page.evaluate("document.documentElement.style.fontSize='200%'")
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
