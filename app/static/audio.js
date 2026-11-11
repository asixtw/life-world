/* 只保存偏好、不存Owner／對話；未核准素材不載入或播放。 */
window.WorldAudio = (() => {
  const key='lifeworld-audio-preferences-v1';
  let preferences={sound:false,music:false}, approved=Object.create(null), background=null, scene='login', unlocked=false, suspended=false;
  const sounds=new Set(); // 僅追蹤本頁音軌；不存任何帳號或交易內容。
  try { const saved=JSON.parse(localStorage.getItem(key)||'null'); if(saved) preferences={sound:saved.sound===true,music:saved.music===true}; } catch (_) { /* 儲存失敗時仍可操作本頁開關。 */ }

  // 停用、離頁和晚到的 play Promise 共用清理，確保聲音不會在取消後復活。
  function release(voice) {
    if(!voice)return;
    voice.stopped=true;
    sounds.delete(voice);
    if(background===voice)background=null;
    try { voice.audio.pause(); } catch (_) { /* 單一音軌失敗不可阻擋其他清理。 */ }
    for(const name of ['ended','error']) {
      try { voice.audio.removeEventListener?.(name,voice.cleanup); } catch (_) { /* 已失效的媒體仍繼續釋放。 */ }
    }
    try { voice.audio.removeAttribute?.('src');voice.audio.load?.(); } catch (_) { /* 無聲退路。 */ }
  }
  function stop(kind) {
    if(!kind||kind==='music')release(background);
    if(!kind||kind==='sound')for(const voice of [...sounds])release(voice);
  }
  function canPlay(asset) {
    return asset?.approved===true&&preferences[asset.kind]&&!suspended&&!document.hidden;
  }
  function resumeMusic() {
    if(unlocked&&preferences.music&&!suspended&&!document.hidden)void play(scene);
  }
  // 兩種偏好獨立；關閉時即使 play 尚未完成也停止該類全部音軌。
  function set(kind,value) {
    if(!['sound','music'].includes(kind))return;
    preferences[kind]=value===true;
    if(!preferences[kind])stop(kind);
    else if(kind==='music')resumeMusic();
    try { localStorage.setItem(key,JSON.stringify(preferences)); } catch (_) { /* 偏好儲存不可阻塞產品交易。 */ }
  }
  async function play(event) {
    const asset=approved[event];
    if(!canPlay(asset))return false;
    if(asset.kind==='music'&&background?.asset===asset)return background.pending;
    let voice;
    try {
      if(asset.kind==='music')stop('music');
      // 快速連點不建立無上限重疊音效；保留最多八條，先釋放最舊者。
      else if(sounds.size>=8)release(sounds.values().next().value);
      const audio=new Audio(asset.url);
      voice={audio,asset,stopped:false,cleanup:null,pending:null};
      voice.cleanup=()=>release(voice);
      audio.volume=asset.kind==='music'?.25:.65;
      audio.loop=asset.kind==='music';
      for(const name of ['ended','error'])audio.addEventListener?.(name,voice.cleanup);
      if(asset.kind==='music')background=voice;else sounds.add(voice);
      voice.pending=Promise.resolve(audio.play()).then(()=>{
        // 只接受仍有效的同一素材與偏好，過期成功不能蓋過較新的路由。
        if(voice.stopped||approved[event]!==asset||!canPlay(asset)) {release(voice);return false;}
        return true;
      },()=>{release(voice);return false;});
      return await voice.pending;
    } catch (_) {release(voice);return false;} // 拒絕／素材失敗只跳過聲音，不影響保存。
  }
  // 撤銷清單即停止舊音軌；只允許明確核准、同源、固定目錄的素材。
  function configure(manifest) {
    stop();approved=Object.create(null);
    const assets=manifest?.assets;
    for(const [event,asset] of Object.entries(assets&&typeof assets==='object'?assets:{})) {
      if(asset&&asset.approved===true&&['sound','music'].includes(asset.kind)&&typeof asset.url==='string'&&/^\/static\/audio\/[a-z0-9._-]+\.(wav|mp3|ogg|m4a)$/.test(asset.url))approved[event]={...asset};
    }
    resumeMusic(); // 清單晚於第一次手勢抵達時，仍沿用當前場景與使用者偏好。
  }
  function route(path) {
    const next=['welcome','profile'].includes(path)?'login':path==='goal-new'?'goals':'world';
    if(next!==scene)stop('music'); // 新場景缺少核准 BGM 時保持無聲，不殘留上一場景。
    scene=next;resumeMusic();
  }
  function unlock() {unlocked=true;resumeMusic();}
  document.addEventListener('pointerdown',unlock);
  document.addEventListener('keydown',unlock);
  document.addEventListener('pointerup',event=>{const target=event.target.closest?.('button,a');if(target&&!target.disabled)void play('ui-tap');});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();else resumeMusic();});
  window.addEventListener('pagehide',()=>{suspended=true;stop();});
  window.addEventListener('pageshow',()=>{suspended=false;resumeMusic();});
  const heard=new Set(); // 僅本頁去重，從不持久化Owner／經歷識別碼。
  // 收到成功回執後才回饋，同一經歷的重送不再次播成功音。
  function feedback(path,method,body,owner) {
    if(method!=='POST'||!body)return;
    const event=/^\/drafts\/[^/]+\/confirm$/.test(path)?'experience-confirmed':path==='/experiences/drafts'?'draft-saved':/^\/goals\/[^/]+\/complete$/.test(path)?'goal-completed':null;
    if(!event)return;
    const id=owner+':'+event+':'+(body.experience_id||body.completion_id||body.id||path);
    if(heard.has(id))return;heard.add(id);if(heard.size>256)heard.delete(heard.values().next().value);
    void play(event);
  }
  function mount() {
    const host=document.querySelector('#audio-preferences');if(!host)return;
    host.innerHTML='<summary>聲音設定</summary><label><input type="checkbox" data-audio="sound"> 音效</label> <label><input type="checkbox" data-audio="music"> 音樂</label><p class="small muted">分別控制音效與背景音樂；設定只保存在這台裝置。</p>';
    for(const input of host.querySelectorAll('[data-audio]')) {input.checked=preferences[input.dataset.audio];input.addEventListener('change',()=>set(input.dataset.audio,input.checked));}
  }
  document.addEventListener('DOMContentLoaded',()=>{mount();fetch('/static/audio-approved.json').then(r=>r.ok?r.json():{}).then(configure).catch(()=>{});});
  return {set,play,configure,feedback,route,get preferences(){return {...preferences};}};
})();
