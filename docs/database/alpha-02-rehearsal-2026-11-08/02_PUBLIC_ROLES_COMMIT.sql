-- 僅既有DBA；必須先完成受控可還原備份。若角色已存在，停止核對，不覆寫。
BEGIN;
DO $target$ BEGIN
 IF current_database()<>'life_world_alpha' OR current_setting('server_version_num')::int/10000<>18 THEN RAISE EXCEPTION 'STOP: wrong public target/PG version'; END IF;
 IF current_user IN ('lw_alpha_app','lw_product_staging_app') THEN RAISE EXCEPTION 'STOP: runtime is not DBA'; END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname=current_user AND (rolsuper OR (rolcreaterole AND rolcreatedb)))
 OR NOT has_database_privilege(current_user,current_database(),'CREATE WITH GRANT OPTION')
 OR NOT has_database_privilege(current_user,current_database(),'CONNECT WITH GRANT OPTION') THEN RAISE EXCEPTION 'STOP: effective DBA role/grant privileges missing'; END IF;
 IF to_regnamespace('lw_core_draft') IS NOT NULL THEN RAISE EXCEPTION 'STOP: Alpha core already exists; no automatic rebuild'; END IF;
END $target$;
CREATE ROLE lw_alpha_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE lw_alpha_app_role NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE lw_alpha_app NOLOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT lw_alpha_app_role TO lw_alpha_app;
-- 只有現有執行DBA可SET非登入owner；Runtime不得獲此membership。
GRANT lw_alpha_owner TO CURRENT_USER WITH INHERIT FALSE, SET TRUE;
REVOKE CONNECT,TEMPORARY ON DATABASE life_world_alpha FROM PUBLIC;
GRANT CONNECT ON DATABASE life_world_alpha TO lw_alpha_owner,lw_alpha_app_role;
GRANT CREATE ON DATABASE life_world_alpha TO lw_alpha_owner;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
-- 後續007/008要求DB owner與Schema owner相同；只對空Alpha目標設定。
ALTER DATABASE life_world_alpha OWNER TO lw_alpha_owner;
-- 移轉會重寫舊Owner ACL；必須在移轉後以新Owner保留原DBA連線。
SET LOCAL ROLE lw_alpha_owner;
GRANT CONNECT ON DATABASE life_world_alpha TO SESSION_USER;
COMMIT;
