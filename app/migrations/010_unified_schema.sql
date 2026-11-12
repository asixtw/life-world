-- 010 Unified Schema（SQLite 等價版，只供本機開發與自動測試）。
-- 對應 PostgreSQL 的 010_alpha_unification.sql（Codex 候選，目標 42 表／80 外鍵）：相同的表名、欄名、預設值與檢查規則。
-- SQLite 的限制與替代：
-- * ALTER TABLE 不能加表級 UNIQUE 或複合外鍵 → 以唯一索引作為複合外鍵的目標；
--   people／person_connections／works 新增欄位的「同帳號」檢查在 PG 由複合外鍵保證，SQLite 由服務端檢查。
-- * 時間欄沿用 TEXT（ISO 8601）；布林沿用 INTEGER 0／1；jsonb 以 TEXT 加 json_valid 檢查。
-- * relationship_memory_*（009）是 SQLite 專有功能表，不在 PG 010 範圍內，維持原樣。

-- 外部身分與訪客清除收據：PG（Alpha）已有，SQLite 補齊，讓訪客清除與 Google 綁定的測試行為一致。
CREATE TABLE IF NOT EXISTS external_identities (
    provider TEXT NOT NULL CHECK (provider = 'google'),
    issuer TEXT NOT NULL CHECK (issuer = 'https://accounts.google.com'),
    subject TEXT NOT NULL CHECK (length(subject) BETWEEN 1 AND 255),
    owner_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    PRIMARY KEY (provider, issuer, subject)
);
CREATE INDEX IF NOT EXISTS external_identities_owner ON external_identities(owner_id);

-- 收據沒有 owner 外鍵（與 Alpha 相同）：帳號清除後收據仍保留。
CREATE TABLE IF NOT EXISTS guest_abandonments (
    owner_id TEXT PRIMARY KEY,
    abandoned_at TEXT NOT NULL,
    purge_after TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','retry','completed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error_code TEXT,
    completed_at TEXT,
    media_state TEXT NOT NULL DEFAULT 'pending' CHECK (media_state IN ('pending','retry','done')),
    media_attempts INTEGER NOT NULL DEFAULT 0 CHECK (media_attempts >= 0)
);

-- 人物：真實／虛構兩大類；歷史人物屬真實，自創人物屬虛構。舊資料為 real＋legacy（未分類，不代表已驗證）。
ALTER TABLE people ADD COLUMN person_type TEXT NOT NULL DEFAULT 'real' CHECK (person_type IN ('real','fictional'));
ALTER TABLE people ADD COLUMN person_subtype TEXT CHECK (
    person_subtype IS NULL
    OR (person_subtype = 'historical' AND person_type = 'real')
    OR (person_subtype = 'original' AND person_type = 'fictional'));
ALTER TABLE people ADD COLUMN aliases TEXT NOT NULL DEFAULT '[]' CHECK (
    json_valid(aliases) AND json_type(aliases) = 'array' AND json_array_length(aliases) <= 20);
ALTER TABLE people ADD COLUMN description TEXT NOT NULL DEFAULT '' CHECK (length(description) <= 2000);
ALTER TABLE people ADD COLUMN origin_type TEXT NOT NULL DEFAULT 'legacy' CHECK (origin_type IN ('legacy','manual','imported','ai_generated'));
ALTER TABLE people ADD COLUMN status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived'));
CREATE UNIQUE INDEX IF NOT EXISTS people_unification_id_owner_uq ON people(id, owner_id);

-- 人物關係：每對一列；多種關係存在陣列；新增樂觀鎖版本。
ALTER TABLE person_connections ADD COLUMN relation_types TEXT NOT NULL DEFAULT '[]' CHECK (
    json_valid(relation_types) AND json_type(relation_types) = 'array' AND json_array_length(relation_types) <= 10);
ALTER TABLE person_connections ADD COLUMN description TEXT NOT NULL DEFAULT '' CHECK (length(description) <= 2000);
ALTER TABLE person_connections ADD COLUMN confirmation_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK (
    confirmation_status IN ('unreviewed','proposed','confirmed','rejected','archived'));
ALTER TABLE person_connections ADD COLUMN revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1);
CREATE UNIQUE INDEX IF NOT EXISTS person_connections_id_owner_uq ON person_connections(id, owner_id);

-- 角色卡可選擇連到一位人物（一人多卡）。
ALTER TABLE works ADD COLUMN profile_person_id TEXT REFERENCES people(id) CHECK (profile_person_id IS NULL OR kind = 'character_card');
CREATE INDEX IF NOT EXISTS works_unification_profile_person_idx ON works(owner_id, profile_person_id) WHERE profile_person_id IS NOT NULL;

-- 人物經歷的生成來源以 (id, owner_id) 連回生成紀錄。
CREATE UNIQUE INDEX IF NOT EXISTS ai_generations_id_owner_uq ON ai_generations(id, owner_id);

-- 人物經歷：獨立資料流，沒有草稿鏈、目標、積分與本人互動統計。
CREATE TABLE subject_experiences (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id),
    experience_type TEXT NOT NULL CHECK (experience_type IN ('real','historical','fictional')),
    origin_type TEXT NOT NULL CHECK (origin_type IN ('manual','imported','ai_generated')),
    title TEXT NOT NULL DEFAULT '',
    raw_text TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    occurred_at TEXT,
    occurred_precision TEXT NOT NULL DEFAULT 'unknown' CHECK (occurred_precision IN ('exact','day','month','year','unknown')),
    occurred_label TEXT NOT NULL DEFAULT '' CHECK (length(occurred_label) <= 120),
    creator_person_id TEXT,
    owner_participates INTEGER CHECK (owner_participates IS NULL OR owner_participates = 0),
    generation_id TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (length(raw_text) BETWEEN 1 AND 20000 AND length(title) <= 200 AND length(summary) <= 20000),
    CHECK ((occurred_at IS NULL) = (occurred_precision = 'unknown')),
    CHECK (origin_type <> 'ai_generated' OR generation_id IS NOT NULL),
    UNIQUE (id, owner_id),
    FOREIGN KEY (creator_person_id, owner_id) REFERENCES people(id, owner_id),
    FOREIGN KEY (generation_id, owner_id) REFERENCES ai_generations(id, owner_id)
);
CREATE INDEX subject_experiences_owner_idx ON subject_experiences(owner_id, occurred_at, id);

-- 經歷與人物：主體、參與者、被提及者分開；只有參與者可以標記直接互動。
CREATE TABLE subject_experience_people (
    subject_experience_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('subject','participant','mentioned')),
    created_at TEXT NOT NULL,
    interacted INTEGER NOT NULL DEFAULT 0 CHECK (interacted IN (0,1)),
    PRIMARY KEY (subject_experience_id, person_id, role),
    CHECK (role = 'participant' OR interacted = 0),
    FOREIGN KEY (subject_experience_id, owner_id) REFERENCES subject_experiences(id, owner_id) ON DELETE CASCADE,
    FOREIGN KEY (person_id, owner_id) REFERENCES people(id, owner_id)
);
CREATE INDEX subject_experience_people_person_idx ON subject_experience_people(owner_id, person_id, subject_experience_id);

-- 關係來源（與 PG 010 最終版相同）：我的紀錄（experience_id）或人物經歷（subject_experience_id）每列恰好一種，
-- 各自依 source_position 排序；API 仍以兩個 ID 陣列呈現。舊 source_experience_ids JSONB 只保留為切換快照。
CREATE UNIQUE INDEX IF NOT EXISTS experiences_id_owner_uq ON experiences(id, owner_id);
CREATE TABLE person_connection_experience_sources (
    connection_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    subject_experience_id TEXT,
    experience_id TEXT,
    source_position INTEGER NOT NULL DEFAULT 1 CHECK (source_position > 0),
    CHECK ((subject_experience_id IS NOT NULL) + (experience_id IS NOT NULL) = 1),
    FOREIGN KEY (connection_id, owner_id) REFERENCES person_connections(id, owner_id),
    FOREIGN KEY (subject_experience_id, owner_id) REFERENCES subject_experiences(id, owner_id),
    FOREIGN KEY (experience_id, owner_id) REFERENCES experiences(id, owner_id)
);
-- PG 用 UNIQUE NULLS NOT DISTINCT；SQLite 以 COALESCE 運算式索引達到相同效果。
CREATE UNIQUE INDEX person_connection_experience_sources_source_uq
    ON person_connection_experience_sources(connection_id, COALESCE(subject_experience_id, ''), COALESCE(experience_id, ''));
CREATE INDEX person_connection_experience_sources_subject_idx ON person_connection_experience_sources(owner_id, subject_experience_id, connection_id);
-- 與 PG 010 相同：把舊 JSONB 的我的紀錄來源依原順序重建到關聯表（position 從 1 起算）。
INSERT INTO person_connection_experience_sources(connection_id, owner_id, experience_id, source_position)
SELECT c.id, c.owner_id, j.value, j.key + 1
FROM person_connections c, json_each(c.source_experience_ids) j;
