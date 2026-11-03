-- 管理者在專用 DB 核對 effective privileges（含 PUBLIC／繼承影響），不輸出資料列。
-- 檢查與 PASS 同一唯讀交易：任一檢查失敗即中止交易，client 未設 ON_ERROR_STOP 也不會印出 PASS。
BEGIN READ ONLY;
DO $verify$
DECLARE
 -- 逐表白名單與 02_grants.sql／dev 審查矩陣相同；只比總數會讓「撤一張、補另一張」誤判 PASS。
 dml_tables CONSTANT text[] := ARRAY['actions','completions','contributions','draft_stories','drafts','evidence',
   'experience_mentions','experience_participants','experience_stories','experiences','fact_sources',
   'goal_reviews','goals','habit_quantity_versions','interaction_events','interaction_experiences',
   'interaction_people','note_sources','notes','pending_contributions','people','person_connections',
   'person_facts','person_goals','requests','reward_ledger','sessions','story_history','tasks','users'];
 update_tables CONSTANT text[] := ARRAY['actions','draft_stories','drafts','experience_mentions','experience_stories',
   'fact_sources','goals','habit_quantity_versions','interaction_events','interaction_experiences',
   'pending_contributions','people','person_connections','person_facts','person_goals','tasks','users'];
 delete_tables CONSTANT text[] := ARRAY['draft_stories','experience_mentions','experience_participants',
   'interaction_events','interaction_people','sessions'];
 privilege text; expected text[]; actual text[];
BEGIN
 IF current_database()<>'life_world_e2e' OR
    shobj_description((SELECT oid FROM pg_database WHERE datname=current_database()),'pg_database')
      IS DISTINCT FROM 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1' THEN RAISE EXCEPTION 'Wrong E2E database'; END IF;
 IF current_setting('server_version_num')::int<>180006 THEN RAISE EXCEPTION 'PostgreSQL 18.6 required'; END IF;
 IF (SELECT count(*) FROM pg_tables WHERE schemaname='lw_core_draft')<>31 OR
    EXISTS (SELECT FROM pg_roles WHERE rolname='lw_e2e_app' AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls OR rolinherit)) OR
    EXISTS (SELECT FROM pg_auth_members WHERE member='lw_e2e_app'::regrole) OR
    has_schema_privilege('lw_e2e_app','lw_core_draft','CREATE') THEN RAISE EXCEPTION 'Unsafe runtime role'; END IF;
 -- DDL／提權路徑：資料庫 CREATE／TEMP、任一 schema CREATE、擁有任何物件、可執行 SECURITY DEFINER 函式。
 IF has_database_privilege('lw_e2e_app',current_database(),'CREATE,TEMP') OR
    EXISTS (SELECT FROM pg_namespace WHERE nspname NOT LIKE 'pg\_temp\_%' AND nspname NOT LIKE 'pg\_toast\_temp\_%'
            AND has_schema_privilege('lw_e2e_app',oid,'CREATE')) OR
    EXISTS (SELECT FROM pg_shdepend WHERE refclassid='pg_authid'::regclass AND refobjid='lw_e2e_app'::regrole AND deptype='o') OR
    EXISTS (SELECT FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE p.prosecdef AND n.nspname NOT IN ('pg_catalog','information_schema')
              AND has_function_privilege('lw_e2e_app',p.oid,'EXECUTE')) THEN
   RAISE EXCEPTION 'Runtime has DDL, ownership or definer-function path'; END IF;
 -- 31 表必須正好是 30 張白名單業務表加 schema_migrations，白名單名稱不能指向不存在的表。
 SELECT array_agg(tablename::text ORDER BY tablename::text COLLATE "C") INTO actual FROM pg_tables WHERE schemaname='lw_core_draft';
 IF actual IS DISTINCT FROM (SELECT array_agg(t ORDER BY t COLLATE "C") FROM unnest(dml_tables||'schema_migrations'::text) t) THEN
   RAISE EXCEPTION 'E2E table set differs from canonical whitelist'; END IF;
 -- 以 OID 核對，避免名稱解析受呼叫者 schema 權限影響；WHERE 無固定評估順序，以 CASE 限定 relkind。
 -- effective privilege 已含 PUBLIC 與繼承；欄位級授權不出現在 has_table_privilege，另以 any-column 比對同一白名單。
 FOREACH privilege IN ARRAY ARRAY['SELECT','INSERT','UPDATE','DELETE'] LOOP
   SELECT array_agg(t ORDER BY t COLLATE "C") INTO expected
     FROM unnest(CASE privilege WHEN 'UPDATE' THEN update_tables WHEN 'DELETE' THEN delete_tables ELSE dml_tables END) t;
   SELECT array_agg(c.relname::text ORDER BY c.relname::text COLLATE "C") INTO actual FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname='lw_core_draft' AND CASE WHEN c.relkind IN ('r','p') THEN has_table_privilege('lw_e2e_app',c.oid,privilege) ELSE false END;
   IF actual IS DISTINCT FROM expected THEN RAISE EXCEPTION 'Runtime % table whitelist mismatch', privilege; END IF;
   IF privilege<>'DELETE' THEN
     SELECT array_agg(c.relname::text ORDER BY c.relname::text COLLATE "C") INTO actual FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
       WHERE n.nspname='lw_core_draft' AND CASE WHEN c.relkind IN ('r','p') THEN has_any_column_privilege('lw_e2e_app',c.oid,privilege) ELSE false END;
     IF actual IS DISTINCT FROM expected THEN RAISE EXCEPTION 'Runtime % column whitelist mismatch', privilege; END IF;
   END IF;
 END LOOP;
 -- schema_migrations 對 runtime 完全禁止（表級、欄位級、PUBLIC 皆不可）。
 IF EXISTS (SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='lw_core_draft' AND c.relname='schema_migrations' AND
              CASE WHEN c.relkind IN ('r','p')
                   THEN has_table_privilege('lw_e2e_app',c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN') OR
                        has_any_column_privilege('lw_e2e_app',c.oid,'SELECT,INSERT,UPDATE,REFERENCES') ELSE false END) THEN
   RAISE EXCEPTION 'Runtime must not access schema_migrations'; END IF;
 IF EXISTS (SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg\_toast%'
              AND CASE WHEN c.relkind IN ('r','p','v','m','f')
                       THEN has_table_privilege('lw_e2e_app',c.oid,'TRUNCATE,REFERENCES,TRIGGER,MAINTAIN') OR
                            has_any_column_privilege('lw_e2e_app',c.oid,'REFERENCES') ELSE false END) THEN
   RAISE EXCEPTION 'Runtime must not TRUNCATE, REFERENCE, TRIGGER or MAINTAIN'; END IF;
 IF EXISTS (SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg\_toast%'
              AND CASE WHEN c.relkind='S' THEN has_sequence_privilege('lw_e2e_app',c.oid,'SELECT,USAGE,UPDATE') ELSE false END) THEN
   RAISE EXCEPTION 'Runtime direct sequence privilege not allowed'; END IF;
END $verify$;
SELECT 'E2E_PERMISSIONS_PASS' AS result;
COMMIT;
