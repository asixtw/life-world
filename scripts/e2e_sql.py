"""從唯一 canonical 31 表來源產生受 DB marker 保護的 SQL；不連線資料庫。"""
import argparse
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / 'docs/database/schema-2026-11-02/POSTGRESQL_CORE_DRAFT.sql'
GUARD = """DO $guard$
BEGIN
  IF current_database()<>'life_world_e2e' OR
     shobj_description((SELECT oid FROM pg_database WHERE datname=current_database()),'pg_database')
       IS DISTINCT FROM 'LIFEWORLD_E2E_SYNTHETIC_ONLY_v1' THEN
    RAISE EXCEPTION 'Refusing non-E2E database';
  END IF;
  IF current_setting('server_version_num')::int<>180006 THEN RAISE EXCEPTION 'PostgreSQL 18.6 required'; END IF;
END $guard$;
"""


def schema_sql():
    """每次取同一 canonical DDL，不維護第二份長期 schema。"""
    text = CORE.read_text(encoding='utf-8')
    digest = hashlib.sha256(text.encode()).hexdigest()
    # Guard 與 DDL 共用 canonical 的交易；禁止錯誤後落到別的 DB 繼續 DDL／REVOKE。
    assert text.count('BEGIN;')==text.count('COMMIT;')==1
    wrapped = text.replace('BEGIN;', 'BEGIN;\n'+GUARD+
        'SET LOCAL ROLE lw_e2e_owner;\nREVOKE CREATE ON SCHEMA public FROM PUBLIC;\n',1)
    return '-- Generated from canonical core DDL; normalized UTF-8 SHA256 '+digest+'\n'+wrapped


def audit_sql(run_id, points=1):
    """只允許 UUID hex 與正整數進入產生的固定驗證 SQL，不接收任意 SQL／識別字。"""
    if not re.fullmatch(r'[0-9a-f]{32}',run_id) or type(points) is not int or points<1:
        raise ValueError('Invalid synthetic run identifier or points')
    # Guard、查核與 PASS 同一唯讀交易；任一檢查失敗即中止，未設 ON_ERROR_STOP 也印不出 PASS。
    return 'BEGIN READ ONLY;\n'+GUARD+f"""
DO $audit$
DECLARE a text; b text;
BEGIN
 SELECT id INTO STRICT a FROM lw_core_draft.users WHERE name='E2E-{run_id}-A';
 SELECT id INTO STRICT b FROM lw_core_draft.users WHERE name='E2E-{run_id}-B';
 IF a=b OR (SELECT count(*) FROM lw_core_draft.goals WHERE owner_id IN (a,b))<>2 OR
    (SELECT count(*) FROM lw_core_draft.actions WHERE owner_id IN (a,b))<>6 OR
    (SELECT count(*) FROM lw_core_draft.experiences WHERE owner_id=a)<>1 OR
    (SELECT count(*) FROM lw_core_draft.reward_ledger WHERE owner_id=a)<>1 OR
    (SELECT sum(points) FROM lw_core_draft.reward_ledger WHERE owner_id=a) IS DISTINCT FROM {points} OR
    (SELECT count(*) FROM lw_core_draft.contributions WHERE owner_id=a)<>1 OR
    (SELECT sum(quantity) FROM lw_core_draft.contributions WHERE owner_id=a) IS DISTINCT FROM 0.123456::numeric OR
    (SELECT count(*) FROM lw_core_draft.tasks WHERE owner_id=a)<>1 OR
    (SELECT count(*) FROM lw_core_draft.experience_stories WHERE owner_id=a)<>1 OR
    (SELECT count(*) FROM lw_core_draft.experiences WHERE owner_id=b)<>0 OR
    (SELECT count(*) FROM lw_core_draft.requests WHERE owner_id=a AND operation='confirm')<>1 OR
    (SELECT count(*) FROM lw_core_draft.requests WHERE owner_id=a AND request_id='{run_id}-rollback')<>0 OR
    (SELECT count(*) FROM lw_core_draft.drafts WHERE owner_id=a AND status='draft' AND raw_text='LIFEWORLD_E2E_SYNTHETIC rollback')<>1 THEN
   RAISE EXCEPTION 'E2E persistence, idempotency, owner or rollback audit failed';
 END IF;
END $audit$;
SELECT 'E2E_DATABASE_AUDIT_PASS' AS result;
COMMIT;
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True)
    parser.add_argument('--run-id')
    parser.add_argument('--points',type=int,default=1)
    args = parser.parse_args(); target = Path(args.out); target.mkdir(parents=True,exist_ok=True)
    for path in (ROOT/'deploy/postgres/e2e').glob('*.sql'):
        (target/path.name).write_text(path.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
    (target/'01_schema.sql').write_text(schema_sql(),encoding='utf-8',newline='\n')
    if args.run_id:
        (target/'30_verify_run.sql').write_text(audit_sql(args.run_id,args.points),encoding='utf-8',newline='\n')
    print('Prepared E2E SQL only; no database or GCP connection')


if __name__=='__main__':
    main()
