/* 只保存偏好、不存Owner／對話；未核准素材不載入或播放。 */
window.WorldAudio = (() => {
  const key='lifeworld-audio-preferences-v1';
  let preferences={sound:false,music:false}, approved={}, background=null, scene='login', unlocked=false;
  try { const saved=JSON.parse(localStorage.getItem(key)||'null'); if(saved) preferences={sound:saved.sound===true,music:saved.music===true}; } catch (_) { /* 儲存失敗時仍可操作本頁開關。 */ }
  // 兩種偏好獨立，停用音樂時立即停止目前背景聲。
  function set(kind,value) {
    if(!['sound','music'].includes(kind)) return;
    preferences[kind]=value===true;
    if(kind==='music'&&!value&&background) { background.pause(); background=null; }
    if(kind==='music'&&value&&unlocked) void play(scene);
    try { localStorage.setItem(key,JSON.stringify(preferences)); } catch (_) { /* 偏好儲存不可阻塞產品交易。 */ }
  }
  async function play(event) {
    const asset=approved[event];
    if(!asset||asset.approved!==true||!preferences[asset.kind]) return false;
    try { if(asset.kind==='music'&&background?.src?.endsWith(asset.url))return true; const audio=new Audio(asset.url);audio.volume=asset.kind==='music'?.25:.65; if(asset.kind==='music') { if(background) background.pause(); background=audio;audio.loop=true; } await audio.play(); return true; }
    catch (_) { return false; } // 自動播放／素材失敗只跳過聲音，不影響保存。
  }
  // 只有逐項核准且同源的靜態素材可以進入播放白名單。
  function configure(manifest) {
    approved={};
    for(const [event,asset] of Object.entries(manifest?.assets||{})) {
      if(asset.approved===true&&['sound','music'].includes(asset.kind)&&/^\/static\/audio\/[a-z0-9._-]+\.(wav|mp3|ogg|m4a)$/.test(asset.url)) approved[event]={...asset};
    }
  }
  function route(path) { scene=['welcome','profile'].includes(path)?'login':path==='goal-new'?'goals':'world';if(unlocked&&preferences.music)void play(scene); }
  document.addEventListener('pointerdown',()=>{unlocked=true;if(preferences.music)void play(scene);});
  document.addEventListener('keydown',()=>{unlocked=true;if(preferences.music)void play(scene);});
  document.addEventListener('pointerup',event=>{if(event.target.closest?.('button,a')&&!event.target.disabled)void play('ui-tap');});
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
