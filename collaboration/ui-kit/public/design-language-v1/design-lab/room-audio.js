/* 房間與聲音只作本機候選呈現；不呼叫 API，不修改正式偏好或採用清單。 */
(() => {
  'use strict';
  const $=id=>document.getElementById(id), base=window.LifeWorldStaticBase;
  const {room,audio}=window.LifeWorldRoomAudio;
  const url=path=>window.LifeWorldPreviewAsset?.(base+'/'+path) || base+'/'+path;
  function showRoom(){
    const legacy=$('room-version').value==='legacy',quiet=$('room-quiet').checked;
    $('room-background').hidden=false;$('room-fallback').hidden=true;
    $('room-background').src=url(legacy?room.legacy_path:room.web_path);
    $('room-lumi').src=url('art/design-v1/lumi-'+(quiet?'quiet':'idle')+'-512.png');
    $('room-lumi').hidden=!$('room-show-lumi').checked;
    $('room-scene').setAttribute('aria-label',(legacy?'舊版房間背景':'新版暖白薄荷綠房間')+($('room-show-lumi').checked?(quiet?'，Lumi 安靜地陪伴你':'，Lumi 在中央地毯上陪伴你'):'，暫時隱藏 Lumi'));
  }
  for(const id of ['room-version','room-quiet','room-show-lumi'])$(id).addEventListener('change',showRoom);
  $('room-background').addEventListener('error',()=>{$('room-background').hidden=true;$('room-fallback').hidden=false;});
  $('room-lumi').addEventListener('error',()=>{$('room-lumi').hidden=true;$('room-fallback').hidden=false;$('room-fallback').textContent='部分場景素材無法顯示。下方操作仍可使用，可以切換版本重試。';});

  const rows=audio.assets;
  const kindLabel={sound:'音效',music:'音樂',ambience:'環境聲'};
  $('audio-comparisons').innerHTML=rows.map(asset=>`<article class="dl-audio-card"><span class="tag">${kindLabel[asset.kind]}・新候選</span><h3>${asset.label}</h3><p>${asset.duration_seconds} 秒${asset.bpm?' · '+asset.bpm+' BPM':''} · ${asset.loop?'循環':'單次'} · 原創合成</p><div class="button-row"><button class="primary" data-audio-new="${asset.id}" disabled>試聽新版</button>${asset.legacy_path?`<button class="secondary" data-audio-old="${asset.id}" disabled>比較舊版</button>`:'<span class="small">本次新增，沒有舊版</span>'}</div><a href="${url(asset.source_path)}" download="${asset.id}-v1.wav">下載 WAV 原稿</a></article>`).join('');
  const active={sound:null,music:null},enabled={sound:false,music:false};
  const channel=asset=>asset.kind==='sound'?'sound':'music';
  const isQuiet=()=>$('quiet').checked;
  function message(text){$('compare-status').textContent=text;$('audio-status').textContent=text;}
  function stop(kind){
    const track=active[kind];active[kind]=null;
    if(track){track.pause();track.removeAttribute('src');track.load();}
  }
  function stopAll(){stop('music');stop('sound');}
  function updateButtons(){
    document.querySelectorAll('[data-audio-new],[data-audio-old]').forEach(button=>{
      const asset=rows.find(item=>item.id===(button.dataset.audioNew||button.dataset.audioOld));
      button.disabled=!enabled[channel(asset)]||isQuiet();
    });
  }
  function enable(kind,value){
    enabled[kind]=value;
    for(const id of kind==='sound'?['sound','compare-sound']:['music','compare-music'])$(id).checked=value;
    if(!value){stop(kind);message(kind==='sound'?'音效已關閉。':'音樂與環境聲已關閉。');}updateButtons();
  }
  async function play(asset,legacy=false,loop=false){
    const kind=channel(asset);
    if(!enabled[kind]||document.hidden||isQuiet())return;
    stop(kind);
    const track=new Audio(url(legacy?asset.legacy_path:asset.web_path));active[kind]=track;
    track.loop=loop;track.volume=legacy?asset.legacy_audition_gain:asset.audition_gain;
    track.addEventListener('ended',()=>{if(active[kind]===track){active[kind]=null;message('試聽結束，可以比較另一個版本。');}});
    try{
      await track.play();
      // 關閉、換曲或離頁後才完成的 play Promise，不能重新讓舊音軌發聲。
      if(active[kind]!==track||!enabled[kind]||document.hidden||isQuiet()){track.pause();return;}
      message(`正在試聽${legacy?'舊版':'新版'}：${asset.label}。${loop?'循環中，可隨時停止。':'僅為候選示例。'}`);
    }catch{
      track.pause();if(active[kind]!==track)return;active[kind]=null;
      message('目前無法播放聲音，畫面和互動仍可完整使用。可以再次試聽。');
    }
  }
  document.querySelectorAll('[data-audio-new],[data-audio-old]').forEach(button=>button.addEventListener('click',()=>{
    const asset=rows.find(item=>item.id===(button.dataset.audioNew||button.dataset.audioOld));void play(asset,Boolean(button.dataset.audioOld),asset.loop);
  }));
  for(const id of ['sound','compare-sound'])$(id).addEventListener('change',event=>enable('sound',event.target.checked));
  for(const id of ['music','compare-music'])$(id).addEventListener('change',event=>{
    enable('music',event.target.checked);
    if(id==='music'&&event.target.checked)void play(rows.find(item=>item.id==='login'),false,true);
  });
  $('audio-stop').addEventListener('click',()=>{stopAll();message('全部聲音已停止；可重新選擇試聽。');});
  $('quiet').addEventListener('change',()=>{if(isQuiet()){stopAll();message('安靜呈現中，聲音已停止。');}updateButtons();});
  function pausePage(){stopAll();message('聲音已停止；回到頁面後可重新選擇試聽。');}
  document.addEventListener('visibilitychange',()=>{if(document.hidden)pausePage();});
  window.addEventListener('pagehide',pausePage);
  window.WorldAudio={play:event=>{const asset=rows.find(item=>item.id===event);if(asset)void play(asset);}};
  window.LifeWorldSoundDemo={stopSounds:()=>stop('sound'),stopMusic:()=>stop('music')};
  // 跟隨真正被接受的三次按鈕操作；動畫鎖定期間不重播，不作正式孵化狀態判斷。
  $('hatch-demo').addEventListener('click',event=>{
    const button=event.target.closest('[data-birth-egg]');if(!button||button.disabled)return;
    const stage=Number(button.closest('[data-birth]').dataset.stage);
    const asset=rows.find(item=>item.id===['egg-fine','egg-deep','shell-open'][stage]);if(asset)void play(asset);
  },true);
  showRoom();updateButtons();
})();
