-- REVIEW ONLY：先在life_world_alpha建立31表核心，再由Alpha物件owner套用本增量。
-- 不建立DB／角色、不授權dev、不在App啟動執行。DBA逐項批准後才可套用。
BEGIN;
DO $$ BEGIN
 IF current_database() <> 'life_world_alpha' THEN
  RAISE EXCEPTION 'Alpha increment requires life_world_alpha';
 END IF;
END $$;
CREATE TABLE lw_core_draft.auth_rate_buckets (
 scope text NOT NULL CHECK(scope IN ('login_account_fail','login_source_attempt','guest_source_create','login_global_attempt','alpha_worlds_total','alpha_worlds_daily','alpha_writes_total','alpha_owner_writes')),
 key_hash text NOT NULL CHECK(key_hash ~ '^[0-9a-f]{64}$'),
 window_started_at timestamptz NOT NULL,
 attempts bigint NOT NULL DEFAULT 0 CHECK(attempts>=0),
 PRIMARY KEY(scope,key_hash)
);
CREATE INDEX auth_rate_buckets_window ON lw_core_draft.auth_rate_buckets(window_started_at);
COMMIT;
