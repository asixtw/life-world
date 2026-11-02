'use strict';
// 本機兩個原型 key 的示例／清除使用可恢復日誌；不是跨分頁資料庫交易。
const WireframeStorage = (() => {
  const MAIN='lifeworld:flow-wireframe:v1',THEATER='lifeworld:theater-wireframe:v05',JOURNAL='lifeworld:flow-wireframe:transaction:v1'; // 僅觸及本原型命名空間。
  let blocked=false,error=''; // 回復失敗時禁止再做取代操作。
  const write=(key,value)=>value===null?localStorage.removeItem(key):localStorage.setItem(key,value); // null 表示移除此原型 key。
  function recover(){ // 頁面載入時先完成或撤回先前中斷的取代。
    try {const raw=localStorage.getItem(JOURNAL);if(!raw)return true;const tx=JSON.parse(raw);if(!tx||tx.version!==1||!['prepared','committed'].includes(tx.phase))throw Error('invalid journal');
      const main=tx.phase==='committed'?tx.nextMain:tx.beforeMain,theater=tx.phase==='committed'?tx.nextTheater:tx.beforeTheater;
      write(MAIN,main);write(THEATER,theater);localStorage.removeItem(JOURNAL);blocked=false;error='';return true;
    } catch(_){blocked=true;error='上次資料取代尚未完成復原。請保留此頁，不要清除瀏覽器資料。';return false;}
  }
  function replace(nextMain,nextTheater=null){ // 先保存原文，失敗則保留日誌供重載復原。
    try{if(blocked||localStorage.getItem(JOURNAL)){error='原型資料仍有待復原操作，請重新載入後重試。';return false;}}catch(_){error='無法讀取原型儲存空間；原有資料未更動。';return false;}
    let tx;
    try {tx={version:1,phase:'prepared',beforeMain:localStorage.getItem(MAIN),beforeTheater:localStorage.getItem(THEATER),nextMain,nextTheater};localStorage.setItem(JOURNAL,JSON.stringify(tx));}
    catch(_){error='無法準備安全取代，原有資料未更動。';return false;}
    try {write(MAIN,nextMain);write(THEATER,nextTheater);tx.phase='committed';localStorage.setItem(JOURNAL,JSON.stringify(tx));}
    catch(_){try{write(MAIN,tx.beforeMain);write(THEATER,tx.beforeTheater);localStorage.removeItem(JOURNAL);error='資料未能保存；原有內容已保留。';}catch(_){blocked=true;error='資料取代未完成；請保留此頁並重新載入以復原。';}return false;}
    try{localStorage.removeItem(JOURNAL);}catch(_){} // 已記錄 committed，重載可安全重放。
    error='';return true;
  }
  recover(); // theater.js 與 app.js 讀取各自狀態前必須先執行。
  return {replace,recover,get error(){return error;},get blocked(){return blocked;},journalKey:JOURNAL};
})();
// 劇場 v0.5 是獨立的本機演練資料；絕不寫入正式人物、經歷或獎勵狀態。
const TheaterUI = (() => {
  const KEY = 'lifeworld:theater-wireframe:v05';
  const safe = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const emptyDraft = () => ({id:crypto.randomUUID(),revision:0,stage:'situation',situation:'',purpose:'理解立場',people:[],sources:[],assumptions:[],updatedAt:Date.now()}); // 每份草稿有獨立身分。
  const defaults = () => ({schemaVersion:2,revision:0,stage:'situation',draft:emptyDraft(),current:null,history:[],viewingHistoryId:null,asr:'idle',asrText:'',asrChecked:false,qa:'ANSWER',error:'',lumiInput:'',soundEnabled:false}); // 舊欄位保留供原型相容。
  let state;
  let loadError=''; // 損毀或未知版本先阻止覆寫。
  try { const raw=localStorage.getItem(KEY); state=raw?JSON.parse(raw):defaults(); } catch (_) {loadError='劇場資料無法讀取，請保留此頁並匯出原始資料。';}
  if (state && state.schemaVersion>2) loadError='劇場資料版本較新，請使用新版頁面；目前不會覆寫。'; // 降版不可清空資料。
  if (!state && !loadError) state=defaults(); // 全新資料域才初始化。
  state ||= defaults(); // 讀取錯誤時僅提供唯讀退路。
  if (!loadError && state.schemaVersion!==2) { // 舊場缺乏可信快照，不接續生成。
    state.schemaVersion=2; state.revision||=0; state.viewingHistoryId=null;
    state.draft={...emptyDraft(),...state.draft,stage:state.stage||'situation'};
    state.history=(Array.isArray(state.history)?state.history:[]).map((h,index)=>({...h,id:h.id||`legacy-${index}`,legacySnapshotMissing:true,events:(h.events||[]).map(e=>({...e,visibility:'displayed'}))}));
    if(state.current && !state.current.endReason){state.current.paused=true;state.current.pauseReason='舊版場次缺少可信快照，請結束回顧或另建新場。';state.current.legacySnapshotMissing=true;}
  }
  state.draft ||= emptyDraft(); state.history ||= []; state.viewingHistoryId ||= null;
  if(state.current?.pending?.length){const action=state.current.actionRecords?.at(-1),attempt=action?.attempts?.at(-1);if(attempt?.status==='pending'){attempt.status='interrupted';if(action.status==='pending')action.status='interrupted';}state.current.pending.forEach(e=>e.visibility='discarded');state.current.pending=[];state.current.generationEpoch=(state.current.generationEpoch||0)+1;} // 刷新不補播未展示內容；未完成技術嘗試標為中斷。
  let host;
  let timer = null;
  let soundEpoch = 0;
  const sounding = new Set();
  function stopSounds(){soundEpoch++;for(const oscillator of sounding){try{oscillator.stop();}catch(_){}}sounding.clear();}
  const persist = () => { // revision 防止舊分頁蓋掉新資料。
    if(loadError){state.error=loadError;return false;}
    try {const disk=JSON.parse(localStorage.getItem(KEY)||'null');if(disk && (disk.revision||0)!==state.revision){state.error='其他分頁已更新劇場資料。請複製目前輸入，再重新讀取；此頁不會覆寫。';showSaveError();return false;}const next={...state,revision:state.revision+1};localStorage.setItem(KEY,JSON.stringify(next));state.revision=next.revision;return true;}
    catch (_) {state.error='尚未保存，請保留此頁並重試。';showSaveError();return false;}
  };
  const showSaveError = () => {const main=document.querySelector('.theater-main');if(!main)return;let p=main.querySelector('.theater-error');if(!p){p=document.createElement('p');p.className='theater-error';p.setAttribute('role','alert');main.querySelector('.theater-compose')?.before(p);}if(p)p.textContent=state.error;}; // 不重繪輸入框，保留可複製文字。
  const nav = route => {if(persist())host.go(route);else host.go(host.route?.()||route);}; // 保存失敗保留畫面。
  const btn = (label,action,cls='') => `<button type="button" data-theater="${action}" class="${cls}">${label}</button>`;
  const person = id => host.people().find(item => item.id===id);
  const chosen = () => state.draft.people.map(person).filter(Boolean); // 僅建場預覽可讀可變人物。
  const sessionCast = c => (c.participantSnapshots||[]).map(p=>({id:p.personId,name:p.name,role:p.roles?.[0],source:p.source})); // 進行中固定快照。
  const cap = () => state.current?.limitsSnapshot?.playerActions ?? (state.draft.people.length > 1 ? 6 : 8);
  const cover = (name) => ({'三國策略':'assets/cover-three-kingdoms.800x450.png','國際協調':'assets/cover-international-dialogue@800x450.png','哲學辯論':'assets/cover-philosophy-800x450.png'})[name];
  const title = text => `<span class="tag planned">可操作 Wireframe · 模擬，非正式 App／AI</span><h1 id="title" tabindex="-1">${text}</h1>`;
  const note = '<p class="muted">對話、轉錄及額度皆為本機模擬；角色回應不代表真人意見，也不更新人物事實、目標或積分。</p>';
  function selectList() {
    return host.people().map(item => `<label class="theater-person"><input type="checkbox" data-theater-person="${safe(item.id)}" aria-label="加入${safe(item.name)}" ${state.draft.people.includes(item.id)?'checked':''}><span><b>${safe(item.name)}</b><small>${safe(item.role||'已建立人物')}</small></span></label>`).join('');
  }
  function builder() {
    const d=state.draft;
    if (state.stage==='situation') return title('建立我的情境')+`<section class="theater-layout"><div class="card"><p class="steps">1／3 · 情境</p><label class="label" for="theater-situation">你想模擬什麼情境？</label><textarea id="theater-situation" placeholder="例如：與兩位朋友討論下次作品分工">${safe(d.situation)}</textarea><p>只模擬這一次具體互動。場次結束後可重新開始，不沿用虛構承諾。</p>${error()}<div class="actions">${btn('下一步：選擇人物','next','primary')}${btn('返回人物劇場','hub')}</div></div><aside class="theater-aside"><img src="assets/listening@256.png" alt="Lumi 陪你準備情境"><p>先想像一次對話，不必事先寫好全部台詞。</p></aside></section>`;
    if (state.stage==='people') return title('選擇同場人物')+`<section class="card narrow"><p class="steps">2／3 · 人物與目的</p><p>只可選你已建立的人物；一位是 1v1，兩位以上是有限多人交流。示範人物另有入口。</p><div class="theater-person-list">${selectList()}</div><label class="label" for="theater-purpose">這次你希望練習什麼？</label><select id="theater-purpose" aria-label="這次你希望練習什麼？">${['理解立場','練習提問','釐清分工','表達需求','面對不同意見'].map(item=>`<option ${d.purpose===item?'selected':''}>${item}</option>`).join('')}</select>${error()}<div class="actions">${btn('返回情境描述','back')}${btn('檢查本場設定','preview','primary')}</div></section>`;
    return title('開始前先核對')+`<section class="card narrow"><p class="steps">3／3 · 來源與假設</p><h2>${safe(d.situation)}</h2><p><b>在場：</b>${chosen().map(p=>safe(p.name)).join('、')} · ${'你與 '+d.people.length+' 位模擬人物'}</p><p><b>練習目的：</b>${safe(d.purpose)}</p><h3>本場可用的已記錄資訊</h3>${chosen().map(p=>`<label class="check"><input type="checkbox" data-theater-source="${safe(p.id)}" ${d.sources.includes(p.id)?'checked':''} ${p.source?'':'disabled'}>使用 ${safe(p.name)} 的已記錄來源</label><p class="muted">${safe(p.source||'尚未了解；本場不得冒充已知事實。')}</p>`).join('')}<div class="callout">未選或未知資料只能作為明示假設；模擬對話不會回寫人物卡。演練可隨時暫停、旁聽或結束。</div>${error()}<div class="actions">${btn('返回修改人物','back')}${btn('確認開始演練','start','primary')}</div></section>`;
  }
  const error = () => state.error ? `<p class="theater-error" role="alert">${safe(state.error)}</p>` : '';
  const behaviorLabels={ANSWER:'回應',ASK_BACK:'反問',CHARACTER_SILENCE:'暫時沉默',DEFER:'暫緩答覆',CLOSING:'準備結束',EVADE:'轉移話題',MONOLOGUE:'持續表達'};
  function events(items) {
    return items.filter(item=>!item.visibility||item.visibility==='displayed').map(item=>`<article class="theater-event ${item.speaker==='user'?'mine':''}" data-theater-event data-speaker="${safe(item.speaker)}"><header><b>${safe(item.speaker==='user'?'你':item.speaker)}</b><span>→ ${safe(item.recipient||'全場')}</span>${item.behavior?`<small>${safe(behaviorLabels[item.behavior]||item.behavior)}</small>`:''}</header><p>${safe(item.text)}</p></article>`).join('');
  }
  let audioContext=null; // 音效只在明確開啟及使用者手勢後合成。
  const soundFailure = () => {stopSounds();state.soundEnabled=false;state.error='此裝置無法播放提示音；文字提示仍可使用。';const toggle=document.querySelector('[data-theater="sound-toggle"]');if(toggle)toggle.textContent='提示音：關閉（點此開啟）';showSaveError();persist();};
  const sound = kind => {if(!state.soundEnabled)return;if(!window.AudioContext){soundFailure();return;}const epoch=soundEpoch;try{audioContext ||= new AudioContext();const play=()=>{if(epoch!==soundEpoch||!state.soundEnabled)return;try{const oscillator=audioContext.createOscillator(),gain=audioContext.createGain(),now=audioContext.currentTime;oscillator.frequency.value=kind==='error'?220:kind==='complete'?660:440;gain.gain.setValueAtTime(.0001,now);gain.gain.exponentialRampToValueAtTime(.035,now+.015);gain.gain.exponentialRampToValueAtTime(.0001,now+.13);oscillator.connect(gain).connect(audioContext.destination);sounding.add(oscillator);oscillator.onended=()=>sounding.delete(oscillator);oscillator.start(now);oscillator.stop(now+.14);}catch(_){soundFailure();}};if(audioContext.state==='suspended')Promise.resolve(audioContext.resume()).then(play).catch(()=>{if(epoch===soundEpoch)soundFailure();});else play();}catch(_){soundFailure();}}; // 拒絕解鎖或無音訊設備時保留文字提示。
  const soundControl = () => btn(state.soundEnabled?'提示音：開啟（點此靜音）':'提示音：關閉（點此開啟）','sound-toggle','secondary'); // 狀態始終可見。
  const modes = ['ANSWER','ASK_BACK','SILENCE','DEFER','CLOSING','EVADE','MONOLOGUE','PROVIDER_ERROR','PROVIDER_REFUSAL'];
  function asr() {
    if (state.asr==='idle') return btn('錄音轉文字（模擬）','asr-open');
    let content='';
    if (state.asr==='permission') content='<p>尚未請求真實麥克風權限。</p>'+btn('模擬允許麥克風','asr-allow')+btn('模擬拒絕麥克風','asr-deny');
    else if (state.asr==='recording') content='<p>錄音中（模擬，沒有音檔）</p>'+btn('停止錄音','asr-stop')+btn('取消錄音','asr-cancel');
    else if (state.asr==='stopped') content=btn('模擬轉錄成功','asr-success')+btn('模擬轉錄失敗','asr-fail');
    else if (state.asr==='failed') content='<p>轉錄失敗。錄音草稿仍在此頁；仍可直接打字。</p>'+btn('重試轉錄（模擬）','asr-retry');
    else if (state.asr==='denied') content='<p>麥克風權限遭拒；仍可直接打字。</p>'+btn('模擬允許麥克風','asr-allow');
    else content=`<label class="label" for="theater-asr-text">校對轉錄文字</label><textarea id="theater-asr-text">${safe(state.asrText)}</textarea><label class="check"><input id="theater-asr-check" type="checkbox" ${state.asrChecked?'checked':''}>我已核對轉錄內容</label>${btn('加入發言草稿','asr-apply')}`;
    return `<div class="theater-asr"><h3>錄音轉文字 · 模擬</h3>${content}${state.error?error():''}</div>`;
  }
  function live() {
    const c=state.current;
    if (!c) return builder();
    if(!c.endReason){const invalid=validity(c);if(invalid&&!c.paused){cancelPending();c.paused=true;c.pauseReason=invalid;state.error=invalid;persist();}} // 返回頁面即檢查撤回，不等下一次送出。
    const selected=sessionCast(c);
    const recipients=selected.map(p=>`<option value="${safe(p.id)}" ${c.recipient===p.id?'selected':''}>${safe(p.name)}</option>`).join('');
    const cast=`<div class="theater-room-cast" aria-label="本場在場人物示意">${selected.map(p=>`<span class="theater-room-person"><b aria-hidden="true">${safe(p.name.slice(0,1))}</b><span>${safe(p.name)}</span></span>`).join('')}</div>`;
    return title(selected.length>1?'多人情境演練':'1v1 情境演練')+`<div class="theater-scene"><div class="theater-room"><img src="assets/room-${document.body.classList.contains('quiet')?'quiet':'day'}@768x1024.png" alt="Lumi 房間背景，角色與文字獨立顯示">${cast}<div class="theater-room-caption"><b>${safe(c.situation)}</b><span>在場：${selected.map(p=>safe(p.name)).join('、')} · 姓名牌非本人肖像</span></div></div><section class="card theater-main">${note}${soundControl()}<div class="row between"><span>玩家行動 ${c.actions}／${cap()} · 角色每段最多 3 則 · Lumi ${c.lumiCount}／2 · 技術重試 ${c.retries}／1</span><span class="tag">${c.paused?'已暫停':'進行中'}</span></div>${c.pauseReason?`<p class="callout">${safe(c.pauseReason)}</p>`:''}<div class="theater-transcript" aria-live="polite">${events(c.events)}${c.pending.length?'<p class="theater-pending">還有未展示的角色發言；暫停或結束後不列入紀錄。</p>':''}</div>${c.unresolved?`<p class="callout">未解議題：${safe(c.unresolved)}</p>`:''}${error()}${c.failed?btn('重試本次發言','retry','secondary'):''}<div class="theater-compose"><label class="label" for="theater-recipient">發言對象</label><select id="theater-recipient"><option value="all" ${c.recipient==='all'?'selected':''}>全場</option>${recipients}</select><label class="label" for="theater-speech">你的發言</label><textarea id="theater-speech" ${c.paused?'disabled':''}>${safe(c.input)}</textarea><div class="actions">${btn('送出發言','send','primary')}${btn('繼續旁聽','listen')}${btn('介入討論','intervene')}${btn(c.paused?'繼續演練':'暫停演練','pause')}${btn('私下問 Lumi','lumi')}${btn('結束本場','end')}${btn('返回人物劇場','hub')}</div></div>${asr()}<details class="theater-qa"><summary>測試控制：模擬角色下一次行為（非產品介面）</summary><label for="theater-qa-select">下一次模擬結果</label><select id="theater-qa-select" aria-label="下一次模擬結果">${modes.map(mode=>`<option ${state.qa===mode?'selected':''}>${mode}</option>`).join('')}</select></details></section></div>`;
  }
  function lumi() {
    return title('私下問 Lumi')+`<section class="card narrow lumi-private"><img class="theater-lumi" src="assets/quiet@256.png" alt="安靜陪伴的 Lumi"><p>只有你看得到。Lumi 建議不會傳給場內人物，也不會自動變成你的長期標籤。</p><label class="label" for="theater-lumi-input">想問 Lumi 什麼？</label><textarea id="theater-lumi-input">${safe(state.lumiInput)}</textarea>${state.current?.lumiAdvice?`<p class="callout">${safe(state.current.lumiAdvice)}</p>`:''}${error()}<div class="actions">${btn('取得私人建議','lumi-advice','primary')}${btn('返回演練','lumi-back')}</div></section>`;
  }
  function recap() {
    const c=state.viewingHistoryId?state.history.find(h=>h.id===state.viewingHistoryId):state.current;
    if (!c) return history();
    return title(state.viewingHistoryId?'歷史回顧':'本場演練回顧')+`<section class="card narrow"><h2>${safe(c.situation)}</h2><p>結束原因：<b>${safe(c.endReason||'由你結束')}</b> · ${c.actions} 次玩家行動</p><p>只有已展示的發言與行為會出現在此。未展示台詞不算已發生；停止不表示已發生的處理費用會撤銷。</p><div class="recap-events">${events(c.events)}</div><h3>未解議題</h3><p>${safe(c.unresolved||'還沒有明確的共識；下次可先核對彼此限制。')}</p><h3>下一次可以嘗試</h3><p>先問對方最在意的限制，再確認是否有共同可行的下一步。</p><p>這是模擬練習，不是對真人未來反應的預測。</p><div class="actions">${btn('再練一次','again','primary')}${btn('返回人物劇場','hub')}${btn('演練歷史','history')}</div></section>`;
  }
  function history() {
    return title('演練歷史')+`<section class="card narrow">${state.history.map((item,index)=>`<article><h2>${safe(item.situation)}</h2><p>${safe(item.mode?.startsWith('多人')?'多人情境演練':item.mode)} · ${item.actions} 次行動 · ${safe(item.endReason)}</p>${item.legacySnapshotMissing?'<p class="muted">舊版紀錄，缺少當時人物／來源版本；僅供唯讀查看。</p>':''}${btn('查看本場回顧','view:'+item.id)}${btn('刪除本場紀錄','delete:'+item.id)}</article>`).join('')||'<p>還沒有保存的演練。私人模擬不會改動人物卡。</p>'}${btn('返回人物劇場','hub')}</section>`;
  }
  function render(route) { return ({'theater-build':builder,'theater-preview':builder,'theater-live':live,'theater-lumi':lumi,'theater-recap':recap,'theater-history':history})[route]?.() || builder(); }
  function cancelPending() { // 已排隊但未展示的回應一律作廢。
    stopSounds();
    if(timer)clearTimeout(timer);timer=null;
    const c=state.current;if(!c)return;
    c.generationEpoch=(c.generationEpoch||0)+1;
    (c.pending||[]).forEach(e=>{e.visibility='discarded';});c.pending=[];
  }
  function validity(c) { // 每次發言前檢查來源與人物是否仍可使用。
    if(c.legacySnapshotMissing)return '舊版場次缺少可信快照，請結束回顧或另建新場。';
    for(const p of c.participantSnapshots||[])if(!person(p.personId)){p.availability='missing';return `人物 ${p.name} 已不存在；本場已暫停。`;}
    for(const src of c.sourceSnapshots||[]){const p=person(src.personId);if(!p||p.source!==src.content){src.validity='invalid';return `已選來源 ${src.personName} 已撤回或變更；本場已暫停。`;}}
    return '';
  }
  function generated(behavior,action) { // 角色只讀建場快照，絕不讀可變草稿。
    const c=state.current,all=sessionCast(c),participants=c.recipient!=='all'?[...all.filter(p=>p.id===c.recipient),...all.filter(p=>p.id!==c.recipient)]:all;
    const base={sessionId:c.id,actionId:action.actionId,visibility:'queued'};
    if(behavior==='SILENCE'){c.events.push({...base,eventId:crypto.randomUUID(),speaker:participants[0].name,recipient:'你',behavior:'CHARACTER_SILENCE',text:'對方暫時沒有回應。你可以等待、澄清、再次發言或結束。',visibility:'displayed',displayedAt:Date.now()});c.unresolved='對方暫時沒有回應';return;}
    const phrases={ANSWER:'我們可以先釐清這次最重要的事。',ASK_BACK:'你認為誰先負責比較合適？',DEFER:'我需要再想一下，現在先不做承諾。',CLOSING:'今天先談到這裡，下次再討論。',EVADE:'我們先把其他事情說完吧。',MONOLOGUE:'我在意的有幾件事：時間、品質，還有是否能真的做到。'};
    c.pending=[{...base,eventId:crypto.randomUUID(),speaker:participants[0].name,recipient:'你',behavior,text:phrases[behavior]||phrases.ANSWER}];
    if(participants.length>1)c.pending.push({...base,eventId:crypto.randomUUID(),speaker:participants[1].name,recipient:participants[0].name,behavior:'ANSWER',text:'我聽到了；我也想先確認時間安排。'});
    if(behavior==='DEFER'||behavior==='EVADE')c.unresolved='尚未釐清分工或承諾';
  }
  function showOne(sessionId,actionId,attemptId,epoch) { // 晚到計時器必須逐一符合四個身分。
    const c=state.current,a=c?.actionRecords?.find(x=>x.actionId===actionId),t=a?.attempts?.at(-1);
    if(!c||c.id!==sessionId||c.generationEpoch!==epoch||t?.attemptId!==attemptId||c.paused||c.endReason||!c.pending.length)return;
    const event=c.pending.shift();if(event.visibility!=='queued')return;
    event.visibility='displayed';event.displayedAt=Date.now();c.events.push(event);
    if(persist())host.go('theater-live');
  }
  function finish(reason) { // 先存歷史，再切換畫面；失敗保留活動場。
    const c=state.current;if(!c||c.endReason)return;
    const before=structuredClone(state);cancelPending();c.endReason=reason;c.status='ENDED';c.endedAt=Date.now();
    state.history.push(structuredClone(c));
    if(!persist()){state.current=before.current;state.history=before.history;host.go('theater-live');return;}
    state.viewingHistoryId=null;host.go('theater-recap');sound('complete');
  }
  function send(retry=false) { // 玩家行動與技術嘗試分開保存。
    const c=state.current;if(!c||c.endReason)return;
    const invalid=validity(c);if(invalid){cancelPending();c.paused=true;c.pauseReason=invalid;state.error=invalid;nav('theater-live');sound('error');return;}
    if(c.paused){state.error='請先繼續演練。';nav('theater-live');return;}
    const before=structuredClone(state); // 儲存失敗時復原行動、額度及未送文字。
    let action=retry?c.actionRecords?.at(-1):null;
    if(retry&&(!action||action.status!=='failed'||c.retries>=1)){state.error='本次發言已完成或無法再重試。';nav('theater-live');return;}
    if(!retry){if(c.actions>=cap()){finish('BUDGET_EXHAUSTED');return;}const text=c.input.trim();if(!text){state.error='請先輸入發言。';nav('theater-live');return;}cancelPending();action={actionId:crypto.randomUUID(),sessionId:c.id,text,recipientIds:[c.recipient],status:'pending',counted:true,attempts:[],createdAt:Date.now()};c.actionRecords ||= [];c.actionRecords.push(action);c.actions++;}
    else{c.retries++;cancelPending();}
    const attempt={attemptId:crypto.randomUUID(),actionId:action.actionId,status:'pending',epoch:c.generationEpoch};action.attempts.push(attempt);
    const behavior=state.qa;state.qa='ANSWER';
    if(behavior==='PROVIDER_ERROR'||behavior==='PROVIDER_REFUSAL'){attempt.status='failed';attempt.errorKind=behavior;action.status='failed';c.failed=behavior==='PROVIDER_ERROR';c.input=action.text;state.error=behavior==='PROVIDER_ERROR'?'服務故障（模擬），發言已保留，可重試。':'服務拒絕（模擬），發言已保留；可改寫或結束。';if(!persist()){state=before;state.error='尚未保存，請保留此頁並重試。';host.go('theater-live');return;}host.go('theater-live');sound('error');return;}
    attempt.status='succeeded';action.status='succeeded';c.failed=false;state.error='';
    if(!c.events.some(e=>e.actionId===action.actionId&&e.speaker==='user'))c.events.push({eventId:crypto.randomUUID(),sessionId:c.id,actionId:action.actionId,speaker:'user',recipient:c.recipient==='all'?'全場':sessionCast(c).find(p=>p.id===c.recipient)?.name||'全場',text:action.text,visibility:'displayed',displayedAt:Date.now()});
    c.input='';generated(behavior,action);if(!persist()){state=before;state.error='尚未保存，請保留此頁並重試。';host.go('theater-live');return;}host.go('theater-live');sound('confirm');
    const epoch=c.generationEpoch,tId=attempt.attemptId;
    if(c.pending.length)timer=setTimeout(()=>showOne(c.id,action.actionId,tId,epoch),450);
    if(c.actions>=cap()&&!c.pending.length)finish('BUDGET_EXHAUSTED');
    else if(c.actions>=cap())setTimeout(()=>{if(state.current?.id===c.id&&state.current.generationEpoch===epoch)finish('BUDGET_EXHAUSTED');},850);
  }
  function handle(action) {
    const c=state.current;
    const disk=(()=>{try{return JSON.parse(localStorage.getItem(KEY)||'null');}catch(_){return null;}})(); // 按鈕命令也先做版本核對。
    if(disk&&(disk.revision||0)!==state.revision){state.error='其他分頁已更新劇場資料。請複製目前輸入，再重新讀取；此頁不會覆寫。';showSaveError();return;}
    state.error='';
    if(action==='sound-toggle'){state.soundEnabled=!state.soundEnabled;if(!state.soundEnabled)stopSounds();nav('theater-live');if(state.soundEnabled)sound('confirm');return;}
    if (action==='hub') { cancelPending(); state.viewingHistoryId=null; nav('theater-hub'); return; }
    if (action==='history') { state.viewingHistoryId=null; nav('theater-history'); return; }
    if (action==='next') { if (!state.draft.situation.trim()) state.error='請描述這次想練習的情境。'; else state.stage='people'; nav('theater-build'); return; }
    if (action==='back') { state.stage=state.stage==='preview'?'people':'situation'; nav('theater-build'); return; }
    if (action==='preview') { if(state.draft.people.some(id=>!person(id)))state.error='選擇的人物已不存在，請返回人物步驟重新確認。'; else if (!chosen().length) state.error='至少選一位已建立人物。'; else state.stage='preview'; nav(state.error?'theater-build':'theater-preview'); return; }
    if (action==='start') { // 未結束場次須由使用者明確選擇處理。
      const missing=state.draft.people.filter(id=>!person(id));
      if(!state.draft.situation.trim()||!state.draft.people.length||missing.length){state.error=missing.length?'選擇的人物已不存在，請返回人物步驟重新確認。':'請先完成情境與人物設定。';nav('theater-build');return;}
      const sourceMissing=state.draft.sources.filter(id=>!person(id)?.source);
      if(sourceMissing.length){state.error='已選來源不存在或已撤回，請重新確認。';nav('theater-preview');return;}
      if(c&&!c.endReason&&!window.confirm('目前演練尚未結束。確定結束原場並開始新場？取消會保留原場與新草稿。'))return;
      const before=structuredClone(state),people=chosen(),createdAt=Date.now();
      const snapshots=people.map(p=>({personId:p.id,snapshotVersion:1,name:p.name,roles:[p.role||'已建立人物'],kind:'saved_person',capturedAt:createdAt,availability:'available'}));
      const sources=people.filter(p=>state.draft.sources.includes(p.id)).map(p=>({sourceId:`local:${p.id}:source`,personId:p.id,personName:p.name,capturedAt:createdAt,content:p.source,sourceKind:'user_report',selectedByUser:true,validity:'valid'}));
      if(c&&!c.endReason){cancelPending();c.endReason='新場取代';c.status='ENDED';c.endedAt=createdAt;state.history.push(structuredClone(c));}
      state.current={id:crypto.randomUUID(),revision:0,createdAt,situation:state.draft.situation,purpose:state.draft.purpose,scenarioSnapshot:{situation:state.draft.situation,purpose:state.draft.purpose},personIds:[...state.draft.people],participantSnapshots:snapshots,sourceIds:[...state.draft.sources],sourceSnapshots:sources,assumptionsSnapshot:[],mode:people.length>1?'多人情境演練':'1v1 情境演練',limitsSnapshot:{playerActions:people.length>1?6:8,characterEvents:3,lumi:2,technicalRetries:1},status:'ACTIVE',actions:0,actionRecords:[],lumiCount:0,retries:0,recipient:'all',input:'',events:[],pending:[],generationEpoch:0,paused:false,failed:false,endReason:null,unresolved:'',lumiPrivate:[]};
      state.viewingHistoryId=null;
      if(!persist()){state.current=before.current;state.history=before.history;host.go('theater-preview');return;}
      host.go('theater-live');sound('confirm');return;
    }
    if (action==='send'||action==='intervene') {send();return;}
    if (action==='retry') {send(true);return;}
    if (action==='listen') { if(c?.pending.length){const a=c.actionRecords?.at(-1),t=a?.attempts?.at(-1);showOne(c.id,a.actionId,t.attemptId,c.generationEpoch);} else {state.error='目前沒有待展示的角色發言；你可自行發言或結束。';nav('theater-live');} return; }
    if (action==='pause') {if(c?.paused){const invalid=validity(c);if(invalid){c.pauseReason=invalid;state.error=invalid;}else{c.paused=false;c.pauseReason='';}} else {cancelPending();if(c)c.paused=true;}nav('theater-live');return;}
    if (action==='lumi') {cancelPending();if(c)c.paused=true;nav('theater-lumi');return;}
    if (action==='lumi-advice') {if(!state.lumiInput.trim()){state.error='請先寫下想問的問題。';}else if(c.lumiCount>=2){state.error='本場 Lumi 私人建議已用完（原型配置）。';}else{c.lumiCount++;c.lumiAdvice='先問對方最在意的限制，再確認你們是否有可行的下一步。';c.lumiPrivate ||= [];c.lumiPrivate.push({input:state.lumiInput,advice:c.lumiAdvice});}nav('theater-lumi');return;}
    if (action==='lumi-back') {if(c)c.paused=false;nav('theater-live');return;}
    if (action==='end') {finish('由你結束');return;}
    if (action==='again') {const source=state.viewingHistoryId?state.history.find(h=>h.id===state.viewingHistoryId):c;state.draft={...emptyDraft(),stage:'preview',situation:source?.situation||'',purpose:source?.purpose||'理解立場',people:(source?.personIds||[]).filter(id=>person(id)),sources:[]};state.stage='preview';state.viewingHistoryId=null;nav('theater-preview');return;}
    if (action.startsWith('view:')) {state.viewingHistoryId=action.slice(5);nav('theater-recap');return;}
    if (action.startsWith('delete:')) {const id=action.slice(7);if(window.confirm('刪除這場私人模擬紀錄？')){state.history=state.history.filter(h=>h.id!==id);if(state.viewingHistoryId===id)state.viewingHistoryId=null;nav('theater-history');}return;}
    if (action==='asr-open') state.asr='permission';
    if (action==='asr-allow') state.asr='recording';
    if (action==='asr-deny') state.asr='denied';
    if (action==='asr-stop') state.asr='stopped';
    if (action==='asr-cancel') state.asr='idle';
    if (action==='asr-fail') state.asr='failed';
    if (action==='asr-retry'||action==='asr-success') {state.asr='review';state.asrText='模擬轉錄：請核對這段話。';state.asrChecked=false;}
    if (action==='asr-apply') {if (!state.asrChecked) state.error='請先核對轉錄內容。';else {c.input=state.asrText;state.asr='idle';}}
    nav('theater-live');
  }
  document.addEventListener('click',event=>{const button=event.target.closest('button[data-theater]');if(!button)return;event.preventDefault();event.stopImmediatePropagation();handle(button.dataset.theater);},true);
  document.addEventListener('input',event=>{
    const item=event.target;
    if(item.id==='theater-situation')state.draft.situation=item.value;
    if(item.id==='theater-speech'&&state.current)state.current.input=item.value;
    if(item.id==='theater-asr-text'){state.asrText=item.value;state.asrChecked=false;const checkbox=document.querySelector('#theater-asr-check');if(checkbox)checkbox.checked=false;}
    if(item.id==='theater-lumi-input')state.lumiInput=item.value;
    persist();
  },true);
  document.addEventListener('change',event=>{
    const item=event.target;
    if(item.dataset.theaterPerson){state.draft.people=item.checked?[...new Set([...state.draft.people,item.dataset.theaterPerson])]:state.draft.people.filter(id=>id!==item.dataset.theaterPerson);}
    if(item.dataset.theaterSource){state.draft.sources=item.checked?[...new Set([...state.draft.sources,item.dataset.theaterSource])]:state.draft.sources.filter(id=>id!==item.dataset.theaterSource);}
    if(item.id==='theater-purpose')state.draft.purpose=item.value;
    if(item.id==='theater-recipient'&&state.current)state.current.recipient=item.value;
    if(item.id==='theater-qa-select')state.qa=item.value;
    if(item.id==='theater-asr-check')state.asrChecked=item.checked;
    persist();
  },true);
  return {connect(value){host=value;},render,cover,snapshot(){return JSON.parse(JSON.stringify({...state,builderDraft:state.draft,activeSession:state.current}));},openForPerson(id){newDraft(id);},newDraft(id){newDraft(id);},resetMemory(){cancelPending();state=defaults();loadError='';},hasData(){return !!(state.current||state.history.length||state.draft.situation||state.draft.people.length);},leave(){cancelPending();persist();}};
  function newDraft(id){if(state.draft.situation||state.draft.people.length){if(window.confirm('繼續上次草稿？按取消可選擇另建或保留。')){state.stage=state.draft.stage||state.stage;nav('theater-build');return;}if(!window.confirm('另建新情境將取代上次草稿。按取消保留原草稿。'))return;}state.draft=emptyDraft();if(id)state.draft.people=[id];state.stage='situation';nav('theater-build');}
})();
