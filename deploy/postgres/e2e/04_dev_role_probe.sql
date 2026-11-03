-- 只在 life_world_dev 查權限 metadata；唯讀交易，沒有業務資料 SELECT、DML、GRANT 或 REVOKE。
-- 以 OID 呼叫權限函式：非 superuser 的 Cloud SQL 管理者不必取得 dev schema USAGE 也能核對；CASE 限定 relkind。
-- 若現有 PUBLIC 權限讓新 E2E login 取得 dev 資料／DDL 權限，停止並交 DBA 審查，不自動改 dev。
BEGIN READ ONLY;
DO $verify$
BEGIN
 IF current_database()<>'life_world_dev' THEN RAISE EXCEPTION 'Expected dev metadata probe'; END IF;
 IF EXISTS (SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg\_toast%'
              AND CASE WHEN c.relkind IN ('r','p','v','m','f')
                       THEN has_table_privilege('lw_e2e_app',c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN') OR
                            has_any_column_privilege('lw_e2e_app',c.oid,'SELECT,INSERT,UPDATE,REFERENCES') ELSE false END) THEN
   RAISE EXCEPTION 'E2E login unexpectedly has dev table privileges'; END IF;
 IF EXISTS (SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg\_toast%'
              AND CASE WHEN c.relkind='S' THEN has_sequence_privilege('lw_e2e_app',c.oid,'SELECT,USAGE,UPDATE') ELSE false END) THEN
   RAISE EXCEPTION 'E2E login unexpectedly has dev sequence privileges'; END IF;
 IF has_database_privilege('lw_e2e_app',current_database(),'CREATE') OR
    EXISTS (SELECT FROM pg_namespace WHERE nspname NOT LIKE 'pg\_temp\_%' AND nspname NOT LIKE 'pg\_toast\_temp\_%'
            AND has_schema_privilege('lw_e2e_app',oid,'CREATE')) THEN
   RAISE EXCEPTION 'E2E login can create dev objects'; END IF;
END $verify$;
-- PUBLIC 預設的 CONNECT／TEMP 只回報不修改；是否撤銷屬 dev 變更，由使用者／DBA 決定。
SELECT 'E2E_DEV_ROLE_ISOLATION_PASS' AS result,
  has_database_privilege('lw_e2e_app',current_database(),'CONNECT') AS dev_connect_possible,
  has_database_privilege('lw_e2e_app',current_database(),'TEMP') AS dev_temp_possible;
COMMIT;
