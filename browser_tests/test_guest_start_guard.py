"""只驗證正式Guest入口控制函式；HTTP與PG另由G01–G10實跑。"""
from pathlib import Path
from playwright.sync_api import sync_playwright


def test_duplicate_guest_clicks_share_one_request_and_can_retry():
    source=Path('app/static/app.js').read_text()
    start=source.index('function startGuest()')
    helper=source[start:source.index('// Guest入口控制結束',start)]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        page.evaluate('''() => {window.guestStartPending=null;window.state={};window.calls=0;
          window.api=async()=>{calls++;await new Promise(r=>setTimeout(r,30));return {owner_id:'synthetic',csrf_token:'synthetic'};};'''+helper+'''
          window.startGuest=startGuest;}''')
        page.evaluate('Promise.all([startGuest(),startGuest()])')
        assert page.evaluate('calls')==1
        assert page.evaluate('state.me.owner_id')=='synthetic'
        assert page.evaluate('guestStartPending') is None
        page.evaluate("window.api=async()=>{throw new Error('synthetic_network_failure')};window.failure=startGuest().catch(()=>{});")
        page.evaluate('failure')
        assert page.evaluate('guestStartPending') is None
        page.evaluate("window.api=async()=>({owner_id:'same-world',csrf_token:'new'});startGuest()")
        assert page.evaluate('state.me.owner_id')=='same-world'
        page.evaluate('''async () => {
          state.me=null;const original=window.setTimeout;
          window.setTimeout=(fn,ms)=>original(fn,ms===8000?10:ms);
          window.api=(url,options)=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError'))));
          try {await startGuest();} catch(error) {window.timeoutMessage=error.message;}
          window.setTimeout=original;
        }''')
        assert '尚未確認' in page.evaluate('timeoutMessage')
        assert page.evaluate('state.me') is None
        assert page.evaluate('guestStartPending') is None
        browser.close()
