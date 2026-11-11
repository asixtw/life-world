'use strict';
/** 人物詳情的生日與任職，以正式API讀寫；不推算年齡、不呼叫AI、不把工作塞進標籤。 */
window.PersonDetailsUI=(()=>{
 let c,current=null,editing=null,withdrawal=null;
 const h=v=>c.esc(v),owner=()=>c.state.me?.owner_id||'',id=v=>encodeURIComponent(v);
 const status={current:'目前',past:'過去',unknown:'未知'};
 function initialize(context){c=context;current=null;editing=null;}
 function birthday(v){return v?.birth_month?`${v.birth_year?`${v.birth_year} 年 `:''}${v.birth_month} 月 ${v.birth_day} 日`:'未記錄生日';}
 function sourceButton(v){return v?.source_experience_id?`<button class="text-button" data-action="basic-source" data-source-id="${h(v.source_experience_id)}">查看原始經歷來源</button>`:'';}
 function withdrawButton(v,kind){return v?.source_status==='active'?`<button class="text-button" data-action="basic-withdraw" data-kind="${kind}" data-employment-id="${h(v.id||'')}">撤回這筆資訊的來源</button>`:'';}
 function provenance(v){return `${{manual:'自行記錄',raw:'經歷原文'}[v.source_kind]||'待核對'} · ${{stated_by_person:'人物本人告知',observed_by_user:'使用者觀察',documented_source:'文件記載'}[v.evidence_type]||'得知依據未記錄'}${v.source_status==='withdrawn'?' · 來源已撤回，待核對':''}`;}
 function work(v){return `<strong>${h([v.company_name,v.job_title].filter(Boolean).join(' · '))}</strong><span class="tag">${h(status[v.employment_status])}</span><p class="small">${h(v.valid_from||'開始日期未記錄')} — ${h(v.valid_to||'結束日期未記錄')}</p>`;}
 async function view(pid){const ticket=owner();let data;try{data=await c.api('/people/'+id(pid)+'/details');}catch(e){if(e.status===503)return '<section class="card"><h2>生日與任職</h2><p>此環境尚未完成基本資料契約與權限驗收，目前不開放輸入。</p></section>';throw e;}if(owner()!==ticket)return '';current={owner:ticket,pid,data};
  const canEdit=data.person.status!=='archived';
  return `<section class="card person-basic-panel"><div class="section-title"><h2>生日與任職</h2>${c.link('persons-edit/'+id(pid),'編輯人物識別資訊','text-button')}</div><div class="basic-birthday"><h3>${h(birthday(data.birthday))}</h3>${data.birthday?`<p class="small">${h(provenance(data.birthday))} · 版本 ${data.birthday.revision}</p>${sourceButton(data.birthday)}${canEdit?withdrawButton(data.birthday,'birthday'):''}`:''}${canEdit?'<button class="secondary" data-action="basic-birthday">新增／更正生日</button>':''}</div><h3 class="space-top">任職紀錄</h3><p class="small muted">可以同時有多份目前工作；新增不會結束或刪除舊工作。</p><div class="stack">${data.employments.map(e=>`<article class="card">${work(e)}<p class="small">${h(provenance(e))} · 版本 ${e.revision}</p>${sourceButton(e)}${canEdit?withdrawButton(e,'employment'):''}${canEdit?`<button class="text-button" data-action="basic-work" data-employment-id="${h(e.id)}">更正這筆任職</button>`:''}</article>`).join('')||'<p>尚無任職紀錄。</p>'}</div>${canEdit?'<button class="secondary space-top" data-action="basic-work">＋ 新增一筆任職</button>':''}<details class="space-top"><summary>查看更正歷史</summary>${data.birthday_history.map(v=>`<p>生日 · 版本 ${v.revision}：${h(birthday(v))} · ${h(provenance(v))}</p>`).join('')}${data.employment_history.map(v=>`<div>任職 · 版本 ${v.revision}：${work(v)}</div>`).join('')||'<p class="small">尚無任職異動。</p>'}</details><p class="small muted">這是使用者核對的記錄，不代表已向人物本人獨立查證。</p></section>`;
 }
 function sourceFields(v){return `<details class="space-top"><summary>資訊依據（選填）</summary><label>這項資訊從何得知？<select name="evidence_type"><option value="">自行記錄／目前不知道</option>${Object.entries({stated_by_person:'人物本人告知',observed_by_user:'我觀察到',documented_source:'文件記載'}).map(([k,n])=>`<option value="${k}"${v?.evidence_type===k?' selected':''}>${n}</option>`).join('')}</select></label><p class="small">此詳情編輯為自行記錄，不會虛構經歷ID或傳送至AI。</p></details>`;}
 function open(kind,eid){if(!current||current.owner!==owner())throw new Error('帳號已改變，請重新載入人物。');const v=kind==='birthday'?current.data.birthday:current.data.employments.find(e=>e.id===eid);editing={kind,eid,owner:owner(),pid:current.pid,revision:v?.revision||0,requestId:c.requestId('person-basic')};
  const fields=kind==='birthday'?`<p class="small">月日可獨立保存，年份選填；全部留白表示未知，不會推算年齡。</p><div class="button-row">${[['birth_year','年（選填）',1,9999],['birth_month','月',1,12],['birth_day','日',1,31]].map(([k,label,min,max])=>`<label>${label}<input name="${k}" type="number" min="${min}" max="${max}" value="${h(v?.[k]??'')}"></label>`).join('')}</div>`:`<div class="field"><label>公司／組織<input name="company_name" maxlength="300" value="${h(v?.company_name||'')}"></label></div><div class="field"><label>職稱／工作<input name="job_title" maxlength="300" value="${h(v?.job_title||'')}"></label></div><label>任職狀態<select name="employment_status">${Object.entries(status).map(([k,n])=>`<option value="${k}"${(v?.employment_status||'unknown')===k?' selected':''}>${n}</option>`).join('')}</select></label><div class="button-row"><label>開始日期（選填）<input name="valid_from" type="date" value="${h(v?.valid_from||'')}"></label><label>結束日期（選填）<input name="valid_to" type="date" value="${h(v?.valid_to||'')}"></label></div>`;
  c.dialog(`<h2 id="account-heading">${kind==='birthday'?'核對生日':eid?'核對這筆任職更正':'新增任職紀錄'}</h2><form id="person-basic-form" class="stack">${fields}${sourceFields(v)}<p class="small">按下保存代表你已核對本次輸入。失敗時內容保留；版本衝突不覆寫他人修改。</p><button class="primary" type="submit">核對並保存</button></form>`);
 }
 async function handleClick(action,target){if(action==='basic-withdraw'){
  if(!current||current.owner!==owner())throw new Error('帳號已改變，請重新載入。');
  const kind=target.dataset.kind,value=kind==='birthday'?current.data.birthday:current.data.employments.find(e=>e.id===target.dataset.employmentId);
  if(!value)throw new Error('找不到可撤回的資料。');
  withdrawal={owner:owner(),pid:current.pid,kind,eid:value.id,revision:value.revision,requestId:c.requestId('person-source-withdrawal')};
  c.dialog('<h2 id="account-heading">撤回這筆資訊的來源？</h2><p>保留原始資料與歷史，並標示來源已撤回、需要重新核對。這不會刪除原經歷、其他人物資料、進度或獎勵。</p><div class="button-row"><button class="secondary" data-action="close-account">保留來源</button><button class="danger" data-action="basic-confirm-withdraw">確認撤回來源</button></div>');return true;
 }if(action==='basic-confirm-withdraw'){
  const w=withdrawal;if(!w||w.owner!==owner())throw new Error('帳號已改變，請重新載入。');
  const prefix='/people/'+id(w.pid),path=w.kind==='birthday'?prefix+'/basic-details/source-withdrawal':prefix+'/employments/'+id(w.eid)+'/source-withdrawal';
  await c.api(path,{method:'POST',body:{request_id:w.requestId,expected_revision:w.revision,confirmed:true}});
  if(owner()!==w.owner||withdrawal!==w)return true; // 回應到達時若已換帳號或另開操作，不關閉新的對話框。
  withdrawal=null;document.querySelector('#account-dialog').close();await c.render();c.toast('來源已撤回，原始資料與歷史保留。');return true;
 }if(action==='basic-source'){const ticket=owner(),data=await c.api('/connections/stories/'+id(target.dataset.sourceId)+'?manage=true');if(owner()!==ticket)return true;c.dialog(`<h2 id="account-heading">原始經歷來源</h2><p class="record-content">${h(data.raw_text)}</p><p class="small">原始內容沒有被摘要覆寫；這次查看不修改任何資料。</p>`);return true;}if(action==='basic-birthday'){open('birthday');return true;}if(action==='basic-work'){open('employment',target.dataset.employmentId);return true;}return false;}
 async function handleSubmit(form){if(form.id!=='person-basic-form')return false;if(!editing||editing.owner!==owner())throw new Error('帳號已改變，請重新載入。');const f=new FormData(form),value={};
  if(editing.kind==='birthday')for(const k of ['birth_year','birth_month','birth_day'])value[k]=f.get(k)===''?null:Number(f.get(k));
  else{for(const k of ['company_name','job_title','employment_status'])value[k]=String(f.get(k)||'');for(const k of ['valid_from','valid_to'])value[k]=f.get(k)||null;}
  const body={request_id:editing.requestId,confirmed:true,value,source:{source_kind:'manual',evidence_type:f.get('evidence_type')||null}};
  const prefix='/people/'+id(editing.pid);let path,method;
  if(editing.kind==='birthday'){path=prefix+'/basic-details';method='PATCH';body.expected_revision=editing.revision;}else if(editing.eid){path=prefix+'/employments/'+id(editing.eid);method='PATCH';body.expected_revision=editing.revision;}else{path=prefix+'/employments';method='POST';}
  await c.api(path,{method,body});document.querySelector('#account-dialog').close();editing=null;c.state.dirty=false;await c.render();c.toast('人物資料已保存，異動歷史已保留。');return true;
 }
 return {initialize,view,handleClick,handleSubmit};
})();
