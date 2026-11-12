-- REVIEW ONLY / NOT EXECUTED。僅在備份/011/角色與Owner另行核准後使用；不建立角色/不改Owner。
-- 不可由網站Runtime執行；正式操作需先保存原ACL，任何差異停止，不用盲目REVOKE當回復。
BEGIN;
DO $permission_review$
DECLARE target_role text; item text; expected_marker text;
BEGIN
 IF current_setting('server_version_num')::int/10000<>18 THEN RAISE EXCEPTION 'STOP PG18 required'; END IF;
 CASE current_database()
  WHEN 'life_world_e2e' THEN target_role:='lw_e2e_app'; expected_marker:='LIFEWORLD_E2E_SYNTHETIC_ONLY_v1';
  WHEN 'life_world_alpha' THEN target_role:='lw_alpha_app_role'; expected_marker:='LIFEWORLD_PUBLIC_ALPHA_GCP144_V1';
  ELSE RAISE EXCEPTION 'STOP target database';
 END CASE;
 IF (SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()) IS DISTINCT FROM expected_marker THEN RAISE EXCEPTION 'STOP marker'; END IF;
 IF current_user<>(SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='lw_core_draft') THEN RAISE EXCEPTION 'STOP reviewed schema owner role required'; END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=target_role) THEN RAISE EXCEPTION 'STOP existing Runtime role missing'; END IF;
 FOREACH item IN ARRAY ARRAY['person_basic_details','person_basic_detail_history','person_employments','person_employment_history'] LOOP
  IF to_regclass('lw_core_draft.'||item) IS NULL THEN RAISE EXCEPTION 'STOP reviewed 011 table missing'; END IF;
  IF has_column_privilege(target_role,'lw_core_draft.'||item,'owner_id','UPDATE') OR has_column_privilege(target_role,'lw_core_draft.'||item,'person_id','UPDATE') OR has_table_privilege(target_role,'lw_core_draft.'||item,'DELETE') THEN
   RAISE EXCEPTION 'STOP unexpected broad existing privilege; do not silently revoke';
  END IF;
 END LOOP;
 FOREACH item IN ARRAY ARRAY['person_basic_detail_history','person_employment_history'] LOOP
  IF EXISTS(SELECT 1 FROM pg_attribute a WHERE a.attrelid=to_regclass('lw_core_draft.'||item) AND a.attnum>0 AND NOT a.attisdropped AND has_column_privilege(target_role,a.attrelid,a.attname,'UPDATE')) THEN RAISE EXCEPTION 'STOP history must be append-only'; END IF;
 END LOOP;
 -- 目前值：只允許服務實際會更新的內容/來源/版本；不准重派Owner、主鍵、人物或created_at。
 EXECUTE format('GRANT SELECT,INSERT ON lw_core_draft.person_basic_details,lw_core_draft.person_employments,lw_core_draft.person_basic_detail_history,lw_core_draft.person_employment_history TO %I',target_role);
 EXECUTE format('GRANT UPDATE(birth_year,birth_month,birth_day,source_kind,source_experience_id,evidence_type,source_quote,source_status,confirmed_at,revision,updated_at) ON lw_core_draft.person_basic_details TO %I',target_role);
 EXECUTE format('GRANT UPDATE(company_name,job_title,employment_status,valid_from,valid_to,source_kind,source_experience_id,evidence_type,source_quote,source_status,confirmed_at,revision,updated_at) ON lw_core_draft.person_employments TO %I',target_role);
 -- 已核准的草稿刪除API與同意撤回所需差異；不授權正式經歷/獎勵刪除。
 EXECUTE format('GRANT DELETE ON lw_core_draft.drafts TO %I',target_role);
 EXECUTE format('GRANT UPDATE(revoked_at) ON lw_core_draft.data_consents TO %I',target_role);
END $permission_review$;
COMMIT;
