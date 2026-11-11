"""Unsupported platforms must stop before touching storage or input files."""
import json
import os
import pytest
from model_eval import core, cli

@pytest.mark.parametrize('platform', ['nt', 'java', 'unknown'])
def test_unsupported_platform_rejected_before_any_storage(monkeypatch, platform):
    monkeypatch.setattr(core, '_OS_NAME', platform, raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError('storage must not be touched')
    monkeypatch.setattr(core, 'Path', forbidden)
    monkeypatch.setattr(core.sqlite3, 'connect', forbidden)
    with pytest.raises(core.EvalError, match='^private_storage_platform_unsupported$'):
        core.EvaluationStore('synthetic-not-created')

@pytest.mark.parametrize('command', [
    ['prepare','--case','synthetic-missing.json','--request-id','synth'],
    ['show','synthetic-run'], ['stop','synthetic-run'],
    ['run','synthetic-run','--attempt-id','synth'],
    ['retry','synthetic-run','--attempt-id','synth'],
    ['score','synthetic-run','--scores','synthetic-missing.json'],
])
def test_windows_cli_fails_closed_without_file_access(monkeypatch, capsys, command):
    monkeypatch.setattr(core, '_OS_NAME', 'nt', raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError('storage or input must not be touched')
    monkeypatch.setattr(core, 'Path', forbidden)
    monkeypatch.setattr(cli, 'Path', forbidden)
    assert cli.main(['--directory','synthetic-not-created', *command]) == 2
    output = capsys.readouterr().out
    assert 'private_storage_platform_unsupported' in output


@pytest.mark.skipif(os.name == 'posix', reason='Native unsupported-platform rejection only; POSIX storage success is tested separately')
def test_native_unsupported_platform_constructor_rejects_before_storage(monkeypatch, record_property):
    record_property('native_os_name', os.name)
    record_property('scope', 'native_platform_rejection_not_storage_functionality_or_ACL_validation')
    assert core._OS_NAME == os.name
    def forbidden(*args, **kwargs):
        raise AssertionError('storage must not be touched')
    monkeypatch.setattr(core, 'Path', forbidden)
    monkeypatch.setattr(core.sqlite3, 'connect', forbidden)
    with pytest.raises(core.EvalError, match='^private_storage_platform_unsupported$'):
        core.EvaluationStore('synthetic-not-created')


@pytest.mark.skipif(os.name == 'posix', reason='Native unsupported-platform rejection only; POSIX CLI storage success is tested separately')
@pytest.mark.parametrize('command', [
    ['prepare', '--case', 'synthetic-missing.json', '--request-id', 'synth'],
    ['show', 'synthetic-run'], ['stop', 'synthetic-run'],
    ['run', 'synthetic-run', '--attempt-id', 'synth'],
    ['retry', 'synthetic-run', '--attempt-id', 'synth'],
    ['score', 'synthetic-run', '--scores', 'synthetic-missing.json'],
])
def test_native_unsupported_platform_cli_rejects_before_files(monkeypatch, capsys, record_property, command):
    record_property('native_os_name', os.name)
    record_property('scope', 'native_platform_rejection_not_storage_functionality_or_ACL_validation')
    assert core._OS_NAME == os.name
    def forbidden(*args, **kwargs):
        raise AssertionError('storage or input must not be touched')
    monkeypatch.setattr(core, 'Path', forbidden)
    monkeypatch.setattr(cli, 'Path', forbidden)
    monkeypatch.setattr(core.sqlite3, 'connect', forbidden)
    assert cli.main(['--directory', 'synthetic-not-created', *command]) == 2
    assert json.loads(capsys.readouterr().out) == {'error': 'private_storage_platform_unsupported'}
