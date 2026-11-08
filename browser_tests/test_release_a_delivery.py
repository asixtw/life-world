"""獨立Chromium操作正式App：隔離SQLite，不冒充Product PG或真AI驗收。"""
import os,socket,subprocess,time,urllib.request
from datetime import date,timedelta
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright,expect

@pytest.fixture(scope='module')
def base(tmp_path_factory):
    root=Path(__file__).resolve().parents[1]
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    env={k:v for k,v in os.environ.items() if not k.startswith(('LIFEWORLD_','K_SERVICE','K_REVISION'))}
    env.update(LIFEWORLD_DATA_DIR=str(tmp_path_factory.mktemp('release-a')),LIFEWORLD_AI_ENABLED='false')
    log=Path('/private/tmp/GCP144_releaseA/server.log').open('w')
    python=os.environ.get('LIFEWORLD_API_TEST_PYTHON','/private/tmp/lw-alpha-py312/bin/python')
    process=subprocess.Popen([python,'-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port',str(port)],cwd=root,env=env,stdout=log,stderr=log)
    url=f'http://127.0.0.1:{port}'
    try:
        for _ in range(80):
            if process.poll() is not None:raise RuntimeError('isolated API failed')
            try:urllib.request.urlopen(url+'/health',timeout=.2);break
            except Exception:time.sleep(.1)
        yield url
    finally:process.terminate();process.wait(timeout=10);log.close()

@pytest.mark.parametrize('date_method',['native','quick'])
def test_core_goal_submission_and_readback(base,date_method):
    with sync_playwright() as pw:
        browser=pw.chromium.launch();page=browser.new_page(locale='zh-TW',viewport={'width':390 if date_method=='quick' else 1280,'height':1000})
        page.set_default_timeout(8000)
        page.goto(base);page.get_by_role('button',name='不用註冊，先開始').click()
        page.locator('#profile-name').fill('合成ReleaseA');page.locator('#bio').fill('合成閱讀驗收')
        page.get_by_role('button',name='接著，建立第一個目標').click()
        page.locator('#goal-title').fill('合成閱讀15分鐘');page.get_by_role('button',name='下一步').click()
        page.locator('#outcome').fill('七天閱讀心得')
        # 空日期必須阻止前進且不能送出正式目標，與原生控制器自動化失敗分開。
        page.get_by_role('button',name='下一步').click();expect(page.locator('#goal-form')).to_have_attribute('data-step','1')
        today=page.request.get(base+'/api/auth/me').json()['today']
        deadline=(date.fromisoformat(today)+timedelta(days=7)).isoformat()
        if date_method=='native':page.locator('#goal-deadline').fill(deadline)
        else:page.get_by_role('button',name='一週後',exact=True).click();expect(page.locator('#goal-deadline')).to_have_value(deadline)
        page.reload();expect(page.locator('#goal-deadline')).to_have_value(deadline)
        page.screenshot(path=f'/private/tmp/GCP144_releaseA/{date_method}-date.png',full_page=True)
        page.get_by_role('button',name='下一步').click()
        for i,name in enumerate(['閱讀','記錄心得','整理重點']):
            page.locator(f'#action-title-{i}').fill(name);page.get_by_role('button',name='每天',exact=True).click();page.get_by_role('button',name='下一步').click()
        with page.expect_response(lambda r:r.url.endswith('/api/goals') and r.request.method=='POST') as response:
            page.get_by_role('button',name='確認設定，建立目標蛋').click()
        assert response.value.status==201,response.value.text()
        for stage in range(1,4):
            page.locator('[data-birth-egg]').click();expect(page.locator('[data-birth]')).to_have_attribute('data-stage',str(stage))
        page.locator('[data-birth-enter]').click()
        world=page.request.get(base+'/api/state').json();assert len(world['goals'])==1
        goal=world['goals'][0];assert len(goal['actions'])==3
        page.goto(base+'/#record');page.locator('#raw-text').fill('合成紀錄：今天閱讀15分鐘並寫下心得。')
        page.locator('#goal-id').select_option(goal['id'])
        action=goal['actions'][0];page.locator('#quantity-'+action['id']).fill('1')
        page.get_by_role('button',name='保存草稿並進入核對').click();expect(page.locator('#review-form')).to_be_visible()
        before=page.request.get(base+'/api/state').json();assert len(before['experiences'])==0 and before['rewards']['total']==0
        page.locator('#summary').fill('人工核對：完成一次閱讀。');page.locator('#followups').fill('明天整理下一章')
        with page.expect_response(lambda r:'/confirm' in r.url and r.request.method=='POST') as confirmation:
            page.get_by_role('button',name='我已核對，確認保存').click()
        assert confirmation.value.status==201,confirmation.value.text()
        # 重送使用同一份實際UI請求及Session；CSRF只在記憶體，不輸出憑證。
        req=confirmation.value.request
        repeated=page.request.post(req.url,data=req.post_data,headers={'Content-Type':'application/json','X-CSRF-Token':req.headers['x-csrf-token']})
        assert repeated.status==201
        assert repeated.json()==confirmation.value.json()
        page.reload();world=page.request.get(base+'/api/state').json()
        assert len(world['goals'])==1 and len(world['goals'][0]['actions'])==3
        assert len(world['experiences'])==1 and world['rewards']['total']==1 and len(world['tasks'])==1
        assert world['goals'][0]['actions'][0]['progress']=='1'
        page.goto(base+'/#world');expect(page.locator('.home-lumi')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=f'/private/tmp/GCP144_releaseA/{date_method}-world.png',full_page=True)
        browser.close()
