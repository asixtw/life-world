'use strict';
// 純呈現適配層，不重算後端目標量，也不將安排推論成已完成。
function mapHomeHabitOverview(goal,trustedToday=goal?.today){
  if(!goal||!['active','awaiting_review','needs_setup'].includes(goal.status))return {dataStatus:'no-goal',items:[]};
  const base={goalId:goal.id,goalTitle:goal.title,goalStatus:goal.status,today:trustedToday,timezone:goal.schedule_timezone};
  if(!Array.isArray(goal.actions)||goal.actions.length!==3)return {...base,dataStatus:'incomplete',items:[]};
  const decimal=value=>typeof value==='string'&&/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value)?value:null;
  const validDate=value=>typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)&&!Number.isNaN(Date.parse(value+'T12:00:00Z'))&&new Date(value+'T12:00:00Z').toISOString().slice(0,10)===value;
  const trusted=!!goal.schedule_timezone&&validDate(trustedToday)&&validDate(goal.start_date)&&validDate(goal.deadline);
  const items=goal.actions.map(a=>{
    const known=trusted&&Array.isArray(a.dates)&&a.dates.every(d=>validDate(d)&&d>=goal.start_date&&d<=goal.deadline);
    const next=known?[...a.dates].filter(d=>d>=trustedToday).sort()[0]||null:null;
    return {actionId:a.id,title:a.title,progress:decimal(a.progress),target:decimal(a.target),unit:typeof a.unit==='string'&&a.unit.trim()?a.unit:null,nextScheduledDate:next,scheduleStatus:!known?'unavailable':next?'known':'none'};
  });
  return {...base,items,dataStatus:items.every(a=>a.progress!==null&&a.target!==null&&a.unit)?'ready':'unavailable'};
}
function homeScheduleLabel(item,today){
  if(item.scheduleStatus==='unavailable')return '下次安排暫無法顯示';
  if(item.scheduleStatus==='none')return '目前沒有後續安排';
  if(item.nextScheduledDate===today)return '今天有安排';
  const next=new Date(today+'T12:00:00Z');next.setUTCDate(next.getUTCDate()+1);
  if(item.nextScheduledDate===next.toISOString().slice(0,10))return '明天有安排';
  return '下次安排 '+(item.nextScheduledDate.slice(0,4)===today.slice(0,4)?item.nextScheduledDate.slice(5):item.nextScheduledDate).replaceAll('-','/');
}
function renderHomeHabitRows(vm,openRow){
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  return `<div class="home-habit-rows" aria-label="我的三個習慣">${vm.items.map(a=>openRow(a.actionId,`<strong>${esc(a.title||'名稱暫無法顯示')}</strong><span>已確認 ${esc(a.progress??'—')} / ${esc(a.target??'—')} ${esc(a.unit||'單位暫無法顯示')}</span><small>${esc(homeScheduleLabel(a,vm.today))}</small>`)).join('')}</div>`;
}
if(typeof module!=='undefined')module.exports={mapHomeHabitOverview,homeScheduleLabel,renderHomeHabitRows};
