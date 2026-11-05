-- REVIEW ONLY：DBA先批准並建立獨立life_world_alpha空庫，再在該庫審查本契約。
-- 不含密碼；LOGIN角色沒有可用密碼前不可提供給App，秘密注入由Owner另案處理。
-- 角色已存在則明確失敗／整筆回滾，不自動改其他人的角色。
BEGIN;
DO $$ BEGIN
 IF current_database() <> 'life_world_alpha' THEN
  RAISE EXCEPTION 'Alpha role contract requires life_world_alpha';
 END IF;
END $$;
CREATE ROLE lw_alpha_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE lw_alpha_migrator LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE lw_alpha_app_role NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE lw_alpha_app LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT lw_alpha_owner TO lw_alpha_migrator;
GRANT lw_alpha_app_role TO lw_alpha_app;
REVOKE CONNECT, TEMPORARY ON DATABASE life_world_alpha FROM PUBLIC;
GRANT CONNECT ON DATABASE life_world_alpha TO lw_alpha_owner, lw_alpha_app_role;
GRANT CREATE ON DATABASE life_world_alpha TO lw_alpha_owner;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
-- 由lw_alpha_migrator SET ROLE lw_alpha_owner建立核心schema與增量；runtime不得繼承owner。
-- 原dev CONNECT/PUBLIC策略由DBA另審，這份檔不更動life_world_dev任何權限。
COMMIT;
