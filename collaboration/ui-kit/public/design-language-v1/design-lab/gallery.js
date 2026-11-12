/* 本機元件庫：只展示固定示例與 manifest，不讀取任何私人 API。 */
(() => {
  'use strict';
  const $=id=>document.getElementById(id), base=window.LifeWorldStaticBase;
  const assets=window.LifeWorldVisualManifest.assets;
  const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels={idle:'日常陪伴',welcome:'溫和歡迎',listening:'專注傾聽',confirmed:'確認後的喜悅',celebrate:'成果慶祝',quiet:'安靜',curious:'好奇',surprised:'驚喜',thinking:'思考',running:'跑步',sleeping:'睡眠',side:'側面',back:'背面','three-quarter':'3/4 視角','hatch-peek':'慢慢探頭','hatch-closed':'適應世界・閉眼',rest:'完整目標蛋',fine:'第一道細裂',deep:'裂痕擴大',open:'蛋殼打開'};
  document.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML=DesignIcons.render(el.dataset.icon);});
  $('hero-lumi').innerHTML=LumiUI.render({pose:'welcome',size:'hero'});
  const colors=window.LifeWorldDesignTokens.color;
  const colorNames={paper:'品牌暖白',brandMint:'品牌薄荷綠',brandYellow:'品牌暖黃',ink:'主要文字',primary:'主要操作',muted:'次要文字',success:'確認成功',pending:'待核對',error:'失敗',info:'中性資訊',surface:'卡片表面',surfaceSoft:'柔和表面'};
  $('colors').innerHTML=Object.entries(colorNames).map(([key,name])=>`<article class="dl-swatch"><div class="dl-swatch-color" style="background:${colors[key]}"></div><strong>${name}</strong><code>${colors[key].toUpperCase()}</code></article>`).join('');
  $('spacing').innerHTML=[4,8,12,16,20,24,32,40,48,64].map(size=>`<div><i style="height:${size}px;width:16px"></i>${size}</div>`).join('');
  $('icons').innerHTML=['world','goals','history','people','back','close','settings','retry','check','warning'].map(name=>`<span title="${name}">${DesignIcons.render(name)}</span>`).join('');

  function renderScenario(){
    const scenario=$('scenario').value;
    let html;
    if(scenario==='empty')html='<article class="card"><h3>讓故事有個起點。</h3><p>先留下一段經歷，慢慢看見變化。</p><span class="tag">空白狀態示例</span></article>';
    else if(scenario==='loading')html='<article class="card" aria-busy="true"><h3>正在整理示例…</h3><p>這是載入狀態，不代表真實 AI 已開始處理。</p><span class="tag dl-info">整理中・示例</span></article>';
    else if(scenario==='withdrawn')html='<article class="card"><h3>這段來源暫時不可用。</h3><p>已撤回的來源不作為新的候選依據。既有正式資料不因這個示例而刪除。</p><span class="tag dl-info">來源已撤回・示例</span></article>';
    else if(scenario==='error')html='<article class="card"><h3>暫時沒有保存成功。</h3><p>內容還在，可以再試一次。此處只展示失敗退路。</p><span class="tag dl-error">保存失敗・示例</span></article>';
    else html=`<article class="card"><span class="tag">我的成長・示例</span><h3>${scenario==='long'?'在很多次很小的練習之後，終於更有勇氣與重要的人好好說話':'一步一步，更敢開口。'}</h3><p>一個目標與三個習慣。排程代表打算做，進度以確認經歷為準。</p><label>英文練習：30／120 分鐘<progress value="30" max="120" aria-label="示例英文練習進度"></progress></label></article><article class="card"><span class="tag dl-pending">AI 草稿・尚未確認</span><h3>最後，由你決定。</h3><p>摘要：完成 30 分鐘英文練習。<br>互動者候選：${scenario==='long'?'小安、小晴，以及名字很長的虛構人物林同學':'小安（虛構人物）'}。</p><p class="small">可以修改、採納或排除；只是提及不等於互動。</p></article>`;
    $('scenario-cards').innerHTML=html;
  }
  $('scenario').addEventListener('change',renderScenario);
  $('preview-width').addEventListener('change',e=>{$('example-board').dataset.width=e.target.value;});
  $('quiet').addEventListener('change',e=>{document.body.dataset.quiet=String(e.target.checked);});
  $('example-form').addEventListener('submit',e=>e.preventDefault());
  $('demo-save').addEventListener('click',()=>{
    $('feedback').className='callout '+($('example-confirm').checked?'dl-success':'dl-pending');
    $('feedback').textContent=$('example-confirm').checked?'示例確認完成；沒有保存資料或發放獎勵。':'請先核對這份示例；內容尚未確認。';
  });
  function failure(){ $('feedback').className='callout dl-error';$('feedback').textContent='暫時沒有保存成功。內容還在，可以再試一次。（示例）'; }
  $('demo-error').addEventListener('click',failure);
  $('demo-clear').addEventListener('click',()=>{$('example-form').reset();$('feedback').className='callout';$('feedback').textContent='示例輸入已清除，沒有產品資料變更。';});
  $('open-dialog').addEventListener('click',()=>$('demo-dialog').showModal());
  document.querySelectorAll('[data-close-dialog]').forEach(button=>button.addEventListener('click',()=>button.closest('dialog').close()));

  function renderAssets(){
    const query=$('asset-search').value.trim().toLowerCase(),category=$('asset-category').value;
    const selected=assets.filter(asset=>(category==='all'||asset.category===category)&&[asset.asset_id,asset.state,labels[asset.state]].join(' ').toLowerCase().includes(query));
    $('asset-count').textContent=`顯示 ${selected.length}／${assets.length} 項候選素材；全部待視覺驗收。`;
    $('asset-grid').innerHTML=selected.length?selected.map(asset=>`<article class="dl-asset-card"><div class="dl-asset-image"><img src="${base}/${asset.web_path}" width="512" height="512" alt="${labels[asset.state]}"><span data-failed hidden>素材載入失敗；可查看規格或重試重新載入。</span></div><h3>${labels[asset.state]}</h3><code>${asset.asset_id}</code><button class="text-button" data-asset="${asset.asset_id}">查看規格 →</button></article>`).join(''):'<p class="callout">找不到符合條件的素材。可以清除搜尋或改選分類。</p>';
    $('asset-grid').querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{img.hidden=true;img.nextElementSibling.hidden=false;}));
  }
  for(const id of ['asset-search','asset-category'])$(id).addEventListener(id==='asset-search'?'input':'change',renderAssets);
  $('checkerboard').addEventListener('change',e=>{$('asset-grid').dataset.checkerboard=String(e.target.checked);});
  $('art-size').addEventListener('change',e=>{$('asset-grid').dataset.large=String(e.target.value==='large');});
  $('asset-grid').addEventListener('click',e=>{
    const button=e.target.closest('[data-asset]');if(!button)return;
    const asset=assets.find(item=>item.asset_id===button.dataset.asset);
    $('asset-title').textContent=labels[asset.state]+'・素材規格';
    const metadata={asset_id:asset.asset_id,version:asset.version,size:`${asset.width}×${asset.height}`,format:asset.format,source:asset.source_path,source_size:asset.source_size.join('×'),native_cell:asset.native_cell_size.join('×'),anchor:asset.anchor.join(', '),sha256:asset.variants['512'].sha256,usage:asset.usage,fallback:asset.fallback,license:asset.license_status,approval:asset.approval_status,integration_status:asset.integration_status,resolution:asset.resolution_note};
    $('asset-detail').innerHTML=`<img class="dl-metadata-image" src="${base}/${asset.web_path}" alt="${escape(labels[asset.state])}"><dl>${Object.entries(metadata).map(([key,value])=>`<dt>${key}</dt><dd>${escape(value)}</dd>`).join('')}</dl>`;
    $('asset-dialog').showModal();
  });

  /* 候選聲音由共用展示播放器管理，重播與離頁共用同一清理入口。 */
  const stopSounds=()=>window.LifeWorldSoundDemo.stopSounds();
  window.addEventListener('pagehide',()=>BirthUI.unmount());
  function hatch(){BirthUI.unmount();$('hatch-demo').innerHTML=BirthUI.view(LumiUI.render({pose:'welcome',size:'hero',motion:!$('reduced').checked}));BirthUI.mount({reducedMotion:$('reduced').checked});}
  $('restart-hatch').addEventListener('click',()=>{stopSounds();hatch();});
  $('reduced').addEventListener('change',()=>{document.body.classList.toggle('dl-reduced',$('reduced').checked);hatch();});
  const params=new URLSearchParams(location.search);
  if(params.get('section')==='audio')document.body.classList.add('dl-audio-only');
  $('quiet').checked=params.get('quiet')==='1';document.body.dataset.quiet=String($('quiet').checked);
  $('reduced').checked=params.get('reduced')==='1'||window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.body.classList.toggle('dl-reduced',$('reduced').checked);
  renderScenario();renderAssets();hatch();
})();
