"""建置安全邊界：驗證 API 產物後，只能經由既有安全發布器部署。"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_api_build_releases_only_after_test_build_verify_and_push():
    config = yaml.safe_load((ROOT / 'deploy/cloudbuild.api.yaml').read_text(encoding='utf-8'))
    assert config['serviceAccount'] == 'projects/life-world-513506/serviceAccounts/lw-build-main@life-world-513506.iam.gserviceaccount.com'
    steps = config['steps']
    ids = [step['id'] for step in steps]
    assert ids.index('sqlite-and-real-pg18-tests') < ids.index('api-image-build') < ids.index('api-container-verification') < ids.index('api-image-push')
    image = 'asia-east1-docker.pkg.dev/life-world-513506/lw-containers/lw-api:${COMMIT_SHA}-${BUILD_ID}'
    # 明確 Push 必須先於發布；不得讓 images 在切流量後重複上傳。
    assert 'images' not in config
    assert ids[-2:] == ['api-image-push', 'deploy-main']
    release = steps[-1]
    assert release['name'] == 'gcr.io/google.com/cloudsdktool/google-cloud-cli:slim'
    assert release['entrypoint'] == '/usr/lib/google-cloud-sdk/platform/bundledpythonunix/bin/python3'
    assert release['args'] == ['deploy/release.py', '--component', 'api',
                               '--commit', '$COMMIT_SHA', '--build-id', '$BUILD_ID',
                               '--branch', '$BRANCH_NAME']
    build = steps[ids.index('api-image-build')]['args']
    assert image in build and 'VCS_REF=${COMMIT_SHA}' in build and 'deploy/Dockerfile.api' in build
    assert steps[ids.index('api-image-push')]['args'] == ['push', image]
    commands = '\n'.join('\n'.join(s.get('args',[])) for s in steps)
    assert 'gcloud ' not in commands and 'lw-web' not in commands
    assert 'run deploy' not in commands and 'triggers' not in commands
    # YAML 不得繞過發布器，另加公開存取、IAM、Cloud SQL 或 hostfix 改動。
    for forbidden in ('--allow-unauthenticated', '--no-invoker-iam-check', 'allUsers',
                      'allAuthenticatedUsers', 'set-iam-policy', 'add-iam-policy-binding',
                      'sql instances', 'sql databases', 'sql users', '--clear-tags',
                      '--remove-tags=hostfix', '--tag=hostfix'):
        assert forbidden not in commands
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


def node_step():
    config = yaml.safe_load((ROOT / 'deploy/cloudbuild.api.yaml').read_text(encoding='utf-8'))
    return next(s for s in config['steps'] if s['id'] == 'sqlite-and-real-pg18-tests')['args'][-1]


def test_release_tests_get_the_pinned_node_before_both_pytest_runs():
    """Node 前端契約（例如 test_person_choices_frontend.py 直接讀 LIFEWORLD_NODE）是發布測試的一部分。
    1a02a82 的 Cloud Build 在這一步沒有 Node，KeyError 讓 Step 3 失敗，後續建置與發布都沒有執行。
    SQLite 與 PostgreSQL 兩輪都要拿到同一個 Node；版本跟 web 建置（collaboration/ui-kit/Dockerfile）一致，
    避免兩條建置用不同的前端執行環境驗證同一批 JS。"""
    lines = [line.strip() for line in node_step().splitlines()]
    runs = [i for i, line in enumerate(lines) if 'pytest tests' in line]
    exports = [i for i, line in enumerate(lines) if line.startswith('export LIFEWORLD_NODE=')]
    assert len(runs) == 2 and len(exports) == 1 and exports[0] < runs[0]
    web = re.search(r'^FROM node:(\d+\.\d+\.\d+)-', (ROOT / 'collaboration/ui-kit/Dockerfile').read_text(encoding='utf-8'), re.M)[1]
    assert f'https://nodejs.org/dist/v{web}/node-v{web}-linux-x64.tar.xz' in node_step()


def test_release_node_download_is_refused_when_the_checksum_does_not_match(tmp_path, monkeypatch):
    """下載內容和固定的官方 SHA-256 不符就停止，不寫出 node、不讓測試用來源不明的執行檔。不連網。"""
    script = node_step()
    code = script.split("python - <<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.step10-tests').mkdir()
    import io
    import urllib.request
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *args, **kwargs: io.BytesIO(b'not the official archive'))
    try:
        exec(compile(code, 'cloudbuild-node', 'exec'), {'__name__': '__main__'})
    except SystemExit as stop:
        assert stop.code and 'SHA-256' in str(stop.code)
    else:
        raise AssertionError('checksum mismatch must stop the build step')
    assert not (tmp_path / '.step10-tests/node').exists()


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
