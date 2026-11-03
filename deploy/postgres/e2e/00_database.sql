-- 只由操作者在 postgres 管理資料庫手動執行。無密碼、無 life_world_dev 授權變更。
-- 初次建立用；任何同名物件已存在即停止，不擅自接管既有資料。
DO $guard$
BEGIN
  IF current_database() <> 'postgres' OR current_setting('server_version_num')::int <> 180006 THEN
    RAISE EXCEPTION 'E2E requires postgres administration database on PostgreSQL 18.6';
  END IF;
  IF EXISTS (SELECT FROM pg_database WHERE datname='life_world_e2e') OR
     EXISTS (SELECT FROM pg_roles WHERE rolname IN ('lw_e2e_owner','lw_e2e_app')) THEN
    RAISE EXCEPTION 'E2E objects already exist; inspect, do not overwrite';
  END IF;
END $guard$;
CREATE ROLE lw_e2e_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE lw_e2e_app NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT lw_e2e_owner TO CURRENT_USER;
-- CREATE DATABASE 不可放在 BEGIN／COMMIT 中；不得改成現有 dev 資料庫。
CREATE DATABASE life_world_e2e OWNER lw_e2e_owner TEMPLATE template0 ENCODING 'UTF8';
COMMENT ON DATABASE life_world_e2e IS 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1';
REVOKE ALL ON DATABASE life_world_e2e FROM PUBLIC;
GRANT CONNECT ON DATABASE life_world_e2e TO lw_e2e_app;
