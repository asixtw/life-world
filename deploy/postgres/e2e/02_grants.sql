-- E2E 專用：只套用在 life_world_e2e；最小權限沿用已驗證 30/17/6 表矩陣，不改 dev。
BEGIN;
DO $guard$
BEGIN
  IF current_database()<>'life_world_e2e' OR
     shobj_description((SELECT oid FROM pg_database WHERE datname=current_database()),'pg_database')
       IS DISTINCT FROM 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1' THEN
    RAISE EXCEPTION 'Refusing non-E2E database';
  END IF;
  IF current_setting('server_version_num')::int<>180006 THEN RAISE EXCEPTION 'PostgreSQL 18.6 required'; END IF;
END $guard$;
SET LOCAL ROLE lw_e2e_owner;
REVOKE ALL ON SCHEMA lw_core_draft FROM PUBLIC;

GRANT USAGE ON SCHEMA lw_core_draft TO lw_e2e_app;
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
  lw_core_draft.tasks, lw_core_draft.users TO lw_e2e_app;
GRANT UPDATE ON TABLE
  lw_core_draft.actions, lw_core_draft.draft_stories, lw_core_draft.drafts,
  lw_core_draft.experience_mentions, lw_core_draft.experience_stories,
  lw_core_draft.fact_sources, lw_core_draft.goals, lw_core_draft.habit_quantity_versions,
  lw_core_draft.interaction_events, lw_core_draft.interaction_experiences,
  lw_core_draft.pending_contributions, lw_core_draft.people,
  lw_core_draft.person_connections, lw_core_draft.person_facts,
  lw_core_draft.person_goals, lw_core_draft.tasks, lw_core_draft.users TO lw_e2e_app;
GRANT DELETE ON TABLE
  lw_core_draft.draft_stories, lw_core_draft.experience_mentions,
  lw_core_draft.experience_participants, lw_core_draft.interaction_events,
  lw_core_draft.interaction_people, lw_core_draft.sessions TO lw_e2e_app;
REVOKE ALL ON TABLE lw_core_draft.schema_migrations FROM lw_e2e_app;
-- PG identity 自動產值與直接呼叫 nextval 是不同權限路徑；由整合測試驗證最小權限。
-- 本 App 不直接呼叫 nextval／setval，不授予 Sequence SELECT／UPDATE／USAGE。
REVOKE ALL ON SEQUENCE lw_core_draft.goal_reviews_audit_seq_seq,
  lw_core_draft.story_history_audit_seq_seq FROM lw_e2e_app;
COMMIT;
