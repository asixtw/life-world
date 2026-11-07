"""孵化只改前端呈現；隔離頁測試三次輸入與動畫鎖。"""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('mobile,reduced', [(False,False),(True,False),(False,True),(True,True)])
def test_three_deliberate_hatch_inputs(mobile, reduced):
    """鍵盤與觸控都不能連點跨過階段；第三下才顯示 Lumi。"""
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width':390 if mobile else 1280,'height':844},
            has_touch=mobile, reduced_motion='reduce' if reduced else 'no-preference')
        page=context.new_page()
        page.set_content('<main id="app"></main>')
        page.add_style_tag(path=str(ROOT/'app/static/birth.css'))
        page.add_script_tag(path=str(ROOT/'app/static/birth.js'))
        page.evaluate("document.querySelector('#app').innerHTML=BirthUI.view('<div>Lumi 現有角色</div>'); BirthUI.mount()")
        egg=page.locator('[data-birth-egg]')
        expect(egg).to_have_accessible_name('輕觸目標蛋，出現細裂痕')
        enter=page.get_by_role('link',name='進入我的世界')
        expect(enter).to_be_hidden()
        for stage in range(1,4):
            if mobile: egg.tap()
            else: egg.focus(); egg.press('Enter')
            expect(egg).to_be_disabled()
            # 動畫中重送 click 不得跳到下一階段。
            page.evaluate("document.querySelector('[data-birth-egg]').click()")
            expect(page.locator('[data-birth]')).to_have_attribute('data-stage',str(stage))
            if stage<3:
                expect(enter).to_be_hidden()
                expect(egg).to_be_enabled(timeout=3000)
            else:
                expect(enter).to_be_visible(timeout=3000)
                expect(page.locator('[data-birth-lumi]')).to_be_visible()
        context.close(); browser.close()
