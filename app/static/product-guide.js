/* 新手導覽獨立於首次建立世界的 onboarding；只記裝置教學偏好，不取得 API 寫入能力。 */
const ProductGuideUI = (() => {
  'use strict';
  const version=1,introKey='lifeworld:intro:v2',memory=new Map();
  let c,act=0;
  function read(key){
    if(memory.has(key))return memory.get(key);
    const records=[];
    for(const store of ['localStorage','sessionStorage'])try{const value=JSON.parse(window[store].getItem(key)||'null');if(value?.version===version)records.push(value);}catch{}
    // localStorage 額度滿時可能仍能讀舊值；使用較新的 session 退路，不能讓舊偏好蓋過剛完成的選擇。
    return records.sort((a,b)=>(b.updatedAt||0)-(a.updatedAt||0))[0]||{version};
  }
  function write(key,value){
    const record={...value,version,updatedAt:Date.now()};memory.set(key,record);
    for(const store of ['localStorage','sessionStorage'])try{window[store].setItem(key,JSON.stringify(record));return;}catch{}
  }
  const key=()=>c.state.me?.owner_id?'lifeworld:guide:v1:'+c.state.me.owner_id:null;
  const preference=()=>key()?read(key()):{version};
  function change(values){if(key())write(key(),{...preference(),...values});}
  function shouldIntroduce(){return !read(introKey).seen;}
  const resume=()=>!c.state.me?'welcome':!c.state.me.bio?'profile':!c.state.me.lumi_hatched?'goal-new':'world';
  const nextAction=()=>!c.state.me?'welcome':!c.state.me.lumi_hatched?resume():'record';
  const artwork=name=>'/static/intro/assets/art/v1/'+name+'-512.png';
  function actView(){
    const titles=['你明明做了很多事，卻常常覺得自己沒什麼進步。','不用寫日記，一句話就能記下今天。','原來，你已經走了這麼遠。'];
    const themes=['有些努力，連自己都忘了','讓努力留下來','看得見的成長'];
    const leads=['每天忙著工作、學習、生活。','做了什麼、學到了什麼、遇見了誰。','你的努力會慢慢累積成自己的成長紀錄。'];
    const details=['有些努力很小，小到過幾天，連自己都忘了。','Life World 可以幫你整理成紀錄和下一步，重要內容都由你自己確認。','而 Lumi 和這個小世界，也會陪著你一起成長。'];
    const example='<div data-intro-example class="guide-example-demo"><p class="small muted">固定虛構示例 · 不呼叫 AI</p><div class="guide-demo-row"><span>今天的紀錄</span><p>今天終於把簡報做完了，雖然花了好幾天。</p></div><div class="guide-demo-row guide-demo-summary"><span>整理成你的經歷</span><p>完成了一份重要簡報</p></div><div class="guide-demo-row guide-demo-next"><span>下一步建議</span><p>準備分享或發表</p></div><small>示範內容。正式保存與進度更新仍需你確認。</small></div>';
    const scene=act===0?'<div class="guide-fragments"><span>忙碌的一天</span><p>做完了一份簡報</p><p>學會一個新方法</p><p>和朋友聊了聊</p><small>過幾天，還記得多少？</small></div>':act===1?example:`<div class="guide-room" aria-hidden="true"><img class="guide-room-cabinet" src="/static/art/cabinet.png" width="512" height="512" alt=""><img class="guide-room-plant" src="/static/art/plant.png" width="512" height="512" alt=""><img class="guide-lumi" src="${artwork('lumi-welcome')}" width="512" height="512" alt=""></div><p class="small muted">Lumi 與世界變化示意，非實際帳號。</p>`;
    return `<section class="guide-intro guide-act-${act}" aria-labelledby="guide-intro-title"><div class="guide-intro-top"><p class="eyebrow">${themes[act]} · ${act+1} / 3</p><button type="button" class="text-button" data-guide-skip>跳過</button></div><div class="guide-intro-copy"><h1 id="guide-intro-title" tabindex="-1">${titles[act]}</h1><p class="guide-lead">${leads[act]}</p><p>${details[act]}</p>${act===2?'<p class="guide-gentle">不用每天都很厲害，只要願意繼續就好。</p>':''}</div><div class="guide-scene">${scene}</div><div class="guide-intro-actions"><div class="button-row">${act?'<button type="button" class="secondary" data-guide-prev>上一步</button>':''}<button type="button" class="primary" data-guide-next>${['下一步','看看接下來會發生什麼','開始我的世界'][act]}</button></div><p class="small muted">約 20 秒，可隨時跳過或重看。介紹不會建立帳號或寫入資料。</p></div></section>`;
  }
  function intro(){act=0;return actView();}
  const topics=[
    ['goal','先給自己一個方向','先選擇一件你真正想完成的事情。沿用一個目標、三個習慣與日期設定。','例如：讀完一本書。習慣可以是閱讀 10 分鐘、寫一句心得、回想下一步。請填你真正想做的事，示例不會自動填入。'],
    ['record','記下真實發生的事','文字就能開始，照片與語音依目前功能選用，不必先開啟 AI。','四步：記錄經歷 → 目標與實際活動量（可略過）→ 人物關聯（可沒有）→ 檢視並確認。'],
    ['confirm','整理之後，由你確認','AI 輸出只是可編輯草稿。未選用 AI 不呼叫模型，外部處理仍需現有授權。','最後確認前可修改摘要、活動量、人物、來源與任務。AI 不能自行宣告目標完成；草稿不等於正式進度。'],
    ['world','讓努力留下回應','真實投入經過確認後，才依既有規則更新進度、任務及獎勵。','Lumi 與世界陪你回望成長。教學不額外發獎、不建立完成紀錄，也不會替你確認成果。']
  ];
  function tutorial(){
    return `<div class="guide-tutorial narrow"><p class="eyebrow">使用教學 · 隨時可以重看</p><h1 tabindex="-1">照自己的步調，認識 Life World</h1><p>先看一個容易理解的閱讀示例，再回到你的真實操作。這裡不會建立任何示例資料。</p>${topics.map(([id,title,copy,detail],i)=>`<article class="card"><h2>${i+1}. ${title}</h2><p>${copy}</p><details><summary>看看怎麼做</summary><p>${detail}</p></details></article>`).join('')}<div class="card"><h2>把世界放在手邊</h2><p>了解產品之後，再依需要加入主畫面；它不是 App Store 安裝，也不代表離線可用。</p><button type="button" class="secondary" data-pwa-open>加到手機主畫面</button></div><div class="button-row"><button type="button" class="primary" data-guide-start>回到操作，邊做邊看</button><button type="button" class="secondary" data-guide-return>返回產品</button><button type="button" class="text-button" data-guide-open="intro">重看三幕介紹</button></div><details class="space-top"><summary>關於這份教學</summary><p>產品介紹記在這台裝置；操作提示則分別記在各帳號的此瀏覽器。換裝置可重看；無法儲存偏好也能正常使用。</p><a href="/intro/v05/">重播原版完整 v05 動畫介紹</a></details></div>`;
  }
  function mount(path){
    const pref=preference(),me=c.state.me;
    if(['intro','tutorial'].includes(path)){document.body.classList.add('guide-view');return;}
    document.body.classList.remove('guide-view');
    if(me&&pref.installOffer&&path==='world'){offerInstall();document.dispatchEvent(new Event('lifeworld:guide-rendered'));}
    if(!me||pref.paused)return;
    // 已有歷史的帳號只主動開教學時出現提示；不把「看過」當成業務完成。
    if(c.state.world?.experiences?.length&&!pref.started)return;
    const topic=path==='goal-new'?'goal':path==='record'?'record':path.startsWith('review/')?'confirm':path==='world'?'world':null;
    if(!topic||pref[topic]||(topic==='goal'&&Number(document.querySelector('#goal-form')?.dataset.step)>0))return;
    const [id,title,copy,detail]=topics.find(t=>t[0]===topic),aside=document.createElement('aside');
    aside.className='guide-context callout';aside.dataset.guideContext=id;aside.setAttribute('aria-label','操作提示');
    aside.innerHTML=`<strong>${title}</strong><p>${copy}</p><details><summary>看看閱讀示例</summary><p>${detail}</p><small>示例不會自動填入或建立資料。</small></details><div class="button-row"><button type="button" class="text-button" data-guide-dismiss="${id}">知道了</button><button type="button" class="text-button" data-guide-pause>稍後繼續</button></div>`;
    const anchor=document.querySelector('#goal-form,#record-form,#review-form');if(anchor)anchor.before(aside);else document.querySelector('#app').prepend(aside);
    document.dispatchEvent(new Event('lifeworld:guide-rendered'));
  }
  function offerInstall(){
    if(!c.state.me||document.querySelector('[data-pwa-nudge]'))return;
    const card=document.createElement('aside');card.className='callout guide-install';card.dataset.pwaNudge='';
    card.innerHTML='<strong>這一步已經留下，讓世界更順手。</strong><p>想從手機主畫面開啟嗎？'+(c.state.me.status==='guest'?'你仍是訪客，請先確認帳號選單是否能保存世界。切換瀏覽器不會自動轉移資料。':'加入後仍需要網路，可能需要重新登入。')+'</p><div class="button-row"><button type="button" class="secondary" data-pwa-open>加到主畫面</button><button type="button" class="text-button" data-pwa-later>稍後再說</button></div>';
    document.querySelector('#app').append(card);
  }
  function confirmed(){change({installOffer:true});}
  function finish(){write(introKey,{seen:true});c.navigate(resume());}
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-guide-open],[data-guide-next],[data-guide-prev],[data-guide-skip],[data-guide-dismiss],[data-guide-pause],[data-guide-start],[data-guide-return]');
    if(!button||!c)return;
    document.querySelector('.intro-menu')?.removeAttribute('open');
    if(button.dataset.guideOpen){c.navigate(button.dataset.guideOpen);return;}
    if(button.hasAttribute('data-guide-next')||button.hasAttribute('data-guide-prev')){
      if(button.hasAttribute('data-guide-next')&&act===2){finish();return;}
      act+=button.hasAttribute('data-guide-prev')?-1:1;document.querySelector('.guide-intro').outerHTML=actView();document.querySelector('#guide-intro-title').focus();return;
    }
    if(button.hasAttribute('data-guide-skip')){finish();return;}
    if(button.dataset.guideDismiss){change({[button.dataset.guideDismiss]:true});button.closest('[data-guide-context]')?.remove();return;}
    if(button.hasAttribute('data-guide-pause')){change({paused:true});button.closest('[data-guide-context]')?.remove();return;}
    if(button.hasAttribute('data-guide-start')){change({started:true,paused:false});c.navigate(nextAction());return;}
    if(button.hasAttribute('data-guide-return'))c.navigate(resume());
  });
  document.addEventListener('keydown',event=>{if(event.key==='Escape'){const menu=document.querySelector('.intro-menu[open]');if(menu){menu.removeAttribute('open');menu.querySelector('summary').focus();}}});
  document.addEventListener('click',event=>{if(event.target.closest('[data-pwa-open]'))document.querySelector('.intro-menu')?.removeAttribute('open');});
  return {initialize:context=>{c=context;},shouldIntroduce,intro,tutorial,mount,confirmed};
})();
