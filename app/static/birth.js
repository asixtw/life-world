'use strict';
// 孵化是呈現互動，不呼叫 API、不改帳號、目標、進度或積分。
window.BirthUI = (() => {
  const labels=['輕觸目標蛋，出現細裂痕','再輕觸一次，裂痕慢慢擴大','最後輕觸一次，迎接 Lumi'];
  function view(character) {
    return `<div class="narrow" data-birth data-stage="0"><section class="hero"><div class="hero-copy"><div class="eyebrow">A NEW BEGINNING</div><h1>目標蛋誕生了。</h1><p>每次輕觸，讓裂痕慢慢展開；第三次，迎接 Lumi。</p><p data-birth-status role="status" aria-live="polite">準備好了，就輕觸目標蛋。</p><a href="#world" class="primary" data-birth-enter hidden>進入我的世界 →</a></div><div class="birth-scene"><button type="button" class="birth-egg has-art" data-birth-egg aria-label="${labels[0]}"><img class="egg-layer egg-rest" data-egg-art src="/static/art/egg-rest.png" alt=""><img class="egg-layer egg-fine" data-egg-art src="/static/art/egg-fine.png" alt=""><img class="egg-layer egg-deep" data-egg-art src="/static/art/egg-deep.png" alt=""><img class="egg-layer egg-open" data-egg-art src="/static/art/egg-open.png" alt=""><span class="birth-crack birth-crack-one" aria-hidden="true"></span><span class="birth-crack birth-crack-two" aria-hidden="true"></span></button><div data-birth-lumi hidden>${character}</div></div></section></div>`;
  }
  function mount() {
    const root=document.querySelector('[data-birth]');if(!root)return;
    const egg=root.querySelector('[data-birth-egg]'), status=root.querySelector('[data-birth-status]');
    let stage=0, locked=false;
    egg.addEventListener('click',()=>{
      // 鎖定到動畫完成；原生 button 同時支援 Enter、Space 與觸控。
      if(locked||stage===3)return;locked=true;egg.disabled=true;stage+=1;
      root.dataset.stage=String(stage);
      status.textContent=['','第一道細裂痕慢慢出現。','裂痕慢慢擴大。','蛋殼慢慢打開，Lumi 就要出現。'][stage];
      const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      window.setTimeout(()=>{
        if(!root.isConnected)return;
        if(stage===3){
          root.querySelector('[data-birth-lumi]').hidden=false;
          window.WorldAudio?.play('first-hatch');
          const enter=root.querySelector('[data-birth-enter]');enter.hidden=false;
          status.textContent='你好，我是 Lumi。從現在起，我們一起慢慢走。';enter.focus();
        } else {locked=false;egg.disabled=false;egg.setAttribute('aria-label',labels[stage]);status.textContent+=' 準備好後，再輕觸一次。';}
      },reduced?400:1400);
    });
  }
  return {view,mount};
})();
