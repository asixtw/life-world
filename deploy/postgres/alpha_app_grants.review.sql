-- REVIEW ONLY：Alpha專用DML權限，須DBA先建立並審查獨立角色／CONNECT。
-- runtime不得有DDL或限流表DELETE；sessions等既有核心流程需精確DELETE白名單。
BEGIN;
DO $$ BEGIN
 IF current_database() <> 'life_world_alpha' THEN
  RAISE EXCEPTION 'Alpha grants require life_world_alpha';
 END IF;
 IF to_regrole('lw_alpha_app') IS NULL OR to_regrole('lw_alpha_app_role') IS NULL THEN
  RAISE EXCEPTION 'Alpha roles must be created and reviewed first';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('lw_alpha_app','lw_alpha_app_role')
            AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls)) THEN
  RAISE EXCEPTION 'Privileged Alpha role rejected';
 END IF;
 IF NOT pg_has_role('lw_alpha_app', 'lw_alpha_app_role', 'MEMBER') THEN
  RAISE EXCEPTION 'Alpha membership must be reviewed first';
 END IF;
 IF to_regrole('lw_alpha_owner') IS NOT NULL AND pg_has_role('lw_alpha_app', 'lw_alpha_owner', 'MEMBER') THEN
  RAISE EXCEPTION 'Runtime must not inherit Alpha owner';
 END IF;
 IF pg_has_role('lw_alpha_app', 'lw_migration_role', 'MEMBER') THEN
  RAISE EXCEPTION 'Runtime must not inherit dev migration role';
 END IF;
 IF pg_has_role('lw_alpha_app', 'lw_app_role', 'MEMBER') THEN
  RAISE EXCEPTION 'Shared dev role membership rejected';
 END IF;
END $$;
GRANT USAGE ON SCHEMA lw_core_draft TO lw_alpha_app_role;
GRANT SELECT, INSERT ON TABLE
  lw_core_draft.actions, lw_core_draft.completions, lw_core_draft.contributions,
  lw_core_draft.draft_stories, lw_core_draft.drafts, lw_core_draft.evidence,
  lw_core_draft.experience_mentions, lw_core_draft.experience_participants,
  lw_core_draft.experience_stories, lw_core_draft.experiences, lw_core_draft.fact_sources,
  lw_core_draft.goal_reviews, lw_core_draft.goals, lw_core_draft.habit_quantity_versions,
  lw_core_draft.interaction_events, lw_core_draft.interaction_experiences,
  lw_core_draft.interaction_people, lw_core_draft.note_sources, lw_core_draft.notes,
  lw_core_draft.pending_contributions, lw_core_draft.people, lw_core_draft.person_connections,
  lw_core_draft.person_facts, lw_core_draft.person_goals, lw_core_draft.requests,
  lw_core_draft.reward_ledger, lw_core_draft.sessions, lw_core_draft.story_history,
  lw_core_draft.tasks, lw_core_draft.users TO lw_alpha_app_role;
GRANT UPDATE ON TABLE
  lw_core_draft.actions, lw_core_draft.draft_stories, lw_core_draft.drafts,
  lw_core_draft.experience_mentions, lw_core_draft.experience_stories,
  lw_core_draft.fact_sources, lw_core_draft.goals, lw_core_draft.habit_quantity_versions,
  lw_core_draft.interaction_events, lw_core_draft.interaction_experiences,
  lw_core_draft.pending_contributions, lw_core_draft.people,
  lw_core_draft.person_connections, lw_core_draft.person_facts,
  lw_core_draft.person_goals, lw_core_draft.tasks, lw_core_draft.users TO lw_alpha_app_role;
GRANT DELETE ON TABLE
  lw_core_draft.draft_stories, lw_core_draft.experience_mentions,
  lw_core_draft.experience_participants, lw_core_draft.interaction_events,
  lw_core_draft.interaction_people, lw_core_draft.sessions TO lw_alpha_app_role;
REVOKE ALL ON TABLE lw_core_draft.schema_migrations FROM lw_alpha_app_role;
-- PG identity 自動產值與直接呼叫 nextval 是不同權限路徑；由整合測試驗證最小權限。
-- 本 App 不直接呼叫 nextval／setval，不授予 Sequence SELECT／UPDATE／USAGE。
REVOKE ALL ON SEQUENCE lw_core_draft.goal_reviews_audit_seq_seq,
  lw_core_draft.story_history_audit_seq_seq FROM lw_alpha_app_role;
GRANT SELECT, INSERT, UPDATE ON TABLE lw_core_draft.auth_rate_buckets TO lw_alpha_app_role;
REVOKE DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLE lw_core_draft.auth_rate_buckets FROM lw_alpha_app_role;
COMMIT;
