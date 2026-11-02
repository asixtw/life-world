# 發布前獨立驗證｜2026-11-02

結論：可合併為「SQLite 現況文件＋PG／劇場設計草案」，不得當作正式 PG migration 或完整安全驗證。原 ZIP 沒有實際 DB，這輪沒有開啟、修改或上傳使用者資料庫。

1. 從目前待發布程式獨立重播 001–005；逐檔與原包來源位元組一致。
2. 在另一記憶體 SQLite 執行 SQLITE_FACT_SCHEMA.sql，逐表比對欄位、PK、FK、索引：31 表、201 欄、60 FK、50 索引，均一致；與原包 metadata 欄位及 FK 亦一致。
3. 兩個空庫 integrity_check 均為 ok，foreign_key_check 無異常。不代表真實資料升級／備份還原已測。
4. PG 草案只建立獨立 draft schemas，未發現 DROP／TRUNCATE／業務資料 DML。另以暫存安裝的 pglast 7.22 實際解析：核心 104 個 SQL statement／31 表、劇場 21 個 statement／9 表，語法解析成功。這不是 PostgreSQL 實例執行；constraint 語意、RLS、併發或匯入仍未驗。Jerry 正式採用前仍需 PostgreSQL 實例、舊資料 preflight 與回復演練。App 依賴未新增此 parser。
5. 原文件列出的 SQLite 限制確實需要保留：TEXT PK 空值、owner 跨實體一致性、JSON 合法性、布林及數量限制，不全由 DB CHECK 保證；應區分現有 API 驗證與未來 DB 強化。
6. 劇場九表是候選資料模型，來源撤回、私人內容留存、費用及正式交易仍待審。合併文件不授權建立這九表。

發布整理：不重複上傳原包的 evidence 程式副本、作者工作材料及組裝腳本；來源以固定 Git SHA 與 SOURCE_MANIFEST.json 追溯。更正純 DDL 中 evidence.content 的中文註解為圖片位元組，不更動結構。原包的 VERIFICATION.md 保留為歷史紀錄。

正式 App 的既有遷移是儲存庫原有工程變更；本文件不新增或套用遷移。部署新版 App 前仍須備份，程式回退不能自動撤銷已執行的資料遷移。開發 main 合併不等於封測／正式上線驗收。
