"""Node 執行真實人物表單，候選必須來自目前 Owner。"""
import json
import os
import subprocess
from pathlib import Path
from html.parser import HTMLParser


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.inputs = []; self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'input': self.inputs.append(dict(attrs))


def test_reusable_choices_empty_legacy_escape_and_owner():
    script = r'''
const fs=require('fs'),vm=require('vm');global.window={};
vm.runInThisContext(fs.readFileSync('app/static/relationships.js','utf8'));const PeopleUI=window.PeopleUI;
let html='',state={me:{owner_id:'a'},world:{user:{owner_id:'a'},people:[{id:'1',roles:[' 合作 ','合作','舊、完整角色'],tags:['<img src=x>','學校專題'],common_context:'資訊管理課'}]}};
const esc=v=>String(v??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
PeopleUI.initialize({state,esc,dialog:x=>html=x});
PeopleUI.openPersonEditor(); const first=html;
PeopleUI.openPersonEditor({id:'1',revision:1,name:'甲',roles:['舊、完整角色'],tags:['學校專題'],common_context:'資訊管理課'}); const edit=html;
state.me={owner_id:'b'};PeopleUI.openPersonEditor();const stale=html;state.world={user:{owner_id:'b'},people:[]};PeopleUI.openPersonEditor();
console.log(JSON.stringify({first,edit,stale,empty:html}));
'''
    node = os.environ['LIFEWORLD_NODE']
    result = subprocess.run([node, '-e', script], cwd=Path(__file__).parents[1], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    inputs = Inputs(data['first']).inputs
    assert len([x for x in inputs if x.get('name') == 'roles_selected' and x.get('value') == '合作']) == 1
    assert any(x.get('name') == 'tags_selected' and x.get('value') == '<img src=x>' for x in inputs)
    assert '<img src=x>' not in data['first']
    assert '資訊管理課' in data['first']
    assert any(x.get('name') == 'roles_selected' and x.get('value') == '舊、完整角色' and 'checked' in x for x in Inputs(data['edit']).inputs)
    assert '學校專題' not in data['stale']
    assert '學校專題' not in data['empty'] and '資訊管理課' not in data['empty']
