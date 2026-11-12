'use strict';
/** R2輸入資訊架構：移動/隱藏既有DOM，不複製媒體、草稿或AI交易。 */
window.MomentUI=(()=>{
  let c,form;
  function initialize(context){c=context;}
  function mount(node,initialMode='manual'){
    form=node;const step=node.querySelector('[data-experience-step="1"]');if(!step)return;
    const raw=node.elements.raw_text,text=raw.closest('.field'),media=node.querySelector('#media-panel');
    text.dataset.momentText='true';text.classList.add('moment-text');
    step.insertAdjacentHTML('afterbegin','<div class="moment-tabs" role="tablist" aria-label="記錄方式">'+[['text','文字'],...(c.state.me.status==='registered'?[['photo','拍照／影像'],['audio','語音']]:[])].map(([key,label])=>`<button type="button" role="tab" id="moment-tab-${key}" data-moment-tab="${key}" aria-controls="${key==='text'?'moment-panel-text':'media-panel'}">${label}</button>`).join('')+'</div><input type="hidden" name="moment_input_tab" value="text">');
    text.id='moment-panel-text';text.setAttribute('role','tabpanel');text.setAttribute('aria-labelledby','moment-tab-text');
    if(media)media.setAttribute('role','tabpanel');
    const time=node.querySelector('#occurred-at').closest('.field');
    const details=document.createElement('details');details.dataset.momentTime='true';details.innerHTML='<summary>發生時間 · <span data-moment-time-label></span></summary>';
    time.before(details);details.append(time);time.insertAdjacentHTML('beforeend','<p data-moment-time-error role="alert" hidden></p>');
    node.querySelector('[data-moment-time-error]').id='moment-time-error';node.elements.occurred_at.setAttribute('aria-describedby','moment-time-error');
    const feedback=document.createElement('div');feedback.className='moment-sources';feedback.setAttribute('role','status');feedback.dataset.momentSources='true';details.before(feedback);
    const ai=!!c.state.capabilities?.ai_available&&c.state.me.status==='registered';
    step.insertAdjacentHTML('beforeend',`<fieldset class="moment-organize"><legend>這段經歷要怎麼整理？</legend><label class="choice"><input type="radio" name="moment_ai_mode" value="manual" checked>直接使用我的原文<span>預設手動，不傳送給模型。</span></label><label class="choice"><input type="radio" name="moment_ai_mode" value="ai" ${ai?'':'disabled'}>使用 AI 整理這段經歷<span>${ai?'保存候選草稿後，於第四步接續既有授權與整理。':'AI 目前未開放；仍可完成手動記錄。'}</span></label><p class="small muted">選擇AI不是授權；送出原文前仍需核對提供者、範圍及用途。</p></fieldset>`);
    node.elements.moment_ai_mode.value=ai&&initialMode==='ai'?'ai':'manual';
    node.addEventListener('input',sync);node.addEventListener('change',sync);
    node.addEventListener('invalid',event=>{
      if(event.target===raw){node.elements.moment_input_tab.value='text';sync();}
      if(event.target===node.elements.occurred_at||event.target===node.elements.calendar_time)details.open=true;
    },true);
    sync();
  }
  function sync(){
    if(!form?.isConnected)return;
    const tab=form.elements.moment_input_tab?.value||'text',media=form.querySelector('#media-panel');
    form.querySelector('[data-moment-text]').hidden=tab!=='text';
    form.querySelectorAll('[data-moment-tab]').forEach(n=>{const on=n.dataset.momentTab===tab;n.setAttribute('aria-selected',String(on));n.tabIndex=on?0:-1;});
    if(media){
      media.hidden=tab==='text';media.id='media-panel';media.setAttribute('aria-labelledby','moment-tab-'+tab);media.setAttribute('aria-label',tab==='audio'?'語音素材':'拍照與影像素材');
      media.querySelectorAll('[data-media-file]').forEach(n=>{n.closest('label').hidden=(n.dataset.mediaFile==='audio')!==(tab==='audio');});
      media.querySelectorAll('[data-media-kind]').forEach(n=>n.hidden=(n.dataset.mediaKind==='audio')!==(tab==='audio'));
      const recorder=media.querySelector('.media-recorder');if(recorder){recorder.hidden=tab!=='audio';if(tab==='audio')recorder.open=true;}
      // 長篇技術限制收合；保留原生媒體實作與每項素材的校對入口。
      const panel=media.querySelector('.media-panel');
      if(panel&&!panel.querySelector('[data-moment-media-policy]')){
        const policy=[...panel.children].filter(n=>n.tagName==='P'&&n.id!=='media-storage').pop();
        if(policy){const d=document.createElement('details');d.dataset.momentMediaPolicy='true';d.innerHTML='<summary>素材保留與容量說明</summary>';policy.before(d);d.append(policy);}
      }
    }
    const text=form.elements.raw_text.value,items=[...(media?.querySelectorAll('[data-media-kind]')||[])];
    form.querySelector('[data-moment-sources]').textContent=`文字 · ${text.trim()?text.length+' 字':'尚未輸入'}${items.length?' · 影像 '+items.filter(n=>n.dataset.mediaKind!=='audio').length+' · 語音 '+items.filter(n=>n.dataset.mediaKind==='audio').length:''}｜素材切換不會清除輸入`;
    const value=form.elements.calendar_time?form.elements.calendar_date.value+'T'+form.elements.calendar_time.value:form.elements.occurred_at.value;
    form.querySelector('[data-moment-time-label]').textContent=value.replace('T',' ')||'請選擇實際時間';
    const error=form.querySelector('[data-moment-time-error]');if(error&&!error.hidden){error.hidden=true;form.elements.occurred_at.setCustomValidity('');}
  }
  async function validate(){
    if(!form?.isConnected)return true;
    const input=form.elements.occurred_at,details=form.querySelector('[data-moment-time]'),error=form.querySelector('[data-moment-time-error]');
    try{
      const ownForm=form,owner=c.state.me.owner_id,latest=await c.api('/auth/me');
      if(ownForm!==form||!ownForm.isConnected||owner!==c.state.me.owner_id||latest.owner_id!==owner)return false;
      c.state.me.server_now=latest.server_now;
      const value=form.elements.calendar_time?form.elements.calendar_date.value+'T'+form.elements.calendar_time.value:input.value;
      const iso=c.inputISO(value,form.dataset.calendarZone||c.state.me.timezone);
      if(c.state.me.server_now&&Date.parse(iso)>Date.parse(c.state.me.server_now))throw new Error('不能記錄未來的經歷，請確認實際發生時間。');
      error.hidden=true;input.setCustomValidity('');return true;
    }catch(e){details.open=true;error.textContent=e.message;error.hidden=false;input.focus();return false;}
  }
  document.addEventListener('click',e=>{const tab=e.target.closest('[data-moment-tab]');if(!tab||!form?.contains(tab))return;form.elements.moment_input_tab.value=tab.dataset.momentTab;sync();form.dispatchEvent(new Event('input',{bubbles:true}));});
  document.addEventListener('keydown',e=>{const tab=e.target.closest('[data-moment-tab]');if(!tab||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;const tabs=[...form.querySelectorAll('[data-moment-tab]')],i=tabs.indexOf(tab),next=e.key==='Home'?0:e.key==='End'?tabs.length-1:(i+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;e.preventDefault();tabs[next].click();tabs[next].focus();});
  function revealText(){if(!form?.isConnected)return;form.elements.moment_input_tab.value='text';sync();form.elements.raw_text.focus();}
  return {initialize,mount,sync,validate,revealText};
})();
