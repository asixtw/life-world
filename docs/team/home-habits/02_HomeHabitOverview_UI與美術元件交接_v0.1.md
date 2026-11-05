# Life World｜HomeHabitOverview UI／美術元件交接規格

**文件 ID**：LW-HOME-HABIT-ART-001　**版本**：v0.1 審查草案　**日期**：2026-11-03<br>
**收件人**：歐桑（UI／美術與 React 候選元件）；Boyi 負責產品視覺驗收；Jerry 負責正式 App 接入。

## 0. 適用範圍與既有資產

本規格只擴充**世界首頁右側目前目標區**，不得重畫左側 Lumi 房間／目標蛋，不新增第五個分頁，也不得把 Goal Detail 詳情的月曆、七日圖搬到首頁。沿用 `docs/team/ART_DELIVERY_SPEC.md`、現有 `collaboration/ui-kit/` 的卡片、Button、Typography、Icon、Focus、Quiet／Reduced Motion 與正式核准 tokens。未經核准不重建配色；已有房間、Lumi、蛋殼候選圖資需依 `assetId` 查重及來源。

**設計主張**：左側是陪伴感；右側是可在短時間理解的「目標＋三個習慣＋下一步」。習慣資訊以精簡列呈現，不使用三張大型裝飾卡。

## 1. 版型與資訊順序

| 順位 | UI ID | 標題／內容 | 視覺權重 |
|---|---|---|---|
| 1 | HH-HERO | 目前目標名稱、生命週期、可選一句陪伴文案 | 第一級，目標標題唯一主焦點 |
| 2 | HH-GROUP | 區塊標題「我的三個習慣」＋三列 | 第二級，資訊核心 |
| 3 | HH-ROW×3 | 習慣名稱／已確認 `progress / target + unit`／下次安排（可用時） | 中性、可點選，不重複三個大 CTA |
| 4 | HH-CTA | 主要「記錄新經歷」、次要「查看目前挑戰」 | 只有一個最高優先動作 |
| 5 | HH-SECONDARY | 繼續草稿（條件顯示）、人物劇場（保留入口） | 文字連結／弱化樣式 |

注意：封測不顯示積分、養分、商店、排名、登入連續天數、負面警告。Lumi 不因零投入變得失望。

## 2. 共用元件清單與輸入介面

| 元件 ID | 元件名 | 依賴／輸入 | 交付 variants | 備註 |
|---|---|---|---|---|
| HH-C01 | `HomeGoalPanel` | `goalTitle`, `goalStatus`, `children` | active、awaiting-review、needs-setup、empty、error | 優先修改既有 Goal Card |
| HH-C02 | `HomeHabitOverview` | 3 items、dataStatus | ready、loading、incomplete、error | 只負責排列，資料由工程提供 |
| HH-C03 | `HomeHabitRow` | `title`, `progressLabel`, `scheduleLabel`, `actionId` | zero、partial、over-target、unknown、no-schedule、readonly | 可點擊但不可讓整個區域有多個巢狀 button |
| HH-C04 | `HomeHabitProgress` | `value`, `max`, `unit`, `unknown` | default、over-target、unknown | 現有 Progress 重用；文字永遠可讀 |
| HH-C05 | `HomeHabitScheduleHint` | 文案 | today、tomorrow、date、none、unavailable | 無新圖示必要；日期文字應可讀 |
| HH-C06 | `HomeHabitActionGroup` | primary、secondary、draft | enabled、loading、disabled、error | 原有 Button／Link 元件 |
| HH-C07 | `HomeHabitState` | state、message、retry | loading、no-goal、incomplete、offline、error | 重用通用 Empty/Error/Skeleton |

**Component contract**（展示層；非正式 API）：

```ts
interface HomeHabitRowProps {
  actionId: string;
  title: string;
  progressLabel: string; // e.g. 「已確認 0.5 / 10 小時」
  scheduleLabel: string; // e.g. 「下次安排 11/05」；未知要明說
  isReadonly?: boolean;
  onOpenDetail: (actionId: string) => void;
}
```

Figma 與 React Gallery fixture 可用虛構數字，但畫面上標註 `DEMO`，不可把它推進正式資料。正式 App 的點擊事件由宿主處理；美術端不寫業務邏輯、API、權限或記帳。

## 3. 尺寸、版型與無障礙

| 情境 | 要求 |
|---|---|
| 390×844 手機 | 單欄；三列垂直排；數值與次資訊能換行；保留按鈕觸控高度；不橫向捲動 |
| 320px 極窄手機 | 三列逐項向下伸展，長習慣名稱可多行；不裁切唯一標識 |
| 1440×900 桌面 | 左房間右 Goal 卡雙欄；右卡留白適當，三列不讓右區高度顯著高於左房間 |
| 200% 字級 | 三列可增高，數值不疊字，按鈕可換行 |
| 鍵盤 | `Tab` 可抵每列，Enter/Space 依真實語意操作；Focus ring 可見且不被容器裁切 |
| 螢幕閱讀器 | 一個區塊 heading，三筆有清楚名稱／進度文字／可觸發名稱；不要只有圖示或色彩 |
| Quiet／Reduce Motion | 保留狀態及對比；取消非必要滑動或光效，不以動畫告知進度 |

**尺寸建議（待核准 tokens 覆蓋）**：三列間隔 8–12 px、列內距 12–16 px、觸控區至少 44×44 CSS px；避免每列再加一張大型卡。日期以文案為主，若用 icon，需能在 16／20／24 px 網格中一致呈現。

## 4. 視覺語意及異常狀態

| 狀態 | 畫面文案樣例 | 呈現規則 |
|---|---|---|
| zero | 已確認 0 / 10 次 | 中性，不用紅色、不顯示扣分 |
| partial | 已確認 3 / 10 次 | 可選細進度條，但絕不標成成果完成 |
| over-target | 已確認 12 / 10 次 | 文字完整保留 12；bar 顯示滿格即可 |
| no-schedule | 目前沒有後續安排 | 中性，可查看詳情 |
| unknown-schedule | 下次安排暫無法顯示 | 不冒充無安排 |
| awaiting-review | 這次挑戰待回顧 | 把主要 CTA 改為「查看並回顧」 |
| needs-setup | 需要先補齊目標設定 | 提供詳情入口，進度未知則用 — |
| no-open-goal | 目前沒有進行中的挑戰 | 建立新目標／查看過往旅程，不顯示舊三習慣 |
| load-fail | 習慣暫時無法載入 | 顯示重試，不使 Lumi 區塊跟著全頁消失 |

## 5. 美術交付與避免重工

- **不需要新 2D 建模、新寵物姿態、新背景或動畫**；這次是 UI 元件與資訊層級改版。
- 先提交「沿用／修改／新增」盤點：沿用 Goal Card、Button、Progress、Icon、Empty／Error、Focus tokens；修改右側卡排版與 `HomeHabitRow`；新增者以最小範圍為原則。
- 若新增任何 SVG／PNG：提供 `assetId`、原稿路徑、版本、尺寸、透明規則、用途、許可範圍、alt；不要把動態數值或文字烘焙到圖片。
- Figma Frames：`Home_Habits_390_Default`、`Home_Habits_320_LongText`、`Home_Habits_1440_Default`、`Home_Habits_390_Zero`、`Home_Habits_390_Review`、`Home_Habits_390_LoadingError`；提供日間／Quiet／減少動效參考。
- UI Kit Gallery 交付 `HomeHabitOverview` fixture 與 Variants、typed props、事件回呼說明。Gallery 必須明示不寫入正式 App。
- 最終整合後由 Jerry 提供可運行 App 截圖，Boyi 審核，不以 Figma、靜態 Gallery 或生成圖取代真實操作驗收。

## 6. 完成標準（美術驗收）

| 驗收 ID | 標準 |
|---|---|
| HHA-01 | 舊 Lumi／房間畫面未被重做或擠小成角落 |
| HHA-02 | 右側有且只有三個主要習慣列，標題與數值可讀 |
| HHA-03 | 369 安排日不可顯示成 369 次完成；數字來源以工程為準 |
| HHA-04 | 無資料、零投入、待回顧、載入錯誤均有獨立 variants |
| HHA-05 | 320px、390px、1440px、200% 字級、鍵盤焦點、Quiet、Reduced Motion 有交付證據 |
| HHA-06 | 新畫面與既有世界／目標／紀錄／關係視覺一致，無新全域色票與重複套件 |
| HHA-07 | CTA 有唯一主次：記錄新經歷／查看目前挑戰，不把三習慣各做大型主要按鈕 |

## 7. 與其他規格的關係

- 本文件專管 `世界` 首頁三習慣；不取代 Goal Dashboard v0.1、Goal Detail v0.2、HabitScheduleDisclosure v0.3。
- `HabitScheduleDisclosure` 的完整日曆與「日期／用量」單日明細**只存在 Goal Detail**；首頁不重複實作。
- 導覽返回、未保存內容及焦點規則繼續依 `Navigation Contract v0.1`。
- 若本規格與正式核准的 `BETA_FLOW_SPEC v1.1` 或最新 `ART_DELIVERY_SPEC` 衝突，先回報 Boyi，不能以較新的草案私自覆蓋核准規格。
