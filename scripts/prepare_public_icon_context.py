"""產生精確靜態白名單的Cloud Build context，不上傳產品程式、資料或憑證。"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def build(destination):
    """只複製索引、manifest與已列管圖示；輸出雜湊可對照線上內容。"""
    target=Path(destination).resolve()
    target.mkdir(parents=True,exist_ok=False)
    source=ROOT/'app/static'
    assets=json.loads((source/'art/mobile-web-v1/asset-manifest.json').read_text())
    files=['index.html','mobile-manifest-v1.webmanifest']+['art/mobile-web-v1/'+item['file'] for item in assets['variants']]+['art/mobile-web-v1/favicon.ico']
    receipt=[]
    for name in files:
        path=source/name;dest=target/'overlay'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,dest)
        receipt.append({'path':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    shutil.copyfile(ROOT/'deploy/Dockerfile.public-icons',target/'Dockerfile')
    (target/'.gcloudignore').write_text('.git\n**/.DS_Store\n')
    # 指紋留在context外，runtime layer只有上述真正必要的靜態檔。
    (target.parent/(target.name+'-manifest.json')).write_text(json.dumps({'files':receipt},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'context':str(target),'static_files':len(files),'backend_files':0}))


if __name__=='__main__':build(sys.argv[1])
