'use strict'; // 啟用嚴格模式，及早發現未宣告變數等錯誤
const $ = (selector, root = document) => root.querySelector(selector); // 共用單一 DOM 元素查詢工具
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); // 將使用者文字轉義後才插入 HTML，避免被當成標記
const newId = () => crypto.randomUUID(); // 產生提交去重需要的隨機識別碼
const state = {me:null, world:null, csrf:'', draft:null, editingDraft:false, route:'', dirty:false, requests:new Map(), candidate:null, returnTo:null}; // 集中保存登入、世界、草稿、路由及未保存狀態
const names = {world:'我的世界', goals:'目標花園', record:'記錄經歷', history:'經歷收藏', people:'我的關係', notes:'私人小劇場', profile:'認識你', 'goal-new':'建立目標', birth:'新的開始', welcome:'歡迎'}; // 定義主頁面顯示名稱
const dayNames = ['一','二','三','四','五','六','日']; // 以週一到週日的順序顯示星期
let renderSequence = 0; // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
const renderControls = new Map(); // 保存切頁前各表單控制項原本的停用狀態
let toastTimer; // 保留短暫提示的關閉計時器
function lockRenderControls() { // 暫停舊畫面的表單輸入，避免切頁期間內容遭新畫面覆蓋
  $('#app').setAttribute('aria-busy','true'); // 向輔助工具標示畫面是否正在載入
  $('#app').querySelectorAll('input,textarea,select,button').forEach(node => { // 執行「暫停舊畫面的表單輸入，避免切頁期間內容遭新畫面覆蓋」的目前處理步驟
    if(!renderControls.has(node)) renderControls.set(node,node.disabled); // 第一次停用時記住原狀態，避免多次切頁覆蓋備份
    node.disabled=true; // 在新畫面就緒前暫停舊控制項操作
  }); // 結束目前回呼、區塊或模組定義
} // 結束目前回呼、區塊或模組定義

function toast(message) { // 顯示短暫操作提示並重設關閉計時器
  $('#toast').textContent = message; $('#toast').classList.add('visible'); // 執行「顯示短暫操作提示並重設關閉計時器」的目前處理步驟
  clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 4500); // 執行「顯示短暫操作提示並重設關閉計時器」的目前處理步驟
} // 結束目前回呼、區塊或模組定義
function showError(error) { // 在頁面與對話框顯示可閱讀的錯誤
  const fields = error.fields?.length ? ` 欄位：${error.fields.join('、')}` : ''; // 組合可閱讀的欄位錯誤提示
  $('#notice').innerHTML = `<div class="callout error-message">${esc(error.message + fields)}</div>`; // 執行「在頁面與對話框顯示可閱讀的錯誤」的目前處理步驟
  if ($('#account-dialog').open) { // 依目前選項或狀態進入對應處理分支
    const existing = $('#dialog-error'); // 尋找目前對話框內的錯誤訊息區
    if (existing) existing.textContent = error.message + fields; // 依目前選項或狀態進入對應處理分支
  } // 結束目前回呼、區塊或模組定義
} // 結束目前回呼、區塊或模組定義
async function api(path, options = {}) { // 統一送出 API、CSRF、JSON 與連線失敗處理
  const headers = {'X-CSRF-Token':state.csrf, ...options.headers}; // 為寫入請求帶上目前工作階段的 CSRF 代碼
  if (options.body && !(options.body instanceof FormData)) { // 依目前選項或狀態進入對應處理分支
    headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(options.body); // 序列化提交內容供 API 或請求指紋使用
  } // 結束目前回呼、區塊或模組定義
  let response; // 保存待讀取的伺服器回應
  try { response = await fetch('/api' + path, {...options, headers, credentials:'same-origin', cache:'no-store'}); } // 以同來源 Cookie 送出請求，停用 API 快取
  catch { throw new Error('目前無法連線。請保留內容，連線恢復後再送出；尚未確認保存成功。'); } // 顯示失敗原因，讓使用者保留內容並重試
  const body = response.status === 204 ? null : await response.json(); // 無內容回應不解析 JSON，其他回應讀取本文
  if (!response.ok) { // 依目前選項或狀態進入對應處理分支
    const error = new Error(body?.error?.message || '操作未完成，請重試。'); // 建立包含代碼、狀態與欄位資訊的錯誤
    error.code = body?.error?.code; error.status = response.status; error.fields = body?.error?.fields; // 執行「統一送出 API、CSRF、JSON 與連線失敗處理」的目前處理步驟
    if (response.status === 401 && !path.startsWith('/auth/')) { // 依目前選項或狀態進入對應處理分支
      state.me = null; state.world = null; state.csrf = ''; state.draft = null; state.dirty = false; // 成功保存或明確導覽後清除未保存旗標
      $('#account-dialog').close(); await render(); // 執行「統一送出 API、CSRF、JSON 與連線失敗處理」的目前處理步驟
    } // 結束目前回呼、區塊或模組定義
    throw error; // 執行「統一送出 API、CSRF、JSON 與連線失敗處理」的目前處理步驟
  } // 結束目前回呼、區塊或模組定義
  return body; // 回傳此步驟組合完成的結果
} // 結束目前回呼、區塊或模組定義
async function refresh() { // 重新讀取身分與世界資料
  state.me = await api('/auth/me'); state.csrf = state.me.csrf_token; // 等待伺服器完成讀取或保存，再進入下一步
  state.world = state.me.lumi_hatched ? await api('/state') : null; // 等待伺服器完成讀取或保存，再進入下一步
} // 結束目前回呼、區塊或模組定義
function requestId(scope, body) { // 相同內容沿用提交代碼，避免重送造成重複入帳
  const fingerprint = JSON.stringify(body); // 序列化提交內容供 API 或請求指紋使用
  if (state.requests.get(scope)?.fingerprint !== fingerprint) state.requests.set(scope, {fingerprint, id:newId()}); // 相同內容沿用同一提交識別碼，內容改變才換新代碼
  return state.requests.get(scope).id; // 相同內容沿用同一提交識別碼，內容改變才換新代碼
} // 結束目前回呼、區塊或模組定義
function navigate(route) { // 切換 hash 路由並先鎖住舊畫面
  state.dirty = false; $('#notice').innerHTML = ''; // 成功保存或明確導覽後清除未保存旗標
  lockRenderControls(); // 切頁開始前鎖住舊表單，避免非同步載入時遺失輸入
  if (location.hash.slice(1) === route) render().catch(showError); else location.hash = route; // 依目前選項或狀態進入對應處理分支
} // 結束目前回呼、區塊或模組定義
function link(route, label, style = 'secondary') { return `<a class="${style}" href="#${esc(route)}">${label}</a>`; } // 產生導覽連結並處理可存取名稱
function button(action, label, style = 'primary', attributes = '') { return `<button type="button" class="${style}" data-action="${action}" ${attributes}>${label}</button>`; } // 產生帶事件代碼的操作按鈕
function heading(title, subtitle, action = '') { return `<div class="heading"><div><div class="eyebrow">YOUR LITTLE UNIVERSE</div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div>${action}</div>`; } // 產生頁面標題與說明
function lumi() { return '<div class="hero-art" aria-label="目標蛋建立後誕生的 Lumi"><div class="ground"></div><div class="lumi"><i class="leaf"></i><i class="eyes"></i><i class="beak"></i><i class="wing"></i></div><span class="spark" aria-hidden="true">✧</span></div>'; } // 以 HTML 與 CSS 組合 Lumi 外觀
function empty(message, action = '') { return `<div class="empty"><span class="empty-icon">✳</span>${esc(message)}${action ? '<div class="space-top">' + action + '</div>' : ''}</div>`; } // 產生空資料提示與下一步入口
function localInput(iso = new Date().toISOString()) { // 依帳號時區轉成表單需要的當地時間
  const parts = new Intl.DateTimeFormat('sv-SE', {timeZone:state.me?.timezone || 'Asia/Taipei', year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(iso)); // 依帳號時區拆出日期與時間欄位
  const p = Object.fromEntries(parts.map(x => [x.type,x.value])); // 取得目前人物或日期欄位資料
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`; // 組合「依帳號時區轉成表單需要的當地時間」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function inputISO(value) { // 將當地時間換算 UTC，並拒絕不存在的當地時間
  const components = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/); // 檢查當地日期時間輸入格式並拆出數字
  if (!components) throw new Error('請填寫實際發生時間。'); // 依目前選項或狀態進入對應處理分支
  const desired = Date.UTC(...components.slice(1).map((v,i) => Number(v) - (i === 1 ? 1 : 0))); // 將輸入欄位組成待換算的日期數值
  let instant = desired; // 逐次校正當地時區對應的 UTC 時刻
  for (let i = 0; i < 3; i++) { // 執行「將當地時間換算 UTC，並拒絕不存在的當地時間」的目前處理步驟
    const rendered = localInput(new Date(instant).toISOString()); // 以帳號時區回算目前 UTC 候選時間
    const p = rendered.match(/\d+/g).map(Number); p[1]--; // 取得目前人物或日期欄位資料
    instant += desired - Date.UTC(...p); // 執行「將當地時間換算 UTC，並拒絕不存在的當地時間」的目前處理步驟
  } // 結束目前回呼、區塊或模組定義
  if (localInput(new Date(instant).toISOString()) !== value) throw new Error('此當地時間不存在，請重新選擇。'); // 依目前選項或狀態進入對應處理分支
  return new Date(instant).toISOString(); // 回傳此步驟組合完成的結果
} // 結束目前回呼、區塊或模組定義
function time(iso) { return new Intl.DateTimeFormat('zh-TW', {timeZone:state.me?.timezone || 'Asia/Taipei',dateStyle:'medium',timeStyle:'short'}).format(new Date(iso)); } // 以帳號時區顯示日期與時間
function options(items, selected, label = 'title') { return items.map(item => `<option value="${esc(item.id)}" ${item.id === selected ? 'selected' : ''}>${esc(item[label])}</option>`).join(''); } // 產生下拉選項並保留目前選取
function goalProgress(goal) { // 顯示各行動已確認的實際累計
  return goal.actions.map(a => `<div class="progress-row"><div class="progress-meta"><b>${esc(a.title)}</b><span>${esc(a.progress)} / ${esc(a.target)} ${esc(a.unit)}</span></div><div class="progress"><progress max="${esc(a.target)}" value="${esc(a.progress)}" aria-label="${esc(a.title)}進度"></progress></div></div>`).join(''); // 回傳此步驟組合完成的結果
} // 結束目前回呼、區塊或模組定義
function goalCard(goal) { // 產生目標摘要卡與詳情入口
  return `<div class="card"><div class="goal-top"><span class="egg ${goal.status === 'completed' ? 'completed' : ''}">${goal.status === 'completed' ? '✿' : '⌁'}</span><div><h3>${esc(goal.title)}</h3><p>${goal.status === 'completed' ? '已由你確認成果' : '每一小步，都在慢慢生長'}</p></div></div>${goalProgress(goal)}<div class="button-row space-top">${link('goal/' + goal.id,'查看目標 →','text-button')}<span class="tag">${goal.status === 'completed' ? '成果收藏' : '成長中'}</span></div></div>`; // 組合「產生目標摘要卡與詳情入口」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function navigation(route) { // 產生四主分頁並更新頁面標題
  const active = /^(person\/|theater\/|source\/|people)/.test(route)?'people':/^(record|review|history|private-notes)/.test(route)?'history':route; // 找出目前有效分頁或進行中目標
  $('#nav').innerHTML = state.me?.lumi_hatched ? [['world','⌂','世界'],['goals','♧','目標'],['history','▤','紀錄'],['people','◌','關係']].map(([key,icon,title]) => `<a class="nav-link ${active === key?'active':''}" href="#${key}"><span class="nav-icon" aria-hidden="true">${icon}</span>${title}</a>`).join('') : ''; // 執行「產生四主分頁並更新頁面標題」的目前處理步驟
  $('#page-label').textContent = names[route] || (route.startsWith('person/')?'人物檔案':route.startsWith('source/')?'資訊來源':route.startsWith('theater/')?'人物小劇場':route.startsWith('goal/')?'目標詳情':route==='private-notes'?'私人草稿箱':'核對經歷'); // 執行「產生四主分頁並更新頁面標題」的目前處理步驟
  $('#account-button').textContent = state.me?.name?.slice(0,1) || '○'; // 執行「產生四主分頁並更新頁面標題」的目前處理步驟
} // 結束目前回呼、區塊或模組定義
function welcomeView() { // 產生訪客開始與本機帳號登入入口
  return `<div class="welcome">${heading('把每一步，種成自己的世界。','不需要一次走很遠。先給想做的事，一個小小的開始。')}<section class="hero"><div class="hero-copy"><div class="eyebrow">A WORLD THAT GROWS WITH YOU</div><h2>從一顆目標蛋，<br>開始你的故事。</h2><p>記下真實的努力，收集成長的痕跡。建立第一個目標後，新的陪伴也將誕生。</p><div class="button-row">${button('guest','不用註冊，先開始 →')}${button('login-dialog','登入我的世界','text-button')}</div></div><div class="hero-art"><span class="egg">⌁</span><span class="spark">✧</span></div></section><p class="small muted">資料保存在此電腦的 Python 服務。訪客尚無帳號恢復保障；請用虛構內容測試。</p></div>`; // 組合「產生訪客開始與本機帳號登入入口」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function profileView() { // 產生個人介紹與時區表單
  return `<div class="narrow">${heading('先認識一下你。','這個世界，從你的名字與一點點自我介紹開始。')}<form id="profile-form" class="card"><div class="step-label"><span class="step-dot">1</span>認識你 → 建立目標 → 新的陪伴</div><div class="field"><label for="profile-name">希望怎麼稱呼你？</label><input id="profile-name" name="name" maxlength="80" required value="${esc(state.me.name)}" placeholder="你的名字或暱稱"></div><div class="field"><label for="bio">一點點關於你</label><textarea id="bio" name="bio" maxlength="2000" required placeholder="現在的你，在意什麼、想靠近什麼？">${esc(state.me.bio)}</textarea></div><div class="field"><label for="timezone">你的時區</label><input id="timezone" name="timezone" value="${esc(state.me.timezone)}" required></div><button class="primary">接著，建立第一個目標 →</button></form></div>`; // 組合「產生個人介紹與時區表單」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function goalForm() { // 產生目標、三項行動與每週規律表單
  return `<div class="narrow">${heading(state.me.lumi_hatched ? '種下下一個目標。' : '給努力，一個方向。','終極成果與日常行動分開。你決定什麼值得累積。')}<form id="goal-form" class="card"><div class="step-label"><span class="step-dot">2</span>目標與行動設定 → 確認建立目標蛋</div><div class="field"><label for="goal-title">目標名稱</label><input id="goal-title" name="title" maxlength="160" required placeholder="例如：完成我的第一個創作作品"></div><div class="field"><label for="outcome">你希望達成的終極成果</label><textarea id="outcome" name="outcome" maxlength="4000" required placeholder="具體描述你認為達標的樣子"></textarea></div><h3>設定三項可自主完成的行動</h3><p class="small muted">Lv1–3 是建立時的行動設定。本次貢獻仍由你每次手動確認。</p>${[0,1,2].map(i => `<fieldset><legend>行動 ${i+1}</legend><div class="field"><label for="action-title-${i}">行動名稱</label><input id="action-title-${i}" name="title${i}" required maxlength="160" placeholder="例如：練習、記錄、主動交流"></div><div class="form-grid"><div class="field"><label for="target-${i}">預期累計</label><input id="target-${i}" name="target${i}" type="number" min="0.000001" max="1000000000000" step="0.000001" required placeholder="例如：10"></div><div class="field"><label for="unit-${i}">計量單位</label><input id="unit-${i}" name="unit${i}" maxlength="20" required placeholder="小時／篇／次"></div></div><div class="field"><label for="level-${i}">預設養分等級</label><select id="level-${i}" name="level${i}">${[1,2,3].map(level => `<option value="${level}" ${level === i+1 ? 'selected' : ''}>Lv${level}</option>`).join('')}</select></div><div class="field"><span class="field-label">預計在哪些日子進行？（可複選）</span><div class="weekdays">${dayNames.map((name,day) => `<label class="day-check"><input type="checkbox" name="days${i}" value="${day}" ${[0,2,4].includes(day) ? 'checked' : ''}>週${name}</label>`).join('')}</div></div></fieldset>`).join('')}<div class="callout">行動累計不會自動完成終極成果。完成時需提供相關佐證，並由你親自確認。現在不啟用負向活力衰減。</div><button class="primary">確認設定，建立目標蛋 →</button></form></div>`; // 組合「產生目標、三項行動與每週規律表單」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function worldView() { // 產生 Lumi、目標、今日行動與待辦首頁
  const w = state.world, active = w.goals.filter(g => g.status === 'active'); // 讀取目前帳號的世界資料
  const weekday = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].indexOf(new Intl.DateTimeFormat('en-US',{timeZone:state.me.timezone,weekday:'short'}).format(new Date())); // 依帳號時區取得當天星期索引
  const today = active.flatMap(g => g.actions.filter(a => a.weekdays.includes(weekday)).map(a => ({...a,goal:g.title}))); // 列出今天依每週規律排定的行動
  return `${heading(`${state.me.name}，歡迎回來。`,'你的每一點努力，都讓這個世界更靠近你。',link('record','＋ 記下一次經歷','primary'))}<section class="hero"><div class="hero-copy"><span class="tag">一點一點，慢慢長大</span><h2 class="space-top">今天也一起，<br>照顧心裡的那顆種子。</h2><p>我是 Lumi。無論你走到哪裡，這個世界都會為你留一個位置。</p><div class="button-row">${link('record','記錄今天的一小步 →','primary')}${link('goals','看看我的目標','text-button')}</div></div>${lumi()}</section><div class="stats"><div class="stat"><span class="stat-icon">♧</span><div><b>${active.length}</b><small>正在成長的目標</small></div></div><div class="stat"><span class="stat-icon">▤</span><div><b>${w.experiences.length}</b><small>已確認的真實經歷</small></div></div><div class="stat"><span class="stat-icon">✧</span><div><b>${w.rewards.total}</b><small>累積積分 · 開發規則</small></div></div></div><div class="grid"><section><div class="section-title"><h2>我的目標花園</h2>${link('goals','查看全部 →','text-button')}</div><div class="stack">${active.length ? active.slice(0,2).map(goalCard).join('') : empty('這一段已經完成，也可以種下新的方向。',link('goal-new','建立新目標','primary'))}</div></section><section><div class="section-title"><h2>今天，可以做的一小步</h2><span class="tag">依你的排程</span></div><div class="card">${today.length ? today.map(a => `<div class="list-item"><div class="list-start"><span class="circle-icon">↗</span><div class="item-main"><h3>${esc(a.title)}</h3><p>${esc(a.goal)} · Lv${a.level}</p></div></div>${link('record','記錄','text-button')}</div>`).join('') : empty('今天沒有排定行動，依照自己的節奏就好。')}</div><div class="section-title space-top"><h2>待辦與下一步</h2></div><div class="card">${w.tasks.length ? w.tasks.map(t => `<label class="check-line"><input type="checkbox" data-task="${esc(t.id)}" ${t.done ? 'checked' : ''}>${esc(t.title)}</label>`).join('') : empty('確認經歷時，可以留下想做的下一步。')}</div></section></div>${w.drafts.length ? `<div class="callout space-top">有 ${w.drafts.length} 份已保存、未確認的草稿。 ${link('history','繼續上次的記錄 →','text-button')}</div>` : ''}`; // 組合「產生 Lumi、目標、今日行動與待辦首頁」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function personField(selected = null) { // 產生選填人物欄位與訪客升級入口
  return `<div class="field"><label for="person-id">關聯人物（選填）</label><select id="person-id" name="person_id"><option value="">不關聯人物</option>${options(state.world.people, selected, 'name')}${state.me.status === 'guest' ? '<option value="__upgrade">建立帳號，再新增／關聯人物…</option>' : ''}</select>${button('new-person','＋ 新增人物','text-button')}</div>`; // 組合「產生選填人物欄位與訪客升級入口」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function contributionFields(goal, values = []) { // 產生指定目標的人工貢獻欄位
  if (!goal) return '<p class="small muted">本次不關聯目標，仍可保存真實經歷與積分。</p>'; // 依目前選項或狀態進入對應處理分支
  return `<fieldset><legend>由你確認本次貢獻</legend><p class="small muted">可填部分完成；空白或 0 表示本次不累計該項。</p>${goal.actions.map(a => `<div class="field"><label for="quantity-${a.id}">${esc(a.title)}（${esc(a.unit)}）</label><input id="quantity-${a.id}" name="quantity-${esc(a.id)}" type="number" min="0" max="1000000000000" step="0.000001" value="${esc(values.find(v => v.action_id === a.id)?.quantity || '')}" placeholder="例如：0.5"></div>`).join('')}</fieldset>`; // 組合「產生指定目標的人工貢獻欄位」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function recordView() { // 產生原始經歷表單並帶入人物與目標上下文
  const d = state.editingDraft ? state.draft : null, active = state.world.goals.filter(g => g.status === 'active'); // 讀取此次編輯的經歷草稿
  const params = new URLSearchParams(location.hash.split('?')[1] || ''); // 解析目前路由的查詢參數
  const goalId = d ? d.goal_id : params.has('goal') ? params.get('goal') : params.has('person') ? null : active[0]?.id; // 保留目前選定目標的識別碼
  const goal = state.world.goals.find(g => g.id === goalId); // 讀取目前選定目標及其行動資料
  const personId = d ? d.person_id : params.get('person'); // 保留來源人物的識別碼
  return `<div class="narrow">${heading('把這一刻，記下來。','今天的小事、昨天的努力，都值得有一個位置。')}<form id="record-form" class="card"><div class="step-label"><span class="step-dot">1</span>原始紀錄 → 人工核對 → 正式保存</div><div class="field"><label for="raw-text">發生了什麼？</label><textarea id="raw-text" name="raw_text" maxlength="20000" required placeholder="用自己的話記下真實經過…">${esc(d?.raw_text || '')}</textarea></div><div class="field"><label for="occurred-at">實際發生時間 · ${esc(state.me.timezone)}</label><input id="occurred-at" name="occurred_at" type="datetime-local" required value="${esc(localInput(d?.occurred_at))}"><span class="small muted">可以補記過去的經歷。發生時間與現在的提交時間會分別保存。</span></div><div class="field"><label for="goal-id">關聯目標（選填）</label><select id="goal-id" name="goal_id"><option value="">不關聯目標</option>${options(state.world.goals, goalId)}</select></div>${personField(personId)}<div id="contribution-fields">${contributionFields(goal, d?.contributions)}</div><div class="callout">人物是選填的。若選擇人物操作，訪客需要先建立帳號；升級時保留這份內容。確認前不累計、不發放積分。</div><div class="button-row"><button class="primary" name="intent" value="review">保存草稿並進入核對 →</button><button class="secondary" name="intent" value="save">先存草稿</button></div></form></div>`; // 組合「產生原始經歷表單並帶入人物與目標上下文」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function reviewView(d) { // 產生人工核對頁，分開保存經歷與勾選人物更新
  const goal = state.world.goals.find(g => g.id === d.goal_id); // 讀取目前選定目標及其行動資料
  return `<div class="narrow">${heading('最後，由你來確認。','原始記錄保留不變。只把你確認的內容，放進真實經歷。')}<form id="review-form" class="card"><h3>原始記錄</h3><div class="raw-source">${esc(d.raw_text)}</div><p class="record-meta">實際發生於 ${esc(time(d.occurred_at))}</p><div class="field space-top"><label for="summary">確認後的摘要</label><textarea id="summary" name="summary" maxlength="20000" required>${esc(d.raw_text)}</textarea></div>${button('suggest','用原文建立整理候選','secondary')}<p class="small muted">目前使用本機手動整理，尚未連接外部 AI。</p><div id="candidate-panel"></div>${personField(d.person_id)}<div id="people-review-fields"></div>${contributionFields(goal, d.contributions)}<div class="field"><label for="followups">想留下的下一步（選填，每行一項）</label><textarea id="followups" name="tasks" placeholder="例如：明天再練習半小時"></textarea></div><div class="callout">${goal ? '關聯目標：' + esc(goal.title) + '。' : ''}貢獻與積分將由伺服器一次保存。相同提交重試不會重複入帳。開發設定：每筆確認經歷 ${state.world.policy.points_per_experience} 分。</div><div class="button-row"><button class="primary">我已核對，確認保存</button>${button('edit-current-draft','返回修改原始草稿','secondary')}</div></form></div>`; // 組合「產生人工核對頁，分開保存經歷與勾選人物更新」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function historyView() { // 列出已確認經歷與可接續草稿
  const w = state.world, filter = new URLSearchParams(location.hash.split('?')[1] || '').get('person'); // 讀取目前帳號的世界資料
  const experiences = filter ? w.experiences.filter(e => e.person_id === filter) : w.experiences; // 保存「experiences」供此流程接續使用
  return `${heading('收藏每一段真實。','所有已確認的經歷，都帶著原始記錄與發生時間。',link('record','＋ 新的經歷','primary'))}${w.drafts.length && !filter ? `<section class="space-bottom"><div class="section-title"><h2>等待你的確認</h2><span class="tag">草稿不計分</span></div><div class="card">${w.drafts.map(d => `<div class="list-item"><div class="item-main"><h3>${esc(d.raw_text.slice(0,65))}</h3><p>${esc(time(d.occurred_at))} · revision ${d.revision}</p></div>${link('review/' + d.id,'繼續核對 →','text-button')}</div>`).join('')}</div></section>` : ''}<div class="button-row space-bottom">${link('private-notes','私人筆記／草稿箱','secondary')}</div><div class="stack">${experiences.length ? experiences.map(e => `<article class="card"><div class="section-title"><span class="tag">已由你確認</span><span class="small muted">${esc(time(e.occurred_at))}</span></div><p class="record-content">${esc(e.summary)}</p><details><summary class="small muted">查看原始紀錄</summary><div class="raw-source space-top">${esc(e.raw_text)}</div></details><p class="record-meta">${esc(w.goals.find(g => g.id === e.goal_id)?.title || '獨立經歷')} · ${esc(w.people.find(p => p.id === e.person_id)?.name || '未關聯人物')}<br>提交保存於 ${esc(time(e.created_at))}</p></article>`).join('') : `<div class="card">${empty('這裡還沒有正式經歷。先記下一次真實行動吧。')}</div>`}</div>`; // 組合「列出已確認經歷與可接續草稿」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function notesView() { // 列出既有無人物私人草稿與筆記
  const selected = new URLSearchParams(location.hash.split('?')[1] || '').get('person'); // 保存「selected」供此流程接續使用
  return `${heading('先練習，再相遇。','這裡是你的私人筆記。模擬不是事實，草稿不代表已送達。')}<div class="grid"><form id="note-form" class="card"><div class="field"><label for="note-kind">這次想做什麼？</label><select id="note-kind" name="kind"><option value="preparation">見面前準備</option><option value="simulation">情境演練筆記</option><option value="message">傳達心意草稿</option></select></div>${personField(selected)}<div class="field"><label for="note-title">標題</label><input id="note-title" name="title" maxlength="160" required placeholder="下一次見面，我想…"></div><div class="field"><label for="note-content">私人內容</label><textarea id="note-content" name="content" required maxlength="20000" placeholder="寫下你的想法、準備或模擬台詞"></textarea></div><div class="callout">不會增加真實互動次數、行動進度或積分；也不會自動發送訊息。目前不提供生成式 AI 多輪演練。</div><button class="primary">保存私人筆記</button></form><div class="stack">${state.world.notes.length ? state.world.notes.map(n => `<article class="card note-card"><span class="tag gold">${{preparation:'私人準備',simulation:'模擬內容，非真人發言',message:'訊息草稿，尚未送出'}[n.kind]}</span><h3 class="space-top">${esc(n.title)}</h3><p class="record-content">${esc(n.content)}</p><p class="record-meta">${esc(time(n.created_at))}</p></article>`).join('') : `<div class="card">${empty('讓想說的話，先有一個安靜的位置。')}</div>`}</div></div>`; // 組合「列出既有無人物私人草稿與筆記」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
async function goalView(goalId) { // 讀取目標、排程預覽、佐證與成果確認頁
  const goal = await api('/goals/' + encodeURIComponent(goalId)); // 等待伺服器完成讀取或保存，再進入下一步
  const calendar = await api('/goals/' + encodeURIComponent(goalId) + '/calendar'); // 等待伺服器完成讀取或保存，再進入下一步
  return `${heading(goal.title,'每一次真實的投入，都會留在這裡。',link('record?goal='+goal.id,'記錄本次行動','primary'))}<div class="grid"><div class="stack"><section class="card"><span class="tag">${goal.status === 'completed' ? '已由你確認成果' : '正在成長'}</span><h2 class="space-top">終極成果</h2><p class="record-content">${esc(goal.outcome)}</p>${goalProgress(goal)}<div class="callout">以上是行動累計，不代表終極成果是否達成。你保有最後的確認權。</div></section><section class="card"><h3>接下來 28 天</h3><p class="small muted">星期規律預覽 · ${esc(state.me.timezone)} · 葉色格子代表當天有預定行動</p><div class="calendar-grid">${calendar.map(d => `<div class="calendar-day ${d.action_ids.length ? 'scheduled' : ''}">${esc(d.date.slice(5))}<small>${d.action_ids.length} 項</small></div>`).join('')}</div></section></div><section class="card"><h2>${goal.status === 'completed' ? '這段成果，已經收藏。' : '我已達成成果'}</h2><p class="small muted">提供拍攝或上傳的相關佐證，再由你手動確認。</p><div class="photo-grid">${goal.evidence.map(e => `<a href="/api/evidence/${esc(e.id)}" target="_blank" rel="noopener"><img src="/api/evidence/${esc(e.id)}" alt="${esc(e.filename)}">${esc(e.filename)}</a>`).join('')}</div>${goal.status === 'active' ? `<form id="upload-form" data-goal="${esc(goal.id)}"><div class="field"><label for="evidence-file">拍攝或選擇圖片</label><input id="evidence-file" name="file" type="file" accept="image/png,image/jpeg" required><span class="small muted">手機可在選擇圖片時使用相機。開發設定：PNG／JPEG，最大 ${Math.round(state.world.policy.max_upload_bytes / 1024 / 1024)} MiB。</span></div><button class="secondary">上傳佐證</button></form><form id="complete-form" class="space-top" data-goal="${esc(goal.id)}"><div class="field"><label for="reflection">這段旅程，想留下什麼？（選填）</label><textarea id="reflection" name="reflection" maxlength="4000"></textarea></div><label class="check-line"><input type="checkbox" name="confirmed" required>我已檢視相關佐證，親自確認終極成果已達成。</label><button class="primary" ${goal.evidence.length ? '' : 'disabled'}>確認完成並收藏成果</button>${goal.evidence.length ? '' : '<p class="small muted">請先成功上傳至少一份相關佐證。</p>'}</form>` : `<p class="record-content">${esc(goal.reflection || '每一步，都已經成為這個世界的一部分。')}</p><p class="record-meta">確認完成於 ${esc(time(goal.completed_at))}</p>${link('goal-new','種下下一個目標 →','primary')}`}</section></div>`; // 組合「讀取目標、排程預覽、佐證與成果確認頁」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
async function render() { // 依路由載入頁面，以序號防止舊回應覆蓋新畫面
  const sequence = ++renderSequence; // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
  state.renderGeneration = sequence; // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
  lockRenderControls(); // 切頁開始前鎖住舊表單，避免非同步載入時遺失輸入
  try { // 包住可能失敗的讀寫並交由錯誤分支處理
  let route = location.hash.slice(1) || 'world'; // 取得目前 hash 指定的目的頁面
  let params = new URLSearchParams(route.split('?')[1] || ''); // 解析目前路由的查詢參數
  if (route.startsWith('history?') && params.get('person')) { // 依目前選項或狀態進入對應處理分支
    route = 'person/' + params.get('person') + '?tab=history'; history.replaceState(null, '', '#' + route); // 執行「依路由載入頁面，以序號防止舊回應覆蓋新畫面」的目前處理步驟
  } else if (route.split('?')[0] === 'notes') { // 依目前選項或狀態進入對應處理分支
    route = params.get('person') ? 'theater/' + params.get('person') : 'private-notes'; history.replaceState(null, '', '#' + route); // 執行「依路由載入頁面，以序號防止舊回應覆蓋新畫面」的目前處理步驟
  } // 結束目前回呼、區塊或模組定義
  if (!state.me) route = 'welcome'; // 依目前選項或狀態進入對應處理分支
  else if (!state.me.lumi_hatched && !['profile','goal-new'].includes(route)) route = state.me.bio ? 'goal-new' : 'profile'; // 依目前選項或狀態進入對應處理分支
  if (state.me && state.me.lumi_hatched && route === 'welcome') route = 'world'; // 依目前選項或狀態進入對應處理分支
  const path = route.split('?')[0]; params = new URLSearchParams(route.split('?')[1] || ''); // 從路由分離出頁面路徑
  if (path !== 'record') state.editingDraft = false; // 依目前選項或狀態進入對應處理分支
  if (state.route) PeopleUI.remember(state.route, window.scrollY); // 依目前選項或狀態進入對應處理分支
  state.route = route; navigation(path); // 執行「依路由載入頁面，以序號防止舊回應覆蓋新畫面」的目前處理步驟
  let html; // 保存目前路由產生的頁面標記
  if (path === 'welcome') html = welcomeView(); // 依目前選項或狀態進入對應處理分支
  else if (path === 'profile') html = profileView(); // 依目前選項或狀態進入對應處理分支
  else if (path === 'goal-new') html = goalForm(); // 依目前選項或狀態進入對應處理分支
  else if (path === 'birth') html = `<div class="narrow"><section class="hero"><div class="hero-copy"><div class="eyebrow">A NEW BEGINNING</div><h1>目標蛋誕生了。<br>你好，我是 Lumi。</h1><p>你的方向，讓這個世界有了第一顆種子。從現在起，我們一起慢慢走。</p>${link('world','進入我的世界 →','primary')}</div>${lumi()}</section></div>`; // 依目前選項或狀態進入對應處理分支
  else if (path === 'world') html = worldView().replace('<div class="grid">', PeopleUI.worldMini()+'<div class="grid space-top">'); // 依目前選項或狀態進入對應處理分支
  else if (path === 'goals') html = `${heading('照顧你的目標花園。','每一顆蛋，都有自己的方向與成長節奏。',link('goal-new','＋ 新的目標','primary'))}<div class="grid-equal">${state.world.goals.map(goalCard).join('')}</div>`; // 依目前選項或狀態進入對應處理分支
  else if (path.startsWith('goal/')) html = await goalView(path.split('/')[1]); // 依目前選項或狀態進入對應處理分支
  else if (path === 'record') {state.returnTo=params.get('return')||null; html=recordView();} // 依目前選項或狀態進入對應處理分支
  else if (path.startsWith('review/')) { // 依目前選項或狀態進入對應處理分支
    const loaded = await api('/drafts/' + encodeURIComponent(path.split('/')[1])); // 等待伺服器完成讀取或保存，再進入下一步
    if(sequence !== renderSequence) return; // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
    state.draft = loaded; state.returnTo=params.get('return')||null; // 執行「依路由載入頁面，以序號防止舊回應覆蓋新畫面」的目前處理步驟
    html = state.draft.status === 'draft' ? reviewView(state.draft) : historyView(); // 執行「依路由載入頁面，以序號防止舊回應覆蓋新畫面」的目前處理步驟
    if(state.draft.status === 'draft') html=html.replace('<div id="people-review-fields"></div>', '<div id="people-review-fields">'+await PeopleUI.reviewExtras(state.draft.person_id)+'</div>'); // 依目前選項或狀態進入對應處理分支
  } // 結束目前回呼、區塊或模組定義
  else if (path === 'people') html = await PeopleUI.renderPeople(); // 依目前選項或狀態進入對應處理分支
  else if (path.startsWith('person/')) html = await PeopleUI.renderPerson(path.split('/')[1],params.get('tab')||'overview'); // 依目前選項或狀態進入對應處理分支
  else if (path.startsWith('source/')) html = await PeopleUI.renderEvidence(path.split('/')[1],path.split('/')[2]); // 依目前選項或狀態進入對應處理分支
  else if (path.startsWith('theater/')) html = await PeopleUI.renderTheater(path.split('/')[1],params.get('mode')||''); // 依目前選項或狀態進入對應處理分支
  else if (path === 'history') html = historyView(); // 依目前選項或狀態進入對應處理分支
  else if (path === 'private-notes') html = notesView(); // 依目前選項或狀態進入對應處理分支
  else html = worldView(); // 處理前述條件不成立時的替代流程
  if ((path === 'record' || path.startsWith('review/')) && state.returnTo) html=link(state.returnTo,'返回人物頁','text-button')+html; // 依目前選項或狀態進入對應處理分支
  if (sequence === renderSequence) {$('#app').innerHTML = html; state.dirty = false; PeopleUI.restore(route);} // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
  } finally { // 操作結束時還原按鈕或載入狀態
    if(sequence === renderSequence) { // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
      renderControls.forEach((disabled,node)=>{if(node.isConnected) node.disabled=disabled;}); // 載入結束後還原仍在頁面上的控制項並清空暫存
      renderControls.clear(); $('#app').setAttribute('aria-busy','false'); // 載入結束後還原仍在頁面上的控制項並清空暫存
    } // 結束目前回呼、區塊或模組定義
  } // 結束目前回呼、區塊或模組定義
} // 結束目前回呼、區塊或模組定義
function dialog(content) { $('#account-content').innerHTML = content + '<p id="dialog-error" class="small" role="alert"></p>'; if (!$('#account-dialog').open) $('#account-dialog').showModal(); } // 更新共用對話框並開啟模態視窗
function accountView(mode = 'account') { // 顯示帳號、升級或登入表單
  if (mode === 'account' && !state.me) mode = 'login'; // 依目前選項或狀態進入對應處理分支
  if (mode === 'account') { // 依目前選項或狀態進入對應處理分支
    dialog(`<h2 id="account-heading">${esc(state.me.name || '你的世界')}</h2><p class="account-state">${state.me.status === 'guest' ? '目前為訪客 · 尚無帳號恢復保障' : '本機帳號：' + esc(state.me.username)}</p><p class="small muted">資料保存在此電腦的 Python 服務。登出會撤銷這個工作階段，不會刪除已保存資料。${state.dirty ? '請先關閉此視窗，保存尚未送出的內容。' : ''}</p><div class="button-row">${state.me.status === 'guest' ? button('claim-dialog','建立帳號，保存世界') : ''}${button('login-dialog','登入其他帳號','secondary')}${button('logout','登出','danger', state.dirty ? 'disabled' : '')}</div>`); // 執行「顯示帳號、升級或登入表單」的目前處理步驟
  } else { // 處理前述條件不成立時的替代流程
    const claim = mode === 'claim'; // 判斷目前顯示建立帳號或登入表單
    dialog(`<h2 id="account-heading">${claim ? '為你的世界，建立帳號。' : '歡迎回到你的世界。'}</h2><p class="small muted">${claim ? '目標、經歷與草稿仍屬於原本的你；升級後可使用人物功能。' : '登入這台 Python 服務已建立的本機帳號。'}</p><form id="${claim ? 'claim' : 'login'}-form"><div class="field"><label for="username">本機帳號名稱</label><input id="username" name="username" autocomplete="username" required pattern="[a-zA-Z0-9_]{3,30}" placeholder="3–30 字英數或底線"></div><div class="field"><label for="password">密碼</label><input id="password" name="password" type="password" minlength="${claim ? 10 : 1}" maxlength="128" autocomplete="${claim ? 'new-password' : 'current-password'}" required placeholder="${claim ? '至少 10 個字元' : '你的密碼'}"></div><div id="guest-conflict"></div><button class="primary">${claim ? '建立帳號，繼續原本的操作' : '登入我的世界'}</button></form><div class="callout">本機開發驗證模式；沒有驗證信或密碼找回服務。正式部署須接入受管身份服務。</div>`); // 執行「顯示帳號、升級或登入表單」的目前處理步驟
  } // 結束目前回呼、區塊或模組定義
} // 結束目前回呼、區塊或模組定義
function formSnapshot() { // 暫存目前表單值與未保存狀態
  const form = $('#record-form') || $('#review-form') || $('#note-form') || $('#complete-form'); // 取得本次操作的表單
  return form ? {id:form.id, values:[...new FormData(form).entries()], dirty:state.dirty} : null; // 讀取使用者目前表單值，不直接推論人物資訊
} // 結束目前回呼、區塊或模組定義
async function refreshKeepingForm() { // 刷新資料後恢復原表單，保留升級與上傳前輸入
  const saved = formSnapshot(); await refresh(); await render(); // 重新讀取伺服器確認的資料，再更新畫面
  if (saved && $('#' + saved.id)) { // 依目前選項或狀態進入對應處理分支
    if (saved.id === 'record-form') { // 依目前選項或狀態進入對應處理分支
      const goalId = saved.values.find(([name]) => name === 'goal_id')?.[1]; // 保留目前選定目標的識別碼
      $('#contribution-fields').innerHTML = contributionFields(state.world.goals.find(g => g.id === goalId)); // 執行「刷新資料後恢復原表單，保留升級與上傳前輸入」的目前處理步驟
    } // 結束目前回呼、區塊或模組定義
    for (const [name,value] of saved.values) { // 執行「刷新資料後恢復原表單，保留升級與上傳前輸入」的目前處理步驟
      const input = document.getElementsByName(name)[0]; // 取得需要恢復值的原表單欄位
      if (input instanceof HTMLInputElement && input.type === 'checkbox') input.checked = true; // 依目前選項或狀態進入對應處理分支
      else if (input && !(input instanceof HTMLInputElement && input.type === 'file')) input.value = value; // 依目前選項或狀態進入對應處理分支
    } // 結束目前回呼、區塊或模組定義
    state.dirty = saved.dirty; // 執行「刷新資料後恢復原表單，保留升級與上傳前輸入」的目前處理步驟
  } // 結束目前回呼、區塊或模組定義
} // 結束目前回呼、區塊或模組定義
function contributions(form) { // 只送出非空且非零的人工行動貢獻
  return [...new FormData(form)].filter(([key,value]) => key.startsWith('quantity-') && value !== '' && Number(value) !== 0).map(([key,value]) => ({action_id:key.slice(9),quantity:value})); // 讀取使用者目前表單值，不直接推論人物資訊
} // 結束目前回呼、區塊或模組定義
async function saveDraft(form, review, destination = 'history') { // 新增或依版本修改草稿，成功後接續核對或返回
  const f = new FormData(form), body = {raw_text:f.get('raw_text'), occurred_at:inputISO(f.get('occurred_at')),goal_id:f.get('goal_id') || null,person_id:f.get('person_id') || null,contributions:contributions(form)}; // 讀取使用者目前表單值，不直接推論人物資訊
  if (body.person_id === '__upgrade') throw new Error('請先建立帳號後再選擇人物。'); // 依目前選項或狀態進入對應處理分支
  let result; // 保存伺服器已確認的操作結果
  if (state.editingDraft && state.draft?.status === 'draft') result = await api('/drafts/' + state.draft.id,{method:'PUT',body:{...body,expected_revision:state.draft.revision}}); // 等待伺服器完成讀取或保存，再進入下一步
  else result = await api('/experiences/drafts',{method:'POST',body}); // 等待伺服器完成讀取或保存，再進入下一步
  state.draft = result; state.editingDraft = false; state.dirty = false; await refresh(); // 成功保存或明確導覽後清除未保存旗標
  if (review) navigate('review/' + result.id + (state.returnTo?'?return='+encodeURIComponent(state.returnTo):'')); else {toast('草稿已保存至伺服器，尚未加分。'); navigate(destination);} // 依目前選項或狀態進入對應處理分支
} // 結束目前回呼、區塊或模組定義
function leaveDialog(route) { // 離開前提供保存草稿、繼續編輯或明確捨棄
  state.pendingRoute = route; // 執行「離開前提供保存草稿、繼續編輯或明確捨棄」的目前處理步驟
  dialog(`<h2 id="account-heading">離開前，留住這段內容。</h2><p class="small muted">目前有尚未保存的修改。你可以繼續編輯，或明確捨棄修改後離開。${$('#record-form') ? '這份原始記錄也可以先存成草稿。' : ''}</p><div class="button-row">${$('#record-form') ? button('save-and-leave','先存草稿並離開') : ''}${button('stay-on-form','繼續編輯','secondary')}${button('discard-and-leave','捨棄未保存修改並離開','danger')}</div>`); // 執行「離開前提供保存草稿、繼續編輯或明確捨棄」的目前處理步驟
} // 結束目前回呼、區塊或模組定義
document.addEventListener('click', event => { // 監聽點擊
  const anchor = event.target.closest('a[href^="#"]'); // 尋找使用者點選的站內 hash 連結
  if (anchor && state.dirty && anchor.hash.slice(1) !== state.route) { // 依目前選項或狀態進入對應處理分支
    event.preventDefault(); leaveDialog(anchor.hash.slice(1)); // 執行「處理click事件與對應的介面狀態」的目前處理步驟
  } else if(anchor && anchor.hash.slice(1) !== state.route) { lockRenderControls(); } // 切頁開始前鎖住舊表單，避免非同步載入時遺失輸入
}, true); // 結束目前回呼、區塊或模組定義
document.addEventListener('input', event => { if (event.target.closest('#app form:not([data-search])')) state.dirty = true; }); // 監聽輸入，標記未保存修改
document.addEventListener('change', async event => { // 監聽欄位變更
  try { // 包住可能失敗的讀寫並交由錯誤分支處理
    if (await PeopleUI.change(event.target)) return; // 依目前選項或狀態進入對應處理分支
    if (event.target.name === 'person_id' && $('#people-review-fields')) $('#people-review-fields').innerHTML = await PeopleUI.reviewExtras(event.target.value); // 依目前選項或狀態進入對應處理分支
    if (event.target.name === 'goal_id' && $('#record-form')) { // 依目前選項或狀態進入對應處理分支
      $('#contribution-fields').innerHTML = contributionFields(state.world.goals.find(g => g.id === event.target.value)); // 執行「處理change事件與對應的介面狀態」的目前處理步驟
    } // 結束目前回呼、區塊或模組定義
    if (event.target.name === 'person_id' && event.target.value === '__upgrade') {event.target.value = ''; accountView('claim');} // 依目前選項或狀態進入對應處理分支
    if (event.target.dataset.task) { // 依目前選項或狀態進入對應處理分支
      const result = await api('/tasks/' + event.target.dataset.task, {method:'PATCH',body:{done:event.target.checked}}); // 等待伺服器完成讀取或保存，再進入下一步
      const task = state.world.tasks.find(t => t.id === result.id); task.done = result.done; toast('待辦狀態已保存；不會重複增加行動進度。'); // 保存「task」供此流程接續使用
    } // 結束目前回呼、區塊或模組定義
  } catch (error) {showError(error); if (event.target.dataset.task) event.target.checked = !event.target.checked;} // 顯示失敗原因，讓使用者保留內容並重試
}); // 結束目前回呼、區塊或模組定義
document.addEventListener('click', async event => { // 監聽點擊
  const target = event.target.closest('[data-action],g[data-person],button[data-person]'); if (!target) return; // 取得本次操作的控制項或合併主要事件
  const action = target.dataset.action; target.disabled = true; // 讀取按鈕明確指定的操作代碼
  try { // 包住可能失敗的讀寫並交由錯誤分支處理
    if (await PeopleUI.handleClick(target)) return; // 依目前選項或狀態進入對應處理分支
    if (action === 'guest') {const me = await api('/auth/guest',{method:'POST'}); state.me = me; state.csrf = me.csrf_token; await refresh(); navigate('profile');} // 開始訪客旅程
    if (action === 'account') accountView(); // 開啟帳號設定
    if (action === 'claim-dialog') accountView('claim'); // 開啟升級帳號表單
    if (action === 'login-dialog') accountView('login'); // 開啟登入表單
    if (action === 'close-account') $('#account-dialog').close(); // 關閉對話框
    if (action === 'stay-on-form') {state.pendingRoute = null; $('#account-dialog').close();} // 保留輸入並繼續編輯
    if (action === 'discard-and-leave') {const route = state.pendingRoute; state.pendingRoute = null; $('#account-dialog').close(); navigate(route);} // 明確捨棄未保存內容後離開
    if (action === 'save-and-leave') {await saveDraft($('#record-form'), false, state.pendingRoute); state.pendingRoute = null; $('#account-dialog').close();} // 先保存草稿再前往目的地
    if (action === 'logout') { // 撤銷登入並清除目前帳號快取
      await api('/auth/logout',{method:'POST'}); $('#account-dialog').close(); state.me = null; state.world = null; state.csrf = ''; state.draft = null; state.candidate = null; state.requests.clear(); navigate('welcome'); // 等待伺服器完成讀取或保存，再進入下一步
    } // 結束目前回呼、區塊或模組定義
    if (action === 'new-person') { // 依訪客狀態升級或新增人物
      if (state.me.status === 'guest') accountView('claim'); // 依目前選項或狀態進入對應處理分支
      else PeopleUI.openPersonEditor(); // 處理前述條件不成立時的替代流程
    } // 結束目前回呼、區塊或模組定義
    if (action === 'edit-current-draft') {state.editingDraft = true; navigate('record');} // 帶回目前草稿進行修改
    if (action === 'suggest') { // 請求手動整理候選而不直接套用
      const result = await api('/drafts/' + state.draft.id + '/suggest',{method:'POST'}); state.candidate = result.summary; // 等待伺服器完成讀取或保存，再進入下一步
      $('#candidate-panel').innerHTML = `<div class="callout"><b>整理候選，尚未套用</b><p>${esc(result.notice || '')}</p><div class="raw-source">${esc(result.summary)}</div>${button('apply-candidate','套用到摘要','secondary')}${button('dismiss-candidate','保留目前摘要','text-button')}</div>`; // 執行「處理click事件與對應的介面狀態」的目前處理步驟
    } // 結束目前回呼、區塊或模組定義
    if (action === 'apply-candidate') {$('#summary').value = state.candidate; $('#candidate-panel').innerHTML = ''; state.candidate = null; state.dirty = true;} // 明確將候選放入可編輯摘要
    if (action === 'dismiss-candidate') {$('#candidate-panel').innerHTML = ''; state.candidate = null;} // 捨棄候選並保留現有摘要
  } catch (error) { showError(error); } // 顯示失敗原因，讓使用者保留內容並重試
  finally {target.disabled = false;} // 操作結束時還原按鈕或載入狀態
}); // 結束目前回呼、區塊或模組定義
document.addEventListener('submit', async event => { // 監聽表單提交
  const form = event.target; event.preventDefault(); // 取得本次操作的表單
  const submitter = event.submitter; const buttons = [...form.querySelectorAll('button')]; buttons.forEach(b => b.disabled = true); $('#notice').innerHTML = ''; // 取得觸發提交的按鈕並暫停重複提交
  try { // 包住可能失敗的讀寫並交由錯誤分支處理
    if (await PeopleUI.handleSubmit(form)) return; // 依目前選項或狀態進入對應處理分支
    const f = new FormData(form); // 讀取使用者目前表單值，不直接推論人物資訊
    if (form.id === 'profile-form') {await api('/profile',{method:'PUT',body:Object.fromEntries(f)}); await refresh(); navigate('goal-new');} // 等待伺服器完成讀取或保存，再進入下一步
    if (form.id === 'goal-form') { // 依目前選項或狀態進入對應處理分支
      const body = {title:f.get('title'),outcome:f.get('outcome'),actions:[0,1,2].map(i => ({title:f.get('title'+i),unit:f.get('unit'+i),target:f.get('target'+i),level:Number(f.get('level'+i)),weekdays:f.getAll('days'+i).map(Number)}))}; // 組合使用者明確提供的 API 提交內容
      const wasHatched = state.me.lumi_hatched; const goal = await api('/goals',{method:'POST',body:{...body,request_id:requestId('goal:create',body)}}); // 等待伺服器完成讀取或保存，再進入下一步
      state.draft = null; await refresh(); navigate(wasHatched ? 'goal/' + goal.id : 'birth'); // 重新讀取伺服器確認的資料，再更新畫面
    } // 結束目前回呼、區塊或模組定義
    if (form.id === 'record-form') await saveDraft(form, submitter?.value !== 'save'); // 依目前選項或狀態進入對應處理分支
    if (form.id === 'review-form') { // 依目前選項或狀態進入對應處理分支
      const body = {...PeopleUI.reviewPayload(form),expected_revision:state.draft.revision,summary:f.get('summary'),person_id:f.get('person_id') || null,contributions:contributions(form),tasks:String(f.get('tasks')).split('\n').map(x => x.trim()).filter(Boolean)}; // 組合使用者明確提供的 API 提交內容
      const result = await api('/drafts/' + state.draft.id + '/confirm',{method:'POST',body:{...body,request_id:requestId('confirm:' + state.draft.id,body)}}); // 等待伺服器完成讀取或保存，再進入下一步
      state.draft = null; state.candidate = null; const destination=state.returnTo||'history'; state.returnTo=null; await refresh(); navigate(destination); toast(`已確認保存，本次增加 ${result.points_awarded} 積分。`); // 重新讀取伺服器確認的資料，再更新畫面
    } // 結束目前回呼、區塊或模組定義
    if (form.id === 'claim-form') { // 依目前選項或狀態進入對應處理分支
      const me = await api('/auth/claim',{method:'POST',body:Object.fromEntries(f)}); state.csrf = me.csrf_token; // 等待伺服器完成讀取或保存，再進入下一步
      await refreshKeepingForm(); $('#account-dialog').close(); toast('帳號已建立，原本的世界與草稿都在。'); // 重新讀取伺服器確認的資料，再更新畫面
    } // 結束目前回呼、區塊或模組定義
    if (form.id === 'login-form') { // 依目前選項或狀態進入對應處理分支
      try { // 包住可能失敗的讀寫並交由錯誤分支處理
        const me = await api('/auth/login',{method:'POST',body:{username:f.get('username'),password:f.get('password'),discard_guest:f.get('discard_guest') === 'on'}}); // 等待伺服器完成讀取或保存，再進入下一步
        state.csrf = me.csrf_token; state.me = me; state.draft = null; state.candidate = null; state.requests.clear(); $('#account-dialog').close(); await refresh(); navigate('world'); // 重新讀取伺服器確認的資料，再更新畫面
      } catch (error) { // 顯示失敗原因，讓使用者保留內容並重試
        if (error.code === 'guest_conflict') $('#guest-conflict').innerHTML = '<div class="callout error-message">登入不會匯入或合併訪客資料。離開這個訪客身分後，可能無法再取得原世界。<label class="check-line"><input type="checkbox" name="discard_guest" required>我了解，仍要離開訪客世界並登入。</label></div>'; // 依目前選項或狀態進入對應處理分支
        throw error; // 執行「處理submit事件與對應的介面狀態」的目前處理步驟
      } // 結束目前回呼、區塊或模組定義
    } // 結束目前回呼、區塊或模組定義
    if (form.id === 'note-form') {const body = Object.fromEntries(f); body.person_id ||= null; await api('/notes',{method:'POST',body}); await refresh(); state.dirty = false; await render(); toast('私人筆記已保存，不計入真實成果。');} // 成功保存或明確導覽後清除未保存旗標
    if (form.id === 'upload-form') {await api('/goals/' + form.dataset.goal + '/evidence',{method:'POST',body:f}); await refreshKeepingForm(); toast('佐證已上傳並可回讀。');} // 等待伺服器完成讀取或保存，再進入下一步
    if (form.id === 'complete-form') { // 依目前選項或狀態進入對應處理分支
      const goal = await api('/goals/' + form.dataset.goal); // 等待伺服器完成讀取或保存，再進入下一步
      const body = {evidence_ids:goal.evidence.map(e => e.id),confirmed:f.get('confirmed') === 'on',reflection:f.get('reflection') || ''}; // 組合使用者明確提供的 API 提交內容
      await api('/goals/' + goal.id + '/complete',{method:'POST',body:{...body,request_id:requestId('complete:'+goal.id,body)}}); // 等待伺服器完成讀取或保存，再進入下一步
      await refresh(); state.dirty = false; await render(); toast('成果已由你確認，這段努力已收藏。'); // 成功保存或明確導覽後清除未保存旗標
    } // 結束目前回呼、區塊或模組定義
  } catch (error) {showError(error);} // 顯示失敗原因，讓使用者保留內容並重試
  finally {buttons.forEach(b => b.disabled = false);} // 操作結束時還原按鈕或載入狀態
}); // 結束目前回呼、區塊或模組定義
window.addEventListener('hashchange', () => { // 監聽路由變更並保護未保存內容
  const destination = location.hash.slice(1); // 保留確認完成或返回時的目的路由
  if (state.dirty && destination !== state.route) {history.replaceState(null, '', '#' + state.route); leaveDialog(destination); return;} // 依目前選項或狀態進入對應處理分支
  $('#notice').innerHTML = ''; render().catch(showError); // 執行「處理hashchange事件與對應的介面狀態」的目前處理步驟
}); // 結束目前回呼、區塊或模組定義
$('#account-dialog').addEventListener('close', () => {$('#account-content').replaceChildren();}); // 執行「處理hashchange事件與對應的介面狀態」的目前處理步驟
window.addEventListener('beforeunload', event => {if (state.dirty) {event.preventDefault(); event.returnValue = '';}}); // 監聽關閉頁面以保護未保存內容
window.addEventListener('offline', () => {$('#notice').innerHTML = '<div class="callout error-message">目前離線；尚未送出的內容沒有保存成功。請保留此頁，連線後再試。</div>';}); // 監聽離線狀態並提示保留輸入
async function start() { // 讀取既有身分後啟動畫面
  try {await refresh();} // 重新讀取伺服器確認的資料，再更新畫面
  catch (error) {if (error.status !== 401) showError(error);} // 顯示失敗原因，讓使用者保留內容並重試
  await render(); // 執行「讀取既有身分後啟動畫面」的目前處理步驟
} // 結束目前回呼、區塊或模組定義
PeopleUI.initialize({state,api,esc,link,button,heading,empty,time,options,toast,dialog,requestId,refresh,render,navigate,refreshKeepingForm}); // 將主程式工具注入人物模組，使兩者共用狀態
document.addEventListener('keydown', event => {if(event.target.matches('[data-person]') && ['Enter',' '].includes(event.key)) {event.preventDefault(); event.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}}); // 監聽鍵盤操作，讓星點支援 Enter 與空白鍵
start().catch(showError); // 啟動 App，未處理錯誤交由共用提示呈現
