## A.5 現有 SQLite 完整逐表字典

本節由固定 commit 的 001–005 重播 metadata 產生；語意說明參考 DATABASE_SCHEMA.md 並對照服務。NN 僅指 SQL NOT NULL 宣告。所有 FK 的 ON UPDATE／ON DELETE 均為 NO ACTION；缺少 cascade 是事實，不可擅改。未宣告 default 用 —。TEXT PK 在此 SQLite rowid table 不自動等於 NN。

### A.5.1 `actions`｜三個習慣

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：001_initial.sql、004_goal_journey.sql。**隔離／修改風險**：DB 無每目標恰三筆、position 唯一與 owner/goal 相等保證。target_is_derived 無 0/1 CHECK；新增約束先盤點。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `goal_id` | `TEXT` | — | 是 | — | `goals.id` | 關聯目標 goals.id；不因目標結束而刪除歷史。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `title` | `TEXT` | — | 是 | — | — | 供畫面呈現的標題／名稱；不是來源原文。 |
| `unit` | `TEXT` | — | 是 | — | — | 固定計量單位；本輪修改習慣不更換單位。 |
| `target` | `TEXT` | — | 是 | — | — | 預計累計量十進位字串；新式依日期版本加總，舊明確總量保留。 |
| `level` | `INTEGER` | — | 是 | — | — | 舊版 1–3 養分等級，相容保留，不當成目前正式獎勵政策。 |
| `weekdays` | `TEXT` | — | 是 | — | — | JSON 整數陣列，週一 0 至週日 6；保存星期快選。 |
| `position` | `INTEGER` | — | 是 | — | — | 三習慣的顯示順序；服務新建使用 0、1、2。 |
| `per_occurrence` | `TEXT` | — | 是 | `'1'` | — | 實體原始每次量；API 會用 quantity_versions 覆寫為今天適用量，不可直接當最新標準。 |
| `schedule_dates` | `TEXT` | — | 否 | — | — | 已確認安排日期的 JSON 字串陣列；NULL 代表舊資料待補設定。 |
| `cycle` | `TEXT` | — | 是 | `'month'` | — | month／week，日期編輯檢視，不是目標期限。 |
| `target_is_derived` | `INTEGER` | — | 是 | `0` | — | 1 代表 target 可依日期／用量版本推算，0 保留明確總量；DB 無布林 CHECK。 |

**CHECK**：`CHECK(level BETWEEN 1 AND 3)`；`CHECK(cycle IN ('month','week'))`。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_actions_1` | PK 自動／是 | `id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.2 `completions`｜人工成果完成

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：001_initial.sql。**隔離／修改風險**：一目標至多一筆；evidence_ids 是 JSON 無元素 FK，服務核對同目標，不由累計量自動完成。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `goal_id` | `TEXT` | — | 是 | — | `goals.id` | 唯一已完成目標；由佐證及人工確認交易產生。 |
| `evidence_ids` | `TEXT` | — | 是 | — | — | JSON 佐證 ID 陣列；不是 SQL 外鍵，服務檢查同帳號／同目標。 |
| `reflection` | `TEXT` | — | 是 | — | — | 使用者人工輸入的回顧／完成感想。 |
| `created_at` | `TEXT` | — | 是 | — | — | 建立時間，服務寫入帶時區的 UTC ISO 8601 文字。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_completions_1` | PK 自動／是 | `id` |
| `sqlite_autoindex_completions_2` | UNIQUE 自動／是 | `goal_id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.3 `contributions`｜正式習慣投入

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：001_initial.sql。**隔離／修改風險**：quantity 為 Decimal 字串；UNIQUE 防同經歷同行動重複，但 DB 不保證行動屬於經歷的目標。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `experience_id` | `TEXT` | — | 是 | — | `experiences.id` | 來源已確認經歷 experiences.id；不是尚未確認草稿。 |
| `action_id` | `TEXT` | — | 是 | — | `actions.id` | 關聯習慣 actions.id；保留穩定 ID，不以名稱配對。 |
| `quantity` | `TEXT` | — | 是 | — | — | 使用者核對的實際投入量，Decimal 處理；不可由排程推定。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_contributions_1` | PK 自動／是 | `id` |
| `sqlite_autoindex_contributions_2` | UNIQUE 自動／是 | `experience_id`, `action_id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.4 `draft_stories`｜草稿人物整理

**PK**：`draft_id`。**資料主權**：經 drafts.owner_id 繼承；payload 內人物 ID 沒有元素級 FK。

**來源**：003_connections.sql。**隔離／修改風險**：只在正式人工確認交易中轉為故事；payload 無 JSON CHECK／元素 FK。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `draft_id` | `TEXT` | 1 | 否 | — | `drafts.id` | 一對一依附 drafts.id，保存未審閱的人物整理。 |
| `payload` | `TEXT` | — | 是 | — | — | JSON StoryInput：title、participants[{person_id,interacted}]、mentions[{name,start,end,person_id?}]。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_draft_stories_1` | PK 自動／是 | `draft_id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.5 `drafts`｜經歷草稿

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：001_initial.sql。**隔離／修改風險**：contributions 是候選 JSON，不是正式貢獻。確認後禁止草稿編輯為服務規則；直接 SQL 可繞過。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `goal_id` | `TEXT` | — | 否 | — | `goals.id` | 草稿關聯目標，選填；有貢獻時需核對行動屬於該目標。 |
| `person_id` | `TEXT` | — | 否 | — | `people.id` | 草稿主要關聯人物，選填；多人候選另存 draft_stories。 |
| `raw_text` | `TEXT` | — | 是 | — | — | 原始經歷文字，保留空白、換行與 Unicode，摘要不覆寫本欄。 |
| `occurred_at` | `TEXT` | — | 是 | — | — | 實際發生時間，服務轉 UTC 保存；與建立時間分開。 |
| `contributions` | `TEXT` | — | 是 | — | — | JSON [{action_id,quantity}]，尚未確認，不更新正式進度。 |
| `status` | `TEXT` | — | 是 | — | — | draft／confirmed；只有明確確認交易才能轉正式。 |
| `revision` | `INTEGER` | — | 是 | — | — | 樂觀鎖版本；寫入攜帶 expected_revision，衝突須重新核對。 |
| `created_at` | `TEXT` | — | 是 | — | — | 建立時間，服務寫入帶時區的 UTC ISO 8601 文字。 |
| `updated_at` | `TEXT` | — | 是 | — | — | 最近修改時間，UTC ISO 8601 文字。 |

**CHECK**：`CHECK(status IN ('draft','confirmed'))`。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_drafts_1` | PK 自動／是 | `id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.6 `evidence`｜目標完成圖片佐證

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：001_initial.sql。**隔離／修改風險**：content 為圖片 BLOB；不是一般經歷附件表。移到物件儲存須核對 digest、owner、size 與引用。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `goal_id` | `TEXT` | — | 是 | — | `goals.id` | 關聯目標 goals.id；不因目標結束而刪除歷史。 |
| `filename` | `TEXT` | — | 是 | — | — | 原始顯示檔名；視為私人 metadata，不作公開物件鍵。 |
| `mime` | `TEXT` | — | 是 | — | — | 驗證後圖片 MIME；目前服務接受 PNG／JPEG。 |
| `digest` | `TEXT` | — | 是 | — | — | 圖片內容 SHA-256，用於同目標、同帳號去重。 |
| `content` | `BLOB` | — | 是 | — | — | 經服務驗證的圖片 BLOB；不是私人筆記文字。 |
| `size` | `INTEGER` | — | 是 | — | — | 內容位元組數；上限由服務設定，不由 DB CHECK 強制。 |
| `created_at` | `TEXT` | — | 是 | — | — | 建立時間，服務寫入帶時區的 UTC ISO 8601 文字。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_evidence_1` | PK 自動／是 | `id` |
| `sqlite_autoindex_evidence_2` | UNIQUE 自動／是 | `owner_id`, `goal_id`, `digest` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.7 `experience_mentions`｜原文提及與身分配對

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：003_connections.sql。**隔離／修改風險**：位置為 Python Unicode code point，JS UTF-16 索引不可直接寫回；不可只因同名自動配對。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `experience_id` | `TEXT` | — | 是 | — | `experience_stories.experience_id` | 來源已確認經歷 experiences.id；不是尚未確認草稿。 |
| `name` | `TEXT` | — | 是 | — | — | 精確原文人名片段，須與 raw_text[start:end] 相符。 |
| `start` | `INTEGER` | — | 是 | — | — | Python Unicode code point 起點；不是 UTF-8 byte 或 JavaScript UTF-16 位移。 |
| `end` | `INTEGER` | — | 是 | — | — | Unicode code point 排他終點；必須大於 start。 |
| `status` | `TEXT` | — | 是 | `'unmatched'` | — | unmatched／matched／rejected；配對不等於出席或直接關係。 |
| `person_id` | `TEXT` | — | 否 | — | `people.id` | matched 時必填，其餘狀態必空，由 DB CHECK 保護。 |
| `revision` | `INTEGER` | — | 是 | `1` | — | 樂觀鎖版本；寫入攜帶 expected_revision，衝突須重新核對。 |

**CHECK**：`CHECK(start>=0)`；`CHECK(end>start)`；`CHECK(status IN ('unmatched','matched','rejected'))`；`CHECK((status='matched' AND person_id IS NOT NULL) OR (status<>'matched' AND person_id IS NULL))`。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `mentions_person` | 明確建立／否 | `person_id`, `status`, `experience_id` |
| `sqlite_autoindex_experience_mentions_1` | PK 自動／是 | `id` |
| `sqlite_autoindex_experience_mentions_2` | UNIQUE 自動／是 | `experience_id`, `start`, `end` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.8 `experience_participants`｜逐故事參與與直接互動

**PK**：`experience_id`, `person_id`。**資料主權**：由 experience_stories 與 people 雙端推導；服務必須確認同 owner。

**來源**：003_connections.sql。**隔離／修改風險**：interacted 與參與分開；提及配對不能自行插入此表。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `experience_id` | `TEXT` | 1 | 是 | — | `experience_stories.experience_id` | 逐筆故事的實際參與名單，不取合併事件人物聯集。 |
| `person_id` | `TEXT` | 2 | 是 | — | `people.id` | 關聯人物 people.id；是否可空依本欄宣告。 |
| `interacted` | `INTEGER` | — | 是 | `0` | — | 0／1 同場是否另有直接互動；提及不能直接設為參與。 |

**CHECK**：`CHECK(interacted IN (0,1))`。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `participants_person` | 明確建立／否 | `person_id`, `experience_id` |
| `sqlite_autoindex_experience_participants_1` | PK 自動／是 | `experience_id`, `person_id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.9 `experience_stories`｜交會故事狀態

**PK**：`experience_id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：003_connections.sql。**隔離／修改風險**：reviewed 表示使用者核對，不是第三人證實。available=0 是展示撤回，不等於刪除經歷或隱私抹除。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `experience_id` | `TEXT` | 1 | 否 | — | `experiences.id` | 與正式經歷一對一的故事狀態。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `title` | `TEXT` | — | 是 | `''` | — | 故事標題；空白時 API 以摘要前 80 字顯示，不造事件。 |
| `reviewed` | `INTEGER` | — | 是 | `0` | — | 0／1，人物及故事是否已由使用者核對；不表示所有參與者證實。 |
| `available` | `INTEGER` | — | 是 | `1` | — | 0／1，只控制交會來源展示；撤回不刪經歷或帳本。 |
| `revision` | `INTEGER` | — | 是 | `1` | — | 樂觀鎖版本；寫入攜帶 expected_revision，衝突須重新核對。 |

**CHECK**：`CHECK(reviewed IN (0,1))`；`CHECK(available IN (0,1))`。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_experience_stories_1` | PK 自動／是 | `experience_id` |
| `stories_owner_review` | 明確建立／否 | `owner_id`, `reviewed`, `available` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.10 `experiences`｜已確認真實經歷

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：001_initial.sql。**隔離／修改風險**：draft_id UNIQUE 防重複確認；原文不可用摘要取代。主人物欄位不等同逐故事出席名單。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `draft_id` | `TEXT` | — | 是 | — | `drafts.id` | 唯一來源草稿；同一草稿至多形成一筆正式經歷。 |
| `goal_id` | `TEXT` | — | 否 | — | `goals.id` | 保存記錄當時的目標上下文；不表示自動有貢獻。 |
| `person_id` | `TEXT` | — | 否 | — | `people.id` | 相容舊版的主要人物，非完整參與名單；新版必須是已確認參與者。 |
| `raw_text` | `TEXT` | — | 是 | — | — | 原始經歷文字，保留空白、換行與 Unicode，摘要不覆寫本欄。 |
| `summary` | `TEXT` | — | 是 | — | — | 經使用者確認的摘要。 |
| `occurred_at` | `TEXT` | — | 是 | — | — | 實際發生時間，服務轉 UTC 保存；與建立時間分開。 |
| `created_at` | `TEXT` | — | 是 | — | — | 建立時間，服務寫入帶時區的 UTC ISO 8601 文字。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `experiences_owner_idx` | 明確建立／否 | `owner_id` |
| `sqlite_autoindex_experiences_1` | PK 自動／是 | `id` |
| `sqlite_autoindex_experiences_2` | UNIQUE 自動／是 | `draft_id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.11 `fact_sources`｜人物資訊來源

**PK**：`fact_id`, `experience_id`。**資料主權**：由 person_facts 與 experiences 雙端推導；服務必須確認同 owner。

**來源**：002_people_360.sql。**隔離／修改風險**：revoked_at 不會刪原經歷；evidence_type 的三種值由服務驗證，DB 無 enum CHECK。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `fact_id` | `TEXT` | 1 | 是 | — | `person_facts.id` | 關聯人物資訊 person_facts.id。 |
| `experience_id` | `TEXT` | 2 | 是 | — | `experiences.id` | 來源已確認經歷 experiences.id；不是尚未確認草稿。 |
| `evidence_type` | `TEXT` | — | 是 | — | — | 服務限定 stated_by_person／observed_by_user／documented_source；DB 未加 CHECK。 |
| `revoked_at` | `TEXT` | — | 否 | — | — | 來源撤回時間；不刪除原經歷。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_fact_sources_1` | PK 自動／是 | `fact_id`, `experience_id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.12 `goal_reviews`｜目標回顧與異動快照

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：004_goal_journey.sql。**隔離／修改風險**：前後 JSON 可能含私人內容；ORDER BY created_at,rowid 不能直接移至 PG。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `goal_id` | `TEXT` | — | 是 | — | `goals.id` | 關聯目標 goals.id；不因目標結束而刪除歷史。 |
| `decision` | `TEXT` | — | 是 | — | — | 服務限定 end／extend／setup／schedule；DB 未加 enum CHECK。 |
| `previous_state` | `TEXT` | — | 是 | — | — | 操作前目標及習慣 JSON 快照，不遞迴嵌入歷史 reviews。 |
| `new_state` | `TEXT` | — | 是 | — | — | 操作後 JSON 快照，保留名稱／排程／用量版本異動。 |
| `reflection` | `TEXT` | — | 是 | — | — | 使用者人工輸入的回顧／完成感想。 |
| `created_at` | `TEXT` | — | 是 | — | — | 建立時間，服務寫入帶時區的 UTC ISO 8601 文字。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_goal_reviews_1` | PK 自動／是 | `id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.13 `goals`｜目標與實體生命週期

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：001_initial.sql、004_goal_journey.sql。**隔離／修改風險**：DB 無單一未結束目標唯一約束；到期待回顧仍占名額。不得把公開五狀態寫進實體兩狀態。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `title` | `TEXT` | — | 是 | — | — | 供畫面呈現的標題／名稱；不是來源原文。 |
| `outcome` | `TEXT` | — | 是 | — | — | 使用者描述終極成果；不由習慣累計自動認定達成。 |
| `status` | `TEXT` | — | 是 | — | — | 實體僅 active／completed；公開五狀態另由日期與結束欄位推導。 |
| `created_at` | `TEXT` | — | 是 | — | — | 建立時間，服務寫入帶時區的 UTC ISO 8601 文字。 |
| `completed_at` | `TEXT` | — | 否 | — | — | 人工確認完成時間；未完成可空。 |
| `reflection` | `TEXT` | — | 是 | `''` | — | 使用者人工輸入的回顧／完成感想。 |
| `start_date` | `TEXT` | — | 否 | — | — | 目標當地開始日 YYYY-MM-DD；舊資料可空，不猜期限。 |
| `deadline` | `TEXT` | — | 否 | — | — | 使用者選定的截止日；含固定目標時區整天，舊資料可空。 |
| `schedule_timezone` | `TEXT` | — | 否 | — | — | 建立／補設定時固定的 IANA 目標時區；舊資料可空。 |
| `revision` | `INTEGER` | — | 是 | `1` | — | 樂觀鎖版本；寫入攜帶 expected_revision，衝突須重新核對。 |
| `ended_at` | `TEXT` | — | 否 | — | — | 主動收藏未完成挑戰的時間；不等於刪除目標。 |
| `end_reason` | `TEXT` | — | 否 | — | — | early_end／expired；區分提前結束與到期未完成。 |

**CHECK**：`CHECK(status IN ('active','completed'))`；`CHECK(end_reason IN ('early_end','expired'))`。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `goals_owner_idx` | 明確建立／否 | `owner_id` |
| `sqlite_autoindex_goals_1` | PK 自動／是 | `id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.14 `habit_quantity_versions`｜習慣日期用量版本

**PK**：`action_id`, `effective_from`。**資料主權**：經 actions.owner_id → users.id 繼承；此表沒有 owner_id。

**來源**：005_habit_versions.sql。**隔離／修改風險**：0001-01-01 是舊原始標準標記；同生效日 UPSERT，改前值須由 goal_reviews 追溯。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `action_id` | `TEXT` | 1 | 是 | — | `actions.id` | 關聯習慣 actions.id；保留穩定 ID，不以名稱配對。 |
| `effective_from` | `TEXT` | 2 | 是 | — | — | 目標當地生效日；新調整從隔天生效；0001-01-01 只標記舊原始標準，非真實起日。 |
| `quantity` | `TEXT` | — | 是 | — | — | 該版本每次預期量的精確十進位字串，不是完成量。 |
| `created_at` | `TEXT` | — | 是 | — | — | 此生效日版本最近確認時間；同日改寫會更新，前值見 goal_reviews。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_habit_quantity_versions_1` | PK 自動／是 | `action_id`, `effective_from` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.15 `interaction_events`｜去重互動事件

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：002_people_360.sql。**隔離／修改風險**：只有 in_person 算實體見面；legacy: ID 不可轉為 UUID。事件聚合不代表逐故事所有人都到場。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `kind` | `TEXT` | — | 是 | — | — | in_person／call／message／other／unknown；只有 in_person 計見面次數。 |
| `occurred_at` | `TEXT` | — | 是 | — | — | 實際發生時間，服務轉 UTC 保存；與建立時間分開。 |
| `revision` | `INTEGER` | — | 是 | `1` | — | 樂觀鎖版本；寫入攜帶 expected_revision，衝突須重新核對。 |

**CHECK**：`CHECK(kind IN ('in_person','call','message','other','unknown'))`。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `interactions_owner_time` | 明確建立／否 | `owner_id`, `occurred_at` |
| `sqlite_autoindex_interaction_events_1` | PK 自動／是 | `id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.16 `interaction_experiences`｜事件與經歷對應

**PK**：`experience_id`。**資料主權**：由 experiences 與 interaction_events 雙端推導；服務必須確認同 owner。

**來源**：002_people_360.sql。**隔離／修改風險**：PK 限一經歷至多一事件；合併事件不可重複計會面或重發獎。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `experience_id` | `TEXT` | 1 | 否 | — | `experiences.id` | 主鍵使一筆經歷最多對應一個互動事件；一事件可對應多筆經歷。 |
| `event_id` | `TEXT` | — | 是 | — | `interaction_events.id` | 關聯互動事件 interaction_events.id。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_interaction_experiences_1` | PK 自動／是 | `experience_id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.17 `interaction_people`｜事件互動人物

**PK**：`event_id`, `person_id`。**資料主權**：由 interaction_events 與 people 雙端推導；服務必須確認同 owner。

**來源**：002_people_360.sql。**隔離／修改風險**：事件人物是直接互動聚合，不能拿聯集覆蓋 experience_participants。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `event_id` | `TEXT` | 1 | 是 | — | `interaction_events.id` | 事件聚合的互動人物關聯；不能當成每筆故事的出席名單。 |
| `person_id` | `TEXT` | 2 | 是 | — | `people.id` | 關聯人物 people.id；是否可空依本欄宣告。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_interaction_people_1` | PK 自動／是 | `event_id`, `person_id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.18 `note_sources`｜筆記引用來源

**PK**：`note_id`, `experience_id`。**資料主權**：由 notes 與 experiences 雙端推導；服務必須確認同 owner。

**來源**：002_people_360.sql。**隔離／修改風險**：只保存來源引用，不是建立時內容快照；讀取須重新核對來源可用性及 owner。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `note_id` | `TEXT` | 1 | 是 | — | `notes.id` | 關聯私人筆記 notes.id。 |
| `experience_id` | `TEXT` | 2 | 是 | — | `experiences.id` | 私人筆記引用的已確認經歷；服務另檢查與人物的關聯。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_note_sources_1` | PK 自動／是 | `note_id`, `experience_id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.19 `notes`｜私人小劇場筆記

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：001_initial.sql。**隔離／修改風險**：正式私人 preparation/simulation/message 筆記；不是多輪劇場場次，也不得回寫人物或帳本。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `person_id` | `TEXT` | — | 否 | — | `people.id` | 關聯人物 people.id；是否可空依本欄宣告。 |
| `kind` | `TEXT` | — | 是 | — | — | preparation／simulation／message；相遇後回顧另走真實經歷流程。 |
| `title` | `TEXT` | — | 是 | — | — | 供畫面呈現的標題／名稱；不是來源原文。 |
| `content` | `TEXT` | — | 是 | — | — | 私人準備／模擬／訊息草稿；不更新正式人物、進度或積分。 |
| `created_at` | `TEXT` | — | 是 | — | — | 建立時間，服務寫入帶時區的 UTC ISO 8601 文字。 |

**CHECK**：`CHECK(kind IN ('preparation','simulation','message'))`。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_notes_1` | PK 自動／是 | `id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.20 `pending_contributions`｜待處理／未採計投入

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：004_goal_journey.sql。**隔離／修改風險**：採計只寫 contributions，不重發獎；accepted_quantity 與 status 一致性未用 CHECK 限制。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `goal_id` | `TEXT` | — | 是 | — | `goals.id` | 關聯目標 goals.id；不因目標結束而刪除歷史。 |
| `experience_id` | `TEXT` | — | 是 | — | `experiences.id` | 來源已確認經歷 experiences.id；不是尚未確認草稿。 |
| `action_id` | `TEXT` | — | 是 | — | `actions.id` | 關聯習慣 actions.id；保留穩定 ID，不以名稱配對。 |
| `quantity` | `TEXT` | — | 是 | — | — | 原填貢獻量字串；經歷可已保存，但本量尚未正式採計。 |
| `status` | `TEXT` | — | 是 | `'pending'` | — | pending／accepted／unapplied；逐筆採計或未採計歷史。 |
| `accepted_quantity` | `TEXT` | — | 否 | — | — | 人工核對後實際採計量，可與原填不同，未採計可空。 |
| `accepted_at` | `TEXT` | — | 否 | — | — | 確認採計時間；不會再次產生 reward_ledger。 |

**CHECK**：`CHECK(status IN ('pending','accepted','unapplied'))`。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `pending_goal_idx` | 明確建立／否 | `owner_id`, `goal_id` |
| `sqlite_autoindex_pending_contributions_1` | PK 自動／是 | `id` |
| `sqlite_autoindex_pending_contributions_2` | UNIQUE 自動／是 | `experience_id`, `action_id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.21 `people`｜人物收藏冊主檔

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：001_initial.sql、002_people_360.sql。**隔離／修改風險**：role 為舊相容欄位；roles/tags 非四維度正式事實。revision 存在，但不是全域人物來源版本鏈。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `name` | `TEXT` | — | 是 | — | — | 人物稱呼，不以姓名作唯一身分。 |
| `role` | `TEXT` | — | 是 | `''` | — | 舊版單一完整角色字串，相容保留，不能自動拆成已驗證事實。 |
| `notes` | `TEXT` | — | 是 | `''` | — | 使用者備註，不自動轉人物事實或 AI 訓練資料。 |
| `created_at` | `TEXT` | — | 是 | — | — | 建立時間，服務寫入帶時區的 UTC ISO 8601 文字。 |
| `roles` | `TEXT` | — | 是 | `'[]'` | — | JSON 多角色字串陣列。 |
| `tags` | `TEXT` | — | 是 | `'[]'` | — | JSON 人物標籤字串陣列，用於搜尋。 |
| `category` | `TEXT` | — | 是 | `'other'` | — | 服務限定 business／life／learning／other；DB 無類別 CHECK。 |
| `followed` | `INTEGER` | — | 是 | `0` | — | 0／1 私人星標（介面已由關注改稱星標）；不通知對方，不代表親密度。 |
| `revision` | `INTEGER` | — | 是 | `1` | — | 樂觀鎖版本；寫入攜帶 expected_revision，衝突須重新核對。 |
| `common_context` | `TEXT` | — | 是 | `''` | — | 人工記錄的共同場合／交集文字，不推論私人關係。 |

**CHECK**：`CHECK(followed IN (0,1))`。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_people_1` | PK 自動／是 | `id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.22 `person_connections`｜明確人物關係

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：002_people_360.sql。**隔離／修改風險**：服務排序 person_a/person_b 並拒絕自連；DB 無 a<b／a<>b CHECK，JSON 來源無實體 FK。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `person_a` | `TEXT` | — | 是 | — | `people.id` | 明確關係的一端人物；服務將兩端 ID 排序。 |
| `person_b` | `TEXT` | — | 是 | — | `people.id` | 明確關係的另一端人物；服務拒絕自連與跨帳號。 |
| `label` | `TEXT` | — | 是 | — | — | 使用者明確輸入的關係名稱，不由故事共現自動推論。 |
| `source_experience_ids` | `TEXT` | — | 是 | — | — | JSON 經歷 ID 陣列；來源由服務核對，非 SQL 外鍵，可空陣列。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_person_connections_1` | PK 自動／是 | `id` |
| `sqlite_autoindex_person_connections_2` | UNIQUE 自動／是 | `person_a`, `person_b` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.23 `person_facts`｜四維度人物資訊

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：002_people_360.sql。**隔離／修改風險**：normalized_value 為 NFKC/casefold 等應用正規化；不可用 PG lower 替代。conflict/archived/unavailable 均須保留。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `person_id` | `TEXT` | — | 是 | — | `people.id` | 關聯人物 people.id；是否可空依本欄宣告。 |
| `dimension` | `TEXT` | — | 是 | — | — | interests／food／skills／habits，對應四個人物維度。 |
| `value` | `TEXT` | — | 是 | — | — | 使用者已核對的資訊標籤，無資料不補造。 |
| `normalized_value` | `TEXT` | — | 是 | — | — | Unicode NFKC＋casefold 等正規化後的同值去重鍵。 |
| `description` | `TEXT` | — | 是 | — | — | 資訊說明，不覆寫來源經歷。 |
| `status` | `TEXT` | — | 是 | — | — | confirmed／conflict／archived／unavailable；衝突保留，最後來源撤回可不可用。 |
| `conflict_group` | `TEXT` | — | 否 | — | — | 人工指定的衝突群組；未衝突可空。 |
| `revision` | `INTEGER` | — | 是 | `1` | — | 樂觀鎖版本；寫入攜帶 expected_revision，衝突須重新核對。 |
| `created_at` | `TEXT` | — | 是 | — | — | 建立時間，服務寫入帶時區的 UTC ISO 8601 文字。 |

**CHECK**：`CHECK(dimension IN ('interests','food','skills','habits'))`；`CHECK(status IN ('confirmed','conflict','archived','unavailable'))`。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_person_facts_1` | PK 自動／是 | `id` |
| `sqlite_autoindex_person_facts_2` | UNIQUE 自動／是 | `person_id`, `dimension`, `normalized_value` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.24 `person_goals`｜人物與目標關聯

**PK**：`person_id`, `goal_id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：002_people_360.sql。**隔離／修改風險**：普通 FK 不保證人物、目標、owner 三者一致；label 不代表對方承諾。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `person_id` | `TEXT` | 1 | 是 | — | `people.id` | 關聯人物 people.id；是否可空依本欄宣告。 |
| `goal_id` | `TEXT` | 2 | 是 | — | `goals.id` | 關聯目標 goals.id；不因目標結束而刪除歷史。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `label` | `TEXT` | — | 是 | `''` | — | 人物與目標的明確關聯說明，不代表對方承諾。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_person_goals_1` | PK 自動／是 | `person_id`, `goal_id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.25 `requests`｜請求重送去重

**PK**：`owner_id`, `operation`, `request_id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：001_initial.sql。**隔離／修改風險**：fingerprint 依穩定 JSON 序列化；回執可能含私人資料。沒有 created_at／expires_at，清理期限未定。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `owner_id` | `TEXT` | 1 | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `operation` | `TEXT` | 2 | 是 | — | — | 去重操作命名空間，例如 confirm／goal:create／goal:review:<ID>。 |
| `request_id` | `TEXT` | 3 | 是 | — | — | 呼叫端產生、重試沿用的提交識別碼，與 owner／operation 組成 PK。 |
| `fingerprint` | `TEXT` | — | 是 | — | — | 穩定序列化請求的內容雜湊；同 key 不同內容回衝突。 |
| `response` | `TEXT` | — | 是 | — | — | 成功 JSON 回執；可能含私人資料，不作公開測試資料。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_requests_1` | PK 自動／是 | `owner_id`, `operation`, `request_id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.26 `reward_ledger`｜養分帳本

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：001_initial.sql。**隔離／修改風險**：一經歷至多一筆正分帳；rule_version 是實作政策版本，不代表正式商業獎勵已核准。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `experience_id` | `TEXT` | — | 是 | — | `experiences.id` | 唯一經歷來源，防止同筆經歷重複發獎。 |
| `points` | `INTEGER` | — | 是 | — | — | 一次已確認經歷的正整數養分；不因缺席扣分。 |
| `rule_version` | `TEXT` | — | 是 | — | — | 產生本次回饋的規則版本，保留歷史可追溯。 |
| `created_at` | `TEXT` | — | 是 | — | — | 建立時間，服務寫入帶時區的 UTC ISO 8601 文字。 |

**CHECK**：`CHECK(points>0)`。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_reward_ledger_1` | PK 自動／是 | `id` |
| `sqlite_autoindex_reward_ledger_2` | UNIQUE 自動／是 | `experience_id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.27 `schema_migrations`｜資料庫遷移版本

**PK**：`version`。**資料主權**：系統層，全資料庫共用；沒有使用者內容。

**來源**：app/db.py。**隔離／修改風險**：只記 migration 檔名，沒有 checksum；不得修改舊 migration 後假設 runner 會重跑。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `version` | `TEXT` | 1 | 否 | — | — | 已套用的 migration 檔名；僅版本標記，未保存 migration 內容雜湊。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_schema_migrations_1` | PK 自動／是 | `version` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.28 `sessions`｜登入工作階段

**PK**：`token_hash`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：001_initial.sql。**隔離／修改風險**：這是登入 Session；到期由服務判斷。遷移是否輪換登入待決，不能與 theater_sessions 合併。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `token_hash` | `TEXT` | 1 | 否 | — | — | 登入 cookie token 的 SHA-256 雜湊；不是可回傳的原 token。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `csrf_token` | `TEXT` | — | 是 | — | — | 寫入防護的隨機 CSRF token；不放公開文件／日誌。 |
| `expires_at` | `TEXT` | — | 是 | — | — | 工作階段到期時間；服務判定失效。 |
| `created_at` | `TEXT` | — | 是 | — | — | 建立時間，服務寫入帶時區的 UTC ISO 8601 文字。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `session_owner_idx` | 明確建立／否 | `owner_id` |
| `sqlite_autoindex_sessions_1` | PK 自動／是 | `token_hash` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.29 `story_history`｜交會更正歷史

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：003_connections.sql。**隔離／修改風險**：前後快照含隱私，撤回後仍可能留副本；rowid 次序需另設穩定排序。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `experience_id` | `TEXT` | — | 是 | — | `experience_stories.experience_id` | 來源已確認經歷 experiences.id；不是尚未確認草稿。 |
| `action` | `TEXT` | — | 是 | — | — | 人工更正／配對／展示異動的操作名稱；DB 未限制 enum。 |
| `before_json` | `TEXT` | — | 是 | — | — | 操作前 JSON 狀態，可能包含來源原文，不公開匯出。 |
| `after_json` | `TEXT` | — | 是 | — | — | 操作後 JSON 狀態；與更正同交易保存。 |
| `created_at` | `TEXT` | — | 是 | — | — | 建立時間，服務寫入帶時區的 UTC ISO 8601 文字。 |

**CHECK**：無。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_story_history_1` | PK 自動／是 | `id` |
| `story_history_source` | 明確建立／否 | `experience_id`, `created_at` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.30 `tasks`｜後續待辦

**PK**：`id`。**資料主權**：owner_id → users.id；每次讀寫仍由服務核對登入 owner，FK 不提供列層權限。

**來源**：001_initial.sql。**隔離／修改風險**：正式表只有 title/done，無 due_date／goal_id／action_id；不能把原型具名任務日期寫成正式欄位。勾選不發獎。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `owner_id` | `TEXT` | — | 是 | — | `users.id` | 資料所屬 users.id；寫入及讀取均須核對同一帳號。 |
| `experience_id` | `TEXT` | — | 是 | — | `experiences.id` | 來源已確認經歷 experiences.id；不是尚未確認草稿。 |
| `title` | `TEXT` | — | 是 | — | — | 供畫面呈現的標題／名稱；不是來源原文。 |
| `done` | `INTEGER` | — | 是 | `0` | — | 0／1 待辦勾選，不等於習慣貢獻或終極成果完成。 |

**CHECK**：`CHECK(done IN (0,1))`。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_tasks_1` | PK 自動／是 | `id` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。

### A.5.31 `users`｜帳號與首次引導

**PK**：`id`。**資料主權**：本列 id 是私人世界的 owner；不是團隊共用帳號。

**來源**：001_initial.sql。**隔離／修改風險**：升級訪客保留 ID；遷移不可重建 owner 或公開 password_hash。

| 欄位 | 型別 | PK 順位 | NN | Default | FK | 語意／來源追溯 |
|---|---|---|---|---|---|---|
| `id` | `TEXT` | 1 | 否 | — | — | 固定識別碼；服務產生，遷移保留原字串，不重建 ID。 |
| `status` | `TEXT` | — | 是 | — | — | guest／registered；升級不變更 owner ID。 |
| `username` | `TEXT` | — | 否 | — | — | 本機登入帳號，唯一；訪客可空。 |
| `password_hash` | `TEXT` | — | 否 | — | — | 密碼雜湊，使用 pwdlib 建議雜湊器；訪客可空，不存明文。 |
| `name` | `TEXT` | — | 是 | `''` | — | 使用者希望被稱呼的名稱。 |
| `bio` | `TEXT` | — | 是 | `''` | — | 首次引導的個人介紹；建立首目標前由服務檢查。 |
| `timezone` | `TEXT` | — | 是 | `'Asia/Taipei'` | — | 帳號 IANA 時區；不覆寫既有目標固定時區。 |
| `hatched_at` | `TEXT` | — | 否 | — | — | 首次成功建立目標後 Lumi 誕生時間；NULL 代表尚未孵化。 |
| `created_at` | `TEXT` | — | 是 | — | — | 建立時間，服務寫入帶時區的 UTC ISO 8601 文字。 |

**CHECK**：`CHECK(status IN ('guest','registered'))`。

| 索引名稱 | 類型／Unique | 鍵欄位 |
|---|---|---|
| `sqlite_autoindex_users_1` | PK 自動／是 | `id` |
| `sqlite_autoindex_users_2` | UNIQUE 自動／是 | `username` |

唯一約束即上列 Unique 索引；未列者無其他 UNIQUE。自動索引名稱僅記錄 SQLite metadata，不作 PG 名稱契約。
