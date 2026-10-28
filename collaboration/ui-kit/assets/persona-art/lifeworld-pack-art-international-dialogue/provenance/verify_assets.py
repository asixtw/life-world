#!/usr/bin/env python3
from pathlib import Path
from PIL import Image
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'assets/manifest.json').read_text())
sources=json.loads((ROOT/'provenance/generation-sources.json').read_text())
records=[]
assert len(manifest['assets'])==6
assert len({a['id'] for a in manifest['assets']})==6
for asset in manifest['assets']:
 assert asset['usage_scope']=='demo' and asset['formal_release_approved'] is False
 assert asset['alt'] and asset['generation']['tool']=='OpenAI built-in image_gen.imagegen'
 expected=[(1672,941),(1600,900),(800,450)] if asset['asset_type']=='scenario_cover' else [(1254,1254),(1024,1024),(256,256),(256,256)]
 assert [(x['width'],x['height']) for x in asset['variants']]==expected
for variant in [v for a in manifest['assets'] for v in a['variants']]+manifest['technical_previews']:
 p=ROOT/variant['path']
 assert p.is_file()
 assert p.stat().st_size==variant['bytes']
 assert hashlib.sha256(p.read_bytes()).hexdigest()==variant['sha256']
 with Image.open(p) as im:
  im.verify()
 with Image.open(p) as im:
  assert im.size==(variant['width'],variant['height'])
  assert im.mode==variant['mode']
  if variant['role']=='circle_crop_preview':
   assert im.mode=='RGBA' and im.getpixel((0,0))[3]==0 and im.getpixel((128,128))[3]==255
 records.append(dict(path=variant['path'],status='pass'))
original_checks=[]
for s in sources:
 original=ROOT/f"originals/{s['id']}.png"
 source=Path(s['source_path'])
 if source.exists():
  assert original.read_bytes()==source.read_bytes()
  original_checks.append(dict(id=s['id'],status='pass_byte_identical_to_tool_output'))
 else:
  original_checks.append(dict(id=s['id'],status='source_not_in_this_environment_original_hash_verified'))
report=dict(status='pass',asset_count=6,verified_image_files=len(records),usage_scope='demo',formal_release_approved=False,file_checks=records,original_preservation_checks=original_checks)
(ROOT/'provenance/verification-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['file_checks','original_preservation_checks']},ensure_ascii=False))
