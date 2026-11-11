'use strict';
/** 單一people列表與精簡識別編輯；沿用PR24視覺工具，不搬入Jerry九項人物設定表單。 */
window.PersonsUI=(()=>{
 let c,editing=null;
 const types=[['','未指定（儲存為真實類型）'],['real','真實類型（含預設）'],['historical','歷史'],['fictional','虛構'],['original','自創']];
 const categories=[['','全部'],['business','商務'],['life','生活'],['learning','學習'],['other','其他']];
 const h=v=>c.esc(v),id=v=>encodeURIComponent(v),owner=()=>c.state.me?.owner_id||'';
 function initialize(context){c=context;editing=null;}
 function options(items,value){return items.map(([k,t])=>`<option value="${h(k)}"${value===k?' selected':''}>${h(t)}</option>`).join('');}
 function route(filter,offset){const p=new URLSearchParams();for(const key of ['q','type','category','status','sort'])if(filter[key]&&filter[key]!==({status:'active',sort:'priority'}[key]))p.set(key,filter[key]);if(offset)p.set('offset',offset);return 'persons'+(p.size?'?'+p:'');}
 async function list(params=new URLSearchParams()){
  const ticket=owner(),filter=Object.fromEntries(['q','type','category','status','sort'].map(k=>[k,params.get(k)||({status:'active',sort:'priority'}[k]||'')]));
  let offset=Math.max(0,Math.floor((Number(params.get('offset'))||0)/50)*50);
  const fetchPage=o=>{const q=new URLSearchParams({q:filter.q,person_type:filter.type,category:filter.category,status:filter.status,sort:filter.sort,limit:50,offset:o});return c.api('/persons?'+q);};
  let data=await fetchPage(offset);if(owner()!==ticket)return '';
  if(offset&&offset>=data.total){offset=data.total?Math.floor((data.total-1)/50)*50:0;data=await fetchPage(offset);const corrected=route(filter,offset);history.replaceState(null,'','#'+corrected);c.state.route=corrected;}
  const cards=data.items.map(p=>`<article class="card char-card persons-list-card"><a class="persons-card-open" href="#persons/${id(p.id)}"><h3>${h(p.name)}</h3><p>${h(p.description||'可以隨著真實經歷，逐步補充了解。')}</p><span class="tag">${h(types.find(([k])=>k===(p.person_subtype||p.person_type))?.[1]||'真實類型（含預設）')}</span>${p.status==='archived'?'<span class="tag">已封存</span>':''}</a></article>`).join('');
  return c.heading('人物','每位人物只有一份主檔；參與、互動與提及分開記錄。',c.link('persons-new','新增人物','primary'))+`<form id="persons-filter-form" class="card stack space-bottom"><div class="field"><label>搜尋<input name="q" value="${h(filter.q)}" maxlength="200"></label></div><div class="button-row"><label>人物類型<select name="type">${options([['','全部'],...types.slice(1)],filter.type)}</select></label><label>分類<select name="category">${options(categories,filter.category)}</select></label><label>狀態<select name="status">${options([['active','使用中'],['archived','已封存']],filter.status)}</select></label><label>排序<select name="sort">${options([['priority','關注優先'],['name','姓名'],['recent','最近']],filter.sort)}</select></label><button class="primary" type="submit">套用</button></div></form><div class="grid">${cards||c.empty('還沒有人物，可以稍後在經歷中加入。')}</div><nav class="button-row space-top" aria-label="人物分頁"><span>共 ${data.total} 位 · 第 ${offset/50+1}／${Math.max(1,Math.ceil(data.total/50))} 頁</span>${offset?c.link(route(filter,offset-50),'上一頁'):''}${offset+50<data.total?c.link(route(filter,offset+50),'下一頁'):''}</nav>`;
 }
 function identityForm(p=null){return `<form id="persons-edit-form" class="card narrow"><div class="field"><label for="identity-name">稱呼／姓名</label><input id="identity-name" name="name" maxlength="100" required value="${h(p?.name||'')}"></div><details><summary>選填識別資訊</summary><div class="field"><label>別名（以逗號分隔）<input name="aliases" value="${h((p?.aliases||[]).join('、'))}" maxlength="2000"></label></div><div class="field"><label>人物類型<select name="person_type">${options(types,p?.person_subtype||p?.person_type||'')}</select></label></div><div class="field"><label>背景簡介<textarea name="description" maxlength="2000">${h(p?.description||'')}</textarea></label></div></details><p class="small muted">人物類型由後端驗證；標籤不會決定真人互動或獎勵。</p><button type="submit" class="primary">保存人物</button></form>`;}
 function createForm(){editing={owner:owner(),requestId:null};return c.link('persons','← 返回人物列表','text-button')+c.heading('新增人物','先留下稱呼，其餘都可稍後補充。')+identityForm();}
 async function editForm(pid){const ticket=owner(),data=await c.api('/persons/'+id(pid));if(owner()!==ticket)return '';const p=data.person;if(p.status==='archived'){editing=null;return c.empty('這位人物已封存，不能修改。',c.link('persons/'+id(pid),'返回人物詳細頁'));}editing={owner:ticket,id:p.id,revision:p.revision,requestId:null};return c.link('persons/'+id(pid),'← 返回人物','text-button')+c.heading('編輯人物',p.name)+identityForm(p);}
 async function handleSubmit(form){
  if(form.id==='persons-filter-form'){const f=new FormData(form);c.navigate(route(Object.fromEntries(f),0));return true;}
  if(form.id!=='persons-edit-form')return false;
  if(!editing||editing.owner!==owner())throw new Error('帳號已改變，請重新載入人物。');
  const f=new FormData(form),kind=f.get('person_type'),body={name:String(f.get('name')).trim(),aliases:String(f.get('aliases')||'').split(/[、,，\n]/).map(x=>x.trim()).filter(Boolean),description:String(f.get('description')||''),person_type:['fictional','original'].includes(kind)?'fictional':'real',person_subtype:['historical','original'].includes(kind)?kind:null};
  editing.requestId=editing.requestId||c.requestId('person');
  const p=editing.id?await c.api('/persons/'+id(editing.id),{method:'PATCH',body:{...body,expected_revision:editing.revision}}):await c.api('/persons',{method:'POST',body:{...body,request_id:editing.requestId}});
  c.state.dirty=false;await c.refresh();c.navigate('persons/'+p.id);return true;
 }
 return {initialize,list,createForm,editForm,handleSubmit};
})();
