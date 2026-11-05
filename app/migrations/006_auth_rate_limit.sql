-- 共用首次起算視窗；永久容量桶不可按一般過期桶清除。
CREATE TABLE auth_rate_buckets (
 scope TEXT NOT NULL CHECK(scope IN ('login_account_fail','login_source_attempt','guest_source_create','login_global_attempt','alpha_worlds_total','alpha_worlds_daily','alpha_writes_total','alpha_owner_writes')),
 key_hash TEXT NOT NULL CHECK(length(key_hash)=64),
 window_started_at TEXT NOT NULL,
 attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts>=0),
 PRIMARY KEY(scope,key_hash)
);
CREATE INDEX auth_rate_buckets_window ON auth_rate_buckets(window_started_at);
