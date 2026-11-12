"""作品頁讀取生成進度：一次讀不到不能讓頁面停止更新。

2026-11-12 真實模型驗收時發現：背景生成中，作品頁有一次讀取進度拿到空白回應，頁面顯示錯誤後就不再更新，
停在「5/8 段」，而後端其實已經把 8 段都生成完。背景排程時生成在後端進行，頁面只是讀進度，所以讀不到要稍後再讀。

以 Node 直接執行 app/static/generation.js（假的 API，不開任何網站）。
"""
from test_run_export_view import run_node

EXTRA = r"""
const panel = {innerHTML: '', inserted: [], insertAdjacentHTML(position, html) { this.inserted.push(html); }};
document.getElementById = id => id === 'gen-run-panel' ? panel : null;
const running = () => ({...detail('running'), run: {...detail('running').run, completed_segments: 5, total_segments: 8}});
let replies = [], background = true, pauses = [];
const pollApi = async (path, options = {}) => {
  calls.push({path, method: options.method || 'GET'});
  if (path === '/generation/status') return {available: true, background};
  if (path === '/works/w1/exports') return {available: true, items: []};
  const next = replies.shift();
  if (next instanceof Error) throw next;
  return next;
};
const settle = async () => { for (let i = 0; i < 40 && replies.length; i++) await new Promise(resolve => setTimeout(resolve, 20)); await new Promise(resolve => setTimeout(resolve, 30)); };
const start = () => UI.initialize({state: {renderGeneration: 1}, api: pollApi, esc,
  link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button type="button" class="${style}" data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1><p>${esc(subtitle)}</p>${action}`, empty: m => m, time: x => x, toast() {},
  requestId: () => 'rid', render: async () => { renders++; }, navigate() {}, sleep: async ms => { pauses.push(ms); }});
"""


def test_background_progress_keeps_polling_after_a_failed_read():
    run_node(EXTRA + r"""
start();
replies = [running(), new Error('Unexpected end of JSON input'), new Error('offline'), running(), detail('completed')];
await UI.run('w1');   // 第一次讀取成功（生成中）；之後由頁面自己定期讀取
await settle();
assert.equal(replies.length, 0, '讀不到之後繼續讀，直到完成');
assert.equal(panel.inserted.filter(html => html.includes('暫時讀不到進度')).length, 2);  // 每次讀不到都說明：生成仍在後端進行
assert.ok(panel.inserted.every(html => !html.includes('Unexpected end of JSON input')));  // 不把內部錯誤訊息直接顯示出來
assert.ok(panel.innerHTML.includes('已完成'));  // 恢復之後畫面換成最新進度，提示也跟著消失
assert.equal(renders, 1);  // 完成：重畫整頁，下載區才會出現
assert.ok(pauses[0] >= 3000 && pauses[1] > pauses[0]);  // 連續讀不到時間隔拉長
""")


def test_foreground_stepping_still_stops_and_shows_the_error():
    run_node(EXTRA + r"""
background = false;   // 沒有背景排程的環境：頁面每次送出「推進一段」；失敗時停下來，不自動重送
start();
replies = [running(), new Error('推進失敗'), detail('completed')];
await UI.run('w1');
await new Promise(resolve => setTimeout(resolve, 150));
assert.equal(replies.length, 1, '失敗後不再自動送出');
assert.ok(panel.inserted.some(html => html.includes('推進失敗')));
assert.equal(renders, 0);
""")
