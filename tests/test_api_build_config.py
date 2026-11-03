"""建置安全邊界：測試先於 API 產物、不可加入部署或沿用 web image。"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_api_build_is_test_then_build_push_only():
    config = yaml.safe_load((ROOT / 'deploy/cloudbuild.api.yaml').read_text(encoding='utf-8'))
    assert config['serviceAccount'] == 'projects/life-world-513506/serviceAccounts/lw-build-main@life-world-513506.iam.gserviceaccount.com'
    steps = config['steps']
    ids = [step['id'] for step in steps]
    assert ids.index('sqlite-and-real-pg18-tests') < ids.index('api-image-build') < ids.index('api-container-verification') < ids.index('api-image-push')
    image = 'asia-east1-docker.pkg.dev/life-world-513506/lw-containers/lw-api:${COMMIT_SHA}-${BUILD_ID}'
    assert config['images'] == [image]
    build = steps[ids.index('api-image-build')]['args']
    assert image in build and 'VCS_REF=${COMMIT_SHA}' in build and 'deploy/Dockerfile.api' in build
    assert steps[ids.index('api-image-push')]['args'] == ['push', image]
    commands = '\n'.join('\n'.join(s.get('args',[])) for s in steps)
    assert 'gcloud ' not in commands and 'lw-web' not in commands
    assert 'run deploy' not in commands and 'triggers' not in commands
    assert 'staging' not in commands and 'lw-build-stg' not in config['serviceAccount']
    tests = steps[ids.index('sqlite-and-real-pg18-tests')]['args'][-1]
    assert tests.count('pytest tests') == 2
    assert 'LIFEWORLD_TEST_BACKEND=postgresql' in tests and 'pg_test_bootstrap.py' in tests


def substituted(script, sha='a' * 40, build_id='11111111-1111-4111-8111-111111111111', project='life-world-513506'):
    """只模擬一次 Cloud Build substitution，保留 $$ 轉出的 shell 變數。"""
    values = dict(COMMIT_SHA=sha, BUILD_ID=build_id, PROJECT_ID=project)
    return re.sub(r'\$\$|\$\{([A-Z_][A-Z_0-9]*)\}|\$([A-Z_][A-Z_0-9]*)',
                  lambda match: '$' if match[0] == '$$' else values[match[1] or match[2]], script)


def bash():
    executable = r'C:\Program Files\Git\bin\bash.exe' if os.name == 'nt' else shutil.which('bash')
    assert executable and Path(executable).is_file(), 'Bash required for API build shell verification'
    return [executable, '--noprofile', '--norc']


def test_api_build_shell_syntax_after_substitution():
    config = yaml.safe_load((ROOT / 'deploy/cloudbuild.api.yaml').read_text(encoding='utf-8'))
    for step in config['steps']:
        if step.get('entrypoint') in ('bash', 'sh'):
            result = subprocess.run(bash() + ['-n'], input=substituted(step['args'][-1]),
                                    capture_output=True, text=True, encoding='utf-8')
            assert result.returncode == 0, (step['id'], result.stderr)


def test_api_build_source_guards_reject_missing_or_invalid_identity(tmp_path):
    """只執行本機來源驗證，不啟動 Docker、不呼叫任何 GCP 工具。"""
    config = yaml.safe_load((ROOT / 'deploy/cloudbuild.api.yaml').read_text(encoding='utf-8'))
    script = config['steps'][0]['args'][-1]
    cases = [('a' * 40, '1' * 36, 'life-world-513506', True),
             ('', '1' * 36, 'life-world-513506', False),
             ('g' * 40, '1' * 36, 'life-world-513506', False),
             ('a' * 41, '1' * 36, 'life-world-513506', False),
             ('a' * 40, '', 'life-world-513506', False),
             ('a' * 40, 'x' * 36, 'life-world-513506', False),
             ('a' * 40, '1' * 36, 'wrong-project', False)]
    for index, (sha, build_id, project, valid) in enumerate(cases):
        directory = tmp_path / str(index)
        (directory / 'deploy').mkdir(parents=True)
        (directory / 'deploy/Dockerfile.api').touch()
        result = subprocess.run(bash() + ['-ceu', substituted(script, sha, build_id, project)],
                                cwd=directory, capture_output=True, text=True, encoding='utf-8')
        assert (result.returncode == 0) == valid, result.stderr
        assert (directory / '.step10-tests/synthetic.env').exists() == valid
