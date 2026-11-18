/* 共用安裝導覽：不呼叫 API、不保留帳號資料、不替使用者自動安裝。 */
(() => {
  'use strict';
  const key='lifeworld:install-hint:v1';
  let pending=null,trigger=null,dialog=null;
  const installed=()=>navigator.standalone===true||matchMedia('(display-mode: standalone)').matches;
  const route=()=>window.LifeWorldInstallGuide.route({userAgent:navigator.userAgent,maxTouchPoints:navigator.maxTouchPoints,standalone:installed(),promptAvailable:!!pending});
  const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function hideNudges(){document.querySelectorAll('[data-pwa-nudge]').forEach(el=>el.hidden=true);}
  function refresh(){
    let dismissed=false;try{dismissed=localStorage.getItem(key)==='later';}catch{}
    if(installed()||dismissed)hideNudges();
  }
  function message(text){if(dialog)dialog.querySelector('[data-pwa-status]').textContent=text;}
  function steps(kind){
    if(kind==='installed')return '<p>你已從主畫面模式開啟 Life World，可以直接繼續使用。</p>';
    if(kind==='inapp')return '<p>你目前可能在 IG、FB 或其他 App 的內建瀏覽器。</p><ol><li>點右上角或下方的「⋯」選單。</li><li>若有「在瀏覽器開啟」，選擇 Safari（iPhone）或 Chrome（Android）。</li><li>在外部瀏覽器重新開啟安裝說明，完成加入主畫面。</li></ol><p>如果找不到選項，可複製下方網址，貼到 Safari／Chrome。不同 App 版本的選單可能不同。</p>';
    if(kind==='ios')return '<ol><li>在 Safari 開啟 Life World。</li><li>點「分享」圖示（方框向上箭頭），部分版本需先開啟「⋯」。</li><li>選「加入主畫面」→「新增」。如果看到「以網頁 App 開啟」，保持開啟。</li></ol><p>看不到「加入主畫面」時，可在分享選單底部「編輯動作」加入。選單位置依系統版本而異。</p>';
    if(kind==='prompt')return '<p>此瀏覽器已提供安裝選項。點下方按鈕，再由你在瀏覽器視窗確認。</p><button type="button" class="primary pwa-primary" data-pwa-prompt>開啟瀏覽器安裝視窗</button><p>暫時不想安裝也能正常使用。</p>';
    if(kind==='android')return '<ol><li>在 Android 的 Chrome 開啟 Life World。</li><li>點網址列旁的「⋮」選單。</li><li>選「安裝並建立捷徑」／「安裝應用程式」或「加到主畫面」，再依畫面確認。</li></ol><p>名稱依 Chrome 版本而異；沒有安裝選項時仍可用瀏覽器開啟。</p>';
    return '<p>你可以直接用瀏覽器使用，或依裝置選擇加入主畫面的方式。</p>';
  }
  function render(kind){
    const url=location.origin+'/',ios=kind==='ios';
    dialog.innerHTML=`<div class="pwa-head"><img src="/static/art/mobile-web-v1/icon-192.png" width="56" height="56" alt="Life World 圖示"><div><p>把你的世界，放在手邊。</p><h2 id="pwa-title">${kind==='installed'?'已從主畫面開啟':'加入主畫面'}</h2></div><button type="button" class="text-button" data-pwa-close aria-label="關閉安裝說明">✕</button></div><div class="pwa-body">${steps(kind)}${kind==='installed'?'':`<details><summary>其他裝置／瀏覽器的做法</summary><div class="pwa-choices"><button type="button" class="secondary" data-pwa-kind="ios">iPhone／iPad</button><button type="button" class="secondary" data-pwa-kind="android">Android</button><button type="button" class="secondary" data-pwa-kind="inapp">IG／FB 內開啟</button></div></details><label for="pwa-url">網站網址</label><input id="pwa-url" readonly value="${escape(url)}"><button type="button" class="text-button" data-pwa-copy>複製網址</button><p class="pwa-warning">仍是訪客？切換瀏覽器前，請先確認帳號選單是否可保存世界。尚未開放保存時，先留在原瀏覽器；新瀏覽器或主畫面 App 可能需要重新登入，訪客資料不會自動轉移。</p>`}<p class="pwa-note">不需要 App Store 下載。使用與保存仍需要網路；加入主畫面不代表離線可用。</p><p data-pwa-status role="status" aria-live="polite"></p></div><div class="pwa-footer"><button type="button" class="secondary" data-pwa-close>稍後再說</button><button type="button" class="primary pwa-primary" data-pwa-close>知道了</button></div>`;
  }
  function open(button){
    // 不在四步輸入途中自動彈窗，也不關閉既有帳號／人工核對視窗。
    if(document.querySelector('dialog[open]'))return;
    trigger=button;
    if(!dialog){dialog=document.createElement('dialog');dialog.id='pwa-install-dialog';dialog.setAttribute('aria-labelledby','pwa-title');document.body.append(dialog);dialog.addEventListener('close',()=>{if(trigger?.isConnected)trigger.focus();});}
    render(route());dialog.showModal();
  }
  window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();pending=event;});
  window.addEventListener('appinstalled',()=>{pending=null;hideNudges();message('瀏覽器已回報完成安裝，可以從主畫面開啟。');});
  document.addEventListener('click',async event=>{
    const b=event.target.closest('[data-pwa-open],[data-pwa-close],[data-pwa-kind],[data-pwa-prompt],[data-pwa-copy],[data-pwa-later]');if(!b)return;
    if(b.hasAttribute('data-pwa-open')){open(b);return;}
    if(b.hasAttribute('data-pwa-later')){try{localStorage.setItem(key,'later');}catch{}hideNudges();return;}
    if(b.hasAttribute('data-pwa-close')){dialog?.close();return;}
    if(b.dataset.pwaKind){render(b.dataset.pwaKind);dialog.querySelector('h2').setAttribute('tabindex','-1');dialog.querySelector('h2').focus();return;}
    if(b.hasAttribute('data-pwa-copy')){
      try{await navigator.clipboard.writeText(location.origin+'/');message('已複製網址，可貼到 Safari 或 Chrome。');}
      catch{dialog.querySelector('#pwa-url').select();message('請使用系統的複製功能複製已選取的網址。');}
      return;
    }
    if(b.hasAttribute('data-pwa-prompt')){
      const prompt=pending;pending=null;b.disabled=true;
      if(!prompt){message('安裝選項已失效；請改用瀏覽器選單，或稍後重新開啟。');return;}
      try{
        await prompt.prompt();const choice=await prompt.userChoice;
        message(choice.outcome==='accepted'?'已接受安裝請求，請依瀏覽器完成。尚未收到安裝完成回報。':'你已取消安裝，仍可正常使用網站。');
      }catch{message('目前無法開啟安裝視窗，請使用瀏覽器選單；你的內容未變更。');}
    }
  });
  document.addEventListener('lifeworld:intro-finished',refresh);
  refresh();
})();
