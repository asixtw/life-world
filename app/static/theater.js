// 人物劇場多角色演出（2026-11-10 自 8445 移植到 B 原生 UI）：選 2～4 位角色與情境 → 保存演出設定 → AI 寫一段多角色對話 → 原樣保存。
// 與人物頁的「小劇場」（私人練習筆記）不同；這裡是虛構角色的演出作品。
window.TheaterUI = (() => {
  let c;
  const POSITIONS = {protagonist: '主角', opponent: '對手', advisor: '軍師', supporting: '配角'};
  const MODES = {faithful: '貼近我的設定', free: '自由改編'};
  let candidate = null; // 尚未保存的演出：{cast_id, cast_version, generation, output, notice}

  function initialize(context) { c = context; }
  const h = value => c.esc(value);
  const fresh = ticket => ticket === c.state.renderGeneration;

  function script(content) {
    const lines = content.lines.map(line => `<li class="${line.cast_index === null ? 'stage-narrator' : ''}"><strong>${h(line.speaker)}</strong>：${h(line.text)}</li>`).join('');
    return `<ol class="stage-lines">${lines}</ol>${content.notes ? `<p class="small muted">${h(content.notes)}</p>` : ''}
      <p class="small muted">虛構演出：台詞不是真人、歷史或原著的已知事實。</p>`;
  }

  const castLine = cast => cast.map(m => `${h(m.name)}（${POSITIONS[m.position]}${m.source === 'system' ? '・系統角色' : ` v${h(m.version)}`}）`).join('、');

  async function builder(editId) {
    const ticket = c.state.renderGeneration;
    const [system, mine, catalog, work] = await Promise.all([c.api('/characters/system'), c.api('/characters?status=active'), c.api('/generation/catalog'),
      editId ? c.api('/works/' + encodeURIComponent(editId)) : null]);
    if (!fresh(ticket)) return '';
    const current = work ? work.version.content : null;
    const chosen = Object.fromEntries((current?.cast || []).map(m => [m.source + '|' + m.id, m.position]));
    const option = (source, id, version, name, label) => `<div class="stage-pick"><label class="play-choice"><input type="checkbox" name="member" value="${h(source + '|' + id + '|' + version)}" data-name="${h(name)}" ${chosen[source + '|' + id] ? 'checked' : ''}>
        <span><strong>${h(name)}</strong> <span class="small muted">${h(label)}</span></span></label>
        <select name="position-${h(source + '|' + id)}" aria-label="${h(name)}的演出位置">${Object.entries(POSITIONS).map(([key, text]) => `<option value="${key}" ${chosen[source + '|' + id] === key ? 'selected' : ''}>${text}</option>`).join('')}</select></div>`;
    const cards = mine.items.map(item => option('card', item.id, String(item.current_version), item.title, `我的角色卡 v${item.current_version}`)).join('');
    const systems = system.items.map(item => option('system', item.id, item.version, item.name, `系統角色${item.pack_label ? '・' + item.pack_label : ''}`)).join('');
    const presets = (catalog.scene_presets || []).map(item => `<option value="${h(item.id)}" data-text="${h(item.description)}" ${current?.scenario.preset_id === item.id ? 'selected' : ''}>${h(item.title)}</option>`).join('');
    const heading = work ? c.heading(`修改「${current.title}」`, `目前 v${work.current_version}；保存後成為 v${work.current_version + 1}，已保存的演出仍保留原本的設定版本。`)
      : c.heading('人物劇場', '選 2～4 位角色和一個情境，AI 會寫一段多角色對話演出；先保存演出設定，之後可以重演或修改。', c.link('works?kind=theater_performance', '我的演出', 'secondary'));
    const missing = (current?.cast || []).filter(m => m.source === 'card' && !mine.items.some(item => item.id === m.id));
    return `${work ? c.link('stage/' + encodeURIComponent(work.id), '← 回到演出設定', 'text-button') : c.link('create', '← AI 生成', 'text-button')}
      ${heading}
      ${missing.length ? `<p class="callout">${missing.map(m => h(m.name)).join('、')} 的角色卡已封存或刪除，不能再加入；請改選其他角色。</p>` : ''}
      <form id="stage-form" class="card stack" ${work ? `data-work="${h(work.id)}" data-base="${work.current_version}" data-revision="${work.revision}"` : ''}>
        <div class="field"><label for="stage-title">演出名稱</label><input id="stage-title" name="title" maxlength="60" required placeholder="例如：霧港夜談" value="${h(current?.title || '')}"></div>
        <div class="field"><label for="stage-preset">範例場景（選填）</label><select id="stage-preset" name="preset"><option value="">自己寫情境</option>${presets}</select></div>
        <div class="field"><label for="stage-scenario">情境</label><textarea id="stage-scenario" name="scenario" maxlength="800" rows="3" required>${h(current?.scenario.text || '')}</textarea></div>
        <div class="field"><label>演出方式</label>${Object.entries(MODES).map(([key, label], i) => `<label class="play-choice"><input type="radio" name="mode" value="${key}" ${(current ? current.mode === key : i === 0) ? 'checked' : ''}><span>${label}</span></label>`).join('')}</div>
        <div class="field"><label for="stage-direction">演出要求（選填）</label><input id="stage-direction" name="direction" maxlength="600" placeholder="例如：節奏緊湊，最後留下懸念" value="${h(current?.direction || '')}"></div>
        <h2 class="section-title">選角（2～4 位，名稱不能重複）</h2>
        ${cards ? `<h3 class="small muted">我的角色卡</h3>${cards}` : ''}<h3 class="small muted">系統角色</h3>${systems}
        <div class="button-row"><button type="submit" class="primary">${work ? '另存為新版本' : '保存演出設定'}</button></div></form>`;
  }

  async function cast(id) {
    const ticket = c.state.renderGeneration;
    const [work, status, made] = await Promise.all([c.api('/works/' + encodeURIComponent(id)), c.api('/generation/status'),
      c.api(`/theater/casts/${encodeURIComponent(id)}/performances`).catch(() => ({items: []}))]);
    if (!fresh(ticket)) return '';
    if (work.kind !== 'theater_cast') { c.navigate('work/' + encodeURIComponent(id)); return ''; }
    const content = work.version.content;
    const pending = candidate && candidate.cast_id === work.id && candidate.cast_version === work.current_version ? candidate : null;
    const action = `<p class="callout">這是舊版「人物劇場」的演出設定，保留供閱讀。新的多人作品請到「作品」→「＋ 建立新作品」，在 ① 人物選 2 位以上。</p>`;
    return `${c.link('works', '← 作品', 'text-button')}
      ${c.heading(content.title, `演出設定 · 目前 v${work.current_version}${work.status === 'archived' ? ' · 已封存' : ''}`, `<div class="button-row">${c.link('create', '＋ 建立新作品', 'secondary')}${c.link('work/' + encodeURIComponent(work.id), '版本與封存', 'secondary')}</div>`)}
      <section class="card stack"><p><strong>陣容：</strong>${castLine(content.cast)}</p><p><strong>情境：</strong>${h(content.scenario.text)}</p>
        <p><strong>演出方式：</strong>${MODES[content.mode]}${content.direction ? `；${h(content.direction)}` : ''}</p></section>
      <div class="space-top">${action}</div>
      <section class="card space-top"><h2 class="section-title">這個設定的演出（${made.items.length}）</h2>
        ${made.items.length ? `<ul class="char-versions" id="stage-performances">${made.items.map(item => `<li><a href="#performance/${encodeURIComponent(item.id)}">${h(item.title)}</a>
          <span class="small muted">設定 v${item.cast_version} · ${item.lines} 句 · ${h(c.time(item.created_at))}${item.status === 'archived' ? ' · 已封存' : ''}</span></li>`).join('')}</ul>`
          : '<p class="small muted">還沒有保存的演出。</p>'}
        <p class="small muted">修改設定只會新增版本；已保存的演出保留當時的設定與台詞，不會被覆蓋。</p></section>`;
  }

  async function performance(id) {
    const ticket = c.state.renderGeneration;
    const work = await c.api('/works/' + encodeURIComponent(id));
    if (!fresh(ticket)) return '';
    const content = work.version.content;
    return `${c.link('works?kind=theater_performance', '← 我的演出', 'text-button')}
      ${c.heading(content.title, `多角色演出 · 使用設定 v${content.cast_ref.version_no} · ${c.time(work.created_at)}`, `<div class="button-row">${c.link('stage/' + encodeURIComponent(content.cast_ref.work_id), '回到演出設定', 'secondary')}${c.link('work/' + encodeURIComponent(work.id), '版本與封存', 'secondary')}</div>`)}
      <section class="card stack"><p><strong>陣容：</strong>${castLine(content.cast)}</p><p><strong>情境：</strong>${h(content.scenario.text)}</p></section>
      <article class="card space-top">${script(content)}</article>`;
  }

  async function perform(again) {
    const id = decodeURIComponent((location.hash.split('/')[1] || '').split('?')[0]);
    const work = await c.api('/works/' + encodeURIComponent(id));
    const body = {module: 'theater_performance', input: {cast_work_id: work.id, cast_version: work.current_version}};
    const result = await c.api('/ai/generate', {method: 'POST', body: {...body, request_id: c.requestId('stage-perform', again ? {...body, again: Date.now()} : body)}});
    candidate = {cast_id: work.id, cast_version: work.current_version, generation: result.generation, output: result.output, notice: result.notice};
    await c.render();
  }

  async function submit(form) {
    if (form.id !== 'stage-form') return false;
    const data = new FormData(form);
    const picked = [...form.querySelectorAll('input[name="member"]:checked')];
    if (picked.length < 2 || picked.length > 4) { c.toast('請選 2～4 位角色。'); return true; }
    const members = picked.map(input => {
      const [source, id, version] = input.value.split('|');
      return {source, id, version, name: input.dataset.name, position: String(data.get(`position-${source}|${id}`) || 'supporting')};
    });
    const preset = String(data.get('preset') || '');
    const content = {title: String(data.get('title') || '').trim(), scenario: {text: String(data.get('scenario') || '').trim(), preset_id: preset || null},
      mode: String(data.get('mode') || 'faithful'), direction: String(data.get('direction') || '').trim(), cast: members};
    let work;
    if (form.dataset.work) {
      const body = {expected_revision: Number(form.dataset.revision), base_version: Number(form.dataset.base), content};
      try {
        work = await c.api(`/theater/casts/${encodeURIComponent(form.dataset.work)}/versions`, {method: 'POST', body: {...body, request_id: c.requestId('stage-cast-edit:' + form.dataset.work, body)}});
      } catch (error) {
        if (error.status !== 409) throw error;
        form.querySelector('.callout')?.remove();
        form.insertAdjacentHTML('afterbegin', `<p class="callout" role="alert">${h(error.message)} 你的修改仍留在表單中。</p>${c.link('stage/' + encodeURIComponent(form.dataset.work) + '?edit=1&reload=' + Date.now(), '重新載入最新版本', 'secondary')}`);
        return true;
      }
    } else {
      work = await c.api('/theater/casts', {method: 'POST', body: {content, request_id: c.requestId('stage-cast', content)}});
    }
    candidate = null;
    c.toast(form.dataset.work ? `已保存 v${work.current_version}。` : '演出設定已保存。');
    c.navigate('stage/' + encodeURIComponent(work.id));
    return true;
  }

  async function handleClick(target) {
    const action = target.dataset.action;
    if (action === 'stage-perform' || action === 'stage-perform-again') { await perform(action === 'stage-perform-again'); return true; }
    if (action === 'stage-save' && candidate) {
      const work = await c.api('/theater/performances', {method: 'POST', body: {generation_id: candidate.generation.id, request_id: 'stage-save-' + candidate.generation.id}});
      candidate = null;
      c.toast(`已保存演出「${work.title}」。`);
      c.navigate('performance/' + encodeURIComponent(work.id));
      return true;
    }
    return false;
  }

  function change(event) { // 選範例場景時帶入描述，之後可以自由修改
    const select = event.target;
    if (select.id !== 'stage-preset' || !select.value) return;
    const area = document.getElementById('stage-scenario');
    if (area) area.value = select.selectedOptions[0].dataset.text || '';
  }

  return {initialize, builder, cast, performance, submit, handleClick, change, render: script};
})();
document.addEventListener('change', event => { if (window.TheaterUI) TheaterUI.change(event); });
