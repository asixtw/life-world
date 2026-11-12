/* 獨立介紹：固定示例只存在記憶體，不讀寫 Owner、帳本、儲存空間或產品 API。 */
(() => {
  'use strict';
  const root = document.querySelector('.lw-preview');
  const find = selector => root.querySelector(selector);
  const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const status = find('#live-status');
  const timing=window.LifeWorldHatchTiming;
  const mobile=window.matchMedia('(max-width: 760px)');
  let stage = 0, phase = 'welcome', busy = false, timer = null, generation = 0;
  const revealTimers = new Set(); // 第三擊子分鏡與主要完成計時器共同取消。

  /* 沿用已交付的柔和聲音候選，正式產品採用清單另行管理；偏好不持久化，關閉／離頁會釋放晚到的播放。 */
  const audio = (() => {
    const preferences = { music: false, sound: false };
    const voices = new Set();
    let background = null, active = true, suspended = false;
    const assets = {
      music: { url: '/static/intro/assets/audio/v1/login-v1.wav', kind: 'music' },
      tap: { url: '/static/intro/assets/audio/v1/ui-tap-v1.wav', kind: 'sound' },
      fine: { url: '/static/intro/assets/audio/v1/egg-fine-v1.wav', kind: 'sound' },
      deep: { url: '/static/intro/assets/audio/v1/egg-deep-v1.wav', kind: 'sound' },
      shell: { url: '/static/intro/assets/audio/v1/shell-open-v1.wav', kind: 'sound' },
      hatch: { url: '/static/intro/assets/audio/v1/first-hatch-v1.wav', kind: 'sound' }
    };
    function release(voice) {
      if (!voice) return;
      voice.stopped = true;
      voices.delete(voice);
      if (background === voice) background = null;
      try {
        voice.element.pause();
        voice.element.removeEventListener('ended', voice.cleanup);
        voice.element.removeEventListener('error', voice.cleanup);
        voice.element.removeAttribute('src');
        voice.element.load();
      } catch { /* 聲音失敗不能阻擋敘事。 */ }
    }
    function stop(kind) {
      for (const voice of [...voices]) if (!kind || voice.kind === kind) release(voice);
    }
    function play(name) {
      const asset = assets[name];
      if (!asset || !preferences[asset.kind] || !active || suspended || document.hidden) return;
      if (asset.kind === 'music' && background) return;
      if (asset.kind === 'sound') stop('sound');
      let voice;
      try {
        const element = new Audio(asset.url);
        voice = { element, kind: asset.kind, stopped: false, cleanup: null };
        voice.cleanup = () => release(voice);
        voices.add(voice);
        if (asset.kind === 'music') background = voice;
        element.loop = asset.kind === 'music';
        element.volume = asset.kind === 'music' ? 0.18 : 0.5;
        element.addEventListener('ended', voice.cleanup);
        element.addEventListener('error', voice.cleanup);
        Promise.resolve(element.play()).then(() => {
          if (voice.stopped || !preferences[voice.kind] || suspended || !active || document.hidden) release(voice);
        }, () => release(voice));
      } catch { release(voice); }
    }
    function set(kind, enabled) {
      preferences[kind] = enabled;
      if (!enabled) stop(kind);
      if (enabled && kind === 'music') play('music');
      find('.lw-audio').dataset.enabled = String(preferences.music || preferences.sound);
    }
    function scene(isActive) {
      active = isActive;
      stop();
      if (active) play('music');
    }
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stop(); else play('music');
    });
    window.addEventListener('pagehide', () => { suspended = true; stop(); });
    window.addEventListener('pageshow', () => { suspended = false; play('music'); });
    return { set, play, scene };
  })();
  find('#music-toggle').addEventListener('change', event => audio.set('music', event.target.checked));
  find('#sfx-toggle').addEventListener('change', event => audio.set('sound', event.target.checked));

  const stories = [
    {
      title: '每一點努力，\n都值得被記得。',
      description: '輕觸三次，看看一段真實經歷，如何留下成長與連結。',
      content: '<div class="lw-story-card"><div class="lw-card-label"><span>故事的起點</span><span>虛構示例</span></div><blockquote>有時是終於跨出的一小步，<br>有時是和某個人一起度過的片刻。</blockquote><p class="lw-card-foot">不必寫得完美，先把值得記得的事留下。</p></div>',
      button: '輕觸第一下，留下一段經歷',
      caption: '輕觸目標蛋，開始第一步 · 0 / 3'
    },
    {
      title: '留下一段經歷，\n也留下一次相遇。',
      description: '自己的進步，和一起走過的人，都藏在生活裡。',
      content: '<div class="lw-story-card"><div class="lw-card-label"><span>今天的一小步</span><span>虛構經歷</span></div><blockquote>「今天和小安練習英文 30 分鐘，<br>比上次更敢開口。」</blockquote><p class="lw-card-foot">一段努力：英文練習　・　一位互動者：小安</p></div>',
      button: '再輕觸一下，看看 AI 怎麼整理',
      caption: '細裂痕出現了，故事正在展開 · 1 / 3'
    },
    {
      title: 'AI 幫你整理，\n最後由你決定。',
      description: '摘要、下一步與人物資訊都只是候選。你可以修改、採納或排除。',
      content: '<div class="lw-story-card"><div class="lw-card-label"><span>AI 草稿示例</span><span>尚未確認</span></div><div class="lw-draft-row"><h2>↗ 我的成長</h2><p>摘要：完成 30 分鐘英文練習。<br>下一步候選：下次練習 10 分鐘對話。</p></div><div class="lw-draft-row"><h2>◎ 人物與互動</h2><p>互動者候選：小安。<br>共同經歷：一起練習英文。</p></div><p class="lw-card-foot">固定示例，沒有呼叫 AI；只是提及的人不會被算成互動。</p></div>',
      button: '確認這份示例，迎接 Lumi',
      caption: '裂痕慢慢擴大，由你決定留下什麼 · 2 / 3'
    }
  ];

  /* 用同寬的隱藏排版保留最長分鏡高度，字體／螢幕變化仍自然重排，不硬鎖像素或裁字。
     inert與aria-hidden使量測內容不進鍵盤或閱讀器；真正文案仍只有一份可操作呈現。 */
  const proseStack=find('.lw-prose-stack');
  // 單檔交付含預先呈現的DOM，重新初始化前先移除量測副本，避免累加。
  proseStack.querySelectorAll('.lw-prose-sizer').forEach(element=>element.remove());
  for(const story of [...stories,{title:'確認之後，\n世界才有回應。',description:'Lumi 正在登場。剛才的確認只屬於這段示例。',content:stories[2].content}]) {
    const sizer=document.createElement('div');
    sizer.className='lw-prose-sizer';sizer.inert=true;sizer.setAttribute('aria-hidden','true');
    const heading=document.createElement('h1');heading.textContent=story.title;heading.style.whiteSpace='pre-line';
    const description=document.createElement('p');description.className='lw-intro';description.textContent=story.description;
    const content=document.createElement('div');content.innerHTML=story.content; // 僅使用上述固定模板。
    sizer.append(heading,description,content);proseStack.append(sizer);
  }

  /* 切頁／跳過／重播使舊完成回呼失效，避免晚到動畫改寫新故事。 */
  function cancelTransition() {
    generation += 1;
    window.clearTimeout(timer);
    for (const id of revealTimers) window.clearTimeout(id);
    revealTimers.clear();
    timer = null;
    busy = false;
  }
  function announce(message) { status.textContent = message; }
  function focusHeading(selector) { find(selector).focus({ preventScroll: true }); }

  /* 手機把角色放在文案與主要操作之間；桌面保留穩定的雙欄，不裁切任何文案。 */
  function placeScene() {
    const scene=find('#scene');
    const parent=mobile.matches?find(phase==='welcome'?'#welcome-copy':phase==='summary'?'#summary-copy':'#experience-copy'):find('.lw-story');
    const anchor=mobile.matches?parent.querySelector(phase==='welcome'?'.lw-welcome-actions':phase==='summary'?'.lw-results':'.lw-stage-actions'):null;
    if(scene.parentElement===parent)return;
    const active=scene.contains(document.activeElement)?document.activeElement:null;
    parent.insertBefore(scene,anchor);
    active?.focus({preventScroll:true});
  }
  mobile.addEventListener('change',placeScene);

  function updateEgg() {
    root.querySelectorAll('[data-egg]').forEach(img => { img.hidden = Number(img.dataset.egg) !== stage; });
    const current = find(`[data-egg="${stage}"]`);
    const failed = current.dataset.failed === 'true';
    current.hidden = failed;
    find('.lw-egg-fallback').hidden = !failed;
    find('#egg').disabled = busy || phase !== 'story';
    find('#egg').setAttribute('aria-label', stories[Math.min(stage, 2)].button);
  }

  function render() {
    placeScene();
    root.dataset.phase = phase;
    root.dataset.stage = String(stage);
    root.dataset.busy = String(busy);
    find('#welcome-copy').hidden = phase !== 'welcome';
    find('#experience-copy').hidden = !['story', 'revealing'].includes(phase);
    find('#summary-copy').hidden = phase !== 'summary';
    find('#egg-scene').hidden = phase === 'summary' || phase === 'revealing';
    find('#lumi-scene').hidden = phase !== 'summary';
    find('#reveal-scene').hidden = phase !== 'revealing';
    find('#scene-note').textContent = phase === 'summary' ? '每一步，都有溫柔的回應。' : '每一個開始，都藏著可能。';
    if (phase === 'story' || phase === 'revealing') {
      const story = stories[Math.min(stage, 2)];
      find('#story-title').textContent = phase === 'revealing' ? '確認之後，\n世界才有回應。' : story.title;
      find('#story-title').style.whiteSpace = 'pre-line';
      find('#story-description').textContent = phase === 'revealing' ? 'Lumi 正在登場。剛才的確認只屬於這段示例。' : story.description;
      // 所有模板皆為程式內固定示例，不接受 URL／使用者 HTML。
      find('#story-content').innerHTML = story.content;
      find('#advance').textContent = busy ? '故事正在展開…' : story.button;
      find('#advance').disabled = busy;
      find('#egg-caption').textContent = phase === 'revealing' ? '蛋殼打開了，Lumi 就要出現 · 3 / 3' : story.caption;
      root.querySelectorAll('[data-step]').forEach(item => {
        if (Number(item.dataset.step) === Math.min(stage + 1, 3)) item.setAttribute('aria-current', 'step');
        else item.removeAttribute('aria-current');
      });
    } else {
      find('#egg-caption').textContent = '從一顆目標蛋，開始你的故事';
    }
    updateEgg();
  }

  function start() {
    cancelTransition(); stage = 0; phase = 'story';
    find('#how-it-works').hidden = true;
    find('#how-button').setAttribute('aria-expanded', 'false');
    audio.scene(true); render(); focusHeading('#story-title');
    announce('互動開始。輕觸目標蛋，或使用文字按鈕，共三次。');
  }
  function summary(skipped = false) {
    cancelTransition(); phase = 'summary'; stage = 3;
    audio.scene(true); render(); focusHeading('#summary-title');
    if (!skipped) audio.play('hatch');
    announce(skipped ? '已跳過演出。這是完整價值摘要，沒有確認或保存任何資料。' : '示例已完成。Lumi 登場；成長紀錄與人物互動皆為演示，沒有保存資料。');
    // 只發出呈現事件；產品接入層可保存介紹偏好，獨立原型本身仍不讀寫儲存空間。
    document.dispatchEvent(new CustomEvent('lifeworld:intro-finished',{detail:{outcome:skipped?'skipped':'completed'}}));
  }
  function advance() {
    if (phase !== 'story' || busy) return;
    busy = true; stage += 1;
    if (stage === 3) {phase = 'revealing';root.dataset.reveal='anticipate';}
    const currentGeneration = generation;
    audio.play(['','fine','deep','shell'][stage]); render();
    if(stage===3) {
      // 所有圖層留在共同畫布，先抬起蛋殼，再以先退後入的交接露出完整Lumi。
      for(const frame of timing.reveal.filter(frame=>frame.at>0)) {
        const id=window.setTimeout(()=>{
          revealTimers.delete(id);if(currentGeneration!==generation)return;
          root.dataset.reveal=frame.key;find('#scene-note').textContent=frame.label;
        },reducedMotion()?0:frame.at);revealTimers.add(id);
      }
    }
    announce(stage === 3 ? '你已確認這份示例，Lumi 正在登場。' : stories[stage].title.replace('\n', '') + ' 動畫中，請稍候。');
    // 時長與 CSS 相符；減少動效時立即靜態切換，但同一輪連點仍只算一次。
    timer = window.setTimeout(() => {
      if (currentGeneration !== generation) return;
      timer = null; busy = false;
      if (stage === 3) summary();
      else {
        render(); focusHeading('#story-title');
        announce(stories[stage].title.replace('\n', '') + ' ' + stories[stage].description);
      }
    }, reducedMotion() ? timing.reduced : stage === 3 ? timing.done : stage === 1 ? timing.fine : timing.deep);
  }
  function restart() {
    cancelTransition(); stage = 0; phase = 'welcome';
    audio.scene(false);
    find('#how-it-works').hidden = true;
    find('#how-button').setAttribute('aria-expanded', 'false');
    render(); find('#start').focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: 'instant' });
    announce('已回到故事起點。沒有儲存或改變任何產品資料。');
  }
  function how() {
    const section = find('#how-it-works');
    section.hidden = false;
    find('#how-button').setAttribute('aria-expanded', 'true');
    focusHeading('#how-title');
    section.scrollIntoView({ behavior: reducedMotion() ? 'instant' : 'smooth', block: 'start' });
  }
  root.addEventListener('click', event => {
    const action = event.target.closest('[data-action]');
    if (!action || action.disabled) return;
    event.preventDefault();
    ({ start, advance, skip: () => summary(true), restart, how })[action.dataset.action]?.();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && find('.lw-audio').open) {
      find('.lw-audio').open = false;
      find('.lw-audio summary').focus();
    }
  });

  // 圖片載入失敗仍保留互動與文字；快取錯誤可能早於腳本執行，須再檢查完整狀態。
  root.querySelectorAll('[data-egg]').forEach(img => {
    const failed = () => { img.dataset.failed = 'true'; updateEgg(); };
    img.addEventListener('error', failed);
    if (img.complete && img.naturalWidth === 0) failed();
  });
  const lumi = find('#lumi-art');
  const lumiFailed = () => { lumi.hidden = true; find('.lw-lumi-fallback').hidden = false; };
  lumi.addEventListener('error', lumiFailed);
  if (lumi.complete && lumi.naturalWidth === 0) lumiFailed();

  // 未來接入僅開啟已設定的入口；拒絕 script/data URL 及含憑證的地址。
  const configuredUrl = window.LifeWorldIntroConfig?.productEntryUrl;
  if (typeof configuredUrl === 'string' && configuredUrl.trim()) {
    try {
      const url = new URL(configuredUrl, location.href);
      if (['https:', 'http:'].includes(url.protocol) && !url.username && !url.password) {
        find('#product-entry').href = url.href;
        find('#product-entry').hidden = false;
      }
    } catch { /* 設定錯誤不影響獨立導覽。 */ }
  }
  render();
  // 手機初始化會移動場景；完成排版及事件綁定後才開放，避免下載中的第一擊落空。
  root.querySelectorAll('[data-intro-initial]').forEach(control=>{control.disabled=false;});
  root.dataset.ready='true';root.setAttribute('aria-busy','false');
})();
