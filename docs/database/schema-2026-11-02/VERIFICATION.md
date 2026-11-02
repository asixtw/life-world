# 本次驗證紀錄

> 下表是原交付包的歷史紀錄，不是發布者本輪實測。最新本輪結果見 [VERIFICATION_LOCAL](VERIFICATION_LOCAL.md)。

執行日：2026-11-02（Asia/Taipei）。全部使用取得的來源副本與記憶體 SQLite，未開啟真實 DB。

| 驗證 | 結果 |
|---|---|
| Git blob SHA-1 核對 baseline＋兩次 fix 來源 | 34 檔符合；另記 SHA-256 於 source_manifest／final_refresh |
| 001–005 空庫重播＋db.py 版本表 | 成功；31 表／201 欄／60 FK／50 索引（9 明確） |
| metadata 與歷史 schema_snapshot 比較 | 欄位、PK、FK、UNIQUE／索引一致 |
| CHECK 比較（忽略空白） | 一致 |
| 純 DDL 在另一空庫重建 | metadata 一致 |
| 虛構 001 舊資料升至 005 | legacy ID／unknown、故事未核對、期限 NULL、哨兵用量、roles、FK 六項斷言成立 |
| SQLite 直接 SQL 約束探針 | 5 類缺口確認，詳見下列說明 |
| PG 草案與資料字典 | 靜態欄位、表數與 FK 端點核對；不是 PG parser／執行測試 |
| FastAPI／Browser／SR | 本次未執行 |
| 真實資料升級／PG 匯入／併發／部署／還原 | 本次未執行 |

約束探針故意繞過 API：TEXT PK 允許兩筆 NULL；不同 owner 的 goal/action 仍通過 FK；JSON TEXT 可放非法 JSON；target_is_derived 可為 2；contributions 可放負文字數量／owner 不一致引用。這證明 DB 約束的邊界，不代表經過既有 API 的同樣輸入會被接受。

原交付包重現命令為 `python3 build_schema.py`；腳本及 evidence 來源副本僅在原 ZIP，未重複納入本儲存庫。此腳本含文件組裝，不是產品測試套件。來源 checksum 僅供交付追溯，不代表現有 migration runner 已實作 checksum。

環境 SQLite 3.35.5；沒有 psql、postgres 或 pglast，故未宣稱 PostgreSQL 語法與執行通過。分支驗收文件中的前次 77／最新 93 passed 為上游歷史紀錄，不是本次結果。
