#!/usr/bin/env python3
"""Natural independent ZIP parts, each below the strict 8,000,000-byte cap."""
from pathlib import Path
import json,zipfile,hashlib
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'packages';DEST.mkdir(exist_ok=True)
manifest=json.loads((ROOT/'assets/manifest.json').read_text())
parts=[];assigned=set()
for a in manifest['assets']:
    paths=[f['path'] for role,f in a['files'].items() if role!='superseded_original']
    assigned.update(paths)
    parts.append((a['id'],paths))
all_paths={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and 'packages' not in p.relative_to(ROOT).parts}
parts.append(('evidence-and-superseded-cover',sorted(all_paths-assigned)))
index={'package_id':'lifeworld-pack-art-philosophy','version':'1.0.0','usage_scope':'demo','formal_release_approved':False,'max_part_bytes':8_000_000,'extract_instruction':'Extract all seven independent ZIP files into the same destination; each contains the lifeworld-pack-art-philosophy root folder. Parts are natural groups, not binary splits.','parts':[]}
coverage=set()
for number,(name,paths) in enumerate(parts,1):
    file=DEST/f'philosophy-{number:02d}-{name}.zip'
    with zipfile.ZipFile(file,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr('PART_README.txt',f'LifeWorld philosophy demo v1.0.0 — part {number}/{len(parts)}: {name}\nFormal release not approved. Extract all parts together. Full manifest, provenance and README are in the evidence part. Historical likenesses are artistic interpretations; cross-era cover is fictional.\n')
        for rel in sorted(paths):
            z.write(ROOT/rel,'lifeworld-pack-art-philosophy/'+rel)
            coverage.add(rel)
    with zipfile.ZipFile(file) as z: assert z.testzip() is None
    assert file.stat().st_size<=8_000_000,(file,file.stat().st_size)
    index['parts'].append({'name':file.name,'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'file_count':len(paths),'files':sorted(paths),'crc_verified':True})
assert coverage==all_paths
index['coverage_verified']=True
index['source_file_count']=len(all_paths)
(DEST/'package-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
(DEST/'SHA256SUMS.txt').write_text(''.join(p['sha256']+'  '+p['name']+'\n' for p in index['parts']))
print(json.dumps({'status':'passed','parts':[{'name':p['name'],'bytes':p['bytes']} for p in index['parts']],'coverage_files':len(all_paths)},ensure_ascii=False,indent=2))
