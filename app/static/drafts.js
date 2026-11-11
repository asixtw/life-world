'use strict';
/** 已保存草稿刪除與未保存修改分開；成功收據後才清理該Owner/草稿素材。 */
window.DraftsUI=(()=>{
 let c,deletion=null,transient=[];
 const key='lifeworld:deleted-draft-media-cleanup';
 function initialize(context){c=context;deletion=null;}
 function owner(){return c.state.me?.owner_id||'';}
 function queue(){let items=[];try{const saved=JSON.parse(localStorage.getItem(key)||'[]');if(Array.isArray(saved))items=saved.filter(x=>typeof x?.owner==='string'&&typeof x?.id==='string');}catch{}return [...new Map([...items,...transient].map(x=>[x.owner+':'+x.id,x])).values()];}
 function remember(item){const items=queue().filter(x=>!(x.owner===item.owner&&x.id===item.id));items.push(item);transient=items;try{localStorage.setItem(key,JSON.stringify(items));}catch{c.toast('瀏覽器無法保存素材清理重試，請保持此頁。');}}
 async function retryLocalCleanup(){const who=owner();for(const item of queue().filter(x=>x.owner===who)){try{await MediaUI.clearDraft(item.owner,item.id);transient=queue().filter(x=>!(x.owner===item.owner&&x.id===item.id));try{localStorage.setItem(key,JSON.stringify(transient));}catch{}}catch{return false;}}return true;}
 async function handleClick(action,target){
  if(action==='delete-saved-draft'){
   const d=c.state.world?.drafts.find(d=>d.id===target.dataset.id);if(!d)return true;
   deletion={owner:owner(),id:d.id,revision:d.revision,requestId:c.newId()};
   c.dialog(`<h2 id="account-heading">刪除已保存草稿？</h2><p>${c.esc(d.raw_text.slice(0,160))}</p><p>這會刪除伺服器上尚未確認的草稿，並清理這份草稿在本機的素材。不是只捨棄未保存修改，亦不刪除其他草稿或已確認經歷。</p><div class="button-row"><button class="secondary" data-action="close-account">保留草稿</button><button class="danger" data-action="confirm-delete-saved-draft">確認刪除草稿</button></div>`);return true;
  }
  if(action==='confirm-delete-saved-draft'){
   const d=deletion;if(!d||d.owner!==owner())throw new Error('帳號已改變，請重新核對草稿。');
   await c.api('/drafts/'+encodeURIComponent(d.id),{method:'DELETE',body:{request_id:d.requestId,expected_revision:d.revision}});
   let cleaned=true;
   try{remember({owner:d.owner,id:d.id});cleaned=await retryLocalCleanup();}catch{cleaned=false;}
   deletion=null;document.querySelector('#account-dialog').close();
   if(owner()===d.owner){await c.refresh();await c.render();c.toast(cleaned?'已刪除伺服器草稿及這份本機素材。':'伺服器草稿已刪除，但本機素材尚未清理；可重試清理。');}
   return true;
  }
  if(action==='retry-draft-media-cleanup'){c.toast(await retryLocalCleanup()?'本機草稿素材已清理。':'本機清理仍未完成，請稍後重試。');return true;}
  return false;
 }
 return {initialize,handleClick,retryLocalCleanup};
})();
