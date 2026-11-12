-- 審查稿，未獲正式套用授權；不得由App/CI自動執行。沒有Migration或資料刪除。
-- 已核對快照：各庫Runtime有data_consents SELECT/INSERT，缺UPDATE(revoked_at)。
-- 僅限指定DB/Marker/PG18及原Owner；只增加該庫單一Runtime的撤回欄位權限。
BEGIN;
DO $review$
DECLARE target_db text:=current_database(); target_owner text; target_app text; expected_marker text; actual_marker text;
BEGIN
 IF current_setting('server_version_num')::int/10000<>18 THEN RAISE EXCEPTION 'STOP PG18 required'; END IF;
 IF target_db='life_world_alpha' THEN
  target_owner:='lw_alpha_owner'; target_app:='lw_alpha_app'; expected_marker:='LIFEWORLD_PUBLIC_ALPHA_GCP144_V1';
 ELSIF target_db='life_world_e2e' THEN
  target_owner:='lw_e2e_owner'; target_app:='lw_e2e_app'; expected_marker:='LIFEWORLD_E2E_SYNTHETIC_ONLY_v1';
 ELSE RAISE EXCEPTION 'STOP wrong database';
 END IF;
 SELECT shobj_description(oid,'pg_database') INTO actual_marker FROM pg_database WHERE datname=target_db;
 IF actual_marker IS DISTINCT FROM expected_marker THEN RAISE EXCEPTION 'STOP wrong marker'; END IF;
 IF (SELECT pg_get_userbyid(c.relowner) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='lw_core_draft' AND c.relname='data_consents' AND c.relkind='r') IS DISTINCT FROM target_owner THEN RAISE EXCEPTION 'STOP wrong object owner'; END IF;
 IF NOT has_table_privilege(target_app,'lw_core_draft.data_consents','SELECT') OR NOT has_table_privilege(target_app,'lw_core_draft.data_consents','INSERT') THEN RAISE EXCEPTION 'STOP baseline privilege drift'; END IF;
 IF has_column_privilege(target_app,'lw_core_draft.data_consents','revoked_at','UPDATE') THEN RAISE EXCEPTION 'STOP already granted; read back instead of replay'; END IF;
 EXECUTE format('SET LOCAL ROLE %I',target_owner);
 EXECUTE format('GRANT UPDATE(revoked_at) ON TABLE lw_core_draft.data_consents TO %I',target_app);
END $review$;
COMMIT;
-- 套用後另以唯讀has_column_privilege驗證；owner_id/subject/provider_scope/source_scope等不應新增UPDATE。
-- 權限回復不在本稿自動執行：先停用草稿AI，再審查有效授權/依賴及原GRANT快照，不刪同意歷史。
