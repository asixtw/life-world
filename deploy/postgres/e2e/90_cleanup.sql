-- 先移除 e2e tag／確認 0% 流量並停用測試 Revision，再由操作者以管理身分執行。
-- 只清理專用合成 DB；不 DROP DATABASE、不 DELETE dev，不賦予 Runtime 清理權限。
BEGIN;
DO $guard$
BEGIN
  IF current_database()<>'life_world_e2e' OR
     shobj_description((SELECT oid FROM pg_database WHERE datname=current_database()),'pg_database')
       IS DISTINCT FROM 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1' THEN
    RAISE EXCEPTION 'Refusing cleanup outside marked life_world_e2e';
  END IF;
  IF (SELECT datdba FROM pg_database WHERE datname=current_database())<>'lw_e2e_owner'::regrole OR
     (SELECT count(*) FROM pg_tables WHERE schemaname='lw_core_draft')<>31 OR
     EXISTS (SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
             WHERE c.relkind IN ('r','p') AND n.nspname NOT IN ('pg_catalog','information_schema')
             AND n.nspname NOT LIKE 'pg_toast%' AND n.nspname NOT LIKE 'pg_temp%'
             AND n.nspname<>'lw_core_draft') THEN
    RAISE EXCEPTION 'Unexpected E2E objects; inspect before cleanup';
  END IF;
END $guard$;
ALTER ROLE lw_e2e_app NOLOGIN;
REVOKE CONNECT ON DATABASE life_world_e2e FROM lw_e2e_app;
-- 先提交禁止新登入，再終止舊連線，避免清理交易期間 Runtime 重新取得連線。
COMMIT;
-- 僅終止此專用 login 在此專用 DB 的連線；無權限時必須停止並由 DBA 處理。
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
 WHERE datname='life_world_e2e' AND usename='lw_e2e_app' AND pid<>pg_backend_pid();
BEGIN;
DO $closed$
BEGIN
 IF current_database()<>'life_world_e2e' OR
    shobj_description((SELECT oid FROM pg_database WHERE datname=current_database()),'pg_database')
      IS DISTINCT FROM 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1' OR
    EXISTS (SELECT FROM pg_roles WHERE rolname='lw_e2e_app' AND rolcanlogin) OR
    EXISTS (SELECT FROM pg_stat_activity WHERE datname='life_world_e2e' AND usename='lw_e2e_app') THEN
   RAISE EXCEPTION 'E2E runtime must be disabled and drained before cleanup';
 END IF;
END $closed$;
SET LOCAL ROLE lw_e2e_owner;
DO $cleanup$
DECLARE tables text; item record; remaining bigint; total bigint := 0;
BEGIN
  SELECT string_agg(format('%I.%I',schemaname,tablename),',') INTO tables
    FROM pg_tables WHERE schemaname='lw_core_draft' AND tablename<>'schema_migrations';
  -- 同時列入所有 FK 關聯表，不使用 CASCADE 擴大清理範圍；保留 migration metadata。
  EXECUTE 'TRUNCATE TABLE ' || tables || ' RESTART IDENTITY';
  FOR item IN SELECT tablename FROM pg_tables WHERE schemaname='lw_core_draft' AND tablename<>'schema_migrations' LOOP
    EXECUTE format('SELECT count(*) FROM lw_core_draft.%I',item.tablename) INTO remaining;
    total := total + remaining;
  END LOOP;
  IF total<>0 THEN RAISE EXCEPTION 'E2E data cleanup incomplete'; END IF;
END $cleanup$;
COMMIT;
-- 提交後另以唯讀交易重驗最終狀態；前段任一步失敗（含 client 未設 ON_ERROR_STOP）時此處中止，不會印出 PASS。
BEGIN READ ONLY;
DO $verified$
DECLARE item record; remaining bigint;
BEGIN
  IF current_database()<>'life_world_e2e' OR
     shobj_description((SELECT oid FROM pg_database WHERE datname=current_database()),'pg_database')
       IS DISTINCT FROM 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1' OR
     (SELECT datdba FROM pg_database WHERE datname=current_database())<>'lw_e2e_owner'::regrole OR
     (SELECT count(*) FROM pg_tables WHERE schemaname='lw_core_draft')<>31 OR
     EXISTS (SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
             WHERE c.relkind IN ('r','p') AND n.nspname NOT IN ('pg_catalog','information_schema')
             AND n.nspname NOT LIKE 'pg_toast%' AND n.nspname NOT LIKE 'pg_temp%'
             AND n.nspname<>'lw_core_draft') OR
     EXISTS (SELECT FROM pg_roles WHERE rolname='lw_e2e_app' AND rolcanlogin) OR
     EXISTS (SELECT FROM pg_stat_activity WHERE datname='life_world_e2e' AND usename='lw_e2e_app') THEN
    RAISE EXCEPTION 'E2E cleanup final state not verified';
  END IF;
  FOR item IN SELECT tablename FROM pg_tables WHERE schemaname='lw_core_draft' AND tablename<>'schema_migrations' LOOP
    EXECUTE format('SELECT count(*) FROM lw_core_draft.%I',item.tablename) INTO remaining;
    IF remaining<>0 THEN RAISE EXCEPTION 'E2E data cleanup incomplete'; END IF;
  END LOOP;
END $verified$;
SELECT 'E2E_CLEANUP_PASS' AS result,
  (SELECT count(*) FROM pg_tables WHERE schemaname='lw_core_draft') AS retained_tables,
  (SELECT rolcanlogin FROM pg_roles WHERE rolname='lw_e2e_app') AS runtime_login,
  (SELECT count(*) FROM pg_stat_activity WHERE datname='life_world_e2e' AND usename='lw_e2e_app') AS runtime_sessions;
COMMIT;
