"""人物頁換頁時的捲動位置與返回列表（2026-11-11：Jerry 回報「列表 → 人物 → 編輯人物」頁面跳動）。

原因：主程式依網址記住捲動位置，編輯頁總是從底部的「儲存人物／返回人物」離開，下次開啟就直接停在表單底部。
規則：進入新頁面從頂端開始；同一頁重畫（例如封存關係後）與同一位人物切換分頁維持目前位置；
從人物頁回到人物列表時回到原本的列表位置，返回連結保留搜尋條件與頁數。
以 Node 直接執行 app/static/persons.js；實際畫面以部署後在 Local 8030（Cloud SQL life_world_e2e）的 Chrome 操作為準。
"""
from test_persons_relations_view import run_node


def test_new_pages_start_at_top_and_only_returning_to_the_list_restores_its_position():
    run_node(r"""
const target = UI.scrollTarget;
// 進入新頁面：從頂端開始（編輯頁不再停在上次離開的表單底部）
assert.equal(target('persons/p1', 'persons-edit/p1', 1200, 5980), 0);
assert.equal(target('persons', 'persons/p1', 400, 700), 0);
assert.equal(target('world', 'persons', 300, 400), 0);
assert.equal(target('persons-edit/p1', 'persons/p1', 5980, 900), 0);
assert.equal(target('persons/p1', 'persons/p2', 220, 0), 0);
assert.equal(target('persons?offset=0', 'persons?offset=50', 2400, 0), 0);  // 翻頁
assert.equal(target(null, 'persons-edit/p1', 0, 5980), 0);  // 第一次載入
// 同一頁重畫（儲存或封存關係後）：維持原位置
assert.equal(target('persons/p1?tab=relations', 'persons/p1?tab=relations', 640, 640), 640);
assert.equal(target('persons?q=a', 'persons?q=a', 1300, 1300), 1300);
// 同一位人物切換分頁：維持目前位置，分頁列不跳動
assert.equal(target('persons/p1?tab=overview', 'persons/p1?tab=relations', 220, 900), 220);
assert.equal(target('persons/p1', 'persons/p1?tab=profile', 180, 0), 180);
// 從人物頁（詳細、編輯、新增）回到列表：回到原本的列表位置
assert.equal(target('persons/p1?tab=relations', 'persons', 300, 1750), 1750);
assert.equal(target('persons-edit/p1', 'persons?q=%E5%91%A8', 300, 820), 820);
assert.equal(target('persons-new', 'persons', 0, 400), 400);
""")


def test_back_to_list_link_keeps_search_and_page_for_the_same_account():
    run_node(r"""
const state = {renderGeneration: 1, capabilities: {unified_people: true}, requests: new Map(), me: {owner_id: 'o1'}, route: 'persons?q=%E5%91%A8&sort=name&offset=0'};
UI.initialize({state, api, esc, link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1><p>${esc(subtitle)}</p>${action}`, empty: (m, a = '') => `<div class="empty">${esc(m)}${a}</div>`,
  time: x => x, toast() {}, requestId: () => 'rid', render: async () => {}, navigate() {}, dialog() {}, closeDialog() {}});
const back = html => (html.match(/<a class="text-button" href="#([^"]*)">← 返回人物列表<\/a>/) || [])[1];
// 還沒看過列表：回到預設列表
state.route = 'persons/p1';
assert.equal(back(await UI.detail('p1', 'overview', new URLSearchParams())), 'persons');
// 看過有搜尋條件的列表後：詳細頁與新增頁的返回連結回到同一個列表（含搜尋與頁數）
state.route = 'persons?q=%E5%91%A8&sort=name&offset=0';
await UI.list(new URLSearchParams('q=周&sort=name&offset=0'));
state.route = 'persons/p1';
assert.equal(back(await UI.detail('p1', 'overview', new URLSearchParams())), 'persons?q=%E5%91%A8&amp;sort=name&amp;offset=0');
state.route = 'persons-new';
assert.equal(back(UI.createForm()), 'persons?q=%E5%91%A8&amp;sort=name&amp;offset=0');
// 換了帳號：不沿用上一個帳號的搜尋條件
state.me = {owner_id: 'o2'};
assert.equal(back(UI.createForm()), 'persons');
""")


def test_list_card_is_one_link_to_the_person_page_and_archive_stays_a_separate_button():
    """Jerry 指定的流程：人物列表 →（點卡片或「編輯」）人物詳細頁 →（點「編輯人物」）編輯頁；列表不直接跳進完整的編輯表單。

    卡片整理（2026-11-11）：整張卡片可點、每張卡片只有一個連結（使用中「編輯」、已封存「查看」，都進人物詳細頁），
    姓名不再是另一個同目的地的連結；封存／恢復仍是獨立按鈕。
    """
    run_node(r"""
const html = await UI.list(new URLSearchParams(''));
const cardOf = id => html.split('<article').find(part => part.includes('"#persons/' + id + '"'));
const card = cardOf('p1');
assert.ok(card.includes('class="card char-card persons-list-card"'), card);
assert.equal((card.match(/<a /g) || []).length, 1, card);  // 只有一個連結
assert.ok(card.includes('<a class="text-button persons-card-open" href="#persons/p1" aria-label="編輯 周瑜">編輯</a>'), card);
assert.ok(card.includes('<strong class="persons-card-name">周瑜</strong>'), card);  // 姓名是標題，不是另一個連結
assert.ok(card.includes('data-action="persons-status"') && card.includes('>封存</button>'), card);
assert.ok(!has(html, 'href="#persons-edit/'), html);
const page = await UI.detail('p1', 'overview', new URLSearchParams());
assert.ok(has(page, 'href="#persons-edit/p1">編輯人物</a>'), page);  // 編輯表單只從詳細頁開啟

// 已封存的人物：連結是「查看」（仍進人物詳細頁，可在那裡恢復），按鈕是「恢復」
const archivedApi = async path => path.startsWith('/persons?') ? {items: [{...me, id: 'p4', name: '魯肅', status: 'archived'}], total: 1, offset: 0, limit: 50} : {};
UI.initialize({state: {renderGeneration: 1, capabilities: {unified_people: true}, requests: new Map()}, api: archivedApi, esc,
  link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1>${action}`, empty: (m, a = '') => `<div class="empty">${esc(m)}${a}</div>`,
  time: x => x, toast() {}, requestId: () => 'rid', render: async () => {}, navigate() {}, dialog() {}, closeDialog() {}});
const archived = await UI.list(new URLSearchParams('status=archived'));
assert.ok(archived.includes('<a class="text-button persons-card-open" href="#persons/p4" aria-label="查看 魯肅">查看</a>'), archived);
assert.ok(archived.includes('>恢復</button>'), archived);
""")
