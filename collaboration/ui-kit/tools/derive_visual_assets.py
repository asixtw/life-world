"""從已交付原稿重現 v1.1 顯示圖，不覆寫原稿。"""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

from PIL import Image
import PIL


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
OUT = ASSETS / "derived-v1_1"
POSE_ROOT = ASSETS / "lumi-poses-candidate-20261029"
SOURCE = json.loads((POSE_ROOT / "manifest.json").read_text(encoding="utf-8"))
POSE_IDS = {"idle", "quiet", "welcome", "listening", "confirmed", "celebrate"}
SHELL_IDS = {"shell-left", "shell-right"}
CANVAS = 1254
FOOT = (627, 1030)
TARGET_POSE_HEIGHT = 790  # alpha > 127 的剪影高，沿用 idle 原稿的視覺尺度。
records: list[dict] = []


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(image: Image.Image, threshold: int) -> tuple[int, int, int, int]:
    mask = image.getchannel("A").point(lambda value: 255 if value > threshold else 0)
    box = mask.getbbox()
    if box is None:
        raise ValueError("透明原稿沒有可見像素")
    return box


def save(image: Image.Image, relative: str, *, source: Path, method: str, anchor: tuple[int, int] | None = None) -> None:
    path = OUT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=True)
    record = {
        "assetId": "v1.1-" + relative.removesuffix(".png").replace("/", "-"),
        "path": (path.relative_to(ASSETS)).as_posix(),
        "sourcePath": (source.relative_to(ASSETS)).as_posix(),
        "sourceSha256": digest(source),
        "sha256": digest(path),
        "width": image.width,
        "height": image.height,
        "mode": image.mode,
        "bytes": path.stat().st_size,
        "usageScope": "product_candidate",
        "version": "v1.1-derived-1",
        "event": relative.split("/")[1].split("@")[0],
        "alt": ("Lumi " + relative.split("/")[1].split("@")[0] + " 姿勢" if relative.startswith("poses/") else
                "獨立左蛋殼" if "shell-left" in relative else "獨立右蛋殼" if "shell-right" in relative else
                "日間房間背景" if "room-day" in relative else "Quiet 房間背景" if "room-quiet" in relative else ""),
        "method": method,
    }
    if image.mode == "RGBA":
        threshold = 127 if image.getchannel("A").getextrema()[1] > 127 else 3
        record["visibleAlphaThreshold"] = threshold
        record["visibleBbox"] = list(bounds(image, threshold))
        record["trueTransparentBackground"] = image.getchannel("A").getextrema()[0] == 0
    if anchor is not None:
        record["anchorPx"] = list(anchor)
    if relative.startswith("world/"):
        record["sceneLumiAnchorPercent"] = [50, 79 if "768x1024" in relative else 76]
        record["backgroundCropAllowed"] = True
    records.append(record)


def on_canvas(image: Image.Image, center: int, bottom: int) -> Image.Image:
    # alpha>3 定義非雜點內容；留 8px 防止 LANCZOS 取樣截掉實際邊緣。
    x0, y0, x1, y1 = bounds(image, 3)
    crop = image.crop((max(0, x0 - 8), max(0, y0 - 8), min(image.width, x1 + 8), min(image.height, y1 + 8)))
    strong = bounds(image, 127)
    scale = TARGET_POSE_HEIGHT / (strong[3] - strong[1])
    resized = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.Resampling.LANCZOS)
    strong_resized = bounds(resized, 127)
    x = round(center - (strong_resized[0] + strong_resized[2]) / 2)
    y = round(bottom - strong_resized[3])
    if x < 0 or y < 0 or x + resized.width > CANVAS or y + resized.height > CANVAS:
        raise ValueError(f"超出共同畫布：{x}, {y}, {resized.size}")
    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    canvas.paste(resized, (x, y))
    return canvas


for item in SOURCE["assets"]:
    original = POSE_ROOT / item["path"]
    if digest(original) != item["sha256"]:
        raise ValueError(f"原稿雜湊不符：{item['id']}")
    image = Image.open(original).convert("RGBA")
    if item["id"] in POSE_IDS:
        master = on_canvas(image, *FOOT)
        save(master, f"poses/{item['id']}@1254.png", source=original, method="alpha>3 crop+8px, LANCZOS proportional scale to alpha>127 height 790, transparent 1254 canvas, center 627/bottom 1030", anchor=FOOT)
        for size in (512, 256, 128):
            save(master.resize((size, size), Image.Resampling.LANCZOS), f"poses/{item['id']}@{size}.png", source=original, method=f"LANCZOS from normalized 1254 master; original native {image.width}x{image.height}", anchor=(round(FOOT[0] * size / CANVAS), round(FOOT[1] * size / CANVAS)))
    elif item["id"] in SHELL_IDS:
        # 兩片仍各自透明；保留原始比例，成對平移到同一 1254 畫布。
        shift_y = 75 if item["id"] == "shell-left" else 82
        master = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        master.paste(image.crop((70, shift_y, CANVAS, CANVAS)), (0, 0))
        for size in (512, 256, 128):
            save(master.resize((size, size), Image.Resampling.LANCZOS), f"shells/{item['id']}@{size}.png", source=original, method=f"paired translation -70x/-{shift_y}y on transparent canvas; LANCZOS proportional resize; shell seam not reconstructed", anchor=(round(FOOT[0] * size / CANVAS), round(1115 * size / CANVAS)))

for mode in ("day", "quiet"):
    wide = ASSETS / f"world-candidates-20261029/originals/room-{mode}-base.png"
    portrait = ASSETS / f"world-portrait-supplement-20261029/room-{mode}-portrait-native.png"
    for path, expected, target in ((wide, (1448, 1086), (1920, 1440)), (wide, (1448, 1086), (1280, 960)), (portrait, (1086, 1448), (768, 1024))):
        image = Image.open(path)
        if image.size != expected:
            raise ValueError(f"背景原稿尺寸不符：{path}")
        method = f"LANCZOS proportional {'upscale' if target[0] > image.width else 'downscale'} from native {image.width}x{image.height}; not native new artwork"
        save(image.resize(target, Image.Resampling.LANCZOS).convert("RGB"), f"world/room-{mode}@{target[0]}x{target[1]}.png", source=path, method=method)

for name, source in (
    ("nourishment", ASSETS / "shared-art/additions-20261029/originals/lw-effects-nourishment-v2.png"),
    ("contact-shadow", ASSETS / "world-candidates-20261029/layers/lumi-contact-shadow.png"),
):
    image = Image.open(source).convert("RGBA")
    for size in (512, 256):
        if name == "contact-shadow":
            # 寬陰影等比例縮至 75% 畫布寬，落在角色腳下；不擴張成橢圓。
            width = round(size * .75)
            height = round(width * image.height / image.width)
            small = image.resize((width, height), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            canvas.paste(small, ((size - width) // 2, round(size * .83 - height / 2)))
        else:
            canvas = image.resize((size, size), Image.Resampling.LANCZOS)
        save(canvas, f"effects/{name}@{size}.png", source=source, method=f"LANCZOS proportional RGBA on transparent canvas; source native {image.width}x{image.height}")

manifest = {
    "schemaVersion": "1.0",
    "sourceSpecCommit": "ae5a9dc57cc49886427d3cb8ac7cc94bdc00065d",
    "tool": f"Python {platform.python_version()}, Pillow {PIL.__version__}; run python tools/derive_visual_assets.py",
    "poseAnchorPxOn1254": list(FOOT),
    "nativeOriginalsUntouched": True,
    "world1920IsDerivedUpscale": True,
    "pairedShellClosureVerified": False,
    "files": records,
}
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Created {len(records)} derivative PNGs; original files were read only.")
