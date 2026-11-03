"""首頁適配層由pytest執行實際JS，保留Decimal字串與未知／無安排區別。"""
import os,shutil,subprocess
import pytest


@pytest.mark.parametrize('script',[
 "const v=m.mapHomeHabitOverview(g);assert.equal(v.items[0].progress,'0.500001');assert.equal(v.items[0].nextScheduledDate,'2026-12-31');assert.equal(v.items[0].scheduleStatus,'known');",
 "assert.equal(m.mapHomeHabitOverview({...g,actions:g.actions.slice(1)}).dataStatus,'incomplete');assert.equal(g.status,'active');",
 "g.actions[0].dates=null;assert.equal(m.mapHomeHabitOverview(g).items[0].scheduleStatus,'unavailable');",
 "g.actions[0].dates=['2026-12-30'];assert.equal(m.mapHomeHabitOverview(g).items[0].scheduleStatus,'none');",
 "assert.equal(m.mapHomeHabitOverview(null).dataStatus,'no-goal');assert.equal(m.mapHomeHabitOverview({...g,status:'completed'}).dataStatus,'no-goal');",
 "g.actions[0].progress=null;assert.equal(m.mapHomeHabitOverview(g).items[0].progress,null);assert.equal(m.mapHomeHabitOverview({...g,today:null}).items[0].scheduleStatus,'unavailable');",
 "g.actions[0].title='<img src=x>';const text=m.renderHomeHabitRows(m.mapHomeHabitOverview(g),(id,body)=>body);assert.ok(text.includes('&lt;img'));assert.ok(!text.includes('<img'));assert.equal(m.homeScheduleLabel({scheduleStatus:'known',nextScheduledDate:'2027-01-01'},'2026-12-31'),'明天有安排');"
])
def test_home_adapter(script):
    node=os.environ.get('LIFEWORLD_NODE') or shutil.which('node')
    if not node:pytest.skip('需Node驗證共用首頁JS，請設定LIFEWORLD_NODE')
    code="const assert=require('node:assert/strict'),m=require('./app/static/home-habits.js');const g={id:'g',title:'目標',status:'active',start_date:'2026-12-01',deadline:'2027-02-01',schedule_timezone:'Asia/Taipei',today:'2026-12-31',actions:[0,1,2].map(i=>({id:'a'+i,title:'習慣'+i,unit:'次',progress:'0.500001',target:'10',dates:['2026-12-31','2027-01-01']}))};"+script
    result=subprocess.run([node,'-e',code],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_formal_and_prototype_use_same_mapper():
    """保持兩個 host 的純資料規則一致，避免原型掩蓋正式差異。"""
    from pathlib import Path
    assert Path('app/static/home-habits.js').read_bytes()==Path('collaboration/flow-wireframe/home-habits.js').read_bytes()
