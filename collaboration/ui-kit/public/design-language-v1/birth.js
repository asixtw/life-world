'use strict';
// 孵化是呈現互動，不呼叫 API、不改帳號、目標、進度或積分。
window.BirthUI = (() => {
  const mounted=new WeakSet(); // 同一 DOM 只綁一次，避免重播／重複移焦。
  let dispose=null;
  const labels=['輕觸目標蛋，出現細裂痕','再輕觸一次，裂痕慢慢擴大','最後輕觸一次，迎接 Lumi'];
  function view(character) {
    const base=window.LifeWorldStaticBase||'/static';
    return `<div class="narrow" data-birth data-stage="0" data-reveal="none"><section class="hero"><div class="hero-copy"><div class="eyebrow">A NEW BEGINNING</div><h1>目標蛋誕生了。</h1><p>每次輕觸，讓裂痕慢慢展開；第三次，迎接 Lumi。</p><p data-birth-status role="status" aria-live="polite">準備好了，就輕觸目標蛋。</p><a href="#world" class="primary" data-birth-enter hidden>進入我的世界 →</a></div><div class="birth-scene"><button type="button" class="birth-egg has-art" data-birth-egg aria-label="${labels[0]}"><img class="egg-layer egg-rest" data-egg-art src="${base}/art/design-v1/egg-rest-512.png" alt=""><img class="egg-layer egg-fine" data-egg-art src="${base}/art/design-v1/egg-fine-512.png" alt=""><img class="egg-layer egg-deep" data-egg-art src="${base}/art/design-v1/egg-deep-512.png" alt=""><img class="egg-layer egg-open" data-egg-art src="${base}/art/design-v1/egg-open-512.png" alt=""><span class="birth-crack birth-crack-one" aria-hidden="true"></span><span class="birth-crack birth-crack-two" aria-hidden="true"></span></button><div class="birth-reveal-frame birth-peek" aria-hidden="true"><img data-hatch-frame src="${base}/art/design-v1/lumi-hatch-peek-512.png" alt=""></div><div class="birth-reveal-frame birth-closed" aria-hidden="true"><img data-hatch-frame src="${base}/art/design-v1/lumi-hatch-closed-512.png" alt=""></div><div data-birth-lumi hidden>${character}</div></div></section></div>`;
  }
  function mount({reducedMotion=false}={}) {
    const root=document.querySelector('[data-birth]');if(!root||mounted.has(root))return;
    dispose?.();mounted.add(root);
    const egg=root.querySelector('[data-birth-egg]'), status=root.querySelector('[data-birth-status]');
    let stage=0, locked=false, cancelled=false;
    const timers=new Set();
    function later(fn,ms) {
      const id=window.setTimeout(()=>{timers.delete(id);if(!cancelled&&root.isConnected)fn();},ms);
      timers.add(id);
    }
    dispose=()=>{cancelled=true;for(const id of timers)window.clearTimeout?.(id);timers.clear();};
    function finish() {
      root.dataset.reveal='settled';root.querySelector('[data-birth-lumi]').hidden=false;
      window.WorldAudio?.play('first-hatch');
      const enter=root.querySelector('[data-birth-enter]');enter.hidden=false;
      status.textContent='你好，我是 Lumi。從現在起，我們一起慢慢走。';enter.focus();
    }
    egg.addEventListener('click',()=>{
      // 鎖定到動畫完成；原生 button 同時支援 Enter、Space 與觸控。
      if(cancelled||!root.isConnected||locked||stage===3)return;locked=true;egg.disabled=true;stage+=1;
      root.dataset.stage=String(stage);
      status.textContent=['','第一道細裂痕慢慢出現。','裂痕慢慢擴大。','蛋殼慢慢打開，Lumi 就要出現。'][stage];
      const reduced=reducedMotion||window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if(stage<3) {
        later(()=>{locked=false;egg.disabled=false;egg.setAttribute('aria-label',labels[stage]);status.textContent+=' 準備好後，再輕觸一次。';},reduced?80:stage===1?800:1000);
      } else if(reduced) {
        later(finish,80);
      } else {
        // 第三擊才探頭／閉眼／睜眼；每個回呼均驗證同一演出仍有效。
        root.dataset.reveal='peek';
        later(()=>{root.dataset.reveal='closed';status.textContent='Lumi 正在適應這個世界。';},600);
        later(()=>{root.dataset.reveal='open';root.querySelector('[data-birth-lumi]').hidden=false;status.textContent='Lumi 慢慢睜開眼睛。';},1000);
        later(()=>{root.dataset.reveal='settled';},1600);
        later(finish,2000);
      }
    });
  }
  function unmount(){dispose?.();dispose=null;}
  return {view,mount,unmount};
})();
