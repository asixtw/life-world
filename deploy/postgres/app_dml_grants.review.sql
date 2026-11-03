-- Step 10-4 待審 SQL：只在本機合成 PG18 測試庫執行過；不可由 CI／API 自動對 GCP 執行。
-- 由物件 owner lw_migration_role 審查執行；不授予 role membership、DDL、TRUNCATE 或超級使用者。
-- CONNECT 是 database owner 的權限範圍；既有 App 已可連線，本檔不假設 schema owner 能轉授它。
BEGIN;
GRANT USAGE ON SCHEMA lw_core_draft TO lw_app_role;
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
  lw_core_draft.tasks, lw_core_draft.users TO lw_app_role;
GRANT UPDATE ON TABLE
  lw_core_draft.actions, lw_core_draft.draft_stories, lw_core_draft.drafts,
  lw_core_draft.experience_mentions, lw_core_draft.experience_stories,
  lw_core_draft.fact_sources, lw_core_draft.goals, lw_core_draft.habit_quantity_versions,
  lw_core_draft.interaction_events, lw_core_draft.interaction_experiences,
  lw_core_draft.pending_contributions, lw_core_draft.people,
  lw_core_draft.person_connections, lw_core_draft.person_facts,
  lw_core_draft.person_goals, lw_core_draft.tasks, lw_core_draft.users TO lw_app_role;
GRANT DELETE ON TABLE
  lw_core_draft.draft_stories, lw_core_draft.experience_mentions,
  lw_core_draft.experience_participants, lw_core_draft.interaction_events,
  lw_core_draft.interaction_people, lw_core_draft.sessions TO lw_app_role;
REVOKE ALL ON TABLE lw_core_draft.schema_migrations FROM lw_app_role;
-- PG identity 自動產值與直接呼叫 nextval 是不同權限路徑；由整合測試驗證最小權限。
-- 本 App 不直接呼叫 nextval／setval，不授予 Sequence SELECT／UPDATE／USAGE。
REVOKE ALL ON SEQUENCE lw_core_draft.goal_reviews_audit_seq_seq,
  lw_core_draft.story_history_audit_seq_seq FROM lw_app_role;
COMMIT;
