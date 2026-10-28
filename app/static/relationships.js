/* Original W01/W02/Person 360 flows. Shared state, real sources, no AI inference. */
window.PeopleUI = (() => { // 封裝人物模組，避免內部狀態污染全域命名空間
  let c, currentOwner, listing = null, profile = null, evidence = null, editorPerson = null, returnRoute = 'people'; // 保存主程式工具、目前帳號與人物頁快取
  const scroll = new Map(); // 依路由保存返回時的捲動位置
  const expanded = new Map(); // 依人物保存四維度展開狀態
  const dims = {interests:'興趣與嗜好', food:'飲食偏好', skills:'專長與背景', habits:'互動習慣'}; // 定義原規劃的四個人物維度
  const categories = {business:'業務',life:'生活',learning:'學習／健身',other:'未分類'}; // 定義人物主分類的中文名稱
  const kinds = {in_person:'實體見面',call:'電話',message:'訊息',other:'其他',unknown:'未分類'}; // 區分實體見面、電話、訊息、其他與未分類
  const evidenceNames = {stated_by_person:'使用者記錄的本人陳述',observed_by_user:'使用者觀察',documented_source:'文件佐證'}; // 顯示使用者確認的證據類型，不宣稱平台查證
  const h = v => c.esc(v); // 將使用者文字轉義後才插入 HTML，避免被當成標記
  const link = (route,label,style='secondary') => { // 共用主程式連結工具並補上可存取名稱
    const name=(label.match(/^<b>(.*?)<\/b>/)?.[1] || label.replace(/<[^>]+>/g,' ')).replace(/^←\s*/,'').replace(/\s*→$/,''); // 從連結文字取得去除裝飾符號的可存取名稱
    return c.link(route,label,style).replace('<a ', '<a aria-label="'+h(name)+'" '); // 回傳此步驟組合完成的結果
  }; // 結束目前回呼、區塊或模組定義
  const btn = (action,label,style='primary',attrs='') => c.button(action,label,style,attrs); // 共用主程式操作按鈕工具
  const query = () => new URLSearchParams(location.hash.split('?')[1] || ''); // 讀取目前 hash 路由的查詢參數
  const json = (method,body) => ({method,body}); // 組合 API 的 HTTP 方法與請求本文
  const tokens = value => String(value || '').split(/[、,，\n]/).map(x=>x.trim()).filter(Boolean); // 將使用者新輸入的角色或標籤依分隔符拆成清單
  function initialize(context) { c = context; } // 注入主程式共用工具與狀態
  function ensureOwner() { // 帳號切換時清除上一帳號的人物與介面快取
    if (currentOwner !== c.state.me?.owner_id) { // 依目前選項或狀態進入對應處理分支
      currentOwner=c.state.me?.owner_id; listing=null; profile=null; evidence=null; editorPerson=null; returnRoute='people'; scroll.clear(); expanded.clear(); // 帳號變更時清空人物、來源、編輯資料與介面狀態
    } // 結束目前回呼、區塊或模組定義
  } // 結束目前回呼、區塊或模組定義
  function remember(route,y) { // 記住返回時的捲動位置與維度展開狀態
    scroll.set(route,y); // 記住目前頁面的捲動位置，返回時可接續閱讀
    const node=document.querySelector('#person-profile'); // 保存「node」供此流程接續使用
    if(node) expanded.set(node.dataset.personId,new Set([...node.querySelectorAll('.dimension[open]')].map(d=>d.dataset.dimension))); // 記住此人物目前已展開的維度區塊
  } // 結束目前回呼、區塊或模組定義
  function restore(route) { window.scrollTo(0,scroll.get(route) || 0); } // 恢復指定路由的捲動位置
  function personRoute(p,tab='overview') { return 'person/'+p.id+'?tab='+tab; } // 組合人物完整頁及指定分頁路由
  function recordRoute(p,goal=null,back=null) { // 組合帶人物、目標與返回位置的新經歷入口
    const q=new URLSearchParams({person:p.id,return:back || location.hash.slice(1)}); // 讀取或組合目前路由的搜尋與返回條件
    if (goal) q.set('goal',goal.id); // 依目前選項或狀態進入對應處理分支
    return 'record?'+q; // 回傳此步驟組合完成的結果
  } // 結束目前回呼、區塊或模組定義
  function listingRoute(changes={}) { // 更新人物清單查詢，同時保留其他條件
    const q=query(); for(const [key,value] of Object.entries(changes)) { if(value === '' || value === null) q.delete(key); else q.set(key,value); } // 僅更新指定查詢欄位；空值移除，其餘條件保留
    return 'people'+(q.size?'?'+q:''); // 回傳此步驟組合完成的結果
  } // 結束目前回呼、區塊或模組定義
  function lastTime(p) { return p.last_interaction_at ? c.time(p.last_interaction_at) : '尚無互動紀錄'; } // 顯示最近互動，無紀錄時不捏造日期
  function follow(p) { return btn('person-follow',p.followed?'已關注':'設為關注','secondary',`data-id="${h(p.id)}" data-revision="${p.revision}" data-followed="${p.followed}"`); } // 產生攜帶版本號的關注切換按鈕
  function starMap(people,selected=null,mini=false) { // 繪製匿名星圖、分類與選取外圈；位置不表示親密度
    const visible=people.slice(0,mini?6:50), count=visible.length; // 首頁最多顯示六個匿名星點；完整清單依分頁資料繪製
    const nodes=visible.map((p,i)=>{ // 組合各星點的人物資料與固定畫布座標
      const ring=Math.floor(i/12), n=Math.min(12,count-ring*12), angle=-Math.PI/2+(i%12)*Math.PI*2/n; // 依固定環形位置排版星點，不把距離視為親密度
      const radius=mini?145:Math.max(60,165-ring*45), x=300+Math.cos(angle)*radius*1.35, y=210+Math.sin(angle)*radius; // 依固定環形位置排版星點，不把距離視為親密度
      return {p,x,y}; // 回傳此步驟組合完成的結果
    }); // 結束目前回呼、區塊或模組定義
    return `<svg class="relationship-map ${mini?'mini-map':''}" viewBox="0 0 600 420" ${mini?'aria-hidden="true"':'role="group" aria-label="關係星圖；位置為視覺排序，不代表親密度"'}>${nodes.map(n=>`<line x1="300" y1="210" x2="${n.x}" y2="${n.y}" class="star-line"/>`).join('')}<circle cx="300" cy="210" r="42" class="self-star"/><text x="300" y="216" text-anchor="middle" class="self-label">我</text>${nodes.map(({p,x,y})=>`<g ${mini?'':`role="button" tabindex="0" aria-label="選取${h(p.name)}" data-person="${h(p.id)}"`} class="star-node category-${p.category} ${p.id===selected?'selected':''}"><circle cx="${x}" cy="${y}" r="29"/><circle cx="${x}" cy="${y}" r="40" class="star-hit"/><text x="${x}" y="${y+6}" text-anchor="middle">✦</text>${p.id===selected?`<circle cx="${x}" cy="${y}" r="36" class="selection-ring"/>`:''}</g>`).join('')}</svg>`; // 組合「繪製匿名星圖、分類與選取外圈；位置不表示親密度」所需的畫面或提交資料
  } // 結束目前回呼、區塊或模組定義
  function worldMini() { // 在世界首頁顯示匿名關係縮圖與入口
    const people=[...c.state.world.people].sort((a,b)=>Number(b.followed)-Number(a.followed)||Number(b.has_active_goal)-Number(a.has_active_goal)||(b.last_interaction_at||'').localeCompare(a.last_interaction_at||'')||a.name.localeCompare(b.name)); // 依關注、進行中目標及最近互動排序首頁人物
    return `<section id="world-relationships" class="card space-top"><div class="section-title"><h2>旅途中遇見的人</h2>${link('people','探索我的關係宇宙 →','text-button')}</div>${starMap(people,null,true)}${people.length?'':`<p class="small muted">${c.state.me.status==='guest'?'建立帳號後，就能開始累積人物與共同經歷。':'從一位重要的人，開始你的關係宇宙。'}</p>`}</section>`; // 組合「在世界首頁顯示匿名關係縮圖與入口」所需的畫面或提交資料
  } // 結束目前回呼、區塊或模組定義
  async function renderPeople() { // 以同一清單繪製星圖或收藏冊並保留查詢與選取
    ensureOwner(); returnRoute=location.hash.slice(1) || 'people'; // 先清除跨帳號快取，再處理目前人物頁操作
    const q=query(), view=q.get('view') || 'star'; // 讀取或組合目前路由的搜尋與返回條件
    const params=new URLSearchParams({q:q.get('q')||'',sort:q.get('sort')||'priority',category:q.get('category')||'',followed_only:q.get('followed_only')||'false',offset:q.get('offset')||'0',limit:'12'}); // 將搜尋、排序、分類、關注及分頁組成同一查詢
    const ticket=c.state.renderGeneration, result=await c.api('/people?'+params); // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
    if(ticket!==c.state.renderGeneration) return ''; // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
    listing=result; // 將這次有效查詢結果設為兩種檢視共用清單
    const selected=listing.items.find(p=>p.id===q.get('selected')); // 從共用清單找出目前選取人物
    // 組合「以同一清單繪製星圖或收藏冊並保留查詢與選取」所需的畫面或提交資料
    return `${c.heading('我的人際關係','從星圖探索，也能用收藏冊快速找到人。',btn('new-person','＋ 新增人物'))}
      <div class="view-switch" role="tablist" aria-label="人物檢視方式">${['star','cards'].map(v=>`<a role="tab" aria-label="${v==='star'?'星圖':'收藏冊'}" aria-selected="${view===v}" href="#${h(listingRoute({view:v}))}">${v==='star'?'✧ 星圖':'▦ 收藏冊'}</a>`).join('')}</div>
      <form id="people-filter-form" data-search="true" class="people-filters"><div class="field"><label for="people-query">搜尋人物、角色、目標或標籤</label><input id="people-query" name="q" value="${h(q.get('q')||'')}" maxlength="200" placeholder="輸入姓名、目標或標籤"></div><div class="filter-controls"><select name="sort" aria-label="視覺排序">${[['priority','綜合優先度'],['recent','最近互動'],['name','姓名']].map(([v,t])=>`<option value="${v}" ${params.get('sort')===v?'selected':''}>${t}</option>`).join('')}</select><select name="category" aria-label="人物分類"><option value="">全部分類</option>${Object.entries(categories).map(([v,t])=>`<option value="${v}" ${params.get('category')===v?'selected':''}>${t}</option>`).join('')}</select><label class="check-line"><input name="followed_only" type="checkbox" ${params.get('followed_only')==='true'?'checked':''}>只看關注</label><button class="primary">搜尋</button></div></form>
      <p class="small muted">綜合優先度：關注 → 關聯進行中目標 → 最近互動。星點位置不代表親密度。共 ${listing.total} 位。</p>
      ${c.state.me.status==='guest'?`<div class="upgrade-banner"><h3>建立帳號，開始記錄你的關係。</h3><p class="small muted">人物資料需要先升級；原本的目標與草稿都會保留。</p>${btn('claim-dialog','建立帳號，繼續記錄')}</div>`:''}
      ${listing.items.length?(view==='star'?`<div class="card map-card">${starMap(listing.items,selected?.id)}<div class="map-legend">${Object.entries(categories).map(([v,t])=>`<span class="category-${v}">● ${t}</span>`).join('')}</div></div>`:`<div class="people-cards">${listing.items.map(p=>`<button class="card person-card ${p.id===selected?.id?'selected':''}" data-person="${h(p.id)}" aria-label="選取${h(p.name)}"><span class="person-avatar category-${p.category}">${h(p.name.slice(0,1))}</span><span><b>${h(p.name)}</b><span class="small muted person-card-line">${h(p.roles.join('、')||'尚未設定角色')}</span><span class="small muted person-card-line">${h(lastTime(p))}${p.followed?' · 已關注':''}</span></span></button>`).join('')}</div>`):c.empty('目前沒有符合條件的人物。')}
      ${selected?`<aside class="person-summary card" aria-label="已選人物摘要"><div class="section-title"><h2>${h(selected.name)}</h2>${btn('person-close-summary','關閉摘要','text-button')}</div><p>${h(selected.roles.join('、')||'尚未設定角色')}</p><p class="small muted">最近互動：${h(lastTime(selected))}</p><p class="small">共同場合／交集：${h(selected.common_context||'尚未記錄')}<br>標籤：${h(selected.tags.join('、')||'尚未設定')}</p><div class="button-row">${follow(selected)}${link(personRoute(selected),'查看人物卡','primary')}</div></aside>`:''}
      <div class="button-row space-top">${listing.offset?link(listingRoute({offset:Math.max(0,listing.offset-listing.limit)}),'上一頁'):''}${listing.offset+listing.items.length<listing.total?link(listingRoute({offset:listing.offset+listing.limit}),'下一頁'):''}</div>`;
  } // 結束目前回呼、區塊或模組定義
  function stats(data) { // 顯示實體見面次數、互動數與最近日期
    return `<div class="person-stats"><div><b data-stat="meetings">${data.stats.meetings}</b><small>見面次數</small></div><div><b data-stat="interactions">${data.stats.interactions}</b><small>互動紀錄</small></div><div><b>${data.stats.last_interaction_at?h(new Intl.DateTimeFormat('zh-TW',{timeZone:c.state.me.timezone,month:'2-digit',day:'2-digit'}).format(new Date(data.stats.last_interaction_at))):'尚無'}</b><small>最近互動</small></div></div>`; // 組合「顯示實體見面次數、互動數與最近日期」所需的畫面或提交資料
  } // 結束目前回呼、區塊或模組定義
  function profileHead(data,tab) { // 產生人物標頭、統計與三個人物分頁
    const p=data.person; // 取得目前人物或日期欄位資料
    return `<div class="section-title">${link(returnRoute,'← 返回關係','text-button')}${btn('person-edit','編輯人物','secondary')}</div><header class="person-heading"><span class="person-avatar category-${p.category}">${h(p.name.slice(0,1))}</span><div><h1>${h(p.name)}</h1><p>${h(p.roles.join(' · ')||'尚未設定角色')}</p><div class="tags">${p.tags.map(t=>`<span class="tag">${h(t)}</span>`).join('')}</div></div>${follow(p)}</header>${stats(data)}<nav class="person-tabs" role="tablist" aria-label="人物資料分頁">${[['overview','人物總覽'],['history','共同經歷'],['goals','合作與目標']].map(([key,title])=>`<a role="tab" aria-selected="${tab===key}" href="#${personRoute(p,key)}">${title}</a>`).join('')}</nav>`; // 組合「產生人物標頭、統計與三個人物分頁」所需的畫面或提交資料
  } // 結束目前回呼、區塊或模組定義
  function factCard(f,p) { // 顯示已確認資訊、衝突操作與來源入口
    return `<article class="fact-detail"><b>${h(f.value)}</b><p class="small">${h(f.description||'尚無補充說明。')}</p>${f.status==='conflict'?`<p class="conflict-label">資訊有衝突，請確認</p>${btn('fact-resolve','採用這項資訊','secondary',`data-id="${h(f.id)}" data-revision="${f.revision}"`)}`:''}<div>${link('source/'+p.id+'/'+f.id,'查看來源','text-button')}</div></article>`; // 組合「顯示已確認資訊、衝突操作與來源入口」所需的畫面或提交資料
  } // 結束目前回呼、區塊或模組定義
  function overviewPanel(data) { // 產生四個展開維度、資訊歷史與共同關係
    const p=data.person; // 取得目前人物或日期欄位資料
    // 組合「產生四個展開維度、資訊歷史與共同關係」所需的畫面或提交資料
    return `<div class="section-title"><h2>關於這個人</h2><span class="small muted">${Object.values(data.facts).filter(v=>v.length).length} 個已知維度</span></div>${Object.entries(dims).map(([key,title])=>`<details class="dimension card" data-dimension="${key}" ${expanded.get(p.id)?.has(key)?'open':''}><summary><span>${title}</span><div class="dimension-tags">${data.facts[key].length?data.facts[key].map(f=>`<span class="tag ${f.status==='conflict'?'gold':''}">${h(f.value)}</span>`).join(''):'<span class="muted small">尚未了解</span>'}</div></summary><div class="dimension-body">${data.facts[key].map(f=>factCard(f,p)).join('')||'<p class="small muted">沒有已確認的來源，不會自動猜測。</p>'}</div></details>`).join('')}
      <div class="button-row">${btn('fact-new','從已確認經歷新增資訊','secondary')}</div>
      ${data.fact_history.length?`<details class="card space-top fact-history"><summary>人物資訊變更歷史（${data.fact_history.length}）</summary>${data.fact_history.map(f=>`<article class="fact-detail"><h3>${h(f.value)}</h3><span class="tag">${f.status==='archived'?'衝突處理後封存':'已無有效來源'}</span><p class="small">${h(f.description)}</p>${link('source/'+p.id+'/'+f.id,'查看來源','text-button')}${f.sources.length?btn('fact-resolve','重新採用此項','secondary',`data-id="${f.id}" data-revision="${f.revision}"`):''}</article>`).join('')}</details>`:''}
      <section class="card space-top"><div class="section-title"><h2>共同關係與交集</h2>${btn('connection-new','新增明確關係','text-button')}</div><p class="small">共同場合／交集：${h(p.common_context||'尚未記錄')}</p>${data.connections.map(r=>`<div class="list-item"><div><h3>${h(r.person.name)}</h3><p>${h(r.label)}</p><span class="small muted">${r.source_experience_ids.length?'附已確認經歷來源':'使用者自行建立的關係'}</span></div>${link(personRoute(r.person),'查看人物','text-button')}</div>`).join('')||'<p class="small muted">尚未建立共同關係。</p>'}</section>
      ${p.notes?`<section class="card space-top"><h3>自行記錄的備註</h3><p class="record-content">${h(p.notes)}</p><p class="small muted">備註不會自動轉成已確認的維度資訊。</p></section>`:''}`;
  } // 結束目前回呼、區塊或模組定義
  function historyPanel(data) { // 以事件呈現共同經歷、分類與合併操作
    const events=data.interactions; // 保存「events」供此流程接續使用
    return `<div class="section-title"><h2>共同經歷</h2><select id="interaction-filter" aria-label="互動類型篩選"><option value="">全部互動</option>${Object.entries(kinds).map(([v,t])=>`<option value="${v}">${t}</option>`).join('')}</select></div><form id="merge-form"><div class="callout">同一次互動可有多筆經歷。合併會保留原文、任務與積分，採用你選定的主要事件日期與類型。</div>${events.length?`<div class="field"><label for="merge-target">保留為主要事件</label><select id="merge-target" name="target">${events.map(e=>`<option value="${e.id}">${h(c.time(e.occurred_at))} · ${kinds[e.kind]}</option>`).join('')}</select></div>`:''}<div class="stack">${events.map(e=>`<article class="card interaction-card" data-kind="${e.kind}"><div class="section-title"><span class="small muted">${h(c.time(e.occurred_at))}</span><select data-classify="${e.id}" data-revision="${e.revision}" aria-label="分類這次互動">${Object.entries(kinds).map(([v,t])=>`<option value="${v}" ${e.kind===v?'selected':''}>${t}</option>`).join('')}</select></div>${e.experiences.map(x=>`<div class="event-experience"><h3>${h(x.summary)}</h3><details><summary class="small muted">查看原始經歷</summary><div class="raw-source">${h(x.raw_text)}</div></details></div>`).join('')}<p class="small muted">${e.experiences.length} 筆經歷，共 1 次互動</p><label class="check-line"><input type="checkbox" name="merge_sources" value="${e.id}">將這筆合併至主要事件</label></article>`).join('')||c.empty('尚無共同經歷，可以從下方記錄第一次互動。')}</div>${events.length>1?'<button class="secondary space-top">合併同一次互動</button>':''}</form>`; // 組合「以事件呈現共同經歷、分類與合併操作」所需的畫面或提交資料
  } // 結束目前回呼、區塊或模組定義
  function goalsPanel(data) { // 顯示人物相關目標與下一步並帶入記錄上下文
    const p=data.person; // 取得目前人物或日期欄位資料
    return `<section id="person-goals"><div class="section-title"><h2>與此人物相關的目標</h2>${btn('person-goal-new','關聯目標','secondary')}</div><div class="stack">${data.goals.map(g=>`<article class="card"><h3>${h(g.title)}</h3><p class="small">${h(g.label||'由共同經歷關聯')}</p><span class="tag">${g.status==='active'?'進行中':'已完成'}</span><p class="small muted">關聯代表使用者的記錄，不表示對方承諾合作。</p>${link(recordRoute(p,g),'記錄這個目標的經歷','text-button')}</article>`).join('')||c.empty('尚未關聯目標。')}<div class="card"><h3>下一步與待辦</h3>${data.tasks.map(t=>`<label class="check-line"><input type="checkbox" data-task="${t.id}" ${t.done?'checked':''}>${h(t.title)}</label>`).join('')||'<p class="small muted">確認經歷時可以留下下一步。</p>'}</div></div></section>`; // 組合「顯示人物相關目標與下一步並帶入記錄上下文」所需的畫面或提交資料
  } // 結束目前回呼、區塊或模組定義
  async function renderPerson(personId,tab='overview') { // 載入人物完整頁並選擇總覽、經歷或目標分頁
    ensureOwner(); const ticket=c.state.renderGeneration, data=await c.api('/people/'+encodeURIComponent(personId)+'/overview'); // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
    if(ticket!==c.state.renderGeneration) return ''; // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
    profile=data; // 保存目前帳號最新人物完整頁資料
    tab=['overview','history','goals'].includes(tab)?tab:'overview'; // 僅接受人物總覽、共同經歷與合作目標三個分頁
    const p=profile.person; // 取得目前人物或日期欄位資料
    return `<div id="person-profile" class="person-profile" data-person-id="${p.id}">${profileHead(profile,tab)}<section class="person-tab-panel">${tab==='overview'?overviewPanel(profile):tab==='history'?historyPanel(profile):goalsPanel(profile)}</section><div class="person-actions">${link(recordRoute(p),'記錄新經歷','primary')}${link('theater/'+p.id+'?return='+encodeURIComponent(location.hash.slice(1)),'開啟小劇場','secondary')}</div></div>`; // 組合「載入人物完整頁並選擇總覽、經歷或目標分頁」所需的畫面或提交資料
  } // 結束目前回呼、區塊或模組定義
  function allExperiences(data) { return [...new Map(data.interactions.flatMap(e=>e.experiences).map(e=>[e.id,e])).values()]; } // 以識別碼去重可引用的已確認經歷
  function sourceChecks(data) { return allExperiences(data).map(e=>`<label class="check-line"><input name="source_ids" type="checkbox" value="${e.id}"><span>${h(c.time(e.occurred_at))}<br>${h(e.summary)}</span></label>`).join('')||'<p class="small muted">目前沒有已確認的來源；仍可手動練習，但不能捏造人物偏好。</p>'; } // 列出可由使用者明確勾選的來源
  async function renderTheater(personId,mode='') { // 產生四用途小劇場，區分模擬、私人草稿與真實經歷
    ensureOwner(); const ticket=c.state.renderGeneration, data=await c.api('/people/'+encodeURIComponent(personId)+'/overview'); // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
    if(ticket!==c.state.renderGeneration) return ''; // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
    profile=data; const p=profile.person; // 保存目前帳號最新人物完整頁資料
    const modes={preparation:['見面前準備','查看來源，留下自己的準備。'],simulation:['情境演練','手動練習；模擬內容，非真人發言。'],message:['傳達心意','保存或複製草稿，尚未送出。'],review:['相遇後回顧','只記錄真正發生的互動。']}; // 定義四種小劇場用途及模擬／未發送說明
    const back=query().get('return')||personRoute(p); // 保留返回人物原分頁的路由
    if(mode==='review') return ''; // The mode link routes directly into the shared experience form. // 相遇後回顧入口直接使用共用的真實經歷表單
    return `<div class="narrow">${link(back,'← 返回人物頁','text-button')}${c.heading('與'+p.name+'的小劇場','先練習，再相遇。真實經歷與私人草稿分開保存。')}<div class="theater-modes">${Object.entries(modes).map(([key,[name,description]])=>link(key==='review'?recordRoute(p,null,back):'theater/'+p.id+'?mode='+key+'&return='+encodeURIComponent(back),`<b>${name}</b><span>${description}</span>`,`card theater-mode ${key===mode?'active':''}`)).join('')}</div>${mode&&modes[mode]?`<form id="theater-note-form" class="card space-top" data-person="${p.id}"><span class="tag gold">${mode==='simulation'?'模擬內容，非真人發言':mode==='message'?'訊息草稿，尚未送出':'私人準備'}</span><input type="hidden" name="kind" value="${mode}"><h3 class="space-top">本次引用的已確認來源（選填）</h3>${sourceChecks(profile)}<div class="field space-top"><label for="theater-title">標題</label><input id="theater-title" name="title" maxlength="160" required></div><div class="field"><label for="theater-content">自己的內容</label><textarea id="theater-content" name="content" maxlength="20000" required></textarea></div><div class="callout">本輪不連接真實 AI；私人內容不更新人物事實、互動次數、進度或積分。</div><div class="button-row"><button class="primary">保存私人筆記</button>${mode==='message'?btn('theater-copy','複製草稿','secondary'):''}</div></form>`:''}<section class="space-top"><h2>私人筆記與草稿</h2><div class="stack">${profile.notes.map(n=>`<article class="card note-card"><span class="tag gold">${n.kind==='simulation'?'模擬內容，非真人發言':n.kind==='message'?'訊息草稿，尚未送出':'私人準備'}</span><h3 class="space-top">${h(n.title)}</h3><p class="record-content">${h(n.content)}</p><p class="small muted">引用 ${n.source_experience_ids.length} 筆來源 · ${h(c.time(n.created_at))}</p></article>`).join('')||c.empty('尚無私人筆記。')}</div></section></div>`; // 組合「產生四用途小劇場，區分模擬、私人草稿與真實經歷」所需的畫面或提交資料
  } // 結束目前回呼、區塊或模組定義
  async function renderEvidence(personId,factId) { // 顯示人物資訊的原文、時間、證據類型與撤回入口
    ensureOwner(); const ticket=c.state.renderGeneration, result=await c.api('/people/'+personId+'/facts/'+factId+'/evidence'); // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
    if(ticket!==c.state.renderGeneration) return ''; // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
    evidence=result; // 保存目前資訊的有效引用來源
    const f=evidence.fact; // 讀取目前表單或資訊來源內容
    return `<div class="narrow">${link('person/'+personId+'?tab=overview','← 返回人物總覽','text-button')}${c.heading('人物資訊的來源',dims[f.dimension]+' · '+f.value)}<p class="record-content">${h(f.description)}</p><div class="stack">${evidence.sources.map(s=>`<article class="card"><span class="tag">${evidenceNames[s.evidence_type]}</span><p class="record-meta">發生於 ${h(c.time(s.occurred_at))}</p><h3>${h(s.summary)}</h3><div class="raw-source">${h(s.raw_text)}</div><div class="callout">這是使用者已確認的記錄，不代表平台獨立查證。</div>${btn('fact-revoke','撤回此來源','secondary',`data-experience="${s.id}"`)}</article>`).join('')||c.empty('目前沒有有效來源；此資訊不再列為已知維度。')}</div></div>`; // 組合「顯示人物資訊的原文、時間、證據類型與撤回入口」所需的畫面或提交資料
  } // 結束目前回呼、區塊或模組定義
  function personForm(p=null) { // 產生多角色、分類、標籤與備註編輯表單
    return `<h2 id="account-heading">${p?'編輯人物':'記下一位重要的人。'}</h2><form id="person-form" ${p?`data-person="${p.id}" data-revision="${p.revision}"`:''}><div class="field"><label for="person-name">稱呼</label><input id="person-name" name="name" maxlength="100" required value="${h(p?.name||'')}"></div><div class="field"><label for="person-role">角色（可多個，以逗號分隔）</label><input id="person-role" name="roles_text" value="${h(p?.roles.join('、')||'')}" placeholder="客戶、跑步夥伴"></div><div class="field"><label for="person-category">主分類</label><select id="person-category" name="category">${Object.entries(categories).map(([v,t])=>`<option value="${v}" ${(p?.category||'other')===v?'selected':''}>${t}</option>`).join('')}</select></div><div class="field"><label for="person-tags">標籤（以逗號分隔）</label><input id="person-tags" name="tags_text" value="${h(p?.tags.join('、')||'')}"></div><div class="field"><label for="common-context">共同場合／交集（自行記錄）</label><input id="common-context" name="common_context" maxlength="1000" value="${h(p?.common_context||'')}"></div><div class="field"><label for="person-notes">自行記錄的備註</label><textarea id="person-notes" name="notes" maxlength="4000">${h(p?.notes||'')}</textarea></div><button class="primary">保存人物</button></form>`; // 組合「產生多角色、分類、標籤與備註編輯表單」所需的畫面或提交資料
  } // 結束目前回呼、區塊或模組定義
  function openPersonEditor(p=null) { editorPerson=p; c.dialog(personForm(p)); } // 記住編輯前人物資料再開啟表單
  async function reviewExtras(personId) { // 在經歷核對頁加入互動分類與逐項人物更新
    if(!personId || personId==='__upgrade' || c.state.me.status==='guest') return '<p class="small muted">本次沒有選擇人物，不會更新人物檔案。</p>'; // 依目前選項或狀態進入對應處理分支
    const data=await c.api('/people/'+encodeURIComponent(personId)+'/overview'); // 等待伺服器完成讀取或保存，再進入下一步
    return `<fieldset><legend>真實互動</legend><div class="form-grid"><div class="field"><label for="interaction-type">互動類型</label><select id="interaction-type" name="interaction_type">${Object.entries(kinds).map(([v,t])=>`<option value="${v}" ${v==='unknown'?'selected':''}>${t}</option>`).join('')}</select></div><div class="field"><label for="existing-event">是否屬於已記錄的同一次互動？</label><select id="existing-event" name="interaction_event_id"><option value="">建立新互動</option>${data.interactions.map(e=>`<option value="${e.id}">${h(c.time(e.occurred_at))} · ${kinds[e.kind]}</option>`).join('')}</select></div></div></fieldset><fieldset><legend>更新人物資訊（選填，逐項確認）</legend><p class="small muted">只有勾選的項目才寫入人物檔案，來源是本次確認的真實經歷。請勿填寫心理推測。</p>${Object.entries(dims).map(([key,title])=>`<div class="candidate-row"><label class="check-line"><input name="fact_selected_${key}" type="checkbox">確認新增：${title}</label><input name="fact_value_${key}" maxlength="160" aria-label="${title}內容" placeholder="從原文確認的資訊"><select name="fact_type_${key}" aria-label="${title}證據類型">${Object.entries(evidenceNames).map(([v,t])=>`<option value="${v}">${t}</option>`).join('')}</select></div>`).join('')}</fieldset>`; // 組合「在經歷核對頁加入互動分類與逐項人物更新」所需的畫面或提交資料
  } // 結束目前回呼、區塊或模組定義
  function reviewPayload(form) { // 只將明確勾選的人物候選加入提交內容
    const f=new FormData(form); // 讀取使用者目前表單值，不直接推論人物資訊
    return {interaction_type:f.get('interaction_type')||'unknown',interaction_event_id:f.get('interaction_event_id')||null, // 組合「只將明確勾選的人物候選加入提交內容」所需的畫面或提交資料
      person_updates:Object.keys(dims).filter(d=>f.has('fact_selected_'+d)).map(d=>({dimension:d,value:f.get('fact_value_'+d),description:'由使用者核對本次原始經歷後確認。',evidence_type:f.get('fact_type_'+d),selected:true}))}; // 執行「只將明確勾選的人物候選加入提交內容」的目前處理步驟
  } // 結束目前回呼、區塊或模組定義
  async function handleClick(target) { // 處理人物選取、關注、來源與明確關係操作
    ensureOwner(); // 先清除跨帳號快取，再處理目前人物頁操作
    if(target.dataset.person) { c.navigate(listingRoute({selected:target.dataset.person})); return true; } // 依目前選項或狀態進入對應處理分支
    const action=target.dataset.action; // 讀取按鈕明確指定的操作代碼
    if(action==='person-close-summary') { c.navigate(listingRoute({selected:null})); return true; } // 關閉摘要並保留查詢條件
    if(action==='person-follow') { // 攜帶版本切換關注狀態
      await c.api('/people/'+target.dataset.id,json('PATCH',{expected_revision:Number(target.dataset.revision),followed:target.dataset.followed!=='true'})); // 等待伺服器完成讀取或保存，再進入下一步
      await c.refresh(); await c.render(); return true; // 重新讀取伺服器確認的資料，再更新畫面
    } // 結束目前回呼、區塊或模組定義
    if(action==='person-edit') { openPersonEditor(profile.person); return true; } // 開啟人物基本資料編輯
    if(action==='fact-new') { // 從已確認經歷建立人物資訊
      c.dialog(`<h2 id="account-heading">從經歷確認人物資訊</h2><form id="fact-form" data-person="${profile.person.id}"><div class="field"><label for="fact-dimension">資訊維度</label><select id="fact-dimension" name="dimension">${Object.entries(dims).map(([v,t])=>`<option value="${v}">${t}</option>`).join('')}</select></div><div class="field"><label for="fact-value">資訊內容</label><input id="fact-value" name="value" required maxlength="160"></div><div class="field"><label for="fact-description">補充說明</label><textarea id="fact-description" name="description" maxlength="2000"></textarea></div><div class="field"><label for="fact-evidence">證據類型</label><select id="fact-evidence" name="evidence_type">${Object.entries(evidenceNames).map(([v,t])=>`<option value="${v}">${t}</option>`).join('')}</select></div><h3>選取已確認的來源</h3>${sourceChecks(profile)}<div class="field"><label for="fact-conflict">若與既有資訊衝突，請明確指出</label><select id="fact-conflict" name="conflicts_with"><option value="">沒有指定衝突</option>${Object.entries(profile.facts).flatMap(([d,items])=>items.map(f=>`<option value="${f.id}">${dims[d]}：${h(f.value)}</option>`)).join('')}</select></div><label class="check-line"><input name="confirmed" type="checkbox" required>我已核對內容與來源，確認加入人物資訊。</label><button class="primary">確認新增人物資訊</button></form>`); return true; // 執行「處理人物選取、關注、來源與明確關係操作」的目前處理步驟
    } // 結束目前回呼、區塊或模組定義
    if(action==='fact-resolve') { await c.api('/people/'+profile.person.id+'/facts/'+target.dataset.id+'/resolve',json('POST',{expected_revision:Number(target.dataset.revision)})); await c.render(); c.toast('已採用這項資訊，衝突紀錄保留於歷史。'); return true; } // 人工採用資訊並保留衝突歷史
    if(action==='fact-revoke') { const f=evidence.fact; await c.api('/people/'+f.person_id+'/facts/'+f.id+'/sources/revoke',json('POST',{expected_revision:f.revision,experience_id:target.dataset.experience})); c.navigate('person/'+f.person_id+'?tab=overview'); c.toast('來源已撤回；沒有有效來源的資訊不再顯示為已知。'); return true; } // 撤回來源且不刪除原始經歷
    if(action==='person-goal-new') { c.dialog(`<h2 id="account-heading">關聯目標與下一步</h2><form id="person-goal-form"><div class="field"><label for="related-goal">目標</label><select id="related-goal" name="goal_id">${c.options(c.state.world.goals,null)}</select></div><div class="field"><label for="goal-label">關聯說明／下一步</label><input id="goal-label" name="label" maxlength="300"></div><button class="primary">保存關聯</button></form>`); return true; } // 明確建立人物目標關聯
    if(action==='connection-new') { const people=c.state.world.people.filter(p=>p.id!==profile.person.id); c.dialog(`<h2 id="account-heading">建立明確的共同關係</h2><form id="connection-form"><div class="field"><label for="other-person">另一位人物</label><select id="other-person" name="other_person_id" required>${c.options(people,null,'name')}</select></div><div class="field"><label for="connection-label">共同關係／場合</label><input id="connection-label" name="label" required maxlength="300"></div><h3>可附相關經歷來源</h3>${sourceChecks(profile)}<button class="primary">保存共同關係</button></form>`); return true; } // 建立人物間明確共同關係
    if(action==='theater-copy') { const text=document.querySelector('#theater-content').value; if(navigator.clipboard) await navigator.clipboard.writeText(text); else throw new Error('請選取草稿文字，使用系統的複製功能。'); c.toast('已複製草稿，尚未發送。'); return true; } // 複製訊息草稿，不對外發送
    return false; // 此事件不屬於人物模組，交回主程式處理
  } // 結束目前回呼、區塊或模組定義
  async function handleSubmit(form) { // 驗證並送出人物、來源、關聯、合併或私人筆記表單
    const f=new FormData(form), id=form.id; // 讀取使用者目前表單值，不直接推論人物資訊
    if(id==='people-filter-form') { c.state.dirty=false; c.navigate(listingRoute({q:f.get('q'),sort:f.get('sort'),category:f.get('category'),followed_only:f.has('followed_only')?'true':null,selected:null,offset:null})); return true; } // 成功保存或明確導覽後清除未保存旗標
    if(id==='person-form') { // 依目前選項或狀態進入對應處理分支
      const unchanged = !!editorPerson && editorPerson.id===form.dataset.person; // 只有確實編輯同一人物，才沿用原始角色與標籤陣列
      const roles=unchanged && f.get('roles_text')===editorPerson.roles.join('、')?editorPerson.roles:tokens(f.get('roles_text')); // 文字未變更時保留舊陣列，避免把舊角色文字誤拆分
      const tags=unchanged && f.get('tags_text')===editorPerson.tags.join('、')?editorPerson.tags:tokens(f.get('tags_text')); // 文字未變更時保留舊陣列，避免把舊角色文字誤拆分
      const body={name:f.get('name'),roles,tags,category:f.get('category'),notes:f.get('notes'),common_context:f.get('common_context')}; // 組合使用者明確提供的 API 提交內容
      const p=await c.api('/people'+(form.dataset.person?'/'+form.dataset.person:''),json(form.dataset.person?'PATCH':'POST',form.dataset.person?{...body,expected_revision:Number(form.dataset.revision)}:body)); // 等待伺服器完成讀取或保存，再進入下一步
      await c.refreshKeepingForm(); document.querySelector('#account-dialog').close(); // 重新讀取伺服器確認的資料，再更新畫面
      const select=document.querySelector('#person-id'); if(select) {select.value=p.id; c.state.dirty=true; if(document.querySelector('#people-review-fields')) document.querySelector('#people-review-fields').innerHTML=await reviewExtras(p.id);} // 標記目前仍有尚未保存的修改
      c.toast('人物已保存。'); return true; // 執行「驗證並送出人物、來源、關聯、合併或私人筆記表單」的目前處理步驟
    } // 結束目前回呼、區塊或模組定義
    if(id==='fact-form') { // 依目前選項或狀態進入對應處理分支
      const body={dimension:f.get('dimension'),value:f.get('value'),description:f.get('description'),evidence_type:f.get('evidence_type'),source_experience_ids:f.getAll('source_ids'),confirmed:f.has('confirmed'),conflicts_with:f.get('conflicts_with')||null}; // 組合使用者明確提供的 API 提交內容
      await c.api('/people/'+form.dataset.person+'/facts',json('POST',{...body,request_id:c.requestId('fact:'+form.dataset.person,body)})); // 等待伺服器完成讀取或保存，再進入下一步
      await c.render(); document.querySelector('#account-dialog').close(); c.toast('人物資訊已確認；沒有額外增加積分。'); return true; // 執行「驗證並送出人物、來源、關聯、合併或私人筆記表單」的目前處理步驟
    } // 結束目前回呼、區塊或模組定義
    if(id==='person-goal-form' || id==='connection-form') { // 依目前選項或狀態進入對應處理分支
      const body=id==='person-goal-form'?{goal_id:f.get('goal_id'),label:f.get('label')}:{other_person_id:f.get('other_person_id'),label:f.get('label'),source_experience_ids:f.getAll('source_ids')}; // 組合使用者明確提供的 API 提交內容
      await c.api('/people/'+profile.person.id+(id==='person-goal-form'?'/goals':'/connections'),json('POST',{...body,request_id:c.requestId(id+profile.person.id,body)})); // 等待伺服器完成讀取或保存，再進入下一步
      await c.refresh(); await c.render(); document.querySelector('#account-dialog').close(); c.toast('關聯已保存。'); return true; // 重新讀取伺服器確認的資料，再更新畫面
    } // 結束目前回呼、區塊或模組定義
    if(id==='merge-form') { // 依目前選項或狀態進入對應處理分支
      const target=profile.interactions.find(e=>e.id===f.get('target')), sources=f.getAll('merge_sources').filter(x=>x!==target?.id); // 取得本次操作的控制項或合併主要事件
      if(!target || !sources.length) throw new Error('請選擇主要事件，以及至少另一筆要合併的互動。'); // 依目前選項或狀態進入對應處理分支
      const body={expected_revision:target.revision,source_event_ids:sources}; // 組合使用者明確提供的 API 提交內容
      await c.api('/interactions/'+target.id+'/merge',json('POST',{...body,request_id:c.requestId('merge:'+target.id,body)})); // 等待伺服器完成讀取或保存，再進入下一步
      c.state.dirty=false; await c.refresh(); await c.render(); c.toast('已合併為同一次互動；原始經歷與積分保留。'); return true; // 成功保存或明確導覽後清除未保存旗標
    } // 結束目前回呼、區塊或模組定義
    if(id==='theater-note-form') { // 依目前選項或狀態進入對應處理分支
      await c.api('/notes',json('POST',{person_id:form.dataset.person,kind:f.get('kind'),title:f.get('title'),content:f.get('content'),source_experience_ids:f.getAll('source_ids')})); // 等待伺服器完成讀取或保存，再進入下一步
      c.state.dirty=false; await c.refresh(); await c.render(); c.toast('私人筆記已保存，不計入真實成果。'); return true; // 成功保存或明確導覽後清除未保存旗標
    } // 結束目前回呼、區塊或模組定義
    return false; // 此事件不屬於人物模組，交回主程式處理
  } // 結束目前回呼、區塊或模組定義
  async function change(target) { // 處理互動分類與時間線類型篩選
    if(target.dataset.classify) { await c.api('/interactions/'+target.dataset.classify,json('PATCH',{expected_revision:Number(target.dataset.revision),kind:target.value})); c.state.dirty=false; await c.refresh(); await c.render(); return true; } // 成功保存或明確導覽後清除未保存旗標
    if(target.id==='interaction-filter') { document.querySelectorAll('.interaction-card').forEach(card=>card.hidden=!!target.value&&card.dataset.kind!==target.value); return true; } // 依目前選項或狀態進入對應處理分支
    return false; // 此事件不屬於人物模組，交回主程式處理
  } // 結束目前回呼、區塊或模組定義
  return {initialize,remember,restore,worldMini,renderPeople,renderPerson,renderTheater,renderEvidence,openPersonEditor,reviewExtras,reviewPayload,handleClick,handleSubmit,change}; // 回傳此步驟組合完成的結果
})(); // 結束目前回呼、區塊或模組定義
