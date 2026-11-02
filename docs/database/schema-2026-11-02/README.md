# Life World Table Schema 交付包

> 本儲存庫整理版：既有 SQLite 結構已於本輪獨立重播核對；PostgreSQL 與劇場新表僅作草案文件合併，沒有套用資料庫。先讀 [本輪驗證與限制](VERIFICATION_LOCAL.md)。原交付包的來源副本、組裝腳本與工作材料不重複入庫，程式來源改以固定 Git commit 追溯。

先閱讀 [完整繁體中文架構文件](LIFE_WORLD_TABLE_SCHEMA_ZH_TW.md)。

| 檔案 | 用途與狀態 |
|---|---|
| LIFE_WORLD_TABLE_SCHEMA_ZH_TW.md | 主文件，包含 31 張既有表／9 張劇場擬議表全欄位字典、關聯、來源、風險與待決 |
| SQLITE_FACT_SCHEMA.sql | 001–005 空庫重播的 SQLite 純結構；非業務備份、非新 migration |
| EXISTING_SQLITE_ERD.mmd | 既有全部 60 條 FK 的 Mermaid 圖；主文件另有易讀分圖 |
| POSTGRESQL_CORE_DRAFT.sql | 全 31 表 PG 候選映射，另有 PK／audit_seq／單目標強化；未在 PG 執行 |
| POSTGRESQL_THEATER_PROPOSAL.sql | 9 張正式劇場持久化候選表；未核准、未落地 |
| VERIFICATION.md | 本次實際執行、結果與未執行範圍 |
| SOURCE_MANIFEST.json | 原 ZIP 指紋、文件指紋與固定來源版本；不含 DB 資料 |
| EXISTING_SQLITE_DICTIONARY.md／THEATER_PROPOSED_DICTIONARY.md | 主文件的分拆資料字典 |
| VERIFICATION_LOCAL.md／verification_local.json | 本輪重新驗證結果及尚未執行事項；原包的組裝材料不重複上傳 |

查核截止 2026-11-02 16:08（台北）。SQLite 基準 6676b61243d8b86a76637e8c154878d6fcd9701a；最新相關原型修復 9ba530999feb9241f5d7f71a9fa6dfa7c36a2a33。

本包未修改、推送或合併 asixtw/life-world，未接觸使用者實際 DB。所有 PG 與劇場新表均為明確區隔的建議。
