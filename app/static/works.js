// 我的人設、同意管理與作品管理（2026-11-10 自 8445 移植到 B 原生 UI）。
// 人設改版以 expected_revision 防過期覆蓋；同意可授予與撤回；作品列表支援種類、狀態與分頁，詳情可讀所有版本。
window.WorksUI = (() => {
  let c;
  const PAGE = 20;
  const KINDS = {character_card: '角色卡', self_persona: '我的人設', generated_work: '生成作品', roleplay_session: '自動演出',
    story_opening: '故事開場', story_session: '互動冒險', person_portrayal: '人物演繹', portrayal_session: '人物互動試演',
    theater_cast: '演出設定', theater_performance: '劇場演出'};
  const PERSONA_FIELDS = [ // [欄位, 標籤, 上限, 必填, 多行]
    ['display_name', '顯示名稱', 60, true, false], ['public_profile', '公開簡介（其他角色看得到）', 400, true, true],
    ['personality', '性格', 2000, true, true], ['speaking_style', '說話方式', 600, true, true], ['motivation', '動機', 1500, false, true],
    ['values', '價值觀', 1500, false, true], ['behavior', '行為模式', 2000, false, true], ['knowledge', '知識與專長', 2000, false, true],
    ['relationships', '人際關係', 2000, false, true], ['boundaries', '界線（不希望 AI 演出的內容）', 1000, false, true], ['appearance', '外觀', 1000, false, true]];
  const TRUTH = {real: '真實的我', mixed: '部分真實', ideal: '理想中的我'};
  const PERSONA_BLOCKS = [['A', '基本資料', ['display_name', 'public_profile', 'appearance']], ['B', '人格特質', ['personality', 'motivation', 'values']], // 與人物設定相同的分區方式
    ['C', '能力與知識', ['knowledge']], ['D', '行為與表達', ['behavior', 'speaking_style', 'sample_lines']], ['E', '關係與界線', ['relationships', 'boundaries']]];
  let persona = null; // 目前人設（保存時帶 revision）

  function initialize(context) { c = context; }
  const h = value => c.esc(value);
  const fresh = ticket => ticket === c.state.renderGeneration;

  // ---- 我的人設與同意 ----
  async function personaView() {
    const ticket = c.state.renderGeneration;
    const data = await c.api('/self-persona');
    if (!fresh(ticket)) return '';
    persona = data.persona;
    const content = persona?.content || {};
    const inputs = Object.fromEntries(PERSONA_FIELDS.map(([key, label, max, required, multi]) => [key, `<div class="field"><label for="persona-${key}">${h(label)}${required ? '（必填）' : ''}</label>${multi
      ? `<textarea id="persona-${key}" name="${key}" maxlength="${max}" rows="3" ${required ? 'required' : ''}>${h(content[key] || '')}</textarea>`
      : `<input id="persona-${key}" name="${key}" maxlength="${max}" value="${h(content[key] || '')}" ${required ? 'required' : ''}>`}</div>`]));
    inputs.sample_lines = `<div class="field"><label for="persona-sample_lines">範例台詞（一行一句，最多 3 句）</label><textarea id="persona-sample_lines" name="sample_lines" rows="3">${h((content.sample_lines || []).join(String.fromCharCode(10)))}</textarea></div>`;
    const fields = PERSONA_BLOCKS.map(([letter, title, keys]) => `<div class="stack" data-persona-block="${letter}"><h3 class="section-title">${letter}｜${h(title)}</h3>${keys.map(key => inputs[key]).join('')}</div>`).join('');
    // 我的設定歸在「人物」底下；從作品進來的才回作品。人物系統不可用時維持原本的返回位置。
    const back = query().get('from') !== 'works' && c.state.capabilities?.unified_people ? c.link('persons', '← 人物', 'text-button') : c.link('works', '← 我的作品', 'text-button');
    const truth = Object.entries(TRUTH).map(([key, label]) => `<option value="${key}" ${(content.truth_level || 'mixed') === key ? 'selected' : ''}>${h(label)}</option>`).join('');
    const consent = data.consent
      ? `<p class="callout">已同意（${h(c.time(data.consent.granted_at))}）。${c.button('persona-consent', '撤回同意', 'secondary', 'data-granted="false"')}</p>`
      : `<p class="callout">尚未同意。${persona ? c.button('persona-consent', '我同意', 'primary', 'data-granted="true"') : '請先保存我的設定再同意。'}</p>`;
    return `${back}
      ${c.heading('我的設定', persona ? `目前第 ${persona.version_no} 版；每次保存都會保留舊版本。AI 扮演你時會依照這份設定。` : '填寫你自己的設定，讓 AI 知道怎麼扮演你。一個帳號只有一份使用中的設定。')}
      <p class="small muted">「我的設定」就是作品裡 AI 扮演你時使用的「我的人設」。你實際做過的事記在${c.link('history', '紀錄 → 我的經歷', 'text-button')}。</p>
      <form id="persona-form" class="card stack">${fields}
        <div class="field"><label for="persona-truth">這份設定是</label><select id="persona-truth" name="truth_level">${truth}</select></div>
        <div class="button-row"><button type="submit" class="primary">${persona ? '保存新版本' : '建立我的設定'}</button>${persona ? c.link('work/' + encodeURIComponent(persona.work_id), '查看所有版本') : ''}</div></form>
      <section class="card stack space-top"><h2 class="section-title">同意使用</h2><p>${h(data.consent_text)}</p>${consent}</section>`;
  }

  async function savePersona(form) {
    const data = new FormData(form);
    const content = {};
    PERSONA_FIELDS.forEach(([key]) => { content[key] = String(data.get(key) || '').trim(); });
    content.sample_lines = String(data.get('sample_lines') || '').split('\n').map(line => line.trim().slice(0, 200)).filter(Boolean).slice(0, 3);
    content.truth_level = data.get('truth_level') || 'mixed';
    const body = {content, ...(persona ? {expected_revision: persona.revision} : {})};
    const result = await c.api('/self-persona', {method: 'PUT', body: {...body, request_id: c.requestId('persona-save', body)}});
    c.state.dirty = false;
    c.toast(`我的設定已保存為第 ${result.persona.version_no} 版。`);
    await c.render();
  }

  // ---- 作品管理 ----
  function query() { return new URLSearchParams(location.hash.slice(1).split('?')[1] || ''); }

  const TABS = [['active', '進行中'], ['completed', '已完成'], ['failed', '失敗／待恢復'], ['all', '全部作品'], ['versions', '版本歷史']];
  const PHASE_LABEL = {active: '進行中', completed: '已完成', failed: '失敗／待恢復'};
  const PAGES = {generated_work: 'run', roleplay_session: 'run', story_opening: 'story', story_session: 'play', person_portrayal: 'portrayal',
    portrayal_session: 'portrayal-play', theater_cast: 'stage', theater_performance: 'performance'};
  const VERSIONED = ['story_opening', 'person_portrayal']; // 這兩種作品頁可以直接讀指定版本；其他作品的指定版本在作品詳情（版本與封存）讀
  const open = (kind, id, version) => version
    ? `#${VERSIONED.includes(kind) ? PAGES[kind] : 'work'}/${encodeURIComponent(id)}?v=${version}`
    : `#${PAGES[kind] || 'work'}/${encodeURIComponent(id)}`;

  /** 作品中心：生成是建立作品的過程，作品是生成後的成果，兩者在同一個列表。角色卡與我的人設在「角色」。 */
  async function list() {
    const ticket = c.state.renderGeneration;
    const q = query(), tab = TABS.some(([id]) => id === q.get('tab')) ? q.get('tab') : 'all', kind = q.get('kind') || '';
    const status = q.get('status') === 'archived' ? 'archived' : 'active', offset = Math.max(0, Number(q.get('offset')) || 0);
    const [result, history] = await Promise.all([
      c.api('/works/center?' + new URLSearchParams({tab: tab === 'versions' ? 'all' : tab, status, kind, limit: String(PAGE), offset: String(offset)})),
      tab === 'versions' ? c.api('/works/center/versions?limit=100') : null]);
    if (!fresh(ticket)) return '';
    const route = changes => 'works?' + new URLSearchParams({tab, status, ...(kind ? {kind} : {}), offset: '0', ...changes});
    const counts = result.counts;
    const tabs = TABS.map(([id, label]) => `<a class="${id === tab ? 'primary' : 'secondary'}" href="#${route({tab: id})}" ${id === tab ? 'aria-current="page"' : ''}>${h(label)}${counts[id] !== undefined ? `（${counts[id]}）` : ''}</a>`).join('');
    let body;
    if (tab === 'versions') {
      body = history.items.length ? `<ol class="stack works-history">${history.items.map(v => `<li><a class="list-item works-item" href="${open(v.kind, v.work_id, v.version_no)}">
          <span class="item-main"><strong>${h(v.title)} · v${v.version_no}</strong><span class="small muted">${h(KINDS[v.kind] || v.kind)} · ${h(v.origin)} · ${h(c.time(v.created_at))}${v.status === 'archived' ? ' · 已封存' : ''}</span></span></a></li>`).join('')}</ol>`
        : c.empty('還沒有任何版本。');
    } else {
      const items = result.items.map(item => `<a class="list-item works-item" href="${open(item.kind, item.id)}"><span class="item-main"><strong>${h(item.title || '（未命名）')}</strong>
          <span class="small muted">${h(KINDS[item.kind] || item.kind)} · <span class="tag">${h(PHASE_LABEL[item.phase])}</span>${item.people.length ? ` · ${h(item.people.join('、'))}` : ''}
          ${item.progress ? ` · ${item.progress.done}／${item.progress.total ?? '?'}` : ''} · v${item.current_version}${item.status === 'archived' ? ' · 已封存' : ''} · ${h(c.time(item.updated_at))}</span></span>
          ${item.can_resume ? '<span class="small">可恢復</span>' : ''}</a>`).join('');
      const pager = `<div class="button-row">${offset > 0 ? c.link(route({offset: String(Math.max(0, offset - PAGE))}), '上一頁') : ''}
        <span class="small muted">第 ${result.total ? offset + 1 : 0}–${Math.min(offset + PAGE, result.total)} 件，共 ${result.total} 件</span>
        ${offset + PAGE < result.total ? c.link(route({offset: String(offset + PAGE)}), '下一頁') : ''}</div>`;
      body = `${items ? `<div class="stack">${items}</div>` : c.empty(status === 'archived' ? '沒有已封存的作品。' : tab === 'all' ? '還沒有作品。按「＋ 建立新作品」開始。' : '這個分類目前沒有作品。')}${pager}`;
    }
    return `${c.heading('作品', '生成是建立作品的過程，作品是生成後的成果；進行中的作品打開後可以繼續，失敗的可以恢復。', c.link('create', '＋ 建立新作品', 'primary'))}
      <nav class="button-row works-tabs" aria-label="作品分類">${tabs}</nav>
      ${tab !== 'versions' ? `<div class="button-row works-filter">${kind ? `<span class="small muted">只看：${h(KINDS[kind] || kind)}</span>${c.link(route({kind: ''}).replace(/&?kind=[^&]*/, ''), '顯示全部種類', 'text-button')}` : ''}
        ${c.link(route({status: status === 'archived' ? 'active' : 'archived'}), status === 'archived' ? '查看使用中' : '查看已封存', 'text-button')}</div>` : ''}
      ${body}`;
  }

  function contentView(kind, content) {
    if (content && typeof content === 'object' && !Array.isArray(content)) {
      const simple = Object.entries(content).filter(([, value]) => typeof value === 'string' && value);
      const rest = Object.fromEntries(Object.entries(content).filter(([, value]) => typeof value !== 'string'));
      return `${simple.length ? `<dl class="char-fields">${simple.map(([key, value]) => `<dt>${h(key)}</dt><dd>${h(value)}</dd>`).join('')}</dl>` : ''}
        ${Object.keys(rest).length ? `<details class="space-top"><summary>其他資料</summary><pre class="works-json">${h(JSON.stringify(rest, null, 2))}</pre></details>` : ''}`;
    }
    return `<pre class="works-json">${h(JSON.stringify(content, null, 2))}</pre>`;
  }

  async function detail(id, versionParam) {
    const ticket = c.state.renderGeneration;
    const work = await c.api('/works/' + encodeURIComponent(id));
    const requested = Number(versionParam) || work.current_version;
    const shown = requested === work.current_version ? work.version : await c.api(`/works/${encodeURIComponent(id)}/versions/${requested}`);
    if (!fresh(ticket)) return '';
    const versions = work.versions.map(v => `<li><a href="#work/${encodeURIComponent(work.id)}?v=${v.version_no}" ${v.version_no === shown.version_no ? 'aria-current="true" class="char-version-active"' : ''}>v${v.version_no}${v.version_no === work.current_version ? '（目前）' : ''}</a>
        <span class="small muted">${h(v.origin)} · ${h(c.time(v.created_at))}</span></li>`).join('');
    const actions = [];
    if (work.kind === 'character_card') actions.push(c.link('character/' + encodeURIComponent(work.id), '在角色卡頁編輯', 'primary'));
    const PAGES = {story_opening: 'story', story_session: 'play', person_portrayal: 'portrayal', portrayal_session: 'portrayal-play',
      theater_cast: 'stage', theater_performance: 'performance', generated_work: 'run', roleplay_session: 'run'};
    if (PAGES[work.kind]) actions.push(c.link(PAGES[work.kind] + '/' + encodeURIComponent(work.id), '開啟', 'primary'));
    if (work.kind === 'self_persona') actions.push(c.link('persona?from=works', '在「我的設定」編輯', 'primary'));
    else actions.push(c.button('work-status', work.status === 'archived' ? '恢復' : '封存', 'secondary',
      `data-id="${h(work.id)}" data-status="${work.status === 'archived' ? 'active' : 'archived'}" data-revision="${work.revision}"`));
    return `${c.link('works', '← 我的作品', 'text-button')}
      ${c.heading(work.title, `${KINDS[work.kind] || work.kind} · 目前 v${work.current_version}${work.status === 'archived' ? ' · 已封存' : ''}`, `<div class="button-row">${actions.join('')}</div>`)}
      <div class="char-layout"><article class="card"><h2 class="section-title">v${shown.version_no}${shown.version_no === work.current_version ? '（目前版本）' : '（舊版本）'}</h2>
        <p class="small muted">${h(shown.content_schema)} · ${h(shown.origin)} · ${h(c.time(shown.created_at))}</p>${contentView(work.kind, shown.content)}</article>
      <aside class="card"><h2 class="section-title">版本</h2><ol class="char-versions">${versions}</ol></aside></div>`;
  }

  async function submit(form) {
    if (form.id === 'persona-form') { await savePersona(form); return true; }
    return false;
  }

  async function handleClick(target) {
    const action = target.dataset.action;
    if (action === 'persona-consent') {
      const body = {granted: target.dataset.granted === 'true'};
      await c.api('/self-persona/consent', {method: 'POST', body: {...body, request_id: c.requestId('persona-consent', body)}});
      c.toast(body.granted ? '已同意。' : '已撤回同意。');
      await c.render();
      return true;
    }
    if (action === 'work-status') {
      const body = {expected_revision: Number(target.dataset.revision), status: target.dataset.status};
      await c.api(`/works/${encodeURIComponent(target.dataset.id)}/status`, {method: 'POST', body: {...body, request_id: c.requestId('work-status:' + target.dataset.id, body)}});
      c.toast(body.status === 'archived' ? '作品已封存。' : '作品已恢復。');
      await c.render();
      return true;
    }
    return false;
  }

  /** 種類篩選切換時更新網址（列表依網址讀取）。 */
  function change(event) {
    if (event.target.id !== 'works-kind') return;
    const q = query();
    c.navigate('works?' + new URLSearchParams({kind: event.target.value, status: q.get('status') || 'active', offset: '0'}));
  }

  return {initialize, personaView, list, detail, submit, handleClick, change};
})();
document.addEventListener('change', event => { if (window.WorksUI) WorksUI.change(event); });
