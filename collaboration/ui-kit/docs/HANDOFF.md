# LW-SIM-001／LW-UI-001／LW-ASSET-001 工作包交接

| 欄位 | 狀態 |
|---|---|
| 人類主責 | 歐桑；Codex 為協作工具 |
| 產品／技術審查 | Boyi／Jerry，均尚未審查 |
| 目前狀態 | 製作中，非完整交付或驗收 |
| 來源 commit | `1c9d502f32688bcc3c73e4b99a2cc3724c179047` |
| 分支／範圍 | `work/ousang-full-kit`，僅 `collaboration/ui-kit/` |
| 主要輸入 | `docs/team/PROMPT_OUSANG_START.md`、`PROMPT_SIMULATION_001.md`、`PROMPT_UI_001.md`、`ART_DELIVERY_SPEC.md`、`FLOWS_AND_STATES.md` |
| 完成條件 | [PLAN.md](PLAN.md) 全部清單與實測證據；目前未達成 |
| 決策阻礙 | 名單依文件還是原創愛好者卡，待 Boyi 確認 |

## 變更與啟動

獨立 Vite／React／TypeScript 展示專案新增在本目錄，無正式 API、DB、獎勵政策、根工具鏈變更。`src/contracts.ts` 定義資料與 adapter；`src/engine.ts` 負責預寫分支與匯出；`src/Theater.tsx` 將接內容包。`src/components.tsx`、`Hatch.tsx`、`FlowSamples.tsx`、`App.tsx` 與 CSS 負責元件、狀態與畫面展示。啟動方式見 [README](../README.md)。

## 驗證

| 案例 | 實際操作 | 結果與限制 |
|---|---|---|
| TS／建置 | `tsc -b`、`vite build` | 2026-10-28 16:52 UTC 通過；37 模組轉換，待最新提交再複驗 |
| 契約測試 | `vitest run` | 2 檔 8 案例通過；腳本、缺引用、循環分支、無即時端點 |
| 桌面 | Chrome 開啟 `http://127.0.0.1:5173/` | 總覽、元件、紀錄、Quiet 可見；Dialog 開啟後焦點在關閉鍵，Escape 關閉並回到原按鈕；錄音失敗後文字仍保留 |
| 手機 | Chrome viewport 390×844 | 五頁逐頁檢查，無水平溢位、可見按鈕達 44 CSS px；孵化開始／跳過／完成、Quiet／減少動效、BottomSheet Escape／焦點返回，附件與錄音失敗後草稿保留均已操作 |
| 桌面 | Chrome viewport 1280×800 | 紀錄頁無水平溢位、小按鈕及 console error；其餘桌面頁面已有初步目視 |
| 真實 AI／PG／正式 App | 未執行 | 無端點／未接入，不能宣稱通過 |

## 已知限制與接入事項

人物名單決議前 `content/catalog.ts` 保持空白，六場景、評估、肖像與封面未完成。共用插畫由協作圖像工作流製作中，所需檔名與錨點見 [PROGRESS.md](PROGRESS.md)。現行孵化視覺為程式狀態圖層，不能替代規格要求的實際圖像原稿。

Library 美術包在 Windows 官方傳輸 helper 的 `os.setxattr` 步驟失敗，無本地檔案可接入。這是環境不支援，結果確定未安裝；需能保留 Library 身分與雜湊驗證的 Windows 傳入途徑。四項圖像生成另遭工具阻擋，並非已產出。

完整逐類覆蓋、未驗項與截圖工具限制見 [十三類盤點](13_CATEGORY_AUDIT.md)。

Jerry 接入時需：確認示範入口及使用權限；審查每個 ID／source／asset 引用；由宿主注入 `LiveAdapter`，處理權限、取消與後端金鑰；將 `Hatch` 的 `confirmedReceiptId` 接到唯一後端確認回執；避免在元件中呼叫正式計分、收藏或經歷寫入。所有回饋視覺僅反映既有回執。

