"""精確產出介紹發布context：一份路由模組、29個靜態檔，不上傳整個工作樹。"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def build(destination):
    """只帶入列管檔案；以來源清單驗證產物，context外保留逐檔雜湊。"""
    target=Path(destination).resolve();target.mkdir(parents=True,exist_ok=False)
    intro=ROOT/'app/static/intro';manifest=json.loads((intro/'asset-manifest.json').read_text())
    files=['main.py','static/index.html','static/app.js','static/intro-entry.css','static/intro-entry.js','static/intro-preference.js','static/intro/asset-manifest.json']
    for item in manifest['copied']+manifest['generated']:
        file=(intro/item['path']).resolve()
        if not file.is_relative_to(intro) or hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('介紹產物與清單不符')
        files.append('static/intro/'+item['path'])
    if len(files)!=30 or len(set(files))!=30:raise ValueError('發布白名單不符預期')
    records=[]
    for name in files:
        source=ROOT/'app'/name;dest=target/'overlay'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        records.append({'path':'app/'+name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
    shutil.copyfile(ROOT/'deploy/Dockerfile.public-intro',target/'Dockerfile')
    (target/'.gcloudignore').write_text('.git\n**/.DS_Store\n')
    (target.parent/(target.name+'-manifest.json')).write_text(json.dumps({'files':records},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'context':str(target),'runtime_files':len(files),'backend_files':1,'static_files':29}))


if __name__=='__main__':build(sys.argv[1])
