'use strict'; // 啟用嚴格模式，及早發現未宣告變數等錯誤
const $ = (selector, root = document) => root.querySelector(selector); // 共用單一 DOM 元素查詢工具
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); // 將使用者文字轉義後才插入 HTML，避免被當成標記
const newId = () => crypto.randomUUID(); // 產生提交去重需要的隨機識別碼
const state = {me:null, world:null, csrf:'', draft:null, editingDraft:false, route:'', dirty:false, requests:new Map(), candidate:null, returnTo:null}; // 集中保存登入、世界、草稿、路由及未保存狀態
// Only explicitly abandoned owner IDs; never credentials or account A data.
const GuestLocalCleanup = (()=>{
  const key='lifeworld:abandoned-local-cleanup';
  const pending=new Set();let busy=false;
  try {for(const owner of JSON.parse(localStorage.getItem(key)||'[]'))if(typeof owner==='string'&&/^[a-zA-Z0-9-]{1,80}$/.test(owner))pending.add(owner);} catch {}
  const persist=()=>{try {localStorage.setItem(key,JSON.stringify([...pending]));return true;}catch{return false;}};
  async function retry(){
    if(busy)return false;busy=true;
    try {
      for(const owner of [...pending]){
        if(owner===state.me?.owner_id)continue;
        try {await MediaUI.clearOwner(owner);localStorage.removeItem('lifeworld:goal-draft:'+owner);pending.delete(owner);persist();}
        catch {toast('訪客本機草稿尚未清除；可在帳號選單重試，重新開啟或恢復連線也會重試。');}
      }
      return pending.size===0;
    } finally {busy=false;}
  }
  async function enqueue(owner){pending.add(owner);if(!persist())toast('瀏覽器無法保存清理重試，請保持此頁並在帳號選單重試。');return retry();}
  return {retry,enqueue};
})();
window.addEventListener('online',()=>GuestLocalCleanup.retry());
window.addEventListener('focus',()=>GuestLocalCleanup.retry());
const names = {world:'我的世界', goals:'目標花園', record:'記錄經歷', history:'經歷收藏', people:'我的關係', notes:'私人小劇場', profile:'認識你', 'goal-new':'建立目標', birth:'新的開始', welcome:'歡迎'}; // 定義主頁面顯示名稱
const dayNames = ['一','二','三','四','五','六','日']; // 以週一到週日的順序顯示星期
let renderSequence = 0; // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
const renderControls = new Map(); // 保存切頁前各表單控制項原本的停用狀態
let toastTimer; // 保留短暫提示的關閉計時器
let loadingTimer; // 延遲顯示等待回饋，避免快速切頁閃爍
function lockRenderControls() { // 暫停舊畫面的表單輸入，避免切頁期間內容遭新畫面覆蓋
  $('#app').setAttribute('aria-busy','true'); // 向輔助工具標示畫面是否正在載入
  if(!loadingTimer) loadingTimer=setTimeout(()=>{if($('#app').getAttribute('aria-busy')==='true') $('#app-loading').hidden=false;},200); // 慢速查詢超過二百毫秒時說明正在載入
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
  const message=ExperienceValidation.apiMessage(error); // 組合可閱讀的欄位錯誤提示
  $('#notice').innerHTML = `<div class="callout error-message">${esc(message)}</div>`; // 執行「在頁面與對話框顯示可閱讀的錯誤」的目前處理步驟
  if(['contribution_out_of_range','goal_setup_required','policy_required'].includes(error.code)&&$('#review-form')&&!document.querySelector('[data-review-goal-validation]:not([hidden])'))$('#notice').insertAdjacentHTML('beforeend',button('fix-experience-goal','返回第二步修正目標與數量','secondary'));
  if ($('#account-dialog').open) { // 依目前選項或狀態進入對應處理分支
    const existing = $('#dialog-error'); // 尋找目前對話框內的錯誤訊息區
    if (existing) existing.textContent = message; // 依目前選項或狀態進入對應處理分支
  } // 結束目前回呼、區塊或模組定義
  if ($('#source-dialog')?.open) $('#source-error').textContent=message; // 來源儲存失敗保持表單並顯示退路
} // 結束目前回呼、區塊或模組定義
async function api(path, options = {}) { // 統一送出 API、CSRF、JSON 與連線失敗處理
  if(state.googleUncertain && options.method && !['GET','HEAD'].includes(options.method) && path!=='/auth/external/status' && !(path==='/auth/external/exchange' && options.googleExchangeOnce))throw new Error('登入交換結果尚未核對，請先核對登入結果；原表單會保留。');
  const headers = {'X-CSRF-Token':state.csrf, ...options.headers}; // 為寫入請求帶上目前工作階段的 CSRF 代碼
  if (options.body && !(options.body instanceof FormData)) { // 依目前選項或狀態進入對應處理分支
    headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(options.body); // 序列化提交內容供 API 或請求指紋使用
  } // 結束目前回呼、區塊或模組定義
  delete options.googleExchangeOnce;
  let response; // 保存待讀取的伺服器回應
  try { response = await fetch('/api' + path, {...options, headers, credentials:'same-origin', cache:'no-store'}); } // 以同來源 Cookie 送出請求，停用 API 快取
  catch { throw new Error('目前無法連線。請保留內容，連線恢復後再送出；尚未確認保存成功。'); } // 顯示失敗原因，讓使用者保留內容並重試
  const body = response.status === 204 ? null : await response.json(); // 無內容回應不解析 JSON，其他回應讀取本文
  if (!response.ok) {
    if(response.status===429){const seconds=Number(response.headers.get('Retry-After'));if(Number.isFinite(seconds)&&seconds>0&&body?.error)body.error.message+=` 約 ${Math.ceil(seconds/60)} 分鐘後再試。`;} // 依目前選項或狀態進入對應處理分支
    const error = new Error(body?.error?.message || '操作未完成，請重試。'); // 建立包含代碼、狀態與欄位資訊的錯誤
    error.code = body?.error?.code; error.status = response.status; error.fields = body?.error?.fields; // 執行「統一送出 API、CSRF、JSON 與連線失敗處理」的目前處理步驟
    if(response.status===401 && state.me?.status==='guest') error.message+=' 訪客工作階段可能已到期或Cookie已清除；伺服器資料不會因此自動刪除，但沒有帳號時可能無法取回。';
    if (response.status === 401 && (!path.startsWith('/auth/') || path === '/auth/me')) { // 依目前選項或狀態進入對應處理分支
      DashboardUI.clear(); state.me = null; state.world = null; state.csrf = ''; state.draft = null; state.dirty = false; // 成功保存或明確導覽後清除未保存旗標
      $('#account-dialog').close(); await render(); // 執行「統一送出 API、CSRF、JSON 與連線失敗處理」的目前處理步驟
    } // 結束目前回呼、區塊或模組定義
    throw error; // 執行「統一送出 API、CSRF、JSON 與連線失敗處理」的目前處理步驟
  } // 結束目前回呼、區塊或模組定義
  // 只有已成功的回應才觸發音效，重送以回執去重；素材／播放失敗不影響交易。
  window.WorldAudio?.feedback(path,options.method,body,state.me?.owner_id);
  return body; // 回傳此步驟組合完成的結果
} // 結束目前回呼、區塊或模組定義
async function refresh() {
  if(!state.capabilities)state.capabilities=await api('/capabilities');
  // 同時保留Alpha入口能力與Dashboard跨帳號快照隔離，避免合併遺失任一安全規則。
  const previousOwner=state.me?.owner_id;
  state.me=await api('/auth/me');
  if(previousOwner!==state.me.owner_id){state.world=null;DashboardUI.clear();}
  state.csrf=state.me.csrf_token;
  state.world=state.me.lumi_hatched?await api('/state'):null;
  state.worldReadError=false;

} // 結束目前回呼、區塊或模組定義
function requestId(scope, body) { // 相同內容沿用提交代碼，避免重送造成重複入帳
  const fingerprint = JSON.stringify(body); // 序列化提交內容供 API 或請求指紋使用
  if (state.requests.get(scope)?.fingerprint !== fingerprint) state.requests.set(scope, {fingerprint, id:newId()}); // 相同內容沿用同一提交識別碼，內容改變才換新代碼
  return state.requests.get(scope).id; // 相同內容沿用同一提交識別碼，內容改變才換新代碼
} // 結束目前回呼、區塊或模組定義
function navigate(route) { // 切換 hash 路由並先鎖住舊畫面
  if(state.route) ConnectionsUI.remember(state.route,window.scrollY); // 在清除導覽旗標前保留尚未正式保存的核對修改
  state.dirty = false; $('#notice').innerHTML = ''; // 成功保存或明確導覽後清除未保存旗標
  lockRenderControls(); // 切頁開始前鎖住舊表單，避免非同步載入時遺失輸入
  if (location.hash.slice(1) === route) render().catch(showError); else location.hash = route; // 依目前選項或狀態進入對應處理分支
} // 結束目前回呼、區塊或模組定義
function link(route, label, style = 'secondary') { return `<a class="${style}" href="#${esc(route)}">${label}</a>`; } // 產生導覽連結並處理可存取名稱
function button(action, label, style = 'primary', attributes = '') { return `<button type="button" class="${style}" data-action="${action}" ${attributes}>${label}</button>`; } // 產生帶事件代碼的操作按鈕
function heading(title, subtitle, action = '') { return `<div class="heading"><div><div class="eyebrow">YOUR LITTLE UNIVERSE</div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div>${action}</div>`; } // 產生頁面標題與說明
function lumi(pose='idle') { return `<div class="hero-art lumi-art" aria-label="目標蛋建立後誕生的 Lumi"><img class="lumi-asset" data-lumi-art src="/static/art/softlife/lumi-hero.png" width="1536" height="1024" alt="Lumi 溫暖地陪伴你"><div data-lumi-fallback hidden><div class="ground"></div><div class="lumi"><i class="leaf"></i><i class="eyes"></i><i class="beak"></i><i class="wing"></i></div></div></div>`; } // 沿用已核實的 Soft Life 主視覺；載入失敗仍由 art.js 還原既有 CSS 角色，不改 Lumi 狀態。
function empty(message, action = '') { return `<div class="empty"><span class="empty-icon">✳</span>${esc(message)}${action ? '<div class="space-top">' + action + '</div>' : ''}</div>`; } // 產生空資料提示與下一步入口
function localInput(iso = new Date().toISOString(), zone = state.me?.timezone || 'Asia/Taipei') { // 依帳號時區轉成表單需要的當地時間
  const parts = new Intl.DateTimeFormat('sv-SE', {timeZone:zone, year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(iso)); // 依帳號時區拆出日期與時間欄位
  const p = Object.fromEntries(parts.map(x => [x.type,x.value])); // 取得目前人物或日期欄位資料
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`; // 組合「依帳號時區轉成表單需要的當地時間」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function inputISO(value, zone = state.me?.timezone || 'Asia/Taipei') { // 將當地時間換算 UTC，並拒絕不存在的當地時間
  const components = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/); // 檢查當地日期時間輸入格式並拆出數字
  if (!components) throw new Error('請填寫實際發生時間。'); // 依目前選項或狀態進入對應處理分支
  const desired = Date.UTC(...components.slice(1).map((v,i) => Number(v) - (i === 1 ? 1 : 0))); // 將輸入欄位組成待換算的日期數值
  let instant = desired; // 逐次校正當地時區對應的 UTC 時刻
  for (let i = 0; i < 3; i++) { // 執行「將當地時間換算 UTC，並拒絕不存在的當地時間」的目前處理步驟
    const rendered = localInput(new Date(instant).toISOString(), zone); // 以帳號時區回算目前 UTC 候選時間
    const p = rendered.match(/\d+/g).map(Number); p[1]--; // 取得目前人物或日期欄位資料
    instant += desired - Date.UTC(...p); // 執行「將當地時間換算 UTC，並拒絕不存在的當地時間」的目前處理步驟
  } // 結束目前回呼、區塊或模組定義
  if (localInput(new Date(instant).toISOString(), zone) !== value) throw new Error('此當地時間不存在，請重新選擇。'); // 依目前選項或狀態進入對應處理分支
  return new Date(instant).toISOString(); // 回傳此步驟組合完成的結果
} // 結束目前回呼、區塊或模組定義
function time(iso) { return new Intl.DateTimeFormat('zh-TW', {timeZone:state.me?.timezone || 'Asia/Taipei',dateStyle:'medium',timeStyle:'short'}).format(new Date(iso)); } // 以帳號時區顯示日期與時間
function options(items, selected, label = 'title') { return items.map(item => `<option value="${esc(item.id)}" ${item.id === selected ? 'selected' : ''}>${esc(item[label])}</option>`).join(''); } // 產生下拉選項並保留目前選取
function goalProgress(goal) { // 顯示各行動已確認的實際累計
  return goal.actions.map(a => `<div class="progress-row"><div class="progress-meta"><b>${esc(a.title)}</b><span>${esc(a.progress)} / ${esc(a.target)} ${esc(a.unit)}</span></div><div class="progress"><progress max="${esc(a.target)}" value="${esc(a.progress)}" aria-label="${esc(a.title)}進度"></progress></div></div>`).join(''); // 回傳此步驟組合完成的結果
} // 結束目前回呼、區塊或模組定義
function goalCard(goal) { // 產生目標摘要卡與詳情入口
  return `<div class="card"><div class="goal-top"><span class="egg ${goal.status==='completed'?'completed':''}">${goal.status==='completed'?'✿':'⌁'}</span><div><h3>${esc(goal.title)}</h3><p>${goal.deadline?'截止日：'+esc(goal.deadline)+' · '+esc(goal.schedule_timezone):(GoalsUI.open(goal)?'請補齊舊目標期限':'舊版歷史，未設定截止日')}</p></div></div>${goalProgress(goal)}<div class="button-row space-top">${link('goal/'+goal.id,goal.status==='awaiting_review'?'查看目標並回顧 →':'查看目標 →','text-button')}<span class="tag">${GoalsUI.labels[goal.status]}${goal.end_reason?' · '+(goal.end_reason==='expired'?'到期未完成':'提前結束'):''}</span></div></div>`; // 生命週期與截止日使用同一後端來源。
} // 結束目前回呼、區塊或模組定義
function navigation(route) { // 產生四主分頁並更新頁面標題
  $('#account-button').hidden=false; // 資料服務未開放也保留入口，明示降級而不是整個隱藏。
  $('.sidebar').classList.toggle('before-world',!state.me?.lumi_hatched); // 手機首次引導不顯示空白底部導覽。
  const active = /^(person\/|theater\/|source\/|people)/.test(route)?'people':/^(record|review|history|private-notes)/.test(route)?'history':route.startsWith('goal/')||route==='goal-new'?'goals':route; // 找出目前有效分頁或進行中目標
  $('#nav').innerHTML = state.me?.lumi_hatched ? [['world','⌂','世界'],['goals','♧','目標'],['history','▤','紀錄'],['people','◌','關係']].map(([key,icon,title]) => `<a class="nav-link ${active === key?'active':''}" href="#${key}"><span class="nav-icon" aria-hidden="true">${icon}</span>${title}</a>`).join('') : ''; // 執行「產生四主分頁並更新頁面標題」的目前處理步驟
  $('#page-label').textContent = names[route] || (route.startsWith('person/')?'人物檔案':route.startsWith('source/')?'資訊來源':route.startsWith('theater/')?'人物小劇場':route.startsWith('goal/')?'目標詳情':route==='private-notes'?'私人草稿箱':'核對經歷'); // 執行「產生四主分頁並更新頁面標題」的目前處理步驟
  $('#account-button').textContent = state.me?.status==='guest' ? '訪客模式' : (state.me?.name?.slice(0,1) || '○'); // 執行「產生四主分頁並更新頁面標題」的目前處理步驟
} // 結束目前回呼、區塊或模組定義
function welcomeView() {
  if(window.IntroEntry?.shouldOffer(state.me))return window.IntroEntry.choice(); // 介紹偏好只影響提示，不取代後端的新手狀態。
  if(state.capabilities?.public_gate_closed)return `<section class="hero"><div class="hero-copy"><h1>Life World</h1><p>讓真實的一小步，成為你的世界。</p><p>記下經歷、整理想法，讓目標與重要的人逐漸連起來。</p><div class="button-row">${button('entry-guest','不用註冊，先開始')}${button('entry-google','Google 登入','secondary')}${button('entry-email','Email 註冊／登入','secondary')}${button('entry-test','專用測試帳密登入','text-button')}</div><p class="callout" role="status">資料保存服務準備中，目前不接受個人資料。你可以查看入口流程；尚未建立帳號、登入或保存世界。</p><p>目標與三個習慣 · 經歷與人工確認 · 人物小劇場 · Lumi陪伴</p></div>${lumi('welcome')}</section>`;
  return `<div class="welcome">${heading('把每一步，種成自己的世界。','不需要一次走很遠。先給想做的事，一個小小的開始。')}<section class="hero"><div class="hero-copy"><div class="eyebrow">A WORLD THAT GROWS WITH YOU</div><h2>從一顆目標蛋，<br>開始你的故事。</h2><p>記下真實的努力，收集成長的痕跡。建立第一個目標後，新的陪伴也將誕生。</p><div class="button-row">${button('guest','不用註冊，先開始 →')}${button('login-dialog',state.capabilities?.google_login_available?'使用 Google 登入':'登入我的世界','text-button')}</div></div>${lumi('welcome')}</section>${!state.capabilities?.google_login_available?'<p class="callout" role="status">Google 登入尚未啟用。可先以訪客操作；既有帳號入口供授權測試帳號使用，尚未完成跨裝置 Google 恢復驗收。</p>':''}<p class="small muted">資料儲存於目前連線的服務。訪客尚無帳號恢復保障；請用虛構內容測試。</p></div>`; // 組合「產生訪客開始與本機帳號登入入口」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function profileView() { // 產生個人介紹與時區表單
  return `<div class="narrow">${heading('先認識一下你。','這個世界，從你的名字與一點點自我介紹開始。')}<form id="profile-form" class="card"><div class="step-label"><span class="step-dot">1</span>認識你 → 建立目標 → 新的陪伴</div><div class="field"><label for="profile-name">希望怎麼稱呼你？</label><input id="profile-name" name="name" maxlength="80" required value="${esc(state.me.name)}" placeholder="你的名字或暱稱"></div><div class="field"><label for="bio">一點點關於你</label><textarea id="bio" name="bio" maxlength="2000" required placeholder="現在的你，在意什麼、想靠近什麼？">${esc(state.me.bio)}</textarea></div><div class="field"><label for="timezone">你的時區</label><input id="timezone" name="timezone" value="${esc(state.me.timezone)}" required></div><button class="primary">接著，建立第一個目標 →</button></form></div>`; // 組合「產生個人介紹與時區表單」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function goalForm() { return GoalsUI.form(); } // 分步設定三個習慣與日期。
// 依目標生命週期選擇操作；資料不完整只降級呈現，不推斷正式狀態。
function homeGoalPanel(w,failed=false) {
  if(failed)return '<section class="card home-goal"><h2>目前挑戰</h2><p role="alert">暫時無法讀取最新資料，請重試。</p><button type="button" class="primary" data-home-retry>重新讀取</button></section>';
  const goals=w.goals.filter(GoalsUI.open);
  if(goals.length>1)return `<section class="card home-goal"><h2>請先整理目前挑戰</h2><p>有多個尚未結束的目標，請逐一檢視。</p>${link('goals','整理目標','primary')}</section>`;
  const g=goals[0];
  if(!g)return `<section class="card home-goal"><h2>讓故事有個起點</h2><p>先選一個方向，再設定三個重要習慣。</p>${link('goal-new','建立新目標','primary')}${link('goals','目標旅程','text-button')}</section>`;
  const vm=mapHomeHabitOverview(g),review=g.status==='awaiting_review',setup=g.status==='needs_setup';
  return `<section class="card home-goal"><span class="tag">${esc(GoalsUI.labels[g.status]||g.status)}</span><h2>${esc(g.title)}</h2><p>${esc(g.outcome||'')}</p><h3>我的三個習慣</h3>${vm.items.length?renderHomeHabitRows(vm,(id,body)=>`<a class="home-habit-row" href="#goal/${esc(g.id)}">${body}</a>`):'<p>三個習慣資料尚未完整，請進入目標補設定。</p>'}<p class="muted">排程代表打算做；投入以確認的經歷為準。</p><div class="button-row">${review||setup?link('goal/'+g.id,review?'查看並回顧':'補齊目標設定','primary'):link('record?goal='+g.id,'記錄新經歷','primary')}${review?link('record?goal='+g.id,'記錄新經歷','text-button'):''}${link('goal/'+g.id,'查看目前挑戰','text-button')}</div></section>`;
}
async function worldView() {
  // 首頁直接使用同次 /state 快照，不為摘要額外載入完整 Dashboard。
  const failed=!!state.worldReadError,w=failed?null:state.world;
  return heading(`${state.me.name}，歡迎回來。`,'每一段投入，都值得被留下。')+`<div class="home-overview"><section class="hero home-lumi"><div class="hero-copy"><h2>Lumi</h2><p>照自己的步調，慢慢前進。</p></div>${lumi()}<img class="world-cabinet" src="/static/art/cabinet.png" alt="" aria-hidden="true"><img class="world-plant" src="/static/art/plant.png" alt="" aria-hidden="true"></section>${homeGoalPanel(w,failed)}</div>`+(w?ConnectionsUI.worldMini()+`<section class="card space-top"><h2>待辦與下一步</h2>${w.tasks.length?w.tasks.map(t=>`<label class="check-line"><input type="checkbox" data-task="${esc(t.id)}" ${t.done?'checked':''}>${esc(t.title)}</label>`).join(''):empty('確認經歷時，可以留下想做的下一步。')}${w.drafts.length?`<p>有 ${w.drafts.length} 份未確認草稿。${link('history','繼續上次的記錄','text-button')}</p>`:''}${link('people?view=cards','人物劇場','text-button')}<p class="muted">選擇人物後進入私人小劇場。</p></section>`:'');
}

function personField(selected = null) { // 產生選填人物欄位與訪客升級入口
  return `<div class="field"><label for="person-id">關聯人物（選填）</label><select id="person-id" name="person_id"><option value="">不關聯人物</option>${options(state.world.people, selected, 'name')}${state.me.status === 'guest' ? '<option value="__upgrade">建立帳號，再新增／關聯人物…</option>' : ''}</select>${button('new-person','＋ 新增人物','text-button')}</div>`; // 組合「產生選填人物欄位與訪客升級入口」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function experiencePersonField(legacyPersonId=null,mode='record') { // 主要人物不自動等於參與；新流程以明確角色清單為準。
  const old=state.world.people.find(p=>p.id===legacyPersonId);
  return `<input type="hidden" id="person-id" name="person_id" value="">${mode!=='record'?'<p>這次有和誰互動，或在原文提到誰嗎？沒有可直接略過。</p>':''}${old?`<p class="callout">原先關聯：${esc(old.name)}。請在下方重新核對參與、直接互動或原文提及；不會自動推定出席。</p>`:''}${state.me.status==='registered'&&mode!=='record'?`<div class="button-row">${button('choose-experience-person','選擇既有人物','secondary')}${button('new-person','＋ 新增人物','text-button')}</div>`:''}`;
}
function contributionFields(goal, values = []) { // 單位只控制操作建議，不修改後端部分完成契約。
  return QuantityUI.fields(goal,values,esc);
} // 結束目前回呼、區塊或模組定義
function recordView() { // 產生原始經歷表單並帶入人物與目標上下文
  const d = state.editingDraft ? state.draft : null; // 讀取此次編輯的經歷草稿
  const params = new URLSearchParams(location.hash.split('?')[1] || ''); // 解析目前路由的查詢參數
  const goalId = d ? d.goal_id : params.has('goal') ? params.get('goal') : null; // 保留目前選定目標的識別碼
  const goal = state.world.goals.find(g => g.id === goalId); // 讀取目前選定目標及其行動資料
  const actionContext=!d&&goal?.actions.find(a=>a.id===params.get('action'));
  const requestedDate=params.get('date');
  const calendarDate=!d&&actionContext&&/^\d{4}-\d{2}-\d{2}$/.test(requestedDate||'')&&requestedDate>=goal.start_date&&requestedDate<=goal.deadline&&requestedDate<=goal.today?requestedDate:null;
  const personId = d ? d.person_id : params.get('person'); // 保留來源人物的識別碼
  return `<div class="narrow">${heading('記錄這一刻。','先留下真實經過，目標和人物稍後再補。')}<form id="record-form" class="card" ${calendarDate?'data-calendar-zone="'+esc(goal.schedule_timezone)+'"':''}><div class="step-label"><span class="step-dot">1</span>原始紀錄 → 人工核對 → 正式保存</div><div class="field"><label for="raw-text">發生了什麼？</label><textarea id="raw-text" name="raw_text" maxlength="20000" required placeholder="用自己的話記下真實經過…">${esc(d?.raw_text || '')}</textarea></div>${state.me.status==='guest'?'<p class="small muted">訪客使用文字記錄；登入後可使用拍照／影像與語音。</p>':'<div id="media-panel"></div>'}${calendarDate?`<div class="field"><label for="calendar-date">實際發生日期 · ${esc(goal.schedule_timezone)}</label><input id="calendar-date" name="calendar_date" type="date" required value="${esc(calendarDate)}"><label for="calendar-time">實際發生時間（請確認並填寫）</label><input id="calendar-time" name="calendar_time" type="time" required><input id="occurred-at" name="occurred_at" type="hidden" value=""><p>這是從月曆帶入的日期，請自行確認實際時間；沒有預填實際投入量。</p></div>`:`<div class="field"><label for="occurred-at">實際發生時間 · ${esc(state.me.timezone)}</label><input id="occurred-at" name="occurred_at" type="datetime-local" required value="${esc(localInput(d?.occurred_at||state.me.server_now))}"><span class="small muted">可以補記過去的經歷。發生時間與現在的提交時間會分別保存。</span></div>` }<div class="field"><label for="goal-id">關聯目標（選填）</label><select id="goal-id" name="goal_id"><option value="">不關聯目標</option>${options(state.world.goals, goalId)}</select></div>${experiencePersonField(personId)}${ConnectionsUI.editor(d?.story,'record')}<div id="contribution-fields">${actionContext?'<p class="callout">本次記錄：'+esc(actionContext.title)+'；請自行填寫實際投入量。</p>':''}${contributionFields(goal, d?.contributions)}</div>${state.me.status==='guest'?'<div class="callout">人物是選填的。若選擇人物操作，訪客需要先建立帳號；升級時保留這份內容。確認前不累計、不發放積分。</div>':''}<div class="button-row"><button class="primary" name="intent" value="review">保存草稿並進入核對 →</button><button class="secondary" name="intent" value="save">先存草稿</button></div></form></div>`; // 組合「產生原始經歷表單並帶入人物與目標上下文」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function reviewView(d) { // 產生人工核對頁，分開保存經歷與勾選人物更新
  const goal = state.world.goals.find(g => g.id === d.goal_id); // 讀取目前選定目標及其行動資料
  return `<div class="narrow">${heading('04｜檢視並確認。','原始記錄保留不變。只把你確認的內容，放進真實經歷。')}<form id="review-form" class="card"><details data-review-raw><summary>查看原始經歷與來源</summary><div class="raw-source">${esc(d.raw_text)}</div><p class="record-meta">實際發生於 ${esc(time(d.occurred_at))}</p><div id="media-panel"></div></details><div class="field space-top"><label for="summary">確認後的摘要</label><textarea id="summary" name="summary" maxlength="20000" required>${esc(ExperienceUI.summaryState(d).value)}</textarea></div>${ExperienceUI.summaryReview(d)}<details data-review-ai-controls><summary>整理方式 · 手動／AI（選用）</summary>${DraftAIUI.render()}</details><div id="candidate-panel"></div><div id="ai-people-panel"></div>${d.review?.person_candidates?.length||d.review?.birthday_candidates?.length||d.review?.employment_candidates?.length?'<div class="callout" data-review-candidate-status role="status">請點人物卡逐項核對或排除人物補充，最後確認才保存。</div>':''}<div id="experience-review-overview"></div><div id="experience-review-people-acceptance"></div><details data-review-people-editor><summary>修改本次人物關聯</summary>${experiencePersonField(d.person_id,'review')}${ConnectionsUI.editor(d.story,'review')}<div id="people-review-fields"></div></details><details data-review-quantities><summary>修改活動量</summary>${contributionFields(goal, d.contributions)}</details><details data-review-tasks><summary>新增或修改後續任務（選填）</summary><div class="field"><label for="followups">想留下的下一步（選填，每行一項）</label><textarea id="followups" name="tasks" placeholder="例如：明天再練習半小時">${esc(ExperienceUI.tasksState(d).join('\n'))}</textarea></div></details><div class="callout">只有最後確認才正式保存與計分。這次依目前規則可獲得 ${state.world.policy.points_per_experience} 積分；失敗後重試不重複計分。</div><div class="button-row"><button class="primary" ${d.review?.person_candidates?.length?'disabled':''}>我已核對，確認保存</button>${button('edit-current-draft','返回修改原始草稿','secondary')}${button('save-review-draft','保存核對草稿並離開','secondary')}</div></form></div>`; // 組合「產生人工核對頁，分開保存經歷與勾選人物更新」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function historyView() { // 列出已確認經歷與可接續草稿
  const w = state.world, filter = new URLSearchParams(location.hash.split('?')[1] || '').get('person'); // 讀取目前帳號的世界資料
  const experiences = filter ? w.experiences.filter(e => e.person_id === filter) : w.experiences; // 保存「experiences」供此流程接續使用
  return `${heading('收藏每一段真實。','所有已確認的經歷，都帶著原始記錄與發生時間。',link('record','＋ 新的經歷','primary'))}${w.drafts.length && !filter ? `<section class="space-bottom"><div class="section-title"><h2>等待你的確認</h2><span class="tag">草稿不計分</span></div><div class="card">${w.drafts.map(d => `<div class="list-item"><div class="item-main"><h3>${esc(d.raw_text.slice(0,65))}</h3><p>${esc(time(d.occurred_at))} · revision ${d.revision}</p></div>${link('review/' + d.id,'繼續核對 →','text-button')}<button type="button" class="text-button" data-action="delete-saved-draft" data-id="${esc(d.id)}">刪除草稿</button></div>`).join('')}</div></section>` : ''}<div class="button-row space-bottom">${link('private-notes','私人筆記／草稿箱','secondary')}<button type="button" class="text-button" data-action="retry-draft-media-cleanup">重試已刪草稿的本機素材清理</button></div><div class="stack">${experiences.length ? experiences.map(e => `<article class="card"><div class="section-title"><span class="tag">已確認並保存</span><span class="small muted">${esc(time(e.occurred_at))}</span></div><p class="record-content">${esc(e.summary)}</p><details><summary class="small muted">查看原始紀錄</summary><div class="raw-source space-top">${esc(e.raw_text)}</div></details>${link('media-sources/'+e.draft_id,'查看此裝置的素材','text-button')}<p class="record-meta">${esc(w.goals.find(g => g.id === e.goal_id)?.title || '獨立經歷')} · ${esc(w.people.find(p => p.id === e.person_id)?.name || '未關聯人物')}<br>提交保存於 ${esc(time(e.created_at))}</p>${state.me.status==='registered'?'<button type="button" class="text-button" data-cx="manage" data-id="'+esc(e.id)+'">整理／查看交會來源</button>':''}</article>`).join('') : `<div class="card">${empty('這裡還沒有正式經歷。先記下一次真實行動吧。')}</div>`}</div>`; // 組合「列出已確認經歷與可接續草稿」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
function notesView() { // 列出既有無人物私人草稿與筆記
  const selected = new URLSearchParams(location.hash.split('?')[1] || '').get('person'); // 保存「selected」供此流程接續使用
  return `${heading('先練習，再相遇。','這裡是你的私人筆記。模擬不是事實，草稿不代表已送達。')}<div class="grid"><form id="note-form" class="card"><div class="field"><label for="note-kind">這次想做什麼？</label><select id="note-kind" name="kind"><option value="preparation">見面前準備</option><option value="simulation">情境演練筆記</option><option value="message">傳達心意草稿</option></select></div>${personField(selected)}<div class="field"><label for="note-title">標題</label><input id="note-title" name="title" maxlength="160" required placeholder="下一次見面，我想…"></div><div class="field"><label for="note-content">私人內容</label><textarea id="note-content" name="content" required maxlength="20000" placeholder="寫下你的想法、準備或模擬台詞"></textarea></div><div class="callout">不會增加真實互動次數、行動進度或積分；也不會自動發送訊息。目前不提供生成式 AI 多輪演練。</div><button class="primary">保存私人筆記</button></form><div class="stack">${state.world.notes.length ? state.world.notes.map(n => `<article class="card note-card"><span class="tag gold">${{preparation:'私人準備',simulation:'模擬內容，非真人發言',message:'訊息草稿，尚未送出'}[n.kind]}</span><h3 class="space-top">${esc(n.title)}</h3><p class="record-content">${esc(n.content)}</p><p class="record-meta">${esc(time(n.created_at))}</p></article>`).join('') : `<div class="card">${empty('讓想說的話，先有一個安靜的位置。')}</div>`}</div></div>`; // 組合「列出既有無人物私人草稿與筆記」所需的畫面或提交資料
} // 結束目前回呼、區塊或模組定義
async function goalView(goalId,localEdit=false) { return GoalsUI.detail(goalId,localEdit); } // 目標與回顧使用同一份正式資料。
async function render(options={}) { // 依路由載入頁面，以序號防止舊回應覆蓋新畫面
  const sequence = ++renderSequence; // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
  state.renderGeneration = sequence; // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
  lockRenderControls(); // 切頁開始前鎖住舊表單，避免非同步載入時遺失輸入
  try { // 包住可能失敗的讀寫並交由錯誤分支處理
  ScheduleUI.leave();
  MediaUI.leave(); // 切頁前保存裝置草稿並停止麥克風，取消舊辨識回應。
  let route = location.hash.slice(1) || 'world'; // 取得目前 hash 指定的目的頁面
  if(!options.localGoalEdit && state.me && /^(world|goals|goal-new|goal\/)/.test(route)) {try{await refresh();}catch(error){if(route==='world'&&state.me&&![401,403].includes(error.status)){state.worldReadError=true;}else if(!(route==='goals'||route.startsWith('goal/'))||!state.me||!state.world||[401,403].includes(error.status))throw error;}if(sequence!==renderSequence)return;} // 跨日與另一視窗更新後，重新核對目標狀態。
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
  if (state.route) { PeopleUI.remember(state.route, window.scrollY); ConnectionsUI.remember(state.route, window.scrollY); } // 依目前選項或狀態進入對應處理分支
  ConnectionsUI.ensureOwner(); state.route = route; navigation(path); window.WorldAudio?.route(path); // 執行「依路由載入頁面，以序號防止舊回應覆蓋新畫面」的目前處理步驟
  let html; // 保存目前路由產生的頁面標記
  if (path === 'welcome') html = welcomeView(); // 依目前選項或狀態進入對應處理分支
  else if (path === 'profile') html = profileView(); // 依目前選項或狀態進入對應處理分支
  else if (path === 'goal-new') html = goalForm(); // 依目前選項或狀態進入對應處理分支
  else if (path === 'birth') html = BirthUI.view(lumi('welcome')); // 三次明確互動後才揭露既有 Lumi 呈現。
  else if (path === 'world') html = await worldView(); // 依目前選項或狀態進入對應處理分支
  else if (path === 'goals') html = await GoalsUI.list(); // 目前挑戰與歷史分區顯示。
  else if (path.startsWith('goal/')) html = await goalView(path.split('/')[1],options.localGoalEdit); // 依目前選項或狀態進入對應處理分支
  else if (path === 'record') {state.returnTo=params.get('return')||null; html=recordView();} // 依目前選項或狀態進入對應處理分支
  else if (path.startsWith('review/')) { // 依目前選項或狀態進入對應處理分支
    const loaded = await api('/drafts/' + encodeURIComponent(path.split('/')[1])); // 等待伺服器完成讀取或保存，再進入下一步
    if(sequence !== renderSequence) return; // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
    state.draft = loaded; state.returnTo=params.get('return')||null; // 執行「依路由載入頁面，以序號防止舊回應覆蓋新畫面」的目前處理步驟
    html = state.draft.status === 'draft' ? reviewView(state.draft) : historyView(); // 執行「依路由載入頁面，以序號防止舊回應覆蓋新畫面」的目前處理步驟
    if(state.draft.status === 'draft') html=html.replace('<div id="people-review-fields"></div>', '<div id="people-review-fields">'+await PeopleUI.reviewExtras(state.draft.person_id)+'</div>'); // 依目前選項或狀態進入對應處理分支
  } // 結束目前回呼、區塊或模組定義
  else if (path === 'persons') html = await PersonsUI.list(params);
  else if (path === 'persons-new') html = PersonsUI.createForm();
  else if (path.startsWith('persons-edit/')) html = await PersonsUI.editForm(path.split('/')[1]);
  else if (path.startsWith('persons/')) html = await PeopleUI.renderPerson(path.split('/')[1],params.get('tab')||'overview');
  else if (path === 'people') html = params.get('view')==='cards' ? await PeopleUI.renderPeople() : await ConnectionsUI.render(); // 交會取代星圖，收藏冊維持人物管理
  else if (path.startsWith('person/')) html = await PeopleUI.renderPerson(path.split('/')[1],params.get('tab')||'overview'); // 依目前選項或狀態進入對應處理分支
  else if (path.startsWith('source/')) html = await PeopleUI.renderEvidence(path.split('/')[1],path.split('/')[2]); // 依目前選項或狀態進入對應處理分支
  else if (path.startsWith('theater/')) html = await PeopleUI.renderTheater(path.split('/')[1],params.get('mode')||''); // 依目前選項或狀態進入對應處理分支
  else if (path.startsWith('media-sources/')) html = `<div class="narrow">${heading('此裝置的原始素材','素材未同步至其他裝置，這裡的編輯不會改動正式經歷。')}${link('history','返回經歷收藏','secondary')}<div id="media-panel"></div></div>`;
  else if (path === 'history') html = '<div id="media-local-drafts"></div>'+historyView(); // 依目前選項或狀態進入對應處理分支
  else if (path === 'private-notes') html = notesView(); // 依目前選項或狀態進入對應處理分支
  else html = await worldView(); // 處理前述條件不成立時的替代流程
  if ((path === 'record' || path.startsWith('review/')) && state.returnTo) html=link(state.returnTo,'返回人物頁','text-button')+html; // 依目前選項或狀態進入對應處理分支
  if (sequence === renderSequence) {
    $('#app').innerHTML = html;
    BirthUI.mount(); // 只為孵化頁綁定互動，不改寫伺服器的目標狀態。
    if(state.guestSaveNoticePending){guestSaveNotice();state.guestSaveNoticePending=false;}
    ExperienceUI.mount();DraftAIUI.mount(); ScheduleUI.mount(); state.dirty = false; PeopleUI.restore(route); ConnectionsUI.restore(route);ExperienceUI.refreshReviewSummary();
    const section=params.get('section');if(['gd-today','gd-week','gd-records'].includes(section)){document.getElementById(section)?.focus();document.getElementById(section)?.scrollIntoView({block:'start'});}
    if (state.me && path==='history') await MediaUI.renderDrafts(state.me.owner_id);
    if (state.me && $('#media-panel')) {
      const scope = path.startsWith('review/') || path.startsWith('media-sources/') ? 'draft:'+path.split('/')[1] : state.editingDraft && state.draft ? 'draft:'+state.draft.id : 'new:'+route;
      await MediaUI.mount({owner:state.me.owner_id, scope, readOnly:path!=='record', revision:scope.startsWith('draft:') && !path.startsWith('media-sources/') ? state.draft?.revision : null});
      ConnectionsUI.hydrateEditors();ExperienceUI.capture(); // 本機來源還原後同步人物區與分步狀態，不假設已上傳。
    }
  } // 恢復人物、故事及核對修改後才開放操作
  } finally { // 操作結束時還原按鈕或載入狀態
    if(sequence === renderSequence) { // 用本次渲染序號拒絕較舊非同步回應覆蓋畫面
      renderControls.forEach((disabled,node)=>{if(node.isConnected) node.disabled=disabled;}); // 載入結束後還原仍在頁面上的控制項並清空暫存
      renderControls.clear(); $('#app').setAttribute('aria-busy','false'); // 載入結束後還原仍在頁面上的控制項並清空暫存
      clearTimeout(loadingTimer); loadingTimer=null; $('#app-loading').hidden=true; // 成功或失敗都結束等待狀態
    } // 結束目前回呼、區塊或模組定義
  } // 結束目前回呼、區塊或模組定義
} // 結束目前回呼、區塊或模組定義
function dialog(content) { $('#account-content').innerHTML = content + '<p id="dialog-error" class="small" role="alert"></p>'; if (!$('#account-dialog').open) $('#account-dialog').showModal(); } // 更新共用對話框並開啟模態視窗
// 公開入口只呈現真實可用狀態；資料Gate關閉時不收集密碼、不送出登入或建世界請求。
function publicEntryView(mode='choose') {
  const intro='<p class="callout" id="entry-state" role="status">資料保存服務尚未開放，目前不會登入、建立帳號或保存資料。</p>';
  let content='';
  if(mode==='guest')content='<h2 id="account-heading">訪客體驗</h2><p>開始後會依序介紹自己、建立目標及三個習慣，再記錄經歷。</p><p>訪客世界須連線到保存服務；清除Cookie或登出後無法自行恢復。升級正式帳號後才能跨裝置回訪，既有世界不會只憑相同Email自動合併。</p><button class="primary" disabled>開始建立訪客世界</button>';
  else if(mode==='google')content='<h2 id="account-heading">Google 登入</h2><p>用Google帳號建立或回到自己的世界；也可在訪客體驗後明確選擇升級，保留原世界。</p><p>資料服務就緒後才開始Google驗證，目前不會開啟Google視窗或傳送登入資料。</p><button class="primary" disabled>繼續使用 Google 登入</button>';
  else if(mode==='email')content='<h2 id="account-heading">Email 註冊／登入</h2><p>一般Email帳密註冊與登入尚未開放。將在Email驗證、密碼重設與帳號恢復流程完成後提供；所有正式登入方式使用相同核心功能。</p><label>Email<input type="email" disabled autocomplete="off" placeholder="尚未開放，請勿輸入個人資料"></label><button disabled>建立或登入Email帳號</button>';
  else if(mode==='test')content='<h2 id="account-heading">專用測試帳密登入</h2><p>使用管理者提供的專用帳密。資料服務就緒後可操作同一套目標、AI與人物劇場；不會公開測試世界。</p><label>測試帳號<input id="entry-username" disabled autocomplete="off" placeholder="資料服務尚未開放"></label><label>密碼<input id="entry-password" type="password" disabled autocomplete="off" placeholder="目前不收集密碼"></label><button disabled>登入我的世界</button>';
  else content=`<h2 id="account-heading">進入你的世界</h2><div class="button-row">${button('entry-guest','不用註冊，先開始')}${button('entry-google','Google 登入','secondary')}${button('entry-email','Email 註冊／登入','secondary')}${button('entry-test','專用測試帳密登入','text-button')}</div>`;
  dialog(content+intro+`<div class="button-row">${button('entry-retry','重試服務連線','secondary')}${button('close-account','關閉入口','text-button')}</div>`);
}
async function retryPublicEntry() {
  const status=$('#entry-state');if(status){status.textContent='正在連線，請稍候…';status.setAttribute('aria-busy','true');}
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
  try {
    const response=await fetch('/ready',{credentials:'same-origin',cache:'no-store',signal:controller.signal});
    if(!response.ok)throw new Error('not_ready');
    const capabilities=await api('/capabilities',{signal:controller.signal});
    if(capabilities.public_gate_closed)throw new Error('not_open');
    state.capabilities=capabilities;$('#account-dialog').close();await render();toast('服務已可連線，請重新選擇登入方式。');
  } catch {if(status)status.textContent='服務尚未開放或暫時無法連線。沒有建立帳號、訪客世界或保存任何資料，可稍後重試。';}
  finally {clearTimeout(timer);status?.setAttribute('aria-busy','false');}
}
function accountView(mode = 'account') { // 顯示帳號、升級或登入表單
  if(state.capabilities?.public_gate_closed){publicEntryView();return;}
  const aiUsageControl=state.me?.status==='registered' && state.capabilities?.ai_available?button('ai-usage','AI 額度與收據','text-button'):'';
  const memoryControl=state.me && state.capabilities?.relationship_memory_available?button('memory-settings','個人化資料與記憶','text-button'):'';
  if (state.capabilities?.google_login_available && mode!=='test-login' && !(mode==='account' && state.me?.status==='registered')) {
    const upgrade=state.me?.status==='guest' && mode!=='login';
    const consent=!upgrade && (!state.me || state.me.status==='guest');
    dialog(`<h2 id="account-heading">${upgrade?'保存或切換你的世界':'登入以前的世界'}</h2><p>${upgrade?'保存目前世界會綁定Google，保留原本目標、草稿、經歷、進度與獎勵。':'只登入已綁定的Google世界；找不到時不會建立新帳號或放棄訪客資料。'}</p>${consent?'<p class="callout">兩個世界不會合併。成功切換後，原訪客世界將進入待清除程序，至少14天後才符合永久清除條件；目前不提供恢復功能。</p><label><input id="google-discard" type="checkbox">我確認成功登入後放棄目前訪客世界及其本機媒體草稿</label>':''}<button type="button" class="primary" data-action="google-start" data-mode="${upgrade?'upgrade':'login'}">${upgrade?'保存目前世界':'繼續使用 Google 登入'}</button>${upgrade?button('google-login-existing','登入以前的世界','secondary'):''}<p id="google-status" role="status" aria-live="polite">尚未開始驗證，訪客資料保持不變。</p><div id="google-button"></div>${button('google-cancel','取消Google驗證','text-button')}${button('google-reconcile','核對登入結果','text-button')}${state.capabilities?.password_login_available?button('test-login-dialog','測試帳號登入','secondary'):''}${memoryControl}${aiUsageControl}${button('retry-guest-cleanup','重試清除已離開的訪客草稿','text-button')}${state.me?button('logout','登出','secondary'):''}`);
    return;
  }
  if(mode==='test-login'){if(!state.capabilities?.password_login_available)throw new Error('測試帳號登入尚未啟用。');mode='login';}
  const alpha=state.capabilities?.access_mode==='public_alpha';
  if(alpha && mode==='claim')throw new Error('Alpha不開放公開註冊或訪客升級。');
  if(alpha && mode==='login' && !state.capabilities.accounts_available)throw new Error('Alpha預建帳號登入尚未啟用。');
  if (mode === 'account' && !state.me) mode = 'login'; // 依目前選項或狀態進入對應處理分支
  if (mode === 'account') { // 依目前選項或狀態進入對應處理分支
    dialog(`<h2 id="account-heading">${esc(state.me.name || '你的世界')}</h2><p class="account-state">${state.me.status === 'guest' ? '訪客模式 · 此瀏覽器工作階段保存' : (state.me.username?'Life World 帳號：'+esc(state.me.username):'已登入 · 私人世界保存中')}</p><p class="small muted">資料儲存於目前連線的服務。登出會撤銷這個工作階段，不會刪除已保存資料。${state.dirty ? '登出時可選擇保存草稿、捨棄未保存修改或繼續編輯。' : ''}</p><div class="button-row">${state.me.status === 'guest' && state.capabilities?.registration_available ? button('claim-dialog','建立帳號，保存世界') : ''}${button('login-dialog','登入其他帳號','secondary')}<label><input id="clear-local-media" type="checkbox">登出後清除此瀏覽器目前世界的媒體草稿（不刪除伺服器資料）</label>${button('logout','登出','danger', '')}${memoryControl}${aiUsageControl}</div>`); // 執行「顯示帳號、升級或登入表單」的目前處理步驟
  } else { // 處理前述條件不成立時的替代流程
    const claim = mode === 'claim'; // 判斷目前顯示建立帳號或登入表單
    dialog(`<h2 id="account-heading">${claim ? '為你的世界，建立帳號。' : '歡迎回到你的世界。'}</h2><p class="small muted">${claim ? '目標、經歷與草稿仍屬於原本的你；升級後可使用人物功能。' : (alpha?'使用管理者提供的預建帳號；不會自動建立新帳號。':'登入目前服務已建立的帳號。')}</p><form id="${claim ? 'claim' : 'login'}-form"><div class="field"><label for="username">${alpha?'預建帳號名稱':'Life World 帳號名稱'}</label><input id="username" name="username" autocomplete="username" required pattern="[a-zA-Z0-9_]{3,30}" placeholder="3–30 字英數或底線"></div><div class="field"><label for="password">密碼</label><input id="password" name="password" type="password" minlength="${claim ? 10 : 1}" maxlength="128" autocomplete="${claim ? 'new-password' : 'current-password'}" required placeholder="${claim ? '至少 10 個字元' : '你的密碼'}"></div><div id="guest-conflict"></div><button class="primary">${claim ? '建立帳號，繼續原本的操作' : '登入我的世界'}</button></form><div class="callout">${alpha?'僅預建帳號可跨裝置回讀；忘記密碼請聯絡管理者，沒有自助註冊或密碼找回。':'目前沒有驗證信或自助密碼找回服務；需要協助時請聯絡管理者。'}</div>`); // 執行「顯示帳號、升級或登入表單」的目前處理步驟
  } // 結束目前回呼、區塊或模組定義
} // 結束目前回呼、區塊或模組定義
let googleSdkPromise;
async function completeGoogleTransition(attempt,me,receipt) {
  // 只依後端綁定新Session的收據清理；不憑畫面跳轉或不同owner猜測交換已提交。
  if(receipt.status!=='committed' || receipt.source_owner_id!==attempt.sourceOwner || receipt.owner_id!==me.owner_id || receipt.mode!==attempt.mode)throw new Error('登入收據無法核對，請保留原表單。');
  const sameOwner=me.owner_id===attempt.sourceOwner;
  if(attempt.mode==='upgrade' && !sameOwner)throw new Error('保存世界的Owner不一致，已停止畫面切換。');
  if(!sameOwner && attempt.sourceGuest && (!attempt.discard || !receipt.guest_abandoned))throw new Error('沒有已提交的訪客放棄收據，已停止切換。');
  state.csrf=me.csrf_token;state.me=me;state.googleUncertain=false;
  if(sameOwner){
    // 不重新render或navigate：完整保留目前路由、未保存欄位、媒體及草稿狀態。
    await refresh();ExperienceUI.refreshCapabilities();navigation(state.route);state.googleAttempt=null;$('#account-dialog').close();toast('已保存目前世界，原本進度與尚未完成的表單都保留。');return;
  }
  lockRenderControls();state.world=null;state.draft=null;state.candidate=null;state.aiPeople=[];state.requests.clear();DashboardUI.clear();
  await refresh();state.googleAttempt=null;$('#account-dialog').close();navigate(state.me.lumi_hatched?'world':'profile');
  if(receipt.guest_abandoned && attempt.sourceOwner!==me.owner_id)GuestLocalCleanup.enqueue(attempt.sourceOwner).catch(()=>toast('訪客本機素材清理尚未完成，可於帳號選單重試。'));
}
async function reconcileGoogleTransition(attempt) {
  // 未知結果先讀Cookie目前的Session，再查同Session收據；不自動重送exchange。
  const response=await fetch('/api/auth/me',{credentials:'same-origin',cache:'no-store'});
  if(!response.ok)throw new Error('目前無法核對登入Session，請保留原表單並稍後核對。');
  const me=await response.json();state.csrf=me.csrf_token;
  const receipt=await api('/auth/external/status',{method:'POST',body:{challenge_id:attempt.challenge.challenge_id}});
  if(receipt.status==='committed'){await completeGoogleTransition(attempt,me,receipt);return true;}
  if(me.owner_id!==attempt.sourceOwner)throw new Error('目前Session與原世界不一致，請先核對帳號；不會清除資料。');
  if(!attempt.definitive && !receipt.expired)throw new Error('交換可能仍在處理，尚無可確認結果；請稍後再次核對，不要重送。');
  state.me=me;state.googleUncertain=false;attempt.exchangeStarted=false;state.googleAttempt=null;$('#google-button')?.replaceChildren();if($('#google-discard'))$('#google-discard').disabled=false;return false;
}
async function startGoogleLogin(mode) {
  if(state.googleUncertain)throw new Error('請先核對上一次登入結果，勿重複驗證。');
  const discard=!!$('#google-discard')?.checked;
  if(mode==='login' && (!state.me || state.me.status==='guest') && !discard)throw new Error('請先確認放棄訪客資料與至少14天清除告知，才開始驗證。');
  const attempt={mode,discard,sourceOwner:state.me?.owner_id,sourceGuest:!state.me || state.me.status==='guest',exchangeStarted:false};state.googleAttempt=attempt;
  $('#google-status').textContent='正在準備Google驗證；尚未切換或清除資料。';
  if(!state.me){const me=await api('/auth/guest',{method:'POST'});state.me=me;state.csrf=me.csrf_token;attempt.sourceOwner=me.owner_id;}
  if($('#google-discard'))$('#google-discard').disabled=true;
  attempt.challenge=await api('/auth/external/challenge',{method:'POST',body:{mode,discard_guest:discard}});
  if(state.googleAttempt!==attempt || !$('#account-dialog').open)return;
  googleSdkPromise ||= new Promise((resolve,reject)=>{
    if(window.google?.accounts?.id){resolve();return;}
    const script=document.createElement('script');script.src='https://accounts.google.com/gsi/client';script.async=true;
    script.onload=resolve;script.onerror=()=>{script.remove();googleSdkPromise=null;reject(new Error('Google驗證服務暫時不可用，原訪客世界與表單保持。'));};document.head.appendChild(script);
  });
  await googleSdkPromise;if(state.googleAttempt!==attempt || !$('#account-dialog').open)return;
  google.accounts.id.initialize({client_id:attempt.challenge.client_id,nonce:attempt.challenge.nonce,auto_select:false,ux_mode:'popup',callback:async response=>{
    if(state.googleAttempt!==attempt || !$('#account-dialog').open || attempt.exchangeStarted)return;
    if(!response.credential){$('#google-status').textContent='Google驗證未完成或已取消，原訪客資料保持。';return;}
    attempt.exchangeStarted=true;state.googleUncertain=true;$('#google-status').textContent='正在交換身分，請稍候；結果不明時會先核對Session。';
    try{
      // exchange本身僅送出一次；狀態未明期間其餘寫入維持阻擋。
      const result=await api('/auth/external/exchange',{method:'POST',googleExchangeOnce:true,body:{challenge_id:attempt.challenge.challenge_id,credential:response.credential}});
      attempt.definitive=true;state.googleUncertain=true;state.csrf=result.csrf_token;
      await reconcileGoogleTransition(attempt);
    }catch(error){
      attempt.definitive=attempt.definitive || Number.isInteger(error.status);state.googleUncertain=true;
      try{if(await reconcileGoogleTransition(attempt))return;}catch{}
      if($('#dialog-error'))$('#dialog-error').textContent=error.message+(state.googleUncertain?' 結果尚未確認，請點「核對登入結果」，不要重送。':' 原訪客世界與表單保留，尚未切換。');
    }
  }});
  google.accounts.id.renderButton($('#google-button'),{type:'standard',theme:'outline',size:'large'});
  $('#google-status').textContent='請完成Google驗證；關閉Google視窗不會放棄訪客世界。';
}

function formSnapshot() { // 暫存目前表單值與未保存狀態
  const form = $('#record-form') || $('#review-form') || $('#note-form') || $('#complete-form'); // 取得本次操作的表單
  return form ? {id:form.id, values:[...new FormData(form).entries()], dirty:state.dirty} : null; // 讀取使用者目前表單值，不直接推論人物資訊
} // 結束目前回呼、區塊或模組定義
async function refreshKeepingForm() { // 刷新資料後恢復原表單，保留升級與上傳前輸入
  const saved = formSnapshot(), storySaved=ConnectionsUI.snapshotEditor(); await refresh(); await render(); // 升級或新增人物前保留動態角色列
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
    ConnectionsUI.restoreEditor(storySaved); // 不遺失尚未確認的提及及多人選取
  } // 結束目前回呼、區塊或模組定義
} // 結束目前回呼、區塊或模組定義
function contributions(form) { // 只送出非空且非零的人工行動貢獻
  return [...new FormData(form)].filter(([key,value]) => key.startsWith('quantity-') && value !== '' && Number(value) !== 0).map(([key,value]) => ({action_id:key.slice(9),quantity:value})); // 讀取使用者目前表單值，不直接推論人物資訊
} // 結束目前回呼、區塊或模組定義
function guestSaveNotice() { // 只在成功保存後提醒；登入者不顯示訪客限制。
  if (state.me?.status !== 'guest' || state.guestSaveNoticeShown) return;
  state.guestSaveNoticeShown=true;
  // 只宣告目前已啟用的保存方式；伺服器保存與裝置媒體草稿不同。
  const accountHelp=state.capabilities?.google_login_available
    ? '可使用 Google 帳號保存世界；帳號衝突時不會自動合併。'
    : '目前未開放 Google 保存世界，請保留此瀏覽器的工作階段。';
  $('#notice').textContent='已保存至目前服務。此瀏覽器的訪客工作階段有效期間內可繼續；清除Cookie或工作階段到期後可能無法取回。'+accountHelp;
}
function showDraftAICandidate(result){
      state.aiPeople=result.people||[];
      $('#ai-people-panel').innerHTML=state.aiPeople.length?'<div class="callout"><strong>原文明示人物資訊候選</strong><p>尚未寫入人物檔案。請返回第三步逐人補充並核對，不會自動套到第一位人物。</p>'+state.aiPeople.map(hint=>'<p>'+esc(hint.person_name)+'：'+esc(hint.value)+'</p><blockquote>'+esc(hint.source_quote)+'</blockquote>').join('')+'</div>':'';
      state.candidate = result.summary; state.aiTasks=result.tasks||[]; // 等待伺服器完成讀取或保存，再進入下一步
      $('#candidate-panel').innerHTML = `<div class="callout"><b>整理候選，尚未套用</b><p>${esc(result.notice || '')}</p><div class="raw-source">${esc(result.summary)}</div>${result.tasks?.length?'<p>建議後續任務（套用後仍可編輯或刪除）</p><ul>'+result.tasks.map(t=>'<li>'+esc(t)+'</li>').join('')+'</ul>':''}${button('apply-candidate',result.tasks?.length?'套用摘要與任務草稿':'套用到摘要','secondary')}${button('dismiss-candidate','保留目前摘要','text-button')}</div>`; // 執行「處理click事件與對應的介面狀態」的目前處理步驟
}
async function saveDraft(form, review, destination = 'history') { // 新增或依版本修改草稿，成功後接續核對或返回
  if(!await MomentUI.validate())return; // 在第一步就提示時間，不等走完人物才由API拒絕。
  if(!ExperienceValidation.sync(form)){ExperienceUI.show(2);return;}
  await MediaUI.awaitReady(); // 縮圖完成才綁定素材與保存伺服器草稿。
  const f = new FormData(form), body = {raw_text:f.get('raw_text'), occurred_at:inputISO(f.has('calendar_time')?f.get('calendar_date')+'T'+f.get('calendar_time'):f.get('occurred_at'),form.dataset.calendarZone||state.me.timezone),goal_id:f.get('goal_id') || null,person_id:f.get('person_id') || null,contributions:contributions(form)}; // 讀取使用者目前表單值，不直接推論人物資訊
  const savedReview=ExperienceUI.reviewSnapshot();if(savedReview)body.review=savedReview;
  body.story=ExperienceUI.storyForDraft(form); // 草稿只保存候選，不建立正式人物連結
  if (body.person_id === '__upgrade') throw new Error('請先建立帳號後再選擇人物。'); // 依目前選項或狀態進入對應處理分支
  let result; // 保存伺服器已確認的操作結果
  if (state.editingDraft && state.draft?.status === 'draft') result = await api('/drafts/' + state.draft.id,{method:'PUT',body:{...body,expected_revision:state.draft.revision}}); // 等待伺服器完成讀取或保存，再進入下一步
  else result = await api('/experiences/drafts',{method:'POST',body:{...body,request_id:requestId('create-draft',body)}}); // 等待伺服器完成讀取或保存，再進入下一步
  state.guestSaveNoticePending=true;
  state.draft = result; state.editingDraft = true; // 文字已保存；若本機素材連結失敗，重試必須更新這份草稿。
  await MediaUI.bindDraft(result.id);
  state.editingDraft = false; state.dirty = false; await refresh(); // 成功保存或明確導覽後清除未保存旗標
  if (review) navigate('review/' + result.id + (state.returnTo?'?return='+encodeURIComponent(state.returnTo):'')); else {toast('草稿已保存至伺服器，尚未加分。'); navigate(destination);} // 依目前選項或狀態進入對應處理分支
} // 結束目前回呼、區塊或模組定義
async function saveReviewDraft(destination='history') { // 核對頁可保存而不建人、計分或確認經歷。
  const form=$('#review-form'),d=state.draft;if(!form||!d)return;
  const f=new FormData(form),review=ExperienceUI.reviewSnapshot();
  const result=await api('/drafts/'+d.id,{method:'PUT',body:{raw_text:d.raw_text,occurred_at:d.occurred_at,goal_id:d.goal_id,person_id:f.get('person_id')||null,contributions:contributions(form),story:ExperienceUI.storyForDraft(form),review,expected_revision:d.revision}});
  ConnectionsUI.clearReview(d.id);state.draft=result;state.dirty=false;await refresh();navigate(destination);toast('核對草稿已保存至伺服器，尚未建立人物或計分。');
}
function leaveDialog(route) { // 離開前提供保存草稿、繼續編輯或明確捨棄
  state.pendingRoute = route; // 執行「離開前提供保存草稿、繼續編輯或明確捨棄」的目前處理步驟
  dialog(`<h2 id="account-heading">離開前，留住這段內容。</h2><p class="small muted">目前有尚未保存的修改。可以保存草稿並離開、繼續編輯，或捨棄本次未保存修改。已保存到伺服器的草稿仍會保留，不會在此刪除。${$('#record-form') ? '這份原始記錄也可以先存成草稿。' : ''}</p><div class="button-row">${$('#record-form') ? button('keep-local-and-leave','保留此裝置草稿並離開','secondary') : ''}${$('#record-form')||$('#review-form')?button('save-and-leave','先存草稿並離開'):''}${button('stay-on-form','繼續編輯','secondary')}${button('discard-and-leave','捨棄未保存修改並離開','danger')}</div>`); // 執行「離開前提供保存草稿、繼續編輯或明確捨棄」的目前處理步驟
} // 結束目前回呼、區塊或模組定義
document.addEventListener('click', event => { // 監聽點擊
  const anchor = event.target.closest('a[href^="#"]'); // 尋找使用者點選的站內 hash 連結
  if (anchor && state.dirty && anchor.hash.slice(1) !== state.route) { // 依目前選項或狀態進入對應處理分支
    event.preventDefault(); leaveDialog(anchor.hash.slice(1)); // 執行「處理click事件與對應的介面狀態」的目前處理步驟
  } else if(anchor && anchor.hash.slice(1) !== state.route) { lockRenderControls(); } // 切頁開始前鎖住舊表單，避免非同步載入時遺失輸入
}, true); // 結束目前回呼、區塊或模組定義
document.addEventListener('input', event => { if (event.target.closest('#app form:not([data-search])')) state.dirty = !event.target.closest('#goal-form'); }); // 監聽輸入，標記未保存修改
document.addEventListener('change', async event => { // 監聽欄位變更
  try { // 包住可能失敗的讀寫並交由錯誤分支處理
    if (ConnectionsUI.change(event.target)) return; // 交會排序及人物輸入先處理
    if (await PeopleUI.change(event.target)) return; // 依目前選項或狀態進入對應處理分支
    if (event.target.name === 'person_id' && $('#people-review-fields')) $('#people-review-fields').innerHTML = await PeopleUI.reviewExtras(event.target.value); // 依目前選項或狀態進入對應處理分支
    if (event.target.name === 'goal_id' && $('#record-form')) { // 依目前選項或狀態進入對應處理分支
      ExperienceValidation.changeGoal(event.target.form); // 執行「處理change事件與對應的介面狀態」的目前處理步驟
    } // 結束目前回呼、區塊或模組定義
    if (event.target.name === 'person_id' && event.target.value === '__upgrade') {event.target.value = ''; accountView('claim');} // 依目前選項或狀態進入對應處理分支
    if (event.target.dataset.task) { // 依目前選項或狀態進入對應處理分支
      const result = await api('/tasks/' + event.target.dataset.task, {method:'PATCH',body:{done:event.target.checked}}); // 等待伺服器完成讀取或保存，再進入下一步
      const task = state.world.tasks.find(t => t.id === result.id); task.done = result.done; if(state.route==='goals'||state.route.startsWith('goal/'))await render(); toast('待辦狀態已保存；不會重複增加行動進度。'); // 保存「task」供此流程接續使用
    } // 結束目前回呼、區塊或模組定義
  } catch (error) {showError(error); if (event.target.dataset.task) event.target.checked = !event.target.checked;} // 顯示失敗原因，讓使用者保留內容並重試
}); // 結束目前回呼、區塊或模組定義
// 先撤銷伺服器Session，再做可取消的本機清理；IndexedDB故障不得保留已登入狀態。
async function finishLogout(){
  const owner=state.me?.owner_id,clear=state.logoutClearMedia;
  const revoke=new AbortController(),timer=setTimeout(()=>revoke.abort(),8000);
  try {await api('/auth/logout',{method:'POST',signal:revoke.signal});}
  catch(error){if(error.status!==401)throw error;} finally{clearTimeout(timer);}
  state.googleAttempt=null;state.dirty=false;state.pendingRoute=null;
  $('#account-dialog').close();DashboardUI.clear();state.me=null;state.world=null;state.csrf='';state.draft=null;state.candidate=null;state.requests.clear();
  navigate('welcome');
  if(clear&&owner){
    const controller=new AbortController();let timeout;
    try {await Promise.race([MediaUI.clearOwner(owner,{signal:controller.signal}),new Promise((_,reject)=>{timeout=setTimeout(()=>{controller.abort();reject(new Error('cleanup_timeout'));},2500);})]);}
    catch {$('#notice').innerHTML='<div class="callout" role="status">已登出；本機媒體草稿尚未清除。可使用瀏覽器網站資料設定清理本機內容；不會刪除伺服器資料。</div>';}
    finally{clearTimeout(timeout);}
  }
}
// 同一頁面首次尚無Cookie時，共用進行中的Guest請求，避免雙擊建立兩個世界。
let guestStartPending=null;
function startGuest() {
  if(guestStartPending)return guestStartPending;
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
  guestStartPending=(async()=>{
    try {
      const me=await api('/auth/guest',{method:'POST',signal:controller.signal});
      state.me=me;state.csrf=me.csrf_token;return me;
    } catch(error) {
      if(error.name==='AbortError')throw new Error('服務回應逾時，尚未確認世界是否建立。請重試；若瀏覽器已收到Session，會恢復同一個世界。');
      throw error;
    } finally {clearTimeout(timer);}
  })().finally(()=>{guestStartPending=null;});
  return guestStartPending;
}
// Guest入口控制結束
document.addEventListener('click', async event => { // 監聽點擊
  const target = event.target.closest('[data-action],g[data-person],button[data-person]'); if (!target) return; // 取得本次操作的控制項或合併主要事件
  if(target.disabled)return; // 防止重複派送仍在處理的操作。
  const action = target.dataset.action; target.disabled = true; // 讀取按鈕明確指定的操作代碼
  try { // 包住可能失敗的讀寫並交由錯誤分支處理
    if(action==='intro-direct'){window.IntroEntry?.dismiss();await render();$('#app [data-action=guest],#app [data-action=entry-guest]')?.focus();return;}
    if(action==='entry-retry'){await retryPublicEntry();return;}
    if(action?.startsWith('entry-')){publicEntryView(action.slice(6));return;}
    if (await DraftsUI.handleClick(action,target)) return;
    if (await PersonDetailsUI.handleClick(action,target)) return;
    if (await PeopleUI.handleClick(target)) return; // 依目前選項或狀態進入對應處理分支
    if (action === 'guest') {await startGuest(); await refresh(); navigate('profile');} // 開始訪客旅程
    if (action === 'account') accountView(); // 開啟帳號設定
    if(action==='test-login-dialog')accountView('test-login');
    if (action === 'claim-dialog') accountView('claim'); // 開啟升級帳號表單
    if (action === 'login-dialog') {if(state.capabilities?.access_mode==='public_alpha'&&!state.capabilities.accounts_available)throw new Error('Alpha預建帳號登入尚未啟用。');accountView('login');} // 開啟登入表單
    if (action === 'close-account') {if(state.googleUncertain)throw new Error('登入結果正在核對，請先核對登入結果；不能把已送出的交換當作取消。');$('#account-dialog').close();} // 關閉對話框
    if(action==='leave-experience'){const destination=state.returnTo||'history';if(state.dirty)leaveDialog(destination);else navigate(destination);return;} // 明確退出專注記錄，沿用既有未保存保護。
    if (action === 'stay-on-form') {state.pendingRoute = null; $('#account-dialog').close();} // 保留輸入並繼續編輯
    if (action === 'discard-and-leave') {await MediaUI.discard(); const route = state.pendingRoute; state.pendingRoute = null; ConnectionsUI.clearReview(state.draft?.id); $('#account-dialog').close(); navigate(route);} // 明確捨棄時不在下次核對偷偷還原修改
    if (action === 'keep-local-and-leave') {await MediaUI.keepLocal(); const route=state.pendingRoute; state.pendingRoute=null; $('#account-dialog').close(); navigate(route);}
    if(action==='save-review-draft')await saveReviewDraft();
    if (action === 'save-and-leave') {if($('#record-form'))await saveDraft($('#record-form'),false,state.pendingRoute);else await saveReviewDraft(state.pendingRoute);state.pendingRoute=null;$('#account-dialog').close();} // 先保存草稿再前往目的地
    if (action === 'logout') {
      state.logoutClearMedia=!!$('#clear-local-media')?.checked;
      if(state.dirty){
        dialog(`<h2 id="account-heading">登出前，處理尚未保存的修改</h2><p>登出不刪除伺服器已保存資料。可繼續編輯，或明確捨棄本次未保存修改。</p><div class="button-row">${button('stay-on-form','繼續編輯','secondary')}${$('#record-form')?button('logout-save','保存草稿後登出','secondary'):''}${button('logout-discard','捨棄未保存修改並登出','danger')}</div>`);
      } else await finishLogout();
    }
    if(action==='logout-save'){await saveDraft($('#record-form'),false);await finishLogout();}
    if(action==='logout-discard'){await finishLogout();}
    if(action==='choose-experience-person'){const root=$('[data-story-editor]');root.querySelector('#include-story').checked=true;root.querySelector('.story-editor-body').hidden=false;root.querySelector('.participant-filter')?.focus();state.dirty=true;}
    if (action === 'new-person') { // 依訪客狀態升級或新增人物
      if (state.me.status === 'guest') accountView('claim'); // 依目前選項或狀態進入對應處理分支
      else if($('#record-form,#review-form')) {const root=$('[data-story-editor]');if(root.querySelector('[data-pending-target-list]')){ConnectionsUI.addPendingPerson(root);return;}root.querySelector('#include-story').checked=true;root.querySelector('.story-editor-body').hidden=false;const pending=root.querySelector('[name=pending_person_enabled]');pending.checked=true;pending.closest('details').open=true;root.querySelector('[name=pending_person_name]').focus();state.dirty=true;}
      else PeopleUI.openPersonEditor(); // 處理前述條件不成立時的替代流程
    } // 結束目前回呼、區塊或模組定義
    if(action==='fix-experience-goal'){const owner=state.me.owner_id;ExperienceUI.capture();state.draft={...state.draft,contributions:contributions($('#review-form'))};state.validationReturnStep=2;state.editingDraft=true;await refresh();if(state.me?.owner_id!==owner){state.draft=null;state.editingDraft=false;state.experienceFlow=null;delete state.validationReturnStep;navigate('world');return;}navigate('record');}
    if (action === 'edit-current-draft') {state.editingDraft = true; navigate('record');} // 帶回目前草稿進行修改
    if (action === 'retry-guest-cleanup') {await GuestLocalCleanup.retry();return;}
    if (action === 'google-login-existing') {accountView('login');return;}
    if(action==='google-cancel'){if(state.googleAttempt?.exchangeStarted){await reconcileGoogleTransition(state.googleAttempt);return;}state.googleAttempt=null;if($('#google-discard'))$('#google-discard').disabled=false;window.google?.accounts?.id?.cancel?.();$('#google-button').replaceChildren();$('#google-status').textContent='已取消Google驗證，原訪客世界與表單保持。';return;}
    if(action==='google-reconcile'){if(state.googleAttempt?.challenge){const done=await reconcileGoogleTransition(state.googleAttempt);if(!done)$('#google-status').textContent='此交換尚未提交，原訪客世界保持，可重新開始驗證。';}return;}
    if (action === 'google-start') {await startGoogleLogin(event.target.closest('[data-action]').dataset.mode);return;}
    if(action==='ai-usage'){
      const usageOwner=state.me?.owner_id,usage=await api('/ai/usage'),usd=n=>'$'+(Number(n)/1000000).toFixed(2);
      if(state.me?.owner_id!==usageOwner)return; // 延遲回應不得把前一帳號收據顯示到切換後的帳號。
      dialog(`<h2 id="account-heading">我的 AI 用量與收據</h2><p>本帳號共 ${esc(usage.calls)} 次預留，預留金額 ${usd(usage.reserved_microusd)}。這不是實際帳單費用。</p><p>已回報輸入 ${esc(usage.input_tokens)} Tokens、輸出 ${esc(usage.output_tokens)} Tokens；未回報的用量不代表零。費用未知或尚未回報：${esc(usage.unknown_cost_calls)} 次。</p><p>預留不因失敗或費用未知而釋放；供應商回報金額也不是最終帳單。實際帳單費用目前未知。</p><details><summary>查看本人最近 ${usage.receipts.length} 筆收據（最多100筆）</summary>${usage.receipts.map(r=>`<article class="card"><p>${esc(r.created_at)} · ${esc({candidate:'候選已回傳',failed:'未完成',reserved:'已預留，結果待核對'}[r.status]||'結果待核對')}</p><p>本次預留 ${usd(r.reserved_microusd)}；模型回報費用：${r.cost_microusd==null?'未知':usd(r.cost_microusd)}（非帳單）。</p><p class="small">收據 ${esc(r.request_id)}</p></article>`).join('')||'<p>尚無本人AI預留收據。</p>'}</details>`);return;
    }
    if(action==='memory-settings'){
      const prefs=await api('/personalization');
      dialog(`<h2 id="account-heading">個人化資料與記憶</h2><p>只使用你已確認的經歷、人物來源及明示偏好。用於建議與私人劇場，不代表真人性格，不自動納入模型訓練。</p><label><input id="memory-enabled" type="checkbox" ${prefs.enabled?'checked':''}>啟用來源可追溯的個人化記憶</label><label>摘要偏好<select id="memory-style"><option value="concise">簡潔</option><option value="detailed">詳細</option></select></label><p>修正或撤回來源後，下次AI請求會重新驗證；停用或刪除會清除衍生特徵，不刪除原經歷。</p>${button('memory-save','保存設定')}${button('memory-delete','刪除個人化資料','danger')}`);
      $('#memory-style').value=prefs.preferences.summary_style||'concise';return;
    }
    if(action==='memory-save'){await api('/personalization',{method:'PUT',body:{enabled:$('#memory-enabled').checked,preferences:{summary_style:$('#memory-style').value}}});$('#account-dialog').close();toast('已保存個人化設定。');return;}
    if(action==='memory-delete'){await api('/personalization',{method:'DELETE'});$('#account-dialog').close();toast('已刪除衍生記憶，原始紀錄保留。');return;}
    if(action==='suggest'){await DraftAIUI.choose();return;}
    if(action==='apply-person-hint'){
      const hint=state.aiPeople?.[Number(target.dataset.index)],personId=$('#person-id')?.value;
      if(!hint||!personId)throw new Error('請先選擇或新增這筆資訊對應的人物，再套入候選。');
      // 避免將同篇另一人的資訊誤套到目前選擇的人物。
      const selectedPerson=state.world.people.find(person=>person.id===personId);
      if(!selectedPerson||selectedPerson.name!==hint.person_name)throw new Error('候選屬於「'+hint.person_name+'」，請選擇對應人物後再套用。');
      const field=document.querySelector('[name="fact_value_'+hint.dimension+'"]');
      if(!field)throw new Error('請先載入人物核對欄位。');
      field.value=hint.value;field.dataset.aiSource=hint.source_quote;
      document.querySelector('[name="fact_type_'+hint.dimension+'"]').value=hint.evidence_type;
      document.querySelector('[name="fact_selected_'+hint.dimension+'"]').checked=false;
      state.dirty=true;toast('已填入待核對欄位，請確認人物對應及內容，再逐項勾選。尚未寫入人物資料。');return;
    }
    if (action === 'apply-candidate') {if(typeof state.candidate!=='string')throw new Error('候選已失效，請重新核對。');$('#summary').value = state.candidate; if(state.aiTasks?.length)$('#followups').value=[...new Set([...$('#followups').value.split('\n'),...state.aiTasks].filter(Boolean))].join('\n');state.aiTasks=[]; $('#candidate-panel').innerHTML = ''; state.candidate = null; state.dirty = true;$('#summary').dispatchEvent(new Event('input',{bubbles:true}));} // 明確將候選放入可編輯摘要
    if (action === 'dismiss-candidate') {$('#candidate-panel').innerHTML = ''; state.candidate = null; state.aiTasks=[];} // 捨棄候選並保留現有摘要
  } catch (error) { showError(error); } // 顯示失敗原因，讓使用者保留內容並重試
  finally {target.disabled = false;} // 操作結束時還原按鈕或載入狀態
}); // 結束目前回呼、區塊或模組定義
document.addEventListener('submit', async event => { // 監聽表單提交
  const form = event.target; event.preventDefault(); // 取得本次操作的表單
  const submitter = event.submitter; const buttons = [...form.querySelectorAll('button')]; buttons.forEach(b => b.disabled = true); $('#notice').innerHTML = ''; // 取得觸發提交的按鈕並暫停重複提交
  try { // 包住可能失敗的讀寫並交由錯誤分支處理
    if (await GoalsUI.submit(form)) return; // 目標建立與回顧先使用新契約。
    if (await ConnectionsUI.submit(form)) return; // 來源核對及角色更正沿用既有錯誤處理
    if (await PersonDetailsUI.handleSubmit(form)) return;
    if (await PersonsUI.handleSubmit(form)) return;
    if (await PeopleUI.handleSubmit(form)) return; // 依目前選項或狀態進入對應處理分支
    const f = new FormData(form); // 讀取使用者目前表單值，不直接推論人物資訊
    if (form.id === 'profile-form') {await api('/profile',{method:'PUT',body:Object.fromEntries(f)}); await refresh(); navigate('goal-new');} // 等待伺服器完成讀取或保存，再進入下一步
    if (form.id === 'record-form') await saveDraft(form, submitter?.value !== 'save'); // 依目前選項或狀態進入對應處理分支
    if (form.id === 'review-form') { // 依目前選項或狀態進入對應處理分支
      const body = {...PeopleUI.reviewPayload(form),expected_revision:state.draft.revision,summary:f.get('summary'),person_id:f.get('person_id') || null,contributions:contributions(form),tasks:String(f.get('tasks')).split('\n').map(x => x.trim()).filter(Boolean)}; // 組合使用者明確提供的 API 提交內容
      const reviewSnapshot=ExperienceUI.reviewSnapshot();if(reviewSnapshot){body.reviewed_summary_sha256=reviewSnapshot.summary_source_sha256;if(reviewSnapshot.person_candidates.length||reviewSnapshot.birthday_candidates?.length||reviewSnapshot.employment_candidates?.length){if(body.person_updates?.length)throw new Error('此草稿使用逐人人物補充；請先取消舊版單人候選，避免兩份資訊互相覆蓋。');body.review=reviewSnapshot;delete body.person_updates;}}
      body.story=ExperienceUI.storyForDraft(form); body.story_reviewed=f.has('story_reviewed'); // 正式角色需獨立人工接受
      if(body.story) { if(body.person_id&&!body.story.participants.some(p=>p.person_id===body.person_id)) throw new Error('主要關聯人物不在參與清單，請調整主要人物或參與者；提及者請在提及區核對。'); body.person_id=body.person_id||body.story.participants[0]?.person_id||null; body.interaction_type=f.get('story_interaction_type')||'unknown'; } // 不將原人物資訊候選誤套到另一位參與者
      const result = await api('/drafts/' + state.draft.id + '/confirm',{method:'POST',body:{...body,request_id:requestId('confirm:' + state.draft.id,body)}}); // 等待伺服器完成讀取或保存，再進入下一步
      ConnectionsUI.clearReview(state.draft.id); // 確認成功後清除核對暫存
      state.draft = null; state.candidate = null; state.aiPeople=[]; const destination=state.returnTo||'history'; state.returnTo=null; await refresh(); navigate(destination); toast(`已確認保存，本次增加 ${result.points_awarded} 積分。`); // 重新讀取伺服器確認的資料，再更新畫面
    } // 結束目前回呼、區塊或模組定義
    if (form.id === 'claim-form') { // 依目前選項或狀態進入對應處理分支
      const me = await api('/auth/claim',{method:'POST',body:Object.fromEntries(f)}); state.csrf = me.csrf_token; // 等待伺服器完成讀取或保存，再進入下一步
      await refreshKeepingForm(); $('#account-dialog').close(); toast('帳號已建立，原本的世界與草稿都在。'); // 重新讀取伺服器確認的資料，再更新畫面
    } // 結束目前回呼、區塊或模組定義
    if (form.id === 'login-form') { // 依目前選項或狀態進入對應處理分支
      try { // 包住可能失敗的讀寫並交由錯誤分支處理
        const me = await api('/auth/login',{method:'POST',body:{username:f.get('username'),password:f.get('password'),discard_guest:f.get('discard_guest') === 'on'}}); // 等待伺服器完成讀取或保存，再進入下一步
        state.csrf = me.csrf_token; state.me = me; state.draft = null; state.candidate = null; state.aiPeople=[]; state.requests.clear(); $('#account-dialog').close(); await refresh(); navigate('world'); // 重新讀取伺服器確認的資料，再更新畫面
      } catch (error) { // 顯示失敗原因，讓使用者保留內容並重試
        if (error.code === 'guest_conflict') $('#guest-conflict').innerHTML = '<div class="callout error-message">登入不會匯入或合併訪客資料。離開這個訪客身分後，可能無法再取得原世界。<label class="check-line"><input type="checkbox" name="discard_guest" required>我了解，仍要離開訪客世界並登入。</label></div>'; // 依目前選項或狀態進入對應處理分支
        throw error; // 執行「處理submit事件與對應的介面狀態」的目前處理步驟
      } // 結束目前回呼、區塊或模組定義
    } // 結束目前回呼、區塊或模組定義
    if (form.id === 'note-form') {const body = Object.fromEntries(f); body.person_id ||= null; await api('/notes',{method:'POST',body}); await refresh(); state.dirty = false; await render(); toast('私人筆記已保存，不計入真實成果。');} // 成功保存或明確導覽後清除未保存旗標
    if (form.id === 'upload-form') {await api('/goals/' + form.dataset.goal + '/evidence',{method:'POST',body:f}); await refreshKeepingForm(); toast('佐證已上傳並可回讀。');} // 等待伺服器完成讀取或保存，再進入下一步
    if (form.id === 'complete-form') { // 依目前選項或狀態進入對應處理分支
      const goal = await api('/goals/' + form.dataset.goal); // 等待伺服器完成讀取或保存，再進入下一步
      const body = {expected_revision:GoalsUI.completion()?.revision,evidence_ids:(GoalsUI.completion()?.evidence||goal.evidence).map(e => e.id),confirmed:f.get('confirmed') === 'on',reflection:f.get('reflection') || ''}; // 組合使用者明確提供的 API 提交內容
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
$('#account-dialog').addEventListener('cancel',event=>{if(state.googleUncertain){event.preventDefault();showError(new Error('登入結果尚未確認，請保留表單並核對登入結果。'));}});
$('#account-dialog').addEventListener('close', () => {if(!state.googleAttempt?.exchangeStarted)state.googleAttempt=null;$('#account-content').replaceChildren();}); // 執行「處理hashchange事件與對應的介面狀態」的目前處理步驟
window.addEventListener('beforeunload', event => {if (state.dirty) {event.preventDefault(); event.returnValue = '';}}); // 監聽關閉頁面以保護未保存內容
window.addEventListener('offline', () => {$('#notice').innerHTML = '<div class="callout error-message">目前離線；尚未送出的內容沒有保存成功。請保留此頁，連線後再試。</div>';}); // 監聽離線狀態並提示保留輸入
async function start() { // 讀取既有身分後啟動畫面
  try {await refresh();} // 重新讀取伺服器確認的資料，再更新畫面
  catch (error) {if (error.status !== 401) showError(error);} // 顯示失敗原因，讓使用者保留內容並重試
  await GuestLocalCleanup.retry();
  await DraftsUI.retryLocalCleanup();
  await render(); // 執行「讀取既有身分後啟動畫面」的目前處理步驟
} // 結束目前回呼、區塊或模組定義
DraftAIUI.initialize({state,api,esc,id:newId,onCandidate:showDraftAICandidate});
ExperienceUI.initialize({state,toast,esc,api,inputISO,personControls:story=>experiencePersonField()+ConnectionsUI.editor(story,'record')});
MediaUI.initialize({state,api,esc,toast,contributionFields,requestLogin:()=>{toast('登入後可使用辨識；原素材與手動文字會保留。');accountView('claim');}});
PeopleUI.initialize({state,api,esc,link,button,heading,empty,time,options,toast,dialog,requestId,refresh,render,navigate,refreshKeepingForm});
PersonsUI.initialize({state,api,esc,link,button,heading,empty,time,toast,requestId:()=>newId(),refresh,render,navigate});
PersonDetailsUI.initialize({state,api,esc,link,dialog,requestId:()=>newId(),render,toast});
DraftsUI.initialize({state,api,esc,dialog,newId,refresh,render,toast}); // 將主程式工具注入人物模組，使兩者共用狀態
ConnectionsUI.initialize({state,api,esc,link,button,heading,empty,time,options,toast,dialog,requestId,refresh,render,navigate,refreshKeepingForm}); // 交會與收藏冊共用 API 及帳號資料
document.addEventListener('click',async event=>{const target=event.target.closest('[data-cx]'); if(!target) return; target.disabled=true; try { await ConnectionsUI.click(target); } catch(error) { showError(error); } finally { if(target.isConnected) target.disabled=false; }}); // 防止來源／配對重複點擊並保留失敗內容
document.addEventListener('keydown', event => {if(event.target.matches('[data-person]') && ['Enter',' '].includes(event.key)) {event.preventDefault(); event.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}}); // 監聽鍵盤操作，讓星點支援 Enter 與空白鍵
start().catch(showError); // 啟動 App，未處理錯誤交由共用提示呈現

// 使用委派事件以符合既有 CSP，不允許內嵌腳本。
document.addEventListener("click",event=>{if(event.target.closest("[data-home-retry]"))render().catch(showError);});

// 返回快取歡迎頁或另一分頁完成介紹時，只更新提示，不打斷產品內任何表單。
window.addEventListener('pageshow',event=>{if(event.persisted&&state.route==='welcome')render().catch(showError);});
window.addEventListener('storage',event=>{if(event.key===window.LifeWorldIntroPreference?.key&&state.route==='welcome')render().catch(showError);});
