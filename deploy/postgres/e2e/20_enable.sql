-- Schema／grants 驗證完畢、操作者安全設定密碼及 Secret Manager 後才可執行。
BEGIN;
DO $guard$
BEGIN
  IF current_database()<>'life_world_e2e' OR
     shobj_description((SELECT oid FROM pg_database WHERE datname=current_database()),'pg_database')
       IS DISTINCT FROM 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1' THEN
    RAISE EXCEPTION 'Refusing non-E2E database';
  END IF;
  IF (SELECT count(*) FROM pg_tables WHERE schemaname='lw_core_draft')<>31 OR
     EXISTS (SELECT FROM pg_roles WHERE rolname='lw_e2e_app' AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls OR rolinherit)) OR
     EXISTS (SELECT FROM pg_auth_members WHERE member='lw_e2e_app'::regrole) THEN
    RAISE EXCEPTION 'E2E schema or runtime role is unsafe';
  END IF;
END $guard$;
GRANT CONNECT ON DATABASE life_world_e2e TO lw_e2e_app;
ALTER ROLE lw_e2e_app LOGIN;
COMMIT;
