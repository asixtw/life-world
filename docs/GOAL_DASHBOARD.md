# Goal Detail／Dashboard｜實作契約與驗收

> **v0.2 更新（2026-11-03）：**完整 Dashboard 移至 `#goal/{id}`，`#goals` 保留目標卡與旅程列表；下文v0.1實測保留為歷史，最新變更與驗收見末節。

日期：2026-11-03。依 LW-GOAL-DASH-001 與 Boyi 本輪確認：正式 App 及全流程 Prototype 一起補齊，包含七日已採計經歷；不處理美術、不更換技術、不修改貢獻或獎勵交易、不新增資料表。本輪未 Commit、Push、Merge 或部署。

## 操作與指標

「目標」分頁依序為目前挑戰、三個習慣投入、今日安排、待核對與後續任務、最近七天、目標旅程。詳情、排程調整、回顧、延長與成果確認沿用既有入口。

- 精確數量與總量來自既有後端 Decimal 計算，長條最高顯示100%，文字保留超量。不提供總成果百分比。
- 今日依目標固定時區及伺服器日期，安排量使用當天用量版本。已有確認投入不等於當日達標。
- 七日含今天及前六日，僅計 contributions 中正式採計的經歷；同經歷跨習慣去重，以 occurred_at 在目標時區歸日。補記或之後採計均歸回發生日，不歸確認日。來源展開含摘要、原文與原始發生時間。
- 未確認草稿、待採計、未採計、私人模擬不進趨勢；查詢成功的空日為0，查詢失敗不冒充0。
- 任務經其來源經歷歸屬目標，只列未完成者；勾選沿用既有PATCH，不產生額外投入。草稿只算該目標未確認伺服器草稿，不聲稱含本機素材或跨裝置同步。
- Dashboard 不顯示獎勵；其他頁既有開發積分與帳本未改。

## API 與資料映射

`GET /api/goals/{goal_id}/dashboard`：需要 session；只讀本人目標，其他owner或不存在目標404，無效身分401。沿用 Database.connect 的唯讀交易，所有欄位在同一快照讀取，不另建統計表。

| 欄位 | 來源／語意 |
|---|---|
| goal | id、title、outcome、status、start_date、deadline、revision，沿用既有目標計算 |
| goalId、today、timezone、updatedAt | 目標ID、固定時區的今天、固定時區（舊資料回退帳號時區）、伺服器讀取時間，非最後編輯時間 |
| habits | actionId、title、unit、progress、target、plannedToday、plannedQuantityToday、confirmedToday；數量為字串，未安排的當日量為null |
| openTasks | 此目標經歷所產生的未完成既有任務；不虛構到期日 |
| drafts、unconfirmedDraftCount | 未確認伺服器草稿的id、raw_text、updated_at及數量 |
| pendingContributions | 僅status=pending的既有來源資料；不將accepted/unapplied算作待核對 |
| trend | status=available；days固定七日，包含date、confirmedExperienceCount及去重experiences（id、summary、raw_text、occurred_at） |

`mapGoalToDashboardVM()` 統一前端映射；世界的今日摘要與Dashboard共用此資料。舊目標期間未知時不猜測今日安排，仍可補設定。無目前目標保留建立及歷史入口；舊多目標分別讀取，不擅自結束。

快照只保存在記憶體，切帳號／登出清除。舊頁回應不寫快照；401/403不回退私人快照。離線可顯示同帳號前次內容並標記可能非最新；重新整理後無記憶體快照則顯示失敗與重試，不宣稱已離線同步。主要導覽沿用既有載入提示及aria-busy。

## 原型界線

[全流程 Prototype](../collaboration/flow-wireframe/index.html) 使用本機虛構資料，顯示相同資訊及七日去重口徑，不連真實API。原型日期來自示範時鐘；正式App日期來自伺服器，兩者不混用。正式App的權限／交易證據不能由原型代替。

## 驗證紀錄

- 先新增pytest測試，端點缺失形成4項有效紅燈。另修正測試使用舊目標revision的前置錯誤，再確認404紅燈；未放寬產品標準。
- API案例覆蓋零資料、Decimal與超量、多習慣去重、待採計後回填、固定時區跨日、七日邊界、用量版本、歷史／完成／舊資料、目標與owner隔離、失效session及唯讀不改帳本。
- Chromium案例覆蓋390×844與1440×900、原文來源、任務完成、記錄上下文、重載、網路錯誤與重試、舊回應隔離、session失效及原型資料口徑。
- 實測命令與結果見下表；未驗證項目明列，不以歷史結果代替。

## 本輪最終實測（2026-11-03）

| 環境 | 命令 | 結果 |
|---|---|---|
| 最新main來源的隔離副本 | `.venv/bin/python -m pytest -q` | 192 passed，0 failed／0 skipped，10.34秒 |
| 同上，隔離測試服務與時鐘 | `.venv/bin/python -m pytest browser_tests -q --tb=short`（截圖僅轉存測試目錄，斷言不變） | 150 passed，0 failed／0 skipped，217.47秒 |
| VS Code既有工作樹＋本輪增量 | `.venv/bin/python -m pytest -q` | 183 passed，0 failed／0 skipped，11.95秒 |
| 同上，隔離虛構資料服務 | `LIFEWORLD_TEST_URL=http://127.0.0.1:18766 .venv/bin/python -m pytest browser_tests/test_dashboard.py -q --tb=short` | 4 passed，0 failed／0 skipped，3.63秒 |

兩個工作樹的既有測試基準不同，因此不混用數量。本輪只將Dashboard增量套回VS Code，沒有覆蓋其餘未提交工作；未同步整份main，也未修改本機私人演進文件。

補充的過期身分案例發現 `/auth/me` 的401可能殘留舊畫面，已清除快照並回到登入入口。測試先以API準備帳號後明確重新載入頁面；七日邊界案例延長隔離測試session以避免訪客到期遮蔽統計，不變更正式session期限。未刪除或放寬原斷言。

[390×844來源展開](artifacts/dashboard/dashboard-sources-390.png)／[1440×900來源展開](artifacts/dashboard/dashboard-sources-1440.png)。均為虛構資料；已檢視手機、桌面版面。鍵盤Enter展開及減少動效已實測；實機Safari、完整螢幕閱讀器與5秒辨識使用者測試尚未執行。

沒有schema遷移、帳本重算、外部AI、Commit、Push、Merge或部署。既有Python服務需重新啟動才會載入新端點，前端需重新整理。

## Goal Detail v0.2 本輪更新

Boyi 提供[產品工程規格](team/goal-detail/PRODUCT_SPEC_v0.2.md)及[UI元件交接參考](team/goal-detail/UI_COMPONENT_SPEC_v0.2.md)，本輪採用頁面資訊階層；原件的草案標記原樣保留，不宣稱已完成Figma、美術或UI Kit接入。

- 列表保留目標卡；完整詳情以目標名稱為唯一H1，先成果、狀態、期間與操作，再目前進展、今日安排、三個習慣卡、七日圖及排程／回顧。
- 三摘要為七日已採計經歷、今日已安排習慣及本目標待核對貢獻；不做跨目標加總，也不新增截止倒數。
- 習慣各自呈現已確認量、目標量、已安排天數、下一安排與收合日期／用量版本；369天安排不視為完成369次。未知舊排程顯示暫無統計。
- 既有dashboard API增量提供 `scheduledDayCount`、`nextScheduledDate`、`scheduleDates`、`quantityVersions`；不改表、不改交易。七日統計沿用已核准的發生日去重規則。
- 七日改為緊湊SVG柱圖及等價文字，僅有來源的日期有明細入口；0筆沒有空白展開箭頭。SVG數值屬資料，沒有放寬CSP或引入inline style。
- 目標本身讀取成功、聚合失敗時仍保留Goal與習慣，未知統計標示暫無統計並提供重試；不把缺值補0。
- 回顧、延長、結束、成果佐證與逐筆採計置後，保留既有權限與版本；不碰人物／劇場／獎勵。Prototype同步結構，仍只處理虛構資料。

本輪有效紅燈：新增欄位缺失造成1 failed／7 passed；補齊後8 passed。`pytest -q` 完整後端184 passed（9.98秒）。第一次完整瀏覽器回歸為134 passed／1 failed，定位為320px且文字放大200%的摘要連結不換行；修正後7項詳情案例通過（5.91秒），最終完整瀏覽器回歸 **135 passed，0 failed／0 skipped（194.53秒）**；使用隔離虛構資料服務、明確測試時鐘與截圖轉存工具，沒有覆寫既有驗收圖片。v0.1的183／192／150數量為歷史，不冒充本輪結果。

已驗：320／390／1440寬度、369日安排與0投入區分、文字200%不橫向溢出、三張習慣卡、零筆不提供空展開、鍵盤明細、錯誤重試、日期與用量。JavaScript語法檢查與Markdown相對連結通過。實機Safari、完整螢幕閱讀器及5秒辨識使用者測試尚未驗證。

[320px畫面](artifacts/goal-detail-v02/goal-detail-v02-320.png)／[390px畫面](artifacts/goal-detail-v02/goal-detail-v02-390.png)／[1440px畫面](artifacts/goal-detail-v02/goal-detail-v02-1440.png)。均為隔離虛構資料，已檢視資訊層級及排版。

## HabitScheduleDisclosure v0.3

日期與用量長清單已改成單月唯讀視圖；原始v0.2截圖與測試保留為歷史。見[本輪月曆契約與驗收](HABIT_SCHEDULE_ACCEPTANCE.md)，每日實際投入尚未提供，不顯示假0。
