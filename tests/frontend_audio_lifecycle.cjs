/* 直接執行產品 audio.js；Audio／頁面事件為明示替身，非原生解碼或人工聽審。 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../app/static/audio.js'), 'utf8');
const manifest = {assets: Object.fromEntries([
  ['login', 'music'], ['goals', 'music'], ['world', 'music'],
  ['ui-tap', 'sound'], ['experience-confirmed', 'sound'], ['first-hatch', 'sound'],
].map(([event, kind]) => [event, {kind, approved: true, url: `/static/audio/${event}.wav` }]))};

function setup(saved = null) {
  const tracks = [], listeners = new Map(), pageListeners = new Map(), writes = [];
  let delayed = false, constructorFailure = false;
  const document = {hidden: false, querySelector: () => null,
    addEventListener: (name, listener) => listeners.set(name, listener)};
  const window = {addEventListener: (name, listener) => pageListeners.set(name, listener)};
  class Audio {
    constructor(url) {
      if (constructorFailure) throw new Error('synthetic constructor failure');
      this.src = url; this.paused = true; this.listeners = new Map(); tracks.push(this);
    }
    play() {
      this.paused = false;
      if (!delayed) return Promise.resolve();
      return new Promise((resolve, reject) => {this.resolve = resolve; this.reject = reject;});
    }
    pause() {this.paused = true;}
    removeAttribute(name) {if (name === 'src') this.src = '';}
    load() {this.paused = true;}
    addEventListener(name, listener) {this.listeners.set(name, listener);}
    removeEventListener(name) {this.listeners.delete(name);}
    emit(name) {this.listeners.get(name)?.();}
  }
  vm.runInNewContext(source, {window, document, Audio, Set, localStorage: {
    getItem: () => JSON.stringify(saved), setItem: (_, value) => writes.push(JSON.parse(value)),
  }, fetch: () => Promise.reject(new Error('fixture does not use network'))});
  const api = window.WorldAudio;
  api.configure(manifest);
  return {api, tracks, writes, document,
    delay: () => {delayed = true;}, failConstructor: () => {constructorFailure = true;},
    gesture: () => listeners.get('pointerdown')?.({}),
    visibility: hidden => {document.hidden = hidden; listeners.get('visibilitychange')?.();},
    page: name => pageListeners.get(name)?.({persisted: true}),
  };
}
const flush = async () => {await Promise.resolve(); await Promise.resolve();};

test('預設不播；已保存偏好在第一次手勢前也不自動播', async () => {
  const fresh = setup(); assert.equal(await fresh.api.play('ui-tap'), false);
  const h = setup({sound: true, music: true}); h.api.route('world');
  assert.equal(h.tracks.length, 0); h.gesture(); await flush();
  assert.equal(h.tracks.length, 1); assert.match(h.tracks[0].src, /world.wav$/);
});
test('關閉音效立即停止所有在播音效，音樂不受影響', async () => {
  const h = setup(); h.api.set('music', true); h.gesture(); h.api.set('sound', true);
  await h.api.play('first-hatch'); await h.api.play('ui-tap'); h.api.set('sound', false);
  assert.equal(h.tracks[0].paused, false); assert.ok(h.tracks.slice(1).every(a => a.paused));
});
test('音效 pending 後停用，晚到成功不可留下聲音', async () => {
  const h = setup(); h.api.set('sound', true); h.delay(); const result = h.api.play('ui-tap');
  h.api.set('sound', false); h.tracks[0].paused = false; h.tracks[0].resolve();
  assert.equal(await result, false); assert.equal(h.tracks[0].paused, true);
});
test('音樂 pending 後停用，晚到成功不可留下聲音', async () => {
  const h = setup(); h.api.set('music', true); h.delay(); const result = h.api.play('login');
  h.api.set('music', false); h.tracks[0].paused = false; h.tracks[0].resolve();
  assert.equal(await result, false); assert.equal(h.tracks[0].paused, true);
});
test('路由切換停止舊 BGM，舊 Promise 不影響新場景', async () => {
  const h = setup(); h.delay(); h.api.set('music', true); h.gesture();
  h.api.route('world'); assert.equal(h.tracks.length, 2); assert.equal(h.tracks[0].paused, true);
  h.tracks[0].paused = false; h.tracks[0].resolve(); await flush();
  assert.equal(h.tracks[0].paused, true); assert.equal(h.tracks[1].paused, false);
  h.tracks[1].resolve(); await flush();
});
test('自動播放拒絕後，下次手勢可重試同場景', async () => {
  const h = setup(); h.delay(); h.api.set('music', true); h.gesture();
  h.tracks[0].reject(new Error('synthetic autoplay rejection')); await flush();
  h.gesture(); assert.equal(h.tracks.length, 2); h.tracks[1].resolve(); await flush();
});
test('重複手勢或路由不建立重疊 BGM', async () => {
  const h = setup(); h.delay(); h.api.set('music', true); h.gesture();
  for (let i = 0; i < 100; i++) {h.gesture(); h.api.route('welcome');}
  assert.equal(h.tracks.length, 1); h.tracks[0].resolve(); await flush();
});
test('背景頁停所有音軌，回前景只恢復目前場景 BGM', async () => {
  const h = setup(); h.api.set('music', true); h.gesture(); h.api.set('sound', true);
  await h.api.play('first-hatch'); h.visibility(true);
  assert.ok(h.tracks.every(a => a.paused)); assert.equal(await h.api.play('ui-tap'), false);
  h.api.route('world'); assert.equal(h.tracks.length, 2); h.visibility(false); await flush();
  assert.equal(h.tracks.length, 3); assert.match(h.tracks[2].src, /world.wav$/);
});
test('pagehide 清理，pageshow 不重播音效也不繞過使用者停用', async () => {
  const h = setup(); h.api.set('music', true); h.gesture(); h.api.set('sound', true);
  await h.api.play('first-hatch'); h.page('pagehide'); assert.ok(h.tracks.every(a => a.paused));
  h.api.set('music', false); h.page('pageshow'); assert.equal(h.tracks.length, 2);
});
test('返回頁面只恢復一條 BGM，重複可見事件不重疊', async () => {
  const h = setup(); h.api.set('music', true); h.gesture(); h.api.set('sound', true);
  await h.api.play('first-hatch'); h.visibility(true); h.page('pagehide'); h.api.route('goal-new');
  h.visibility(false); assert.equal(h.tracks.length, 2);
  h.page('pageshow'); h.visibility(false); h.page('pageshow'); await flush();
  assert.equal(h.tracks.length, 3); assert.match(h.tracks[2].src, /goals.wav$/);
  assert.equal(h.tracks.filter(a => !a.paused).length, 1);
});
test('新場景 BGM 缺失時停止舊場景，保留無聲退路', async () => {
  const h = setup(); h.api.configure({assets: {login: manifest.assets.login}});
  h.api.set('music', true); h.gesture(); await flush();
  h.api.route('world'); assert.equal(h.tracks.length, 1); assert.equal(h.tracks[0].paused, true);
});
test('素材撤銷立即停止已播與 pending 音軌', async () => {
  const h = setup(); h.api.set('sound', true); h.delay(); const result = h.api.play('ui-tap');
  h.api.configure({assets: {}}); assert.equal(h.tracks[0].paused, true);
  h.tracks[0].resolve(); assert.equal(await result, false);
});
test('非核准、外站與不合法 manifest 不可播放且不拋例外', async () => {
  const h = setup(); h.api.set('sound', true);
  assert.doesNotThrow(() => h.api.configure({assets: {null: null, foreign: {approved: true, kind: 'sound', url: 'https://example.invalid/a.wav'}, bad: {approved: true, kind: 'sound', url: '/static/audio/../secret.wav'}, no: {approved: false, kind: 'sound', url: '/static/audio/a.wav'}}}));
  for (const event of ['null', 'foreign', 'bad', 'no', 'toString']) assert.equal(await h.api.play(event), false);
  assert.equal(h.tracks.length, 0);
});
test('自然結束與媒體錯誤都釋放音訊來源', async () => {
  const h = setup(); h.api.set('sound', true); await h.api.play('ui-tap');
  h.tracks[0].emit('ended'); assert.equal(h.tracks[0].src, '');
  await h.api.play('first-hatch'); h.tracks[1].emit('error'); assert.equal(h.tracks[1].src, '');
});
test('快速連點音效有並發上限，停用後全部釋放', async () => {
  const h = setup(); h.api.set('sound', true);
  for (let i = 0; i < 100; i++) await h.api.play('ui-tap');
  assert.ok(h.tracks.filter(a => !a.paused).length <= 8);
  h.api.set('sound', false); assert.ok(h.tracks.every(a => a.paused && a.src === ''));
});
test('播放／建構失敗不拋到產品操作', async () => {
  const h = setup(); h.api.set('sound', true); h.failConstructor();
  assert.equal(await h.api.play('ui-tap'), false);
});
test('成功回執保留去重，偏好儲存不包含 owner 或回執', async () => {
  const h = setup(); h.api.set('sound', true);
  h.api.feedback('/drafts/synthetic/confirm', 'POST', {experience_id: 'synthetic-receipt'}, 'synthetic-owner');
  h.api.feedback('/drafts/synthetic/confirm', 'POST', {experience_id: 'synthetic-receipt'}, 'synthetic-owner');
  h.api.feedback('/drafts/synthetic/confirm', 'GET', {experience_id: 'different'}, 'synthetic-owner');
  assert.equal(h.tracks.length, 1); assert.deepEqual(h.writes, [{sound: true, music: false}]);
});
