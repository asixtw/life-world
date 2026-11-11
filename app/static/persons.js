// Unified Person 2.0：#persons 是唯一的人物建立、編輯與管理入口（產品規格 2.0，2026-11-11）。
// - 列表：搜尋、人物類型／分類／狀態篩選、排序、每頁 50 人（URL 的 offset 保存頁次，翻頁保留條件，重新套用篩選回到第一頁）；卡片可檢視、編輯、封存。
// - 新增／編輯：單頁四個區塊（基本資料、背景與世界觀、人物特質與設定、其他人物資料），按一次「儲存人物」。
//   新增時人物與第 1 版人物設定在同一交易建立；編輯時基本資料走 PATCH（revision 防覆蓋），人物設定有變更才 PUT 新增一版（expected_profile_id 防覆蓋）。
//   AI 產生人物設定在編輯表單的「人物特質與設定」區塊：勾選要產生的欄位，結果只回填被選的欄位，未選的保留；按「儲存人物」才保存。
// - 詳細頁：總覽、人物設定（唯讀，編輯回到同一張表單）、經歷、關係。
// - 關係（P4）：在詳細頁的「關係」分頁直接新增、編輯、封存、恢復，不需要回舊的關係頁。同一對人物只有一筆關係，描述由雙方共用；
//   類型選填、可複選（最多 10 種）；選到已有關係的人物時改為編輯（已封存則提供恢復），不覆蓋；來源只列與兩位人物有關的我的紀錄。
//   注意：按鈕不可用 data-person 屬性（舊關係模組會攔截），一律用 data-person-ref。
// 同名人物可並存；類型與分類選填；封存不刪除，已封存的人物只能讀取與恢復。people.notes（人物備註）與 notes 資料表（人物設定版本）是兩回事。
window.PersonsUI = (() => {
  let c; // 主程式注入的共用工具與狀態
  let editing = null; // 編輯中的人物：{id, revision, person, profile, ai:{generationId, snapshot}|null}
  const TYPE_OPTIONS = [['', '未指定（儲存為真實類型）'], ['real', '真實類型（含預設）'], ['historical', '歷史人物'], ['fictional', '虛構人物'], ['original', '自創人物']];
  const TYPE_FILTERS = [['', '全部'], ['real', '真實'], ['historical', '歷史'], ['fictional', '虛構'], ['original', '自創']];
  const CATEGORIES = [['business', '業務'], ['life', '生活'], ['learning', '學習'], ['other', '其他']];
  const PAGE_SIZE = 50; // 每頁人數；與 /api/persons 的 limit 一致
  // 人物設定（2026-11-11 定型）：五區塊九欄位，只描述人物本身；JSON key 不變（person_profile.v1）。
  // 作品場景、演出職務、演出目標、情境指令、範例台詞與外部演出規則不屬於人物設定，在「作品」中處理。
  // [欄位, 名稱, 上限, 說明, 填寫提示]
  const PROFILE_BLOCKS = [
    ['A', '人物背景', [['background', '背景', 3000, '出身、成長經歷、重要轉折，以及所處的時代或環境。', '例如：出身廬江士族，少年時與孫策結為好友，二十四歲任建威中郎將。']]],
    ['B', '人格特質', [
      ['personality', '性格', 2000, '這個人物給人的整體個性與情緒傾向。', '例如：外表儒雅從容，內心好勝，遇到挑戰時反而更冷靜。'],
      ['motivation', '動機', 1500, '人物長期追求或在意的事，驅動他行動的原因。', '例如：希望守住江東基業，證明自己的才能。'],
      ['stance', '核心信念與價值觀', 1500, '人物相信什麼、重視什麼，做選擇時以什麼為優先。', '例如：重視信義與知遇之恩，認為以智取勝勝過蠻力。']]],
    ['C', '能力與知識', [
      ['abilities', '能力與專長', 1500, '人物擅長的技能、專業或天賦。', '例如：水軍指揮、音律、外交談判。'],
      ['knowledge_boundary', '知識範圍', 1000, '人物知道與不知道的事，例如所處時代、專業領域與見聞的範圍。', '例如：熟悉東漢末年的政局與兵法；不知道後世發生的事。']]],
    ['D', '行為與表達', [
      ['behavior', '行為模式', 2000, '人物在日常與壓力下常見的行為、習慣與反應。', '例如：做決定前會先聽取各方意見；受到輕視時會以行動回應。'],
      ['expression', '說話與表達方式', 2000, '語氣、用詞、說話節奏與常用的表達習慣。', '例如：說話溫和有禮，常引用典故，語氣從容。']]],
    ['E', '個人弱點', [['restrictions', '固有限制與弱點', 1500, '人物本身的弱點、缺陷或做不到的事。這裡描述人物，不是作品演出的規則。', '例如：心高氣傲；身體不算強健；不擅長陸戰。']]],
  ];
  const PROFILE_FIELDS = PROFILE_BLOCKS.flatMap(([, , fields]) => fields.map(([key, label, max]) => [key, label, max]));
  const ORIGIN = {manual: '人工填寫', ai: 'AI 產生', ai_edited: 'AI 產生後修改'};
  const RELATION_KINDS = [['family', '家人'], ['partner', '伴侶'], ['friend', '朋友'], ['colleague', '同事'], ['classmate', '同學'], ['mentor', '師徒'],
    ['client', '客戶'], ['business', '商業往來'], ['neighbor', '鄰居'], ['rival', '對手'], ['enemy', '敵人'], ['other', '其他']];
  const MAX_RELATION_KINDS = 10, MAX_RELATION_SOURCES = 30;
  const RELATION_HINT = '這段關係由雙方共用，請描述兩人之間的關係，不是單方面的人物備註。';
  const kindLabel = kind => (RELATION_KINDS.find(([key]) => key === kind) || [kind, kind])[1];
  let viewing = null; // 目前詳細頁讀到的資料（人物與關係），供關係操作使用；每次顯示詳細頁時更新
  let relation = null; // 關係視窗的狀態：{person, connections, mode:'create'|'edit'|'archived', connection, other, kinds, description, checked, eligible, results, more, q, notice, original}
  let searchSequence = 0, searchTimer = null; // 人物搜尋：只採用最後一次查詢的結果
  let experience = null; // 人物經歷視窗的狀態：{mode:'create'|'edit'|'view', item, subject, participants:[人物摘要], results, more, q, values:{title,content,type,year,month,day,label}}
  let experienceSearchSequence = 0; // 參與人物搜尋：只採用最後一次查詢的結果
  let listMemory = null; // 最後看過的人物列表網址（含搜尋條件與頁數）：{owner, route}；返回連結回到這裡，換帳號不沿用

  const ownerId = () => (c.state.me ? c.state.me.owner_id : null);
  /** 「← 返回人物列表」的目的地：同一帳號最後看過的列表（保留搜尋與頁數）；沒看過就回預設列表。 */
  const backToList = () => (listMemory && listMemory.owner === ownerId() ? listMemory.route : 'persons');
  const routePath = route => String(route || '').split('?')[0];

  /**
   * 換頁後要捲到哪裡（主程式在畫面換好後呼叫）。
   * 主程式依網址記住捲動位置；編輯頁總是從底部的「儲存人物／返回人物」離開，若照記憶恢復，下次開啟就停在表單底部。
   * 規則：進入新頁面從頂端開始；同一頁重畫（例如儲存或封存關係後）與同一位人物切換分頁維持目前位置；
   * 從人物頁（詳細、編輯、新增）回到人物列表時，回到原本的列表位置。
   * @param from 換頁前的路由（第一次載入是 null）  @param to 新路由
   * @param currentY 換頁前的捲動位置  @param rememberedY 主程式為新路由記住的位置
   */
  function scrollTarget(from, to, currentY, rememberedY) {
    const before = routePath(from), after = routePath(to);
    if (from === to) return currentY;
    if (before === after && after.startsWith('persons/')) return currentY;
    if (after === 'persons' && /^persons(\/|-edit\/|-new$)/.test(before)) return rememberedY;
    return 0;
  }

  function initialize(context) { c = context; }
  const h = value => c.esc(value);
  const fresh = ticket => ticket === c.state.renderGeneration; // 拒絕較舊的非同步回應覆蓋新畫面
  const enabled = () => Boolean(c.state.capabilities?.unified_people);
  const encodeId = id => encodeURIComponent(id);

  function typeKey(p) { return p.person_subtype || p.person_type; } // 下拉選單的值：子類型優先
  function typeLabel(p) { return (TYPE_OPTIONS.find(([key]) => key === typeKey(p)) || ['', '真實類型（含預設）'])[1]; }
  function categoryLabel(key) { return (CATEGORIES.find(([k]) => k === key) || ['', '其他'])[1]; }
  function typeBody(key) { // 選填類型 → API 欄位（只選子類型時由伺服器推出類型）
    if (key === 'historical' || key === 'original') return {person_type: key === 'historical' ? 'real' : 'fictional', person_subtype: key};
    return key ? {person_type: key, person_subtype: null} : {};
  }
  const list = value => [...new Set(String(value || '').split(/[,，\n]/).map(item => item.trim()).filter(Boolean))];
  const options = (pairs, selected) => pairs.map(([key, label]) => `<option value="${key}" ${key === selected ? 'selected' : ''}>${h(label)}</option>`).join('');
  const clip = (text, limit) => (text && text.length > limit ? text.slice(0, limit) + '…' : text || '');

  function unavailable() {
    return `${c.heading('人物', '新人物功能要等資料庫升級（Schema 010）完成後才開放。')}${c.empty('目前請先使用「關係」頁管理人物。', c.link('people', '前往關係'))}`;
  }

  // ---------------- 列表 ----------------

  /** 列表路由：只放非預設的條件；offset 為 0 時省略。 */
  function listRoute(filter, offset) {
    const query = new URLSearchParams();
    if (filter.q) query.set('q', filter.q);
    if (filter.type) query.set('type', filter.type);
    if (filter.category) query.set('category', filter.category);
    if (filter.status === 'archived') query.set('status', 'archived');
    if (filter.sort === 'name') query.set('sort', 'name');
    if (offset > 0) query.set('offset', String(offset));
    return 'persons' + (query.toString() ? '?' + query.toString() : '');
  }

  function card(p) {
    const id = encodeId(p.id), archived = p.status === 'archived';
    const meta = [typeLabel(p), categoryLabel(p.category), p.followed ? '已關注' : '', p.origin_type === 'legacy' ? '舊資料' : '', archived ? '已封存' : ''].filter(Boolean);
    // 卡片整理（2026-11-11 Jerry 指定）：整張卡片都進人物詳細頁（有總覽／人物設定／經歷／關係頁籤），完整的編輯表單只從詳細頁的「編輯人物」開啟。
    // 每張卡片只有一個連結：使用中是「編輯」、已封存是「查看」；CSS 把它的點擊範圍延伸到整張卡片。封存／恢復是浮在上層的獨立按鈕。
    const label = archived ? '查看' : '編輯';
    const actions = [`<a class="text-button persons-card-open" href="#persons/${id}" aria-label="${label} ${h(p.name)}">${label}</a>`,
      c.button('persons-status', archived ? '恢復' : '封存', 'text-button', `data-id="${h(p.id)}" data-status="${archived ? 'active' : 'archived'}" data-revision="${p.revision}"`)];
    return `<article class="card char-card persons-list-card"><strong class="persons-card-name">${h(p.name)}</strong>
        <span class="small muted">${h(meta.join(' · '))}</span>
        ${p.aliases.length ? `<span class="small">別名：${h(p.aliases.join('、'))}</span>` : ''}
        ${p.description ? `<span class="char-summary">${h(clip(p.description, 120))}</span>` : ''}
        ${p.tags.length ? `<p class="char-tags">${p.tags.map(tag => `<span class="tag">${h(tag)}</span>`).join('')}</p>` : ''}
        <div class="button-row">${actions.join('')}</div></article>`;
  }

  /** 人物列表：搜尋、人物類型／分類／狀態篩選、排序、分頁、新增入口。 */
  async function listView(params) {
    if (!enabled()) return unavailable();
    const ticket = c.state.renderGeneration;
    const filter = {q: params.get('q') || '', type: params.get('type') || '', category: params.get('category') || '',
      status: params.get('status') === 'archived' ? 'archived' : 'active', sort: params.get('sort') === 'name' ? 'name' : 'recent'};
    const requested = Number.parseInt(params.get('offset') || '0', 10);
    let offset = Number.isFinite(requested) && requested > 0 ? Math.floor(requested / PAGE_SIZE) * PAGE_SIZE : 0; // 對齊頁首，負數或非數字回第一頁
    const query = new URLSearchParams({q: filter.q, category: filter.category, status: filter.status, sort: filter.sort, limit: String(PAGE_SIZE)});
    if (filter.type === 'historical' || filter.type === 'original') query.set('person_subtype', filter.type); else if (filter.type) query.set('person_type', filter.type);
    const fetchPage = start => { query.set('offset', String(start)); return c.api('/persons?' + query.toString()); };
    let data = await fetchPage(offset);
    if (!fresh(ticket)) return '';
    if (offset > 0 && offset >= data.total) { // 超出範圍（例如封存後最後一頁變空）：回到最後一個有效頁，並更正網址
      offset = data.total ? Math.floor((data.total - 1) / PAGE_SIZE) * PAGE_SIZE : 0;
      data = await fetchPage(offset);
      if (!fresh(ticket)) return '';
      const corrected = listRoute(filter, offset);
      history.replaceState(null, '', '#' + corrected); c.state.route = corrected;
    }
    const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE)), page = offset / PAGE_SIZE + 1;
    const pager = `<nav class="button-row space-top" aria-label="人物分頁"><span class="small muted">共 ${data.total} 位 · 第 ${page}／${pages} 頁</span>
      ${offset > 0 ? c.link(listRoute(filter, offset - PAGE_SIZE), '上一頁', 'secondary') : ''}${offset + PAGE_SIZE < data.total ? c.link(listRoute(filter, offset + PAGE_SIZE), '下一頁', 'secondary') : ''}</nav>`;
    const cards = data.items.map(card).join('');
    const filtered = filter.q || filter.type || filter.category;
    listMemory = {owner: ownerId(), route: routePath(c.state.route) === 'persons' ? c.state.route : listRoute(filter, offset)};
    return `${c.heading('人物', '建立及管理你世界中的人物設定。', c.link('persons-new', '新增人物', 'primary'))}
      <form id="persons-filter-form" class="card stack space-bottom" role="search" data-search>
        <div class="field"><label for="persons-q">搜尋</label><input id="persons-q" name="q" value="${h(filter.q)}" maxlength="200" placeholder="搜尋人物名稱、別名、背景或標籤"></div>
        <div class="button-row">
          <label class="small">人物類型 <select name="type">${options(TYPE_FILTERS, filter.type)}</select></label>
          <label class="small">分類 <select name="category">${options([['', '全部'], ...CATEGORIES], filter.category)}</select></label>
          <label class="small">狀態 <select name="status">${options([['active', '使用中'], ['archived', '已封存']], filter.status)}</select></label>
          <label class="small">排序 <select name="sort">${options([['recent', '最近新增'], ['name', '姓名']], filter.sort)}</select></label>
          <button type="submit" class="secondary">套用</button></div></form>
      <section><h2 class="section-title">${filter.status === 'archived' ? '已封存的人物' : '人物'}（${data.total}）</h2>
      ${cards ? `<div class="char-grid">${cards}</div>${pager}` : c.empty(filter.status === 'archived' ? '沒有已封存的人物。' : filtered ? '沒有符合條件的人物。' : '還沒有人物。', filter.status === 'archived' ? '' : c.link('persons-new', '新增人物'))}</section>`;
  }

  // ---------------- 新增／編輯（單頁、分區、一次儲存）----------------

  function field(id, label, control, note = '') {
    return `<div class="field"><label for="${id}">${h(label)}</label>${control}${note ? `<p class="small muted">${h(note)}</p>` : ''}</div>`;
  }
  const textInput = (id, name, value, max, extra = '') => `<input id="${id}" name="${name}" maxlength="${max}" value="${h(value || '')}" ${extra}>`;
  const textArea = (id, name, value, max, rows = 3, placeholder = '') =>
    `<textarea id="${id}" name="${name}" maxlength="${max}" rows="${rows}"${placeholder ? ` placeholder="${h(placeholder)}"` : ''}>${h(value || '')}</textarea>`;

  function aiPanel(person, status) { // 只在編輯既有人物時可用：上下文由伺服器讀取已保存的人物資料
    if (!person) return `<p class="small muted">儲存人物後，就可以在編輯頁使用「AI 產生人物設定」。</p>`;
    if (!status || !status.available) return `<p class="small muted">AI 產生目前無法使用（AI 服務尚未設定）；仍可手動填寫。</p>`;
    const checks = PROFILE_BLOCKS.map(([letter, title, fields]) => `<div><span class="small muted">${letter}｜${h(title)}</span>
      ${fields.map(([key, label]) => `<label class="check-line"><input type="checkbox" name="ai_target" value="${key}" checked> ${h(label)}</label>`).join('')}</div>`).join('');
    return `<div id="persons-ai-panel" class="card stack space-bottom"><h3 class="section-title">AI 輔助：AI 產生人物設定</h3>
      <p class="small muted">依已儲存的基本資料、背景與目前的人物設定產生候選，只描述人物本身。只回填勾選的欄位，未勾選的保留原內容；按「儲存人物」才會保存。</p>
      <fieldset class="field"><legend>方式</legend>
        <label class="check-line"><input type="radio" name="ai_mode" value="generate" checked> 產生（空白欄位補上、已有內容可重寫）</label>
        <label class="check-line"><input type="radio" name="ai_mode" value="improve"> 改善現有內容（保留原本方向，補充與潤飾）</label></fieldset>
      <fieldset class="field"><legend>要處理的欄位</legend><div class="char-checks" id="persons-ai-fields">${checks}</div></fieldset>
      ${field('persons-ai-guidance', '這次的偏好（選填，最多 500 字）', textArea('persons-ai-guidance', 'ai_guidance', '', 500, 2))}
      <label class="check-line"><input type="checkbox" id="persons-ai-consent"> 我了解這位人物的基本資料、背景與目前設定會送往 AI 服務（${h(status.provider || 'AI')}）產生候選。</label>
      <div class="button-row">${c.button('persons-ai-generate', 'AI 產生人物設定', 'secondary', `data-person-ref="${h(person.id)}"`)}</div>
      <p id="persons-ai-notice" class="callout" hidden></p></div>`;
  }

  /** 單頁表單：01 基本資料、02 背景與世界觀、03 人物特質與設定（含 AI）、04 其他人物資料。 */
  function personForm(person, profile, status) {
    const p = person || {aliases: [], roles: [], tags: [], category: 'other'};
    const fields = profile ? profile.fields : {};
    const meta = profile ? `目前人物設定：第 ${profile.version} 版 · ${h(ORIGIN[profile.origin] || profile.origin)} · ${h(c.time(profile.saved_at))}（儲存變更時新增一版，舊版保留）` : '尚未填寫人物設定。';
    return `<form id="${person ? 'persons-edit-form' : 'persons-create-form'}" class="stack">
      <section class="card stack"><h2 class="section-title">01｜基本資料</h2><p class="small muted">定義這個人物是誰。只有人物名稱必填。</p>
        ${field('person-name', '人物名稱', textInput('person-name', 'name', p.name, 100, 'required'))}
        ${field('person-aliases', '別名（以逗號分隔，最多 20 個）', textInput('person-aliases', 'aliases', p.aliases.join('，'), 2000))}
        ${field('person-type', '人物類型（選填）', `<select id="person-type" name="type">${options(TYPE_OPTIONS, person ? typeKey(p) : '')}</select>`,
          '未指定時儲存為真實類型；資料庫無法區分「未指定」與「真實」，這不代表已核實為真實人物。歷史人物屬於真實類型；自創人物屬於虛構類型。')}
        ${field('person-category', '分類（選填）', `<select id="person-category" name="category">${options(CATEGORIES, p.category || 'other')}</select>`)}
        ${field('person-roles', '人物身分／職業／稱號（以逗號分隔）', textInput('person-roles', 'roles', p.roles.join('，'), 2000), '這是人物自身的身分，不是作品中的演出職務。')}
        ${field('person-tags', '標籤（以逗號分隔）', textInput('person-tags', 'tags', p.tags.join('，'), 2000))}
        <label class="check-line"><input type="checkbox" id="person-followed" name="followed" value="yes" ${p.followed ? 'checked' : ''}> 關注這位人物</label></section>
      <section class="card stack"><h2 class="section-title">02｜背景與世界觀</h2><p class="small muted">描述人物所處的世界、時代、出身及背景。</p>
        ${field('person-description', '人物背景與世界觀描述（最多 2000 字）', textArea('person-description', 'description', p.description, 2000, 4))}
        ${field('person-common-context', '相關背景／共同場合（最多 1000 字）', textArea('person-common-context', 'common_context', p.common_context, 1000))}</section>
      <section class="card stack" id="persons-profile-section"><h2 class="section-title">03｜人物設定</h2>
        <p class="small muted">只描述人物本身，全部選填，可以逐步補充。作品的場景、演出職務、演出目標與台詞在「作品」中設定。${meta}</p>
        ${aiPanel(person, status)}
        ${PROFILE_BLOCKS.map(([letter, title, items]) => `<div class="stack"><h3 class="section-title">${letter}｜${h(title)}</h3>
          ${items.map(([key, label, max, help, hint]) => field('profile-' + key, label, textArea('profile-' + key, 'profile_' + key, fields[key], max, 3, hint), help)).join('')}</div>`).join('')}</section>
      <section class="card stack"><h2 class="section-title">04｜其他人物資料</h2><p class="small muted">承接原人物管理的資料。</p>
        ${field('person-notes', '人物備註（最多 4000 字）', textArea('person-notes', 'notes', p.notes, 4000, 4))}</section>
      <div class="button-row">${c.link(person ? `persons/${encodeId(person.id)}` : 'persons', person ? '返回人物' : '返回人物列表', 'secondary')}<button type="submit" class="primary">儲存人物</button></div></form>`;
  }

  function createForm() {
    if (!enabled()) return unavailable();
    editing = null;
    return `${c.link(backToList(), '← 返回人物列表', 'text-button')}${c.heading('新增人物', '只有人物名稱必填，其他內容可以逐步補充。')}${personForm(null, null, null)}`;
  }

  async function editForm(id) {
    if (!enabled()) return unavailable();
    const ticket = c.state.renderGeneration;
    const [data, status] = await Promise.all([c.api('/persons/' + encodeId(id)), c.api('/generation/status').catch(() => null)]);
    if (!fresh(ticket)) return '';
    if (data.person.status === 'archived') { // 伺服器也會拒絕（409 person_archived）；這裡不提供可提交的表單
      editing = null;
      return `${c.link('persons/' + encodeId(id), '← 返回人物', 'text-button')}${c.heading('編輯人物', data.person.name)}
        ${c.empty('這位人物已封存，不能修改。恢復後即可編輯。', c.link('persons/' + encodeId(id), '返回人物詳細頁'))}`;
    }
    editing = {id: data.person.id, revision: data.person.revision, person: data.person, profile: data.profile, ai: null};
    return `${c.link('persons/' + encodeId(id), '← 返回人物', 'text-button')}${c.heading('編輯人物', data.person.name)}${personForm(data.person, data.profile, status)}`;
  }

  /** 讀出表單的基本資料與舊人物欄位。 */
  function basicBody(form) {
    const data = new FormData(form);
    return {name: String(data.get('name') || '').trim(), aliases: list(data.get('aliases')), roles: list(data.get('roles')), tags: list(data.get('tags')),
      category: data.get('category') || 'other', description: String(data.get('description') || '').trim(),
      common_context: String(data.get('common_context') || '').trim(), notes: String(data.get('notes') || '').trim(), followed: data.get('followed') === 'yes',
      ...typeBody(data.get('type'))};
  }
  function profileBody(form) {
    const data = new FormData(form);
    return Object.fromEntries(PROFILE_FIELDS.map(([key]) => [key, String(data.get('profile_' + key) || '').trim()]));
  }
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

  async function saveEdit(form) {
    const basic = basicBody(form);
    if (!form.querySelector('#person-type').value) { basic.person_type = 'real'; basic.person_subtype = null; } // 改回未指定＝預設真實類型
    const before = editing.person;
    const changed = Object.fromEntries(Object.entries(basic).filter(([key, value]) => key === 'person_subtype' ? (before.person_subtype || null) !== value : !same(before[key], value)));
    if (Object.keys(changed).length) { // 只送出有變更的欄位；revision 防止覆蓋他處較新的修改
      const updated = await c.api('/persons/' + encodeId(editing.id), {method: 'PATCH', body: {expected_revision: editing.revision, ...changed}});
      editing.revision = updated.revision; editing.person = updated;
    }
    const fields = profileBody(form);
    const current = editing.profile ? editing.profile.fields : Object.fromEntries(PROFILE_FIELDS.map(([key]) => [key, '']));
    if (!same(fields, PROFILE_FIELDS.reduce((acc, [key]) => ({...acc, [key]: (current[key] || '').trim()}), {})) || editing.ai) {
      const body = {expected_profile_id: editing.profile ? editing.profile.id : null, fields};
      if (editing.ai) Object.assign(body, {origin: same(fields, editing.ai.snapshot) ? 'ai' : 'ai_edited', generation_id: editing.ai.generationId});
      try {
        editing.profile = await c.api(`/persons/${encodeId(editing.id)}/profile`, {method: 'PUT', body: {...body, request_id: c.requestId('persons-profile:' + editing.id, body)}});
        editing.ai = null;
      } catch (error) { // 基本資料已儲存、人物設定沒有：保留表單內容讓使用者重試
        error.message = '基本資料已儲存；人物設定沒有儲存：' + (error.message || '');
        throw error;
      }
    }
    return editing.person;
  }

  // ---------------- 詳細頁 ----------------

  function profileRows(profile, limit) {
    if (!profile) return '';
    return PROFILE_FIELDS.filter(([key]) => profile.fields[key]).map(([key, label]) => `<dt>${h(label)}</dt><dd>${h(limit ? clip(profile.fields[key], limit) : profile.fields[key])}</dd>`).join('');
  }

  function overview(data) {
    const p = data.person;
    const rows = [['人物類型', typeLabel(p)], ['分類', categoryLabel(p.category)], ['別名', p.aliases.join('、')], ['人物身分／職業／稱號', p.roles.join('、')],
      ['標籤', p.tags.join('、')], ['關注', p.followed ? '已關注' : ''], ['來源', p.origin_type === 'legacy' ? '舊資料（Schema 010 前建立）' : '人工建立']]
      .filter(([, value]) => value).map(([label, value]) => `<dt>${h(label)}</dt><dd>${h(value)}</dd>`).join('');
    const background = [['人物背景與世界觀', p.description], ['相關背景／共同場合', p.common_context], ['人物備註', p.notes]]
      .filter(([, value]) => value).map(([label, value]) => `<dt>${h(label)}</dt><dd>${h(clip(value, 300))}</dd>`).join('');
    // 重要關係：只列使用中的關係。關係資料沒有時間欄位，所以「已關注的人物優先，其次依姓名」（伺服器已依姓名排序，sort 是穩定排序）。
    const important = data.connections.filter(x => x.status !== 'archived').sort((a, b) => Number(b.person.followed) - Number(a.person.followed)).slice(0, 3);
    const relations = important.map(x => `<li><a href="#persons/${encodeId(x.person.id)}">${h(x.person.name)}</a> <span class="small muted">${h([x.relation_types.map(type => kindLabel(type.kind)).join('、'), clip(x.text, 60)].filter(Boolean).join(' · '))}</span></li>`).join('');
    return `<h3 class="section-title">人物基本資料</h3><dl class="char-fields">${rows}</dl>
      ${background ? `<h3 class="section-title">人物背景摘要</h3><dl class="char-fields">${background}</dl>` : ''}
      <h3 class="section-title">人物設定摘要</h3>${data.profile ? `<dl class="char-fields">${profileRows(data.profile, 80)}</dl>` : '<p class="small muted">尚未填寫人物設定。</p>'}
      <h3 class="section-title">經歷</h3><p class="small">我的紀錄 ${data.experiences.mine} 筆 · 人物經歷 ${data.experiences.person_experiences} 筆</p>
      <h3 class="section-title">重要關係</h3>${relations ? `<ul class="char-versions">${relations}</ul>` : '<p class="small muted">還沒有關係。</p>'}
      <p>${c.link(`persons/${encodeId(p.id)}?tab=relations`, '查看與管理關係', 'text-button')}</p>`;
  }

  function profileTab(data) {
    const p = data.person, profile = data.profile, archived = p.status === 'archived';
    const meta = profile ? `第 ${profile.version} 版 · ${h(ORIGIN[profile.origin] || profile.origin)} · ${h(c.time(profile.saved_at))}` : '尚未填寫人物設定。';
    const actions = archived ? '' : `<div class="button-row">${c.link(`persons-edit/${encodeId(p.id)}`, '編輯人物設定', 'secondary')}${c.link(`persons-edit/${encodeId(p.id)}`, 'AI 產生人物設定', 'secondary')}</div>`;
    const blocks = PROFILE_BLOCKS.map(([letter, title, items]) => `<h3 class="section-title">${letter}｜${h(title)}</h3><dl class="char-fields">${items.map(([key, label]) =>
      `<dt>${h(label)}</dt><dd>${profile && profile.fields[key] ? h(profile.fields[key]) : '<span class="muted">尚未填寫</span>'}</dd>`).join('')}</dl>`).join('');
    return `<p class="small muted">${meta}　每次保存都會新增一個版本，舊版本保留不刪除。</p>${actions}
      ${blocks}${archived ? c.empty('已封存的人物不能修改設定；恢復後即可編輯。') : ''}`;
  }

  // ---------------- 關係分頁（P4）----------------

  const statusAttrs = (x, status) => `data-connection="${h(x.id)}" data-revision="${x.revision}" data-status="${status}"`;

  function relationCard(data, x) {
    const archived = x.status === 'archived';
    const locked = data.person.status === 'archived' || x.person.status === 'archived'; // 任一端人物已封存：這段關係只能查看
    const chips = x.relation_types.map(type => `<span class="tag">${h(kindLabel(type.kind))}</span>`).join('');
    const sources = x.sources.experiences, peopleSources = x.sources.person_experiences || [];
    const sourceCount = [sources.length ? `${sources.length} 筆我的紀錄` : '', peopleSources.length ? `${peopleSources.length} 筆人物經歷` : ''].filter(Boolean).join('、');
    const actions = locked ? '<p class="small muted">其中一位人物已封存，恢復人物後才能調整這段關係。</p>'
      : archived ? `<div class="button-row">${c.button('persons-relation-status', '恢復', 'secondary', statusAttrs(x, 'confirmed'))}</div>`
        : `<div class="button-row">${c.button('persons-relation-edit', '編輯', 'text-button', `data-connection="${h(x.id)}"`)}${c.button('persons-relation-status', '封存', 'text-button', statusAttrs(x, 'archived'))}</div>`;
    return `<article class="card stack">
      <div><a href="#persons/${encodeId(x.person.id)}"><strong>${h(x.person.name)}</strong></a>
        <span class="small muted">${h([typeLabel(x.person), x.person.status === 'archived' ? '人物已封存' : '', archived ? '關係已封存' : ''].filter(Boolean).join(' · '))}</span></div>
      ${chips ? `<p class="char-tags">${chips}</p>` : ''}
      ${x.text ? `<p>${h(x.text)}</p>` : '<p class="small muted">尚未填寫關係描述。</p>'}
      ${sourceCount ? `<details class="small"><summary>來源：${sourceCount}</summary><ul>${sources.map(s => `<li>${h(c.time(s.occurred_at))}　${h(s.summary)}</li>`).join('')}${
        peopleSources.map(s => `<li>人物經歷（${h(natureLabel(s.experience_type))}）　${h(s.title)}　${h(experienceDate(s))}</li>`).join('')}</ul></details>` : ''}
      ${actions}</article>`;
  }

  /** 關係分頁：使用中的關係可以編輯、封存；已封存的關係另外檢視、可以恢復。所有操作都在這裡完成，不需要回舊的關係頁。 */
  function relations(data, params) {
    const p = data.person, id = encodeId(p.id), showArchived = params?.get('archived') === '1';
    const active = data.connections.filter(x => x.status !== 'archived'), archived = data.connections.filter(x => x.status === 'archived');
    const shown = showArchived ? archived : active;
    const add = showArchived || p.status === 'archived' ? '' : c.button('persons-relation-new', '＋ 新增關係', 'primary', `data-person-ref="${h(p.id)}"`);
    const toggle = showArchived ? c.link(`persons/${id}?tab=relations`, `返回使用中的關係（${active.length}）`, 'text-button')
      : archived.length ? c.link(`persons/${id}?tab=relations&archived=1`, `查看已封存的關係（${archived.length}）`, 'text-button') : '';
    return `<div class="inline-heading"><h2 class="section-title">${showArchived ? '已封存的關係' : '人物關係'}（${shown.length}）</h2>${add}</div>
      ${p.status === 'archived' ? '<p class="small muted">這位人物已封存：關係只能查看，恢復人物後才能新增或調整。</p>' : ''}
      ${shown.length ? `<div class="stack">${shown.map(x => relationCard(data, x)).join('')}</div>`
        : c.empty(showArchived ? '沒有已封存的關係。' : '還沒有關係。關係不會因為共同經歷自動建立。')}
      ${toggle ? `<p class="space-top">${toggle}</p>` : ''}`;
  }

  // ---------------- 新增／編輯關係視窗（P4）----------------

  function personLines(o) { // 同名人物靠類型與簡介分辨
    return `<strong>${h(o.name)}</strong><span class="small muted person-card-line">${h(typeLabel(o))}</span>${o.description ? `<span class="small person-card-line">${h(clip(o.description, 60))}</span>` : ''}`;
  }

  function relationResultsHtml() {
    const r = relation;
    if (!r.results.length) return '<p class="small muted">找不到符合的人物。</p>';
    return r.results.map(o => {
      const existing = r.connections.find(x => x.person.id === o.id); // 已有關係的人物：選取後改為編輯或恢復，不會另外建立
      const mark = existing ? `<span class="small person-card-line">${existing.status === 'archived' ? '已有關係（已封存）' : '已有關係，選取後改為編輯'}</span>` : '';
      return `<button type="button" class="card person-card" data-action="persons-relation-pick" data-person-ref="${h(o.id)}"><span>${personLines(o)}${mark}</span></button>`;
    }).join('') + (r.more ? '<p class="small muted">還有更多人物，請輸入關鍵字縮小範圍。</p>' : '');
  }

  /** 視窗內容完全由 relation 狀態產生；重新繪製前先用 syncRelationDraft 收回使用者已輸入的內容。 */
  function relationDialogHtml() {
    const r = relation, title = r.mode === 'edit' ? '編輯人物關係' : '新增人物關係';
    const self = `<div class="field"><span class="small muted">目前人物</span><p><strong>${h(r.person.name)}</strong> <span class="small muted">${h(typeLabel(r.person))}</span></p></div>`;
    const other = r.other
      ? `<div class="field"><span class="small muted">另一位人物</span><div class="card person-card"><span>${personLines(r.other)}</span></div>
          ${r.mode === 'edit' ? '' : c.button('persons-relation-clear', '更換人物', 'text-button')}</div>`
      : `<div class="field"><label for="persons-relation-q">另一位人物</label>
          <input id="persons-relation-q" type="search" autocomplete="off" maxlength="200" placeholder="搜尋人物名稱、別名或標籤" value="${h(r.q)}">
          <div id="persons-relation-results" class="stack space-top">${relationResultsHtml()}</div>
          <p class="small muted">同名人物請看類型與簡介分辨。找不到的話，請先到人物列表新增這位人物。</p></div>`;
    if (r.mode === 'archived') { // 已封存的關係：只提供恢復，不能在這裡覆蓋
      return `<h2 id="account-heading">${title}</h2><div class="stack">${self}${other}
        <p class="callout">此關係已封存。恢復後才能繼續編輯。</p>
        <div class="button-row">${c.button('close-account', '取消', 'secondary')}${c.button('persons-relation-status', '恢復這段關係', 'primary', statusAttrs(r.connection, 'confirmed'))}</div></div>`;
    }
    const kinds = RELATION_KINDS.map(([kind, label]) => `<label class="check-line"><input type="checkbox" name="relation_kind" value="${kind}"${r.kinds.includes(kind) ? ' checked' : ''}> ${h(label)}</label>`).join('');
    const recordSources = r.eligible && r.eligible.length ? r.eligible.map(s => `<label class="check-line"><input type="checkbox" name="relation_source" value="${h(s.id)}"${r.checked.includes(s.id) ? ' checked' : ''}> ${h(c.time(s.occurred_at))}　${h(s.summary)}</label>`).join('')
      : '<p class="small muted">沒有與這兩位人物有關的已確認紀錄。</p>';
    const peopleSources = r.eligiblePeople && r.eligiblePeople.length ? r.eligiblePeople.map(s => `<label class="check-line"><input type="checkbox" name="relation_person_source" value="${h(s.id)}"${r.checkedPeople.includes(s.id) ? ' checked' : ''}> <span class="tag">${h(natureLabel(s.experience_type))}</span> ${h(s.title)}　${h(experienceDate(s))}</label>`).join('')
      : '<p class="small muted">沒有與這兩位人物有關的人物經歷。</p>';
    const sources = !r.other ? '<p class="small muted">選擇另一位人物後，會列出與這兩位人物有關的我的紀錄與人物經歷。</p>'
      : r.eligible === null ? '<p class="small muted">正在讀取可引用的紀錄…</p>'
        : `<p class="small muted">我的紀錄</p>${recordSources}<p class="small muted">人物經歷</p>${peopleSources}<p class="small muted">來源可以留空。</p>`;
    return `<h2 id="account-heading">${title}</h2>
      <form id="persons-relation-form" class="stack">
        <p class="callout small">${RELATION_HINT}</p>
        ${r.notice ? `<p class="callout small">${h(r.notice)}</p>` : ''}
        ${self}${other}
        <fieldset class="field"><legend>關係類型（選填，可複選，最多 ${MAX_RELATION_KINDS} 種）</legend><div class="char-checks">${kinds}</div></fieldset>
        <div class="field"><label for="persons-relation-description">關係描述</label>
          <textarea id="persons-relation-description" name="description" maxlength="2000" rows="4" placeholder="例如：兩人共同平定江東，建立長期合作及信任關係。">${h(r.description)}</textarea></div>
        <fieldset class="field"><legend>關係來源（選填）：能說明這段關係的我的紀錄與人物經歷</legend>
          <div id="persons-relation-sources" class="stack"${r.other && r.eligible !== null ? ' data-ready="1"' : ''}>${sources}</div></fieldset>
        <div class="button-row">${c.button('close-account', '取消', 'secondary')}<button type="submit" class="primary">儲存關係</button></div>
      </form>`;
  }

  function syncRelationDraft() { // 重新繪製視窗前，把使用者已勾選與輸入的內容收回狀態（Node 測試沒有 DOM，直接略過）
    if (typeof document === 'undefined' || !relation) return;
    const form = document.getElementById('persons-relation-form');
    if (!form) return;
    relation.kinds = [...form.querySelectorAll('input[name=relation_kind]:checked')].map(input => input.value);
    relation.description = form.querySelector('#persons-relation-description').value;
    // 來源清單已經畫在畫面上才讀取勾選狀態；還在「讀取中」時畫面上沒有勾選框，必須保留狀態裡原本的來源。
    if (form.querySelector('#persons-relation-sources[data-ready]')) {
      relation.checked = [...form.querySelectorAll('input[name=relation_source]:checked')].map(input => input.value);
      relation.checkedPeople = [...form.querySelectorAll('input[name=relation_person_source]:checked')].map(input => input.value);
    }
    const search = form.querySelector('#persons-relation-q');
    if (search) relation.q = search.value;
  }

  async function searchPeople(q) { // 只找使用中的人物；排除目前人物。較慢回來的舊查詢結果不採用
    const sequence = ++searchSequence, r = relation;
    const data = await c.api('/persons?' + new URLSearchParams({q, status: 'active', sort: 'name', limit: '20'}).toString());
    if (sequence !== searchSequence || relation !== r) return false;
    Object.assign(r, {q, results: data.items.filter(o => o.id !== r.person.id), more: data.total > data.items.length});
    return true;
  }

  function showRelation() {
    c.dialog(relationDialogHtml());
    if (typeof document === 'undefined') return;
    const box = document.getElementById('persons-relation-q');
    if (!box) return;
    const run = async () => {
      try {
        if (await searchPeople(box.value.trim())) { const list = document.getElementById('persons-relation-results'); if (list) list.innerHTML = relationResultsHtml(); }
      } catch (error) { const place = document.getElementById('dialog-error'); if (place) place.textContent = error.message; }
    };
    box.addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(run, 250); }); // 邊打邊找，只更新結果清單，不重畫整個視窗
    box.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); clearTimeout(searchTimer); run(); } }); // Enter 是搜尋，不是送出表單
    box.focus();
  }

  async function loadEligibleSources() { // 可引用的我的紀錄（與兩端至少一人有關）；編輯時既有來源排在最前面並維持原順序
    const r = relation, otherId = r.other.id;
    const data = await c.api(`/persons/${encodeId(r.person.id)}/connection-sources?other_person_id=${encodeURIComponent(otherId)}`);
    if (relation !== r || !r.other || r.other.id !== otherId) return; // 期間已換人
    if (typeof document !== 'undefined' && !document.getElementById('persons-relation-form')) { relation = null; return; } // 視窗已關閉：不重新打開
    syncRelationDraft(); // 先收回使用者已輸入的內容，再放入來源清單（順序相反會把原本勾選的來源清掉）
    const existing = r.connection ? r.connection.sources.experiences : [];
    r.eligible = [...existing, ...data.items.filter(item => !existing.some(s => s.id === item.id))];
    // 人物經歷來源（同一規則）：既有來源排在最前面並維持原順序
    const existingPeople = r.connection ? (r.connection.sources.person_experiences || []) : [], offered = data.person_experiences ? data.person_experiences.items : [];
    r.eligiblePeople = [...existingPeople, ...offered.filter(item => !existingPeople.some(s => s.id === item.id))];
    showRelation();
  }

  async function openNewRelation(personId) {
    if (!viewing || viewing.person.id !== personId) viewing = await c.api('/persons/' + encodeId(personId));
    relation = {person: viewing.person, connections: viewing.connections, mode: 'create', connection: null, other: null, kinds: [], description: '',
      checked: [], eligible: null, checkedPeople: [], eligiblePeople: null, results: [], more: false, q: '', notice: ''};
    await searchPeople('');
    showRelation();
  }

  async function startRelationEdit(connection, notice) { // 載入原內容；沒有描述的舊關係帶入舊 label，避免儲存後遺失
    const base = relation || {person: viewing.person, connections: viewing.connections, results: [], more: false, q: ''};
    relation = {...base, mode: 'edit', connection, other: connection.person, kinds: connection.relation_types.map(type => type.kind),
      description: connection.text || '', checked: [...connection.source_experience_ids], eligible: null,
      checkedPeople: [...(connection.source_person_experience_ids || [])], eligiblePeople: null, notice};
    relation.original = {kinds: [...relation.kinds], description: relation.description, sources: [...relation.checked], peopleSources: [...relation.checkedPeople]};
    showRelation();
    await loadEligibleSources();
  }

  async function pickRelationPerson(personId) {
    syncRelationDraft();
    const other = relation.results.find(o => o.id === personId);
    if (!other) return;
    const existing = relation.connections.find(x => x.person.id === personId);
    if (existing && existing.status === 'archived') { Object.assign(relation, {mode: 'archived', connection: existing, other}); showRelation(); return; }
    if (existing) { await startRelationEdit(existing, '你和這位人物已經有關係，已載入原內容；儲存後會更新原本的關係，不會另外建立。'); return; }
    Object.assign(relation, {mode: 'create', connection: null, other, eligible: null, checked: [], eligiblePeople: null, checkedPeople: []});
    showRelation();
    await loadEligibleSources();
  }

  async function finishRelation(message) {
    relation = null;
    c.closeDialog();
    c.toast(message);
    await c.render();
  }

  async function setRelationStatus(target) { // 封存（archived）或恢復（confirmed）：走既有 PATCH 與 expected_revision，不刪除
    const id = target.dataset.connection, body = {expected_revision: Number(target.dataset.revision), confirmation_status: target.dataset.status};
    await c.api(`/connections/${encodeId(id)}`, {method: 'PATCH', body: {...body, request_id: c.requestId('persons-relation-status:' + id, body)}});
    await finishRelation(body.confirmation_status === 'archived' ? '關係已封存，資料都保留。' : '關係已恢復。');
  }

  async function saveRelation() {
    syncRelationDraft();
    const r = relation;
    if (!r || !r.other) throw new Error('請先選擇另一位人物。');
    const kinds = r.kinds, description = r.description.trim(), sources = r.checked, peopleSources = r.checkedPeople || [];
    if (kinds.length > MAX_RELATION_KINDS) throw new Error(`關係類型最多選 ${MAX_RELATION_KINDS} 種。`);
    if (sources.length > MAX_RELATION_SOURCES || peopleSources.length > MAX_RELATION_SOURCES) throw new Error(`每種關係來源最多選 ${MAX_RELATION_SOURCES} 筆。`);
    if (!kinds.length && !description) throw new Error('請至少選擇一種關係類型或填寫關係描述。');
    if (r.mode === 'edit') { // 只送出有變更的欄位；revision 防止覆蓋他處較新的修改
      const body = {expected_revision: r.connection.revision};
      const sameKinds = kinds.length === r.original.kinds.length && kinds.every(kind => r.original.kinds.includes(kind));
      if (!sameKinds) body.relation_types = kinds.map(kind => ({kind}));
      if (description !== r.original.description.trim()) body.description = description;
      if (!same(sources, r.original.sources)) body.source_experience_ids = sources;
      if (!same(peopleSources, r.original.peopleSources || [])) body.source_person_experience_ids = peopleSources; // 只改這一種時，另一種來源維持原樣
      if (Object.keys(body).length === 1) { await finishRelation('沒有變更。'); return; }
      await c.api(`/connections/${encodeId(r.connection.id)}`, {method: 'PATCH', body: {...body, request_id: c.requestId('persons-relation-edit:' + r.connection.id, body)}});
      await finishRelation('已儲存關係。');
      return;
    }
    const body = {other_person_id: r.other.id, relation_types: kinds.map(kind => ({kind})), description, source_experience_ids: sources};
    if (peopleSources.length) body.source_person_experience_ids = peopleSources; // 有引用人物經歷才送出
    const scope = 'persons-relation-create:' + r.person.id;
    try {
      await c.api(`/people/${encodeId(r.person.id)}/connections`, {method: 'POST', body: {...body, request_id: c.requestId(scope, body)}});
    } catch (error) {
      if (error.code !== 'connection_exists') throw error;
      // 這一對人物在別處已經建立關係：重新讀取既有關係，改為編輯（或恢復），不覆蓋原本的資料
      viewing = await c.api('/persons/' + encodeId(r.person.id));
      const existing = viewing.connections.find(x => x.person.id === r.other.id);
      if (!existing) throw error;
      relation.connections = viewing.connections;
      if (existing.status === 'archived') { Object.assign(relation, {mode: 'archived', connection: existing}); showRelation(); return; }
      await startRelationEdit(existing, '這兩位人物已經有關係，已載入原內容；請確認後再儲存，不會覆蓋原本的資料。');
      return;
    }
    c.state.requests.delete(scope);
    await finishRelation('已建立關係。');
  }

  // ---------------- 經歷（我的紀錄／人物經歷）：人物頁的經歷分頁、紀錄頁的頁籤、人物經歷對話框 ----------------
  // 分類原則：我的紀錄＝你本人實際參與的生活紀錄（走紀錄的核對流程，計積分與目標）；人物經歷＝以人物為主體的經歷（真實、歷史或虛構，
  // 直接儲存，不計分）；作品內的劇情屬於作品，不在這裡。
  // 人物經歷從人物頁（自動帶入主體）或紀錄頁（先選主體）進入，共用同一個對話框與同一套 API；新增、查看、編輯、封存都不離開原本的頁面。

  const NATURES = [['real', '真實'], ['historical', '歷史'], ['fictional', '虛構']];
  const MAX_EXPERIENCE_PEOPLE = 50;
  const natureLabel = key => (NATURES.find(([k]) => k === key) || [key, key])[1];
  const summaryOf = p => ({id: p.id, name: p.name, person_type: p.person_type, person_subtype: p.person_subtype, status: p.status, description: p.description});
  const natureFor = p => (p.person_subtype === 'historical' ? 'historical' : p.person_type === 'fictional' ? 'fictional' : 'real'); // 性質預設值跟著人物類型，可以改
  // 人物頁的「記錄我和他的經歷」只提供給使用中的真實人物（不含歷史人物）：我的紀錄是你本人實際參與的事。
  const canRecordWith = p => Boolean(p) && p.status === 'active' && p.person_type === 'real' && !p.person_subtype;
  const experienceTitle = x => x.title || clip(x.content, 40); // 沒有標題時顯示內容開頭
  const experienceLocked = x => x.status === 'archived' || !x.subject || x.subject.status === 'archived'; // 已封存的經歷、或主體人物已封存：只能查看
  const experienceAttrs = (x, status) => `data-exp="${h(x.id)}" data-revision="${x.revision}" data-status="${status}"`;
  const experienceLink = o => `<a href="#persons/${encodeId(o.id)}?tab=experiences">${h(o.name)}</a>`; // 點姓名進入該人物的經歷頁籤
  let experienceIndex = new Map(); // 目前畫面上列出的人物經歷（人物頁或紀錄頁）：開啟對話框時從這裡取資料

  /** 依使用者填的精度顯示發生時間，不補造日期；都不知道時顯示「時間不詳」。 */
  function experienceDate(x) {
    const parts = x.occurred_on ? x.occurred_on.split('-').map(Number) : [];
    const date = parts.length === 3 ? `${parts[0]} 年 ${parts[1]} 月 ${parts[2]} 日` : parts.length === 2 ? `${parts[0]} 年 ${parts[1]} 月` : parts.length === 1 ? `${parts[0]} 年` : '';
    return [date, x.occurred_label].filter(Boolean).join(' · ') || '時間不詳';
  }

  /** 合併排序用的時間值：只知道年或年月時取該期間的第一天；不知道時間的排在最後（不當成今天）。 */
  function experienceTime(x) {
    if (!x.occurred_on) return -Infinity;
    const [year, month = 1, day = 1] = x.occurred_on.split('-').map(Number);
    const date = new Date(Date.UTC(2000, month - 1, day));
    date.setUTCFullYear(year); // 西元 100 年以前不能直接交給 Date.UTC
    return date.getTime();
  }

  /** 人物經歷卡片。person＝人物頁上的那位人物（列出其他人物並標示主體／參與）；person 為 null＝紀錄頁（列出主體與參與人物）。 */
  function experienceCard(person, x, options = {}) {
    let who, tags;
    if (person) {
      const others = [x.subject, ...x.participants].filter(o => o && o.id !== person.id); // 這筆經歷裡的其他人物（不含目前這位）；多人時只列前 3 位
      who = others.length ? `與 ${others.slice(0, 3).map(experienceLink).join('、')}${others.length > 3 ? ` 等 ${others.length} 人` : ''}` : '';
      tags = [natureLabel(x.experience_type), x.role === 'subject' ? '主體' : '參與'];
    } else {
      const joined = x.participants.length ? `　參與：${x.participants.slice(0, 3).map(experienceLink).join('、')}${x.participants.length > 3 ? ` 等 ${x.participants.length} 人` : ''}` : '';
      who = `主體：${x.subject ? experienceLink(x.subject) : '（主體人物不存在）'}${joined}`;
      tags = [...(options.typeTag ? ['人物經歷'] : []), natureLabel(x.experience_type)];
    }
    const archived = x.status === 'archived';
    const action = x.subject && x.subject.status === 'archived' ? '<span class="small muted">主體人物已封存，只能查看</span>'
      : c.button('persons-exp-status', archived ? '恢復' : '封存', 'text-button', experienceAttrs(x, archived ? 'active' : 'archived'));
    return `<article class="card person-exp-card" data-exp-card="${h(x.id)}"><h3>${h(experienceTitle(x))}</h3>
      <p class="char-tags">${tags.map(tag => `<span class="tag">${h(tag)}</span>`).join('')}</p><p class="small muted">${h(experienceDate(x))}${who ? ` · ${who}` : ''}</p>
      <p class="person-exp-content">${h(clip(x.content, 160))}</p>
      <div class="button-row">${c.button('persons-exp-open', experienceLocked(x) ? '查看' : '查看／編輯', 'text-button', `data-exp="${h(x.id)}"`)}${action}</div></article>`;
  }

  function experiences(data, params) {
    const p = data.person, lists = data.lists, id = encodeId(p.id), archivedView = Boolean(params && params.get('archived') === '1');
    const here = `persons/${id}?tab=experiences`;
    experienceIndex = new Map(lists.person_experiences.items.map(x => [x.id, x]));
    const recordNote = p.status === 'archived' ? '這位人物已封存，不能新增紀錄。' : canRecordWith(p) ? '' : '以這位人物為主體的經歷，請記在下方的人物經歷。';
    const records = lists.records.items.map(r => `<div class="list-item"><div class="item-main"><h3>${h(r.summary)}</h3><p class="small muted">${h(c.time(r.occurred_at))}</p></div></div>`).join('');
    const recordBlock = `<section class="person-exp-block" data-block="records"><div class="section-title"><h2>我的紀錄（${lists.records.total}）</h2>
        ${canRecordWith(p) ? c.link(`record?person=${id}&return=${encodeURIComponent(here)}`, '記錄我和他的經歷', 'secondary') : ''}</div>
      <p class="small muted">你本人實際參與的事，沿用紀錄的核對流程，會計入積分與目標。${recordNote}</p>
      ${records ? `<div class="card">${records}</div>` : '<p class="small muted">還沒有你和這位人物的紀錄。</p>'}</section>`;
    const px = lists.person_experiences, cards = px.items.map(x => experienceCard(p, x)).join('');
    const toggle = archivedView ? c.link(here, '返回使用中的人物經歷', 'text-button')
      : px.archived_total ? c.link(`${here}&archived=1`, `查看已封存的人物經歷（${px.archived_total}）`, 'text-button') : '';
    const peopleBlock = `<section class="person-exp-block" data-block="person-experiences"><div class="section-title"><h2>${archivedView ? '已封存的人物經歷' : '人物經歷'}（${archivedView ? px.archived_total : px.total}）</h2>
        ${p.status === 'active' && !archivedView ? c.button('persons-exp-new', '＋ 新增人物經歷', 'primary', `data-person-ref="${h(p.id)}"`) : ''}</div>
      <p class="small muted">以這位人物為主體或參與的經歷，你不必在場；不計入積分、目標與互動統計。${p.status === 'archived' ? '這位人物已封存，不能新增。' : ''}</p>
      ${cards ? `<div class="stack">${cards}</div>` : `<p class="small muted">${archivedView ? '沒有已封存的人物經歷。' : '還沒有人物經歷。'}</p>`}${toggle}</section>`;
    return recordBlock + peopleBlock;
  }

  // ---- 紀錄頁（左側「紀錄」）：我的紀錄／人物經歷／全部 ----

  const RECORD_VIEWS = [['mine', '我的紀錄', 'history'], ['people', '人物經歷', 'history?view=people'], ['all', '全部', 'history?view=all']];

  function recordTabs(view) {
    return `<nav class="person-tabs record-tabs" role="tablist" aria-label="紀錄類型">${RECORD_VIEWS.map(([key, label, route]) =>
      `<a role="tab" aria-selected="${key === view}" href="#${route}">${label}</a>`).join('')}</nav>`;
  }

  /**
   * 紀錄頁的「人物經歷」與「全部」頁籤（「我的紀錄」頁籤由主程式沿用原本的畫面）。
   * @param view 'people'｜'all'  @param tabs 頁籤列的 HTML  @param mine {records: 我的紀錄清單, recordCard(e, typeTag): 主程式的紀錄卡片}
   */
  async function recordsPage(view, params, tabs, mine) {
    if (!enabled()) return unavailable();
    const ticket = c.state.renderGeneration, archivedView = view === 'people' && params.get('archived') === '1';
    const data = await c.api('/person-experiences' + (archivedView ? '?archived=true' : ''));
    if (!fresh(ticket)) return '';
    experienceIndex = new Map(data.items.map(x => [x.id, x]));
    if (view === 'people') {
      const here = 'history?view=people';
      const toggle = archivedView ? c.link(here, '返回使用中的人物經歷', 'text-button')
        : data.archived_total ? c.link(`${here}&archived=1`, `查看已封存的人物經歷（${data.archived_total}）`, 'text-button') : '';
      const cards = data.items.map(x => experienceCard(null, x)).join('');
      return `${c.heading('人物經歷', '以人物為主體的經歷，你不必在場；不計入積分、目標與互動統計。', archivedView ? '' : c.button('persons-exp-new', '＋ 新增人物經歷', 'primary'))}${tabs}
        <section data-block="person-experiences"><h2 class="section-title">${archivedView ? '已封存的人物經歷' : '人物經歷'}（${archivedView ? data.archived_total : data.total}）</h2>
        ${cards ? `<div class="stack">${cards}</div>` : `<div class="card">${c.empty(archivedView ? '沒有已封存的人物經歷。' : '還沒有人物經歷。')}</div>`}${toggle}</section>`;
    }
    // 全部：兩種紀錄合併、由新到舊，每筆標示類型；各自保留原本的操作（我的紀錄不能在這裡改成人物經歷，反之亦然）
    const merged = [...mine.records.map(e => ({at: Date.parse(e.occurred_at), html: mine.recordCard(e, true)})),
      ...data.items.map(x => ({at: experienceTime(x), html: experienceCard(null, x, {typeTag: true})}))]
      .map(item => ({...item, at: Number.isFinite(item.at) ? item.at : -Infinity}))
      .sort((a, b) => (a.at === b.at ? 0 : a.at > b.at ? -1 : 1));
    return `${c.heading('全部紀錄', '我的紀錄與人物經歷合併顯示；每筆保留各自的操作方式。',
      `<div class="button-row">${c.link('record', '＋ 新的經歷', 'primary')}${c.button('persons-exp-new', '＋ 新增人物經歷', 'secondary')}</div>`)}${tabs}
      <section data-block="all-records"><h2 class="section-title">全部（${merged.length}）</h2>
      ${merged.length ? `<div class="stack">${merged.map(item => item.html).join('')}</div>` : `<div class="card">${c.empty('還沒有任何紀錄。')}</div>`}</section>`;
  }

  // ---- 人物經歷對話框 ----

  function experienceChips() { // 已選的其他參與人物；查看模式不能移除
    const e = experience;
    if (!e) return '';
    const chips = e.participants.map(o => `<span class="tag person-exp-chip">${h(o.name)} <span class="small muted">${h(typeLabel(o))}${o.status === 'archived' ? '・已封存' : ''}</span>${e.mode === 'view' ? ''
      : `<button type="button" class="text-button" data-action="persons-exp-unpick" data-person-ref="${h(o.id)}" aria-label="移除 ${h(o.name)}">×</button>`}</span>`).join('');
    return `${chips}<span class="small muted">已選 ${e.participants.length}／${MAX_EXPERIENCE_PEOPLE}</span>`;
  }

  function experiencePeopleResults(list, action, more) { // 搜尋結果的人物按鈕：不列主體與已選的人物；同名靠類型與簡介分辨
    const e = experience;
    const taken = new Set([...(e.subject ? [e.subject.id] : []), ...e.participants.map(o => o.id)]);
    const found = list.filter(o => !taken.has(o.id));
    if (!found.length) return '<p class="small muted">找不到可選的人物。</p>';
    return found.map(o => `<button type="button" class="card person-card" data-action="${action}" data-person-ref="${h(o.id)}"><span>${personLines(o)}</span></button>`).join('')
      + (more ? '<p class="small muted">還有更多人物，請輸入關鍵字縮小範圍。</p>' : '');
  }

  function experienceResults() { // 參與人物的搜尋結果；還沒輸入關鍵字時不列出任何人物
    const e = experience;
    return !e || e.results === null ? '' : experiencePeopleResults(e.results, 'persons-exp-pick', e.more);
  }

  /** 搜尋使用中的人物（kind：'results' 參與人物、'subjectResults' 主體）；回傳結果清單的 HTML。較慢回來的舊查詢結果不採用（回傳 null）。 */
  async function searchExperiencePeople(kind, q) {
    const e = experience, sequence = ++experienceSearchSequence;
    if (!e) return '';
    if (!q) { e[kind] = null; return ''; }
    const data = await c.api('/persons?' + new URLSearchParams({q, status: 'active', sort: 'name', limit: '20'}).toString());
    if (sequence !== experienceSearchSequence || experience !== e) return null;
    e[kind] = data.items;
    e.more = data.total > data.items.length;
    return kind === 'results' ? experienceResults() : experiencePeopleResults(e.subjectResults, 'persons-exp-subject-pick', e.more);
  }
  const experienceSearch = q => searchExperiencePeople('results', q);
  const experienceSubjectSearch = q => searchExperiencePeople('subjectResults', q);

  /** 把搜尋框接上「邊打邊找」與「Enter 選第一位」；只更新結果清單，不重畫整個視窗（已填的內容不受影響）。 */
  function wireExperienceSearch(boxId, listId, search, pickAction) {
    if (typeof document === 'undefined') return;
    const box = document.getElementById(boxId);
    if (!box) return;
    let timer = null;
    const run = async () => {
      const q = box.value.trim();
      try {
        const html = await search(q);
        const list = document.getElementById(listId);
        if (html !== null && list) { list.innerHTML = html; box.dataset.searched = q; }
      } catch (error) { const place = document.getElementById('dialog-error'); if (place) place.textContent = error.message; }
    };
    box.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(run, 250); });
    box.addEventListener('keydown', event => {
      if (event.key !== 'Enter') return;
      event.preventDefault(); // Enter 是選人物，不是送出表單
      const first = document.querySelector(`#${listId} button[data-action="${pickAction}"]`);
      if (first && box.dataset.searched === box.value.trim()) first.click(); // 結果已是目前的關鍵字：選第一位
      else { clearTimeout(timer); run(); }
    });
  }

  function refreshExperiencePeople(clearBox) { // 只更新參與人物區塊
    if (typeof document === 'undefined') return;
    const chips = document.getElementById('persons-exp-chips'), list = document.getElementById('persons-exp-results'), box = document.getElementById('persons-exp-q');
    if (chips) chips.innerHTML = experienceChips();
    if (list) list.innerHTML = experienceResults();
    if (box && clearBox) { box.value = ''; box.dataset.searched = ''; box.focus(); }
  }

  function pickExperiencePerson(personId) {
    const e = experience;
    if (!e || e.mode === 'view') return;
    const person = (e.results || []).find(o => o.id === personId);
    if (!person || e.participants.some(o => o.id === personId)) return;
    if (e.participants.length >= MAX_EXPERIENCE_PEOPLE) throw new Error(`其他參與人物最多 ${MAX_EXPERIENCE_PEOPLE} 位。`);
    e.participants.push(summaryOf(person));
    e.results = null; // 加入後清空搜尋，可以直接輸入下一位
    refreshExperiencePeople(true);
  }

  function unpickExperiencePerson(personId) {
    const e = experience;
    if (!e || e.mode === 'view') return;
    e.participants = e.participants.filter(o => o.id !== personId);
    refreshExperiencePeople(false);
  }

  /** 經歷主體：已決定時顯示人物；從紀錄頁新增時先搜尋選擇，選好後可以更換。從人物頁新增或編輯既有經歷時主體固定。 */
  function experienceSubjectHtml() {
    const e = experience;
    if (!e) return '';
    if (e.subject) return `<div class="card person-card"><span>${personLines(e.subject)}</span></div>${e.pickSubject ? c.button('persons-exp-subject-clear', '更換主體', 'text-button') : ''}`;
    return `<input id="persons-exp-subject-q" type="search" autocomplete="off" maxlength="200" placeholder="輸入姓名、別名或標籤搜尋主體人物；按 Enter 選第一位" aria-label="搜尋經歷主體">
      <div id="persons-exp-subject-results" class="stack">${e.subjectResults === null ? '' : experiencePeopleResults(e.subjectResults, 'persons-exp-subject-pick', e.more)}</div>
      <p class="small muted">這筆經歷主要屬於誰。同名人物請看類型與簡介分辨。</p>`;
  }

  function refreshExperienceSubject() { // 只更新主體區塊；選好主體後，性質預設值跟著人物類型，參與人物的搜尋結果也排除主體
    if (typeof document === 'undefined') return;
    const place = document.getElementById('persons-exp-subject'), type = document.getElementById('persons-exp-type');
    if (place) place.innerHTML = experienceSubjectHtml();
    if (type && experience.mode === 'create') type.value = experience.values.type;
    wireExperienceSearch('persons-exp-subject-q', 'persons-exp-subject-results', experienceSubjectSearch, 'persons-exp-subject-pick');
    refreshExperiencePeople(false);
    const next = document.getElementById(experience.subject ? 'persons-exp-content' : 'persons-exp-subject-q');
    if (next) next.focus();
  }

  function pickExperienceSubject(personId) {
    const e = experience;
    if (!e || !e.pickSubject) return;
    const person = (e.subjectResults || []).find(o => o.id === personId);
    if (!person) return;
    e.subject = summaryOf(person);
    e.subjectResults = null;
    e.participants = e.participants.filter(o => o.id !== person.id); // 主體不必再列為參與人物
    e.values.type = natureFor(person);
    refreshExperienceSubject();
  }

  function clearExperienceSubject() {
    const e = experience;
    if (!e || !e.pickSubject) return;
    Object.assign(e, {subject: null, subjectResults: null});
    refreshExperienceSubject();
  }

  /** 視窗內容由 experience 狀態產生：create 新增、edit 編輯、view 只能查看（已封存的經歷或主體人物已封存）。 */
  function experienceDialogHtml() {
    const e = experience, v = e.values, view = e.mode === 'view', off = view ? ' disabled' : '';
    const title = e.mode === 'create' ? '新增人物經歷' : view ? '人物經歷' : '編輯人物經歷';
    const notice = !view ? `<p class="callout">以人物為主體的經歷，你不必在場；不計入積分、目標與互動統計。${canRecordWith(e.subject) ? '如果是你本人實際參與的事，請改用「記錄我和他的經歷」。' : ''}</p>`
      : e.item.status === 'archived' ? '<p class="callout" role="status">此經歷已封存，只能查看；恢復後才能修改。</p>' : '<p class="callout" role="status">主體人物已封存，這筆經歷只能查看。</p>';
    const people = `<div class="field">${view ? '<span class="small muted">其他參與人物</span>' : `<label for="persons-exp-q">其他參與人物（選填，最多 ${MAX_EXPERIENCE_PEOPLE} 位）</label>`}
        <div id="persons-exp-chips" class="person-exp-chips">${experienceChips()}</div>
        ${view ? '' : `<input id="persons-exp-q" type="search" autocomplete="off" maxlength="200" placeholder="輸入姓名、別名或標籤搜尋；按 Enter 加入第一位">
        <div id="persons-exp-results" class="stack">${experienceResults()}</div>
        <p class="small muted">可以連續加入多位；同名人物請看類型與簡介分辨。沒有其他參與人物可以不填。</p>`}</div>`;
    const dateInput = (id, label, value, max) => `<label class="small">${label} <input id="${id}" inputmode="numeric" maxlength="${max}" value="${h(value)}"${off}></label>`;
    const restore = view && e.item.status === 'archived' && e.subject && e.subject.status === 'active' ? c.button('persons-exp-status', '恢復這筆經歷', 'primary', experienceAttrs(e.item, 'active')) : '';
    const buttons = view ? `${c.button('close-account', '關閉', 'secondary')}${restore}`
      : `${c.button('close-account', '取消', 'secondary')}<button type="submit" class="primary">儲存經歷</button>${e.mode === 'edit' ? c.button('persons-exp-status', '封存', 'text-button', experienceAttrs(e.item, 'archived')) : ''}`;
    return `<h2 id="account-heading">${title}</h2><form id="persons-exp-form" class="stack">${notice}
      ${field('persons-exp-title', '經歷標題（選填）', `<input id="persons-exp-title" maxlength="200" placeholder="不填會顯示內容開頭" value="${h(v.title)}"${off}>`)}
      <div class="field"><span class="small muted">經歷主體</span><div id="persons-exp-subject" class="stack">${experienceSubjectHtml()}</div></div>
      ${people}
      ${field('persons-exp-content', '經歷內容', `<textarea id="persons-exp-content" maxlength="20000" rows="6" required${off}>${h(v.content)}</textarea>`)}
      ${field('persons-exp-type', '經歷性質', `<select id="persons-exp-type"${e.mode === 'create' ? '' : ' disabled'}>${options(NATURES, v.type)}</select>`,
        e.mode === 'create' ? '依人物類型帶入預設值，可以改；建立後不能更改，儲存前請確認。' : '建立後不能更改；選錯請封存後重新建立。')}
      <div class="field"><span class="small muted">發生時間（選填）</span>
        <div class="button-row person-exp-date">${dateInput('persons-exp-year', '年', v.year, 4)}${dateInput('persons-exp-month', '月', v.month, 2)}${dateInput('persons-exp-day', '日', v.day, 2)}</div>
        <p class="small muted">只知道年份就只填年（西元）；都不知道就留空。</p></div>
      ${field('persons-exp-label', '時間描述（選填）', `<input id="persons-exp-label" maxlength="120" placeholder="例如：建安十三年冬" value="${h(v.label)}"${off}>`)}
      <div class="button-row">${buttons}</div></form>`;
  }

  function showExperience() {
    c.dialog(experienceDialogHtml());
    wireExperienceSearch('persons-exp-q', 'persons-exp-results', experienceSearch, 'persons-exp-pick');
    wireExperienceSearch('persons-exp-subject-q', 'persons-exp-subject-results', experienceSubjectSearch, 'persons-exp-subject-pick');
  }

  /** 新增人物經歷。從人物頁（personId＝這位人物）自動帶入主體；從紀錄頁（沒有 personId）先搜尋選擇主體。 */
  function openNewExperience(personId) {
    const p = personId && viewing && viewing.person.id === personId ? viewing.person : null;
    if (personId && !p) return;
    experience = {mode: 'create', item: null, subject: p ? summaryOf(p) : null, pickSubject: !p, subjectResults: null, participants: [], results: null, more: false,
      values: {title: '', content: '', type: p ? natureFor(p) : 'real', year: '', month: '', day: '', label: ''}};
    showExperience();
  }

  function openExperience(experienceId) {
    const x = experienceIndex.get(experienceId);
    if (!x) return;
    const [year = '', month = '', day = ''] = x.occurred_on ? x.occurred_on.split('-').map(part => String(Number(part))) : [];
    experience = {mode: experienceLocked(x) ? 'view' : 'edit', item: x, pickSubject: false, subjectResults: null,
      subject: x.subject || {id: '', name: '（主體人物不存在）', person_type: 'real', person_subtype: null, status: 'archived', description: ''},
      participants: x.participants.map(summaryOf), results: null, more: false,
      values: {title: x.title, content: x.content, type: x.experience_type, year, month, day, label: x.occurred_label}};
    showExperience();
  }

  /** 讀取表單並決定時間精度：填到哪裡，精度就到哪裡（只填年＝年、年月＝年月、年月日＝完整日期、都沒填＝不知道）。 */
  function experienceBody(form) {
    const read = selector => String((form.querySelector(selector) || {}).value || '').trim();
    const title = read('#persons-exp-title'), content = read('#persons-exp-content'), label = read('#persons-exp-label');
    const [year, month, day] = ['#persons-exp-year', '#persons-exp-month', '#persons-exp-day'].map(read);
    if (!content) throw new Error('請填寫經歷內容。');
    if ([year, month, day].some(part => part && !/^\d+$/.test(part))) throw new Error('發生時間請填數字（西元年）；其他紀年請寫在「時間描述」。');
    if (!year && (month || day)) throw new Error('請先填年份；不知道年份時可以只寫「時間描述」。');
    if (day && !month) throw new Error('填了日期時也要填月份。');
    const on = !year ? null : [year, month && month.padStart(2, '0'), day && day.padStart(2, '0')].filter(Boolean).join('-');
    return {title, content, experience_type: read('#persons-exp-type') || experience.values.type,
      occurred_precision: !year ? 'unknown' : day ? 'day' : month ? 'month' : 'year', occurred_on: on, occurred_label: label};
  }

  async function finishExperience(message) {
    const open = experience !== null;
    experience = null;
    if (open) c.closeDialog();
    c.toast(message);
    await c.render();
  }

  async function saveExperience(form) {
    const e = experience;
    if (!e || e.mode === 'view') return;
    if (!e.subject) throw new Error('請先選擇經歷主體。');
    const body = experienceBody(form), participantIds = e.participants.map(o => o.id);
    if (e.mode === 'create') {
      const payload = {subject_person_id: e.subject.id, participant_ids: participantIds, ...body};
      await c.api('/person-experiences', {method: 'POST', body: {...payload, request_id: c.requestId('persons-exp-create:' + e.subject.id, payload)}});
      c.state.requests.delete('persons-exp-create:' + e.subject.id); // 成功後換新代碼：下一筆內容相同的經歷是另一筆，不是重送
      await finishExperience('已新增人物經歷。');
      return;
    }
    const x = e.item, change = {expected_revision: x.revision}; // 只送出有變更的欄位；revision 防止覆蓋他處較新的修改
    const plain = on => (on ? on.split('-').map(Number).join('-') : null);
    if (body.title !== x.title) change.title = body.title;
    if (body.content !== x.content) change.content = body.content;
    if (body.occurred_label !== x.occurred_label) change.occurred_label = body.occurred_label;
    if (body.occurred_precision !== x.occurred_precision || plain(body.occurred_on) !== plain(x.occurred_on)) {
      change.occurred_precision = body.occurred_precision;
      if (body.occurred_on) change.occurred_on = body.occurred_on;
    }
    const original = x.participants.map(o => o.id);
    if (participantIds.length !== original.length || participantIds.some(id => !original.includes(id))) change.participant_ids = participantIds;
    if (Object.keys(change).length === 1) { experience = null; c.closeDialog(); c.toast('沒有變更。'); return; }
    await c.api('/person-experiences/' + encodeId(x.id), {method: 'PATCH', body: {...change, request_id: c.requestId('persons-exp-edit:' + x.id, change)}});
    await finishExperience('已更新人物經歷。');
  }

  async function setExperienceStatus(target) { // 封存（archived）或恢復（active）：不刪除任何資料
    const body = {expected_revision: Number(target.dataset.revision), status: target.dataset.status};
    await c.api('/person-experiences/' + encodeId(target.dataset.exp), {method: 'PATCH', body: {...body, request_id: c.requestId('persons-exp-status:' + target.dataset.exp, body)}});
    await finishExperience(body.status === 'archived' ? '人物經歷已封存，資料都保留。' : '人物經歷已恢復。');
  }

  /** 人物詳細頁：總覽、人物設定、經歷、關係；編輯人物與封存／恢復。params 是網址的查詢參數（關係分頁的 archived=1）。 */
  async function detail(id, tab, params) {
    if (!enabled()) return unavailable();
    const ticket = c.state.renderGeneration;
    const data = await c.api('/persons/' + encodeId(id));
    if (!fresh(ticket)) return '';
    viewing = data;
    const p = data.person, archived = p.status === 'archived';
    const tabs = [['overview', '總覽'], ['profile', '人物設定'], ['experiences', '經歷'], ['relations', '關係']];
    const current = tabs.some(([key]) => key === tab) ? tab : 'overview';
    const actions = [archived ? '' : c.link(`persons-edit/${encodeId(p.id)}`, '編輯人物', 'secondary'),
      c.button('persons-status', archived ? '恢復人物' : '封存', 'secondary', `data-id="${h(p.id)}" data-status="${archived ? 'active' : 'archived'}" data-revision="${p.revision}"`)];
    if (current === 'experiences') { // 經歷分頁的兩區內容另外讀取（archived=1 時列出已封存的人物經歷）
      data.lists = await c.api('/persons/' + encodeId(id) + '/experiences' + (params && params.get('archived') === '1' ? '?archived=true' : ''));
      if (!fresh(ticket)) return '';
    }
    const panel = {overview, profile: profileTab, relations, experiences}[current](data, params);
    const subtitle = [typeLabel(p), categoryLabel(p.category), archived ? '已封存' : '', clip(p.description, 60)].filter(Boolean).join(' · ');
    return `${c.link(backToList(), '← 返回人物列表', 'text-button')}
      ${c.heading(p.name, subtitle, `<div class="button-row">${actions.join('')}</div>`)}
      ${p.tags.length ? `<p class="char-tags">${p.tags.map(tag => `<span class="tag">${h(tag)}</span>`).join('')}</p>` : ''}
      <nav class="person-tabs four" role="tablist" aria-label="人物資料分頁">${tabs.map(([key, title]) => `<a role="tab" aria-selected="${current === key}" href="#persons/${encodeId(p.id)}?tab=${key}">${title}</a>`).join('')}</nav>
      <section class="card person-tab-panel" data-person-view="${h(p.id)}" data-tab="${current}">${panel}</section>`;
  }

  // ---------------- 送出與點擊 ----------------

  async function submit(form) {
    if (form.id === 'persons-filter-form') {
      const data = new FormData(form);
      const query = new URLSearchParams([...data.entries()].filter(([key, value]) => value && !(key === 'status' && value === 'active') && !(key === 'sort' && value === 'recent')));
      c.navigate('persons' + (query.toString() ? '?' + query.toString() : ''));
      return true;
    }
    if (form.id === 'persons-create-form') {
      const body = {...basicBody(form), profile: profileBody(form)};
      if (body.person_subtype === null) delete body.person_subtype; // 新增時不需要明確清空
      const person = await c.api('/persons', {method: 'POST', body: {...body, request_id: c.requestId('persons-create', body)}});
      c.state.requests.delete('persons-create'); // 成功後換新代碼：下一位同名同內容的人物是另一筆，不是重送
      c.state.dirty = false; c.toast(`已建立人物「${person.name}」。`);
      c.navigate('persons/' + encodeId(person.id));
      return true;
    }
    if (form.id === 'persons-relation-form') { await saveRelation(); return true; }
    if (form.id === 'persons-exp-form') { await saveExperience(form); return true; }
    if (form.id === 'persons-edit-form') {
      if (!editing) return true; // 已封存：沒有可提交的表單
      const person = await saveEdit(form);
      c.state.dirty = false; c.toast('已儲存人物。');
      c.navigate('persons/' + encodeId(person.id));
      return true;
    }
    return false;
  }

  async function generate(target) { // AI 產生人物設定：只回填勾選的欄位，未勾選的保留；不自動保存
    const consent = document.getElementById('persons-ai-consent');
    if (!consent || !consent.checked) { c.toast('請先勾選同意人物資料會送往 AI 服務。'); return; }
    const targets = [...document.querySelectorAll('#persons-ai-fields input[name=ai_target]:checked')].map(input => input.value);
    if (!targets.length) { c.toast('請至少勾選一個要處理的欄位。'); return; }
    // 注意：不可用 data-person——舊「關係」模組（relationships.js）會把帶 data-person 的按鈕當成開啟舊人物頁並先攔截點擊。
    const mode = document.querySelector('#persons-ai-panel input[name=ai_mode]:checked')?.value === 'improve' ? 'improve' : 'generate';
    const input = {person_id: target.dataset.personRef, guidance: String(document.getElementById('persons-ai-guidance')?.value || '').trim(), consent: true,
      target_fields: targets, mode};
    const scope = 'persons-ai:' + input.person_id;
    try {
      const result = await c.api('/ai/generate', {method: 'POST', body: {module: 'person_profile', input, request_id: c.requestId(scope, input)}});
      targets.forEach(key => { const box = document.getElementById('profile-' + key); if (box) box.value = result.output[key] || ''; });
      const form = document.getElementById('persons-edit-form');
      editing.ai = {generationId: result.generation.id, snapshot: profileBody(form)};
      const notice = document.getElementById('persons-ai-notice');
      if (notice) { notice.textContent = result.notice; notice.hidden = false; }
      target.textContent = '重新生成勾選的欄位';
      c.state.dirty = true; c.toast('AI 候選已回填勾選的欄位，尚未保存。');
    } finally {
      c.state.requests.delete(scope); // 下一次按下是新的產生（失敗時也不重送舊代碼）；同一次的網路重試由伺服器去重
    }
  }

  async function handleClick(target) {
    const action = target.dataset.action;
    if (action === 'persons-relation-new') { await openNewRelation(target.dataset.personRef); return true; }
    if (action === 'persons-relation-edit') {
      const connection = viewing?.connections.find(x => x.id === target.dataset.connection);
      if (connection) { relation = null; await startRelationEdit(connection, ''); }
      return true;
    }
    if (action === 'persons-relation-pick') { if (relation) await pickRelationPerson(target.dataset.personRef); return true; }
    if (action === 'persons-relation-clear') {
      if (relation) { syncRelationDraft(); Object.assign(relation, {mode: 'create', connection: null, other: null, eligible: null, checked: [], eligiblePeople: null, checkedPeople: [], notice: ''}); showRelation(); }
      return true;
    }
    if (action === 'persons-relation-status') { await setRelationStatus(target); return true; }
    if (action === 'persons-exp-new') { openNewExperience(target.dataset.personRef); return true; }
    if (action === 'persons-exp-subject-pick') { pickExperienceSubject(target.dataset.personRef); return true; }
    if (action === 'persons-exp-subject-clear') { clearExperienceSubject(); return true; }
    if (action === 'persons-exp-open') { openExperience(target.dataset.exp); return true; }
    if (action === 'persons-exp-pick') { pickExperiencePerson(target.dataset.personRef); return true; }
    if (action === 'persons-exp-unpick') { unpickExperiencePerson(target.dataset.personRef); return true; }
    if (action === 'persons-exp-status') { await setExperienceStatus(target); return true; }
    if (target.dataset.action === 'persons-ai-generate') { await generate(target); return true; }
    if (target.dataset.action !== 'persons-status') return false;
    const body = {expected_revision: Number(target.dataset.revision), status: target.dataset.status};
    await c.api(`/persons/${encodeId(target.dataset.id)}/status`, {method: 'POST', body: {...body, request_id: c.requestId('persons-status:' + target.dataset.id, body)}});
    c.toast(body.status === 'archived' ? '人物已封存，資料都保留。' : '人物已恢復。');
    await c.render();
    return true;
  }

  // ---- 導覽與「我的人設」入口（2026-11-11） ----
  /** 人物已取代舊的「關係」「角色」：人物系統可用時左側不再列這兩個入口（頁面仍可由作品流程或網址進入）。 */
  function legacyNav() { return enabled() ? [] : [['people', '◌', '關係'], ['characters', '☆', '角色']]; }

  const SELF_FIELDS = ['display_name', 'public_profile', 'personality', 'speaking_style', 'motivation', 'values', 'behavior', 'knowledge', 'relationships', 'boundaries', 'appearance'];
  const SELF_TRUTH = {real: '真實的我', mixed: '部分真實', ideal: '理想中的我'};
  /** 「我的紀錄」上方的「我的人設」卡片：AI 扮演使用者本人時使用的設定。data＝GET /api/self-persona 的回應；讀不到就不顯示。 */
  function selfCard(data) {
    if (!enabled() || !data) return '';
    const persona = data.persona, content = persona?.content || {};
    const filled = SELF_FIELDS.filter(key => String(content[key] || '').trim()).length + ((content.sample_lines || []).length ? 1 : 0);
    const body = persona
      ? `<h3>${h(content.display_name)}</h3><p class="small muted">第 ${persona.version_no} 版 · ${h(SELF_TRUTH[content.truth_level] || '')} · 已填 ${filled}／12 欄 · ${data.consent ? '已同意 AI 使用' : '尚未同意 AI 使用'}</p><p>${h(content.public_profile)}</p>`
      : `<p>尚未建立。填寫性格、說話方式、動機、價值觀等欄位，AI 才知道怎麼扮演你。</p>`;
    return `<section class="card stack space-bottom" data-block="self-persona"><div class="section-title"><h2>我的人設</h2><span class="tag">AI 扮演你時使用</span></div>
      ${body}<div class="button-row">${c.link('persona?from=history', persona ? '編輯我的人設' : '建立我的人設', persona ? 'secondary' : 'primary')}</div></section>`;
  }

  return {initialize, list: listView, createForm, editForm, detail, submit, handleClick, enabled, scrollTarget, experienceSearch, experienceChips,
    experienceSubjectSearch, experienceSubject: experienceSubjectHtml, recordTabs, recordsPage, legacyNav, selfCard};
})();
