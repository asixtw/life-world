"""建立新作品的「① 人物」：人物系統啟用後先列「人物」，送出時引用人物與畫面讀到的人物設定版本。

以 Node 直接執行 app/static/creation.js（假的 API、假的儲存與事件，不開任何網站），檢查產生的 HTML 與送出的請求。
這是開發時的快速檢查；實際畫面以部署後在 Local 8030（Cloud SQL life_world_e2e）的 Chrome 操作為準。
"""
import os
import shutil
import subprocess

import pytest

SETUP = r"""
const assert = require('node:assert/strict');
const store = new Map(), listeners = {}, root = {innerHTML: ''};
globalThis.window = globalThis; globalThis.history = {replaceState() {}};
globalThis.matchMedia = () => ({matches: false});
globalThis.sessionStorage = {getItem: k => store.has(k) ? store.get(k) : null, setItem: (k, v) => { store.set(k, String(v)); }, removeItem: k => { store.delete(k); }};
globalThis.document = {addEventListener: (type, fn) => { listeners[type] = fn; }, getElementById: id => id === 'create-root' ? root : null, querySelector: () => null};
require('./app/static/creation.js');
const UI = window.CreationUI;
const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch]));
const persona = {persona: {work_id: 'sp', version_no: 2, revision: 2, content: {display_name: '小光'}}, consent: {id: 'k1'}, consent_text: '同意文字'};
const cards = [{id: 'card1', title: '舊卡甲', current_version: 1, content: {tagline: '舊卡的簡介'}}, {id: 'card2', title: '舊卡乙', current_version: 3, content: {}}];
const catalog = {styles: [], scene_presets: [], outputs: [{type: 'text', label: '文字', available: true}], lengths: [{id: 'short', label: '短（約 8 段）'}],
  forms: [{id: 'script', label: '劇本對白'}], positions: [], adherence: [], limits: {max_participants: 4, max_materials: 3, max_conditions: 8}};
let people = {enabled: true, items: [
  {id: 'p1', name: '溫若岑 <b>', description: '願意讓手藝留下接縫。', person_type: 'fictional', person_subtype: 'original', roles: ['模型製作者'], profile: {id: 'n3', version: 3}},
  {id: 'p2', name: '阿哲', description: '', person_type: 'real', person_subtype: null, roles: ['大學同學'], profile: {id: 'n1', version: 1}},
  {id: 'p3', name: '周瑜', description: '東吳都督', person_type: 'real', person_subtype: 'historical', roles: [], profile: null}]};
let selfData = persona, peopleFails = false;
const calls = [], navigated = [], toasts = [];
const api = async (path, options = {}) => {
  calls.push({path, method: options.method || 'GET', body: options.body});
  if (path === '/characters?status=active') return {items: cards};
  if (path === '/self-persona') return selfData;
  if (path === '/generation/catalog') return catalog;
  if (path === '/generation/status') return {available: true, provider_kind: 'live', background: true};
  if (path === '/generation/people') { if (peopleFails) throw new Error('offline'); return people; }
  if (path === '/generation/runs') return {id: 'w9'};
  return {};
};
const context = () => ({state: {renderGeneration: 1, me: {owner_id: 'o1'}, dirty: false}, api, esc,
  link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1><p>${esc(subtitle)}</p>${action}`, empty: m => `<div class="empty">${esc(m)}</div>`,
  time: x => x, toast: m => toasts.push(m), requestId: () => 'rid', render: async () => {}, navigate: route => navigated.push(route)});
const open = async () => { UI.forget(); UI.initialize(context()); return UI.view(new URLSearchParams('')); };
const change = (bind, value, checked = true, dataset = {}) => listeners.change({type: 'change',
  target: {closest: () => true, dataset: {bind, ...dataset}, value, checked, type: 'checkbox', tagName: 'INPUT'}});
const pickPosition = (id, value) => listeners.change({type: 'change', target: {closest: () => true, dataset: {bind: 'position', id}, value, type: 'select-one', tagName: 'SELECT'}});
const typed = (bind, value) => listeners.input({type: 'input', target: {closest: sel => sel === '#create-root', dataset: {bind}, value, type: 'textarea', tagName: 'TEXTAREA'}});
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


def test_people_are_listed_first_and_people_without_a_profile_cannot_be_ticked():
    run_node(r"""
const html = await open();
assert.ok(calls.some(call => call.path === '/generation/people'));
assert.ok(has(html, '人物（可多選）'));
assert.ok(has(html, 'data-bind="person" value="p1"') && has(html, '溫若岑 &lt;b&gt;') && has(html, '願意讓手藝留下接縫。'));  // 姓名跳脫、顯示簡介
assert.ok(has(html, '人物設定第 3 版') && has(html, '虛構人物'));
assert.ok(has(html, 'data-bind="person" value="p2"') && has(html, '真實人物') && has(html, '大學同學'));  // 沒有簡介時顯示身分
assert.ok(/data-bind="person" value="p3"[^>]*disabled/.test(html) && has(html, '還沒有人物設定') && has(html, 'href="#persons/p3"'));  // 不能勾，並指向人物頁
assert.ok(has(html, '歷史人物'));
assert.ok(has(html, 'href="#persons"') && !has(html, 'href="#characters"'));  // 補人物的入口是「人物」，不再指向已收起的「角色」
assert.ok(has(html, '舊角色卡（2 張）') && !has(html, 'data-bind="card"'));  // 舊角色卡收合，預設不展開
assert.ok(has(html, 'AI 參與人物：1 位'));  // 預設只有「包含我」
""")


def test_ticking_people_counts_them_and_start_sends_person_refs_with_the_profile_seen():
    run_node(r"""
await open();
change('person', 'p1');
change('person', 'p2');
assert.ok(has(root.innerHTML, 'AI 參與人物：3 位（多人文字）'));
assert.ok(/data-bind="person" value="p1"[^>]*checked/.test(root.innerHTML));
await UI.handleClick({dataset: {action: 'cr-sub', sub: 'positions'}});
assert.ok(has(root.innerHTML, 'data-bind="position" data-id="p1"') && has(root.innerHTML, 'data-bind="position" data-id="p2"'));  // 人物也可以設角色定位
pickPosition('p1', 'supporting');
typed('scene.description', '週六午後的試作桌。');
await UI.handleClick({dataset: {action: 'cr-start'}});
const sent = calls.find(call => call.path === '/generation/runs');
assert.equal(sent.method, 'POST');
assert.deepEqual(sent.body.setup.participants, [
  {source: 'person', ref: {person_id: 'p1', profile_id: 'n3'}, position: 'supporting'},
  {source: 'person', ref: {person_id: 'p2', profile_id: 'n1'}}]);
assert.equal(sent.body.setup.include_me, true);
assert.deepEqual(navigated, ['run/w9']);

const again = await UI.view(new URLSearchParams(''));  // 開始之後草稿清空：再進來沒有勾選任何人物
assert.ok(has(again, 'data-bind="person" value="p1"') && !/data-bind="person" value="p1"[^>]*checked/.test(again));
""")


def test_people_and_old_cards_can_be_mixed_and_removed_people_drop_out_of_the_draft():
    run_node(r"""
await open();
change('person', 'p1');
assert.ok(has(root.innerHTML, 'AI 參與人物：2 位（多人文字）') && !has(root.innerHTML, 'data-bind="card"'));
await UI.handleClick({dataset: {action: 'cr-sub', sub: 'cards'}});
assert.ok(has(root.innerHTML, 'data-bind="card" value="card2"'));
change('card', 'card2', true, {version: '3'});
assert.ok(has(root.innerHTML, 'AI 參與人物：3 位（多人文字）'));
typed('scene.description', '場景');
people = {enabled: true, items: people.items.filter(item => item.id !== 'p1').concat([{...people.items[0], id: 'p9', name: '新人物'}])};
const html = await UI.view(new URLSearchParams(''));  // 重新讀取：p1 已不在可選清單（封存或刪除）
assert.ok(!/data-bind="person" value="p9"[^>]*checked/.test(html) && has(html, 'AI 參與人物：2 位'));  // 只剩舊角色卡與我
assert.ok(has(html, 'data-bind="card" value="card2"'));  // 已選的舊角色卡保持展開，不會藏起來
await UI.handleClick({dataset: {action: 'cr-start'}});
const sent = calls.filter(call => call.path === '/generation/runs').pop();
assert.deepEqual(sent.body.setup.participants, [{source: 'card', ref: {work_id: 'card2', version_no: 3}}]);
""")


def test_without_the_person_system_the_page_keeps_the_card_only_picker():
    run_node(r"""
people = {enabled: false, items: []};
let html = await open();
assert.ok(has(html, '我的角色卡（可多選）') && has(html, 'data-bind="card" value="card1"') && has(html, 'href="#characters"'));
assert.ok(!has(html, '人物（可多選）') && !has(html, 'data-bind="person"'));

people = {enabled: true, items: []}; peopleFails = true;  // 人物清單讀取失敗：不擋住整個建立頁，退回只選角色卡
html = await open();
assert.ok(has(html, '我的角色卡（可多選）') && !has(html, 'data-bind="person"'));
""")
