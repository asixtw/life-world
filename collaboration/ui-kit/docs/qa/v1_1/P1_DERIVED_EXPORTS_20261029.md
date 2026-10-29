# v1.1 P1 顯示圖衍生與裝配核對

程式起點 `0ed17904f98d6a0258428c40d23958242b495929`；規格文件固定 `ae5a9dc57cc49886427d3cb8ac7cc94bdc00065d`。本輪只處理 `collaboration/ui-kit/` 的候選圖像衍生與顯示，不接正式 App／DB／帳本，不推送。使用者已授權程式等比縮放、透明畫布對齊與必要裁切。原稿位元組原樣保留。

## 前後對照與實際檔案

| 內容 | 原生輸入 | 衍生輸出／UI |
|---|---|---|
| 六 Lumi 姿勢 | 各 1254×1254 RGBA，剪影高約 789–909 px，原始落地點 y=1029–1128 | `assets/derived-v1_1/poses/` 每姿勢 1254 正規化透明母版與 512／256／128 PNG；alpha>127 剪影高定為 790、落地錨點母版 `(627,1030)`，512 版可見底部 y=420–421。Gallery、世界與無殼回饋使用 512 版。 |
| 左右殼、陰影、養分 | 左右殼各 1254 RGBA；世界接地陰影 1774×887 RGBA；養分 1254 RGBA | `shells/` 左右各 512／256／128 共畫布透明 PNG；`effects/` 陰影與養分各 512／256 PNG。孵化由左右殼、無殼 Lumi 與獨立陰影組合；一般正向回饋使用無殼 confirmed 與獨立養分。 |
| 世界日間／Quiet | 橫向各 1448×1086 RGB；獨立直向各 1086×1448 RGB | `world/` 兩主題各 1920×1440、1280×960、768×1024 PNG。桌面載入 1280，手機載入獨立直向 768。1920 是 **1448 原生橫稿等比放大衍生**，不是原生高解析新原稿。 |

`tools/derive_visual_assets.py` 使用 Python 3.12、Pillow 12.3 的 LANCZOS 等比重採樣；裁切只移除幾乎透明的外圍與留 8px 取樣邊，無拉伸。`assets/derived-v1_1/manifest.json` 逐一記錄 40 張 PNG 的 ID、用途、原稿和輸出路徑／SHA256、尺寸、模式、bytes、方法、透明 bbox、錨點、版本及顯示用途。`tools/verify_visual_derivatives.py` 重新讀取全部 40 檔，驗證原稿 SHA 未變、實際 PNG 模式與真透明像素、bbox 及六姿勢錨點。最終衍生 PNG 共 11,533,914 bytes。

## 真實畫面與退路

- `tests/v11-lumi-qa.mjs`：390×844 與 1280×800 的日間、Quiet、減少動效六組；兩片殼獨立載入、普通回饋不含殼、圖不破／容器不溢出；另阻斷 confirmed 圖驗證文字替代。真截圖 `lumi-assembly-{mobile|desktop}-{day|quiet|reduced}.png` 與六姿勢局部圖。
- `tests/v11-world-qa.mjs`：同六組固定世界場景；手機真載 768×1024、桌面真載 1280×960，Lumi 完整在房間內，頁面沒有橫向溢出；另阻斷手機背景檔驗證文字操作退路。真截圖 `world-{mobile|desktop}-{day|quiet|reduced}-*.png` 與 `world-scene-*`。
- 已目視手機日間／減少動效孵化、桌面 Quiet 孵化、手機日間與桌面 Quiet 房間，角色、殼與養分均在畫面內；殼口形狀並非同一完整蛋的像素切片，兩殼無法靠縮放保證封閉蛋與裂紋逐格吻合。

## 未達與限制

- 六姿勢的**數值落地錨點**已統一；眼睛、翅膀、葉片的逐姿勢視覺比例與暗底亮邊仍需 Boyi 美術細審，不能以尺寸檢查代替驗收。
- 左右殼可獨立移動且底部對齊，但原稿不是從現有完整蛋／裂紋同源抽層；裂口連續、封閉蛋重組與全程逐格銜接仍需原畫或新同源素材。manifest 的 `pairedShellClosureVerified` 維持 `false`。
- 世界 1920 是上採樣，原生尺寸要求 `targetOriginalSizeMet` 仍為 `false`；日間與 Quiet 僅構圖相近，未達像素級完全對齊。手機瀏海／不同 Safari safe area 與正式宿主仍待 Jerry／實機核對。
- 上述為候選外觀與本地流程；Boyi／Jerry 人工驗收、正式服務整合及發布均未做。
