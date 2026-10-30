'use strict';
// 劇場 v0.5 是獨立的本機演練資料；絕不寫入正式人物、經歷或獎勵狀態。
const TheaterUI = (() => {
  const KEY = 'lifeworld:theater-wireframe:v05';
  const safe = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const defaults = () => ({stage:'situation', draft:{situation:'',purpose:'理解立場',people:[],sources:[]},current:null,history:[],asr:'idle',asrText:'',asrChecked:false,qa:'ANSWER',error:'',lumiInput:''});
  let state;
  try { state = JSON.parse(localStorage.getItem(KEY)); } catch (_) {}
  if (!state || !state.draft || !Array.isArray(state.history)) state = defaults();
  let host;
  let timer = null;
  const persist = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (_) { state.error='此裝置無法儲存演練，請先保留畫面。'; } };
  const nav = route => { persist(); host.go(route); };
  const btn = (label,action,cls='') => `<button type="button" data-theater="${action}" class="${cls}">${label}</button>`;
  const person = id => host.people().find(item => item.id===id);
  const chosen = () => state.draft.people.map(person).filter(Boolean);
  const cap = () => state.draft.people.length > 1 ? 6 : 8;
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
    return title('開始前先核對')+`<section class="card narrow"><p class="steps">3／3 · 來源與假設</p><h2>${safe(d.situation)}</h2><p><b>在場：</b>${chosen().map(p=>safe(p.name)).join('、')} · ${d.people.length>1?'多人 C1 有限交流':'1v1'}</p><p><b>練習目的：</b>${safe(d.purpose)}</p><h3>本場可用的已記錄資訊</h3>${chosen().map(p=>`<label class="check"><input type="checkbox" data-theater-source="${safe(p.id)}" ${d.sources.includes(p.id)?'checked':''} ${p.source?'':'disabled'}>使用 ${safe(p.name)} 的已記錄來源</label><p class="muted">${safe(p.source||'尚未了解；本場不得冒充已知事實。')}</p>`).join('')}<div class="callout">未選或未知資料只能作為明示假設；模擬對話不會回寫人物卡。演練可隨時暫停、旁聽或結束。</div>${error()}<div class="actions">${btn('返回修改人物','back')}${btn('確認開始演練','start','primary')}</div></section>`;
  }
  const error = () => state.error ? `<p class="theater-error" role="alert">${safe(state.error)}</p>` : '';
  function events(items) {
    return items.map(item=>`<article class="theater-event ${item.speaker==='user'?'mine':''}" data-theater-event data-speaker="${safe(item.speaker)}"><header><b>${safe(item.speaker==='user'?'你':item.speaker)}</b><span>→ ${safe(item.recipient||'全場')}</span>${item.behavior?`<small>${safe(item.behavior)}</small>`:''}</header><p>${safe(item.text)}</p></article>`).join('');
  }
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
    const selected=chosen();
    const recipients=selected.map(p=>`<option value="${safe(p.id)}" ${c.recipient===p.id?'selected':''}>${safe(p.name)}</option>`).join('');
    return title(selected.length>1?'多人情境演練':'1v1 情境演練')+`<div class="theater-scene"><div class="theater-room"><img src="assets/room-${document.body.classList.contains('quiet')?'quiet':'day'}@768x1024.png" alt="Lumi 房間背景，角色與文字獨立顯示"><div class="theater-room-caption"><b>${safe(c.situation)}</b><span>在場：${selected.map(p=>safe(p.name)).join('、')}</span></div></div><section class="card theater-main">${note}<div class="row between"><span>玩家行動 ${c.actions}／${cap()} · 角色每段最多 3 則 · Lumi ${c.lumiCount}／2 · 技術重試 ${c.retries}／1</span><span class="tag">${c.paused?'已暫停':'進行中'}</span></div><div class="theater-transcript" aria-live="polite">${events(c.events)}${c.pending.length?'<p class="theater-pending">還有未展示的角色發言；暫停或結束後不列入紀錄。</p>':''}</div>${c.unresolved?`<p class="callout">未解議題：${safe(c.unresolved)}</p>`:''}${error()}${c.failed?btn('重試本次發言','retry','secondary'):''}<div class="theater-compose"><label class="label" for="theater-recipient">發言對象</label><select id="theater-recipient"><option value="all" ${c.recipient==='all'?'selected':''}>全場</option>${recipients}</select><label class="label" for="theater-speech">你的發言</label><textarea id="theater-speech" ${c.paused?'disabled':''}>${safe(c.input)}</textarea><div class="actions">${btn('送出發言','send','primary')}${btn('繼續旁聽','listen')}${btn('介入討論','intervene')}${btn(c.paused?'繼續演練':'暫停演練','pause')}${btn('私下問 Lumi','lumi')}${btn('結束本場','end')}${btn('返回人物劇場','hub')}</div></div>${asr()}<details class="theater-qa"><summary>測試控制：模擬角色下一次行為（非產品介面）</summary><label for="theater-qa-select">下一次模擬結果</label><select id="theater-qa-select" aria-label="下一次模擬結果">${modes.map(mode=>`<option ${state.qa===mode?'selected':''}>${mode}</option>`).join('')}</select></details></section></div>`;
  }
  function lumi() {
    return title('私下問 Lumi')+`<section class="card narrow lumi-private"><img class="theater-lumi" src="assets/quiet@256.png" alt="安靜陪伴的 Lumi"><p>只有你看得到。Lumi 建議不會傳給場內人物，也不會自動變成你的長期標籤。</p><label class="label" for="theater-lumi-input">想問 Lumi 什麼？</label><textarea id="theater-lumi-input">${safe(state.lumiInput)}</textarea>${state.current?.lumiAdvice?`<p class="callout">${safe(state.current.lumiAdvice)}</p>`:''}${error()}<div class="actions">${btn('取得私人建議','lumi-advice','primary')}${btn('返回演練','lumi-back')}</div></section>`;
  }
  function recap() {
    const c=state.current;
    if (!c) return history();
    return title('本場演練回顧')+`<section class="card narrow"><h2>${safe(c.situation)}</h2><p>結束原因：<b>${safe(c.endReason||'由你結束')}</b> · ${c.actions} 次玩家行動</p><p>只有已展示的發言與行為會出現在此。未展示台詞不算已發生；停止不表示已發生的處理費用會撤銷。</p><div class="recap-events">${events(c.events)}</div><h3>未解議題</h3><p>${safe(c.unresolved||'還沒有明確的共識；下次可先核對彼此限制。')}</p><h3>下一次可以嘗試</h3><p>先問對方最在意的限制，再確認是否有共同可行的下一步。</p><p>這是模擬練習，不是對真人未來反應的預測。</p><div class="actions">${btn('再練一次','again','primary')}${btn('返回人物劇場','hub')}${btn('演練歷史','history')}</div></section>`;
  }
  function history() {
    return title('演練歷史')+`<section class="card narrow">${state.history.map((item,index)=>`<article><h2>${safe(item.situation)}</h2><p>${safe(item.mode)} · ${item.actions} 次行動 · ${safe(item.endReason)}</p>${btn('查看本場回顧','view:'+index)}${btn('刪除本場紀錄','delete:'+index)}</article>`).join('')||'<p>還沒有保存的演練。私人模擬不會改動人物卡。</p>'}${btn('返回人物劇場','hub')}</section>`;
  }
  function render(route) { return ({'theater-build':builder,'theater-preview':builder,'theater-live':live,'theater-lumi':lumi,'theater-recap':recap,'theater-history':history})[route]?.() || builder(); }
  function cancelPending() { if (timer) clearTimeout(timer); timer=null; if (state.current) state.current.pending=[]; }
  function generated(behavior) {
    const c=state.current, participants=chosen();
    if (!c || c.paused || c.endReason) return;
    if (behavior==='SILENCE') { c.events.push({speaker:participants[0].name,recipient:'你',behavior:'CHARACTER_SILENCE',text:'對方暫時沒有回應。你可以等待、澄清、再次發言或結束。'}); c.unresolved='對方暫時沒有回應'; return; }
    const phrases={ANSWER:'我們可以先釐清這次最重要的事。',ASK_BACK:'你認為誰先負責比較合適？',DEFER:'我需要再想一下，現在先不做承諾。',CLOSING:'今天先談到這裡，下次再討論。',EVADE:'我們先把其他事情說完吧。',MONOLOGUE:'我在意的有幾件事：時間、品質，還有是否能真的做到。'};
    const text=phrases[behavior] || phrases.ANSWER;
    c.pending=[{speaker:participants[0].name,recipient:'你',behavior,text}];
    if (participants.length>1) c.pending.push({speaker:participants[1].name,recipient:participants[0].name,behavior:'ANSWER',text:'我聽到了；我也想先確認時間安排。'});
    if (behavior==='DEFER'||behavior==='EVADE') c.unresolved='尚未釐清分工或承諾';
  }
  function showOne() {
    const c=state.current;
    if (!c || c.paused || c.endReason || !c.pending.length) return;
    c.events.push(c.pending.shift()); persist(); host.go('theater-live');
    // 每段最多兩則角色發言，保留介入窗口；舊台詞不會在下一次玩家行動後播放。
  }
  function finish(reason) {
    const c=state.current; if (!c || c.endReason) return;
    cancelPending(); c.endReason=reason; c.status='ENDED'; c.input='';
    state.history.push(JSON.parse(JSON.stringify(c)));
    nav('theater-recap');
  }
  function send(retry=false) {
    const c=state.current, utterance=c?.input.trim();
    if (!c || c.paused || c.endReason || !utterance) {state.error='請先輸入發言，或繼續演練。';persist();host.go('theater-live');return;}
    if (c.actions>=cap()) {finish('BUDGET_EXHAUSTED');return;}
    const behavior=state.qa;
    if (behavior==='PROVIDER_ERROR'||behavior==='PROVIDER_REFUSAL') {
      c.failed=true; state.error=behavior==='PROVIDER_ERROR'?'服務故障（模擬），發言已保留，可重試。':'服務拒絕（模擬），發言已保留；可改寫或結束。';
      state.qa='ANSWER'; persist();host.go('theater-live'); return;
    }
    cancelPending(); c.failed=false; state.error='';
    if (!retry) c.actions++;
    c.events.push({speaker:'user',recipient:c.recipient==='all'?'全場':person(c.recipient)?.name||'全場',text:utterance});
    c.input=''; generated(behavior); state.qa='ANSWER';
    persist();host.go('theater-live');
    timer=setTimeout(showOne,450);
    if (c.actions>=cap()) timer=setTimeout(()=>finish('BUDGET_EXHAUSTED'),850);
  }
  function handle(action) {
    const c=state.current;
    state.error='';
    if (action==='hub') { cancelPending(); nav('theater-hub'); return; }
    if (action==='history') { nav('theater-history'); return; }
    if (action==='next') { if (!state.draft.situation.trim()) state.error='請描述這次想練習的情境。'; else state.stage='people'; nav('theater-build'); return; }
    if (action==='back') { state.stage=state.stage==='preview'?'people':'situation'; nav('theater-build'); return; }
    if (action==='preview') { if (!chosen().length) state.error='至少選一位已建立人物。'; else state.stage='preview'; nav(state.error?'theater-build':'theater-preview'); return; }
    if (action==='start') {
      if (!state.draft.situation.trim()||!chosen().length) {state.error='請先完成情境與人物設定。';nav('theater-build');return;}
      cancelPending(); state.current={id:'wf-'+Date.now()+'-'+Math.random().toString(36).slice(2,8),situation:state.draft.situation,purpose:state.draft.purpose,personIds:[...state.draft.people],sourceIds:[...state.draft.sources],mode:chosen().length>1?'多人 C1':'1v1',status:'ACTIVE',actions:0,lumiCount:0,retries:0,recipient:'all',input:'',events:[],pending:[],paused:false,failed:false,endReason:null,unresolved:''};
      nav('theater-live');return;
    }
    if (action==='send'||action==='intervene') {send();return;}
    if (action==='retry') {if(c?.retries>=1){state.error='本場技術重試額度已用完；仍可修改文字或結束。';nav('theater-live');return;} c.retries++;send(true);return;}
    if (action==='listen') { if(c?.pending.length){showOne();} else {state.error='目前沒有待展示的角色發言；你可自行發言或結束。';nav('theater-live');} return; }
    if (action==='pause') {if (c?.paused) c.paused=false; else {cancelPending();if(c)c.paused=true;}nav('theater-live');return;}
    if (action==='lumi') {cancelPending();if(c)c.paused=true;nav('theater-lumi');return;}
    if (action==='lumi-advice') {if(!state.lumiInput.trim()){state.error='請先寫下想問的問題。';}else if(c.lumiCount>=2){state.error='本場 Lumi 私人建議已用完（原型配置）。';}else{c.lumiCount++;c.lumiAdvice='先問對方最在意的限制，再確認你們是否有可行的下一步。';}nav('theater-lumi');return;}
    if (action==='lumi-back') {if(c)c.paused=false;nav('theater-live');return;}
    if (action==='end') {finish('由你結束');return;}
    if (action==='again') {state.stage='preview';state.current=null;nav('theater-preview');return;}
    if (action.startsWith('view:')) {state.current=JSON.parse(JSON.stringify(state.history[Number(action.slice(5))]));nav('theater-recap');return;}
    if (action.startsWith('delete:')) {if(window.confirm('刪除這場私人模擬紀錄？')){state.history.splice(Number(action.slice(7)),1);state.current=null;nav('theater-history');}return;}
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
  return {connect(value){host=value;},render,cover,snapshot(){return JSON.parse(JSON.stringify(state));},openForPerson(id){state.draft.people=[id];state.stage='situation';nav('theater-build');}};
})();
