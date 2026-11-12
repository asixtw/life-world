/* 接入層僅記住介紹選擇；不接觸正式帳號／目標／孵化，也不改變原型狀態機。 */
(() => {
  'use strict';
  function mark(outcome) {
    if(window.LifeWorldIntroPreference.mark(outcome))return;
    if(document.querySelector('#intro-storage-note'))return;
    const note=document.createElement('p');note.id='intro-storage-note';note.className='lw-demo-note';note.setAttribute('role','status');
    note.textContent='此瀏覽器無法記住介紹偏好，下次可能再次提示。你仍可正常進入產品。';
    document.querySelector('#summary-copy').append(note);
  }
  document.addEventListener('lifeworld:intro-finished',event=>mark(event.detail?.outcome));
  document.querySelectorAll('[data-intro-exit],#product-entry').forEach(link=>link.addEventListener('click',()=>mark('skipped')));
})();
