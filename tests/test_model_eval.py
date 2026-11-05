"""只測獨立合成評測；測試provider明示替身，絕不呼叫外部服務。"""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import threading

import pytest
from model_eval.core import EvaluationStore, EvalError, ModelResult, SCORE_FIELDS


class Stub:
    name, model, live = 'synthetic-test-double', 'not-a-real-model', False
    def __init__(self): self.calls = 0
    def generate(self, prompt, max_output_tokens):
        self.calls += 1
        return ModelResult('我目前只知道來源中提到的安排。', 20, 12)


def case():
    return {'synthetic_only': True, 'case_id': 'synthetic-001', 'scenario': '討論下週合成作品',
            'objective': '確認角色限制', 'character': {'id': 'synth-a', 'name': '合成小安', 'version': '1',
                'traits': ['謹慎'], 'boundaries': ['未知不補造']},
            'sources': [{'id': 'synth-source', 'version': '1', 'text': '角色僅在週末有空。'}],
            'turns': [{'speaker': 'user', 'text': '你何時方便？'}]}


def test_records_snapshot_unknown_cost_human_score_and_no_product_tables(tmp_path):
    store, provider = EvaluationStore(tmp_path), Stub()
    data = case()
    run = store.prepare(data, provider, 'request-1')
    data['sources'][0]['text'] = '後來改動'
    result = store.execute(run, provider, 'attempt-1')
    assert result['status'] == 'completed'
    assert result['case']['sources'][0]['text'] == '角色僅在週末有空。'
    assert result['prompt']['version'] == 'theater-eval-v1'
    assert result['provider'] == provider.name and result['model'] == provider.model
    attempt = result['attempts'][0]
    assert attempt['actual_cost'] is None and attempt['charged'] == 100000
    assert attempt['input_tokens'] == 20 and attempt['output_tokens'] == 12
    assert attempt['latency_ms'] >= 0 and attempt['output']
    scored = store.score(run, {key: 3 for key in SCORE_FIELDS}, '合成案例人工核對')
    assert scored['scores']['note'] == '合成案例人工核對'
    with sqlite3.connect(store.path) as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {'policy', 'runs', 'attempts'}
    assert store.path.stat().st_mode & 0o777 == 0o600


def test_idempotent_run_and_attempt_conflict(tmp_path):
    store, provider = EvaluationStore(tmp_path), Stub()
    run = store.prepare(case(), provider, 'same')
    assert store.prepare(case(), provider, 'same') == run
    changed = case(); changed['objective'] = '不同目的'
    with pytest.raises(EvalError, match='request_conflict'):
        store.prepare(changed, provider, 'same')
    store.execute(run, provider, 'same-attempt')
    assert store.execute(run, provider, 'same-attempt')['status'] == 'completed'
    assert provider.calls == 1
    with pytest.raises(EvalError): store.execute(run, provider, 'new-attempt')


def test_live_provider_never_called_without_approval(tmp_path):
    store, provider = EvaluationStore(tmp_path), Stub()
    provider.live = True
    run = store.prepare(case(), provider, 'live')
    with pytest.raises(EvalError, match='not_approved'): store.execute(run, provider, 'attempt')
    assert provider.calls == 0 and store.get(run)['attempts'] == []


def test_failure_is_sanitized_and_one_explicit_retry_is_charged(tmp_path):
    store, provider = EvaluationStore(tmp_path), Stub()
    def fail(*args):
        provider.calls += 1
        raise RuntimeError('SECRET-CANARY')
    provider.generate = fail
    run = store.prepare(case(), provider, 'fail')
    first = store.execute(run, provider, 'fail-attempt')
    assert first['status'] == 'failed' and 'SECRET-CANARY' not in json.dumps(first)
    assert store.execute(run, provider, 'retry-1', retry=True)['status'] == 'failed'
    assert store.execute(run, provider, 'retry-1', retry=True)['status'] == 'failed'
    assert provider.calls == 2
    with pytest.raises(EvalError): store.execute(run, provider, 'retry-2', retry=True)


def test_stop_discards_late_output_but_preserves_usage(tmp_path):
    store, provider = EvaluationStore(tmp_path), Stub()
    entered, release = threading.Event(), threading.Event()
    def delayed(*args):
        entered.set(); assert release.wait(3)
        return ModelResult('未展示的合成台詞', 22, 10, 20000)
    provider.generate = delayed
    run = store.prepare(case(), provider, 'stop')
    with ThreadPoolExecutor() as pool:
        job = pool.submit(store.execute, run, provider, 'attempt')
        assert entered.wait(3)
        assert store.stop(run)['status'] == 'stopped'
        release.set()
        result = job.result()
    assert result['status'] == 'stopped'
    assert result['attempts'][0]['output'] is None
    assert result['attempts'][0]['status'] == 'late_discarded'
    assert result['attempts'][0]['actual_cost'] == 20000


def test_shared_budget_is_atomic_across_independent_stores(tmp_path):
    stores = [EvaluationStore(tmp_path, budget_microusd=200000) for _ in range(3)]
    providers = [Stub() for _ in range(6)]
    runs = [stores[i % 3].prepare(case(), providers[i], 'request-' + str(i)) for i in range(6)]
    def execute(i):
        try: return stores[i % 3].execute(runs[i], providers[i], 'attempt-' + str(i))['status']
        except EvalError as exc: return str(exc)
    with ThreadPoolExecutor(max_workers=6) as pool: outcomes = list(pool.map(execute, range(6)))
    assert outcomes.count('completed') == 2 and outcomes.count('budget_exhausted') == 4
    assert sum(p.calls for p in providers) == 2


@pytest.mark.parametrize('field,value', [('synthetic_only', False), ('sources', []), ('turns', []), ('character', {})])
def test_invalid_cases_are_rejected(tmp_path, field, value):
    data = case(); data[field] = value
    with pytest.raises(EvalError): EvaluationStore(tmp_path).prepare(data, Stub(), 'invalid')


def test_policy_cannot_be_raised_by_other_process(tmp_path):
    EvaluationStore(tmp_path, budget_microusd=100000)
    with pytest.raises(EvalError, match='policy_conflict'): EvaluationStore(tmp_path, budget_microusd=200000)
