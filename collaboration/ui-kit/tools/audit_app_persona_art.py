"""唯讀核對既有 App／人物資產，另存手機封面裁切審查圖。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
QA = ROOT / "docs/qa/v1_1"
QA.mkdir(parents=True, exist_ok=True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(path: Path, size: tuple[int, int], expected: str | None = None) -> dict:
    with Image.open(path) as image:
        assert image.size == size, (path, image.size, size)
        mode = image.mode
    digest = sha(path)
    if expected:
        assert digest == expected, path
    return {"path": path.relative_to(ROOT).as_posix(), "width": size[0], "height": size[1], "mode": mode, "sha256": digest}


kit = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
icon = next(item for item in kit["assets"] if item["id"] == "lw-app-icon-v1")
share = next(item for item in kit["assets"] if item["id"] == "lw-share-illustration-v1")
app_files = [check(ASSETS / icon["originalPath"], (1254, 1254), icon.get("originalSha256"))]
for asset in (icon, share):
    for variant in asset["variants"]:
        app_files.append(check(ASSETS / variant["path"], (variant["width"], variant["height"]), variant["sha256"]))
assert {(item["width"], item["height"]) for item in app_files if "app-icon" in item["path"]} >= {(1024, 1024), (512, 512), (192, 192), (180, 180), (48, 48), (32, 32), (16, 16)}
app_files += [check(ROOT / "public/favicon.png", (48, 48)), check(ROOT / "public/share.png", (1200, 630))]

portraits = json.loads((ASSETS / "persona-art-map.v1.json").read_text(encoding="utf-8"))
assert len(portraits) == 15 and len({row["id"] for row in portraits}) == 15
portrait_files = []
for row in portraits:
    pack = ASSETS / "persona-art" / Path(row["path"]).parts[1]
    display = ASSETS / row["path"]
    masters = list(pack.rglob(f"{row['id']}*1024.png"))
    circles = list(pack.rglob(f"{row['id']}*circle*.png"))
    assert len(masters) == len(circles) == 1, (row["id"], masters, circles)
    portrait_files.append({"id": row["id"], "scope": row["scope"], "original": check(masters[0], (1024, 1024)), "display": check(display, (256, 256), row["sha256"]), "circlePreview": check(circles[0], (256, 256))})

covers = []
for pack in sorted((ASSETS / "persona-art").iterdir()):
    if not pack.is_dir():
        continue
    masters = list(pack.rglob("cover-*1600x900.png"))
    displays = list(pack.rglob("cover-*800x450.png"))
    assert len(masters) == len(displays) == 1, (pack, masters, displays)
    master = check(masters[0], (1600, 900))
    display = check(displays[0], (800, 450))
    with Image.open(masters[0]) as image:
        # 僅作窄版裁切 QA：中央 4:5，不能承諾所有五位群像皆保留。
        crop = image.crop((440, 0, 1160, 900)).resize((400, 500), Image.Resampling.LANCZOS)
        target = QA / f"persona-cover-mobile-{pack.name.removeprefix('lifeworld-pack-art-')}.png"
        crop.save(target, "PNG", optimize=True)
    covers.append({"pack": pack.name, "master": master, "display": display, "mobileCropPreview": check(target, (400, 500)), "cropOn1600": [440, 0, 1160, 900], "allFiveSubjectsPreserved": False, "status": "crop_qa_only_not_runtime"})

report = {"status": "file_and_crop_qa_not_boyi_approval", "app": app_files, "portraits": portrait_files, "covers": covers, "squareThumbnail": "reuse verified 1024x1024 app icon candidate", "limits": ["手機 4:5 中央裁切無法同時保留原 16:9 群像五人，正式手機封面需設計審查", "角色臉部位置與圓形裁切僅有檔案核對，尚需 Boyi 視覺驗收"]}
(QA / "APP_PERSONA_AUDIT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Verified app outputs, {len(portrait_files)} 1024/256/circle portrait triplets and {len(covers)} 1600/800 cover pairs; wrote crop QA previews.")
