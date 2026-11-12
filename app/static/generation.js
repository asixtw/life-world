// AI 生成（2026-11-10 自 8445 移植到 B 原生 UI）：角色卡 AI 草稿、生成精靈（T1 單人物／T2 多人物）、逐段生成進度與恢復。
// 生成頁開著時自動一段一段推進（每段完成就保存）；離開頁面就暫停，回來會從下一段接續。
window.GenerationUI = (() => {
  let c;
  const STATUS = {queued: '排隊中', running: '生成中', completed: '已完成', failed: '已暫停／失敗'};
  const DRAFT_FIELDS = [['background', '背景', 1500], ['personality', '個性', 600], ['motivation', '動機', 600], ['stance', '立場', 600],
    ['voice', '語氣', 400], ['knowledge_boundary', '知識界線', 600], ['restrictions', '禁止事項或其他限制', 600]];
  let draft = null; // 最近一次 AI 草稿：{generation, output}

  function initialize(context) { c = context; }
  const h = value => c.esc(value);
  const fresh = ticket => ticket === c.state.renderGeneration;

  async function providerNote() {
    const status = await c.api('/generation/status');
    if (!status.available) return `<p class="callout">AI 生成尚未設定，暫時無法使用。</p>`;
    return `<p class="small muted">AI：${h(status.provider_kind === 'live' ? `${status.provider}（${status.model}）` : '測試用假回應')}；每日金額上限用完時會暫停，已保存的內容都保留。</p>`;
  }

  // ---- 角色卡 AI 草稿 ----
  async function draftView() {
    const ticket = c.state.renderGeneration;
    const note = await providerNote();
    if (!fresh(ticket)) return '';
    const fields = DRAFT_FIELDS.map(([key, label, max]) => `<div class="field"><label for="draft-${key}">${h(label)}（選填）</label><textarea id="draft-${key}" name="${key}" maxlength="${max}" rows="2"></textarea></div>`).join('');
    const result = draft ? `<section class="card stack space-top"><h2 class="section-title">AI 草稿：${h(draft.output.name)}</h2>
        <p class="small muted">${h(draft.notice || '')}</p>
        <dl class="char-fields">${Object.entries(draft.output).filter(([, v]) => typeof v === 'string' && v).map(([k, v]) => `<dt>${h(k)}</dt><dd>${h(v)}</dd>`).join('')}</dl>
        <div class="button-row">${c.button('gen-save-draft', '保存為我的角色卡', 'primary')}</div></section>` : '';
    return `${c.link('characters', '← 返回角色卡', 'text-button')}
      ${c.heading('AI 產生角色卡', '寫下名稱與幾個重點，AI 會產生一份角色卡草稿；保存前可以先看過。')}
      ${note}<form id="char-draft-form" class="card stack">
        <div class="field"><label for="draft-name">角色名稱（必填）</label><input id="draft-name" name="name" maxlength="60" required></div>
        <div class="field"><label for="draft-kind">類型</label><select id="draft-kind" name="kind"><option value="fictional">原創虛構角色</option><option value="role">職務角色</option></select></div>
        ${fields}<div class="button-row"><button type="submit" class="primary">產生草稿</button></div></form>${result}`;
  }

  async function submitDraft(form) {
    const data = new FormData(form);
    const input = {name: String(data.get('name') || '').trim(), kind: data.get('kind') || 'fictional'};
    DRAFT_FIELDS.forEach(([key]) => { const value = String(data.get(key) || '').trim(); if (value) input[key] = value; });
    const body = {module: 'character_card', input};
    draft = await c.api('/ai/generate', {method: 'POST', body: {...body, request_id: c.requestId('ai-draft', body)}});
    c.toast('草稿已產生，確認後可以保存。');
    await c.render();
  }

  async function saveDraft() {
    if (!draft) return;
    const body = {content: draft.output, generation_id: draft.generation.id};
    const work = await c.api('/characters', {method: 'POST', body: {...body, request_id: c.requestId('ai-draft-save:' + draft.generation.id, body)}});
    draft = null;
    c.toast(`已保存角色卡「${work.title}」。`);
    c.navigate('character/' + encodeURIComponent(work.id));
  }

  // ---- 生成精靈 ----
  async function wizard() {
    const ticket = c.state.renderGeneration;
    const [cards, catalog, persona, note] = await Promise.all([c.api('/characters'), c.api('/generation/catalog'), c.api('/self-persona'), providerNote()]);
    if (!fresh(ticket)) return '';
    const max = catalog.limits.max_participants;
    const cardOptions = cards.items.map(item => `<label class="check-line"><input type="checkbox" name="cards" value="${h(item.id)}" data-version="${item.current_version}"> ${h(item.title)} <span class="small muted">v${item.current_version}</span></label>`).join('');
    const meReady = persona.persona && persona.consent;
    const me = `<label class="check-line"><input type="checkbox" name="include_me" ${meReady ? 'checked' : 'disabled'}> 包含我（${persona.persona ? h(persona.persona.content.display_name) : '尚未建立人設'}）</label>
      ${meReady ? '' : `<p class="small muted">要讓 AI 扮演你，先在${c.link('persona', '我的人設')}建立人設並同意。</p>`}`;
    const presets = catalog.scene_presets.map(item => `<option value="${h(item.id)}">${h(item.title)}</option>`).join('');
    const styles = catalog.styles.map(item => `<label class="check-line"><input type="checkbox" name="styles" value="${h(item.id)}"> ${h(item.label)}</label>`).join('');
    const lengths = catalog.lengths.map((item, i) => `<label class="check-line"><input type="radio" name="length" value="${h(item.id)}" ${i === 0 ? 'checked' : ''}> ${h(item.label)}</label>`).join('');
    const forms = catalog.forms.map((item, i) => `<label class="check-line"><input type="radio" name="form" value="${h(item.id)}" ${i === 0 ? 'checked' : ''}> ${h(item.label)}</label>`).join('');
    return `${c.heading('AI 生成作品', `選 1 位人物是 T1，2～${max} 位是 T2；開始後在作品頁逐段生成，每段完成就保存。`, `<div class="button-row">${c.link('story-new', '故事開場', 'secondary')}${c.link('stage', '人物劇場', 'secondary')}${c.link('runs', '我的生成作品', 'secondary')}</div>`)}
      ${note}<form id="gen-wizard-form" class="card stack" data-presets='${h(JSON.stringify(catalog.scene_presets))}'>
        <div class="field"><label for="gen-title">作品標題（選填，空白時由 AI 命名）</label><input id="gen-title" name="title" maxlength="60"></div>
        <fieldset class="field"><legend>① 人物（最多 ${max} 位，含我）</legend><div class="gen-checks">${cardOptions || '<span class="muted">還沒有角色卡，先到「角色」複製一張。</span>'}</div>${me}</fieldset>
        <div class="field"><label for="gen-preset">② 範例場景（選填，會填入下方描述）</label><select id="gen-preset" name="preset"><option value="">不使用</option>${presets}</select></div>
        <div class="field"><label for="gen-scene">場景描述（必填）</label><textarea id="gen-scene" name="scene" maxlength="2000" rows="4" required></textarea></div>
        <fieldset class="field"><legend>③ 風格（可複選或不選）</legend><div class="gen-checks">${styles}</div></fieldset>
        <fieldset class="field"><legend>④ 長度</legend><div class="gen-checks">${lengths}</div></fieldset>
        <fieldset class="field"><legend>呈現形式</legend><div class="gen-checks">${forms}</div></fieldset>
        <div class="button-row"><button type="submit" class="primary">開始生成</button></div></form>`;
  }

  async function submitWizard(form) {
    const data = new FormData(form);
    const participants = [...form.querySelectorAll('input[name="cards"]:checked')].map(input => ({ref: {work_id: input.value, version_no: Number(input.dataset.version)}}));
    const setup = {participants, include_me: data.get('include_me') === 'on', title: String(data.get('title') || '').trim(),
      scene_context: {description: String(data.get('scene') || '').trim(), ...(data.get('preset') ? {preset_id: data.get('preset')} : {})},
      style_profile: {style_ids: data.getAll('styles')}, output: {type: 'text', text: {length: data.get('length') || 'short', form: data.get('form') || 'script'}}};
    const body = {setup};
    const work = await c.api('/generation/runs', {method: 'POST', body: {...body, request_id: c.requestId('gen-start', body)}});
    c.state.dirty = false;
    c.navigate('run/' + encodeURIComponent(work.id));
  }

  // ---- 生成作品列表與逐段生成 ----
  async function runs() {
    const ticket = c.state.renderGeneration;
    const result = await c.api('/generation/runs');
    if (!fresh(ticket)) return '';
    const items = result.items.map(item => `<a class="list-item works-item" href="#run/${encodeURIComponent(item.id)}"><span class="item-main"><strong>${h(item.title || '（未命名）')}</strong>
        <span class="small muted">${h(item.module)} · ${h(STATUS[item.run.status] || item.run.status)} · ${item.run.completed_segments}/${item.run.total_segments ?? '?'} 段</span></span></a>`).join('');
    return `${c.heading('我的生成作品', '包含 8445 時期建立的作品；未完成的作品打開後會從下一段繼續。', c.link('create', '＋ 新的生成', 'primary'))}
      ${items ? `<div class="stack">${items}</div>` : c.empty('還沒有生成作品。')}`;
  }

  const LENGTHS = {short: '短篇', medium: '中篇', long: '長篇'}, FORMS = {script: '劇本對白', narrative: '小說敘事'}, POSITIONS = {protagonist: '主角', opponent: '對手', advisor: '軍師', supporting: '配角'};

  function settingsView(detail) { // 作品設定（每個欄位只出現一次）與歷史版本
    const s = detail.setup || {};
    const scene = s.scene || {};
    const rows = [['人物', (detail.cast || []).map(m => h(m.name) + (m.is_user ? '（我）' : '') + (m.source === 'person' && m.version ? `（人物設定第 ${m.version} 版）` : '')
        + (m.position ? `・${POSITIONS[m.position] || m.position}` : '')).join('、')], // 人物來源：標出開始時鎖定的人物設定版本
      ['場景', h(scene.description || '')], ...(scene.start?.event ? [['起始事件', h(scene.start.event)]] : []), ...(scene.start?.goal ? [['主角目標', h(scene.start.goal)]] : []),
      ...((scene.conditions || []).length ? [['場景條件', scene.conditions.map(h).join('；')]] : []),
      ['風格', [...(s.styles || []).map(x => h(x.label)), h(s.style_notes || '')].filter(Boolean).join('、') || '不指定'],
      ['輸出', `文字・${LENGTHS[s.length] || h(s.length || '')}・${FORMS[s.form] || h(s.form || '')}`],
      ...((s.materials || []).length ? [['素材', s.materials.map(m => `${h(m.title)}（第 ${m.version_no} 版）`).join('、')]] : []),
      ...(s.direction ? [['演出要求', [s.direction.adherence === 'free' ? '自由詮釋' : '貼近人物設定', h(s.direction.notes || ''), s.direction.avoid ? '避免：' + h(s.direction.avoid) : ''].filter(Boolean).join('；')]] : [])];
    const history = (detail.history || []).slice().reverse().map(v => `<li><a href="#work/${encodeURIComponent(detail.id)}?v=${v.version_no}">v${v.version_no}</a>
        <span class="small muted">${h(STATUS[v.status] || v.status)}${v.resumed ? '・恢復' : ''} · ${h(c.time(v.created_at))}</span></li>`).join('');
    return `<details class="card space-top"><summary><strong>作品設定</strong></summary><dl class="char-fields">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl></details>
      <details class="card space-top"><summary><strong>歷史版本（${(detail.history || []).length}）</strong></summary><ol class="char-versions">${history}</ol></details>`;
  }

  function exportView(detail, exports) { // 作品完成後才能下載：伺服器把已保存的劇情組成一個可以離線打開的 HTML 檔（不呼叫 AI）
    // 兩顆按鈕是同一個動作：「下載 HTML」是整篇的閱讀版；「下載互動版」多帶 data-player="play"（選視角、限次偷看、線索、抉擇與結局）。
    // 互動版那一顆另外帶 data-interactive：下載之前先請伺服器準備這件作品的互動內容（見 handleClick）。
    // 2026-11-12：同一件作品可以看（閱讀版）也可以玩（互動版），所以區塊叫「看或玩」，各有「在這裡…」（不用下載，直接在這一頁打開）與「下載…」兩顆。
    // 「在這裡看」是新的一顆（gen-view-here）；原有三顆的動作與順序不變。玩的遊戲那一頁（GameUI）用同一套說法。
    if (detail.run.status !== 'completed' || !exports) return '';
    if (!exports.available) return '<section class="card space-top"><p class="small muted">這個環境還沒有開放下載作品。</p></section>';
    const last = exports.items[0];
    return `<section class="card space-top" id="gen-export"><h2>看或玩</h2>
      <p class="small muted">看：整篇從頭讀到尾的閱讀版。「在這裡看」不用下載，直接在這一頁打開；「下載 HTML」把這部作品存成一個 HTML 檔，下載後可以離線打開。檔案裡不含人物設定的欄位與我的設定；台詞與反應是 AI 依人物設定寫出來的，可能用到設定裡的說法，分享前可以先看過。</p>
      <p class="small muted">玩：互動版一次看一段：先選一個人的視角入局，他的真心話直接看得到，別人的只能偷看幾次；文字裡藏著線索，找齊了就能看穿對方的底牌。走到轉折要做一次抉擇，通往三個結局——真結局要先找到線索才能選，選錯可以回到轉折點重選。同樣可以離線打開。</p>
      <p class="small muted">「在這裡玩」不用下載，直接在這一頁打開互動版；「下載互動版」存成 HTML 檔。第一次會先準備互動內容（線索、抉擇與結局），需要多等一下。</p>
      <div class="button-row">${c.button('gen-export', '下載 HTML', 'primary', `data-id="${h(detail.id)}"`)}
        ${c.button('gen-export', '下載互動版', 'secondary', `data-id="${h(detail.id)}" data-player="play" data-interactive="1"`)}
        ${c.button('gen-view-here', '在這裡看', 'secondary', `data-id="${h(detail.id)}"`)}
        ${c.button('gen-play-here', '在這裡玩', 'secondary', `data-id="${h(detail.id)}" data-prepare="1"`)}</div>
      ${last ? `<p class="small muted">上次匯出：${h(c.time(last.created_at))}・${(last.size / 1024).toFixed(1)} KB</p>` : ''}
      <div id="gen-inline-player" class="inline-player" hidden></div></section>`;
  }

  function seriesView(detail) { // 多章節作品的入口：已完成的獨立作品可以開始續寫；已經屬於某一部的，指回作品總覽
    const series = detail.series;
    if (series) {
      const place = series.is_draft ? `這是《${h(series.title)}》的草稿。到作品總覽決定要不要採納成下一章。` : `這是《${h(series.title)}》的第 ${series.episode_no} 章。`;
      return `<section class="card space-top"><p>${place}</p><div class="button-row">${c.link('series/' + encodeURIComponent(series.id), '作品總覽', 'secondary')}</div></section>`;
    }
    if (detail.run.status !== 'completed') return '';
    return `<section class="card space-top"><h2>續寫下一章</h2>
      <p class="small muted">把這部作品當成第 1 章，接著寫下去。之後每一章都會延續前面已定稿的劇情。</p>
      <div class="button-row">${c.button('series-open', '續寫下一章', 'secondary', `data-id="${h(detail.id)}"`)}</div></section>`;
  }

  function download(url) { // 用暫時的連結觸發下載：回應是附件，頁面留在原地、不會跳轉
    const link = document.createElement('a');
    link.href = url;
    link.download = '';
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  // 作品頁的互動版：匯出之前先請伺服器準備互動內容——線索、關鍵抉擇與另外兩個結局、番外（「下載互動版」與「在這裡玩」共用）。
  // 那一步會呼叫模型，可能要等一陣子，也可能失敗（金額上限、模型暫時無法使用）。失敗不擋後面的匯出：回傳原因（成功是空字串），
  // 由呼叫的地方說明——那一份互動版沒有抉擇與線索（仍然有視角與限次偷看），之後再按一次會重新準備。
  async function prepareInteractive(target, id) {
    const label = target.textContent;
    let failed = '';
    target.textContent = '準備互動內容中…'; // 提示幾秒就消失，等待比它久：按鈕上也寫著正在做什麼
    c.toast('正在準備互動內容（線索、抉擇與結局）…');
    try {
      await c.api(`/works/${encodeURIComponent(id)}/interactive`, {method: 'POST', body: {request_id: c.requestId('gen-interactive:' + id + ':' + Date.now(), {})}});
    } catch (error) {
      failed = error.message || '互動內容暫時準備不了。';
      c.toast(`互動內容沒有準備好：${failed}`);
    } finally {
      target.textContent = label;
    }
    return failed;
  }

  // 在這裡玩：把某一次匯出的檔案放進這一頁的 iframe（#gen-inline-player，作品頁與互動遊戲頁都有）。
  // 網址是「站內直接看」的路由：和下載同一份檔案、只有本人讀得到，但不是附件。iframe 加上 sandbox、只允許執行程式（沒有 allow-same-origin）：
  // 裡面的頁面在獨立的來源裡執行，讀不到這個網站的登入狀態與儲存空間；那一條回應自己也帶著同樣的限制。
  // 「在新分頁開啟」是同一個網址：手機上畫面太小時、或瀏覽器不讓這一頁放 iframe 時還有路可走。
  // reading＝放進來的是閱讀版（「在這裡看」）：同一個區塊、同樣的沙箱，只有標示的文字不同（閱讀版沒有進度可言）。
  function showInline(id, item, reading = false) {
    const box = document.getElementById('gen-inline-player');
    if (!box) return;
    const src = `/api/works/${encodeURIComponent(id)}/exports/${Number(item.version_no)}/view`;
    const name = reading ? '在這裡看' : '在這裡玩';
    box.innerHTML = `<div class="inline-player-bar"><span class="small muted">${reading ? '在這裡看（閱讀版，和「下載 HTML」的內容相同）' : '在這裡玩（進度只留在這一次；關閉或重新整理就從頭開始）'}</span>
        <span class="button-row"><a class="text-button" href="${h(src)}" target="_blank" rel="noopener">在新分頁開啟</a>${c.button('gen-play-close', '關閉', 'secondary')}</span></div>
      <iframe class="inline-player-frame" sandbox="allow-scripts" src="${h(src)}" title="${name}"></iframe>`;
    box.hidden = false;
    if (box.scrollIntoView) box.scrollIntoView({block: 'start'});
    // 有些環境這一頁的安全設定（CSP 的 frame-src）不讓放 iframe：開了 Google 登入時，首頁只放行 Google 的登入框，同源的也會被擋，框裡一片空白。
    // 瀏覽器擋下來時會對頁面發出事件；收到是這一個網址被擋，就把框換成說明與「在新分頁開啟」（同一個網址；那一條回應自己帶著 sandbox，直接打開一樣安全）。
    stopInlineWatch();
    inlineWatch = event => {
      const directive = String(event.effectiveDirective || event.violatedDirective || '');
      if (!/^(frame-src|child-src|default-src)/.test(directive) || !String(event.blockedURI || '').endsWith(src)) return;
      box.innerHTML = `<p class="callout">這個環境的安全設定不允許在這一頁裡直接顯示。請改用新分頁打開，內容相同。</p>
        <div class="button-row"><a class="primary" href="${h(src)}" target="_blank" rel="noopener">在新分頁開啟</a>${c.button('gen-play-close', '關閉', 'secondary')}</div>`;
    };
    document.addEventListener('securitypolicyviolation', inlineWatch);
  }

  let inlineWatch = null; // 「在這裡玩」開著的時候，看瀏覽器有沒有擋下那個 iframe 的監聽函式

  function stopInlineWatch() { // 換一個作品來玩、或關閉時，把前一個監聽拿掉
    if (inlineWatch && document.removeEventListener) document.removeEventListener('securitypolicyviolation', inlineWatch);
    inlineWatch = null;
  }

  const KINDS = {setup: '起', rise: '承', turn: '轉', payoff: '合'}; // 規劃標出的起承轉合

  function panel(detail, waitSeconds) {
    const run = detail.run;
    const plan = detail.plan || {};
    // 人物多的時候要分得出個人、團體與關鍵情節（2026-11-12）：
    // 個人＝依陣容順序給色號（1～6 循環，樣式在 characters.css 的 .gen-c1～6）；團體＝規劃標出的陣營，顯示在名稱旁；
    // 關鍵情節＝每一幕開頭顯示幕名與起承轉合，轉折那一幕另有樣式。舊作品沒有這些資料，畫面和原本一樣。
    const colorOf = {}, sideOf = {}, beats = {};
    (detail.cast || []).forEach((member, index) => { colorOf[member.id] = index % 6 + 1; });
    (plan.sides || []).forEach(side => (side.members || []).forEach(id => { sideOf[id] = side.name; }));
    (plan.beats || []).forEach(beat => { if (beat.title) beats[beat.beat_no] = beat; }); // 只顯示幕名；goal 是給演出用的情況，會劇透
    let shown = null;
    const segments = detail.segments.map(seg => {
      const beat = seg.beat_no !== shown ? beats[seg.beat_no] : null;
      shown = seg.beat_no;
      const heading = beat ? `<li class="gen-beat${beat.kind === 'turn' ? ' gen-beat-turn' : ''}">${KINDS[beat.kind] ? `<span class="gen-kind">${KINDS[beat.kind]}</span>` : ''}${h(beat.title)}</li>` : '';
      const color = colorOf[seg.speaker_id] ? ` gen-c${colorOf[seg.speaker_id]}` : '';
      const side = sideOf[seg.speaker_id] ? ` <span class="gen-side">${h(sideOf[seg.speaker_id])}</span>` : '';
      const number = Number(seg.turn_no) ? ` value="${Number(seg.turn_no)}"` : ''; // 幕名佔了一列，段落照自己的段號編號
      return `${heading}<li class="gen-seg${seg.is_user ? ' gen-seg-me' : ''}${color}"${number}><strong>${h(seg.speaker_name)}</strong>${side}
        ${seg.stage_direction ? `<span class="small muted">（${h(seg.stage_direction)}）</span>` : ''}${seg.action ? `<em>${h(seg.action)}</em>` : ''}${seg.line ? `<p>${h(seg.line)}</p>` : ''}</li>`;
    }).join('');
    const progress = `${run.completed_segments}/${run.total_segments ?? '?'} 段`;
    const notice = run.notice ? `<p class="callout">${h(run.notice.message)}</p>` : '';
    const waiting = waitSeconds ? `<p class="small muted">約 ${waitSeconds} 秒後自動繼續。</p>` : '';
    const error = run.error ? `<p class="callout gen-error" role="alert">${h(run.error.message)}</p>` : '';
    const resume = run.can_resume ? c.button('gen-resume', '恢復，從下一段繼續', 'primary', `data-id="${h(detail.id)}"`) : '';
    // 開場白（破題）：規劃時寫的 premise。放在第一段之前，觀眾先知道這場戲的看點，再往下讀（2026-11-12）。規劃完成前或舊作品沒有就不顯示。
    const genre = plan.genre ? `<span class="gen-genre">${h(plan.genre)}</span>　` : '';
    const premise = plan.premise ? `<p class="callout gen-premise"><strong>開場</strong>　${genre}${h(plan.premise)}</p>` : '';
    // 故事沒有完全了結時，規劃會寫一句下集預告；全部生成完才顯示，放在最後一段之後
    const teaser = run.status === 'completed' && plan.teaser ? `<p class="callout gen-teaser"><strong>敬請期待下集</strong>　${h(plan.teaser)}</p>` : '';
    return `<p><strong>${h(STATUS[run.status] || run.status)}</strong> · ${progress} · ${h(detail.module)} · 呼叫 ${detail.usage.calls} 次</p>
      ${notice}${waiting}${error}<div class="button-row">${resume}</div>
      ${premise}<ol class="gen-segments">${segments || '<li class="muted">正在規劃段落…</li>'}</ol>${teaser}`;
  }

  async function run(id) {
    const ticket = c.state.renderGeneration;
    const [detail, status] = await Promise.all([c.api('/generation/runs/' + encodeURIComponent(id)), c.api('/generation/status')]);
    if (!fresh(ticket)) return '';
    // 已完成的作品：讀取匯出紀錄（讀不到時不擋住作品頁，只是不顯示下載區）
    const exports = detail.run.status === 'completed' ? await c.api('/works/' + encodeURIComponent(id) + '/exports').catch(() => null) : null;
    if (!fresh(ticket)) return '';
    if (['queued', 'running'].includes(detail.run.status)) setTimeout(() => advance(id, ticket, status.background), 50);
    const cast = detail.cast.map(member => h(member.name) + (member.is_user ? '（我）' : '')).join('、');
    return `${c.link('works', '← 作品', 'text-button')}
      ${c.heading(detail.title || '生成作品', `人物：${cast}`, c.link('work/' + encodeURIComponent(id), '版本與封存', 'secondary'))}
      <section class="card" id="gen-run-panel" aria-live="polite">${panel(detail)}</section>${exportView(detail, exports)}${seriesView(detail)}${settingsView(detail)}`;
  }

  /** 頁面開著時連續推進；換頁（renderGeneration 改變）就停止。 */
  const pause = ms => (c.sleep ? c.sleep(ms) : new Promise(resolve => setTimeout(resolve, ms))); // 測試可以換成不真的等待

  async function advance(id, ticket, background = false) {
    // 背景排程（雲端）：生成由後端 Worker 推進，頁面只定期讀取進度；本機沒有排程時才由頁面逐段推進。
    let misses = 0; // 連續讀不到進度的次數
    while (fresh(ticket)) {
      let result;
      try {
        result = background ? {detail: await c.api(`/generation/runs/${encodeURIComponent(id)}`), wait_seconds: 3}
          : await c.api(`/generation/runs/${encodeURIComponent(id)}/step`, {method: 'POST'});
        misses = 0;
      } catch (error) {
        if (!fresh(ticket)) return;
        const target = document.getElementById('gen-run-panel');
        if (background) {
          // 背景生成在後端繼續進行，這裡只是讀進度：一次讀不到（連線中斷、伺服器暫時沒有回應）不代表生成停了。
          // 2026-11-12 實測：讀不到一次就停止更新，畫面一直停在 5/8 段，後端其實已經生成完。所以說明之後稍後再讀，間隔逐次拉長。
          misses += 1;
          if (target) target.insertAdjacentHTML('afterbegin', '<p class="callout" role="status">暫時讀不到進度，稍後自動重試；生成仍在後端進行，已完成的段落都已保存。</p>');
          await pause(Math.min(3000 * misses, 30000));
          continue;
        }
        if (target) target.insertAdjacentHTML('afterbegin', `<p class="callout gen-error" role="alert">${h(error.message)}</p>`);
        return; // 由頁面逐段推進時不自動重送，避免重複送出
      }
      if (!fresh(ticket)) return;
      const target = document.getElementById('gen-run-panel');
      if (target) target.innerHTML = panel(result.detail, background ? null : result.wait_seconds);
      if (!['queued', 'running'].includes(result.detail.run.status)) {
        if (result.detail.run.status === 'completed') await c.render(); // 剛完成：重畫整頁，下載區才會出現
        return;
      }
      await pause(result.wait_seconds ? result.wait_seconds * 1000 : 300);
    }
  }

  async function submit(form) {
    if (form.id === 'char-draft-form') { await submitDraft(form); return true; }
    if (form.id === 'gen-wizard-form') { await submitWizard(form); return true; }
    return false;
  }

  async function handleClick(target) {
    const action = target.dataset.action;
    if (action === 'gen-save-draft') { await saveDraft(); return true; }
    if (action === 'gen-export') { // 先請伺服器匯出（內容沒有變就沿用上一次），再下載那一次匯出的檔案
      const id = target.dataset.id;
      // 「下載互動版」走同一個流程，多帶 player: 'play'（按鈕上的 data-player）。閱讀版的請求和原本一樣、不帶這個欄位：
      // 伺服器不接受它不認得的欄位，這樣前後端新舊版本交錯時，原本的下載也不會壞。兩種的提交代碼分開。
      const play = target.dataset.player === 'play';
      // 作品頁的互動版（按鈕帶 data-interactive）：匯出之前先請伺服器準備互動內容（見 prepareInteractive）。準備失敗不擋下載：說明原因，照樣匯出。
      // 多章節作品總覽與互動遊戲頁的按鈕沒有這個標記：不另外準備（整部下載用各章已經有的互動內容；互動遊戲的內容在建立時就生成好了）。
      const failed = play && target.dataset.interactive ? await prepareInteractive(target, id) : '';
      const body = {request_id: c.requestId('gen-export:' + id + (play ? ':play:' : ':') + Date.now(), {}), format: 'html'};
      if (play) body.player = 'play';
      const result = await c.api(`/works/${encodeURIComponent(id)}/exports`, {method: 'POST', body});
      download(result.export.download_path);
      if (failed) c.toast(`互動內容沒有準備好：${failed} 這次的互動版沒有抉擇與線索，稍後可以再下載一次。`); // 原因和結果寫在同一則，不會被後一則蓋掉
      else c.toast(`已開始下載${target.dataset.name || (play ? '互動版' : ' HTML')}。`); // 互動遊戲頁的按鈕帶著自己的名稱（data-name）
      await c.render();
      return true;
    }
    if (action === 'gen-play-here') { // 在這裡玩：和下載同一個匯出流程（內容沒有變就沿用上一次），但不下載，放進這一頁的 iframe
      const id = target.dataset.id;
      // 作品頁的那一顆帶 data-prepare：和「下載互動版」一樣先準備互動內容。互動遊戲頁的不帶。兩者都匯出互動的那一種播放器。
      const failed = target.dataset.prepare ? await prepareInteractive(target, id) : '';
      const result = await c.api(`/works/${encodeURIComponent(id)}/exports`, {method: 'POST',
        body: {request_id: c.requestId('gen-export:' + id + ':play:' + Date.now(), {}), format: 'html', player: 'play'}});
      showInline(id, result.export); // 不重畫整頁：重畫會把剛放進去的 iframe 清掉
      if (failed) c.toast(`互動內容沒有準備好：${failed} 這次的互動版沒有抉擇與線索，稍後可以再試一次。`);
      return true;
    }
    if (action === 'gen-view-here') { // 在這裡看：閱讀版。和「下載 HTML」送同一種匯出請求（不帶 player；內容沒有變就沿用上一次），但不下載，放進這一頁的 iframe
      const id = target.dataset.id;
      // 閱讀版不需要互動內容：不呼叫準備的端點，也就不會多花一次模型呼叫
      const result = await c.api(`/works/${encodeURIComponent(id)}/exports`, {method: 'POST',
        body: {request_id: c.requestId('gen-export:' + id + ':' + Date.now(), {}), format: 'html'}});
      showInline(id, result.export, true); // 和「在這裡玩」同一個區塊；不重畫整頁（重畫會把剛放進去的 iframe 清掉）
      return true;
    }
    if (action === 'gen-play-close') { // 關閉：把 iframe 拿掉（裡面的頁面與聲音跟著停）
      const box = document.getElementById('gen-inline-player');
      if (box) { box.innerHTML = ''; box.hidden = true; }
      stopInlineWatch();
      return true;
    }
    if (action === 'gen-resume') {
      await c.api(`/generation/runs/${encodeURIComponent(target.dataset.id)}/resume`, {method: 'POST', body: {request_id: c.requestId('gen-resume:' + target.dataset.id + ':' + Date.now(), {})}});
      c.toast('已恢復，從下一段繼續。');
      await c.render();
      return true;
    }
    return false;
  }

  function change(event) {
    if (event.target.id !== 'gen-preset' || !event.target.value) return;
    const presets = JSON.parse(event.target.form.dataset.presets || '[]');
    const preset = presets.find(item => item.id === event.target.value);
    const scene = document.getElementById('gen-scene');
    if (preset && scene && !scene.value.trim()) scene.value = preset.description;
  }

  return {initialize, draftView, wizard, runs, run, submit, handleClick, change};
})();
document.addEventListener('change', event => { if (window.GenerationUI) GenerationUI.change(event); });
