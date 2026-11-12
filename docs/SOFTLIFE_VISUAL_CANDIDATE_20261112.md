# PR #26 · Soft Life 視覺適配候選

日期：2026-11-12。狀態：Soft Life 視覺候選，使用者已授權推送 PR #26 既有分支供審查；不代表合併、部署或全部驗收完成。

## 基準與範圍

- 初始產品基準：PR #26，`804f3f43135617ef708de38e94074bdfb24b557c`。
- 視覺來源：[Lumi Soft Life 視覺測試](https://life-world-lumi-soft-life-20261111.rhythmicsmile8.chatgpt.site)，v1，來源 commit `0d3b37659f5eb44b50ee41de0e5bc41817490779`。僅讀取來源，未變更該 Site。
- 在全新隔離 clone 的 `visual/pr26-softlife-20261112` 分支製作，沒有覆寫他人未完成工作。
- 使用既有 FastAPI／原生前端 App，不以獨立展示站取代 PR26，不導入 React 或新 runtime 依賴。

## 已實作

1. 歡迎、世界及孵化後的 Lumi 使用 demo 的原始 3D 主視覺，保留暖白身體、薄荷綠嫩芽、基座與目標蛋。未重畫或冒充另一份圖。
2. `softlife.css` 為可獨立移除的外觀層，統一暖白背景、薄荷綠狀態、深綠操作、圓角、輕陰影、表單、目標卡及人物對話框。
3. 保留世界／目標／紀錄／關係四主分頁、PR26 四步紀錄流程、既有提示及表單欄位。補齊 680px／360px 規則、手機安全區留白及鍵盤焦點。
4. 圖片無法載入時仍回到既有 CSS Lumi。舊角色、房間及四階段破蛋圖檔完整保留；世界頁只隱藏與新主圖重複的裝飾。
5. 小目標蛋採用柔和立體漸層；首次孵化的四階段圖與三次輸入鎖仍沿用 PR26，未新增或改寫孵化狀態。

素材：`app/static/art/softlife/lumi-hero.png`，1536 × 1024，1,443,016 bytes。

SHA-256：`4fc69c850fd760cc85882d40b48ab1ea1eb946964e4d3dd6d2c0a21d95c50750`。

## 保護條件

- 不更動 API、schema、登入、所有權、人工確認、積分、排程與資料保存邏輯。
- `app.js` 的唯一變動是 Lumi 圖片模板的來源／尺寸與說明。其餘產品 JavaScript 不變。
- 「一帳號一 Lumi、多顆目標蛋」是使用者產品方向；PR26 目前仍限制同時一個未結束目標。本次只換視覺，不把 demo 多願望行為移入正式規則，也不宣稱已完成多目標支援。
- 初次離線交付沒有遠端 push；本次依後續授權推送 PR26 既有分支。無 merge、Site／GCP 部署或正式資料庫操作，測試只用隔離合成資料。

## 初次候選驗證（804f3f4 基準）

| 檢查 | 結果 |
|---|---|
| `LIFEWORLD_NODE=$(command -v node) ../test-venv/bin/python -m pytest -q` | 772 passed、87 skipped、0 failed |
| Node 音效／孵化／數量／Soft Life 契約測試 | 29 passed、0 failed、0 skipped |
| `node --check app/static/*.js`，逐檔執行 | 全部通過 |
| tinycss2 遞迴解析 `softlife.css` | 0 errors |
| `git diff --check` | 通過 |
| 同一命令內啟動隔離服務並 GET `/` | HTTP 200 |

87 skipped 包含未配置的隔離 PG18 與非目前平台案例，不能當 PG 驗收通過。新增 Node 案例檢查主題載入順序、四主分頁保留、精確素材指紋、Lumi 失敗退路及無外部資源。另針對新增小字色檢查與暖白、側欄及主視覺背景的 4.5:1 對比。

### 未完成的驗證

初次雲端環境 Chromium 啟動被 `socket() Operation not permitted` 阻擋；受支援的瀏覽器無法連到命令隔離網路內的服務。沒有取得本輪桌面／手機截圖，沒有宣稱完成像素、觸控、Safari 或真實瀏覽器端到端驗收。

交付包中的 9 份 HTML（歡迎、首次介紹、世界、目標、目標儀表板、紀錄第一步、經歷收藏、人物收藏冊、首次孵化）已經 JSDOM 載入確認，0 errors。這些 HTML 是真實 PR26 renderer 配合隔離 API 合成資料輸出的唯讀 DOM 快照，方便產品檢視；不是上線版本，不包含登入 Cookie 或可寫入 API，也不取代上述未完成驗證。

## 接續 PR26 最新基準（2026-11-12）

使用者在離線候選交付後指示「OK，幫我推上去」。重新核對 PR26 時，遠端已由初始基準前進三個提交至 `846f250d3645b4e916a3050dee72df3a7b8bcf48`。本次在 Windows 電腦的全新隔離 clone 套用同一補丁，乾淨套入，保留 `22c99eb` 的生日／期間防呆及後續兩個證據文件提交。相對新基準仍只有四個產品視覺檔案，以及測試與交付文件；沒有改動新防呆、API、schema 或所有權邏輯。

- 本輪 Windows Python 3.12、專案鎖定依賴、隔離合成 SQLite：`python -m pytest -q --basetemp=../pytest-data`，**779 passed、90 skipped、0 failed，208.29 秒**。跳過包含 PG18 與非本平台項目，不是 PG 驗收。
- `node --test tests/frontend_audio_lifecycle.cjs tests/frontend_birth_lifecycle.cjs tests/frontend_quantity.cjs tests/frontend_experience_validation.cjs tests/frontend_softlife.cjs`：**58 passed、0 failed、0 skipped**。
- 真實 Chromium 指定新防呆回歸 `browser_tests/test_early_validation.py`：**23 passed、0 failed、0 skipped，51.75 秒**，使用固定時鐘的 `integration_server` 與全新合成 SQLite，不是 PG 測試。Windows 初次因系統 MIME 將 `.js` 回覆 `text/plain` 而阻擋載入，保留初次失敗紀錄；只在隔離啟動器設定 `application/javascript` 後重跑，未改 repo、系統登錄或任何測試斷言。
- 全部 `app/static/*.js` 的 `node --check` 通過；`git diff --check` 通過；原始主圖 SHA-256 保持不變。
- 1440／390／320px 的歡迎、世界、目標、紀錄、關係、歷史及世界頁圖片失敗退路，共 **21 個畫面無水平溢出**；Lumi 三寬度皆載入 1536×1024 圖片，失敗時舊 CSS 角色可見且原圖片隱藏；JavaScript pageerrors **0**。留存 27 張合成資料截圖（含 6 張新防呆），已目視代表畫面，未見阻擋操作的裁切或重疊。這不是完整 browser_tests、Safari、觸控或產品主觀視覺核准。
- 使用現有 GitHub 認證讀回此 repo 的 `push: true`，並通過不改遠端的 push dry-run。目的地限定 `integration/pr24-first-unified-schema010-20261111`，只做普通 fast-forward push，不推 main、不 force、不 merge。
- 未發現 GitHub Actions workflows；repo 既有 Cloud Build 文件及發布器限定 main，這三個新提交未改部署檔。無 repo hooks 管理讀權，不能據此宣稱已盤點所有外部設定。本次不呼叫任何 Cloud Build／GCP 或部署工具。

## 剩餘驗收

已補主要頁面三寬度與圖片退路檢查。仍須完整覆蓋首次介紹、三次孵化、目標排程、四步紀錄所有分支、人物預覽與取消／返回、200% 字體及 reduced-motion，並提交產品與技術審查。合併與部署仍需另有授權。

移除新主題 link、還原唯一 Lumi 模板修改即可回到 PR26 外觀；舊資產與資料邏輯未刪除。
