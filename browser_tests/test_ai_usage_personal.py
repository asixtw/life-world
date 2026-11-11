"""本人用量畫面Chromium契約；metadata為明示fixture，不代表真AI或帳單驗收。"""
import pytest
from playwright.sync_api import expect
from test_journey import page,BASE
from test_integration_person_details import seed,ART

@pytest.mark.parametrize('width',[390,1440])
def test_personal_ai_usage_labels_and_no_global_fields(page,width):
    page.set_viewport_size({'width':width,'height':950});seed(page)
    def capabilities(route):
        response=route.fetch();data=response.json();data['ai_available']=True
        route.fulfill(response=response,json=data)
    page.route('**/api/capabilities',capabilities)
    usage={'calls':2,'reserved_microusd':1000000,'input_tokens':30,'output_tokens':40,'unknown_cost_calls':2,'reported_cost_microusd':None,'actual_invoice_cost_microusd':None,'receipts':[{'request_id':'synthetic-owner-receipt','created_at':'2026-11-11T00:00:00Z','status':'failed','reserved_microusd':500000,'cost_microusd':None}]}
    page.route('**/api/ai/usage',lambda route:route.fulfill(json=usage))
    page.goto(BASE+'/#world');page.reload();page.locator('#account-button').click()
    page.get_by_role('button',name='AI 額度與收據',exact=True).click()
    dialog=page.locator('#account-dialog');expect(dialog).to_contain_text('我的 AI 用量與收據')
    expect(dialog).to_contain_text('本帳號共 2 次預留')
    expect(dialog).to_contain_text('不是實際帳單費用')
    for forbidden in ['全域','剩餘可預留','歷史未知費用預留']:expect(dialog).not_to_contain_text(forbidden)
    dialog.locator('summary').click();expect(dialog).to_contain_text('synthetic-owner-receipt')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    ART.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(ART/f'{width}-personal-ai-usage.png'),full_page=True)


def test_delayed_usage_response_is_discarded_after_owner_switch(page):
    seed(page)
    def capabilities(route):
        r=route.fetch();data=r.json();data['ai_available']=True;route.fulfill(response=r,json=data)
    page.route('**/api/capabilities',capabilities)
    pending=[]
    page.route('**/api/ai/usage',lambda route:pending.append(route))
    page.goto(BASE+'/#world');page.reload();page.locator('#account-button').click()
    page.get_by_role('button',name='AI 額度與收據',exact=True).click()
    # 只驗證延遲畫面回應的Owner閘，Server身分隔離由SQLite/PG API測試驗證。
    page.wait_for_function('document.querySelector("[data-action=ai-usage]").disabled')
    assert pending
    page.evaluate("state.me={...state.me,owner_id:'synthetic-switched-owner'}")
    pending[0].fulfill(json={'calls':99,'reserved_microusd':999,'input_tokens':0,'output_tokens':0,'unknown_cost_calls':0,'receipts':[]})
    expect(page.locator('[data-action=ai-usage]')).to_be_enabled()
    expect(page.locator('#account-dialog')).not_to_contain_text('我的 AI 用量與收據')
