'use strict';
window.ExperienceUI=(()=>{
  let c, flow=null;
  /** @typedef {{ownerId:string,draftId:?string,expectedRevision:?number,currentStep:number,rawText:string,occurredAt:string,goalId:?string,contributions:Array,personId:?string,pendingPerson:?Object,story:?Object,editedSummary:string,hasSummary:boolean,summarySourceRaw:?string,aiConsent:boolean,aiCandidate:?string,dirty:boolean,requestId:?string,mediaScope:?string}} ExperienceFlowState */
  function initialize(context){c=context;}
  function capture(event){ // 單一 DOM 是編輯值來源，換步不重建媒體或清空表單。
    const form=document.querySelector('#record-form,#review-form');if(!form||!flow)return;
    const f=new FormData(form),refreshPeople=!event||!['summary','tasks'].includes(event.target?.name);
    Object.assign(flow,{rawText:f.get('raw_text')??flow.rawText,occurredAt:f.get('occurred_at'),goalId:f.get('goal_id')||null,personId:f.get('person_id')||null,story:refreshPeople?window.ConnectionsUI.collectEditor(form,false):flow.story,dirty:c.state.dirty,contributions:[...f].filter(([k])=>k.startsWith('quantity-')).map(([k,v])=>({action_id:k.slice(9),quantity:v}))});
    flow.pendingPerson=flow.story?.pending_person||null;
    if(f.has('summary')){flow.editedSummary=String(f.get('summary'));flow.hasSummary=true;}
    if(f.has('tasks'))flow.tasks=String(f.get('tasks')).split('\n').map(t=>t.trim()).filter(Boolean);
    if(form.querySelector('[data-summary-source-review]')?.checked){flow.summarySourceRaw=flow.rawText;flow.summarySourceHash=c.state.draft?.raw_sha256;}
    if(event?.target?.id==='story-reviewed'&&event.target.checked)flow.personReviewSignature=reviewStorySignature(form);
    flow.aiCandidate=c.state.candidate||null;if(refreshPeople)refreshReviewSummary(); // 編輯摘要不重建人物卡或反覆掃描長原文。
  }
  function summaryState(d){
    // 同Owner同草稿才沿用未保存摘要；來源內容不同就要求明確重核對，不能套用到另一份草稿。
    const own=flow?.ownerId===c.state.me?.owner_id&&flow.draftId===d.id&&flow.hasSummary;
    const saved=d.review,sourceRaw=own?flow.summarySourceRaw:saved?.summary_needs_review?null:d.raw_text;
    return {value:own?flow.editedSummary:saved?.summary??d.raw_text,sourceRaw,sourceHash:own?flow.summarySourceHash:saved?.summary!=null?saved.summary_source_sha256:d.raw_sha256,needsReview:sourceRaw!==d.raw_text};
  }
  function tasksState(d){return flow?.ownerId===c.state.me?.owner_id&&flow.draftId===d.id&&flow.tasks?flow.tasks:d.review?.tasks||[];}
  function reviewSnapshot(){
    // 只保存本Owner本草稿的核對資料；opaque候選保持原樣，不假裝已有補充UI。
    capture();const d=c.state.draft;if(!d||flow?.ownerId!==c.state.me?.owner_id||flow.draftId!==d.id||!flow.hasSummary)return undefined;
    return {...(d.review||{}),summary:flow.editedSummary,summary_source_sha256:flow.summarySourceHash??(flow.summarySourceRaw===flow.rawText?d.raw_sha256:null),summary_needs_review:flow.summarySourceRaw!==flow.rawText,tasks:flow.tasks||[],person_candidates:d.review?.person_candidates||[]};
  }
  function summaryReview(d){
    return summaryState(d).needsReview?'<div class="callout" role="status">原始經歷已修改，這份摘要需要重新核對。你的摘要已保留，不代表它已與新原文一致。<label class="check-line"><input type="checkbox" data-summary-source-review required>我已對照新原文，重新核對目前摘要。</label></div>':'';
  }
  let previewOrigin=null,previewOwner=null;
  const roleText={interaction:'實際參與並直接互動',participant:'共同參與但未直接互動',mention:'僅在原文中提及'};
  function currentReviewPeople(form){
    // 只使用當前Owner已選的ID/client_ref，絕不依名字把多位人物合併或把資料套到第一人。
    const story=window.ConnectionsUI.collectEditor(form,false),items=new Map();
    if(!story)return [];
    const known=id=>(c.state.world?.people||[]).find(p=>p.id===id);
    function add(key,name,role,extra={}){
      if(items.has(key)){items.get(key).roles.push(role);return;}
      items.set(key,{key,name,roles:[role],...extra});
    }
    for(const p of story.participants)add('existing:'+p.person_id,known(p.person_id)?.name||'已選人物',p.interacted?'interaction':'participant',{personId:p.person_id,isNew:false});
    for(const m of story.mentions)add(m.person_id?'existing:'+m.person_id:'mention:'+m.start+':'+m.end,known(m.person_id)?.name||m.name,'mention',{personId:m.person_id,isNew:false,unmatched:!m.person_id});
    const pending=story.pending_people?.length?story.pending_people:story.pending_person?[{...story.pending_person,client_ref:'legacy'}]:[];
    for(const p of pending)add('pending:'+p.client_ref,p.name||'尚未填寫稱呼',p.relation,{isNew:true});
    return [...items.values()];
  }
  function reviewStorySignature(form){return JSON.stringify({raw:c.state.draft?.raw_text,story:window.ConnectionsUI.collectEditor(form,false)});}
  function refreshReviewSummary(){
    const form=document.querySelector('#review-form'),root=document.querySelector('#experience-review-overview');
    if(!form||!root||flow?.ownerId!==c.state.me?.owner_id||flow.currentStep!==4)return;
    const d=c.state.draft,goal=(c.state.world?.goals||[]).find(g=>g.id===d?.goal_id),people=currentReviewPeople(form);
    const quantities=[...form.querySelectorAll('[name^="quantity-"]')].filter(n=>Number(n.value)>0).map(n=>{
      const action=goal?.actions.find(a=>a.id===n.name.slice(9));return action?`${action.title} ${n.value} ${action.unit}`:'';
    }).filter(Boolean);
    root.innerHTML=`<section class="review-block"><h3>目標與進度</h3><p>${c.esc(goal?.title||'本次不關聯目標')}</p><p class="small">${c.esc(quantities.join(' · ')||'沒有新增活動量')}</p></section><section class="review-block"><h3>人物關聯</h3><div class="stack">${people.length?people.map(p=>`<button type="button" class="card experience-person-preview" data-experience-preview="${c.esc(p.key)}"><strong>${c.esc(p.name)}</strong><span class="tag">${p.isNew?'待建立':p.unmatched?'原文提及，待配對':'既有人物'}</span><span class="small">${c.esc([...new Set(p.roles)].map(r=>roleText[r]||'尚未選角色').join(' · '))}</span><span class="small muted">查看本次關聯與保存範圍 ›</span></button>`).join(''):'<p>沒有相關人物，不建立或修改人物資料。</p>'}</div></section>`;
    const acceptance=form.querySelector('#experience-review-people-acceptance');
    let reviewed=acceptance.querySelector('#story-reviewed');
    // 舊草稿還原會重建editor；保留表單外唯一核對入口，不能留下重複ID或兩份核對狀態。
    for(const input of [...form.querySelectorAll('#story-reviewed')]){
      if(!reviewed){acceptance.append(input.closest('label'));reviewed=input;}
      else if(input!==reviewed)input.closest('label').remove();
    }
    if(reviewed){
      const hasStory=!!window.ConnectionsUI.collectEditor(form,false);
      reviewed.closest('label').hidden=!hasStory;reviewed.required=hasStory;
      if(!hasStory||flow.personReviewSignature!==reviewStorySignature(form))reviewed.checked=false;
    }
  }
  function closePersonPreview(){
    const dialog=document.querySelector('#experience-person-preview');if(dialog?.open)dialog.close();
  }
  function previewPerson(key,origin){
    const form=document.querySelector('#review-form'),d=c.state.draft;
    if(!form||flow?.ownerId!==c.state.me?.owner_id||flow.draftId!==d?.id)return;
    const p=currentReviewPeople(form).find(p=>p.key===key);if(!p)return;
    const dialog=document.querySelector('#experience-person-preview');previewOrigin=origin;previewOwner=c.state.me.owner_id;
    dialog.querySelector('#experience-preview-title').textContent=p.name+' · 本次確認內容';
    const updates=p.personId&&form.elements.person_id?.value===p.personId?window.PeopleUI.reviewPayload(form).person_updates:[];
    // 本輪只預覽真正在Confirm提交的內容；沒有對應候選時不捏造公司/生日或原值差異。
    dialog.querySelector('.experience-preview-body').innerHTML=`<p class="small">尚未正式保存；完成檢視不會寫入人物或經歷。</p><h3>最後確認後會保存</h3>${p.isNew?`<p>待建立的稱呼：${c.esc(p.name)}</p><p class="small">由使用者在本次表單手動輸入；姓名相同不會自動合併。</p>`:''}<p>本次經歷關聯：${c.esc([...new Set(p.roles)].map(r=>roleText[r]||'尚未選角色').join(' · '))}</p>${p.unmatched?'<p class="small">只保留原文提及線索，不建立或配對正式人物。</p>':''}${updates.length?`<h3>已勾選的人物資訊候選</h3>${updates.map(u=>`<p>${c.esc({interests:'興趣與嗜好',food:'飲食偏好',skills:'專長與背景',habits:'互動習慣'}[u.dimension]||'人物資訊')}：${c.esc(u.value)}</p><p class="small">需最後確認，來源為本次經歷及使用者核對。</p>`).join('')}`:!p.isNew?'<p>這次只關聯人物，沒有待修改的基本資料。</p>':''}<details><summary>查看本次原始經歷來源</summary><div class="raw-source">${c.esc(d.raw_text)}</div></details><p class="small muted">這次未列出的資料不會自動寫入人物檔案；不會自行補造未提供的資訊。</p>`;
    if(!dialog.open)dialog.showModal();dialog.querySelector('#experience-preview-title').focus();
  }
  document.addEventListener('click',event=>{
    const target=event.target.closest('[data-experience-preview]');
    if(target){previewPerson(target.dataset.experiencePreview,target);return;}
    if(event.target.closest('[data-experience-preview-close]'))closePersonPreview();
  });
  document.addEventListener('DOMContentLoaded',()=>{
    document.querySelector('#experience-person-preview')?.addEventListener('close',()=>{
      if(previewOwner===c.state.me?.owner_id&&previewOrigin?.isConnected)previewOrigin.focus();
      previewOrigin=null;previewOwner=null;
    });
  });

  function show(step){
    flow.currentStep=step;
    document.querySelectorAll('[data-experience-step]').forEach(n=>{n.hidden=Number(n.dataset.experienceStep)!==step;});
    const title=document.querySelector('#experience-step-title');title.textContent=['記錄經歷','目標活動數量','人物關聯'][step-1];title.focus();
    document.querySelector('#experience-progress').textContent=`${step} / 4 · 記錄經歷 → 目標活動數量 → 人物關聯 → 檢視並確認`;
    document.querySelector('[data-experience-prev]').hidden=step===1;
    document.querySelector('[data-experience-next]').hidden=step===3;
    document.querySelector('[data-experience-review]').hidden=step!==3;
  }
  function mount(){
    closePersonPreview();document.querySelector('#experience-person-preview .experience-preview-body')?.replaceChildren();
    const form=document.querySelector('#record-form');
    document.body.classList.toggle('experience-focus',!!(form||document.querySelector('#review-form'))); // 四步手機專注模式，流程外恢復原導覽。
    if(!form){
      const review=document.querySelector('#review-form'),d=c.state.draft;
      if(review&&d){const acceptance=review.querySelector('#story-reviewed')?.closest('label');if(acceptance)review.querySelector('#experience-review-people-acceptance').append(acceptance);review.insertAdjacentHTML('afterbegin','<button type="button" class="text-button" data-action="leave-experience">離開記錄</button>');const prior=summaryState(d),personReviewSignature=flow?.ownerId===c.state.me.owner_id&&flow.draftId===d.id?flow.personReviewSignature:null;flow={ownerId:c.state.me.owner_id,draftId:d.id,expectedRevision:d.revision,currentStep:4,rawText:d.raw_text,occurredAt:d.occurred_at,goalId:d.goal_id,contributions:d.contributions,personId:d.person_id,pendingPerson:d.story?.pending_person||null,story:d.story,editedSummary:review.elements.summary.value,hasSummary:true,summarySourceRaw:prior.sourceRaw,summarySourceHash:prior.sourceHash,tasks:tasksState(d),personReviewSignature,aiConsent:false,aiCandidate:c.state.candidate||null,dirty:c.state.dirty,requestId:null,mediaScope:'draft:'+d.id};review.addEventListener('input',capture);review.addEventListener('change',capture);refreshReviewSummary();}
      else flow=null;
      c.state.experienceFlow=flow;return;
    }
    // 從第四步選擇修改原文應回第一步；同一份record表單的局部恢復才保留原步。
    const carry=flow?.ownerId===c.state.me.owner_id&&flow.draftId===c.state.draft?.id?flow:null;
    const previousStep=flow?.ownerId===c.state.me.owner_id&&flow.currentStep<=3?flow.currentStep:1;
    flow={ownerId:c.state.me.owner_id,draftId:c.state.editingDraft?c.state.draft?.id:null,expectedRevision:c.state.draft?.revision,currentStep:1,rawText:'',occurredAt:'',goalId:null,contributions:[],personId:null,pendingPerson:null,story:null,editedSummary:carry?.editedSummary??'',hasSummary:carry?.hasSummary||false,summarySourceRaw:carry?.summarySourceRaw??null,summarySourceHash:carry?.summarySourceHash??null,tasks:carry?.tasks,personReviewSignature:carry?.personReviewSignature??null,aiConsent:false,aiCandidate:null,dirty:false,requestId:null,mediaScope:null};
    const sections=[1,2,3].map(n=>{const x=document.createElement('section');x.dataset.experienceStep=n;return x;});
    const nodes=[...form.children], goal=form.querySelector('#goal-id')?.closest('.field'),person=form.querySelector('#person-id');
    for(const node of nodes){
      if(node.classList.contains('step-label')){node.remove();continue;}
      if(node===goal||node.id==='contribution-fields')sections[1].append(node);
      else if(node===person||node.matches('[data-story-editor]')||node.classList.contains('callout')||node.querySelector?.('[data-action=choose-experience-person]')||node.tagName==='P'&&node.textContent.startsWith('這次有和誰'))sections[2].append(node);
      else if(!node.classList.contains('button-row'))sections[0].append(node);
      else node.remove();
    }
    if(c.state.me.status==='guest'){sections[2].dataset.guestLocked='true';sections[2].innerHTML='<p>本次不關聯人物。訪客可繼續確認文字與目標活動量，不會呼叫 AI。</p>';}
    form.dataset.experienceFlow='true';form.append(...sections);
    form.insertAdjacentHTML('afterbegin','<button type="button" class="text-button" data-action="leave-experience">離開記錄</button><p id="experience-progress" class="small muted" role="status"></p><h2 id="experience-step-title" tabindex="-1"></h2>');
    form.insertAdjacentHTML('beforeend','<div class="button-row space-top"><button type="button" class="secondary" data-experience-prev>上一步</button><button type="button" class="primary" data-experience-next>下一步</button><button class="primary" name="intent" value="review" data-experience-review>檢視並確認 →</button><button class="text-button" name="intent" value="save">保存草稿並離開</button></div>');
    form.addEventListener('input',capture);form.addEventListener('change',capture);
    form.querySelector('[data-experience-prev]').onclick=()=>{capture();show(Math.max(1,flow.currentStep-1));};
    form.querySelector('[data-experience-next]').onclick=()=>{
      const section=sections[flow.currentStep-1];
      for(const field of section.querySelectorAll('input,textarea,select'))if(!field.reportValidity())return;
      if(flow.currentStep===1&&!form.elements.raw_text.value.trim()){c.toast('請先輸入或校對經歷文字。');return;}
      capture();show(Math.min(3,flow.currentStep+1));
    };
    c.state.experienceFlow=flow;show(previousStep);capture();
  }
  function refreshCapabilities(){
    // 同Owner升級只替換已鎖住的人物區；保留表單、原文、媒體、步驟與未選人物的狀態。
    if(!flow||flow.ownerId!==c.state.me?.owner_id||c.state.me.status!=='registered')return;
    const section=document.querySelector('[data-experience-step="3"][data-guest-locked="true"]');
    if(!section)return;
    section.innerHTML=c.personControls(flow.story);
    delete section.dataset.guestLocked;
    window.ConnectionsUI.hydrateEditors();
  }
  return {initialize,mount,capture,refreshCapabilities,summaryState,summaryReview,tasksState,reviewSnapshot,refreshReviewSummary,getState:()=>flow};
})();
