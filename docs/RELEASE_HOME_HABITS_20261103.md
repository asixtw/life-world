# 目標總覽、唯讀月曆與首頁摘要｜發布審查

基準：GitHub main `5f015a616f3497a4fb948b143b09d8e625005f74`。本批移入目標 Dashboard／Goal Detail v0.2、HabitScheduleDisclosure v0.3、首頁三習慣摘要及對應測試、來源規格。不改資料表、部署設定、既有劇場與雲端安全設定；不搬入本機整套舊 main。

## 整合修正

保留 main 的 PostgreSQL owner 交易、runtime factory、業務啟用開關、TrustedHost／Origin／Secure Cookie。新增 Dashboard 的時間條件依 SQLite／PostgreSQL 方言選擇；待辦使用兩種資料庫皆合法的 `NOT done`。先新增 SQL 方言契約測試並確認有效失敗，再修正。

## 實際驗證

- 最新基準＋本批差異：pytest 253 通過、14 跳過。跳過均為要求專用 PostgreSQL 18 實例的既有案例；方言 stub 不冒充真 PostgreSQL 執行。
- Chromium 全套 172 通過（233.13 秒）；隔離 SQLite／Chromium，不連 GCP 或正式資料。
- 未修改／收錄受保護演進文件與本機私人內容。既有原工作區未提交成果原樣保留。

## 合併門檻與限制

真 PostgreSQL 18 回歸尚待執行，不能把 SQLite 通過當成 Cloud Run／Cloud SQL 驗收；合併前須確認此發布差異在專用 PG 環境的結果。手機 Safari／Android 與完整讀屏仍未實測。

本批可供團隊從發布分支檢視。不觸發手動部署，不更新其他人的電腦。程式回退不代表資料庫／資料回復；本批沒有新的資料遷移。
