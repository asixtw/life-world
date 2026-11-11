// F06A 人物演繹（2026-11-10 自 8445 移植到 B 原生 UI）：從人物頁選取自己記錄的資料 → AI 推演人物詮釋 → 保存與修改 → 互動試演（最多 6 個來回）。
// AI 推演不是本人的發言或想法；不寫回人物、人物資訊或筆記。
window.PortrayalUI = (() => {
  let c;
  const MAX_TURNS = 6;
  const DIMENSIONS = {interests: '興趣', food: '飲食', skills: '專長', habits: '互動習慣'};
  const FIELDS = {roles: '角色', tags: '標籤', category: '分類', common_context: '共同場合', notes: '人物備註'};
  const SCENARIOS = {advice: '請教問題', conflict: '意見衝突', business: '商業合作', daily: '日常聊天', memory: '共同回憶', custom: '自訂情境'};
  const SECTIONS = [['traits', '性格特徵'], ['motivations', '核心動機'], ['values', '價值觀'], ['behaviors', '行為傾向'], ['emotional_reactions', '可能的情緒反應']];
  const CARD_SECTIONS = [['summary', '摘要 → 一句話介紹'], ['traits', '性格特徵 → 個性'], ['motivations', '核心動機 → 動機'], ['values', '價值觀'],
    ['speaking_style', '說話風格 → 語氣'], ['behaviors', '行為傾向 → 行為'], ['emotional_reactions', '情緒反應 → 行為'], ['knowledge_boundary', '知識界線'], ['sample_dialogues', '示範對話 → 代表台詞']];
  let draft = null; // 尚未保存的人物詮釋：{person_id, generation, output, notice}
  let candidate = null; // 尚未保存的試演回應：{session_id, base_version, generation, output, message, notice}

  function initialize(context) { c = context; }
  const h = value => c.esc(value);
  const fresh = ticket => ticket === c.state.renderGeneration;
  const fieldText = (person, key) => key === 'roles' || key === 'tags' ? (person[key] || []).join('、') : key === 'category' ? ({business: '商務', life: '生活', learning: '學習'}[person.category] || '') : String(person[key] || '');

  function basis(refs, labels) {
    if (!refs || !refs.length) return '<span class="tag">推測</span>';
    return refs.map(ref => `<span class="tag" title="${h(labels[ref] || ref)}">依據 ${h(ref)}</span>`).join(' ');
  }

  function profileView(content, labels) {
    const p = content.profile;
    const items = (list) => list.map(item => `<li>${h(item.text)} ${basis(item.basis, labels)}</li>`).join('');
    const sections = SECTIONS.filter(([key]) => p[key].length).map(([key, title]) => `<h3 class="section-title space-top">${title}</h3><ul>${items(p[key])}</ul>`).join('');
    return `<p class="callout">AI 推演：依你選取的資料推測，不是本人的真實發言、想法或心理判定。</p>
      <p class="story-opening">${h(p.summary)}</p>${sections}
      <h3 class="section-title space-top">說話風格</h3><p>${h(p.speaking_style.text)} ${basis(p.speaking_style.basis, labels)}</p>
      <dl class="char-fields"><dt>知識界線</dt><dd>${h(p.knowledge_boundary)}</dd>${p.uncertainties.length ? `<dt>資料不足</dt><dd>${p.uncertainties.map(h).join('；')}</dd>` : ''}</dl>
      <h3 class="section-title space-top">示範對話（推演，不是本人說過的話）</h3><ul>${p.sample_dialogues.map(d => `<li><span class="small muted">${h(d.situation)}</span><br>「${h(d.line)}」</li>`).join('')}</ul>`;
  }

  const labelsFrom = items => Object.fromEntries((items || []).map(item => [item.ref, `${item.label}：${item.text}`]));
  const legend = items => items && items.length ? `<details class="space-top"><summary>這份推演使用的資料（${items.length} 項）</summary><ul>${items.map(item => `<li><strong>${h(item.ref)}</strong> ${h(item.label)}：${h(item.text)}</li>`).join('')}</ul></details>` : '';

  async function pick() { // 從真人資料建立角色卡：先選一位自己記錄的人物
    const ticket = c.state.renderGeneration;
    const people = await c.api('/people?limit=100');
    if (!fresh(ticket)) return '';
    const items = people.items.map(p => `<a class="list-item works-item" href="#portrayal-new/${encodeURIComponent(p.id)}"><span class="item-main"><strong>${h(p.name)}</strong></span></a>`).join('');
    return `${c.link('characters', '← 角色', 'text-button')}
      ${c.heading('從真人資料建立角色卡', '選一位你在「關係」記錄的人物；AI 只依你勾選的資料推演，確認後可以建立成自己的角色卡，再用在新作品裡。')}
      ${items ? `<div class="stack">${items}</div>` : c.empty('還沒有人物；先到「關係」記錄。', c.link('people', '前往關係', 'primary'))}`;
  }

  async function create(personId) {
    const ticket = c.state.renderGeneration;
    const [profile, status] = await Promise.all([c.api(`/people/${encodeURIComponent(personId)}/overview`), c.api('/generation/status')]);
    if (!fresh(ticket)) return '';
    const person = profile.person;
    const facts = Object.entries(profile.facts).flatMap(([dimension, rows]) => rows.filter(row => row.status === 'confirmed').map(row => ({...row, dimension})));
    const notes = (profile.notes || []).filter(note => note.kind === 'preparation');
    const fields = Object.keys(FIELDS).filter(key => fieldText(person, key).trim());
    const check = (group, id, label, text) => `<label class="play-choice"><input type="checkbox" name="${group}" value="${h(id)}" checked><span><strong>${h(label)}</strong><br><span class="small muted">${h(text)}</span></span></label>`;
    const choices = [...facts.map(f => check('fact', f.id, DIMENSIONS[f.dimension], f.value + (f.description ? '：' + f.description : ''))),
      ...notes.map(n => check('note', n.id, n.title, n.content)), ...fields.map(key => check('field', key, FIELDS[key], fieldText(person, key)))].join('');
    const result = draft && draft.person_id === person.id ? `<section class="card stack space-top"><h2 class="section-title">${h(person.name)} 的人物演繹（尚未保存）</h2>
        <p class="small muted">${h(draft.notice || '')}</p>${profileView(draft.output, {})}
        <div class="button-row">${c.button('portrayal-save', '保存人物演繹', 'primary')}</div></section>` : '';
    return `${c.link('portrayal-new', '← 選擇人物', 'text-button')}
      ${c.heading(`${person.name}｜AI 人物演繹`, '勾選要讓 AI 參考的資料；AI 只會看到你勾選的內容，結果是推演，不是本人。')}
      ${status.available ? '' : '<p class="callout">AI 生成尚未設定，暫時無法使用。</p>'}
      ${choices ? `<form id="portrayal-form" class="card stack" data-person="${h(person.id)}"><h2 class="section-title">選取資料</h2>${choices}
        <label class="play-choice"><input type="checkbox" name="consent" value="yes" required><span>我了解勾選的人物資料會送往 AI 服務（${h(status.provider || 'AI')}）產生推演，請勿包含身分證號、帳號密碼或卡號。</span></label>
        <div class="button-row"><button type="submit" class="primary">產生人物演繹</button></div></form>`
        : c.empty('這位人物還沒有可用的資料；先記錄已確認資訊、人物觀察筆記或主檔欄位。', c.link('person/' + encodeURIComponent(person.id), '返回人物頁', 'primary'))}
      ${result}`;
  }

  async function detail(id, versionParam) {
    const ticket = c.state.renderGeneration;
    const work = await c.api('/works/' + encodeURIComponent(id));
    const requested = Number(versionParam) || work.current_version;
    const shown = requested === work.current_version ? work.version : await c.api(`/works/${encodeURIComponent(id)}/versions/${requested}`);
    const snapshot = (await c.api(`/portrayals/${encodeURIComponent(id)}/versions/${shown.version_no}/snapshot`)).items;
    if (!fresh(ticket)) return '';
    const versions = work.versions.map(v => `<li><a href="#portrayal/${encodeURIComponent(work.id)}?v=${v.version_no}" ${v.version_no === shown.version_no ? 'aria-current="true" class="char-version-active"' : ''}>v${v.version_no}${v.version_no === work.current_version ? '（目前）' : ''}</a>
        <span class="small muted">${h(v.origin)} · ${h(c.time(v.created_at))}</span></li>`).join('');
    const scenarios = Object.entries(SCENARIOS).map(([key, label]) => `<option value="${key}">${h(label)}</option>`).join('');
    // 互動試演已停止新建（D-42）：既有的試演仍可閱讀與依原契約繼續；人物演繹結果可以建立為角色卡。
    const toCard = `<form id="portrayal-card-form" class="card stack space-top" data-work="${h(work.id)}" data-version="${shown.version_no}">
        <h2 class="section-title">把 v${shown.version_no} 轉為角色卡</h2><p class="small muted">只轉入勾選的段落；不會複製人物資訊或筆記原文，也不會改動人物資料。轉入後可以在角色卡頁繼續修改。</p>
        ${CARD_SECTIONS.map(([key, label]) => `<label class="play-choice"><input type="checkbox" name="section" value="${key}" checked><span>${h(label)}</span></label>`).join('')}
        <label class="play-choice"><input type="checkbox" name="acknowledged" value="yes" required><span>我了解轉入的是 AI 依所選資料推論的演出設定，不是真人事實，也不代表本人同意。</span></label>
        <div class="button-row"><button type="submit" class="secondary">轉為角色卡</button></div></form>`;
    return `${c.link('characters', '← 角色', 'text-button')}
      ${c.heading(work.title, `人物演繹 · 目前 v${work.current_version}${work.status === 'archived' ? ' · 已封存' : ''}`, `<div class="button-row">${c.link('person/' + encodeURIComponent(shown.content.source.person_id), '人物頁', 'secondary')}${c.link('work/' + encodeURIComponent(work.id), '版本與封存', 'secondary')}</div>`)}
      <div class="char-layout"><article class="card">${profileView(shown.content, labelsFrom(snapshot))}${legend(snapshot)}</article>
      <aside class="card"><h2 class="section-title">版本</h2><ol class="char-versions">${versions}</ol>
        ${work.status === 'active' ? `<form id="portrayal-edit-form" class="stack space-top" data-work="${h(work.id)}" data-base="${work.current_version}" data-revision="${work.revision}"><label for="portrayal-summary">修改摘要（另存新版本）</label>
          <textarea id="portrayal-summary" name="summary" rows="3" maxlength="120">${h(work.version.content.profile.summary)}</textarea><button type="submit" class="secondary">保存新版本</button></form>` : ''}</aside></div>
      ${toCard}`;
  }

  async function session(id) {
    const ticket = c.state.renderGeneration;
    const [work, status] = await Promise.all([c.api('/works/' + encodeURIComponent(id)), c.api('/generation/status')]);
    if (!fresh(ticket)) return '';
    const content = work.version.content;
    const name = content.portrayal.person_name;
    const active = content.status === 'active' && work.status === 'active';
    const turnView = turn => `<li class="card play-turn"><p class="small muted">第 ${turn.turn_no} 個來回 ${turn.provider_kind === 'fake' ? '<span class="tag">測試用假回應</span>' : ''}</p>
        <p><strong>你：</strong>${h(turn.message)}</p><p class="play-line"><strong>${h(name)}（AI 模擬）：</strong>「${h(turn.reply.line)}」 <span class="small muted">${h(turn.reply.tone)}</span></p>
        ${turn.reply.notes ? `<p class="small muted">${h(turn.reply.notes)}</p>` : ''}</li>`;
    const pending = candidate && candidate.session_id === work.id && candidate.base_version === work.current_version ? candidate : null;
    let next;
    if (!active) next = `<p class="callout">${work.status === 'archived' ? '這段試演已封存。' : content.ending === 'turn_limit' ? `已完成 ${MAX_TURNS} 個來回，試演結束。` : '你已結束這段試演。'}對話紀錄已保存。</p>`;
    else if (pending) next = `<section class="stack"><h2 class="section-title">AI 回應候選（尚未保存）</h2><p class="small muted">${h(pending.notice || '')}</p>
        <ol class="play-turns">${turnView({turn_no: content.turns.length + 1, message: pending.message, reply: pending.output, provider_kind: pending.generation.provider_kind})}</ol>
        <div class="button-row">${c.button('ps-save', '確認這個來回', 'primary')}${c.button('ps-regenerate', '重新生成', 'secondary')}${c.button('ps-discard', '改寫我的話', 'text-button')}</div></section>`;
    else next = status.available ? `<form id="ps-say-form" class="card stack"><label for="ps-message">第 ${content.turns.length + 1} 句：你想說什麼？</label>
        <textarea id="ps-message" name="message" maxlength="300" rows="2" required></textarea><div class="button-row"><button type="submit" class="primary">送出</button></div></form>`
      : '<p class="callout">AI 生成尚未設定，暫時無法對話；已保存的紀錄仍可閱讀。</p>';
    return `${c.link('portrayal/' + encodeURIComponent(content.portrayal.work_id) + '?v=' + content.portrayal.version_no, '← 人物演繹', 'text-button')}
      ${c.heading(content.title, `互動試演 · ${SCENARIOS[content.scenario.kind]}${content.scenario.detail ? '（' + content.scenario.detail + '）' : ''} · 已保存 ${content.turns.length}／${MAX_TURNS} 個來回`, `<div class="button-row">${active ? c.button('ps-end', '結束試演', 'secondary') : ''}${c.link('work/' + encodeURIComponent(work.id), '版本與封存', 'secondary')}</div>`)}
      <p class="small muted">AI 模擬，不是本人的真實回應。</p>
      ${content.turns.length ? `<ol class="play-turns">${content.turns.map(turnView).join('')}</ol>` : ''}<div class="space-top">${next}</div>`;
  }

  const routeId = () => decodeURIComponent((location.hash.split('/')[1] || '').split('?')[0]);

  async function say(work, message, again = false) {
    const input = {session_work_id: work.id, session_version: work.current_version, turn_no: work.version.content.turns.length + 1, message};
    const body = {module: 'portrayal_reply', input};
    const result = await c.api('/ai/generate', {method: 'POST', body: {...body, request_id: c.requestId('ps-say', again ? {...body, again: Date.now()} : body)}});
    candidate = {session_id: work.id, base_version: work.current_version, generation: result.generation, output: result.output, message, notice: result.notice};
    await c.render();
  }

  async function submit(form) {
    if (form.id === 'portrayal-form') {
      const data = new FormData(form);
      const selection = {fact_ids: data.getAll('fact'), note_ids: data.getAll('note'), fields: data.getAll('field')};
      if (!selection.fact_ids.length && !selection.note_ids.length && !selection.fields.length) { c.toast('請至少勾選一項資料。'); return true; }
      const body = {module: 'person_portrayal', input: {person_id: form.dataset.person, selection, dataset: 'custom', consent: true}};
      const result = await c.api('/ai/generate', {method: 'POST', body: {...body, request_id: c.requestId('portrayal-gen', body)}});
      draft = {person_id: form.dataset.person, generation: result.generation, output: result.output, notice: result.notice};
      c.toast('人物演繹已產生，確認後可以保存。');
      await c.render();
      return true;
    }
    if (form.id === 'portrayal-edit-form') {
      const base = Number(form.dataset.base);
      const version = await c.api(`/works/${encodeURIComponent(form.dataset.work)}/versions/${base}`); // 以開啟表單時的版本為基礎，不在送出當下改用最新版
      const summary = String(new FormData(form).get('summary') || '').trim();
      const content = {...version.content, profile: {...version.content.profile, summary}};
      const body = {expected_revision: Number(form.dataset.revision), base_version: base, content};
      const saved = await c.api(`/portrayals/${encodeURIComponent(form.dataset.work)}/versions`, {method: 'POST', body: {...body, request_id: c.requestId('portrayal-edit:' + form.dataset.work, body)}});
      c.toast(`已保存 v${saved.current_version}。`);
      c.navigate('portrayal/' + encodeURIComponent(form.dataset.work));
      return true;
    }
    if (form.id === 'portrayal-card-form') { // 人物演繹結果建立為角色卡
      const sections = new FormData(form).getAll('section');
      if (!sections.length) { c.toast('請至少勾選一個段落。'); return true; }
      const body = {portrayal_work_id: form.dataset.work, version_no: Number(form.dataset.version), sections, acknowledged: true};
      const card = await c.api('/characters/from-portrayal', {method: 'POST', body: {...body, request_id: c.requestId('portrayal-card', body)}});
      c.toast(`已建立角色卡「${card.title}」。`);
      c.navigate('character/' + encodeURIComponent(card.id));
      return true;
    }
    if (form.id === 'ps-say-form') {
      const message = String(new FormData(form).get('message') || '').trim();
      if (!message) return true;
      await say(await c.api('/works/' + encodeURIComponent(routeId())), message);
      return true;
    }
    return false;
  }

  async function handleClick(target) {
    const action = target.dataset.action;
    if (action === 'portrayal-save' && draft) {
      const body = {generation_id: draft.generation.id};
      const work = await c.api('/portrayals', {method: 'POST', body: {...body, request_id: 'portrayal-save-' + draft.generation.id}});
      draft = null;
      c.toast(`已保存「${work.title}」。`);
      c.navigate('portrayal/' + encodeURIComponent(work.id));
      return true;
    }
    if (!['ps-save', 'ps-regenerate', 'ps-discard', 'ps-end'].includes(action)) return false;
    const work = await c.api('/works/' + encodeURIComponent(routeId()));
    if (action === 'ps-discard') { candidate = null; await c.render(); return true; }
    if (action === 'ps-regenerate' && candidate) { await say(work, candidate.message, true); return true; }
    if (action === 'ps-save' && candidate) {
      const saved = await c.api(`/portrayal-sessions/${encodeURIComponent(work.id)}/turns`, {method: 'POST',
        body: {expected_revision: work.revision, generation_id: candidate.generation.id, request_id: 'ps-turn-' + candidate.generation.id}});
      candidate = null;
      const content = saved.version.content;
      c.toast(content.status === 'ended' ? `已完成 ${MAX_TURNS} 個來回，試演結束。` : `第 ${content.turns.length} 個來回已保存。`);
      await c.render();
      return true;
    }
    if (action === 'ps-end') {
      if (!confirm('結束後不能再對話；已保存的來回都會保留。確定結束？')) return true;
      await c.api(`/portrayal-sessions/${encodeURIComponent(work.id)}/end`, {method: 'POST', body: {expected_revision: work.revision, request_id: `ps-end-${work.id}-v${work.current_version}`}});
      candidate = null;
      c.toast('試演已結束。');
      await c.render();
      return true;
    }
    return false;
  }

  return {initialize, pick, create, detail, session, submit, handleClick, render: content => profileView(content, {})};
})();
