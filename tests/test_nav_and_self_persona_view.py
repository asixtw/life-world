"""2026-11-11：左側導覽收掉舊的「關係」「角色」；「我的設定」放在人物首頁最上方，帳號視窗也有入口；紀錄頁的第一個頁籤是「我的經歷」。

以 Node 直接執行 app/static/persons.js（不開任何網站），檢查產生的 HTML。
這是開發時的快速檢查；實際畫面以部署後在 Local 8030（Cloud SQL life_world_e2e）的 Chrome 操作為準。
"""
from test_persons_relations_view import run_node

CONTEXT = r"""
const persona = {work_id: 'w1', version_no: 3, revision: 3, content: {display_name: '小傑 <b>', public_profile: '喜歡桌遊的工程師。', personality: '慢熟、好奇。',
  speaking_style: '語速慢。', motivation: '想把生活過明白。', values: '', behavior: '', knowledge: '', relationships: '', boundaries: '', appearance: '',
  sample_lines: ['先聽我說完。'], truth_level: 'real'}};
let selfData = {persona: null, consent: null}, selfFails = false;
const requested = [];
const pageApi = async (path, options = {}) => {
  requested.push(path);
  if (path === '/self-persona') { if (selfFails) throw new Error('offline'); return selfData; }
  if (path.startsWith('/persons?person_type=real&status=active')) return {items: [me, person('p8', '曹操'), person('p7', '王小明', {person_subtype: null})], total: 3, offset: 0, limit: 100};
  if (path.startsWith('/persons?')) return {items: [me, sun], total: 2, offset: 0, limit: 20};
  return {};
};
const context = (unified, api = pageApi) => ({state: {renderGeneration: 1, capabilities: {unified_people: unified}, requests: new Map(), route: 'persons'}, api, esc,
  link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1><p>${esc(subtitle)}</p>${action}`, empty: m => `<div class="empty">${esc(m)}</div>`,
  time: x => 'T(' + x + ')', toast() {}, requestId: () => 'rid', render: async () => {}, navigate() {}, dialog() {}, closeDialog() {}});
"""


def test_legacy_relation_and_character_entries_are_hidden_once_persons_is_available():
    run_node(CONTEXT + r"""
UI.initialize(context(true));
assert.deepEqual(UI.legacyNav(), []);  // 人物已取代：左側不再列「關係」「角色」
UI.initialize(context(false));
assert.deepEqual(UI.legacyNav(), [['people', '◌', '關係'], ['characters', '☆', '角色']]);  // 人物系統不可用時維持原本的入口
""")


def test_self_settings_card_summarises_my_settings_and_links_to_my_experiences():
    run_node(CONTEXT + r"""
UI.initialize(context(true));
const empty = UI.selfCard({persona: null, consent: null});
assert.ok(has(empty, 'data-block="self-persona"') && has(empty, '<h2>我的設定</h2>') && has(empty, '尚未建立'), empty);
assert.ok(has(empty, 'href="#persona"') && has(empty, '建立我的設定') && has(empty, 'AI 扮演你'), empty);
assert.ok(has(empty, 'href="#history"') && has(empty, '我的經歷'), empty);  // 我的設定旁邊可以直接去我的經歷

const draft = UI.selfCard({persona, consent: null});
assert.ok(has(draft, '小傑 &lt;b&gt;') && !has(draft, '小傑 <b>'), draft);  // 內容要跳脫
assert.ok(has(draft, '第 3 版') && has(draft, '真實的我') && has(draft, '喜歡桌遊的工程師。') && has(draft, '已填 6／12 欄'), draft);
assert.ok(has(draft, '尚未同意') && has(draft, '編輯我的設定') && !has(draft, '建立我的設定'), draft);
const agreed = UI.selfCard({persona, consent: {granted_at: '2026-11-11T00:00:00+00:00'}});
assert.ok(has(agreed, '已同意 AI 使用') && !has(agreed, '尚未同意'), agreed);

assert.equal(UI.selfCard(null), '');  // 讀不到資料時不顯示
UI.initialize(context(false));
assert.equal(UI.selfCard({persona: null, consent: null}), '');  // 人物系統不可用時不顯示
""")


def test_persons_home_starts_with_my_settings_then_the_people_list():
    run_node(CONTEXT + r"""
UI.initialize(context(true));
const home = await UI.list(new URLSearchParams(''));
assert.ok(has(home, 'data-block="self-persona"') && has(home, '建立我的設定'), home);
assert.ok(home.indexOf('data-block="self-persona"') < home.indexOf('id="persons-filter-form"'), '我的設定在搜尋與人物列表之前');
assert.ok(has(home, '人物（2）') && has(home, '周瑜') && has(home, '孫策'));
assert.ok(requested.includes('/self-persona'));

selfData = {persona, consent: null};
const filled = await UI.list(new URLSearchParams(''));
assert.ok(has(filled, '小傑') && has(filled, '第 3 版') && has(filled, '編輯我的設定'), filled);

// 搜尋、篩選或看封存時是在找人物：不顯示我的設定，也不多打一次 API（翻到第 2 頁以後也一樣，由 Chrome 驗收涵蓋）
for (const query of ['q=周', 'type=real', 'status=archived']) {
  requested.length = 0;
  const html = await UI.list(new URLSearchParams(query));
  assert.ok(!has(html, 'data-block="self-persona"') && !requested.includes('/self-persona'), query);
}

selfFails = true;  // 我的設定讀不到時，人物列表照常顯示
const fallback = await UI.list(new URLSearchParams(''));
assert.ok(!has(fallback, 'data-block="self-persona"') && has(fallback, '人物（2）'), fallback);
""")


def test_account_dialog_entry_only_for_signed_in_accounts():
    run_node(CONTEXT + r"""
UI.initialize(context(true));
const entry = UI.accountEntry({status: 'registered'});
assert.ok(has(entry, 'data-action="self-settings"') && has(entry, '我的設定'), entry);
assert.equal(UI.accountEntry({status: 'guest'}), '');  // 訪客沒有我的設定
assert.equal(UI.accountEntry(null), '');
UI.initialize(context(false));
assert.equal(UI.accountEntry({status: 'registered'}), '');
""")


def test_my_experiences_tab_and_people_that_can_be_linked_to_them():
    run_node(CONTEXT + r"""
UI.initialize(context(true));
const tabs = UI.recordTabs('mine');
assert.ok(has(tabs, 'aria-selected="true" href="#history">我的經歷</a>') && has(tabs, '人物經歷') && has(tabs, '全部'), tabs);

// 我的經歷只能關聯使用中的真實人物：歷史人物（周瑜、曹操）不列，沒有子類型的真人（王小明）可以
const ids = await UI.recordableIds();
assert.deepEqual([...ids], ['p7']);
assert.ok(requested.some(path => path === '/persons?person_type=real&status=active&limit=100'));

// 超過一次能讀的數量、讀取失敗或人物系統不可用：回 null，畫面不篩選
UI.initialize(context(true, async () => ({items: [person('p7', '王小明', {person_subtype: null})], total: 250})));
assert.equal(await UI.recordableIds(), null);
UI.initialize(context(true, async () => { throw new Error('offline'); }));
assert.equal(await UI.recordableIds(), null);
UI.initialize(context(false));
assert.equal(await UI.recordableIds(), null);
""")
