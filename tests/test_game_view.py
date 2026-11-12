"""玩的遊戲（回合制互動作品）的頁面：查看（#game/{id}）、作品清單上的入口與標籤，以及「在這裡看」「在這裡玩」。

以 Node 直接執行 app/static/game.js、generation.js 與 works.js（假的 API，不開任何網站），檢查產生的 HTML 與送出的請求：
1. 建立：2026-11-12 起不再有獨立的 #game-new 表單，改在建立頁（#create）第一步選「玩的遊戲」。
   原本在這裡的三個表單案例（欄位與預設值、送出的內容、失敗與不能送出的原因）搬到 tests/test_creation_mode_view.py。
2. 準備中：顯示進度，並自動一位一位往下做（每次用新的提交代碼），直到準備好；離開頁面就停。
3. 某一次失敗：顯示訊息、稍等再試（間隔逐次拉長）、可以按「再試一次」；連續失敗太多次就停止自動重試；找不到的遊戲不重試。
4. 準備好：標題、開場白、同行的人、時數與站數，以及「在這裡玩」與「下載互動遊戲」。
5. 「在這裡玩」：先請伺服器匯出，再把那一次匯出放進頁面上的沙箱 iframe（有「關閉」）；看的故事的作品頁也有這一顆，另外多一顆「在這裡看」（閱讀版）。
   這一頁的安全設定不讓放 iframe 時（開了 Google 登入的環境），改成說明與「在新分頁開啟」，不留一片空白。
6. 作品清單：只有一個建立入口「＋ 建立新作品」；種類的標籤看得出玩法（看的故事、看的故事・多章節、玩的遊戲），玩的遊戲連到遊戲頁。
這是開發時的快速檢查；實際畫面以部署後在 Local 8030（Cloud SQL life_world_e2e）的 Chrome 操作為準。
"""
import os
import shutil
import subprocess

import pytest

SETUP = r"""
const assert = require('node:assert/strict');
const navigations = [], scheduled = [];
globalThis.window = globalThis;
globalThis.location = {hash: '#works'};
// 頁面上會被程式改寫的兩個區塊：準備中的進度、放 iframe 的地方
const panel = {innerHTML: ''}, player = {innerHTML: '', hidden: true, scrolled: 0, scrollIntoView() { this.scrolled++; }};
const listeners = {};  // 頁面上註冊的事件（瀏覽器擋下 iframe 時發出的那一種由測試自己觸發）
globalThis.document = {getElementById: id => id === 'game-build-panel' ? panel : id === 'gen-inline-player' ? player : null, body: {appendChild() {}},
  addEventListener(type, handler) { (listeners[type] = listeners[type] || []).push(handler); },
  removeEventListener(type, handler) { listeners[type] = (listeners[type] || []).filter(item => item !== handler); },
  createElement: () => ({click() { navigations.push(this.href); }, remove() {}})};
globalThis.setTimeout = fn => { scheduled.push(fn); return 0; };  // 進度迴圈由測試自己啟動（不真的等 50 毫秒）
require('./app/static/generation.js');
require('./app/static/works.js');
require('./app/static/game.js');
const UI = window.GameUI;
const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch]));
const building = (done, total = 3) => ({status: 'building', done, total});
const ready = {status: 'ready', done: 3, total: 3};
let game = {id: 'g1', title: '海線小鎮一日行 <i>', premise: '難得大家都有空 <u>。', skin: 'trip', status: 'active', created_at: 't0',
  cast: [{id: 'c1', name: '何以晴'}, {id: 'c2', name: '溫若岑'}], player: {name: '小光'}, meter: {label: '滿意'}, clock: {start: 510, limit: 600}, places: 7, hours: 10, build: building(1)};
const item = {version_no: 3, created_at: '2026-11-12T10:00:00+00:00', format: 'html', player: 'route-1', filename: '海線小鎮一日行（互動遊戲）.html', size: 61440, sha256: 'abc',
  source_version: 1, download_path: '/api/works/g1/exports/3/download'};
let exportsReply = {available: true, items: []}, advanceReplies = [], interactiveFail = null;
const calls = [], toasts = [], navigated = [], sleeps = [];
let renders = 0;
const state = {renderGeneration: 1, dirty: true};
const api = async (path, options = {}) => {
  calls.push({path, method: options.method || 'GET', body: options.body});
  if (path === '/generation/status') return {available: true, background: true};
  if (path === '/games/g1/advance') { const next = advanceReplies.shift(); if (!next) throw new Error('測試沒有準備這一次的回應'); return next(); }
  if (path === '/games/g1') return game;
  if (path === '/works/g1/exports' && options.method === 'POST') return {export: item};
  if (path === '/works/g1/exports') return exportsReply;
  if (path === '/works/w1/interactive') { if (interactiveFail) throw new Error(interactiveFail); return {interactive: {available: true}}; }
  if (path === '/works/w1/exports' && options.method === 'POST') return {export: {...item, version_no: 5, player: 'play-2', download_path: '/api/works/w1/exports/5/download'}};
  if (path === '/works/w1/exports') return exportsReply;
  if (path.startsWith('/works/center')) return {counts: {all: 5}, total: 5, items: [
    {id: 'g1', kind: 'turn_game', title: '海線小鎮一日行', phase: 'completed', people: ['何以晴'], progress: null, current_version: 1, status: 'active', updated_at: 't1', can_resume: false},
    {id: 'w1', kind: 'generated_work', title: '留一條接縫', phase: 'completed', people: [], progress: null, current_version: 2, status: 'active', updated_at: 't2', can_resume: false},
    {id: 's1', kind: 'story_series', title: '留一條接縫（連載）', phase: 'active', people: [], progress: null, current_version: 3, status: 'active', updated_at: 't3', can_resume: false},
    {id: 'r1', kind: 'roleplay_session', title: '舊的自動演出', phase: 'completed', people: [], progress: null, current_version: 1, status: 'active', updated_at: 't4', can_resume: false},
    {id: 'o1', kind: 'story_opening', title: '舊的故事開場', phase: 'completed', people: [], progress: null, current_version: 1, status: 'active', updated_at: 't5', can_resume: false}]};
  return {};
};
const fail = (message, status) => () => { const error = new Error(message); error.status = status; throw error; };
let ids = 0;
const requested = new Map();
const context = {state, api, esc, sleep: async ms => { sleeps.push(ms); },
  link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1><p>${esc(subtitle)}</p>${action}`, empty: m => `<div class="empty">${esc(m)}</div>`,
  // 和主程式的 requestId 一樣：同一個範圍、同樣的內容回同一個代碼，內容或範圍不同才換新代碼
  time: x => 'T(' + x + ')', toast: m => toasts.push(m), render: async () => { renders++; }, navigate: route => navigated.push(route),
  requestId: (scope, body) => { const fingerprint = JSON.stringify(body); if (requested.get(scope)?.fingerprint !== fingerprint) requested.set(scope, {fingerprint, id: 'rid:' + scope + ':' + (++ids)}); return requested.get(scope).id; }};
UI.initialize(context);
window.GenerationUI.initialize(context);
window.WorksUI.initialize(context);
const has = (html, text) => html.includes(text);
const advances = () => calls.filter(call => call.path === '/games/g1/advance');
(async () => {
"""


def run_node(script):
    node = os.environ.get('LIFEWORLD_NODE') or shutil.which('node')
    if not node:
        pytest.skip('需要 Node 執行前端模組；可設定 LIFEWORLD_NODE')
    result = subprocess.run([node, '-e', SETUP + script + '\n})().catch(e => { console.error(e); process.exit(1); });'],
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_the_game_module_no_longer_has_its_own_create_form():
    """建立改在建立頁（#create）選「玩的遊戲」：這個模組只剩查看的頁面，不再讀人物清單、也不處理表單送出。"""
    run_node(r"""
assert.equal(UI.newView, undefined);
assert.equal(UI.submit, undefined);
assert.equal(typeof UI.view, 'function');
assert.equal(typeof UI.handleClick, 'function');
""")


def test_a_building_game_shows_progress_and_advances_until_it_is_ready():
    run_node(r"""
const html = await UI.view('g1');
assert.ok(has(html, '海線小鎮一日行 &lt;i&gt;') && has(html, 'id="game-build-panel"') && has(html, '準備中'));
assert.ok(has(html, '正在請每位同行者想好反應：0／2') && has(html, '何以晴、溫若岑'));
assert.ok(has(html, '<p>玩的遊戲</p>') && !has(html, '互動遊戲'));  // 種類的說法和作品清單一致
assert.ok(!has(html, 'gen-play-here') && !has(html, 'gen-export'));  // 還不能玩
assert.ok(!calls.some(call => call.path === '/works/g1/exports'));
assert.equal(scheduled.length, 1);
assert.equal(advances().length, 0);

const seen = [];
advanceReplies = [() => ({build: building(2)}), () => { seen.push(panel.innerHTML); return {build: ready}; }];
await scheduled[0]();
assert.equal(advances().length, 2);  // 一位一位往下做，準備好就停
assert.ok(advances().every(call => call.method === 'POST' && Object.keys(call.body).join() === 'request_id'));
assert.notEqual(advances()[0].body.request_id, advances()[1].body.request_id);  // 每次用新的提交代碼
assert.ok(seen[0].includes('正在請每位同行者想好反應：1／2'));  // 進度跟著更新
assert.equal(renders, 1);  // 準備好：重畫整頁
assert.deepEqual(sleeps, []);

// 離開這一頁（重畫的世代變了）：不再往下做
scheduled.length = 0;
await UI.view('g1');
state.renderGeneration = 2;
advanceReplies = [() => ({build: building(2)})];
await scheduled[0]();
assert.equal(advances().length, 2);
""")


def test_a_failed_step_is_explained_retried_with_longer_waits_and_can_be_retried_by_hand():
    run_node(r"""
await UI.view('g1');
const shown = [];
advanceReplies = [fail('模型暫時沒有回應，請稍後再試。', 503), () => { shown.push(panel.innerHTML); throw new Error('還是沒有回應。'); },
  () => { shown.push(panel.innerHTML); return {build: building(2)}; }, () => ({build: ready})];
await scheduled[0]();
assert.equal(advances().length, 4);
assert.deepEqual(sleeps, [5000, 10000]);  // 稍等再試，間隔逐次拉長
assert.ok(shown[0].includes('模型暫時沒有回應，請稍後再試。') && shown[0].includes('約 5 秒後自動再試') && shown[0].includes('data-action="game-retry" data-id="g1"'));
assert.ok(shown[0].includes('正在請每位同行者想好反應：0／2'));  // 進度還在
assert.ok(shown[1].includes('還是沒有回應。') && shown[1].includes('約 10 秒後自動再試'));
// 2026-11-12 外部檢驗：伺服器確認失敗（503）之後是新的嘗試；連線中斷（沒有狀態碼）之後沿用同一個提交代碼，
// 伺服器若其實已經做完，重送只會找回那一次的結果，不會再付費生成一次。原本「每次重試都換新代碼」的斷言因此改寫。
const tried = advances().map(call => call.body.request_id);
assert.notEqual(tried[1], tried[0]);  // 503 之後：新的提交代碼
assert.equal(tried[2], tried[1]);  // 連線中斷之後：沿用
assert.notEqual(tried[3], tried[2]);  // 成功之後：下一位用新的提交代碼
assert.ok(!panel.innerHTML.includes('game-retry'));  // 成功之後訊息收掉
assert.equal(renders, 1);
""")


def test_retrying_by_hand_cuts_the_wait_short_and_too_many_failures_stop_the_automatic_retries():
    run_node(r"""
// 等待中按「再試一次」：不用等到時間到
let release = null;
context.sleep = ms => new Promise(resolve => { sleeps.push(ms); release = resolve; });
await UI.view('g1');
advanceReplies = [fail('暫時失敗', 503), () => ({build: ready})];
const loop = scheduled[0]();
await new Promise(resolve => setImmediate(resolve));
assert.equal(advances().length, 1);
assert.deepEqual(sleeps, [5000]);
assert.equal(await UI.handleClick({dataset: {action: 'game-retry', id: 'g1'}}), true);
await loop;
assert.equal(advances().length, 2);
assert.equal(renders, 1);
assert.equal(await UI.handleClick({dataset: {action: 'something-else'}}), false);

// 連續失敗：自動重試 5 次之後停下來（每一次都可能是要付費的呼叫），只留按鈕
context.sleep = async ms => { sleeps.push(ms); };
sleeps.length = 0; calls.length = 0; scheduled.length = 0;
await UI.view('g1');
advanceReplies = Array.from({length: 6}, () => fail('一直失敗', 503));
await scheduled[0]();
assert.equal(advances().length, 6);
assert.deepEqual(sleeps, [5000, 10000, 20000, 40000, 60000]);  // 最長等一分鐘
assert.ok(panel.innerHTML.includes('已經停止自動重試') && panel.innerHTML.includes('data-action="game-retry"') && panel.innerHTML.includes('一直失敗'));
// 這時按「再試一次」：重新開始往下做
advanceReplies = [() => ({build: ready})];
assert.equal(await UI.handleClick({dataset: {action: 'game-retry', id: 'g1'}}), true);
await new Promise(resolve => setImmediate(resolve));
assert.equal(advances().length, 7);
assert.equal(renders, 2);

// 找不到這件遊戲：再試也一樣，不重試
sleeps.length = 0; calls.length = 0; scheduled.length = 0;
await UI.view('g1');
advanceReplies = [fail('找不到可存取的作品。', 404)];
await scheduled[0]();
assert.equal(advances().length, 1);
assert.deepEqual(sleeps, []);
assert.ok(panel.innerHTML.includes('找不到可存取的作品。'));
""")


def test_a_ready_game_shows_what_it_is_and_offers_playing_here_and_downloading():
    run_node(r"""
game = {...game, build: ready};
exportsReply = {available: true, items: [item]};
const html = await UI.view('g1');
assert.equal(scheduled.length, 0);  // 準備好了：不再呼叫 advance
assert.ok(has(html, '海線小鎮一日行 &lt;i&gt;') && has(html, '難得大家都有空 &lt;u&gt;。') && !has(html, '<u>'));
assert.ok(has(html, '何以晴、溫若岑') && has(html, '小光') && has(html, '08:30 出發・10 小時・7 站') && has(html, '「滿意」'));
assert.ok(has(html, 'data-action="gen-play-here" data-id="g1"') && has(html, '>在這裡玩</button>'));
assert.ok(has(html, 'data-action="gen-export" data-id="g1" data-player="play"') && has(html, '>下載互動遊戲</button>'));
assert.ok(html.indexOf('>在這裡玩</button>') < html.indexOf('>下載互動遊戲</button>'));
assert.ok(has(html, 'id="gen-inline-player"') && has(html, 'hidden') && has(html, '離線') && has(html, '不含人物設定'));
assert.ok(has(html, '上次匯出') && has(html, '60.0 KB'));
assert.ok(calls.some(call => call.path === '/works/g1/exports'));
// 用語和看的故事的作品頁一致：種類叫「玩的遊戲」；「在這裡玩」不用下載、直接在這一頁打開；下載的是一個 HTML 檔
assert.ok(has(html, '<p>玩的遊戲</p>') && has(html, '<h2>開始玩</h2>') && has(html, '「在這裡玩」不用下載，直接在這一頁打開') && has(html, '存成一個 HTML 檔'));
assert.ok(!has(html, 'gen-view-here'));  // 玩的遊戲沒有閱讀版：不提供「在這裡看」
game = {...game, title: ''};   // 沒有標題時，用種類的名稱
assert.ok(has(await UI.view('g1'), '<h1>玩的遊戲</h1>'));

exportsReply = {available: false, items: []};   // 這個環境沒有開放下載：說明原因，不給按鈕
const off = await UI.view('g1');
assert.ok(!has(off, 'gen-play-here') && !has(off, 'data-action="gen-export"') && has(off, '還沒有開放下載'));
""")


def test_play_here_exports_then_shows_the_export_in_a_sandboxed_frame_that_can_be_closed():
    run_node(r"""
const G = window.GenerationUI;
assert.equal(await UI.handleClick({dataset: {action: 'gen-play-here', id: 'g1'}}), false);  // 遊戲頁自己不處理，交給作品頁的匯出流程
assert.equal(await G.handleClick({dataset: {action: 'gen-play-here', id: 'g1'}}), true);
const posts = calls.filter(call => call.method === 'POST');
assert.deepEqual(posts.map(call => call.path), ['/works/g1/exports']);  // 互動遊戲不需要另外準備互動內容
assert.deepEqual({...posts[0].body, request_id: null}, {request_id: null, format: 'html', player: 'play'});
assert.equal(player.hidden, false);
assert.ok(/<iframe[^>]* sandbox="allow-scripts"[^>]* src="\/api\/works\/g1\/exports\/3\/view"/.test(player.innerHTML));  // 沙箱裡只允許執行程式
assert.ok(!/sandbox="[^"]*allow-same-origin/.test(player.innerHTML));
assert.ok(player.innerHTML.includes('data-action="gen-play-close"') && player.innerHTML.includes('關閉'));
assert.ok(/<a [^>]*href="\/api\/works\/g1\/exports\/3\/view"[^>]*target="_blank"[^>]*rel="noopener"/.test(player.innerHTML));
assert.equal(player.scrolled, 1);
assert.deepEqual(navigations, []);  // 沒有下載
assert.equal(renders, 0);  // 不重畫整頁（iframe 才不會被清掉）

assert.equal(await G.handleClick({dataset: {action: 'gen-play-close'}}), true);
assert.equal(player.hidden, true);
assert.equal(player.innerHTML, '');

// 下載：同一個匯出流程，下載伺服器回的那一次
assert.equal(await G.handleClick({dataset: {action: 'gen-export', id: 'g1', player: 'play', name: '互動遊戲'}}), true);
assert.deepEqual(navigations, ['/api/works/g1/exports/3/download']);
assert.equal(toasts[toasts.length - 1], '已開始下載互動遊戲。');
assert.ok(!calls.some(call => call.path.includes('/interactive')));
""")


def test_when_the_page_may_not_frame_it_play_here_falls_back_to_opening_a_new_tab():
    """開了 Google 登入的環境，首頁的 CSP 只放行 Google 的登入框（frame-src），同源的 iframe 也會被瀏覽器擋下來、框裡一片空白。
    瀏覽器擋的時候會對頁面發出 securitypolicyviolation 事件：收到之後把框換成說明與「在新分頁開啟」（同一個網址，內容相同）。"""
    run_node(r"""
const G = window.GenerationUI;
await G.handleClick({dataset: {action: 'gen-play-here', id: 'g1'}});
assert.ok(player.innerHTML.includes('<iframe'));
const fire = event => (listeners.securitypolicyviolation || []).forEach(handler => handler(event));
assert.equal((listeners.securitypolicyviolation || []).length, 1);
fire({effectiveDirective: 'script-src-elem', blockedURI: 'inline'});  // 別的東西被擋：不關這裡的事
fire({effectiveDirective: 'frame-src', blockedURI: 'https://accounts.example/other'});
assert.ok(player.innerHTML.includes('<iframe'));
fire({effectiveDirective: 'frame-src', blockedURI: 'https://lw.example/api/works/g1/exports/3/view'});  // 這一個 iframe 被擋了
assert.ok(!player.innerHTML.includes('<iframe') && player.hidden === false);
assert.ok(player.innerHTML.includes('不允許在這一頁裡直接顯示'));
assert.ok(/<a class="primary" href="\/api\/works\/g1\/exports\/3\/view" target="_blank" rel="noopener">在新分頁開啟<\/a>/.test(player.innerHTML));
assert.ok(player.innerHTML.includes('data-action="gen-play-close"'));

// 再按一次、或關閉：不會留下重複的監聽
await G.handleClick({dataset: {action: 'gen-play-here', id: 'g1'}});
assert.equal(listeners.securitypolicyviolation.length, 1);
await G.handleClick({dataset: {action: 'gen-play-close'}});
assert.equal(listeners.securitypolicyviolation.length, 0);
""")


def test_the_run_page_also_gets_a_play_here_button_for_its_interactive_version():
    run_node(r"""
const G = window.GenerationUI;
const detail = {id: 'w1', title: '留一條接縫', module: 'T2', cast: [{id: 'c1', name: '溫若岑', source: 'person', version: 3, is_user: false}],
  run: {status: 'completed', completed_segments: 2, total_segments: 2, notice: null, error: null, can_resume: false}, usage: {calls: 3},
  segments: [{speaker_name: '溫若岑', is_user: false, line: '先做一小塊。', action: '', stage_direction: ''}], setup: {scene: {description: '試作桌'}, styles: []}, history: []};
G.initialize({...context, api: async (path, options = {}) => path === '/generation/runs/w1' ? detail : api(path, options)});
const html = await G.run('w1');
assert.ok(has(html, 'data-action="gen-play-here" data-id="w1" data-prepare="1"') && has(html, '>在這裡玩</button>') && has(html, 'id="gen-inline-player"'));
assert.equal(html.split('data-action="gen-export"').length - 1, 2);  // 原本的兩顆下載按鈕不變

// 按下去：和下載互動版一樣先準備互動內容，再匯出互動版，然後放進 iframe
const button = {dataset: {action: 'gen-play-here', id: 'w1', prepare: '1'}, textContent: '在這裡玩'};
assert.equal(await G.handleClick(button), true);
assert.deepEqual(calls.filter(call => call.method === 'POST').map(call => call.path), ['/works/w1/interactive', '/works/w1/exports']);
assert.equal(calls.find(call => call.path === '/works/w1/exports' && call.method === 'POST').body.player, 'play');
assert.ok(player.innerHTML.includes('src="/api/works/w1/exports/5/view"') && player.hidden === false);
assert.equal(button.textContent, '在這裡玩');
assert.deepEqual(navigations, []);

// 互動內容準備不了：照樣可以玩（沒有抉擇與線索的互動版），並說明原因
interactiveFail = '今天的 AI 用量已達上限，明天再試。';
player.innerHTML = ''; player.hidden = true;
assert.equal(await G.handleClick(button), true);
assert.ok(player.innerHTML.includes('/exports/5/view') && toasts[toasts.length - 1].includes('今天的 AI 用量已達上限，明天再試。'));
""")


def test_the_run_page_has_a_read_here_button_that_shows_the_reading_version_in_the_same_frame():
    """看的故事的作品頁多一顆「在這裡看」：建立或沿用閱讀版的匯出（和「下載 HTML」同一種請求），放進和「在這裡玩」同一個區塊。"""
    run_node(r"""
const G = window.GenerationUI;
const detail = {id: 'w1', title: '留一條接縫', module: 'T2', cast: [{id: 'c1', name: '溫若岑', source: 'person', version: 3, is_user: false}],
  run: {status: 'completed', completed_segments: 2, total_segments: 2, notice: null, error: null, can_resume: false}, usage: {calls: 3},
  segments: [{speaker_name: '溫若岑', is_user: false, line: '先做一小塊。', action: '', stage_direction: ''}], setup: {scene: {description: '試作桌'}, styles: []}, history: []};
G.initialize({...context, api: async (path, options = {}) => path === '/generation/runs/w1' ? detail : api(path, options)});
const html = await G.run('w1');
assert.ok(has(html, '<h2>看或玩</h2>'));  // 區塊的標題涵蓋看與玩
assert.ok(has(html, 'data-action="gen-view-here" data-id="w1"') && has(html, '>在這裡看</button>'));
assert.ok(html.indexOf('>在這裡看</button>') < html.indexOf('>在這裡玩</button>'));  // 「在這裡看」「在這裡玩」排在一起
assert.equal(html.split('id="gen-inline-player"').length - 1, 1);  // 兩顆共用同一個顯示區塊

const button = {dataset: {action: 'gen-view-here', id: 'w1'}, textContent: '在這裡看'};
assert.equal(await UI.handleClick(button), false);  // 遊戲頁的模組不處理
assert.equal(await G.handleClick(button), true);
const posts = calls.filter(call => call.method === 'POST');
assert.deepEqual(posts.map(call => call.path), ['/works/w1/exports']);  // 閱讀版不準備互動內容
assert.deepEqual({...posts[0].body, request_id: null}, {request_id: null, format: 'html'});  // 和「下載 HTML」一樣不帶 player：伺服器沿用或建立閱讀版
assert.ok(typeof posts[0].body.request_id === 'string' && posts[0].body.request_id.length > 0 && !posts[0].body.request_id.includes(':play:'));
assert.equal(player.hidden, false);
assert.ok(/<iframe[^>]* sandbox="allow-scripts"[^>]* src="\/api\/works\/w1\/exports\/5\/view"[^>]* title="在這裡看"/.test(player.innerHTML));  // 伺服器回的那一次匯出
assert.ok(!/sandbox="[^"]*allow-same-origin/.test(player.innerHTML));
assert.ok(player.innerHTML.includes('在這裡看') && !player.innerHTML.includes('在這裡玩'));  // 說明文字是看的，不是玩的
assert.ok(/<a [^>]*href="\/api\/works\/w1\/exports\/5\/view"[^>]*target="_blank"[^>]*rel="noopener"/.test(player.innerHTML));
assert.ok(player.innerHTML.includes('data-action="gen-play-close"'));
assert.equal(player.scrolled, 1);
assert.deepEqual(navigations, []);  // 沒有下載
assert.equal(renders, 0);  // 不重畫整頁（iframe 才不會被清掉）
assert.equal(button.textContent, '在這裡看');

// 「在這裡玩」的說明不變；關閉照舊
await G.handleClick({dataset: {action: 'gen-play-here', id: 'w1'}});
assert.ok(player.innerHTML.includes('在這裡玩（進度只留在這一次') && /title="在這裡玩"/.test(player.innerHTML));
assert.equal(listeners.securitypolicyviolation.length, 1);  // 換一種來看：不會留下重複的監聽
assert.equal(await G.handleClick({dataset: {action: 'gen-play-close'}}), true);
assert.equal(player.hidden, true);
assert.equal(player.innerHTML, '');
""")


def test_the_works_page_has_one_create_entry_and_labels_works_by_how_they_are_used():
    run_node(r"""
const html = await window.WorksUI.list();
// 只有一個建立入口：「＋ 建立新作品」（玩法到建立頁再選）
assert.ok(has(html, '<a class="primary" href="#create">＋ 建立新作品</a>'));
assert.equal(html.split('＋').length - 1, 1);
assert.ok(!has(html, 'game-new') && !has(html, '＋ 互動遊戲'));
// 清單：種類的標籤看得出玩法；玩的遊戲連到遊戲頁
assert.ok(has(html, 'href="#game/g1"') && has(html, '玩的遊戲 · '));
assert.ok(has(html, 'href="#run/w1"') && has(html, '看的故事 · '));
assert.ok(has(html, 'href="#series/s1"') && has(html, '看的故事・多章節 · '));
assert.ok(!has(html, '互動遊戲') && !has(html, '生成作品') && !has(html, '多章節作品'));
assert.ok(!has(html, 'turn_game') && !has(html, 'href="#work/g1"'));
// 其他舊種類的標籤不動
assert.ok(has(html, 'href="#run/r1"') && has(html, '自動演出 · ') && has(html, 'href="#story/o1"') && has(html, '故事開場 · '));
""")


def test_the_app_shell_routes_the_game_pages_and_loads_the_module():
    """主程式接上了：路由、頁面標題、所屬分頁、點擊的分派；index.html 載入模組（在主程式之前）。
    建立表單併進建立頁之後：#game-new 只是轉址（舊連結不會壞），主程式不再把表單送出交給這個模組。"""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / 'app' / 'static'
    app, index = (root / 'app.js').read_text(encoding='utf-8'), (root / 'index.html').read_text(encoding='utf-8')
    assert "route.split('?')[0] === 'game-new'" in app and "route = 'create?mode=game'; history.replaceState(null, '', '#' + route);" in app, \
        '舊的建立入口就地換成建立頁，並預選玩的遊戲'
    assert "path === 'game-new'" not in app and 'GameUI.newView' not in app and 'GameUI.submit' not in app
    assert "path.startsWith('game/')) html = await GameUI.view(decodeURIComponent(path.split('/')[1]))" in app
    assert 'await GameUI.handleClick(target)' in app and 'GameUI.initialize({' in app
    assert "route.startsWith('game/')?'玩的遊戲'" in app and "'互動遊戲'" not in app, '頁面標題'
    assert 'game-new|game\\/' in app, '玩的遊戲的頁面算在「作品」分頁底下'
    assert index.index('/static/game.js') < index.index('/static/app.js') and index.count('/static/game.js') == 1
    assert index.index('/static/generation.js') < index.index('/static/game.js')


def test_a_step_still_running_elsewhere_keeps_the_same_request_and_a_reloaded_page_starts_fresh():
    """2026-11-12 外部檢驗：伺服器回「還在進行」（409 generation_in_progress）時結果還沒定，沿用同一個提交代碼；
    不是同一頁的另一次執行（重新進入這一頁）也延續同一件遊戲目前的嘗試，不會從頭用回已經成功過的代碼。"""
    run_node(r"""
await UI.view('g1');
const busy = () => { const error = new Error('這件作品正在生成下一位同行者的反應，請稍候。'); error.status = 409; error.code = 'generation_in_progress'; throw error; };
advanceReplies = [busy, () => ({build: building(2)}), () => ({build: ready})];
await scheduled[0]();
const tried = advances().map(call => call.body.request_id);
assert.equal(tried[1], tried[0]);  // 還在進行：沿用
assert.notEqual(tried[2], tried[1]);  // 成功之後：新的
// 回到這一頁再做：不會用回前面已經成功過的代碼
scheduled.length = 0;
game = {...game, build: building(2)};
await UI.view('g1');
advanceReplies = [() => ({build: ready})];
await scheduled[0]();
assert.ok(!tried.includes(advances()[3].body.request_id));
""")
