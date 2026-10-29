> 2026-10-29 更新：三張新美術已接入、原創十五卡已追加。22 項測試、型別檢查、建置及六張新靜態畫面核對通過；Boyi／Jerry 尚未驗收。詳見 [最新交接](docs/HANDOFF.md) 及 [十三類盤點](docs/13_CATEGORY_AUDIT.md)。

# Life World 獨立展示套件

來源共同 commit：`1c9d502f32688bcc3c73e4b99a2cc3724c179047`；工作分支：`work/ousang-full-kit`。

本目錄是獨立 React＋TypeScript／Vite 展示，不是正式 App。人物與劇情是 demo，所有錄音、附件、回執與進度狀態目前均為 fixture。正式 App 維持 Python／SQLite／原生前端；本目錄不呼叫其寫入 API。

## 啟動

需求：Node 24、pnpm 12。於本目錄執行：

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

打開 `http://127.0.0.1:5173/`。執行 `corepack pnpm build` 與 `corepack pnpm test` 驗證。本輪 Windows 環境的預設 `node` shim 未啟用，實際使用 Codex 附帶 Node 24.22.1 將其 `bin` 目錄加至 PATH 後執行。

## 瀏覽器畫面驗證

在 Windows 安裝版 Chrome 可用時，另開終端以 `corepack pnpm dev -- --port 5174` 啟動本機展示，再執行 `corepack pnpm qa:visual`。此腳本只開啟 `127.0.0.1:5174`，用隔離的無頭 Chrome 測試 390×844 與 1280×800、破圖和水平溢位，將四張實際 PNG 寫入 `docs/qa/screenshots/`。其他作業系統可修改腳本的 Chrome 執行路徑後重跑；既有截圖是本輪 Windows Chrome 的實測證據，不代表實機或 Safari 驗收。

## 契約與隔離

- `src/contracts.ts` 定義人物、場景、來源、資產、對話、session、即時 adapter 及孵化事件。
- `src/engine.ts` 驗證節點、執行預寫分支、隔離 session、匯出標記為 simulation 的 JSON；沒有即時 adapter 時回報未設定。
- `src/Theater.tsx` 接收版本化內容與來源清單。換人物／場景、重設與返回均限當前 session；使用者主動匯出，不自動匯入正式經歷。
- 正式接入前需由 Jerry 核對資料模型、回執來源、權限、取消、錯誤及入口。Boyi 決定示範角色是否保留正式版。

完整需求與目前缺口見 [PLAN](docs/PLAN.md) 與 [PROGRESS](docs/PROGRESS.md)。

## 本輪靜態核對（不執行延後的互動測試）

`pnpm dev --port 5174` 保持運行；另一終端 `node tests/static-art-qa.mjs`。Windows 預設 Chrome 安裝路徑，其他位置用 `CHROME_PATH` 指定。已輸出六張 day／quiet／reduced × 390／1280 靜態圖與 `static-layout.json` 至 `docs/qa/20261029/`。上方舊 qa:visual 是歷史互動腳本，不在這次授權測試範圍。

追加內容：[原創興趣人物十五卡](content/original-enthusiasts/README.md)。
