'use strict';
/** 素材容器：元件只顯示狀態，麥克風、IndexedDB 與傳輸由此模組管理。 */
const MediaUI = (() => {
  let ctx, active = null, recorder = null, recordingSession = null, stream = null;
  let permissionToken = 0, timer = null, elapsed = 0, recorderMessage = '', pending = Promise.resolve();
  let maxBytes = 5 * 1024 * 1024, available = false;
  const sessions = new Map(), urls = new Set(), requests = new Map();
  const dbPromise = () => new Promise((resolve, reject) => {
    const request = indexedDB.open('lifeworld-media-local', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('workspaces');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error('本機資料庫被其他分頁鎖定'));
  });
  async function storage(key, value, remove = false) {
    const db = await dbPromise();
    try {
      return await new Promise((resolve, reject) => {
        const tx = db.transaction('workspaces', value !== undefined || remove ? 'readwrite' : 'readonly');
        const store = tx.objectStore('workspaces');
        const request = remove ? store.delete(key) : value === undefined ? store.get(key) : store.put(value, key);
        tx.oncomplete = () => resolve(request.result);
        tx.onerror = () => reject(tx.error);
        tx.onabort = () => reject(tx.error || new Error('本機保存已中斷'));
      });
    } finally { db.close(); }
  }
  function storageStatus(session, message) {
    session.storageMessage = message;
    if (active === session && document.querySelector('#media-storage')) document.querySelector('#media-storage').textContent = message;
  }
  function persist(session = active) {
    if (!session) return Promise.resolve();
    const snapshot = structuredClone({items: session.items, fields: session.fields, serverRevision:session.serverRevision});
    const revision = session.saveRevision = (session.saveRevision || 0) + 1;
    storageStatus(session, '正在保存到此裝置…');
    // 排隊寫入快照，避免較慢的舊請求蓋掉較新的校對文字。
    pending = pending.catch(() => {}).then(() => revision === session.saveRevision ? storage(session.key, snapshot) : undefined).then(() => {
      if (revision === session.saveRevision) {session.storedRevision=revision; storageStatus(session, '已保存在此裝置；尚未同步至其他裝置。');}
    }).catch(() => storageStatus(session, '本機保存失敗，請保持此頁並另行保留素材；重新整理可能遺失。'));
    return pending;
  }
  function capture() {
    if (!active || active.readOnly) return;
    const form = document.querySelector('#record-form');
    if (!form) return;
    active.fields = [...form.querySelectorAll('input,textarea,select')]
      .filter(node => node.type !== 'file' && !node.closest('#media-panel'))
      .map(node => ({id: node.id, name: node.name, value: node.value, checked: node.checked, type: node.type}));
    persist();
  }
  function restoreFields(session) {
    if (session.readOnly || !session.fields?.length) return;
    const form = document.querySelector('#record-form');
    const selectedGoal = session.fields.find(f => f.name === 'goal_id');
    if (selectedGoal && form) {
      const target = document.querySelector('#goal-id');
      if (target) {target.value = selectedGoal.value; const fields=document.querySelector('#contribution-fields'); if(fields)fields.innerHTML=ctx.contributionFields(ctx.state.world.goals.find(g=>g.id===selectedGoal.value));}
    }
    for (const field of session.fields) {
      const node = field.id ? document.getElementById(field.id) : [...(form?.elements || [])].find(n => n.name === field.name && n.value === field.value);
      if (!node || node.closest('#media-panel')) continue;
      if (field.type === 'checkbox' || field.type === 'radio') node.checked = field.checked;
      else node.value = field.value;
    }
  }
  function releaseURLs() { for (const url of urls) URL.revokeObjectURL(url); urls.clear(); }
  function fileURL(blob) { const url = URL.createObjectURL(blob); urls.add(url); return url; }
  function controls() {
    return `<div class="media-inputs" role="group" aria-label="新增紀錄素材">${[['image','圖片'],['screenshot','截圖'],['camera','拍照'],['card','名片'],['audio','音檔']].map(([kind,label]) => `<label class="secondary media-file">${label}<input type="file" data-media-file="${kind}" accept="${kind==='audio'?'audio/wav,audio/x-wav,audio/webm,audio/ogg,audio/mp4,audio/mpeg':'image/png,image/jpeg'}" ${kind==='camera'?'capture="environment"':''} aria-label="${label}"></label>`).join('')}</div>`;
  }
  function itemView(item) {
    const e = ctx.esc, busy = requests.has(item.id), isCard = item.kind === 'card';
    const label = item.kind === 'audio' ? '上傳並轉文字' : '上傳並辨識文字';
    const source = item.kind === 'audio' ? `<audio controls preload="metadata" src="${fileURL(item.blob)}" aria-label="選擇性試聽錄音"></audio>` : `<img src="${fileURL(item.blob)}" alt="所選${isCard?'名片':'圖片'}的本機預覽">`;
    return `<article class="media-item" data-media-id="${e(item.id)}"><h3>${e(item.name)}</h3><p class="small muted">${(item.blob.size/1024).toFixed(1)} KiB · ${e(item.mime)} · ${busy?'正在傳送／辨識，尚未保存正式資料':'原素材僅在此裝置'}</p>${source}${isCard?'<p class="callout">名片只供人物資料校對，不會建立見面、經歷或獎勵。</p>':''}<div class="button-row"><button type="button" class="secondary" data-media="recognize" ${busy?'disabled':''}>${label}</button>${busy?'<button type="button" class="secondary" data-media="cancel-upload">取消辨識</button>':''}<button type="button" class="text-button" data-media="remove">移除此素材</button></div>${busy?'<p role="status">正在上傳或等待辨識回應…</p><progress aria-label="上傳與辨識處理中"></progress>':''}${item.error?`<p class="media-error" role="alert">${e(item.error)}</p>`:''}${item.originalText?`<details><summary>查看未修改的辨識原文</summary><pre class="raw-source">${e(item.originalText)}</pre></details>`:''}<div class="field"><label for="media-text-${e(item.id)}">校對文字</label><textarea id="media-text-${e(item.id)}" data-media-text maxlength="20000" placeholder="可手動輸入；不覆寫原始素材或辨識原文">${e(item.editedText || '')}</textarea></div><label class="check-line"><input type="checkbox" data-media-checked ${item.checked?'checked':''}>我已核對這段文字</label><button type="button" class="secondary" data-media="${isCard?'copy':'apply'}" ${!item.checked||!item.editedText?.trim()||active.readOnly?'disabled':''}>${isCard?'複製已校對文字':'加入經歷文字'}</button>${active.readOnly?'<p class="small muted">此處保留本機來源。修改正式經歷須回到原草稿核對。</p>':''}</article>`;
  }
  function draw() {
    const root = document.querySelector('#media-panel');
    if (!root || !active) return;
    releaseURLs();
    root.innerHTML = `<section class="media-panel" aria-label="紀錄素材"><h2>從不同方式留下經歷</h2><p class="small muted">選取素材不會自動上傳。文字須自行校對；確認前不增加進度或獎勵。</p><p id="media-storage" role="status">${ctx.esc(active.storageMessage || '僅保存在此裝置，尚未同步。')}</p>${active.readOnly?'':controls()+`<details class="media-recorder" ${active.recorderOpen?'open':''}><summary>語音轉文字</summary><p>錄完後再決定是否上傳。試聽可選，不必先播放。</p><p id="recorder-status" role="status">${ctx.esc(recorderMessage || '尚未開始錄音')}</p><div class="button-row"><button type="button" class="secondary" data-media="start" ${recorder||stream||recordingSession?'disabled':''}>開始錄音</button><button type="button" class="secondary" data-media="stop" ${recorder?.state==='recording'?'':'disabled'}>停止錄音</button><button type="button" class="text-button" data-media="cancel-recording" ${recorder||stream||recordingSession?'':'disabled'}>取消錄音</button></div></details>`}<p class="small muted">${available?'辨識服務已設定；送出後仍需人工校對。':'尚未設定辨識服務，可先保留素材並手動輸入。'}目前本機單檔傳輸上限 ${(maxBytes/1024/1024).toFixed(1)} MiB，非正式產品限制。</p><div class="media-items">${active.items.length?active.items.map(itemView).join(''):'<p class="small muted">此裝置尚無連結素材；其他裝置的素材不會自動出現在這裡。</p>'}</div>`;
  }
  async function mount({owner, scope, readOnly = false, revision = null}) {
    const key = owner + ':' + scope;
    const session = sessions.get(key) || {key, items: [], fields: [], readOnly};
    active = session;
    session.readOnly = readOnly;
    sessions.set(key, session);
    await pending;
    if (!session.loaded) {
      try {const saved = await storage(key); if (saved) {session.items=saved.items || []; session.fields=saved.fields || []; session.serverRevision=saved.serverRevision;} session.loaded=true; storageStatus(session,'已保存在此裝置；尚未同步至其他裝置。');}
      catch {storageStatus(session, '本機保存不可用，請保持此頁，重新整理可能遺失素材。');}
    }
    if (active !== session) return;
    // 本機只覆寫同一伺服器版本的未送出表單；新版伺服器原文不能被舊快照蓋掉。
    if (revision !== null && session.serverRevision !== revision) {
      session.fields=[]; session.serverRevision=revision;
      await persist(session);
    }
    if (active !== session) return;
    restoreFields(session);
    draw();
    try {const caps = await ctx.api('/media/capabilities'); if(active!==session)return; maxBytes=caps.max_bytes; available=caps.recognition_available; draw();}
    catch {if(active===session) storageStatus(session,'無法取得辨識能力，素材仍保留在此裝置。');}
  }
  async function renderDrafts(owner) {
    const root=document.querySelector('#media-local-drafts');
    if(!root)return;
    await pending;
    let db;
    try {
      db=await dbPromise();
      const records=await new Promise((resolve,reject)=>{
        const tx=db.transaction('workspaces','readonly'), out=[];
        const request=tx.objectStore('workspaces').openCursor();
        request.onsuccess=()=>{const cursor=request.result; if(!cursor)return; if(String(cursor.key).startsWith(owner+':new:'))out.push({key:cursor.key,value:cursor.value}); cursor.continue();};
        tx.oncomplete=()=>resolve(out); tx.onerror=()=>reject(tx.error);
      });
      if(!root.isConnected||ctx.state.me?.owner_id!==owner)return;
      const drafts=records.filter(r=>r.value.items?.length||r.value.fields?.some(f=>f.name==='raw_text'&&f.value.trim()));
      root.innerHTML=drafts.length?`<section class="card space-bottom"><h2>此裝置尚未整理的草稿</h2><p class="small muted">以下內容尚未存成伺服器經歷草稿，不計進度與獎勵。</p>${drafts.map(r=>`<p><a class="text-button" href="#${ctx.esc(r.key.slice((owner+':new:').length))}">接續素材草稿 · ${r.value.items?.length||0} 個素材</a></p>`).join('')}</section>`:'';
    } catch {if(root.isConnected)root.textContent='此裝置草稿暫時無法讀取；已保存的伺服器經歷不受影響。';}
    finally {db?.close();}
  }
  async function addFile(file, kind, session = active) {
    if (!session || !file) return;
    const mime = file.type.split(';')[0];
    if (file.size === 0 || file.size > maxBytes) throw new Error('素材為空或超過目前本機單檔傳輸上限。');
    const types = kind==='audio' ? ['audio/wav','audio/x-wav','audio/webm','audio/ogg','audio/mp4','audio/mpeg'] : ['image/png','image/jpeg'];
    if (!types.includes(mime)) throw new Error('目前不支援這個檔案格式；請選擇 PNG／JPEG 圖片或支援的音檔。');
    // IndexedDB 保存原始 Blob；object URL 僅供目前畫面，不拿來當永久來源。
    session.items.push({id:crypto.randomUUID(), kind:kind==='camera'?'image':kind, name:file.name || '錄音', mime, blob:file, originalText:'',editedText:'',checked:false});
    if (active===session) draw();
    await persist(session);
  }
  function stopTracks() { stream?.getTracks().forEach(track => track.stop()); stream=null; clearInterval(timer); timer=null; }
  function stopRecording(cancel = false) {
    permissionToken++;
    if (recordingSession) recordingSession.cancelled = cancel;
    if (recorder?.state === 'recording') recorder.stop();
    stopTracks();
    if (cancel) {recorderMessage='已取消錄音，其他文字與素材保留。'; recordingSession=null; recorder=null;}
    draw();
  }
  async function startRecording() {
    if (recordingSession || recorder) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('此環境無法錄音，請改用文字或上傳音檔。');
    const token=++permissionToken, session=active;
    session.recorderOpen=true;
    recordingSession={session,cancelled:false};
    recorderMessage='等待麥克風權限；尚未開始錄音。'; draw();
    try {
      const captured = await navigator.mediaDevices.getUserMedia({audio:true});
      if(token!==permissionToken || active!==session) {captured.getTracks().forEach(track=>track.stop()); return;}
      stream=captured;
      const mime = ['audio/webm;codecs=opus','audio/webm','audio/mp4','audio/ogg;codecs=opus'].find(type=>MediaRecorder.isTypeSupported(type));
      const current = new MediaRecorder(stream, mime?{mimeType:mime}:undefined);
      const recording=recordingSession, chunks=[];
      let size=0;
      recorder=current; elapsed=0;
      current.addEventListener('dataavailable', event=>{
        if(event.data?.size) {chunks.push(event.data); size+=event.data.size; if(size>maxBytes) {recording.cancelled=true; recorderMessage='錄音超過目前傳輸上限，請重新錄製較短片段。'; stopRecording(true);}}
      });
      current.addEventListener('stop', async()=>{
        // 舊錄音的 stop 可能晚於取消／重錄，不能停止下一段的新麥克風。
        if (stream === captured) stopTracks();
        else captured.getTracks().forEach(track=>track.stop());
        if(recorder===current) recorder=null;
        if(recordingSession===recording) recordingSession=null;
        if(recording.cancelled) return;
        const type=(current.mimeType||mime||'audio/webm').split(';')[0];
        const blob=new Blob(chunks,{type});
        try {await addFile(new File([blob], '錄音-'+Date.now()+'.'+({ 'audio/mp4':'m4a','audio/ogg':'ogg' }[type]||'webm'),{type}), 'audio',session); if(!recordingSession) recorderMessage='錄音已停止，可直接上傳並轉文字，或選擇性試聽。';}
        catch(error) {recorderMessage=error.message;}
        if(active===session) draw();
      });
      current.addEventListener('error',()=>{recorderMessage='錄音中斷，已停止麥克風；請檢查可用片段或重新錄製。'; stopRecording();});
      current.start(1000);
      recorderMessage='錄音中 · 00:00'; draw();
      timer=setInterval(()=>{elapsed++; recorderMessage='錄音中 · '+String(Math.floor(elapsed/60)).padStart(2,'0')+':'+String(elapsed%60).padStart(2,'0'); const status=document.querySelector('#recorder-status'); if(status)status.textContent=recorderMessage;},1000);
    } catch(error) {
      if(token!==permissionToken) return;
      stopTracks(); recordingSession=null; recorder=null;
      recorderMessage=error.name==='NotAllowedError'?'未取得麥克風權限；可改用文字或上傳音檔。':error.name==='NotFoundError'?'找不到麥克風；可改用文字或上傳音檔。':'錄音無法開始，請檢查裝置或改用音檔。'; draw();
    }
  }
  async function recognizeItem(item) {
    const session=active, controller=new AbortController(), editRevision=item.editRevision || 0;
    if(requests.has(item.id)) return;
    requests.set(item.id,controller); item.error=''; draw();
    try {
      const body=new FormData(); body.append('kind',item.kind); body.append('file',item.blob,item.name);
      const response=await fetch('/api/media/recognize',{method:'POST',headers:{'X-CSRF-Token':ctx.state.csrf},body,signal:controller.signal,credentials:'same-origin'});
      const data=await response.json();
      if(!response.ok) throw new Error(data.error?.message||'辨識未完成，請保留素材並重試。');
      if(typeof data.text!=='string'||!data.text.trim()||data.text.length>20000||data.applied!==false) throw new Error('辨識回應不完整，請重試或手動校對。');
      // 移除、取消或返回後的舊回應不得重新插入或覆蓋校對內容。
      if(controller.signal.aborted || !session.items.includes(item)) return;
      item.originalText=data.text; item.receipt=data.source;
      if ((item.editRevision || 0) === editRevision) {item.editedText=data.text; item.checked=false;}
      else item.error='辨識已完成，已保留你等待期間的手動校對；辨識原文可展開查看。';
    } catch(error) {if(!controller.signal.aborted && session.items.includes(item)) item.error=error.message || '連線失敗，素材仍保留。';}
    finally {if(requests.get(item.id)===controller)requests.delete(item.id); await persist(session); if(active===session)draw();}
  }
  function cancelRequests(session=active) {
    for(const item of session?.items||[]) {const controller=requests.get(item.id); if(controller){controller.abort(); requests.delete(item.id); item.error='已取消等待，素材保留；已傳送的工作可能仍在伺服器執行。';}}
  }
  function leave() {
    capture(); cancelRequests();
    if(recordingSession || recorder) stopRecording();
    active=null; releaseURLs();
  }
  async function bindDraft(id) {
    const session=active;
    if(!session) return;
    capture(); await pending;
    if (!session.items.length) {
      // 沒有素材時不依賴 IndexedDB，避免媒體儲存失敗阻擋原本的文字核心流程。
      try {await storage(session.key,undefined,true);}
      catch {ctx.toast('文字草稿已保存至伺服器；本機暫存無法清除，未影響文字保存。');}
      sessions.delete(session.key); active=null; releaseURLs();
      return;
    }
    const nextKey=ctx.state.me.owner_id+':draft:'+id;
    const serverRevision=ctx.state.draft?.revision;
    if(session.key===nextKey) {session.serverRevision=serverRevision; await persist(session); return;}
    const oldKey=session.key;
    // 先確認新位置保存成功，再移除建立時的暫存，失敗不假裝素材已同步。
    try {await storage(nextKey,{items:session.items,fields:session.fields,serverRevision}); await storage(oldKey,undefined,true); sessions.delete(oldKey); session.key=nextKey; session.serverRevision=serverRevision; sessions.set(nextKey,session);}
    catch {throw new Error('文字草稿已到伺服器，但本機素材未完成連結。請保留此頁，勿重複建立草稿。');}
  }
  async function clearOwner(owner,{signal}={}) { // 僅在使用者勾選後清本owner本機素材，不刪伺服器或其他owner。
    if(active?.owner===owner){stopRecording(true);cancelRequests(active);}
    await pending;
    if(signal?.aborted)throw new Error('本機清理已取消');
    const db=await dbPromise();
    try {
      if(signal?.aborted)throw new Error('本機清理已取消');
      await new Promise((resolve,reject)=>{
        const tx=db.transaction('workspaces','readwrite'),store=tx.objectStore('workspaces');
        const cursor=store.openCursor();
        cursor.onsuccess=()=>{const row=cursor.result;if(!row)return;if(String(row.key).startsWith(owner+':'))row.delete();row.continue();};
        const abort=()=>{try{tx.abort();}catch{}};signal?.addEventListener('abort',abort,{once:true});
        tx.oncomplete=()=>{signal?.removeEventListener('abort',abort);resolve();};tx.onerror=()=>{signal?.removeEventListener('abort',abort);reject(new Error('本機媒體草稿尚未清除；不影響已完成的登出。'));};tx.onabort=tx.onerror;
      });
      for(const key of sessions.keys())if(key.startsWith(owner+':'))sessions.delete(key);
      if(active?.owner===owner){active=null;releaseURLs();}
    } finally {db.close();}
  }
  async function discard() {
    if(!active)return;
    const session=active;
    stopRecording(true); cancelRequests(session); await pending;
    try {await storage(session.key,undefined,true);} catch {throw new Error('本機草稿移除失敗，請重試。');}
    sessions.delete(session.key); active=null; releaseURLs();
  }
  async function keepLocal() {
    const session=active;
    capture(); await pending;
    if(!session || session.storedRevision!==session.saveRevision) throw new Error('本機保存尚未成功，請保持此頁或另行保留內容。');
  }
  function updateApply(item, root) {
    const action=root.querySelector('[data-media="apply"],[data-media="copy"]');
    if(action)action.disabled=!item.checked||!item.editedText?.trim()||active.readOnly;
  }
  function initialize(value) {
    ctx=value;
    document.addEventListener('toggle',event=>{if(active&&event.target.matches?.('.media-recorder'))active.recorderOpen=event.target.open;},true);
    document.addEventListener('input', event=>{
      if(!active)return;
      const root=event.target.closest('[data-media-id]'), item=active.items.find(i=>i.id===root?.dataset.mediaId);
      if(item&&event.target.matches('[data-media-text]')) {item.editedText=event.target.value; item.editRevision=(item.editRevision||0)+1; item.checked=false; root.querySelector('[data-media-checked]').checked=false; updateApply(item,root); persist();}
      else if(event.target.closest('#record-form')&&!event.target.closest('#media-panel')) capture();
    });
    document.addEventListener('change', async event=>{
      try {
        if(event.target.matches('[data-media-file]')) {await addFile(event.target.files[0],event.target.dataset.mediaFile); event.target.value='';}
        else if(active&&event.target.matches('[data-media-checked]')) {const root=event.target.closest('[data-media-id]'),item=active.items.find(i=>i.id===root.dataset.mediaId); item.checked=event.target.checked; updateApply(item,root); await persist();}
        else if(active&&event.target.closest('#record-form'))capture();
      } catch(error){ctx.toast(error.message);}
    });
    document.addEventListener('click',async event=>{
      const target=event.target.closest('[data-media]'); if(!target||!active)return;
      const item=active.items.find(i=>i.id===target.closest('[data-media-id]')?.dataset.mediaId);
      try {
        switch(target.dataset.media) {
          case 'start': await startRecording(); break;
          case 'stop': stopRecording(); break;
          case 'cancel-recording': stopRecording(true); break;
          case 'recognize': if(ctx.state.me?.status==='guest') {ctx.requestLogin();break;} await recognizeItem(item); break;
          case 'cancel-upload': requests.get(item.id)?.abort(); requests.delete(item.id); item.error='已取消等待，素材保留；伺服器已收到的工作不保證撤銷。'; await persist(); draw(); break;
          case 'remove': requests.get(item.id)?.abort(); requests.delete(item.id); active.items=active.items.filter(i=>i!==item); await persist(); draw(); break;
          case 'apply': {
            if(!item.checked||!item.editedText.trim()||active.readOnly)break;
            const raw=document.querySelector('#raw-text'), text=[raw.value,item.editedText].filter(Boolean).join('\n\n');
            if(text.length>20000)throw new Error('合併文字超過 20,000 字，請先精簡內容。');
            raw.value=text; raw.dispatchEvent(new Event('input',{bubbles:true})); ctx.toast('已加入文字，仍須保存草稿並完成經歷確認。'); break;
          }
          case 'copy': if(item.checked&&!active.readOnly){await navigator.clipboard.writeText(item.editedText); ctx.toast('已複製校對文字；未建立人物或經歷。');} break;
        }
      } catch(error){ctx.toast(error.message);}
    });
    window.addEventListener('pagehide',()=>{capture();cancelRequests();if(recorder||recordingSession)stopRecording();});
    window.addEventListener('beforeunload',event=>{if(recorder||recordingSession){event.preventDefault();event.returnValue='';}});
  }
  return {initialize,clearOwner,mount,capture,leave,bindDraft,discard,renderDrafts,keepLocal};
})();
