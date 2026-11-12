"""多章節作品的「作品總覽」頁與作品頁上的入口。

以 Node 直接執行 app/static/series.js 與 generation.js（假的 API，不開任何網站），檢查產生的 HTML 與送出的請求。
這是開發時的快速檢查；實際畫面以部署後在 Local 8030（Cloud SQL life_world_e2e）的 Chrome 操作為準。
"""
import os
import shutil
import subprocess

import pytest

SETUP = r"""
const assert = require('node:assert/strict');
globalThis.window = globalThis;
globalThis.document = {getElementById: () => null, addEventListener() {}, body: {appendChild() {}}, createElement: () => ({click() {}, remove() {}})};
require('./app/static/generation.js');
require('./app/static/series.js');
const UI = window.SeriesUI;
const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch]));
let series = {id: 's1', title: '留一條接縫 <b>', status: 'active', revision: 3, version_no: 3, next_episode_no: 3,
  cast: [{name: '溫若岑', source: 'person', position: 'supporting', is_user: false}, {name: '小光', source: 'self', position: null, is_user: true}],
  episodes: [{no: 1, work_id: 'w1', title: '留一條接縫', segments: 8, adopted_at: '2026-11-11T10:00:00+00:00'},
             {no: 2, work_id: 'w2', title: '開門之前', segments: 9, adopted_at: '2026-11-12T10:00:00+00:00'}],
  drafts: [{work_id: 'd1', title: '草稿甲', run_status: 'completed', completed_segments: 8, total_segments: 8, base_episode_no: 2, can_adopt: true, created_at: 't1'},
           {work_id: 'd2', title: '草稿乙', run_status: 'running', completed_segments: 3, total_segments: 8, base_episode_no: 2, can_adopt: false, created_at: 't2'},
           {work_id: 'd3', title: '草稿丙', run_status: 'completed', completed_segments: 8, total_segments: 8, base_episode_no: 1, can_adopt: false, created_at: 't3'}]};
let exportsReply = {available: true, items: []}, available = true;
const calls = [], toasts = [], navigated = [];
let renders = 0;
const api = async (path, options = {}) => {
  calls.push({path, method: options.method || 'GET', body: options.body});
  if (path === '/series/s1' ) return series;
  if (path === '/series' && options.method === 'POST') return {id: 's1'};
  if (path === '/series/s1/episodes' && options.method === 'POST') return {id: 'w9', series_id: 's1', base_episode_no: 2};
  if (path === '/series/s1/episodes/d1/adopt') return series;
  if (path === '/works/d2') return {id: 'd2', revision: 4};
  if (path === '/works/d2/status') return {id: 'd2', status: 'archived'};
  if (path === '/works/s1/exports' && options.method === 'POST') return {export: {version_no: 1, download_path: '/api/works/s1/exports/1/download'}};
  if (path === '/works/s1/exports') return exportsReply;
  if (path === '/generation/status') return {available, background: true};
  return {};
};
const context = {state: {renderGeneration: 1}, api, esc,
  link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1><p>${esc(subtitle)}</p>${action}`, empty: m => `<div class="empty">${esc(m)}</div>`,
  time: x => 'T(' + x + ')', toast: m => toasts.push(m), requestId: (scope, body) => 'rid:' + scope, render: async () => { renders++; }, navigate: route => navigated.push(route)};
UI.initialize(context);
window.GenerationUI.initialize(context);
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


def test_overview_lists_adopted_chapters_drafts_and_the_continue_form():
    run_node(r"""
const html = await UI.view('s1');
assert.ok(has(html, '留一條接縫 &lt;b&gt;') && has(html, '溫若岑、小光（我）'));  // 標題跳脫；人物
assert.ok(has(html, '已定稿的章節（2）') && has(html, 'href="#run/w1"') && has(html, '第 1 章') && has(html, 'href="#run/w2"') && has(html, '開門之前') && has(html, '9 段'));
assert.ok(has(html, '草稿（3）'));
assert.ok(has(html, 'data-action="series-adopt" data-series="s1" data-work="d1"') && has(html, '採納為第 3 章'));  // 可以採納的草稿
assert.ok(has(html, '生成中（3／8 段）') && !has(html, 'data-work="d2" data-action="series-adopt"') && !/series-adopt[^>]*data-work="d2"/.test(html));  // 生成中的不能採納
assert.ok(has(html, '接在第 1 章後面寫的') && !/series-adopt[^>]*data-work="d3"/.test(html));  // 過時的草稿說明原因
assert.ok(has(html, 'data-action="series-discard" data-work="d2"') && has(html, 'href="#run/d1"'));
assert.ok(has(html, 'id="series-next-form"') && has(html, 'data-series="s1"') && has(html, '續寫第 3 章') && has(html, 'name="description"'));
assert.ok(has(html, '各章大綱') && has(html, '記憶'));  // 說明會繼承什麼
assert.ok(has(html, 'data-action="gen-export" data-id="s1"') && has(html, '已定稿的 2 章'));  // 整部下載
assert.ok(calls.some(call => call.path === '/works/s1/exports'));
// 互動版：同一個動作，多帶 data-player="play"；旁邊有一句說明
assert.ok(has(html, 'data-action="gen-export" data-id="s1" data-player="play"') && has(html, '下載互動版'));
assert.equal(html.split('data-action="gen-export"').length - 1, 2);
assert.equal(html.split('data-player=').length - 1, 1);  // 原本那一顆不帶 player
assert.ok(has(html, '一次看一段') && has(html, '真心話') && has(html, '底牌'));
// play-2：說明寫出新的玩法；總覽的互動版按鈕不帶 data-interactive（整部下載不另外準備互動內容，用各章已經有的）
for (const word of ['視角', '偷看', '線索', '抉擇']) assert.ok(has(html, word), word);
assert.ok(!has(html, 'data-interactive') && !has(html, '可以開「真心話」'));
""")


def test_the_overview_play_button_exports_the_whole_work_as_the_play_version():
    """作品總覽的兩顆下載按鈕都交給作品頁的下載流程（GenerationUI）：互動版多帶 player: 'play'，原本那一顆的請求不變。"""
    run_node(r"""
await UI.view('s1');
assert.equal(await UI.handleClick({dataset: {action: 'gen-export', id: 's1', player: 'play'}}), false);  // 總覽自己不處理下載
assert.equal(await window.GenerationUI.handleClick({dataset: {action: 'gen-export', id: 's1', player: 'play'}}), true);
assert.equal(await window.GenerationUI.handleClick({dataset: {action: 'gen-export', id: 's1'}}), true);
const posts = calls.filter(call => call.path === '/works/s1/exports' && call.method === 'POST');
assert.equal(posts.length, 2);
assert.deepEqual({...posts[0].body, request_id: null}, {request_id: null, format: 'html', player: 'play'});
assert.deepEqual({...posts[1].body, request_id: null}, {request_id: null, format: 'html'});
assert.ok(toasts.some(message => message.includes('互動版')));
// 整部下載不呼叫準備互動內容的端點：照總覽頁實際畫出來的按鈕（沒有 data-interactive）送出，只有匯出的請求
assert.ok(!calls.some(call => call.path.includes('/interactive')));
assert.deepEqual(calls.filter(call => call.method === 'POST').map(call => call.path), ['/works/s1/exports', '/works/s1/exports']);
assert.ok(!toasts.some(message => message.includes('準備互動內容')));
""")


def test_continue_adopt_and_discard_send_the_right_requests():
    run_node(r"""
await UI.view('s1');
const form = {id: 'series-next-form', dataset: {series: 's1'}, elements: {description: {value: ' 隔天早上，展場開門前。 '}, event: {value: ''}, goal: {value: '把標籤定案'},
  length: {value: 'medium'}, form: {value: 'narrative'}, title: {value: '開門之前'}}};
assert.equal(await UI.submit(form), true);
const started = calls.find(call => call.path === '/series/s1/episodes');
assert.deepEqual({...started.body, request_id: null}, {request_id: null, title: '開門之前',
  scene: {description: '隔天早上，展場開門前。', start: {event: '', goal: '把標籤定案'}}, output: {length: 'medium', form: 'narrative'}});
assert.deepEqual(navigated, ['run/w9']);  // 建立後到這一章的作品頁看生成進度
assert.equal(await UI.submit({id: 'other-form'}), false);

assert.equal(await UI.handleClick({dataset: {action: 'series-adopt', series: 's1', work: 'd1'}}), true);
assert.equal(calls.find(call => call.path === '/series/s1/episodes/d1/adopt').method, 'POST');
assert.equal(await UI.handleClick({dataset: {action: 'series-discard', work: 'd2'}}), true);
const discard = calls.find(call => call.path === '/works/d2/status');
assert.deepEqual({...discard.body, request_id: null}, {request_id: null, expected_revision: 4, status: 'archived'});  // 捨棄＝封存那份草稿
assert.equal(renders, 2);
assert.equal(await UI.handleClick({dataset: {action: 'series-open', id: 'w1'}}), true);
assert.equal(calls.find(call => call.path === '/series' && call.method === 'POST').body.work_id, 'w1');
assert.deepEqual(navigated, ['run/w9', 'series/s1']);
assert.equal(await UI.handleClick({dataset: {action: 'something-else'}}), false);
""")


def test_empty_drafts_and_missing_generation_or_storage_are_explained():
    run_node(r"""
series = {...series, drafts: [], episodes: series.episodes.slice(0, 1), next_episode_no: 2};
available = false; exportsReply = {available: false, items: []};
const html = await UI.view('s1');
assert.ok(!has(html, '草稿（') && has(html, '續寫第 2 章'));
assert.ok(has(html, 'AI 生成尚未設定') && /<button[^>]*type="submit"[^>]*disabled/.test(html));
assert.ok(!has(html, 'data-action="gen-export"') && has(html, '還沒有開放下載'));
""")


def test_work_page_offers_continuing_or_links_back_to_the_overview():
    run_node(r"""
const detail = (status, series) => ({id: 'w1', title: '留一條接縫', module: 'T2', cast: [{id: 'c1', name: '溫若岑', source: 'person', version: 3, is_user: false}],
  run: {status, completed_segments: 8, total_segments: 8, notice: null, error: null, can_resume: false}, usage: {calls: 9}, series,
  segments: [{speaker_name: '溫若岑', is_user: false, line: '先做一小塊。', action: '', stage_direction: ''}], setup: {scene: {description: '試作桌'}, styles: []}, history: []});
let current = detail('completed', null);
const runApi = async path => path === '/generation/runs/w1' ? current : path === '/generation/status' ? {available: true, background: true} : {available: true, items: []};
window.GenerationUI.initialize({...context, api: runApi});
let html = await window.GenerationUI.run('w1');
assert.ok(has(html, 'data-action="series-open" data-id="w1"') && has(html, '續寫下一章'));  // 獨立的已完成作品：可以開始續寫

current = detail('completed', {id: 's1', title: '留一條接縫', episode_no: 2, is_draft: false});
html = await window.GenerationUI.run('w1');
assert.ok(has(html, '第 2 章') && has(html, 'href="#series/s1"') && !has(html, 'data-action="series-open"'));

current = detail('completed', {id: 's1', title: '留一條接縫', episode_no: null, is_draft: true});
html = await window.GenerationUI.run('w1');
assert.ok(has(html, '草稿') && has(html, 'href="#series/s1"') && has(html, '採納'));  // 草稿：提示回總覽決定要不要採納

current = detail('failed', null);
html = await window.GenerationUI.run('w1');
assert.ok(!has(html, 'series-open'));  // 沒有完成：不提供續寫
""")


def test_continue_form_defaults_to_the_output_setting_of_the_work():
    """第 1 章是小說敘事、中篇：續寫表單預設就是小說敘事、中篇，使用者不用每一章重選（也不會不小心換了呈現形式）。"""
    run_node(r"""
series = {...series, output: {length: 'medium', form: 'narrative'}};
let html = await UI.view('s1');
assert.ok(has(html, '<option value="narrative" selected>') && has(html, '<option value="medium" selected>'));
assert.ok(!has(html, '<option value="script" selected>') && !has(html, '<option value="short" selected>'));
series = {...series, output: undefined};   // 舊資料沒有這個欄位：維持原本的預設
html = await UI.view('s1');
assert.ok(has(html, '<option value="script" selected>') && has(html, '<option value="short" selected>'));
""")
