"""Cloud Run e2e CLI：Token 僅由 stdin 讀入，不接受金鑰或自動操作 GCP。"""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

from scripts.e2e_safety import SafetyError, validate_plan, check_token
from scripts.e2e_flow import run_acceptance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True,help='15 分鐘內匯出的 Service／兩個 Revision／IAM JSON')
    parser.add_argument('--report',required=True)
    parser.add_argument('--token-stdin',required=True,action='store_true')
    parser.add_argument('--retired',action='store_true',help='Tag 移除後只驗主要 Revision 關閉，不新增資料')
    args = parser.parse_args()
    try:
        plan = json.loads(Path(args.plan).read_text(encoding='utf-8-sig'))
        if plan.get('mode')!='cloud': raise SafetyError('cli_cloud_only')
        result = run_acceptance(plan,sys.stdin.read().strip(),retired=args.retired)
    except Exception:
        # 連讀檔／TLS 初始化失敗也留下固定失敗紀錄，不能把原始輸入包入診斷。
        result = {'passed':False,'run_id':uuid4().hex,'mode':'cloud','database_cleanup':'requires_operator_review',
                  'checks':[{'name':'configuration_or_transport','expected':'valid_input_and_transport','actual':'rejected',
                             'status':'FAIL','reason':'invalid_input_or_transport'}]}
    try:
        Path(args.report).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'passed':result['passed'],'run_id':result['run_id'],'checks':len(result['checks']),
                          'cleanup':result['database_cleanup']}))
        return 0 if result['passed'] else 1
    except Exception:
        print('E2E failed: invalid input, TLS/transport or report output; no credential details emitted',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
