"""首頁摘要與主流程驗證；不使用正式帳號或資料。"""
import pytest
from playwright.sync_api import expect
from test_dashboard import seed
from test_journey import page, BASE

@pytest.mark.parametrize('width',[320,390,1440])
def test_home_rows_and_context(page,width,tmp_path):
    page.set_viewport_size({'width':width,'height':900})
    goal,_,_=seed(page)
    page.goto(BASE+'/#world')
    rows=page.locator('.home-habit-row')
    expect(rows).to_have_count(3)
    expect(rows.first).to_contain_text('已確認 1.25 / 1 次')
    expect(rows.first).to_contain_text('今天有安排')
    expect(page.get_by_text('累積積分 · 開發規則',exact=True)).to_have_count(0)
    expect(page.get_by_label('繼續整理作品',exact=True)).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(tmp_path/f'home-{width}.png'),full_page=True)
    page.get_by_role('link',name='記錄新經歷',exact=True).click()
    expect(page.locator('#goal-id')).to_have_value(goal['id'])
    page.goto(BASE+'/#world')
    rows.first.click()
    expect(page.get_by_role('region',name='目標儀表板')).to_be_visible()

def test_home_error_keeps_lumi_and_retry(page):
    seed(page,False)
    page.route('**/api/state',lambda r:r.abort())
    page.goto(BASE+'/#world')
    expect(page.get_by_text('暫時無法讀取最新資料，請重試。')).to_be_visible()
    expect(page.locator('.home-lumi')).to_be_visible()
    expect(page.locator('.home-habit-row')).to_have_count(0)
    page.unroute('**/api/state')
    page.get_by_role('button',name='重新讀取',exact=True).click()
    expect(page.locator('.home-habit-row')).to_have_count(3)

from test_flow_wireframe import wireframe_url

@pytest.mark.parametrize('width',[390,1440])
def test_prototype_home_uses_shared_rows(page,wireframe_url,width,tmp_path):
    page.set_viewport_size({'width':width,'height':900})
    page.goto(wireframe_url)
    page.get_by_role('button',name='載入虛構示例',exact=True).click()
    expect(page.locator('.home-habit-row')).to_have_count(3)
    expect(page.get_by_text('虛構示例資料 · 排程只代表打算做')).to_be_visible()
    page.screenshot(path=str(tmp_path/f'prototype-home-{width}.png'),full_page=True)
    page.locator('.home-habit-row').first.click()
    expect(page.get_by_role('heading',name='三個重要習慣',exact=True)).to_be_visible()

@pytest.mark.parametrize('variant,label',[('awaiting_review','查看並回顧'),('needs_setup','補齊目標設定'),('empty','建立新目標'),('incomplete','三個習慣資料尚未完整，請進入目標補設定。')])
def test_home_degraded_states_are_read_only(page,variant,label):
    seed(page,False)
    writes=[]
    def snapshot(route):
        response=route.fetch()
        body=response.json()
        if variant=='empty':body['goals']=[]
        elif variant=='incomplete':body['goals'][0]['actions']=body['goals'][0]['actions'][:2]
        else:body['goals'][0]['status']=variant
        route.fulfill(response=response,json=body)
    page.route('**/api/state',snapshot)
    page.on('request',lambda r:writes.append(r.url) if '/api/' in r.url and r.method not in ['GET','HEAD'] else None)
    page.goto(BASE+'/#world')
    expect(page.get_by_text(label,exact=True)).to_be_visible()
    if variant in ['empty','incomplete']:expect(page.locator('.home-habit-row')).to_have_count(0)
    assert writes==[]
