-- REVIEW ONLY / GCP NOT RUN：兩庫唯讀Snapshot已比對；僅本機合成PG18副本試跑成功。
-- 不由Runtime執行。不重跑010，不DROP/TRUNCATE，不授權。實體名稱、版號、收據待審查凍結。
BEGIN;
DO $gate$
BEGIN
 IF current_database() NOT IN ('life_world_e2e','life_world_alpha') OR current_setting('server_version_num')::int/10000<>18 THEN
  RAISE EXCEPTION 'STOP target/PG mismatch';
 END IF;
 -- 同名DB不足以辨識環境；只接受Owner來源收據中的既有Marker，不自行補寫Marker。
 IF (SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()) IS DISTINCT FROM
    CASE current_database() WHEN 'life_world_e2e' THEN 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1'
     WHEN 'life_world_alpha' THEN 'LIFEWORLD_PUBLIC_ALPHA_GCP144_V1' END THEN
  RAISE EXCEPTION 'STOP database marker mismatch';
 END IF;
 IF current_user<>(SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='lw_core_draft') THEN
  RAISE EXCEPTION 'STOP: DBA must select reviewed existing schema owner role';
 END IF;
 IF to_regclass('lw_core_draft.person_basic_details') IS NOT NULL OR to_regclass('lw_core_draft.person_employments') IS NOT NULL THEN
  RAISE EXCEPTION 'STOP: existing target requires receipt and definition review, no automatic replay';
 END IF;
END $gate$;
CREATE TABLE lw_core_draft.person_basic_details (
 person_id text PRIMARY KEY, owner_id text NOT NULL,
 birth_year integer, birth_month integer, birth_day integer,
 source_kind text NOT NULL CHECK(source_kind IN ('manual','raw')),
 source_experience_id text, evidence_type text CHECK(evidence_type IN ('stated_by_person','observed_by_user','documented_source')),
 source_quote text, source_status text NOT NULL DEFAULT 'active' CHECK(source_status IN ('active','withdrawn')),
 confirmed_at timestamptz NOT NULL, revision integer NOT NULL CHECK(revision>=1), updated_at timestamptz NOT NULL,
 UNIQUE(person_id,owner_id),
 FOREIGN KEY(person_id,owner_id) REFERENCES lw_core_draft.people(id,owner_id),
 FOREIGN KEY(source_experience_id,owner_id) REFERENCES lw_core_draft.experiences(id,owner_id),
 CHECK(source_kind<>'raw' OR (source_experience_id IS NOT NULL AND evidence_type IS NOT NULL AND source_quote IS NOT NULL AND length(source_quote)>0)),
 CONSTRAINT person_birthday_valid CHECK(
  (birth_year IS NULL AND birth_month IS NULL AND birth_day IS NULL) OR
  (birth_month IS NOT NULL AND birth_day IS NOT NULL AND birth_month BETWEEN 1 AND 12 AND birth_day>=1
   AND (birth_year IS NULL OR birth_year BETWEEN 1 AND 9999)
   AND birth_day<=CASE WHEN birth_month IN (1,3,5,7,8,10,12) THEN 31 WHEN birth_month IN (4,6,9,11) THEN 30
    WHEN birth_month=2 THEN CASE WHEN birth_year IS NULL OR birth_year%400=0 OR (birth_year%4=0 AND birth_year%100<>0) THEN 29 ELSE 28 END ELSE 0 END))
);
CREATE INDEX person_basic_details_owner_idx ON lw_core_draft.person_basic_details(owner_id,person_id);
CREATE INDEX person_basic_details_source_idx ON lw_core_draft.person_basic_details(owner_id,source_experience_id) WHERE source_experience_id IS NOT NULL;
CREATE TABLE lw_core_draft.person_basic_detail_history (
 id text PRIMARY KEY, person_id text NOT NULL, owner_id text NOT NULL,
 revision integer NOT NULL CHECK(revision>=1),
 birth_year integer, birth_month integer, birth_day integer,
 source_kind text NOT NULL CHECK(source_kind IN ('manual','raw')), source_experience_id text,
 evidence_type text CHECK(evidence_type IN ('stated_by_person','observed_by_user','documented_source')),
 source_quote text, source_status text NOT NULL CHECK(source_status IN ('active','withdrawn')),
 change_kind text NOT NULL CHECK(change_kind IN ('created','corrected','cleared','source_withdrawn')),
 confirmed_at timestamptz NOT NULL, recorded_at timestamptz NOT NULL,
 UNIQUE(person_id,owner_id,revision),
 FOREIGN KEY(person_id,owner_id) REFERENCES lw_core_draft.person_basic_details(person_id,owner_id),
 FOREIGN KEY(source_experience_id,owner_id) REFERENCES lw_core_draft.experiences(id,owner_id)
);
CREATE TABLE lw_core_draft.person_employments (
 id text PRIMARY KEY, person_id text NOT NULL, owner_id text NOT NULL,
 company_name text NOT NULL DEFAULT '' CHECK(length(company_name)<=300),
 job_title text NOT NULL DEFAULT '' CHECK(length(job_title)<=300),
 employment_status text NOT NULL CHECK(employment_status IN ('current','past','unknown')),
 valid_from date, valid_to date,
 source_kind text NOT NULL CHECK(source_kind IN ('manual','raw')), source_experience_id text,
 evidence_type text CHECK(evidence_type IN ('stated_by_person','observed_by_user','documented_source')),
 source_quote text, source_status text NOT NULL DEFAULT 'active' CHECK(source_status IN ('active','withdrawn')),
 confirmed_at timestamptz NOT NULL, revision integer NOT NULL CHECK(revision>=1), created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,owner_id), UNIQUE(id,person_id,owner_id),
 FOREIGN KEY(person_id,owner_id) REFERENCES lw_core_draft.people(id,owner_id),
 FOREIGN KEY(source_experience_id,owner_id) REFERENCES lw_core_draft.experiences(id,owner_id),
 CHECK(length(btrim(company_name))>0 OR length(btrim(job_title))>0),
 CHECK(valid_from IS NULL OR valid_to IS NULL OR valid_from<=valid_to),
 CHECK(source_kind<>'raw' OR (source_experience_id IS NOT NULL AND evidence_type IS NOT NULL AND source_quote IS NOT NULL AND length(source_quote)>0))
);
CREATE INDEX person_employments_owner_person_idx ON lw_core_draft.person_employments(owner_id,person_id,employment_status);
CREATE INDEX person_employments_source_idx ON lw_core_draft.person_employments(owner_id,source_experience_id) WHERE source_experience_id IS NOT NULL;
CREATE TABLE lw_core_draft.person_employment_history (
 id text PRIMARY KEY, employment_id text NOT NULL, owner_id text NOT NULL, person_id text NOT NULL,
 revision integer NOT NULL CHECK(revision>=1),
 company_name text NOT NULL, job_title text NOT NULL,
 employment_status text NOT NULL CHECK(employment_status IN ('current','past','unknown')),
 valid_from date, valid_to date,
 source_kind text NOT NULL CHECK(source_kind IN ('manual','raw')), source_experience_id text,
 evidence_type text CHECK(evidence_type IN ('stated_by_person','observed_by_user','documented_source')),
 source_quote text, source_status text NOT NULL CHECK(source_status IN ('active','withdrawn')),
 change_kind text NOT NULL CHECK(change_kind IN ('created','corrected','source_withdrawn')),
 confirmed_at timestamptz NOT NULL, recorded_at timestamptz NOT NULL,
 UNIQUE(employment_id,owner_id,revision),
 FOREIGN KEY(employment_id,person_id,owner_id) REFERENCES lw_core_draft.person_employments(id,person_id,owner_id),
 FOREIGN KEY(person_id,owner_id) REFERENCES lw_core_draft.people(id,owner_id),
 FOREIGN KEY(source_experience_id,owner_id) REFERENCES lw_core_draft.experiences(id,owner_id)
);
-- 尚不加入正式Migration收據：需比對兩庫FK目標唯一鍵、核准名稱/版號後凍結。
-- 最小權限、History append-only與GuestPurger新增FK另行審查；不在本稿自行GRANT。
COMMIT;
