# 歐桑 v1.1 獨立候選交付摘要（供組員審查）

v1.1 首次程式基準：`6a0f8cf651a6869361e1c378a3fe2a83884d7161`；上次遠端待審查版 `7e3301eab31b0c25283545c9286bcec97c254fdf`；v1.1 文件基準 `ae5a9dc57cc49886427d3cb8ac7cc94bdc00065d`。本次另含 2026-10-30 三項審查修正；最新提交以本 PR head 為準。所有改動只在 `collaboration/ui-kit/` 的待審查分支，**尚未 merge 或 deploy**。此摘要是可審查候選，不是十四類整體驗收通過。

## 一分鐘摘要

- 舊版已有隔離的 React／TypeScript 展示套件、指定十五人物及劇場、另附十五張原創愛好者 TXT、三項新孵化／回饋圖。v1.1 在此之上增加受控月份與週排程、三習慣、錄音／附件／校對 mock 契約與 IndexedDB 本機草稿、六 Lumi 姿勢和左右殼、日間／Quiet 房間、音效，以及完整輸入／面板狀態展示。本輪**未修改**兩套既有角色內容，未把人物劇場寫入正式服務。
- 隔離套件的最新程式通過 TypeScript、Vite build、55 個 Vitest 測試；Chrome localhost 定向操作檢查通過。2026-10-30 審查修正的失敗→修復證據見 [三項回歸紀錄](qa/v1_1/REVIEW_FIXES_20261030.md)。Boyi 美術／聽審、Jerry 正式接入與實機／Safari 都未完成。
- 立即需要組員判斷的是：蛋殼與完整蛋非同源素材、世界 1920 圖是小原稿上採樣、三組群像在手機中心裁切失去邊緣人物；此外真回執、權限、上傳、AI 與正式資料模型須由宿主提供。

## 從上次遠端版到本地候選

| 階段 | 實際變更 | 審查線索 |
|---|---|---|
| P0 操作 | 月／週日期及固定時區、三行動安排、32 SVG 圖示、按鈕契約、十類輸入六狀態、未保存退出與錯誤退路 | `src/ScheduleDemo.tsx`、`src/MediaDemo.tsx`、`src/InputGallery.tsx`、`src/PanelGallery.tsx`；[候選矩陣](V1_1_CANDIDATE_MATRIX.md) |
| P0 媒體 | 明示 mock 延遲／取消／錯誤；真本機檔預覽，原素材／辨識原文／校對文分離；owner＋draft＋revision IndexedDB 續作與衝突處理 | `src/PersistentDraftDemo.tsx`、`src/media-workflow.ts`；`qa/v1_1/P0_P1_P2_BATCH_3_20261029.md` |
| P1 視覺 | 六姿勢、真正左右兩片殼、獨立陰影／養分；日／Quiet 橫直房間和分層；一般確認採無殼 Lumi；孵化／轉場取消、重播、卸載與減少動效契約 | `src/LumiPoses.tsx`、`src/WorldRoom.tsx`、`src/Hatch.tsx`、`src/Transitions.tsx`；`qa/v1_1/P1_DERIVED_EXPORTS_20261029.md` |
| P2 聲音 | 五事件各兩個原創程式合成候選，共十聲；每聲 WAV、AAC／M4A、Ogg 三格式，預設關閉、Quiet 無聲、回執去重 | `assets/audio-candidates/manifest.json`、`src/SoundGallery.tsx`；`qa/v1_1/P0_P1_P2_BATCH_3_20261029.md` |

源碼獨立審查從 `fff363c` 指出週起點、慢回讀／慢保存、真 Blob 續作與逐事件音長缺口；`d82f781` 修正週對齊、草稿競態、真檔／原文保存及五個過長音效；`0ed1790` 再修訂「文字修改即取消核對」與慢回讀保留原 Blob。母端另對**當時**的三格式 30 檔獨立查核 48 kHz 與逐事件時長。2026-10-30 補修 Dialog 焦點、劇場切換／刷新與非法日期；最新 55 個測試和 Chrome 檢查是**交付端本機重跑**，不能說成母端重跑或人工驗收。

## 如何開啟與先看哪些內容

在 `collaboration/ui-kit/`，Node 24 與鎖定依賴就緒時，可執行 `corepack pnpm install --frozen-lockfile`、`corepack pnpm dev -- --port 5174`，開啟 `http://127.0.0.1:5174/`。本機 Windows 的 npm shim 未提供 Node 設定，因此實際驗證是用已配置的 Node 24 執行 `node_modules/typescript/bin/tsc --noEmit`、`node_modules/vitest/vitest.mjs run`、`node_modules/vite/bin/vite.js build`；Vite 啟在 127.0.0.1:5174，再依序執行 `tests/v11-controls-qa.mjs`、`v11-lifecycle-qa.mjs`、`v11-interaction-qa.mjs` 與 `v11-lumi-qa.mjs`。Chrome 路徑由本機腳本指定，其他環境須調整後重跑。

建議審查順序：先看首頁與「元件」頁的輸入矩陣／面板退路，再看排程與媒體草稿重整、世界日／Quiet、孵化與轉場、音效靜音政策，最後看人物劇場與來源標記。先審核套件事件及素材限制，再由 Boyi 判斷視覺／聽感、由 Jerry 決定正式能力接線；不要把 fixture 回執當真交易。

## 十四類狀態速覽

| 類別 | 候選狀態 | 主要待驗／缺口 |
|---|---|---|
| 1 設計基礎 | 可供審查 | Safari／正式宿主隔離與安全區 |
| 2 按鈕 | 可供審查 | 正式宿主鍵盤與輔助技術 |
| 3 輸入 | 可供審查 | 正式校驗及保存規則 |
| 4 導覽、卡片、排程 | 可供審查 | 正式目標與帳本接線 |
| 5 面板與回饋 | 可供審查 | 真路由離開、保存及錯誤碼 |
| 6 多模態 | 部分完成 | 真麥克風、上傳、辨識、認證與後端 |
| 7 App 圖示 | 可供審查 | Boyi／平台實機驗收；無向量原稿 |
| 8 Lumi 與世界 | 部分完成 | 原生高解析世界原畫、日／Quiet 精準同構圖及美術驗收 |
| 9 蛋 | 部分完成 | 同源完整蛋／裂口／左右殼與逐格連續原畫 |
| 10 孵化 | 部分完成 | 真回執與正式宿主、人工動效審查 |
| 11 正向回饋 | 可供審查 | 亮度／節奏及正式觸發驗收 |
| 12 人物美術 | 部分完成 | 手機五人群像裁切及 Boyi 驗收 |
| 13 轉場 | 部分完成 | 逐格／atlas 素材及宿主事件驗收 |
| 14 音效 | 部分完成 | Boyi 聽審、Jerry 跨瀏覽器與正式觸發 |

詳列可審查證據與限制見 [最新核對](qa/v1_1/P0_CONTROLS_ART_AUDIT_20261029.md)。本表的「可供審查」只指套件內候選，**沒有任何一類被宣告正式驗收完成**。

## 測試、資產與不可代替的外部工作

- 交付端最後程式：TypeScript exit 0；Vitest **18 檔／55 測試**；Vite build exit 0；本地 Chrome 的焦點、劇場同 owner 續作／切換、控制項及既有互動腳本通過，相關日期純函式與無效畫面由單元測試檢查。真 PNG 在 `qa/v1_1/controls-*.png`、`lumi-assembly-*.png`、`world-*.png`、`mobile-p0-*.png`，是先前畫面證據；新修正的操作斷言與失敗反例見 `qa/v1_1/REVIEW_FIXES_20261030.md`。這些不是實機／Safari、真 API 或人工驗收。
- `assets/derived-v1_1/manifest.json` 記 40 張真 PNG：六姿勢各正規化母版＋512／256／128，共 24；左右殼各 512／256／128，共 6；陰影與養分各 512／256，共 4；日／Quiet 房間各 1920×1440、1280×960、768×1024，共 6。`tools/verify_visual_derivatives.py` 核對原稿 hash 未變、透明像素與落地錨點。六姿勢母版用 alpha bbox 等比調整到可見身高 790、腳底錨點 `(627,1030)`，並非重新繪圖。1920 是由 1448 原生橫稿上採樣；左右殼非完整蛋同源抽層，不能以尺寸合格替代視覺驗收。
- 十聲音效共有 **30 個播放／原稿檔**，分別為 48 kHz WAV、AAC／M4A、Ogg；逐事件時長、峰值與 SHA 在音效清單。Quiet 無聲與重複回執不重播在 Chrome 候選檢查，聽感、不同瀏覽器和正式觸發仍待 Boyi／Jerry。
- 指定十五人物、六場劇場及另附十五原創愛好者卡是舊版沿用內容，本次 v1.1 **未改角色卡、人物設定或劇情**；創作內容的人工審閱與正式採用仍由組員決定。`content/original-enthusiasts/` 不替代劇場指定人物。
- App icon／十五肖像／三封面實際尺寸與 SHA 稽核在 `qa/v1_1/APP_PERSONA_AUDIT.json`。`qa/v1_1/persona-cover-mobile-*.png` 是審查裁切圖，中心裁切無法保留兩側人物，**不是 runtime 素材**；手機正式群像需重新構圖，或用 contain 並檢查版面。

## 舊版交接紀錄（v0.4 歷史，以下不代表 v1.1 目前狀態）

### LW-SIM-001／LW-UI-001／LW-ASSET-001 更新交接

## 任務卡

| 欄位 | 狀態 |
|---|---|
| 主責／審查 | 歐桑；Boyi 產品／內容、Jerry 技術／正式接入 |
| 目前狀態 | 接入實作、單元／型別／建置及本輪六張靜態畫面核對完成；待審查，不等於 Boyi／Jerry 驗收 |
| 共同規格 | `1c9d502f32688bcc3c73e4b99a2cc3724c179047` |
| 恢復來源 | `LifeWorld_ui-kit_full_b3a715c.zip`，SHA-256 `0683792faff60acb7d3adf01f0a7a5c854e9ee49853d8669ea872123fe9a5cf0` |
| Git 邊界 | 本地工作樹以 b3a715c 為上一提交；本輪新增內容與驗證證據另成提交 |
| 目錄／分支 | 僅 collaboration/ui-kit；work/ousang-full-kit 待審查分支，不改 main |
| 最新使用者範圍 | 三張新圖接回 UI 後再上傳；世界基底先延後；人物以創作合理性／角色一致性為主；互動測試延後 |

## 本次變更

- Hatch 將 open／complete 接回專用分離蛋殼與完成定格；保留 deepcrack 獨立階段，回執、重播、跳過、取消仍不改帳本。
- PositiveFeedback 在人工確認 fixture 與流程回饋中組合獨立養分／Lumi；無回執不顯示。無聲定格，Quiet 降低光效亮度。
- 三張 1254 RGBA 原稿、生成來源及 SHA 保持原檔，清單新增實際狀態、尺寸、錨點、限制；AssetGallery 與舊缺件文案更新。
- FlowSamples 補四主分頁樣板、麵包屑、目標／故事卡；不改正式導覽。
- content/original-enthusiasts 追加十五原創 TXT、索引及重算摘要。HS01 exact hash 保持；不替換原三國／職務／哲學十五人。
- ArtReview 為共享實際元件的只讀固定 fixture；新測試／靜態截圖腳本與本交接可供接續。

## 實際驗證與限制

本輪 `pnpm test` 6 檔／22 案例通過；`pnpm build`（tsc -b + Vite）通過。日誌在 `docs/qa/20261029/`。新圖原像素與 alpha 實測通過，所有 top-level 清單路徑存在。15 份追加卡的 60 段各 1000 漢字與 HS01 雜湊通過。

**本輪靜態版面 gate 已通過，仍非完整產品驗收。** 在受核准的本機 Windows Chrome 環境，以暫時 Vite localhost 服務執行 `tests/static-art-qa.mjs`，六個 day／quiet／reduced × 390／1280 固定畫面全數載入；無破圖、水平溢位或仍運行的動畫。六張真實 PNG 已目視檢查分離蛋殼、完成 Lumi、養分層級、留白與 Quiet 呈現，見 `docs/qa/20261029/art-*.png` 與 `static-layout.json`。舊 `static-layout.txt` 僅記先前失敗，不代表最終狀態。

另用 `tests/static-ui-qa.mjs` 核對全套 UI 的五個主展示頁手機／桌面、六種關鍵構圖、五種系統狀態及共用元件 Quiet／減少動效，共 21 張固定 PNG；無破圖或橫向溢位，已逐張目視檢查。逐項覆蓋、實際布局證據與未驗的開啟／互動狀態見 [全套 UI 靜態核對](qa/20261029/OVERALL_UI_STATIC_AUDIT.md)。靜態通過不代表整套 UI 或正式 App 已完成驗收。

最後程式版本 `035aae19d19242cf93f01bb804c23c566b0d0165` 的獨立重跑指令、UTC 時間、原始輸出及三項退出碼記於 [最終程式檢查紀錄](qa/20261029/final-code-checks.txt)。這份紀錄是在新增全套 UI 靜態審查程式後執行，與前版 19726ce 的測試日誌分開；其後只追加此 QA 紀錄及交接文字，未改程式。

`pnpm dev --port 5174` 保持運行，另一終端 `node tests/static-art-qa.mjs` 可重現固定 fixture；只讀取 `?art-review&mode=day|quiet|reduced`，390×844／1280×800。可設定 `CHROME_PATH`。本輪沒有執行 qa:visual 舊互動腳本；新互動、Safari、實機延後。

## 美術與接入契約

Hatch 容器維持 300px（手機270px）高；新增圖以 contain、最大276px／12px安全留白呈現，錨點 (0.5,0.88)。回饋為最大300px正方形、光效全幅在後、Lumi 84%居中在前，Quiet opacity .38、日間 .65。所有模式無聲且定格，不依賴動畫完成才可繼續。

PNG 是平面原稿：蛋殼兩半仍同一檔，完成 Lumi 與殼亦非獨立圖層；獨立蛋／分離殼／完成／養分檔可組合，無 PSD 或原生向量宣稱。新圖細 alpha 斑點及完成圖窄側邊保留；六張固定合成畫面已目視核對，仍待產品美術審查。未重採樣導出另尺寸；原稿兼 runtime 來源，CSS 控制顯示。

## 不變內容與後續

規定 15 人、6 場、18 主路徑、90 人物專屬首輪回應、45 多輪示例（每例至少4輪）、30 保留評估題及參考隔離仍保持。資料 reviewed=false 不改成通過；先前機器來源定位紀錄只屬歷史，不把創作任務變事實考核。即時 AI 端點／金鑰／正式 App、DB、部署與 Summit 不在範圍。

世界基底及新互動測試明確延後；其餘十三類與最終靜態 gate 見 [13_CATEGORY_AUDIT](13_CATEGORY_AUDIT.md)。Boyi／Jerry 尚未審查；只有真實對應檢查與審查後才可更新為已驗收。
