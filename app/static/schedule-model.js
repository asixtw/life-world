'use strict';
// 純日曆運算只處理日期，不將預期量換算成實際投入。
const HabitScheduleModel = (() => {
  const iso=d=>d.toISOString().slice(0,10);
  const first=month=>month+'-01';
  const last=month=>{const [y,m]=month.split('-').map(Number);return iso(new Date(Date.UTC(y,m,0,12)));};
  function shift(month,n){const [y,m]=month.split('-').map(Number);return iso(new Date(Date.UTC(y,m-1+n,1,12))).slice(0,7);}
  function bounds(g,month){if(!g.start||!g.end)return null;const start=first(month)>g.start?first(month):g.start,end=last(month)<g.end?last(month):g.end;return start<=end?{start,end}:null;}
  function initial(g,dates){const wanted=['completed','ended'].includes(g.status)?[...(dates||[])].sort().at(-1)||g.start:g.today;const month=(wanted||g.start).slice(0,7);return month<g.start.slice(0,7)?g.start.slice(0,7):month>g.end.slice(0,7)?g.end.slice(0,7):month;}
  function cells(month){const offset=(new Date(first(month)+'T12:00:00Z').getUTCDay()+6)%7;return [...Array(offset).fill(null),...Array.from({length:Number(last(month).slice(-2))},(_,i)=>month+'-'+String(i+1).padStart(2,'0'))];}
  return {bounds,initial,cells,shift};
})();
if(typeof module!=='undefined')module.exports=HabitScheduleModel;
