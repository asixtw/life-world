# Step 10 4 App 資料庫權限審查

此矩陣是現有 FastAPI 服務需要的完整 DML 集合，待使用者審查。只在獨立本機 PG18.6 合成容器驗證，未對 GCP 執行。雲端目前只有30張業務表 SELECT，不能啟用業務流量。

## Runtime 與 Migration 身分

`lw_app` 只繼承 `lw_app_role`；`lw_migrator` 繼承 `lw_migration_role`，31表與2個 identity sequences 由 migration role 擁有。App 不應成為 owner、superuser、cloudsqlsuperuser，或繼承 migration role。

Database `life_world_dev` 需要 CONNECT，目前可連線已具此能力；如需明確授權，須由 database owner 審查，不能假設 schema owner 有 CONNECT 的 grant option。待審 DML 檔不轉授 CONNECT。schema `lw_core_draft` 需要 USAGE。App 不需要 CREATE、TRUNCATE、REFERENCES、TRIGGER、授權其他角色或 ALTER DEFAULT PRIVILEGES。

## Table DML 矩陣

所有表都在 `lw_core_draft`。表級 UPDATE 是目前所列17表的服務更新權限；如需再限制到欄位，必須另行核對所有實際 UPDATE，不以本矩陣推定。

| Table | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|
| `actions` | 允許 | 允許 | 允許 | 禁止 |
| `completions` | 允許 | 允許 | 禁止 | 禁止 |
| `contributions` | 允許 | 允許 | 禁止 | 禁止 |
| `draft_stories` | 允許 | 允許 | 允許 | 允許 |
| `drafts` | 允許 | 允許 | 允許 | 禁止 |
| `evidence` | 允許 | 允許 | 禁止 | 禁止 |
| `experience_mentions` | 允許 | 允許 | 允許 | 允許 |
| `experience_participants` | 允許 | 允許 | 禁止 | 允許 |
| `experience_stories` | 允許 | 允許 | 允許 | 禁止 |
| `experiences` | 允許 | 允許 | 禁止 | 禁止 |
| `fact_sources` | 允許 | 允許 | 允許 | 禁止 |
| `goal_reviews` | 允許 | 允許 | 禁止 | 禁止 |
| `goals` | 允許 | 允許 | 允許 | 禁止 |
| `habit_quantity_versions` | 允許 | 允許 | 允許 | 禁止 |
| `interaction_events` | 允許 | 允許 | 允許 | 允許 |
| `interaction_experiences` | 允許 | 允許 | 允許 | 禁止 |
| `interaction_people` | 允許 | 允許 | 禁止 | 允許 |
| `note_sources` | 允許 | 允許 | 禁止 | 禁止 |
| `notes` | 允許 | 允許 | 禁止 | 禁止 |
| `pending_contributions` | 允許 | 允許 | 允許 | 禁止 |
| `people` | 允許 | 允許 | 允許 | 禁止 |
| `person_connections` | 允許 | 允許 | 允許 | 禁止 |
| `person_facts` | 允許 | 允許 | 允許 | 禁止 |
| `person_goals` | 允許 | 允許 | 允許 | 禁止 |
| `requests` | 允許 | 允許 | 禁止 | 禁止 |
| `reward_ledger` | 允許 | 允許 | 禁止 | 禁止 |
| `schema_migrations` | 禁止 | 禁止 | 禁止 | 禁止 |
| `sessions` | 允許 | 允許 | 禁止 | 允許 |
| `story_history` | 允許 | 允許 | 禁止 | 禁止 |
| `tasks` | 允許 | 允許 | 允許 | 禁止 |
| `users` | 允許 | 允許 | 允許 | 禁止 |

INSERT 涵蓋新帳號／session、目標／行動、草稿／來源、經歷／人物關聯／帳本／回執；UPDATE 涵蓋人工版本變更；DELETE 只處理 session 撤銷、草稿故事替換、經歷角色重建及互動事件合併。沒有帳本、經歷、原文或目標整批刪除權限。

## Sequence 矩陣

| Sequence | USAGE | SELECT | UPDATE | 用法 |
|---|---|---|---|---|
| `goal_reviews_audit_seq_seq` | 禁止 | 禁止 | 禁止 | INSERT 省略 identity 欄位，由 PG 自動產值 |
| `story_history_audit_seq_seq` | 禁止 | 禁止 | 禁止 | INSERT 省略 identity 欄位，由 PG 自動產值 |

PG18 identity 自動產值不需要 App 直接呼叫 nextval 的權限。已用 lw_app 實際插入兩表並取得 audit_seq，同時確認 nextval 被拒絕；不套用 serial 常見的 blanket GRANT USAGE。序號有 rollback gap 屬正常，僅作寫入順序，不作業務 ID。

## 待審 SQL 與驗收

待審檔：[app_dml_grants.review.sql](../../deploy/postgres/app_dml_grants.review.sql)。只對指定31表、2個 sequence 與指定角色操作，不授予未來新表的預設權限。檔案被本機合成 bootstrap 呼叫，API startup 與 Cloud SQL runtime 都不會執行它。雲端 schema 已建立，不能重跑 CORE DRAFT 來授權。

使用者先在 Console 核對物件 owner、schema、role memberships 與 PUBLIC／既有 grants；本 SQL 不會消除所有可能的繼承權限。審查通過後，由 migration 身分手動套用待審 DML，核對30表 SELECT／INSERT、17表 UPDATE、6表 DELETE，schema_migrations 仍禁止、CREATE/TRUNCATE 仍禁止、2個 sequences 的三項權限仍全部禁止。

接著以 lw_app 合成資料測試並 ROLLBACK，確認單次經歷／積分／回執交易成功及兩個 identity 的自動產值，才可進入 Cloud Run 測試 revision 的業務驗收。不要使用真實資料；試用 Cloud SQL 的一般備份／還原未就緒。
