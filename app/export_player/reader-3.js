(function () {
  // Life World 離線閱讀器 reader-3：內容已經寫在頁面裡，這段程式只負責閱讀偏好（字級、深淺色、場景提示）。
  // 人物顏色、陣營標籤、幕名與轉折都是 HTML 與樣式，不靠這段程式：程式不能執行的預覽工具裡一樣分得出來。
  // 沒有任何連線；偏好存在這個瀏覽器（沿用前一版的鍵，換新版不會忘記設定），存不了（例如直接點開的檔案被限制）也照常閱讀。
  var root = document.documentElement;
  var tools = document.querySelector('.lw-tools');
  if (!tools) return;
  var KEY = 'lw-reader-prefs';
  var SIZES = ['s', 'm', 'l', 'xl'];
  var prefs = {theme: '', size: 'm', stage: 'on'};
  try {
    var saved = JSON.parse(window.localStorage.getItem(KEY) || 'null');
    if (saved && typeof saved === 'object') {
      Object.keys(prefs).forEach(function (key) { if (typeof saved[key] === 'string') prefs[key] = saved[key]; });
    }
  } catch (error) { /* 讀不到就用預設值 */ }

  function isDark() {
    var theme = root.getAttribute('data-theme');
    if (theme) return theme === 'dark';
    return Boolean(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  }

  function apply() {
    if (prefs.theme === 'dark' || prefs.theme === 'light') root.setAttribute('data-theme', prefs.theme);
    else root.removeAttribute('data-theme');
    root.setAttribute('data-size', SIZES.indexOf(prefs.size) < 0 ? 'm' : prefs.size);
    root.setAttribute('data-stage', prefs.stage === 'off' ? 'off' : 'on');
    var stage = tools.querySelector('[data-tool=stage]');
    if (stage) stage.setAttribute('aria-pressed', prefs.stage === 'off' ? 'false' : 'true');
    var theme = tools.querySelector('[data-tool=theme]');
    if (theme) theme.textContent = isDark() ? '淺色' : '深色';
    try { window.localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (error) { /* 存不了不影響閱讀 */ }
  }

  tools.addEventListener('click', function (event) {
    var button = event.target.closest ? event.target.closest('button[data-tool]') : null;
    if (!button) return;
    var tool = button.getAttribute('data-tool');
    if (tool === 'smaller' || tool === 'larger') {
      var index = SIZES.indexOf(prefs.size);
      if (index < 0) index = 1;
      prefs.size = SIZES[Math.max(0, Math.min(SIZES.length - 1, index + (tool === 'larger' ? 1 : -1)))];
    } else if (tool === 'theme') {
      prefs.theme = isDark() ? 'light' : 'dark';
    } else if (tool === 'stage') {
      prefs.stage = prefs.stage === 'off' ? 'on' : 'off';
    }
    apply();
  });

  apply();
  tools.hidden = false;
})();
