"""Alpha候選的離線配置檢查；只讀JSON，不部署、不讀Secret、不連DB。"""
import argparse
import json
from pathlib import Path


def validate(plan):
    """拒絕錯庫／管理角色及未封頂AI；成功無副作用，錯誤僅含固定碼。"""
    env=plan['env']
    expected={'LIFEWORLD_DB_BACKEND':'postgresql','LIFEWORLD_DB_NAME':'life_world_alpha','LIFEWORLD_DB_USER':'lw_alpha_app','LIFEWORLD_DB_SCHEMA':'lw_core_draft'}
    if any(env.get(k)!=v for k,v in expected.items()):raise ValueError('wrong_alpha_target')
    if 'LIFEWORLD_TEST_ACCOUNT_SEED' in env:raise ValueError('startup_seed_forbidden')
    if 'LIFEWORLD_DB_PASSWORD' in env:raise ValueError('plaintext_password_forbidden')
    ref=plan.get('secret_refs',{}).get('LIFEWORLD_DB_PASSWORD','')
    # 必須指定版本；這僅驗證提案，不證明Secret存在或SA已有權限。
    import re
    if not re.fullmatch(r'lw-public-alpha-db-password/versions/[1-9][0-9]*',ref):raise ValueError('fixed_alpha_secret_required')
    if env.get('LIFEWORLD_AI_CALLS_APPROVED')=='true':
        total=int(env.get('LIFEWORLD_AI_TOTAL_BUDGET_MICROUSD','0'))
        historical=plan.get('historical_reservation_microusd')
        reserve=int(env.get('LIFEWORLD_AI_RESERVATION_MICROUSD','0'))
        daily=int(env.get('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD','0'))
        owner=int(env.get('LIFEWORLD_AI_OWNER_DAILY_CALLS','0'))
        global_calls=int(env.get('LIFEWORLD_AI_GLOBAL_DAILY_CALLS','0'))
        if type(historical) is not int or historical<0:raise ValueError('historical_cost_unreconciled')
        if not 0<reserve<=daily<=total or total+historical>20_000_000:raise ValueError('ai_budget_not_bounded')
        if not 0<owner<=global_calls:raise ValueError('ai_calls_not_bounded')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True)
    args=parser.parse_args()
    try:validate(json.loads(Path(args.plan).read_text()))
    except (ValueError,KeyError,TypeError,OSError):
        print('FAIL: invalid Alpha release configuration');return 1
    print('READY: offline configuration only; IAM/network/DB/login/AI acceptance NOT RUN');return 0


if __name__=='__main__':raise SystemExit(main())
