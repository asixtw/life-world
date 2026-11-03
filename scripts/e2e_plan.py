"""組合操作者自行匯出的 GCP JSON，離線檢查後才產生驗收 plan；不呼叫 gcloud。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from scripts.e2e_safety import validate_plan, source_digest, SafetyError, require, SOURCE_KEYS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('service','main-revision','tag-revision','iam-policy','project-number','out'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--retired',action='store_true')
    parser.add_argument('--snapshot-evidence',help='匯出時建立的證據 JSON；預設為 service JSON 同目錄的 snapshot-evidence.json')
    args = parser.parse_args()
    try:
        evidence_path = Path(args.snapshot_evidence) if args.snapshot_evidence else Path(args.service).parent/'snapshot-evidence.json'
        evidence = json.loads(evidence_path.read_text(encoding='utf-8-sig'))
        result = {'mode':'cloud','project_id':'life-world-513506','project_number':args.project_number,
                  'created_at':datetime.now(timezone.utc).isoformat(),'captured_at':evidence['started_at'],
                  'snapshot_evidence':evidence,'expected_points':1}
        require(set(evidence['sources'])==set(SOURCE_KEYS),'snapshot_evidence_sources')
        for key in SOURCE_KEYS:
            path = Path(getattr(args,key)); raw = path.read_bytes(); record = evidence['sources'][key]
            require(record['filename']==path.name and record['sha256']==hashlib.sha256(raw).hexdigest(), 'snapshot_source_hash')
            result[key] = json.loads(raw.decode('utf-8-sig'))
            digest = source_digest(result[key])
            require(record.get('content_sha256',digest)==digest,'snapshot_plan_content_hash')
            record['content_sha256'] = digest
        validate_plan(result,retired=args.retired)
        Path(args.out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Offline E2E plan validated; no GCP changes or credentials emitted')
        return 0
    except SafetyError as error:
        print('Plan rejected: '+str(error),file=sys.stderr)
    except Exception:
        print('Plan rejected: unreadable or malformed snapshot',file=sys.stderr)
    return 2


if __name__=='__main__':
    raise SystemExit(main())
