'use strict';
// 所有阻擋都同時提供欄位說明與操作區摘要，避免頁首提示留在視窗外。
const FormUX = (() => {
  let serial=0, nativeFirst=null;
  function summary(container,message){
    if(!container)return;
    let node=container.querySelector(':scope > .form-feedback');
    if(!node){node=document.createElement('p');node.className='form-feedback';node.setAttribute('aria-live','polite');const actions=container.querySelector(':scope > .actions,.theater-compose > .actions');if(actions)actions.before(node);else container.append(node);}
    node.textContent=message;
  }
  function clear(field){
    if(!field)return;
    field.removeAttribute('aria-invalid');
    const id=field.dataset.validationError;
    if(id){document.getElementById(id)?.remove();const refs=(field.getAttribute('aria-describedby')||'').split(' ').filter(x=>x&&x!==id);if(refs.length)field.setAttribute('aria-describedby',refs.join(' '));else field.removeAttribute('aria-describedby');delete field.dataset.validationError;}
    const container=field.closest('form,.card');
    if(container&&!container.querySelector('[aria-invalid="true"]'))container.querySelector(':scope > .form-feedback')?.remove();
  }
  function fail(message,selector,focus=true){
    const field=typeof selector==='string'?document.querySelector(selector):selector;
    const container=field?.closest('form,.card')||document.querySelector('#app form,#app .card');
    if(focus)summary(container,message);
    if(!field)return;
    if(!field.id)field.id='validation-field-'+(++serial);
    const id=field.id+'-error';let error=document.getElementById(id);
    if(!error){error=document.createElement('p');error.id=id;error.className='field-error';(field.closest('label.check')||field).after(error);}
    error.textContent=message;field.setAttribute('aria-invalid','true');field.dataset.validationError=id;
    field.setAttribute('aria-describedby',[...new Set((field.getAttribute('aria-describedby')||'').split(' ').filter(Boolean).concat(id))].join(' '));
    if(focus){
      const collapsed=field.closest('details');if(collapsed)collapsed.open=true;
      if(!field.matches('input,textarea,select,button,a'))field.tabIndex=-1;
      field.focus({preventScroll:true});field.scrollIntoView({block:'center',behavior:'instant'});
    }
  }
  function nativeMessage(field){
    const label=field.labels?.[0]?.textContent.trim()||field.getAttribute('aria-label')||'此欄位';
    if(field.validity.valueMissing)return '請填寫'+label+'，再繼續。';
    if(field.validity.rangeUnderflow)return label+'不可小於 '+field.min+'。';
    if(field.validity.rangeOverflow)return label+'不可大於 '+field.max+'。';
    if(field.validity.stepMismatch)return '請依欄位允許的精度填寫'+label+'。';
    return '請檢查'+label+'的格式，再繼續。';
  }
  document.addEventListener('invalid',event=>{
    event.preventDefault();const first=!nativeFirst;
    if(first){nativeFirst=event.target;queueMicrotask(()=>{nativeFirst=null;});}
    fail(nativeMessage(event.target),event.target,first);
  },true);
  for(const type of ['input','change'])document.addEventListener(type,event=>{clear(event.target);if(event.target.id==='file'&&event.target.files?.length)clear(document.querySelector('#raw'));},true);
  return {fail,clear,summary};
})();
