#!/usr/bin/env python3
"""Create natural transport groups; no binary splitting or recompression of originals."""
from pathlib import Path
import hashlib,json,zipfile,tempfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'packages'; OUT.mkdir(exist_ok=True)
ids=[x['id'] for x in json.loads((ROOT/'assets/manifest.json').read_text())['assets'] if x['asset_type']=='fictional_role_portrait']
groups={
 '01-original-portraits-us-iran': [ROOT/f'originals/{i}.png' for i in ids[:2]],
 '02-original-portraits-mediator-observer-shipping': [ROOT/f'originals/{i}.png' for i in ids[2:]],
 '03-portrait-1024-masters': [ROOT/f'masters/{i}@1024.png' for i in ids],
 '04-cover-original-master-export': [ROOT/'originals/cover-international-dialogue.png',ROOT/'masters/cover-international-dialogue@1600x900.png',ROOT/'exports/cover-international-dialogue@800x450.png'],
 '05-portrait-exports-previews-manifest-provenance': sorted([p for d in ['exports','previews','assets','provenance'] for p in (ROOT/d).rglob('*') if p.is_file() and p.name!='cover-international-dialogue@800x450.png'])
}
assigned=[p for ps in groups.values() for p in ps]
all_files={p for p in ROOT.rglob('*') if p.is_file() and OUT not in p.parents and p.name!='README.md'}
assert len(assigned)==len(set(assigned)) and set(assigned)==all_files
index=[]
for name,files in groups.items():
 path=OUT/f'international-dialogue-v1-{name}.zip'
 entries=[ROOT/'README.md']+files
 with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in entries: z.write(p,ROOT.name+'/'+str(p.relative_to(ROOT)))
 assert path.stat().st_size<=8_000_000
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
 index.append(dict(file=path.name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),contents=[str(p.relative_to(ROOT)) for p in entries]))
with tempfile.TemporaryDirectory(prefix='dialogue-package-verify-') as t:
 for part in index:
  with zipfile.ZipFile(OUT/part['file']) as z: z.extractall(t)
 unpacked=Path(t)/ROOT.name
 for p in all_files|{ROOT/'README.md'}:
  q=unpacked/p.relative_to(ROOT)
  assert q.read_bytes()==p.read_bytes()
(OUT/'INDEX.json').write_text(json.dumps(dict(package_id=ROOT.name,version='v1',size_limit_bytes=8_000_000,all_zips_crc_verified=True,reconstructed_tree_byte_verified=True,parts=index),ensure_ascii=False,indent=2)+'\n')
(OUT/'README.txt').write_text('Life World international-dialogue art v1\n\nDownload all five ZIP files listed in INDEX.json. These are independent natural groups, not binary fragments. Extract all into the same destination. Each ZIP contains the same top-level lifeworld-pack-art-international-dialogue folder and README.md. Allow the identical README.md to merge.\n\nUse assets/manifest.json after reconstruction. All relative paths then resolve. Each archive is <= 8,000,000 bytes, CRC checked, SHA-256 recorded in INDEX.json, and the reconstructed tree is byte-verified.\n\nTransport only: do not commit ZIP duplicates into the repository. Demo only; formal release not approved.\n')
print(json.dumps([dict(file=p['file'],bytes=p['bytes'],sha256=p['sha256']) for p in index],indent=2))
