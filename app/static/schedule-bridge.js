'use strict';
// 所有日期用量由既有calendar端點提供；不從今天用量回填歷史。
const ScheduleUI=HabitScheduleView.create({
  owner:()=>state.me?.owner_id,
  escape:value=>esc(value),
  load:(g,a,range)=>api('/goals/'+encodeURIComponent(g.id)+'/calendar?start='+range.start+'&end='+range.end),
  record:(g,a,date)=>{const route='record?goal='+g.id+'&action='+a.id+'&date='+date;if(state.dirty)leaveDialog(route);else navigate(route);}
});
