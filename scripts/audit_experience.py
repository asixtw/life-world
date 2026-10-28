from pathlib import Path  # 保存本機虛構資料的效能證據
from time import perf_counter  # 量測實際操作到畫面可用的時間
from statistics import median  # 以中位數避免單次偶發誤差
import json, sys, os  # 匯出不含私人資料的量測摘要並固定隔離環境
from uuid import uuid4  # 建立隔離提交識別碼
from playwright.sync_api import sync_playwright, expect  # 使用真實 Chromium 及頁面斷言
os.chdir(Path(__file__).resolve().parents[1])  # 不因執行目錄不同而寫錯報告位置
os.environ['LIFEWORLD_TEST_URL'] = 'http://127.0.0.1:8001'  # 防止外部環境變數讓測試資料流向其他服務
sys.path.insert(0, str(Path.cwd() / 'browser_tests'))  # 使用現有 UI 首次旅程作前置
from test_connections import seed_stories  # 以正式 API 建立虛構故事與帳號
BASE = 'http://127.0.0.1:8001'  # 僅測隔離服務，不接觸實際資料庫
output = Path('docs/artifacts/connections')  # 本輪證據與舊星圖分開
output.mkdir(parents=True, exist_ok=True)  # 建立驗收目錄
results = {'date': '2026-10-28 Asia/Taipei', 'browser': 'Playwright Chromium headless', 'navigation': [], 'api': [], 'limits': '每條路由各三次，非正式負載／實機／Safari 測試；CPU 與網路設定為模擬。'}  # 清楚保留測量界線
with sync_playwright() as playwright:  # 於結束時關閉所有瀏覽器資源
    browser = playwright.chromium.launch(headless=True)  # 啟動真正 Chromium
    context = browser.new_context(viewport={'width': 390, 'height': 844}, locale='zh-TW')  # 使用手機畫面尺寸
    page = context.new_page(); page.set_default_timeout(15000)  # 給慢網路足夠等待時間
    page.add_init_script('window.__uxLongTasks=[]; try {new PerformanceObserver(list=>list.getEntries().forEach(e=>window.__uxLongTasks.push(e.duration))).observe({type:"longtask",buffered:true});} catch(e) {}')  # 觀察實際大於五十毫秒的主執行緒工作
    errors = []; page.on('pageerror', lambda error: errors.append(str(error)))  # 捕捉未處理前端錯誤
    people, receipts = seed_stories(page)  # 從正常使用流程建立資料
    cdp = context.new_cdp_session(page)  # 以 DevTools 協定模擬較慢裝置
    routes = [('world', 'world'), ('goals', 'goals'), ('history', 'history'), ('connections', 'people'), ('collection', 'people?view=cards'), ('record', 'record')]  # 涵蓋主要入口與人物整理表單
    def ready(route):  # 等待真正的該頁渲染完成
        page.wait_for_function('route=>state.route===route && document.querySelector("#app").getAttribute("aria-busy")==="false"', arg=route)  # 不把舊畫面當載入成功
        page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')  # 等待實際繪製兩幀
    def navigate(route):  # 透過 hash 執行產品原生路由
        page.goto(BASE + '/#' + route); ready(route)  # 不直接呼叫內部 render 作弊
    for size in ['small', '300_people_103_stories']:  # 分開正常與較大資料量
        if size != 'small':  # 使用正式 API 逐批擴充同一隔離帳號
            csrf = page.request.get(BASE + '/api/auth/me').json()['csrf_token']; headers = {'X-CSRF-Token': csrf}  # 取得本人正式 CSRF
            for i in range(296):  # 加上原四人合計三百人
                response = page.request.post(BASE + '/api/people', headers=headers, data={'name': f'規模測試人物{i:03d}', 'roles': ['虛構驗收']})  # 真正保存而非僅塞前端假清單
                assert response.ok, response.text()  # 前置出錯就中止量測
            for i in range(100):  # 加上原三份合計一百零三份經歷
                raw = f'第{i:03d}段虛構驗收經歷，與小安記錄了一次真實活動的示例。'; story = {'title': f'規模測試故事{i:03d}', 'participants': [{'person_id': people[0]['id'], 'interacted': True}], 'mentions': []}  # 每筆來源獨立
                draft = page.request.post(BASE + '/api/experiences/drafts', headers=headers, data={'raw_text': raw, 'occurred_at': '2026-01-10T12:00:00+08:00', 'story': story}).json()  # 先保存未審閱草稿
                response = page.request.post(BASE + '/api/drafts/' + draft['id'] + '/confirm', headers=headers, data={'request_id': str(uuid4()), 'expected_revision': draft['revision'], 'summary': raw, 'story': story, 'story_reviewed': True})  # 正式人工確認不跳過資料規則
                assert response.ok, response.text()  # 不對未建立成功的資料做量測
            page.reload(); ready(page.url.split('#', 1)[-1] or 'world')  # 重新載入較大的正式世界狀態
        for network in ['local', '150ms_latency_4x_cpu']:  # 同時量測本機及模擬慢速條件
            cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4 if network != 'local' else 1})  # 模擬較慢 CPU
            cdp.send('Network.emulateNetworkConditions', {'offline': False, 'latency': 150 if network != 'local' else 0, 'downloadThroughput': 125000 if network != 'local' else -1, 'uploadThroughput': 62500 if network != 'local' else -1})  # 清楚指定延遲與頻寬
            page.evaluate('window.__uxLongTasks=[]')  # 各量測組分開統計
            for label, route in routes:  # 操作每個主要頁面
                timings = []  # 保存三次畫面可用時間
                for repeat in range(3):  # 重複但不以同 hash 的無操作當切頁
                    navigate('history' if route == 'world' else 'world')  # 回到另一頁形成真正切換
                    start = perf_counter(); navigate(route); timings.append(round((perf_counter() - start) * 1000, 1))  # 包含路由與繪製時間
                results['navigation'].append({'data': size, 'condition': network, 'route': label, 'median_ms': median(timings), 'max_ms': max(timings)})  # 不用少量樣本宣稱正式百分位
            results.setdefault('long_tasks', []).append({'data': size, 'condition': network, **page.evaluate('({count:window.__uxLongTasks.length,max_ms:Math.max(0,...window.__uxLongTasks)})')})  # 記錄長任務而非聲稱全程固定 FPS
            page.reload(); ready(page.url.split('#', 1)[-1] or 'world')  # 檢查冷載入的世界狀態影響
        for endpoint in ['/api/state', '/api/connections?limit=8', '/api/people?limit=12']:  # API 請求工具不受 DevTools 模擬網路影響
            timings=[]  # 獨立量測本機服務往返
            for repeat in range(5):  # 取得五次中位數
                start=perf_counter(); response=page.request.get(BASE+endpoint); timings.append(round((perf_counter()-start)*1000,1)); assert response.ok  # 只有成功回應才納入
            results['api'].append({'data':size,'endpoint':endpoint,'local_median_ms':median(timings),'local_max_ms':max(timings)})  # 不混淆頁面延遲與服務耗時
        cdp.send('Emulation.setCPUThrottlingRate', {'rate':1}); cdp.send('Network.emulateNetworkConditions', {'offline':False,'latency':0,'downloadThroughput':-1,'uploadThroughput':-1})  # 恢復正常條件後擴充資料或截圖
    navigate('people?story='+receipts[0]['experience_id'])  # 回到含提及的故事
    page.get_by_role('button',name='查看完整來源',exact=True).click(); expect(page.locator('#source-dialog')).to_contain_text('那天的午餐')  # 真正開啟來源抽屜
    page.screenshot(path=str(output/'390-source-viewport.png'))  # 保存實際視窗而非全頁拼接
    results['javascript_errors']=errors  # 保留執行錯誤摘要
    (output/'performance.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')  # 只輸出虛構資料的匿名效能量測
    print(json.dumps(results,ensure_ascii=False))  # 回報實際量測而非推測
    context.close(); browser.close()  # 清理所有測試視窗
