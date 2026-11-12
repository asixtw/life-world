'use strict';
/** 四步第三步的人物選擇視圖；沿用StoryInput，不推斷參與、互動或同名身分。 */
window.ExperiencePeopleUI=(()=>{
  let c;
  const roles={interaction:'實際參與並直接互動',participant:'共同參與但未直接互動',mention:'僅在原文中提及'};
  const esc=v=>c.esc(v);
  function initialize(context){c=context;}
  function person(id){return c.state.world.people.find(p=>p.id===id);}
  // 類型限制只是UI引導；正式身分/參與資格仍由後端獨立驗證。
  function roleOptions(id,value){
    const p=person(id),real=p?.person_type!=='fictional'&&p?.person_subtype!=='historical';
    return '<option value="">請選擇本次角色</option>'+Object.entries(roles).filter(([k])=>real||k==='mention'||k===value).map(([k,v])=>`<option value="${k}" ${value===k?'selected':''}>${v}</option>`).join('');
  }
  // 同名人物仍以ID定向；識別資訊只取自目前Owner已可讀的人物。
  function identity(p){return [...(p.roles||[]),p.common_context||'', c.state.world.people.filter(x=>x.name===p.name).length>1?'識別 '+p.id.slice(-8):''].filter(Boolean).join(' · ');}
  function option(p){return `<button type="button" class="person-search-row" data-workflow-pick="${esc(p.id)}" data-search="${esc((p.name+' '+identity(p)).normalize('NFKC').toLowerCase())}"><span class="person-search-avatar" aria-hidden="true">${esc([...p.name][0]||'人')}</span><span class="person-search-copy"><strong>${esc(p.name)}</strong><small>${esc(identity(p))}</small></span><span data-person-selected class="tag" hidden>已選擇</span><span aria-hidden="true">＋</span></button>`;}
  function row(p){
    const known=person(p.person_id);
    return `<article class="card space-top" data-workflow-person data-row-key="${esc(p.key||crypto.randomUUID())}" data-person-id="${esc(p.person_id)}"><strong>${esc(known?.name||'目前無法讀取的人物')}</strong>${known?`<p class="small muted">${esc(identity(known))}</p>`:''}${known?.status==='archived'?'<p class="callout">人物已封存，請移除此關聯或返回人物頁處理，不會自動變更。</p>':''}<label class="field">本次角色<select data-workflow-role>${roleOptions(p.person_id,p.relation)}</select></label><div data-workflow-mention ${p.relation==='mention'?'':'hidden'}><label class="field">原文中的稱呼<input data-workflow-name maxlength="100" value="${esc(p.source_name||known?.name||'')}"></label><label class="field">核對原文位置<select data-workflow-start data-start="${p.start??''}"></select></label><p class="small muted">只保留提及來源，不計見面或直接互動。</p></div><button type="button" class="text-button" data-workflow-remove>移除此關聯</button></article>`;
  }
  function editor(story){
    const rows=[...(story?.participants||[]).map(p=>({person_id:p.person_id,relation:p.interacted?'interaction':'participant'})),...(story?.mentions||[]).filter(m=>m.person_id).map(m=>({person_id:m.person_id,relation:'mention',source_name:m.name,start:m.start}))];
    const pending=story?.pending_people?.length?story.pending_people:story?.pending_person?[{...story.pending_person,client_ref:'legacy'}]:[];
    const available=c.state.world.people.filter(p=>p.status!=='archived');
    return `<section class="story-editor" data-story-editor data-compact="true" data-mode="record"><label class="check-line"><input id="include-story" name="include_story" type="checkbox" ${story?'checked':''}>這次有相關人物（沒有可直接下一步）</label><div class="button-row"><button type="button" class="secondary" data-workflow-open>選擇既有人物</button><button type="button" class="secondary" data-action="new-person">＋ 新增人物</button></div><div class="story-editor-body" ${story?'':'hidden'}><input type="hidden" id="workflow-existing-people" name="workflow_existing_people"><section class="card space-top" data-workflow-picker hidden><label class="field">搜尋自己的人物<input data-workflow-search placeholder="搜尋人物姓名或角色"></label><div data-workflow-options>${available.map(option).join('')||'<p>尚未有人物，可選擇新增。</p>'}</div><p class="small" data-workflow-no-match hidden>找不到相符人物；可以關閉後新增。</p><button type="button" class="text-button" data-workflow-picker-close>關閉選擇</button></section><div data-workflow-people>${rows.map(row).join('')}</div>${c.pending(pending)}<details class="space-top" data-workflow-extra><summary>其他原文稱呼與故事標題（選填）</summary><label class="field">故事標題<input id="story-title" name="story_title" maxlength="160" value="${esc(story?.title||'')}"></label><div class="story-mention-rows">${(story?.mentions||[]).filter(m=>!m.person_id).map(c.mention).join('')}</div><button type="button" class="text-button" data-cx="add-mention">只記錄原文中的稱呼</button><p class="small muted">尚未選定人物的名字只保留來源，不自動建人或合併同名人物。</p></details></div></section>`;
  }
  function rows(root){return [...root.querySelectorAll('[data-workflow-person]')].map(n=>({key:n.dataset.rowKey,person_id:n.dataset.personId,relation:n.querySelector('[data-workflow-role]').value,source_name:n.querySelector('[data-workflow-name]').value,start:n.querySelector('[data-workflow-start]').value===''?null:Number(n.querySelector('[data-workflow-start]').value)}));}
  // 保留已明確選擇的Unicode位置；無有效位置時留空，不改選第一個同名片段。
  function updateMention(n){
    const root=n.closest('[data-compact]'),input=n.querySelector('[name=mention_name]'),select=n.querySelector('[name=mention_start]'),previous=select.value||select.dataset.start;
    select.innerHTML='<option value="">請選擇原文位置</option>'+c.spans(c.raw(root),input.value).map(x=>'<option value="'+x.start+'" '+(String(previous)===String(x.start)?'selected':'')+'>'+esc(x.label)+'</option>').join('');delete select.dataset.start;
  }
  function hydrate(root){
    if(!root?.dataset.compact)return;
    for(const n of root.querySelectorAll('[data-workflow-person]')){
      const isMention=n.querySelector('[data-workflow-role]').value==='mention',select=n.querySelector('[data-workflow-start]'),previous=select.value||select.dataset.start;
      n.querySelector('[data-workflow-mention]').hidden=!isMention;
      select.innerHTML='<option value="">請選擇原文位置</option>'+c.spans(c.raw(root),n.querySelector('[data-workflow-name]').value).map(x=>`<option value="${x.start}" ${String(previous)===String(x.start)?'selected':''}>${esc(x.label)}</option>`).join('');delete select.dataset.start;
    }
    const selectedIds=new Set(rows(root).map(p=>p.person_id));
    root.querySelectorAll('[data-workflow-pick]').forEach(n=>{n.querySelector('[data-person-selected]').hidden=!selectedIds.has(n.dataset.workflowPick);});
    root.querySelectorAll('.story-mention-editor').forEach(updateMention);
    const pending=root.querySelector('.pending-people-summary');if(pending)pending.hidden=!pending.querySelector('[data-pending-target]');
  }
  /** 將視圖投影回原StoryInput；validate=false允許本機未完成狀態，不寫DB或改角色。 */
  function collect(root,validate){
    hydrate(root);const participants=[],mentions=[];
    for(const p of rows(root)){
      if(validate&&!Object.hasOwn(roles,p.relation))throw new Error('請選擇每位人物的本次角色，或移除此關聯。');
      if(p.relation==='mention'){
        const text=[...c.raw(root)],name=[...p.source_name];
        if(validate&&(!name.length||p.start===null||text.slice(p.start,p.start+name.length).join('')!==p.source_name))throw new Error('請核對提及人物的稱呼與原文位置。');
        mentions.push({person_id:p.person_id,name:p.source_name,start:p.start??-1,end:p.start===null?-1:p.start+name.length});
      }else if(p.relation){
        if(validate&&participants.some(x=>x.person_id===p.person_id))throw new Error('同一人物的參與角色請保留一份；另一處提及可獨立記錄。');
        participants.push({person_id:p.person_id,interacted:p.relation==='interaction'});
      }
    }
    for(const n of root.querySelectorAll('.story-mention-editor')){
      const name=n.querySelector('[name=mention_name]').value,start=n.querySelector('[name=mention_start]').value;
      if(validate&&(!name||start===''))throw new Error('請核對原文稱呼與位置。');
      mentions.push({name,person_id:null,start:start===''?-1:Number(start),end:start===''?-1:Number(start)+[...name].length});
    }
    const pending=c.collectPending(root,validate);
    if(validate&&!participants.length&&!mentions.length&&!pending.length)throw new Error('請選擇或新增人物，或取消「這次有相關人物」。');
    return {title:root.querySelector('#story-title').value,participants,mentions,...(pending.length?{pending_people:pending}:{})};
  }
  function changed(root){c.state.dirty=true;hydrate(root);root.dispatchEvent(new Event('change',{bubbles:true}));}
  function persist(form){
    const root=form?.querySelector('[data-compact]'),field=root?.querySelector('#workflow-existing-people');if(field)field.value=JSON.stringify({owner_id:c.state.me.owner_id,rows:rows(root)});
  }
  /** 只恢復同Owner的有限本機行資料；格式不符保留原始素材，避免猜測或覆蓋。 */
  function restore(form){
    const root=form?.querySelector('[data-compact]'),field=root?.querySelector('#workflow-existing-people');if(!field?.value)return;
    try{const saved=JSON.parse(field.value);if(saved.owner_id!==c.state.me.owner_id||!Array.isArray(saved.rows)||saved.rows.length>200||new Set(saved.rows.map(x=>x?.key)).size!==saved.rows.length||!saved.rows.every(x=>x&&typeof x.person_id==='string'&&x.person_id.length>0&&x.person_id.length<=128&&typeof x.key==='string'&&x.key.length>0&&x.key.length<=128&&['',...Object.keys(roles)].includes(x.relation)&&typeof x.source_name==='string'&&x.source_name.length<=100&&(x.start===null||Number.isSafeInteger(x.start)&&x.start>=0)))throw new Error();root.querySelector('[data-workflow-people]').innerHTML=saved.rows.map(row).join('');hydrate(root);}catch{c.toast('本機人物關聯無法安全還原；原文與素材仍保留，請勿覆蓋。');}
  }
  document.addEventListener('click',event=>{
    const root=event.target.closest('[data-compact]');if(!root)return;
    if(event.target.closest('[data-workflow-open]')){root.querySelector('#include-story').checked=true;root.querySelector('.story-editor-body').hidden=false;root.querySelector('[data-workflow-picker]').hidden=false;root.querySelector('[data-workflow-search]').focus();changed(root);}
    const selected=event.target.closest('[data-workflow-pick]');if(selected){if(root.querySelectorAll('[data-workflow-person]').length>=200){c.toast('本次人物關聯已達容量，現有輸入保留；請先移除不需要的關聯。');return;}root.querySelector('[data-workflow-people]').insertAdjacentHTML('beforeend',row({person_id:selected.dataset.workflowPick,relation:''}));root.querySelector('[data-workflow-picker]').hidden=true;changed(root);root.querySelector('[data-workflow-person]:last-child [data-workflow-role]').focus();}
    if(event.target.closest('[data-workflow-picker-close]')){root.querySelector('[data-workflow-picker]').hidden=true;root.querySelector('[data-workflow-open]').focus();}
    const remove=event.target.closest('[data-workflow-remove]');if(remove){remove.closest('[data-workflow-person]').remove();changed(root);}
  });
  document.addEventListener('input',event=>{
    const root=event.target.closest('[data-compact]');if(!root)return;
    if(event.target.matches('[data-workflow-search]')){const q=event.target.value.normalize('NFKC').toLowerCase();const buttons=[...root.querySelectorAll('[data-workflow-pick]')];buttons.forEach(n=>n.hidden=!n.dataset.search.includes(q));root.querySelector('[data-workflow-no-match]').hidden=buttons.some(n=>!n.hidden);}
    if(event.target.matches('[data-workflow-name]')){event.target.closest('[data-workflow-person]').querySelector('[data-workflow-start]').value='';hydrate(root);}
  });
  document.addEventListener('change',event=>{if(event.target.matches('[data-workflow-role]'))hydrate(event.target.closest('[data-compact]'));});
  return {initialize,editor,collect,hydrate,persist,restore,updateMention};
})();
