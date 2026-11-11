"""人物經歷 E2／E3 的畫面輸出：紀錄頁的三個頁籤、從紀錄頁新增人物經歷（先選主體）、關係來源可選人物經歷。

以 Node 直接執行 app/static/persons.js（假的 API 與假的對話框，不開任何網站），檢查產生的 HTML 與送出的請求。
這是開發時的快速檢查；實際畫面以部署後在 Local 8030（Cloud SQL life_world_e2e）的 Chrome 操作為準。
"""
from test_persons_experiences_view import PREPARE
from test_persons_relations_view import run_node

RECORDS = PREPARE + r"""
const all = {items: [exp('x1'), exp('x2', {title: '', content: '少年時在廬江求學。', occurred_precision: 'unknown', occurred_on: null, occurred_label: '', participants: []}),
  exp('x3', {title: '赤壁之戰', subject: summary(zhuge), participants: [summary(me), ...many], occurred_precision: 'month', occurred_on: '0208-12', occurred_label: '',
    experience_type: 'fictional'})], total: 3, archived_total: 1};
const api3 = async (path, options = {}) => {
  if (path === '/person-experiences' && !options.method) return all;
  if (path === '/person-experiences?archived=true') return {items: [exp('x9', {status: 'archived', title: '舊的經歷'})], total: 3, archived_total: 1};
  if (path.startsWith('/persons/p1/connection-sources')) return {items: [{id: 'e2', summary: '江東會議', occurred_at: '2026-11-02T00:00:00+00:00'}], total: 1,
    person_experiences: {items: [{id: 'x1', title: '平定江東', experience_type: 'historical', occurred_precision: 'year', occurred_on: '0199', occurred_label: '建安四年', subject: '周瑜'},
      {id: 'x7', title: '架空世界共同創業', experience_type: 'fictional', occurred_precision: 'unknown', occurred_on: null, occurred_label: '', subject: '孫策'}], total: 2}};
  return api2(path, options);
};
UI.initialize({state: {renderGeneration: 1, capabilities: {unified_people: true}, requests: new Map()}, api: api3, esc,
  link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1><p>${esc(subtitle)}</p>${action}`, empty: (m, a = '') => `<div class="empty">${esc(m)}${a}</div>`,
  time: x => 'T(' + x + ')', toast: m => toasts.push(m), requestId: () => 'rid', render: async () => { renders++; }, navigate() {},
  dialog: html => dialogs.push(html), closeDialog: () => { closed++; }});
const mine = {records: [{id: 'r1', occurred_at: '2026-11-01T00:00:00+00:00'}, {id: 'r2', occurred_at: '0150-01-01T00:00:00+00:00'}],
  recordCard: (e, typeTag) => `<article data-record="${e.id}">${typeTag ? '我的紀錄' : ''}</article>`};
const tabs = UI.recordTabs('people');
"""


def test_records_page_has_three_tabs_and_lists_person_experiences_with_clickable_people():
    run_node(RECORDS + r"""
for (const route of ['history', 'history?view=people', 'history?view=all']) assert.ok(has(tabs, 'href="#' + route + '"'), tabs);
assert.ok(has(tabs, 'aria-selected="true" href="#history?view=people"') && has(tabs, 'aria-selected="false" href="#history"'), tabs);
assert.ok(has(tabs, '我的紀錄') && has(tabs, '人物經歷') && has(tabs, '全部'));

const html = await UI.recordsPage('people', new URLSearchParams('view=people'), tabs, mine);
assert.ok(has(html, tabs) && has(html, '人物經歷（3）') && has(html, 'data-action="persons-exp-new"') && has(html, '＋ 新增人物經歷'), html);
assert.ok(has(html, 'href="#history?view=people&amp;archived=1"') && has(html, '查看已封存的人物經歷（1）'));
const card = cardOf(html, 'x3');  // 顯示主體與其他參與人物；姓名可以點進該人物的經歷頁籤；多人只列前 3 位
assert.ok(has(card, '主體：<a href="#persons/p3?tab=experiences">諸葛亮</a>') && has(card, '參與：') && has(card, 'href="#persons/p1?tab=experiences">周瑜</a>'), card);
assert.ok(has(card, '等 6 人') && has(card, '虛構') && has(card, '208 年 12 月') && has(card, '赤壁之戰'), card);
assert.ok(has(card, 'data-action="persons-exp-open" data-exp="x3"') && has(card, 'data-status="archived"'), card);
assert.ok(has(cardOf(html, 'x2'), '少年時在廬江求學') && has(cardOf(html, 'x2'), '時間不詳') && !has(cardOf(html, 'x2'), '參與：'));

const archived = await UI.recordsPage('people', new URLSearchParams('view=people&archived=1'), tabs, mine);
assert.ok(has(archived, '已封存的人物經歷（1）') && has(archived, '舊的經歷') && !has(archived, 'persons-exp-new') && has(archived, 'href="#history?view=people"'), archived);

// 從紀錄頁開啟：與人物頁是同一個對話框、同一筆資料
await UI.recordsPage('people', new URLSearchParams('view=people'), tabs, mine);
await click({action: 'persons-exp-open', exp: 'x1'});
assert.ok(has(dialogs.at(-1), 'id="account-heading">編輯人物經歷') && has(dialogs.at(-1), 'value="平定江東"') && !has(dialogs.at(-1), '更換主體'));
await click({action: 'persons-exp-status', exp: 'x1', revision: '2', status: 'archived'});
assert.deepEqual(sent.at(-1), {path: '/person-experiences/x1', method: 'PATCH', body: {expected_revision: 2, status: 'archived', request_id: 'rid'}});
""")


def test_all_tab_merges_both_kinds_newest_first_with_type_tags_and_unknown_dates_last():
    run_node(RECORDS + r"""
const merged = await UI.recordsPage('all', new URLSearchParams('view=all'), UI.recordTabs('all'), mine);
const order = [...merged.matchAll(/data-record="(r\d)"|data-exp-card="(x\d)"/g)].map(m => m[1] || m[2]);
assert.deepEqual(order, ['r1', 'x3', 'x1', 'r2', 'x2']);  // 2026、208 年 12 月、199 年、150 年、不知道時間
assert.ok(has(merged, '全部（5）') && has(merged, '<article data-record="r1">我的紀錄</article>'), merged);
assert.ok(has(cardOf(merged, 'x1'), '>人物經歷<') && has(cardOf(merged, 'x1'), '歷史'), merged);  // 每筆標示類型
assert.ok(has(merged, 'href="#record"') && has(merged, 'data-action="persons-exp-new"'), merged);  // 兩種新增入口都在
""")


def test_new_from_records_page_picks_the_subject_first_and_uses_the_same_form():
    run_node(RECORDS + r"""
await UI.recordsPage('people', new URLSearchParams('view=people'), tabs, mine);
await click({action: 'persons-exp-new'});
const html = dialogs.at(-1);
assert.ok(has(html, 'id="account-heading">新增人物經歷') && has(html, 'id="persons-exp-subject-q"') && !has(html, '更換主體'), html);
for (const id of ['persons-exp-title', 'persons-exp-q', 'persons-exp-content', 'persons-exp-type', 'persons-exp-year', 'persons-exp-label']) assert.ok(has(html, 'id="' + id + '"'), id);
await assert.rejects(UI.submit(form({'#persons-exp-content': '還沒選主體'})));  // 沒有主體不能儲存
assert.equal(sent.length, 0);

const found = await UI.experienceSubjectSearch('周');
assert.ok(has(found, 'data-action="persons-exp-subject-pick" data-person-ref="p1"') && has(found, 'data-person-ref="p5"'), found);
assert.ok(has(found, '虛構人物') && has(found, '架空三國的現代企業家'), found);  // 同名人物靠類型與簡介分辨
await click({action: 'persons-exp-subject-pick', personRef: 'p5'});
assert.ok(has(UI.experienceSubject(), '架空三國的現代企業家') && has(UI.experienceSubject(), '更換主體') && !has(UI.experienceSubject(), 'persons-exp-subject-q'));
assert.ok(!has(await UI.experienceSearch('周'), 'data-person-ref="p5"'));  // 主體不會再出現在參與人物的搜尋結果
await UI.submit(form({'#persons-exp-content': '在架空世界共同創業。'}));
assert.deepEqual(sent.at(-1), {path: '/person-experiences', method: 'POST', body: {subject_person_id: 'p5', participant_ids: [], title: '', content: '在架空世界共同創業。',
  experience_type: 'fictional', occurred_precision: 'unknown', occurred_on: null, occurred_label: '', request_id: 'rid'}});  // 性質預設跟著主體的人物類型

await click({action: 'persons-exp-new'});
await UI.experienceSubjectSearch('孫');
await click({action: 'persons-exp-subject-pick', personRef: 'p2'});
await click({action: 'persons-exp-subject-clear'});
assert.ok(has(UI.experienceSubject(), 'id="persons-exp-subject-q"'));  // 更換主體：回到搜尋
""")


def test_relation_sources_offer_person_experiences_and_cards_show_both_kinds():
    run_node(RECORDS + r"""
detail.connections[0].source_person_experience_ids = ['x1'];
detail.connections[0].sources.person_experiences = [{id: 'x1', title: '平定江東', experience_type: 'historical', occurred_precision: 'year', occurred_on: '0199',
  occurred_label: '建安四年', subject: '周瑜'}];
const page = await UI.detail('p1', 'relations', new URLSearchParams(''));
assert.ok(has(page, '來源：1 筆我的紀錄、1 筆人物經歷') && has(page, '平定江東') && has(page, '歷史'), page);  // 關係卡片列出兩種來源
assert.ok(has(page, '來源：1 筆我的紀錄') || true);

await click({action: 'persons-relation-new', personRef: 'p1'});
await click({action: 'persons-relation-pick', personRef: 'p9'});
let html = dialogs.at(-1);
assert.ok(has(html, 'name="relation_source" value="e2"') && has(html, '江東會議'), html);  // 我的紀錄來源照舊
assert.ok(has(html, 'name="relation_person_source" value="x1"') && has(html, '平定江東') && has(html, '199 年 · 建安四年'), html);
assert.ok(has(html, 'name="relation_person_source" value="x7"') && has(html, '架空世界共同創業') && has(html, '虛構') && !has(html, 'value="x7" checked'), html);

// 編輯既有關係：原本引用的人物經歷已勾選、排在最前面
await click({action: 'persons-relation-edit', connection: 'c1'});
html = dialogs.at(-1);
assert.ok(has(html, 'name="relation_person_source" value="x1" checked') && has(html, 'name="relation_source" value="e1" checked'), html);
assert.ok(html.indexOf('value="x1"') < html.indexOf('value="x7"'), html);
""")
