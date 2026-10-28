#!/usr/bin/env python3
"""Only authorized technical resize/crop/mask exports; no art synthesis or retouching."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib, json, shutil

ROOT = Path(__file__).resolve().parents[1]
records = json.loads((ROOT/'provenance/generation-records.json').read_text())
prompts = json.loads((ROOT/'provenance/prompts.json').read_text())
alts = {
 'caocao': '曹操的歷史藝術詮釋：灰黑鬍鬚、沉著神情與深藍綠衣袍，暖米色背景。',
 'liubei': '劉備的歷史藝術詮釋：溫厚神情、黑鬚與米白綠色衣袍，暖米色背景。',
 'zhugeliang': '諸葛亮的歷史藝術詮釋：長鬚、素色學者衣冠與羽扇，暖米色背景。',
 'sunquan': '孫權的歷史藝術詮釋：紅棕鬍鬚、堅定神情與墨綠淡金衣袍，暖米色背景。',
 'zhouyu': '周瑜的歷史藝術詮釋：無鬚的清俊成年面容、赭色與鼠尾草綠衣袍，暖米色背景。',
 'cover': '虛構三國策略情境封面：五位古代人物在江畔亭中圍桌商議，桌上有地形圖，遠方是平靜江面與山巒。'
}
assets=[]
all_files=[]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def meta(path, variant, operation, source):
    p=ROOT/path
    with Image.open(p) as im:
        d={'variant':variant,'path':path,'type':'image/png','format':'PNG','width':im.width,'height':im.height,'mode':im.mode,'bytes':p.stat().st_size,'sha256':sha(p),'operation':operation,'source_path':source}
    all_files.append(d)
    return d

for r in records:
    aid,slug=r['id'],r['slug']
    source=Path(r['source_path'])
    original=f'assets/originals/{aid}.original.png'
    shutil.copyfile(source,ROOT/original)
    assert sha(source)==sha(ROOT/original)
    im=Image.open(source).convert('RGB')
    variants=[meta(original,'original_native','byte-identical copy of built-in imagegen result',r['source_path'])]
    if slug!='cover':
        master=f'assets/masters/{aid}.1024.png'
        image=im.resize((1024,1024),Image.Resampling.LANCZOS)
        image.save(ROOT/master,optimize=True)
        variants.append(meta(master,'master','LANCZOS resize from native square; no content crop',original))
        display=f'assets/display/{aid}.256.png'
        thumb=image.resize((256,256),Image.Resampling.LANCZOS)
        thumb.save(ROOT/display,optimize=True)
        variants.append(meta(display,'display','LANCZOS downscale of 1024 master',master))
        circle=f'assets/previews/{aid}.circle-256.png'
        mask=Image.new('L',(1024,1024),0)
        ImageDraw.Draw(mask).ellipse((0,0,1023,1023),fill=255)
        mask=mask.resize((256,256),Image.Resampling.LANCZOS)
        cropped=thumb.convert('RGBA'); cropped.putalpha(mask)
        cropped.save(ROOT/circle,optimize=True)
        variants.append(meta(circle,'circle_crop_preview','Centered circular alpha mask, 4x antialiased; no retouching',display))
        dims=[1024,1024]
    else:
        master=f'assets/masters/{aid}.1600x900.png'
        cropheight=im.width*9/16
        box=(0,(im.height-cropheight)/2,im.width,(im.height+cropheight)/2)
        image=im.resize((1600,900),Image.Resampling.LANCZOS,box=box)
        image.save(ROOT/master,optimize=True)
        variants.append(meta(master,'master',f'Centered 16:9 subpixel crop box {box}, LANCZOS resize',original))
        display=f'assets/display/{aid}.800x450.png'
        image.resize((800,450),Image.Resampling.LANCZOS).save(ROOT/display,optimize=True)
        variants.append(meta(display,'display','LANCZOS downscale of 1600x900 master',master))
        dims=[1600,900]
    assets.append({'id':aid,'pack_id':'three-kingdoms','persona_key':None if slug=='cover' else slug,'display_name':r['name'],'asset_type':'pack_cover' if slug=='cover' else 'persona_portrait','path':master,'display_path':display,'dimensions':dims,'format':'PNG','bytes':(ROOT/master).stat().st_size,'sha256':sha(ROOT/master),'usage_scope':'demo','allowed_channels':['test','POC','closed_beta_demo'],'formal_status':'formal_not_approved','production_approved':False,'version':'1.0.0','theme':'warm_cream_mint_sage_light_gold','state':'static','alt':alts[slug],'status':'generated_exported_visual_qa_passed_pending_owner_review','source_type':'AI-generated historical artistic interpretation; not verified authentic likeness','tool':'OpenAI built-in image_gen.imagegen','tool_version':'not exposed by tool','model_version':'not exposed by tool','prompt_record':'provenance/prompts.json#'+aid,'generation_record':'provenance/generation-records.json#'+aid,'usage_basis':'Owner-authorized demo pack art, fifteen-person list A selected 2026-10-28; no assertion of unrestricted commercial clearance','integration_notes':'Keep this asset in the demo namespace. Render text and names as accessible UI outside the raster. Do not use as evidence of authentic appearance or an actual historical meeting.','variants':variants})

manifest={'schema_version':'1.0.0','pack_id':'three-kingdoms','version':'1.0.0','usage_scope':'demo','formal_status':'formal_not_approved','production_approved':False,'source_repository':'asixtw/life-world','source_ref':'1c9d502f32688bcc3c73e4b99a2cc3724c179047','created_date_utc':'2026-10-28','assets':assets}
(ROOT/'assets/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
(ROOT/'provenance/export-records.json').write_text(json.dumps(all_files,ensure_ascii=False,indent=2)+'\n')

# QA contact sheet is a review-only composition, never a runtime asset.
sheet=Image.new('RGB',(1400,1100),'#f8f4e9')
d=ImageDraw.Draw(sheet)
try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20)
except OSError: font=ImageFont.load_default()
for i,a in enumerate(assets[:5]):
    x=12+i*280
    d.text((x,10),a['persona_key'],fill='#284c42',font=font)
    sq=Image.open(ROOT/a['display_path']); sheet.paste(sq,(x,45))
    circle=Image.open(ROOT/a['variants'][3]['path'])
    sheet.paste(circle,(x,325),circle)
d.text((12,605),'Cover / 800 x 450 / demo only',fill='#284c42',font=font)
sheet.paste(Image.open(ROOT/assets[-1]['display_path']),(300,635))
sheet.save(ROOT/'qa/contact-sheet.png',optimize=True)

# Validate all paths, dimensions, modes, source preservation and circle masks.
checks=[]
for a in assets:
    for v in a['variants']:
        p=ROOT/v['path']
        with Image.open(p) as im:
            im.verify()
        with Image.open(p) as im:
            if v['variant']=='circle_crop_preview':
                assert im.size==(256,256) and im.mode=='RGBA'
                assert im.getpixel((0,0))[3]==0 and im.getpixel((128,128))[3]==255
            elif v['variant']=='master':
                assert list(im.size)==a['dimensions']
            elif v['variant']=='display':
                assert im.size==((800,450) if a['asset_type']=='pack_cover' else (256,256))
            assert sha(p)==v['sha256']
        checks.append({'path':v['path'],'dimensions_ok':True,'sha256_ok':True,'decode_ok':True})
result={'status':'technical_checks_passed','logical_assets':len(assets),'image_files':len(all_files),'originals_byte_identical':True,'required_dimensions_passed':True,'circle_alpha_passed':True,'manifest_paths_passed':True,'checks':checks,'visual_qa':'All six originals inspected from imagegen output. Export contact sheet inspection recorded separately.','not_tested':['App integration','physical devices','Safari','production rights clearance','authentic historical likeness']}
(ROOT/'qa/technical-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'assets':len(assets),'images':len(all_files),'total_image_bytes':sum(v['bytes'] for v in all_files)},indent=2))
