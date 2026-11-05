-- 僅供migration角色審查，App啟動不執行DDL；不得直接在正式CloudSQL執行。
BEGIN;
DO $$ BEGIN
 IF current_database() <> 'life_world_dev' THEN
  RAISE EXCEPTION 'Dev rate-limit increment requires life_world_dev';
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
GRANT SELECT,INSERT,UPDATE ON lw_core_draft.auth_rate_buckets TO lw_app_role;
-- 永久容量桶不可納入一般過期桶清理；runtime不具DDL或DELETE權限。
COMMIT;
