-- 管理者在專用 DB 核對 effective privileges（含 PUBLIC／繼承影響），不輸出資料列。
-- 檢查與 PASS 同一唯讀交易：任一檢查失敗即中止交易，client 未設 ON_ERROR_STOP 也不會印出 PASS。
BEGIN READ ONLY;
DO $verify$
DECLARE privilege text; actual bigint; expected bigint;
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
 -- 以 OID 核對，避免名稱解析受呼叫者 schema 權限影響；WHERE 無固定評估順序，以 CASE 限定 relkind。
 -- 欄位級授權不出現在 has_table_privilege，另以 any-column 核對同一矩陣。
 FOREACH privilege IN ARRAY ARRAY['SELECT','INSERT','UPDATE','DELETE'] LOOP
   expected := CASE privilege WHEN 'SELECT' THEN 30 WHEN 'INSERT' THEN 30 WHEN 'UPDATE' THEN 17 ELSE 6 END;
   SELECT count(*) INTO actual FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname='lw_core_draft' AND CASE WHEN c.relkind IN ('r','p') THEN has_table_privilege('lw_e2e_app',c.oid,privilege) ELSE false END;
   IF actual<>expected THEN RAISE EXCEPTION 'Runtime effective privileges differ from 30/30/17/6'; END IF;
   IF privilege<>'DELETE' THEN
     SELECT count(*) INTO actual FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
       WHERE n.nspname='lw_core_draft' AND CASE WHEN c.relkind IN ('r','p') THEN has_any_column_privilege('lw_e2e_app',c.oid,privilege) ELSE false END;
     IF actual<>expected THEN RAISE EXCEPTION 'Runtime column privileges differ from 30/30/17'; END IF;
   END IF;
 END LOOP;
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
