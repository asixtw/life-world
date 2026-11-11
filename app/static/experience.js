'use strict';
window.ExperienceUI=(()=>{
  let c, flow=null;
  /** @typedef {{ownerId:string,draftId:?string,expectedRevision:?number,currentStep:number,rawText:string,occurredAt:string,goalId:?string,contributions:Array,personId:?string,pendingPerson:?Object,story:?Object,editedSummary:string,aiConsent:boolean,aiCandidate:?string,dirty:boolean,requestId:?string,mediaScope:?string}} ExperienceFlowState */
  function initialize(context){c=context;}
  function capture(){ // 單一 DOM 是編輯值來源，換步不重建媒體或清空表單。
    const form=document.querySelector('#record-form,#review-form');if(!form||!flow)return;
    const f=new FormData(form);
    Object.assign(flow,{rawText:f.get('raw_text')??flow.rawText,occurredAt:f.get('occurred_at'),goalId:f.get('goal_id')||null,personId:f.get('person_id')||null,story:window.ConnectionsUI.collectEditor(form,false),dirty:c.state.dirty,contributions:[...f].filter(([k])=>k.startsWith('quantity-')).map(([k,v])=>({action_id:k.slice(9),quantity:v}))});
    flow.pendingPerson=flow.story?.pending_person||null;flow.editedSummary=f.get('summary')||flow.editedSummary;flow.aiCandidate=c.state.candidate||null;
  }
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
    const form=document.querySelector('#record-form');
    if(!form){
      const review=document.querySelector('#review-form'),d=c.state.draft;
      if(review&&d){flow={ownerId:c.state.me.owner_id,draftId:d.id,expectedRevision:d.revision,currentStep:4,rawText:d.raw_text,occurredAt:d.occurred_at,goalId:d.goal_id,contributions:d.contributions,personId:d.person_id,pendingPerson:d.story?.pending_person||null,story:d.story,editedSummary:review.elements.summary.value,aiConsent:false,aiCandidate:c.state.candidate||null,dirty:c.state.dirty,requestId:null,mediaScope:'draft:'+d.id};review.addEventListener('input',capture);review.addEventListener('change',capture);}
      else flow=null;
      c.state.experienceFlow=flow;return;
    }
    const previousStep=flow?.ownerId===c.state.me.owner_id?Math.min(3,flow.currentStep):1;
    flow={ownerId:c.state.me.owner_id,draftId:c.state.editingDraft?c.state.draft?.id:null,expectedRevision:c.state.draft?.revision,currentStep:1,rawText:'',occurredAt:'',goalId:null,contributions:[],personId:null,pendingPerson:null,story:null,editedSummary:'',aiConsent:false,aiCandidate:null,dirty:false,requestId:null,mediaScope:null};
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
    form.insertAdjacentHTML('afterbegin','<p id="experience-progress" class="small muted" role="status"></p><h2 id="experience-step-title" tabindex="-1"></h2>');
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
  return {initialize,mount,capture,refreshCapabilities,getState:()=>flow};
})();
