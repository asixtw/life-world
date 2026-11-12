/* 靜態視覺契約與素材失敗退路；這些斷言不代替瀏覽器版面驗收。 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const root = path.join(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

test('Soft Life 主題在舊樣式之後載入，四主分頁與現有腳本仍保留', () => {
  const html = read('app/static/index.html');
  assert.ok(html.indexOf('/static/softlife.css') > html.indexOf('/static/birth.css'));
  for (const name of ['experience', 'goals', 'connections', 'birth', 'app']) {
    assert.match(html, new RegExp(`/static/${name}\\.js`));
  }
  const app = read('app/static/app.js');
  for (const route of ['world', 'goals', 'history', 'people']) assert.ok(app.includes(`['${route}',`));
  assert.match(html, /name="theme-color" content="#fffdf8"/);
});

test('新 Lumi 圖片與核實 demo v1 完全相同，尺寸及既有 fallback 保留', () => {
  const image = fs.readFileSync(path.join(root, 'app/static/art/softlife/lumi-hero.png'));
  assert.equal(crypto.createHash('sha256').update(image).digest('hex'), '4fc69c850fd760cc85882d40b48ab1ea1eb946964e4d3dd6d2c0a21d95c50750');
  assert.equal(image.readUInt32BE(16), 1536);
  assert.equal(image.readUInt32BE(20), 1024);
  const source = read('app/static/app.js');
  const renderer = source.match(/function lumi\([^\n]+/)[0];
  const html = vm.runInNewContext(renderer + '\nlumi()');
  assert.equal((html.match(/data-lumi-art/g) || []).length, 1);
  assert.match(html, /\/static\/art\/softlife\/lumi-hero\.png/);
  assert.match(html, /data-lumi-fallback hidden/);
  assert.match(html, /alt="Lumi 溫暖地陪伴你"/);
});

test('新素材載入失敗仍回到既有 CSS Lumi，不依賴 API', () => {
  let listener;
  vm.runInNewContext(read('app/static/art.js'), {document: {addEventListener: (_, callback) => {listener = callback;}}});
  const fallback = {hidden: true};
  const image = {hidden: false, matches: selector => selector === '[data-lumi-art]', parentElement: {querySelector: () => fallback}};
  listener({target: image});
  assert.equal(image.hidden, true);
  assert.equal(fallback.hidden, false);
});

test('視覺主題包含窄螢幕、焦點及減少動態規則，不載入外部資源', () => {
  const css = read('app/static/softlife.css');
  for (const expected of ['max-width: 680px', 'max-width: 360px', 'focus-visible', 'prefers-reduced-motion: reduce', 'env(safe-area-inset-bottom)']) assert.ok(css.includes(expected));
  assert.doesNotMatch(css, /https?:\/\/|@import/);
  for (const name of ['lumi-idle', 'lumi-welcome', 'egg-rest', 'egg-fine', 'egg-deep', 'egg-open', 'world-day']) assert.ok(fs.existsSync(path.join(root, `app/static/art/${name}.png`)));
});

test('新增小字色與暖白／側欄／主視覺背景達到 4.5:1 對比', () => {
  const css = read('app/static/softlife.css');
  const color = css.match(/--muted:\s*(#[0-9a-f]{6})/)[1];
  function luminance(hex) {
    const channels = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map(c => c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4);
    return channels.reduce((sum, c, i) => sum + c * [.2126, .7152, .0722][i], 0);
  }
  for (const background of ['#fffdf8', '#f5f6ef', '#f5f6ed']) {
    const [dark, light] = [luminance(color), luminance(background)].sort((a, b) => a - b);
    assert.ok((light + .05) / (dark + .05) >= 4.5);
  }
  for (const selector of ['.eyebrow', '.brand small', '.sidebar-bottom', 'footer']) {
    const rule = css.slice(css.indexOf(selector + ' {')).split('}')[0];
    assert.ok(rule.includes('color: var(--muted)'), selector);
  }
});
