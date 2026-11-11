-- 原Studio／postgres管理工作階段；分別選life_world_e2e與life_world_alpha各執行一次。
-- 僅系統目錄、DDL定義、Migration版本與權限；不讀業務資料，不授權，不改Schema。
BEGIN READ ONLY;
DO $gate$
DECLARE schema_owner name;
BEGIN
 IF current_database() NOT IN ('life_world_alpha','life_world_e2e') OR current_setting('server_version_num')::int/10000<>18 THEN
  RAISE EXCEPTION 'STOP: target database/PG18 mismatch';
 END IF;
 SELECT pg_get_userbyid(nspowner) INTO STRICT schema_owner FROM pg_namespace WHERE nspname='lw_core_draft';
 -- 使用目錄的既有Owner角色只為讀Migration；交易結束恢復原角色，沒有任何GRANT。
 EXECUTE format('SET LOCAL ROLE %I',schema_owner);
END $gate$;
WITH ns AS (SELECT oid FROM pg_namespace WHERE nspname='lw_core_draft'),
relations AS (
 SELECT c.oid,c.relname,c.relkind,c.relowner,c.relacl,c.relrowsecurity,c.relforcerowsecurity,c.reloptions
 FROM pg_class c WHERE c.relnamespace=(SELECT oid FROM ns) AND c.relkind IN ('r','p','v','m','S')
), snapshot AS (
 SELECT jsonb_build_object(
  'columns',(SELECT coalesce(jsonb_agg(jsonb_build_object('table',c.relname,'position',a.attnum,'name',a.attname,'type',format_type(a.atttypid,a.atttypmod),'nullable',NOT a.attnotnull,'default',pg_get_expr(d.adbin,d.adrelid),'identity',a.attidentity,'generated',a.attgenerated,'collation',CASE WHEN a.attcollation<>0 THEN a.attcollation::regcollation::text ELSE NULL END) ORDER BY c.relname,a.attnum),'[]'::jsonb) FROM relations c JOIN pg_attribute a ON a.attrelid=c.oid LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum WHERE a.attnum>0 AND NOT a.attisdropped),
  'relations',(SELECT coalesce(jsonb_agg(jsonb_build_object('name',relname,'kind',relkind,'rls',relrowsecurity,'force_rls',relforcerowsecurity,'options',reloptions) ORDER BY relname),'[]'::jsonb) FROM relations),
  'constraints',(SELECT coalesce(jsonb_agg(jsonb_build_object('table',c.relname,'name',k.conname,'kind',k.contype,'definition',pg_get_constraintdef(k.oid,true),'validated',k.convalidated,'deferrable',k.condeferrable,'deferred',k.condeferred) ORDER BY c.relname,k.conname),'[]'::jsonb) FROM relations c JOIN pg_constraint k ON k.conrelid=c.oid),
  'indexes',(SELECT coalesce(jsonb_agg(jsonb_build_object('table',tablename,'name',indexname,'definition',indexdef) ORDER BY tablename,indexname),'[]'::jsonb) FROM pg_indexes WHERE schemaname='lw_core_draft'),
  'views',(SELECT coalesce(jsonb_agg(jsonb_build_object('name',relname,'definition',pg_get_viewdef(oid,true)) ORDER BY relname),'[]'::jsonb) FROM relations WHERE relkind IN ('v','m')),
  'functions',(SELECT coalesce(jsonb_agg(jsonb_build_object('name',p.oid::regprocedure::text,'kind',p.prokind,'security_definer',p.prosecdef,'definition',pg_get_functiondef(p.oid)) ORDER BY p.oid::regprocedure::text),'[]'::jsonb) FROM pg_proc p WHERE p.pronamespace=(SELECT oid FROM ns) AND p.prokind IN ('f','p')),
  'triggers',(SELECT coalesce(jsonb_agg(jsonb_build_object('table',c.relname,'name',t.tgname,'enabled',t.tgenabled,'definition',pg_get_triggerdef(t.oid,true)) ORDER BY c.relname,t.tgname),'[]'::jsonb) FROM relations c JOIN pg_trigger t ON t.tgrelid=c.oid WHERE NOT t.tgisinternal),
  'policies',(SELECT coalesce(jsonb_agg(to_jsonb(p) ORDER BY p.tablename,p.policyname),'[]'::jsonb) FROM pg_policies p WHERE schemaname='lw_core_draft')
 ) AS structure
)
SELECT jsonb_build_object(
 'captured_at',clock_timestamp(),'database',current_database(),'session_user',session_user,'effective_role',current_user,'search_path',current_setting('search_path'),'pg_version',current_setting('server_version_num'),
 'database_metadata',(SELECT jsonb_build_object('owner',pg_get_userbyid(datdba),'marker',shobj_description(oid,'pg_database'),'acl',datacl::text) FROM pg_database WHERE datname=current_database()),
 'schema_metadata',(SELECT jsonb_build_object('owner',pg_get_userbyid(nspowner),'acl',nspacl::text) FROM pg_namespace WHERE nspname='lw_core_draft'),
 'structure',structure,'structure_md5_pg',md5(structure::text),
 'migration_receipts',query_to_xml('SELECT version FROM lw_core_draft.schema_migrations ORDER BY version',true,true,'')::text,
 'relation_acl',(SELECT coalesce(jsonb_agg(jsonb_build_object('name',relname,'owner',pg_get_userbyid(relowner),'acl',relacl::text) ORDER BY relname),'[]'::jsonb) FROM relations),
 'column_acl',(SELECT coalesce(jsonb_agg(jsonb_build_object('table',c.relname,'column',a.attname,'acl',a.attacl::text) ORDER BY c.relname,a.attname),'[]'::jsonb) FROM relations c JOIN pg_attribute a ON a.attrelid=c.oid WHERE a.attnum>0 AND NOT a.attisdropped AND a.attacl IS NOT NULL),
 'roles',(SELECT jsonb_agg(jsonb_build_object('name',rolname,'login',rolcanlogin,'inherit',rolinherit,'superuser',rolsuper,'createdb',rolcreatedb,'createrole',rolcreaterole,'replication',rolreplication,'bypassrls',rolbypassrls) ORDER BY rolname) FROM pg_roles WHERE rolname LIKE 'lw\_%' ESCAPE '\'),
 'memberships',(SELECT jsonb_agg(jsonb_build_object('parent',p.rolname,'member',c.rolname,'admin',m.admin_option,'inherit',m.inherit_option,'set',m.set_option) ORDER BY p.rolname,c.rolname) FROM pg_auth_members m JOIN pg_roles p ON p.oid=m.roleid JOIN pg_roles c ON c.oid=m.member WHERE p.rolname LIKE 'lw\_%' ESCAPE '\' OR c.rolname LIKE 'lw\_%' ESCAPE '\'),
 'default_acl',(SELECT coalesce(jsonb_agg(jsonb_build_object('owner',pg_get_userbyid(d.defaclrole),'namespace',n.nspname,'object_type',d.defaclobjtype,'acl',d.defaclacl::text) ORDER BY d.defaclrole,n.nspname,d.defaclobjtype),'[]'::jsonb) FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace),
 'effective_runtime_privileges',(SELECT jsonb_agg(jsonb_build_object('role',r.rolname,'table',t.relname,'select',has_table_privilege(r.rolname,t.oid,'SELECT'),'insert',has_table_privilege(r.rolname,t.oid,'INSERT'),'update',has_table_privilege(r.rolname,t.oid,'UPDATE'),'delete',has_table_privilege(r.rolname,t.oid,'DELETE')) ORDER BY r.rolname,t.relname) FROM pg_roles r CROSS JOIN relations t WHERE r.rolname IN ('lw_alpha_app','lw_e2e_app') AND t.relkind IN ('r','p'))
) AS schema_snapshot FROM snapshot;
COMMIT;
