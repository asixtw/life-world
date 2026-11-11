// 角色卡（2026-11-10 自 8445 角色管理中心移植到 B 原生 UI）：我的角色卡、系統角色、複製、改版、新舊版本、封存與恢復。
// 所有資料都經同源 /api/characters/*（Cookie＋CSRF），寫入以 request_id 防重送、expected_revision 防過期覆蓋。
window.CharactersUI = (() => {
  let c; // 主程式注入的共用工具與狀態
  const TEXT_FIELDS = [ // [欄位, 標籤, 上限, 多行]
    ['name', '名稱', 60, false], ['tagline', '一句話設定', 400, true], ['background', '背景', 3000, true],
    ['personality', '性格', 2000, true], ['motivation', '動機', 1500, true], ['stance', '立場', 1500, true],
    ['values', '價值觀', 1500, true], ['voice', '說話方式', 600, true], ['behavior', '行為與情緒反應', 2000, true],
    ['appearance', '外觀', 1000, true], ['knowledge_boundary', '知識界線', 1000, true]];
  const LIST_FIELDS = [['restrictions', '限制或禁止事項（一行一項，最多 8 項）', 8, 120], ['sample_lines', '範例台詞（一行一句，最多 3 句）', 3, 400]];
  const INSPIRATIONS = {original: '原創', anime: '動漫', wuxia: '武俠', history: '歷史', real_person: '真人', role: '角色', mixed: '混合'};
  const PROVENANCE = {copy_system: '複製系統角色', copy_card: '複製角色卡', portrayal: '人物演繹轉入', ai: 'AI 生成', manual: '人工建立'};
  const ORIGIN = {human: '人工', ai: 'AI 原稿', ai_edited: 'AI 修改稿'};
  let editing = null; // 目前編輯中的角色卡：{id, revision, version, content}

  function initialize(context) { c = context; }
  const h = value => c.esc(value);
  const fresh = ticket => ticket === c.state.renderGeneration; // 拒絕較舊的非同步回應覆蓋新畫面

  function summary(content) {
    return content.tagline || content.personality || content.background || '尚未填寫設定。';
  }

  function labels(content) {
    const tags = [...(content.tags || []), ...(content.inspirations || []).map(key => INSPIRATIONS[key] || key)];
    return tags.length ? `<p class="char-tags">${tags.map(tag => `<span class="tag">${h(tag)}</span>`).join('')}</p>` : '';
  }

  /** 角色卡列表：我的角色卡（可切換封存）與系統角色。 */
  async function list(status = 'active') {
    const ticket = c.state.renderGeneration;
    const [mine, system] = await Promise.all([c.api('/characters?status=' + encodeURIComponent(status)), c.api('/characters/system')]);
    if (!fresh(ticket)) return '';
    const cards = mine.items.map(item => `<a class="card char-card" href="#character/${encodeURIComponent(item.id)}">
        <strong>${h(item.title)}</strong><span class="small muted">v${item.current_version} · ${h(PROVENANCE[item.provenance] || '')}${item.used_by ? ` · ${item.used_by} 個作品使用` : ''}${item.status === 'archived' ? ' · 已封存' : ''}</span>
        <span class="char-summary">${h(summary(item.content))}</span>${labels(item.content)}</a>`).join('');
    const catalog = system.items.map(item => `<a class="card char-card" href="#character-system/${encodeURIComponent(item.id)}">
        <strong>${h(item.name)}</strong><span class="small muted">系統角色 · ${h(item.pack_label || '')} · ${h(item.version)}</span>
        <span class="char-summary">${h(summary(item.content))}</span></a>`).join('');
    const toggle = status === 'archived' ? c.link('characters', '查看使用中的角色卡') : c.link('characters?status=archived', '查看已封存');
    return `${c.heading('角色卡', '角色卡是你私人世界中的演員設定。從系統角色複製一張，就能自由修改；每次儲存都會保留舊版本。', `<div class="button-row">${c.link('character-ai', 'AI 產生角色卡', 'primary')}${c.link('portrayal-new', '從真人資料建立', 'secondary')}${c.link('persona', '我的人設', 'secondary')}</div>`)}
      <section class="space-bottom"><div class="inline-heading"><h2 class="section-title">${status === 'archived' ? '已封存的角色卡' : '我的角色卡'}</h2>${toggle}</div>
      ${cards ? `<div class="char-grid">${cards}</div>` : c.empty(status === 'archived' ? '沒有已封存的角色卡。' : '還沒有角色卡。從下方的系統角色複製一張開始。')}</section>
      <section><h2 class="section-title">系統角色</h2><p class="small muted">系統角色唯讀、所有人共用；複製後成為你自己的角色卡。</p>
      <div class="char-grid">${catalog}</div></section>`;
  }

  function readOnly(content) {
    const rows = TEXT_FIELDS.filter(([key]) => key !== 'name' && content[key]).map(([key, label]) => `<dt>${h(label)}</dt><dd>${h(content[key])}</dd>`);
    LIST_FIELDS.forEach(([key, label]) => { if ((content[key] || []).length) rows.push(`<dt>${h(label.split('（')[0])}</dt><dd>${content[key].map(h).join('<br>')}</dd>`); });
    const sources = (content.source_references || []).map(ref => `${ref.kind === 'system_character' ? '系統角色' : ref.kind === 'character_card' ? '角色卡' : '人物演繹'}「${h(ref.name)}」${h(ref.version)}${ref.ai_inferred ? '（AI 推論的演出設定，不是真人事實）' : ''}`);
    if (sources.length) rows.push(`<dt>來源</dt><dd>${sources.join(' → ')}</dd>`);
    return `${labels(content)}<dl class="char-fields">${rows.join('') || '<dd class="muted">尚未填寫設定。</dd>'}</dl>`;
  }

  /** 系統角色詳情：唯讀，可複製成自己的角色卡。 */
  async function system(id) {
    const ticket = c.state.renderGeneration;
    const item = await c.api('/characters/system/' + encodeURIComponent(id));
    if (!fresh(ticket)) return '';
    return `${c.link('characters', '← 返回角色卡', 'text-button')}
      ${c.heading(item.name, `系統角色 · ${item.pack_label || ''} · 版本 ${item.version}`, c.button('char-copy-system', '複製成我的角色卡', 'primary', `data-id="${h(item.id)}" data-version="${h(item.version)}"`))}
      <article class="card">${readOnly(item.content)}</article>`;
  }

  function editForm(work) {
    const content = work.version.content;
    const text = TEXT_FIELDS.map(([key, label, max, multi]) => `<div class="field"><label for="char-${key}">${h(label)}</label>${multi
      ? `<textarea id="char-${key}" name="${key}" maxlength="${max}" rows="${key === 'tagline' ? 2 : 3}">${h(content[key] || '')}</textarea>`
      : `<input id="char-${key}" name="${key}" maxlength="${max}" value="${h(content[key] || '')}" required>`}</div>`).join('');
    const lists = LIST_FIELDS.map(([key, label]) => `<div class="field"><label for="char-${key}">${h(label)}</label><textarea id="char-${key}" name="${key}" rows="3">${h((content[key] || []).join('\n'))}</textarea></div>`).join('');
    const inspirations = Object.entries(INSPIRATIONS).map(([key, label]) => `<label class="check-line"><input type="checkbox" name="inspirations" value="${key}" ${(content.inspirations || []).includes(key) ? 'checked' : ''}> ${h(label)}</label>`).join('');
    return `<form id="character-edit-form" class="card stack" data-id="${h(work.id)}">
      <h2 class="section-title">編輯並儲存為新版本</h2><p class="small muted">儲存後成為 v${work.current_version + 1}，v${work.current_version} 與更早的版本都會保留。</p>
      ${text}${lists}
      <div class="field"><label for="char-tags">標籤（以逗號分隔，最多 12 個）</label><input id="char-tags" name="tags" value="${h((content.tags || []).join('，'))}"></div>
      <fieldset class="field"><legend>靈感來源</legend><div class="char-checks">${inspirations}</div></fieldset>
      <div class="button-row"><button type="submit" class="primary">儲存新版本</button></div></form>`;
  }

  /** 我的角色卡詳情：版本清單、所選版本內容、目前版本的編輯表單、封存／恢復與複製此版本。 */
  async function detail(id, versionParam) {
    const ticket = c.state.renderGeneration;
    const [work, references] = await Promise.all([c.api('/characters/' + encodeURIComponent(id)), c.api(`/characters/${encodeURIComponent(id)}/references`)]);
    const requested = Number(versionParam) || work.current_version;
    const shown = requested === work.current_version ? work.version : await c.api(`/characters/${encodeURIComponent(id)}/versions/${requested}`);
    if (!fresh(ticket)) return '';
    editing = {id: work.id, revision: work.revision, version: work.current_version, content: work.version.content};
    const versions = work.versions.map(v => `<li><a href="#character/${encodeURIComponent(work.id)}?v=${v.version_no}" ${v.version_no === shown.version_no ? 'aria-current="true" class="char-version-active"' : ''}>v${v.version_no}${v.version_no === work.current_version ? '（目前）' : ''}</a>
        <span class="small muted">${h(ORIGIN[v.origin] || v.origin)} · ${h(c.time(v.created_at))}</span></li>`).join('');
    const archived = work.status === 'archived';
    const actions = [archived ? c.button('char-status', '恢復角色卡', 'secondary', `data-id="${h(work.id)}" data-status="active" data-revision="${work.revision}"`)
      : c.button('char-status', '封存', 'secondary', `data-id="${h(work.id)}" data-status="archived" data-revision="${work.revision}"`)];
    if (!archived) actions.push(c.button('char-copy-card', `複製 v${shown.version_no} 成新角色卡`, 'secondary', `data-id="${h(work.id)}" data-version="${shown.version_no}"`));
    // 角色卡只能封存與恢復，不提供永久刪除（2026-11-10 定案）。
    const isCurrent = shown.version_no === work.current_version;
    return `${c.link('characters', '← 返回角色卡', 'text-button')}
      ${c.heading(shown.content.name, `我的角色卡 · 目前 v${work.current_version}${archived ? ' · 已封存' : ''}`, `<div class="button-row">${actions.join('')}</div>`)}
      <div class="char-layout"><article class="card"><h2 class="section-title">v${shown.version_no}${isCurrent ? '（目前版本）' : '（舊版本，唯讀）'}</h2>
        <p class="small muted">${h(shown.content_schema)} · ${h(ORIGIN[shown.origin] || shown.origin)} · ${h(c.time(shown.created_at))}</p>${readOnly(shown.content)}</article>
      <aside class="card"><h2 class="section-title">版本</h2><ol class="char-versions">${versions}</ol>${usedBy(references.items)}</aside></div>
      ${isCurrent && !archived ? editForm(work) : archived ? c.empty('已封存的角色卡不能修改；恢復後即可編輯。') : `<p class="callout">這是舊版本。${c.link(`character/${encodeURIComponent(work.id)}`, '回到目前版本編輯')}</p>`}`;
  }

  function contentFrom(form) {
    const data = new FormData(form);
    const content = {...editing.content}; // 保留 kind、來源參照與肖像（伺服器管理欄位）
    TEXT_FIELDS.forEach(([key]) => { content[key] = String(data.get(key) || '').trim(); });
    LIST_FIELDS.forEach(([key, , max, length]) => { content[key] = String(data.get(key) || '').split('\n').map(line => line.trim().slice(0, length)).filter(Boolean).slice(0, max); });
    content.tags = [...new Set(String(data.get('tags') || '').split(/[,，]/).map(tag => tag.trim().slice(0, 20)).filter(Boolean))].slice(0, 12);
    content.inspirations = data.getAll('inspirations');
    return content;
  }

  async function submit(form) {
    if (form.id !== 'character-edit-form') return false;
    const content = contentFrom(form);
    const body = {expected_revision: editing.revision, base_version: editing.version, content};
    const work = await c.api(`/characters/${encodeURIComponent(editing.id)}/versions`, {method: 'POST', body: {...body, request_id: c.requestId('char-version:' + editing.id, body)}});
    c.state.dirty = false;
    c.toast(`已儲存 v${work.current_version}；舊版本仍可讀取。`);
    c.navigate('character/' + encodeURIComponent(work.id));
    return true;
  }

  const KIND_PAGES = {story_opening: ['故事開場', 'story'], story_session: ['互動冒險', 'play'], theater_cast: ['演出設定', 'stage'],
    theater_performance: ['劇場演出', 'performance'], roleplay_session: ['自動演出', 'run'], generated_work: ['生成作品', 'run']};

  function usedBy(items) { // 列出引用這張卡的作品（任何版本、含已封存作品）；角色卡一律只能封存
    if (!items.length) return '<p class="small muted space-top">目前沒有作品使用這張角色卡。</p>';
    return `<h2 class="section-title space-top">使用這張角色卡的作品（${items.length}）</h2><ul class="char-versions">${items.map(item => {
      const [label, page] = KIND_PAGES[item.kind] || [item.kind, 'work'];
      return `<li><a href="#${page}/${encodeURIComponent(item.work_id)}">${h(item.title)}</a> <span class="small muted">${h(label)} · 用到 v${item.card_versions.join('、v')}${item.status === 'archived' ? ' · 已封存' : ''}</span></li>`;
    }).join('')}</ul><p class="small muted">角色卡只能封存；封存後，已完成的作品仍保留使用的版本。</p>`;
  }

  async function handleClick(target) {
    const action = target.dataset.action;
    if (action === 'char-copy-system' || action === 'char-copy-card') {
      const body = {source_kind: action === 'char-copy-system' ? 'system' : 'card', source_id: target.dataset.id, source_version: String(target.dataset.version)};
      const work = await c.api('/characters/copy', {method: 'POST', body: {...body, request_id: c.requestId('char-copy:' + body.source_id + ':' + body.source_version, body)}});
      c.toast(`已建立角色卡「${work.title}」。`);
      c.navigate('character/' + encodeURIComponent(work.id));
      return true;
    }
    if (action === 'char-status') {
      const body = {expected_revision: Number(target.dataset.revision), status: target.dataset.status};
      await c.api(`/characters/${encodeURIComponent(target.dataset.id)}/status`, {method: 'POST', body: {...body, request_id: c.requestId('char-status:' + target.dataset.id, body)}});
      c.toast(body.status === 'archived' ? '角色卡已封存。' : '角色卡已恢復。');
      await c.render();
      return true;
    }
    return false;
  }

  return {initialize, list, system, detail, submit, handleClick};
})();
