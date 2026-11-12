'use strict';
/** 經歷中的生日/任職只建立逐人候選，與既有Confirm共用交易，不在此提前寫入。 */
window.BasicCandidatesUI=(()=>{
  let c;const priorDetails=new WeakMap();
  const labels={birthday:'生日',employment:'任職'};
  const esc=v=>c.esc(v??'');
  function initialize(context){c=context;}
  function entries(f=c.getFlow()){return [...(f?.birthdayCandidates||[]).map(x=>({kind:'birthday',x})),...(f?.employmentCandidates||[]).map(x=>({kind:'employment',x}))];}
  function field(key,label,value,type='text'){return `<label class="field">${label}<input type="${type}" data-supplement-input="${key}" value="${esc(value)}" ${type==='number'?'min="1" step="1"':type==='text'?'maxlength="300"':''}></label>`;}
  function inputs(v){return `<div data-basic-fields hidden><div data-basic-birthday hidden>${field('birth_month','月份',v.birth_month,'number')}${field('birth_day','日期',v.birth_day,'number')}${field('birth_year','出生年（選填，不推算年齡）',v.birth_year,'number')}</div><div data-basic-employment hidden><label class="field">本次任職<select data-supplement-input="employment_id"><option value="">新增一筆任職，不結束原有工作</option></select></label>${field('company_name','公司／組織',v.company_name)}${field('job_title','職稱／工作身分',v.job_title)}<label class="field">任職狀態<select data-supplement-input="employment_status">${[['unknown','未知'],['current','目前'],['past','過去']].map(([k,t])=>`<option value="${k}" ${v.employment_status===k?'selected':''}>${t}</option>`).join('')}</select></label>${field('valid_from','開始日期（選填）',v.valid_from,'date')}${field('valid_to','結束日期（選填）',v.valid_to,'date')}</div><p class="small" data-basic-prior-status role="status"></p><p class="small muted">自行記錄可以不指定證據；原文來源須核對片段與得知依據。最後確認前不更新人物檔案。</p></div>`;}
  function birthday(v){return v.birth_month==null?(v.birth_year!=null?'出生年 '+v.birth_year+'（月日待填）':v.birth_day!=null?'月份待填 · '+v.birth_day+' 日':'尚未填寫生日月日'):`${v.birth_year==null?'':v.birth_year+' 年 '}${v.birth_month} 月 ${v.birth_day??'待填'} 日`;}
  function work(v){return '公司／組織：'+(v.company_name===undefined?'未修改':v.company_name||'空白')+'；職稱：'+(v.job_title===undefined?'未修改':v.job_title||'空白')+'；'+({current:'目前',past:'過去',unknown:'未知'}[v.employment_status]||'狀態未修改')+(v.valid_from||v.valid_to?'；期間：'+(v.valid_from||'未指定')+' 至 '+(v.valid_to||'未指定'):'');}
  function text(kind,x){return kind==='birthday'?(x.clear?'明確清除生日':birthday(x.value)):work(x.value);}
  function onPerson(x,p){return p.personId?x.target.person_id===p.personId:x.target.client_ref===p.key.slice(8);}
  /** 依類別局部開啟欄位並唯讀載入原值；Owner/草稿變更後拒絕晚回應。 */
  async function configure(row){
    const kind=row.querySelector('[data-supplement-input=dimension]').value,isBasic=!!labels[kind];
    row.querySelector('[data-basic-fields]').hidden=!isBasic;row.querySelector('[data-basic-birthday]').hidden=kind!=='birthday';row.querySelector('[data-basic-employment]').hidden=kind!=='employment';
    row.querySelector('[data-supplement-input=value]').closest('label').hidden=isBasic;row.querySelector('[data-supplement-input=description]').closest('label').hidden=isBasic;
    if(!isBasic)return;
    const flow=c.getFlow(),owner=c.state.me.owner_id,person=c.people(row.closest('form')).find(p=>p.key===row.dataset.supplementPerson),note=row.querySelector('[data-basic-prior-status]');
    if(!person?.personId){note.textContent='待建立人物，尚無原有基本資料。';return;}
    note.textContent='正在讀取原有基本資料…';
    try{
      const details=await c.api('/people/'+person.personId+'/details');
      if(c.getFlow()!==flow||owner!==c.state.me?.owner_id||!row.isConnected||row.querySelector('[data-supplement-input=dimension]').value!==kind)return;
      priorDetails.set(row,details);
      const select=row.querySelector('[data-supplement-input=employment_id]'),saved=flow.supplementInputs?.[person.key]?.employment_id||select.value;
      select.innerHTML='<option value="">新增一筆任職，不結束原有工作</option>'+details.employments.map(j=>`<option value="${esc(j.id)}">${esc(work(j))}</option>`).join('');select.value=saved;
      note.textContent=kind==='birthday'?'原有生日：'+(details.birthday?birthday(details.birthday):'尚無紀錄'):'選擇新增任職，或明確選一筆原有任職更正；不自動覆寫其他工作。';
    }catch{if(row.isConnected&&c.getFlow()===flow)note.textContent='原有資料暫時讀取失敗，輸入保留；請重選資訊類別後再試。';}
  }
  /** 回傳一項指定人物的本機候選；只讀版本，不在加入/保存草稿時寫正式資料。 */
  async function create(person,v,raw){
    const f=c.getFlow(),owner=c.state.me.owner_id,kind=v.dimension;
    const details=person.personId?await c.api('/people/'+person.personId+'/details'):null;
    if(f!==c.getFlow()||owner!==c.state.me?.owner_id)throw new Error('帳號或草稿已變更，未加入資訊。');
    const x={candidate_ref:crypto.randomUUID(),target:person.personId?{person_id:person.personId}:{client_ref:person.key.slice(8)},expected_revision:0,source_kind:v.source_kind||'manual',source_sha256:null,quote:v.source_kind==='raw'?v.quote:null,evidence_type:v.evidence_type||null,selected:false,excluded:false,needs_review:true};
    if(kind==='birthday'){
      x.expected_revision=details?.birthday?.revision||0;x.value=Object.fromEntries(['birth_year','birth_month','birth_day'].map(k=>[k,v[k]===''||v[k]==null?null:Number(v[k])]));
      if(Object.values(x.value).every(v=>v==null))throw new Error('請填寫生日月日；空白不代表清除生日。');
    }else{
      const prior=v.employment_id?details?.employments.find(j=>j.id===v.employment_id):null;
      if(v.employment_id&&!prior)throw new Error('找不到這位人物的原有任職，請重新選擇。');
      x.employment_id=prior?.id||null;x.expected_revision=prior?.revision||0;
      x.value={company_name:v.company_name?.trim()||'',job_title:v.job_title?.trim()||'',employment_status:v.employment_status||'unknown',valid_from:v.valid_from||null,valid_to:v.valid_to||null};
      if(!x.value.company_name&&!x.value.job_title)throw new Error('公司或職稱至少填一項；不會用空白清除工作。');
    }
    return {kind,x};
  }
  /** 原文須再核對；未知年份僅用閏年檢查月日，不將該年存入資料。 */
  function ready(kind,x,recheck=false){
    const raw=c.state.draft?.raw_text||'',hash=c.state.draft?.raw_sha256;
    if(x.source_kind==='raw'&&(!x.evidence_type||!x.quote||!raw.includes(x.quote)||!recheck&&x.source_sha256!==hash))return false;
    if(kind==='birthday'){
      const v=x.value;if(v.birth_month==null)return !!x.clear&&v.birth_year==null&&v.birth_day==null;
      const year=v.birth_year??2000;if(!Number.isInteger(year)||year<1||year>9999||!Number.isInteger(v.birth_month)||!Number.isInteger(v.birth_day))return false;
      const d=new Date(0);d.setUTCFullYear(year,v.birth_month-1,v.birth_day);
      return !x.clear&&d.getUTCFullYear()===year&&d.getUTCMonth()===v.birth_month-1&&d.getUTCDate()===v.birth_day;
    }
    return !!(x.value.company_name||x.value.job_title)&&(!x.value.valid_from||!x.value.valid_to||x.value.valid_from<=x.value.valid_to);
  }
  function render(p,dialog){
    const own=entries().filter(({x})=>onPerson(x,p));if(!own.length)return;
    const body=dialog.querySelector('.experience-preview-body');body.querySelector('[data-basic-candidate-review]')?.remove();
    body.insertAdjacentHTML('afterbegin',`<section data-basic-candidate-review><h3>本次基本資料變更</h3><p class="small">逐項核對這份資料；不是向人物本人獨立查證。未採用不會寫入。</p>${own.map(({kind,x})=>`<section class="card space-top" data-basic-review-row="${esc(x.candidate_ref)}"><h4>${labels[kind]} · ${kind==='birthday'?(x.expected_revision===0?'新增生日':'更正生日'):!x.employment_id?'新增任職':'更正任職'}</h4><p data-basic-prior="${esc(x.candidate_ref)}">${p.personId?'正在讀取原值…':'待建立人物，尚無原值。'}</p><p>→ 本次資料：${esc(text(kind,x))}</p><details><summary>查看資料來源</summary><p>${x.source_kind==='raw'?'本次原文片段':'我手動提供／自行記錄'}</p>${x.quote?`<blockquote>${esc(x.quote)}</blockquote>`:''}<p>${esc({stated_by_person:'人物本人告知',observed_by_user:'我觀察到',documented_source:'文件記載'}[x.evidence_type]||'未指定證據，不視為人物本人告知')}</p></details>${x.needs_review?'<p class="small">'+(x.source_kind==='raw'&&x.source_sha256&&x.source_sha256!==c.state.draft?.raw_sha256?'原始經歷已修改，這項資訊需要重新核對；請對照目前原文。':'請核對內容、有效來源與日期；不完整資料請返回修改或排除。')+'</p>':''}<label class="check-line"><input type="checkbox" data-basic-select="${esc(x.candidate_ref)}" ${x.selected?'checked':''} ${p.personId?'disabled':''}>我已核對，最後確認時保存</label><button type="button" class="text-button" data-basic-exclude="${esc(x.candidate_ref)}">${x.excluded?'恢復待你確認':'本次不保存這項'}</button><p data-basic-result>${x.selected?'確認後會保存':x.excluded?'此次完成後不會保留到人物檔案':'待你確認，目前不會寫入'}</p></section>`).join('')}</section>`);
    if(p.personId)loadPrior(p,dialog,own);
  }
  /** 原值與候選版本不同就撤銷採用；不可靜默更新預期版本來繞過衝突。 */
  async function loadPrior(p,dialog,own){
    const f=c.getFlow(),owner=c.state.me.owner_id,key=p.key;
    try{
      const details=await c.api('/people/'+p.personId+'/details');
      if(f!==c.getFlow()||owner!==c.state.me?.owner_id||dialog.dataset.personKey!==key)return;
      for(const {kind,x} of own){
        const prior=kind==='birthday'?details.birthday:x.employment_id?details.employments.find(j=>j.id===x.employment_id):null;
        const n=dialog.querySelector('[data-basic-prior="'+CSS.escape(x.candidate_ref)+'"]');if(!n)continue;
        n.textContent='原有資料：'+(prior?text(kind,{value:prior}):'尚無此筆資料')+(prior?.source_status==='withdrawn'?'（來源已撤回，不能當有效證據）':'');
        const control=dialog.querySelector('[data-basic-select="'+CSS.escape(x.candidate_ref)+'"]');control.disabled=false;
        if((prior?.revision||0)!==x.expected_revision){n.textContent+='；版本已變更，請返回第三步重新加入資訊，不會自動覆寫。';x.selected=false;x.needs_review=true;n.dataset.versionConflict='true';dialog.querySelector('[data-basic-select="'+CSS.escape(x.candidate_ref)+'"]').disabled=true;control.checked=false;control.closest('[data-basic-review-row]').querySelector('[data-basic-result]').textContent='版本衝突，目前不會寫入';c.state.dirty=true;}
      }
      c.refresh();
    }catch{if(f===c.getFlow()&&dialog.dataset.personKey===key)dialog.querySelectorAll('[data-basic-prior]').forEach(n=>n.textContent='原值暫時讀取失敗，請關閉後重開；資訊保留。');}
  }
  function valid(kind,x){
    // IndexedDB是可被修改的輸入，不信任另一Owner/任意JSON；正式API仍會再次驗證。
    const text=(v,n)=>typeof v==='string'&&v.length>0&&v.length<=n;
    if(!x||typeof x!=='object'||Array.isArray(x)||!text(x.candidate_ref,128)||!x.target||typeof x.target!=='object')return false;
    const keys=Object.keys(x.target);if(keys.length!==1||!['person_id','client_ref'].includes(keys[0])||!text(x.target[keys[0]],128))return false;
    const allowed=['candidate_ref','target','expected_revision','source_kind','source_sha256','quote','evidence_type','selected','excluded','needs_review','value',kind==='birthday'?'clear':'employment_id'];
    if(Object.keys(x).some(k=>!allowed.includes(k))||!Number.isInteger(x.expected_revision)||x.expected_revision<0||!['manual','raw'].includes(x.source_kind)||![x.selected,x.excluded,x.needs_review].every(v=>typeof v==='boolean')||x.selected&&x.excluded)return false;
    if(x.quote!=null&&(typeof x.quote!=='string'||x.quote.length>2000)||x.source_sha256!=null&&!/^[0-9a-f]{64}$/.test(x.source_sha256)||x.evidence_type!=null&&!['stated_by_person','observed_by_user','documented_source'].includes(x.evidence_type))return false;
    const v=x.value;if(!v||typeof v!=='object'||Array.isArray(v))return false;
    if(kind==='birthday')return (x.clear==null||typeof x.clear==='boolean')&&Object.keys(v).every(k=>['birth_year','birth_month','birth_day'].includes(k))&&Object.entries(v).every(([k,n])=>n==null||Number.isInteger(n)&&n>=1&&n<=({birth_year:9999,birth_month:12,birth_day:31}[k]));
    return (x.employment_id==null||text(x.employment_id,128))&&Object.keys(v).every(k=>['company_name','job_title','employment_status','valid_from','valid_to'].includes(k))&&Object.entries(v).every(([k,n])=>k==='employment_status'?['current','past','unknown'].includes(n):['valid_from','valid_to'].includes(k)?n==null||typeof n==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(n):typeof n==='string'&&n.length<=300);
  }
  function update(ref,action,value){
    const found=entries().find(({x})=>x.candidate_ref===ref),f=c.getFlow();if(!found||f?.ownerId!==c.state.me?.owner_id)return;
    const {kind,x}=found,row=document.querySelector('[data-basic-review-row="'+CSS.escape(ref)+'"]');
    if(action==='select'&&value&&!ready(kind,x,true)){c.toast('資料或來源尚未完整，請返回第三步修改或排除此項。');row.querySelector('[data-basic-select]').checked=false;return;}
    if(action==='exclude'){x.excluded=!x.excluded;x.selected=false;}else{x.selected=value;x.excluded=false;if(value){x.needs_review=false;if(x.source_kind==='raw')x.source_sha256=c.state.draft.raw_sha256;}}
    c.state.dirty=true;c.refresh();row.querySelector('[data-basic-select]').checked=x.selected;row.querySelector('[data-basic-exclude]').textContent=x.excluded?'恢復待你確認':'本次不保存這項';row.querySelector('[data-basic-result]').textContent=x.selected?'確認後會保存':x.excluded?'此次完成後不會保留到人物檔案':'待你確認，目前不會寫入';
  }
  document.addEventListener('change',e=>{if(e.target.matches('[data-supplement-input=employment_id]')){const row=e.target.closest('[data-supplement-person]'),job=priorDetails.get(row)?.employments.find(j=>j.id===e.target.value);if(job){for(const key of ['company_name','job_title','employment_status','valid_from','valid_to'])row.querySelector('[data-supplement-input='+key+']').value=job[key]??'';row.dispatchEvent(new Event('input',{bubbles:true}));}}if(e.target.matches('[data-supplement-input=dimension]'))configure(e.target.closest('[data-supplement-person]'));if(e.target.dataset.basicSelect)update(e.target.dataset.basicSelect,'select',e.target.checked);});
  document.addEventListener('click',e=>{const n=e.target.closest('[data-basic-exclude]');if(n)update(n.dataset.basicExclude,'exclude');});
  return {initialize,entries,inputs,configure,create,ready,render,text,onPerson,valid};
})();
