'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const newId = () => crypto.randomUUID();
const state = {me:null, world:null, csrf:'', draft:null, editingDraft:false, route:'', dirty:false, requests:new Map(), candidate:null};
const names = {world:'我的世界', goals:'目標花園', record:'記錄經歷', history:'經歷收藏', people:'我的關係', notes:'私人小劇場', profile:'認識你', 'goal-new':'建立目標', birth:'新的開始', welcome:'歡迎'};
const dayNames = ['一','二','三','四','五','六','日'];
let renderSequence = 0;
let toastTimer;

function toast(message) {
  $('#toast').textContent = message; $('#toast').classList.add('visible');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 4500);
}
function showError(error) {
  const fields = error.fields?.length ? ` 欄位：${error.fields.join('、')}` : '';
  $('#notice').innerHTML = `<div class="callout error-message">${esc(error.message + fields)}</div>`;
  if ($('#account-dialog').open) {
    const existing = $('#dialog-error');
    if (existing) existing.textContent = error.message + fields;
  }
}
async function api(path, options = {}) {
  const headers = {'X-CSRF-Token':state.csrf, ...options.headers};
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(options.body);
  }
  let response;
  try { response = await fetch('/api' + path, {...options, headers, credentials:'same-origin', cache:'no-store'}); }
  catch { throw new Error('目前無法連線。請保留內容，連線恢復後再送出；尚未確認保存成功。'); }
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    const error = new Error(body?.error?.message || '操作未完成，請重試。');
    error.code = body?.error?.code; error.status = response.status; error.fields = body?.error?.fields;
    if (response.status === 401 && !path.startsWith('/auth/')) {
      state.me = null; state.world = null; state.csrf = ''; state.draft = null; state.dirty = false;
      $('#account-dialog').close(); await render();
    }
    throw error;
  }
  return body;
}
async function refresh() {
  state.me = await api('/auth/me'); state.csrf = state.me.csrf_token;
  state.world = state.me.lumi_hatched ? await api('/state') : null;
}
function requestId(scope, body) {
  const fingerprint = JSON.stringify(body);
  if (state.requests.get(scope)?.fingerprint !== fingerprint) state.requests.set(scope, {fingerprint, id:newId()});
  return state.requests.get(scope).id;
}
function navigate(route) {
  state.dirty = false; $('#notice').innerHTML = '';
  if (location.hash.slice(1) === route) render().catch(showError); else location.hash = route;
}
function link(route, label, style = 'secondary') { return `<a class="${style}" href="#${esc(route)}">${label}</a>`; }
function button(action, label, style = 'primary', attributes = '') { return `<button type="button" class="${style}" data-action="${action}" ${attributes}>${label}</button>`; }
function heading(title, subtitle, action = '') { return `<div class="heading"><div><div class="eyebrow">YOUR LITTLE UNIVERSE</div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div>${action}</div>`; }
function lumi() { return '<div class="hero-art" aria-label="目標蛋建立後誕生的 Lumi"><div class="ground"></div><div class="lumi"><i class="leaf"></i><i class="eyes"></i><i class="beak"></i><i class="wing"></i></div><span class="spark" aria-hidden="true">✧</span></div>'; }
function empty(message, action = '') { return `<div class="empty"><span class="empty-icon">✳</span>${esc(message)}${action ? '<div class="space-top">' + action + '</div>' : ''}</div>`; }
function localInput(iso = new Date().toISOString()) {
  const parts = new Intl.DateTimeFormat('sv-SE', {timeZone:state.me?.timezone || 'Asia/Taipei', year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(iso));
  const p = Object.fromEntries(parts.map(x => [x.type,x.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
function inputISO(value) {
  const components = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/);
  if (!components) throw new Error('請填寫實際發生時間。');
  const desired = Date.UTC(...components.slice(1).map((v,i) => Number(v) - (i === 1 ? 1 : 0)));
  let instant = desired;
  for (let i = 0; i < 3; i++) {
    const rendered = localInput(new Date(instant).toISOString());
    const p = rendered.match(/\d+/g).map(Number); p[1]--;
    instant += desired - Date.UTC(...p);
  }
  if (localInput(new Date(instant).toISOString()) !== value) throw new Error('此當地時間不存在，請重新選擇。');
  return new Date(instant).toISOString();
}
function time(iso) { return new Intl.DateTimeFormat('zh-TW', {timeZone:state.me?.timezone || 'Asia/Taipei',dateStyle:'medium',timeStyle:'short'}).format(new Date(iso)); }
function options(items, selected, label = 'title') { return items.map(item => `<option value="${esc(item.id)}" ${item.id === selected ? 'selected' : ''}>${esc(item[label])}</option>`).join(''); }
function goalProgress(goal) {
  return goal.actions.map(a => `<div class="progress-row"><div class="progress-meta"><b>${esc(a.title)}</b><span>${esc(a.progress)} / ${esc(a.target)} ${esc(a.unit)}</span></div><div class="progress"><progress max="${esc(a.target)}" value="${esc(a.progress)}" aria-label="${esc(a.title)}進度"></progress></div></div>`).join('');
}
function goalCard(goal) {
  return `<div class="card"><div class="goal-top"><span class="egg ${goal.status === 'completed' ? 'completed' : ''}">${goal.status === 'completed' ? '✿' : '⌁'}</span><div><h3>${esc(goal.title)}</h3><p>${goal.status === 'completed' ? '已由你確認成果' : '每一小步，都在慢慢生長'}</p></div></div>${goalProgress(goal)}<div class="button-row space-top">${link('goal/' + goal.id,'查看目標 →','text-button')}<span class="tag">${goal.status === 'completed' ? '成果收藏' : '成長中'}</span></div></div>`;
}
function navigation(route) {
  $('#nav').innerHTML = state.me?.lumi_hatched ? [['world','⌂'],['goals','♧'],['record','✎'],['history','▤'],['people','◌'],['notes','✧']].map(([key,icon]) => `<a class="nav-link ${route === key || route.startsWith(key + '/') ? 'active' : ''}" href="#${key}"><span class="nav-icon" aria-hidden="true">${icon}</span>${names[key]}</a>`).join('') : '';
  $('#page-label').textContent = names[route] || (route.startsWith('goal/') ? '目標詳情' : '核對經歷');
  $('#account-button').textContent = state.me?.name?.slice(0,1) || '○';
}
function welcomeView() {
  return `<div class="welcome">${heading('把每一步，種成自己的世界。','不需要一次走很遠。先給想做的事，一個小小的開始。')}<section class="hero"><div class="hero-copy"><div class="eyebrow">A WORLD THAT GROWS WITH YOU</div><h2>從一顆目標蛋，<br>開始你的故事。</h2><p>記下真實的努力，收集成長的痕跡。建立第一個目標後，新的陪伴也將誕生。</p><div class="button-row">${button('guest','不用註冊，先開始 →')}${button('login-dialog','登入我的世界','text-button')}</div></div><div class="hero-art"><span class="egg">⌁</span><span class="spark">✧</span></div></section><p class="small muted">資料保存在此電腦的 Python 服務。訪客尚無帳號恢復保障；請用虛構內容測試。</p></div>`;
}
function profileView() {
  return `<div class="narrow">${heading('先認識一下你。','這個世界，從你的名字與一點點自我介紹開始。')}<form id="profile-form" class="card"><div class="step-label"><span class="step-dot">1</span>認識你 → 建立目標 → 新的陪伴</div><div class="field"><label for="profile-name">希望怎麼稱呼你？</label><input id="profile-name" name="name" maxlength="80" required value="${esc(state.me.name)}" placeholder="你的名字或暱稱"></div><div class="field"><label for="bio">一點點關於你</label><textarea id="bio" name="bio" maxlength="2000" required placeholder="現在的你，在意什麼、想靠近什麼？">${esc(state.me.bio)}</textarea></div><div class="field"><label for="timezone">你的時區</label><input id="timezone" name="timezone" value="${esc(state.me.timezone)}" required></div><button class="primary">接著，建立第一個目標 →</button></form></div>`;
}
function goalForm() {
  return `<div class="narrow">${heading(state.me.lumi_hatched ? '種下下一個目標。' : '給努力，一個方向。','終極成果與日常行動分開。你決定什麼值得累積。')}<form id="goal-form" class="card"><div class="step-label"><span class="step-dot">2</span>目標與行動設定 → 確認建立目標蛋</div><div class="field"><label for="goal-title">目標名稱</label><input id="goal-title" name="title" maxlength="160" required placeholder="例如：完成我的第一個創作作品"></div><div class="field"><label for="outcome">你希望達成的終極成果</label><textarea id="outcome" name="outcome" maxlength="4000" required placeholder="具體描述你認為達標的樣子"></textarea></div><h3>設定三項可自主完成的行動</h3><p class="small muted">Lv1–3 是建立時的行動設定。本次貢獻仍由你每次手動確認。</p>${[0,1,2].map(i => `<fieldset><legend>行動 ${i+1}</legend><div class="field"><label for="action-title-${i}">行動名稱</label><input id="action-title-${i}" name="title${i}" required maxlength="160" placeholder="例如：練習、記錄、主動交流"></div><div class="form-grid"><div class="field"><label for="target-${i}">預期累計</label><input id="target-${i}" name="target${i}" type="number" min="0.000001" max="1000000000000" step="0.000001" required placeholder="例如：10"></div><div class="field"><label for="unit-${i}">計量單位</label><input id="unit-${i}" name="unit${i}" maxlength="20" required placeholder="小時／篇／次"></div></div><div class="field"><label for="level-${i}">預設養分等級</label><select id="level-${i}" name="level${i}">${[1,2,3].map(level => `<option value="${level}" ${level === i+1 ? 'selected' : ''}>Lv${level}</option>`).join('')}</select></div><div class="field"><span class="field-label">預計在哪些日子進行？（可複選）</span><div class="weekdays">${dayNames.map((name,day) => `<label class="day-check"><input type="checkbox" name="days${i}" value="${day}" ${[0,2,4].includes(day) ? 'checked' : ''}>週${name}</label>`).join('')}</div></div></fieldset>`).join('')}<div class="callout">行動累計不會自動完成終極成果。完成時需提供相關佐證，並由你親自確認。現在不啟用負向活力衰減。</div><button class="primary">確認設定，建立目標蛋 →</button></form></div>`;
}
function worldView() {
  const w = state.world, active = w.goals.filter(g => g.status === 'active');
  const weekday = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].indexOf(new Intl.DateTimeFormat('en-US',{timeZone:state.me.timezone,weekday:'short'}).format(new Date()));
  const today = active.flatMap(g => g.actions.filter(a => a.weekdays.includes(weekday)).map(a => ({...a,goal:g.title})));
  return `${heading(`${state.me.name}，歡迎回來。`,'你的每一點努力，都讓這個世界更靠近你。',link('record','＋ 記下一次經歷','primary'))}<section class="hero"><div class="hero-copy"><span class="tag">一點一點，慢慢長大</span><h2 class="space-top">今天也一起，<br>照顧心裡的那顆種子。</h2><p>我是 Lumi。無論你走到哪裡，這個世界都會為你留一個位置。</p><div class="button-row">${link('record','記錄今天的一小步 →','primary')}${link('goals','看看我的目標','text-button')}</div></div>${lumi()}</section><div class="stats"><div class="stat"><span class="stat-icon">♧</span><div><b>${active.length}</b><small>正在成長的目標</small></div></div><div class="stat"><span class="stat-icon">▤</span><div><b>${w.experiences.length}</b><small>已確認的真實經歷</small></div></div><div class="stat"><span class="stat-icon">✧</span><div><b>${w.rewards.total}</b><small>累積積分 · 開發規則</small></div></div></div><div class="grid"><section><div class="section-title"><h2>我的目標花園</h2>${link('goals','查看全部 →','text-button')}</div><div class="stack">${active.length ? active.slice(0,2).map(goalCard).join('') : empty('這一段已經完成，也可以種下新的方向。',link('goal-new','建立新目標','primary'))}</div></section><section><div class="section-title"><h2>今天，可以做的一小步</h2><span class="tag">依你的排程</span></div><div class="card">${today.length ? today.map(a => `<div class="list-item"><div class="list-start"><span class="circle-icon">↗</span><div class="item-main"><h3>${esc(a.title)}</h3><p>${esc(a.goal)} · Lv${a.level}</p></div></div>${link('record','記錄','text-button')}</div>`).join('') : empty('今天沒有排定行動，依照自己的節奏就好。')}</div><div class="section-title space-top"><h2>待辦與下一步</h2></div><div class="card">${w.tasks.length ? w.tasks.map(t => `<label class="check-line"><input type="checkbox" data-task="${esc(t.id)}" ${t.done ? 'checked' : ''}>${esc(t.title)}</label>`).join('') : empty('確認經歷時，可以留下想做的下一步。')}</div></section></div>${w.drafts.length ? `<div class="callout space-top">有 ${w.drafts.length} 份已保存、未確認的草稿。 ${link('history','繼續上次的記錄 →','text-button')}</div>` : ''}`;
}
function personField(selected = null) {
  return `<div class="field"><label for="person-id">關聯人物（選填）</label><select id="person-id" name="person_id"><option value="">不關聯人物</option>${options(state.world.people, selected, 'name')}${state.me.status === 'guest' ? '<option value="__upgrade">建立帳號，再新增／關聯人物…</option>' : ''}</select>${button('new-person','＋ 新增人物','text-button')}</div>`;
}
function contributionFields(goal, values = []) {
  if (!goal) return '<p class="small muted">本次不關聯目標，仍可保存真實經歷與積分。</p>';
  return `<fieldset><legend>由你確認本次貢獻</legend><p class="small muted">可填部分完成；空白或 0 表示本次不累計該項。</p>${goal.actions.map(a => `<div class="field"><label for="quantity-${a.id}">${esc(a.title)}（${esc(a.unit)}）</label><input id="quantity-${a.id}" name="quantity-${esc(a.id)}" type="number" min="0" max="1000000000000" step="0.000001" value="${esc(values.find(v => v.action_id === a.id)?.quantity || '')}" placeholder="例如：0.5"></div>`).join('')}</fieldset>`;
}
function recordView() {
  const d = state.editingDraft ? state.draft : null, active = state.world.goals.filter(g => g.status === 'active');
  const goalId = d ? d.goal_id : active[0]?.id;
  const goal = state.world.goals.find(g => g.id === goalId);
  return `<div class="narrow">${heading('把這一刻，記下來。','今天的小事、昨天的努力，都值得有一個位置。')}<form id="record-form" class="card"><div class="step-label"><span class="step-dot">1</span>原始紀錄 → 人工核對 → 正式保存</div><div class="field"><label for="raw-text">發生了什麼？</label><textarea id="raw-text" name="raw_text" maxlength="20000" required placeholder="用自己的話記下真實經過…">${esc(d?.raw_text || '')}</textarea></div><div class="field"><label for="occurred-at">實際發生時間 · ${esc(state.me.timezone)}</label><input id="occurred-at" name="occurred_at" type="datetime-local" required value="${esc(localInput(d?.occurred_at))}"><span class="small muted">可以補記過去的經歷。發生時間與現在的提交時間會分別保存。</span></div><div class="field"><label for="goal-id">關聯目標（選填）</label><select id="goal-id" name="goal_id"><option value="">不關聯目標</option>${options(state.world.goals, goalId)}</select></div>${personField(d?.person_id)}<div id="contribution-fields">${contributionFields(goal, d?.contributions)}</div><div class="callout">人物是選填的。若選擇人物操作，訪客需要先建立帳號；升級時保留這份內容。確認前不累計、不發放積分。</div><div class="button-row"><button class="primary" name="intent" value="review">保存草稿並進入核對 →</button><button class="secondary" name="intent" value="save">先存草稿</button></div></form></div>`;
}
function reviewView(d) {
  const goal = state.world.goals.find(g => g.id === d.goal_id);
  return `<div class="narrow">${heading('最後，由你來確認。','原始記錄保留不變。只把你確認的內容，放進真實經歷。')}<form id="review-form" class="card"><h3>原始記錄</h3><div class="raw-source">${esc(d.raw_text)}</div><p class="record-meta">實際發生於 ${esc(time(d.occurred_at))}</p><div class="field space-top"><label for="summary">確認後的摘要</label><textarea id="summary" name="summary" maxlength="20000" required>${esc(d.raw_text)}</textarea></div>${button('suggest','用原文建立整理候選','secondary')}<p class="small muted">目前使用本機手動整理，尚未連接外部 AI。</p><div id="candidate-panel"></div>${personField(d.person_id)}${contributionFields(goal, d.contributions)}<div class="field"><label for="followups">想留下的下一步（選填，每行一項）</label><textarea id="followups" name="tasks" placeholder="例如：明天再練習半小時"></textarea></div><div class="callout">${goal ? '關聯目標：' + esc(goal.title) + '。' : ''}貢獻與積分將由伺服器一次保存。相同提交重試不會重複入帳。開發設定：每筆確認經歷 ${state.world.policy.points_per_experience} 分。</div><div class="button-row"><button class="primary">我已核對，確認保存</button>${button('edit-current-draft','返回修改原始草稿','secondary')}</div></form></div>`;
}
function historyView() {
  const w = state.world, filter = new URLSearchParams(location.hash.split('?')[1] || '').get('person');
  const experiences = filter ? w.experiences.filter(e => e.person_id === filter) : w.experiences;
  return `${heading('收藏每一段真實。','所有已確認的經歷，都帶著原始記錄與發生時間。',link('record','＋ 新的經歷','primary'))}${w.drafts.length && !filter ? `<section class="space-bottom"><div class="section-title"><h2>等待你的確認</h2><span class="tag">草稿不計分</span></div><div class="card">${w.drafts.map(d => `<div class="list-item"><div class="item-main"><h3>${esc(d.raw_text.slice(0,65))}</h3><p>${esc(time(d.occurred_at))} · revision ${d.revision}</p></div>${link('review/' + d.id,'繼續核對 →','text-button')}</div>`).join('')}</div></section>` : ''}<div class="stack">${experiences.length ? experiences.map(e => `<article class="card"><div class="section-title"><span class="tag">已由你確認</span><span class="small muted">${esc(time(e.occurred_at))}</span></div><p class="record-content">${esc(e.summary)}</p><details><summary class="small muted">查看原始紀錄</summary><div class="raw-source space-top">${esc(e.raw_text)}</div></details><p class="record-meta">${esc(w.goals.find(g => g.id === e.goal_id)?.title || '獨立經歷')} · ${esc(w.people.find(p => p.id === e.person_id)?.name || '未關聯人物')}<br>提交保存於 ${esc(time(e.created_at))}</p></article>`).join('') : `<div class="card">${empty('這裡還沒有正式經歷。先記下一次真實行動吧。')}</div>`}</div>`;
}
function peopleView() {
  return `${heading('那些，與你相遇的人。','人物跨目標保存；每筆真實互動，都能回到原始經歷。',button('new-person','＋ 新增人物'))}${state.me.status === 'guest' ? `<div class="upgrade-banner"><h3>為你的關係，建立一個可找回的帳號。</h3><p class="small muted">訪客需先建立本機帳號，才能新增或關聯人物。已保存的目標與草稿會留在原本的世界。</p>${button('claim-dialog','建立帳號，繼續記錄')}</div>` : ''}<div class="grid-equal">${state.world.people.length ? state.world.people.map(p => `<article class="card person-card"><div class="inline-heading"><span class="circle-icon">${esc(p.name.slice(0,1))}</span><div><h3>${esc(p.name)}</h3><span class="small muted">${esc(p.role || '生命中的相遇')}</span></div></div><p class="small muted space-top">${p.interaction_count} 筆已確認的互動紀錄</p>${p.notes ? `<p class="record-content small">${esc(p.notes)}</p>` : ''}<div class="button-row">${link('history?person=' + p.id,'共同經歷 →','text-button')}${link('notes?person=' + p.id,'私人準備／草稿','text-button')}</div></article>`).join('') : `<div class="card">${empty('從一位重要的人，慢慢開始。')}</div>`}</div>`;
}
function notesView() {
  const selected = new URLSearchParams(location.hash.split('?')[1] || '').get('person');
  return `${heading('先練習，再相遇。','這裡是你的私人筆記。模擬不是事實，草稿不代表已送達。')}<div class="grid"><form id="note-form" class="card"><div class="field"><label for="note-kind">這次想做什麼？</label><select id="note-kind" name="kind"><option value="preparation">見面前準備</option><option value="simulation">情境演練筆記</option><option value="message">傳達心意草稿</option></select></div>${personField(selected)}<div class="field"><label for="note-title">標題</label><input id="note-title" name="title" maxlength="160" required placeholder="下一次見面，我想…"></div><div class="field"><label for="note-content">私人內容</label><textarea id="note-content" name="content" required maxlength="20000" placeholder="寫下你的想法、準備或模擬台詞"></textarea></div><div class="callout">不會增加真實互動次數、行動進度或積分；也不會自動發送訊息。目前不提供生成式 AI 多輪演練。</div><button class="primary">保存私人筆記</button></form><div class="stack">${state.world.notes.length ? state.world.notes.map(n => `<article class="card note-card"><span class="tag gold">${{preparation:'私人準備',simulation:'模擬內容，非真人發言',message:'訊息草稿，尚未送出'}[n.kind]}</span><h3 class="space-top">${esc(n.title)}</h3><p class="record-content">${esc(n.content)}</p><p class="record-meta">${esc(time(n.created_at))}</p></article>`).join('') : `<div class="card">${empty('讓想說的話，先有一個安靜的位置。')}</div>`}</div></div>`;
}
async function goalView(goalId) {
  const goal = await api('/goals/' + encodeURIComponent(goalId));
  const calendar = await api('/goals/' + encodeURIComponent(goalId) + '/calendar');
  return `${heading(goal.title,'每一次真實的投入，都會留在這裡。',link('record','記錄本次行動','primary'))}<div class="grid"><div class="stack"><section class="card"><span class="tag">${goal.status === 'completed' ? '已由你確認成果' : '正在成長'}</span><h2 class="space-top">終極成果</h2><p class="record-content">${esc(goal.outcome)}</p>${goalProgress(goal)}<div class="callout">以上是行動累計，不代表終極成果是否達成。你保有最後的確認權。</div></section><section class="card"><h3>接下來 28 天</h3><p class="small muted">星期規律預覽 · ${esc(state.me.timezone)} · 葉色格子代表當天有預定行動</p><div class="calendar-grid">${calendar.map(d => `<div class="calendar-day ${d.action_ids.length ? 'scheduled' : ''}">${esc(d.date.slice(5))}<small>${d.action_ids.length} 項</small></div>`).join('')}</div></section></div><section class="card"><h2>${goal.status === 'completed' ? '這段成果，已經收藏。' : '我已達成成果'}</h2><p class="small muted">提供拍攝或上傳的相關佐證，再由你手動確認。</p><div class="photo-grid">${goal.evidence.map(e => `<a href="/api/evidence/${esc(e.id)}" target="_blank" rel="noopener"><img src="/api/evidence/${esc(e.id)}" alt="${esc(e.filename)}">${esc(e.filename)}</a>`).join('')}</div>${goal.status === 'active' ? `<form id="upload-form" data-goal="${esc(goal.id)}"><div class="field"><label for="evidence-file">拍攝或選擇圖片</label><input id="evidence-file" name="file" type="file" accept="image/png,image/jpeg" required><span class="small muted">手機可在選擇圖片時使用相機。開發設定：PNG／JPEG，最大 ${Math.round(state.world.policy.max_upload_bytes / 1024 / 1024)} MiB。</span></div><button class="secondary">上傳佐證</button></form><form id="complete-form" class="space-top" data-goal="${esc(goal.id)}"><div class="field"><label for="reflection">這段旅程，想留下什麼？（選填）</label><textarea id="reflection" name="reflection" maxlength="4000"></textarea></div><label class="check-line"><input type="checkbox" name="confirmed" required>我已檢視相關佐證，親自確認終極成果已達成。</label><button class="primary" ${goal.evidence.length ? '' : 'disabled'}>確認完成並收藏成果</button>${goal.evidence.length ? '' : '<p class="small muted">請先成功上傳至少一份相關佐證。</p>'}</form>` : `<p class="record-content">${esc(goal.reflection || '每一步，都已經成為這個世界的一部分。')}</p><p class="record-meta">確認完成於 ${esc(time(goal.completed_at))}</p>${link('goal-new','種下下一個目標 →','primary')}`}</section></div>`;
}
async function render() {
  const sequence = ++renderSequence;
  let route = location.hash.slice(1) || 'world';
  if (!state.me) route = 'welcome';
  else if (!state.me.lumi_hatched && !['profile','goal-new'].includes(route)) route = state.me.bio ? 'goal-new' : 'profile';
  if (state.me && state.me.lumi_hatched && route === 'welcome') route = 'world';
  if (route !== 'record') state.editingDraft = false;
  state.route = route; navigation(route.split('?')[0]);
  let html;
  if (route === 'welcome') html = welcomeView();
  else if (route === 'profile') html = profileView();
  else if (route === 'goal-new') html = goalForm();
  else if (route === 'birth') html = `<div class="narrow"><section class="hero"><div class="hero-copy"><div class="eyebrow">A NEW BEGINNING</div><h1>目標蛋誕生了。<br>你好，我是 Lumi。</h1><p>你的方向，讓這個世界有了第一顆種子。從現在起，我們一起慢慢走。</p>${link('world','進入我的世界 →','primary')}</div>${lumi()}</section></div>`;
  else if (route === 'world') html = worldView();
  else if (route === 'goals') html = `${heading('照顧你的目標花園。','每一顆蛋，都有自己的方向與成長節奏。',link('goal-new','＋ 新的目標','primary'))}<div class="grid-equal">${state.world.goals.map(goalCard).join('')}</div>`;
  else if (route.startsWith('goal/')) html = await goalView(route.split('/')[1]);
  else if (route === 'record') html = recordView();
  else if (route.startsWith('review/')) {state.draft = await api('/drafts/' + encodeURIComponent(route.split('/')[1])); html = state.draft.status === 'draft' ? reviewView(state.draft) : historyView();}
  else if (route.startsWith('history')) html = historyView();
  else if (route === 'people') html = peopleView();
  else if (route.startsWith('notes')) html = notesView();
  else html = worldView();
  if (sequence === renderSequence) {$('#app').innerHTML = html; state.dirty = false;}
}
function dialog(content) { $('#account-content').innerHTML = content + '<p id="dialog-error" class="small" role="alert"></p>'; if (!$('#account-dialog').open) $('#account-dialog').showModal(); }
function accountView(mode = 'account') {
  if (mode === 'account' && !state.me) mode = 'login';
  if (mode === 'account') {
    dialog(`<h2 id="account-heading">${esc(state.me.name || '你的世界')}</h2><p class="account-state">${state.me.status === 'guest' ? '目前為訪客 · 尚無帳號恢復保障' : '本機帳號：' + esc(state.me.username)}</p><p class="small muted">資料保存在此電腦的 Python 服務。登出會撤銷這個工作階段，不會刪除已保存資料。${state.dirty ? '請先關閉此視窗，保存尚未送出的內容。' : ''}</p><div class="button-row">${state.me.status === 'guest' ? button('claim-dialog','建立帳號，保存世界') : ''}${button('login-dialog','登入其他帳號','secondary')}${button('logout','登出','danger', state.dirty ? 'disabled' : '')}</div>`);
  } else {
    const claim = mode === 'claim';
    dialog(`<h2 id="account-heading">${claim ? '為你的世界，建立帳號。' : '歡迎回到你的世界。'}</h2><p class="small muted">${claim ? '目標、經歷與草稿仍屬於原本的你；升級後可使用人物功能。' : '登入這台 Python 服務已建立的本機帳號。'}</p><form id="${claim ? 'claim' : 'login'}-form"><div class="field"><label for="username">本機帳號名稱</label><input id="username" name="username" autocomplete="username" required pattern="[a-zA-Z0-9_]{3,30}" placeholder="3–30 字英數或底線"></div><div class="field"><label for="password">密碼</label><input id="password" name="password" type="password" minlength="${claim ? 10 : 1}" maxlength="128" autocomplete="${claim ? 'new-password' : 'current-password'}" required placeholder="${claim ? '至少 10 個字元' : '你的密碼'}"></div><div id="guest-conflict"></div><button class="primary">${claim ? '建立帳號，繼續原本的操作' : '登入我的世界'}</button></form><div class="callout">本機開發驗證模式；沒有驗證信或密碼找回服務。正式部署須接入受管身份服務。</div>`);
  }
}
function formSnapshot() {
  const form = $('#record-form') || $('#review-form') || $('#note-form') || $('#complete-form');
  return form ? {id:form.id, values:[...new FormData(form).entries()], dirty:state.dirty} : null;
}
async function refreshKeepingForm() {
  const saved = formSnapshot(); await refresh(); await render();
  if (saved && $('#' + saved.id)) {
    if (saved.id === 'record-form') {
      const goalId = saved.values.find(([name]) => name === 'goal_id')?.[1];
      $('#contribution-fields').innerHTML = contributionFields(state.world.goals.find(g => g.id === goalId));
    }
    for (const [name,value] of saved.values) {
      const input = document.getElementsByName(name)[0];
      if (input instanceof HTMLInputElement && input.type === 'checkbox') input.checked = true;
      else if (input && !(input instanceof HTMLInputElement && input.type === 'file')) input.value = value;
    }
    state.dirty = saved.dirty;
  }
}
function contributions(form) {
  return [...new FormData(form)].filter(([key,value]) => key.startsWith('quantity-') && value !== '' && Number(value) !== 0).map(([key,value]) => ({action_id:key.slice(9),quantity:value}));
}
async function saveDraft(form, review, destination = 'history') {
  const f = new FormData(form), body = {raw_text:f.get('raw_text'), occurred_at:inputISO(f.get('occurred_at')),goal_id:f.get('goal_id') || null,person_id:f.get('person_id') || null,contributions:contributions(form)};
  if (body.person_id === '__upgrade') throw new Error('請先建立帳號後再選擇人物。');
  let result;
  if (state.editingDraft && state.draft?.status === 'draft') result = await api('/drafts/' + state.draft.id,{method:'PUT',body:{...body,expected_revision:state.draft.revision}});
  else result = await api('/experiences/drafts',{method:'POST',body});
  state.draft = result; state.editingDraft = false; state.dirty = false; await refresh();
  if (review) navigate('review/' + result.id); else {toast('草稿已保存至伺服器，尚未加分。'); navigate(destination);}
}
function leaveDialog(route) {
  state.pendingRoute = route;
  dialog(`<h2 id="account-heading">離開前，留住這段內容。</h2><p class="small muted">目前有尚未保存的修改。你可以繼續編輯，或明確捨棄修改後離開。${$('#record-form') ? '這份原始記錄也可以先存成草稿。' : ''}</p><div class="button-row">${$('#record-form') ? button('save-and-leave','先存草稿並離開') : ''}${button('stay-on-form','繼續編輯','secondary')}${button('discard-and-leave','捨棄未保存修改並離開','danger')}</div>`);
}
document.addEventListener('click', event => {
  const anchor = event.target.closest('a[href^="#"]');
  if (anchor && state.dirty && anchor.hash.slice(1) !== state.route) {
    event.preventDefault(); leaveDialog(anchor.hash.slice(1));
  }
}, true);
document.addEventListener('input', event => { if (event.target.closest('#app form')) state.dirty = true; });
document.addEventListener('change', async event => {
  try {
    if (event.target.name === 'goal_id' && $('#record-form')) {
      $('#contribution-fields').innerHTML = contributionFields(state.world.goals.find(g => g.id === event.target.value));
    }
    if (event.target.name === 'person_id' && event.target.value === '__upgrade') {event.target.value = ''; accountView('claim');}
    if (event.target.dataset.task) {
      const result = await api('/tasks/' + event.target.dataset.task, {method:'PATCH',body:{done:event.target.checked}});
      const task = state.world.tasks.find(t => t.id === result.id); task.done = result.done; toast('待辦狀態已保存；不會重複增加行動進度。');
    }
  } catch (error) {showError(error); if (event.target.dataset.task) event.target.checked = !event.target.checked;}
});
document.addEventListener('click', async event => {
  const target = event.target.closest('[data-action]'); if (!target) return;
  const action = target.dataset.action; target.disabled = true;
  try {
    if (action === 'guest') {const me = await api('/auth/guest',{method:'POST'}); state.me = me; state.csrf = me.csrf_token; await refresh(); navigate('profile');}
    if (action === 'account') accountView();
    if (action === 'claim-dialog') accountView('claim');
    if (action === 'login-dialog') accountView('login');
    if (action === 'close-account') $('#account-dialog').close();
    if (action === 'stay-on-form') {state.pendingRoute = null; $('#account-dialog').close();}
    if (action === 'discard-and-leave') {const route = state.pendingRoute; state.pendingRoute = null; $('#account-dialog').close(); navigate(route);}
    if (action === 'save-and-leave') {await saveDraft($('#record-form'), false, state.pendingRoute); state.pendingRoute = null; $('#account-dialog').close();}
    if (action === 'logout') {
      await api('/auth/logout',{method:'POST'}); $('#account-dialog').close(); state.me = null; state.world = null; state.csrf = ''; state.draft = null; state.candidate = null; state.requests.clear(); navigate('welcome');
    }
    if (action === 'new-person') {
      if (state.me.status === 'guest') accountView('claim');
      else dialog('<h2 id="account-heading">記下一位重要的人。</h2><form id="person-form"><div class="field"><label for="person-name">稱呼</label><input id="person-name" name="name" maxlength="100" required></div><div class="field"><label for="person-role">你們的關係（選填）</label><input id="person-role" name="role" maxlength="100"></div><div class="field"><label for="person-notes">人工紀錄（選填）</label><textarea id="person-notes" name="notes" maxlength="4000"></textarea></div><button class="primary">保存人物</button></form>');
    }
    if (action === 'edit-current-draft') {state.editingDraft = true; navigate('record');}
    if (action === 'suggest') {
      const result = await api('/drafts/' + state.draft.id + '/suggest',{method:'POST'}); state.candidate = result.summary;
      $('#candidate-panel').innerHTML = `<div class="callout"><b>整理候選，尚未套用</b><p>${esc(result.notice || '')}</p><div class="raw-source">${esc(result.summary)}</div>${button('apply-candidate','套用到摘要','secondary')}${button('dismiss-candidate','保留目前摘要','text-button')}</div>`;
    }
    if (action === 'apply-candidate') {$('#summary').value = state.candidate; $('#candidate-panel').innerHTML = ''; state.candidate = null; state.dirty = true;}
    if (action === 'dismiss-candidate') {$('#candidate-panel').innerHTML = ''; state.candidate = null;}
  } catch (error) { showError(error); }
  finally {target.disabled = false;}
});
document.addEventListener('submit', async event => {
  const form = event.target; event.preventDefault();
  const submitter = event.submitter; const buttons = [...form.querySelectorAll('button')]; buttons.forEach(b => b.disabled = true); $('#notice').innerHTML = '';
  try {
    const f = new FormData(form);
    if (form.id === 'profile-form') {await api('/profile',{method:'PUT',body:Object.fromEntries(f)}); await refresh(); navigate('goal-new');}
    if (form.id === 'goal-form') {
      const body = {title:f.get('title'),outcome:f.get('outcome'),actions:[0,1,2].map(i => ({title:f.get('title'+i),unit:f.get('unit'+i),target:f.get('target'+i),level:Number(f.get('level'+i)),weekdays:f.getAll('days'+i).map(Number)}))};
      const wasHatched = state.me.lumi_hatched; const goal = await api('/goals',{method:'POST',body:{...body,request_id:requestId('goal:create',body)}});
      state.draft = null; await refresh(); navigate(wasHatched ? 'goal/' + goal.id : 'birth');
    }
    if (form.id === 'record-form') await saveDraft(form, submitter?.value !== 'save');
    if (form.id === 'review-form') {
      const body = {expected_revision:state.draft.revision,summary:f.get('summary'),person_id:f.get('person_id') || null,contributions:contributions(form),tasks:String(f.get('tasks')).split('\n').map(x => x.trim()).filter(Boolean)};
      const result = await api('/drafts/' + state.draft.id + '/confirm',{method:'POST',body:{...body,request_id:requestId('confirm:' + state.draft.id,body)}});
      state.draft = null; state.candidate = null; await refresh(); navigate('history'); toast(`已確認保存，本次增加 ${result.points_awarded} 積分。`);
    }
    if (form.id === 'claim-form') {
      const me = await api('/auth/claim',{method:'POST',body:Object.fromEntries(f)}); state.csrf = me.csrf_token; $('#account-dialog').close();
      await refreshKeepingForm(); toast('帳號已建立，原本的世界與草稿都在。');
    }
    if (form.id === 'login-form') {
      try {
        const me = await api('/auth/login',{method:'POST',body:{username:f.get('username'),password:f.get('password'),discard_guest:f.get('discard_guest') === 'on'}});
        state.csrf = me.csrf_token; state.me = me; state.draft = null; state.candidate = null; state.requests.clear(); $('#account-dialog').close(); await refresh(); navigate('world');
      } catch (error) {
        if (error.code === 'guest_conflict') $('#guest-conflict').innerHTML = '<div class="callout error-message">登入不會匯入或合併訪客資料。離開這個訪客身分後，可能無法再取得原世界。<label class="check-line"><input type="checkbox" name="discard_guest" required>我了解，仍要離開訪客世界並登入。</label></div>';
        throw error;
      }
    }
    if (form.id === 'person-form') {
      const person = await api('/people',{method:'POST',body:Object.fromEntries(f)}); $('#account-dialog').close(); await refreshKeepingForm();
      if ($('#person-id')) {$('#person-id').value = person.id; state.dirty = true;} toast('人物已保存。');
    }
    if (form.id === 'note-form') {const body = Object.fromEntries(f); body.person_id ||= null; await api('/notes',{method:'POST',body}); await refresh(); state.dirty = false; await render(); toast('私人筆記已保存，不計入真實成果。');}
    if (form.id === 'upload-form') {await api('/goals/' + form.dataset.goal + '/evidence',{method:'POST',body:f}); await refreshKeepingForm(); toast('佐證已上傳並可回讀。');}
    if (form.id === 'complete-form') {
      const goal = await api('/goals/' + form.dataset.goal);
      const body = {evidence_ids:goal.evidence.map(e => e.id),confirmed:f.get('confirmed') === 'on',reflection:f.get('reflection') || ''};
      await api('/goals/' + goal.id + '/complete',{method:'POST',body:{...body,request_id:requestId('complete:'+goal.id,body)}});
      await refresh(); state.dirty = false; await render(); toast('成果已由你確認，這段努力已收藏。');
    }
  } catch (error) {showError(error);}
  finally {buttons.forEach(b => b.disabled = false);}
});
window.addEventListener('hashchange', () => {
  const destination = location.hash.slice(1);
  if (state.dirty && destination !== state.route) {history.replaceState(null, '', '#' + state.route); leaveDialog(destination); return;}
  $('#notice').innerHTML = ''; render().catch(showError);
});
$('#account-dialog').addEventListener('close', () => {$('#account-content').replaceChildren();});
window.addEventListener('beforeunload', event => {if (state.dirty) {event.preventDefault(); event.returnValue = '';}});
window.addEventListener('offline', () => {$('#notice').innerHTML = '<div class="callout error-message">目前離線；尚未送出的內容沒有保存成功。請保留此頁，連線後再試。</div>';});
async function start() {
  try {await refresh();}
  catch (error) {if (error.status !== 401) showError(error);}
  await render();
}
start().catch(showError);
