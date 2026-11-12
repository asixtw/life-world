'use strict';
/** 單位只決定操作建議；部分完成/最多六位小數仍由既有後端契約決定。 */
window.QuantityUI=(()=>{
  const scale=1000000n,max=1000000000000n*scale;
  function profile(unit){
    const value=String(unit||'').normalize('NFKC').trim().toLowerCase();
    if(['次','回','個','件','篇','本','頁','組','項','count','times'].includes(value))return {step:'1',hint:'通常填整數；部分完成也可直接輸入，例如 0.5。'};
    if(['小時','小时','時','h','hr','hour','hours'].includes(value))return {step:'0.25',hint:'例如 0.5、1.25；可按實際投入填寫。'};
    if(['分鐘','分钟','分','公尺','米','m'].includes(value))return {step:'1',hint:'可填部分完成，依實際投入保留原值。'};
    return {step:'0.1',hint:'例如 1.5、2.75；依單位填寫實際完成量。'};
  }
  function scaled(value){
    const m=String(value).match(/^(\d+)(?:\.(\d{0,6}))?$/);if(!m)return null;
    return BigInt(m[1])*scale+BigInt((m[2]||'').padEnd(6,'0'));
  }
  function format(value){
    const text=String(value??'');return /^\d+\.\d+$/.test(text)?text.replace(/0+$/,'').replace(/\.$/,''):text;
  }
  function decimal(n){return String(n/scale)+(n%scale?'.'+String(n%scale).padStart(6,'0').replace(/0+$/,''):'');}
  function add(value,step,direction){
    const original=scaled(value||'0'),delta=scaled(step);if(original===null||delta===null)return null;
    const result=original+(direction<0?-delta:delta);return result<0n?'0':result>max?null:decimal(result);
  }
  function stepFor(value,unit){const p=profile(unit),v=scaled(value);return value===''||v!==null&&v%scaled(p.step)===0n?p.step:'any';}
  function fields(goal,values,esc){
    if(!goal)return '<p class="small muted">本次不關聯目標，仍可保存真實經歷與積分。</p>';
    return `<fieldset><legend>由你確認本次貢獻</legend><p class="small muted">空白或 0 不累計；部分完成仍會保留，不會自動取整數。</p>${goal.actions.map(a=>{
      const p=profile(a.unit),value=format(values.find(v=>v.action_id===a.id)?.quantity||'');
      return `<div class="field quantity-field"><label for="quantity-${esc(a.id)}">${esc(a.title)}（${esc(a.unit)}）</label><div class="quantity-entry"><button type="button" class="secondary" data-quantity-down="${esc(a.id)}" aria-label="減少${esc(a.title)} ${p.step} ${esc(a.unit)}">−</button><input id="quantity-${esc(a.id)}" name="quantity-${esc(a.id)}" type="number" inputmode="decimal" min="0" max="1000000000000" step="${stepFor(value,a.unit)}" data-quantity-input data-quantity-unit="${esc(a.unit)}" value="${esc(value)}" placeholder="${p.step==='1'?'例如：1':'例如：0.5'}"><button type="button" class="secondary" data-quantity-up="${esc(a.id)}" aria-label="增加${esc(a.title)} ${p.step} ${esc(a.unit)}">＋</button></div><small>${esc(p.hint)}</small><p class="small muted" data-quantity-status role="status"></p></div>`;
    }).join('')}</fieldset>`;
  }
  function sync(root=document){
    for(const input of root.querySelectorAll('[data-quantity-input]')){
      input.step=stepFor(input.value,input.dataset.quantityUnit);
      // 不截斷/改寫使用者文字；超出六位小數交由既有契約拒絕。
      const status=input.closest('.quantity-field').querySelector('[data-quantity-status]');
      const error=input.validity.badInput?'請輸入完整的活動數量。':window.ExperienceValidation?.quantity(input.value);
      status.textContent=error||(input.value&&input.step==='any'?'已保留部分完成數量：'+format(input.value)+' '+input.dataset.quantityUnit:'');
    }
  }
  document.addEventListener('input',e=>{if(e.target.matches('[data-quantity-input]'))sync(e.target.closest('form'));});
  document.addEventListener('click',e=>{
    const button=e.target.closest('[data-quantity-up],[data-quantity-down]');if(!button)return;
    const root=button.closest('.quantity-field'),input=root.querySelector('[data-quantity-input]'),result=add(input.value,profile(input.dataset.quantityUnit).step,button.hasAttribute('data-quantity-down')?-1:1);
    if(result===null){root.querySelector('[data-quantity-status]').textContent='請確認數值格式與上限；現有輸入保留。';return;}
    input.value=result;input.dispatchEvent(new Event('input',{bubbles:true}));
  });
  return {profile,format,add,stepFor,fields,sync};
})();
