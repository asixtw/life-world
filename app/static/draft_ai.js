'use strict';
/** 草稿AI為單一明確選用；有效授權以後端為準，不存本機同意旗標。 */
window.DraftAIUI=(()=>{
  let c,epoch=0,policy=null,mode='manual',attempt=null,flight=null,origin=null,dialogMode=null;
  const esc=v=>c.esc(v);
  function initialize(context){c=context;}
  function scope(){return c.state.me?.owner_id+':'+c.state.draft?.id+':'+c.state.renderGeneration;}
  function valid(token,key){return token===epoch&&key===scope()&&!!document.querySelector('[data-draft-ai]');}
  function root(){return document.querySelector('[data-draft-ai]');}
  function status(text){const n=root()?.querySelector('[data-draft-ai-status]');if(n)n.textContent=text;}
  function render(){
    const registered=c.state.me?.status==='registered';
    return '<fieldset data-draft-ai><legend>如何整理這段經歷？</legend><label class="check-line"><input type="radio" name="draft_ai_mode" value="manual" checked>直接使用我的原文</label><label class="check-line"><input type="radio" name="draft_ai_mode" value="ai" disabled>使用 AI 整理這段經歷</label><p class="small muted">手動摘要與原文保留；AI只提供可編輯候選，最後仍由你確認。</p><p class="small" data-draft-ai-status role="status">'+(registered?'正在確認AI整理是否可用…':'訪客請使用手動記錄；保存世界後可使用已開放的功能。')+'</p><div class="button-row">'+(registered?'<button type="button" class="text-button" data-draft-ai-manage>查看／撤回AI整理授權</button>':'')+'<button type="button" class="secondary" data-draft-ai-retry hidden>再次整理（會使用額度）</button><button type="button" class="text-button" data-action="ai-usage" data-draft-ai-receipts hidden>查看本人用量與收據</button><button type="button" class="text-button" data-draft-ai-recheck hidden>重新確認可用狀態</button></div></fieldset>';
  }
  function dialog(){
    let n=document.querySelector('#draft-ai-consent-dialog');if(n)return n;
    n=document.createElement('dialog');n.id='draft-ai-consent-dialog';n.setAttribute('aria-labelledby','draft-ai-heading');n.innerHTML='<div data-draft-ai-dialog-body></div>';document.body.append(n);
    n.addEventListener('cancel',event=>{event.preventDefault();close(true);});
    n.addEventListener('close',()=>{if(origin?.isConnected)origin.focus();origin=null;});
    return n;
  }
  function clearCandidate(){
    c.state.candidate=null;c.state.aiTasks=[];c.state.aiPeople=[];
    document.querySelector('#candidate-panel')?.replaceChildren();document.querySelector('#ai-people-panel')?.replaceChildren();
  }
  function manual(message){
    epoch++;mode='manual';clearCandidate();
    const input=root()?.querySelector('[value=manual]');if(input)input.checked=true;
    const retry=root()?.querySelector('[data-draft-ai-retry]');if(retry)retry.hidden=true;
    status(message||'目前使用手動摘要，不會呼叫模型。');
  }
  function close(cancel=false){
    const n=document.querySelector('#draft-ai-consent-dialog');if(n?.open)n.close();
    if(cancel&&dialogMode==='request')manual('已維持手動，摘要與原文都保留。');
    dialogMode=null;
  }
  async function metadata(token,key){
    const data=await c.api('/ai/draft-consent');if(!valid(token,key))return null;
    policy=data;root().querySelector('[value=ai]').disabled=!data.available;
    return data;
  }
  async function mount(){
    epoch++;policy=null;mode='manual';attempt=null;flight=null;
    if(document.querySelector('#draft-ai-consent-dialog')?.open)close(false);
    if(!root())return;
    clearCandidate();if(c.state.me?.status!=='registered')return;
    const token=epoch,key=scope();
    try{const data=await metadata(token,key);if(!data)return;status(data.available?'可選用AI整理；尚未傳送原文。':'AI整理目前未開放，可繼續手動記錄。');}
    catch{if(valid(token,key)){status('暫時無法確認AI可用狀態，原文與摘要保留。');root().querySelector('[data-draft-ai-recheck]').hidden=false;}}
  }
  function disclosure(data,kind){
    dialogMode=kind;origin=document.activeElement;const n=dialog();
    const body=n.querySelector('[data-draft-ai-dialog-body]');
    body.innerHTML='<h2 id="draft-ai-heading" tabindex="-1">'+(kind==='request'?'使用AI前，先確認資料用途':'AI整理授權')+'</h2><p>服務提供者：'+esc(data.provider_label)+'</p><p>傳送範圍：本篇草稿原文與固定整理指令；用於摘要、後續任務及原文明示的人物資訊候選。</p><p>不傳送其他人物檔案、媒體或背景記憶。背景AI授權不涵蓋這份草稿；此操作不會把資料加入Life World訓練集。</p><p>結果仍需你編輯並人工確認；未套用的候選不會正式保存。撤回不會取消已送出的請求。</p><p data-draft-ai-dialog-status role="status">'+(data.consent_status==='unavailable'?'目前無法安全確認／撤回這項授權。':data.granted?'相同提供者及範圍的授權有效。':data.has_consent?'既有授權不適用目前提供者或範圍。':'目前尚未取得這個用途的授權。')+'</p><div class="button-row">'+(kind==='request'&&data.available?'<button type="button" class="primary" data-draft-ai-approve>同意並整理</button>':'')+(data.has_consent&&data.can_revoke?'<button type="button" class="danger" data-draft-ai-revoke>撤回這項授權</button>':'')+'<button type="button" class="secondary" data-draft-ai-close>'+(kind==='request'?'維持手動':'關閉')+'</button></div>';
    if(!n.open)n.showModal();body.querySelector('h2').focus();
  }
  async function choose(){
    if(!root()||c.state.me?.status!=='registered')return;
    const token=++epoch,key=scope();mode='ai';attempt=null;status('正在確認授權…');
    try{
      const data=await metadata(token,key);if(!data)return;
      if(!data.available){manual('AI整理目前未開放，已保留手動摘要。');return;}
      if(data.granted)await run();else disclosure(data,'request');
    }catch(error){if(valid(token,key))manual('無法確認授權：'+error.message+' 原文與摘要保留。');}
  }
  async function approve(button){
    const token=epoch,key=scope(),expected=policy;if(!expected||!valid(token,key))return;
    button.disabled=true;
    try{
      await c.api('/ai/draft-consent',{method:'POST',body:{request_id:c.id(),policy_fingerprint:expected.policy_fingerprint,confirmed:true}});
      const data=await metadata(token,key);if(!data)return;
      if(!data.granted)throw new Error('授權尚未生效，請重新核對。');
      close(false);await run();
    }catch(error){if(valid(token,key)){const n=dialog().querySelector('[data-draft-ai-dialog-status]');if(n)n.textContent=error.message+' 原文與摘要保留，沒有自動呼叫模型。';}}
    finally{if(button.isConnected)button.disabled=false;}
  }
  async function run(retry=false){
    if(mode!=='ai'||!policy?.granted)return;
    if(flight?.key===scope()){status('先前請求仍在處理；等待完成後可明確重試，或維持手動。');root().querySelector('[data-draft-ai-retry]').hidden=false;return;}
    const token=epoch,key=scope(),draftId=c.state.draft.id,sourceRevision=c.state.draft.revision,sourceHash=c.state.draft.raw_sha256;
    // 未知傳輸結果沿用識別碼；已知失敗需使用者主動重試，保留原預留收據。
    if(!retry||!attempt||attempt.knownFailure)attempt={id:c.id(),knownFailure:false};
    const activeFlight={key,token};flight=activeFlight;status('AI整理中；原文與手動摘要仍保留。');
    const retryButton=root().querySelector('[data-draft-ai-retry]');retryButton.hidden=true;
    try{
      const result=await c.api('/drafts/'+draftId+'/suggest',{method:'POST',headers:{'Idempotency-Key':attempt.id,'X-Draft-Revision':String(sourceRevision)}});
      if(!valid(token,key)||mode!=='ai')return;
      // 不把舊版本或停用後的手動fallback冒稱為這份原文的AI結果。
      if(result.source_revision!==sourceRevision||result.source_sha256!==sourceHash){manual('來源版本無法核對，請重新讀取草稿；原文與手動摘要保留。');return;}
      c.onCandidate(result);attempt=null;status('候選已備妥，尚未取代摘要或正式保存。');
      retryButton.textContent='再次整理（會使用額度）';retryButton.hidden=false;
    }catch(error){
      if(!valid(token,key)||mode!=='ai')return;
      if(error.code==='draft_ai_consent_required'||error.code==='ai_consent_permission_missing'||error.code==='source_revision_conflict'){manual(error.message+' 原文與摘要保留。');return;}
      attempt.knownFailure=error.status===502;
      status(error.message+' 可維持手動；失敗或未知費用不當作零。');
      retryButton.textContent=attempt.knownFailure?'重試AI整理（會使用新額度）':'重試AI整理';retryButton.hidden=error.code==='ai_request_already_reserved';root().querySelector('[data-draft-ai-receipts]').hidden=error.code!=='ai_request_already_reserved';
    }finally{if(flight===activeFlight)flight=null;}
  }
  document.addEventListener('change',event=>{
    if(event.target.name!=='draft_ai_mode')return;
    if(event.target.value==='manual')manual(flight?.key===scope()?'已返回手動；已送出的請求仍可能計入預留，晚回應不會套用。':null);else choose();
  });
  document.addEventListener('click',async event=>{
    const button=event.target.closest('[data-draft-ai-manage],[data-draft-ai-approve],[data-draft-ai-revoke],[data-draft-ai-close],[data-draft-ai-retry],[data-draft-ai-recheck]');if(!button||button.disabled)return;
    if(button.hasAttribute('data-draft-ai-close')){close(true);return;}
    if(button.hasAttribute('data-draft-ai-approve')){await approve(button);return;}
    if(button.hasAttribute('data-draft-ai-retry')){await run(true);return;}
    const token=epoch,key=scope();button.disabled=true;
    try{
      if(button.hasAttribute('data-draft-ai-revoke')){await c.api('/ai/draft-consent',{method:'DELETE'});if(valid(token,key)){close(false);manual('已撤回此用途授權，原文與摘要保留。');policy=null;}return;}
      const data=await metadata(token,key);if(!data)return;
      if(button.hasAttribute('data-draft-ai-manage'))disclosure(data,'manage');
      else{root().querySelector('[data-draft-ai-recheck]').hidden=true;status(data.available?'AI可選用；目前仍是手動。':'AI整理目前未開放，可繼續手動記錄。');}
    }catch(error){if(valid(token,key)){if(document.querySelector('#draft-ai-consent-dialog')?.open)dialog().querySelector('[data-draft-ai-dialog-status]').textContent=error.message+' 原文與摘要保留。';else status(error.message+' 原文與摘要保留。');}}
    finally{if(button.isConnected)button.disabled=false;}
  });
  return {initialize,render,mount,choose};
})();
