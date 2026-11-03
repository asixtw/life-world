-- 只在 life_world_dev 查權限 metadata；沒有業務資料 SELECT、DML、GRANT 或 REVOKE。
-- 若現有 PUBLIC 權限讓新 E2E login 取得 dev 資料權限，停止並交 DBA 審查，不自動改 dev。
DO $verify$
DECLARE item record;
BEGIN
 IF current_database()<>'life_world_dev' THEN RAISE EXCEPTION 'Expected dev metadata probe'; END IF;
 FOR item IN SELECT tablename FROM pg_tables WHERE schemaname='lw_core_draft' LOOP
   IF has_table_privilege('lw_e2e_app',format('lw_core_draft.%I',item.tablename),'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') THEN
     RAISE EXCEPTION 'E2E login unexpectedly has dev table privileges'; END IF;
 END LOOP;
 IF has_schema_privilege('lw_e2e_app','lw_core_draft','CREATE') THEN RAISE EXCEPTION 'E2E login can create dev objects'; END IF;
END $verify$;
SELECT 'E2E_DEV_ROLE_ISOLATION_PASS' AS result;
