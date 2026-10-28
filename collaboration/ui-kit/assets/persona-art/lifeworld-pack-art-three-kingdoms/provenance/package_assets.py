#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'lifeworld-pack-art-three-kingdoms-packages'
OUT.mkdir(exist_ok=True)
manifest=json.loads((ROOT/'assets/manifest.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
common=['README.md','assets/manifest.json']
index=[]
for number,asset in enumerate(manifest['assets'],1):
    slug=asset['persona_key'] or 'cover'
    files=common+[v['path'] for v in asset['variants']]
    if number==1:
        files+=sorted(str(p.relative_to(ROOT)) for folder in ['provenance','qa'] for p in (ROOT/folder).rglob('*') if p.is_file())
    out=OUT/f'lifeworld-three-kingdoms-v1-{number:02d}-{slug}.zip'
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for rel in files: z.write(ROOT/rel,rel)
    with zipfile.ZipFile(out) as z: assert z.testzip() is None
    assert out.stat().st_size<8_000_000,(out,out.stat().st_size)
    index.append({'part':number,'name':out.name,'path':str(out),'bytes':out.stat().st_size,'sha256':sha(out),'asset_id':asset['id'],'contents':files,'includes_full_provenance_and_qa':number==1})
result={'pack_id':'three-kingdoms','version':'1.0.0','usage_scope':'demo','formal_status':'formal_not_approved','archive_limit_bytes':8_000_000,'parts':index,'extract_instructions':'Extract all six parts into the same directory. Repeated README.md and assets/manifest.json are byte-identical. Full provenance and QA are in part 01.','total_zip_bytes':sum(x['bytes'] for x in index)}
for p in [OUT/'PACKAGE_INDEX.json',ROOT/'PACKAGE_INDEX.json']: p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

# Test the exact delivered archive set from a clean directory.
with tempfile.TemporaryDirectory(prefix='lw-three-kingdoms-qa-') as temp:
    dest=Path(temp)
    for part in index:
        with zipfile.ZipFile(part['path']) as z: z.extractall(dest)
    extracted=json.loads((dest/'assets/manifest.json').read_text())
    for a in extracted['assets']:
        for variant in a['variants']:
            p=dest/variant['path']; assert p.is_file() and sha(p)==variant['sha256']
result['archive_extract_verified']=True
result['asset_sha256_verified_after_extraction']=23
for p in [OUT/'PACKAGE_INDEX.json',ROOT/'PACKAGE_INDEX.json']: p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'archives':[{'name':p['name'],'bytes':p['bytes'],'sha256':p['sha256']} for p in index],'archive_extract_verified':True,'asset_sha256_verified_after_extraction':23},indent=2))
