// 玩的遊戲（回合制互動作品，第 1 期只有「行程」這一種題材，2026-11-12）：查看的頁面。
// - 建立不在這裡：2026-11-12 起只有一個建立入口，在建立頁（#create，creation.js）第一步選「玩的遊戲」，送出後到這裡。
//   舊的 #game-new 由主程式轉到建立頁並預選玩的遊戲。
// - #game/{id}：規劃之後，每位同行者各要一次生成（想好他在每一站的反應）。這一頁開著就一位一位往下做（POST …/advance），
//   全部完成才能玩；離開就暫停，回來接著做。某一次失敗時說明原因、稍等再試（間隔逐次拉長），也可以自己按「再試一次」。
//   為了不讓一直失敗的生成反覆花錢，自動重試有次數上限；超過之後只留手動的按鈕。
// - 準備好之後：「在這裡玩」與「下載互動遊戲」。兩顆都交給作品頁的匯出流程（GenerationUI 的 gen-play-here／gen-export）：
//   先請伺服器匯出（內容沒有變就沿用上一次），再放進頁面上的 iframe，或下載那個檔案。
//   用語和看的故事的作品頁一致：「在這裡…」是不用下載、直接在這一頁打開；「下載…」是存成一個可以離線打開的 HTML 檔。
// 這一頁不顯示任何反應、願望與結局的文字（伺服器也不回傳）：玩的人不應該先被劇透。
window.GameUI = (() => {
  let c;
  const KIND = '玩的遊戲'; // 這種作品在畫面上的叫法：和作品清單的種類標籤、建立頁的玩法同一個說法
  const AUTO_RETRIES = 5; // 連續失敗時最多自動再試幾次；之後只留「再試一次」按鈕
  const FIRST_WAIT = 5000, LONGEST_WAIT = 60000; // 失敗後第一次等多久（毫秒），之後每次加倍，最長等多久
  let waiting = null; // 正在等下一次自動重試：按「再試一次」就提早結束這段等待
  let stopped = null; // 已經停止自動重試的那一件遊戲：{id, build}；按「再試一次」從這裡重新開始
  // 每件遊戲目前是第幾次嘗試：提交代碼的範圍用它區分（2026-11-12 外部檢驗）。
  // 成功、或伺服器確認失敗（有狀態碼，且不是「還在進行」）→ 下一次嘗試，用新的提交代碼；
  // 連線中斷等結果不明、或還在進行 → 沿用同一個提交代碼：伺服器若其實已經做完，重送只會找回那一次的結果，不會再付費生成一次。
  const attempts = new Map();
  const nextAttempt = id => attempts.set(id, (attempts.get(id) || 1) + 1);

  function initialize(context) { c = context; }
  const h = value => c.esc(value);
  const fresh = ticket => ticket === c.state.renderGeneration;
  const path = id => encodeURIComponent(id);
  const pause = ms => (c.sleep ? c.sleep(ms) : new Promise(resolve => setTimeout(resolve, ms))); // 測試可以換成不真的等待
  const clock = minutes => `${String(Math.floor(minutes / 60) % 24).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;

  // ---- 查看：準備中 ----
  function progress(build) { // 進度裡的第一項是規劃（建立時已經完成）；其餘每位同行者一項
    const total = Math.max(0, (Number(build.total) || 1) - 1);
    const done = Math.max(0, Math.min(total, (Number(build.done) || 0) - 1));
    return {done, total, text: `正在請每位同行者想好反應：${done}／${total}`};
  }

  // problem：最近一次失敗——{message, wait}；wait 是幾秒後自動再試，0 表示已經停止自動重試
  function buildPanel(id, build, problem = null) {
    const state = progress(build);
    const trouble = problem ? `<p class="callout gen-error" role="alert">${h(problem.message)}</p>
      <p class="small muted">${problem.wait ? `約 ${problem.wait} 秒後自動再試；已經完成的部分都保留著。` : '已經停止自動重試；已經完成的部分都保留著，可以稍後再按「再試一次」。'}</p>
      <div class="button-row">${c.button('game-retry', '再試一次', 'secondary', `data-id="${h(id)}"`)}</div>` : '';
    return `<p><strong>準備中</strong>　${h(state.text)}</p>
      <progress max="${state.total || 1}" value="${state.done}" aria-label="同行者的反應完成了幾位"></progress>
      <p class="small muted">每位同行者會先想好自己在每一站的反應，全部完成之後才能玩。這一頁開著就會自動繼續；離開就暫停，回來會接著做。</p>${trouble}`;
  }

  /** 頁面開著時一位一位往下做；換頁（renderGeneration 改變）就停。提交代碼依上面的 attempts 規則決定要不要換。 */
  async function advance(id, ticket, build) {
    let failures = 0;
    stopped = null;
    const paint = problem => {
      const target = document.getElementById('game-build-panel');
      if (target) target.innerHTML = buildPanel(id, build, problem);
    };
    while (fresh(ticket)) {
      try {
        const result = await c.api(`/games/${path(id)}/advance`, {method: 'POST', body: {request_id: c.requestId(`game-advance:${id}:${attempts.get(id) || 1}`, {})}});
        nextAttempt(id);
        if (!fresh(ticket)) return;
        failures = 0;
        build = result.build;
        paint(null);
        if (build.status === 'ready') { await c.render(); return; } // 剛完成：重畫整頁，換成可以玩的樣子
      } catch (error) {
        if (Number.isInteger(error.status) && !(error.status === 409 && error.code === 'generation_in_progress')) nextAttempt(id);
        if (!fresh(ticket)) return;
        failures += 1;
        // 找不到、沒有權限：再試也一樣，直接停。其餘（模型暫時失敗、金額上限、連線中斷）稍等再試，間隔逐次拉長；
        // 連續失敗太多次就不再自動試——每一次都可能是一次要付費的模型呼叫，交給使用者決定什麼時候再按。
        const final = [401, 403, 404].includes(error.status) || failures > AUTO_RETRIES;
        const wait = final ? 0 : Math.min(FIRST_WAIT * 2 ** (failures - 1), LONGEST_WAIT);
        paint({message: error.message || '這一步沒有完成。', wait: Math.round(wait / 1000)});
        if (final) { stopped = {id, build}; return; }
        await new Promise(resolve => { // 等到時間到，或使用者按了「再試一次」
          const done = () => { if (waiting === done) waiting = null; resolve(); };
          waiting = done;
          pause(wait).then(done);
        });
      }
    }
  }

  // ---- 查看：準備好了 ----
  function playView(game, exports) {
    if (!exports) return '';
    if (!exports.available) return '<section class="card space-top"><p class="small muted">這個環境還沒有開放下載作品，暫時不能玩。</p></section>';
    const last = exports.items[0];
    // 說明的寫法和看的故事的作品頁（GenerationUI 的 exportView）一致：先講「在這裡…」，再講「下載…」，最後講檔案裡有什麼
    return `<section class="card space-top" id="gen-export"><h2>開始玩</h2>
      <p class="small muted">「在這裡玩」不用下載，直接在這一頁打開。「下載互動遊戲」把這個遊戲存成一個 HTML 檔，下載後可以離線打開，也可以傳給沒有帳號的親友玩。檔案裡不含人物設定的欄位與我的設定；台詞與反應是 AI 依人物設定寫出來的，可能用到設定裡的說法，分享前可以先看過。</p>
      <div class="button-row">${c.button('gen-play-here', '在這裡玩', 'primary', `data-id="${h(game.id)}"`)}
        ${c.button('gen-export', '下載互動遊戲', 'secondary', `data-id="${h(game.id)}" data-player="play" data-name="互動遊戲"`)}</div>
      ${last ? `<p class="small muted">上次匯出：${h(c.time(last.created_at))}・${(last.size / 1024).toFixed(1)} KB</p>` : ''}
      <div id="gen-inline-player" class="inline-player" hidden></div></section>`;
  }

  async function view(id) {
    const ticket = c.state.renderGeneration;
    const game = await c.api('/games/' + path(id));
    if (!fresh(ticket)) return '';
    const cast = (game.cast || []).map(member => h(member.name)).join('、');
    const head = `${c.link('works', '← 作品', 'text-button')}${c.heading(game.title || KIND, KIND)}`;
    if (game.build?.status !== 'ready') { // 還在準備：顯示進度，並從這裡接著做
      setTimeout(() => advance(id, ticket, game.build), 50);
      return `${head}<section class="card" id="game-build-panel" aria-live="polite">${buildPanel(id, game.build || {})}</section>
        <section class="card space-top"><dl class="char-fields"><dt>同行的人</dt><dd>${cast}</dd></dl></section>`;
    }
    const exports = await c.api('/works/' + path(id) + '/exports').catch(() => null); // 讀不到時不擋住這一頁，只是沒有按鈕
    if (!fresh(ticket)) return '';
    const hours = game.hours ?? Math.round((game.clock?.limit || 0) / 60);
    const label = game.meter?.label || '';
    return `${head}
      <section class="card stack">${game.premise ? `<p class="callout gen-premise"><strong>開場</strong>　${h(game.premise)}</p>` : ''}
        <dl class="char-fields"><dt>同行的人</dt><dd>${cast}</dd><dt>你扮演</dt><dd>${h(game.player?.name || '你')}</dd>
          <dt>行程</dt><dd>${game.clock ? h(clock(game.clock.start)) + ' 出發・' : ''}${h(hours)} 小時・${h(game.places)} 站</dd></dl>
        <p class="small muted">每一步選要去哪裡：選之前只看得到要花的時間，選了之後才看到每個人的反應${label ? `與「${h(label)}」的升降` : ''}。回到起點時，依每個人的數值走到不同的結局。</p>
      </section>${playView(game, exports)}`;
  }

  async function handleClick(target) {
    if (target.dataset.action !== 'game-retry') return false;
    if (waiting) waiting(); // 正在等自動重試：提早結束等待，馬上再試
    else if (stopped && stopped.id === target.dataset.id) advance(stopped.id, c.state.renderGeneration, stopped.build); // 已經停止：從這裡重新開始
    return true;
  }

  return {initialize, view, handleClick};
})();
