"""共用派送鎖與正式劇場模組契約；模型為明示替身，不算真模型驗收。"""
from pathlib import Path
from playwright.sync_api import sync_playwright,expect


def test_common_locked_button_still_dispatches_one_simulation():
    with sync_playwright() as pw:
        browser=pw.chromium.launch();page=browser.new_page();page.set_content('<main id="root"></main>')
        page.add_script_tag(path=str(Path(__file__).resolve().parents[1]/'app/static/relationships.js'))
        page.evaluate('''async () => {
          window.calls=[];
          const profile={person:{id:'synthetic-person',name:'合成人物'},facts:{interests:[{id:'synthetic-fact',status:'confirmed',value:'閱讀',sources:[{id:'synthetic-source'}]}]},interactions:[],stories:[],notes:[]};
          PeopleUI.initialize({state:{me:{owner_id:'synthetic-owner',status:'registered'},capabilities:{ai_available:true},renderGeneration:1},esc:String,time:String,heading:(a,b)=>'<h2>'+a+'</h2>',link:(p,l)=>'<a href="#'+p+'">'+l+'</a>',button:(a,l)=>'<button type="button" data-action="'+a+'">'+l+'</button>',empty:()=>'',toast:()=>{},api:async(path,options)=>{if(path.endsWith('/overview'))return profile;calls.push({path,body:options.body});return {utterance:'合成測試候選',notice:'Fixture，非真實模型',source_experience_ids:[]};}});
          document.querySelector('#root').innerHTML=await PeopleUI.renderTheater('synthetic-person','simulation');
        }''')
        page.locator('[name="simulation_facts"]').check();page.locator('#simulation-message').fill('一起閱讀嗎？')
        # 正式共用click派送在進入模組前已鎖定按鈕；此處驗證模組接受該契約。
        page.evaluate('''async () => {const target=document.querySelector('[data-action="theater-generate"]');target.disabled=true;await PeopleUI.handleClick(target);}''')
        assert len(page.evaluate('calls'))==1
        expect(page.locator('#simulation-output')).to_contain_text('合成測試候選')
        browser.close()
