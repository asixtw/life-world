"""LW-PWA-001 基準／候選共用量測；只連線隔離合成資料。"""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,os,time
import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from app.main import create_app
from app.runtime import RuntimeSettings
from app.config import DemoPolicy
from conftest import onboard,register,guest,draft
from lw_pwa_support import running

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('LW_PWA_EVIDENCE_DIR',ROOT/'docs/pwa/LW-PWA-001/2026-11-18/candidate'))
SIZES=[(320,568),(390,844),(768,1024),(1440,900)]
CLS_INIT=r'''(() => {
 const state={supported:PerformanceObserver.supportedEntryTypes.includes('layout-shift'),entries:[]};window.__lwBaselineCLS=state;
 const selector=n=>n?(n.id?'#'+n.id:n.tagName?.toLowerCase()+'.'+[...n.classList||[]].slice(0,2).join('.')):'unknown';
 if(state.supported)new PerformanceObserver(list=>{for(const e of list.getEntries())state.entries.push({value:e.value,time:e.startTime,recent:e.hadRecentInput,sources:(e.sources||[]).map(s=>({node:selector(s.node),before:s.previousRect.toJSON(),after:s.currentRect.toJSON()}))});}).observe({type:'layout-shift',buffered:true});
})();'''
GEOMETRY=r'''() => {
 const visible=e=>!!e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
 const name=e=>e.id?'#'+e.id:e.tagName.toLowerCase()+'.'+[...e.classList].slice(0,2).join('.');
 const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,right:r.right};};
 const width=document.documentElement.clientWidth;
 return {width:innerWidth,height:innerHeight,layout_client_width:width,document_width:document.documentElement.scrollWidth,overflow_px:Math.max(0,document.documentElement.scrollWidth-width),
   visual_viewport:visualViewport?{width:visualViewport.width,height:visualViewport.height,offset_top:visualViewport.offsetTop,scale:visualViewport.scale}:null,
   standalone:matchMedia('(display-mode: standalone)').matches,coarse_pointer:matchMedia('(pointer: coarse)').matches,
   topbar:document.querySelector('.topbar')?rect(document.querySelector('.topbar')):null,
   dashboard:document.querySelector('.dashboard')?{...rect(document.querySelector('.dashboard')),columns:getComputedStyle(document.querySelector('.dashboard')).gridTemplateColumns,parent_width:document.querySelector('.dashboard').parentElement.clientWidth}:null,
   nowrap_links:[...document.querySelectorAll('a')].filter(e=>visible(e)&&getComputedStyle(e).whiteSpace==='nowrap'&&e.getBoundingClientRect().width>width).map(e=>({node:name(e),width:e.getBoundingClientRect().width,text_length:e.textContent.length,white_space:getComputedStyle(e).whiteSpace})),
   nav:document.querySelector('.sidebar')?{...rect(document.querySelector('.sidebar')),display:getComputedStyle(document.querySelector('.sidebar')).display}:null,
   horizontal_offenders:[...document.body.querySelectorAll('*')].filter(e=>visible(e)&&e.getBoundingClientRect().width>0&&(e.getBoundingClientRect().right>width+1||e.getBoundingClientRect().left< -1)).slice(0,14).map(e=>({node:name(e),...rect(e)})),
   images_without_html_dimensions:[...document.images].filter(visible).filter(e=>!e.hasAttribute('width')||!e.hasAttribute('height')).map(e=>({node:name(e),...rect(e),css_aspect_ratio:getComputedStyle(e).aspectRatio,position:getComputedStyle(e).position})).slice(0,12)};
}'''


def cls(page):
    data=page.evaluate('window.__lwBaselineCLS')
    if not data or not data['supported']:return {'status':'NOT RUN','reason':'Layout Instability API unavailable'}
    total=best=0;first=last=None
    entries=[e for e in data['entries'] if not e['recent']]
    for e in entries:
        if last is None or e['time']-last>=1000 or e['time']-first>=5000:total=e['value'];first=e['time']
        else:total+=e['value']
        best=max(best,total);last=e['time']
    return {'status':'MEASURED','value':round(best,6),'entries':entries,'window':'document navigation to settled + 750ms; not field p75'}


def reach(page,selector):
    matches=page.locator(selector)
    target=next((matches.nth(i) for i in range(matches.count()) if matches.nth(i).is_visible()),None)
    if target is None:return {'selector':selector,'status':'ABSENT_OR_HIDDEN'}
    target.evaluate("e=>e.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'})")
    result=target.evaluate('''e=>{const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2,hit=document.elementFromPoint(x,y);return {rect:{x:r.x,y:r.y,width:r.width,height:r.height},reachable:x>=0&&y>=0&&x<innerWidth&&y<innerHeight&&!!hit&&(hit===e||e.contains(hit)),blocked_by:hit?.id||hit?.tagName,disabled:e.disabled===true};}''')
    return {'selector':selector,'status':'MEASURED',**result}


@pytest.mark.parametrize('width,height',SIZES)
def test_lw_pwa_baseline(tmp_path,monkeypatch,width,height):
    # 僅進程內停用外部服務，沒有修改 .env 或任何正式設定。
    monkeypatch.setenv('LIFEWORLD_AI_CALLS_APPROVED','false')
    monkeypatch.delenv('LIFEWORLD_AI_API_KEY',raising=False)
    monkeypatch.delenv('LIFEWORLD_TEST_ACCOUNT_SEED',raising=False)
    app=create_app(tmp_path/'synthetic',settings=RuntimeSettings(backend='sqlite',auth_source_mode='direct'),policy=DemoPolicy(),clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))
    OUT.mkdir(parents=True,exist_ok=True)
    records=[];errors=[];external=[];problems=[]
    with TestClient(app) as client:
        _,goal=onboard(client);register(client)
        person=client.post('/api/people',json={'name':'合成人物小安','role':'朋友'}).json()
        assert 'id' in person,person
        d=draft(client,goal,raw_text=('今天與小安一起閱讀，核對了彼此分享的內容。\n'*24),contributions=[],story={'participants':[{'person_id':person['id'],'interacted':True}]})
        cookie=client.cookies.get('lw_session')
        with TestClient(app) as fresh:
            new=guest(fresh)
            assert fresh.put('/api/profile',json={'name':'合成新訪客','bio':'隔離測試','timezone':'Asia/Taipei'}).status_code==200
            fresh_cookie=fresh.cookies.get('lw_session')
        with running(app) as base,sync_playwright() as pw:
            browser=pw.chromium.launch(channel='chrome',headless=True)
            context=browser.new_context(viewport={'width':width,'height':height},is_mobile=width<=768,has_touch=width<=768,reduced_motion='reduce')
            context.add_cookies([{'name':'lw_session','value':cookie,'url':base}])
            context.add_init_script(CLS_INIT)
            page=context.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('dialog',lambda d:d.accept())
            def route_read(route):
                if not route.request.url.startswith(base):external.append(route.request.url);route.abort();return
                if route.request.method=='GET' and '/api/' in route.request.url:time.sleep(.12)
                route.continue_()
            page.route('**/*',route_read)
            cdp=context.new_cdp_session(page);cdp.send('Network.setCacheDisabled',{'cacheDisabled':True})
            version=browser.version
            def settled():
                page.wait_for_function("() => document.querySelector('#app')?.getAttribute('aria-busy')!=='true'&&document.querySelector('#app')?.innerText!=='正在打開你的世界…'")
                page.wait_for_timeout(750)
            def measure(name,targets=(),picture=False,cold=False):
                row={'screen':name,'viewport':[width,height],'geometry':page.evaluate(GEOMETRY),'cls':cls(page) if cold else {'status':'NOT APPLICABLE','reason':'user-driven state; do not label as initial-load CLS'},'actions':[reach(page,x) for x in targets]}
                if row['geometry']['overflow_px']>1:row.setdefault('defects',[]).append('horizontal_overflow')
                if any(x.get('status')=='MEASURED' and not x['reachable'] for x in row['actions']):row.setdefault('defects',[]).append('action_occluded_or_outside_viewport')
                if row['cls'].get('value',0)>.1:row.setdefault('defects',[]).append('initial_cls_above_target')
                if picture or row.get('defects'):
                    page.evaluate("window.scrollTo({left:0,top:0,behavior:'instant'})");page.wait_for_function('() => scrollY < 1 && scrollX < 1');path=OUT/f'{width}x{height}-{name}.png';page.screenshot(path=str(path));row['screenshot']=path.name
                records.append(row);(OUT/f'{width}x{height}.json').write_text(json.dumps({'status':'INCOMPLETE','viewport':[width,height],'records':records},ensure_ascii=False,indent=2)+'\n');print(json.dumps({'viewport':[width,height],'screen':name,'overflow':row['geometry']['overflow_px'],'cls':row['cls'].get('value'),'defects':row.get('defects',[])},ensure_ascii=False),flush=True)
                return row
            def go(name,route,ready,targets=(),picture=False):
                page.goto(base+'/?lw_baseline='+name+route,wait_until='domcontentloaded');page.locator(ready).wait_for(state='visible');settled();return measure(name,targets,picture,cold=True)
            # 以有效 Session 重新載入路由；不是把 Demo 內容塞入 DOM。
            go('world','#world','.home-lumi',('a[href^="#record"]',),True)
            go('goal','#goal/'+goal['id'],'#goal-completion',('#complete-form button',))
            go('person','#person/'+person['id'],'#person-profile',('#person-profile a.primary',))
            go('birth','#birth','[data-birth-egg]',('[data-birth-egg]',),width==390)
            go('step1','#record','[name=raw_text]',('[data-experience-next]',))
            page.locator('[name=raw_text]').fill('合成原文：短視窗檢查時這段輸入不可遺失。')
            page.locator('[data-experience-next]').click();page.locator('[data-experience-step="2"]').wait_for(state='visible')
            measure('step2',('[data-experience-next]',))
            page.locator('[data-experience-next]').click();page.locator('[data-experience-step="3"]').wait_for(state='visible')
            measure('step3',('[data-experience-review]','[data-experience-prev]'),True)
            if width==390:
                page.set_viewport_size({'width':390,'height':400})
                measure('step3-short-viewport',('[data-experience-review]','[data-experience-prev]'),True)
                assert page.locator('[name=raw_text]').input_value()=='合成原文：短視窗檢查時這段輸入不可遺失。'
                page.set_viewport_size({'width':width,'height':height})
            # 來源與參與者由草稿 API 正式回讀，不需要真正 Confirm 才檢視排版。
            go('step4','#review/'+d['id'],'#review-form',('#review-form button.primary',))
            page.locator('[data-experience-preview]').first.click();page.locator('#experience-person-preview').wait_for(state='visible')
            page.locator('#experience-person-preview details summary').first.click()
            measure('person-modal',('#experience-person-preview .experience-preview-footer button',),True)
            if width==390:
                page.set_viewport_size({'width':390,'height':400})
                measure('person-modal-short-viewport',('#experience-person-preview .experience-preview-footer button',),True)
                page.set_viewport_size({'width':width,'height':height})
            page.locator('#experience-person-preview .experience-preview-head button').click()
            # 新訪客目標設定使用另一個真實 Guest Session，避免 active goal 阻擋頁誤當設定表單。
            context.clear_cookies();context.add_cookies([{'name':'lw_session','value':fresh_cookie,'url':base}])
            go('goal-new','#goal-new','#goal-form',('#goal-form button[type=submit]',))
            context.clear_cookies()
            go('welcome','#welcome','#app .welcome',('[data-action=guest]',),width==390)
            page.locator('.intro-menu summary').click();page.locator('[data-pwa-open]').first.click()
            measure('install-modal',('#pwa-install-dialog .pwa-footer .primary',),width==390)
            manifest=page.request.get(base+'/static/mobile-manifest-v1.webmanifest')
            assert manifest.status==200 and manifest.json()['display']=='standalone'
            assert all(page.request.get(base+i['src']).status==200 for i in manifest.json()['icons'])
            context.close();browser.close()
    for row in records:
        problems.extend({'screen':row['screen'],'kind':x} for x in row.get('defects',[]))
    result={'viewport':[width,height],'engine':'Chrome '+version,'db':'fresh isolated SQLite; synthetic clock 2026-10-27','api_latency':'120ms per read interception; cache disabled; normal CSS/JS unchanged','records':records,'problems':problems,'javascript_errors':errors,'external_requests_blocked':external,'webkit':'NOT RUN: executable absent','real_keyboard_safe_area_installation':'NOT RUN','rotation':'OUT OF SCOPE'}
    (OUT/f'{width}x{height}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    assert not errors,errors
    assert not external,external
    assert not problems,json.dumps(problems,ensure_ascii=False)


@pytest.mark.parametrize('width,height',SIZES)
def test_lw_pwa_entry_action_supplement(tmp_path,monkeypatch,width,height):
    """補齊首輪錯選隱藏／帶參數連結的8項探測，不重跑CLS及其餘頁面。"""
    monkeypatch.setenv('LIFEWORLD_AI_CALLS_APPROVED','false')
    monkeypatch.delenv('LIFEWORLD_AI_API_KEY',raising=False)
    monkeypatch.delenv('LIFEWORLD_TEST_ACCOUNT_SEED',raising=False)
    app=create_app(tmp_path/'entry-synthetic',settings=RuntimeSettings(backend='sqlite',auth_source_mode='direct'),policy=DemoPolicy(),clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))
    rows=[]
    with TestClient(app) as client:
        _,goal=onboard(client);register(client)
        draft(client,goal,raw_text='今天與小安一起閱讀，核對了彼此分享的內容。\n'*24,contributions=[])
        with running(app) as base,sync_playwright() as pw:
            browser=pw.chromium.launch(channel='chrome',headless=True)
            context=browser.new_context(viewport={'width':width,'height':height},is_mobile=width<=768,has_touch=width<=768,reduced_motion='reduce')
            context.add_cookies([{'name':'lw_session','value':client.cookies.get('lw_session'),'url':base}]);page=context.new_page()
            for name,route,ready,selector in [('world','#world','.home-lumi','a[href^="#record"]'),('goal','#goal/'+goal['id'],'#goal-completion',None),('welcome','#welcome','#app .welcome','[data-action=guest]')]:
                if name=='welcome':context.clear_cookies()
                page.goto(base+'/?entry_probe='+name+route,wait_until='domcontentloaded');page.locator(ready).wait_for(state='visible');page.wait_for_timeout(300)
                # 入口頁首畫面先拍，再做會改變捲動位置的可達性檢查。
                page.screenshot(path=str(OUT/f'{width}x{height}-{name}-initial.png'))
                if selector:
                    result=reach(page,selector);rows.append({'screen':name,**result})
            context.close();browser.close()
    (OUT/f'{width}x{height}-entries.json').write_text(json.dumps({'viewport':[width,height],'actions':rows,'reason':'correct hidden/parameterized selector probes; no CLS re-measurement'},ensure_ascii=False,indent=2)+'\n')
    assert all(r['status']=='MEASURED' and r['reachable'] for r in rows),rows
