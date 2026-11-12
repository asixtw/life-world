'use strict';
/** 四步提早驗證與人類可讀錯誤；不寫DB、不修改日期或正式貢獻。 */
window.ExperienceValidation=(()=>{
  let c;const forms=new WeakMap();
  const present=v=>v!==''&&v!=null;
  function calendar(year,month,day){const d=new Date(0);d.setUTCFullYear(year,month-1,day);return d.getUTCFullYear()===year&&d.getUTCMonth()===month-1&&d.getUTCDate()===day;}
  function birthday(v,complete=false){
    const errors={},m=present(v.birth_month)?Number(v.birth_month):null,d=present(v.birth_day)?Number(v.birth_day):null,y=present(v.birth_year)?Number(v.birth_year):null;
    if(m!=null&&(!Number.isInteger(m)||m<1||m>12))errors.birth_month='月份請填 1 到 12。';
    if(y!=null&&(!Number.isInteger(y)||y<1||y>9999))errors.birth_year='出生年請填 1 到 9999 的整數；不知道可以留白。';
    if(d!=null&&(!Number.isInteger(d)||d<1||d>31))errors.birth_day='日期請填 1 到 31，並確認這個月份有這一天。';
    if((complete||m!=null||d!=null||y!=null)&&m==null)errors.birth_month='請填寫生日月份，月和日需要一起填。';
    if((complete||m!=null||d!=null||y!=null)&&d==null)errors.birth_day='請填寫生日日期，月和日需要一起填。';
    // 未知年份只用閏年驗證月日；不把該年回填或保存。
    if(m!=null&&d!=null&&!Object.keys(errors).length&&!calendar(y??2000,m,d))errors.birth_day=m+' 月沒有 '+d+' 日'+(y!=null?'（'+y+' 年）':'')+'，請重新選擇日期。';
    return errors;
  }
  function employment(v,complete=false){
    const errors={};for(const key of ['valid_from','valid_to'])if(v[key]){const p=String(v[key]).match(/^(\d{4})-(\d{2})-(\d{2})$/);if(!p||Number(p[1])<1||!calendar(...p.slice(1).map(Number)))errors[key]='請選擇有效的任職日期。';}
    if(!Object.keys(errors).length&&v.valid_from&&v.valid_to&&v.valid_from>v.valid_to)errors.valid_to='結束日期不能早於開始日期，請確認任職期間。';
    if(complete&&!v.company_name?.trim()&&!v.job_title?.trim())errors.company_name='公司／組織或職稱至少填寫一項。';return errors;
  }
  function quantity(value){
    if(value===''||value==null)return '';
    // Decimal允許科學記號；檢查有效小數精度，不把微小正數當零或四捨五入。
    const match=String(value).match(/^\+?(\d+)(?:\.(\d*))?(?:e([+-]?\d+))?$/i),n=Number(value);
    if(!match||!Number.isFinite(n)||n<0)return '請填寫 0 或正數；空白表示本次不累計。';
    if(n>1000000000000)return '活動數量超過可用上限，請確認實際完成量。';
    if((match[2]?.length||0)-Number(match[3]||0)>6)return '活動數量最多保留 6 位小數，請依實際完成量調整。';return '';
  }
  function period(goal,iso,positive){
    if(!goal)return {message:'',blocked:false};
    if(!goal.start_date||!goal.deadline||!goal.schedule_timezone)return {message:'這個目標尚未完成期間或時區設定；經歷可以保留，請先選擇不計入目標。',blocked:positive&& !['awaiting_review','needs_setup'].includes(goal.status)};
    let day;try{day=new Intl.DateTimeFormat('en-CA',{timeZone:goal.schedule_timezone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(iso));}catch{return {message:'請先確認第一步的實際發生時間。',blocked:positive};}
    const outside=day<goal.start_date||day>goal.deadline,closed=['completed','ended'].includes(goal.status),pending=['awaiting_review','needs_setup'].includes(goal.status);
    return {day,outside,blocked:positive&&(closed||outside&&!pending),message:`挑戰期間：${goal.start_date} 至 ${goal.deadline}；本次經歷：${day}（${goal.schedule_timezone}）。`+(closed?'此挑戰已收藏，活動量不能再計入。':outside?'這次經歷不在目標挑戰期間。':'')+(pending?'此目標需回顧／設定，活動量依既有規則暫存待處理，不直接累計。':outside?'經歷仍可保存，但本次活動量不能計入此目標。':'')};
  }
  function initialize(context){c=context;}
  function remember(form){const f=forms.get(form);if(!f)return;if(f.goalId)f.values[f.goalId]=[...form.querySelectorAll('[data-quantity-input]')].map(n=>({action_id:n.name.slice(9),quantity:n.value}));const input=form.querySelector('#experience-goal-inputs');if(input)input.value=JSON.stringify({owner_id:c.state.me.owner_id,values:f.values});}
  function mount(form){
    if(!form?.querySelector('#goal-id')||forms.has(form))return;
    const f={goalId:form.elements.goal_id.value,values:Object.create(null)};forms.set(form,f);
    form.querySelector('#goal-id').closest('.field').insertAdjacentHTML('afterend','<div class="callout" data-goal-period hidden><p data-goal-period-status role="status"></p><button type="button" class="secondary" data-goal-omit>保留經歷但不計入目標</button></div><p class="small muted" data-goal-retained role="status"></p><input type="hidden" id="experience-goal-inputs" name="experience_goal_inputs">');sync(form);
  }
  function restore(form){
    const f=forms.get(form),input=form?.querySelector('#experience-goal-inputs');if(!f||!input)return;
    try{const x=input.value?JSON.parse(input.value):null;if(x?.owner_id===c.state.me.owner_id&&x.values&&Object.keys(x.values).length<=200)for(const goal of c.state.world.goals){const list=x.values[goal.id];if(Array.isArray(list)&&list.length<=50&&list.every(v=>goal.actions.some(a=>a.id===v.action_id)&&typeof v.quantity==='string'&&v.quantity.length<=100))f.values[goal.id]=list;}}catch{/* 不信任本機JSON；畫面現值不受影響。 */}
    f.goalId=form.elements.goal_id.value;sync(form);
  }
  function changeGoal(form){
    const f=forms.get(form);if(!f)return;remember(form);f.goalId=form.elements.goal_id.value;const goal=c.state.world.goals.find(g=>g.id===f.goalId);
    form.querySelector('#contribution-fields').innerHTML=QuantityUI.fields(goal,f.values[f.goalId]||[],c.esc);sync(form);form.dispatchEvent(new Event('input',{bubbles:true}));
  }
  function sync(form){
    if(!form)return true;const f=forms.get(form);if(f)remember(form);let valid=true;
    for(const n of form.querySelectorAll('[data-quantity-input]')){const error=n.validity.badInput?'請輸入完整的活動數量。':quantity(n.value);const status=n.closest('.quantity-field').querySelector('[data-quantity-status]');if(error)status.textContent=error;n.setCustomValidity(error);n.setAttribute('aria-invalid',String(!!error));if(error)valid=false;}
    if(!f){const node=form.querySelector('[data-review-goal-validation]');if(node){const goal=c.state.world.goals.find(g=>g.id===c.state.draft?.goal_id),positive=[...form.querySelectorAll('[data-quantity-input]')].some(n=>Number(n.value)>0),result=period(goal,c.state.draft?.occurred_at,positive);node.hidden=!result.blocked;node.querySelector('p').textContent=result.message;}return valid;}
    const goal=c.state.world.goals.find(g=>g.id===form.elements.goal_id.value),positive=[...form.querySelectorAll('[data-quantity-input]')].some(n=>Number(n.value)>0);
    let iso;try{iso=c.inputISO(form.elements.calendar_time?form.elements.calendar_date.value+'T'+form.elements.calendar_time.value:form.elements.occurred_at.value,form.dataset.calendarZone||c.state.me.timezone);}catch{}
    const result=period(goal,iso,positive),panel=form.querySelector('[data-goal-period]');panel.hidden=!goal;panel.querySelector('[data-goal-period-status]').textContent=result.message;panel.classList.toggle('error-message',result.blocked);panel.querySelector('[data-goal-omit]').hidden=!goal||!result.blocked&&!result.outside;
    const saved=Object.entries(f.values).filter(([id])=>id!==f.goalId).flatMap(([id,values])=>values.filter(x=>x.quantity!==''&&Number(x.quantity)!==0).map(x=>(c.state.world.goals.find(g=>g.id===id)?.title||'原目標')+'：'+x.quantity));form.querySelector('[data-goal-retained]').textContent=saved.length?'已保留尚未計入的輸入（重新選擇原目標可取回）：'+saved.join('、'):'';
    return valid&&!result.blocked;
  }
  function mountReview(form){if(!form||form.querySelector('[data-review-goal-validation]'))return;form.querySelector('#experience-review-overview').insertAdjacentHTML('beforebegin','<div class="callout error-message" data-review-goal-validation hidden><p role="status"></p><button type="button" class="secondary" data-action="fix-experience-goal">返回第二步修正目標與數量</button></div>');sync(form);}
  function people(form,complete=false){
    if(form.querySelector('#include-story')?.checked===false)return true;
    let valid=true;
    for(const input of form.querySelectorAll('[data-workflow-role],[data-target-role]')){
      const card=input.closest('[data-workflow-person],[data-pending-target]'),name=card?.querySelector('[data-target-name]')?.value||card?.querySelector('strong')?.textContent||'這位人物';
      let node=input.parentElement.querySelector('[data-role-error]');if(!node){node=document.createElement('small');node.dataset.roleError='true';node.className='error-message';node.setAttribute('role','status');input.after(node);}
      const error=!input.value?'請選擇「'+name+'」本次是直接互動、共同參與，還是只有提及。':'';node.textContent=error;input.setAttribute('aria-invalid',String(!!error));if(error)valid=false;
    }
    return valid;
  }
  function apiMessage(error){
    if(error.code==='validation_error'||Array.isArray(error.fields)&&error.fields.length||/review\.(birthday|employment|person)_candidates/.test(error.message||'')){const labels={birth_day:'生日日期',birth_month:'生日月份',birth_year:'出生年份',valid_from:'任職開始日期',valid_to:'任職結束日期',company_name:'公司／組織',job_title:'職稱',quantity:'活動數量',occurred_at:'實際發生時間',evidence_type:'資訊得知依據',source_kind:'資訊來源',quote:'原文片段',relation:'人物角色',interacted:'人物互動角色'};
      const names=[...new Set((Array.isArray(error.fields)?error.fields:[]).map(path=>labels[String(path).split('.').at(-1)]||(/birthday/.test(path)?'生日資料':/employment/.test(path)?'任職資料':/story|person/.test(path)?'人物關聯資訊':'輸入資料')))];return '請確認'+(names.join('、')||'輸入資料')+'是否完整且格式正確；已輸入的內容仍保留。';}
    return error.message;
  }
  document.addEventListener('input',e=>{const form=e.target.closest('#record-form');if(form)sync(form);});
  document.addEventListener('focusout',e=>{if(e.target.matches('[data-workflow-role],[data-target-role]')){e.target.dataset.roleTouched='true';people(e.target.closest('form'));}const form=e.target.closest('#record-form');if(form)sync(form);});
  document.addEventListener('click',e=>{if(e.target.closest('[data-goal-omit]')){const form=e.target.closest('form');remember(form);form.elements.goal_id.value='';changeGoal(form);}});
  return {mountReview,people,initialize,calendar,birthday,employment,quantity,period,mount,restore,changeGoal,sync,apiMessage};
})();
