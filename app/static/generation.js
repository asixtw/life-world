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

  function panel(detail, waitSeconds) {
    const run = detail.run;
    const segments = detail.segments.map(seg => `<li class="gen-seg${seg.is_user ? ' gen-seg-me' : ''}"><strong>${h(seg.speaker_name)}</strong>
        ${seg.stage_direction ? `<span class="small muted">（${h(seg.stage_direction)}）</span>` : ''}${seg.action ? `<em>${h(seg.action)}</em>` : ''}${seg.line ? `<p>${h(seg.line)}</p>` : ''}</li>`).join('');
    const progress = `${run.completed_segments}/${run.total_segments ?? '?'} 段`;
    const notice = run.notice ? `<p class="callout">${h(run.notice.message)}</p>` : '';
    const waiting = waitSeconds ? `<p class="small muted">約 ${waitSeconds} 秒後自動繼續。</p>` : '';
    const error = run.error ? `<p class="callout gen-error" role="alert">${h(run.error.message)}</p>` : '';
    const resume = run.can_resume ? c.button('gen-resume', '恢復，從下一段繼續', 'primary', `data-id="${h(detail.id)}"`) : '';
    return `<p><strong>${h(STATUS[run.status] || run.status)}</strong> · ${progress} · ${h(detail.module)} · 呼叫 ${detail.usage.calls} 次</p>
      ${notice}${waiting}${error}<div class="button-row">${resume}</div>
      <ol class="gen-segments">${segments || '<li class="muted">正在規劃段落…</li>'}</ol>`;
  }

  async function run(id) {
    const ticket = c.state.renderGeneration;
    const [detail, status] = await Promise.all([c.api('/generation/runs/' + encodeURIComponent(id)), c.api('/generation/status')]);
    if (!fresh(ticket)) return '';
    if (['queued', 'running'].includes(detail.run.status)) setTimeout(() => advance(id, ticket, status.background), 50);
    const cast = detail.cast.map(member => h(member.name) + (member.is_user ? '（我）' : '')).join('、');
    return `${c.link('works', '← 作品', 'text-button')}
      ${c.heading(detail.title || '生成作品', `人物：${cast}`, c.link('work/' + encodeURIComponent(id), '版本與封存', 'secondary'))}
      <section class="card" id="gen-run-panel" aria-live="polite">${panel(detail)}</section>${settingsView(detail)}`;
  }

  /** 頁面開著時連續推進；換頁（renderGeneration 改變）就停止。 */
  async function advance(id, ticket, background = false) {
    // 背景排程（雲端）：生成由後端 Worker 推進，頁面只定期讀取進度；本機沒有排程時才由頁面逐段推進。
    while (fresh(ticket)) {
      let result;
      try {
        result = background ? {detail: await c.api(`/generation/runs/${encodeURIComponent(id)}`), wait_seconds: 3}
          : await c.api(`/generation/runs/${encodeURIComponent(id)}/step`, {method: 'POST'});
      } catch (error) {
        if (fresh(ticket) && document.getElementById('gen-run-panel')) document.getElementById('gen-run-panel').insertAdjacentHTML('afterbegin', `<p class="callout gen-error" role="alert">${h(error.message)}</p>`);
        return;
      }
      if (!fresh(ticket)) return;
      const target = document.getElementById('gen-run-panel');
      if (target) target.innerHTML = panel(result.detail, background ? null : result.wait_seconds);
      if (!['queued', 'running'].includes(result.detail.run.status)) return;
      await new Promise(resolve => setTimeout(resolve, result.wait_seconds ? result.wait_seconds * 1000 : 300));
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
