-- 現有 SQLite：001–005 在獨立空庫重播的結構，不含業務資料。
-- schema_migrations 版本列未匯出；不可直接交給現有 runner 當已遷移 DB。
CREATE TABLE actions ( -- 定義目標行動
 id TEXT PRIMARY KEY, goal_id TEXT NOT NULL REFERENCES goals(id), owner_id TEXT NOT NULL REFERENCES users(id), -- 定義固定識別碼、關聯目標識別碼、所屬帳號
 title TEXT NOT NULL, unit TEXT NOT NULL, target TEXT NOT NULL, -- 定義標題、行動計量單位、行動預期累計值
 level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 3), weekdays TEXT NOT NULL, position INTEGER NOT NULL -- 定義建立時的養分等級、每週預計執行日（週一為 0）、position
, per_occurrence TEXT NOT NULL DEFAULT '1', schedule_dates TEXT, cycle TEXT NOT NULL DEFAULT 'month' CHECK(cycle IN ('month','week')), target_is_derived INTEGER NOT NULL DEFAULT 0);

CREATE TABLE completions ( -- 定義目標完成紀錄
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT NOT NULL UNIQUE REFERENCES goals(id), -- 定義固定識別碼、所屬帳號、關聯目標識別碼
 evidence_ids TEXT NOT NULL, reflection TEXT NOT NULL, created_at TEXT NOT NULL -- 定義完成目標所引用的佐證識別碼、目標完成感想、建立時間
);

CREATE TABLE contributions ( -- 定義行動貢獻
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL REFERENCES experiences(id), -- 定義固定識別碼、所屬帳號、已確認經歷識別碼
 action_id TEXT NOT NULL REFERENCES actions(id), quantity TEXT NOT NULL, -- 定義本次貢獻所屬行動識別碼、本次人工確認的貢獻量
 UNIQUE(experience_id, action_id) -- 定義唯一鍵、主鍵或外鍵限制
);

CREATE TABLE draft_stories ( -- 保存尚未確認的人物整理，不改舊草稿欄位
 draft_id TEXT PRIMARY KEY REFERENCES drafts(id), payload TEXT NOT NULL -- 以草稿識別碼與 JSON 保存未審閱角色
);

CREATE TABLE drafts ( -- 定義經歷草稿
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT REFERENCES goals(id), -- 定義固定識別碼、所屬帳號、關聯目標識別碼
 person_id TEXT REFERENCES people(id), raw_text TEXT NOT NULL, occurred_at TEXT NOT NULL, -- 定義關聯人物識別碼、原始經歷文字（保留空白與換行）、帶時區的實際發生時間
 contributions TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('draft','confirmed')), -- 定義本次要累計的行動貢獻清單、資料狀態
 revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL -- 定義資料版本、建立時間、updated_at
);

CREATE TABLE evidence ( -- 定義圖片佐證
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT NOT NULL REFERENCES goals(id), -- 定義固定識別碼、所屬帳號、關聯目標識別碼
 filename TEXT NOT NULL, mime TEXT NOT NULL, digest TEXT NOT NULL, content BLOB NOT NULL, size INTEGER NOT NULL, -- 定義filename、mime、digest、圖片原始位元組、size
 created_at TEXT NOT NULL, UNIQUE(owner_id, goal_id, digest) -- 定義建立時間
);

CREATE TABLE experience_mentions ( -- 保留原文提及與人工身分核對
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL REFERENCES experience_stories(experience_id), -- 保存固定線索與來源
 name TEXT NOT NULL, start INTEGER NOT NULL CHECK(start>=0), end INTEGER NOT NULL CHECK(end>start), -- 以 Unicode 字元定位原文
 status TEXT NOT NULL DEFAULT 'unmatched' CHECK(status IN ('unmatched','matched','rejected')), -- 配對狀態不等於參與
 person_id TEXT REFERENCES people(id), revision INTEGER NOT NULL DEFAULT 1, -- 正式人物與版本
 UNIQUE(experience_id,start,end), CHECK((status='matched' AND person_id IS NOT NULL) OR (status<>'matched' AND person_id IS NULL)) -- 拒絕矛盾與重複來源
);

CREATE TABLE experience_participants ( -- 保留每筆故事的實際參與者
 experience_id TEXT NOT NULL REFERENCES experience_stories(experience_id), person_id TEXT NOT NULL REFERENCES people(id), -- 不使用合併事件的人物聯集
 interacted INTEGER NOT NULL DEFAULT 0 CHECK(interacted IN (0,1)), PRIMARY KEY(experience_id,person_id) -- 同場與直接互動分開
);

CREATE TABLE experience_stories ( -- 定義逐經歷的交會狀態
 experience_id TEXT PRIMARY KEY REFERENCES experiences(id), owner_id TEXT NOT NULL REFERENCES users(id), -- 保存來源與帳號
 title TEXT NOT NULL DEFAULT '', reviewed INTEGER NOT NULL DEFAULT 0 CHECK(reviewed IN (0,1)), -- 未核對的舊關聯不進探索
 available INTEGER NOT NULL DEFAULT 1 CHECK(available IN (0,1)), revision INTEGER NOT NULL DEFAULT 1 -- 提供撤回與樂觀鎖
);

CREATE TABLE experiences ( -- 定義已確認經歷
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), draft_id TEXT NOT NULL UNIQUE REFERENCES drafts(id), -- 定義固定識別碼、所屬帳號、draft_id
 goal_id TEXT REFERENCES goals(id), person_id TEXT REFERENCES people(id), raw_text TEXT NOT NULL, -- 定義關聯目標識別碼、關聯人物識別碼、原始經歷文字（保留空白與換行）
 summary TEXT NOT NULL, occurred_at TEXT NOT NULL, created_at TEXT NOT NULL -- 定義使用者核對後的經歷摘要、帶時區的實際發生時間、建立時間
);

CREATE TABLE fact_sources ( -- 定義人物資訊來源
 fact_id TEXT NOT NULL REFERENCES person_facts(id), experience_id TEXT NOT NULL REFERENCES experiences(id), -- 定義fact_id、已確認經歷識別碼
 evidence_type TEXT NOT NULL, revoked_at TEXT, PRIMARY KEY(fact_id,experience_id) -- 定義人工確認的證據類型、來源撤回時間
);

CREATE TABLE goal_reviews ( -- 保存期限與排程修改的前後快照。
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT NOT NULL REFERENCES goals(id), -- 回顧歸屬於同一帳號與目標。
 decision TEXT NOT NULL, previous_state TEXT NOT NULL, new_state TEXT NOT NULL, reflection TEXT NOT NULL, created_at TEXT NOT NULL -- 不覆寫歷史回顧。
);

CREATE TABLE goals ( -- 定義目標
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), title TEXT NOT NULL, -- 定義固定識別碼、所屬帳號、標題
 outcome TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','completed')), -- 定義目標的終極成果說明、資料狀態
 created_at TEXT NOT NULL, completed_at TEXT, reflection TEXT NOT NULL DEFAULT '' -- 定義建立時間、completed_at、目標完成感想
, start_date TEXT, deadline TEXT, schedule_timezone TEXT, revision INTEGER NOT NULL DEFAULT 1, ended_at TEXT, end_reason TEXT CHECK(end_reason IN ('early_end','expired')));

CREATE TABLE habit_quantity_versions (
    action_id TEXT NOT NULL REFERENCES actions(id),
    effective_from TEXT NOT NULL,
    quantity TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (action_id, effective_from)
);

CREATE TABLE interaction_events ( -- 定義真實互動事件
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), -- 定義固定識別碼、所屬帳號
 kind TEXT NOT NULL CHECK(kind IN ('in_person','call','message','other','unknown')), -- 定義互動或私人筆記的分類
 occurred_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1 -- 定義帶時區的實際發生時間、資料版本
);

CREATE TABLE interaction_experiences ( -- 定義事件與經歷關聯
 experience_id TEXT PRIMARY KEY REFERENCES experiences(id), -- 定義已確認經歷識別碼
 event_id TEXT NOT NULL REFERENCES interaction_events(id) -- 定義event_id
);

CREATE TABLE interaction_people ( -- 定義事件參與人物
 event_id TEXT NOT NULL REFERENCES interaction_events(id), person_id TEXT NOT NULL REFERENCES people(id), -- 定義event_id、關聯人物識別碼
 PRIMARY KEY(event_id,person_id) -- 定義唯一鍵、主鍵或外鍵限制
);

CREATE TABLE note_sources ( -- 定義私人筆記引用來源
 note_id TEXT NOT NULL REFERENCES notes(id), experience_id TEXT NOT NULL REFERENCES experiences(id), -- 定義note_id、已確認經歷識別碼
 PRIMARY KEY(note_id,experience_id) -- 定義唯一鍵、主鍵或外鍵限制
);

CREATE TABLE notes ( -- 定義私人筆記
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), person_id TEXT REFERENCES people(id), -- 定義固定識別碼、所屬帳號、關聯人物識別碼
 kind TEXT NOT NULL CHECK(kind IN ('preparation','simulation','message')), title TEXT NOT NULL, -- 定義互動或私人筆記的分類、標題
 content TEXT NOT NULL, created_at TEXT NOT NULL -- 定義私人筆記內容、建立時間
);

CREATE TABLE pending_contributions ( -- 到期後先確認經歷，不提前計入目標。
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT NOT NULL REFERENCES goals(id), -- 權限與目標來源。
 experience_id TEXT NOT NULL REFERENCES experiences(id), action_id TEXT NOT NULL REFERENCES actions(id), quantity TEXT NOT NULL, -- 保留原始建議數量。
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','unapplied')), accepted_quantity TEXT, accepted_at TEXT, -- 人工採計歷史。
 UNIQUE(experience_id,action_id) -- 同筆經歷的同項貢獻只能待處理一次。
);

CREATE TABLE people ( -- 定義人物基本資料
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), name TEXT NOT NULL, -- 定義固定識別碼、所屬帳號、顯示稱呼
 role TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL -- 定義舊版完整角色文字、自行記錄的備註（不自動轉成事實）、建立時間
, roles TEXT NOT NULL DEFAULT '[]', tags TEXT NOT NULL DEFAULT '[]', category TEXT NOT NULL DEFAULT 'other', followed INTEGER NOT NULL DEFAULT 0 CHECK(followed IN (0,1)), revision INTEGER NOT NULL DEFAULT 1, common_context TEXT NOT NULL DEFAULT '');

CREATE TABLE person_connections ( -- 定義明確人物關係
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), -- 定義固定識別碼、所屬帳號
 person_a TEXT NOT NULL REFERENCES people(id), person_b TEXT NOT NULL REFERENCES people(id), -- 定義person_a、person_b
 label TEXT NOT NULL, source_experience_ids TEXT NOT NULL, UNIQUE(person_a,person_b) -- 定義關聯說明、引用的已確認經歷識別碼清單
);

CREATE TABLE person_facts ( -- 定義已確認人物資訊
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), person_id TEXT NOT NULL REFERENCES people(id), -- 定義固定識別碼、所屬帳號、關聯人物識別碼
 dimension TEXT NOT NULL CHECK(dimension IN ('interests','food','skills','habits')), -- 定義人物資訊所屬四維度之一
 value TEXT NOT NULL, normalized_value TEXT NOT NULL, description TEXT NOT NULL, -- 定義人物資訊標籤內容、去重用正規化值、人物資訊補充說明
 status TEXT NOT NULL CHECK(status IN ('confirmed','conflict','archived','unavailable')), -- 定義資料狀態
 conflict_group TEXT, revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, -- 定義衝突資訊群組、資料版本、建立時間
 UNIQUE(person_id,dimension,normalized_value) -- 定義唯一鍵、主鍵或外鍵限制
);

CREATE TABLE person_goals ( -- 定義人物與目標關聯
 person_id TEXT NOT NULL REFERENCES people(id), goal_id TEXT NOT NULL REFERENCES goals(id), -- 定義關聯人物識別碼、關聯目標識別碼
 owner_id TEXT NOT NULL REFERENCES users(id), label TEXT NOT NULL DEFAULT '', -- 定義所屬帳號、關聯說明
 PRIMARY KEY(person_id,goal_id) -- 定義唯一鍵、主鍵或外鍵限制
);

CREATE TABLE requests ( -- 定義去重請求
 owner_id TEXT NOT NULL REFERENCES users(id), operation TEXT NOT NULL, request_id TEXT NOT NULL, -- 定義所屬帳號、operation、重送去重用的提交代碼
 fingerprint TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(owner_id, operation, request_id) -- 定義fingerprint、response
);

CREATE TABLE reward_ledger ( -- 定義積分帳本
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL UNIQUE REFERENCES experiences(id), -- 定義固定識別碼、所屬帳號、已確認經歷識別碼
 points INTEGER NOT NULL CHECK(points>0), rule_version TEXT NOT NULL, created_at TEXT NOT NULL -- 定義points、積分規則的開發版本代號、建立時間
);

CREATE TABLE schema_migrations (version TEXT PRIMARY KEY);

CREATE TABLE sessions ( -- 定義登入工作階段
 token_hash TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), -- 定義token_hash、所屬帳號
 csrf_token TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL -- 定義csrf_token、expires_at、建立時間
);

CREATE TABLE story_history ( -- 保存人工更正、配對與展示撤回歷史
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL REFERENCES experience_stories(experience_id), -- 限制歷史所屬來源
 action TEXT NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL, created_at TEXT NOT NULL -- 保留更正前後與日期
);

CREATE TABLE tasks ( -- 定義下一步待辦
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL REFERENCES experiences(id), -- 定義固定識別碼、所屬帳號、已確認經歷識別碼
 title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0 CHECK(done IN (0,1)) -- 定義標題、待辦完成狀態（不代表行動貢獻）
);

CREATE TABLE users ( -- 定義帳號與個人介紹
 id TEXT PRIMARY KEY, status TEXT NOT NULL CHECK(status IN ('guest','registered')), -- 定義固定識別碼、資料狀態
 username TEXT UNIQUE, password_hash TEXT, name TEXT NOT NULL DEFAULT '', bio TEXT NOT NULL DEFAULT '', -- 定義本機帳號名稱、password_hash、顯示稱呼、自我介紹
 timezone TEXT NOT NULL DEFAULT 'Asia/Taipei', hatched_at TEXT, created_at TEXT NOT NULL -- 定義IANA 時區、hatched_at、建立時間
);

CREATE INDEX experiences_owner_idx ON experiences(owner_id);
CREATE INDEX goals_owner_idx ON goals(owner_id);
CREATE INDEX interactions_owner_time ON interaction_events(owner_id,occurred_at);
CREATE INDEX mentions_person ON experience_mentions(person_id,status,experience_id);
CREATE INDEX participants_person ON experience_participants(person_id,experience_id);
CREATE INDEX pending_goal_idx ON pending_contributions(owner_id,goal_id);
CREATE INDEX session_owner_idx ON sessions(owner_id);
CREATE INDEX stories_owner_review ON experience_stories(owner_id,reviewed,available);
CREATE INDEX story_history_source ON story_history(experience_id,created_at);
