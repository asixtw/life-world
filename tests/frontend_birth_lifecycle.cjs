/* 對實際 birth.js 操作確定性 DOM／計時替身；不冒充瀏覽器畫面驗收。 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../app/static/birth.js'), 'utf8');

function setup(reduced = false) {
  const callbacks = [], timers = [], sounds = [];
  const egg = {disabled: false, attributes: {}, addEventListener: (_, fn) => callbacks.push(fn), setAttribute(name, value) {this.attributes[name] = value;}};
  const status = {textContent: ''}, lumi = {hidden: true}, enter = {hidden: true, focused: 0, focus() {this.focused++;}};
  const children = {'[data-birth-egg]': egg, '[data-birth-status]': status, '[data-birth-lumi]': lumi, '[data-birth-enter]': enter};
  const root = {dataset: {stage: '0'}, isConnected: true, querySelector: name => children[name]};
  const window = {matchMedia: () => ({matches: reduced}), setTimeout: (fn, ms) => {timers.push({fn, ms});}, WorldAudio: {play: event => sounds.push(event)}};
  vm.runInNewContext(source, {window, document: {querySelector: () => root}, fetch: () => {throw new Error('孵化不得呼叫 API');}});
  window.BirthUI.mount();
  return {api: window.BirthUI, root, egg, status, lumi, enter, timers, sounds,
    click: () => callbacks.forEach(fn => fn()),
    tick: () => timers.shift()?.fn(),
  };
}

for (const reduced of [false, true]) test(`三次明確輸入、動畫鎖與最終聲音：reduced=${reduced}`, () => {
  const h = setup(reduced);
  for (let stage = 1; stage <= 3; stage++) {
    h.click(); assert.equal(h.root.dataset.stage, String(stage)); assert.equal(h.egg.disabled, true);
    for (let i = 0; i < 100; i++) h.click();
    assert.equal(h.root.dataset.stage, String(stage)); assert.equal(h.timers.length, 1);
    assert.equal(h.timers[0].ms, reduced ? 400 : 1400); assert.equal(h.enter.hidden, true);
    assert.deepEqual(h.sounds, []); h.tick();
    if (stage < 3) {assert.equal(h.egg.disabled, false); assert.equal(h.lumi.hidden, true);}
  }
  assert.equal(h.enter.hidden, false); assert.equal(h.lumi.hidden, false); assert.equal(h.enter.focused, 1);
  assert.deepEqual(h.sounds, ['first-hatch']); h.click(); assert.equal(h.timers.length, 0);
});
test('相同 DOM 重複 mount 不重綁、不重複播孵化聲或移動焦點', () => {
  const h = setup(); h.api.mount(); h.api.mount();
  for (let stage = 1; stage <= 3; stage++) {h.click(); assert.equal(h.timers.length, 1); h.tick();}
  assert.deepEqual(h.sounds, ['first-hatch']); assert.equal(h.enter.focused, 1);
  h.api.mount(); h.click(); assert.equal(h.timers.length, 0);
});
test('離開孵化頁後，舊計時器不可揭露、移焦或播放', () => {
  const h = setup(); h.click(); h.tick(); h.click(); h.tick(); h.click();
  h.root.isConnected = false; h.tick();
  assert.equal(h.enter.hidden, true); assert.equal(h.lumi.hidden, true);
  assert.equal(h.enter.focused, 0); assert.deepEqual(h.sounds, []);
});
test('既有顯示保留可讀狀態、三階段按鈕與美術 fallback 標記', () => {
  const h = setup(); const html = h.api.view('<span>合成 Lumi</span>');
  assert.match(html, /aria-live="polite"/); assert.match(html, /type="button"/);
  assert.match(html, /data-birth-enter hidden/); assert.match(html, /data-birth-lumi hidden/);
  for (const stage of ['rest', 'fine', 'deep', 'open']) assert.match(html, new RegExp(`/static/art/egg-${stage}.png`));
  assert.equal((html.match(/data-egg-art/g) || []).length, 4);
});
