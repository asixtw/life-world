-- 只由操作者在 postgres 管理資料庫手動執行。無密碼、無 life_world_dev 授權變更。
-- 初次建立用；任何同名物件已存在即停止，不擅自接管既有資料。
-- 分三個操作階段：①建角色（guard 交易）②CREATE DATABASE（不可放在交易內）③標記與 DB 權限（guard 交易）。
-- client 未設 ON_ERROR_STOP 時仍 fail-closed：session 先改為唯讀預設，只有①成功提交才解除；
-- ①失敗時②的 CREATE DATABASE 與③都在唯讀交易被拒，③另要求本 session 的①完成旗標。
-- 失敗後此 session 會維持唯讀預設；請關閉連線，檢查物件後再處理，不要在同一連線續做其他變更。
SET default_transaction_read_only = on;
SET lw_e2e.bootstrap_stage = '';
BEGIN READ WRITE;
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
-- 交易內的 SET 隨提交生效；交易中止時自動還原，session 維持唯讀且旗標為空。
SET lw_e2e.bootstrap_stage = 'roles_created';
SET default_transaction_read_only = off;
COMMIT;
-- CREATE DATABASE 不可放在 BEGIN／COMMIT 中；不得改成現有 dev 資料庫。①未提交時此處因唯讀被拒。
CREATE DATABASE life_world_e2e OWNER lw_e2e_owner TEMPLATE template0 ENCODING 'UTF8';
BEGIN;
DO $created$
BEGIN
  -- 只標記本 session ①剛建立的 owner 所擁有、尚無 marker 的新資料庫；既有同名 DB 一律不改。
  IF current_setting('lw_e2e.bootstrap_stage',true) IS DISTINCT FROM 'roles_created' OR
     current_database() <> 'postgres' OR NOT EXISTS (
       SELECT FROM pg_database WHERE datname='life_world_e2e' AND datdba='lw_e2e_owner'::regrole
       AND shobj_description(oid,'pg_database') IS NULL) THEN
    RAISE EXCEPTION 'life_world_e2e was not freshly created by this session';
  END IF;
END $created$;
COMMENT ON DATABASE life_world_e2e IS 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1';
REVOKE ALL ON DATABASE life_world_e2e FROM PUBLIC;
GRANT CONNECT ON DATABASE life_world_e2e TO lw_e2e_app;
SET lw_e2e.bootstrap_stage = 'database_marked';
COMMIT;
