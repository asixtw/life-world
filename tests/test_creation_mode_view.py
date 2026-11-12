"""建立新作品最上面的「玩法」：只有一個建立入口，第一步選「看的故事」或「玩的遊戲」（2026-11-12）。

以 Node 直接執行 app/static/creation.js（假的 API、假的儲存與事件，不開任何網站），檢查產生的 HTML 與送出的請求：
1. 預設是「看的故事」：除了多出「玩法」那一塊，畫面和加入玩法之前完全相同（雜湊在加入之前記下），送出的請求也相同。
2. 「玩法」是兩個原生的單選按鈕，在 ① 人物上方；各有一行說明；不佔節點的編號。
3. 選「玩的遊戲」：同一頁只顯示這個玩法需要的節點與欄位（人物 1～3 位、稱呼、行程說明、題材、起點、時數、出發時間、標題）。
4. 兩種玩法來回切換，兩邊填過的內容都還在；重新整理（讀回草稿）也在。
5. 玩的遊戲不能開始的原因寫清楚：AI 沒有設定、沒選人、超過 3 位、沒寫說明、出發時間不對。
6. 開始：送 POST /api/games（內容照共同規格），等待時按鈕停用並說明正在規劃，成功後到 #game/{id}；
   失敗時顯示伺服器的訊息、內容都留著；等待中再按一次不會送出第二次；等待中登出，回應回來之後不動這一頁。
7. 舊的 #game-new：主程式換成建立頁並預選「玩的遊戲」。
第 3、5、6 項的檢查點原本在 tests/test_game_view.py（獨立的 #game-new 表單），表單併進建立頁之後搬到這裡。
這是開發時的快速檢查；實際畫面以部署後在 Local 8030（Cloud SQL life_world_e2e）的 Chrome 操作為準。
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SETUP = r"""
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const store = new Map(), listeners = {}, root = {innerHTML: ''}, replaced = [];
globalThis.window = globalThis; globalThis.history = {replaceState(a, b, url) { replaced.push(url); }};
globalThis.matchMedia = () => ({matches: false});
globalThis.sessionStorage = {getItem: k => store.has(k) ? store.get(k) : null, setItem: (k, v) => { store.set(k, String(v)); }, removeItem: k => { store.delete(k); }};
globalThis.document = {addEventListener: (type, fn) => { listeners[type] = fn; }, getElementById: id => id === 'create-root' ? root : null, querySelector: () => null};
require('./app/static/creation.js');
const UI = window.CreationUI;
const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch]));
const persona = {persona: {work_id: 'sp', version_no: 2, revision: 2, content: {display_name: '小光'}}, consent: {id: 'k1'}, consent_text: '同意文字'};
const cards = [{id: 'card1', title: '舊卡甲', current_version: 1, content: {tagline: '舊卡的簡介'}}, {id: 'card2', title: '舊卡乙', current_version: 3, content: {}}];
const catalog = {styles: [{id: 'warm', label: '溫暖'}, {id: 'noir', label: '冷硬'}], scene_presets: [{id: 'harbor', title: '港口', description: '深夜的港口倉庫。'}],
  outputs: [{type: 'text', label: '文字', available: true}, {type: 'image', label: '圖片', available: false, note: '尚未開放'}],
  lengths: [{id: 'short', label: '短（約 8 段）'}, {id: 'medium', label: '中（約 16 段）'}], forms: [{id: 'script', label: '劇本對白'}, {id: 'narrative', label: '小說敘事'}],
  positions: [], adherence: [], limits: {max_participants: 4, max_materials: 3, max_conditions: 8}};
let people = {enabled: true, items: [
  {id: 'p-a', name: '何以晴 <b>', description: '愛吃、行動派', person_type: 'fictional', person_subtype: 'original', roles: [], profile: {id: 'prof-a', version: 3}},
  {id: 'p-b', name: '溫若岑', description: '', person_type: 'real', person_subtype: null, roles: ['朋友'], profile: {id: 'prof-b', version: 1}},
  {id: 'p-c', name: '沈知衡', description: '', person_type: 'real', person_subtype: null, roles: [], profile: {id: 'prof-c', version: 2}},
  {id: 'p-d', name: '羅映川', description: '', person_type: 'fictional', person_subtype: 'original', roles: [], profile: {id: 'prof-d', version: 1}},
  {id: 'p-e', name: '還沒設定的人', description: '', person_type: 'real', person_subtype: 'historical', roles: [], profile: null}]};
let available = true, createReply = null;
const calls = [], navigated = [], toasts = [], ids = [];
const state = {renderGeneration: 1, me: {owner_id: 'o1'}, dirty: true};
const api = async (path, options = {}) => {
  calls.push({path, method: options.method || 'GET', body: options.body});
  if (path === '/characters?status=active') return {items: cards};
  if (path === '/self-persona') return persona;
  if (path === '/generation/catalog') return catalog;
  if (path === '/generation/status') return {available, provider_kind: 'live', background: true};
  if (path === '/generation/people') return people;
  if (path === '/generation/runs') return {id: 'w9'};
  if (path === '/games' && options.method === 'POST') return createReply ? createReply() : {id: 'g1', title: '海線', build: {status: 'building', done: 1, total: 3}};
  return {};
};
const fail = (message, status) => () => { const error = new Error(message); error.status = status; throw error; };
const context = {state, api, esc,
  link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1><p>${esc(subtitle)}</p>${action}`, empty: m => `<div class="empty">${esc(m)}</div>`,
  time: x => x, toast: m => toasts.push(m), requestId: (scope, body) => { ids.push({scope, body}); return 'rid:' + scope; }, render: async () => {}, navigate: route => navigated.push(route)};
// 進入建立頁：先當成剛登入（記憶體裡沒有草稿），草稿從假的 sessionStorage 讀回
const open = async (query = '') => { UI.forget(); UI.initialize(context); return UI.view(new URLSearchParams(query)); };
const again = () => UI.view(new URLSearchParams(''));  // 留在同一頁重新讀取：拿到依目前草稿畫出來的整頁
// 事件的替身：勾選、單選、下拉選單（change），文字輸入（input）
const tick = (bind, value, checked = true, dataset = {}) => listeners.change({type: 'change', target: {closest: () => true, dataset: {bind, ...dataset}, value, checked, type: 'checkbox', tagName: 'INPUT'}});
const radio = (bind, value) => listeners.change({type: 'change', target: {closest: () => true, dataset: {bind}, value, checked: true, type: 'radio', tagName: 'INPUT'}});
const pick = (bind, value, dataset = {}) => listeners.change({type: 'change', target: {closest: () => true, dataset: {bind, ...dataset}, value, type: 'select-one', tagName: 'SELECT'}});
const typed = (bind, value, type = 'text') => listeners.input({type: 'input', target: {closest: sel => sel === '#create-root', dataset: {bind}, value, type, tagName: type === 'textarea' ? 'TEXTAREA' : 'INPUT'}});
const click = (action, dataset = {}) => UI.handleClick({dataset: {action, ...dataset}});
const has = (html, text) => html.includes(text);
const count = (html, text) => html.split(text).length - 1;
const posts = path => calls.filter(call => call.path === path && call.method === 'POST');
const startButton = html => (html.match(/<button[^>]*data-action="cr-start"[^>]*>[^<]*<\/button>/) || [''])[0];
const MODE_BLOCK = /<section class="card create-mode"[\s\S]*?<\/section>/g;  // 「玩法」那一塊
(async () => {
"""

# 「看的故事」的一趟完整操作：各階段的畫面（去掉「玩法」那一塊之後取雜湊）與最後送出的請求。
# 加入玩法之前（2026-11-12）用同一段程式跑出下面的 STORY_BASELINE；之後每次都要和它一樣。
STORY_FLOW = r"""
const sha = html => crypto.createHash('sha256').update(html.replace(MODE_BLOCK, '')).digest('hex');
const shots = {};
shots.initial = sha(await open());
tick('person', 'p-a'); tick('person', 'p-b');
await click('cr-sub', {sub: 'positions'});
pick('position', 'supporting', {id: 'p-a'});
await click('cr-sub', {sub: 'cards'});
tick('card', 'card2', true, {version: '3'});
shots.people = sha(root.innerHTML);
await click('cr-next', {from: 'participants', to: 'scene'});
typed('scene.description', '週六午後的試作桌。', 'textarea');
await click('cr-sub', {sub: 'start'});
typed('scene.event', '門鈴響了。', 'textarea');
await click('cr-sub', {sub: 'conditions'});
typed('scene.conditions', '不能離開試作桌\n只有一把剪刀', 'textarea');
shots.scene = sha(await again());
await click('cr-toggle', {node: 'style'});
tick('style', 'warm');
typed('styleNotes', '慢節奏');
await click('cr-toggle', {node: 'output'});
pick('output.length', 'medium');
radio('output.form', 'narrative');
await click('cr-add-direction');
radio('direction.adherence', 'free');
typed('direction.notes', '多一點沉默', 'textarea');
typed('title', '試作桌');
shots.full = sha(await again());
await click('cr-start');
const sent = posts('/generation/runs');
shots.after = sha(await again());  // 開始之後草稿清空
people = {enabled: false, items: []};  // 沒有人物系統的環境：只有角色卡
shots.legacy = sha(await open());
"""

STORY_BASELINE = {
    'initial': '319387305dd30a23c4c81374d096f033a2bb5471235643e58cb653cb6a5818c1',  # 剛進來：只展開 ① 人物
    'people': '7423cc365bb0d4e17885ed4a2363764a45c99130c549f3422c0cf94df0f4d70f',  # 兩位人物、一張舊角色卡、角色定位
    'scene': 'a2aded495a47a4090448f21cb82d1cb8d362e08e73b5cfa3e8581aa302e7671f',  # ② 場景：描述、劇情起點、場景條件
    'full': '958b8fca5981703740a42fa2dcd0364c7c79960a5287d361d91c2a429b2df77c',  # 風格、輸出、演出要求、標題都填了
    'after': '319387305dd30a23c4c81374d096f033a2bb5471235643e58cb653cb6a5818c1',  # 開始之後草稿清空：和剛進來一樣
    'legacy': 'e5bf00481f14701651279d9a7fbf4f1a5bc531e610e3cd36b1a25af9e32eceda',  # 沒有人物系統的環境
}

# 「看的故事」送出的請求（加入玩法之前記下的內容）
STORY_REQUEST = r"""{request_id: 'rid:create-run', setup: {
  participants: [{source: 'person', ref: {person_id: 'p-a', profile_id: 'prof-a'}, position: 'supporting'}, {source: 'person', ref: {person_id: 'p-b', profile_id: 'prof-b'}},
    {source: 'card', ref: {work_id: 'card2', version_no: 3}}],
  include_me: true, title: '試作桌',
  scene_context: {description: '週六午後的試作桌。', start: {event: '門鈴響了。', goal: ''}, conditions: ['不能離開試作桌', '只有一把剪刀'], shared_history_refs: []},
  style_profile: {style_ids: ['warm'], notes: '慢節奏'}, output: {type: 'text', text: {length: 'medium', form: 'narrative'}},
  direction: {adherence: 'free', notes: '多一點沉默', avoid: ''}}}"""


def run_node(script):
    node = os.environ.get('LIFEWORLD_NODE') or shutil.which('node')
    if not node:
        pytest.skip('需要 Node 執行前端模組；可設定 LIFEWORLD_NODE')
    result = subprocess.run([node, '-e', SETUP + script + '\n})().catch(e => { console.error(e); process.exit(1); });'],
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_story_is_the_default_and_its_page_and_request_are_the_same_as_before_the_mode_was_added():
    """預設玩法（看的故事）：各階段的畫面去掉「玩法」那一塊之後，和加入玩法之前逐字相同；送出的請求也相同。"""
    checks = '\n'.join(f"assert.equal(shots.{name}, '{digest}', '{name}：畫面和加入玩法之前不同');" for name, digest in STORY_BASELINE.items())
    run_node(STORY_FLOW + checks + r"""
assert.equal(sent.length, 1);
assert.deepEqual(sent[0].body, """ + STORY_REQUEST + r""");
assert.deepEqual(navigated, ['run/w9']);
assert.equal(state.dirty, false);
assert.ok(!calls.some(call => call.path === '/games'));  // 看的故事不會碰到建立遊戲的端點
""")


def test_the_mode_is_two_native_radios_above_the_people_node_with_story_preselected():
    run_node(r"""
const html = await open();
assert.equal(count(html, 'class="card create-mode"'), 1);
const block = html.match(MODE_BLOCK)[0];
// 兩個原生的單選按鈕，同一組（name 相同）；預設選「看的故事」
assert.equal(count(block, '<input type="radio" name="create-mode" data-bind="mode"'), 2);
assert.ok(/<input type="radio" name="create-mode" data-bind="mode" value="story" checked>/.test(block));
assert.ok(/<input type="radio" name="create-mode" data-bind="mode" value="game" >/.test(block));
assert.ok(has(block, '<legend>玩法</legend>') && has(block, '<strong>看的故事</strong>') && has(block, '<strong>玩的遊戲</strong>'));
// 每個選項一行說明
assert.ok(has(block, 'AI 把整個劇情演完') && has(block, '你每回合做選擇') && has(block, '角色依個性反應') && has(block, '數值決定結局'));
assert.ok(has(block, '到作品頁再選'));  // 呈現方式不在這裡問
assert.equal(count(block, '<label class="play-choice">'), 2);  // 每個選項整列都在 label 裡：點文字也選得到
// 在 ① 人物上方，而且不是節點：既有節點的數量與編號不變
assert.ok(html.indexOf('class="card create-mode"') < html.indexOf('① 人物'));
assert.ok(html.indexOf('class="create-tree"') < html.indexOf('class="card create-mode"'));
assert.equal(count(html, 'class="card create-node'), 4);
for (const title of ['① 人物', '② 場景', '③ 風格', '④ 輸出', '⑦ 開始生成']) assert.ok(has(html, title), title);
assert.ok(!has(block, 'create-node') && !has(block, '<button'));
""")


def test_the_game_mode_shows_only_the_nodes_and_fields_the_game_needs():
    """原本 #game-new 表單的檢查點（列出人物、有人物設定才能勾、各欄位與預設值），現在在建立頁選了「玩的遊戲」之後檢查。"""
    run_node(r"""
assert.ok(has(await open(), 'href="#works"'));  // 回作品的連結
radio('mode', 'game');
let html = root.innerHTML;
assert.ok(/<input type="radio" name="create-mode" data-bind="mode" value="game" checked>/.test(html));
assert.ok(/<input type="radio" name="create-mode" data-bind="mode" value="story" >/.test(html));
assert.ok(calls.some(call => call.path === '/generation/people'));
// ① 人物：只列人物，1～3 位。有人物設定的可以勾；沒有的不能勾，並指到人物頁
assert.ok(has(html, '同行的人（選 1～3 位）'));
assert.equal(count(html, 'data-bind="person"'), 5);
assert.ok(/<input type="checkbox" data-bind="person" value="p-a" {2}>/.test(html) && has(html, '何以晴 &lt;b&gt;') && !has(html, '何以晴 <b>'));
assert.ok(has(html, '人物設定第 3 版') && has(html, '愛吃、行動派') && has(html, '朋友'));
assert.ok(/data-bind="person" value="p-e"[^>]*disabled>/.test(html) && has(html, '還沒有人物設定') && has(html, 'href="#persons/p-e"'));
// 不顯示舊角色卡、「包含我」與角色定位
assert.ok(!has(html, 'data-bind="card"') && !has(html, '舊角色卡') && !has(html, 'data-bind="me"') && !has(html, '包含我') && !has(html, '角色定位'));
assert.ok(!has(html, 'AI 參與人物'));
// 稱呼：選填，預設「你」
assert.ok(/<input id="create-player" data-bind="game.playerName" maxlength="20" placeholder="你" value="">/.test(html) && has(html, '預設「你」'));
assert.ok(has(html, '同行的人物：0 位（需要 1～3 位）'));
// 只有 ① 人物與 ② 場景兩個節點：沒有風格、輸出、素材、演出要求
assert.equal(count(html, 'class="card create-node'), 2);
assert.ok(has(html, '① 人物') && has(html, '② 場景'));
for (const gone of ['③ 風格', '④ 輸出', '⑤ 素材', '⑥ 演出要求', '加入素材', '加入演出要求', 'data-bind="output.type"', 'data-bind="style"']) assert.ok(!has(html, gone), gone);

tick('person', 'p-a'); tick('person', 'p-b');  // 選了人：② 場景自動展開
html = root.innerHTML;
assert.ok(has(html, '同行的人物：2 位（需要 1～3 位）'));
// ② 場景：場景描述沿用同一個欄位，提示換成行程用的；沒有範例場景、劇情起點、場景條件
assert.ok(/<textarea id="create-scene" data-bind="scene.description" maxlength="2000" rows="5"/.test(html));
assert.ok(has(html, '候選地點與營業時間') && has(html, '虛構的地方'));
for (const gone of ['範例場景', '劇情起點', '場景條件', 'create-preset', 'create-event', 'create-goal', 'create-conditions', '港口倉庫']) assert.ok(!has(html, gone), gone);
// 題材：下拉選單，目前只有「行程」，並註明之後會有更多
assert.ok(has(html, '<select id="create-skin" data-bind="game.skin"><option value="trip" selected>行程</option></select>') && has(html, '之後會有更多題材'));
// 起點、可用時數、出發時間與預設值
assert.ok(/<input id="create-start-place" data-bind="game.startPlace" maxlength="40" value="車站">/.test(html));
assert.ok(has(html, '<select id="create-hours" data-bind="game.hours">') && has(html, '<option value="8" >8 小時</option>')
  && has(html, '<option value="10" selected>10 小時</option>') && has(html, '<option value="12" >12 小時</option>'));
assert.ok(/<input id="create-start-time" data-bind="game.startTime" type="time" value="08:00">/.test(html));
// 開始生成的面板：摘要是這個玩法的項目；標題照舊；說明會呼叫幾次模型（不再是「自動判斷」）
assert.ok(has(html, '⑦ 開始生成'));
assert.ok(has(html, '<dt>人物</dt><dd>何以晴 &lt;b&gt;、溫若岑（2 位）</dd>') && has(html, '<dt>行程說明</dt><dd>尚未填寫</dd>'));
assert.ok(has(html, '<dt>題材</dt><dd>行程</dd>') && has(html, '<dt>時數與出發時間</dt><dd>10 小時・08:00 出發</dd>'));
for (const gone of ['<dt>風格</dt>', '<dt>輸出</dt>', '<dt>場景</dt>', '<dt>素材</dt>', '<dt>演出要求</dt>']) assert.ok(!has(html, gone), gone);
assert.ok(/<input id="create-title" data-bind="title" maxlength="60" value="">/.test(html));
assert.ok(!has(html, '自動判斷'));
assert.ok(has(html, '<p class="create-module" aria-live="polite">會呼叫模型 3 次：規劃 1 次，加上 2 位同行者各 1 次。</p>'));
assert.ok(has(startButton(html), '>開始生成</button>'));

// 人物很多的時候，和看的故事一樣有搜尋框
people = {enabled: true, items: [...people.items, ...Array.from({length: 5}, (_, i) => ({id: 'x' + i, name: '路人' + i, description: '', person_type: 'real', roles: [], profile: {id: 'px' + i, version: 1}}))]};
assert.ok(has(await again(), 'data-bind="personFilter"'));
""")


def test_switching_modes_keeps_what_was_filled_on_both_sides():
    run_node(r"""
await open();
// 看的故事：兩位人物、一張舊角色卡、包含我（預設）、角色定位、場景、劇情起點、風格、標題
tick('person', 'p-a'); tick('person', 'p-b');
await click('cr-sub', {sub: 'cards'});
tick('card', 'card2', true, {version: '3'});
await click('cr-sub', {sub: 'positions'});
pick('position', 'advisor', {id: 'p-b'});
typed('scene.description', '週六午後的試作桌。', 'textarea');
await click('cr-sub', {sub: 'start'});
typed('scene.event', '門鈴響了。', 'textarea');
await click('cr-toggle', {node: 'style'});
tick('style', 'warm');
typed('title', '試作桌');

radio('mode', 'game');  // 切到玩的遊戲：人物、場景描述與標題是同一個欄位，帶過來
let html = root.innerHTML;
assert.ok(/data-bind="person" value="p-a"[^>]*checked/.test(html) && /data-bind="person" value="p-b"[^>]*checked/.test(html));
assert.ok(has(html, '>週六午後的試作桌。</textarea>') && has(html, 'maxlength="60" value="試作桌"'));
assert.ok(!has(html, 'data-bind="card"') && !has(html, '門鈴響了。') && !has(html, '溫暖'));
typed('game.playerName', '小光');
typed('game.startPlace', '火車站');
pick('game.hours', '12');
typed('game.startTime', '09:30', 'time');
typed('scene.description', '週六去海邊小鎮。', 'textarea');

radio('mode', 'story');  // 切回看的故事：這個玩法專用的內容都還在；共用的欄位是剛才改過的
html = root.innerHTML;
assert.ok(/<input type="radio" name="create-mode" data-bind="mode" value="story" checked>/.test(html));
assert.ok(/data-bind="card" value="card2"[^>]*checked/.test(html) && /data-bind="me" checked/.test(html));
assert.ok(/data-bind="position" data-id="p-b"[\s\S]*?<option value="advisor" selected>/.test(html));
assert.ok(has(html, '>門鈴響了。</textarea>') && has(html, 'value="warm" checked'));
assert.ok(has(html, '>週六去海邊小鎮。</textarea>') && has(html, '<dt>風格</dt><dd>溫暖</dd>'));
assert.ok(has(html, 'AI 參與人物：4 位（多人文字）') && has(html, '自動判斷：多人文字（4 位）'));
assert.ok(!has(html, 'create-player') && !has(html, 'create-hours'));

radio('mode', 'game');  // 再切回玩的遊戲：稱呼、起點、時數、出發時間都還在
html = root.innerHTML;
assert.ok(has(html, 'placeholder="你" value="小光"') && has(html, 'maxlength="40" value="火車站"'));
assert.ok(has(html, '<option value="12" selected>12 小時</option>') && has(html, '<option value="10" >10 小時</option>') && has(html, 'type="time" value="09:30"'));
assert.ok(has(html, '<dt>時數與出發時間</dt><dd>12 小時・09:30 出發</dd>'));

// 重新整理（草稿從 sessionStorage 讀回）：玩法與兩邊的內容都在
html = await open();
assert.ok(/value="game" checked/.test(html) && has(html, 'value="小光"') && has(html, 'value="火車站"') && has(html, 'type="time" value="09:30"'));
radio('mode', 'story');
assert.ok(/data-bind="card" value="card2"[^>]*checked/.test(root.innerHTML) && has(root.innerHTML, '>門鈴響了。</textarea>'));

// 「清除重來」：回到預設的看的故事
await click('cr-reset');
assert.ok(/value="story" checked/.test(root.innerHTML) && !/data-bind="person" value="p-a"[^>]*checked/.test(root.innerHTML));
""")


def test_the_game_mode_says_exactly_why_it_cannot_start():
    """原本表單的檢查點「沒有選人、選太多人：不送出，直接說明」「AI 生成沒有設定：說明原因，不能送出」，加上沒寫說明與出發時間不對。"""
    run_node(r"""
const reason = () => (root.innerHTML.match(/<p class="small muted" role="status">([^<]*)<\/p>/) || [])[1];
const blocked = async why => {
  assert.equal(reason(), why);
  assert.ok(/data-action="cr-start" disabled>/.test(startButton(root.innerHTML)), why);
  await click('cr-start');  // 就算按鈕被按到，也不送出
  assert.equal(posts('/games').length, 0, why);
};
await open();
radio('mode', 'game');
await blocked('請在 ① 人物選 1～3 位同行的人物。');
assert.ok(has(root.innerHTML, '會呼叫模型：規劃 1 次，加上每位同行者各 1 次。'));  // 還沒選人：先說明規則
tick('person', 'p-a');
await blocked('請在 ② 場景寫下這趟行程的說明。');
typed('scene.description', '   ', 'textarea');  // 只有空白不算
await click('cr-sub', {sub: 'x'});
await blocked('請在 ② 場景寫下這趟行程的說明。');
typed('scene.description', '隨便走走', 'textarea');
tick('person', 'p-b'); tick('person', 'p-c'); tick('person', 'p-d');  // 四位：超過上限
await blocked('玩的遊戲最多 3 位同行的人物，目前選了 4 位，請取消 1 位。');
assert.ok(has(root.innerHTML, '<p class="callout">同行的人物：4 位（需要 1～3 位）。</p>'));
tick('person', 'p-d', false);
typed('game.startTime', '25:00', 'time');  // 不支援時間欄位的瀏覽器可能打出不合格的時間
await click('cr-sub', {sub: 'x'});
await blocked('出發時間請填 24 小時制的時與分，例如 08:00。');
typed('game.startTime', '08:30', 'time');
await click('cr-sub', {sub: 'x'});
assert.equal(reason(), undefined);  // 都齊了：可以開始
assert.ok(/data-action="cr-start" >開始生成<\/button>/.test(startButton(root.innerHTML)));
assert.ok(has(root.innerHTML, '會呼叫模型 4 次：規劃 1 次，加上 3 位同行者各 1 次。'));

available = false;  // AI 生成沒有設定：說明原因，不能送出
await again();
await click('cr-sub', {sub: 'x'});
await blocked('AI 生成尚未設定，暫時無法開始。');
""")


def test_starting_a_game_sends_the_contract_body_explains_the_wait_and_opens_the_game_page():
    """原本表單的檢查點：送出的內容照共同規格；等待時說明正在規劃、按鈕停用；建立後到遊戲頁；選填的沒有填就用預設值。"""
    run_node(r"""
await open();
radio('mode', 'game');
tick('person', 'p-a'); tick('person', 'p-b');
typed('game.playerName', ' 小光 ');
typed('scene.description', ' 週六去海邊小鎮。\n山城咖啡 10:00–17:00 ', 'textarea');
typed('game.startPlace', ' 火車站 ');
pick('game.hours', '12');
typed('game.startTime', '09:30', 'time');
typed('title', ' 海線 ');
let during = null;
createReply = () => { during = root.innerHTML; return {id: 'g 1', title: '海線', build: {status: 'building', done: 1, total: 3}}; };
assert.equal(await click('cr-start'), true);
const sent = posts('/games');
assert.equal(sent.length, 1);
assert.deepEqual(sent[0].body, {request_id: 'rid:game-new', skin: 'trip',
  participants: [{person_id: 'p-a', profile_id: 'prof-a'}, {person_id: 'p-b', profile_id: 'prof-b'}], player: {name: '小光'},
  description: '週六去海邊小鎮。\n山城咖啡 10:00–17:00', start_place: '火車站', hours: 12, start_time: '09:30', title: '海線'});
// 提交代碼依內容決定（主程式對相同內容回同一個代碼）：連線中斷後再按一次，不會規劃出兩件
const asked = ids.filter(item => item.scope === 'game-new');
assert.equal(asked.length, 1);
assert.deepEqual({...asked[0].body, request_id: 'rid:game-new'}, sent[0].body);
assert.ok(!posts('/generation/runs').length);  // 不會建立看的故事
// 等待時：說明正在規劃，按鈕停用、字換成「規劃中…」
assert.ok(has(during, '正在規劃') && /data-action="cr-start" disabled>規劃中…<\/button>/.test(startButton(during)));
assert.ok(has(during, '<dt>行程說明</dt><dd>週六去海邊小鎮。') && has(during, 'value=" 小光 "'));  // 等待中內容還在畫面上
assert.deepEqual(navigated, ['game/g%201']);  // 建立後到遊戲頁（那一頁接著跑生成進度）
assert.equal(state.dirty, false);
// 建立之後草稿清空（和看的故事一樣）：再進來是預設的玩法，沒有勾選任何人
const html = await again();
assert.ok(/value="story" checked/.test(html) && !/data-bind="person" value="p-a"[^>]*checked/.test(html));

// 選填的都沒有填：稱呼不送（伺服器用預設的「你」）、起點與時間用預設值、標題留白；沒有人物設定代號就只送人物
people = {enabled: true, items: people.items.map(item => item.id === 'p-c' ? {...item, profile: {version: 2}} : item)};
await again();
radio('mode', 'game');
tick('person', 'p-c');
typed('scene.description', '隨便走走', 'textarea');
typed('game.startPlace', '   ');
typed('game.startTime', '', 'time');
pick('game.hours', '');
createReply = null;
await click('cr-start');
assert.deepEqual(posts('/games')[1].body, {request_id: 'rid:game-new', skin: 'trip', participants: [{person_id: 'p-c'}], player: {},
  description: '隨便走走', start_place: '車站', hours: 10, start_time: '08:00', title: ''});
assert.deepEqual(navigated, ['game/g%201', 'game/g1']);
""")


def test_a_failed_start_shows_the_server_message_and_keeps_everything():
    """原本表單的檢查點：失敗時顯示伺服器的訊息、內容都留著，可以直接再送。"""
    run_node(r"""
await open();
radio('mode', 'game');
tick('person', 'p-a');
typed('game.playerName', '小光');
typed('scene.description', '週六去海邊小鎮。', 'textarea');
typed('title', '海線');
createReply = fail('今天的 AI 用量已達上限，明天再試。', 429);
assert.equal(await click('cr-start'), true);  // 錯誤在這一頁說明，不往外丟
let html = root.innerHTML;
assert.ok(has(html, '<p class="callout gen-error" role="alert">今天的 AI 用量已達上限，明天再試。</p>'));  // 伺服器的訊息
assert.ok(/data-action="cr-start" >開始生成<\/button>/.test(startButton(html)));  // 按鈕還原，可以再按
assert.deepEqual(navigated, []);
// 內容都留著（畫面上與草稿裡）
assert.ok(/value="game" checked/.test(html) && /data-bind="person" value="p-a"[^>]*checked/.test(html));
assert.ok(has(html, 'value="小光"') && has(html, '>週六去海邊小鎮。</textarea>') && has(html, 'value="海線"'));
html = await open();
assert.ok(/value="game" checked/.test(html) && has(html, 'value="小光"') && has(html, '>週六去海邊小鎮。</textarea>'));
assert.ok(!has(html, '今天的 AI 用量已達上限'));  // 重新進來：上一次的錯誤訊息不留著

// 沒有訊息的失敗也要說明；之後再按一次成功，訊息收掉並前往遊戲頁
createReply = () => { throw {}; };
await click('cr-start');
assert.ok(has(root.innerHTML, 'role="alert">規劃沒有完成，請稍後再試一次。</p>'));
createReply = null;
await click('cr-start');
assert.equal(posts('/games').length, 3);
assert.deepEqual(navigated, ['game/g1']);
""")


def test_the_start_button_cannot_be_sent_twice_while_waiting():
    run_node(r"""
await open();
radio('mode', 'game');
tick('person', 'p-a');
typed('scene.description', '週六去海邊小鎮。', 'textarea');
let release = null;
createReply = () => new Promise(resolve => { release = () => resolve({id: 'g1', title: '海線', build: {status: 'building', done: 1, total: 2}}); });
const first = click('cr-start');
await new Promise(resolve => setImmediate(resolve));
assert.equal(posts('/games').length, 1);
assert.ok(/data-action="cr-start" disabled>規劃中…<\/button>/.test(startButton(root.innerHTML)));  // 等待時按鈕停用
assert.equal(await click('cr-start'), true);  // 這時再按：不送第二次
// 等待中改了欄位、切換玩法：重畫出來的按鈕仍然停用，另一種玩法也不能在這時候開始
typed('game.playerName', '小光');
await click('cr-sub', {sub: 'x'});
assert.ok(/data-action="cr-start" disabled>/.test(startButton(root.innerHTML)));
radio('mode', 'story');
assert.ok(/data-action="cr-start" disabled>/.test(startButton(root.innerHTML)));
await click('cr-start');
assert.equal(posts('/games').length, 1);
assert.equal(posts('/generation/runs').length, 0);
release();
await first;
assert.equal(posts('/games').length, 1);
assert.deepEqual(navigated, ['game/g1']);
""")


def test_logging_out_while_waiting_does_not_touch_the_page_afterwards():
    """等待建立遊戲的回應時登出（登入過期時主程式也會清掉這一頁的狀態）：回應回來之後不換頁、不清草稿；失敗的話錯誤交給主程式顯示。"""
    run_node(r"""
await open();
radio('mode', 'game');
tick('person', 'p-a');
typed('scene.description', '週六去海邊小鎮。', 'textarea');
let release = null, refuse = null;
createReply = () => new Promise((resolve, reject) => { release = () => resolve({id: 'g1', title: '海線'}); refuse = reject; });
const first = click('cr-start');
await new Promise(resolve => setImmediate(resolve));
UI.forget();  // 等待中登出
release();
await first;
assert.deepEqual(navigated, []);  // 不換頁
const html = await open();  // 同一個帳號再進來：草稿還在，也可以再開始
assert.ok(/value="game" checked/.test(html) && /data-bind="person" value="p-a"[^>]*checked/.test(html) && has(html, '>週六去海邊小鎮。</textarea>'));
assert.ok(/data-action="cr-start" >開始生成<\/button>/.test(startButton(html)));

const second = click('cr-start');
await new Promise(resolve => setImmediate(resolve));
UI.forget();
refuse(new Error('登入已過期，請重新登入。'));
await assert.rejects(second, /登入已過期/);  // 往外丟給主程式顯示
assert.deepEqual(navigated, []);
""")


def test_the_old_game_new_address_lands_on_the_create_page_with_the_game_preselected():
    """舊的 #game-new：主程式把路由就地換成 create?mode=game；建立頁讀到 mode 就預選那個玩法，並把網址整理回 #create。"""
    run_node(r"""
let html = await open('mode=game');
assert.ok(/<input type="radio" name="create-mode" data-bind="mode" value="game" checked>/.test(html));
assert.ok(has(html, '同行的人（選 1～3 位）') && !has(html, '包含我'));
assert.deepEqual(replaced, ['#create']);
html = await open();  // 之後再進來：玩法留在草稿裡
assert.ok(/value="game" checked/.test(html));
html = await open('mode=story');  // 也可以指定回看的故事
assert.ok(/value="story" checked/.test(html) && has(html, '包含我'));
html = await open('mode=movie');  // 不認得的值：不理會
assert.ok(/value="story" checked/.test(html));
assert.deepEqual(replaced, ['#create', '#create']);
""")
    static = Path(__file__).resolve().parents[1] / 'app' / 'static'
    app = (static / 'app.js').read_text(encoding='utf-8')
    # 和其他舊網址（history?person、notes）一樣在 render 開頭就地改寫，不另外跳轉：不多留一筆瀏覽紀錄，按上一頁不會被彈回來
    rewrite = "(route.split('?')[0] === 'game-new') {"
    assert rewrite in app and "route = 'create?mode=game'; history.replaceState(null, '', '#' + route);" in app, '舊的 #game-new 換成建立頁並預選玩的遊戲'
    assert app.index(rewrite) < app.index("const path = route.split('?')[0]; params = new URLSearchParams("), '改寫要在拆出頁面路徑與參數之前'
    assert "path === 'game-new'" not in app and 'GameUI.newView' not in app and 'GameUI.submit' not in app, '獨立的建立表單已經拿掉'
    assert "path === 'create') html = await CreationUI.view(params)" in app


def test_without_the_person_system_the_game_mode_says_people_are_needed():
    run_node(r"""
people = {enabled: false, items: []};
await open();
radio('mode', 'game');
let html = root.innerHTML;
assert.ok(has(html, '讀不到人物清單') && !has(html, 'data-bind="card"') && !has(html, 'data-bind="person"'));  // 不退回舊角色卡：玩的遊戲只能選人物
assert.ok(has(html, '請在 ① 人物選 1～3 位同行的人物。') && /data-action="cr-start" disabled>/.test(startButton(html)));

people = {enabled: true, items: []};  // 人物系統開著，但一位人物都沒有
html = await again();
assert.ok(has(html, '還沒有人物') && has(html, 'href="#persons"'));
people = {enabled: true, items: [{id: 'p-e', name: '還沒設定的人', description: '', person_type: 'real', roles: [], profile: null}]};  // 有人物，但都沒有人物設定
html = await again();
assert.ok(has(html, '目前沒有任何人物有人物設定'));
""")


def test_a_failed_plan_can_be_planned_again_but_a_lost_connection_reuses_the_same_request():
    """2026-11-12 外部檢驗（Codex）：建立頁對相同內容一律沿用同一個提交代碼，伺服器已經確認失敗的規劃，再按只會重放同一個錯誤。
    改成：伺服器明確回了失敗（有狀態碼，且不是「還在進行」）→ 下一次是新的嘗試（新的提交代碼），並說明再按會重新規劃、會再呼叫一次模型；
    連線中斷或結果不明 → 沿用原本的提交代碼，再按一次只會找回上一次的結果，不會重複規劃；還在進行 → 沿用，請使用者稍候。"""
    run_node(r"""
await open();
radio('mode', 'game');
tick('person', 'p-a');
typed('scene.description', '週六去海邊小鎮。', 'textarea');
const used = () => posts('/games').map(call => call.body.request_id);

// 伺服器確認失敗（模型輸出不合格）：再按是新的嘗試
createReply = fail('AI 回傳的內容格式不完整。', 502);
await click('cr-start');
assert.ok(has(root.innerHTML, '再按「開始生成」會重新規劃一次（會再呼叫一次模型）。'));
createReply = fail('今天的 AI 用量已達上限，明天再試。', 429);
await click('cr-start');
assert.notEqual(used()[1], used()[0]);  // 不重放第一次的失敗

// 連線中斷（沒有狀態碼）：結果不明，沿用同一個提交代碼
createReply = () => { throw new Error('目前無法連線。'); };
await click('cr-start');
assert.ok(has(root.innerHTML, '還不確定伺服器有沒有收到；再按一次會先找回上一次的結果，不會重複規劃。'));
createReply = () => { const error = new Error('這次生成仍在進行，請稍候再查看結果。'); error.status = 409; error.code = 'generation_in_progress'; throw error; };
await click('cr-start');
assert.ok(has(root.innerHTML, '上一次的規劃還在進行，請稍候再按一次。'));
createReply = null;
await click('cr-start');
assert.equal(used().length, 5);
assert.equal(new Set(used().slice(2)).size, 1);  // 連線中斷、還在進行、成功：都是同一個提交代碼
assert.notEqual(used()[2], used()[1]);
assert.deepEqual(navigated, ['game/g1']);
""")
