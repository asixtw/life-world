-- Owner在原Cloud SQL Studio整檔單次Run；三個結果及無錯誤缺一不可。
SELECT 'before' AS phase,'lw_alpha_tx_probe_c2bb85cada267dd0' AS probe_role,count(*) AS role_count FROM pg_roles WHERE rolname='lw_alpha_tx_probe_c2bb85cada267dd0';
BEGIN;
DO $$ BEGIN
 IF current_database()<>'life_world_alpha' OR current_setting('server_version_num')::int/10000<>18 THEN RAISE EXCEPTION 'STOP wrong Alpha target or PG major'; END IF;
 IF to_regrole('lw_alpha_tx_probe_c2bb85cada267dd0') IS NOT NULL THEN RAISE EXCEPTION 'STOP probe role already exists'; END IF;
END $$;
CREATE ROLE lw_alpha_tx_probe_c2bb85cada267dd0 NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
SELECT 'inside_transaction' AS phase,'lw_alpha_tx_probe_c2bb85cada267dd0' AS probe_role,count(*) AS role_count FROM pg_roles WHERE rolname='lw_alpha_tx_probe_c2bb85cada267dd0';
ROLLBACK;
SELECT 'after_rollback' AS phase,'lw_alpha_tx_probe_c2bb85cada267dd0' AS probe_role,count(*) AS role_count FROM pg_roles WHERE rolname='lw_alpha_tx_probe_c2bb85cada267dd0';
