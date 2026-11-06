"""Bounded one-shot maintenance entry; operator scheduler invokes this, never HTTP."""
import argparse
from datetime import datetime,timezone
import json
import os
from .runtime import RuntimeSettings
from .postgres import PostgresDatabase
from .guest_lifecycle import GuestPurger


def run_batch(db,clock,limit=10):
    with db.connect() as c:
        jobs=c.execute("SELECT owner_id,attempts,media_attempts FROM guest_abandonments WHERE status<>'completed' AND purge_after<=? ORDER BY purge_after,owner_id LIMIT ?",(clock().isoformat(),limit)).fetchall()
    counts={};failed=False
    worker=GuestPurger(db,clock)
    for job in jobs:
        if job['attempts']>=5 or job['media_attempts']>=5:result='retry_exhausted'
        else:result=worker.purge(job['owner_id'])
        counts[result]=counts.get(result,0)+1
        if result not in ('completed','noop','not_due'):failed=True
        # Stop the batch on schema/owner/cross-owner error, never keep deleting.
        if result in ('unreviewed_fk','unreviewed_table','cross_owner_reference','owner_changed','fk_cycle'):break
    return counts,failed


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--max-jobs',type=int,default=10)
    args=parser.parse_args()
    if not args.execute or not 1<=args.max_jobs<=50:raise SystemExit('Explicit --execute and max-jobs 1..50 required')
    s=RuntimeSettings.from_env()
    if s.backend!='postgresql' or s.db_name!='life_world_beta' or s.db_user!='lw_beta_maintenance' or os.environ.get('K_SERVICE'):raise SystemExit('Separate approved Beta maintenance process required')
    db=PostgresDatabase(s)
    try:
        counts,failed=run_batch(db,lambda:datetime.now(timezone.utc),args.max_jobs)
        print(json.dumps({'counts':counts,'alert':failed})) # no tokens/identity/provider error details
        raise SystemExit(2 if failed else 0)
    finally:db.close()


if __name__=='__main__':main()
