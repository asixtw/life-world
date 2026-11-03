# Life World｜Goal Detail / Dashboard——UI 與美術元件交接規格

**文件 ID：LW-GOAL-DETAIL-ART-002｜版本：v0.2 審查草案｜日期：2026-11-03**  
**交接對象：**UI／UX、美術與元件製作（歐桑），由 Boyi 驗收、Jerry 審技術接入。  
**對應工程規格：**`01_Goal_Detail_產品工程規格_v0.2.md`。本文件**不授權重畫現有 Lumi、目標蛋、房間或更改正式 UI Kit 的全域 tokens**。

## 1. 版面原則

**先 Goal、後 Overview、再細節。** 應從「長篇目標內容清單」改為「一眼看懂的目標頁」。上方 Goal Header 不堆習慣詳情；下方 3 個 Habit 卡不能再合成一張無止境長卡。

1. **GD-HERO**：目標名稱為唯一 H1，狀態／目標成果／期間有次要層級。給使用者的主要 CTA 是記錄真實經歷；編輯安排為次要。
2. **GD-OVERVIEW**：最多三個摘要卡，分別表示「最近七天已採計經歷」「今日安排」「待核對貢獻」，缺資料以文字解釋。不可顯示未定義的總完成百分比。
3. **GD-TODAY**：一句話或短列表指出今天有安排的活動；全部空白時保留陪伴式文案，不作負面警告。
4. **GD-HABITS**：三張等寬卡，每張先名稱＋已確認量，接「已安排天數」與下一安排；底部次要 CTA「記錄此習慣」＋「查看排程」可展開。
5. **GD-WEEK**：近七天密集、可讀的七柱圖，非七個巨大 `<details>`；有紀錄的日期顯示明細入口，沒有資料的日期不顯示虛假可展開箭頭。
6. **GD-SCHEDULE／GD-RECORDS**：排程、來源佐證、待處理貢獻與回顧置於後段，採條件式區塊／分組摺疊，不額外增加主分頁。

## 2. Figma Frame／元件交付清單

| 組件 ID | 元件 | 必要 variants／狀態 | 美術或工程責任 |
|---|---|---|---|
| GD01 | `GoalHero` | active／awaiting_review／needs_setup／completed／ended；長標題與缺描述 | UI 排版；資料由工程 |
| GD02 | `GoalStatusBadge` | 五種生命週期，文字與色彩雙編碼 | 沿用既有 Badge／Status tokens |
| GD03 | `GoalOverviewMetric` | default／zero／loading／error／unavailable；緊湊與完整 | 既有卡片元件衍生 |
| GD04 | `TodayActionList` | scheduled／not-scheduled／unavailable；長標題 | 一般列表，不需新插畫 |
| GD05 | `HabitSummaryCard` | zero／partial／target-reached／unknown-target／read-only；三種不同單位 | 卡片＋進度條組合 |
| GD06 | `HabitProgressBar` | 正常／滿額／過量／無目標值／載入；不能單靠顏色 | 先使用現有 `<progress>` 語意 |
| GD07 | `HabitScheduleDisclosure` | collapsed／expanded／readonly／editing／conflict | 現有日期元件重用 |
| GD08 | `WeeklyActivityChart` | 0／少量／多筆／部分缺資料／載入／錯誤 | CSS／SVG；非一日一張圖片 |
| GD09 | `WeeklyDayDetail` | has-records／empty／loading／error | 只對有紀錄資料顯示明細入口 |
| GD10 | `PendingContributionSection` | empty／pending／unapplied／accepted／conflict | 重用既有人工核對區塊 |
| GD11 | `GoalActions` | record／edit-schedule／review／complete／end；disabled／loading／error | 既有 Button／Dialog 元件 |

### 2.1 不要重做的素材
- 現有 Lumi／目標蛋／房間／導覽 icon／Quiet／Reduced Motion 候選先做資產盤點。
- 上方 Hero **不需要新主視覺**；需要時只可低對比重用已核准裝飾，不要讓插畫擠掉 Goal 標題與 CTA。
- 七日趨勢、數字統計、進度條採元件繪製，不製作點陣圖。這些是由實際資料驅動的介面。

## 3. 響應式與排版建議（待 UI Kit tokens 核准）

| 場景 | 版面 |
|---|---|
| 手機 320–767px | 單欄；GoalHero 高度隨內容、CTA 可換行；三個指標必要時 2＋1 或縱向排列；習慣卡 1 欄；七日圖與日期可在 320px 內閱讀 |
| 平板／桌面 ≥768px | 內容主欄控制最大閱讀寬度；GoalHero 全寬；概覽最多三欄；Habits 可在寬度足夠時 3 欄；時間表及歷史細節不壓縮為窄欄 |
| 文字放大 200% | 不截斷目標全文，不遮蔽主要 CTA，按鈕維持可觸及與可讀 |
| Quiet／減少動效 | 只保留必要狀態切換；沒有連續閃爍、壓力紅色、完成炫光；進度變更可無動畫 |

**建議而非既定 tokens**：區塊間距 16–24px，卡片內距 16–24px，按鈕最小觸控目標約 44×44px；文字、色彩、陰影及圓角一律優先使用現有 UI Kit 的正式核准值，不額外創造另一套。

## 4. 視覺語意與文案樣例

```text
成為海賊王                    進行中
想達成的成果：超帥超厲害
2026/10/29 — 2028/01/01
[記錄經歷] [調整未來安排]

目前進展
[最近七天已採計經歷 --] [今日安排 --] [待核對 --]

三個重要習慣
┌─────────────────────────────┐
│ 每天健身                    │
│ 已確認投入 -- / 目標量 -- 次 │
│ 已安排 369 天               │
│ [記錄此習慣] [查看排程 ▾]  │
└─────────────────────────────┘
```

上例 `--` 代表工程需綁定實際資料，不得由美術 fixture 自行推論已完成數量。**「369 個已安排日」可用於排程資訊，不能變為進度 369/369。**

## 5. 必須交付的 UI 狀態

- 所有元件需提供：default、hover（可支援裝置）、focus-visible、pressed、disabled、loading、error；可展開元件另有 expanded／collapsed。
- Goal 在待回顧、已完成、曾經挑戰時，頁面主操作與文案要改變，不能一直顯示可繼續累計。
- `WeeklyActivityChart` 的 0 筆是平靜的中性色；非 0 的柱體必須有可讀的數字與日期；圖表下應有等價的日期與筆數表述。
- 長習慣名稱（至少約 35 字）、大用量數字（例如 369 日）、小數（例如 0.5 小時）、長單位、跨年日期都要設計。
- 媒體及數字不以顏色作為唯一資訊來源；鍵盤焦點清楚，屏幕閱讀器可得知標籤及數值。
- `0`、`尚無資料`、`載入中`、`資料讀取失敗` 必須是四種不同狀態；禁用假資料補 0。

## 6. 交付物與命名

- `GoalDetail_Mobile_390`、`GoalDetail_Desktop_1440`、`GoalDetail_Mobile_320`；各附 active／ended／empty／loading／error 截圖或 Frame。
- Figma 元件：`GoalHero`、`GoalOverviewMetric`、`HabitSummaryCard`、`WeeklyActivityChart` 等；每個附 props／variants 與互動註解。
- 若新增 icon／插畫，提供可追溯的 `assetId`、用途、授權範圍、尺寸、輸出格式、透明需求、替代文字、版本；不交付無來源說明的替代素材。
- 提供一張「沿用／修改／新增」對照表：對應既有 `collaboration/ui-kit` 元件與正式 `app/static` 使用點，避免重畫重工。
- 交付 390×844 與 1440×900 的實際瀏覽器畫面作為工程整合後的後續驗收；Figma 截圖**不算**正式 App 的互動測試。

## 7. 驗收關卡

| ID | 驗收 | 標準 |
|---|---|---|
| ART-01 | 信息層級 | Goal 最先、Overview 接著、三 Habit 再往下；標題與操作不被雜項取代 |
| ART-02 | 稀疏資料 | 0 筆近七天、無今天安排時不顯示負面意涵 |
| ART-03 | 真實數據壓力 | 369 已安排日與 0 已確認投入明顯可區分 |
| ART-04 | 觸控／鍵盤 | 320／390 手機不橫向溢出；focus-visible、可展開、Dialog 可操作 |
| ART-05 | 長內容與狀態 | 長標題、歷史、待回顧、載入、錯誤均有獨立畫面 |
| ART-06 | 既有視覺一致性 | 完整沿用核准 tokens；未重新建立色票／Lumi／房間系統 |
| ART-07 | 動畫與無障礙 | Quiet／Reduced Motion 不妨礙理解，讀屏有文字替代 |

**交付優先順序**：P0 先做 GD01–GD06 + 目標狀態／空白／錯誤；P1 再做 GD07–GD11 的呈現精修及七日趨勢。工程不得等待額外插畫才能完成 P0。

**本文件不是正式美術批准或 UI Kit 接入驗收。** 由 Boyi 核准後，Jerry 核對可接入性，實際 App 測試通過才標記為完成。
