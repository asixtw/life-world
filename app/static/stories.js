// F04 故事開場（2026-11-10 自 8445 移植到 B 原生 UI）：選一張自己的角色卡，AI 產生故事開場（開場、目標、衝突與三個起始行動），確認後保存。
window.StoriesUI = (() => {
  let c;
  const INPUTS = [['genre', '故事類型', 40, false, '例如：奇幻冒險、懸疑、校園'], ['setting', '場景', 800, true, '故事發生的地點、時間與氣氛'],
    ['conflict', '當前衝突', 800, true, '眼前的麻煩或對立'], ['player_goal', '你的目標', 600, true, '你想在這個故事裡達成什麼'],
    ['constraints', '其他限制（選填）', 600, true, '不想出現的內容或特別要求']];
  let draft = null; // 最近一次 AI 產生的故事開場：{generation, output}
  let conflict = null; // 舊分頁保存被拒時的提示：{id, message}

  function initialize(context) { c = context; }
  const h = value => c.esc(value);
  const fresh = ticket => ticket === c.state.renderGeneration;

  function storyBody(content) {
    const choices = (content.choices || []).map(choice => `<li><strong>${h(choice.label)}</strong> <span class="tag">${h(choice.strategy)}</span><p>${h(choice.description)}</p></li>`).join('');
    return `<p class="story-opening">${h(content.opening)}</p>
      <dl class="char-fields"><dt>目標</dt><dd>${h(content.objective)}</dd><dt>衝突</dt><dd>${h(content.conflict)}</dd>
        <dt>角色</dt><dd>${h(content.source?.character_name || '')} · v${h(content.source?.character_version || '')}</dd>
        ${content.narrative_notes ? `<dt>敘事筆記</dt><dd>${h(content.narrative_notes)}</dd>` : ''}</dl>
      <h3 class="section-title space-top">三個起始行動</h3><ol class="story-choices">${choices}</ol>`;
  }

  const EDITABLE = [['title', '標題', 80, false], ['opening', '開場', 2000, true], ['objective', '目標', 400, true], ['conflict', '衝突', 600, true],
    ['narrative_notes', '敘事筆記', 600, true]];

  function editForm(work) { // 修改目前版本並另存新版本；角色卡來源與三個起始行動不變
    const content = work.version.content;
    const fields = EDITABLE.map(([key, label, max, multi]) => `<div class="field"><label for="story-edit-${key}">${label}</label>${multi
      ? `<textarea id="story-edit-${key}" name="${key}" maxlength="${max}" rows="${key === 'opening' ? 5 : 2}" ${key === 'narrative_notes' ? '' : 'required'}>${h(content[key] || '')}</textarea>`
      : `<input id="story-edit-${key}" name="${key}" maxlength="${max}" value="${h(content[key] || '')}" required>`}</div>`).join('');
    return `<details class="space-top" ${conflict && conflict.id === work.id ? 'open' : ''}><summary>修改並另存新版本</summary><form id="story-edit-form" class="stack space-top" data-work="${h(work.id)}" data-base="${work.current_version}" data-revision="${work.revision}">
      ${conflict && conflict.id === work.id ? `<p class="callout" role="alert">${h(conflict.message)} 你的修改仍留在下方表單，可以先複製。</p>${c.button('story-reload', '重新載入最新版本', 'secondary')}` : ''}${fields}
      <p class="small muted">角色卡來源與三個起始行動不變；舊版本保留，已開始的冒險仍引用原本的版本。</p>
      <button type="submit" class="secondary">保存新版本</button></form></details>`;
  }

  async function create() {
    const ticket = c.state.renderGeneration;
    const [cards, status] = await Promise.all([c.api('/characters'), c.api('/generation/status')]);
    if (!fresh(ticket)) return '';
    const options = cards.items.map(item => `<option value="${h(item.id)}" data-version="${item.current_version}">${h(item.title)}（v${item.current_version}）</option>`).join('');
    const fields = INPUTS.map(([key, label, max, multi, hint]) => `<div class="field"><label for="story-${key}">${h(label)}</label>${multi
      ? `<textarea id="story-${key}" name="${key}" maxlength="${max}" rows="2" placeholder="${h(hint)}" ${key === 'constraints' ? '' : 'required'}></textarea>`
      : `<input id="story-${key}" name="${key}" maxlength="${max}" placeholder="${h(hint)}" required>`}</div>`).join('');
    const result = draft ? `<section class="card stack space-top"><h2 class="section-title">${h(draft.output.title)}</h2>
        <p class="small muted">${h(draft.notice || '')}</p>${storyBody(draft.output)}
        <div class="button-row">${c.button('story-save', '保存故事開場', 'primary')}</div></section>` : '';
    return `${c.link('create', '← AI 生成', 'text-button')}
      ${c.heading('故事開場', '選一張你的角色卡，AI 會依設定寫出故事開場與三個不同的起始行動；保存前可以先看過。')}
      ${status.available ? '' : '<p class="callout">AI 生成尚未設定，暫時無法使用。</p>'}
      ${options ? `<form id="story-form" class="card stack"><div class="field"><label for="story-card">角色卡</label><select id="story-card" name="card">${options}</select></div>
        ${fields}<div class="button-row"><button type="submit" class="primary">產生故事開場</button></div></form>` : c.empty('還沒有角色卡；先到「角色」複製或產生一張。', c.link('characters', '前往角色卡', 'primary'))}
      ${result}`;
  }

  async function submit(form) {
    if (form.id === 'story-edit-form') {
      const base = Number(form.dataset.base);
      const version = await c.api(`/works/${encodeURIComponent(form.dataset.work)}/versions/${base}`); // 以開啟表單時的版本為基礎
      const data = new FormData(form);
      const content = {...version.content};
      EDITABLE.forEach(([key]) => { content[key] = String(data.get(key) || '').trim(); });
      const body = {expected_revision: Number(form.dataset.revision), base_version: base, content, generation_id: version.generation_id || null};
      let saved;
      try {
        saved = await c.api(`/stories/${encodeURIComponent(form.dataset.work)}/versions`, {method: 'POST', body: {...body, request_id: c.requestId('story-edit:' + form.dataset.work, body)}});
      } catch (error) {
        if (error.status !== 409) throw error;
        conflict = {id: form.dataset.work, message: error.message}; // 其他分頁已更新：不覆寫，保留表單內容並提示重新載入
        form.querySelector('.callout')?.remove();
        form.insertAdjacentHTML('afterbegin', `<p class="callout" role="alert">${h(error.message)} 你的修改仍留在下方表單，可以先複製。</p>${c.button('story-reload', '重新載入最新版本', 'secondary')}`);
        return true;
      }
      conflict = null;
      c.toast(`已保存 v${saved.current_version}。`);
      c.navigate('story/' + encodeURIComponent(form.dataset.work));
      return true;
    }
    if (form.id !== 'story-form') return false;
    const data = new FormData(form);
    const select = form.querySelector('#story-card');
    const input = {character_work_id: select.value, character_version: Number(select.selectedOptions[0].dataset.version)};
    INPUTS.forEach(([key]) => { input[key] = String(data.get(key) || '').trim(); });
    const body = {module: 'story_opening', input};
    draft = await c.api('/ai/generate', {method: 'POST', body: {...body, request_id: c.requestId('story-gen', body)}});
    c.toast('故事開場已產生，確認後可以保存。');
    await c.render();
    return true;
  }

  async function handleClick(target) {
    if (target.dataset.action === 'story-reload') { conflict = null; await c.render(); return true; } // 讀取最新版本重新修改
    if (target.dataset.action !== 'story-save' || !draft) return false;
    const body = {content: draft.output, generation_id: draft.generation.id};
    const work = await c.api('/stories', {method: 'POST', body: {...body, request_id: c.requestId('story-save:' + draft.generation.id, body)}});
    draft = null;
    c.toast(`已保存故事開場「${work.title}」。`);
    c.navigate('story/' + encodeURIComponent(work.id));
    return true;
  }

  async function detail(id, versionParam) {
    const ticket = c.state.renderGeneration;
    const work = await c.api('/works/' + encodeURIComponent(id));
    const requested = Number(versionParam) || work.current_version;
    const shown = requested === work.current_version ? work.version : await c.api(`/works/${encodeURIComponent(id)}/versions/${requested}`);
    if (!fresh(ticket)) return '';
    const versions = work.versions.map(v => `<li><a href="#story/${encodeURIComponent(work.id)}?v=${v.version_no}" ${v.version_no === shown.version_no ? 'aria-current="true" class="char-version-active"' : ''}>v${v.version_no}${v.version_no === work.current_version ? '（目前）' : ''}</a>
        <span class="small muted">${h(v.origin)} · ${h(c.time(v.created_at))}</span></li>`).join('');
    return `${c.link('works?kind=story_opening', '← 我的故事開場', 'text-button')}
      ${c.heading(shown.content.title, `故事開場 · 目前 v${work.current_version}${work.status === 'archived' ? ' · 已封存' : ''}`, `<div class="button-row">${c.link('create', '＋ 建立新作品', 'secondary')}${c.link('work/' + encodeURIComponent(work.id), '版本與封存', 'secondary')}</div>`)}
      <div class="char-layout"><article class="card">${storyBody(shown.content)}</article>
      <aside class="card"><h2 class="section-title">版本</h2><ol class="char-versions">${versions}</ol>${work.status === 'active' ? editForm(work) : ''}</aside></div>`;
  }

  return {initialize, create, submit, handleClick, detail, render: storyBody};
})();
