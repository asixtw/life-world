"""只連 Main Web 本機建置輸出；驗證 React 入口與共用靜態元件庫可操作。"""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright,expect

ART=Path(__file__).resolve().parents[3]/'docs/design-language-v1/evidence'


@pytest.mark.parametrize('width',[320,390,768,1440])
def test_main_web_design_language_entry_and_shared_gallery(width):
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch()
        context=browser.new_context(viewport={'width':width,'height':1000})
        page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8211/')
        expect(page.locator('.hero-illustration')).to_be_visible()
        if width<=390:
            assert page.locator('.hero>div').first.bounding_box()['width']>=width-120
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        ART.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(ART/f'{width}-main-web-overview.png'),full_page=True)
        page.locator('button:visible').filter(has_text='設計語言').click()
        frame=page.frame_locator('.design-language-frame')
        expect(frame.locator('.dl-asset-card')).to_have_count(20)
        frame.locator('#asset-search').fill('listening')
        expect(frame.locator('.dl-asset-card')).to_have_count(1)
        frame.locator('[data-asset]').click()
        expect(frame.locator('#asset-dialog')).to_be_visible()
        page.keyboard.press('Escape')
        frame.locator('#reduced').check()
        for _ in range(3):frame.locator('[data-birth-egg]').click()
        expect(frame.locator('[data-birth-enter]')).to_be_visible()
        assert frame.locator('body').evaluate('e=>e.scrollWidth<=e.ownerDocument.defaultView.innerWidth')
        page.screenshot(path=str(ART/f'{width}-main-web-design-language.png'),full_page=True)
        assert errors==[]
        context.close();browser.close()
