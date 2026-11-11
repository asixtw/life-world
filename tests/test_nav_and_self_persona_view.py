"""2026-11-11：左側導覽收掉舊的「關係」「角色」，以及「我的紀錄」上方的「我的人設」入口。

以 Node 直接執行 app/static/persons.js（不開任何網站），檢查產生的 HTML。
這是開發時的快速檢查；實際畫面以部署後在 Local 8030（Cloud SQL life_world_e2e）的 Chrome 操作為準。
"""
from test_persons_relations_view import run_node

CONTEXT = r"""
const context = unified => ({state: {renderGeneration: 1, capabilities: {unified_people: unified}, requests: new Map()}, api: async () => ({}), esc,
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


def test_my_records_shows_a_self_persona_card_with_an_edit_entry():
    run_node(CONTEXT + r"""
UI.initialize(context(true));
const empty = UI.selfCard({persona: null, consent: null});
assert.ok(has(empty, 'data-block="self-persona"') && has(empty, '我的人設') && has(empty, '尚未建立'), empty);
assert.ok(has(empty, 'href="#persona?from=history"') && has(empty, '建立我的人設'), empty);
assert.ok(has(empty, 'AI 扮演你'), empty);  // 說明用途：讓 AI 扮演「我」

const content = {display_name: '小傑 <b>', public_profile: '喜歡桌遊的工程師。', personality: '慢熟、好奇。', speaking_style: '語速慢。', motivation: '想把生活過明白。',
  values: '', behavior: '', knowledge: '', relationships: '', boundaries: '', appearance: '', sample_lines: ['先聽我說完。'], truth_level: 'real'};
const draft = UI.selfCard({persona: {work_id: 'w1', version_no: 3, revision: 3, content}, consent: null});
assert.ok(has(draft, '小傑 &lt;b&gt;') && !has(draft, '小傑 <b>'), draft);  // 內容要跳脫
assert.ok(has(draft, '第 3 版') && has(draft, '真實的我') && has(draft, '喜歡桌遊的工程師。') && has(draft, '已填 6／12 欄'), draft);
assert.ok(has(draft, '尚未同意') && has(draft, 'href="#persona?from=history"') && has(draft, '編輯我的人設') && !has(draft, '建立我的人設'), draft);

const agreed = UI.selfCard({persona: {work_id: 'w1', version_no: 3, revision: 3, content}, consent: {granted_at: '2026-11-11T00:00:00+00:00'}});
assert.ok(has(agreed, '已同意 AI 使用') && !has(agreed, '尚未同意'), agreed);

assert.equal(UI.selfCard(null), '');  // 讀不到資料時不顯示，不影響我的紀錄
UI.initialize(context(false));
assert.equal(UI.selfCard({persona: null, consent: null}), '');  // 人物系統不可用時不顯示
""")
