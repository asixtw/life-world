"""發布保護：在現役來源上只增加介紹介面，其他既有內容必須逐byte保留。"""
from pathlib import Path
import json,re,subprocess,importlib.util

ROOT=Path(__file__).resolve().parents[1]
BASE='421e9b95c21a4abd1059f3c235545649e12ca830'


def original(name):return subprocess.check_output(['git','show',BASE+':'+name],text=True)


def test_original_backend_and_product_ui_are_preserved():
    main=(ROOT/'app/main.py').read_text()
    main,count=re.subn(r"    @app.api_route\('/intro', methods=\['GET','HEAD'\].*?\n\n(?=    @app.get\('/'\,)",'',main,flags=re.S)
    assert count==1
    main=main.replace("('/','/intro','/intro/','/health'","('/','/health'",1)
    assert main==original('app/main.py')
    script=(ROOT/'app/static/app.js').read_text()
    script=script.replace('  if(window.IntroEntry?.shouldOffer(state.me))return window.IntroEntry.choice(); // 介紹偏好只影響提示，不取代後端的新手狀態。\n','',1)
    script=script.replace("    if(action==='intro-direct'){window.IntroEntry?.dismiss();await render();$('#app [data-action=guest],#app [data-action=entry-guest]')?.focus();return;}\n",'',1)
    script=script.split('\n// 返回快取歡迎頁或另一分頁完成介紹時，只更新提示，不打斷產品內任何表單。')[0]
    assert script==original('app/static/app.js')
    html=(ROOT/'app/static/index.html').read_text()
    for line in ['  <link rel="stylesheet" href="/static/intro-entry.css">\n','  <script src="/static/intro-preference.js" defer></script>\n','  <script src="/static/intro-entry.js" defer></script>\n']:
        assert html.count(line)==1;html=html.replace(line,'',1)
    html=html.replace('<details class="intro-menu"><summary>關於</summary><a href="/intro" target="_blank" rel="noopener">認識 Life World（另開分頁）</a></details>','',1)
    assert html==original('app/static/index.html')


def test_release_context_is_only_thirty_reviewed_files(tmp_path):
    spec=importlib.util.spec_from_file_location('intro_context',ROOT/'scripts/prepare_public_intro_context.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    target=tmp_path/'context';module.build(target)
    names={str(p.relative_to(target/'overlay')) for p in (target/'overlay').rglob('*') if p.is_file()}
    assert len(names)==30 and 'main.py' in names and 'static/app.js' in names
    assert not any(name.endswith(('.db','.sqlite3','.env')) for name in names)
    docker=(target/'Dockerfile').read_text()
    assert '@sha256:c3ec8b6a3a71f1101f143cd08841a20b3ceba1c227f93b6bbc637e1e7dc3ae55' in docker
    assert all('\n'+command+' ' not in docker for command in ['RUN','CMD','USER','ENTRYPOINT'])
