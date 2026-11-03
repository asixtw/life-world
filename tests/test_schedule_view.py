"""唯讀月份模型：由pytest驅動實際JavaScript，沒有用Python重寫另一份日期規則。"""
import os
import shutil
import subprocess
from pathlib import Path
import pytest


@pytest.mark.parametrize('script',[
 "const r=m.bounds(g,'2026-10');assert.deepEqual(r,{start:'2026-10-30',end:'2026-10-31'});",
 "assert.equal(m.cells('2028-02').filter(Boolean).length,29);assert.equal(m.shift('2026-12',1),'2027-01');",
 "assert.equal(m.initial({...g,status:'active',today:'2027-03-01'},[]),'2027-02');assert.equal(m.initial({...g,status:'completed'},['2026-12-05']),'2026-12');",
 "assert.equal(m.bounds(g,'2026-09'),null);assert.equal(m.cells('2026-11')[0],null);",
])
def test_schedule_month_model(script):
    node=os.environ.get('LIFEWORLD_NODE') or shutil.which('node')
    if not node:pytest.skip('需Node執行共用前端日期模型；可設定LIFEWORLD_NODE')
    code="const assert=require('node:assert/strict'),m=require('./app/static/schedule-model.js');const g={start:'2026-10-30',end:'2027-02-02',today:'2026-11-03',status:'active'};"+script
    result=subprocess.run([node,'-e',code],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_formal_and_prototype_share_same_schedule_controller():
    for name in ['schedule-model.js','schedule-view.js']:
        assert (Path('app/static')/name).read_bytes()==(Path('collaboration/flow-wireframe')/name).read_bytes()
