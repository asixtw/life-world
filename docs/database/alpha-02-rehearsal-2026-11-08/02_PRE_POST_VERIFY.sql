-- 唯讀：演練前保存baseline、ROLLBACK後比較、正式COMMIT後驗收。整檔Run。
BEGIN READ ONLY;
WITH db AS (
 SELECT oid,datname,datdba,datacl,shobj_description(oid,'pg_database') AS marker FROM pg_database WHERE datname=current_database()
), roles AS (
 SELECT oid,rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls
 FROM pg_roles WHERE rolname IN ('lw_alpha_owner','lw_alpha_app_role','lw_alpha_app')
), memberships AS (
 SELECT parent.rolname AS parent_role,child.rolname AS member_role,grantor.rolname AS grantor,m.admin_option,m.inherit_option,m.set_option
 FROM pg_auth_members m JOIN pg_roles parent ON parent.oid=m.roleid JOIN pg_roles child ON child.oid=m.member JOIN pg_roles grantor ON grantor.oid=m.grantor
 WHERE parent.rolname IN ('lw_alpha_owner','lw_alpha_app_role','lw_alpha_app') OR child.rolname IN ('lw_alpha_owner','lw_alpha_app_role','lw_alpha_app')
), schemas AS (
 SELECT nspname,pg_get_userbyid(nspowner) AS owner,
 (SELECT jsonb_agg(a::text ORDER BY a::text) FROM unnest(nspacl) a) AS acl
 FROM pg_namespace WHERE nspname !~ '^pg_(temp|toast_temp)_'
), snapshot AS (
 SELECT jsonb_build_object(
  'database',(SELECT jsonb_build_object('name',datname,'owner',pg_get_userbyid(datdba),'marker',marker,'acl',(SELECT jsonb_agg(a::text ORDER BY a::text) FROM unnest(datacl) a)) FROM db),
  'roles',COALESCE((SELECT jsonb_agg(to_jsonb(r)-'oid' ORDER BY rolname) FROM roles r),'[]'::jsonb),
  'memberships',COALESCE((SELECT jsonb_agg(to_jsonb(m) ORDER BY parent_role,member_role,grantor) FROM memberships m),'[]'::jsonb),
  'schemas',COALESCE((SELECT jsonb_agg(to_jsonb(s) ORDER BY nspname) FROM schemas s),'[]'::jsonb)
 ) AS value
)
SELECT current_database() AS database,session_user,current_user,
 current_database()='life_world_alpha' AS correct_target,
 current_setting('server_version_num')::int/10000=18 AS pg18,
 (SELECT count(*) FROM roles) AS alpha_role_count,
 (SELECT pg_get_userbyid(datdba) FROM db) AS database_owner,
 (SELECT pg_get_userbyid(datdba)='cloudsqlsuperuser' FROM db) AS original_owner,
 (SELECT pg_get_userbyid(datdba)='lw_alpha_owner' FROM db) AS committed_owner,
 to_regnamespace('lw_core_draft') IS NULL AS core_still_absent,
 has_database_privilege(current_user,current_database(),'CONNECT') AS dba_can_connect,
 COALESCE(pg_has_role(current_user,to_regrole('lw_alpha_owner'),'SET'),false) AS dba_can_set_owner,
 COALESCE(pg_has_role(to_regrole('lw_alpha_app'),to_regrole('lw_alpha_owner'),'MEMBER'),false) AS runtime_owner_membership_forbidden,
 COALESCE((SELECT bool_and(NOT rolcanlogin AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls) FROM roles),false) AS all_three_attributes_safe,
 value AS state_snapshot,md5(value::text) AS snapshot_fingerprint_md5
FROM snapshot;
COMMIT;
