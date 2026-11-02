# 2026-11-02｜原型、劇場修正與 Table Schema 審查入口

此為開發審查基準，不是部署完成或封測就緒聲明。正式 App、獨立原型與候選 Schema 分開驗收；沒有連接外部 AI、正式 PostgreSQL 或雲端素材服務。

## 這一批包含什麼

- 接續 `review/current-state-2026-11-01`（6676b61）與 `fix/theater-session-isolation`（f1d09d2）的公開工程成果，保留作者提交及歷史。
- [全流程原型](../collaboration/flow-wireframe/README.md)：目標／三習慣、月週排程、經歷、人物、交會、劇場及夜間；修正重試對象、跨場暫態、無效人物及欄位提示。
- [劇場可靠性規格](team/theater/SESSION_RELIABILITY_SPEC.md)、[本機整合紀錄](team/theater/PROTOTYPE_INTEGRATION_2026-11-02.md)、[表單提示](team/theater/VALIDATION_FEEDBACK_2026-11-02.md)。其中「當時未提交／未推送」為歷史狀態，不用來判斷這一批之後的 GitHub 發布結果。
- [Table Schema 交接](database/schema-2026-11-02/README.md)：SQLite 對照固定 6676b61 的 001–005；PG 核心／劇場九表只作草案，不是新增執行遷移。來源副本與作者工作材料不重複上傳。

## 本輪實測

整合測試樹以 f1d09d2 加上本輪修正：後端 `python -m pytest -q --tb=short` **176 passed，9.60 秒**；完整 `browser_tests` **145 passed，211.24 秒**，均無失敗或跳過。瀏覽器使用隔離測試 DB 與 Chromium；截圖輸出導向暫存目錄，測試斷言不變。

SQLite 兩個記憶體空庫的 migration／純 DDL metadata 一致：31 表、201 欄、60 FK、50 索引，integrity_check 正常、FK 無異常。PG 以 pglast 7.22 解析成功：核心 104 statements／31 表、劇場 21 statements／9 表；未在 PG 實例執行。

## 明確未完成與合併界線

- 目標期間外採計：正式 App 的 `GoalService._save_goal_contributions()` 尚未依 occurred_at 做完整起訖限制，Schema 文件亦已指出。這是程式靜態確認的業務缺口，不因以上測試全通過而消失；應修正後再將相關正式 App 更新作無缺口交付。
- 真實 AI／ASR／圖片辨識、PG 遷移、權限／來源撤回留存與備份還原、實機 Safari／鍵盤仍未完整驗收。
- 純原型可獨立使用，不會更新正式資料。公開 Schema 不含資料列、憑證、真實人物素材或 DB 檔；不能把草案 DDL 放進 migrations 自動套用。
- 受保護的本機 EVOLUTION 新版仍不在本批，不公開私人覆寫、工具 session 或本機備份。
- 保留歷史分支，不刪除或重寫。main 的合併範圍依 Boyi 本輪決定；不把分支上傳視為同仁本機同步或部署。

回退程式不會自動還原 DB 或降版 localStorage；任何部署前都需有備份及相容性回復方案。本輪沒有操作實際使用者 DB。
