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
const initial = () => ({name:'',route:'intro',goal:null,archived:[],wizard:null,records:[],draft:null,notes:[],roster:[],rehearsal:null,rehearsalHistory:[],rehearsalSources:[],privateDrafts:{},points:0,people:[{id:'zhe',name:'阿哲',role:'朋友',food:'不吃辣',source:'2025-07-12 海邊旅行：阿哲說今天想吃清淡一點、不吃辣。（虛構示例）'},{id:'an',name:'小安',role:'同學',food:'尚未了解'},{id:'jun',name:'怡君',role:'攝影夥伴',food:'尚未了解'}],selected:'zhe',tab:'人物總覽',relation:'交會',focus:'zhe',story:0,trail:[],historyTab:'已完成',demo:{pack:0,role:0,scenario:0,turns:[],done:false},night:{choice:null,start:'23:00',end:'07:00',enabled:true}});
let s;
try {s=JSON.parse(localStorage.getItem(KEY));} catch {}
if(!s||!Array.isArray(s.people)) s=initial();
s.archived ||= [];
s.demo ||= {pack:0,role:0,scenario:0,turns:[],done:false};
s.privateDrafts ||= {};
s.roster ||= [];s.rehearsalHistory ||= [];s.rehearsalSources ||= [];
if(s.goal&&!s.goal.id)s.goal.id='restored-demo-goal';
TheaterUI.connect({people:()=>s.people,go});
function goalStatus(){return s.goal?.status==='進行中'&&dateNow()>s.goal.deadline?'待回顧':s.goal?.status;}
let feedback='',voice='idle',inputMode='文字',edit=null,scene='見面前準備',privateText='',nightOverride=null,attachment=null;
const stories=[{title:'海邊旅行',date:'2025-07-12',text:'那天下午一起拍照、散步，阿哲提議留下旅行照片。',people:['zhe','an'],tags:'海邊 · 旅行'},{title:'畢業聚會',date:'2026-06-20',text:'小安與怡君在聚會中分享畢業後的計畫。',people:['an','jun'],tags:'學校 · 聚會'},{title:'攝影活動',date:'2026-08-08',text:'與怡君參加攝影活動，練習捕捉街道上的光。',people:['jun'],tags:'攝影 · 學習'}];
// 示範包只呈現互動契約，預寫回應不代表歐桑完整人物包或真實 AI。
const packs=[{name:'三國策略',roles:['曹操','劉備','諸葛亮','孫權','周瑜'],scenes:['赤壁前夕策略／結盟','假設糧運／撤軍協商']},{name:'國際協調',roles:['美方代表','伊方代表','中立調停者','國際組織觀察員','航運方代表'],scenes:['假設停火與議程','航運安全／查核協商']},{name:'哲學辯論',roles:['蘇格拉底','孔子','莊子','尼采','柏拉圖'],scenes:['成功與自由','承諾、責任與個人選擇']}];
// 這些頭像只屬於三組示範包，不混入使用者的人物收藏冊。
const packPortraits=[['portrait-three-kingdoms-caocao.256.png','portrait-three-kingdoms-liubei.256.png','portrait-three-kingdoms-zhugeliang.256.png','portrait-three-kingdoms-sunquan.256.png','portrait-three-kingdoms-zhouyu.256.png'],['portrait-international-dialogue-us-representative@256.png','portrait-international-dialogue-iran-representative@256.png','portrait-international-dialogue-neutral-mediator@256.png','portrait-international-dialogue-international-observer@256.png','portrait-international-dialogue-shipping-representative@256.png'],['portrait-philosophy-socrates-256.png','portrait-philosophy-confucius-256.png','portrait-philosophy-zhuangzi-256.png','portrait-philosophy-nietzsche-256.png','portrait-philosophy-plato-256.png']];
const goalLabel = g => g.status==='進行中'?(g.id===s.goal?.id&&goalStatus()==='待回顧'?'待回顧':'挑戰中'):g.status==='已完成'?'已完成':'已結束';
// 關聯依已確認參與保存；不把全部人物自動綁到下一個目標。
const relatedPeople = g => [...new Set(s.records.filter(r=>r.goalId===g.id&&r.person).map(r=>r.personId).filter(Boolean))];
const personGoals = id => [...s.archived,...(s.goal&&!s.archived.some(g=>g.id===s.goal.id)?[s.goal]:[])].filter(g=>relatedPeople(g).includes(id));
const allStories = () => [...stories,...s.records.filter(r=>r.person&&r.personId).map(r=>({title:r.summary,date:r.occurred.slice(0,10),text:r.summary,people:[r.personId],tags:'已確認的原型經歷'}))];
const who = id => s.people.find(p=>p.id===id) || s.people[0];
function save(){try{localStorage.setItem(KEY,JSON.stringify(s));}catch{feedback='無法保存本機原型資料，請勿關閉頁面。';}}
function say(text){feedback=text;$('#feedback').textContent=text;}
function go(route){s.route=route;feedback='';save();render();window.scrollTo(0,0);$('#title')?.focus({preventScroll:true});}
const button = (text,action,cls='') => `<button type="button" data-action="${action}" class="${cls}">${text}</button>`;
const link = (text,route,cls='') => `<button type="button" data-go="${route}" class="${cls}">${text}</button>`;
const title = (text,implemented=true) => `<span class="tag ${implemented?'':'planned'}">${implemented?'App 已實作對應能力':'規劃模擬 · 尚未串接 App'}</span><h1 id="title" tabindex="-1">${esc(text)}</h1>`;
const field = (label,id,value='',type='text',extra='') => `<label class="label" for="${id}">${label}</label><input id="${id}" type="${type}" value="${esc(value)}" ${extra}>`;
const text = (label,id,value='') => `<label class="label" for="${id}">${label}</label><textarea id="${id}">${esc(value)}</textarea>`;
const check = (label,id,checked=false) => `<label class="check"><input id="${id}" type="checkbox" ${checked?'checked':''}>${label}</label>`;
const dates = (start,end) => {const out=[];for(let d=start;d<=end&&out.length<10000;d=shift(d,1))out.push(d);return out;};
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
  const cursor=a.cursor||start,month=cursor.slice(0,7),first=month+'-01',last=new Date(Number(month.slice(0,4)),Number(month.slice(5)),0).getDate();
  const lo=a.cycle==='week'?shift(cursor,-weekday(cursor)):first,hi=a.cycle==='week'?shift(lo,6):month+'-'+last;
  return `<div class="row">${button('按月檢視','month')}${button('按週檢視','week')}</div><p class="muted">星期快選套用期間內日期；「已安排」不是完成。</p><div class="row weekday">${names.map((n,i)=>button(n,'weekday:'+i)).join('')}</div><div class="row calendar-head">${button('平日','weekdays')}${button('每天','daily')}${button('清除安排','clear')}</div><div class="row between">${button('←','prev-month')}<b>${esc(a.cycle==='week'?lo+' ～ '+hi:month)}</b>${button('→','next-month')}</div><div class="calendar">${a.cycle==='week'?'':'<span class="offset"></span>'.repeat(weekday(first))}${dates(lo,hi).map(d=>`<button type="button" data-action="day:${d}" class="${a.dates.includes(d)?'selected':''}" ${d<start||d>end?'disabled':''} aria-pressed="${a.dates.includes(d)}" aria-label="${d}">${Number(d.slice(-2))}<small>${a.dates.includes(d)?'已安排':'－'}</small></button>`).join('')}</div><p>已安排 ${a.dates.length} 天 · 每次 ${esc(a.quantity)} ${esc(a.unit)}</p>`;
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
function world(){return title(isQuiet()?'你的世界會在這裡':'你的世界，歡迎回來',!isQuiet())+`<div class="grid"><section class="card hero"><h2>Lumi</h2><div class="egg">${isQuiet()?'◡ ◡':'• ◡ •'}</div><p>${isQuiet()?'辛苦了，今晚不用急著做更多事。':'每一段投入，都值得被留下。'}</p><small>角色與破蛋為線框示意，非正式美術資產。</small></section><section class="card"><h2>${esc(s.goal?.title||'讓故事有個起點')}</h2><p>${s.goal?'三個習慣，照自己的步調前進。':'先建立一個目標，或載入虛構示例預覽其他流程。'}</p>${s.goal?link('查看目前挑戰','goal','primary'):link(s.wizard?'繼續建立目標':'建立第一個目標','wizard','primary')}<div class="actions">${link('記錄新經歷','record','primary')}${s.draft?link('繼續草稿','record'):''}</div><p>已確認經歷 ${s.records.length} 筆 · 排程只代表打算做</p>${link('人物劇場','theater-hub')}</section></div><section class="card"><h2>旅途中遇見的人</h2><p>沿著共同經歷，重新遇見另一段故事。</p>${link('探索交會','connections')}${link('人物收藏冊','cards')}</section>`;}
function pendingPreview(g){
  // 原型也將延後採計與首次確認分開，避免演示時暗示重複獎勵。
  const rows=s.records.filter(r=>r.goalId===g.id&&(r.pending||r.unapplied));
  return rows.length?`<section class="card"><h2>待處理與未採計貢獻</h2>${rows.map(r=>`<article><p>${esc(r.summary)} · 發生 ${esc(r.occurred)}</p><p>${r.unapplied?'未採計':'等待逐筆核對'}</p>${r.pending&&goalStatus()==='進行中'?check('我已核對這筆貢獻','accept-'+r.id)+button('確認採計這筆貢獻','accept:'+r.id):''}</article>`).join('')}<p>採計不再發獎勵；需先延長並核對發生日期。</p></section>`:'';
}
function goalPage(){
  const g=s.goal;if(!g)return title('目前挑戰')+link('建立第一個目標','wizard','primary')+link('目標旅程','journey');
  if(edit)return title('調整未來安排')+`<form id="habit-edit" class="card">${edit.actions.map((a,i)=>`<details ${i===0?'open':''}><summary>${esc(a.title)}</summary>${field('更正名稱 '+(i+1),'edit-name-'+i,a.title)}${field('明天起用量 '+(i+1),'edit-quantity-'+i,a.quantity,'number','min="0.000001" max="1000000000000" step="0.000001" required')}<p>固定單位：${esc(a.unit)}；用途不替換。</p></details>`).join('')}<p>用量從 ${shift(dateNow(),1)} 起生效；今天與歷史不回算。日期調整請在下方各習慣選取。</p><select id="edit-index" aria-label="選擇要調整的習慣">${edit.actions.map((a,i)=>`<option value="${i}" ${i===edit.index?'selected':''}>${esc(a.title)}</option>`).join('')}</select>${calendar(edit.actions[edit.index],dateNow(),edit.deadline||g.deadline)}${check('我已核對變更與生效日','edit-confirm')}<div class="actions"><button class="primary">確認修改</button>${button('取消修改','cancel-edit')}</div></form>`;
  return title('目前挑戰')+`<section class="card"><h2>${esc(g.title)}</h2><p>${esc(g.outcome)}</p><p>${g.start} ～ ${g.deadline} · ${goalStatus()}</p>${g.actions.map(a=>`<article><h3>${esc(a.title)}</h3><p>${a.dates.length} 個已安排日 · 原始每次 ${esc(a.quantity)} ${esc(a.unit)}${a.next?' · '+a.next.from+' 起 '+esc(a.next.quantity)+' '+esc(a.unit):''}</p></article>`).join('')}<div class="actions">${goalStatus()==='進行中'?button('調整未來安排','edit-habits'):''}${link('記錄本次行動','record')}${['進行中','待回顧'].includes(goalStatus())?link('回顧這次挑戰','goal-review'):''}${link('目標旅程','journey')}</div></section>${pendingPreview(g)}`;
}
function record(){
  if(!s.draft)s.draft={raw:'',occurred:eventNow(),created:eventNow(),goal:false,person:false,quantity:'1',name:'虛構名片人物',mode:'文字',voice:'idle'};
  const d=s.draft;inputMode=d.mode||'文字';voice=d.voice||'idle';
  return title(isQuiet()?'今晚想留下什麼？':'記錄真實經歷',inputMode==='文字'&&!isQuiet())+`<form id="record" class="card narrow"><p>輸入會先成為草稿；不完整也可以先保存。</p><p class="callout">封測必備：真實語音及圖片辨識。本原型僅示範；真實服務未完成前不可宣稱封測就緒。</p><div class="row">${['文字','錄音','圖片','名片'].map(m=>`<button type="button" data-action="mode:${m}" aria-pressed="${inputMode===m}">${m}</button>`).join('')}</div>${text('今天發生了什麼？','raw',d.raw)}${field('實際發生的時間','occurred',d.occurred,'datetime-local','required')}<p class="muted">建立時間：${esc(d.created)} · 跨日補記仍採你確認的發生時間。</p>${inputMode==='錄音'?`<div class="callout"><b>錄音／權限／上傳／辨識皆為模擬</b><p id="voice-state">${esc(voice)}</p><div class="row">${button('開始模擬錄音','voice-start')}${button('模擬權限拒絕','voice-denied')}${button('停止','voice-stop')}${button('模擬試聽','voice-play')}${button('重錄','voice-reset')}${button('模擬上傳','voice-upload')}${button('模擬辨識失敗','voice-fail')}${button('重試辨識','voice-retry')}</div></div>`:''}${['圖片','名片'].includes(inputMode)?`<label class="label" for="file">${inputMode==='名片'?'掃描／上傳名片':'選擇圖片或截圖'}</label><input id="file" type="file" accept="image/*" ${inputMode==='名片'?'capture="environment"':''}><p>僅在本頁預覽，無上傳、OCR 或遠端保存。</p><div id="attachment">${d.fileName?`<p>${esc(d.fileName)}（重新整理後需重選預覽）</p>${button('移除附件','remove-file')}`:''}</div>${button(inputMode==='名片'?'填入虛構名片示例':'填入虛構圖片示例','sample')}<p class="callout">名片只是資訊來源，不代表雙方見面或已完成行動。</p>`:''}${check('稍後核對與目前目標的貢獻','record-goal',d.goal)}${check('稍後核對人物參與及資訊','record-person',d.person)}<div class="actions"><button class="primary">整理為草稿</button>${button('手動整理','manual-review')}${button('模擬整理失敗','organize-fail')}${button('先存草稿，明天再整理','save-draft')}${link('取消並保留草稿','world')}</div></form>`;
}
function review(){
  const d=s.draft;if(!d)return link('記錄新經歷','record');
  const card=d.mode==='名片';
  return title('先確認，再放進世界',!card)+`<form id="review" class="card narrow"><div class="callout">${d.manual?'手動整理':'模擬整理，沒有呼叫 AI'}。只有明確勾選的項目才保存。</div><details><summary>原始輸入與來源</summary><p>${esc(d.raw||d.fileName||'尚無文字內容')}</p></details>${card?field('人物稱呼','person-name',d.name,'text','required'):text('經歷摘要','summary',d.summary||d.raw)}<p>發生時間：${esc(d.occurred)}<br>建立時間：${esc(d.created)}</p>${card?check('確認人物資訊與來源','person-confirm'):check('確認經歷內容正確','experience-confirm')}${!card&&d.person?check(`確認關聯人物：${esc(who(d.personId||s.selected).name)}（實際參與，非僅提及）`,'person-confirm'):''}${!card&&d.goal&&s.goal?check('確認閱讀貢獻（不因排程自動完成）','goal-confirm')+field('實際投入量','actual-quantity',d.quantity,'number','min="0.000001" max="1000000000000" step="0.000001"'):''}${!card?check('建立後續任務：明天接續（選填）','task-confirm'):''}<p>未確認項目不更新。名片保存與私人模擬不發獎。</p><div class="actions"><button class="primary">${card?'只保存人物資料':'確認保存'}</button>${link('返回修改','record')}${button('先存草稿，明天再整理','save-draft')}</div></form>`;
}
function connections(){
  const available=allStories().map((v,i)=>({...v,index:i})).filter(v=>v.people.includes(s.focus));
  const story=available.find(v=>v.index===s.story)||available[0];if(!story)return title('交會')+`<section class="card"><p>還沒有這位人物的已確認共同經歷。</p>${link('返回收藏冊','cards')}${link('人物劇場','theater-hub')}</section>`;s.story=story.index;
  return title('沿著一段故事，遇見另一個人')+`<div class="row">${link('交會','connections','secondary')}${link('收藏冊','cards')}${link('人物劇場','theater-hub')}</div><p>正在探索：${esc(who(s.focus).name)}</p><div class="trail">${s.trail.map(x=>esc(who(x.focus).name)+' → ').join('')} ${esc(who(s.focus).name)}</div><article class="card story"><span class="date">${story.date} · ${story.tags==='已確認的原型經歷'?'已確認經歷（原型）':'虛構共同經歷'}</span><h2>${esc(story.title)}</h2><p>${esc(story.text)}</p><p>${esc(story.tags)}</p><small>使用者審閱不等於所有參與者證實；探索路徑不代表直接私人關係。</small><div class="actions">${story.people.map(id=>`<button data-action="explore:${id}">探索${esc(who(id).name)}</button>`).join('')}${button('查看連結來源','story-source')}</div></article><div class="row">${available.length>1?button('查看另一段故事','next-story'):''}${s.trail.length?button('上一段探索','previous-story'):''}${button('查看人物卡','focus-person')}</div>`;
}
function cards(){return title('人物收藏冊')+`<div class="row">${link('交會','connections')}${link('收藏冊','cards','secondary')}</div>${field('搜尋姓名、角色、目標或標籤','search',s.search||'')}<div class="grid">${s.people.filter(p=>(p.name+p.role+(p.tags||'')).includes(s.search||'')).map(p=>`<article class="card"><div class="person">${esc(p.name.slice(0,1))}</div><h2>${esc(p.name)}</h2><p>${esc(p.role)} · ${p.follow?'★ 已加星標':'未加星標'}</p><p class="muted">最近互動：虛構示例時間</p><button data-action="select:${p.id}">查看${esc(p.name)}</button></article>`).join('')}</div>${s.showSummary?`<section class="card"><h2>${esc(who(s.selected).name)}</h2><p>${esc(who(s.selected).role)} · 共同場合：虛構旅程</p><button data-action="follow" aria-pressed="${!!who(s.selected).follow}" title="${who(s.selected).follow?'再次點選可取消星標':'方便你之後找回，只有你自己看得到'}">${who(s.selected).follow?'★ 已加星標':'☆ 加入星標'}</button>${link('查看人物卡','person')}</section>`:''}`;}
function person(){
  const p=who(s.selected),tab=s.tab;
  return title(p.name+' · 人物 360°')+`<section class="card"><div class="person">${esc(p.name.slice(0,1))}</div><p>${esc(p.role)} · 虛構示例人物</p><div class="row"><span class="tag">見面 1 次（示例）</span><span class="tag">互動 2 筆（示例）</span><span class="tag">最近 2026-08-08（示例）</span></div></section><div class="row">${['人物總覽','共同經歷','合作與目標'].map(t=>button(t,'tab:'+t,t===tab?'secondary':'')).join('')}</div><section class="card">${tab==='人物總覽'?['興趣與嗜好','飲食偏好','專長與背景','互動習慣'].map(t=>`<details><summary><button data-action="dimension">${t}</button></summary><p>${t==='飲食偏好'?esc(p.food):'尚未了解'}</p>${t==='飲食偏好'&&p.source?button('查看來源','person-source'):''}</details>`).join('')+'<details><summary>共同關係／場合／交集</summary><p>共同旅行（虛構示例）；不推斷人物私人關係。</p></details>':tab==='共同經歷'?allStories().filter(x=>x.people.includes(p.id)).map(x=>`<article><h3>${esc(x.title)}</h3><p>${esc(x.date)} · ${esc(x.text)}</p></article>`).join(''):`<h2>相關目標</h2>${personGoals(p.id).map(g=>`<article><h3>${esc(g.title)}</h3><p>${goalLabel(g)}${g.reason?' · '+esc(g.reason):''}</p></article>`).join('')||'<p>尚未關聯目標</p>'}${s.goal&&goalStatus()==='進行中'?button('為此目標記錄經歷','record-context'):''}`}</section><div class="actions">${button('記錄新經歷','record-context')}${link('開啟小劇場','theater')}${button('探索相關故事','person-explore')}${link('返回收藏冊','cards')}</div>`;
}
function theater(){privateText=s.privateDrafts[s.selected+':'+scene]||'';return title('與 '+who(s.selected).name+' 的私人小劇場')+`<section class="card"><div class="row">${['見面前準備','情境演練','傳達心意','相遇後回顧'].map(t=>button(t,'scene:'+t,scene===t?'secondary':'')).join('')}</div><p class="callout">${scene==='情境演練'?'模擬不代表對方真實反應。':scene==='傳達心意'?'訊息草稿不自動發送。':scene==='相遇後回顧'?'請另記真實經歷並經人工確認。':'可參考已確認來源，筆記保持私人。'}</p>${scene==='相遇後回顧'?button('記錄真實經歷','record-context'):text('私人筆記','private-note',privateText)+`<div class="actions">${button('保存私人筆記','save-note')}${scene==='傳達心意'?button('複製草稿','copy-note'):''}</div>`}<h3>已保存私人筆記</h3>${s.notes.filter(n=>n.person===s.selected).map(n=>`<p>${esc(n.scene)}：${esc(n.text)}</p>`).join('')||'<p>尚無筆記。</p>'}<div class="actions">${link('返回人物卡','person')}${button('建立與此人物的情境','theater-v05-person','primary')}${button('加入其他人物一起演練','expand-rehearsal')}${link('返回人物劇場','theater-hub')}</div></section>`;}
function theaterHub(){return title('人物劇場',false)+`<section class="card theater-hub-hero"><div><p class="steps">一場、一個具體情境</p><h2>先試著說說看</h2><p>從已建立人物出發，練習一次現實對話。</p><div class="actions">${button('建立我的情境','theater-v05-new','primary')}${button('演練歷史','theater-v05-history')}${TheaterUI.snapshot().current?.status==='ACTIVE'?button('繼續目前演練','theater-v05-resume'):''}</div></div><img src="assets/idle@256.png" alt="Lumi 陪伴你準備演練"></section><section class="card"><h2>我的人物演練</h2><p>私人準備、演練與訊息草稿；不預測對方真實反應。</p>${s.people.map(p=>button('與'+esc(p.name)+'演練','private-person:'+p.id)).join('')}<h3>選擇同場人物</h3><p>可選本人已建立的任何人物；不會自動讓所有人加入。</p>${s.people.map(p=>check('加入'+esc(p.name),'roster-'+p.id,s.roster.includes(p.id))).join('')}${text('演練情境','rehearsal-context',s.rehearsalContext||'')}<details><summary>選取本次使用的來源</summary>${s.people.filter(p=>s.roster.includes(p.id)).map(p=>p.source?check('來源：'+esc(p.name),'rehearsal-source-'+p.id,s.rehearsalSources.includes(p.id))+'<p>'+esc(p.source)+'</p>':'<p>'+esc(p.name)+'：尚無可選來源，回應不能當成已知事實。</p>').join('')}</details>${button('開始多人演練','rehearsal-start','primary')}${s.rehearsal?link('繼續私人演練','group-theater'):''}${s.rehearsalHistory.length?'<h3>先前私人演練</h3>'+s.rehearsalHistory.map((r,i)=>button(esc(r.context||'私人演練')+'（'+r.participants.length+'位）','rehearsal-history:'+i)).join(''):''}</section><section class="card"><h2>示範情境</h2><p>三組十五位示範角色，與你的正式人物資料分開。</p>${link('情境體驗（示範角色）','demo-theater')}</section>`;}
// 私人多人物場次獨立保存；逐輪指定回應對象，避免無限自動互聊。
function groupTheater(){
  const r=s.rehearsal;if(!r)return link('返回人物劇場','theater-hub');
  return title(r.done?'私人演練回顧':'私人多人演練',false)+`<section class="card"><p class="callout">預寫示意，非真人反應或即時 AI；不更新正式人物／經歷。</p><h2>${esc(r.context||'私人演練')}</h2><p>在場：${r.participants.map(id=>esc(who(id).name)).join('、')}</p><details><summary>本場來源（只含明確選取內容）</summary>${r.sources.map(x=>'<p>'+esc(who(x.personId).name)+'：'+esc(x.text)+'</p>').join('')||'<p>未選來源；請勿把模擬當已知事實。</p>'}</details>${r.turns.map(t=>`<article data-speaker="${esc(t.speaker)}"><b>${esc(t.speaker==='user'?'你':who(t.speaker).name)}</b><p>${esc(t.text)}</p></article>`).join('')}${!r.done?`<label class="label" for="rehearsal-recipient">回應對象</label><select id="rehearsal-recipient">${r.participants.map(id=>`<option value="${esc(id)}" ${id===r.recipient?'selected':''}>${esc(who(id).name)}</option>`).join('')}</select>${text('你的演練發言','rehearsal-input',r.input||'')}<div class="actions">${button('送出演練發言','rehearsal-send','primary')}${button('模擬回應失敗','rehearsal-fail')}${button('結束演練並回顧','rehearsal-end')}</div>`:''}${link('返回人物劇場','theater-hub')}</section>`;
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
    birth:()=>title('一個新的開始')+`<section class="card hero"><div class="egg">✧</div><p>目標已確認，Lumi 誕生。破蛋畫面為線框示意。</p>${link('進入我的世界','world','primary')}</section>`,
    success:()=>title('這段經歷已留下',!isQuiet())+`<section class="card hero"><div class="egg">${isQuiet()?'◡ ◡':'✦'}</div><p>${isQuiet()?'辛苦了，今晚不用再做更多事。':'謝謝你，留下今天的一小步。'}</p><p>經歷已保存；只有你確認的內容會更新。封測不提供積分或虛擬獎勵。</p>${link('回到世界','world','primary')}${link('查看紀錄','records')}</section>`,
    records:()=>title('經歷紀錄')+`<section class="card">${s.draft?link('繼續草稿','record'):''}${s.records.map(r=>`<article><span class="tag">已確認 · 虛構示範</span><h2>${esc(r.summary)}</h2><p>發生：${esc(r.occurred)}<br>建立：${esc(r.created)}</p><p>${r.contribution?'已人工核對投入':'沒有採計目標貢獻'}${r.pending?' · 待回顧後另行採計':''}</p></article>`).join('')||'<p>尚無已確認經歷。</p>'}${link('記錄新經歷','record','primary')}</section>`};
  $('#app').innerHTML=(pages[s.route]||pages.world)();
  $('#nav').innerHTML=s.route==='intro'||s.route==='wizard'?'':[['世界','world'],['目標','goal'],['紀錄','records'],['關係','connections']].map(([t,r])=>link(t,r)).join('');
}
function capture(){
  if(s.route==='wizard'&&s.wizard){const w=s.wizard,a=w.actions[w.step-2];if($('#goal-name'))w.title=$('#goal-name').value;if($('#goal-outcome')){w.outcome=$('#goal-outcome').value;w.deadline=$('#deadline').value;}if(a&&$('#habit-name')){a.title=$('#habit-name').value;a.quantity=$('#habit-quantity').value;a.unit=$('#habit-unit').value;}}
  if(s.route==='record'&&s.draft){s.draft.raw=$('#raw').value;s.draft.occurred=$('#occurred').value;s.draft.goal=$('#record-goal').checked;s.draft.person=$('#record-person').checked;}
  if(s.route==='review'&&s.draft){if($('#summary'))s.draft.summary=$('#summary').value;if($('#person-name'))s.draft.name=$('#person-name').value;if($('#actual-quantity'))s.draft.quantity=$('#actual-quantity').value;}
  if(s.route==='theater'&&$('#private-note')){privateText=$('#private-note').value;s.privateDrafts[s.selected+':'+scene]=privateText;}
  if(s.route==='theater-hub'&&$('#rehearsal-context'))s.rehearsalContext=$('#rehearsal-context').value;
  if(s.route==='group-theater'&&s.rehearsal&&$('#rehearsal-input')){s.rehearsal.input=$('#rehearsal-input').value;s.rehearsal.recipient=$('#rehearsal-recipient').value;}
  if(s.route==='demo-theater'&&$('#demo-text'))s.demo.input=$('#demo-text').value;
  if(edit&&$('#habit-edit'))edit.actions.forEach((a,i)=>{a.title=$('#edit-name-'+i).value;a.quantity=$('#edit-quantity-'+i).value;});
  save();
}
function showSource(value){$('#source-text').textContent=value;$('#source').showModal();}
function sampleData(){s=initial();s.name='虛構體驗者';s.goal={title:'完成作品',outcome:'完成一份可分享的作品',start:dateNow(),deadline:shift(dateNow(),30),id:'demo-goal-'+Date.now(),status:'進行中',actions:['閱讀','整理','分享'].map(title=>({title,quantity:'1',unit:'次',dates:[dateNow(),shift(dateNow(),1)],cycle:'month'}))};go('world');}
document.addEventListener('input',event=>{capture();if(event.target.id==='search'){s.search=event.target.value;const pos=event.target.selectionStart;render();$('#search').focus();$('#search').setSelectionRange(pos,pos);}});
document.addEventListener('change',event=>{
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
  if(action==='reset'){if(confirm('只清除本原型的虛構資料？')){s=initial();nightOverride=null;attachment=null;edit=null;go('intro');}return;}
  if(action==='wizard-back'){s.wizard.step--;go('wizard');return;}
  if(action==='night-yes'||action==='night-no'){s.night.choice=action==='night-yes';s.night.enabled=s.night.choice;nightOverride=null;save();render();return;}
  if(action==='demo-time'){s.demoTime=$('#demo-time').value;nightOverride=null;save();render();return;}
  if(action==='quiet-off'||action==='quiet-on'){nightOverride=action==='quiet-on';render();return;}
  if(action==='edit-habits'){edit={actions:structuredClone(s.goal.actions),index:0};render();return;}
  if(action==='cancel-edit'){edit=null;go('goal');return;}
  const calendarAction=['month','week','weekdays','daily','clear','weekday','day','prev-month','next-month'].includes(kind);
  if(calendarAction){
    const w=edit?null:s.wizard,a=edit?edit.actions[edit.index]:w?.actions[w.step-2];if(!a)return;
    const start=edit?dateNow():w.start,end=edit?(edit.deadline||s.goal.deadline):w.deadline;
    if(kind==='month'||kind==='week')a.cycle=kind;
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
  if(action==='theater-v05-new'){go('theater-build');return;}
  if(action==='theater-v05-history'){go('theater-history');return;}
  if(action==='theater-v05-resume'){go('theater-live');return;}
  if(action==='theater-v05-person'){TheaterUI.openForPerson(s.selected);return;}
  if(action==='expand-rehearsal'){s.roster=[...new Set([...s.roster,s.selected])];go('theater-hub');return;}
  if(action==='rehearsal-start'){
    const ids=s.roster.filter(id=>s.people.some(p=>p.id===id));if(!ids.length){say('至少選一位已建立人物。');return;}
    if(s.rehearsal){if(!confirm('建立新場次？原場次會保留於私人演練歷史。'))return;s.rehearsalHistory.push(structuredClone(s.rehearsal));}
    s.rehearsal={participants:[...new Set(ids)],context:s.rehearsalContext||'',sources:s.people.filter(p=>ids.includes(p.id)&&s.rehearsalSources.includes(p.id)&&p.source).map(p=>({personId:p.id,text:p.source})),recipient:ids[0],turns:[],input:'',done:false};go('group-theater');return;
  }
  if(kind==='rehearsal-history'){s.rehearsal=structuredClone(s.rehearsalHistory[Number(value)]);go('group-theater');return;}
  if(action==='rehearsal-send'){
    const r=s.rehearsal;if(!r||r.done)return;if(!r.input.trim()||!r.participants.includes(r.recipient)){say('請輸入發言並選在場人物。');return;}
    r.turns.push({speaker:'user',recipient:r.recipient,text:r.input},{speaker:r.recipient,recipient:'user',text:'預寫示意：我們可以先釐清這次討論的目標，這不是對方的真實反應。'});r.input='';save();render();return;
  }
  if(action==='rehearsal-fail'){say('回應失敗（模擬）；發言與場次已保留，可以重試。');return;}
  if(action==='rehearsal-end'){s.rehearsal.done=true;save();render();return;}
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
  if(action==='record-context'){s.draft={raw:'',occurred:eventNow(),created:eventNow(),person:true,personId:s.selected,goal:!!s.goal,mode:'文字',quantity:'1'};go('record');return;}
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
  if(id==='intro'){s.name=$('#name').value;go('wizard');}
  if(id==='wizard'){
    const w=s.wizard,a=w.actions[w.step-2];
    if(w.step===1&&(!w.outcome.trim()||w.deadline<w.start)){say('請描述成果並選有效截止日。');return;}
    if(a&&!a.dates.length){say('每個習慣至少安排一天。');return;}
    if(w.step<5){w.step++;go('wizard');}else{s.goal={...structuredClone(w),id:'demo-goal-'+Date.now(),status:'進行中'};s.wizard=null;go('birth');}
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
    const contribution=!!$('#goal-confirm')?.checked,pending=s.goal?.status!=='進行中'||dateNow()>s.goal.deadline;
    s.records.push({...d,personId:d.personId||s.selected,id:'record-'+Date.now(),goalId:s.goal?.id,summary:$('#summary').value,person:!!$('#person-confirm')?.checked,quantity:$('#actual-quantity')?.value||null,task:!!$('#task-confirm')?.checked,contribution:contribution&&!pending,pending:contribution&&pending});s.draft=null;go('success');
  }
  if(id==='settings'){const start=$('#night-start').value,end=$('#night-end').value;if(start===end){say('請設定不同的開始與結束時間。');return;}s.night={choice:$('#night-auto').checked,enabled:$('#night-auto').checked,start,end};nightOverride=null;save();render();say('夜間示範設定已保存，可隨時關閉。');}
});
window.addEventListener('hashchange',()=>{if(location.hash==='#world')go('world');});
render();
