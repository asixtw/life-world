"""Main Web 本機實際建置的世界房間、聲音入口及共用播放器驗收。"""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('width',[390,1440])
def test_world_room_and_sound_comparison_in_main_web(width):
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':width,'height':1000})
        page.goto('http://127.0.0.1:8211/?ui-review=components&flow=world')
        expect(page.locator('.world-room--v1')).to_be_visible()
        assert page.locator('.world-room--v1 img').first.evaluate('e=>e.complete&&e.naturalWidth>0')
        assert page.locator('.world-room__lumi').evaluate('e=>e.complete&&e.naturalWidth>0')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.locator('[aria-label="房間版本"]').select_option('legacy')
        expect(page.locator('.world-room--v1')).to_have_count(0)
        page.locator('[aria-label="房間版本"]').select_option('new')
        page.locator('.world-room-wrap').screenshot(path=str(ROOT/f'docs/design-language-v1/evidence/room-audio-v1/{width}-main-web-room.png'))
        frame=page.frame_locator('[title="新版聲音候選與新舊試聽"]')
        expect(frame.locator('[data-audio-new]')).to_have_count(12)
        expect(frame.locator('#room')).to_be_hidden()
        frame.locator('#compare-sound').check()
        frame.locator('[data-audio-new="experience-confirmed"]').click()
        expect(frame.locator('#compare-status')).to_contain_text('新版')
        page.get_by_label('Quiet',exact=True).check()
        expect(frame.locator('#quiet')).to_be_checked()
        frame.locator('#compare-sound').check()
        expect(frame.locator('[data-audio-new="experience-confirmed"]')).to_be_disabled()
        browser.close()
