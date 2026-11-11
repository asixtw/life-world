"""人物經歷（Unified Person E1）：人物詳細頁「經歷」分頁的兩個區塊與人物經歷對話框的畫面輸出。

以 Node 直接執行 app/static/persons.js（假的 API 與假的對話框，不開任何網站），檢查產生的 HTML 與送出的請求。
這是開發時的快速檢查；實際畫面以部署後在 Local 8030（Cloud SQL life_world_e2e）的 Chrome 操作為準。
"""
from test_persons_relations_view import run_node

PREPARE = r"""
const exp = (id, extra = {}) => ({id, owner_id: 'o', revision: 2, status: 'active', title: '平定江東', content: '與孫策平定江東，建立基業。', experience_type: 'historical',
  origin_type: 'manual', occurred_precision: 'year', occurred_on: '0199', occurred_label: '建安四年', created_at: '', updated_at: '',
  subject: summary(me), participants: [summary(sun)], role: 'subject', ...extra});
const many = [sun, zhuge, twin, fresh, person('p6', '魯肅')].map(summary);
const lists = {records: {items: [{id: 'r1', summary: '與周瑜討論合作', occurred_at: '2026-11-01T00:00:00+00:00'}], total: 1},
  person_experiences: {items: [exp('x1'), exp('x2', {title: '', content: '少年時在廬江求學，結識了許多朋友。', occurred_precision: 'unknown', occurred_on: null, occurred_label: '',
    participants: []}), exp('x3', {title: '赤壁之戰', role: 'participant', subject: summary(zhuge), participants: [summary(me), many[0], many[3], many[4], many[2]],
    occurred_precision: 'month', occurred_on: '0208-12', occurred_label: '', experience_type: 'fictional'})], total: 3, archived_total: 1}};
const archivedLists = {records: lists.records, person_experiences: {items: [exp('x9', {status: 'archived', title: '舊的經歷'})], total: 3, archived_total: 1}};
const real = person('p7', '王小明', {person_subtype: null});
const sent = [];
const api2 = async (path, options = {}) => {
  if (path === '/persons/p1/experiences') return lists;
  if (path === '/persons/p1/experiences?archived=true') return archivedLists;
  if (path === '/persons/p7') return {person: real, profile: null, experiences: {mine: 0, person_experiences: 0}, connections: []};
  if (path === '/persons/p7/experiences') return {records: {items: [], total: 0}, person_experiences: {items: [], total: 0, archived_total: 0}};
  if (path.startsWith('/person-experiences')) { sent.push({path, method: options.method, body: options.body}); return {}; }
  return api(path, options);
};
let toasts = [];
UI.initialize({state: {renderGeneration: 1, capabilities: {unified_people: true}, requests: new Map()}, api: api2, esc,
  link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1><p>${esc(subtitle)}</p>${action}`, empty: (m, a = '') => `<div class="empty">${esc(m)}${a}</div>`,
  time: x => 'T(' + x + ')', toast: m => toasts.push(m), requestId: () => 'rid', render: async () => { renders++; }, navigate() {},
  dialog: html => dialogs.push(html), closeDialog: () => { closed++; }});
const form = values => ({id: 'persons-exp-form', querySelector: selector => ({value: values[selector] ?? ''})});
const block = (html, name) => html.split('data-block="').find(part => part.startsWith(name + '"')) || '';
const cardOf = (html, id) => html.split('<article').find(part => part.includes('data-exp-card="' + id + '"')) || '';
"""


def test_tab_has_two_blocks_and_never_leaves_the_person_page():
    run_node(PREPARE + r"""
const html = await UI.detail('p1', 'experiences', new URLSearchParams('tab=experiences'));
const records = block(html, 'records'), people = block(html, 'person-experiences');
assert.ok(has(records, '我的經歷（1）') && has(records, '與周瑜討論合作') && has(records, 'T(2026-11-01T00:00:00+00:00)'), records);
assert.ok(!has(records, 'href="#record') && has(records, '以這位人物為主體的經歷'), records);  // 周瑜是歷史人物：不提供「記錄我和他的經歷」
assert.ok(has(people, '人物經歷（3）') && has(people, 'data-action="persons-exp-new" data-person-ref="p1"') && has(people, '＋ 新增人物經歷'), people);
assert.ok(has(people, 'href="#persons/p1?tab=experiences&amp;archived=1"') && has(people, '查看已封存的人物經歷（1）'));
assert.ok(!has(html, 'href="#person/') && !has(html, 'href="#history'), html);  // 不跳到舊人物頁或紀錄頁

const first = cardOf(html, 'x1');  // 主體；只知道年份＋時間描述
assert.ok(has(first, '平定江東') && has(first, '歷史') && has(first, '主體') && has(first, '199 年 · 建安四年') && has(first, '孫策'), first);
assert.ok(has(first, 'data-action="persons-exp-open" data-exp="x1"') && has(first, 'data-action="persons-exp-status" data-exp="x1" data-revision="2" data-status="archived"'), first);
const untitled = cardOf(html, 'x2');  // 沒有標題：顯示內容開頭；不知道時間
assert.ok(has(untitled, '少年時在廬江求學') && has(untitled, '時間不詳'), untitled);
const joined = cardOf(html, 'x3');  // 參與人物；多人時只列前 3 位
assert.ok(has(joined, '赤壁之戰') && has(joined, '虛構') && has(joined, '參與') && has(joined, '208 年 12 月') && has(joined, '等 5 人'), joined);
assert.ok(!has(joined, '>周瑜<'), joined);  // 不把目前人物自己列進「其他人物」

// 真實人物（非歷史）：提供「記錄我和他的經歷」，帶入人物並在完成後回到這個分頁
const realPage = await UI.detail('p7', 'experiences', new URLSearchParams('tab=experiences'));
assert.ok(has(realPage, 'href="#record?person=p7&amp;return=persons%2Fp7%3Ftab%3Dexperiences"') && has(realPage, '記錄我和他的經歷'), realPage);
assert.ok(has(realPage, '還沒有你和這位人物的紀錄') && has(realPage, '還沒有人物經歷'), realPage);
""")


def test_archived_view_lists_archived_experiences_with_restore_only():
    run_node(PREPARE + r"""
const html = await UI.detail('p1', 'experiences', new URLSearchParams('tab=experiences&archived=1'));
const people = block(html, 'person-experiences'), card = cardOf(html, 'x9');
assert.ok(has(people, '已封存的人物經歷（1）') && has(people, 'href="#persons/p1?tab=experiences"') && !has(people, 'persons-exp-new'), people);
assert.ok(has(card, 'data-status="active"') && has(card, '恢復') && has(card, 'data-action="persons-exp-open"') && !has(card, 'data-status="archived"'), card);
await click({action: 'persons-exp-open', exp: 'x9'});
const dialog = dialogs.at(-1);
assert.ok(has(dialog, '此經歷已封存') && has(dialog, '恢復這筆經歷') && !has(dialog, '儲存經歷') && !has(dialog, 'id="persons-exp-q"'), dialog);
await click({action: 'persons-exp-status', exp: 'x9', revision: '2', status: 'active'});
assert.deepEqual(sent.at(-1), {path: '/person-experiences/x9', method: 'PATCH', body: {expected_revision: 2, status: 'active', request_id: 'rid'}});
""")


def test_new_dialog_defaults_and_saves_with_date_precision_from_what_was_filled():
    run_node(PREPARE + r"""
await UI.detail('p1', 'experiences', new URLSearchParams('tab=experiences'));
await click({action: 'persons-exp-new', personRef: 'p1'});
let html = dialogs.at(-1);
assert.ok(has(html, 'id="account-heading">新增人物經歷') && has(html, '不計入積分、目標與互動統計'), html);
for (const id of ['persons-exp-title', 'persons-exp-q', 'persons-exp-content', 'persons-exp-type', 'persons-exp-year', 'persons-exp-month', 'persons-exp-day', 'persons-exp-label'])
  assert.ok(has(html, 'id="' + id + '"'), id);
assert.ok(has(html, '經歷主體') && has(html, '周瑜') && has(html, '<option value="historical" selected>歷史</option>'), html);  // 歷史人物預設「歷史」
assert.ok(has(html, '儲存經歷') && has(html, '取消') && !has(html, '建立者') && !has(html, '是否參與'), html);

const values = {'#persons-exp-title': ' 平定江東 ', '#persons-exp-content': '與孫策平定江東。', '#persons-exp-type': 'historical',
  '#persons-exp-year': '199', '#persons-exp-month': '', '#persons-exp-day': '', '#persons-exp-label': '建安四年'};
await UI.submit(form(values));
assert.deepEqual(sent.at(-1), {path: '/person-experiences', method: 'POST', body: {subject_person_id: 'p1', participant_ids: [], title: '平定江東',
  content: '與孫策平定江東。', experience_type: 'historical', occurred_precision: 'year', occurred_on: '199', occurred_label: '建安四年', request_id: 'rid'}});
assert.ok(closed === 1 && renders === 1 && toasts.at(-1).includes('已新增'));

// 日期：填到哪裡，精度就到哪裡；都沒填就是不知道
const precision = async extra => { await click({action: 'persons-exp-new', personRef: 'p1'}); await UI.submit(form({...values, ...extra})); return [sent.at(-1).body.occurred_precision, sent.at(-1).body.occurred_on]; };
assert.deepEqual(await precision({'#persons-exp-month': '12'}), ['month', '199-12']);
assert.deepEqual(await precision({'#persons-exp-month': '3', '#persons-exp-day': '5'}), ['day', '199-03-05']);
assert.deepEqual(await precision({'#persons-exp-year': ''}), ['unknown', null]);
// 填了月卻沒填年、填了日卻沒填月、沒有內容：不送出
const count = sent.length;
for (const extra of [{'#persons-exp-year': '', '#persons-exp-month': '12'}, {'#persons-exp-day': '5'}, {'#persons-exp-year': '二〇八'}, {'#persons-exp-content': '  '}]) {
  await click({action: 'persons-exp-new', personRef: 'p1'});
  await assert.rejects(UI.submit(form({...values, ...extra})));
}
assert.equal(sent.length, count);
""")


def test_participants_are_picked_continuously_and_capped_at_fifty():
    run_node(PREPARE + r"""
await UI.detail('p1', 'experiences', new URLSearchParams('tab=experiences'));
await click({action: 'persons-exp-new', personRef: 'p1'});
assert.ok(!has(dialogs.at(-1), 'data-action="persons-exp-pick"'));  // 還沒輸入關鍵字時不列出人物
let results = await UI.experienceSearch('周');
assert.ok(calls.some(x => x.path.startsWith('/persons?') && x.path.includes('status=active')));
assert.ok(!has(results, 'data-person-ref="p1"') && has(results, 'data-person-ref="p5"') && has(results, '虛構人物') && has(results, '架空三國的現代企業家'), results);  // 排除主體；同名靠類型與簡介分辨
await click({action: 'persons-exp-pick', personRef: 'p5'});
assert.equal(await UI.experienceSearch(''), '');  // 加入後搜尋已清空，可以直接輸入下一位
await UI.experienceSearch('孫');
await click({action: 'persons-exp-pick', personRef: 'p2'});
let chips = UI.experienceChips();
assert.ok(has(chips, '周瑜') && has(chips, '孫策') && has(chips, '已選 2／50') && has(chips, 'data-action="persons-exp-unpick" data-person-ref="p2"'), chips);
results = await UI.experienceSearch('周');
assert.ok(!has(results, 'data-person-ref="p2"') && !has(results, 'data-person-ref="p5"') && has(results, 'data-person-ref="p3"'), results);  // 已選的不再列出
await click({action: 'persons-exp-unpick', personRef: 'p5'});
assert.ok(!has(UI.experienceChips(), 'data-person-ref="p5"') && has(UI.experienceChips(), '已選 1／50'));
await UI.submit(form({'#persons-exp-content': '赤壁之戰。', '#persons-exp-type': 'historical'}));
assert.deepEqual(sent.at(-1).body.participant_ids, ['p2']);
""")


def test_edit_sends_only_changes_and_nature_cannot_be_changed():
    run_node(PREPARE + r"""
await UI.detail('p1', 'experiences', new URLSearchParams('tab=experiences'));
await click({action: 'persons-exp-open', exp: 'x1'});
const html = dialogs.at(-1);
assert.ok(has(html, 'id="account-heading">編輯人物經歷') && has(html, 'value="平定江東"') && has(html, '與孫策平定江東，建立基業。'), html);
assert.ok(has(html, 'id="persons-exp-type" disabled') && has(html, '建立後不能更改'), html);
assert.ok(has(html, 'value="199"') && has(html, 'value="建安四年"') && has(html, 'data-action="persons-exp-unpick" data-person-ref="p2"'), html);
assert.ok(has(html, 'data-action="persons-exp-status" data-exp="x1" data-revision="2" data-status="archived"'), html);  // 對話框內也能封存
const same = {'#persons-exp-title': '平定江東', '#persons-exp-content': '與孫策平定江東，建立基業。', '#persons-exp-type': 'historical',
  '#persons-exp-year': '199', '#persons-exp-month': '', '#persons-exp-day': '', '#persons-exp-label': '建安四年'};
await UI.submit(form(same));  // 沒有變更：不送出請求
assert.equal(sent.length, 0);

await click({action: 'persons-exp-open', exp: 'x1'});
await click({action: 'persons-exp-unpick', personRef: 'p2'});
await UI.submit(form({...same, '#persons-exp-title': '平定江東之戰', '#persons-exp-month': '6'}));
assert.deepEqual(sent.at(-1), {path: '/person-experiences/x1', method: 'PATCH', body: {expected_revision: 2, title: '平定江東之戰',
  occurred_precision: 'month', occurred_on: '199-06', participant_ids: [], request_id: 'rid'}});

// 目前人物是參與者時：主體顯示真正的主體，其他參與人物不含主體
await click({action: 'persons-exp-open', exp: 'x3'});
const joined = dialogs.at(-1);
assert.ok(has(joined, '諸葛亮') && has(joined, 'data-action="persons-exp-unpick" data-person-ref="p1"') && !has(joined, 'data-action="persons-exp-unpick" data-person-ref="p3"'), joined);
""")
