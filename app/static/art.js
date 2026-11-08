/* 既有專案素材接入；圖片載入失敗仍保留可辨識的CSS角色／蛋。 */
document.addEventListener('error',event=>{
  const image=event.target;
  if(image?.matches?.('[data-lumi-art]')) { image.hidden=true;const fallback=image.parentElement.querySelector('[data-lumi-fallback]');if(fallback)fallback.hidden=false; }
  if(image?.matches?.('[data-egg-art]')) { const egg=image.closest('.birth-egg');egg?.classList.remove('has-art');egg?.querySelectorAll('[data-egg-art]').forEach(x=>x.hidden=true); }
},true);
