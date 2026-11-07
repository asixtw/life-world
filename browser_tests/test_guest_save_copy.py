"""實際瀏覽器執行保存提示；缺少 GIS 時不得承諾帳號保存。"""
from pathlib import Path
import re
from playwright.sync_api import sync_playwright
import pytest

@pytest.mark.parametrize('google', [False, True])
def test_guest_notice_respects_enabled_login(google):
    source = Path('app/static/app.js').read_text()
    fn = re.search(r'function guestSaveNotice\(\).*?\n}', source, re.S).group()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content('<div id="notice"></div>')
        page.evaluate('window.state={me:{status:"guest"},capabilities:{google_login_available:'+str(google).lower()+'}}; window.$=s=>document.querySelector(s);'+fn+';guestSaveNotice();')
        text = page.locator('#notice').inner_text()
        assert '清除Cookie或工作階段到期後可能無法取回' in text
        if google:
            assert '使用 Google 帳號保存世界' in text
        else:
            assert '目前未開放 Google 保存世界' in text
            assert '登入功能可協助保存' not in text
        browser.close()

@pytest.mark.parametrize('fail', [False, True])
def test_loading_finishes_on_success_and_failure(fail):
    """執行正式 render 與 finally；只替代頁面查詢，不聲稱後端或 AI 實測。"""
    source = Path('app/static/app.js').read_text()
    render = source[source.index('async function render('):source.index('function dialog(')]
    lock = source[source.index('function lockRenderControls('):source.index('function toast(')]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content('<main id="app"></main><div id="app-loading" hidden>正在載入，請稍候…</div>')
        page.evaluate('''() => {window.$=s=>document.querySelector(s);
          window.state={me:{lumi_hatched:true},route:'world'};
          window.renderSequence=0;window.renderControls=new Map();window.loadingTimer=null;
          window.navigation=()=>{};window.refresh=async()=>{};window.MediaUI={leave:()=>{}};window.ScheduleUI={mount:()=>{},leave:()=>{}};
          window.PeopleUI={restore:()=>{},remember:()=>{}};window.ConnectionsUI={restore:()=>{},remember:()=>{},ensureOwner:()=>{}};
          window.worldView=async()=>{await new Promise(r=>setTimeout(r,600));
          '''+('throw new Error("synthetic query failure");' if fail else 'return "<p>載入完成</p>";')+'};'+lock+render+';window.render=render;}')
        # 指定world路由，避免空白hash走welcome。
        page.evaluate('history.replaceState(null,"","#world");window.pending=render({localGoalEdit:true}).catch(()=>{});void 0;')
        page.wait_for_function('document.querySelector("#app-loading").hidden===false',timeout=3000)
        page.evaluate('window.pending')
        assert page.locator('#app-loading').is_hidden()
        assert page.locator('#app').get_attribute('aria-busy') == 'false'
        browser.close()
