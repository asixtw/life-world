# Life World｜HomeHabitOverview 產品與工程交接規格

**文件 ID**：LW-HOME-HABIT-001　**版本**：v0.1（審查草案）　**日期**：2026-11-03  
**對象**：Jerry（後端／整合）、前端實作者、Boyi（產品驗收）　**狀態**：待核准，尚未實作或驗收。

## 0. 基準、來源及決策邊界

本規格依 2026-11-03 核對的 `asixtw/life-world` `main` commit `5f015a616f34` 之 `app/static/app.js`、`goals.js`、`docs/API.md`，以及 `docs/team/BETA_FLOW_SPEC.md`、`ART_DELIVERY_SPEC.md` 制定。參照既有 Goal Dashboard v0.1、Goal Detail v0.2、HabitScheduleDisclosure v0.3、Navigation Contract v0.1。既有正式 App 是 FastAPI + 原生前端；獨立 React UI Kit、Wireframe 示範不等於正式 App 已整合。

**確定既有能力**：四主分頁 `世界／目標／紀錄／關係`；單一未結束目標與三項習慣；`GET /api/state`（實際程式中 `api('/state')`）可取得世界快照，`GET /api/goals/{id}` 可取得目標詳情；`actions[].id/title/progress/target/unit/dates` 等為既有顯示所使用的欄位；紀錄、人工採計及目標完成分屬獨立流程。**待核實**：每個環境／分支中 `/state` 是否提供計算下一安排所需的所有日期、時區與用量版本；以實際 OpenAPI／資料回應為準。

**產品決策**：封測 v1.1 不展示積分、養分或兌換；保留 Lumi 的陪伴、真實經歷及人工確認；不能以排程視作完成。本文不要求改變資料庫、增加習慣數量、增加第五個分頁、變更分數帳本或替換既有 UI Kit。

## 1. 使用者情境與成功條件

進入「世界」首頁的使用者希望一眼理解目前目標下三件持續投入的事，而不先進入目標詳情，也不必看 369 個排程日。

**必須達成**：
1. 一個視覺區塊呈現目前目標名稱與**恰好三筆習慣**（資料異常時明確降級，不以空資料冒充習慣）。
2. 每列至少有「習慣名稱」與「已確認投入／計畫總量及單位」；可選顯示「下一次安排」但無可靠資料時不可推算。
3. 使用者可從各列到該目標詳情的習慣位置；快速記錄仍進入既有經歷草稿／人工核對流程。
4. Lumi 房間維持主要情感視覺；右側卡片簡潔；不要將正式 Goal Detail 整頁搬進首頁。
5. 無計畫日、零投入、到期待回顧、舊目標缺欄位與請求失敗時，畫面仍可理解且不施加懲罰感。

## 2. 範圍與版面位置

| 項目 | 本輪規範 | 不做 |
|---|---|---|
| 主導覽 | 維持世界／目標／紀錄／關係 | 不新增 Dashboard 分頁 |
| 首頁左側 | 保留 Lumi、房間／目標蛋及既有候選資產 | 不重畫 Lumi、房間、不新增寵物動作 |
| 首頁右側 | 目標標題／狀態 → 3 習慣精簡列 → 主要 CTA → 次要入口 | 不呈現完整日曆、七日圖與來源列表 |
| 指標 | 顯示已確認累計 vs 該習慣的後端目標用量、明確單位；下次安排為次資訊 | 不顯示總體成果完成率／平均三習慣百分比 |
| 導覽 | 列項進目標詳情，返回保留位置；記錄走既有流程 | 不在首頁直接寫貢獻或修改排程 |

### 2.1 資訊排序（決策建議，待 Boyi 核准）

1. 目標名稱＋狀態（進行中／待回顧／待補設定）。
2. `HomeHabitOverview`：區塊標題「我的三個習慣」，三個緊湊列。
3. 主要 CTA：「記錄新經歷」，次要 CTA：「查看目前挑戰」。
4. 「繼續草稿」只有草稿存在時顯示；「人物劇場」維持次要入口。
5. 其他世界首頁內容沿用現有邏輯，避免與原本「今日安排／待辦」形成第二份相同的三習慣列表；工程需檢查重複資訊並依 Boyi 決策合併或保留原區塊。

桌面：插入右側現有目標區，不新增大型全寬卡。手機：Lumi 與目標卡上下排列，三列不採水平滾動。

## 3. 功能與操作契約表

| ID | 使用者看到 | 觸發 | 正確行為 | 不變條件 | 優先 |
|---|---|---|---|---|---|
| HH-01 | 「我的三個習慣」 | 首頁載入 | 僅顯示目前未結束目標的三項 action，順序沿用後端 | 不混入歷史目標 | P0 |
| HH-02 | 每項名稱 | 初次渲染 | 顯示完整可讀標題，長文字可換行 | 不截斷唯一可辨識名稱 | P0 |
| HH-03 | 「已確認 2 / 10 次」 | 資料載入 | `progress/target` 由後端提供，保留小數與單位 | 計畫日不等於完成 | P0 |
| HH-04 | 進度視覺 | 更新畫面 | `target>0` 才呈現進度條；可超量時文字顯示真實累計，bar 視覺不超過 100% | 不推出最終成果完成 | P1 |
| HH-05 | 「下次安排 11/05」 | 資料可用 | 從 `dates` 找 **目標時區的今天起** 最早已安排日期（包含今天）；今日當地日期優先取後端 | 不使用使用者電腦當地日曆推測 | P1 |
| HH-06 | 「目前沒有後續安排」 | 無未來日期 | 用中性文字呈現，仍可前往目標詳情 | 不顯示「失敗／中斷」 | P1 |
| HH-07 | 習慣列詳情 | 點擊／Enter | 路由 `#goal/{goalId}`，能定位該習慣則定位，不支援時進一般 Goal Detail | 不新增未經支援的路由 | P0 |
| HH-08 | 「記錄新經歷」 | 點擊 | `#record` 或現有核准的 `#record?goal=...`；使用者仍須自行選擇並確認習慣貢獻 | 點擊不增加進度 | P0 |
| HH-09 | 「繼續草稿」 | 有未確認草稿 | 沿既有草稿入口，保護輸入與附件 | 不從首頁覆蓋舊草稿 | P1 |
| HH-10 | 待回顧提示 | 目標 status=awaiting_review | 呈現「先回顧目前挑戰」，主要 CTA 導向詳情回顧；不假裝仍能直接採計 | 生命週期依後端 | P0 |
| HH-11 | 載入／錯誤／未提供 | API 不完整 | 四種狀態明確分辨；顯示重試或目標詳情入口 | 未知值不補 0 | P0 |
| HH-12 | 完成或結束後 | 無開放目標 | 不顯示過往習慣作為「目前」；提供查看目標旅程或建立下一個目標入口 | 歷史不被重設 | P0 |

## 4. 資料來源與 ViewModel（建議前端 adapter，非新增公開 API）

### 4.1 既有欄位映射

| VM 欄位 | 優先來源 | 備註 |
|---|---|---|
| `goalId`, `goalTitle`, `goalStatus` | `/state` 的目前 `goals[]`，必要時 `/goals/{id}` | 只取單一未結束目標；舊資料多目標依既有目標規則處理，不任選第一個掩蓋衝突 |
| `habit.id`, `habit.title` | `goal.actions[].id/title` | `actionId` 穩定，不以陣列索引當 ID |
| `habit.progress` | `goal.actions[].progress` | **只代表已確認累計**，保留 Decimal 字串 |
| `habit.target`, `habit.unit` | `goal.actions[].target/unit` | 後端已計算標準，不重算用量版本 |
| `habit.nextScheduledDate` | `goal.actions[].dates` + goal 固定 `schedule_timezone` + 可信 `today` | 若 `/state` 未提供資料則先抓該目標詳情；仍缺資料顯示 unavailable；不以 `weekdays` 推導新日程 |
| `habit.nextPlannedQuantity` | 若需顯示，從 `/goals/{id}/calendar` 的日期 `planned_quantities` 取值 | v0.1 **不必顯示**，避免增加請求與口徑風險 |
| `pendingDraftCount` | 世界快照 `drafts[]` | 沿用現有草稿 UX，非習慣列內容 |

### 4.2 候選 TypeScript（只定義呈現適配層）

```ts
export type HomeHabitStatus = 'ready' | 'unavailable';
export interface HomeHabitItemVM {
  actionId: string;
  title: string;
  progress: string | null; // 例如 '0.5'；null=未知，絕不視為 0
  target: string | null;   // 後端權威目標量
  unit: string | null;
  nextScheduledDate: string | null; // null=查明無未來安排；未知使用 status='unavailable'
  scheduleStatus: 'known' | 'none' | 'unavailable';
}
export interface HomeHabitOverviewVM {
  goalId: string;
  goalTitle: string;
  goalStatus: 'active' | 'awaiting_review' | 'needs_setup';
  timezone: string | null;
  today: string | null;
  items: [HomeHabitItemVM, HomeHabitItemVM, HomeHabitItemVM];
  dataStatus: HomeHabitStatus;
}
```

> 型別約束：`items` 必須有 3 筆，否則呈現 `needs_setup`／不完整資料狀態並提供目標詳情入口；不可複製或創造第三個假習慣。Date 是 `YYYY-MM-DD` 的**目標日曆日**。不要把 `null` 同時當作「無安排」與「讀不到」。

### 4.3 日期／用量規則

- 今天由目標固定時區判定；優先使用 `GET /api/goals/{id}` 回傳 `today`。若僅有完整排程而暫無可信 today，`scheduleStatus='unavailable'`；不能用設備 UTC 日期硬算。
- 取 `dates` 中 `date >= today` 的最小日期，須先驗證 date 字串及目標期間。今天有安排即顯示「今天」，明天可顯示「明天」，其餘顯示 `MM/DD` 或 `YYYY/MM/DD`（跨年）。
- 不從星期快選推算 `dates`；已存在 `dates=null` 的舊目標以 `unavailable` 表示，導向詳情補設定。
- `target>0` 時視覺進度 `min(100, max(0, progress/target*100))`；使用精度安全的 Decimal/既有數字呈現 utility，不能將字串精度丟掉造成不一致。若值超額，明示 `12/10 次` 而非 `100% 完成目標`。
- 已確認累計 ≠ 最近 7 天投入 ≠ 最終成果已達標；不混合計算。

## 5. 導覽、資料安全與狀態

- 習慣列為明確的連結或按鈕，使用既有 `#goal/{id}`。**定位特定習慣**屬新增前端協作契約：可先採 `#goal/{id}` 並在渲染後依 `actionId` 聚焦；若計畫使用 query 參數，須先納入 Navigation Contract 路由驗證，**不能宣稱已存在**。
- 記錄操作沿用現有 `#record`／已支援的 `#record?goal=...`；若要直接預選 `actionId`，必須由 Jerry 與前端先確認路由及表單契約。預選不得產生貢獻，提交仍由人確認。
- 從首頁去詳情、返回首頁時保留有意義的滾動與焦點；瀏覽器 Back/Forward、滑鼠側鍵依共用 Navigation Contract 處理，不自行監聽水平滾動。
- 不存未經確認內容於 URL，不包含人物原文或敏感素材；所有資料沿 owner 授權。
- 不要為首頁單獨儲存統計表；Dashboard 只讀，不向後端送 `progress`／`target` 修改。

## 6. 資料與 UX 狀態表

| 情況 | 應顯示 | 禁止 |
|---|---|---|
| 首次載入 | 三列 skeleton（或簡潔「載入習慣中」） | 閃爍假 0/0 |
| 已確認值 0 | `已確認 0 / N 單位` | 「失敗」「落後」 |
| 尚無下一安排 | `目前沒有後續安排` | 紅色警告／自動扣分 |
| 排程資料未知 | `下次安排暫無法顯示` | 顯示「沒有安排」假結論 |
| 待回顧 | `這次挑戰待回顧` 並進目標詳情 | 將未採計直接加進進度 |
| 待補設定 | `需先補齊目標設定` | 猜測舊日期 |
| 目標已結束／完成 | `這段挑戰已收藏` 或顯示新目標入口 | 仍顯示「進行中」 |
| API 失敗 | 保留整體首頁其他可用區塊，習慣區顯示可重試錯誤 | 空白／顯示非本帳號快取 |
| 長名稱／200% 字級 | 可換行、不裁切，操作區可下移 | 文字疊圖、水平捲動 |

## 7. 介面示例（內容為示意）

```text
┌─ 右側目前挑戰 ─────────────────────────┐
│ 成為海賊王                      進行中 │
│ 三個習慣，照自己的步調前進。           │
│                                       │
│ 我的三個習慣                          │
│ 每天健身               已確認 2/10 次 │
│                         下次 11/05    │
│ 認識三個朋友成為船員   已確認 1/3 次  │
│                         今天有安排     │
│ 吃惡魔果實             已確認 0/1 次  │
│                         尚無後續安排   │
│                                       │
│ [記錄新經歷]  [查看目前挑戰]           │
│ [繼續草稿（有才顯示）] [人物劇場]     │
└───────────────────────────────────────┘
```

上例數值純屬 fixture，正式頁面不得寫死。Lumi 在左側；右側僅放三個精簡摘要，沒有週圖、月曆或日期全集。

## 8. 工程交付物與驗收門檻

**Jerry／前端必交**：
- 一個純 `mapHomeHabitOverview(goal, trustedToday)` 函式，附資料來源對照與單元測試；格式化函式須正確處理 Decimal、未知、跨年與長標題。
- 組件顯示與事件整合；新增焦點定位／預選行動的情況須明訂 Route Contract，沒有契約時先走通用目標詳情及紀錄。
- 以合法帳號的 `/state` 或 `/goals/{id}` 讀取，不新增寫入 API／資料表；檢查 3 習慣數量、`awaiting_review`、`needs_setup`。
- 更新首頁主 CTA 層級但不破壞既有四主分頁／人物劇場／草稿復原。
- 真正跑測試並保存命令、結果、手機／桌面畫面；不以 Figma gallery 的通過紀錄代替正式 App。

**合併前門檻**：附共同文件 `03_HomeHabitOverview_驗收與交付清單_v0.1.md` 中的 P0 測試結果；與 Boyi 核對首頁是否保留舊「今日安排」區，避免重複資訊；確認首頁不顯示封測禁用的積分／養分。

## 9. 尚待產品決策

1. 右側 Goal 卡片主要 CTA 是「記錄新經歷」或「查看目前挑戰」？本規格**建議前者**，並移除同層重複大按鈕，待 Boyi 核准。
2. 已確認累計數值是否每項都顯示進度條？本規格建議桌面可有極細進度條、手機先以文字為主；避免造成「成果完成百分比」錯覺。
3. 「下次安排」是本輪必交還是可延後？本規格建議可用可信來源就顯示，未知時有誠實退路，不阻擋三習慣基本概覽。
4. 是否保留首頁既有「今日，可以做的一小步」區塊？建議保留操作入口、合併重複的三習慣摘要，不重複統計。

## 10. 參考路徑

- GitHub main: https://github.com/asixtw/life-world/tree/5f015a616f3497a4/app/static
- 正式程式：`app/static/app.js`、`app/static/goals.js`；API：`docs/API.md`
- 規則：`docs/team/BETA_FLOW_SPEC.md`、`docs/team/ART_DELIVERY_SPEC.md`
- 相關待核准交接：Goal Dashboard v0.1、Goal Detail v0.2、HabitScheduleDisclosure v0.3、Navigation UX v0.1
