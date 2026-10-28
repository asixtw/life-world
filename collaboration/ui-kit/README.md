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

## 契約與隔離

- `src/contracts.ts` 定義人物、場景、來源、資產、對話、session、即時 adapter 及孵化事件。
- `src/engine.ts` 驗證節點、執行預寫分支、隔離 session、匯出標記為 simulation 的 JSON；沒有即時 adapter 時回報未設定。
- `src/Theater.tsx` 接收版本化內容與來源清單。換人物／場景、重設與返回均限當前 session；使用者主動匯出，不自動匯入正式經歷。
- 正式接入前需由 Jerry 核對資料模型、回執來源、權限、取消、錯誤及入口。Boyi 決定示範角色是否保留正式版。

完整需求與目前缺口見 [PLAN](docs/PLAN.md) 與 [PROGRESS](docs/PROGRESS.md)。
