// 多章節作品的「作品總覽」（2026-11-12）：一部作品分批續寫。
// - 已定稿的章節：主線，依序列出；每一章是一件各自的生成作品，點進去閱讀。
// - 草稿：續寫出來、還沒決定的章節。採納之後才成為主線的下一章；捨棄就是封存那件作品。
//   草稿只能接在它開始時的進度上；主線已經往前，就不能再採納。
// - 續寫：只要寫這一章的場景與要發生的事。人物、風格與演出要求沿用整部作品；
//   AI 會帶著前面各章的大綱、上一章結尾，以及每位人物自己的狀態與記憶接著寫。
// - 整部下載：把已定稿的章節匯出成一個有目錄的 HTML（沿用作品頁的下載流程）；閱讀版與互動版各一顆按鈕。
window.SeriesUI = (() => {
  let c;
  const LENGTHS = [['short', '短（約 8 段）'], ['medium', '中（約 16 段）'], ['long', '長（約 30 段）']];
  const FORMS = [['script', '劇本對白'], ['narrative', '小說敘事']];

  function initialize(context) { c = context; }
  const h = value => c.esc(value);
  const fresh = ticket => ticket === c.state.renderGeneration;
  const path = id => encodeURIComponent(id);

  function draftStatus(draft, mainline) {
    if (draft.run_status === 'completed') {
      return draft.can_adopt ? '已完成，等你決定' : `已完成；它是接在第 ${draft.base_episode_no} 章後面寫的，主線已經到第 ${mainline} 章，不能採納`;
    }
    if (draft.run_status === 'failed') return '已暫停；到這一章的頁面可以恢復';
    return `生成中（${draft.completed_segments}／${draft.total_segments ?? '?'} 段）`;
  }

  function draftsView(series) {
    if (!series.drafts.length) return '';
    const mainline = series.episodes.length;
    const items = series.drafts.map(draft => `<li class="list-item"><span class="item-main"><strong>${h(draft.title || '（未命名）')}</strong>
        <span class="small muted">${h(draftStatus(draft, mainline))}</span></span>
        <span class="button-row">${c.link('run/' + path(draft.work_id), draft.run_status === 'completed' ? '閱讀' : '查看進度', 'text-button')}
        ${draft.can_adopt ? c.button('series-adopt', `採納為第 ${series.next_episode_no} 章`, 'primary', `data-series="${h(series.id)}" data-work="${h(draft.work_id)}"`) : ''}
        ${c.button('series-discard', '捨棄', 'text-button', `data-work="${h(draft.work_id)}"`)}</span></li>`).join('');
    return `<section class="card space-top"><h2>草稿（${series.drafts.length}）</h2>
      <p class="small muted">草稿不影響已定稿的章節。採納之後才成為下一章；不要的可以捨棄，之後在作品的「已封存」裡還找得到。</p>
      <ul class="stack">${items}</ul></section>`;
  }

  function continueView(series, status) {
    const options = (items, picked) => items.map(([value, label]) => `<option value="${value}" ${value === picked ? 'selected' : ''}>${label}</option>`).join('');
    const output = series.output || {}; // 這部作品第 1 章選的長度與呈現形式：續寫預設沿用，使用者不用每一章重選（舊資料沒有就用原本的預設）
    return `<section class="card space-top"><h2>續寫第 ${series.next_episode_no} 章</h2>
      <p class="small muted">只要寫這一章的場景與要發生的事。AI 會接著前面已定稿的章節寫：各章大綱、上一章的結尾，以及每位人物自己的狀態與記憶。人物、風格與演出要求沿用這部作品；人物設定用開始當下最新的版本。</p>
      ${status.available ? '' : '<p class="callout">AI 生成尚未設定，暫時無法續寫。</p>'}
      <form id="series-next-form" class="stack" data-series="${h(series.id)}">
        <div class="field"><label for="series-description">這一章的場景與要發生的事（必填）</label>
          <textarea id="series-description" name="description" maxlength="2000" rows="4" required placeholder="時間、地點，以及這一章要發生什麼，例如「隔天早上，展場開門前，兩人要把標籤定案」。"></textarea></div>
        <div class="field"><label for="series-event">起始事件（選填）</label><input id="series-event" name="event" maxlength="800"></div>
        <div class="field"><label for="series-goal">這一章的目標（選填）</label><input id="series-goal" name="goal" maxlength="600"></div>
        <div class="field"><label for="series-length">長度</label><select id="series-length" name="length">${options(LENGTHS, output.length || 'short')}</select></div>
        <div class="field"><label for="series-form">呈現形式</label><select id="series-form" name="form">${options(FORMS, output.form || 'script')}</select></div>
        <div class="field"><label for="series-title">章名（選填，留白時由 AI 規劃）</label><input id="series-title" name="title" maxlength="60"></div>
        <div class="button-row"><button type="submit" class="primary" ${status.available ? '' : 'disabled'}>開始生成這一章</button></div>
        <p class="small muted">生成出來的是草稿；看過之後再決定要不要採納。</p>
      </form></section>`;
  }

  function exportView(series, exports) { // 兩顆按鈕都交給作品頁的下載流程（GenerationUI 的 gen-export）；互動版多帶 data-player="play"
    // 這裡的互動版按鈕不帶 data-interactive：整部下載不另外準備互動內容（那一步是一章一章做的，在各章的作品頁下載互動版時準備）。
    if (!exports) return '';
    if (!exports.available) return '<section class="card space-top"><p class="small muted">這個環境還沒有開放下載作品。</p></section>';
    const last = exports.items[0];
    return `<section class="card space-top" id="gen-export"><h2>下載整部作品（HTML）</h2>
      <p class="small muted">把已定稿的 ${series.episodes.length} 章存成一個有目錄的 HTML 檔，下載後可以離線打開。草稿不在裡面。檔案裡不含人物設定的欄位與我的設定；台詞與反應是 AI 依人物設定寫出來的，可能用到設定裡的說法，分享前可以先看過。</p>
      <p class="small muted">互動版一次看一段（跨章連續）：先選一個人的視角入局，他的真心話直接看得到，別人的只能偷看幾次；讀完可以看每一章每個人的底牌。同樣可以離線打開。</p>
      <p class="small muted">線索與抉擇是一章一章準備的：在那一章的作品頁下載過互動版的章節，合集裡才有它的線索與抉擇（選了真結局才繼續到下一章）；其他章節照常閱讀。</p>
      <div class="button-row">${c.button('gen-export', '下載 HTML', 'primary', `data-id="${h(series.id)}"`)}
        ${c.button('gen-export', '下載互動版', 'secondary', `data-id="${h(series.id)}" data-player="play"`)}</div>
      ${last ? `<p class="small muted">上次匯出：${h(c.time(last.created_at))}・${(last.size / 1024).toFixed(1)} KB</p>` : ''}</section>`;
  }

  async function view(id) {
    const ticket = c.state.renderGeneration;
    const [series, exports, status] = await Promise.all([c.api('/series/' + path(id)),
      c.api('/works/' + path(id) + '/exports').catch(() => null), c.api('/generation/status')]); // 匯出清單讀不到時不擋住這一頁
    if (!fresh(ticket)) return '';
    const cast = series.cast.map(member => h(member.name) + (member.is_user ? '（我）' : '')).join('、');
    const chapters = series.episodes.map(episode => `<li><a class="list-item works-item" href="#run/${path(episode.work_id)}"><span class="item-main">
        <strong>第 ${episode.no} 章　${h(episode.title || '（未命名）')}</strong><span class="small muted">${episode.segments} 段 · ${h(c.time(episode.adopted_at))}</span></span></a></li>`).join('');
    return `${c.link('works', '← 作品', 'text-button')}
      ${c.heading(series.title || '多章節作品', `人物：${cast}`)}
      <section class="card"><h2>已定稿的章節（${series.episodes.length}）</h2><ol class="stack series-chapters">${chapters}</ol></section>
      ${draftsView(series)}${continueView(series, status)}${exportView(series, exports)}`;
  }

  async function submit(form) {
    if (form.id !== 'series-next-form') return false;
    const value = name => (form.elements[name]?.value || '').trim();
    const id = form.dataset.series;
    const body = {title: value('title'), scene: {description: value('description'), start: {event: value('event'), goal: value('goal')}},
      output: {length: value('length') || 'short', form: value('form') || 'script'}};
    const draft = await c.api(`/series/${path(id)}/episodes`, {method: 'POST', body: {...body, request_id: c.requestId('series-next:' + id, body)}});
    c.state.dirty = false;
    c.toast('已開始生成這一章的草稿。');
    c.navigate('run/' + path(draft.id)); // 到這一章的作品頁看生成進度；完成後回作品總覽決定要不要採納
    return true;
  }

  async function handleClick(target) {
    const action = target.dataset.action || '';
    if (action === 'series-open') { // 作品頁的「續寫下一章」：把這件作品開成多章節作品（已經開過就回那一部）
      const series = await c.api('/series', {method: 'POST', body: {work_id: target.dataset.id, request_id: c.requestId('series-open:' + target.dataset.id, {})}});
      c.navigate('series/' + path(series.id));
      return true;
    }
    if (action === 'series-adopt') {
      const {series, work} = target.dataset;
      await c.api(`/series/${path(series)}/episodes/${path(work)}/adopt`, {method: 'POST', body: {request_id: c.requestId('series-adopt:' + work, {})}});
      c.toast('已採納，成為主線的下一章。');
      await c.render();
      return true;
    }
    if (action === 'series-discard') { // 捨棄草稿＝封存那件作品（之後在作品的「已封存」裡可以恢復）
      const work = await c.api('/works/' + path(target.dataset.work));
      await c.api(`/works/${path(target.dataset.work)}/status`, {method: 'POST',
        body: {request_id: c.requestId('series-discard:' + target.dataset.work + ':' + work.revision, {}), expected_revision: work.revision, status: 'archived'}});
      c.toast('已捨棄這份草稿。');
      await c.render();
      return true;
    }
    return false;
  }

  return {initialize, view, submit, handleClick};
})();
