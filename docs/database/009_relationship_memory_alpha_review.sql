-- REVIEW ONLY：Alpha完整Metadata/Owner/ACL受控Restore Gate尚未PASS，不執行。
-- 增量新增兩表；不重跑02–08、不清除來源資料、不給Runtime DDL。
BEGIN;
DO $guard$ BEGIN
 IF current_database()<>'life_world_alpha' OR current_setting('server_version_num')::int/10000<>18 THEN RAISE EXCEPTION 'STOP wrong Alpha target'; END IF;
 IF (SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()) IS DISTINCT FROM 'LIFEWORLD_PUBLIC_ALPHA_GCP144_V1' THEN RAISE EXCEPTION 'STOP missing Alpha marker'; END IF;
 IF to_regclass('lw_core_draft.relationship_features') IS NOT NULL OR to_regclass('lw_core_draft.relationship_memory_preferences') IS NOT NULL THEN RAISE EXCEPTION 'STOP migration already present or partial'; END IF;
END $guard$;
SET LOCAL ROLE lw_alpha_owner;
SET LOCAL search_path=lw_core_draft,pg_catalog;
CREATE TABLE relationship_memory_preferences (
 owner_id TEXT PRIMARY KEY REFERENCES users(id), enabled BOOLEAN NOT NULL DEFAULT FALSE,
 preferences TEXT NOT NULL DEFAULT '{}', revision INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE relationship_features (
 owner_id TEXT NOT NULL REFERENCES users(id), subject_type TEXT NOT NULL CHECK(subject_type IN ('user','person','relationship','context')),
 subject_id TEXT NOT NULL, feature_key TEXT NOT NULL, value TEXT NOT NULL, source_refs TEXT NOT NULL,
 context_scope TEXT NOT NULL, epistemic_status TEXT NOT NULL, model_version TEXT NOT NULL,
 profile_version INTEGER NOT NULL, revocation_state TEXT NOT NULL CHECK(revocation_state IN ('active','withdrawn')),
 PRIMARY KEY(owner_id,subject_type,subject_id,feature_key)
);

GRANT SELECT,INSERT,UPDATE,DELETE ON relationship_memory_preferences,relationship_features TO lw_alpha_app_role;
-- 收據需在隔離PG18結構／權限驗收後固定原始SQL SHA，現版不得執行。
ROLLBACK;
