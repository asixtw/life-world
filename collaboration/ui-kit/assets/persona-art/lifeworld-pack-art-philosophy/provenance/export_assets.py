#!/usr/bin/env python3
"""Reproducible technical delivery exports only; no generative or creative retouching."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib, json, datetime

ROOT = Path(__file__).resolve().parents[1]
LANCZOS = Image.Resampling.LANCZOS
PEOPLE = [
    ('socrates', '蘇格拉底', 'Socrates', '蘇格拉底的生成藝術詮釋：禿頂、灰白捲鬚，穿米白與鼠尾草綠古希臘披衣，神情專注溫和。'),
    ('confucius', '孔子', 'Confucius', '孔子的生成藝術詮釋：戴素色學者帽、蓄長鬚，穿米白、淡金與鼠尾草綠長袍，神情沉靜。'),
    ('zhuangzi', '莊子', 'Zhuangzi', '莊子的生成藝術詮釋：髮束成鬆髻、蓄疏鬚，穿素雅淺綠長袍，背景是淡墨般的遠山。'),
    ('nietzsche', '尼采', 'Nietzsche', '尼采的生成藝術詮釋：向後梳的深髮、濃厚大鬍髭，穿深鼠尾草綠十九世紀外套與米白襯衫。'),
    ('plato', '柏拉圖', 'Plato', '柏拉圖的生成藝術詮釋：灰白捲髮與濃密長鬚，穿帶淡金邊的鼠尾草綠古希臘披衣。'),
]
def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def info(path):
    im=Image.open(path)
    return dict(path=path.relative_to(ROOT).as_posix(), width=im.width, height=im.height,
                format='PNG', mode=im.mode, bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())
assets=[]; transforms=[]
for slug, name, english, alt in PEOPLE:
    asset_id='portrait-philosophy-'+slug
    original=ROOT/'assets/originals'/f'{asset_id}-generated-v1.png'
    im=Image.open(original).convert('RGB')
    master=ROOT/'assets/masters'/f'{asset_id}-1024.png'
    display=ROOT/'assets/display'/f'{asset_id}-256.png'
    preview=ROOT/'assets/previews'/f'{asset_id}-circle-256.png'
    m=im.resize((1024,1024), LANCZOS); m.save(master, optimize=True)
    small=m.resize((256,256), LANCZOS); small.save(display, optimize=True)
    mask=Image.new('L',(1024,1024),0)
    ImageDraw.Draw(mask).ellipse((0,0,1023,1023),fill=255)
    circle=small.convert('RGBA'); circle.putalpha(mask.resize((256,256),LANCZOS)); circle.save(preview,optimize=True)
    transforms.append(dict(id=asset_id,source=info(original),operation='square resize; no source crop; then display downsample and antialiased circular alpha mask',resize_filter='Pillow LANCZOS',master_size=[1024,1024],display_size=[256,256],circle_center=[128,128],circle_radius=128))
    assets.append(dict(id=asset_id,persona_id='philosophy-'+slug,pack_id='philosophy',display_name=name,type='historical_interpretation_portrait',usage='人物選角、回合發言、人物來源及回顧的 demo 頭像',usage_scope='demo',channels=['test','POC','closed_beta'],formal_release_approved=False,formal_release_status='not_approved',version='1.0.0',generation_revision='v1',theme='warm cream / mint / sage / muted gold; theme-neutral raster',state='static',alt=alt+' 此為藝術詮釋，非經核實的歷史肖像。',tool='image_gen.imagegen (built-in)',model_version='not exposed by tool',source_type='AI-generated artistic interpretation',source='provenance/prompts-v1.json',use_basis='User-authorized fullkit demo generation and approved philosophy cast; no reference portrait inputs. Rights and formal-production review pending; no unrestricted-commercial-use claim.',status='generated_exported_self_reviewed_pending_Boyi_Jerry_acceptance',files={'generated_original':info(original),'master':info(master),'display':info(display),'circle_preview':info(preview)},integration={'display_path':display.relative_to(ROOT).as_posix(),'master_path':master.relative_to(ROOT).as_posix(),'css_object_fit':'cover','css_object_position':'50% 50%','circle_css':'border-radius: 50%','identity_mapping_status':'stable art ID; persona_id integration alias requires schema reconciliation by parent/Jerry'}))

asset_id='cover-philosophy'
original=ROOT/'assets/originals/cover-philosophy-generated-v2.png'
old=ROOT/'assets/originals/cover-philosophy-generated-v1.png'
im=Image.open(original).convert('RGB')
# Native 1672x941 output is almost 16:9. Center crop 0.25 px from top/bottom, not distortion.
target_ratio=16/9
if im.width/im.height < target_ratio:
    h=im.width/target_ratio; box=(0,(im.height-h)/2,im.width,(im.height+h)/2)
else:
    w=im.height*target_ratio; box=((im.width-w)/2,0,(im.width+w)/2,im.height)
master=ROOT/'assets/masters/cover-philosophy-1600x900.png'
display=ROOT/'assets/display/cover-philosophy-800x450.png'
m=im.resize((1600,900),LANCZOS,box=box);m.save(master,optimize=True)
m.resize((800,450),LANCZOS).save(display,optimize=True)
transforms.append(dict(id=asset_id,source=info(original),operation='center crop to exact 16:9 then resize; no creative retouching',source_crop_box=list(box),resize_filter='Pillow LANCZOS',master_size=[1600,900],display_size=[800,450]))
assets.append(dict(id=asset_id,pack_id='philosophy',type='imaginary_cross_era_group_cover',display_name='哲學辯論｜想像的跨時代聚會',usage='哲學辯論 demo 組別封面／情境選擇',usage_scope='demo',channels=['test','POC','closed_beta'],formal_release_approved=False,formal_release_status='not_approved',version='1.0.0',generation_revision='v2',theme='warm cream / mint / sage / muted gold; theme-neutral raster',state='static',alt='想像的跨時代哲學聚會：由左至右，蘇格拉底、孔子、莊子、尼采與柏拉圖在庭院圓桌旁交流。此場景為創作，並非真實發生的歷史會面。',tool='image_gen.imagegen (built-in)',model_version='not exposed by tool',source_type='AI-generated explicitly imaginary historical scene',source='provenance/prompts-v1.json + provenance/prompt-cover-v2.txt',use_basis='User-authorized fullkit philosophy demo cast; v2 uses only this pack’s generated v1 cover as edit target. Rights and formal-production review pending; no unrestricted-commercial-use claim.',status='generated_refined_exported_self_reviewed_pending_Boyi_Jerry_acceptance',files={'generated_original':info(original),'master':info(master),'display':info(display),'superseded_original':info(old)},integration={'display_path':display.relative_to(ROOT).as_posix(),'master_path':master.relative_to(ROOT).as_posix(),'css_object_fit':'cover','css_object_position':'50% 50%','recommended_aspect_ratio':'16 / 9','disclosure':'跨時代聚會為創作；頭像為藝術詮釋，不是經核實的真實肖像。'}))

# Mechanical QA contact sheet, labels are outside artworks and never in delivery artwork files.
sheet=Image.new('RGB',(1440,940),'#fffefb'); d=ImageDraw.Draw(sheet)
try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
except OSError: font=ImageFont.load_default()
for index,(slug,name,english,alt) in enumerate(PEOPLE):
    x=24+index*284; asset_id='portrait-philosophy-'+slug
    square=Image.open(ROOT/'assets/display'/f'{asset_id}-256.png')
    circle=Image.open(ROOT/'assets/previews'/f'{asset_id}-circle-256.png')
    d.text((x,12),english,fill='#334431',font=font); sheet.paste(square,(x,42))
    sheet.paste(circle,(x,330),circle)
    d.rounded_rectangle((x-4,620,x+260,884),radius=16,fill='#263329')
    sheet.paste(circle,(x,624),circle)
d.text((24,906),'QA only: square / circular on cream / circular on dark. All art is demo; historical likenesses unverified.',fill='#334431',font=font)
qa=ROOT/'assets/previews/philosophy-contact-sheet.png';sheet.save(qa,optimize=True)
manifest=dict(schema_version='lifeworld.art-pack/1.0',pack_id='philosophy',package_version='1.0.0',usage_scope='demo',formal_release_approved=False,formal_release_status='not_approved',root_integration_target='collaboration/ui-kit/',created_utc='2026-10-28',source_ref='asixtw/life-world@1c9d502f32688bcc3c73e4b99a2cc3724c179047',assets=assets,qa_preview=info(qa),limitations=['Generated portraits are artistic interpretations, not verified historical likenesses.','The five-person gathering is fictional and cross-era, not a documented historical event.','Generation tool model/version was not exposed; asset and prompt revisions are recorded separately.','Native generation outputs are flattened raster images, no editable layers.','Formal release and unrestricted commercial-use approval are not established.','No frontend integration, browser QA, mobile/Safari QA, public upload or desktop repository change performed by this art subtask.'])
dump(ROOT/'assets/manifest.json',manifest)
dump(ROOT/'provenance/export-records.json',transforms)
print(json.dumps({'asset_count':len(assets),'files':sum(len(a['files']) for a in assets),'manifest':'assets/manifest.json','qa_preview':str(qa)},ensure_ascii=False))
