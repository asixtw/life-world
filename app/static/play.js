// F05 短篇互動（2026-11-10 自 8445 移植到 B 原生 UI）：從故事開場開始冒險；每回合選一個行動或自由輸入，AI 角色回應後由玩家確認保存，最多 5 回合。
window.PlayUI = (() => {
  let c;
  const MAX_TURNS = 5;
  const RESOLUTION = {executed: '照你的意思完成', blocked: '受阻', modified: '結果改變'};
  const ENDING = {player_ended: '你主動結束了這段冒險。', turn_limit: `已完成 ${MAX_TURNS} 個回合，冒險結束。`};
  let candidate = null; // 尚未保存的角色回應：{session_id, base_version, generation, output, action, notice}

  function initialize(context) { c = context; }
  const h = value => c.esc(value);
  const fresh = ticket => ticket === c.state.renderGeneration;

  function turnView(turn, name) {
    const res = turn.action_resolution;
    const fake = turn.provider_kind === 'fake' ? '<span class="tag">測試用假回應</span>' : '';
    return `<li class="card play-turn"><p class="small muted">第 ${turn.turn_no} 回合 ${fake}</p>
      <p><strong>你的行動：</strong>${h(turn.action.text)}${turn.action.strategy ? ` <span class="tag">${h(turn.action.strategy)}</span>` : ''}</p>
      ${res ? `<p class="small"><strong>結算：</strong>${h(RESOLUTION[res.status] || res.status)}${res.reason ? `（${h(res.reason)}）` : ''}</p>` : ''}
      ${turn.action_effect ? `<p>${h(turn.action_effect)}</p>` : ''}
      <p class="play-line"><strong>${h(name)}：</strong>「${h(turn.npc_line)}」</p><p>${h(turn.scene)}</p>
      ${turn.narrative_notes ? `<p class="small muted">${h(turn.narrative_notes)}</p>` : ''}</li>`;
  }

  function actionForm(choices) {
    const options = choices.map((choice, index) => `<label class="play-choice"><input type="radio" name="play-action" value="${index}" ${index === 0 ? 'checked' : ''}>
        <span><strong>${h(choice.label)}</strong> <span class="tag">${h(choice.strategy)}</span><br><span class="small muted">${h(choice.description)}</span></span></label>`).join('');
    return `<form id="play-form" class="card stack"><h2 class="section-title">你接下來要做什麼？</h2>${options}
      <label class="play-choice"><input type="radio" name="play-action" value="free"><span><strong>自由行動</strong></span></label>
      <textarea name="free_text" maxlength="300" rows="2" placeholder="選「自由行動」時，寫下你要做的事"></textarea>
      <div class="button-row"><button type="submit" class="primary">送出行動</button></div></form>`;
  }

  async function detail(id) {
    const ticket = c.state.renderGeneration;
    const [work, status] = await Promise.all([c.api('/works/' + encodeURIComponent(id)), c.api('/generation/status')]);
    if (work.kind !== 'story_session') { c.navigate('work/' + encodeURIComponent(id)); return ''; }
    const content = work.version.content;
    const story = await c.api(`/works/${encodeURIComponent(content.story.work_id)}/versions/${content.story.version_no}`);
    if (!fresh(ticket)) return '';
    const name = content.character.name;
    const turns = content.turns;
    const active = content.status === 'active' && work.status === 'active';
    const choices = turns.length ? turns[turns.length - 1].choices : story.content.choices;
    const pending = candidate && candidate.session_id === work.id && candidate.base_version === work.current_version ? candidate : null;
    let next = '';
    if (!active) {
      next = `<p class="callout">${h(work.status === 'archived' ? '這段冒險已封存；恢復後才能繼續。' : ENDING[content.ending] || '冒險已結束。')}</p>`;
    } else if (pending) {
      const preview = {...pending.output, turn_no: turns.length + 1, action: pending.action, provider_kind: pending.generation.provider_kind};
      next = `<section class="stack"><h2 class="section-title">第 ${turns.length + 1} 回合（尚未保存）</h2><p class="small muted">${h(pending.notice || '')}</p>
        <ol class="play-turns">${turnView(preview, name)}</ol>
        <div class="button-row">${c.button('play-save', '確認這回合', 'primary')}${c.button('play-regenerate', '重新生成這回合', 'secondary')}${c.button('play-discard', '換一個行動', 'text-button')}</div></section>`;
    } else {
      next = status.available ? actionForm(choices) : '<p class="callout">AI 生成尚未設定，暫時無法進行新回合；已保存的紀錄仍可閱讀。</p>';
    }
    const end = active ? c.button('play-end', '結束冒險', 'secondary') : c.link('story/' + encodeURIComponent(content.story.work_id), '回到故事開場', 'secondary');
    return `${c.link('works?kind=story_session', '← 我的互動冒險', 'text-button')}
      ${c.heading(content.title, `互動冒險 · ${h(name)} · 已保存 ${turns.length}／${MAX_TURNS} 回合 · v${work.current_version}`, `<div class="button-row">${end}${c.link('work/' + encodeURIComponent(work.id), '版本與封存', 'secondary')}</div>`)}
      <section class="card stack"><p><strong>目標：</strong>${h(content.objective)}</p><p class="story-opening">${h(story.content.opening)}</p></section>
      ${turns.length ? `<ol class="play-turns space-top">${turns.map(turn => turnView(turn, name)).join('')}</ol>` : ''}
      <div class="space-top">${next}</div>`;
  }

  async function generate(work, action, again = false) {
    // 同一行動沿用同一提交代碼（重送不重複呼叫）；「重新生成」才換新代碼，再呼叫一次。
    const content = work.version.content;
    const input = {session_work_id: work.id, session_version: work.current_version, turn_no: content.turns.length + 1, action};
    const body = {module: 'character_reply', input};
    const requestId = c.requestId('play-turn', again ? {...body, again: Date.now()} : body);
    const result = await c.api('/ai/generate', {method: 'POST', body: {...body, request_id: requestId}});
    let choices = content.turns.length ? content.turns[content.turns.length - 1].choices : null;
    if (!choices) choices = (await c.api(`/works/${encodeURIComponent(content.story.work_id)}/versions/${content.story.version_no}`)).content.choices;
    const picked = action.kind === 'choice' ? choices[action.choice_index] : null;
    candidate = {session_id: work.id, base_version: work.current_version, generation: result.generation, output: result.output, notice: result.notice,
      action: picked ? {kind: 'choice', choice_index: action.choice_index, text: picked.label, strategy: picked.strategy}
        : {kind: 'free', choice_index: null, text: action.text, strategy: ''}};
    await c.render();
  }

  const sessionId = () => decodeURIComponent((location.hash.split('/')[1] || '').split('?')[0]);

  async function submit(form) {
    if (form.id !== 'play-form') return false;
    const data = new FormData(form);
    const picked = data.get('play-action');
    const text = String(data.get('free_text') || '').trim();
    if (picked === 'free' && !text) { c.toast('請先寫下你要做的事。'); return true; }
    const work = await c.api('/works/' + encodeURIComponent(sessionId()));
    await generate(work, picked === 'free' ? {kind: 'free', text} : {kind: 'choice', choice_index: Number(picked)});
    return true;
  }

  async function handleClick(target) {
    const action = target.dataset.action;
    if (action === 'play-start') {
      const body = {story_work_id: target.dataset.story, story_version: Number(target.dataset.version)};
      const work = await c.api('/play/sessions', {method: 'POST', body: {...body, request_id: c.requestId('play-start', {...body, at: Date.now()})}});
      candidate = null;
      c.navigate('play/' + encodeURIComponent(work.id));
      return true;
    }
    if (!['play-save', 'play-regenerate', 'play-discard', 'play-end'].includes(action)) return false;
    const work = await c.api('/works/' + encodeURIComponent(sessionId()));
    if (action === 'play-discard') { candidate = null; await c.render(); return true; }
    if (action === 'play-regenerate' && candidate) {
      const old = candidate.action;
      await generate(work, old.kind === 'free' ? {kind: 'free', text: old.text} : {kind: 'choice', choice_index: old.choice_index}, true);
      return true;
    }
    if (action === 'play-save' && candidate) {
      const body = {expected_revision: work.revision, generation_id: candidate.generation.id};
      const saved = await c.api(`/play/sessions/${encodeURIComponent(work.id)}/turns`, {method: 'POST', body: {...body, request_id: 'turn-save-' + candidate.generation.id}});
      candidate = null;
      const content = saved.version.content;
      c.toast(content.status === 'ended' ? `已完成 ${MAX_TURNS} 個回合，冒險結束。` : `第 ${content.turns.length} 回合已保存。`);
      await c.render();
      return true;
    }
    if (action === 'play-end') {
      if (!confirm('結束後不能再進行新回合；已保存的回合都會保留。確定結束？')) return true;
      await c.api(`/play/sessions/${encodeURIComponent(work.id)}/end`, {method: 'POST', body: {expected_revision: work.revision, request_id: `session-end-${work.id}-v${work.current_version}`}});
      candidate = null;
      c.toast('冒險已結束。');
      await c.render();
      return true;
    }
    return false;
  }

  return {initialize, detail, submit, handleClick};
})();
