-- 唯讀補充既有Schema Snapshot的Sequence定義/有效權限；不讀業務資料或密碼，不寫設定。
-- 正式備份操作當時使用，非要求Owner重跑歷史02。由已核對既有管理角色執行。
BEGIN READ ONLY;
DO $backup_target$
DECLARE expected_marker text;
BEGIN
 IF current_setting('server_version_num')::int/10000<>18 THEN RAISE EXCEPTION 'STOP PG18 required'; END IF;
 CASE current_database()
  WHEN 'life_world_e2e' THEN expected_marker:='LIFEWORLD_E2E_SYNTHETIC_ONLY_v1';
  WHEN 'life_world_alpha' THEN expected_marker:='LIFEWORLD_PUBLIC_ALPHA_GCP144_V1';
  ELSE RAISE EXCEPTION 'STOP target database';
 END CASE;
 IF (SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()) IS DISTINCT FROM expected_marker THEN RAISE EXCEPTION 'STOP marker'; END IF;
END $backup_target$;
SELECT jsonb_build_object(
 'database',current_database(),'captured_at',clock_timestamp(),'server_version_num',current_setting('server_version_num'),
 'read_only',current_setting('transaction_read_only'),'captured_by',current_user,
 'sequence_definitions',(SELECT jsonb_agg(jsonb_build_object(
  'schema',n.nspname,'name',c.relname,'owner',pg_get_userbyid(c.relowner),'acl',c.relacl::text,
  'type',format_type(s.seqtypid,NULL),'start',s.seqstart,'increment',s.seqincrement,
  'min',s.seqmin,'max',s.seqmax,'cache',s.seqcache,'cycle',s.seqcycle,
  'runtime_role',CASE current_database() WHEN 'life_world_e2e' THEN 'lw_e2e_app' ELSE 'lw_alpha_app' END,
  'runtime_usage',has_sequence_privilege(CASE current_database() WHEN 'life_world_e2e' THEN 'lw_e2e_app' ELSE 'lw_alpha_app' END,c.oid,'USAGE'),
  'runtime_select',has_sequence_privilege(CASE current_database() WHEN 'life_world_e2e' THEN 'lw_e2e_app' ELSE 'lw_alpha_app' END,c.oid,'SELECT'),
  'runtime_update',has_sequence_privilege(CASE current_database() WHEN 'life_world_e2e' THEN 'lw_e2e_app' ELSE 'lw_alpha_app' END,c.oid,'UPDATE')
 ) ORDER BY n.nspname,c.relname) FROM pg_sequence s JOIN pg_class c ON c.oid=s.seqrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='lw_core_draft'),
 'sequence_visible_state',(SELECT jsonb_agg(jsonb_build_object('schema',schemaname,'name',sequencename,'last_value',last_value,'state_visible',last_value IS NOT NULL) ORDER BY schemaname,sequencename) FROM pg_sequences WHERE schemaname='lw_core_draft'),
 'note','last_value=NULL may mean insufficient privilege or unused sequence; do not infer zero or complete state. Full schema/roles/ACL are supplied separately by the existing snapshot.'
) AS backup_completeness;
COMMIT;
