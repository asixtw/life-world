"""逐檔核對顯示版、透明度與原稿；不改任何像素。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parents[1] / "assets"
manifest = json.loads((ASSETS / "derived-v1_1/manifest.json").read_text(encoding="utf-8"))
assert len(manifest["files"]) == 40
for item in manifest["files"]:
    target = ASSETS / item["path"]
    source = ASSETS / item["sourcePath"]
    assert hashlib.sha256(target.read_bytes()).hexdigest() == item["sha256"], target
    assert hashlib.sha256(source.read_bytes()).hexdigest() == item["sourceSha256"], source
    with Image.open(target) as image:
        assert (image.width, image.height, image.mode) == (item["width"], item["height"], item["mode"]), target
        if image.mode == "RGBA":
            alpha = image.getchannel("A")
            assert alpha.getextrema()[0] == 0 and alpha.getextrema()[1] > 0, target
            threshold = item["visibleAlphaThreshold"]
            box = alpha.point(lambda value: 255 if value > threshold else 0).getbbox()
            assert list(box) == item["visibleBbox"], target

for size in (512, 256, 128):
    poses = [item for item in manifest["files"] if "/poses/" in item["path"] and item["path"].endswith(f"@{size}.png")]
    assert len(poses) == 6
    assert len({tuple(item["anchorPx"]) for item in poses}) == 1
    assert max(item["visibleBbox"][3] for item in poses) - min(item["visibleBbox"][3] for item in poses) <= 2

print("Verified 40 derivative PNGs, unchanged source hashes, real alpha and six-pose foot anchors; 1920 remains marked as derived upscale.")
