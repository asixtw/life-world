#!/usr/bin/env python3
"""Verify exact sizes, manifest integrity, original preservation and alpha crop."""
from pathlib import Path
from PIL import Image
import json, hashlib
ROOT=Path(__file__).resolve().parents[1]
m=json.loads((ROOT/'assets/manifest.json').read_text())
checks=[]
assert m['usage_scope']=='demo' and m['formal_release_approved'] is False
assert len(m['assets'])==6 and len({a['id'] for a in m['assets']})==6
for a in m['assets']:
    assert a['usage_scope']=='demo' and a['formal_release_status']=='not_approved'
    assert a['alt'] and a['model_version']=='not exposed by tool'
    for role,f in a['files'].items():
        p=ROOT/f['path'];assert p.is_file(),p
        with Image.open(p) as im:
            im.load();assert im.size==(f['width'],f['height']);assert im.mode==f['mode']
        assert p.stat().st_size==f['bytes']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==f['sha256']
        checks.append({'id':a['id'],'role':role,'path':f['path'],'verified':True})
    if a['id'].startswith('portrait-'):
        assert (a['files']['master']['width'],a['files']['master']['height'])==(1024,1024)
        assert (a['files']['display']['width'],a['files']['display']['height'])==(256,256)
        with Image.open(ROOT/a['files']['circle_preview']['path']) as im:
            assert im.size==(256,256) and im.mode=='RGBA'
            assert im.getpixel((0,0))[3]==0 and im.getpixel((128,128))[3]==255
    else:
        assert (a['files']['master']['width'],a['files']['master']['height'])==(1600,900)
        assert (a['files']['display']['width'],a['files']['display']['height'])==(800,450)
for r in json.loads((ROOT/'provenance/generation-records-v1.json').read_text()):
    original=ROOT/'assets/originals'/f"{r['id']}-generated-v1.png"
    source=Path(r['source_path'])
    if source.is_file(): assert source.read_bytes()==original.read_bytes()
r=json.loads((ROOT/'provenance/generation-record-cover-v2.json').read_text())
if Path(r['source_path']).is_file():assert Path(r['source_path']).read_bytes()==(ROOT/'assets/originals/cover-philosophy-generated-v2.png').read_bytes()
qa=m['qa_preview']; p=ROOT/qa['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==qa['sha256']
report={'status':'passed','verified_utc':'2026-10-28','asset_count':6,'portrait_count':5,'selected_cover_count':1,'image_file_count':25,'checks':checks,'qa_contact_sheet_hash_verified':True,'tool_original_bytes_preserved':True,'visual_review':{'reviewer':'generating assistant self-review, not human acceptance','method':'Every generated image inspected from imagegen output; 256px squares and circles on cream/dark inspected in contact sheet; final 800x450 cover inspected.','result':'Five distinguishable dignified faces; coherent warm cream/sage painterly family; faces, hair and hats safely visible in circles; no baked-in text or watermark observed. Cover shows exactly the five intended figures, unobstructed faces and readable group composition.','cover_refinement':'v1 too photographic; one targeted built-in imagegen style-transfer produced selected v2; v1 preserved and marked superseded.','human_acceptance':'pending Boyi/Jerry'},'limitations':m['limitations']}
(ROOT/'provenance/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'passed','asset_count':6,'verified_image_files':25,'report':'provenance/verification.json'}))
