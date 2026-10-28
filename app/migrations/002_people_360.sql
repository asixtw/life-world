ALTER TABLE people ADD COLUMN roles TEXT NOT NULL DEFAULT '[]'; -- 定義人物基本資料
ALTER TABLE people ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'; -- 定義人物基本資料
ALTER TABLE people ADD COLUMN category TEXT NOT NULL DEFAULT 'other'; -- 定義人物基本資料
ALTER TABLE people ADD COLUMN followed INTEGER NOT NULL DEFAULT 0 CHECK(followed IN (0,1)); -- 定義人物基本資料
ALTER TABLE people ADD COLUMN revision INTEGER NOT NULL DEFAULT 1; -- 定義人物基本資料
ALTER TABLE people ADD COLUMN common_context TEXT NOT NULL DEFAULT ''; -- 定義人物基本資料
UPDATE people SET roles=CASE WHEN role<>'' THEN json_array(role) ELSE '[]' END; -- 更新人物基本資料
CREATE TABLE interaction_events ( -- 定義真實互動事件
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), -- 定義固定識別碼、所屬帳號
 kind TEXT NOT NULL CHECK(kind IN ('in_person','call','message','other','unknown')), -- 定義互動或私人筆記的分類
 occurred_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1 -- 定義帶時區的實際發生時間、資料版本
); -- 完成真實互動事件的欄位與資料限制
CREATE TABLE interaction_experiences ( -- 定義事件與經歷關聯
 experience_id TEXT PRIMARY KEY REFERENCES experiences(id), -- 定義已確認經歷識別碼
 event_id TEXT NOT NULL REFERENCES interaction_events(id) -- 定義event_id
); -- 完成事件與經歷關聯的欄位與資料限制
CREATE TABLE interaction_people ( -- 定義事件參與人物
 event_id TEXT NOT NULL REFERENCES interaction_events(id), person_id TEXT NOT NULL REFERENCES people(id), -- 定義event_id、關聯人物識別碼
 PRIMARY KEY(event_id,person_id) -- 定義唯一鍵、主鍵或外鍵限制
); -- 完成事件參與人物的欄位與資料限制
INSERT INTO interaction_events(id,owner_id,kind,occurred_at) -- 新增真實互動事件
 SELECT 'legacy:'||id,owner_id,'unknown',occurred_at FROM experiences WHERE person_id IS NOT NULL; -- 將舊經歷回填為未分類互動，不推定實體見面
INSERT INTO interaction_experiences SELECT id,'legacy:'||id FROM experiences WHERE person_id IS NOT NULL; -- 新增事件與經歷關聯
INSERT INTO interaction_people SELECT 'legacy:'||id,person_id FROM experiences WHERE person_id IS NOT NULL; -- 新增事件參與人物
CREATE INDEX interactions_owner_time ON interaction_events(owner_id,occurred_at); -- 建立查詢索引，支援所屬帳號或時間排序
CREATE TABLE person_facts ( -- 定義已確認人物資訊
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), person_id TEXT NOT NULL REFERENCES people(id), -- 定義固定識別碼、所屬帳號、關聯人物識別碼
 dimension TEXT NOT NULL CHECK(dimension IN ('interests','food','skills','habits')), -- 定義人物資訊所屬四維度之一
 value TEXT NOT NULL, normalized_value TEXT NOT NULL, description TEXT NOT NULL, -- 定義人物資訊標籤內容、去重用正規化值、人物資訊補充說明
 status TEXT NOT NULL CHECK(status IN ('confirmed','conflict','archived','unavailable')), -- 定義資料狀態
 conflict_group TEXT, revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, -- 定義衝突資訊群組、資料版本、建立時間
 UNIQUE(person_id,dimension,normalized_value) -- 定義唯一鍵、主鍵或外鍵限制
); -- 完成已確認人物資訊的欄位與資料限制
CREATE TABLE fact_sources ( -- 定義人物資訊來源
 fact_id TEXT NOT NULL REFERENCES person_facts(id), experience_id TEXT NOT NULL REFERENCES experiences(id), -- 定義fact_id、已確認經歷識別碼
 evidence_type TEXT NOT NULL, revoked_at TEXT, PRIMARY KEY(fact_id,experience_id) -- 定義人工確認的證據類型、來源撤回時間
); -- 完成人物資訊來源的欄位與資料限制
CREATE TABLE person_goals ( -- 定義人物與目標關聯
 person_id TEXT NOT NULL REFERENCES people(id), goal_id TEXT NOT NULL REFERENCES goals(id), -- 定義關聯人物識別碼、關聯目標識別碼
 owner_id TEXT NOT NULL REFERENCES users(id), label TEXT NOT NULL DEFAULT '', -- 定義所屬帳號、關聯說明
 PRIMARY KEY(person_id,goal_id) -- 定義唯一鍵、主鍵或外鍵限制
); -- 完成人物與目標關聯的欄位與資料限制
CREATE TABLE person_connections ( -- 定義明確人物關係
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), -- 定義固定識別碼、所屬帳號
 person_a TEXT NOT NULL REFERENCES people(id), person_b TEXT NOT NULL REFERENCES people(id), -- 定義person_a、person_b
 label TEXT NOT NULL, source_experience_ids TEXT NOT NULL, UNIQUE(person_a,person_b) -- 定義關聯說明、引用的已確認經歷識別碼清單
); -- 完成明確人物關係的欄位與資料限制
CREATE TABLE note_sources ( -- 定義私人筆記引用來源
 note_id TEXT NOT NULL REFERENCES notes(id), experience_id TEXT NOT NULL REFERENCES experiences(id), -- 定義note_id、已確認經歷識別碼
 PRIMARY KEY(note_id,experience_id) -- 定義唯一鍵、主鍵或外鍵限制
); -- 完成私人筆記引用來源的欄位與資料限制
