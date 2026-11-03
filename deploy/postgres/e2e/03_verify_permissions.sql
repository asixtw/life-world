-- 管理者在專用 DB 核對 effective privileges（含 PUBLIC／繼承影響），不輸出資料列。
DO $verify$
DECLARE privilege text; actual bigint; expected bigint; item record;
BEGIN
 IF current_database()<>'life_world_e2e' OR
    shobj_description((SELECT oid FROM pg_database WHERE datname=current_database()),'pg_database')
      IS DISTINCT FROM 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1' THEN RAISE EXCEPTION 'Wrong E2E database'; END IF;
 IF (SELECT count(*) FROM pg_tables WHERE schemaname='lw_core_draft')<>31 OR
    EXISTS (SELECT FROM pg_roles WHERE rolname='lw_e2e_app' AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls OR rolinherit)) OR
    EXISTS (SELECT FROM pg_auth_members WHERE member='lw_e2e_app'::regrole) OR
    has_schema_privilege('lw_e2e_app','lw_core_draft','CREATE') THEN RAISE EXCEPTION 'Unsafe runtime role'; END IF;
 FOREACH privilege IN ARRAY ARRAY['SELECT','INSERT','UPDATE','DELETE'] LOOP
   SELECT count(*) INTO actual FROM pg_tables WHERE schemaname='lw_core_draft'
     AND has_table_privilege('lw_e2e_app',format('%I.%I',schemaname,tablename),privilege);
   expected := CASE privilege WHEN 'SELECT' THEN 30 WHEN 'INSERT' THEN 30 WHEN 'UPDATE' THEN 17 ELSE 6 END;
   IF actual<>expected THEN RAISE EXCEPTION 'Runtime effective privileges differ from 30/30/17/6'; END IF;
 END LOOP;
 FOR item IN SELECT tablename FROM pg_tables WHERE schemaname='lw_core_draft' LOOP
   IF has_table_privilege('lw_e2e_app',format('lw_core_draft.%I',item.tablename),'TRUNCATE') THEN
     RAISE EXCEPTION 'Runtime must not TRUNCATE'; END IF;
 END LOOP;
 FOR item IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
              WHERE n.nspname='lw_core_draft' AND c.relkind='S' LOOP
   IF has_sequence_privilege('lw_e2e_app',format('lw_core_draft.%I',item.relname),'SELECT,USAGE,UPDATE') THEN
     RAISE EXCEPTION 'Runtime direct sequence privilege not allowed'; END IF;
 END LOOP;
END $verify$;
SELECT 'E2E_PERMISSIONS_PASS' AS result;
