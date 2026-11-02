# Jerry｜Table Schema 接續與 PostgreSQL 規劃

日期：2026-10-29。**現況已查核；下列 PostgreSQL 型別、強化與新表是審查提案，不是已建立的 schema 或已發布 migration。** 本輪只補文件，沒有修改 SQLite、連線設定、產品程式或 GCP。

## 1. 先取得一致來源

1. 先讀[完整資料字典](../DATABASE_SCHEMA.md)，再核對[機器快照](schema_snapshot.json)中的 migration 指紋，配合 `app/migrations/001–005`、`app/service.py`、`app/goals.py`、`app/people.py`、`app/connections.py` 及 [API](../API.md)閱讀。
2. 此刻的 Git HEAD `585e0a3` 尚未包含工作樹的 005 習慣版本與本輪 schema 文件；目前也沒有 PostgreSQL DDL／Alembic 等正式遷移工具。Boyi 另行核准發布後，才能以新共同 commit 開工，不拿舊 GitHub HEAD 當本機資料庫版本。
3. 本機已核對 8000 程序使用預設 SQLite 路徑；這不保證舊程序已重新載入目前工作樹程式。接手須分別核對程式版本、schema_migrations 與連線目標，不透過重啟「猜測更新成功」。
4. 目前所有正式資料由同一 SQLite 服務管理。完整流程 wireframe、未提交的目標建立草稿、歐桑示範人物素材，都不能當成正式資料表已存在或真實訓練資料已入庫。

### 歷史提案的差異

另外找到舊交接的資料模型／API 提案及人物研究的 `proposed_schema.sql`，均明示非正式 migration。舊提案的可選 deadline、固定 28 天預覽與 `/v1` 路由不能蓋過目前必選期限、真實日期及 `/api` 契約。研究 SQL 的 `lw_persons`／`lw_experiences`／UUID owner 亦未接入目前 users／people，不能直接執行後就稱已整合；其 observation／claim／profile／simulation 表只供後續研究比對，不取代目前人工 person_facts 與來源規則。

## 2. 優先保留的資料規則

| 必須保留 | 接手時的落點 |
|---|---|
| owner／ID／來源不變 | 保留字串 ID，包括 `legacy:` 事件；禁止按姓名重建人物或重編來源 |
| 一個未結束目標、三習慣 | 到期待回顧／待補設定仍占名額；先處理舊多目標，不自動關閉 |
| 進度與獎勵分離 | 已確認經歷一次發獎；延後採計、配對、改星標、私人劇場不再發分 |
| 排程與完成分離 | 日期只是預計；用量按生效日，固定目標時區，今天／歷史不回算 |
| 參與／直接互動／提及分離 | 逐經歷名單與聚合事件各自保留；共現不是私人關係 |
| 真實與私人／模擬分離 | notes／示範人物不寫正式人物事實、貢獻或帳本 |
| 同交易與重送去重 | 經歷／貢獻／任務／人物／獎勵／requests 原子保存；不以工作佇列分拆正式確認交易 |
| 歷史與未知保留 | NULL 舊期限、原始角色備註、unapplied、衝突／撤回及用量快照不因遷移補造或刪除 |

## 3. SQLite → PostgreSQL 審查方案

### 3.1 型別與來源

以下是保留語意的建議，Jerry 應產出實際 PG DDL 與契約差異，經審查後實作，不直接把 SQLite 檔搬到雲端服務當正式 DB。

| 現有欄位 | PG 建議 | 注意 |
|---|---|---|
| id、各外鍵、token_hash | 第一輪保留 TEXT | 不是每個 ID 都是 UUID；token_hash 不是 UUID。沒有必要先重編所有 ID |
| created_at／occurred_at／updated_at／expires_at／完成及撤回時間 | TIMESTAMPTZ | 先驗證時區格式；原時區名稱仍獨立保存，不能只保留一個 UTC offset |
| start_date／deadline／effective_from | DATE | 0001-01-01 是舊原始用量標記，不是挑戰真實起日；不得自動補舊期限 |
| quantity／accepted_quantity／per_occurrence／target | NUMERIC，API 仍回十進位字串 | 不用 FLOAT。每次輸入最多六位小數與 10^12 上限；衍生總量可能更大，勿一律選 `NUMERIC(18,6)` 或套同一上限。實際精度／上限經資料盤點及產品規則核對 |
| done／followed／reviewed／available／interacted／target_is_derived | BOOLEAN | SQLite 目前只有部分欄位有 0／1 CHECK；先檢查舊值，不默默把任意數字轉 true |
| roles／tags／weekdays／schedule_dates、payload、快照、回執 | 第一輪以 JSONB 候選保留結構 | 原始 raw_text 不改為 JSONB。為既有序列化、fingerprint 及歷史回執做相容測試；不能假設重新序列化仍有相同指紋 |
| evidence.content BLOB | 第一階段可映為 BYTEA；私人媒體另階段移到物件儲存 | 移轉須逐筆核對 digest、owner、存取權限、引用與舊備份；未確認前不刪 BLOB。不把資料庫或 API 設為公開圖片直連 |
| 狀態 enum 字串 | 先保留 TEXT＋明確 CHECK | 保持原語意與舊值；公開目標狀態仍是服務推導，不把五種字串直接塞回原 status |

型別能力以 [PostgreSQL 官方資料型別](https://www.postgresql.org/docs/current/datatype.html)為參照；本輪核對的 current 文件為 18，**不表示 GCP 已選定 PG 18**。實際版本、區域與可用服務由 Jerry 核對。

### 3.2 約束、交易及查詢

- **單一目標併發**：不能把 SQLite `BEGIN IMMEDIATE` 換成一般 PG transaction 就認為等效。候選方案是鎖定該 users 列，並在完成舊資料整理後增加 owner 的部分唯一索引，條件為實體 `status='active' AND ended_at IS NULL`；不可用「截止日還沒過」決定唯一名額，否則待回顧會意外解鎖。
- **三習慣／owner 一致**：三個 actions 及其所有權由同交易驗證；跨表筆數不能當成已存在的一般 CHECK。FK 目前只核對 ID 存在，不核對 owner 相同；可評估複合 FK／額外約束，但保留服務權限檢查，先驗證舊資料再增加限制。
- **去重／版本競爭**：保留 requests 複合 PK、experiences.draft_id 與 reward_ledger.experience_id 唯一鍵、expected_revision。PG unique violation／serialization failure 需定義回滾與重讀回執策略，不盲目重試後重發獎。
- **空值與刪除**：目前所有實體 FK 為 NO ACTION；不擅自改成 cascade delete。SQLite TEXT PK 未一律宣告 NOT NULL，PG PK 會更嚴格；先做資料 preflight，非法值人工處理，不填假 ID。
- **索引與分頁**：現有 9 個明確索引只是最低基準。人物搜尋與綜合排序部分在 Python 端執行，不能因 API 有 limit 就宣稱 DB 已分頁。先量測，再設計 owner＋時間、人物／目標關聯及故事焦點查詢索引；不未量測就替所有 JSONB 建 GIN。
- **隱含 rowid**：story_history／goal_reviews 等排序使用 SQLite rowid 作同時刻次序。PG 沒有相同依賴，須增加穩定的寫入順序鍵或明確次序方案，測試固定時鐘的連續修改，不用隨機 UUID 當時間順序。
- **SQL 方言**：`?` 參數、`INSERT OR IGNORE`、ON CONFLICT、布林判斷、PRAGMA、字串日期與 JSON 取值須逐項適配；API 及前端不因遷移自行換格式。migration runner 目前直接執行 SQLite SQL 並只記檔名，不是通用遷移框架。

約束與隔離設計參照 [PG Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)、[Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html)。以上為建議，尚未在 PG 執行或驗證。

## 4. 頁面缺口所需的候選新表

**以下全都尚未存在，名稱及欄位為設計草案。** 先完成既有核心遷移，再依工作包導入；不把全部候選一次建好，也不把 UI 假操作當成後端需求已核准。

| 需求／候選表 | 最小責任及候選欄位 | 關聯／確認邊界 |
|---|---|---|
| 私人媒體 `media_objects` | id、owner_id、storage_key、mime、byte_size、checksum、狀態、created_at | 不存公開網址；檔名是私人 metadata；storage_key 不含姓名／電話 |
| 經歷附件 `draft_media` | draft_id、media_id、顯示次序 | 同 owner；支援先有媒體無文字的草稿。現有 DraftCreate 原文規則須同步擴充，不塞假原文繞驗證 |
| 媒體來源 `experience_media` | experience_id、media_id、來源定位／校對資訊 | 正式確認後引用既有素材；多附件不是多次互動，也不多發分 |
| 辨識工作 `processing_jobs` | id、owner_id、草稿／媒體關聯、kind、status、attempt、錯誤碼、結果 schema 版本、建立／更新時間 | STT／VLM／LLM 供應商可換；結果只進候選。是否拆成 job_inputs／job_outputs，由核准的佇列契約決定；金鑰不入表 |
| 夜間設定 `user_preferences` 或 `night_settings`（二選一） | owner_id、是否同意自動切換、詢問狀態、開始／結束時間、updated_at | 採已確認首次 23:00–07:00 詢問、同意後自動且可關閉；依 users.timezone，不另建一套夜間經歷或獎勵表 |
| 名片人物草稿 | 可擴充既有草稿或另設 contact_drafts | 原圖／辨識欄位／人工配對分開；不能只因掃描名片就生成見面、正式事實或獎勵；最終模型待輸入契約審查 |
| 邀請與復原 | invitations、recovery_codes 候選 | 只存雜湊及到期／使用狀態；需涵蓋首次 guest 門檻；依認證工作包先審查，不在本輪改安全設定 |
| 劇場示範人物／多輪演練 | 初期維持獨立 fixtures／交付包；若需持久化再設 simulation_sessions／messages | 明確虛構來源，與 people／person_facts／reward_ledger 隔離；不宣稱這些資料已用於訓練或能忠實模擬真人 |
| 房間、食物、裝飾／進階寵物 | 本輪不設計新庫表 | 尚未有對應正式能力及完整資產驗收；先確認產品規則再談 pet／inventory schema |

媒體保存／刪除期限、雲端備份留存、正式模型廠商及成本、示範劇場是否納入封測，仍待對應決策。未決不填成永久規則、不自動啟用刪除策略。

## 5. Jerry 可直接接續的工作順序

| 次序 | 工作與輸入 | 完成證據 |
|---|---|---|
| 1 | 確認一致來源版本、31 表／201 欄位與 001–005；回報實際 PG／GCP 環境 | 來源 commit、migration 指紋、環境與待填項；不需交密碼／金鑰 |
| 2 | 輸出現有表 → PG 型別／鍵／索引及交易差異；釐清 JSON、NUMERIC、rowid 替代與去重策略 | 可審查的 PG DDL／遷移草案、對照表；明列產品決策與工程選擇 |
| 3 | 對私人備份副本做 preflight；檢查 owner、PK NULL、JSON、十進位、時區、未結束多目標、原文範圍 | 只公開聚合差異與虛構案例，不公開真實列；不擅自修正來源 |
| 4 | 建隔離 PG 測試庫與一次性匯入，保留 ID／原文／密碼雜湊／來源／帳本 | 各表總數、鍵值與內容指紋、Decimal 合計、blob digest、FK／約束差異；排除 sessions 是否沿用須依登入切換策略 |
| 5 | 以真實 PG 跑 API／併發／重送及手機／桌面旅程 | 同時建立第二目標拒絕；同草稿只一經歷／獎勵；延後採計不重發；版本與跨帳號拒絕；Unicode 與隔天用量正確 |
| 6 | 制定切換與回退，再提出發布審查 | 停寫窗口／最後同步／備份還原；切換後新資料的回復方案，不把程式 revert 等同 DB rollback |

本輪只做 SQLite metadata 與文件驗證，**未執行步驟 2–6 的 PG 工程**。Jerry 完成差異規劃後由 Boyi 核對產品規則、Jerry 審查技術、歐桑核對資料；發布與部署另取當批授權。文件尚未 Push，不代傳訊息給同仁。
