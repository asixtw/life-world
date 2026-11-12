// 建立新作品（2026-11-10 依 8445 已定案的統一生成作品中心整合到 8030 原生 UI）：唯一的建立入口。
// 一份設定 generation_setup.v1，以七個節點呈現：① 人物 ② 場景 ③ 風格 ④ 輸出 ⑤ 選用素材 ⑥ 選用演出要求 ⑦ 開始生成。
// - 預設只展開「人物」；人物完成後按「下一步」展開場景；完成的節點收合成一行摘要，可以隨時點開修改。
// - 素材與演出要求預設不顯示，按「＋ 加入」才出現；⑦ 開始生成永遠可見（桌面在右側、手機在底部）。
// - 所有設定只存在這一份草稿（sessionStorage），收合或修改前面的節點都不會清除其他節點的資料。
// - 草稿依登入帳號隔離：儲存鍵含 owner_id；登出清除記憶體狀態；換帳號只讀到該帳號自己的草稿。
// - 看的故事：開始生成一律建立 generated_work（POST /api/generation/runs）；T1／T2 由伺服器依人數判斷，前端只顯示白話結果。
// 參考：8445 GenerationWizard.tsx、GENERATION_WORK_CENTER_UNIFIED_UI_REDESIGN_20261108.md §4–§8。
// 2026-11-11：① 人物先列「人物」（人物系統啟用時）。選到的人物以 source:'person' 送出，伺服器讀取並鎖定他的正式人物設定；
//   沒有人物設定的人物列出但不能勾選。舊角色卡收在可展開的區塊裡，仍然可以選。
// 2026-11-12：「＋ 建立新作品」是唯一的入口，最上面先選「玩法」（不佔節點編號）：
//   - 看的故事：AI 把整個劇情演完。就是原本的七個節點，送 POST /api/generation/runs；選這個時畫面與請求和加入玩法之前相同。
//   - 玩的遊戲：你每回合做選擇，角色依個性反應，數值決定結局。同一頁只留它需要的東西（① 人物 1～3 位與稱呼、② 場景與行程的設定、⑦ 開始生成），
//     送 POST /api/games，成功後到 #game/{id}（那一頁接著請每位同行者想好反應）。原本獨立的 #game-new 表單併到這裡。
//   兩種玩法用同一份草稿：人物、場景描述與標題是同一個欄位；各自專用的欄位在切換時都留著，切回來還在。
//   要用哪一種方式呈現（閱讀版、互動版…）是作品頁的事，建立時不問。
window.CreationUI = (() => {
  let c;
  const STORE = 'lw-create:draft:'; // ＋ owner_id
  const LEGACY_KEYS = ['lw-create:draft', 'lw-create:setup']; // 舊版未分帳號的草稿：讀到就刪除，避免被下一個帳號看到
  const MAX = 4;
  const MODES = {story: ['看的故事', 'AI 把整個劇情演完，你從頭看到尾。'], game: ['玩的遊戲', '你每回合做選擇，角色依個性反應，數值決定結局。']}; // 玩法：[名稱, 一行說明]
  const GAME_MAX = 3; // 玩的遊戲：同行的人物最多幾位（伺服器也會檢查）
  const GAME_HOURS = [8, 10, 12]; // 玩的遊戲：可用時數的選項
  const GAME_TIME = /^([01][0-9]|2[0-3]):[0-5][0-9]$/; // 出發時間：伺服器只收半形的 HH:MM
  // 玩的遊戲的題材。目前只有「行程」；之後加題材就在這裡加一筆（名稱、場景描述在摘要裡的叫法、輸入框的範例與提示）。
  const GAME_SKINS = {trip: {label: '行程', scene: '行程說明',
    placeholder: '例如：週六和朋友去海邊小鎮一日遊，想吃海鮮、逛老街，也想找地方坐下來休息。',
    hint: '寫下這趟行程想做什麼。可以直接貼上候選地點與營業時間（一行一個，例如「山城咖啡 10:00–17:00」）；沒有寫的話，AI 會用虛構的地方來安排。'}};
  const POSITIONS = {protagonist: '主角', opponent: '對手', advisor: '軍師', supporting: '配角'};
  const ADHERENCE = {faithful: '貼近人物設定', free: '自由詮釋'};
  const NODE_TITLES = {participants: '① 人物', scene: '② 場景', style: '③ 風格', output: '④ 輸出', materials: '⑤ 素材', direction: '⑥ 演出要求'};
  let owner = null; // 目前草稿所屬的帳號
  let S = blank();
  let D = null; // 這一頁用到的資料：人物、角色卡、人設、目錄、AI 狀態、可引用的作品
  const PEOPLE_FILTER_FROM = 8; // 人物超過這個數量才顯示搜尋框
  let sending = false; // 玩的遊戲：建立的請求已經送出、還在等伺服器（規劃要十幾秒到一分鐘）。這段時間「開始生成」停用，不能再送一次
  let failure = ''; // 玩的遊戲：最近一次建立失敗時伺服器的訊息，顯示在開始生成的面板上（內容都留著，可以直接再按）
  let followup = ''; // 玩的遊戲：失敗之後再按「開始生成」會發生什麼（重新規劃，或只是找回上一次的結果）
  // 第幾次嘗試：提交代碼的範圍用它區分。2026-11-12 外部檢驗（Codex）發現：對相同內容一律沿用同一個提交代碼時，
  // 伺服器已經確認失敗的規劃，再按只會重放同一個錯誤。所以伺服器明確回了失敗就換下一次嘗試；連線中斷等結果不明時沿用，
  // 伺服器若其實已經規劃好，重送只會找回那一件，不會重複規劃、重複付費。
  let attempt = 1;

  // 玩的遊戲專用的欄位（稱呼、題材、起點、時數、出發時間）放在 game 裡，和看的故事的欄位分開存：切換玩法時兩邊都不會被清掉
  function blankGame() { return {playerName: '', skin: 'trip', startPlace: '車站', hours: 10, startTime: '08:00'}; }
  function blank() {
    return {persons: [], personFilter: '', cards: [], versions: {}, includeMe: true, positions: {},
      scene: {description: '', preset: '', event: '', goal: '', conditions: ''}, styleIds: [], styleNotes: '',
      output: {type: 'text', length: 'short', form: 'script'}, materialsOpen: false, materials: [],
      directionOpen: false, direction: {adherence: 'faithful', notes: '', avoid: ''}, title: '', open: ['participants'], subs: [],
      mode: 'story', game: blankGame()};
  }
  function load(id) {
    try {
      LEGACY_KEYS.forEach(key => sessionStorage.removeItem(key));
      const saved = JSON.parse(sessionStorage.getItem(STORE + id) || 'null');
      // 加入玩法之前存下來的草稿沒有 mode 與 game：當成看的故事，遊戲的欄位用預設值補齊
      if (saved && Array.isArray(saved.cards)) return {...blank(), ...saved, mode: saved.mode === 'game' ? 'game' : 'story', game: {...blankGame(), ...(saved.game || {})}};
    } catch { /* 無法使用時以空白開始 */ }
    return blank();
  }
  function save() { if (!owner) return; try { sessionStorage.setItem(STORE + owner, JSON.stringify(S)); } catch { /* 僅為方便，失敗不影響建立 */ } }
  function useOwner() { // 每次進入建立頁都核對登入帳號；換帳號就改讀該帳號自己的草稿
    const id = c.state.me?.owner_id || null;
    if (id !== owner) { owner = id; S = id ? load(id) : blank(); D = null; }
  }
  function forget() { owner = null; S = blank(); D = null; sending = false; failure = ''; followup = ''; attempt = 1; } // 登出：清除記憶體中的草稿與資料（各帳號的 sessionStorage 草稿各自保留）

  function initialize(context) { c = context; }
  const h = value => c.esc(value);
  const fresh = ticket => ticket === c.state.renderGeneration;

  // ---- 判斷 ----
  const unified = () => Boolean(D?.people?.enabled); // 人物系統啟用：① 人物先列「人物」
  const personOf = id => (D?.people?.items || []).find(item => item.id === id);
  const personType = item => item.person_subtype === 'historical' ? '歷史人物' : item.person_type === 'fictional' ? '虛構人物' : '真實人物';
  const count = () => S.persons.length + S.cards.length + (S.includeMe ? 1 : 0);
  const moduleLabel = () => count() === 1 ? '單人文字' : count() >= 2 && count() <= MAX ? '多人文字' : '';
  const personaReady = () => Boolean(D?.persona?.persona && D?.persona?.consent);
  // 玩的遊戲：只算勾選的人物（1～3 位），不看舊角色卡與「包含我」——那些留在草稿裡，但這個玩法不用
  const playing = () => S.mode === 'game';
  const gameSkin = () => (GAME_SKINS[S.game.skin] ? S.game.skin : 'trip'); // 草稿裡是不認得的題材（之後拿掉的）就當成行程
  const gameHours = () => (GAME_HOURS.includes(Number(S.game.hours)) ? Number(S.game.hours) : 10);
  const gameStartTime = () => String(S.game.startTime || '').trim() || '08:00'; // 清空就用預設的出發時間
  const participantsDone = () => playing() ? S.persons.length >= 1 && S.persons.length <= GAME_MAX
    : count() >= 1 && count() <= MAX && (!S.includeMe || personaReady());
  function gameBlocker() { // 玩的遊戲不能開始的原因：一次說一項，照畫面由上到下的順序
    const picked = S.persons.length;
    if (!picked) return `請在 ① 人物選 1～${GAME_MAX} 位同行的人物。`;
    if (picked > GAME_MAX) return `玩的遊戲最多 ${GAME_MAX} 位同行的人物，目前選了 ${picked} 位，請取消 ${picked - GAME_MAX} 位。`;
    if (!S.scene.description.trim()) return '請在 ② 場景寫下這趟行程的說明。';
    if (!GAME_TIME.test(gameStartTime())) return '出發時間請填 24 小時制的時與分，例如 08:00。'; // 不支援時間欄位的瀏覽器會變成一般文字框：送出之前先擋下來
    return '';
  }
  function blocker() {
    if (!D?.status?.available) return 'AI 生成尚未設定，暫時無法開始。';
    if (playing()) return gameBlocker();
    if (count() === 0) return `請在 ① 人物至少選擇 1 位（${unified() ? '人物' : '角色卡'}或「包含我」）。`;
    if (count() > MAX) return `第一版最多 ${MAX} 位 AI 參與人物（含我）。`;
    if (S.includeMe && !D.persona.persona) return '勾選「包含我」需要先建立我的人設。';
    if (S.includeMe && !D.persona.consent) return '勾選「包含我」需要先同意讓 AI 依你的人設演出。';
    if (!S.scene.description.trim()) return '請在 ② 場景寫下場景描述。';
    if (S.output.type !== 'text') return '圖片與圖＋文尚未開放，請選擇文字。';
    return '';
  }

  // ---- 摘要（收合時顯示一行） ----
  function summaries() {
    if (playing()) { // 玩的遊戲只有 ① 人物與 ② 場景兩個節點；人物只算勾選的人物
      const picked = S.persons.map(id => (personOf(id) || {}).name || '（已不可用的人物）');
      return {participants: picked.length ? `${picked.join('、')}（${picked.length} 位）` : '尚未選擇',
        scene: S.scene.description.trim() ? S.scene.description.trim().slice(0, 40) : '尚未填寫'};
    }
    const name = id => (D.cards.find(card => card.id === id) || {}).title || '（已不可用的角色卡）';
    const people = [...S.persons.map(id => (personOf(id) || {}).name || '（已不可用的人物）'), ...S.cards.map(name),
      S.includeMe ? (D.persona.persona ? `我（${D.persona.persona.content.display_name}）` : '我') : null].filter(Boolean);
    const length = (D.catalog.lengths.find(item => item.id === S.output.length) || {}).label || S.output.length;
    const form = (D.catalog.forms.find(item => item.id === S.output.form) || {}).label || S.output.form;
    return {
      participants: people.length ? `${people.join('、')}（${count()} 位）` : '尚未選擇',
      scene: S.scene.description.trim() ? S.scene.description.trim().slice(0, 40) : '尚未填寫',
      style: [...S.styleIds.map(id => (D.catalog.styles.find(s => s.id === id) || {}).label || id), S.styleNotes.trim()].filter(Boolean).join('、') || '不指定',
      output: S.output.type === 'text' ? `文字・${length}・${form}` : '尚未開放',
      materials: S.materials.map(item => item.title).join('、'),
      direction: S.directionOpen ? [ADHERENCE[S.direction.adherence], S.direction.notes.trim() && '有演出要求', S.direction.avoid.trim() && '有避免內容'].filter(Boolean).join('・') : '',
    };
  }

  // ---- 畫面 ----
  async function view(params) {
    const ticket = c.state.renderGeneration;
    useOwner();
    failure = ''; followup = ''; // 重新進來：上一次建立失敗的訊息不留著
    // 網址指定玩法（#create?mode=game）：舊的 #game-new 由主程式轉到這裡。預選之後把網址整理回 #create，重新整理時以草稿為準
    if (['story', 'game'].includes(params?.get('mode'))) { S.mode = params.get('mode'); save(); history.replaceState(null, '', '#create'); }
    if (params?.get('focus') === 'start') { S.open = [...new Set([...S.open, 'scene'])]; S.subs = [...new Set([...S.subs, 'start'])]; save(); history.replaceState(null, '', '#create'); }
    const [cards, persona, catalog, status, people] = await Promise.all([c.api('/characters?status=active'), c.api('/self-persona'), c.api('/generation/catalog'), c.api('/generation/status'),
      c.api('/generation/people').catch(() => ({enabled: false, items: []}))]); // 人物清單讀不到時不擋住整頁，退回只選角色卡
    if (!fresh(ticket)) return '';
    D = {cards: cards.items, persona, catalog, status, people, works: D?.works || null};
    S.cards = S.cards.filter(id => D.cards.some(card => card.id === id)); // 已封存或刪除的角色卡不能再選
    S.persons = (S.persons || []).filter(id => Boolean(personOf(id)?.profile)); // 已封存、已不在、或沒有人物設定的人物不能再選
    if (unified() && S.cards.length && !S.subs.includes('cards')) S.subs = [...S.subs, 'cards']; // 草稿裡已經選了舊角色卡：保持展開，不把已選的項目藏起來
    if (S.materialsOpen && !D.works) await loadWorks();
    return `${c.link('works', '← 作品', 'text-button')}<div id="create-root">${build()}</div>`;
  }

  async function loadWorks() { // ⑤ 素材：自己的作品（含舊作品）與角色卡，我的人設除外
    const [center, cards] = await Promise.all([c.api('/works/center?tab=all&limit=200'), c.api('/characters?status=all')]);
    D.works = [...center.items.map(item => ({id: item.id, title: item.title || '（未命名）', version: item.current_version, kind: item.kind})),
      ...cards.items.map(item => ({id: item.id, title: item.title, version: item.current_version, kind: 'character_card'}))];
  }

  function node(id, body, {done = false, optional = false} = {}) {
    const open = S.open.includes(id);
    const summary = summaries()[id];
    return `<section class="card create-node ${open ? 'create-current' : ''}" aria-label="${h(NODE_TITLES[id])}">
      <button type="button" class="create-head" data-action="cr-toggle" data-node="${id}" aria-expanded="${open}">
        <strong>${h(NODE_TITLES[id])}</strong>${optional ? '<span class="small muted">（選用）</span>' : ''}
        <span class="small muted create-summary">${h(summary)}</span><span aria-hidden="true">${done ? '✓' : open ? '▾' : '▸'}</span></button>
      ${open ? `<div class="stack space-top">${body}</div>` : ''}</section>`;
  }

  function sub(id, label, body) {
    const open = S.subs.includes(id);
    return `<div class="create-sub"><button type="button" class="text-button" data-action="cr-sub" data-sub="${id}" aria-expanded="${open}">${open ? '▾' : '▸'} ${h(label)}</button>
      ${open ? `<div class="stack">${body}</div>` : ''}</div>`;
  }

  function personChoice(item) { // 一位可選的人物：姓名、類型與人物設定版本、公開簡介；沒有人物設定就不能勾
    const about = item.description || (item.roles || []).join('、');
    const search = (item.name + ' ' + about).toLowerCase();
    const filter = S.personFilter.trim().toLowerCase();
    const meta = `${personType(item)}・${item.profile ? `人物設定第 ${item.profile.version} 版` : '還沒有人物設定'}`;
    return `<label class="play-choice" data-person-choice data-search="${h(search)}" ${filter && !search.includes(filter) ? 'hidden' : ''}>
        <input type="checkbox" data-bind="person" value="${h(item.id)}" ${S.persons.includes(item.id) ? 'checked' : ''} ${item.profile ? '' : 'disabled'}>
        <span><strong>${h(item.name)}</strong> <span class="small muted">${h(meta)}</span>${about ? `<br><span class="small muted">${h(about)}</span>` : ''}
        ${item.profile ? '' : `<br>${c.link('persons/' + encodeURIComponent(item.id), '到人物頁填寫人物設定 →', 'text-button')}`}</span></label>`;
  }

  function filterPeople() { // 搜尋人物：直接顯示或隱藏清單項目，不重畫（保留輸入游標）
    const filter = S.personFilter.trim().toLowerCase();
    document.querySelectorAll('#create-root [data-person-choice]').forEach(node => { node.hidden = Boolean(filter) && !node.dataset.search.includes(filter); });
  }

  function participantsBody() {
    const cards = D.cards.map(item => `<label class="play-choice"><input type="checkbox" data-bind="card" value="${h(item.id)}" data-version="${item.current_version}" ${S.cards.includes(item.id) ? 'checked' : ''}>
        <span><strong>${h(item.title)}</strong>${item.content?.tagline ? `<br><span class="small muted">${h(item.content.tagline)}</span>` : ''}</span></label>`).join('');
    const persona = D.persona;
    let me = '';
    if (S.includeMe && !persona.persona) { // 就地建立人設（沿用「我的人設」的保存流程）
      me = `<form id="persona-form" class="card stack"><p class="small">勾選「包含我」需要先建立我的人設：</p>
        ${[['display_name', '顯示名稱', 60, false], ['public_profile', '公開簡介（其他角色看得到）', 400, true], ['personality', '性格', 2000, true], ['speaking_style', '說話方式', 600, true]]
          .map(([key, label, max, multi]) => `<div class="field"><label for="persona-${key}">${h(label)}</label>${multi ? `<textarea id="persona-${key}" name="${key}" maxlength="${max}" rows="2" required></textarea>`
            : `<input id="persona-${key}" name="${key}" maxlength="${max}" required>`}</div>`).join('')}
        <div class="button-row"><button type="submit" class="secondary">建立我的人設</button></div></form>`;
    } else if (S.includeMe && !persona.consent) {
      me = `<p class="callout">${h(persona.consent_text)} ${c.button('persona-consent', '我同意', 'primary', 'data-granted="true"')}</p>`;
    } else if (S.includeMe) {
      me = `<p class="small muted">我的人設：${h(persona.persona.content.display_name)}（第 ${persona.persona.version_no} 版，已同意）${c.link('persona', '修改', 'text-button')}</p>`;
    }
    const staged = [...S.persons.map(id => [id, (personOf(id) || {}).name || id]), ...S.cards.map(id => [id, (D.cards.find(card => card.id === id) || {}).title || id])];
    const positions = count() >= 2 && staged.length ? sub('positions', '角色定位（選用）', staged.map(([id, name]) => {
      return `<div class="stage-pick"><span>${h(name)}</span><select data-bind="position" data-id="${h(id)}" aria-label="${h(name)}的角色定位"><option value="">不指定</option>
        ${Object.entries(POSITIONS).map(([key, label]) => `<option value="${key}" ${S.positions[id] === key ? 'selected' : ''}>${label}</option>`).join('')}</select></div>`;
    }).join('')) : '';
    const cardPicker = `<fieldset class="field"><legend>我的角色卡（可多選）</legend>${cards || '<p class="small muted">還沒有角色卡。</p>'}</fieldset>`;
    const pickers = unified() // 人物系統啟用：先列人物；舊角色卡收合在下方，仍然可以選
      ? `<fieldset class="field"><legend>人物（可多選）</legend>
          ${D.people.items.length > PEOPLE_FILTER_FROM ? `<input type="search" data-bind="personFilter" value="${h(S.personFilter)}" placeholder="搜尋姓名或簡介" aria-label="搜尋人物">` : ''}
          <div class="create-people">${D.people.items.map(personChoice).join('') || '<p class="small muted">還沒有人物。</p>'}</div></fieldset>
        <p class="small muted">AI 依每位人物的「人物設定」演出；開始後使用當時的版本，之後再改不影響這部作品。沒有想要的人物？到「人物」新增並填寫人物設定。${c.link('persons', '前往人物 →', 'text-button')}</p>
        ${D.cards.length ? sub('cards', `舊角色卡（${D.cards.length} 張）`, `<p class="small muted">角色卡是人物系統之前的資料，內容和人物設定各自獨立；同名的人物與角色卡不能一起出場。</p>${cardPicker}`) : ''}`
      : `${cardPicker}
      <p class="small muted">沒有想要的角色？到「角色」建立新角色、複製系統範例，或從真人資料建立。${c.link('characters', '前往角色 →', 'text-button')}</p>`;
    return `${pickers}
      <label class="play-choice"><input type="checkbox" data-bind="me" ${S.includeMe ? 'checked' : ''}><span><strong>包含我</strong><br><span class="small muted">AI 依「我的人設」扮演你</span></span></label>
      ${me}${positions}
      <p class="${count() > MAX || count() === 0 ? 'callout' : 'small muted'}">AI 參與人物：${count()} 位${moduleLabel() ? `（${moduleLabel()}）` : ''}。第一版最多 ${MAX} 位，由系統自動判斷。</p>
      <div class="button-row">${c.button('cr-next', '下一步：場景', 'secondary', `data-from="participants" data-to="scene" ${participantsDone() ? '' : 'disabled'}`)}</div>`;
  }

  function sceneBody() {
    const presets = (D.catalog.scene_presets || []).map(item => `<option value="${h(item.id)}" data-text="${h(item.description)}" ${S.scene.preset === item.id ? 'selected' : ''}>${h(item.title)}</option>`).join('');
    return `<div class="field"><label for="create-scene">場景描述（必填）</label>
        <textarea id="create-scene" data-bind="scene.description" maxlength="2000" rows="4" placeholder="時間、地點、背景與正在發生的事，例如「深夜的港口倉庫，一批藥品不見了」。">${h(S.scene.description)}</textarea></div>
      ${sub('preset', '從範例場景開始（選用）', `<div class="field"><label for="create-preset">範例場景（選擇後帶入場景描述，可以再修改）</label>
        <select id="create-preset" data-bind="scene.preset"><option value="">不使用</option>${presets}</select></div>`)}
      ${sub('start', '劇情起點（選用）', `<div class="field"><label for="create-event">起始事件</label><textarea id="create-event" data-bind="scene.event" maxlength="800" rows="2">${h(S.scene.event)}</textarea></div>
        <div class="field"><label for="create-goal">主角目標</label><textarea id="create-goal" data-bind="scene.goal" maxlength="600" rows="2">${h(S.scene.goal)}</textarea></div>`)}
      ${sub('conditions', '場景條件（選用）', `<div class="field"><label for="create-conditions">每行一項，最多 8 項，例如「不能離開港口」</label>
        <textarea id="create-conditions" data-bind="scene.conditions" rows="3">${h(S.scene.conditions)}</textarea></div>`)}
      <div class="button-row">${c.button('cr-next', '完成場景', 'secondary', 'data-from="scene" data-to=""')}</div>`;
  }

  // ---- 玩法 ----
  function modePicker() { // 建立頁的第一步：選玩法。兩個原生的單選按鈕（鍵盤用方向鍵切換），整列包在 label 裡，點文字也選得到
    // 不是節點（沒有 create-node、沒有編號）：既有的 ①～⑦ 不用重新編號，看的故事的畫面只多出這一塊
    const choices = Object.entries(MODES).map(([id, [label, about]]) => `<label class="play-choice"><input type="radio" name="create-mode" data-bind="mode" value="${id}" ${S.mode === id ? 'checked' : ''}>
        <span><strong>${label}</strong><br><span class="small muted">${about}</span></span></label>`).join('');
    return `<section class="card create-mode" aria-label="玩法"><fieldset class="field"><legend>玩法</legend>${choices}</fieldset>
      <p class="small muted">要用哪一種方式呈現（閱讀版、互動版…），作品完成後到作品頁再選。</p></section>`;
  }

  // ---- 玩的遊戲：① 人物與 ② 場景（只有這個玩法需要的欄位） ----
  function gamePeopleBody() { // 只列人物：AI 依正式的人物設定決定每個人的反應，所以沒有人物設定的不能選；不列舊角色卡、「包含我」與角色定位
    const items = D.people.items || [];
    const picked = S.persons.length;
    let picker;
    if (!unified()) picker = '<p class="callout">玩的遊戲要從「人物」裡選同行的人，但目前讀不到人物清單，或這個環境還沒有開放人物。請稍後重新整理再試。</p>';
    else if (!items.length) picker = `<p class="small muted">還沒有人物。先到「人物」新增，並填寫人物設定。${c.link('persons', '前往人物 →', 'text-button')}</p>`;
    else picker = `<fieldset class="field"><legend>同行的人（選 1～${GAME_MAX} 位）</legend>
          ${items.length > PEOPLE_FILTER_FROM ? `<input type="search" data-bind="personFilter" value="${h(S.personFilter)}" placeholder="搜尋姓名或簡介" aria-label="搜尋人物">` : ''}
          <div class="create-people">${items.map(personChoice).join('')}</div></fieldset>
        <p class="small muted">AI 依每位人物的「人物設定」決定他每一回合的反應；開始後使用當時的版本，之後再改不影響這件作品。${items.some(item => item.profile) ? '' : '目前沒有任何人物有人物設定，請先到人物頁填寫。'}${c.link('persons', '前往人物 →', 'text-button')}</p>`;
    return `${picker}
      <div class="field"><label for="create-player">你在這場戲裡的稱呼（選填，預設「你」）</label><input id="create-player" data-bind="game.playerName" maxlength="20" placeholder="你" value="${h(S.game.playerName)}"></div>
      <p class="${picked < 1 || picked > GAME_MAX ? 'callout' : 'small muted'}">同行的人物：${picked} 位（需要 1～${GAME_MAX} 位）。</p>
      <div class="button-row">${c.button('cr-next', '下一步：場景', 'secondary', `data-from="participants" data-to="scene" ${participantsDone() ? '' : 'disabled'}`)}</div>`;
  }

  function gameSceneBody() { // 場景描述和看的故事是同一個欄位（scene.description），提示換成題材用的；沒有範例場景、劇情起點與場景條件
    const skin = GAME_SKINS[gameSkin()];
    const skins = Object.entries(GAME_SKINS).map(([id, item]) => `<option value="${id}" ${gameSkin() === id ? 'selected' : ''}>${h(item.label)}</option>`).join('');
    const hours = GAME_HOURS.map(value => `<option value="${value}" ${gameHours() === value ? 'selected' : ''}>${value} 小時</option>`).join('');
    return `<div class="field"><label for="create-scene">場景描述（必填）</label>
        <textarea id="create-scene" data-bind="scene.description" maxlength="2000" rows="5" placeholder="${h(skin.placeholder)}">${h(S.scene.description)}</textarea>
        <p class="small muted">${h(skin.hint)}</p></div>
      <div class="field"><label for="create-skin">題材</label><select id="create-skin" data-bind="game.skin">${skins}</select>
        <p class="small muted">目前只有「行程」，之後會有更多題材。</p></div>
      <div class="field"><label for="create-start-place">起點（出發與最後要回來的地方）</label><input id="create-start-place" data-bind="game.startPlace" maxlength="40" value="${h(S.game.startPlace)}"></div>
      <div class="field"><label for="create-hours">可用時數</label><select id="create-hours" data-bind="game.hours">${hours}</select></div>
      <div class="field"><label for="create-start-time">出發時間</label><input id="create-start-time" data-bind="game.startTime" type="time" value="${h(S.game.startTime)}"></div>
      <div class="button-row">${c.button('cr-next', '完成場景', 'secondary', 'data-from="scene" data-to=""')}</div>`;
  }

  function styleBody() {
    return `<p class="small muted">可以多選，也可以不選（不指定）。</p>
      <div class="gen-checks">${D.catalog.styles.map(item => `<label class="check-line"><input type="checkbox" data-bind="style" value="${h(item.id)}" ${S.styleIds.includes(item.id) ? 'checked' : ''}> ${h(item.label)}</label>`).join('')}</div>
      <div class="field"><label for="create-style-notes">其他風格（選填，最多 40 字）</label><input id="create-style-notes" data-bind="styleNotes" maxlength="40" value="${h(S.styleNotes)}"></div>`;
  }

  function outputBody() {
    const outputs = D.catalog.outputs.map(item => `<label class="play-choice"><input type="radio" name="create-output" data-bind="output.type" value="${h(item.type)}" ${S.output.type === item.type ? 'checked' : ''} ${item.available ? '' : 'disabled'}>
        <span><strong>${h(item.label)}</strong>${item.available ? '' : ` <span class="small muted">（${h(item.note || '尚未開放')}）</span>`}</span></label>`).join('');
    const text = S.output.type === 'text' ? `<div class="field"><label for="create-length">長度</label><select id="create-length" data-bind="output.length">
        ${D.catalog.lengths.map(item => `<option value="${h(item.id)}" ${S.output.length === item.id ? 'selected' : ''}>${h(item.label)}</option>`).join('')}</select></div>
      <fieldset class="field"><legend>呈現形式</legend>${D.catalog.forms.map(item => `<label class="check-line"><input type="radio" name="create-form" data-bind="output.form" value="${h(item.id)}" ${S.output.form === item.id ? 'checked' : ''}> ${h(item.label)}</label>`).join('')}</fieldset>` : '';
    return `<div role="radiogroup" aria-label="輸出類型">${outputs}</div>${text}`;
  }

  function materialsBody() {
    const limit = D.catalog.limits.max_materials;
    const list = S.materials.map(item => `<li>${h(item.title)}（第 ${item.version_no} 版）${c.button('cr-remove-material', '移除', 'text-button', `data-id="${h(item.work_id)}"`)}</li>`).join('');
    const choices = (D.works || []).filter(item => !S.materials.some(m => m.work_id === item.id))
      .map(item => `<option value="${h(item.id)}" ${D.pick?.id === item.id ? 'selected' : ''}>${h(item.title)}（目前第 ${item.version} 版）</option>`).join('');
    const versions = D.pick ? `<div class="field"><label for="create-material-version">版本（可以選歷史版本）</label><select id="create-material-version">
        ${D.pick.versions.map(v => `<option value="${v.version_no}">第 ${v.version_no} 版${v.version_no === D.pick.current ? '（目前）' : ''} · ${h(c.time(v.created_at))}</option>`).join('')}</select></div>
      <div class="button-row">${c.button('cr-add-material', '加入這個版本', 'secondary')}</div>` : '';
    return `<p class="small muted">引用自己的既有作品（含舊作品）或角色卡的某個版本作為參考，最多 ${limit} 件；只當參考，不會重複建立人物或場景。生成時使用你選定版本的內容。</p>
      ${list ? `<ul class="char-versions">${list}</ul>` : ''}
      ${S.materials.length < limit ? `<div class="field"><label for="create-material">加入作品</label><select id="create-material" data-bind="material"><option value="">選擇作品</option>${choices}</select></div>${versions}` : ''}
      <div class="button-row">${c.button('cr-remove-materials', '移除素材節點', 'text-button')}</div>`;
  }

  function directionBody() {
    return `<fieldset class="field"><legend>人物設定忠實度</legend>${Object.entries(ADHERENCE).map(([key, label]) => `<label class="check-line"><input type="radio" name="create-adherence" data-bind="direction.adherence" value="${key}" ${S.direction.adherence === key ? 'checked' : ''}> ${h(label)}</label>`).join('')}</fieldset>
      <div class="field"><label for="create-notes">演出要求（例如節奏、視角或想強調的情緒，最多 600 字）</label><textarea id="create-notes" data-bind="direction.notes" maxlength="600" rows="2">${h(S.direction.notes)}</textarea></div>
      <div class="field"><label for="create-avoid">避免內容（最多 600 字）</label><textarea id="create-avoid" data-bind="direction.avoid" maxlength="600" rows="2">${h(S.direction.avoid)}</textarea></div>
      <div class="button-row">${c.button('cr-remove-direction', '移除演出要求', 'text-button')}</div>`;
  }

  function startPanel() {
    const s = summaries();
    const reason = blocker();
    const game = playing();
    const skin = GAME_SKINS[gameSkin()];
    // 摘要：玩的遊戲只列它用到的項目（人物、行程說明、題材、時數與出發時間）
    const rows = game ? [['人物', s.participants], [skin.scene, s.scene], ['題材', skin.label], ['時數與出發時間', `${gameHours()} 小時・${gameStartTime()} 出發`]]
      : [['人物', s.participants], ['場景', s.scene], ['風格', s.style], ['輸出', s.output], ...(s.materials ? [['素材', s.materials]] : []), ...(s.direction ? [['演出要求', s.direction]] : [])];
    // 看的故事在這裡說明自動判斷的結果；玩的遊戲沒有這種判斷，改成說明會呼叫幾次模型：規劃 1 次，加上每位同行者各 1 次
    const picked = S.persons.length;
    const headline = game ? (picked ? `會呼叫模型 ${picked + 1} 次：規劃 1 次，加上 ${picked} 位同行者各 1 次。` : '會呼叫模型：規劃 1 次，加上每位同行者各 1 次。')
      : moduleLabel() ? `自動判斷：${moduleLabel()}（${count()} 位）` : `AI 參與人物：${count()} 位`;
    // 等待建立遊戲的回應時說明正在做什麼（按鈕停用）；上一次失敗時顯示伺服器的訊息；其餘是不能開始的原因
    const notice = sending ? '<p class="small muted" role="status">正在規劃這趟行程（地點、時間與結局），大約需要十幾秒到一分鐘；請留在這一頁。</p>'
      : `${failure ? `<p class="callout gen-error" role="alert">${h(failure)}</p>${followup ? `<p class="small muted">${h(followup)}</p>` : ''}` : ''}${reason ? `<p class="small muted" role="status">${h(reason)}</p>` : ''}`;
    const after = game ? '開始後先規劃地點、時間與結局，再到遊戲頁請每位同行者想好反應；全部完成才能玩，同行的人越多等越久。'
      : D.status.background ? '生成在後端進行，每段完成就保存；可以關閉頁面，回來就能看到最新進度。' : '開始後會在作品頁逐段生成，每段完成就保存；離開頁面會暫停，回到作品頁就從下一段繼續。';
    return `<aside class="card create-start" aria-label="開始生成"><details class="create-start-details" ${window.matchMedia('(max-width: 900px)').matches ? '' : 'open'}><summary><strong>⑦ 開始生成</strong> <span class="small muted">設定摘要與標題</span></summary>
        <dl class="char-fields">${rows.map(([k, v]) => `<dt>${h(k)}</dt><dd>${h(v)}</dd>`).join('')}</dl>
        <div class="field"><label for="create-title">作品標題（選填，留白時由 AI 規劃）</label><input id="create-title" data-bind="title" maxlength="60" value="${h(S.title)}"></div></details>
      <p class="create-module" aria-live="polite">${headline}</p>
      ${notice}
      <div class="button-row">${c.button('cr-start', sending ? '規劃中…' : '開始生成', 'primary', reason || sending ? 'disabled' : '')}</div>
      <p class="small muted">${after}</p></aside>`;
  }

  function gate() {
    if (!participantsDone()) {
      S.open = S.open.filter(id => id === 'participants'); // 人物未完成：只保留人物節點（其他節點的資料都還在）
      S.sceneAuto = false;
      if (!S.open.includes('participants')) S.open.push('participants');
    } else if (!S.sceneAuto) {
      S.sceneAuto = true;
      if (!S.open.includes('scene')) S.open.push('scene'); // 人物完成後自動展開場景
    }
  }

  function build() {
    gate();
    const game = playing();
    // 玩的遊戲只有 ① 人物與 ② 場景兩個節點（編號照舊）；風格、輸出、素材與演出要求是看的故事才有的，這裡不顯示（草稿裡的內容留著）
    const nodes = game ? [node('participants', gamePeopleBody(), {done: participantsDone()}), node('scene', gameSceneBody(), {done: Boolean(S.scene.description.trim())})].join('')
      : [node('participants', participantsBody(), {done: participantsDone()}), node('scene', sceneBody(), {done: Boolean(S.scene.description.trim())}),
      node('style', styleBody(), {done: S.styleIds.length > 0 || Boolean(S.styleNotes.trim()), optional: true}), node('output', outputBody(), {done: S.output.type === 'text'}),
      S.materialsOpen ? node('materials', materialsBody(), {done: S.materials.length > 0, optional: true}) : '',
      S.directionOpen ? node('direction', directionBody(), {done: true, optional: true}) : ''].join('');
    const add = !game && participantsDone() ? `<div class="button-row">${S.materialsOpen ? '' : c.button('cr-add-materials', '＋ 加入素材', 'secondary')}${S.directionOpen ? '' : c.button('cr-add-direction', '＋ 加入演出要求', 'secondary')}</div>` : '';
    const intro = game ? '選同行的人物、寫下這趟行程。按「開始生成」後，AI 先規劃地點與時間，再請每位同行者想好反應；準備好之後，每回合由你做選擇。'
      : '依序設定人物與場景，其他設定可以不填。按「開始生成」後，AI 會扮演所有參與人物並逐段完成整部作品。';
    return `${c.heading('建立新作品', intro, c.button('cr-reset', '清除重來', 'text-button'))}
      ${D.status.available && D.status.provider_kind !== 'live' ? '<p class="callout">目前使用「測試用假回應」：不是 AI，只用來驗證流程。</p>' : ''}
      <div class="create-layout"><div class="create-tree">${modePicker()}${nodes}${add}</div>${startPanel()}</div>`;
  }

  function repaint() { // 只重畫建立流程本身（不重新讀取資料、不離開頁面）
    const root = document.getElementById('create-root');
    if (root) root.innerHTML = build();
  }

  // ---- 互動：輸入即寫回草稿；會改變結構的選項才重畫 ----
  function set(path, value) {
    const keys = path.split('.');
    let target = S;
    keys.slice(0, -1).forEach(key => { target = target[key]; });
    target[keys[keys.length - 1]] = value;
  }

  function bind(event) {
    const el = event.target;
    if (!el.closest || !el.closest('#create-root') || !el.dataset.bind) return;
    const key = el.dataset.bind;
    const choice = el.type === 'checkbox' || el.type === 'radio' || el.tagName === 'SELECT';
    if (choice && event.type !== 'change') return; // 勾選與選單只處理 change（瀏覽器也會送 input，避免同一次點擊處理兩次）
    let structural = event.type === 'change';
    if (key === 'personFilter') { S.personFilter = el.value; save(); filterPeople(); return; }
    if (key === 'mode') { // 切換玩法：只換這一頁顯示哪些節點與欄位；兩邊填過的內容都留在草稿裡，切回來還在
      S.mode = el.value === 'game' ? 'game' : 'story';
      failure = ''; followup = ''; // 上一次建立遊戲失敗的訊息不帶到另一種玩法
      save();
      repaint();
      // 重畫會換掉整個區塊，焦點跟著不見：放回選到的那一個單選按鈕，用鍵盤方向鍵切換之後可以接著操作
      document.querySelector('#create-root input[data-bind="mode"]:checked')?.focus();
      return;
    }
    if (key === 'person') S.persons = el.checked ? [...new Set([...S.persons, el.value])] : S.persons.filter(id => id !== el.value);
    else if (key === 'card') {
      S.cards = el.checked ? [...new Set([...S.cards, el.value])] : S.cards.filter(id => id !== el.value);
      S.versions[el.value] = Number(el.dataset.version);
    } else if (key === 'me') S.includeMe = el.checked;
    else if (key === 'position') S.positions[el.dataset.id] = el.value || undefined;
    else if (key === 'style') S.styleIds = el.checked ? [...new Set([...S.styleIds, el.value])] : S.styleIds.filter(id => id !== el.value);
    else if (key === 'game.hours') S.game.hours = Number(el.value); // 選單的值是字串；草稿與送出的內容都用數字
    else if (key === 'material') {
      const work = (D.works || []).find(item => item.id === el.value);
      D.pick = null;
      if (work) { // 讀出這件作品的所有版本，讓使用者選要引用哪一版
        c.api('/works/' + encodeURIComponent(work.id)).then(detail => {
          D.pick = {id: work.id, title: work.title, current: detail.current_version, versions: detail.versions.map(v => ({version_no: v.version_no, created_at: v.created_at}))};
          repaint();
        }).catch(error => c.toast(error.message));
        return;
      }
    } else if (key === 'scene.preset') {
      S.scene.preset = el.value;
      if (el.value) S.scene.description = el.selectedOptions[0].dataset.text || S.scene.description; // 帶入描述，之後可以自由修改
    } else {
      set(key, el.type === 'radio' ? el.value : el.value);
      structural = event.type === 'change' && (el.type === 'radio' || el.tagName === 'SELECT'); // 文字欄位不重畫，避免失焦時吃掉按鈕點擊
    }
    save();
    if (structural) repaint();
    else if (event.type === 'input' && !el.closest('.create-start')) { // 文字輸入不重畫（保留游標）；只更新開始生成區
      const panel = document.querySelector('#create-root .create-start');
      if (panel) { const fresh = document.createElement('div'); fresh.innerHTML = startPanel(); panel.replaceWith(fresh.firstElementChild); }
    }
  }

  function buildSetup() {
    const conditions = S.scene.conditions.split('\n').map(line => line.trim()).filter(Boolean).slice(0, 8);
    const position = id => (count() >= 2 && S.positions[id] ? {position: S.positions[id]} : {});
    return {participants: [
        // 人物：只送人物與畫面讀到的人物設定版本；實際使用哪一版由伺服器鎖定，畫面讀到的不是最新版時伺服器會拒絕
        ...S.persons.map(id => ({source: 'person', ref: {person_id: id, profile_id: personOf(id)?.profile?.id}, ...position(id)})),
        ...S.cards.map(id => ({source: 'card', ref: {work_id: id, version_no: S.versions[id] || (D.cards.find(card => card.id === id) || {}).current_version}, ...position(id)}))],
      include_me: S.includeMe, title: S.title.trim(),
      scene_context: {description: S.scene.description.trim(), start: {event: S.scene.event.trim(), goal: S.scene.goal.trim()}, conditions,
        ...(S.scene.preset ? {preset_id: S.scene.preset} : {}), shared_history_refs: S.materials.map(m => ({work_id: m.work_id, version_no: m.version_no}))},
      style_profile: {style_ids: S.styleIds, notes: S.styleNotes.trim()},
      output: {type: 'text', text: {length: S.output.length, form: S.output.form}},
      ...(S.directionOpen ? {direction: {adherence: S.direction.adherence, notes: S.direction.notes.trim(), avoid: S.direction.avoid.trim()}} : {})};
  }

  function buildGame() { // 玩的遊戲送出的內容（POST /api/games，不含提交代碼）。只取這個玩法的欄位：舊角色卡、「包含我」、風格等不送
    const name = S.game.playerName.trim();
    return {skin: gameSkin(),
      // 只送人物與畫面讀到的人物設定版本；實際用哪一版由伺服器鎖定，畫面讀到的不是最新版時伺服器會拒絕
      participants: S.persons.map(id => { const profile = personOf(id)?.profile?.id; return {person_id: id, ...(profile ? {profile_id: profile} : {})}; }),
      player: name ? {name} : {}, // 稱呼沒有填就不送，由伺服器用預設的「你」
      description: S.scene.description.trim(), start_place: S.game.startPlace.trim() || '車站', hours: gameHours(), start_time: gameStartTime(), title: S.title.trim()};
  }

  async function startGame() { // 建立玩的遊戲：伺服器在這一次請求裡做「規劃」，要等十幾秒到一分鐘
    if (blocker()) { repaint(); return; } // 還不能開始（按鈕本來就停用）：不送出，畫面上已經寫著原因
    const body = buildGame();
    const who = owner; // 等待期間如果登出了（登入過期時主程式也會清掉這一頁的狀態）或換了帳號：回來之後不動別人的草稿，也不換頁
    sending = true; // 等待時按鈕停用：重畫出來的按鈕也是停用的，不會送出第二次
    failure = ''; followup = '';
    repaint();
    try {
      // 同一次嘗試、內容沒有改就沿用同一個提交代碼：連線中斷後再按一次，不會規劃出兩件
      const scope = attempt === 1 ? 'game-new' : `game-new:${attempt}`;
      const game = await c.api('/games', {method: 'POST', body: {...body, request_id: c.requestId(scope, body)}});
      sending = false;
      if (owner !== who) return;
      attempt = 1;
      S = blank(); // 和看的故事一樣：建立之後草稿清空
      save();
      c.state.dirty = false;
      c.navigate('game/' + encodeURIComponent(game.id)); // 遊戲頁接著請每位同行者想好反應
    } catch (error) {
      sending = false;
      if (owner !== who) throw error; // 這一頁已經不是原本那個帳號的了：交給主程式顯示（例如「請重新登入」），不寫進這一頁
      failure = error.message || '規劃沒有完成，請稍後再試一次。'; // 草稿沒有動：內容都留著，可以直接再按
      const running = error.status === 409 && error.code === 'generation_in_progress';
      if (Number.isInteger(error.status) && !running) { // 伺服器確認這一次已經結束（失敗）：下一次是新的嘗試，會再呼叫一次模型
        attempt += 1;
        followup = '再按「開始生成」會重新規劃一次（會再呼叫一次模型）。';
      } else {
        followup = running ? '上一次的規劃還在進行，請稍候再按一次。' : '還不確定伺服器有沒有收到；再按一次會先找回上一次的結果，不會重複規劃。';
      }
      repaint();
      document.querySelector('#create-root [data-action="cr-start"]')?.focus(); // 重畫之後把焦點放回按鈕，鍵盤可以直接再試
    }
  }

  async function handleClick(target) {
    const action = target.dataset.action || '';
    if (!action.startsWith('cr-')) return false;
    if (action === 'cr-start' && sending) return true; // 建立遊戲的請求還在等伺服器：兩種玩法都不能在這時候再開始一次
    if (action === 'cr-start' && playing()) { await startGame(); return true; }
    if (action === 'cr-toggle' && target.dataset.node !== 'participants' && !S.open.includes(target.dataset.node) && !participantsDone()) {
      c.toast(playing() ? `請先完成 ① 人物：選 1～${GAME_MAX} 位同行的人物。` : '請先完成 ① 人物：至少 1 位，「包含我」需要人設與同意。');
      return true;
    }
    if (action === 'cr-toggle') S.open = S.open.includes(target.dataset.node) ? S.open.filter(id => id !== target.dataset.node) : [...S.open, target.dataset.node];
    else if (action === 'cr-next' && target.dataset.from === 'scene' && !S.scene.description.trim()) { c.toast('請先寫下場景描述。'); return true; }
    else if (action === 'cr-next') S.open = [...S.open.filter(id => id !== target.dataset.from), ...(target.dataset.to ? [target.dataset.to] : [])]; // 完成後收合，展開下一個必要節點
    else if (action === 'cr-sub') S.subs = S.subs.includes(target.dataset.sub) ? S.subs.filter(id => id !== target.dataset.sub) : [...S.subs, target.dataset.sub];
    else if (action === 'cr-add-materials') { S.materialsOpen = true; S.open = [...new Set([...S.open, 'materials'])]; if (!D.works) await loadWorks(); }
    else if (action === 'cr-remove-materials') { S.materialsOpen = false; S.materials = []; }
    else if (action === 'cr-remove-material') S.materials = S.materials.filter(m => m.work_id !== target.dataset.id);
    else if (action === 'cr-add-material' && D.pick) {
      const version = Number(document.getElementById('create-material-version')?.value || D.pick.current);
      S.materials = [...S.materials.filter(m => m.work_id !== D.pick.id), {work_id: D.pick.id, version_no: version, title: D.pick.title}].slice(0, D.catalog.limits.max_materials);
      D.pick = null;
    }
    else if (action === 'cr-add-direction') { S.directionOpen = true; S.open = [...new Set([...S.open, 'direction'])]; }
    else if (action === 'cr-remove-direction') S.directionOpen = false;
    else if (action === 'cr-reset') { S = blank(); failure = ''; followup = ''; }
    else if (action === 'cr-start') {
      const setup = buildSetup();
      const work = await c.api('/generation/runs', {method: 'POST', body: {setup, request_id: c.requestId('create-run', setup)}});
      S = blank();
      save();
      c.state.dirty = false;
      c.navigate('run/' + encodeURIComponent(work.id));
      return true;
    }
    save();
    repaint();
    return true;
  }

  async function submit() { return false; } // 建立流程沒有自己的表單；「建立我的人設」沿用 WorksUI 的人設表單

  document.addEventListener('input', event => { if (window.CreationUI && document.getElementById('create-root')) bind(event); });
  document.addEventListener('change', event => { if (window.CreationUI && document.getElementById('create-root')) bind(event); });

  return {initialize, view, submit, handleClick, forget};
})();
