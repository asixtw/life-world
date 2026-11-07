"""只驗證新增UI／偏好；傳輸明示替身，不宣稱真實模型或素材已核准。"""
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]


def test_audio_independent_switches_approval_gate_and_receipt_deduplication():
    with sync_playwright() as pw:
        browser=pw.chromium.launch();page=browser.new_page()
        page.route('https://synthetic.test/**',lambda route:route.fulfill(body='<details id="audio-preferences"></details>',content_type='text/html'))
        page.goto('https://synthetic.test/');page.evaluate('()=>{localStorage.clear();window.played=[];window.Audio=class{constructor(url){this.url=url}play(){played.push(this.url);return Promise.resolve()}pause(){}};}')
        page.add_script_tag(path=str(ROOT/'app/static/audio.js'));page.evaluate("document.dispatchEvent(new Event('DOMContentLoaded'))")
        page.locator('summary').click()
        expect(page.get_by_label('音效',exact=True)).not_to_be_checked();expect(page.get_by_label('音樂',exact=True)).not_to_be_checked()
        page.get_by_label('音效',exact=True).check();expect(page.get_by_label('音樂',exact=True)).not_to_be_checked()
        page.evaluate("WorldAudio.configure({assets:{'experience-confirmed':{kind:'sound',url:'/static/audio/test.wav',approved:false}}});WorldAudio.feedback('/drafts/d/confirm','POST',{experience_id:'e'},'owner')")
        assert page.evaluate('played.length')==0
        page.evaluate("WorldAudio.configure({assets:{'experience-confirmed':{kind:'sound',url:'/static/audio/test.wav',approved:true},'music':{kind:'music',url:'https://unapproved.invalid/test.mp3',approved:true}}});WorldAudio.feedback('/drafts/d/confirm','POST',{experience_id:'e2'},'owner');WorldAudio.feedback('/drafts/d/confirm','POST',{experience_id:'e2'},'owner')")
        assert page.evaluate('played')==['/static/audio/test.wav']
        page.get_by_label('音樂',exact=True).check();page.get_by_label('音效',exact=True).uncheck()
        assert page.evaluate('WorldAudio.preferences')=={'sound':False,'music':True}
        browser.close()


def test_theater_editable_simulation_history_and_no_implicit_save():
    with sync_playwright() as pw:
        browser=pw.chromium.launch();page=browser.new_page();page.set_content('<main id="app"></main>')
        page.add_script_tag(path=str(ROOT/'app/static/relationships.js'))
        page.evaluate('''async()=>{
          window.calls=[];window.ctx={state:{me:{owner_id:'o',status:'registered'},capabilities:{ai_available:true},renderGeneration:1},esc:v=>String(v).replaceAll('<','&lt;'),link:(route,label)=>'<a>'+label+'</a>',heading:(a,b)=>'<h1>'+a+'</h1>',time:v=>v,empty:v=>v,button:(a,l)=>'<button type="button" data-action="'+a+'">'+l+'</button>',toast:()=>{}};
          ctx.api=async(path,options)=>{if(options){calls.push({path,body:options.body});return {utterance:'明示替身：<script>不可執行</script>',notice:'測試替身，非真人',source_experience_ids:['e']};}return {person:{id:'p',name:'合成人物'},facts:{interests:[{id:'f',value:'閱讀',status:'confirmed',sources:[{id:'e'}]}]},interactions:[],stories:[{id:'e',occurred_at:'合成時間',summary:'合成來源'}],notes:[]};};
          PeopleUI.initialize(ctx);document.querySelector('#app').innerHTML=await PeopleUI.renderTheater('p','simulation');
        }''')
        page.locator('[name="simulation_facts"]').check();page.locator('#simulation-message').fill('如何開始？')
        page.evaluate("PeopleUI.handleClick(document.querySelector('[data-action=theater-generate]'))")
        expect(page.locator('#simulation-output')).to_contain_text('明示替身')
        assert page.locator('#simulation-output script').count()==0
        assert '模擬對話，非真人事實' in page.locator('#theater-content').input_value()
        page.locator('#theater-content').fill('使用者可改寫的模擬筆記')
        page.evaluate("PeopleUI.handleClick(document.querySelector('[data-action=theater-generate]'))")
        assert page.evaluate('calls[1].body.history.length')==2
        assert page.evaluate("calls.every(c=>c.path.endsWith('/simulation'))") is True
        assert page.locator('[name="source_ids"]').is_checked()
        browser.close()


def test_audio_success_hook_never_runs_for_failed_api_response():
    """直接執行新增hook所在的正式api函式；失敗不得播放成功回饋。"""
    import re
    source=(ROOT/'app/static/app.js').read_text()
    api=source[source.index('async function api('):source.index('async function refresh(')]
    with sync_playwright() as pw:
        browser=pw.chromium.launch();page=browser.new_page();page.set_content('<main></main>')
        page.evaluate('''()=>{window.calls=[];window.state={csrf:'synthetic',me:{owner_id:'o'}};window.WorldAudio={feedback:(...args)=>calls.push(args)};window.fetch=async()=>new Response(JSON.stringify({experience_id:'e'}),{status:201,headers:{'Content-Type':'application/json'}});}''')
        page.add_script_tag(content=api)
        assert page.evaluate("api('/drafts/d/confirm',{method:'POST',body:{request_id:'synthetic'}})")=={'experience_id':'e'}
        assert page.evaluate('calls.length')==1
        page.evaluate("window.fetch=async()=>new Response(JSON.stringify({error:{message:'合成失敗'}}),{status:500,headers:{'Content-Type':'application/json'}})")
        assert page.evaluate("async()=>{try{await api('/drafts/d/confirm',{method:'POST',body:{}});return false;}catch(e){return true;}}") is True
        assert page.evaluate('calls.length')==1
        browser.close()
