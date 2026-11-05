"""獨立本機入口；預設只準備案例，沒有供應商／預算批准不發外部請求。"""
import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace

from .core import EvaluationStore, EvalError
from .gateway import JsonGatewayProvider
from .gemini import GeminiProvider


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def parser():
    result = argparse.ArgumentParser(description='Life World 本機合成人物評測；與正式App資料隔離。')
    result.add_argument('--directory', default='.local/model-eval')
    result.add_argument('--budget-microusd', type=int, default=1000000)
    result.add_argument('--max-attempts', type=int, default=10)
    commands = result.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--case', required=True)
    prepare.add_argument('--request-id', required=True)
    prepare.add_argument('--provider', default='not-configured')
    prepare.add_argument('--model', default='not-configured')
    prepare.add_argument('--gateway')
    prepare.add_argument('--reservation-microusd', type=int, default=100000)
    prepare.add_argument('--max-output-tokens', type=int, default=400)
    for name in ('show', 'stop', 'run', 'retry', 'score'):
        command = commands.add_parser(name)
        command.add_argument('run_id')
        if name in ('run', 'retry'):
            command.add_argument('--attempt-id', required=True)
            command.add_argument('--approval-file')
            command.add_argument('--key-env', default='LIFEWORLD_EVAL_API_KEY')
        if name == 'score':
            command.add_argument('--scores', required=True, help='評分JSON檔：values五項0–4，note人工說明')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        store = EvaluationStore(args.directory, args.budget_microusd, args.max_attempts)
        if args.command == 'prepare':
            data = json.loads(Path(args.case).read_text(encoding='utf-8'))
            provider = (GeminiProvider(args.model,key_supplier=lambda:None) if args.provider=='gemini' else JsonGatewayProvider(args.provider, args.model, args.gateway, key_supplier=lambda: None)
                        if args.gateway else SimpleNamespace(name=args.provider, model=args.model, live=False))
            run_id = store.prepare(data, provider, args.request_id, args.reservation_microusd, args.max_output_tokens)
            run = store.get(run_id)
            print_json({'id': run_id, 'status': run['status'], 'model': run['model'], 'external_called': False})
        elif args.command in ('run', 'retry'):
            if not args.approval_file:
                raise EvalError('approval_required')
            run = store.get(args.run_id)
            approval = json.loads(Path(args.approval_file).read_text(encoding='utf-8'))
            config = run['prompt'].get('provider_configuration', {})
            expected = {'approved': True, 'provider': run['provider'], 'model': run['model'],
                        'endpoint': config.get('endpoint'), 'budget_microusd': args.budget_microusd,
                        'max_attempts': args.max_attempts}
            if (not run['live'] or not approval.get('owner_reference') or not config.get('endpoint')
                    or any(approval.get(k) != v for k, v in expected.items())):
                raise EvalError('approval_mismatch')
            # CLI只讀既有環境注入，不呼叫Secret Manager、不列印key、不自動換key。
            provider = GeminiProvider(run['model'],key_supplier=lambda: os.environ.get(args.key_env)) if run['provider']=='gemini' else JsonGatewayProvider(run['provider'], run['model'], config['endpoint'],
                                           key_supplier=lambda: os.environ.get(args.key_env))
            result = store.execute(args.run_id, provider, args.attempt_id, approved_live=True, retry=args.command == 'retry')
            latest = result['attempts'][-1]
            print_json({'id': result['id'], 'status': result['status'], 'actual_cost_microusd': latest['actual_cost'],
                        'charged_microusd': latest['charged'], 'latency_ms': latest['latency_ms']})
        elif args.command == 'show':
            print_json(store.get(args.run_id))
        elif args.command == 'stop':
            print_json({'id': args.run_id, 'status': store.stop(args.run_id)['status']})
        elif args.command == 'score':
            data = json.loads(Path(args.scores).read_text(encoding='utf-8'))
            scored = store.score(args.run_id, data['values'], data.get('note', ''))
            print_json({'id': args.run_id, 'scores': scored['scores']})
        return 0
    except EvalError as exc:
        print_json({'error': str(exc)})
        return 2
    except Exception:
        print_json({'error': 'invalid_local_input'})
        return 2
