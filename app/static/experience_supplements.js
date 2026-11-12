'use strict';
/** 第三步逐人選填補充；只產生草稿候選，不呼叫建人或事實寫入API。 */
window.PersonSupplementsUI=(()=>{
  let c;
  const dims={interests:'興趣與嗜好',food:'飲食偏好',skills:'專長與背景',habits:'互動習慣',birthday:'生日（月日，年份選填）',employment:'公司／組織與職稱'};
  const evidence={stated_by_person:'人物本人告知',observed_by_user:'我觀察到',documented_source:'文件記載'};
  const esc=x=>c.esc(x);
  function initialize(context){c=context;}
  function current(){const f=c.getFlow();return f&&c.state.me?.status==='registered'&&f.ownerId===c.state.me.owner_id?f:null;}
  function keyOf(x){return x.target.person_id?'existing:'+x.target.person_id:'pending:'+x.target.client_ref;}
  function field(key,label,input){return `<label class="field">${label}${input}</label>`;}
  function options(values,value){return '<option value="">請選擇</option>'+Object.entries(values).map(([k,v])=>`<option value="${k}" ${value===k?'selected':''}>${esc(v)}</option>`).join('');}
  function renderCard(person,values){
    return `<details class="card space-top" data-supplement-person="${esc(person.key)}" data-active-dimension="${esc(values.dimension||'')}"><summary>${esc(person.name)} · ＋ 補充這次了解的人物資訊（選填）</summary><div class="space-top">${field('dimension','資訊類別',`<select data-supplement-input="dimension">${options(dims,values.dimension)}</select>`)}${field('value','這次了解的資訊',`<input data-supplement-input="value" maxlength="160" value="${esc(values.value||'')}">`)}${BasicCandidatesUI.inputs(values)}<details data-supplement-source><summary>來源與得知依據</summary>${field('evidence','這項資訊從何得知？',`<select data-supplement-input="evidence_type">${options(evidence,values.evidence_type)}</select>`)}${field('source','輸入來源',`<select data-supplement-input="source_kind"><option value="" ${!values.source_kind?'selected':''}>請選擇輸入來源</option><option value="manual" ${values.source_kind==='manual'?'selected':''}>我手動提供</option><option value="raw" ${values.source_kind==='raw'?'selected':''}>本次原文片段</option></select>`)}<details><summary>原文片段與補充說明</summary>${field('quote','原文片段（選擇原文來源時填寫）',`<textarea data-supplement-input="quote" maxlength="2000">${esc(values.quote||'')}</textarea>`)}${field('description','補充說明（選填）',`<textarea data-supplement-input="description" maxlength="2000">${esc(values.description||'')}</textarea>`)}</details></details><p class="small" data-supplement-input-status role="status" aria-live="polite"></p><p data-supplement-status role="status" aria-live="polite"></p><p class="small muted">公司／職稱與生日依正式結構化資料保存，不存入其他欄位。核對這份資料不代表向人物本人獨立查證。</p><div class="button-row"><button type="button" class="secondary" data-supplement-add>加入資訊</button><button type="button" class="text-button" data-supplement-reset>清空這次輸入</button></div><div data-supplement-candidates class="space-top"></div></div></details>`;
  }
  function all(f){return [...(f.personCandidates||[]),...BasicCandidatesUI.entries(f).map(({x})=>x)];}
  function hasInput(v){return !!(v.value?.trim()||v.description?.trim()||v.quote?.trim()||['birth_year','birth_month','birth_day','company_name','job_title','valid_from','valid_to'].some(k=>v[k]));}
  function inputStatus(row,person,v){
    row.querySelector('[data-supplement-input-status]').textContent=hasInput(v)?'「'+person.name+'」·'+(dims[v.dimension]||'尚未選資訊類別')+'：尚未加入資訊。請加入資訊或明確清空。':'';
  }
  function captureInputs(form){
    const f=current();if(!f)return;
    f.supplementInputs||={};
    for(const row of form.querySelectorAll('[data-supplement-person]'))f.supplementInputs[row.dataset.supplementPerson]=Object.fromEntries([...row.querySelectorAll('[data-supplement-input]')].map(n=>[n.dataset.supplementInput,n.value]));
  }
  function refresh(form=document.querySelector('#record-form')){
    const f=current(),step=form?.querySelector('[data-experience-step="3"]');if(!f||!step)return;
    captureInputs(form);f.personCandidates||=[];f.supplementInputs||={};
    let root=step.querySelector('[data-person-supplements]');
    if(!root){root=document.createElement('section');root.dataset.personSupplements='true';root.innerHTML='<input type="hidden" id="experience-person-supplements" name="experience_person_supplements"><h3>這次有多了解他們嗎？（選填）</h3><div data-supplement-cards></div><div data-supplement-orphans></div>';step.append(root);}
    const people=c.people(form).filter(p=>p.personId||p.key.startsWith('pending:')),cards=root.querySelector('[data-supplement-cards]'),keys=new Set(people.map(p=>p.key));
    for(const row of [...cards.querySelectorAll('[data-supplement-person]')])if(!keys.has(row.dataset.supplementPerson))row.remove();
    for(const p of people){
      let row=[...cards.children].find(n=>n.dataset.supplementPerson===p.key);
      if(!row){cards.insertAdjacentHTML('beforeend',renderCard(p,f.supplementInputs[p.key]||{}));row=cards.lastElementChild;BasicCandidatesUI.configure(row);}
      inputStatus(row,p,f.supplementInputs[p.key]||{});
      const own=all(f).filter(x=>keyOf(x)===p.key);
      row.querySelector('summary').textContent=p.name+' · ＋ 補充這次了解的人物資訊（選填）'+(own.length?' · '+'已加入 '+own.length+' 項資訊':'');
      row.querySelector('[data-supplement-candidates]').innerHTML=own.map(x=>`<p class="small">已加入資訊：${esc(dims[x.dimension]||'人物資訊')} · ${esc(typeof x.value==='string'?x.value:BasicCandidatesUI.text(Object.hasOwn(x.value,'birth_month')?'birthday':'employment',x))} <button type="button" class="text-button" data-supplement-remove="${esc(x.candidate_ref)}">移除此資訊</button></p>`).join('');
    }
    const orphans=[...new Set([...all(f).map(keyOf),...Object.keys(f.supplementInputs).filter(k=>hasInput(f.supplementInputs[k]))].filter(k=>!keys.has(k)))];
    root.querySelector('[data-supplement-orphans]').innerHTML=orphans.map(key=>`<div class="callout"><p>有補充資訊的人物已不在本次關聯，輸入仍保留。請重新關聯或明確移除補充後再保存。</p><button type="button" class="text-button" data-supplement-clear="${esc(key)}">移除此人物的補充資訊</button></div>`).join('');
    root.hidden=!people.length&&!orphans.length;
  }
  async function add(row){
    const f=current(),form=row.closest('form');if(!f)return;
    captureInputs(form);const key=row.dataset.supplementPerson,person=c.people(form).find(p=>p.key===key),v=f.supplementInputs[key];
    const basic=['birthday','employment'].includes(v.dimension);
    if(!person||!v.dimension||!basic&&!v.value?.trim())throw new Error('請選資訊類別並填寫內容，或保留不補充。');
    // 換類別不刪舊輸入；加入資訊前必須處理其他類別尚未保存的內容。
    const birthInput=['birth_year','birth_month','birth_day'].some(k=>v[k]),jobInput=['company_name','job_title','valid_from','valid_to'].some(k=>v[k]);
    if(basic&&(v.value?.trim()||v.description?.trim())||v.dimension==='birthday'&&jobInput||v.dimension==='employment'&&birthInput||!basic&&(birthInput||jobInput))throw new Error('其他資訊類別還有未保存輸入；請切回加入資訊，或明確清空後再繼續，不會默默捨棄。');
    if(!['manual','raw'].includes(v.source_kind))throw new Error('請選擇資訊輸入來源，不會自動推定來源或證據。');
    if(all(f).length>=100)throw new Error('每份草稿最多100項補充資訊；現有輸入保留。');
    if(f.personCandidates.some(x=>keyOf(x)===key&&x.dimension===v.dimension&&x.value===v.value.trim()))throw new Error('已加入相同人物、類別與內容的資訊，請於第四步核對。');
    const raw=form.elements.raw_text.value;
    if(v.source_kind==='raw'&&(!v.quote?.trim()||!raw.includes(v.quote)))throw new Error('請填寫目前原文中確實存在的片段，不會自動猜測來源。');
    const revision=person.personId?c.state.world.people.find(p=>p.id===person.personId)?.revision:null;
    if(basic){
      const snapshot=JSON.stringify(v),created=await BasicCandidatesUI.create(person,v,raw);
      if(current()!==f||!row.isConnected||form.elements.raw_text.value!==raw||JSON.stringify(Object.fromEntries([...row.querySelectorAll('[data-supplement-input]')].map(n=>[n.dataset.supplementInput,n.value])))!==snapshot)throw new Error('補充內容已改變，未加入舊資訊；請重新確認。');
      if(all(f).length>=100)throw new Error('每份草稿最多100項補充資訊；輸入保留。');
      if(all(f).some(x=>keyOf(x)===key&&typeof x.value==='object'&&(created.kind==='birthday'?Object.hasOwn(x.value,'birth_month'):x.employment_id&&x.employment_id===created.x.employment_id||JSON.stringify(x.value)===JSON.stringify(created.x.value))))throw new Error('已有此人物的相同基本資料資訊，請先移除或核對。');
      const list=created.kind==='birthday'?'birthdayCandidates':'employmentCandidates';f[list]||=[];f[list].push(created.x);
    }else f.personCandidates.push({candidate_ref:crypto.randomUUID(),target:person.personId?{person_id:person.personId}:{client_ref:key.slice(8)},expected_person_revision:revision||null,dimension:v.dimension,value:v.value.trim(),description:v.description||'',source_kind:v.source_kind||'manual',evidence_type:v.evidence_type||null,quote:v.source_kind==='raw'?v.quote:null,source_sha256:null,selected:false,excluded:false,needs_review:!v.evidence_type||v.source_kind==='raw'});
    f.supplementInputs[key]={};row.dataset.activeDimension='';row.querySelector('[data-supplement-status]').textContent='';row.querySelector('[data-supplement-input-status]').textContent='';row.querySelectorAll('[data-supplement-input]').forEach(n=>n.value='');
    BasicCandidatesUI.configure(row);c.state.dirty=true;refresh(form);row.open=false;row.querySelector('summary').focus();c.toast('已加入資訊；第四步逐項確認後才會正式保存。');
    form.dispatchEvent(new Event('input',{bubbles:true}));
  }
  function validate(form){
    const f=current();if(!f)return;
    captureInputs(form);const keys=new Set(c.people(form).map(p=>p.key));
    if(all(f).some(x=>!keys.has(keyOf(x))))throw new Error('請重新關聯補充資訊所屬人物，或明確移除該資訊；不會自動轉給其他人物。');
    const unfinished=Object.entries(f.supplementInputs||{}).filter(([,v])=>hasInput(v));
    if(unfinished.length)throw new Error(unfinished.map(([key,v])=>'「'+(c.people(form).find(p=>p.key===key)?.name||'原人物')+'」·'+(dims[v.dimension]||'未選類別')).join('、')+'：尚未加入資訊；請加入資訊或清空後再保存，避免遺漏輸入。');
  }
  function persist(form){
    const f=current(),field=form?.querySelector('#experience-person-supplements');if(!f||!field)return;
    captureInputs(form);field.value=JSON.stringify({owner_id:f.ownerId,candidates:f.personCandidates||[],birthday_candidates:f.birthdayCandidates||[],employment_candidates:f.employmentCandidates||[],inputs:f.supplementInputs||{}});
  }
  function validCandidate(x){
    const text=(v,max)=>typeof v==='string'&&v.length<=max;
    return x&&text(x.candidate_ref,128)&&x.candidate_ref.length>0&&x.target&&(Number(typeof x.target.person_id==='string')+Number(typeof x.target.client_ref==='string')===1)&&text(x.target.person_id||x.target.client_ref,128)&&text(x.value,160)&&text(x.description,2000)&&(x.dimension==null||Object.hasOwn(dims,x.dimension))&&(x.evidence_type==null||Object.hasOwn(evidence,x.evidence_type))&&['manual','raw'].includes(x.source_kind)&&[x.selected,x.excluded,x.needs_review].every(v=>typeof v==='boolean')&&(x.quote==null||text(x.quote,2000))&&(x.source_sha256==null||typeof x.source_sha256==='string'&&/^[0-9a-f]{64}$/.test(x.source_sha256));
  }
  function validInputs(inputs){
    return inputs&&typeof inputs==='object'&&!Array.isArray(inputs)&&Object.keys(inputs).length<=100&&Object.entries(inputs).every(([key,value])=>key.length<=136&&value&&typeof value==='object'&&!Array.isArray(value)&&Object.values(value).every(v=>typeof v==='string'&&v.length<=2000));
  }
  function restore(form){
    const f=current(),field=form?.querySelector('#experience-person-supplements');if(!f||!field?.value)return;
    try{const saved=JSON.parse(field.value);if(saved.owner_id!==f.ownerId||!Array.isArray(saved.candidates)||saved.candidates.length>100||!saved.candidates.every(validCandidate)||!validInputs(saved.inputs))throw new Error();if(![['birthday',saved.birthday_candidates||[]],['employment',saved.employment_candidates||[]]].every(([kind,list])=>Array.isArray(list)&&list.length<=100&&list.every(x=>BasicCandidatesUI.valid(kind,x)))||saved.candidates.length+(saved.birthday_candidates||[]).length+(saved.employment_candidates||[]).length>100)throw new Error();f.personCandidates=saved.candidates;f.birthdayCandidates=saved.birthday_candidates||[];f.employmentCandidates=saved.employment_candidates||[];f.supplementInputs=saved.inputs&&typeof saved.inputs==='object'&&!Array.isArray(saved.inputs)?saved.inputs:{};form.querySelector('[data-supplement-cards]')?.replaceChildren();refresh(form);}catch{c.toast('本機人物補充草稿無法安全還原；原始素材仍保留，請勿覆蓋。');}
  }
  // 未加入的上一類資訊保持可見，先處理再切換，避免隱藏欄位到最後才阻擋。
  document.addEventListener('change',event=>{
    if(!event.target.matches('[data-supplement-input=dimension]'))return;
    const row=event.target.closest('[data-supplement-person]'),previous=row.dataset.activeDimension||'',next=event.target.value;
    const values=Object.fromEntries([...row.querySelectorAll('[data-supplement-input]')].map(n=>[n.dataset.supplementInput,n.value]));
    if(previous&&previous!==next&&hasInput(values)){
      event.target.value=previous;BasicCandidatesUI.configure(row);
      row.querySelector('[data-supplement-status]').textContent='請先加入「'+dims[previous]+'」資訊，或清空這次輸入，再切換類別；內容仍保留。';
      captureInputs(row.closest('form'));return;
    }
    row.dataset.activeDimension=next;row.querySelector('[data-supplement-status]').textContent='';captureInputs(row.closest('form'));
  });
  document.addEventListener('input',event=>{if(event.target.matches('[data-supplement-input]')){const form=event.target.closest('form');captureInputs(form);const row=event.target.closest('[data-supplement-person]'),f=current(),person=c.people(form).find(p=>p.key===row.dataset.supplementPerson);if(f&&person)inputStatus(row,person,f.supplementInputs[person.key]||{});}});
  document.addEventListener('click',async event=>{
    const f=current();if(!f)return;
    const reset=event.target.closest('[data-supplement-reset]'),addButton=event.target.closest('[data-supplement-add]'),remove=event.target.closest('[data-supplement-remove]'),clear=event.target.closest('[data-supplement-clear]');
    try{if(reset){const row=reset.closest('[data-supplement-person]');f.supplementInputs[row.dataset.supplementPerson]={};row.dataset.activeDimension='';row.querySelector('[data-supplement-status]').textContent='';row.querySelector('[data-supplement-input-status]').textContent='';row.querySelectorAll('[data-supplement-input]').forEach(n=>n.value='');BasicCandidatesUI.configure(row);c.state.dirty=true;row.closest('form').dispatchEvent(new Event('input',{bubbles:true}));}if(addButton){if(addButton.disabled)return;addButton.disabled=true;try{await add(addButton.closest('[data-supplement-person]'));}finally{if(addButton.isConnected)addButton.disabled=false;}}if(remove){f.personCandidates=f.personCandidates.filter(x=>x.candidate_ref!==remove.dataset.supplementRemove);f.birthdayCandidates=(f.birthdayCandidates||[]).filter(x=>x.candidate_ref!==remove.dataset.supplementRemove);f.employmentCandidates=(f.employmentCandidates||[]).filter(x=>x.candidate_ref!==remove.dataset.supplementRemove);c.state.dirty=true;refresh();document.querySelector('#record-form')?.dispatchEvent(new Event('input',{bubbles:true}));}if(clear){f.personCandidates=f.personCandidates.filter(x=>keyOf(x)!==clear.dataset.supplementClear);f.birthdayCandidates=(f.birthdayCandidates||[]).filter(x=>keyOf(x)!==clear.dataset.supplementClear);f.employmentCandidates=(f.employmentCandidates||[]).filter(x=>keyOf(x)!==clear.dataset.supplementClear);delete f.supplementInputs[clear.dataset.supplementClear];c.state.dirty=true;refresh();document.querySelector('#record-form')?.dispatchEvent(new Event('input',{bubbles:true}));}}catch(error){const row=addButton?.closest('[data-supplement-person]');if(row){const status=row.querySelector('[data-supplement-status]');status.textContent=error.message;if(!row.querySelector('[data-supplement-input=source_kind]').value){row.querySelector('[data-supplement-source]').open=true;row.querySelector('[data-supplement-input=source_kind]').focus();}else status.scrollIntoView({block:'nearest'});}c.toast(error.message);}
  });
  return {initialize,refresh,validate,persist,restore};
})();
