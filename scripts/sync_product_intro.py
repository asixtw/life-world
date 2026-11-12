"""將已確認的獨立介紹同步到產品靜態區，保留原型並產出可核對的來源雜湊。"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'app/static/intro'


def sync(source):
    """只複製HTML／CSS／JS實際引用的本機資源；不複製設計工作樹其他產品修改。"""
    source=source.resolve();html=(source/'index.html').read_text();javascript=(source/'preview.js').read_text()
    resources={name for name in re.findall(r'(?:src|href)="([^"]+)"',html) if not name.startswith(('#','http:','https:'))}
    resources.update(re.findall(r"url: '([^']+)'",javascript))
    resources.discard('config.js')
    TARGET.mkdir(parents=True,exist_ok=True);records=[]
    for name in sorted(resources):
        original=(source/name).resolve()
        if not original.is_relative_to(source):raise ValueError('素材路徑不得離開介紹來源')
        data=original.read_bytes()
        if name=='preview.js':data=re.sub(r"url: '([^']+)'",lambda m:"url: '/static/intro/"+m.group(1)+"'",data.decode()).encode()
        output=TARGET/name;output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(data)
        records.append({'path':name,'source_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    html=re.sub(r'((?:src|href)=")([^"#][^"]*)(")',lambda m:m.group(1)+'/static/intro/'+m.group(2)+m.group(3) if not m.group(2).startswith(('https:','http:')) else m.group(0),html)
    html=html.replace('<script src="/static/intro/config.js" defer></script>','<script src="/static/intro-preference.js" defer></script>\n  <script src="/static/intro/config.js" defer></script>\n  <script src="/static/intro/entry-bridge.js" defer></script>')
    html=html.replace('</head>','  <link rel="stylesheet" href="/static/intro/integration.css">\n</head>')
    html=html.replace('<span class="lw-edition">一顆蛋，一段新故事</span>','<a class="lw-link" href="/#welcome" data-intro-exit>直接進入產品</a>')
    html=html.replace('<button class="lw-button lw-primary" id="how-button"','<a class="lw-button lw-primary" id="product-entry" href="/#welcome">開始我的故事</a>\n            <button class="lw-button lw-secondary" id="how-button"')
    html=html.replace('            <a class="lw-button lw-secondary" id="product-entry" hidden>前往 Life World ↗</a>\n','')
    html=html.replace('本頁為獨立介紹候選，尚未接入正式產品；不代表展示功能皆已公開上線。','本頁是固定虛構示例。正式使用需進入產品，由你建立目標並確認經歷；介紹演出不會更新正式成果。')
    html=html.replace('互動流程示意・內容為固定虛構示例，不會儲存資料或呼叫 AI。','互動流程示意・固定虛構內容，不建立世界或呼叫 AI；僅在此瀏覽器記住已看過或跳過介紹。')
    (TARGET/'index.html').write_text(html)
    (TARGET/'config.js').write_text("/* 固定同來源產品入口；不接受查詢字串指定跳轉位置。 */\nwindow.LifeWorldIntroConfig=Object.freeze({productEntryUrl:'/#welcome'});\n")
    (TARGET/'entry-bridge.js').write_text('''/* 接入層僅記住介紹選擇；不接觸正式帳號／目標／孵化，也不改變原型狀態機。 */
(() => {
  'use strict';
  function mark(outcome) {
    if(window.LifeWorldIntroPreference.mark(outcome))return;
    if(document.querySelector('#intro-storage-note'))return;
    const note=document.createElement('p');note.id='intro-storage-note';note.className='lw-demo-note';note.setAttribute('role','status');
    note.textContent='此瀏覽器無法記住介紹偏好，下次可能再次提示。你仍可正常進入產品。';
    document.querySelector('#summary-copy').append(note);
  }
  document.addEventListener('lifeworld:intro-finished',event=>mark(event.detail?.outcome));
  document.querySelectorAll('[data-intro-exit],#product-entry').forEach(link=>link.addEventListener('click',()=>mark('skipped')));
})();
''')
    (TARGET/'integration.css').write_text('''/* 接入頁補充；其餘構圖與破殼完全沿用獨立原型。 */
.lw-preview .lw-header-actions{gap:16px;flex-wrap:wrap;justify-content:flex-end;}
.lw-preview .lw-header-actions .lw-link{display:flex;align-items:center;}
@media(max-width:760px){.lw-preview .lw-header{flex-wrap:wrap;}.lw-preview .lw-header-actions{margin-left:auto;gap:8px;}}
''')
    # 完整來源清單另存於文件，避免把未使用舊素材誤稱為本次上架。
    audit=ROOT/'docs/intro-integration';audit.mkdir(parents=True,exist_ok=True)
    (audit/'SOURCE_ASSETS.json').write_bytes((source/'assets/manifest.json').read_bytes())
    manifest={'date':'2026-11-13','source':'LifeWorld_Design_Language_v1/collaboration/onboarding-preview','product_base':'421e9b95c21a4abd1059f3c235545649e12ca830','status':'reviewed_release_payload','source_index_sha256':hashlib.sha256((source/'index.html').read_bytes()).hexdigest(),'copied':records,'generated':[]}
    for name in ['index.html','config.js','entry-bridge.js','integration.css']:
        data=(TARGET/name).read_bytes();manifest['generated'].append({'path':name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    (TARGET/'asset-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(f'Copied {len(records)} referenced files; generated integration page and source manifest.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=ROOT.parent/'LifeWorld_Design_Language_v1/collaboration/onboarding-preview');sync(parser.parse_args().source)
