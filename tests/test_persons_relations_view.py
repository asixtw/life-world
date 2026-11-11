"""Unified Person P4：人物詳細頁「關係」分頁與新增／編輯視窗的畫面輸出。

以 Node 直接執行 app/static/persons.js（假的 API 與假的對話框，不開任何網站），檢查產生的 HTML 與送出的請求。
這是開發時的快速檢查；實際畫面以部署後在 Local 8030（Cloud SQL life_world_e2e）的 Chrome 操作為準。
"""
import os
import shutil
import subprocess

import pytest

SETUP = r"""
const assert = require('node:assert/strict');
globalThis.window = globalThis; globalThis.history = {replaceState() {}};
require('./app/static/persons.js');
const UI = window.PersonsUI;
const person = (id, name, extra = {}) => ({id, owner_id: 'o', name, aliases: [], person_type: 'real', person_subtype: 'historical', description: name + '的簡介', roles: [],
  tags: [], category: 'other', status: 'active', origin_type: 'manual', followed: false, revision: 1, created_at: '', notes: '', common_context: '', ...extra});
const summary = p => ({id: p.id, name: p.name, person_type: p.person_type, person_subtype: p.person_subtype, status: p.status, description: p.description, followed: p.followed});
const me = person('p1', '周瑜'), sun = person('p2', '孫策'), zhuge = person('p3', '諸葛亮', {followed: true}), lu = person('p4', '魯肅', {status: 'archived'});
const twin = person('p5', '周瑜', {person_type: 'fictional', person_subtype: null, description: '架空三國的現代企業家'}), fresh = person('p9', '小喬');
const relation = (id, other, extra = {}) => ({id, revision: 3, status: 'active', confirmation_status: 'confirmed', person: summary(other),
  relation_types: [{kind: 'friend'}, {kind: 'colleague'}], description: '一同平定江東', label: '一同平定江東', text: '一同平定江東',
  source_experience_ids: ['e1'], source_person_experience_ids: [], sources: {experiences: [{id: 'e1', summary: '赤壁之戰前的會議', occurred_at: '2026-11-01T00:00:00+00:00'}]}, ...extra});
const detail = {person: me, profile: null, experiences: {mine: 0, person_experiences: 0}, connections: [
  relation('c1', sun), relation('c3', zhuge, {status: 'archived', confirmation_status: 'archived', relation_types: [{kind: 'rival'}], text: '軍事上的對手', description: '軍事上的對手'}),
  relation('c4', lu, {relation_types: [], source_experience_ids: [], sources: {experiences: []}, description: '', label: '舊說明', text: '舊說明'})]};
const calls = [], dialogs = []; let renders = 0, closed = 0;
const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch]));
const api = async (path, options = {}) => {
  calls.push({path, method: options.method || 'GET', body: options.body});
  if (path === '/persons/p1') return detail;
  if (path.startsWith('/persons?')) return {items: [me, twin, sun, zhuge, fresh], total: 5, offset: 0, limit: 20};
  if (path.startsWith('/persons/p1/connection-sources')) return {items: [{id: 'e2', summary: '江東會議', occurred_at: '2026-11-02T00:00:00+00:00'},
    {id: 'e1', summary: '赤壁之戰前的會議', occurred_at: '2026-11-01T00:00:00+00:00'}], total: 2};
  return {};
};
UI.initialize({state: {renderGeneration: 1, capabilities: {unified_people: true}, requests: new Map()}, api, esc,
  link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1><p>${esc(subtitle)}</p>${action}`, empty: (m, a = '') => `<div class="empty">${esc(m)}${a}</div>`,
  time: x => x, toast() {}, requestId: () => 'rid', render: async () => { renders++; }, navigate() {},
  dialog: html => dialogs.push(html), closeDialog: () => { closed++; }});
const has = (html, text) => html.includes(text);
const click = dataset => UI.handleClick({dataset});
(async () => {
"""


def run_node(script):
    node = os.environ.get('LIFEWORLD_NODE') or shutil.which('node')
    if not node:
        pytest.skip('需要 Node 執行前端模組；可設定 LIFEWORLD_NODE')
    result = subprocess.run([node, '-e', SETUP + script + '\n})().catch(e => { console.error(e); process.exit(1); });'],
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_relations_tab_lists_active_relations_with_actions_and_no_legacy_page():
    run_node(r"""
const tab = await UI.detail('p1', 'relations', new URLSearchParams(''));
assert.ok(has(tab, '人物關係（2）'));  // 使用中：孫策、魯肅；已封存的諸葛亮不在預設列表
assert.ok(has(tab, 'data-action="persons-relation-new"') && has(tab, '＋ 新增關係'));
assert.ok(has(tab, '孫策') && has(tab, '朋友') && has(tab, '同事') && has(tab, '一同平定江東') && has(tab, '來源：1 筆我的經歷') && has(tab, '赤壁之戰前的會議'));
assert.ok(has(tab, 'data-action="persons-relation-edit" data-connection="c1"'));
assert.ok(has(tab, 'data-action="persons-relation-status" data-connection="c1" data-revision="3" data-status="archived"'));
assert.ok(!has(tab, '諸葛亮') && !has(tab, '軍事上的對手'));
assert.ok(has(tab, '魯肅') && has(tab, '舊說明') && has(tab, '人物已封存'));  // 舊 label 回退顯示；對方已封存
assert.ok(!has(tab, 'data-connection="c4"'));  // 任一端人物已封存：沒有編輯、封存按鈕
assert.ok(has(tab, 'href="#persons/p1?tab=relations&amp;archived=1"') && has(tab, '查看已封存的關係（1）'));
assert.ok(!has(tab, 'href="#person/'));  // 不再要求回舊關係頁
assert.ok(!/data-person="/.test(tab));  // 舊模組會攔截 data-person
""")


def test_archived_view_offers_restore_only():
    run_node(r"""
const tab = await UI.detail('p1', 'relations', new URLSearchParams('archived=1'));
assert.ok(has(tab, '已封存的關係（1）') && has(tab, '諸葛亮') && has(tab, '對手') && has(tab, '軍事上的對手'));
assert.ok(has(tab, 'data-action="persons-relation-status" data-connection="c3" data-revision="3" data-status="confirmed"') && has(tab, '恢復'));
assert.ok(!has(tab, 'persons-relation-edit') && !has(tab, 'persons-relation-new') && !has(tab, '孫策'));
assert.ok(has(tab, 'href="#persons/p1?tab=relations"') && has(tab, '返回使用中的關係（2）'));
""")


def test_overview_shows_important_relations_followed_first_and_active_only():
    run_node(r"""
detail.connections[1].status = 'active'; detail.connections[1].confirmation_status = 'confirmed';  // 諸葛亮（已關注）改為使用中
const overview = await UI.detail('p1', 'overview', new URLSearchParams(''));
const at = name => overview.indexOf('>' + name + '<');
assert.ok(has(overview, '重要關係') && at('諸葛亮') > 0 && at('孫策') > at('諸葛亮'));  // 已關注的人物優先
assert.ok(has(overview, 'href="#persons/p1?tab=relations"'));
detail.connections[1].status = 'archived';
assert.ok(!has(await UI.detail('p1', 'overview', new URLSearchParams('')), '>諸葛亮<'));  // 已封存的不列
""")


def test_new_relation_dialog_has_shared_hint_types_and_a_selector_that_tells_same_names_apart():
    run_node(r"""
await UI.detail('p1', 'relations', new URLSearchParams(''));
await click({action: 'persons-relation-new', personRef: 'p1'});
const html = dialogs.at(-1);
assert.ok(has(html, 'id="account-heading">新增人物關係'));
assert.ok(has(html, '這段關係由雙方共用，請描述兩人之間的關係，不是單方面的人物備註。'));
for (const label of ['家人', '伴侶', '朋友', '同事', '同學', '師徒', '客戶', '商業往來', '鄰居', '對手', '敵人', '其他']) assert.ok(has(html, label), label);
assert.equal((html.match(/name="relation_kind"/g) || []).length, 12);
assert.ok(has(html, '最多 10 種') && has(html, 'id="persons-relation-q"') && has(html, 'id="persons-relation-description"') && has(html, '儲存關係') && has(html, '取消'));
assert.ok(has(html, '目前人物') && has(html, '周瑜'));
assert.ok(!has(html, 'data-person-ref="p1"'));  // 排除目前人物
assert.ok(has(html, 'data-action="persons-relation-pick" data-person-ref="p5"') && has(html, '虛構人物') && has(html, '架空三國的現代企業家'));  // 同名人物靠類型與簡介分辨
assert.ok(has(html, '已有關係，選取後改為編輯') && has(html, '已有關係（已封存）'));
assert.ok(calls.some(x => x.path.startsWith('/persons?') && x.path.includes('status=active')));  // 只找使用中的人物
assert.ok(!/data-person="/.test(html) && !has(html, '新增人物</a>'));  // 選擇器內不提供新增人物
""")


def test_picking_a_person_loads_eligible_records_or_switches_to_existing_relation():
    run_node(r"""
await UI.detail('p1', 'relations', new URLSearchParams(''));
await click({action: 'persons-relation-new', personRef: 'p1'});
await click({action: 'persons-relation-pick', personRef: 'p9'});
let html = dialogs.at(-1);
assert.ok(has(html, '新增人物關係') && has(html, '小喬') && has(html, 'data-action="persons-relation-clear"') && !has(html, 'id="persons-relation-q"'));
assert.ok(calls.some(x => x.path === '/persons/p1/connection-sources?other_person_id=p9'));
assert.ok(has(html, 'name="relation_source" value="e2"') && has(html, '江東會議') && !has(html, 'value="e2" checked'));
await click({action: 'persons-relation-clear'});
await click({action: 'persons-relation-pick', personRef: 'p2'});  // 已有使用中的關係：切換為編輯並載入原內容
html = dialogs.at(-1);
assert.ok(has(html, '編輯人物關係') && has(html, '已經有關係') && has(html, 'value="friend" checked') && has(html, 'value="colleague" checked') && !has(html, 'value="rival" checked'));
assert.ok(has(html, '>一同平定江東</textarea>') && has(html, 'name="relation_source" value="e1" checked') && has(html, 'name="relation_source" value="e2"'));
assert.ok(html.indexOf('value="e1"') < html.indexOf('value="e2"') && !has(html, 'persons-relation-clear'));  // 既有來源排在前面；編輯時不能換人
await click({action: 'persons-relation-new', personRef: 'p1'});
await click({action: 'persons-relation-pick', personRef: 'p3'});  // 已封存的關係：提示並提供恢復
html = dialogs.at(-1);
assert.ok(has(html, '此關係已封存') && has(html, 'data-action="persons-relation-status" data-connection="c3" data-revision="3" data-status="confirmed"'));
assert.ok(!has(html, '儲存關係') && !has(html, 'persons-relation-form'));
""")


def test_edit_button_prefills_and_status_buttons_call_patch():
    run_node(r"""
await UI.detail('p1', 'relations', new URLSearchParams(''));
await click({action: 'persons-relation-edit', connection: 'c4'});  // 舊資料：沒有描述時帶入舊 label，避免儲存後遺失
let html = dialogs.at(-1);
assert.ok(has(html, '編輯人物關係') && has(html, '>舊說明</textarea>') && has(html, '魯肅'));
await click({action: 'persons-relation-status', connection: 'c1', revision: '3', status: 'archived'});
let call = calls.at(-1);
assert.equal(call.path, '/connections/c1'); assert.equal(call.method, 'PATCH');
assert.deepEqual(call.body, {expected_revision: 3, confirmation_status: 'archived', request_id: 'rid'});
assert.equal(renders, 1); assert.equal(closed, 1);
await click({action: 'persons-relation-status', connection: 'c3', revision: '3', status: 'confirmed'});
assert.deepEqual(calls.at(-1).body, {expected_revision: 3, confirmation_status: 'confirmed', request_id: 'rid'});
""")


def test_archived_person_page_is_read_only_for_relations():
    run_node(r"""
me.status = 'archived';
const tab = await UI.detail('p1', 'relations', new URLSearchParams(''));
assert.ok(!has(tab, 'persons-relation-new') && !has(tab, 'persons-relation-edit') && !has(tab, 'persons-relation-status'));
assert.ok(has(tab, '孫策') && has(tab, '這位人物已封存'));  // 仍可瀏覽
""")
