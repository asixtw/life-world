-- S1：AI 生成紀錄、私人作品與作品版本。只供隔離本機 SQLite 開發；不代表正式留存政策已核准。
-- 生成內容不寫入 people／person_facts／experiences／experience_stories／reward_ledger，與真實紀錄分域保存。
-- module／kind 由應用程式白名單驗證，資料庫不寫死，以便後續模組擴充時不必重建表。
CREATE TABLE ai_generations ( -- 每次生成請求的預留、結果與用量；原稿保存在 output_json
 id TEXT PRIMARY KEY,
 owner_id TEXT NOT NULL REFERENCES users(id),
 module TEXT NOT NULL CHECK(length(module) BETWEEN 1 AND 64),
 request_id TEXT NOT NULL CHECK(length(request_id) BETWEEN 1 AND 128),
 fingerprint TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed','interrupted')),
 provider TEXT NOT NULL,
 provider_kind TEXT NOT NULL CHECK(provider_kind IN ('fake','live')), -- fake 必須在畫面標示為測試用假回應
 model TEXT NOT NULL,
 model_version TEXT,
 prompt_id TEXT NOT NULL,
 prompt_version TEXT NOT NULL,
 prompt_sha256 TEXT NOT NULL,
 params_json TEXT NOT NULL,
 input_json TEXT NOT NULL, -- 玩家明確輸入的虛構設定，不含真人經歷或人物事實
 output_json TEXT, -- AI 原稿；失敗或逾時為 NULL
 error_code TEXT,
 input_tokens INTEGER CHECK(input_tokens IS NULL OR input_tokens>=0),
 output_tokens INTEGER CHECK(output_tokens IS NULL OR output_tokens>=0),
 cost_status TEXT NOT NULL CHECK(cost_status IN ('known','unknown','not_billable')), -- 未知費用不寫成 0
 cost_microusd INTEGER CHECK(cost_microusd IS NULL OR cost_microusd>=0),
 latency_ms INTEGER CHECK(latency_ms IS NULL OR latency_ms>=0),
 provider_request_id TEXT,
 created_at TEXT NOT NULL,
 finished_at TEXT,
 UNIQUE(owner_id, module, request_id) -- 同一提交代碼只呼叫一次 Provider
);
CREATE INDEX ai_generations_owner_created ON ai_generations(owner_id, created_at);
CREATE INDEX ai_generations_created ON ai_generations(created_at);

CREATE TABLE works ( -- 使用者明確保存的私人作品；目前只開放 character_card
 id TEXT PRIMARY KEY,
 owner_id TEXT NOT NULL REFERENCES users(id),
 kind TEXT NOT NULL CHECK(length(kind) BETWEEN 1 AND 64),
 title TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('active','archived')),
 current_version INTEGER NOT NULL CHECK(current_version>=1),
 revision INTEGER NOT NULL CHECK(revision>=1),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX works_owner_updated ON works(owner_id, updated_at);

CREATE TABLE work_versions ( -- 只新增不改寫；AI 原稿、AI 修改稿與人工稿以 origin 區分
 work_id TEXT NOT NULL REFERENCES works(id),
 owner_id TEXT NOT NULL REFERENCES users(id),
 version_no INTEGER NOT NULL CHECK(version_no>=1),
 parent_version INTEGER CHECK(parent_version IS NULL OR parent_version>=1),
 origin TEXT NOT NULL CHECK(origin IN ('ai','ai_edited','human')),
 content_schema TEXT NOT NULL,
 content_json TEXT NOT NULL,
 generation_id TEXT REFERENCES ai_generations(id),
 created_at TEXT NOT NULL,
 PRIMARY KEY(work_id, version_no)
);
