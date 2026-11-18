/* 只保存介紹選擇；不含帳號、世界、孵化或任何私人內容。 */
(() => {
  'use strict';
  const key='lifeworld:intro:v1';
  let memory=null;
  const valid=value=>value?.version===1&&['completed','skipped'].includes(value.outcome);
  function read() {
    for(const name of ['localStorage','sessionStorage']) {
      try {const value=JSON.parse(window[name].getItem(key)||'null');if(valid(value))return value;}catch { /* 禁止儲存或壞資料時，繼續使用退路。 */ }
    }
    return memory;
  }
  function mark(outcome) {
    if(!['completed','skipped'].includes(outcome))return false;
    // 重看後跳過不把原本已完成的紀錄降級；正式產品狀態完全不在此管理。
    memory=read()?.outcome==='completed'?{version:1,outcome:'completed'}:{version:1,outcome};
    for(const name of ['localStorage','sessionStorage']) {
      try {window[name].setItem(key,JSON.stringify(memory));return true;}catch { /* 失敗不阻擋進入產品。 */ }
    }
    return false;
  }
  window.LifeWorldIntroPreference=Object.freeze({key,hasSeen:()=>valid(read()),mark});
})();
