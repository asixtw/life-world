'use strict';
// 只映射後端已驗權的唯讀資料；不從總投入反推日期分布。
function mapGoalToDashboardVM(data) { return {...data, title:data.goal.title, status:data.goal.status}; }
const DashboardUI = (() => {
  let owner = null;
  const cache = new Map();
  function clear() { owner=null; cache.clear(); ScheduleUI.clear(); }
  async function load(id) {
    const currentOwner=state.me?.owner_id, generation=state.renderGeneration;
    if(owner!==currentOwner){clear();owner=currentOwner;}
    try {
      const data=mapGoalToDashboardVM(await api('/goals/'+encodeURIComponent(id)+'/dashboard'));
      // 切帳號或舊切頁回應不可寫入目前帳號快照。
      if(state.me?.owner_id!==currentOwner||generation!==state.renderGeneration)return null;
      cache.set(id,data); return {...data,stale:false};
    } catch(error) {
      if([401,403,404].includes(error.status)){clear();if(error.status!==401)document.querySelector('#app').replaceChildren();throw error;}
      if(state.me?.owner_id!==currentOwner||generation!==state.renderGeneration)return null;
      return cache.has(id)?{...cache.get(id),stale:true}:{error:true};
    }
  }
  function view(vm, fallback=null) {
    if(!vm)return '';
    // 聚合暫時失敗時，保留已成功讀取的目標與習慣，未知統計不可補零。
    if(vm.error&&fallback){vm={error:false,partial:true,goal:fallback,today:fallback.today,timezone:fallback.schedule_timezone||state.me.timezone,habits:fallback.actions.map(a=>({actionId:a.id,title:a.title,unit:a.unit,progress:a.progress,target:a.target,scheduledDayCount:a.dates?.length??null,nextScheduledDate:null,scheduleDates:a.dates,quantityVersions:a.quantity_versions})),trend:null};}
    const retry='<button type="button" class="secondary" data-dashboard-retry>重新讀取進度</button>';
    if(vm.error)return `<section class="card" role="alert"><h2>目標總覽</h2><p>暫時無法讀取最新進度，請重試；沒有將錯誤當成零筆。</p>${retry}</section>`;
    const g=vm.goal, active=g.status==='active',live=GoalsUI.open(g),days=vm.trend?.days;
    const jump=(id,label)=>`<a class="text-button" href="#goal/${esc(g.id)}?section=${id}" aria-label="查看${esc(label)}">查看來源</a>`;
    const metric=(label,value,id)=>`<article class="card"><h3>${label}</h3><strong>${value??'暫無統計'}</strong>${jump(id,label)}</article>`;
    const action=active?link('record?goal='+g.id,'記錄經歷','primary'):link('goal/'+g.id+'?section=gd-records',g.status==='awaiting_review'?'先回顧這段挑戰':g.status==='needs_setup'?'補齊目標設定':'查看旅程紀錄','primary');
    const peak=Math.max(1,...(days||[]).map(d=>d.confirmedExperienceCount));
    return `<section class="dashboard" aria-label="目標儀表板"><header class="card goal-hero"><h1>${esc(g.title)}</h1><p class="tag">${esc(GoalsUI.labels[g.status])}</p><p>想達成的成果：${esc(g.outcome)}</p><p>${esc(g.start_date||'尚未設定')} ～ ${esc(g.deadline||'尚未設定')}</p><p>目標時區：${esc(vm.timezone)} · 今天 ${esc(vm.today)}</p><div class="button-row">${action}${active?'<button type="button" class="secondary" data-gj="schedule">調整未來安排</button>':''}${link('goals','返回目標花園','text-button')}</div>${vm.updatedAt?'<p class="small">資料讀取時間：'+esc(time(vm.updatedAt))+'</p>':''}${vm.stale||vm.partial?`<div role="alert" class="callout">${vm.partial?'部分資料暫時無法讀取；已讀取的目標仍保留，缺值不是零。':'暫時無法讀取最新進度，以下為上次資料，可能非最新。'}${retry}</div>`:''}</header>
    <section aria-labelledby="gd-overview"><h2 id="gd-overview">目前進展</h2><div class="dash-overview">${metric('最近七天已採計經歷',days?.reduce((n,d)=>n+d.confirmedExperienceCount,0),'gd-week')}${metric('今日已安排習慣',vm.partial?null:vm.habits.filter(a=>a.plannedToday).length,'gd-today')}${metric('待核對貢獻',vm.pendingContributions?.length,'gd-records')}</div><p class="small">已安排不是已完成；習慣投入不代表最終成果完成率。</p></section>
    <section class="card" id="gd-today" tabindex="-1"><h2>今天可以做的一小步</h2>${vm.partial?'<p>暫無今日安排統計。</p>':vm.habits.filter(a=>a.plannedToday).map(a=>`<article><h3>${esc(a.title)}</h3><p>已安排 ${esc(a.plannedQuantityToday)} ${esc(a.unit)} · ${a.confirmedToday?'已有確認投入（不代表當日已達標）':'尚無已採計投入'}</p>${active?link('record?goal='+g.id+'&action='+a.actionId,'記錄投入：'+esc(a.title),'text-button'):''}</article>`).join('')||'<p>今天沒有安排，依自己的節奏就好；也可以記錄真實經歷。</p>'}</section>
    <section><h2>三個重要習慣</h2><div class="dash-habits">${vm.habits.map(a=>`<article class="card dash-habit"><h3>${esc(a.title)}</h3><p>已確認投入：${esc(a.progress)} ${esc(a.unit)}</p><p>目標投入：${esc(a.target??'暫無統計')} ${esc(a.unit)}</p>${Number(a.target)>0?`<progress aria-label="${esc(a.title)}已確認投入" max="${esc(a.target)}" value="${esc(a.progress)}"></progress>`:'<p>尚無目標投入量。</p>'}<p>${a.scheduledDayCount===null?'安排天數暫無統計':'已安排 '+a.scheduledDayCount+' 天'}</p><p>下一安排：${esc(a.nextScheduledDate||'尚無後續安排')}</p>${active?link('record?goal='+g.id+'&action='+a.actionId,'記錄'+esc(a.title),'text-button'):''}${ScheduleUI.disclosure({id:g.id,revision:g.revision,start:g.start_date,end:g.deadline,today:vm.today,status:g.status,zone:vm.timezone,record:(fallback?.allowed_actions||[]).includes('record')},{id:a.actionId,title:a.title,unit:a.unit,dates:a.scheduleDates??null})}</article>`).join('')}</div></section>
    <section class="card" id="gd-week" tabindex="-1"><h2>最近七天</h2><p>有已採計投入的經歷筆數，同一經歷只算一次；依實際發生日。</p>${days?`<div class="dash-week" aria-label="七日已採計經歷圖表">${days.map(d=>`<div class="dash-day"><div class="dash-bar-space"><svg class="dash-bar" viewBox="0 0 20 100" aria-hidden="true"><rect x="2" y="${100-d.confirmedExperienceCount/peak*100}" width="16" height="${d.confirmedExperienceCount/peak*100}" fill="currentColor" /></svg></div><span>${esc(d.date.slice(5))}</span><strong>${d.confirmedExperienceCount}</strong>${d.confirmedExperienceCount?`<button type="button" class="text-button" data-dashboard-day="${esc(d.date)}" aria-label="查看 ${esc(d.date)} 的 ${d.confirmedExperienceCount} 筆經歷">明細</button>`:'<span class="small">尚無紀錄</span>'}</div>`).join('')}</div><div class="dash-day-sources">${days.filter(d=>d.confirmedExperienceCount).map(d=>`<details id="dashboard-day-${esc(d.date)}"><summary>${esc(d.date)}：${d.confirmedExperienceCount} 筆已採計經歷</summary>${d.experiences.map(e=>`<article><h3>${esc(e.summary)}</h3><p>${esc(e.raw_text)}</p><p>實際發生時間：${esc(e.occurred_at)}</p>${link('history','查看經歷收藏','text-button')}</article>`).join('')}</details>`).join('')}</div>`:`<p>七日統計暫時無法讀取，請使用上方重新讀取進度。</p>`}</section>
    <section class="card" id="gd-followup"><h2>草稿與後續任務</h2><p>${vm.unconfirmedDraftCount??'暫無統計'} 份伺服器未確認草稿（不含此裝置素材）</p>${(vm.drafts||[]).map(d=>link('review/'+d.id,'核對草稿：'+esc(d.raw_text.slice(0,50)),'text-button')).join('')}${(vm.openTasks||[]).map(t=>`<label class="check-line"><input type="checkbox" data-task="${esc(t.id)}" ${vm.stale?'disabled':''}>${esc(t.title)}</label>`).join('')||(vm.partial?'<p>後續任務暫無統計。</p>':'<p>目前沒有未完成的後續任務。</p>')}</section></section>`;
  }
  document.addEventListener('click',event=>{if(event.target.closest('[data-dashboard-retry]'))render().catch(showError);const day=event.target.closest('[data-dashboard-day]');if(day){const panel=document.getElementById('dashboard-day-'+day.dataset.dashboardDay);if(panel){panel.open=true;panel.querySelector('summary').focus();panel.scrollIntoView({block:'nearest'});}}});
  return {load,view,clear};
})();
