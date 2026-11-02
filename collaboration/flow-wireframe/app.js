'use strict';
// 此展示只讀寫專用 localStorage；不載入帳號、正式 API、音檔或 AI 服務。
const KEY = 'lifeworld:flow-wireframe:v1';
const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stamp = () => new Date().toLocaleString('sv-SE').replace(' ','T').slice(0,16);
const dateNow = () => (s.demoTime || stamp()).slice(0,10);
const eventNow = () => s.demoTime || stamp();
const shift = (day,n) => {const d=new Date(day+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10);};
const weekday = value => (new Date(value+'T12:00:00Z').getUTCDay()+6)%7;
const names = ['一','二','三','四','五','六','日'];
const initial = () => ({name:'',route:'intro',goal:null,archived:[],wizard:null,records:[],tasks:[],draft:null,notes:[],roster:[],rehearsal:null,rehearsalHistory:[],rehearsalSources:[],privateDrafts:{},points:0,people:[{id:'zhe',name:'阿哲',role:'朋友',food:'不吃辣',source:'2025-07-12 海邊旅行：阿哲說今天想吃清淡一點、不吃辣。（虛構示例）'},{id:'an',name:'小安',role:'同學',food:'尚未了解'},{id:'jun',name:'怡君',role:'攝影夥伴',food:'尚未了解'}],selected:'zhe',tab:'人物總覽',relation:'交會',focus:'zhe',story:0,trail:[],historyTab:'已完成',demo:{pack:0,role:0,scenario:0,turns:[],done:false},night:{choice:null,start:'23:00',end:'07:00',enabled:true}});
let s;
try {s=JSON.parse(localStorage.getItem(KEY));} catch {}
if(!s||!Array.isArray(s.people)) s=initial();
s.archived ||= [];
s.demo ||= {pack:0,role:0,scenario:0,turns:[],done:false};
s.privateDrafts ||= {};
s.roster ||= [];s.rehearsalHistory ||= [];s.rehearsalSources ||= [];
s.rehearsalHistory.forEach((item,index)=>{item.legacyId ||= `legacy-${index}`;}); // 舊紀錄新增穩定檢視 ID，不補造快照。
s.tasks ||= [];
// 重整後不會有舊計時器；中斷的視覺流程回到可點擊起點，目標資料保留。
if(s.hatch&&s.hatch.stage!=='complete')s.hatch.stage='idle';
if(s.goal&&!s.goal.id)s.goal.id='restored-demo-goal';
ensureActionIds(s.goal);s.archived.forEach(ensureActionIds);
TheaterUI.connect({people:()=>s.people,go});
function goalStatus(){return s.goal?.status==='進行中'&&dateNow()>s.goal.deadline?'待回顧':s.goal?.status;}
let hatchTimer=null;
let feedback='',voice='idle',inputMode='文字',edit=null,scene='見面前準備',privateText='',nightOverride=null,attachment=null;
const stories=[{title:'海邊旅行',date:'2025-07-12',text:'那天下午一起拍照、散步，阿哲提議留下旅行照片。',people:['zhe','an'],tags:'海邊 · 旅行'},{title:'畢業聚會',date:'2026-06-20',text:'小安與怡君在聚會中分享畢業後的計畫。',people:['an','jun'],tags:'學校 · 聚會'},{title:'攝影活動',date:'2026-08-08',text:'與怡君參加攝影活動，練習捕捉街道上的光。',people:['jun'],tags:'攝影 · 學習'}];
// 示範包只呈現互動契約，預寫回應不代表歐桑完整人物包或真實 AI。
const packs=[{name:'三國策略',roles:['曹操','劉備','諸葛亮','孫權','周瑜'],scenes:['赤壁前夕策略／結盟','假設糧運／撤軍協商']},{name:'國際協調',roles:['美方代表','伊方代表','中立調停者','國際組織觀察員','航運方代表'],scenes:['假設停火與議程','航運安全／查核協商']},{name:'哲學辯論',roles:['蘇格拉底','孔子','莊子','尼采','柏拉圖'],scenes:['成功與自由','承諾、責任與個人選擇']}];
// 這些頭像只屬於三組示範包，不混入使用者的人物收藏冊。
const packPortraits=[['portrait-three-kingdoms-caocao.256.png','portrait-three-kingdoms-liubei.256.png','portrait-three-kingdoms-zhugeliang.256.png','portrait-three-kingdoms-sunquan.256.png','portrait-three-kingdoms-zhouyu.256.png'],['portrait-international-dialogue-us-representative@256.png','portrait-international-dialogue-iran-representative@256.png','portrait-international-dialogue-neutral-mediator@256.png','portrait-international-dialogue-international-observer@256.png','portrait-international-dialogue-shipping-representative@256.png'],['portrait-philosophy-socrates-256.png','portrait-philosophy-confucius-256.png','portrait-philosophy-zhuangzi-256.png','portrait-philosophy-nietzsche-256.png','portrait-philosophy-plato-256.png']];
const goalLabel = g => g.status==='進行中'?(g.id===s.goal?.id&&goalStatus()==='待回顧'?'待回顧':'挑戰中'):g.status==='已完成'?'已完成':'已結束';
// 關聯依已確認參與保存；不把全部人物自動綁到下一個目標。
const recordParticipants = r => Array.isArray(r.peopleLinks)?r.peopleLinks.filter(p=>p.relation==='participant').map(p=>p.id):r.person&&r.personId?[r.personId]:[];
const relatedPeople = g => [...new Set(s.records.filter(r=>r.goalId===g.id).flatMap(recordParticipants))];
const personGoals = id => [...s.archived,...(s.goal&&!s.archived.some(g=>g.id===s.goal.id)?[s.goal]:[])].filter(g=>relatedPeople(g).includes(id));
const allStories = () => [...stories,...s.records.filter(r=>recordParticipants(r).length).map(r=>({title:r.summary,date:r.occurred.slice(0,10),text:r.summary,people:recordParticipants(r),tags:'已確認的原型經歷'}))];
const who = id => s.people.find(p=>p.id===id) || s.people[0];
function save(){try{localStorage.setItem(KEY,JSON.stringify(s));}catch{feedback='無法保存本機原型資料，請勿關閉頁面。';}}
function say(text){feedback=text;$('#feedback').textContent=text;}
function go(route){
  if(s.route==='theater-live'&&route!=='theater-live')TheaterUI.leave(); // 離開活動頁就作廢尚未展示的回應。
  if(s.route==='birth'&&route!=='birth'){stopHatch();if(s.hatch?.stage!=='complete'&&s.hatch)s.hatch.stage='idle';}
  const continuing=route==='theater-live'&&s.route===route;
  s.route=route;feedback='';save();render();
  if(continuing){
    // 劇場每次重繪只捲動對話容器，並讓發言欄回到視窗內，避免玩家反覆手動找輸入框。
    requestAnimationFrame(()=>{const log=$('.theater-transcript'),input=$('#theater-speech');if(log)log.scrollTop=log.scrollHeight;input?.scrollIntoView({block:'center'});if(input&&!input.disabled)input.focus({preventScroll:true});});
  }else{window.scrollTo(0,0);$('#title')?.focus({preventScroll:true});}
}
const button = (text,action,cls='') => `<button type="button" data-action="${action}" class="${cls}">${text}</button>`;
const link = (text,route,cls='') => `<button type="button" data-go="${route}" class="${cls}">${text}</button>`;
// 導覽筆畫沿用已合併 UI kit 的 world／goal／record／relation 向量圖示，文字仍是可讀名稱。
const navPaths={world:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',goal:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',records:'<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',connections:'<circle cx="8" cy="8" r="3"/><circle cx="17" cy="15" r="3"/><path d="m10.5 9.5 4 3.5M3 20c0-3 2-5 5-5h3"/>'};
const navIcon = route => `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${navPaths[route]}</svg>`;
const title = (text,implemented=true) => `<span class="tag ${implemented?'':'planned'}">${implemented?'App 已實作對應能力':'規劃模擬 · 尚未串接 App'}</span><h1 id="title" tabindex="-1">${esc(text)}</h1>`;
const field = (label,id,value='',type='text',extra='') => `<label class="label" for="${id}">${label}</label><input id="${id}" type="${type}" value="${esc(value)}" ${extra}>`;
const text = (label,id,value='') => `<label class="label" for="${id}">${label}</label><textarea id="${id}">${esc(value)}</textarea>`;
const check = (label,id,checked=false) => `<label class="check"><input id="${id}" type="checkbox" ${checked?'checked':''}>${label}</label>`;
const dates = (start,end) => {const out=[];for(let d=start;d<=end&&out.length<10000;d=shift(d,1))out.push(d);return out;};
// 舊版「週次＋單一星期」只轉為等價格子；新格子可獨立選取，月份不是固定 28 天。
function monthPattern(a,month){
  const old=a.monthlyDraft||a.monthlyRule;
  const slots=old?.slots?.map(x=>({...x}))||old?.ordinals?.map(nth=>({nth,weekday:Number(old.weekday)}))||[];
  return {slots:slots.filter(x=>x.nth>=1&&x.nth<=4),repeat:old?.repeat!==false,month:old?.month||month};
}
const matchesMonthly = (day,rule) => rule.slots.some(slot=>weekday(day)===slot.weekday&&Math.floor((Number(day.slice(-2))-1)/7)+1===slot.nth);
function monthPatternText(rule){
  const groups=names.map((name,weekday)=>({name,ordinals:rule.slots.filter(x=>x.weekday===weekday).map(x=>x.nth).sort()})).filter(x=>x.ordinals.length);
  return groups.map(x=>(rule.repeat?'每月':'僅 '+rule.month)+'第 '+x.ordinals.join('、')+' 個週'+x.name).join('；')||'選取想安排的格子';
}
function monthPatternEditor(a,month){
  const draft=monthPattern(a,month);
  const rows=[1,2,3,4].map(nth=>`<div class="month-pattern-week"><span class="month-pattern-label">第 ${nth} 週</span><div class="month-pattern-cells">${names.map((name,weekday)=>`<button type="button" data-action="month-slot:${nth}-${weekday}" data-month-slot="${nth}-${weekday}" aria-label="第 ${nth} 週，週${name}" aria-pressed="${draft.slots.some(x=>x.nth===nth&&x.weekday===weekday)}">${draft.slots.some(x=>x.nth===nth&&x.weekday===weekday)?'✓':'＋'}</button>`).join('')}</div></div>`).join('');
  return `<fieldset class="monthly-rule"><legend>每月固定日期規律</legend><p class="muted">每格獨立選取，四週可以安排不同日子。</p><div class="month-pattern-head" aria-hidden="true">${names.map(name=>'<span>'+name+'</span>').join('')}</div><div class="month-pattern" role="group" aria-label="每月四週安排">${rows}</div>${check('每月重複這份安排','month-pattern-repeat',draft.repeat)}<p class="muted">${draft.repeat?'套用至整個挑戰期間的各月份。':'只套用目前檢視月份 '+month+'，其他月份保留。'}每格代表該月第幾個星期幾，第 5 次不自動安排，可在日曆補選。</p><div class="monthly-preview"><span>${esc(monthPatternText(draft))}</span>${button('套用每月規律','monthly-apply','secondary')}</div></fieldset>`;
}
function isQuiet(){
  if(nightOverride!==null)return nightOverride;
  const now=(s.demoTime||stamp()).slice(11,16),n=s.night;
  const within=n.start>n.end?now>=n.start||now<n.end:now>=n.start&&now<n.end;
  return n.choice===true&&n.enabled&&within;
}
function nightPrompt(){
  const now=(s.demoTime||stamp()).slice(11,16),within=now>='23:00'||now<'07:00';
  $('#night-prompt').innerHTML=s.night.choice===null&&within?`<b>晚上了，要讓世界安靜一點嗎？</b><p>規劃模擬：同意後於當地 23:00–07:00 自動切換，可在設定更改。</p><div class="row">${button('同意夜間自動切換','night-yes','primary')}${button('暫不啟用','night-no')}</div>`:'';
  document.body.className=isQuiet()?'quiet':'';
}
function calendar(a,start,end,index=0){
  const cursor=a.cursor||start,month=cursor.slice(0,7),first=month+'-01';
  const last=new Date(Number(month.slice(0,4)),Number(month.slice(5)),0).getDate();
  const lo=a.cycle==='week'?shift(cursor,-weekday(cursor)):first;
  const hi=a.cycle==='week'?shift(lo,6):month+'-'+last;
  const mode=a.scheduleMode||'dates';
  const hasDates=dates(lo,hi).some(d=>d>=start&&d<=end);
  const modes=[['dates','自選日期'],['weekly','每週固定'],['monthly','每月固定']];
  const modeTabs=`<div class="schedule-modes" role="group" aria-label="選擇安排方式">${modes.map(([id,label])=>`<button type="button" data-action="schedule-mode:${id}" aria-pressed="${mode===id}">${label}</button>`).join('')}</div>`;
  const monthly=mode==='monthly'?monthPatternEditor(a,month):'';
  const weekly=mode==='weekly'?`<div class="weekday-pills" role="group" aria-label="每週固定星期">${names.map((n,i)=>{
    const eligible=dates(start,end).filter(d=>weekday(d)===i),pressed=eligible.length>0&&eligible.every(d=>a.dates.includes(d));
    return `<button type="button" data-action="weekday:${i}" aria-pressed="${pressed}">每週${n}</button>`;
  }).join('')}</div>`:'';
  const deadlineEditor=!edit&&a.deadlineOpen?`<div class="deadline-editor">${field('調整挑戰截止日','schedule-deadline',end,'date',`min="${start}"`)}${button('確認截止日','schedule-deadline','secondary')}<p class="muted">此日期適用於同一目標的三個習慣。</p></div>`:'';
  return `<section class="schedule-editor" aria-label="習慣日期安排"><div class="schedule-period"><span>挑戰期間 <b>${start} ～ ${end}</b></span>${!edit?button('調整截止日','schedule-deadline-open','text-button'):''}</div>${deadlineEditor}${modeTabs}${monthly}${weekly}<div class="schedule-shortcuts">${button('平日','weekdays')}${button('每天','daily')}${button('清除安排','clear')}</div><div class="calendar-toolbar"><div class="calendar-period"><button type="button" data-action="prev-month" aria-label="上一個月">‹</button><b>${esc(a.cycle==='week'?lo+' ～ '+hi:month)}</b><button type="button" data-action="next-month" aria-label="下一個月">›</button></div><div class="view-switch" role="group" aria-label="日曆檢視"><button type="button" data-action="month" aria-pressed="${a.cycle!=='week'}">按月檢視</button><button type="button" data-action="week" aria-pressed="${a.cycle==='week'}">按週檢視</button></div></div>${!hasDates?'<p class="calendar-notice" role="status">這個月不在挑戰期間。可返回期間內，或調整截止日後再選日期。</p>':''}<div class="calendar-weekdays" aria-hidden="true">${names.map(n=>'<span>'+n+'</span>').join('')}</div><div class="calendar">${a.cycle==='week'?'':'<span class="offset"></span>'.repeat(weekday(first))}${dates(lo,hi).map(d=>`<button type="button" data-action="day:${d}" class="${a.dates.includes(d)?'selected':''} ${d<start||d>end?'outside':''}" ${d<start||d>end?'disabled title="不在挑戰期間"':''} aria-pressed="${a.dates.includes(d)}" aria-label="${d}">${Number(d.slice(-2))}${a.dates.includes(d)?'<small aria-hidden="true">✓</small>':''}</button>`).join('')}</div><div class="schedule-summary"><b>已安排 ${a.dates.length} 天</b><span>每次 ${esc(a.quantity)} ${esc(a.unit)}</span></div>${a.monthlyRule?`<p class="monthly-summary">目前規律：${esc(monthPatternText(monthPattern({monthlyRule:a.monthlyRule},month)))}</p>`:''}<p class="muted schedule-hint">點選日期可微調；安排代表打算做，不是已完成。</p></section>`;
}
function newWizard(){s.wizard={step:0,title:'',outcome:'',deadline:'',start:dateNow(),actions:[0,1,2].map(()=>({title:'',quantity:'1',unit:'次',dates:[],cycle:'month'}))};}
function wizard(){
  if(!s.wizard)newWizard();const w=s.wizard,i=w.step-2,a=w.actions[i];
  let content='';
  if(w.step===0)content=field('目標名稱','goal-name',w.title,'text','required maxlength="160"');
  if(w.step===1)content=text('達成的樣子','goal-outcome',w.outcome)+field('截止日','deadline',w.deadline,'date',`required min="${w.start}"`);
  if(a)content=field('習慣名稱','habit-name',a.title,'text','required')+`<details><summary>每次預期 ${esc(a.quantity)} ${esc(a.unit)} · 調整</summary>${field('每次預期量','habit-quantity',a.quantity,'number','required min="0.000001" max="1000000000000" step="0.000001"')}${field('單位','habit-unit',a.unit,'text','required')}</details>`+calendar(a,w.start,w.deadline,i);
  if(w.step===5)content=`<h2>${esc(w.title)}</h2><p>${esc(w.outcome)}</p><p>${w.start} ～ ${w.deadline}</p>${w.actions.map(a=>`<p><b>${esc(a.title)}</b> · ${a.dates.length} 天，每次 ${esc(a.quantity)} ${esc(a.unit)}</p>`).join('')}<div class="callout">確認前不建目標、不發獎勵；只在實際 App 確認真實經歷後增加正式成果。</div>`;
  return title(['為目標取名','達成的樣子與期限','第一個重要習慣','第二個重要習慣','第三個重要習慣','檢查這次挑戰'][w.step])+`<form id="wizard" class="card narrow"><p class="steps">第 ${w.step+1}／6 步 · 此裝置自動保存草稿</p>${content}<div class="actions">${w.step?button('上一步','wizard-back'):''}<button class="primary">${w.step===5?'確認開始挑戰':'下一步'}</button>${link('稍後繼續','world')}</div></form>`;
}
// 動畫呈現已建立的目標結果；重播與跳過都不重建資料或發獎。
function stopHatch(){if(hatchTimer)clearTimeout(hatchTimer);hatchTimer=null;}
function finishHatch(){stopHatch();s.hatch={goalId:s.goal?.id,stage:'complete'};s.lumiBorn=true;save();render();}
function playHatch(){
  stopHatch();
  if(isQuiet()||matchMedia('(prefers-reduced-motion: reduce)').matches){finishHatch();return;}
  const stages=['glow','crack','split','reveal','complete'];let index=0;
  function step(){
    if(s.route!=='birth')return;
    s.hatch={goalId:s.goal?.id,stage:stages[index++]};save();render();
    if(index<stages.length)hatchTimer=setTimeout(step,700);
    else{s.lumiBorn=true;save();hatchTimer=null;}
  }
  step();
}
function birth(){
  const stage=s.hatch?.goalId===s.goal?.id?s.hatch.stage:'idle';
  const complete=stage==='complete',playing=stage!=='idle'&&!complete;
  const status={idle:'輕點這顆蛋，迎接 Lumi。',glow:'蛋開始發出微光。',crack:'出現了一道裂紋。',split:'蛋殼正在打開。',reveal:'Lumi 來到你的世界。',complete:'Lumi 會陪你走過這次挑戰。'}[stage];
  const egg=stage==='glow'?'goal-egg-glow@512.png':stage==='crack'?'goal-egg-initial@512.png':'goal-egg-rest@256.png';
  return title('一個新的開始',false)+`<section class="card hero hatch-card"><h2>你的第一步，讓世界有了新夥伴</h2><div class="hatch-stage" data-stage="${stage}"><div class="hatch-aura"></div><img class="hatch-lumi" src="assets/welcome@256.png" alt="迎接你的 Lumi"><img class="hatch-shell left" src="assets/shell-left@512.png" alt=""><img class="hatch-shell right" src="assets/shell-right@512.png" alt="">${stage==='idle'?`<button type="button" class="hatch-trigger" data-action="hatch-start" aria-label="點擊目標蛋，喚醒 Lumi"><img src="assets/${egg}" alt="目標蛋"><span>輕點目標蛋</span></button>`:`<img class="hatch-egg" src="assets/${egg}" alt="正在孵化的目標蛋">`}</div><p class="hatch-status" role="status">${status}</p><div class="actions hatch-actions">${playing?button('跳過動畫','hatch-skip'):''}${complete?button('重播破蛋','hatch-start'):''}${link('進入我的世界','world','primary')}</div><p class="muted">${isQuiet()?'安靜模式以靜態結果迎接 Lumi。':'可跳過或重播，挑戰資料都會保留。'}</p></section>`;
}
function world(){
  const quiet=isQuiet(),mode=quiet?'quiet':'day';
  const scene=`<div class="world-scene"><picture><source media="(max-width: 600px)" srcset="assets/room-${mode}@768x1024.png"><img class="world-room-image" src="assets/room-${mode}@1280x960.png" alt="${quiet?'安靜房間':'日間房間'}"></picture><img class="world-lumi-image" src="assets/${quiet?'quiet':'idle'}@256.png" alt="${quiet?'安靜的 Lumi':'日間的 Lumi'}">${s.goal?'<img class="world-goal-egg" src="assets/goal-egg-rest@256.png" alt="目前目標蛋">':''}</div>`;
  return title(quiet?'你的世界會在這裡':'你的世界，歡迎回來',!quiet)+`<div class="grid"><section class="card hero world-hero"><h2>Lumi</h2>${scene}<p>${quiet?'辛苦了，今晚不用急著做更多事。':'每一段投入，都值得被留下。'}</p><small>房間、Lumi 與目標蛋沿用 UI kit 候選美術；此頁仍是獨立原型。</small></section><section class="card"><h2>${esc(s.goal?.title||'讓故事有個起點')}</h2><p>${s.goal?'三個習慣，照自己的步調前進。':'先建立一個目標，或載入虛構示例預覽其他流程。'}</p>${s.goal?link('查看目前挑戰','goal','primary'):link(s.wizard?'繼續建立目標':'建立第一個目標','wizard','primary')}<div class="actions">${link('記錄新經歷','record','primary')}${s.draft?link('繼續草稿','record'):''}</div><p>已確認經歷 ${s.records.length} 筆 · 排程只代表打算做</p>${link('人物劇場','theater-hub')}</section></div><section class="card"><h2>旅途中遇見的人</h2><p>沿著共同經歷，重新遇見另一段故事。</p>${link('探索交會','connections')}${link('人物收藏冊','cards')}</section>`;
}
function pendingPreview(g){
  // 原型也將延後採計與首次確認分開，避免演示時暗示重複獎勵。
  const rows=s.records.filter(r=>r.goalId===g.id&&(r.pending||r.unapplied));
  return rows.length?`<section class="card"><h2>待處理與未採計貢獻</h2>${rows.map(r=>`<article><p>${esc(r.summary)} · 發生 ${esc(r.occurred)}</p><p>${r.unapplied?'未採計':'等待逐筆核對'}</p>${r.pending&&goalStatus()==='進行中'?check('我已核對這筆貢獻','accept-'+r.id)+button('確認採計這筆貢獻','accept:'+r.id):''}</article>`).join('')}<p>採計不再發獎勵；需先延長並核對發生日期。</p></section>`:'';
}
function goalPage(){
  const g=s.goal;ensureActionIds(g);if(!g)return title('目前挑戰')+link('建立第一個目標','wizard','primary')+link('目標旅程','journey');
  if(edit)return title('調整未來安排')+`<form id="habit-edit" class="card">${edit.actions.map((a,i)=>`<details ${i===0?'open':''}><summary>${esc(a.title)}</summary>${field('更正名稱 '+(i+1),'edit-name-'+i,a.title)}${field('明天起用量 '+(i+1),'edit-quantity-'+i,a.quantity,'number','min="0.000001" max="1000000000000" step="0.000001" required')}<p>固定單位：${esc(a.unit)}；用途不替換。</p></details>`).join('')}<p>用量從 ${shift(dateNow(),1)} 起生效；今天與歷史不回算。日期調整請在下方各習慣選取。</p><select id="edit-index" aria-label="選擇要調整的習慣">${edit.actions.map((a,i)=>`<option value="${i}" ${i===edit.index?'selected':''}>${esc(a.title)}</option>`).join('')}</select>${calendar(edit.actions[edit.index],dateNow(),edit.deadline||g.deadline)}${check('我已核對變更與生效日','edit-confirm')}<div class="actions"><button class="primary">確認修改</button>${button('取消修改','cancel-edit')}</div></form>`;
  return title('目前挑戰')+`<section class="card"><h2>${esc(g.title)}</h2><p>${esc(g.outcome)}</p><p>${g.start} ～ ${g.deadline} · ${goalStatus()}</p>${g.actions.map(a=>`<article><h3>${esc(a.title)}</h3><p>${a.dates.length} 個已安排日 · 原始每次 ${esc(a.quantity)} ${esc(a.unit)}${a.next?' · '+a.next.from+' 起 '+esc(a.next.quantity)+' '+esc(a.unit):''}</p>${button('記錄'+esc(a.title),'record-action:'+a.id)}</article>`).join('')}<div class="actions">${goalStatus()==='進行中'?button('調整未來安排','edit-habits'):''}${link('記錄本次行動','record')}${['進行中','待回顧'].includes(goalStatus())?link('回顧這次挑戰','goal-review'):''}${link('目標旅程','journey')}</div></section>${pendingPreview(g)}`;
}
// 新人物先放在本次草稿；只有最後逐位確認才加入收藏冊，提及者不成為共同經歷參與者。
function draftPeople(){
  const d=s.draft;
  if(!Array.isArray(d.peopleLinks)){
    const p=d.person?s.people.find(p=>p.id===(d.personId||s.selected)):null;
    d.peopleLinks=p?[{key:p.id,id:p.id,name:p.name,role:p.role,relation:'participant'}]:[];
  }
  return d.peopleLinks;
}
function recordPeople(){
  const links=draftPeople();
  return `<section class="record-people"><div class="row between"><h3>這段經歷有哪些人？</h3><span class="muted">選填</span></div><p class="muted">可加入多人，並區分實際參與或只在故事中被提到。</p>${links.map((p,i)=>`<div class="record-person-row"><div><b>${esc(p.name)}</b><small>${p.isNew?'新人物草稿':esc(p.role||'已建立人物')}</small></div><label class="sr-only" for="record-person-relation-${i}">${esc(p.name)}在這段經歷中的角色</label><select id="record-person-relation-${i}" data-person-relation="${i}"><option value="participant" ${p.relation==='participant'?'selected':''}>實際參與</option><option value="mentioned" ${p.relation==='mentioned'?'selected':''}>僅被提及</option></select><button type="button" data-action="record-remove-person:${esc(p.key)}" aria-label="移除${esc(p.name)}">×</button></div>`).join('')}<div class="row">${button('關聯已有人物','record-add-existing')}${button('新增人物','record-add-new')}</div>${links.some(p=>p.isNew)?'<p class="muted">新人物仍是草稿，確認經歷時可逐位決定是否建立。</p>':''}</section>`;
}
function openPeoplePicker(){
  const dialog=$('#people-picker'),selected=draftPeople().map(p=>p.id);
  dialog.innerHTML=`<h2>關聯已有人物</h2>${field('搜尋已有人物','people-search')}<div id="people-options">${s.people.filter(p=>!selected.includes(p.id)).map(p=>`<button type="button" data-action="record-choose-person:${esc(p.id)}" aria-label="選取${esc(p.name)}">選取${esc(p.name)}<small>${esc(p.role||'已建立人物')}</small></button>`).join('')||'<p>目前人物都已加入。</p>'}</div>${button('取消選取','record-picker-cancel')}`;
  dialog.showModal();$('#people-search').focus();
}
function openNewPerson(){
  const d=s.draft.newPersonDraft||{name:'',role:''},dialog=$('#new-person-dialog');
  dialog.innerHTML=`<form id="new-record-person"><h2>新增人物草稿</h2><p>先記住稱呼，詳細資訊之後再補。最後確認前不會加入人物收藏冊。</p>${field('新人物稱呼','new-person-name',d.name,'text','required maxlength="80"')}${field('與你的關係或角色','new-person-role',d.role,'text','maxlength="80"')}<p id="new-person-error" role="alert"></p><div class="actions"><button class="primary">加入本次人物草稿</button>${button('取消新增','record-new-cancel')}</div></form>`;
  dialog.showModal();$('#new-person-name').focus();
}
function reviewPeople(){
  const d=s.draft,confirmed=d.confirmedPeople||[];
  return draftPeople().map((p,i)=>{
    const label=p.isNew?`確認新增並關聯人物：${p.name}（${p.relation==='mentioned'?'僅被提及':'實際參與'}）`:`確認關聯人物：${p.name}（${p.relation==='mentioned'?'僅被提及':'實際參與，非僅提及'}）`;
    return check(esc(label),'person-link-confirm-'+i,confirmed.includes(p.key));
  }).join('');
}
function savedRecordPeople(r){
  const links=Array.isArray(r.peopleLinks)?r.peopleLinks:recordParticipants(r).map(id=>({id,name:who(id).name,relation:'participant'}));
  return links.length?`<div class="record-links"><p class="muted">這段經歷的人物</p>${links.map(p=>button(esc(p.name)+' · '+(p.relation==='mentioned'?'僅被提及':'實際參與'),'record-open-person:'+p.id)).join('')}</div>`:'';
}
function savedRecordActivity(r){
  const goal=linkedGoal(r);
  return goal?`<p class="record-activity">關聯目標：${esc(goal.title)}${r.activityName?' · 活動：'+esc(r.activityName):' · 未指定活動'}</p>`:'<p class="muted record-activity">未關聯目標</p>';
}
// 識別碼不依名稱變動；舊原型僅補穩定 ID，不把未選的習慣猜成已完成活動。
function ensureActionIds(goal){if(goal)goal.actions?.forEach((a,i)=>{a.id ||= goal.id+'-habit-'+i;});}
function linkedGoal(d){return [s.goal,...s.archived].find(g=>g&&g.id===d.goalId)||null;}
function linkedActivities(goal){
  if(!goal)return [];
  ensureActionIds(goal);
  return [...goal.actions.map(a=>({...a,kind:'habit'})),...s.tasks.filter(t=>t.goalId===goal.id&&t.status==='open').map(t=>({...t,kind:'task',quantity:'1',unit:'次'}))];
}
function contributionEligibility(d){
  const goal=linkedGoal(d),activity=linkedActivities(goal).find(a=>a.id===d.actionId);
  if(!goal||!activity)return {allowed:false,pending:false,message:'選擇一個習慣或活動任務，才可確認實際投入。'};
  const day=d.occurred?.slice(0,10),waiting=goal.status==='待回顧'||goal.status==='進行中'&&dateNow()>goal.deadline;
  if(!day||day<goal.start||day>goal.deadline&&!waiting)return {allowed:false,pending:false,message:'發生日期不在挑戰期間；可保存經歷與關聯，但不採計投入。'};
  if(!['進行中','待回顧'].includes(goal.status))return {allowed:false,pending:false,message:'這次目標已結束，只保留關聯，不新增投入。'};
  return {allowed:true,pending:waiting,message:waiting?'目標待回顧：本筆投入先待處理，延長後仍須另行確認。':'只有明確核對後，才會採計這個活動的實際投入。'};
}
function activityAssociation(d,review=false){
  if(d.goalId===undefined)d.goalId=d.goal&&s.goal?s.goal.id:null;
  d.actionId ||= null;
  const goal=linkedGoal(d),activities=linkedActivities(goal),selected=activities.find(a=>a.id===d.actionId);
  const available=[s.goal,...s.archived].filter((g,i,all)=>g&&all.findIndex(x=>x?.id===g.id)===i&&(g.id===d.goalId||['進行中','待回顧'].includes(g.status)));
  const eligibility=contributionEligibility(d);
  return `<section class="activity-association"><h3>這次經歷與哪個活動有關？</h3><label class="label" for="linked-goal">關聯目標</label><select id="linked-goal"><option value="">不關聯目標</option>${available.map(g=>`<option value="${esc(g.id)}" ${g.id===d.goalId?'selected':''}>${esc(g.title)}</option>`).join('')}</select>${goal?`<label class="label" for="linked-action">關聯的習慣／活動任務</label><select id="linked-action"><option value="">只關聯目標，不指定活動</option><optgroup label="三個習慣">${activities.filter(a=>a.kind==='habit').map(a=>`<option value="${esc(a.id)}" ${a.id===d.actionId?'selected':''}>${esc(a.title)}</option>`).join('')}</optgroup>${activities.some(a=>a.kind==='task')?`<optgroup label="後續活動任務">${activities.filter(a=>a.kind==='task').map(a=>`<option value="${esc(a.id)}" ${a.id===d.actionId?'selected':''}>${esc(a.title)}</option>`).join('')}</optgroup>`:''}</select>`:''}${review&&selected?`<p class="contribution-notice ${eligibility.allowed?'':'error'}">${esc(eligibility.message)}</p><label class="label" for="actual-quantity">實際投入量</label><div class="quantity-with-unit"><input id="actual-quantity" type="number" value="${esc(d.quantity||'1')}" min="0.000001" max="1000000000000" step="0.000001" required><span>${esc(selected.unit)}</span></div><label class="check"><input id="goal-confirm" type="checkbox" ${d.contributionConfirmed?'checked':''} ${eligibility.allowed?'':'disabled'}>確認「${esc(selected.title)}」的實際投入</label>`:goal?'<p class="muted">關聯本身不代表完成；投入會在下一步另外確認。</p>':'<p class="muted">不關聯目標也可以保存經歷、人物與故事。</p>'}</section>`;
}
function followupEditor(d){
  return `<section class="followup-editor">${check('建立後續任務（選填）','task-confirm',!!d.followupRequested)}${d.followupRequested?field('後續任務名稱','followup-title',d.followupTitle||'','text','required maxlength="160"')+field('後續任務日期','followup-date',d.followupDate||shift(dateNow(),1),'date','required'):''}</section>`;
}
function record(){
  if(!s.draft)s.draft={raw:'',occurred:eventNow(),created:eventNow(),goal:false,person:false,quantity:'1',name:'虛構名片人物',mode:'文字',voice:'idle'};
  const d=s.draft;inputMode=d.mode||'文字';voice=d.voice||'idle';
  return title(isQuiet()?'今晚想留下什麼？':'記錄真實經歷',inputMode==='文字'&&!isQuiet())+`<form id="record" class="card narrow"><p>輸入會先成為草稿；不完整也可以先保存。</p><p class="callout">封測必備：真實語音及圖片辨識。本原型僅示範；真實服務未完成前不可宣稱封測就緒。</p><div class="row">${['文字','錄音','圖片','名片'].map(m=>`<button type="button" data-action="mode:${m}" aria-pressed="${inputMode===m}">${m}</button>`).join('')}</div>${text('今天發生了什麼？','raw',d.raw)}${field('實際發生的時間','occurred',d.occurred,'datetime-local','required')}<p class="muted">建立時間：${esc(d.created)} · 跨日補記仍採你確認的發生時間。</p>${inputMode==='錄音'?`<div class="callout"><b>錄音／權限／上傳／辨識皆為模擬</b><p id="voice-state">${esc(voice)}</p><div class="row">${button('開始模擬錄音','voice-start')}${button('模擬權限拒絕','voice-denied')}${button('停止','voice-stop')}${button('模擬試聽','voice-play')}${button('重錄','voice-reset')}${button('模擬上傳','voice-upload')}${button('模擬辨識失敗','voice-fail')}${button('重試辨識','voice-retry')}</div></div>`:''}${['圖片','名片'].includes(inputMode)?`<label class="label" for="file">${inputMode==='名片'?'掃描／上傳名片':'選擇圖片或截圖'}</label><input id="file" type="file" accept="image/*" ${inputMode==='名片'?'capture="environment"':''}><p>僅在本頁預覽，無上傳、OCR 或遠端保存。</p><div id="attachment">${d.fileName?`<p>${esc(d.fileName)}（重新整理後需重選預覽）</p>${button('移除附件','remove-file')}`:''}</div>${button(inputMode==='名片'?'填入虛構名片示例':'填入虛構圖片示例','sample')}<p class="callout">名片只是資訊來源，不代表雙方見面或已完成行動。</p>`:''}${inputMode!=='名片'?activityAssociation(d):''}${inputMode!=='名片'?recordPeople():''}<div class="actions"><button class="primary">整理為草稿</button>${button('手動整理','manual-review')}${button('模擬整理失敗','organize-fail')}${button('先存草稿，明天再整理','save-draft')}${link('取消並保留草稿','world')}</div></form>`;
}
function review(){
  const d=s.draft;if(!d)return link('記錄新經歷','record');
  const card=d.mode==='名片';
  return title('先確認，再放進世界',!card)+`<form id="review" class="card narrow"><div class="callout">${d.manual?'手動整理':'模擬整理，沒有呼叫 AI'}。只有明確勾選的項目才保存。</div><details><summary>原始輸入與來源</summary><p>${esc(d.raw||d.fileName||'尚無文字內容')}</p></details>${card?field('人物稱呼','person-name',d.name,'text','required'):text('經歷摘要','summary',d.summary||d.raw)}<p>發生時間：${esc(d.occurred)}<br>建立時間：${esc(d.created)}</p>${card?check('確認人物資訊與來源','person-confirm'):check('確認經歷內容正確','experience-confirm',!!d.experienceConfirmed)}${!card?reviewPeople():''}${!card?activityAssociation(d,true):''}${!card?followupEditor(d):''}<p>未確認項目不更新。名片保存與私人模擬不發獎。</p><div class="actions"><button class="primary">${card?'只保存人物資料':'確認保存'}</button>${link('返回修改','record')}${button('先存草稿，明天再整理','save-draft')}</div></form>`;
}
function connections(){
  const available=allStories().map((v,i)=>({...v,index:i})).filter(v=>v.people.includes(s.focus));
  const story=available.find(v=>v.index===s.story)||available[0];if(!story)return title('交會')+`<section class="card"><p>還沒有這位人物的已確認共同經歷。</p>${link('返回收藏冊','cards')}${link('人物劇場','theater-hub')}</section>`;s.story=story.index;
  return title('沿著一段故事，遇見另一個人')+`<div class="row">${link('交會','connections','secondary')}${link('收藏冊','cards')}${link('人物劇場','theater-hub')}</div><p>正在探索：${esc(who(s.focus).name)}</p><div class="trail">${s.trail.map(x=>esc(who(x.focus).name)+' → ').join('')} ${esc(who(s.focus).name)}</div><article class="card story"><span class="date">${story.date} · ${story.tags==='已確認的原型經歷'?'已確認經歷（原型）':'虛構共同經歷'}</span><h2>${esc(story.title)}</h2><p>${esc(story.text)}</p><p>${esc(story.tags)}</p><small>使用者審閱不等於所有參與者證實；探索路徑不代表直接私人關係。</small><div class="actions">${story.people.map(id=>`<button data-action="explore:${id}">探索${esc(who(id).name)}</button>`).join('')}${button('查看連結來源','story-source')}</div></article><div class="row">${available.length>1?button('查看另一段故事','next-story'):''}${s.trail.length?button('上一段探索','previous-story'):''}${button('查看人物卡','focus-person')}</div>`;
}
function cards(){return title('人物收藏冊')+`<div class="row">${link('交會','connections')}${link('收藏冊','cards','secondary')}</div>${field('搜尋姓名、角色、目標或標籤','search',s.search||'')}<div class="grid">${s.people.filter(p=>(p.name+p.role+(p.tags||'')).includes(s.search||'')).map(p=>`<article class="card"><div class="person">${esc(p.name.slice(0,1))}</div><h2>${esc(p.name)}</h2><p>${esc(p.role)} · ${p.follow?'★ 已加星標':'未加星標'}</p><p class="muted">最近互動：虛構示例時間</p><button data-action="select:${p.id}">查看${esc(p.name)}</button></article>`).join('')}</div>${s.showSummary?`<section class="card"><h2>${esc(who(s.selected).name)}</h2><p>${esc(who(s.selected).role)} · 共同場合：虛構旅程</p><button data-action="follow" aria-pressed="${!!who(s.selected).follow}" title="${who(s.selected).follow?'再次點選可取消星標':'方便你之後找回，只有你自己看得到'}">${who(s.selected).follow?'★ 已加星標':'☆ 加入星標'}</button>${link('查看人物卡','person')}</section>`:''}`;}
function person(){
  const p=who(s.selected),tab=s.tab;
  return title(p.name+' · 人物 360°')+`<section class="card"><div class="person">${esc(p.name.slice(0,1))}</div><p>${esc(p.role)} · 虛構示例人物</p><div class="row"><span class="tag">參與 ${allStories().filter(x=>x.people.includes(p.id)).length} 段已記錄故事</span><span class="tag">僅提及 ${s.records.filter(r=>r.peopleLinks?.some(x=>x.id===p.id&&x.relation==='mentioned')).length} 次</span><span class="tag">見面次數：尚未分類</span></div></section><div class="row">${['人物總覽','共同經歷','合作與目標'].map(t=>button(t,'tab:'+t,t===tab?'secondary':'')).join('')}</div><section class="card">${tab==='人物總覽'?['興趣與嗜好','飲食偏好','專長與背景','互動習慣'].map(t=>`<details><summary><button data-action="dimension">${t}</button></summary><p>${t==='飲食偏好'?esc(p.food):'尚未了解'}</p>${t==='飲食偏好'&&p.food!=='尚未了解'&&p.source?button('查看來源','person-source'):''}</details>`).join('')+'<details><summary>共同關係／場合／交集</summary><p>共同旅行（虛構示例）；不推斷人物私人關係。</p></details>':tab==='共同經歷'?allStories().filter(x=>x.people.includes(p.id)).map(x=>`<article><h3>${esc(x.title)}</h3><p>${esc(x.date)} · ${esc(x.text)}</p></article>`).join(''):`<h2>相關目標</h2>${personGoals(p.id).map(g=>`<article><h3>${esc(g.title)}</h3><p>${goalLabel(g)}${g.reason?' · '+esc(g.reason):''}</p></article>`).join('')||'<p>尚未關聯目標</p>'}${s.goal&&goalStatus()==='進行中'?button('為此目標記錄經歷','record-goal-context'):''}`}</section><div class="actions">${button('記錄新經歷','record-context')}${link('開啟小劇場','theater')}${button('探索相關故事','person-explore')}${link('返回收藏冊','cards')}</div>`;
}
function theater(){privateText=s.privateDrafts[s.selected+':'+scene]||'';return title('與 '+who(s.selected).name+' 的私人小劇場')+`<section class="card"><div class="row">${['見面前準備','情境演練','傳達心意','相遇後回顧'].map(t=>button(t,'scene:'+t,scene===t?'secondary':'')).join('')}</div><p class="callout">${scene==='情境演練'?'模擬不代表對方真實反應。':scene==='傳達心意'?'訊息草稿不自動發送。':scene==='相遇後回顧'?'請另記真實經歷並經人工確認。':'可參考已確認來源，筆記保持私人。'}</p>${scene==='相遇後回顧'?button('記錄真實經歷','record-context'):text('私人筆記','private-note',privateText)+`<div class="actions">${button('保存私人筆記','save-note')}${scene==='傳達心意'?button('複製草稿','copy-note'):''}</div>`}<h3>已保存私人筆記</h3>${s.notes.filter(n=>n.person===s.selected).map(n=>`<p>${esc(n.scene)}：${esc(n.text)}</p>`).join('')||'<p>尚無筆記。</p>'}<div class="actions">${link('返回人物卡','person')}${button('建立與此人物的情境','theater-v05-person','primary')}${button('建立與此人物的多人情境','theater-v05-person')}${link('返回人物劇場','theater-hub')}</div></section>`;}
function theaterHub(){ // 新場一律進 v0.5 Builder；舊引擎只提供唯讀歷史。
  const legacy=s.rehearsalHistory.map(item=>`<article><h3>${esc(item.context||'舊版私人演練')}</h3>${button('查看舊版回顧','rehearsal-history:'+item.legacyId)}</article>`).join('');
  return title('人物劇場',false)+`<section class="card theater-hub-hero"><div><p class="steps">一場、一個具體情境</p><h2>先試著說說看</h2><p>從已建立人物出發，練習一次現實對話。</p><div class="actions">${button('建立我的情境','theater-v05-new','primary')}${button('演練歷史','theater-v05-history')}${TheaterUI.snapshot().current?.status==='ACTIVE'?button('繼續目前演練','theater-v05-resume'):''}</div></div><img src="assets/idle@256.png" alt="Lumi 陪伴你準備演練"></section><section class="card"><h2>我的人物演練</h2><p>私人準備、演練與訊息草稿；不預測對方真實反應。</p>${s.people.map(p=>button('與'+esc(p.name)+'演練','private-person:'+p.id)).join('')}<h3>舊版私人演練回顧</h3><p>舊場次只供查看，建立新情境請使用上方入口。</p>${s.rehearsal?button('查看舊版目前場次','rehearsal-current'):''}${legacy||(!s.rehearsal?'<p>沒有舊版演練紀錄。</p>':'')}</section><section class="card"><h2>示範情境</h2><p>三組十五位示範角色，與你的正式人物資料分開。</p>${link('情境體驗（示範角色）','demo-theater')}</section>`;
}
function groupTheater(){ // 缺失人物不以其他人代替；舊來源不假造版本。
  const r=s.legacyViewingId==='legacy-active'?s.rehearsal:s.rehearsalHistory.find(item=>item.legacyId===s.legacyViewingId);
  if(!r)return title('舊版紀錄不存在')+`<section class="card">${link('返回人物劇場','theater-hub')}</section>`;
  const name=id=>id==='user'?'你':s.people.find(p=>p.id===id)?.name||`已刪除人物（${id}）`;
  return title('舊版私人演練回顧',false)+`<section class="card"><p class="callout">舊版紀錄缺少當時人物／來源快照，只供唯讀查看。無法核對的來源不會用於新場次。</p><h2>${esc(r.context||'私人演練')}</h2><p>當時人物 ID：${(r.participants||[]).map(id=>esc(name(id))).join('、')}</p><details><summary>舊版來源文字（版本未保存）</summary>${(r.sources||[]).map(x=>`<p>${esc(name(x.personId))}：${esc(x.text)}</p>`).join('')||'<p>沒有保存來源。</p>'}</details>${(r.turns||[]).map(t=>`<article data-speaker="${esc(t.speaker)}"><b>${esc(name(t.speaker))}</b><p>${esc(t.text)}</p></article>`).join('')}${link('返回人物劇場','theater-hub')}</section>`;
}
function demoTheater(){
  const d=s.demo,p=packs[d.pack];d.participants ||= [d.role||0];
  return title('情境體驗（示範角色）',false)+`<section class="card"><p class="callout">預寫示意，非即時 AI；不是歷史原話或真人預測，不寫正式人物及經歷。</p><div class="row">${packs.map((p,i)=>button(p.name,'demo-pack:'+i,i===d.pack?'secondary':'')).join('')}</div><img class="theater-demo-cover" src="${TheaterUI.cover(p.name)}" alt="${esc(p.name)}示範封面"><fieldset><legend>加入本場示範角色</legend>${p.roles.map((name,i)=>`<label class="check theater-demo-person"><img src="assets/${packPortraits[d.pack][i]}" alt="${esc(name)}示範頭像"><input type="checkbox" id="demo-member-${i}" ${d.participants.includes(i)?'checked':''} ${d.started?'disabled':''}>加入${esc(name)}</label>`).join('')}</fieldset><label class="label" for="demo-role">選擇角色</label><select id="demo-role">${p.roles.map((r,i)=>d.participants.includes(i)?`<option value="${i}" ${i===d.role?'selected':''}>${r}</option>`:'').join('')}</select><label class="label" for="demo-scene">選擇場景</label><select id="demo-scene" ${d.started?'disabled':''}>${p.scenes.map((r,i)=>`<option value="${i}" ${i===d.scenario?'selected':''}>${r}</option>`).join('')}</select>${button('查看示範來源說明','demo-source')}<h2>${d.done?'模擬回顧':esc(p.scenes[d.scenario])}</h2>${d.turns.map(t=>`<p><b>${esc(t.role)}</b>：${esc(t.text)}</p>`).join('')}${!d.started?button('開始腳本示範','demo-start','primary'):!d.done?text('你的回應','demo-text',d.input||'')+button('送出模擬回應','demo-send')+button('模擬對話失敗','demo-fail')+button('結束並回顧','demo-end'):''}<div class="actions">${button('重設本次示範','demo-reset')}${link('返回人物劇場','theater-hub')}</div></section>`;
}
function memorial(){
  const g=s.archived.find(g=>g.id===s.memorialId);if(!g)return journey();
  const snap=g.memorial||{records:0,people:[],text:g.reflection||'尚無回顧摘要。'};
  return title(g.status==='已完成'?'完成紀念':'旅程紀錄',false)+`<section class="card"><h2>${esc(g.title)}</h2><p>${g.start} ～ ${g.deadline} · ${goalLabel(g)} · ${esc(g.reason)}</p><p>${esc(snap.text)}</p><p>基本數據：已確認 ${snap.records} 筆過程 · 相關人物 ${snap.people.length} 位</p><h3>三個習慣</h3>${g.actions.map(a=>`<p>${esc(a.title)} · ${a.dates.length} 個安排日（非完成數）</p>`).join('')}<h3>過程中遇見的人</h3>${snap.people.map(id=>button('查看相關人物：'+esc(who(id).name),'memorial-person:'+id)).join('')||'<p>尚無已確認人物。</p>'}<p>此處只展示文字摘要與基本數據，原始經歷及人物資訊仍保留。</p>${link('返回目標旅程','journey')}</section>`;
}
function login(){return title('登入你的世界',false)+`<section class="card narrow"><p class="callout">登入介面模擬，不輸入真實帳密、不建立 session。</p><p>正式登入使用帳號與密碼；邀請及恢復依安全契約接入。</p>${button('模擬新使用者進入','login-new','primary')}${button('模擬登入既有世界','login-existing')}${button('模擬登入失敗','login-fail')}${link('帳號恢復','recovery')}${link('返回稱呼設定','intro')}</section>`;}
function settings(){return title('讓晚上安靜一點',false)+`<form id="settings" class="card narrow"><p>本原型只示範呈現，不啟用系統通知、麥克風或真實排程。</p>${field('示範當地時間','demo-time',s.demoTime||stamp(),'datetime-local')}<div class="actions">${button('套用示範時間','demo-time')}</div>${field('安靜時段開始','night-start',s.night.start,'time','required')}${field('安靜時段結束','night-end',s.night.end,'time','required')}${check('夜間自動使用安靜模式','night-auto',s.night.choice===true&&s.night.enabled)}<p>依帳號當地時間切換；目標用量另依目標固定時區。</p><div class="actions"><button class="primary">保存夜間設定</button>${button('本次切回一般模式','quiet-off')}${button('本次開啟安靜模式','quiet-on')}</div></form>`;}
function reviewGoal(){return title('回顧這次挑戰')+`<form id="goal-review" class="card narrow"><h2>${esc(s.goal?.title||'尚未建立目標')}</h2><p>到期先回顧，不自動判失敗；仍可保存經歷，貢獻需另行核對。</p>${field('延長截止日','extend-deadline','','date',`min="${s.goal?shift(s.goal.deadline,1):dateNow()}"`)}${text('回顧感想','reflection')}<label class="label" for="proof">成果佐證（原型僅預覽檔名）</label><input id="proof" type="file" accept="image/*">${check('我已核對成果或結束選擇','end-confirm')}<div class="actions">${button('延長並檢視三習慣安排','extend-goal')}${button('確認完成成果','complete-goal')}${button('結束這次挑戰','end-goal')}${link('返回目標','goal')}</div></form>`;}
function journey(){const archived=s.archived.filter(g=>g.status===s.historyTab);return title('目標旅程')+`<div class="row">${button('已完成','history:已完成')}${button('曾經挑戰','history:曾經挑戰')}</div><section class="card">${archived.length?archived.map(g=>`<h2>${esc(g.title)}</h2><p>${esc(g.reflection||'每一段投入，都值得留下。')}</p><p>${esc(g.reason||'已確認完成')} · ${g.deadline}</p>${button(g.status==='已完成'?'查看完成紀念':'查看旅程紀錄','memorial:'+g.id)}<p>歷史只供查看，不提供恢復或重試捷徑。</p>`).join(''):'<p>這裡會收藏你的挑戰。</p>'}${!s.goal||['已完成','曾經挑戰'].includes(s.goal.status)?button('建立下一個目標','next-goal'):''}</section>`;}
function render(){
  nightPrompt();$('#feedback').textContent=feedback;
  if(s.route.startsWith('theater-')&&['theater-build','theater-preview','theater-live','theater-lumi','theater-recap','theater-history'].includes(s.route)){
    $('#app').innerHTML=TheaterUI.render(s.route);
    $('#nav').innerHTML=[['世界','world'],['目標','goal'],['紀錄','records'],['關係','connections']].map(([t,r])=>link(t,r)).join('');
    return;
  }
  const pages={intro:()=>title('在故事開始之前')+`<form id="intro" class="card narrow">${field('你的稱呼','name',s.name,'text','required maxlength="80"')}<p>一次一個目標；每個目標三個重要習慣。</p><button class="primary">開始設定目標</button>${link('查看登入流程','login')}</form>`,login,recovery:()=>title('帳號恢復',false)+`<section class="card narrow"><p>一次性復原碼 → 設定新密碼 → 撤銷舊登入狀態；此原型只呈現流程，不接收憑證。</p><p>密碼及復原碼皆遺失時不能保證恢復；正式政策由帳號安全審查定案。</p>${button('模擬恢復失敗','recovery-fail')}${button('模擬恢復完成','login-new')}${link('返回登入','login')}</section>`,wizard,world,goal:goalPage,record,review,connections,cards,person,theater,'theater-hub':theaterHub,'group-theater':groupTheater,'demo-theater':demoTheater,memorial,settings,'goal-review':reviewGoal,journey,
    birth,
    success:()=>title('這段經歷已留下',!isQuiet())+`<section class="card hero"><img class="success-lumi" src="assets/${isQuiet()?'quiet':'confirmed'}@256.png" alt="${isQuiet()?'安靜陪伴的 Lumi':'為你留下經歷的 Lumi'}"><p>${isQuiet()?'辛苦了，今晚不用再做更多事。':'謝謝你，留下今天的一小步。'}</p><p>經歷已保存；只有你確認的內容會更新。封測不提供積分或虛擬獎勵。</p>${link('回到世界','world','primary')}${link('查看紀錄','records')}</section>`,
    records:()=>title('經歷紀錄')+`<section class="card">${s.draft?link('繼續草稿','record'):''}${s.records.map(r=>`<article><span class="tag">已確認 · 虛構示範</span><h2>${esc(r.summary)}</h2><p>發生：${esc(r.occurred)}<br>建立：${esc(r.created)}</p>${savedRecordActivity(r)}${savedRecordPeople(r)}<p>${r.contribution?'已人工核對投入':'沒有採計目標貢獻'}${r.pending?' · 待回顧後另行採計':''}</p></article>`).join('')||'<p>尚無已確認經歷。</p>'}${link('記錄新經歷','record','primary')}</section>`};
  $('#app').innerHTML=(pages[s.route]||pages.world)();
  $('#nav').innerHTML=['intro','wizard','birth'].includes(s.route)?'':[['世界','world'],['目標','goal'],['紀錄','records'],['關係','connections']].map(([t,r])=>`<button type="button" data-go="${r}" ${s.route===r?'aria-current="page"':''}>${navIcon(r)}<span>${t}</span></button>`).join('');
}
function capture(){
  if(s.route==='wizard'&&s.wizard){const w=s.wizard,a=w.actions[w.step-2];if($('#goal-name'))w.title=$('#goal-name').value;if($('#goal-outcome')){w.outcome=$('#goal-outcome').value;w.deadline=$('#deadline').value;}if(a&&$('#habit-name')){a.title=$('#habit-name').value;a.quantity=$('#habit-quantity').value;a.unit=$('#habit-unit').value;}}
  if(s.route==='record'&&s.draft){s.draft.raw=$('#raw').value;s.draft.occurred=$('#occurred').value;if($('#linked-goal')){s.draft.goalId=$('#linked-goal').value||null;s.draft.goal=!!s.draft.goalId;s.draft.actionId=$('#linked-action')?.value||null;}if($('#record-person'))s.draft.person=$('#record-person').checked;}
  if(s.route==='review'&&s.draft){if($('#summary'))s.draft.summary=$('#summary').value;if($('#experience-confirm'))s.draft.experienceConfirmed=$('#experience-confirm').checked;if($('#task-confirm'))s.draft.followupRequested=$('#task-confirm').checked;if($('#followup-title'))s.draft.followupTitle=$('#followup-title').value;if($('#followup-date'))s.draft.followupDate=$('#followup-date').value;if($('#person-name'))s.draft.name=$('#person-name').value;if($('#actual-quantity'))s.draft.quantity=$('#actual-quantity').value;if($('#linked-goal')){s.draft.goalId=$('#linked-goal').value||null;s.draft.actionId=$('#linked-action')?.value||null;}if($('#goal-confirm'))s.draft.contributionConfirmed=$('#goal-confirm').checked;if(s.draft.mode!=='名片')s.draft.confirmedPeople=draftPeople().filter((p,i)=>$('#person-link-confirm-'+i)?.checked).map(p=>p.key);}
  if(s.route==='theater'&&$('#private-note')){privateText=$('#private-note').value;s.privateDrafts[s.selected+':'+scene]=privateText;}
  if(s.route==='theater-hub'&&$('#rehearsal-context'))s.rehearsalContext=$('#rehearsal-context').value;
  if(s.route==='group-theater'&&s.rehearsal&&$('#rehearsal-input')){s.rehearsal.input=$('#rehearsal-input').value;s.rehearsal.recipient=$('#rehearsal-recipient').value;}
  if(s.route==='demo-theater'&&$('#demo-text'))s.demo.input=$('#demo-text').value;
  if(edit&&$('#habit-edit'))edit.actions.forEach((a,i)=>{a.title=$('#edit-name-'+i).value;a.quantity=$('#edit-quantity-'+i).value;});
  save();
}
function showSource(value){$('#source-text').textContent=value;$('#source').showModal();}
function sampleData(){ // 取代前須同時核對主原型與劇場資料域。
  if((s.name||s.goal||s.records.length||s.draft||TheaterUI.hasData())&&!confirm('載入示例將取代主原型、建立草稿、活動場與劇場歷史。確定繼續？'))return;
  const next=initial();next.lumiBorn=true;next.name='虛構體驗者';next.goal={title:'完成作品',outcome:'完成一份可分享的作品',start:dateNow(),deadline:shift(dateNow(),30),id:'demo-goal-'+Date.now(),status:'進行中',actions:['閱讀','整理','分享'].map(title=>({title,quantity:'1',unit:'次',dates:[dateNow(),shift(dateNow(),1)],cycle:'month'}))};ensureActionIds(next.goal);next.route='world';
  if(!WireframeStorage.replace(JSON.stringify(next))){say(WireframeStorage.error);return;} // 成功後才切換兩個記憶體狀態。
  TheaterUI.resetMemory();s=next;go('world');
}
document.addEventListener('input',event=>{
  capture();
  if(event.target.id==='new-person-name'||event.target.id==='new-person-role'){
    s.draft.newPersonDraft={name:$('#new-person-name').value,role:$('#new-person-role').value};save();
  }
  if(event.target.id==='people-search'){
    const query=event.target.value.trim().toLocaleLowerCase();
    $('#people-options').querySelectorAll('button').forEach(b=>{b.hidden=!b.textContent.toLocaleLowerCase().includes(query);});
  }
  if(event.target.id==='search'){s.search=event.target.value;const pos=event.target.selectionStart;render();$('#search').focus();$('#search').setSelectionRange(pos,pos);}
});
document.addEventListener('change',event=>{
  if(event.target.id==='linked-goal'||event.target.id==='linked-action'){
    const d=s.draft;if(!d)return;
    d.goalId=$('#linked-goal').value||null;
    d.actionId=event.target.id==='linked-goal'?null:($('#linked-action')?.value||null);
    d.goal=!!d.goalId;d.contributionConfirmed=false;d.quantity='1';
    save();const y=scrollY;render();scrollTo(0,y);
  }
  if(event.target.id==='task-confirm'){s.draft.followupRequested=event.target.checked;save();const y=scrollY;render();scrollTo(0,y);}
  if(event.target.id==='month-pattern-repeat'){
    const a=edit?edit.actions[edit.index]:s.wizard?.actions[s.wizard.step-2];
    if(a){a.monthlyDraft=monthPattern(a,(a.cursor||(edit?dateNow():s.wizard.start)).slice(0,7));a.monthlyDraft.repeat=event.target.checked;save();const y=scrollY;render();scrollTo(0,y);}
  }
  if(event.target.dataset.personRelation!==undefined){const p=draftPeople()[Number(event.target.dataset.personRelation)];if(p){p.relation=event.target.value;s.draft.confirmedPeople=[];save();}}
  if(event.target.id.startsWith('roster-')){const id=event.target.id.slice(7);s.roster=event.target.checked?[...new Set([...s.roster,id])]:s.roster.filter(x=>x!==id);save();render();}
  if(event.target.id.startsWith('rehearsal-source-')){const id=event.target.id.slice(17);s.rehearsalSources=event.target.checked?[...new Set([...s.rehearsalSources,id])]:s.rehearsalSources.filter(x=>x!==id);save();}
  if(event.target.id.startsWith('demo-member-')){const i=Number(event.target.id.slice(12));s.demo.participants=event.target.checked?[...new Set([...s.demo.participants,i])]:s.demo.participants.filter(x=>x!==i);if(!s.demo.participants.includes(s.demo.role))s.demo.role=s.demo.participants[0];save();render();}
  if(event.target.id==='demo-role'){s.demo.role=Number(event.target.value);save();}
  if(event.target.id==='demo-scene'){s.demo.scenario=Number(event.target.value);save();render();}
  if(event.target.id==='edit-index'){edit.index=Number(event.target.value);render();}
  if(event.target.id==='file'&&event.target.files[0]){
    const file=event.target.files[0];
    if(!file.type.startsWith('image/')||file.size>10*1024*1024){say('原型預覽僅接受 10 MiB 內圖片；文字保留，請重新選擇。');event.target.value='';return;}
    attachment=file;s.draft.fileName=file.name;const reader=new FileReader();
    reader.onload=()=>{if(attachment!==file||!$('#attachment'))return;$('#attachment').innerHTML=`<img class="preview" alt="本機附件預覽"><p>${esc(file.name)}</p>${button('移除附件','remove-file')}`;$('#attachment img').src=reader.result;};
    reader.onerror=()=>say('無法讀取預覽，文字保留，請重新選擇圖片。');reader.readAsDataURL(file);save();
  }
});
document.addEventListener('click',async event=>{
  const b=event.target.closest('button');if(!b||b.disabled)return;capture();
  if(b.dataset.go){if(b.dataset.go==='wizard'&&s.goal&&['進行中','待回顧'].includes(goalStatus())){say('先回顧或結束目前挑戰。');return;}if(b.dataset.go==='record'&&!s.goal){say('先建立目標，或載入虛構示例。');return;}go(b.dataset.go);return;}
  const action=b.dataset.action;if(!action)return;
  const [kind,value]=action.split(':');
  if(action==='login-new'){go('intro');return;}
  if(action==='login-existing'){sampleData();return;}
  if(action==='login-fail'||action==='recovery-fail'){say(action==='login-fail'?'登入未成功：請核對帳號或使用恢復入口（模擬）。':'恢復未成功：復原碼無效或已使用（模擬）。');return;}
  if(action==='demo'){sampleData();return;}
  if(action==='reset'){if(confirm('清除主原型、建立草稿、活動場、劇場歷史與舊私人演練資料？其他網站資料不受影響。')){const next=initial();if(!WireframeStorage.replace(JSON.stringify(next))){say(WireframeStorage.error);return;}TheaterUI.resetMemory();s=next;nightOverride=null;attachment=null;edit=null;go('intro');}return;}
  if(action==='wizard-back'){s.wizard.step--;go('wizard');return;}
  if(action==='night-yes'||action==='night-no'){s.night.choice=action==='night-yes';s.night.enabled=s.night.choice;nightOverride=null;save();render();return;}
  if(action==='demo-time'){s.demoTime=$('#demo-time').value;nightOverride=null;save();render();return;}
  if(action==='quiet-off'||action==='quiet-on'){nightOverride=action==='quiet-on';render();return;}
  if(action==='edit-habits'){edit={actions:structuredClone(s.goal.actions),index:0};render();return;}
  if(action==='cancel-edit'){edit=null;go('goal');return;}
  if(action==='record-add-existing'){openPeoplePicker();return;}
  if(action==='record-add-new'){openNewPerson();return;}
  if(action==='record-picker-cancel'){$('#people-picker').close();return;}
  if(action==='record-new-cancel'){$('#new-person-dialog').close();return;}
  if(kind==='record-choose-person'){
    const p=s.people.find(p=>p.id===value),links=draftPeople();
    if(p&&!links.some(x=>x.id===p.id))links.push({key:p.id,id:p.id,name:p.name,role:p.role,relation:'participant'});
    $('#people-picker').close();save();render();return;
  }
  if(kind==='record-remove-person'){s.draft.peopleLinks=draftPeople().filter(p=>p.key!==value);save();render();return;}
  if(kind==='record-open-person'){s.selected=value;s.tab='人物總覽';go('person');return;}
  if(action==='hatch-start'){playHatch();return;}
  if(action==='hatch-skip'){finishHatch();return;}
  if(kind==='schedule-mode'||kind==='month-slot'||action==='schedule-deadline-open'||action==='schedule-deadline'){
    const a=edit?edit.actions[edit.index]:s.wizard?.actions[s.wizard.step-2];if(!a)return;
    if(kind==='schedule-mode')a.scheduleMode=value;
    if(kind==='month-slot'){
      const [nth,weekday]=value.split('-').map(Number),draft=monthPattern(a,(a.cursor||(edit?dateNow():s.wizard.start)).slice(0,7));
      const exists=draft.slots.some(x=>x.nth===nth&&x.weekday===weekday);
      draft.slots=exists?draft.slots.filter(x=>x.nth!==nth||x.weekday!==weekday):[...draft.slots,{nth,weekday}];
      a.monthlyDraft=draft;
    }
    if(action==='schedule-deadline-open')a.deadlineOpen=!a.deadlineOpen;
    if(action==='schedule-deadline'){
      const deadline=$('#schedule-deadline').value,w=s.wizard;
      if(!w||!deadline||deadline<w.start){say('截止日不可早於挑戰起始日。');return;}
      w.deadline=deadline;w.actions.forEach(item=>{item.dates=item.dates.filter(d=>d<=deadline);item.monthlyRule=null;});a.deadlineOpen=false;
    }
    save();const y=scrollY;render();scrollTo(0,y);return;
  }
  if(action==='monthly-apply'){
    const w=edit?null:s.wizard,a=edit?edit.actions[edit.index]:w?.actions[w.step-2];if(!a)return;
    const start=edit?shift(dateNow(),1):w.start,end=edit?(edit.deadline||s.goal.deadline):w.deadline;
    const month=(a.cursor||start).slice(0,7),rule=monthPattern(a,month);rule.month=month;
    if(!rule.slots.length){say('請先選至少一格，再套用規律。');return;}
    if(!end||end<start){say('請先設定有效截止日，或延長目標期間。');return;}
    const selected=dates(start,end).filter(day=>(rule.repeat||day.slice(0,7)===month)&&matchesMonthly(day,rule));
    if(!selected.length){say('目前期間沒有符合的日期；請調整週次或截止日。');return;}
    // 只替換可編輯期間，歷史已安排日期及既有投入都不回算。
    a.dates=[...a.dates.filter(day=>day<start||!rule.repeat&&day.slice(0,7)!==month),...selected].sort();a.monthlyRule=rule;a.monthlyDraft=rule;save();const y=scrollY;render();scrollTo(0,y);return;
  }
  const calendarAction=['month','week','weekdays','daily','clear','weekday','day','prev-month','next-month'].includes(kind);
  if(calendarAction){
    const w=edit?null:s.wizard,a=edit?edit.actions[edit.index]:w?.actions[w.step-2];if(!a)return;
    const start=edit?dateNow():w.start,end=edit?(edit.deadline||s.goal.deadline):w.deadline;
    if(kind==='month'||kind==='week')a.cycle=kind;
    if(['day','weekdays','daily','clear','weekday'].includes(kind))a.monthlyRule=null;
    if(kind==='clear')a.monthlyDraft={slots:[],repeat:a.monthlyDraft?.repeat!==false,month:(a.cursor||start).slice(0,7)};
    if(kind==='day')a.dates=a.dates.includes(value)?a.dates.filter(x=>x!==value):[...a.dates,value].sort();
    if(['weekdays','daily','clear','weekday'].includes(kind)){const old=a.dates.filter(d=>d<start),period=dates(start,end);if(kind==='weekday'){const set=period.filter(d=>weekday(d)===Number(value)),all=set.every(d=>a.dates.includes(d));a.dates=all?a.dates.filter(d=>!set.includes(d)):[...new Set([...a.dates,...set])].sort();}else a.dates=[...old,...period.filter(d=>kind==='daily'||kind==='weekdays'&&weekday(d)<5)];}
    if(kind==='prev-month'||kind==='next-month'){const d=new Date((a.cursor||start)+'T12:00:00Z');if(a.cycle==='week')d.setUTCDate(d.getUTCDate()+(kind==='next-month'?7:-7));else{d.setUTCDate(1);d.setUTCMonth(d.getUTCMonth()+(kind==='next-month'?1:-1));}a.cursor=d.toISOString().slice(0,10);}
    save();const y=scrollY;render();scrollTo(0,y);return;
  }
  if(kind==='mode'){s.draft.mode=value;save();render();return;}
  if(kind.startsWith('voice-')){
    const states={'voice-start':'錄音中（模擬）','voice-denied':'權限拒絕：可改用文字，原文保留','voice-stop':'已停止，可試聽／重錄（模擬）','voice-play':'試聽示意：沒有實際音檔','voice-reset':'idle','voice-upload':'上傳中（模擬）','voice-fail':'辨識失敗：原文保留，可重試或手動整理','voice-retry':'已重試辨識（模擬），請手動校對'};
    s.draft.voice=states[kind];save();render();return;
  }
  if(action==='sample'){s.draft.raw=s.draft.mode==='名片'?'虛構示例：林先生，作品交流夥伴。':'虛構示例：與朋友討論作品，圖片中有筆記。';save();render();return;}
  if(action==='remove-file'){attachment=null;delete s.draft.fileName;save();render();return;}
  if(action==='organize-fail'){say('模擬整理失敗；文字與附件資訊保留，可重試或手動整理。');return;}
  if(action==='manual-review'){s.draft.manual=true;s.draft.summary=s.draft.raw;save();go('review');return;}
  if(action==='save-draft'){save();go('records');say('草稿已保存在此瀏覽器，尚未確認，不更新正式成果。');return;}
  if(action==='theater-v05-new'){TheaterUI.newDraft();return;}
  if(action==='theater-v05-history'){go('theater-history');return;}
  if(action==='theater-v05-resume'){go('theater-live');return;}
  if(action==='theater-v05-person'){TheaterUI.openForPerson(s.selected);return;}
  if(action==='rehearsal-current'){s.legacyViewingId='legacy-active';go('group-theater');return;} // 舊場唯讀。
  if(kind==='rehearsal-history'){s.legacyViewingId=value;go('group-theater');return;} // 歷史按穩定 ID 檢視。
  if(action.startsWith('rehearsal-')||action==='expand-rehearsal'){say('舊版演練只供回顧，請由「建立我的情境」開始新場。');return;} // 停止舊引擎新增與回覆。
  if(kind==='memorial'){s.memorialId=value;go('memorial');return;}
  if(kind==='memorial-person'||kind==='private-person'){s.selected=value;go(kind==='memorial-person'?'person':'theater');return;}
  if(kind==='demo-pack'){if(s.demo.started&&!confirm('切換情境組將重設本次示範對話，是否繼續？'))return;s.demo={pack:Number(value),role:0,scenario:0,turns:[],done:false};save();render();return;}
  if(action==='demo-source'){showSource('本線框只有介面與預寫占位，沒有引用史料或聲稱人物原話。完整來源與角色內容依歐桑 LW-SIM-001 交付，尚未在本原型接入。');return;}
  if(action==='demo-start'){if(!s.demo.participants?.length){say('至少選一位示範角色。');return;}s.demo.started=true;s.demo.turns=[{role:'系統',text:'預寫示意：請說明你希望討論的問題。'}];save();render();return;}
  if(action==='demo-send'){const value=$('#demo-text').value.trim();if(!value){say('請先輸入模擬回應。');return;}s.demo.input='';s.demo.turns.push({role:'你',text:value},{role:packs[s.demo.pack].roles[s.demo.role],text:'預寫示意：我們先釐清各方的目標與限制。'});save();render();return;}
  if(action==='demo-fail'){say('對話失敗（模擬）；你的輸入已保留，可以重試或結束回顧。');return;}
  if(action==='demo-end'){s.demo.done=true;save();render();return;}
  if(action==='demo-reset'){if(!confirm('只清除這次示範對話？不影響正式人物及經歷。'))return;s.demo={pack:s.demo.pack,role:0,scenario:0,turns:[],done:false};save();render();return;}
  if(kind==='select'){s.selected=value;s.showSummary=true;go('cards');return;}
  if(action==='follow'){who(s.selected).follow=!who(s.selected).follow;save();render();say(who(s.selected).follow?'已加入星標，方便你之後找回，只有你自己看得到。':'已取消星標。');return;}
  if(kind==='tab'){s.tab=value;save();render();return;}
  if(action==='dimension'){const d=b.closest('details');event.preventDefault();d.open=!d.open;return;}
  if(action==='person-source'){showSource(who(s.selected).source||'尚未了解，沒有可用來源。');return;}
  if(action==='story-source'){const story=allStories()[s.story];showSource('虛構示例 · '+story.date+'：'+story.text+'；參與者：'+story.people.map(id=>who(id).name).join('、')+'。不是私人關係推論。');return;}
  if(action==='close-source'){$('#source').close();return;}
  if(action==='person-explore'){s.focus=s.selected;s.trail=[];go('connections');return;}
  if(action==='focus-person'){s.selected=s.focus;go('person');return;}
  if(kind==='explore'&&value!==s.focus){s.trail.push({focus:s.focus,story:s.story});s.focus=value;go('connections');return;}
  if(action==='previous-story'){Object.assign(s,s.trail.pop()||{});go('connections');return;}
  if(action==='next-story'){const ids=allStories().map((x,i)=>x.people.includes(s.focus)?i:-1).filter(i=>i>=0);s.trail.push({focus:s.focus,story:s.story});s.story=ids[(ids.indexOf(s.story)+1)%ids.length];go('connections');return;}
  if(kind==='scene'){scene=value;privateText='';render();return;}
  if(action==='save-note'){s.notes.push({person:s.selected,scene,text:privateText});save();say('私人筆記已保存，不改人物事實、進度或積分。');return;}
  if(action==='copy-note'){try{await navigator.clipboard.writeText(privateText);say('已複製草稿，沒有發送。');}catch{say('無法使用剪貼簿，請手動選取筆記複製。');}return;}
  if(action==='record-context'||action==='record-goal-context'||kind==='record-action'){const contextualGoal=action!=='record-context'&&!!s.goal;s.draft={raw:'',occurred:eventNow(),created:eventNow(),person:kind!=='record-action',personId:kind!=='record-action'?s.selected:null,goal:contextualGoal,goalId:contextualGoal?s.goal.id:null,actionId:kind==='record-action'?value:null,mode:'文字',quantity:'1'};go('record');return;}
  if(action==='extend-goal'){
    const deadline=$('#extend-deadline').value;if(!s.goal||!deadline||deadline<=s.goal.deadline||deadline<dateNow()){say('請選晚於原截止日且不早於今天的日期。');return;}
    edit={actions:structuredClone(s.goal.actions),index:0,deadline};go('goal');say('延長為原型模擬；請檢視三個習慣的未來安排。');return;
  }
  if(action==='complete-goal'||action==='end-goal'){
    if(!s.goal||!['進行中','待回顧'].includes(goalStatus())){say('這次挑戰已收藏，請到目標旅程查看。');return;}
    if(!$('#end-confirm').checked){say('請先明確確認。');return;}
    if(action==='complete-goal'&&!$('#proof').files.length){say('請選成果佐證，再確認完成。');return;}
    s.goal.status=action==='complete-goal'?'已完成':'曾經挑戰';s.goal.reason=action==='end-goal'?(dateNow()>s.goal.deadline?'到期未完成':'提前結束'):'已確認完成';s.goal.reflection=$('#reflection').value;s.records.filter(r=>r.goalId===s.goal.id&&r.pending).forEach(r=>{r.pending=false;r.unapplied=true;});s.historyTab=s.goal.status;s.goal.memorial={text:s.goal.reflection||'尚無回顧摘要。',records:s.records.filter(r=>r.goalId===s.goal.id).length,people:relatedPeople(s.goal)};s.archived.push(structuredClone(s.goal));go('journey');return;
  }
  if(kind==='history'){s.historyTab=value;go('journey');return;}
  if(kind==='accept'){
    const r=s.records.find(r=>r.id===value);if(!r||!$('#accept-'+r.id).checked){say('請先逐筆核對。');return;}
    const occurred=r.occurred.slice(0,10);if(occurred<s.goal.start||occurred>s.goal.deadline){say('發生日期不在挑戰期間內，請檢視延長日期。');return;}
    r.pending=false;r.contribution=true;save();render();say('已採計示範貢獻，沒有再次發獎。');return;
  }
  if(action==='next-goal'){s.goal=null;newWizard();go('wizard');}
});
document.addEventListener('submit',event=>{
  event.preventDefault();capture();const id=event.target.id;
  if(id==='new-record-person'){
    const name=$('#new-person-name').value.trim(),role=$('#new-person-role').value.trim();
    if(!name){$('#new-person-error').textContent='請先填寫人物稱呼。';return;}
    const duplicate=[...s.people,...draftPeople()].find(p=>p.name.trim().toLocaleLowerCase()===name.toLocaleLowerCase());
    if(duplicate){$('#new-person-error').textContent='已有同名人物，請取消新增後從已有人物選取，避免重複。';return;}
    draftPeople().push({key:'new-'+Date.now(),isNew:true,name,role,relation:'participant'});
    delete s.draft.newPersonDraft;$('#new-person-dialog').close();save();render();return;
  }
  if(id==='intro'){s.name=$('#name').value;go('wizard');}
  if(id==='wizard'){
    const w=s.wizard,a=w.actions[w.step-2];
    if(w.step===1&&(!w.outcome.trim()||w.deadline<w.start)){say('請描述成果並選有效截止日。');return;}
    if(a&&!a.dates.length){say('每個習慣至少安排一天。');return;}
    if(w.step<5){w.step++;go('wizard');}else{s.goal={...structuredClone(w),id:'demo-goal-'+Date.now(),status:'進行中'};ensureActionIds(s.goal);s.wizard=null;if(s.lumiBorn){go('world');}else{s.lumiBorn=true;s.hatch={goalId:s.goal.id,stage:'idle'};go('birth');}}
  }
  if(id==='habit-edit'){
    if(!$('#edit-confirm').checked){say('請核對修改。');return;}
    const from=shift(dateNow(),1);if(edit.actions.some(a=>!a.title.trim()||!a.dates.length||!Number.isFinite(Number(a.quantity))||Number(a.quantity)<=0)){say('請填有效名稱、正數及安排日期。');return;}
    if(edit.actions.some((a,i)=>a.quantity!==(s.goal.actions[i].next?.quantity||s.goal.actions[i].quantity)&&!a.dates.some(d=>d>=from))){say('沒有明天起的執行日期，請先延長或安排日期。');return;}
    if(edit.deadline){s.goal.deadline=edit.deadline;s.goal.status='進行中';}
    s.goal.actions=edit.actions.map((a,i)=>({...a,quantity:s.goal.actions[i].quantity,next:{from,quantity:a.quantity}}));edit=null;save();go('goal');say('本機示範安排已保存；不回算歷史。');
  }
  if(id==='record'){if(!s.draft.raw.trim()&&!s.draft.fileName){say('先輸入內容或選擇附件。');return;}s.draft.summary=s.draft.raw;go('review');}
  if(id==='review'){
    const d=s.draft,card=d.mode==='名片';
    if(card){if(!$('#person-confirm').checked){say('請先確認人物資訊與來源。');return;}s.people.push({id:'card-'+Date.now(),name:$('#person-name').value,role:'名片來源',food:'尚未了解'});s.draft=null;go('cards');say('人物資料已保存；沒有新增見面、經歷或獎勵。');return;}
    if(!$('#experience-confirm').checked||!$('#summary').value.trim()){say('請核對經歷摘要並明確確認。');return;}
    const contribution=!!$('#goal-confirm')?.checked,eligibility=contributionEligibility(d),associatedGoal=linkedGoal(d),associatedAction=linkedActivities(associatedGoal).find(a=>a.id===d.actionId);
    if(contribution&&!eligibility.allowed){say(eligibility.message);return;}
    const pending=contribution&&eligibility.pending;
    if(d.followupRequested&&(!d.followupTitle?.trim()||!d.followupDate)){say('請填寫後續任務名稱與日期。');return;}
    const summary=$('#summary').value,peopleLinks=[];
    draftPeople().forEach((p,i)=>{
      if(!$('#person-link-confirm-'+i)?.checked)return;
      let personId=p.id;
      if(p.isNew){
        personId='person-'+Date.now()+'-'+i;
        s.people.push({id:personId,name:p.name,role:p.role||'尚未設定',food:'尚未了解',source:d.occurred.slice(0,10)+' 經歷原文：'+d.raw});
      }
      peopleLinks.push({id:personId,name:p.name,relation:p.relation});
    });
    const participant=peopleLinks.find(p=>p.relation==='participant');
    // 正式原型經歷只保存逐位核對的關聯，不保留未確認的新人物候選。
    const {peopleLinks:ignoredLinks,newPersonDraft,confirmedPeople,...content}=d;
    s.records.push({...content,peopleLinks,personId:participant?.id||null,id:'record-'+Date.now(),goal:!!associatedGoal,goalId:associatedGoal?.id||null,actionId:associatedAction?.id||null,activityName:associatedAction?.title||null,activityType:associatedAction?.kind||null,activityUnit:associatedAction?.unit||null,summary,person:!!participant,quantity:$('#actual-quantity')?.value||null,task:!!$('#task-confirm')?.checked,contribution:contribution&&!pending,pending:contribution&&pending});
    if(d.followupRequested)s.tasks.push({id:'task-'+Date.now(),title:d.followupTitle.trim(),dueDate:d.followupDate,goalId:associatedGoal?.id||null,sourceRecordId:s.records[s.records.length-1].id,status:'open'});
    s.draft=null;go('success');
  }
  if(id==='settings'){const start=$('#night-start').value,end=$('#night-end').value;if(start===end){say('請設定不同的開始與結束時間。');return;}s.night={choice:$('#night-auto').checked,enabled:$('#night-auto').checked,start,end};nightOverride=null;save();render();say('夜間示範設定已保存，可隨時關閉。');}
});
window.addEventListener('hashchange',()=>{if(location.hash==='#world')go('world');});
render();
