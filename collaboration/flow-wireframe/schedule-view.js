'use strict';
// 正式App與原型共用控制器，由adapter供應已授權資料；不自行採計或寫入。
const HabitScheduleView = {
  create(env){
    const m=HabitScheduleModel,cache=new Map(),registrations=new Map();let owner=null,generation=0;
    const h=env.escape;
    function clear(){generation++;cache.clear();registrations.clear();owner=env.owner();}
    function disclosure(g,a){
      if(owner!==env.owner())clear();
      const key=[owner,g.id,a.id,g.revision||0].join(':');
      const unavailable=!g.start||!g.end||a.dates===null;
      let s=cache.get(key);
      if(!s){s={month:unavailable?null:m.initial(g,a.dates),selected:null,open:false,data:null,error:'',loading:false,epoch:0,scroll:null};cache.set(key,s);}
      registrations.set(key,{g,a,s});
      return `<details class="habit-schedule" data-hs-key="${h(key)}" ${s.open?'open':''}><summary aria-expanded="${s.open}">${s.open?'收合':'查看'}日期與用量：${h(a.title)}</summary><div class="hs-body">${unavailable?'<p>舊版排程或目標期間尚未完整設定，請先補齊設定；不以星期規律推算已確認日期。</p>':'<p>展開後載入唯讀月份；查看不會修改安排。</p>'}</div></details>`;
    }
    function draw(host,r){
      if(!host.isConnected)return;
      const {g,a,s}=r,body=host.querySelector('.hs-body');if(!s.month)return;
      const range=m.bounds(g,s.month),data=s.data,month=data?.month||s.month;
      const row=s.selected&&data?.rows.find(d=>d.date===s.selected),scheduled=!!row?.action_ids.includes(a.id);
      const names=['一','二','三','四','五','六','日'];
      const selectedLabel=s.selected?new Intl.DateTimeFormat('zh-TW',{weekday:'long',timeZone:'UTC'}).format(new Date(s.selected+'T12:00:00Z')):'';
      body.setAttribute('aria-busy',String(s.loading));
      body.innerHTML=`<div class="hs-month"><b tabindex="-1">${h(month.replace('-',' 年 '))} 月</b><div><button type="button" data-hs="prev" ${s.loading||!m.bounds(g,m.shift(month,-1))?'disabled':''} aria-label="${h(a.title)}上一月">上一月</button><button type="button" data-hs="next" ${s.loading||!m.bounds(g,m.shift(month,1))?'disabled':''} aria-label="${h(a.title)}下一月">下一月</button></div></div>${s.loading?'<p role="status">正在載入月份…</p>':''}${s.error?`<p role="alert">${h(s.error)} <button type="button" data-hs="retry">重試月份</button></p>`:''}${data?`<div class="hs-weekdays" aria-hidden="true">${names.map(n=>'<span>'+n+'</span>').join('')}</div><div class="hs-grid" aria-label="${h(a.title+' '+month+' 月曆')}">${m.cells(month).map(date=>{if(!date)return '<span aria-hidden="true"></span>';const d=data.rows.find(r=>r.date===date),inRange=!!d,arranged=d?.action_ids.includes(a.id);return `<button type="button" data-hs="day" data-date="${date}" ${!inRange||s.loading?'disabled':''} aria-pressed="${date===s.selected}" ${date===g.today?'aria-current="date"':''} aria-label="${date} ${!inRange?'目標期間外':arranged?'已安排':'未安排'}"><span>${Number(date.slice(-2))}</span>${arranged?'<span class="hs-dot" aria-hidden="true">●</span>':''}</button>`;}).join('')}</div><p class="small">● 已安排 · 外框表示已選日期；查看不代表完成。</p>${!data.rows.some(r=>r.action_ids.includes(a.id))?'<p>這個月尚未安排此習慣。</p>':''}`:''}${s.selected&&row?`<section class="hs-day-detail" aria-live="polite"><h4>${h(s.selected)}（${selectedLabel}）</h4><p>${scheduled?'已安排；原訂預期量：'+h(row.planned_quantities[a.id])+' '+h(a.unit):'這天沒有安排這項習慣'}</p><p>當日已確認投入：暫無逐日統計。</p>${g.record&&s.selected<=g.today?'<button type="button" data-hs="record">記錄這次投入</button>':''}</section>`:'<p>選擇目標期間內的日期，查看當日預期用量。</p>'}`;
    }
    async function load(host,r,wanted){
      const {g,a,s}=r,range=m.bounds(g,wanted);if(!range)return;
      const focusAction=host.contains(document.activeElement)?document.activeElement.dataset.hs:null;
      const epoch=++s.epoch,gen=generation,scope=owner;s.loading=true;s.error='';draw(host,r);
      try{
        const rows=await env.load(g,a,range);
        if(!Array.isArray(rows))throw new Error('月份資料格式不正確');
        if(epoch!==s.epoch||gen!==generation||scope!==env.owner()||!host.isConnected)return;
        s.month=wanted;s.data={month:wanted,rows};s.selected=rows.some(d=>d.date===s.selected)?s.selected:rows.find(d=>d.date===g.today)?.date||null;
      }catch(error){
        if(epoch!==s.epoch||gen!==generation||scope!==env.owner()||!host.isConnected)return;
        if([401,403,404].includes(error.status)){clear();host.querySelector('.hs-body').textContent='無法存取此排程，請重新確認登入與權限。';return;}
        s.failedMonth=wanted;s.error='無法載入月份；保留上次已讀資料，請重試。';
      }finally{if(epoch===s.epoch&&gen===generation){s.loading=false;const restoreFocus=focusAction&&(document.activeElement===document.body||host.contains(document.activeElement));draw(host,r);if(restoreFocus)(host.querySelector(`[data-hs="${focusAction}"]:not([disabled])`)||host.querySelector('.hs-month b'))?.focus({preventScroll:true});}}
    }
    function mount(){
      if(owner!==env.owner())clear();
      for(const host of document.querySelectorAll('.habit-schedule')){const r=registrations.get(host.dataset.hsKey);if(!r)continue;if(r.s.open){draw(host,r);if(r.s.month&&!r.s.data&&!r.s.loading)void load(host,r,r.s.month);if(r.s.scroll!==null)window.scrollTo(0,r.s.scroll);}}
    }
    function leave(){generation++;for(const host of document.querySelectorAll('.habit-schedule')){const r=registrations.get(host.dataset.hsKey);if(r){r.s.open=host.open;r.s.loading=false;r.s.scroll=window.scrollY;}}}
    document.addEventListener('toggle',event=>{const host=event.target;if(!host.matches?.('.habit-schedule'))return;const r=registrations.get(host.dataset.hsKey);if(!r)return;r.s.open=host.open;const summary=host.querySelector('summary');summary.textContent=(host.open?'收合':'查看')+'日期與用量：'+r.a.title;summary.setAttribute('aria-expanded',String(host.open));if(host.open){draw(host,r);if(r.s.month&&!r.s.data&&!r.s.loading)void load(host,r,r.s.month);}},true);
    document.addEventListener('click',event=>{const control=event.target.closest('[data-hs]'),host=control?.closest('.habit-schedule');if(!host)return;const r=registrations.get(host.dataset.hsKey);if(!r)return;const action=control.dataset.hs;if(action==='prev'||action==='next')void load(host,r,m.shift(r.s.month,action==='prev'?-1:1));if(action==='retry')void load(host,r,r.s.failedMonth||r.s.month);if(action==='day'){r.s.selected=control.dataset.date;draw(host,r);host.querySelector(`[data-date="${r.s.selected}"]`)?.focus({preventScroll:true});}if(action==='record'&&r.g.record&&r.s.selected<=r.g.today)env.record(r.g,r.a,r.s.selected);});
    return {disclosure,mount,leave,clear};
  }
};
