-- 2026-10-29 SQLite 純結構參考，不是正式 migration。

-- 不含使用者資料或 migration 版本列；schema_migrations 為空。

-- 不可將此參考空庫直接交給 App 啟動，否則會重跑既有建表。

PRAGMA foreign_keys=ON;

BEGIN;

CREATE TABLE schema_migrations (version TEXT PRIMARY KEY);

CREATE TABLE users (
 id TEXT PRIMARY KEY, status TEXT NOT NULL CHECK(status IN ('guest','registered')),
 username TEXT UNIQUE, password_hash TEXT, name TEXT NOT NULL DEFAULT '', bio TEXT NOT NULL DEFAULT '',
 timezone TEXT NOT NULL DEFAULT 'Asia/Taipei', hatched_at TEXT, created_at TEXT NOT NULL
);

CREATE TABLE goals (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), title TEXT NOT NULL,
 outcome TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','completed')),
 created_at TEXT NOT NULL, completed_at TEXT, reflection TEXT NOT NULL DEFAULT ''
, start_date TEXT, deadline TEXT, schedule_timezone TEXT, revision INTEGER NOT NULL DEFAULT 1, ended_at TEXT, end_reason TEXT CHECK(end_reason IN ('early_end','expired')));

CREATE TABLE interaction_events (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),
 kind TEXT NOT NULL CHECK(kind IN ('in_person','call','message','other','unknown')),
 occurred_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE people (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), name TEXT NOT NULL,
 role TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
, roles TEXT NOT NULL DEFAULT '[]', tags TEXT NOT NULL DEFAULT '[]', category TEXT NOT NULL DEFAULT 'other', followed INTEGER NOT NULL DEFAULT 0 CHECK(followed IN (0,1)), revision INTEGER NOT NULL DEFAULT 1, common_context TEXT NOT NULL DEFAULT '');

CREATE TABLE requests (
 owner_id TEXT NOT NULL REFERENCES users(id), operation TEXT NOT NULL, request_id TEXT NOT NULL,
 fingerprint TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(owner_id, operation, request_id)
);

CREATE TABLE sessions (
 token_hash TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),
 csrf_token TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL
);

CREATE TABLE actions (
 id TEXT PRIMARY KEY, goal_id TEXT NOT NULL REFERENCES goals(id), owner_id TEXT NOT NULL REFERENCES users(id),
 title TEXT NOT NULL, unit TEXT NOT NULL, target TEXT NOT NULL,
 level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 3), weekdays TEXT NOT NULL, position INTEGER NOT NULL
, per_occurrence TEXT NOT NULL DEFAULT '1', schedule_dates TEXT, cycle TEXT NOT NULL DEFAULT 'month' CHECK(cycle IN ('month','week')), target_is_derived INTEGER NOT NULL DEFAULT 0);

CREATE TABLE completions (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT NOT NULL UNIQUE REFERENCES goals(id),
 evidence_ids TEXT NOT NULL, reflection TEXT NOT NULL, created_at TEXT NOT NULL
);

CREATE TABLE drafts (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT REFERENCES goals(id),
 person_id TEXT REFERENCES people(id), raw_text TEXT NOT NULL, occurred_at TEXT NOT NULL,
 contributions TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('draft','confirmed')),
 revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE TABLE evidence (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT NOT NULL REFERENCES goals(id),
 filename TEXT NOT NULL, mime TEXT NOT NULL, digest TEXT NOT NULL, content BLOB NOT NULL, size INTEGER NOT NULL,
 created_at TEXT NOT NULL, UNIQUE(owner_id, goal_id, digest)
);

CREATE TABLE goal_reviews ( -- 保存期限與排程修改的前後快照。
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT NOT NULL REFERENCES goals(id), -- 回顧歸屬於同一帳號與目標。
 decision TEXT NOT NULL, previous_state TEXT NOT NULL, new_state TEXT NOT NULL, reflection TEXT NOT NULL, created_at TEXT NOT NULL -- 不覆寫歷史回顧。
);

CREATE TABLE interaction_people (
 event_id TEXT NOT NULL REFERENCES interaction_events(id), person_id TEXT NOT NULL REFERENCES people(id),
 PRIMARY KEY(event_id,person_id)
);

CREATE TABLE notes (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), person_id TEXT REFERENCES people(id),
 kind TEXT NOT NULL CHECK(kind IN ('preparation','simulation','message')), title TEXT NOT NULL,
 content TEXT NOT NULL, created_at TEXT NOT NULL
);

CREATE TABLE person_connections (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),
 person_a TEXT NOT NULL REFERENCES people(id), person_b TEXT NOT NULL REFERENCES people(id),
 label TEXT NOT NULL, source_experience_ids TEXT NOT NULL, UNIQUE(person_a,person_b)
);

CREATE TABLE person_facts (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), person_id TEXT NOT NULL REFERENCES people(id),
 dimension TEXT NOT NULL CHECK(dimension IN ('interests','food','skills','habits')),
 value TEXT NOT NULL, normalized_value TEXT NOT NULL, description TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('confirmed','conflict','archived','unavailable')),
 conflict_group TEXT, revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
 UNIQUE(person_id,dimension,normalized_value)
);

CREATE TABLE person_goals (
 person_id TEXT NOT NULL REFERENCES people(id), goal_id TEXT NOT NULL REFERENCES goals(id),
 owner_id TEXT NOT NULL REFERENCES users(id), label TEXT NOT NULL DEFAULT '',
 PRIMARY KEY(person_id,goal_id)
);

CREATE TABLE draft_stories ( -- 保存尚未確認的人物整理，不改舊草稿欄位
 draft_id TEXT PRIMARY KEY REFERENCES drafts(id), payload TEXT NOT NULL -- 以草稿識別碼與 JSON 保存未審閱角色
);

CREATE TABLE experiences (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), draft_id TEXT NOT NULL UNIQUE REFERENCES drafts(id),
 goal_id TEXT REFERENCES goals(id), person_id TEXT REFERENCES people(id), raw_text TEXT NOT NULL,
 summary TEXT NOT NULL, occurred_at TEXT NOT NULL, created_at TEXT NOT NULL
);

CREATE TABLE habit_quantity_versions (
    action_id TEXT NOT NULL REFERENCES actions(id),
    effective_from TEXT NOT NULL,
    quantity TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (action_id, effective_from)
);

CREATE TABLE contributions (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL REFERENCES experiences(id),
 action_id TEXT NOT NULL REFERENCES actions(id), quantity TEXT NOT NULL,
 UNIQUE(experience_id, action_id)
);

CREATE TABLE experience_stories ( -- 定義逐經歷的交會狀態
 experience_id TEXT PRIMARY KEY REFERENCES experiences(id), owner_id TEXT NOT NULL REFERENCES users(id), -- 保存來源與帳號
 title TEXT NOT NULL DEFAULT '', reviewed INTEGER NOT NULL DEFAULT 0 CHECK(reviewed IN (0,1)), -- 未核對的舊關聯不進探索
 available INTEGER NOT NULL DEFAULT 1 CHECK(available IN (0,1)), revision INTEGER NOT NULL DEFAULT 1 -- 提供撤回與樂觀鎖
);

CREATE TABLE fact_sources (
 fact_id TEXT NOT NULL REFERENCES person_facts(id), experience_id TEXT NOT NULL REFERENCES experiences(id),
 evidence_type TEXT NOT NULL, revoked_at TEXT, PRIMARY KEY(fact_id,experience_id)
);

CREATE TABLE interaction_experiences (
 experience_id TEXT PRIMARY KEY REFERENCES experiences(id),
 event_id TEXT NOT NULL REFERENCES interaction_events(id)
);

CREATE TABLE note_sources (
 note_id TEXT NOT NULL REFERENCES notes(id), experience_id TEXT NOT NULL REFERENCES experiences(id),
 PRIMARY KEY(note_id,experience_id)
);

CREATE TABLE pending_contributions ( -- 到期後先確認經歷，不提前計入目標。
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT NOT NULL REFERENCES goals(id), -- 權限與目標來源。
 experience_id TEXT NOT NULL REFERENCES experiences(id), action_id TEXT NOT NULL REFERENCES actions(id), quantity TEXT NOT NULL, -- 保留原始建議數量。
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','unapplied')), accepted_quantity TEXT, accepted_at TEXT, -- 人工採計歷史。
 UNIQUE(experience_id,action_id) -- 同筆經歷的同項貢獻只能待處理一次。
);

CREATE TABLE reward_ledger (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL UNIQUE REFERENCES experiences(id),
 points INTEGER NOT NULL CHECK(points>0), rule_version TEXT NOT NULL, created_at TEXT NOT NULL
);

CREATE TABLE tasks (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL REFERENCES experiences(id),
 title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0 CHECK(done IN (0,1))
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

CREATE TABLE story_history ( -- 保存人工更正、配對與展示撤回歷史
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL REFERENCES experience_stories(experience_id), -- 限制歷史所屬來源
 action TEXT NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL, created_at TEXT NOT NULL -- 保留更正前後與日期
);

CREATE INDEX mentions_person ON experience_mentions(person_id,status,experience_id);

CREATE INDEX participants_person ON experience_participants(person_id,experience_id);

CREATE INDEX stories_owner_review ON experience_stories(owner_id,reviewed,available);

CREATE INDEX experiences_owner_idx ON experiences(owner_id);

CREATE INDEX goals_owner_idx ON goals(owner_id);

CREATE INDEX interactions_owner_time ON interaction_events(owner_id,occurred_at);

CREATE INDEX pending_goal_idx ON pending_contributions(owner_id,goal_id);

CREATE INDEX session_owner_idx ON sessions(owner_id);

CREATE INDEX story_history_source ON story_history(experience_id,created_at);

COMMIT;
