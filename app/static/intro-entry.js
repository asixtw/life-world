/* 首次接觸只提供選擇，不自動建立訪客、呼叫AI或改變產品流程。 */
(() => {
  'use strict';
  const preference=window.LifeWorldIntroPreference;
  function choice() {
    return `<section class="intro-choice" id="intro-choice" aria-labelledby="intro-choice-title"><p class="intro-eyebrow">歡迎來到 Life World</p><h1 id="intro-choice-title">先認識這個世界，<br>或直接開始你的故事。</h1><p>記下真實努力，讓成長與重要的人，都在自己的世界留下痕跡。</p><img src="/static/intro/assets/art/v1/egg-rest-512.png" width="200" height="200" alt="奶油色、薄荷綠嫩芽的目標蛋"><div class="intro-choice-actions"><a class="primary" href="/intro">先認識 Life World</a><button class="secondary" type="button" data-action="intro-direct">直接開始</button></div><p class="intro-choice-note">介紹可以跳過。之後也能從「關於」選單重看。</p></section>`;
  }
  window.IntroEntry=Object.freeze({shouldOffer:me=>!me&&!!preference&&!preference.hasSeen(),choice,dismiss:()=>preference?.mark('skipped')});
})();
