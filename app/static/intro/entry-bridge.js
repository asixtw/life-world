/* 接入層僅記住介紹選擇；不接觸正式帳號／目標／孵化，也不改變原型狀態機。 */
(() => {
  'use strict';
  function mark(outcome) {
    if(window.LifeWorldIntroPreference.mark(outcome))return;
    if(document.querySelector('#intro-storage-note'))return;
    // 偏好失敗沿用同一屏的狀態區，不再追加一列把進入產品的操作推離視窗。
    const note=document.querySelector('.lw-demo-note');if(!note)return;
    note.id='intro-storage-note';note.setAttribute('role','status');
    note.textContent='示例未呼叫 AI／寫入世界；無法記住偏好，下次可能再提示。';
  }
  document.addEventListener('lifeworld:intro-finished',event=>mark(event.detail?.outcome));
  document.querySelectorAll('[data-intro-exit],#product-entry').forEach(link=>link.addEventListener('click',()=>mark('skipped')));
})();
