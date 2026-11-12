"""本機評測入口與外部gateway邊界；HTTP transport全部為明示替身。"""
import json
import os
from pathlib import Path

import pytest
from model_eval.core import EvaluationStore, EvalError, ModelResult
from model_eval.cli import main
from model_eval.gateway import JsonGatewayProvider
from test_model_eval import case


@pytest.mark.skipif(os.name != "posix", reason="POSIX storage contract; Windows product storage is disabled, POSIX functionality is tested separately")
def test_cli_prepares_and_shows_without_network(tmp_path, capsys):
    source = tmp_path / 'case.json'; source.write_text(json.dumps(case()))
    directory = tmp_path / 'private-eval'
    assert main(['--directory', str(directory), 'prepare', '--case', str(source), '--request-id', 'one']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'prepared' and result['model'] == 'not-configured'
    assert main(['--directory', str(directory), 'show', result['id']]) == 0
    assert json.loads(capsys.readouterr().out)['case']['synthetic_only']


@pytest.mark.skipif(os.name != "posix", reason="POSIX storage contract; Windows product storage is disabled, POSIX functionality is tested separately")
def test_cli_unapproved_run_is_blocked_and_does_not_read_key(tmp_path, capsys, monkeypatch):
    source = tmp_path / 'case.json'; source.write_text(json.dumps(case()))
    args = ['--directory', str(tmp_path / 'store')]
    assert main(args + ['prepare', '--case', str(source), '--request-id', 'one']) == 0
    run = json.loads(capsys.readouterr().out)['id']
    assert main(args + ['run', run, '--attempt-id', 'try-1']) == 2
    assert 'approval_required' in capsys.readouterr().out
    assert EvaluationStore(tmp_path / 'store').get(run)['attempts'] == []


def test_gateway_shape_usage_key_callback_and_no_auto_retry():
    requests, keys = [], []
    def transport(endpoint, body, headers, timeout):
        requests.append((endpoint, json.loads(body), headers, timeout))
        return {'text': '合成回應', 'usage': {'input_tokens': 12, 'output_tokens': 8}, 'cost_microusd': 6, 'request_id': 'gateway-synthetic'}
    provider = JsonGatewayProvider('approved-gateway', 'test-model', 'https://example.test/infer',
                                   key_supplier=lambda: keys.append(1) or 'SYNTHETIC-SECRET', transport=transport)
    result = provider.generate({'system': '合成測試', 'case': case()}, 100)
    assert result == ModelResult('合成回應', 12, 8, 6, 'gateway-synthetic')
    assert keys == [1] and len(requests) == 1
    assert requests[0][1]['max_output_tokens'] == 100
    assert 'SYNTHETIC-SECRET' not in repr(provider)
    assert 'SYNTHETIC-SECRET' not in json.dumps(provider.metadata)


@pytest.mark.parametrize('url', ['http://example.test/infer', 'https://user:secret@example.test/infer', 'https://example.test/infer?key=secret', 'https://example.test/infer#secret'])
def test_gateway_rejects_unsafe_endpoint(url):
    with pytest.raises(EvalError): JsonGatewayProvider('gateway', 'model', url, key_supplier=lambda: 'synthetic')


def test_gateway_does_not_rotate_keys_on_failure():
    calls, keys = [], []
    def fail(*args): calls.append(1); raise RuntimeError('provider quota SYNTHETIC-SECRET')
    provider = JsonGatewayProvider('gateway', 'model', 'https://example.test/infer', key_supplier=lambda: keys.append(1) or 'synthetic', transport=fail)
    with pytest.raises(EvalError, match='gateway_failed'): provider.generate({}, 100)
    assert len(calls) == len(keys) == 1


@pytest.mark.skipif(os.name != "posix", reason="POSIX storage contract; Windows product storage is disabled, POSIX functionality is tested separately")
def test_prepared_gateway_cannot_change_endpoint(tmp_path):
    def transport(*args): return {'text': '合成'}
    first = JsonGatewayProvider('gateway', 'model', 'https://example.test/a', key_supplier=lambda: 'synthetic', transport=transport)
    second = JsonGatewayProvider('gateway', 'model', 'https://example.test/b', key_supplier=lambda: 'synthetic', transport=transport)
    store = EvaluationStore(tmp_path)
    run = store.prepare(case(), first, 'request')
    with pytest.raises(EvalError, match='provider_changed'): store.execute(run, second, 'attempt', approved_live=True)
