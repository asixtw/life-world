# 2026-10-30 三項審查修正：失敗、修復與驗證

本輪起點 `fdbd8d906b7e33e6e62257c25e62fb128760db56`，範圍只在 `collaboration/ui-kit/`。劇場仍為單人預寫腳本；未加入多人、自訂情境或場次預算。沒有改正式 App、API、DB、Experience、Person、Reward 或美術原稿。本紀錄是交付端本地候選驗證，非 Boyi／Jerry 人工驗收。

## 先重現的真實失敗

| 問題 | 修正前反例與結果 |
|---|---|
| Dialog 焦點 | `node tests/review-fixes-qa.mjs --dialog`：`pressSequentially('逐字輸入測試')` 後文字／焦點斷言失敗，`dialog rerender stole typing focus`，exit 1。原因是 inline `onClose` 每次 render 改身份，使 effect 清理後再聚焦關閉鍵。 |
| 劇場對話丟失 | `node tests/review-fixes-qa.mjs --theater`：選柏拉圖、進入場景並走一輪後刷新，`same owner refresh lost dialogue`，exit 1。舊選角／場景處理也直接清空 session/history，沒有切換確認。 |
| 非法日期 | `node node_modules/vitest/vitest.mjs run tests/schedule-model.test.ts`：新增非法月份／日數／閏年／格式案例在 `2026-13-01` 觸發 `RangeError: Invalid time value`，1 失敗／4 通過，exit 1。 |

## 實際修復

- `Dialog` 的開關 effect 只依 `open`；`onCloseRef` 每次 render 更新事件回呼，輸入期間不再重新初始化焦點。Escape、關閉鍵、開啟初始聚焦與取消未存退出均由 Chrome 腳本檢查。
- 劇場增加明示 fixture owner 的 `sessionStorage` 命名空間、同 owner 的選角／場景／回合／返回快照恢復；更換人物、場景或重設有確認／保留兩條路。不同 owner 導航與壞 JSON 退回安全空草稿。owner 字串只是**隔離展示鍵，不是正式認證或權限控制**；草稿只在同一瀏覽器分頁有效，不寫正式人物、經歷或獎勵。儲存被拒時顯示刷新風險並保留本頁操作。
- 日期先檢查格式與 `Date` 是否有效才轉 ISO；無效月／週回空集合或空字串，`MonthSchedule` 顯示可讀警告、停用前後期並保留「今天」恢復入口。閏年真日期仍可使用。既有目標時區語義不變。

## 修正後驗證

- 本機 Node 24：`node node_modules/typescript/bin/tsc --noEmit` exit 0；`node node_modules/vitest/vitest.mjs run` **18 檔／55 案例全通過**；`node node_modules/vite/bin/vite.js build` exit 0。
- 本機 Chrome／Playwright 連隔離 Vite `127.0.0.1:5174`：`review-fixes-qa.mjs --dialog`、`review-fixes-qa.mjs --theater`、`v11-controls-qa.mjs`、`v11-interaction-qa.mjs` 全部 exit 0。劇場腳本核對同 owner 刷新、跨 owner 不讀取、取消場景切換與重設、確認人物切換；既有三路線／返回／重設／匯出、月份操作與 Dialog 退路也重跑。手機採 390×844；既有互動腳本另含 1280×800。
- 沒有新增截圖：本輪重點是焦點、資料保留與例外退路的操作斷言。舊截圖未冒充本輪修復證據；新瀏覽器腳本與單元測試就是可重現證據。

## 尚未驗證

正式 owner 認證、伺服器草稿持久化、跨分頁／跨裝置同步、真 API／資料庫、Safari／實機及 Boyi／Jerry 人工驗收均未執行。`sessionStorage` 是本機候選續作機制，不能取代正式產品保存政策。美術缺口仍依 [交接摘要](../../HANDOFF.md) 保留。
