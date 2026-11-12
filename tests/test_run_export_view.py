"""作品頁的「下載 HTML」與「下載互動版」：作品完成後才出現；按下去先請伺服器匯出，再下載那一次匯出的檔案。
「下載互動版」多一步：先請伺服器準備互動內容（線索、抉擇與結局），成功後才匯出；準備失敗就說明原因，改成匯出沒有抉擇的互動版。
2026-11-12：這個區塊的標題改成「看或玩」，多一顆「在這裡看」（閱讀版直接在這一頁打開）；原有的按鈕行為不變。

以 Node 直接執行 app/static/generation.js（假的 API，不開任何網站），檢查產生的 HTML 與送出的請求。
這是開發時的快速檢查；實際畫面以部署後在 Local 8030（Cloud SQL life_world_e2e）的 Chrome 操作為準。
"""
import os
import shutil
import subprocess

import pytest

SETUP = r"""
const assert = require('node:assert/strict');
const navigations = [];
globalThis.window = globalThis;
// 下載用暫時的連結元素觸發（不讓整個頁面跳轉）；這裡記下被點擊的網址。
globalThis.document = {getElementById: () => null, addEventListener() {}, body: {appendChild() {}},
  createElement: () => ({click() { navigations.push(this.href); }, remove() {}})};
require('./app/static/generation.js');
const UI = window.GenerationUI;
const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch]));
const detail = status => ({id: 'w1', title: '留一條接縫', module: 'T2', cast: [{id: 'c1', name: '溫若岑', source: 'person', version: 3, is_user: false, position: 'supporting'}],
  run: {status, completed_segments: 2, total_segments: 2, notice: null, error: null, can_resume: false}, usage: {calls: 3},
  segments: [{speaker_name: '溫若岑', is_user: false, line: '先做一小塊。', action: '', stage_direction: ''}], setup: {scene: {description: '試作桌'}, styles: []}, history: []});
const item = {version_no: 2, created_at: '2026-11-11T10:00:00+00:00', format: 'html', player: 'reader-1', filename: '留一條接縫.html', size: 20480, sha256: 'abc',
  source_version: 3, download_path: '/api/works/w1/exports/2/download'};
let status = 'completed', exportsReply = {available: true, items: []}, exportsFail = false, interactiveFail = null;
const calls = [], toasts = [];
let renders = 0;
const api = async (path, options = {}) => {
  calls.push({path, method: options.method || 'GET', body: options.body});
  if (path === '/generation/runs/w1') return detail(status);
  if (path === '/generation/status') return {available: true, background: true};
  if (path === '/works/w1/exports' && options.method === 'POST') return {export: item};
  if (path === '/works/w1/interactive' && options.method === 'POST') {  // 準備互動內容；interactiveFail 有值就當成失敗（例如金額上限）
    if (interactiveFail) throw new Error(interactiveFail);
    return {interactive: {available: true, has_decision: true, clues: 2, epilogues: 2}};
  }
  if (path === '/works/w1/exports') { if (exportsFail) throw new Error('offline'); return exportsReply; }
  return {};
};
UI.initialize({state: {renderGeneration: 1}, api, esc,
  link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1><p>${esc(subtitle)}</p>${action}`, empty: m => `<div class="empty">${esc(m)}</div>`,
  time: x => 'T(' + x + ')', toast: m => toasts.push(m), requestId: (scope, body) => 'rid:' + scope, render: async () => { renders++; }, navigate() {}});
const has = (html, text) => html.includes(text);
(async () => {
"""


def run_node(script):
    node = os.environ.get('LIFEWORLD_NODE') or shutil.which('node')
    if not node:
        pytest.skip('需要 Node 執行前端模組；可設定 LIFEWORLD_NODE')
    result = subprocess.run([node, '-e', SETUP + script + '\n})().catch(e => { console.error(e); process.exit(1); });'],
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_a_completed_work_offers_the_html_download_and_shows_the_last_export():
    run_node(r"""
let html = await UI.run('w1');
assert.ok(calls.some(call => call.path === '/works/w1/exports'));
assert.ok(has(html, 'data-action="gen-export" data-id="w1"') && has(html, '下載 HTML'));
assert.ok(has(html, '離線') && has(html, '不含人物設定'));  // 說明這個檔案是什麼、裡面沒有什麼
assert.ok(!has(html, '上次匯出'));
// 互動版：同一個動作，多帶 data-player="play"；旁邊說明它和閱讀版差在哪裡
assert.ok(has(html, 'data-action="gen-export" data-id="w1" data-player="play"') && has(html, '下載互動版'));
assert.equal(html.split('data-action="gen-export"').length - 1, 2);  // 兩顆按鈕：下載 HTML、下載互動版
assert.equal(html.split('data-player=').length - 1, 1);  // 原本那一顆不帶 player
assert.ok(html.indexOf('>下載 HTML</button>') < html.indexOf('>下載互動版</button>'));
assert.ok(has(html, '一次看一段') && has(html, '真心話') && has(html, '底牌'));
// play-2：作品頁的互動版按鈕多帶 data-interactive（下載前先準備互動內容）；說明寫出新的玩法
assert.ok(has(html, 'data-id="w1" data-player="play" data-interactive="1"'));
assert.equal(html.split('data-interactive=').length - 1, 1);  // 只有互動版那一顆
for (const word of ['視角', '偷看', '線索', '抉擇', '三個結局']) assert.ok(has(html, word), word);
assert.ok(!has(html, '可以開「真心話」'));  // 真心話不再是總開關

exportsReply = {available: true, items: [item]};
html = await UI.run('w1');
assert.ok(has(html, '上次匯出') && has(html, 'T(2026-11-11T10:00:00+00:00)') && has(html, '20.0 KB'));
""")


def test_the_section_covers_reading_and_playing_and_reading_here_asks_for_the_reading_export():
    """區塊標題涵蓋看與玩；多一顆「在這裡看」，原有的三顆（下載 HTML、下載互動版、在這裡玩）不變。
    「在這裡看」送的是和「下載 HTML」一樣的匯出請求（不帶 player、不準備互動內容），但不下載、不重畫整頁。
    （放進頁面上那個區塊的檢查在 tests/test_game_view.py，那裡有顯示區塊的替身。）"""
    run_node(r"""
const html = await UI.run('w1');
assert.ok(has(html, '<h2>看或玩</h2>') && !has(html, '<h2>下載 HTML</h2>'));
assert.ok(has(html, 'data-action="gen-view-here" data-id="w1"') && has(html, '>在這裡看</button>'));
assert.equal(html.split('data-action="gen-view-here"').length - 1, 1);
const order = ['>下載 HTML</button>', '>下載互動版</button>', '>在這裡看</button>', '>在這裡玩</button>'].map(text => html.indexOf(text));
assert.ok(order.every(at => at > 0) && order.join() === [...order].sort((a, b) => a - b).join());  // 下載的兩顆照原本的順序，看與玩排在一起
assert.ok(has(html, 'data-action="gen-play-here" data-id="w1" data-prepare="1"'));  // 「在這裡玩」照舊
assert.ok(has(html, '「在這裡看」') && has(html, '「在這裡玩」') && has(html, '不用下載'));  // 說明兩顆各是什麼

assert.equal(await UI.handleClick({dataset: {action: 'gen-view-here', id: 'w1'}}), true);
const writes = calls.filter(call => call.method === 'POST');
assert.deepEqual(writes.map(call => call.path), ['/works/w1/exports']);
assert.deepEqual(Object.keys(writes[0].body).sort(), ['format', 'request_id']);
assert.equal(writes[0].body.format, 'html');
assert.deepEqual(navigations, []);  // 沒有下載
assert.equal(renders, 0);
assert.deepEqual(toasts, []);
""")


def test_unfinished_works_and_environments_without_storage_do_not_offer_it():
    run_node(r"""
status = 'failed';
let html = await UI.run('w1');
assert.ok(!has(html, 'gen-export') && !calls.some(call => call.path === '/works/w1/exports'));  // 還沒完成：不顯示，也不查詢

status = 'completed'; exportsReply = {available: false, items: []};
html = await UI.run('w1');
assert.ok(!has(html, 'data-action="gen-export"') && has(html, '還沒有開放下載'));

exportsFail = true;  // 匯出清單讀不到：不擋住作品頁
html = await UI.run('w1');
assert.ok(has(html, '先做一小塊。') && !has(html, 'data-action="gen-export"'));
""")


def test_clicking_exports_first_and_then_downloads_that_export():
    run_node(r"""
await UI.run('w1');
const handled = await UI.handleClick({dataset: {action: 'gen-export', id: 'w1'}});
assert.equal(handled, true);
const sent = calls.find(call => call.path === '/works/w1/exports' && call.method === 'POST');
assert.equal(sent.body.format, 'html');
assert.ok(typeof sent.body.request_id === 'string' && sent.body.request_id.length > 0);
assert.deepEqual(Object.keys(sent.body).sort(), ['format', 'request_id']);  // 閱讀版的請求和加入互動版之前一樣，不帶 player
assert.deepEqual(navigations, ['/api/works/w1/exports/2/download']);  // 下載伺服器回傳的那一次匯出
assert.ok(toasts.some(message => message.includes('下載')));
assert.equal(renders, 1);  // 重新整理頁面，顯示「上次匯出」
""")


def test_clicking_the_play_button_prepares_the_interactive_layer_then_exports_and_downloads():
    """作品頁的「下載互動版」：先 POST /works/{id}/interactive 準備互動內容（期間提示正在準備），成功後照原本的流程
    POST 建立匯出（多帶 player: 'play'），再下載伺服器回的那一筆。"""
    run_node(r"""
await UI.run('w1');
const button = {dataset: {action: 'gen-export', id: 'w1', player: 'play', interactive: '1'}, textContent: '下載互動版'};
const handled = await UI.handleClick(button);
assert.equal(handled, true);
const writes = calls.filter(call => call.method === 'POST');
assert.deepEqual(writes.map(call => call.path), ['/works/w1/interactive', '/works/w1/exports']);  // 先準備互動內容，再匯出
assert.deepEqual(Object.keys(writes[0].body), ['request_id']);
assert.ok(typeof writes[0].body.request_id === 'string' && writes[0].body.request_id.includes('interactive'));
assert.deepEqual({...writes[1].body, request_id: null}, {request_id: null, format: 'html', player: 'play'});
assert.ok(typeof writes[1].body.request_id === 'string' && writes[1].body.request_id.includes('play'));  // 提交代碼和閱讀版的分開
assert.notEqual(writes[0].body.request_id, writes[1].body.request_id);
assert.deepEqual(navigations, ['/api/works/w1/exports/2/download']);
assert.equal(toasts[0], '正在準備互動內容（線索、抉擇與結局）…');  // 準備期間的提示
assert.equal(toasts[toasts.length - 1], '已開始下載互動版。');
assert.ok(!toasts.some(message => message.includes('沒有抉擇')));
assert.equal(button.textContent, '下載互動版');  // 等待時按鈕上的字會換掉，結束後還原
assert.equal(renders, 1);

await UI.handleClick({dataset: {action: 'gen-export', id: 'w1', player: 'movie', interactive: '1'}});  // 不認得的值不往後送：當成閱讀版
const last = calls.filter(call => call.path === '/works/w1/exports' && call.method === 'POST').pop();
assert.ok(!('player' in last.body));
await UI.handleClick({dataset: {action: 'gen-export', id: 'w1'}});
assert.equal(calls.filter(call => call.path === '/works/w1/interactive').length, 1);  // 閱讀版不準備互動內容
""")


def test_when_the_interactive_layer_cannot_be_prepared_the_play_version_still_downloads_without_decisions():
    """準備互動內容失敗（例如金額上限、模型暫時無法使用）：說明原因，改成直接匯出沒有抉擇的互動版，並告訴使用者稍後可以再下載一次。"""
    run_node(r"""
await UI.run('w1');
interactiveFail = '今天的 AI 用量已達上限，明天再試。';
const shown = [];
const button = {dataset: {action: 'gen-export', id: 'w1', player: 'play', interactive: '1'}, set textContent(value) { shown.push(value); }, get textContent() { return shown[shown.length - 1] ?? '下載互動版'; }};
assert.equal(await UI.handleClick(button), true);
const writes = calls.filter(call => call.method === 'POST');
assert.deepEqual(writes.map(call => call.path), ['/works/w1/interactive', '/works/w1/exports']);  // 準備失敗仍然匯出
assert.deepEqual({...writes[1].body, request_id: null}, {request_id: null, format: 'html', player: 'play'});
assert.deepEqual(navigations, ['/api/works/w1/exports/2/download']);
assert.equal(toasts[0], '正在準備互動內容（線索、抉擇與結局）…');
assert.ok(toasts.some(message => message.includes('今天的 AI 用量已達上限，明天再試。')));  // 提示原因
const last = toasts[toasts.length - 1];
assert.ok(last.includes('今天的 AI 用量已達上限，明天再試。') && last.includes('這次的互動版沒有抉擇與線索，稍後可以再下載一次'));
assert.ok(!toasts.includes('已開始下載互動版。'));
assert.ok(shown.length >= 2 && shown[0].includes('準備') && shown[shown.length - 1] === '下載互動版');  // 按鈕上的字還原
assert.equal(renders, 1);
""")


def test_a_play_button_without_the_interactive_mark_exports_as_before():
    """沒有 data-interactive 的互動版按鈕（多章節作品總覽的那一顆）：不呼叫準備互動內容的端點，照原本的流程匯出。"""
    run_node(r"""
await UI.run('w1');
assert.equal(await UI.handleClick({dataset: {action: 'gen-export', id: 'w1', player: 'play'}}), true);
assert.deepEqual(calls.filter(call => call.method === 'POST').map(call => call.path), ['/works/w1/exports']);
assert.deepEqual(navigations, ['/api/works/w1/exports/2/download']);
assert.deepEqual(toasts, ['已開始下載互動版。']);
""")


def test_work_page_opens_with_the_premise_before_the_first_segment():
    """作品頁先顯示開場白（規劃時寫的 premise），再顯示段落：觀眾在第一段之前就知道看點（2026-11-12）。"""
    run_node(r"""
const base = detail('completed');
const withPlan = plan => ({...base, plan});
const planApi = reply => async path => path === '/generation/runs/w1' ? reply : path === '/generation/status' ? {available: true, background: true} : {available: true, items: []};
const context = {state: {renderGeneration: 1}, esc,
  link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1><p>${esc(subtitle)}</p>${action}`, empty: m => m, time: x => x, toast() {}, requestId: () => 'rid', render: async () => {}, navigate() {}};
UI.initialize({...context, api: planApi(withPlan({title: '宴', premise: '鴻門宴搬到商場 <b>：他能不簽字走出會館嗎？', beats: []}))});
let html = await UI.run('w1');
assert.ok(has(html, 'class="callout gen-premise"') && has(html, '開場'));
assert.ok(has(html, '鴻門宴搬到商場 &lt;b&gt;：他能不簽字走出會館嗎？') && !has(html, '<b>：'));  // 內容跳脫
assert.ok(html.indexOf('gen-premise') < html.indexOf('gen-segments'));  // 在第一段之前

UI.initialize({...context, api: planApi(withPlan(null))});   // 還在規劃：沒有開場白
html = await UI.run('w1');
assert.ok(!has(html, 'gen-premise'));
UI.initialize({...context, api: planApi(withPlan({title: '宴', premise: '', beats: []}))});   // 舊作品沒有寫前提
html = await UI.run('w1');
assert.ok(!has(html, 'gen-premise'));
""")


def test_work_page_distinguishes_people_sides_and_acts_and_ends_with_the_teaser():
    """人物多的時候要分得出個人、團體與關鍵情節（2026-11-12 使用者的要求）：
    個人＝依陣容順序的顏色；團體＝規劃標出的陣營；關鍵情節＝每一幕的幕名與起承轉合，轉折那一幕特別標出來。
    故事沒有完全了結時，完成後在最後顯示「敬請期待下集」與預告。規劃用的 goal 不顯示（會劇透）。"""
    run_node(r"""
const plan = {title: '宴', genre: '職場', premise: '開場的話', teaser: '真正的買家才要現身 <b>。',
  sides: [{name: '集團 <i>', members: ['c2']}, {name: '小公司', members: ['c1']}],
  beats: [{beat_no: 1, title: '慶功宴', kind: 'setup', goal: '不該顯示的規劃內容'}, {beat_no: 2, title: '闖進來的人 <u>', kind: 'turn', goal: '另一段規劃'}]};
const cast = [{id: 'c1', name: '羅映川', source: 'person', version: 3, is_user: false}, {id: 'c2', name: '沈知衡', source: 'person', version: 3, is_user: false}];
const seg = (turn_no, beat_no, speaker_id, speaker_name) => ({turn_no, beat_no, speaker_id, speaker_name, is_user: false, line: '台詞' + turn_no, action: '', stage_direction: ''});
const full = status => ({...detail(status), cast, plan, segments: [seg(1, 1, 'c2', '沈知衡'), seg(2, 1, 'c1', '羅映川'), seg(3, 2, 'c2', '沈知衡')]});
const context = reply => ({state: {renderGeneration: 1}, esc,
  api: async path => path === '/generation/runs/w1' ? reply : path === '/generation/status' ? {available: true, background: true} : {available: true, items: []},
  link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1><p>${esc(subtitle)}</p>${action}`, empty: m => m, time: x => x, toast() {}, requestId: () => 'rid', render: async () => {}, navigate() {}});
UI.initialize(context(full('completed')));
let html = await UI.run('w1');
// 個人：c1 是陣容第 1 位、c2 是第 2 位；團體：名稱旁的陣營標籤
assert.ok(/class="gen-seg gen-c2"[^>]*>\s*<strong>沈知衡<\/strong>\s*<span class="gen-side">集團 &lt;i&gt;<\/span>/.test(html));
assert.ok(/class="gen-seg gen-c1"[^>]*>\s*<strong>羅映川<\/strong>\s*<span class="gen-side">小公司<\/span>/.test(html));
// 關鍵情節：每一幕開頭有幕名與起承轉合；轉折那一幕有自己的樣式
assert.ok(has(html, '<li class="gen-beat"><span class="gen-kind">起</span>慶功宴</li>'));
assert.ok(has(html, '<li class="gen-beat gen-beat-turn"><span class="gen-kind">轉</span>闖進來的人 &lt;u&gt;</li>'));
assert.ok(html.indexOf('闖進來的人') > html.indexOf('台詞2') && html.indexOf('闖進來的人') < html.indexOf('台詞3'));  // 幕名在那一幕的第一段之前
assert.ok(!has(html, '不該顯示的規劃內容') && !has(html, '另一段規劃'));
assert.ok(has(html, 'value="3"'));  // 幕名佔了一列，段落仍然照自己的段號編號
// 類型與開場白；完成後的下集預告
assert.ok(has(html, '<span class="gen-genre">職場</span>') && has(html, '開場的話'));
assert.ok(has(html, 'class="callout gen-teaser"') && has(html, '敬請期待下集') && has(html, '真正的買家才要現身 &lt;b&gt;。'));
assert.ok(html.indexOf('gen-teaser') > html.indexOf('台詞3'));

UI.initialize(context(full('running')));   // 還在生成：不顯示下集預告
html = await UI.run('w1');
assert.ok(!has(html, 'gen-teaser') && has(html, 'gen-beat'));

UI.initialize(context({...detail('completed'), plan: {title: '舊', premise: '', beats: [{beat_no: 1, goal: '舊作品的節拍'}]}}));   // 舊作品：沒有這些欄位
html = await UI.run('w1');
assert.ok(!has(html, 'gen-beat') && !has(html, 'gen-side') && !has(html, 'gen-teaser') && !has(html, 'gen-genre') && has(html, '先做一小塊。'));
""")
