from pathlib import Path  # 只在本交付包內讀寫技術輸出。
from PIL import Image, ImageDraw, ImageFont  # 僅縮放、定位、裁切與驗收預覽，不重繪插畫。
import json, hashlib  # 記錄尺寸、轉換資訊與完整性雜湊。
ROOT = Path(__file__).resolve().parents[1]  # 以腳本所在交付包為根目錄。
OUT = ROOT / 'exports'  # 顯示用資產與原始生成稿分開。
PRE = ROOT / 'previews'  # 技術裁切與明暗驗收圖不當作原稿。
OUT.mkdir(exist_ok=True)  # 確保輸出目錄存在。
PRE.mkdir(exist_ok=True)  # 確保預覽目錄存在。
records = []  # 收集實際生成的輸出資訊。
def save(im, path, source, transform):  # 寫檔並記錄可重現的技術處理。
    im.save(path, optimize=True)  # 保留 PNG 透明色版並只做無損壓縮。
    records.append({'path': str(path.relative_to(ROOT)), 'source': source, 'width': im.width, 'height': im.height, 'mode': im.mode, 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'transform': transform})  # 實際讀取已寫檔案計算交付資訊。
def align(im, scale, offset):  # 將生成圖按共同畫布與錨點等比例縮放定位。
    result = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))  # 透明畫布僅提供排版空間，不增添繪畫。
    resized = im.resize((round(im.width * scale), round(im.height * scale)), Image.Resampling.LANCZOS)  # 使用高品質等比例取樣。
    result.alpha_composite(resized, tuple(round(v) for v in offset))  # 把未重繪的原稿放上共同畫布。
    return result  # 回傳統一尺寸的透明圖。
for source in sorted((ROOT / 'originals').glob('*.png')):  # 逐一處理已實際生成的原稿。
    name = source.stem  # 穩定 ID 與檔名保持一致。
    im = Image.open(source).convert('RGBA')  # 保留原有 alpha 資訊。
    if name.startswith('lw-egg-'):  # 四個已完成蛋狀態使用完全相同的幾何轉換。
        transform = {'operation': 'uniform resize and transparent-canvas placement', 'scale': .66, 'offset': [98, 107], 'anchor': [512, 820], 'no_alpha_cleanup': True}  # 原有近透明雜訊亦不私自修繪。
        master = align(im, .66, (98, 107))  # 蛋底約在共同 y=820，狀態差異小於約兩像素。
        sizes = [1024, 512, 256]  # 提供原稿規格與實際顯示尺寸。
    elif name.startswith('lw-lumi-'):  # Lumi 兩姿勢共用同一身體錨點。
        transform = {'operation': 'uniform resize and transparent-canvas placement', 'scale': .82, 'offset': [-2, -25], 'anchor': [512, 820], 'no_alpha_cleanup': True}  # 未重繪、換色或刪除圖像細節。
        master = align(im, .82, (-2, -25))  # 將人物身體底與蛋底對齊。
        sizes = [1024, 512, 256]  # 提供透明顯示輸出。
    elif name == 'lw-app-icon-v1':  # App icon 使用整張方形原稿。
        transform = {'operation': 'full-frame resize', 'from': list(im.size), 'to': [1024, 1024]}  # 原始生成解析度不冒稱原生 1024。
        master = im.convert('RGB').resize((1024, 1024), Image.Resampling.LANCZOS)  # 輸出不透明可裁切的方形 master。
        sizes = [1024, 512, 192, 180, 48, 32, 16]  # 含明訂尺寸與額外 favicon 小尺寸。
    else:  # 分享圖按規格做中央比例裁切再縮放。
        ratio = 1200 / 630  # 使用指定分享圖比例。
        crop_width = min(im.width, round(im.height * ratio))  # 只裁掉極少量邊緣，不改繪內容。
        crop_height = min(im.height, round(im.width / ratio))  # 保持主角完全可見。
        box = ((im.width-crop_width)//2, (im.height-crop_height)//2, (im.width+crop_width)//2, (im.height+crop_height)//2)  # 記錄中央裁切範圍。
        master = im.convert('RGB').crop(box).resize((1200, 630), Image.Resampling.LANCZOS)  # 技術輸出而非新生成插畫。
        save(master, OUT / (name + '@1200x630.png'), source.name, {'operation': 'center crop and resize', 'crop': list(box)})  # 保留完整轉換記錄。
        save(master.resize((600, 315), Image.Resampling.LANCZOS), OUT / (name + '@600x315.png'), source.name, {'operation': 'resize 1200x630 export to 600x315'})  # 較小預覽輸出。
        continue  # 分享圖不套用方形規格。
    for size in sizes:  # 寫入每個明訂方形輸出。
        output = master if size == 1024 else master.resize((size, size), Image.Resampling.LANCZOS)  # 不重新生成或重繪。
        save(output, OUT / (name + '@' + str(size) + '.png'), source.name, transform if size == 1024 else {'operation': 'resize normalized 1024 master', 'to': [size, size]})  # 各輸出皆有追溯資訊。
icon = Image.open(OUT / 'lw-app-icon-v1@1024.png').convert('RGBA')  # 裁切預覽使用真正已交付 App icon。
for shape in ['circle', 'rounded']:  # 只製作需求明訂的兩種裁切預覽。
    mask = Image.new('L', icon.size, 0)  # 遮罩用於技術裁切，非新增美術內容。
    draw = ImageDraw.Draw(mask)  # 建立裁切邊界工具。
    draw.ellipse((0, 0, 1023, 1023), fill=255) if shape == 'circle' else draw.rounded_rectangle((0, 0, 1023, 1023), radius=224, fill=255)  # 套用標準圓形或圓角裁切。
    cut = icon.copy()  # 方形 master 不被覆蓋。
    cut.putalpha(mask)  # 只有裁切預覽變為透明外框。
    save(cut.resize((512,512), Image.Resampling.LANCZOS), PRE / ('lw-app-icon-' + shape + '-preview.png'), 'lw-app-icon-v1@1024.png', {'operation': 'requested crop preview', 'shape': shape})  # 裁切是展示圖，不替代完整 master。
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)  # 預覽標籤使用工具字型，資產本身無烤字。
items = ['lw-egg-rest-v1', 'lw-egg-softglow-v1', 'lw-egg-initialcrack-v1', 'lw-egg-deepcrack-v1', 'lw-lumi-companion-v1', 'lw-lumi-quiet-v1']  # 不以不存在資產或占位圖補數。
for theme, bg, fg in [('day', '#f7f8f2', '#334431'), ('quiet', '#26352b', '#f7f8f2')]:  # 在明暗兩種底色檢查透明邊緣。
    sheet = Image.new('RGB', (1200, 860), bg)  # 技術驗收聯絡表不是美術原稿。
    draw = ImageDraw.Draw(sheet)  # 標示實際狀態名稱方便審查。
    for i, name in enumerate(items):  # 每個輸出使用相同格子與顯示尺度。
        picture = Image.open(OUT / (name + '@512.png')).resize((380, 380), Image.Resampling.LANCZOS)  # 以常見 UI 視覺尺寸檢查。
        x, y = (i % 3) * 400 + 10, (i // 3) * 430 + 10  # 排列為兩排三欄。
        sheet.paste(picture, (x, y), picture)  # 合成僅作明暗底色驗收。
        draw.text((x+8, y+385), name, fill=fg, font=font)  # 文字不寫入產品資產。
    save(sheet, PRE / ('lw-transparent-states-' + theme + '.png'), 'normalized exports', {'operation': 'QA contact sheet on ' + theme + ' background'})  # 保存可檢查證據。
(ROOT / 'provenance' / 'export-records.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')  # 保存每個輸出大小與雜湊。
print(json.dumps({'outputs': len(records), 'export_bytes': sum(x['bytes'] for x in records)}, ensure_ascii=False))  # 回報真實寫檔結果。
