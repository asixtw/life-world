-- PostgreSQL 候選草案：不是已實作 migration，未在 PostgreSQL 執行。

-- 只建立 lw_core_draft；不可對正式 DB 直接套用。無資料匯入／登入切換／RLS／刪除政策。

-- ID 保留 text；PK 將隱含 NOT NULL。數量 numeric 不指定 typmod，輸入限制仍由 API 驗證。

-- JSONB、boolean、時間與 date 轉換須先做 preflight。新增兩個 audit_seq 取代 rowid 排序。

BEGIN;

CREATE SCHEMA lw_core_draft;

CREATE TABLE lw_core_draft."actions" (
  "id" text,
  "goal_id" text NOT NULL,
  "owner_id" text NOT NULL,
  "title" text NOT NULL,
  "unit" text NOT NULL,
  "target" numeric NOT NULL,
  "level" bigint NOT NULL,
  "weekdays" jsonb NOT NULL,
  "position" bigint NOT NULL,
  "per_occurrence" numeric NOT NULL DEFAULT '1',
  "schedule_dates" jsonb,
  "cycle" text NOT NULL DEFAULT 'month',
  "target_is_derived" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("id"),
  CHECK("level" BETWEEN 1 AND 3),
  CHECK("cycle" IN ('month','week'))
);

CREATE TABLE lw_core_draft."completions" (
  "id" text,
  "owner_id" text NOT NULL,
  "goal_id" text NOT NULL,
  "evidence_ids" jsonb NOT NULL,
  "reflection" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  UNIQUE ("goal_id")
);

CREATE TABLE lw_core_draft."contributions" (
  "id" text,
  "owner_id" text NOT NULL,
  "experience_id" text NOT NULL,
  "action_id" text NOT NULL,
  "quantity" numeric NOT NULL,
  PRIMARY KEY ("id"),
  UNIQUE ("experience_id", "action_id")
);

CREATE TABLE lw_core_draft."draft_stories" (
  "draft_id" text,
  "payload" jsonb NOT NULL,
  PRIMARY KEY ("draft_id")
);

CREATE TABLE lw_core_draft."drafts" (
  "id" text,
  "owner_id" text NOT NULL,
  "goal_id" text,
  "person_id" text,
  "raw_text" text NOT NULL,
  "occurred_at" timestamptz NOT NULL,
  "contributions" jsonb NOT NULL,
  "status" text NOT NULL,
  "revision" bigint NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CHECK("status" IN ('draft','confirmed'))
);

CREATE TABLE lw_core_draft."evidence" (
  "id" text,
  "owner_id" text NOT NULL,
  "goal_id" text NOT NULL,
  "filename" text NOT NULL,
  "mime" text NOT NULL,
  "digest" text NOT NULL,
  "content" bytea NOT NULL,
  "size" bigint NOT NULL,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  UNIQUE ("owner_id", "goal_id", "digest")
);

CREATE TABLE lw_core_draft."experience_mentions" (
  "id" text,
  "owner_id" text NOT NULL,
  "experience_id" text NOT NULL,
  "name" text NOT NULL,
  "start" bigint NOT NULL,
  "end" bigint NOT NULL,
  "status" text NOT NULL DEFAULT 'unmatched',
  "person_id" text,
  "revision" bigint NOT NULL DEFAULT 1,
  PRIMARY KEY ("id"),
  UNIQUE ("experience_id", "start", "end"),
  CHECK("start">=0),
  CHECK("end">"start"),
  CHECK("status" IN ('unmatched','matched','rejected')),
  CHECK(("status"='matched' AND "person_id" IS NOT NULL) OR ("status"<>'matched' AND "person_id" IS NULL))
);

CREATE TABLE lw_core_draft."experience_participants" (
  "experience_id" text NOT NULL,
  "person_id" text NOT NULL,
  "interacted" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("experience_id", "person_id")
);

CREATE TABLE lw_core_draft."experience_stories" (
  "experience_id" text,
  "owner_id" text NOT NULL,
  "title" text NOT NULL DEFAULT '',
  "reviewed" boolean NOT NULL DEFAULT false,
  "available" boolean NOT NULL DEFAULT true,
  "revision" bigint NOT NULL DEFAULT 1,
  PRIMARY KEY ("experience_id")
);

CREATE TABLE lw_core_draft."experiences" (
  "id" text,
  "owner_id" text NOT NULL,
  "draft_id" text NOT NULL,
  "goal_id" text,
  "person_id" text,
  "raw_text" text NOT NULL,
  "summary" text NOT NULL,
  "occurred_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  UNIQUE ("draft_id")
);

CREATE TABLE lw_core_draft."fact_sources" (
  "fact_id" text NOT NULL,
  "experience_id" text NOT NULL,
  "evidence_type" text NOT NULL,
  "revoked_at" timestamptz,
  PRIMARY KEY ("fact_id", "experience_id")
);

CREATE TABLE lw_core_draft."goal_reviews" (
  "id" text,
  "owner_id" text NOT NULL,
  "goal_id" text NOT NULL,
  "decision" text NOT NULL,
  "previous_state" jsonb NOT NULL,
  "new_state" jsonb NOT NULL,
  "reflection" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  audit_seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE
);

CREATE TABLE lw_core_draft."goals" (
  "id" text,
  "owner_id" text NOT NULL,
  "title" text NOT NULL,
  "outcome" text NOT NULL,
  "status" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  "completed_at" timestamptz,
  "reflection" text NOT NULL DEFAULT '',
  "start_date" date,
  "deadline" date,
  "schedule_timezone" text,
  "revision" bigint NOT NULL DEFAULT 1,
  "ended_at" timestamptz,
  "end_reason" text,
  PRIMARY KEY ("id"),
  CHECK("status" IN ('active','completed')),
  CHECK("end_reason" IN ('early_end','expired'))
);

CREATE TABLE lw_core_draft."habit_quantity_versions" (
  "action_id" text NOT NULL,
  "effective_from" date NOT NULL,
  "quantity" numeric NOT NULL,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("action_id", "effective_from")
);

CREATE TABLE lw_core_draft."interaction_events" (
  "id" text,
  "owner_id" text NOT NULL,
  "kind" text NOT NULL,
  "occurred_at" timestamptz NOT NULL,
  "revision" bigint NOT NULL DEFAULT 1,
  PRIMARY KEY ("id"),
  CHECK("kind" IN ('in_person','call','message','other','unknown'))
);

CREATE TABLE lw_core_draft."interaction_experiences" (
  "experience_id" text,
  "event_id" text NOT NULL,
  PRIMARY KEY ("experience_id")
);

CREATE TABLE lw_core_draft."interaction_people" (
  "event_id" text NOT NULL,
  "person_id" text NOT NULL,
  PRIMARY KEY ("event_id", "person_id")
);

CREATE TABLE lw_core_draft."note_sources" (
  "note_id" text NOT NULL,
  "experience_id" text NOT NULL,
  PRIMARY KEY ("note_id", "experience_id")
);

CREATE TABLE lw_core_draft."notes" (
  "id" text,
  "owner_id" text NOT NULL,
  "person_id" text,
  "kind" text NOT NULL,
  "title" text NOT NULL,
  "content" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CHECK("kind" IN ('preparation','simulation','message'))
);

CREATE TABLE lw_core_draft."pending_contributions" (
  "id" text,
  "owner_id" text NOT NULL,
  "goal_id" text NOT NULL,
  "experience_id" text NOT NULL,
  "action_id" text NOT NULL,
  "quantity" numeric NOT NULL,
  "status" text NOT NULL DEFAULT 'pending',
  "accepted_quantity" numeric,
  "accepted_at" timestamptz,
  PRIMARY KEY ("id"),
  UNIQUE ("experience_id", "action_id"),
  CHECK("status" IN ('pending','accepted','unapplied'))
);

CREATE TABLE lw_core_draft."people" (
  "id" text,
  "owner_id" text NOT NULL,
  "name" text NOT NULL,
  "role" text NOT NULL DEFAULT '',
  "notes" text NOT NULL DEFAULT '',
  "created_at" timestamptz NOT NULL,
  "roles" jsonb NOT NULL DEFAULT '[]'::jsonb,
  "tags" jsonb NOT NULL DEFAULT '[]'::jsonb,
  "category" text NOT NULL DEFAULT 'other',
  "followed" boolean NOT NULL DEFAULT false,
  "revision" bigint NOT NULL DEFAULT 1,
  "common_context" text NOT NULL DEFAULT '',
  PRIMARY KEY ("id")
);

CREATE TABLE lw_core_draft."person_connections" (
  "id" text,
  "owner_id" text NOT NULL,
  "person_a" text NOT NULL,
  "person_b" text NOT NULL,
  "label" text NOT NULL,
  "source_experience_ids" jsonb NOT NULL,
  PRIMARY KEY ("id"),
  UNIQUE ("person_a", "person_b")
);

CREATE TABLE lw_core_draft."person_facts" (
  "id" text,
  "owner_id" text NOT NULL,
  "person_id" text NOT NULL,
  "dimension" text NOT NULL,
  "value" text NOT NULL,
  "normalized_value" text NOT NULL,
  "description" text NOT NULL,
  "status" text NOT NULL,
  "conflict_group" text,
  "revision" bigint NOT NULL DEFAULT 1,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  UNIQUE ("person_id", "dimension", "normalized_value"),
  CHECK("dimension" IN ('interests','food','skills','habits')),
  CHECK("status" IN ('confirmed','conflict','archived','unavailable'))
);

CREATE TABLE lw_core_draft."person_goals" (
  "person_id" text NOT NULL,
  "goal_id" text NOT NULL,
  "owner_id" text NOT NULL,
  "label" text NOT NULL DEFAULT '',
  PRIMARY KEY ("person_id", "goal_id")
);

CREATE TABLE lw_core_draft."requests" (
  "owner_id" text NOT NULL,
  "operation" text NOT NULL,
  "request_id" text NOT NULL,
  "fingerprint" text NOT NULL,
  "response" jsonb NOT NULL,
  PRIMARY KEY ("owner_id", "operation", "request_id")
);

CREATE TABLE lw_core_draft."reward_ledger" (
  "id" text,
  "owner_id" text NOT NULL,
  "experience_id" text NOT NULL,
  "points" bigint NOT NULL,
  "rule_version" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  UNIQUE ("experience_id"),
  CHECK("points">0)
);

CREATE TABLE lw_core_draft."schema_migrations" (
  "version" text,
  PRIMARY KEY ("version")
);

CREATE TABLE lw_core_draft."sessions" (
  "token_hash" text,
  "owner_id" text NOT NULL,
  "csrf_token" text NOT NULL,
  "expires_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("token_hash")
);

CREATE TABLE lw_core_draft."story_history" (
  "id" text,
  "owner_id" text NOT NULL,
  "experience_id" text NOT NULL,
  "action" text NOT NULL,
  "before_json" jsonb NOT NULL,
  "after_json" jsonb NOT NULL,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  audit_seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE
);

CREATE TABLE lw_core_draft."tasks" (
  "id" text,
  "owner_id" text NOT NULL,
  "experience_id" text NOT NULL,
  "title" text NOT NULL,
  "done" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("id")
);

CREATE TABLE lw_core_draft."users" (
  "id" text,
  "status" text NOT NULL,
  "username" text,
  "password_hash" text,
  "name" text NOT NULL DEFAULT '',
  "bio" text NOT NULL DEFAULT '',
  "timezone" text NOT NULL DEFAULT 'Asia/Taipei',
  "hatched_at" timestamptz,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  UNIQUE ("username"),
  CHECK("status" IN ('guest','registered'))
);

ALTER TABLE lw_core_draft."actions" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."actions" ADD FOREIGN KEY ("goal_id") REFERENCES lw_core_draft."goals" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."completions" ADD FOREIGN KEY ("goal_id") REFERENCES lw_core_draft."goals" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."completions" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."contributions" ADD FOREIGN KEY ("action_id") REFERENCES lw_core_draft."actions" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."contributions" ADD FOREIGN KEY ("experience_id") REFERENCES lw_core_draft."experiences" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."contributions" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."draft_stories" ADD FOREIGN KEY ("draft_id") REFERENCES lw_core_draft."drafts" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."drafts" ADD FOREIGN KEY ("person_id") REFERENCES lw_core_draft."people" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."drafts" ADD FOREIGN KEY ("goal_id") REFERENCES lw_core_draft."goals" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."drafts" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."evidence" ADD FOREIGN KEY ("goal_id") REFERENCES lw_core_draft."goals" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."evidence" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."experience_mentions" ADD FOREIGN KEY ("person_id") REFERENCES lw_core_draft."people" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."experience_mentions" ADD FOREIGN KEY ("experience_id") REFERENCES lw_core_draft."experience_stories" ("experience_id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."experience_mentions" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

CREATE INDEX "mentions_person" ON lw_core_draft."experience_mentions" ("person_id", "status", "experience_id");

ALTER TABLE lw_core_draft."experience_participants" ADD FOREIGN KEY ("person_id") REFERENCES lw_core_draft."people" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."experience_participants" ADD FOREIGN KEY ("experience_id") REFERENCES lw_core_draft."experience_stories" ("experience_id") ON UPDATE NO ACTION ON DELETE NO ACTION;

CREATE INDEX "participants_person" ON lw_core_draft."experience_participants" ("person_id", "experience_id");

ALTER TABLE lw_core_draft."experience_stories" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."experience_stories" ADD FOREIGN KEY ("experience_id") REFERENCES lw_core_draft."experiences" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

CREATE INDEX "stories_owner_review" ON lw_core_draft."experience_stories" ("owner_id", "reviewed", "available");

ALTER TABLE lw_core_draft."experiences" ADD FOREIGN KEY ("person_id") REFERENCES lw_core_draft."people" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."experiences" ADD FOREIGN KEY ("goal_id") REFERENCES lw_core_draft."goals" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."experiences" ADD FOREIGN KEY ("draft_id") REFERENCES lw_core_draft."drafts" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."experiences" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

CREATE INDEX "experiences_owner_idx" ON lw_core_draft."experiences" ("owner_id");

ALTER TABLE lw_core_draft."fact_sources" ADD FOREIGN KEY ("experience_id") REFERENCES lw_core_draft."experiences" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."fact_sources" ADD FOREIGN KEY ("fact_id") REFERENCES lw_core_draft."person_facts" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."goal_reviews" ADD FOREIGN KEY ("goal_id") REFERENCES lw_core_draft."goals" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."goal_reviews" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."goals" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

CREATE INDEX "goals_owner_idx" ON lw_core_draft."goals" ("owner_id");

ALTER TABLE lw_core_draft."habit_quantity_versions" ADD FOREIGN KEY ("action_id") REFERENCES lw_core_draft."actions" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."interaction_events" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

CREATE INDEX "interactions_owner_time" ON lw_core_draft."interaction_events" ("owner_id", "occurred_at");

ALTER TABLE lw_core_draft."interaction_experiences" ADD FOREIGN KEY ("event_id") REFERENCES lw_core_draft."interaction_events" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."interaction_experiences" ADD FOREIGN KEY ("experience_id") REFERENCES lw_core_draft."experiences" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."interaction_people" ADD FOREIGN KEY ("person_id") REFERENCES lw_core_draft."people" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."interaction_people" ADD FOREIGN KEY ("event_id") REFERENCES lw_core_draft."interaction_events" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."note_sources" ADD FOREIGN KEY ("experience_id") REFERENCES lw_core_draft."experiences" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."note_sources" ADD FOREIGN KEY ("note_id") REFERENCES lw_core_draft."notes" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."notes" ADD FOREIGN KEY ("person_id") REFERENCES lw_core_draft."people" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."notes" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."pending_contributions" ADD FOREIGN KEY ("action_id") REFERENCES lw_core_draft."actions" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."pending_contributions" ADD FOREIGN KEY ("experience_id") REFERENCES lw_core_draft."experiences" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."pending_contributions" ADD FOREIGN KEY ("goal_id") REFERENCES lw_core_draft."goals" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."pending_contributions" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

CREATE INDEX "pending_goal_idx" ON lw_core_draft."pending_contributions" ("owner_id", "goal_id");

ALTER TABLE lw_core_draft."people" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."person_connections" ADD FOREIGN KEY ("person_b") REFERENCES lw_core_draft."people" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."person_connections" ADD FOREIGN KEY ("person_a") REFERENCES lw_core_draft."people" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."person_connections" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."person_facts" ADD FOREIGN KEY ("person_id") REFERENCES lw_core_draft."people" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."person_facts" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."person_goals" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."person_goals" ADD FOREIGN KEY ("goal_id") REFERENCES lw_core_draft."goals" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."person_goals" ADD FOREIGN KEY ("person_id") REFERENCES lw_core_draft."people" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."requests" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."reward_ledger" ADD FOREIGN KEY ("experience_id") REFERENCES lw_core_draft."experiences" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."reward_ledger" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."sessions" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

CREATE INDEX "session_owner_idx" ON lw_core_draft."sessions" ("owner_id");

ALTER TABLE lw_core_draft."story_history" ADD FOREIGN KEY ("experience_id") REFERENCES lw_core_draft."experience_stories" ("experience_id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."story_history" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

CREATE INDEX "story_history_source" ON lw_core_draft."story_history" ("experience_id", "created_at");

ALTER TABLE lw_core_draft."tasks" ADD FOREIGN KEY ("experience_id") REFERENCES lw_core_draft."experiences" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

ALTER TABLE lw_core_draft."tasks" ADD FOREIGN KEY ("owner_id") REFERENCES lw_core_draft."users" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;

-- 候選強化：先核對／人工處理舊多目標；active 且未 ended 包含到期待回顧。

CREATE UNIQUE INDEX one_open_goal_per_owner ON lw_core_draft.goals(owner_id) WHERE status='active' AND ended_at IS NULL;

COMMIT;
