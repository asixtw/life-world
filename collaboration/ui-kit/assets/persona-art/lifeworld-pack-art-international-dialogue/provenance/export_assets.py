#!/usr/bin/env python3
"""Technical resize/circle-crop previews only; no painting, recoloring, or artwork synthesis."""
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont
import hashlib, json

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'provenance/prompts.json').read_text())
NAMES = {x['id']: x['label'] for x in DATA['prompts']}
NAMES['cover-international-dialogue'] = '國際協調：虛構協商場景封面'
ALTS = {
 'portrait-international-dialogue-us-representative': '虛構美方代表：短捲髮帶銀色髮絲的中年女性，穿海軍藍西裝外套與米白上衣；奶油與鼠尾草綠背景的柔和繪畫頭像。',
 'portrait-international-dialogue-iran-representative': '虛構伊方代表：深色微捲髮、短灰黑鬍鬚的中年男性，穿炭灰西裝外套與米白襯衫；柔和奶油與綠色背景。',
 'portrait-international-dialogue-neutral-mediator': '虛構中立調停者：銀色短直髮、戴細圓框眼鏡的年長女性，穿鼠尾草綠外套與米白上衣；柔和繪畫頭像。',
 'portrait-international-dialogue-international-observer': '虛構國際組織觀察員：黑髮低髮髻的成年女性，穿炭灰外套與薄荷綠上衣；奶油與淡綠背景的柔和繪畫頭像，無機構標誌。',
 'portrait-international-dialogue-shipping-representative': '虛構航運方代表：深棕膚色、短髮與短鬍鬚的成年男性，穿灰綠外套與米白襯衫；背景為柔和想像港景。',
 'cover-international-dialogue': '五位虛構代表圍坐淺木色圓桌，在奶油與鼠尾草綠的明亮房間中平和討論；桌上有空白紙張和水杯，窗外是庭園，沒有旗幟、文字或機構標誌。',
}
LANCZOS = Image.Resampling.LANCZOS
for folder in ['masters', 'exports', 'previews', 'assets']:
 (ROOT / folder).mkdir(exist_ok=True)

def save(im, path):
 im.save(ROOT / path, format='PNG', optimize=True)

def info(path, role, transform):
 p=ROOT/path
 with Image.open(p) as im:
  size=list(im.size); mode=im.mode
 return dict(path=path, role=role, width=size[0], height=size[1], format='PNG', mode=mode, bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest(), transform=transform)

assets=[]
for asset_id, label in NAMES.items():
 original_path=f'originals/{asset_id}.png'
 original=Image.open(ROOT/original_path)
 variants=[info(original_path, 'imagegen_original', 'none; generator bytes preserved')]
 is_cover=asset_id.startswith('cover-')
 target=(1600,900) if is_cover else (1024,1024)
 master=ImageOps.fit(original, target, method=LANCZOS, centering=(0.5,0.5))
 suffix='1600x900' if is_cover else '1024'
 master_path=f'masters/{asset_id}@{suffix}.png'
 save(master, master_path)
 transformation='center fit from 1672x941; source crop box [0,0.25,1672,940.75]; Lanczos resize to 1600x900' if is_cover else 'uniform Lanczos resize 1254x1254 to 1024x1024; no crop'
 variants.append(info(master_path, 'derived_master', transformation))
 small_size=(800,450) if is_cover else (256,256)
 suffix='800x450' if is_cover else '256'
 export_path=f'exports/{asset_id}@{suffix}.png'
 save(master.resize(small_size,LANCZOS), export_path)
 variants.append(info(export_path, 'display_export', f'Lanczos resize derived master to {small_size[0]}x{small_size[1]}'))
 if not is_cover:
  circle=master.resize((256,256),LANCZOS).convert('RGBA')
  mask=Image.new('L',(1024,1024)); ImageDraw.Draw(mask).ellipse((0,0,1023,1023),fill=255)
  circle.putalpha(mask.resize((256,256),LANCZOS))
  path=f'previews/{asset_id}@256-circle.png'
  save(circle,path)
  variants.append(info(path,'circle_crop_preview','centered 256px circle alpha mask; no retouching; transparent outside circle'))
 assets.append(dict(id=asset_id,pack_id='international-dialogue',display_name=label,asset_type='scenario_cover' if is_cover else 'fictional_role_portrait',version='v1',usage_scope='demo',applicable_channels=['test','POC','closed_beta'],formal_release_approved=False,status='generated_visual_qa_passed_pending_product_review',theme='warm_cream_mint_sage_light_gold',alt=ALTS[asset_id],usage_basis='User approved repository specified character list A and Life World fullkit artwork; completely fictional role visualization, not a real official portrait or institutional endorsement. Formal product use and legal clearance not asserted.',generation=dict(tool='OpenAI built-in image_gen.imagegen',tool_mode='built-in',model_version='not exposed by tool',date_utc='2026-10-28',prompt_path='provenance/prompt-cover.txt' if is_cover else 'provenance/prompts.json',prompt_key=None if is_cover else asset_id,input_image_refs=list(NAMES)[:-1] if is_cover else [],source_path=f'originals/{asset_id}.png',source_pixels=list(original.size)),variants=variants,integration='Render image as demo-only fiction with adjacent UI label 示範角色・虛構形象. Keep real UI text outside pixels. Preserve these IDs and explicit persona mapping. CSS circle clipping can use the square 256px export; preview is not the only master. Cover is an imaginary scene, not news or evidence of a real meeting.'))

# A technical clipping/thumbnail sheet, labels are outside the artwork.
font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font=ImageFont.truetype(font_path,18)
labels=['US-side role','Iran-side role','Neutral mediator','Intl. observer','Shipping role']
ids=list(NAMES)[:-1]
sheet=Image.new('RGB',(1440,1000),'#f7f3e8'); draw=ImageDraw.Draw(sheet)
draw.text((24,16),'INTERNATIONAL DIALOGUE - FICTIONAL DEMO ROLE ART / TECHNICAL PREVIEW',fill='#293b35',font=font)
for i,asset_id in enumerate(ids):
 x=20+i*284
 draw.text((x,52),labels[i],fill='#293b35',font=font)
 thumb=Image.open(ROOT/f'exports/{asset_id}@256.png').convert('RGB')
 sheet.paste(thumb,(x,86))
 circ=Image.open(ROOT/f'previews/{asset_id}@256-circle.png')
 sheet.paste(circ,(x,370),circ)
 draw.rectangle((x-4,654,x+260,930),fill='#1f2d29')
 sheet.paste(circ,(x,664),circ)
 draw.text((x,950),'Square / Day / Quiet',fill='#293b35',font=font)
save(sheet,'previews/international-dialogue-crop-qa.png')

manifest=dict(schema_version='1.0',package_id='lifeworld-pack-art-international-dialogue',pack_id='international-dialogue',version='v1',usage_scope='demo',formal_release_approved=False,expected_count=dict(portraits=5,covers=1),delivered_count=dict(portraits=5,covers=1),source_repository='asixtw/life-world',source_ref='1c9d502f32688bcc3c73e4b99a2cc3724c179047',path_base='package root',assets=assets,technical_previews=[info('previews/international-dialogue-crop-qa.png','technical_contact_sheet','square exports plus transparent circle previews composited on Day and Quiet backgrounds; labels are outside art')],limits=['Flattened generated PNGs, not layered illustration sources or editable vector.','No actual politicians or private-person reference images used; generated fictional faces are not claimed to represent current officials.','No official institutional endorsement, commercial-use clearance, real events, deployment, device tests, or formal product approval claimed.','Art QA covers images and technical crops; application integration remains parent/Jerry responsibility.'])
(ROOT/'assets/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(f'Created {len(assets)} assets; 6 preserved originals, 6 masters, 6 exports, 5 circle previews and 1 QA sheet.')
