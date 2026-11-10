'use strict';
/** 獨立設計樣本：只有記憶體狀態，沒有 fetch、帳號交換、模型或資料庫存取。 */
const UX=(()=>{
 const $=s=>document.querySelector(s), h=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const roleNames={interaction:'有直接互動',participant:'一起參與，未直接互動',mention:'只是提及'};
 const people=[{id:'yi',name:'怡君',hint:'讀書會的朋友',old:{interests:'閱讀'}},{id:'zhe',name:'阿哲',hint:'攝影社的朋友',old:{}},{id:'an',name:'小安',hint:'大學同學',old:{}}];
 const raw='今天和怡君在咖啡店聊了半小時，一起完成讀書練習。怡君說最近開始學攝影，喜歡拍街景，也提到阿哲。小安加入我們，說他開始喜歡登山。他也分享自己在青木設計擔任設計師的近況。';
 const summary='和怡君一起完成讀書練習，聊了最近的生活。小安也加入分享工作近況；怡君另外提到了阿哲。';
 const scenes={summaryChanged:'04 · 原文修改需重核對',summaryReviewed:'04 · 摘要重新核對完成',manualUnrelated:'04 · 無關手動資訊保留',aiManual:'AI · 預設手動',aiConsentFirst:'AI · 首次範圍授權',aiAuthorized:'AI · 有效授權不重複詢問',aiFailure:'AI · 整理失敗可手動',aiCandidate:'AI · 可編輯示意候選',guestAccount:'帳號 · 訪客',guestStep3:'帳號 · 第三步訪客',upgradeConfirm:'帳號 · 保存世界確認',upgradeSuccess:'帳號 · 原地升級成功',oldWorldWarning:'帳號 · 登入舊世界告知',registeredAccount:'帳號 · 正式帳號選單',authFailure:'帳號 · 驗證失敗',authCancelled:'帳號 · 取消驗證',authUnavailable:'帳號 · 能力未開啟',authConflict:'帳號 · 綁定衝突',step1:'01 · 文字記錄',media:'01 · 文字與素材',empty:'01 · 空白',guest:'01 · 訪客',aiOff:'01 · AI 不可用',step2:'02 · 不關聯目標',goal:'02 · 有活動數量',step3:'03 · 沒有人物',existing:'03 · 選擇既有人物',new:'03 · 新增人物',multiple:'03 · 多人與提及',multiUpdates:'04 · 多人物各自變更',mention:'03 · 只有提及',step4:'04 · 摘要確認',newPreview:'04 · 新人物預覽',updatePreview:'04 · 既有人物變更',noChanges:'04 · 無變更',source:'04 · 來源',saveFailure:'04 · 確認失敗',saveSuccess:'確認成功示意',drafts:'草稿列表',draftEmpty:'草稿空白',deleteConfirm:'刪除二次確認',deleteFailure:'刪除失敗',deleteConflict:'刪除版本衝突',deleteSuccess:'刪除成功',leave:'離開三選一'};
 let s,returnFocus=null,returnFocusKey=null,toastTimer,sequence=0;
 const clone=x=>JSON.parse(JSON.stringify(x));
 const change=()=>({id:'yi-interest',label:'興趣與嗜好',old:'閱讀',value:'攝影、街景拍攝',operation:'add',origin:'AI 候選 · 示意',quote:'怡君說最近開始學攝影，喜歡拍街景',supported:true,accepted:false});
 const member=(id,role='interaction')=>({...clone(people.find(p=>p.id===id)),key:id,isNew:false,role,mentionReviewed:false,changes:[]});
 function sessionFixture(status='registered',owner='world-one',available=true){return {source:'DESIGN_FIXTURE_ONLY',ownerId:owner,status,capabilities:{googleUpgrade:available,googleLogin:available}};}
 // 只做保守的字串來源判定，不假裝已有語意模型；忽略外圍空白及換行格式。
 function normalizedRaw(value){return String(value).normalize('NFC').replace(/\r\n/g,'\n').trim();}
 function updateRaw(next){const previous=s.raw;s.raw=next;if(normalizedRaw(previous)===normalizedRaw(next))return;
  if(s.summary){s.summaryNeedsReview=true;if(s.aiCandidate)s.aiCandidateStale=true;}
  for(const p of s.people){
   if(p.role==='mention'){const i=previous.indexOf(p.name);p.mentionQuote=p.mentionQuote||(i<0?p.name:previous.slice(Math.max(0,i-8),i+p.name.length+8));if(!next.includes(p.mentionQuote))p.mentionReviewed=false;}
   for(const x of p.changes){if(x.origin.includes('AI')||!next.includes(x.quote)){x.accepted=false;x.needsReview=true;}}
  }
 }
 function grantFixture(){return {source:'DESIGN_PERMISSION_FIXTURE_ONLY',ownerId:s.session.ownerId,provider:'Google Gemini',scope:'explicit-draft-text',purpose:'summary-and-task-candidates',version:1,active:true};}
 function hasAiGrant(){const g=s.aiGrant;return !!(g&&g.active&&g.ownerId===s.session.ownerId&&g.provider==='Google Gemini'&&g.scope==='explicit-draft-text'&&g.purpose==='summary-and-task-candidates'&&g.version===1);}
 function aiControls(){if(s.session.status==='guest')return '<p class="quiet-note">訪客可用文字留下經歷；影像、語音和 AI 需登入後使用。</p>';
  return `<section class="card compact"><fieldset class="organize-choice"><legend>這段經歷要怎麼整理？</legend><label class="choice"><input type="radio" name="organize-mode" value="manual" ${s.aiMode==='manual'?'checked':''}><span><strong>直接使用我的原文</strong><small>預設手動，不傳送內容給模型。</small></span></label><label class="choice"><input type="radio" name="organize-mode" value="ai" ${s.aiMode==='ai'?'checked':''} ${!s.aiAvailable?'disabled':''}><span><strong>使用 AI 整理這段經歷</strong><small>${s.aiAvailable?'產生可編輯候選，最後仍由你確認。':'AI 暫不可用，仍能手動完成。'}</small></span></label></fieldset>${s.aiMode==='ai'?`<p class="small">${hasAiGrant()?'相同範圍授權有效（示意），不重複詢問。':'首次使用需確認提供者、傳送範圍與用途。'}</p>`:''}${s.aiState==='working'?'<div class="notice" role="status">正在準備整理候選（設計示意，未呼叫模型）…</div>':s.aiState==='failed'?'<div class="notice error" id="ai-error" role="alert">AI 整理失敗示意，原文與手動摘要仍保留。</div><div class="row wrap"><button data-action="retry-ai">重試整理（示意）</button><button class="text-button" data-action="manual-mode">改用手動</button></div>':s.aiMode==='ai'&&hasAiGrant()?'<button class="text-button small-button" data-action="run-ai">重新整理（示意）</button>':''}</section>`;
 }
 function aiAuthorization(){open(sheetHead('使用 AI 前，先了解資料用途')+`<p><strong>服務提供者：Google Gemini</strong> <span class="badge outline">示意設定</span></p><p>只有在你主動選擇 AI 時，才將這篇<strong>未確認草稿的文字原文</strong>交給提供者，產生摘要與後續任務候選。原文中的姓名也會隨文字送出。</p><p class="small">不包含其他經歷、人物完整檔案或未校對的原始影像／音訊；已校對並加入原文的文字會包含在內。背景 AI 授權不涵蓋這項操作。</p><p class="small">相同 Owner、提供者、用途與資料範圍的授權有效時不再詢問；範圍改變需重新取得授權。此 Demo 授權只存在記憶體，重置即清除。</p><div class="notice">這是互動設計，不會傳送任何資料或呼叫模型。正式產品依後端實際提供者與授權狀態顯示。</div><div class="sheet-actions"><button data-action="cancel-ai">維持手動</button><button class="primary" data-action="approve-ai">同意並整理（示意）</button></div>`);}
 function chooseAi(){if(s.session.status!=='registered'||!s.aiAvailable){s.aiMode='manual';syncAiPresentation();return;}if(!s.raw.trim()){toast('請先留下原文，再選擇 AI 整理。');s.aiMode='manual';syncAiPresentation();return;}s.aiMode='ai';syncAiPresentation();if(!hasAiGrant())aiAuthorization();else requestAiDemo();}
 async function requestAiDemo(){if(s.aiMode!=='ai'||!s.aiAvailable||s.session.status!=='registered'||!hasAiGrant())return;
  const generation=++s.aiGeneration,input=s.raw,owner=s.session.ownerId;s.aiPreviewRequests++;s.aiState='working';syncAiPresentation();await new Promise(r=>setTimeout(r,650));
  if(generation!==s.aiGeneration||owner!==s.session.ownerId||s.aiMode!=='ai')return;
  if(input!==s.raw){s.aiState='stale';toast('來源已修改，沒有套用舊的示意回應。');syncAiPresentation();return;}
  if(s.aiOutcome==='failure'){s.aiState='failed';syncAiPresentation();return;}
  const candidate=input===raw?summary:input;s.aiState='candidate';
  if(s.summaryEdited){s.aiSuggestion=candidate;s.aiSuggestionRaw=input;}else{s.summary=candidate;s.summarySourceRaw=input;s.summaryNeedsReview=false;s.aiCandidate=true;s.aiCandidateStale=false;}
  syncAiPresentation();toast('示意候選已備妥；沒有呼叫真實 AI。');
 }
 function summaryNotice(){return s.summaryNeedsReview?`<div class="notice warning" id="summary-review-notice" role="alert"><strong>來源已修改，需要重新核對摘要。</strong><p>目前摘要${s.summaryEdited?'包含你的手動編輯，已完整保留':'仍保留原內容'}，不代表已依新原文整理。</p><details><summary>查看目前原文</summary><div class="source-quote">${h(s.raw)}</div></details><div class="row wrap space-top"><button class="small-button" data-action="review-summary">已對照原文，保留此摘要</button><button class="text-button small-button" data-action="use-current-raw">改用目前原文</button></div></div>`:s.summaryBeforeReplace?'<button class="text-button small-button" data-action="restore-summary">復原上一版摘要</button>':'';}
 function aiResult(){return s.aiSuggestion?`<details class="notice"><summary>有一份新整理候選（示意），尚未取代你的摘要</summary><p>${h(s.aiSuggestion)}</p><button data-action="adopt-ai">採用這份候選</button></details>`:'';}
 function summaryOrigin(){return s.aiCandidate?`<span class="badge outline">${s.aiCandidateStale?(s.summaryNeedsReview?'既有 AI 候選 · 來源已修改':'既有 AI 候選 · 已人工重核對'):'AI 候選示意，可編輯'}</span>`:'';}
 function summaryControls(){return `<div class="field" style="margin-top:0"><label for="summary">本次經歷摘要 <span id="summary-origin">${summaryOrigin()}</span></label><textarea class="summary" id="summary" data-bind="summary">${h(s.summary)}</textarea></div><div id="summary-status">${summaryNotice()}</div><div id="ai-candidate-result">${aiResult()}</div>`;}
 function syncAiPresentation(){const region=$('#ai-region');if(region)region.innerHTML=aiControls();if(s.step===4&&s.view==='flow'){const input=$('#summary');if(input&&document.activeElement!==input)input.value=s.summary;if($('#summary-origin'))$('#summary-origin').innerHTML=summaryOrigin();if($('#summary-status'))$('#summary-status').innerHTML=summaryNotice();if($('#ai-candidate-result'))$('#ai-candidate-result').innerHTML=aiResult();}}
 function base(){return {step:1,identity:'registered',session:sessionFixture('registered'),authOutcome:'success',accountMessage:'',raw,summary:'',occurredAt:'2026-11-10T18:30',tab:'text',photo:false,audio:false,goal:false,qty:['','',''],people:[],related:false,aiMode:'manual',aiGrant:null,aiOutcome:'success',aiState:'idle',aiPreviewRequests:0,aiGeneration:0,aiSuggestion:'',aiAvailable:true,aiCandidate:false,aiCandidateStale:false,summaryNeedsReview:false,summaryEdited:false,summarySourceRaw:raw,backgroundAiGrant:false,task:'',dirty:false,view:'flow',error:'',saveOutcome:'success',deleteOutcome:'success',deleting:false,drafts:[{id:'draft-one',title:'咖啡店裡的一次交流',updated:'今天 18:30',revision:3},{id:'draft-two',title:'傍晚的散步與想法',updated:'昨天 19:10',revision:1}],draftId:null};}
 function load(scene='step1'){
  sequence++;close(false);s=base();
  if(['step2','goal'].includes(scene))s.step=2;
  if(['step3','existing','new','multiple','mention'].includes(scene))s.step=3;
  if(['step4','newPreview','updatePreview','noChanges','source','saveFailure','saveSuccess'].includes(scene))s.step=4;
  if(scene==='empty')s.raw='';if(scene==='media')s.photo=s.audio=true;
  if(scene==='guest')s.identity='guest';if(scene==='aiOff')s.aiAvailable=false;
  if(scene==='goal'){s.goal=true;s.qty=['0.5','1',''];}
  if(['existing','step4','updatePreview','source','saveFailure'].includes(scene)){s.related=true;s.people=[member('yi')];}
  if(['new','newPreview'].includes(scene)){s.related=true;s.people=[{key:'new-an',name:'小安',isNew:true,role:'interaction',changes:[]}];}
  if(scene==='newPreview'){s.people[0].changes=[{id:'an-job',label:'工作',old:'',value:'設計師',origin:'原文候選 · 示意',quote:'小安加入我們，說他開始喜歡登山。他也分享自己在青木設計擔任設計師的近況',supported:false,accepted:false},{id:'an-company',label:'公司',old:'',value:'青木設計',origin:'原文候選 · 示意',quote:'小安加入我們，說他開始喜歡登山。他也分享自己在青木設計擔任設計師的近況',supported:false,accepted:false}];}
  if(['updatePreview','source','saveFailure'].includes(scene))s.people[0].changes=[change()];
  if(scene==='noChanges'){s.related=true;s.people=[member('yi','participant')];}
  if(scene==='mention'){s.related=true;s.people=[member('zhe','mention')];s.people[0].mentionReviewed=true;}
  if(scene==='multiple'){s.related=true;s.people=[member('yi'),{key:'new-an',name:'小安',isNew:true,role:'participant',changes:[]},member('zhe','mention')];s.people[2].mentionReviewed=true;}
  if(['drafts','draftEmpty','deleteConfirm','deleteFailure','deleteConflict','deleteSuccess'].includes(scene))s.view='drafts';
  if(scene==='draftEmpty')s.drafts=[];
  if(scene==='saveFailure'){s.error='連線暫時中斷，尚未確認保存。內容與勾選項目都保留，請重試。';s.saveOutcome='failure';}
  if(scene==='multiUpdates'){s.step=4;s.related=true;s.people=[member('yi'),member('an','participant'),member('zhe','mention')];s.people[0].changes=[change()];s.people[1].changes=[{id:'an-interest',label:'興趣與嗜好',old:'',value:'登山',origin:'使用者輸入 · 示意',quote:'小安加入我們，說他開始喜歡登山',supported:true,accepted:false}];s.people[2].mentionReviewed=true;}
  if(s.step===4)s.summary=summary;
  if(scene==='saveSuccess')s.view='success';
  if(scene==='deleteSuccess'){s.drafts=s.drafts.filter(d=>d.id!=='draft-one');s.deleted=true;}
  if(['guestAccount','guestStep3','upgradeConfirm','upgradeSuccess','oldWorldWarning','authFailure','authCancelled','authUnavailable','authConflict'].includes(scene)){s.identity='guest';s.step=scene==='guestAccount'?1:3;s.goal=true;s.qty=['0.5','1',''];}
  s.session=sessionFixture(s.identity,'world-one',scene!=='authUnavailable');
  if(scene==='upgradeSuccess'){s.identity='registered';s.session=sessionFixture('registered');s.related=true;s.accountMessage='世界已升級（示意），仍在第 3 步；Owner 與輸入保留。';}
  if(scene==='authCancelled')s.accountMessage='Google 驗證已取消（示意），仍是原訪客世界，內容沒有變更。';
  if(['summaryChanged','summaryReviewed','manualUnrelated'].includes(scene)){
   s.step=4;s.summary='這是我親自整理並保留的摘要。';s.summaryEdited=true;s.related=true;s.people=[member('yi'),member('an','participant')];s.people[0].changes=[{...change(),accepted:true}];s.people[1].changes=[{id:'an-manual',label:'興趣與嗜好',old:'',value:'登山',origin:'使用者輸入 · 示意',quote:'小安加入我們，說他開始喜歡登山',supported:true,accepted:true}];
   updateRaw(raw.replace('怡君說最近開始學攝影，喜歡拍街景','怡君說最近改練習水彩'));
   if(scene==='summaryReviewed'){s.summaryNeedsReview=false;s.summarySourceRaw=s.raw;}
  }
  if(scene==='aiConsentFirst')s.aiMode='ai';
  if(['aiAuthorized','aiFailure','aiCandidate'].includes(scene)){s.aiMode='ai';s.aiGrant=grantFixture();}
  if(scene==='aiFailure'){s.aiState='failed';s.aiOutcome='failure';}
  if(scene==='aiAuthorized')s.aiState='ready';
  if(scene==='aiCandidate'){s.step=4;s.aiState='candidate';s.aiCandidate=true;s.summary=summary;s.summarySourceRaw=s.raw;}
  $('#scenario').value=scene;syncTools();render();
  if(scene==='aiConsentFirst')aiAuthorization();
  if(['newPreview','updatePreview','noChanges'].includes(scene))preview(s.people[0].key);
  if(scene==='source')showSource('yi','yi-interest');
  if(['deleteConfirm','deleteFailure','deleteConflict'].includes(scene)){s.deleteOutcome=scene==='deleteFailure'?'failure':scene==='deleteConflict'?'conflict':'success';syncTools();deleteDialog('draft-one',scene==='deleteFailure'?'failure':scene==='deleteConflict'?'conflict':'');}
  if(['upgradeConfirm','authFailure','authConflict'].includes(scene))upgradeDialog(scene==='authFailure'?'驗證失敗，仍是原訪客世界。內容都保留，請重試。':scene==='authConflict'?'這個 Google 帳號已綁定另一個世界。沒有合併或覆寫，原訪客世界仍保留。':'');
  if(scene==='oldWorldWarning')oldWorldDialog();
  if(scene==='registeredAccount')accountMenu();
  if(scene==='leave'){s.dirty=true;leave();}
 }
 function syncTools(){$('#ai-outcome').value=s.aiOutcome;$('#auth-outcome').value=s.authOutcome;$('#save-outcome').value=s.saveOutcome;$('#delete-outcome').value=s.deleteOutcome;}
 function buttons(last=false){return `<div class="actions">${s.step>1?'<button data-action="back">上一步</button>':''}<button class="primary" data-action="${last?'confirm':'next'}">${last?'確認這段經歷':'下一步 →'}</button></div><button class="text-button save-link" data-action="save-draft">保存草稿，稍後再繼續</button>`;}
 function frame(){return `<div class="flow-top"><button class="text-button" data-action="leave">← 離開</button><span>${s.step} / 4 <button class="text-button small-button" data-action="draft-menu" aria-label="草稿選單">⋯</button></span></div><div class="progress" aria-label="第${s.step}步，共4步">${[1,2,3,4].map(n=>`<span class="${n<=s.step?'active':''}"></span>`).join('')}</div>`;}
 function render(){
  document.body.dataset.view=s.view;renderAccount();
  $('#main').innerHTML=s.view==='drafts'?draftView():s.view==='success'?successView():s.view==='old-world'?oldWorldView():frame()+[step1,step2,step3,step4][s.step-1]();
  if(s.accountMessage)$('#main').insertAdjacentHTML('afterbegin',`<div id="account-feedback" class="notice ${s.session.status==='guest'?'':'success'}" role="status">${h(s.accountMessage)}</div>`);
  $('#main h1')?.setAttribute('tabindex','-1');
  if(s.view==='flow'&&s.error){$('#flow-error')?.remove();$('#main').insertAdjacentHTML('beforeend',`<div id="flow-error" class="notice error" role="alert">${h(s.error)}</div>`);}
 }
 function step1(){
  const content=s.tab==='text'?`<div class="field"><label for="raw-text">發生了什麼？</label><textarea id="raw-text" data-bind="raw" placeholder="用自己的話，留下真實經過…">${h(s.raw)}</textarea></div>`:`<div class="file-sample"><h3>${s.tab==='photo'?'拍照或加入影像':'錄音或加入音檔'}</h3><p class="small">設計樣本不讀取照片、不開啟麥克風、不上傳。</p><button class="space-top" data-action="sample-media" data-kind="${s.tab}">${(s.tab==='photo'?s.photo:s.audio)?'移除示意素材':'＋ 加入示意素材'}</button></div><button class="text-button small-button" data-action="tab" data-tab="text">返回文字內容</button>`;
  return `<div class="eyebrow">A MOMENT WORTH KEEPING</div><h1>記錄這一刻。</h1><p class="subtitle">先留下真實經過，目標和人物稍後再補。</p><section class="card"><div class="input-tabs" role="group" aria-label="記錄方式">${[['text','文字'],['photo','拍照／影像'],['audio','語音']].filter(([v])=>s.session.status!=='guest'||v==='text').map(([v,t])=>`<button class="${s.tab===v?'active':''}" data-action="tab" data-tab="${v}" aria-pressed="${s.tab===v}">${t}</button>`).join('')}</div>${content}<div class="sources"><span class="source-chip">文字${s.raw?' · 已輸入':' · 尚未輸入'}</span>${s.photo?'<span class="source-chip">影像 · 示意<button aria-label="移除影像" data-action="sample-media" data-kind="photo">×</button></span>':''}${s.audio?'<span class="source-chip">語音 · 示意<button aria-label="移除音訊" data-action="sample-media" data-kind="audio">×</button></span>':''}</div><details class="space-top"><summary>發生時間 · ${h(s.occurredAt.replace('T',' '))}</summary><div class="field"><label for="occurred-at">實際發生時間</label><input id="occurred-at" type="datetime-local" data-bind="occurredAt" value="${h(s.occurredAt)}"></div></details></section><div id="ai-region">${aiControls()}</div>${buttons()}`;
 }
 function step2(){return `<div class="eyebrow">ONE SMALL STEP</div><h1>這次完成了多少？</h1><p class="subtitle">有和目標相關才填；普通日記也能直接繼續。</p><section class="card"><label class="choice"><input type="radio" name="goal-mode" value="none" ${!s.goal?'checked':''}><span><strong>不關聯目標</strong><small>只收藏這段生活</small></span></label><label class="choice"><input type="radio" name="goal-mode" value="goal" ${s.goal?'checked':''}><span><strong>有目標進度</strong><small>留下這次實際完成的活動量</small></span></label>${s.goal?`<div class="field"><label for="goal">選擇目標</label><select id="goal"><option>養成持續學習的習慣</option></select></div><div class="space-top">${[['專注練習','小時'],['整理閱讀筆記','篇'],['分享與交流','次']].map(([n,u],i)=>`<div class="quantity-row"><label for="q${i}">${n}<br><span>${u}</span></label><input id="q${i}" data-qty="${i}" type="number" min="0" step="0.5" placeholder="—" value="${h(s.qty[i])}" aria-label="${n} ${u}"></div>`).join('')}<p class="hint space-top">空白或 0 表示不累計。由你填寫，不由 AI 推定。</p></div>`:''}</section>${buttons()}`;}
 function peopleRegion(){
  if(s.session.status==='guest')return `<p class="subtitle">訪客暫不建立人物資料。可以直接確認經歷，或先保存世界再繼續。</p><section class="card"><p>本次不關聯人物。</p><p class="small">保存世界後，留在這一步解鎖人物功能；原文與活動量不會重填。</p>${s.session.capabilities.googleUpgrade?'<button class="primary space-top" data-action="upgrade">保存我的世界</button>':'<div class="notice">保存帳號服務尚未開放，仍可繼續訪客文字流程。</div>'}</section>`;
  return `<p class="subtitle">一起參與、直接互動、只是提及，分開記下。</p><section class="card"><label class="choice"><input type="radio" name="people-mode" value="none" ${!s.related?'checked':''}><span><strong>不關聯人物</strong><small>這是自己的日記或活動</small></span></label><label class="choice"><input type="radio" name="people-mode" value="some" ${s.related?'checked':''}><span><strong>有相關人物</strong><small>可以一位一位加入</small></span></label>${s.related?`<div class="row wrap space-top"><button data-action="pick">選擇既有人物</button><button class="text-button" data-action="new-person">＋ 新增人物</button></div>${s.people.length?s.people.map(p=>`<div class="person-row" data-person="${h(p.key)}"><span class="person-avatar">${h([...p.name][0])}</span><div class="person-main"><strong>${h(p.name)}</strong> ${p.isNew?`<span class="badge pending">待建立</span><button class="text-button inline-link" data-action="rename-person" data-key="${h(p.key)}">修改稱呼</button>`:''}<select data-role="${h(p.key)}" aria-label="${h(p.name)}本次角色"><option value="">請選擇本次關聯</option>${Object.entries(roleNames).map(([v,t])=>`<option value="${v}" ${p.role===v?'selected':''}>${t}</option>`).join('')}</select>${p.role==='mention'?`<button class="text-button inline-link" data-action="mention-source" data-key="${h(p.key)}">${p.mentionReviewed?'✓ 已核對原文提及':'核對提及的原文片段'}</button>`:''}</div><button class="remove" data-action="remove-person" data-key="${h(p.key)}" aria-label="移除${h(p.name)}">×</button></div>`).join(''):'<div class="empty"><span class="empty-symbol">♧</span>先選一位人物，或記下新認識的名字。</div>'}<p class="hint space-top">只是提及不代表出席；一起參與也不等於直接互動。新人物會等到最後確認才建立。</p>`:''}</section>`;
 }
 function step3(){return `<div class="eyebrow">PEOPLE IN THIS MOMENT</div><h1>這次有誰在其中？</h1><div id="people-region">${peopleRegion()}</div>${buttons()}`;}
 function renderAccount(){ // 正式接線只能讀實際 Session/capabilities；此檔僅載入標明來源的設計 Fixture。
  const session=s.session;
  $('#account-region').innerHTML=session.status==='guest'?`<div class="guest-account"><span class="guest-label">訪客</span>${session.capabilities.googleUpgrade?'<button class="text-button small-button" data-action="upgrade">保存我的世界</button>':'<span class="small">保存服務暫不可用</span>'}<button class="avatar account-button" data-action="account-menu" aria-label="訪客帳號選單">訪</button></div>`:'<button class="avatar account-button" data-action="account-menu" aria-label="帳號選單">光</button>';
 }
 function accountMenu(){open(sheetHead(s.session.status==='guest'?'訪客世界':'我的帳號')+(s.session.status==='guest'?`<p class="small">訪客資料依目前 Session 保留。清除 Cookie 後無法保證找回。</p><div class="field">${s.session.capabilities.googleUpgrade?'<button class="primary" data-action="upgrade">保存我的世界</button>':'<p class="notice">Google 保存能力尚未開啟，沒有可用的驗證入口。</p>'}${s.session.capabilities.googleLogin?'<button class="text-button" data-action="old-world">登入以前的世界</button>':'<p class="small">以前世界的登入服務目前不可用。</p>'}</div>`:'<p><strong>小光</strong> <span class="badge">已登入</span></p><p class="small">帳號狀態以實際 Session 為準。正式產品沿用既有帳號選單，不提供訪客模式切換。</p><button disabled>登出 · 此設計樣本未連接 Session</button>')+'<p class="small">以上是設計測試資料，不是實際登入。</p>');}
 function upgradeDialog(error=''){
  if(!s.session.capabilities.googleUpgrade){toast('Google 保存能力尚未開啟；沒有啟動驗證。');return;}
  open(sheetHead('保存我的世界')+`<p>以 Google 帳號保存現在的世界，下次可以回到相同進度。</p><div class="notice">保留原世界、草稿、目標、紀錄及未保存輸入。完成後留在第 ${s.step} 步，不重新開始。</div>${error?`<div class="notice error" role="alert">${h(error)}</div>`:''}<p class="small">此 Demo 不會開啟 Google。正式接線沿用 PR #22 upgrade、Nonce、Session 與 CSRF 輪替。</p><div class="sheet-actions"><button data-action="close">先繼續記錄</button><button class="primary" data-action="auth-demo" data-mode="upgrade">模擬 Google 驗證</button></div><hr><button class="text-button small-button" data-action="old-world">登入以前的世界</button>`);
 }
 function oldWorldDialog(error=''){
  if(!s.session.capabilities.googleLogin){toast('以前世界登入能力尚未開啟。');return;}
  open(sheetHead('要回到以前的世界嗎？')+`<p>這會切換到已綁定 Google 的另一個世界。</p><div class="notice warning"><strong>目前的訪客內容不會帶入或自動合併。</strong><br>只有驗證成功、確認以前世界存在且完成安全交換後，才會放棄原訪客世界並開始清除程序。至少 14 天後才符合永久清除條件；目前不承諾可恢復。</div><label class="checkline"><input id="discard-consent" type="checkbox"><span>我了解資料不會合併，同意成功切換後放棄目前訪客世界。</span></label>${error?`<div class="notice error" role="alert">${h(error)}</div>`:''}<p class="small">使用 PR #22 login，不建立新帳號；此 Demo 沒有真交換或清除排程。</p><div class="sheet-actions"><button data-action="close">保留目前世界</button><button class="primary" data-action="auth-demo" data-mode="login">模擬登入以前的世界</button></div>`);
 }
 function deliverUpgradeFixture(){ // 只替換帳號與人物區；測試必須確認 Owner、路由、DOM 與編輯值不變。
  s.session=sessionFixture('registered',s.session.ownerId);s.identity=s.session.status;
  s.accountMessage='世界已升級（設計示意），原 Owner 與輸入保留。';if(s.step===3)s.related=true;renderAccount();
  const region=$('#people-region');if(region)region.innerHTML=peopleRegion();
  if(s.step===1){const fragment=document.createElement('div');fragment.innerHTML=step1();$('#main .input-tabs').innerHTML=fragment.querySelector('.input-tabs').innerHTML;$('#ai-region').innerHTML=fragment.querySelector('#ai-region').innerHTML;} // 保留原文 textarea 與素材容器，只解鎖能力區。
  if(!$('#account-feedback'))$('#main').insertAdjacentHTML('afterbegin','<div id="account-feedback" class="notice success" role="status"></div>');
  $('#account-feedback').textContent=s.accountMessage;
 }
 function oldWorldView(){return `<section class="card"><h1>回到以前的世界。</h1><p>目前顯示另一個 Owner 的世界（設計示意）。</p><p class="notice">剛才的訪客表單沒有帶入，也沒有合併到這個世界。</p><p class="small">訪客待清除僅是設計狀態，沒有啟動任何正式刪除或排程。</p><button data-action="fresh">在這個世界記錄經歷</button></section>`;}
 function writableChange(p,x){return x.supported&&s.people.length===1&&p.role!=='mention';} // 現有確認契約無多人定向target，不在設計中假裝已能保存。
 function status(p){return p.isNew?'待建立':p.changes.some(x=>x.accepted&&writableChange(p,x))?'有資料變更':p.changes.some(x=>x.accepted)?'已核對，暫不寫入':p.changes.length?'有候選，待核對':'僅關聯，不修改';}
 function step4(){return `<div class="eyebrow">READY WHEN YOU ARE</div><h1>確認這段經歷。</h1><p class="subtitle">只把你確認的內容，放進自己的世界。</p><section class="card">${summaryControls()}<details><summary>查看原始文字與來源${s.photo||s.audio?' · 含素材':''}</summary><div class="source-quote">${h(s.raw)}</div><p class="small">${s.photo?'影像示意素材 · 未同步。 ':''}${s.audio?'語音示意素材 · 未同步。 ':''}原文不會被摘要覆寫。</p></details><div class="review-block"><div class="row"><h3>目標與進度</h3><button class="text-button inline-link" data-action="edit" data-step="2">修改</button></div><p>${s.goal?'養成持續學習的習慣':'本次不關聯目標'}</p>${s.goal?`<p class="small">${s.qty.map((q,i)=>q&&Number(q)>0?['專注練習 '+q+' 小時','閱讀筆記 '+q+' 篇','分享交流 '+q+' 次'][i]:'').filter(Boolean).join(' · ')||'沒有新增活動量'}</p>`:''}</div><div class="review-block"><div class="row"><h3>人物關聯</h3><button class="text-button inline-link" data-action="edit" data-step="3">修改</button></div>${s.related&&s.people.length?s.people.map(p=>`<button class="person-preview" data-action="preview" data-key="${h(p.key)}" aria-label="查看${h(p.name)}本次變更"><span class="person-avatar">${h([...p.name][0])}</span><span><strong>${h(p.name)}</strong> <span class="badge ${p.isNew?'pending':'outline'}">${status(p)}</span><span class="status">${h(roleNames[p.role]||'尚未選擇角色')}</span></span><span class="arrow">›</span></button>`).join(''):'<p class="small">沒有相關人物，不建立或更新人物資料。</p>'}</div><div class="review-block"><div class="row"><h3>下一步</h3><button class="text-button inline-link" data-action="task">${s.task?'修改':'＋ 選填'}</button></div><p class="small">${h(s.task||'沒有新增後續任務')}</p></div></section><p class="footer-assurance">人物與進度只在最後確認後更新；未勾選候選不會寫入。</p>${buttons(true)}<p class="small" style="text-align:center">此 Candidate 只模擬操作，不會儲存至 Life World。</p>`;}
 function open(html){
  if(!$('#sheet').open){returnFocus=document.activeElement;returnFocusKey=returnFocus?.closest('[data-action=preview]')?.dataset.key||null;}
  const fragment=document.createElement('div');fragment.innerHTML=html;
  const header=fragment.querySelector('.sheet-head'),footers=fragment.querySelectorAll('.sheet-actions'),footer=footers[footers.length-1];
  $('#sheet-content').replaceChildren();if(header)$('#sheet-content').append(header);
  if(footer)footer.remove();const body=document.createElement('div');body.className='sheet-body';body.tabIndex=0;body.setAttribute('aria-label','對話框內容');body.append(...fragment.childNodes);$('#sheet-content').append(body);
  if(footer){footer.classList.add('sheet-footer');$('#sheet-content').append(footer);}
  if(!$('#sheet').open)$('#sheet').showModal();body.scrollTop=0;$('#sheet-content h2')?.focus();
 }
 function sheetHead(title){return `<div class="sheet-head"><h2 id="sheet-title" tabindex="-1">${title}</h2><button data-action="close" aria-label="關閉預覽">×</button></div>`;}
 function close(restore=true){if($('#sheet')?.open){sequence++;$('#sheet').close();}if(restore){if(returnFocus?.isConnected)returnFocus.focus();else if(returnFocusKey&&document.querySelector('[data-action=preview][data-key="'+CSS.escape(returnFocusKey)+'"]'))document.querySelector('[data-action=preview][data-key="'+CSS.escape(returnFocusKey)+'"]').focus();else $('#main h1')?.focus();}}
 function pick(filter=''){open(sheetHead('選擇既有人物')+`<div class="field"><label for="person-search">搜尋稱呼</label><input id="person-search" type="search" placeholder="輸入人物稱呼" value="${h(filter)}"></div><div id="picker-results">${pickRows(filter)}</div><p class="small space-top">同名人物以你保存的脈絡區分，不會自動合併。</p>`);}
 function pickRows(filter){const items=people.filter(p=>p.name.includes(filter));return items.length?items.map(p=>`<button class="picker-item" data-action="select-person" data-id="${p.id}" ${s.people.some(x=>x.id===p.id)?'disabled':''}><span class="person-avatar">${h(p.name[0])}</span><span><strong>${h(p.name)}</strong><small>${h(p.hint)}${s.people.some(x=>x.id===p.id)?' · 已加入':''}</small></span></button>`).join(''):'<div class="empty">找不到這個稱呼。可以清除搜尋，或回上一頁新增人物。</div>';}
 function newPerson(key=null){const current=s.people.find(p=>p.key===key);open(sheetHead(current?'修改待建立的稱呼':'記下一個新名字')+`<p class="small">先填稱呼就好。尚未建立人物，其他資料之後再補。</p><div class="field"><label for="new-name">稱呼／姓名</label><input id="new-name" value="${h(current?.name||'')}" maxlength="100" placeholder="你怎麼稱呼這個人？" autocomplete="off"></div><div id="duplicate-warning"></div><p id="person-error" class="small" role="alert"></p><div class="sheet-actions"><button data-action="close">取消</button><button class="primary" data-action="add-person" data-key="${h(key||'')}">${current?'保留修改':'加入本次經歷'}</button></div>`);$('#new-name').dispatchEvent(new Event('input',{bubbles:true}));}
 function factCard(p,x,willSave){
  const valid=s.raw.includes(x.quote);
  return `<section class="change-card ${willSave?'':'unselected'}" data-change-card="${h(x.id)}"><div class="row"><strong>${h(x.label)}</strong><span class="badge outline">${h(x.origin)}</span></div><div class="diff">${x.old?`<span class="previous-value">原有：${h(x.old)}</span><span>＋</span>`:''}<span class="candidate-value">${willSave?'確認後新增：':'未採用候選：'}${h(x.value)}</span></div>${x.needsReview?'<p class="source-stale">來源已修改，需要重新核對此項。</p>':''}${valid?`<label class="checkline"><input type="checkbox" data-change="${h(x.id)}" data-key="${h(p.key)}" ${x.accepted?'checked':''}><span>${willSave?'已核對，納入確認後保存':writableChange(p,x)?'核對後，將此項納入保存':'保留本項核對（目前不寫入）'}<small>只作用於${h(p.name)}。關閉預覽不會取消勾選。</small></span></label>`:'<p class="source-stale">這段引用已不在目前原文中，不可直接採用。</p>'}<div class="row wrap"><button class="text-button inline-link" data-action="source" data-key="${h(p.key)}" data-change-id="${h(x.id)}">查看來源 ↗</button><button class="text-button inline-link" data-action="edit-change" data-key="${h(p.key)}" data-change-id="${h(x.id)}">修改候選</button><button class="text-button inline-link" data-action="reject-change" data-key="${h(p.key)}" data-change-id="${h(x.id)}">不採用</button></div></section>`;
 }
 function preview(key){const p=s.people.find(x=>x.key===key);if(!p)return;if(!$('#sheet').open)returnFocusKey=key;
  const ready=x=>writableChange(p,x)&&x.accepted&&!x.needsReview&&s.raw.includes(x.quote),saved=p.changes.filter(ready),pending=p.changes.filter(x=>x.supported&&!ready(x)),unsupported=p.changes.filter(x=>!x.supported);
  open(sheetHead(h(p.name)+' · 本次變更')+`<div class="row"><span class="badge ${p.isNew?'pending':'outline'}">${p.isNew?'待建立人物':'既有人物'}</span><span class="small">${h(roleNames[p.role]||'待核對')}</span></div><section id="will-save" class="preview-section"><h3>確認後會保存</h3>${p.isNew?`<div class="save-item"><strong>建立稱呼：${h(p.name)}</strong><p class="small">來源：使用者本次輸入</p></div>`:''}<div class="save-item"><strong>本次經歷關聯</strong><p>${h(roleNames[p.role]||'尚未選擇')}</p><p class="small">${p.role==='mention'?'只保存原文提及，不計參與或見面。':'只保存你選定的角色，不推定見面。'}</p></div>${saved.map(x=>factCard(p,x,true)).join('')}${!p.isNew&&!saved.length?'<p class="small">本次只有經歷關聯，不修改人物資料。</p>':''}</section>${pending.length||unsupported.length?`<section id="not-saving" class="preview-section"><h3>原文提到，但目前不寫入人物檔案</h3>${pending.some(x=>!writableChange(p,x))?'<p class="notice warning">本次的多人定向／提及人物資料保存尚未接通。可以分人保留核對，但這些項目目前不會寫入人物檔案。</p>':''}${pending.map(x=>factCard(p,x,false)).join('')}${unsupported.length?`<div class="notice warning">工作／職稱、公司目前沒有正式保存契約。以下只保留在原文，不是將新增或將更新的欄位。</div><div class="unsupported-list">${unsupported.map(x=>`<div><strong>${h(x.label)}</strong><span>${h(x.value)}</span><button class="text-button inline-link" data-action="source" data-key="${h(p.key)}" data-change-id="${h(x.id)}">查看來源 ↗</button></div>`).join('')}</div>`:''}</section>`:''}<p class="small">預覽不會寫入。只有最後確認，才提交上方「確認後會保存」的內容。</p><div class="sheet-actions"><button data-action="preview-edit" data-key="${h(key)}">返回修改關聯</button><button class="primary" data-action="close">完成檢視</button></div>`);
 }
 function showSource(key,id){const p=s.people.find(x=>x.key===key),x=p?.changes.find(x=>x.id===id);if(!x)return;open(sheetHead('這項資訊從哪裡來？')+`<p><strong>${h(p.name)} · ${h(x.label)}</strong></p><div class="source-meta"><span>本次經歷原文</span><span>${h(x.origin)}</span><span>待人工核對</span></div>${s.raw.includes(x.quote)?`<div class="source-quote">${quote(s.raw,x.quote)}</div>`:`<div class="notice warning">先前引用已不在目前原文中；這項候選尚未重新核對。</div><p class="small">先前引用（已失效）</p><div class="source-quote">${h(x.quote)}</div><p class="small">目前原文</p><div class="source-quote">${h(s.raw)}</div>`}<p class="small space-top">來源只屬於${h(p.name)}。若原文不符，請不採用候選或返回修改；不推測未記錄的真人資訊。</p><div class="sheet-actions"><button class="primary" data-action="preview" data-key="${h(key)}">返回人物預覽</button></div>`);}
 function quote(text,part){const i=text.indexOf(part);return i<0?h(text):h(text.slice(0,i))+'<mark>'+h(part)+'</mark>'+h(text.slice(i+part.length));}
 function mentionSource(key){const p=s.people.find(x=>x.key===key),has=s.raw.includes(p.name);open(sheetHead('核對原文提及')+`<div class="source-quote">${quote(s.raw,p.name)}</div>${has?'<p class="small space-top">只確認原文提到了這個人，不代表他實際參與或有直接互動。</p>':'<div class="notice error">原文沒有這個稱呼。請返回第一步補正原文，或移除此人物關聯。</div>'}<div class="sheet-actions"><button data-action="close">返回</button>${has?`<button class="primary" data-action="accept-mention" data-key="${h(key)}">確認只是提及</button>`:''}</div>`);}
 function draftView(){return `<div class="eyebrow">KEEP IT FOR LATER</div><div class="section-head"><h1>還沒寫完的片刻。</h1><button class="text-button" data-action="fresh">＋ 記錄經歷</button></div><p class="subtitle">草稿不計進度，也不發獎勵。隨時回來接著寫。</p>${s.deleted?'<div class="notice success" role="status">草稿已從示意清單移除。正式產品需 API 成功才顯示刪除完成。</div>':''}<section class="card">${s.drafts.length?s.drafts.map(d=>`<article class="draft-row"><div class="row"><div><h3>${h(d.title)}</h3><p>${h(d.updated)} · 草稿</p></div></div><div class="tools space-top"><button class="small-button" data-action="resume" data-id="${d.id}">繼續編輯</button><button class="text-button small-button delete-text" data-action="delete-draft" data-id="${d.id}">刪除草稿</button></div></article>`).join(''):'<div class="empty"><span class="empty-symbol">▤</span><h3>沒有尚未完成的草稿</h3><p>想記下一段生活時，從文字開始就好。</p><button class="space-top" data-action="fresh">記錄一段經歷</button></div>'}</section><p class="small">已確認的正式經歷不在這份清單中，不能由此刪除。</p>`;}
 function deleteDialog(id,error=''){const d=s.drafts.find(x=>x.id===id);if(!d)return;
  open(sheetHead(error==='reloaded'?'已載入較新的草稿':error?'草稿尚未刪除':'確定刪除這份草稿？')+`<p><strong>${h(d.title)}</strong></p><p class="small">這會刪除已保存的這份草稿，不是只捨棄未保存修改。已確認的經歷、其他草稿與獎勵不受影響。</p><p class="small">此草稿的本機素材引用將解除；若素材仍被其他紀錄使用，必須保留。素材本身是否移除需另外選擇。</p><div class="notice warning">正式伺服器草稿刪除 API 尚未實作。此處只示範確認、失敗與重試，不會刪除任何真實資料。</div>${error?`<div class="notice ${error==='reloaded'?'success':'error'}" role="alert">${error==='reloaded'?'已重新載入示意新版本，請再次確認內容；尚未刪除。':error==='conflict'?'這份草稿已有較新的內容。未刪除，請重新載入再確認。':'連線中斷，未確認刪除成功。草稿仍在清單中，可以重試。'}</div>`:''}<div id="delete-progress" role="status"></div><div class="sheet-actions"><button data-action="close">保留草稿</button><button class="danger" data-action="${error==='conflict'?'reload-draft':'delete-now'}" data-id="${id}">${error==='conflict'?'重新載入草稿':error?'重試刪除（示意）':'刪除這份草稿（示意）'}</button></div>`);
 }
 function leave(){open(sheetHead('先留住這段內容？')+'<p class="small">「保存草稿」會保留目前內容；「捨棄未保存修改」不會刪除已存的伺服器草稿。</p><div class="field"><button class="primary" data-action="save-draft">保存草稿並離開（示意）</button><button data-action="discard">捨棄未保存修改</button><button class="text-button" data-action="close">繼續編輯</button></div>');}
 function successView(){return `<section class="card success-panel"><img src="assets/lumi-idle.png" alt="Lumi"><h2>這一刻，已在示意世界收藏。</h2><p>正式產品須先收到確認交易的成功收據，<br>才更新經歷、人物、活動量與 Lumi 回饋。</p><div class="notice">這只是設計樣本，沒有建立人物、寫入資料或發放獎勵。</div><button class="primary space-top" data-action="fresh">再記下一段</button><button class="text-button" data-action="drafts">查看草稿</button></section>`;}
 function toast(message){clearTimeout(toastTimer);$('#toast').textContent=message;$('#toast').classList.add('visible');toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),2200);}
 function validate(){if(s.step===1&&!s.raw.trim())return '請先輸入文字，或校對素材辨識後的文字；素材本身不能當成已確認的經歷。';if(s.step===2&&s.goal&&s.qty.some(q=>q!==''&&(!Number.isFinite(Number(q))||Number(q)<0)))return '活動數量請填有效的非負數字。';if(s.step===3&&s.related){if(!s.people.length)return '請加入人物，或選擇不關聯人物。';if(s.people.some(p=>!p.role))return '請為每位人物選擇本次關聯，系統不會自行推定。';if(s.people.some(p=>p.role==='mention'&&!p.mentionReviewed))return '請先核對只提及人物的原文片段。';}if(s.step===4&&s.people.some(p=>p.changes.some(x=>x.accepted&&(!x.supported||!s.raw.includes(x.quote)))))return '人物候選的來源已變更，請重新核對後再確認。';if(s.step===4&&s.summaryNeedsReview)return '來源已修改，需要重新核對摘要後才能確認。';if(s.step===4&&!s.summary.trim())return '請填寫你確認的經歷摘要。';return '';}
 async function action(target){const a=target.dataset.action,key=target.dataset.key;
  if(a==='approve-ai'){s.aiGrant=grantFixture();close();requestAiDemo();return;}
  if(a==='cancel-ai'){s.aiMode='manual';s.aiState='idle';close();syncAiPresentation();return;}
  if(a==='retry-ai'||a==='run-ai'){chooseAi();return;}
  if(a==='manual-mode'){s.aiMode='manual';s.aiGeneration++;s.aiState='idle';syncAiPresentation();return;}
  if(a==='review-summary'){s.summaryNeedsReview=false;s.summarySourceRaw=s.raw;s.aiReviewedAfterSourceChange=s.aiCandidateStale;syncAiPresentation();return;}
  if(a==='use-current-raw'){s.summaryBeforeReplace=s.summary;s.summary=s.raw;s.summaryEdited=false;s.summaryNeedsReview=false;s.summarySourceRaw=s.raw;s.aiCandidate=false;s.aiCandidateStale=false;syncAiPresentation();return;}
  if(a==='restore-summary'){s.summary=s.summaryBeforeReplace;s.summaryBeforeReplace='';s.summaryEdited=true;s.summaryNeedsReview=true;syncAiPresentation();return;}
  if(a==='adopt-ai'){if(s.aiSuggestionRaw!==s.raw){toast('候選依據的原文已修改，請重新整理或手動核對。');return;}s.summaryBeforeReplace=s.summary;s.summary=s.aiSuggestion;s.aiSuggestion='';s.summaryEdited=false;s.summaryNeedsReview=false;s.summarySourceRaw=s.raw;s.aiCandidate=true;s.aiCandidateStale=false;syncAiPresentation();return;}
  if(a==='account-menu')accountMenu();
  if(a==='upgrade')upgradeDialog();if(a==='old-world')oldWorldDialog();
  if(a==='auth-demo'){
   const mode=target.dataset.mode;
   if(mode==='login'&&!$('#discard-consent')?.checked){oldWorldDialog('請先確認放棄告知；尚未開始驗證，也沒有標記清除。');return;}
   target.disabled=true;target.textContent='正在驗證（示意）…';const ticket=sequence;await new Promise(r=>setTimeout(r,650));if(ticket!==sequence)return;
   if(s.authOutcome==='cancel'){close();s.accountMessage='驗證已取消（示意），原訪客身分與輸入都保留。';toast(s.accountMessage);return;}
   if(s.authOutcome==='failure'||(mode==='upgrade'&&s.authOutcome==='conflict')||(mode==='login'&&s.authOutcome==='no-world')){const message=s.authOutcome==='conflict'?'此 Google 已綁定另一個世界。沒有合併或覆寫，原訪客世界仍保留。':s.authOutcome==='no-world'?'找不到以前的 Google 世界。沒有建立新帳號，也未放棄訪客資料。':'驗證失敗，仍是原訪客世界。輸入都保留，可以重試。';if(mode==='upgrade')upgradeDialog(message);else oldWorldDialog(message);return;}
   close();if(mode==='upgrade'){deliverUpgradeFixture();return;}
   s.aiGrant=null;s.aiGeneration++;s.session=sessionFixture('registered','existing-world-two');s.identity='registered';s.raw='';s.summary='';s.people=[];s.goal=false;s.qty=['','',''];s.photo=s.audio=false;s.view='old-world';s.dirty=false;render();return;
  }
  if(a==='next'){s.error=validate();if(s.error){render();return;}s.step++;if(s.step===4&&!s.summary){s.summary=s.raw;s.summarySourceRaw=s.raw;s.summaryEdited=false;}s.dirty=true;render();window.scrollTo(0,0);$('#main h1')?.focus();}
  if(a==='back'){s.step=Math.max(1,s.step-1);s.error='';render();window.scrollTo(0,0);$('#main h1')?.focus();}
  if(a==='edit'){s.step=Number(target.dataset.step);s.error='';render();window.scrollTo(0,0);$('#main h1')?.focus();}
  if(a==='tab'){s.tab=target.dataset.tab;render();}
  if(a==='sample-media'){const field=target.dataset.kind==='photo'?'photo':'audio';s[field]=!s[field];s.dirty=true;render();}
  if(a==='pick')pick();if(a==='new-person')newPerson();if(a==='rename-person')newPerson(key);
  if(a==='select-person'){if(!s.people.some(x=>x.id===target.dataset.id))s.people.push(member(target.dataset.id,''));s.related=true;close();render();}
  if(a==='add-person'){const name=$('#new-name').value.trim();if(!name){$('#person-error').textContent='請填寫稱呼，或取消新增。';return;}if(people.some(p=>p.name===name)&&!$('#distinct-person')?.checked){$('#person-error').textContent='請改選既有人物，或確認這是另一位同名人物。';return;}const current=s.people.find(p=>p.key===key);if(current)current.name=name;else s.people.push({key:'new-'+(++sequence),name,isNew:true,role:'',changes:[]});s.related=true;s.dirty=true;close();render();}
  if(a==='remove-person'){s.people=s.people.filter(p=>p.key!==key);render();}
  if(a==='mention-source')mentionSource(key);if(a==='accept-mention'){s.people.find(p=>p.key===key).mentionReviewed=true;close();render();}
  if(a==='preview')preview(key);if(a==='source')showSource(key,target.dataset.changeId);
  if(a==='edit-change'){const p=s.people.find(p=>p.key===key),x=p.changes.find(x=>x.id===target.dataset.changeId);open(sheetHead('校對這項候選')+`<p class="small">只修改${h(p.name)}本次的${h(x.label)}候選，尚未更新人物。</p><div class="field"><label for="change-value">候選內容</label><input id="change-value" maxlength="160" value="${h(x.value)}"></div><div class="source-quote">${h(x.quote)}</div><div class="sheet-actions"><button data-action="preview" data-key="${h(key)}">取消修改</button><button class="primary" data-action="apply-change" data-key="${h(key)}" data-change-id="${h(x.id)}">保留候選</button></div>`);}
  if(a==='apply-change'){const p=s.people.find(p=>p.key===key),x=p.changes.find(x=>x.id===target.dataset.changeId),v=$('#change-value').value.trim();if(!v){toast('候選內容不可空白；不採用請回預覽取消勾選。');return;}x.value=v;x.origin='使用者校對 · 示意';x.accepted=false;preview(key);render();}
  if(a==='reject-change'){s.people.find(p=>p.key===key).changes.find(x=>x.id===target.dataset.changeId).accepted=false;preview(key);render();}
  if(a==='preview-edit'){close();s.step=3;render();window.scrollTo(0,0);$('#main h1')?.focus();}
  if(a==='task'){open(sheetHead('留下一個小小的下一步')+`<div class="field"><label for="next-task">後續任務（選填）</label><input id="next-task" maxlength="300" value="${h(s.task)}" placeholder="例如：下次讀書會分享一張街景照片"></div><div class="sheet-actions"><button data-action="close">取消</button><button class="primary" data-action="apply-task">放入本次確認</button></div>`);}
  if(a==='apply-task'){s.task=$('#next-task').value.trim();close();render();}
  if(a==='close')close();if(a==='leave')leave();
  if(a==='drafts'){if(s.dirty&&s.view==='flow'){leave();return;}s.view='drafts';render();}
  if(a==='save-draft'){if(!s.raw.trim()){toast('空白內容不建立草稿。');return;}if(!s.draftId){s.draftId='draft-'+(++sequence);s.drafts.unshift({id:s.draftId,title:s.raw.slice(0,22),updated:'剛剛',revision:1});}const saved=s.drafts.find(d=>d.id===s.draftId);saved.title=s.raw.slice(0,22);saved.payload=clone({raw:s.raw,summary:s.summary,occurredAt:s.occurredAt,goal:s.goal,qty:s.qty,people:s.people,related:s.related,photo:s.photo,audio:s.audio,task:s.task,aiMode:s.aiMode,summaryEdited:s.summaryEdited,summaryNeedsReview:s.summaryNeedsReview,summarySourceRaw:s.summarySourceRaw,aiCandidate:s.aiCandidate,aiCandidateStale:s.aiCandidateStale});close();s.dirty=false;s.view='drafts';render();toast('草稿保存成功示意；沒有呼叫伺服器。');}
  if(a==='discard'){close();s.dirty=false;s.view='drafts';render();toast('只捨棄示意中的未存修改；原有草稿仍保留。');}
  if(a==='fresh'){close();const keep={drafts:s.drafts,identity:s.identity,session:clone(s.session),aiGrant:clone(s.aiGrant),authOutcome:s.authOutcome,saveOutcome:s.saveOutcome,deleteOutcome:s.deleteOutcome};s={...base(),...keep,raw:'',summary:''};$('#scenario').value='empty';syncTools();render();window.scrollTo(0,0);}
  if(a==='draft-menu'){open(sheetHead('這份草稿')+`<p class="small">${s.draftId?'已保存的示意草稿。刪除與捨棄未保存修改是不同操作。':'目前尚未保存為伺服器草稿。'}</p><div class="field"><button data-action="save-draft">保存目前內容（示意）</button>${s.draftId?`<button class="delete-text" data-action="delete-draft" data-id="${s.draftId}">刪除此草稿</button>`:''}<button class="text-button" data-action="close">繼續編輯</button></div>`);}
  if(a==='resume'){close();s.view='flow';s.draftId=target.dataset.id;const saved=s.drafts.find(d=>d.id===s.draftId);s.aiGeneration++;Object.assign(s,{raw:saved.id==='draft-two'?'傍晚獨自散步，整理生活的想法。':raw,summary:'',occurredAt:'2026-11-10T18:30',goal:false,qty:['','',''],people:[],related:false,photo:false,audio:false,task:'',aiMode:'manual',aiState:'idle',aiSuggestion:'',aiSuggestionRaw:'',aiCandidate:false,aiCandidateStale:false,summaryNeedsReview:false,summaryEdited:false,summaryBeforeReplace:'',summarySourceRaw:raw,accountMessage:'',deleted:false},clone(saved.payload||{}));s.step=1;s.error='';s.dirty=false;render();}
  if(a==='delete-draft'){s.conflictReloaded=false;deleteDialog(target.dataset.id);}
  if(a==='reload-draft'){const d=s.drafts.find(d=>d.id===target.dataset.id);d.revision++;d.updated='剛剛更新（示意新版本）';s.conflictReloaded=true;render();deleteDialog(d.id,'reloaded');}
  if(a==='delete-now'){
   if(s.deleteOutcome==='conflict'&&!s.conflictReloaded){deleteDialog(target.dataset.id,'conflict');toast('版本衝突示意：保留草稿，需重新取得最新版。');return;}
   target.disabled=true;$('#delete-progress').textContent='正在刪除示意草稿，請稍候…';const ticket=sequence;await new Promise(r=>setTimeout(r,650));if(ticket!==sequence)return;
   if(s.deleteOutcome==='failure'){deleteDialog(target.dataset.id,'failure');return;}
   s.drafts=s.drafts.filter(d=>d.id!==target.dataset.id);s.deleted=true;close();s.view='drafts';render();
  }
  if(a==='confirm'){
   s.error=validate();if(s.error){render();return;}target.disabled=true;target.textContent='正在確認（示意）…';const ticket=sequence;await new Promise(r=>setTimeout(r,650));if(ticket!==sequence)return;
   if(s.saveOutcome==='failure'){s.error='連線暫時中斷，尚未確認保存。內容與勾選項目都保留，請重試。';render();return;}s.view='success';s.dirty=false;render();
  }
  if(a==='reset')load($('#scenario').value);
 }
 document.addEventListener('click',e=>{const t=e.target.closest('[data-action]');if(!t||t.disabled)return;e.preventDefault();action(t);});
 document.addEventListener('input',e=>{
  if(e.target.dataset.bind){if(e.target.dataset.bind==='raw')updateRaw(e.target.value);else{s[e.target.dataset.bind]=e.target.value;if(e.target.dataset.bind==='summary')s.summaryEdited=true;}s.dirty=true;}
  if(e.target.dataset.qty!==undefined){s.qty[Number(e.target.dataset.qty)]=e.target.value;s.dirty=true;}
  if(e.target.id==='person-search')$('#picker-results').innerHTML=pickRows(e.target.value);
  if(e.target.id==='new-name')$('#duplicate-warning').innerHTML=people.some(p=>p.name===e.target.value.trim())?'<div class="notice warning">已有同名人物，請先確認是否為同一人。</div><label class="checkline"><input id="distinct-person" type="checkbox"><span>我確認是另一位人物，不合併。</span></label>':'';
 });
 document.addEventListener('change',e=>{
  const t=e.target;if(t.id==='scenario'){load(t.value);return;}if(t.id==='auth-outcome')s.authOutcome=t.value;

  if(t.id==='save-outcome')s.saveOutcome=t.value;if(t.id==='delete-outcome')s.deleteOutcome=t.value;
  if(t.id==='ai-outcome')s.aiOutcome=t.value;
  if(t.name==='organize-mode'){if(t.value==='ai')chooseAi();else{s.aiMode='manual';s.aiGeneration++;s.aiState='idle';syncAiPresentation();}}
  if(t.name==='goal-mode'){s.goal=t.value==='goal';render();}if(t.name==='people-mode'){s.related=t.value==='some';if(!s.related)s.people=[];render();}
  if(t.dataset.role){const p=s.people.find(p=>p.key===t.dataset.role);p.role=t.value;p.mentionReviewed=false;s.dirty=true;render();}
  if(t.dataset.change){const p=s.people.find(p=>p.key===t.dataset.key),x=p.changes.find(x=>x.id===t.dataset.change);if(x.supported&&s.raw.includes(x.quote)){x.accepted=t.checked;if(x.accepted)x.needsReview=false;}const key=p.key,id=x.id;render();preview(key);document.querySelector('[data-change="'+id+'"]')?.focus();}
 });
 function viewportChanged(){const v=window.visualViewport;document.documentElement.style.setProperty('--usable-height',(v?.height||innerHeight)+'px');document.documentElement.style.setProperty('--usable-width',(v?.width||innerWidth)+'px');document.documentElement.style.setProperty('--visual-left',(v?.offsetLeft||0)+'px');document.body.dataset.narrowViewport=String((v?.width||innerWidth)<=700);document.body.dataset.compactViewport=String((v?.width||innerWidth)<280);document.documentElement.style.setProperty('--keyboard-inset',Math.max(0,innerHeight-(v?.height||innerHeight)-(v?.offsetTop||0))+'px');}
 viewportChanged();window.visualViewport?.addEventListener('resize',viewportChanged);window.addEventListener('resize',viewportChanged);
 $('#sheet').addEventListener('cancel',e=>{e.preventDefault();close();});
 $('#scenario').innerHTML=Object.entries(scenes).map(([k,v])=>`<option value="${k}">${v}</option>`).join('');load(new URLSearchParams(location.search).get('scene')||'step1');
 return {load,getState:()=>clone(s),scenes,close};
})();
