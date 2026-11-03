"""組合操作者自行匯出的 GCP JSON，離線檢查後才產生驗收 plan；不呼叫 gcloud。"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from scripts.e2e_safety import validate_plan, SafetyError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('service','main-revision','tag-revision','iam-policy','project-number','out'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--retired',action='store_true')
    args = parser.parse_args()
    try:
        result = {'mode':'cloud','project_id':'life-world-513506','project_number':args.project_number,
                  'captured_at':datetime.now(timezone.utc).isoformat(),'expected_points':1}
        for key in ('service','main_revision','tag_revision','iam_policy'):
            result[key] = json.loads(Path(getattr(args,key)).read_text(encoding='utf-8-sig'))
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
