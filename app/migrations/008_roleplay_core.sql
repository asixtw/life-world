-- P1 生成作品中心（2026-11-08）：同意紀錄、Self Persona 一人一份、自動演出的逐段紀錄。
-- 對應 PostgreSQL 的 008a（deploy/e2e-f05/sql/12_008a_roleplay_core.sql）。SQLite 只作隔離測試工具，不是產品 Runtime。
-- 時間由應用程式寫入；段落只新增不改寫；同一作品同一段號只會有一筆（中斷恢復與重送不重複）。
CREATE TABLE data_consents ( -- 可稽核、可撤回的同意：送往 AI 前伺服器必須查得到有效紀錄
 id TEXT PRIMARY KEY,
 owner_id TEXT NOT NULL REFERENCES users(id),
 subject TEXT NOT NULL CHECK(length(subject) BETWEEN 1 AND 140),
 purpose TEXT NOT NULL CHECK(purpose IN ('ai_generation')),
 provider_scope TEXT NOT NULL CHECK(length(provider_scope) BETWEEN 1 AND 200),
 source_scope TEXT NOT NULL,
 consent_version TEXT NOT NULL CHECK(length(consent_version) BETWEEN 1 AND 40),
 granted_at TEXT NOT NULL,
 revoked_at TEXT,
 CHECK(revoked_at IS NULL OR revoked_at >= granted_at)
);
CREATE UNIQUE INDEX data_consents_one_active_uq ON data_consents(owner_id, subject, purpose) WHERE revoked_at IS NULL;
CREATE INDEX data_consents_owner_idx ON data_consents(owner_id, subject, granted_at);

CREATE UNIQUE INDEX works_one_active_self_persona_uq ON works(owner_id) WHERE kind = 'self_persona' AND status = 'active';

CREATE TABLE session_turns ( -- 自動演出的逐段紀錄（控制器寫入）
 id TEXT PRIMARY KEY,
 owner_id TEXT NOT NULL REFERENCES users(id),
 work_id TEXT NOT NULL REFERENCES works(id),
 turn_no INTEGER NOT NULL CHECK(turn_no >= 1),
 request_id TEXT NOT NULL CHECK(length(request_id) BETWEEN 1 AND 128),
 actor TEXT NOT NULL CHECK(actor IN ('controller')),
 speaker_ref TEXT NOT NULL CHECK(length(speaker_ref) BETWEEN 1 AND 64),
 segment_kind TEXT NOT NULL CHECK(segment_kind IN ('dialogue','action','narration')),
 witnesses TEXT NOT NULL,
 input_json TEXT NOT NULL,
 output_json TEXT NOT NULL,
 generation_id TEXT REFERENCES ai_generations(id),
 state_after_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 UNIQUE(work_id, turn_no),
 UNIQUE(owner_id, work_id, request_id)
);
CREATE INDEX session_turns_owner_work_idx ON session_turns(owner_id, work_id, turn_no);
