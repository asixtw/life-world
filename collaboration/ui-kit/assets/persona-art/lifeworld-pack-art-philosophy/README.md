# LifeWorld 哲學美術包 v1.0.0

已交付 **五位獨立頭像＋一組封面**：蘇格拉底、孔子、莊子、尼采、柏拉圖。所有資產為 `usage_scope=demo`，供測試／POC／封測；**正式版未核准**，仍待 Boyi／Jerry 驗收。

## 檔案

- `assets/originals/`：保留工具原始 PNG；五張頭像原生 1254×1254，封面原生 1672×941。封面 v1 為較寫實的初版，v2 為已選用的繪畫風格修訂，兩者皆保留，勿把 v1 用於展示。
- `assets/masters/`：五張精確 1024×1024 頭像與精確 1600×900 封面。
- `assets/display/`：五張 256×256 頭像與 800×450 封面。
- `assets/previews/`：五張 256×256 透明圓形裁切預覽，與淺／深底 QA 總覽。QA 總覽標籤不屬於圖像素材本身。
- `assets/manifest.json`：穩定 ID、路徑、用途、尺寸、格式、位元組、SHA-256、版本、狀態、alt、來源／工具、用途依據及整合說明。
- `provenance/`：完整提示詞、生成輸出位置、規格來源與 blob SHA、精確技術轉換紀錄、檢驗紀錄與重現腳本。
- `packages/`：依人物／封面／證據拆分的獨立自然分包 ZIP，每包不超過 8,000,000 bytes。不是二進位分割檔。

## ID 與整合

頭像 ID：`portrait-philosophy-socrates`、`portrait-philosophy-confucius`、`portrait-philosophy-zhuangzi`、`portrait-philosophy-nietzsche`、`portrait-philosophy-plato`；封面 ID：`cover-philosophy`。

將本包唯一命名的資產併入 `collaboration/ui-kit/assets/`，由整合者彙整 manifest；不要用本包 manifest 覆寫其他 pack 的清單。`persona_id` 是 `philosophy-{slug}` 的整合別名，須與父任務最終人物 schema 核對，穩定美術 ID 不變。建議頭像 `object-fit: cover; object-position: 50% 50%`；圓形可用 CSS `border-radius: 50%`。封面保持 16:9，勿任意裁切掉最外側人物。文字標示使用 UI／alt，不烤進素材。

**必要揭露：**「歷史人物為藝術詮釋，非經核實肖像；跨時代聚會為創作，並非真實會面。」

## 製作與限制

使用內建 `image_gen.imagegen` 逐張生成真實 raster 插畫，沒有 SVG／CSS 占位圖；模型名稱與模型版本未由工具揭露，不臆測填寫。資產 v1.0.0 與生成修訂 v1／v2 分開記錄。頭像不使用參考肖像；封面 v2 只以本包自己生成的 v1 作風格修訂。不得宣稱已核實外貌、服制或可任意商用，權利／正式版評估仍待確認。

僅以 Pillow 做已授權的尺寸轉換、16:9 中心裁切、圓形 alpha 裁切及機械 QA 總覽；沒有程式重畫人物。原始檔位元組保持不變。輸出為扁平 raster，工具未提供可編輯圖層。非 Lumi、非電影《空山問獅會》素材，未引用或修改該等資產。

本包完成圖像自查與檔案驗證，不等於正式產品整合驗收。未更動桌面 repo、路由、正式資料、伺服器或 UI 元件，未執行 mobile／Safari／瀏覽器整合測試；由父任務／Jerry 進一步接入與驗收。

## 可重現檢驗

在本目錄執行：

```sh
python provenance/export_assets.py
python provenance/verify_assets.py
python provenance/package_assets.py
```

Python 3＋Pillow；原始來源保留於 `assets/originals/`。首次生成及一項封面風格修訂的精確提示詞、來源和輸出均附於 `provenance/`。
