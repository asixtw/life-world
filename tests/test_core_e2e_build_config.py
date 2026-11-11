"""M0：lw-core-e2e 映像的建置設定（只讀檔案；以本機 Bash 模擬 Cloud Build 的替換值；不執行 Docker 或 Cloud Build）。"""
import difflib
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
IMAGE_PREFIX = 'asia-east1-docker.pkg.dev/life-world-513506/lw-containers/lw-core-e2e:'


def lines(path):
    return (ROOT / path).read_text(encoding='utf-8').replace('\r\n', '\n').split('\n')


def build_config():
    return yaml.safe_load((ROOT / 'deploy/cloudbuild.core-e2e.yaml').read_text(encoding='utf-8'))


# ---------- Dockerfile ----------

def test_core_dockerfile_differs_from_api_only_by_marker_and_healthcheck_host():
    api = [line for line in lines('deploy/Dockerfile.api') if not line.startswith('# API 專用映像')]
    core = [line for line in lines('deploy/Dockerfile.core-e2e') if not line.startswith(('# M0', '# 1.', '#    app/', '# 2.', '# 修改 Dockerfile.api'))]
    changes = [op for op in difflib.SequenceMatcher(a=api, b=core, autojunk=False).get_opcodes() if op[0] != 'equal']
    # 只允許兩處：加入映像標記的 RUN、HEALTHCHECK 的指令改為帶 Host
    assert [(tag, i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in changes] == [('insert', 0, 1), ('replace', 1, 1)]
    inserted = core[changes[0][3]]
    assert inserted.startswith('RUN mkdir -p /etc/lifeworld') and "printf 'core-e2e\\n' > /etc/lifeworld/deployment-profile" in inserted
    assert 'chown root:root' in inserted and 'chmod 0444 /etc/lifeworld/deployment-profile' in inserted
    assert core.index(inserted) < core.index('USER 10001:10001')  # 以 root 建立，之後才切換成 runtime 使用者
    assert "headers={'Host':h}" in core[changes[1][3]] and 'LIFEWORLD_TRUSTED_HOSTS' in core[changes[1][3]]
    assert not any('LIFEWORLD_DEPLOYMENT_PROFILE' in line for line in core)  # 不再依賴可被覆寫的 ENV


# ---------- Cloud Build 設定的結構 ----------

STEP_IDS = ['validate-target', 'verify-package', 'core-e2e-image-build', 'core-e2e-push-and-record']


def test_core_build_only_builds_and_pushes_the_dedicated_image():
    config = build_config()
    assert config['serviceAccount'].endswith('/lw-build-main@life-world-513506.iam.gserviceaccount.com')
    assert [step['id'] for step in config['steps']] == STEP_IDS
    assert 'images' not in config  # push 與 digest 由本設定自己的步驟處理並記錄
    body = (ROOT / 'deploy/cloudbuild.core-e2e.yaml').read_text(encoding='utf-8').split('steps:', 1)[1]
    for forbidden in ('run deploy', 'update-traffic', 'release.py', 'lw-api-main', 'set-iam-policy', 'add-iam-policy-binding', 'eval '):
        assert forbidden not in body
    assert config['substitutions'] == {'_SOURCE_MANIFEST_SHA256': '', '_PACKAGE_SHA256': ''}


def test_docker_build_argv_is_fixed_element_by_element():
    build = build_config()['steps'][2]
    assert build['name'] == 'gcr.io/cloud-builders/docker' and 'entrypoint' not in build  # exec 形式，沒有 shell
    assert build['args'] == ['build', '--build-arg', 'VCS_REF=68102f230aa947a434286ba9260e1ae75f6634b0',
                             '--label', 'org.lifeworld.source-manifest-sha256=${_SOURCE_MANIFEST_SHA256}',
                             '--label', 'org.lifeworld.package-sha256=${_PACKAGE_SHA256}',
                             '--label', 'org.lifeworld.build-id=$BUILD_ID',
                             '-f', 'deploy/Dockerfile.core-e2e',
                             '-t', IMAGE_PREFIX + 'm0-${_SOURCE_MANIFEST_SHA256}-$BUILD_ID', '.']


def test_substitutions_never_enter_bash_program_text():
    config = build_config()
    for step in config['steps']:
        if step.get('entrypoint') == 'bash':
            script = step['args'][-1]
            assert '${_' not in script and '$_' not in script  # 使用者的替換值只經由 options.env
            assert '$PROJECT_ID' not in script and '$BUILD_ID' not in script
    assert config['options']['env'] == ['CORE_SOURCE_SHA256=${_SOURCE_MANIFEST_SHA256}', 'CORE_PACKAGE_SHA256=${_PACKAGE_SHA256}',
                                        'CORE_PROJECT=$PROJECT_ID', 'CORE_BUILD_ID=$BUILD_ID']


def test_no_step_decides_by_error_message_text_or_reads_digest_back_from_a_tag():
    text = (ROOT / 'deploy/cloudbuild.core-e2e.yaml').read_text(encoding='utf-8').split('steps:', 1)[1]
    assert 'NOT_FOUND' not in text and 'not found' not in text.lower()
    assert 'images describe' not in text and 'tags list' not in text


# ---------- 以本機 Bash 模擬 Cloud Build 的替換與執行 ----------

def find_bash():
    for candidate in (r'C:\Program Files\Git\bin\bash.exe', shutil.which('bash')):
        if candidate and os.path.exists(candidate) and 'system32' not in candidate.lower():
            return candidate
    return None


BASH = find_bash()
needs_bash = pytest.mark.skipif(BASH is None, reason='本機沒有可用的 Bash（Git Bash）')
BUILD_A = '11111111-2222-4333-8444-555555555555'
BUILD_B = '66666666-7777-4888-9999-aaaaaaaaaaaa'


def substitute(value, values):
    """依 Cloud Build 的規則替換：先解析 YAML，再對字串值替換；$$ 是跳脫，最後才變成 $。"""
    if isinstance(value, dict):
        return {k: substitute(v, values) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, values) for v in value]
    if not isinstance(value, str):
        return value
    text = value.replace('$$', '\0')
    for key, replacement in values.items():
        text = text.replace('${' + key + '}', replacement).replace('$' + key, replacement)
    return text.replace('\0', '$')


def run_step(step_id, source_sha, workspace, extra_env=None, package_sha='b' * 64, build_id=BUILD_A):
    values = {'_SOURCE_MANIFEST_SHA256': source_sha, '_PACKAGE_SHA256': package_sha,
              'PROJECT_ID': 'life-world-513506', 'BUILD_ID': build_id}
    config = substitute(build_config(), values)
    step = next(s for s in config['steps'] if s['id'] == step_id)
    env = dict(os.environ, **(extra_env or {}))
    for entry in config['options']['env']:
        key, value = entry.split('=', 1)
        env[key] = value
    return subprocess.run([BASH, '-ceu', step['args'][-1]], cwd=workspace, env=env, capture_output=True, text=True, timeout=60)


def make_workspace(tmp_path, extra_file=None):
    """建立一份合成的上傳內容，以及它的來源清單（格式與 Prepare-CoreE2EBuild.ps1 相同）。"""
    workspace = tmp_path / 'workspace'
    for relative in ('deploy/Dockerfile.core-e2e', 'app/deployment_profile.py'):
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    entries = [f'{hashlib.sha256((workspace / p).read_bytes()).hexdigest()}  {p}' for p in sorted(('app/deployment_profile.py', 'deploy/Dockerfile.core-e2e'))]
    manifest = ('\n'.join(entries) + '\n').encode()
    (workspace / 'core-e2e-source-manifest.sha256').write_bytes(manifest)
    if extra_file:
        (workspace / extra_file).write_text('synthetic', encoding='utf-8')
    return workspace, hashlib.sha256(manifest).hexdigest()


@needs_bash
def test_valid_manifest_passes_validation_and_tag_includes_the_build_id(tmp_path):
    workspace, sha = make_workspace(tmp_path)
    result = run_step('validate-target', sha, workspace)
    assert result.returncode == 0, result.stderr
    assert f'LW_CORE_E2E_TAG=m0-{sha}-{BUILD_A}' in result.stdout


@needs_bash
def test_two_builds_in_the_same_second_with_the_same_source_get_different_tags(tmp_path):
    """同一秒、相同來源 SHA、同時執行：tag 一定不同，因為每次建置的 BUILD_ID 不同。"""
    workspace, sha = make_workspace(tmp_path)
    first = run_step('validate-target', sha, workspace, build_id=BUILD_A)
    second = run_step('validate-target', sha, workspace, build_id=BUILD_B)
    assert first.returncode == 0 and second.returncode == 0
    tags = {line for r in (first, second) for line in r.stdout.splitlines() if line.startswith('LW_CORE_E2E_TAG=')}
    assert len(tags) == 2


@needs_bash
@pytest.mark.parametrize('value', ['$(touch PWNED)', '`touch PWNED`', 'a"; touch PWNED; "', "a'; touch PWNED; '",
                                   'a\ntouch PWNED', 'a' * 63, 'A' * 64, 'zz' * 32, ''])
def test_malicious_or_invalid_source_sha_is_only_data(tmp_path, value):
    workspace, _ = make_workspace(tmp_path)
    result = run_step('validate-target', value, workspace)
    assert result.returncode != 0 and not (workspace / 'PWNED').exists()


@needs_bash
@pytest.mark.parametrize('value', ['$(touch PWNED)', '`touch PWNED`', 'a"; touch PWNED; "', 'a\ntouch PWNED', ''])
def test_malicious_or_invalid_package_sha_is_only_data(tmp_path, value):
    workspace, sha = make_workspace(tmp_path)
    result = run_step('validate-target', sha, workspace, package_sha=value)
    assert result.returncode != 0 and not (workspace / 'PWNED').exists()


@needs_bash
@pytest.mark.parametrize('build_id', ['$(touch PWNED)', 'latest', '11111111-2222-4333-8444-55555555555'])
def test_unexpected_build_id_is_refused(tmp_path, build_id):
    workspace, sha = make_workspace(tmp_path)
    result = run_step('validate-target', sha, workspace, build_id=build_id)
    assert result.returncode != 0 and not (workspace / 'PWNED').exists()


@needs_bash
def test_extra_uploaded_file_is_refused(tmp_path):
    workspace, sha = make_workspace(tmp_path, extra_file='fake-service-account.json')
    result = run_step('validate-target', sha, workspace)
    assert result.returncode != 0 and 'differs from the manifest' in result.stderr


@needs_bash
def test_modified_uploaded_file_is_refused(tmp_path):
    workspace, sha = make_workspace(tmp_path)
    (workspace / 'app/deployment_profile.py').write_text('# tampered', encoding='utf-8')
    result = run_step('validate-target', sha, workspace)
    assert result.returncode != 0


# ---------- 建置端重新驗證封裝（替身 gcloud；不連任何雲端） ----------

def fake_tools(tmp_path, gcloud_script='', docker_script=''):
    bin_dir = tmp_path / 'fakebin'
    bin_dir.mkdir(exist_ok=True)
    for name, body in (('gcloud', gcloud_script), ('docker', docker_script)):
        if body:
            (bin_dir / name).write_text('#!/bin/bash\n' + body, encoding='utf-8', newline='\n')
    return {'PATH': str(bin_dir) + os.pathsep + os.environ.get('PATH', '')}


def gcloud_describe_and_cat(describe_out, describe_code=0, object_file=None, cat_code=0):
    cat = (f'echo "ERROR: (gcloud.storage.cat) HTTPError 403: permission denied" >&2; exit {cat_code}' if cat_code
           else f'cat "{object_file}"; exit 0')
    return (f'if [ "$1 $2" = "builds describe" ]; then printf "%b" "{describe_out}"; exit {describe_code}; fi\n'
            f'if [ "$1 $2" = "storage cat" ]; then {cat}; fi\n'
            'echo "unexpected gcloud call: $*" >&2; exit 99\n')


@needs_bash
@pytest.mark.parametrize('tamper,describe_code,describe_bucket,expected_ok', [
    (False, 0, 'life-world-513506_cloudbuild', True),
    (True, 0, 'life-world-513506_cloudbuild', False),       # 上傳的封裝被修改
    (False, 0, 'other-bucket', False),                        # 不是預期的來源 bucket
    (False, 1, 'life-world-513506_cloudbuild', False),        # 查詢失敗（例如權限不足、認證錯誤訊息含 not found）
])
def test_package_is_reverified_from_the_build_record(tmp_path, tamper, describe_code, describe_bucket, expected_ok):
    package = tmp_path / 'package.tgz'
    package.write_bytes(b'synthetic package bytes')
    sha = hashlib.sha256(package.read_bytes()).hexdigest()
    if tamper:
        package.write_bytes(b'synthetic package bytes + extra file')
    describe = f'{describe_bucket}\\tsource/1762700000.123456-{"c" * 32}.tgz\\t1762700000123456\\n'
    if describe_code:
        describe = 'ERROR: (gcloud.builds.describe) credentials file not found\\n'
    env = fake_tools(tmp_path, gcloud_describe_and_cat(describe, describe_code, package.as_posix()))
    result = run_step('verify-package', 'a' * 64, tmp_path, env, package_sha=sha)
    assert (result.returncode == 0) is expected_ok, result.stderr


GOOD_DESCRIBE = f'life-world-513506_cloudbuild\\tsource/1762700000.123456-{"c" * 32}.tgz\\t1762700000123456\\n'


@needs_bash
@pytest.mark.parametrize('describe_error', [
    'ERROR: (gcloud.builds.describe) PERMISSION_DENIED: The caller does not have permission\\n',   # 權限不足
    'ERROR: (gcloud.builds.describe) NOT_FOUND: Requested entity was not found.\\n',               # 文字含 not found 也只是失敗
    'ERROR: (gcloud.auth) credentials file not found\\n',                                          # 認證錯誤
])
def test_build_record_errors_are_failures_whatever_the_text(tmp_path, describe_error):
    package = tmp_path / 'package.tgz'
    package.write_bytes(b'synthetic package bytes')
    env = fake_tools(tmp_path, gcloud_describe_and_cat(describe_error, 1, package.as_posix()))
    result = run_step('verify-package', 'a' * 64, tmp_path, env, package_sha=hashlib.sha256(package.read_bytes()).hexdigest())
    assert result.returncode != 0


@needs_bash
def test_unreadable_package_object_is_refused_even_for_the_empty_hash(tmp_path):
    """讀取來源物件失敗（權限不足）時，sha256sum 只會看到空輸入；即使替換值剛好是空輸入的 SHA-256，也必須失敗。"""
    empty_sha = hashlib.sha256(b'').hexdigest()
    env = fake_tools(tmp_path, gcloud_describe_and_cat(GOOD_DESCRIBE, 0, None, cat_code=1))
    result = run_step('verify-package', 'a' * 64, tmp_path, env, package_sha=empty_sha)
    assert result.returncode != 0


# ---------- provenance 綁定這次 push 的 digest（替身 docker；不連任何 Registry） ----------

REPO = 'asia-east1-docker.pkg.dev/life-world-513506/lw-containers/lw-core-e2e'


def docker_fake(push_digest, repo_digests, push_code=0, inspect_code=0):
    lines = '\\n'.join(repo_digests)
    inspect = f'printf "%b\\n" "{lines}"' if repo_digests else ':'  # 空清單：完全沒有輸出
    return (f'if [ "$1" = "push" ]; then echo "m0: digest: {push_digest} size: 1234"; exit {push_code}; fi\n'
            f'if [ "$1" = "inspect" ]; then {inspect}; exit {inspect_code}; fi\n'
            'echo "unexpected docker call: $*" >&2; exit 99\n')


@needs_bash
def test_provenance_uses_the_digest_from_this_push_even_if_the_tag_moves_later(tmp_path):
    digest_a, digest_b = 'sha256:' + 'a' * 64, 'sha256:' + 'b' * 64
    marker = tmp_path / 'gcloud-called'
    env = fake_tools(tmp_path, gcloud_script=f'touch "{marker.as_posix()}"; echo "{digest_b}"\n',  # 若有人以 tag 查詢，會得到被替換後的 B
                     docker_script=docker_fake(digest_a, [f'{REPO}@{digest_a}']))
    result = run_step('core-e2e-push-and-record', 'c' * 64, tmp_path, env)
    assert result.returncode == 0, result.stderr
    assert f'image={REPO}@{digest_a}' in result.stdout and digest_b not in result.stdout
    assert not marker.exists()  # 沒有事後以 tag 查詢 digest


@needs_bash
def test_push_failure_or_mismatched_local_digest_is_refused(tmp_path):
    digest_a, digest_b = 'sha256:' + 'a' * 64, 'sha256:' + 'b' * 64
    failed = run_step('core-e2e-push-and-record', 'c' * 64, tmp_path,
                      fake_tools(tmp_path, docker_script=docker_fake(digest_a, [f'{REPO}@{digest_a}'], push_code=1)))
    assert failed.returncode != 0  # tag 已存在（immutable）或其他 push 失敗
    mismatch = run_step('core-e2e-push-and-record', 'c' * 64, tmp_path,
                        fake_tools(tmp_path, docker_script=docker_fake(digest_a, [f'{REPO}@{digest_b}'])))
    assert mismatch.returncode != 0 and 'RepoDigests' in mismatch.stderr


# ---------- M0 修正 V4（F4）：docker inspect 的退出碼與 RepoDigests 必須正好相符 ----------

DIGEST_A, DIGEST_B = 'sha256:' + 'a' * 64, 'sha256:' + 'b' * 64


@needs_bash
@pytest.mark.parametrize('case,repo_digests,inspect_code,ok', [
    ('correct digest but inspect exits 42', [f'{REPO}@{DIGEST_A}'], 42, False),   # Codex 第三輪反例：grep 成功掩蓋 inspect 的失敗
    ('inspect prints nothing', [], 0, False),
    ('inspect prints a different digest', [f'{REPO}@{DIGEST_B}'], 0, False),
    ('inspect prints several digests', [f'{REPO}@{DIGEST_A}', f'{REPO}@{DIGEST_B}'], 0, False),
    ('inspect prints the pushed digest for another repository', [f'{REPO}-other@{DIGEST_A}'], 0, False),
    ('inspect succeeds with exactly the pushed digest', [f'{REPO}@{DIGEST_A}'], 0, True),
])
def test_provenance_requires_inspect_exit_zero_and_exactly_the_pushed_digest(tmp_path, case, repo_digests, inspect_code, ok):
    env = fake_tools(tmp_path, docker_script=docker_fake(DIGEST_A, repo_digests, inspect_code=inspect_code))
    result = run_step('core-e2e-push-and-record', 'c' * 64, tmp_path, env)
    assert (result.returncode == 0) is ok, (case, result.stdout, result.stderr)
    assert ('LW_CORE_E2E_PROVENANCE' in result.stdout) is ok, case  # 失敗時絕不輸出 provenance
    if ok:
        assert f'image={REPO}@{DIGEST_A}' in result.stdout


@needs_bash
def test_push_without_a_reported_digest_is_refused(tmp_path):
    env = fake_tools(tmp_path, docker_script=('if [ "$1" = "push" ]; then echo "pushed"; exit 0; fi\n'
                                              f'if [ "$1" = "inspect" ]; then echo "{REPO}@{DIGEST_A}"; exit 0; fi\nexit 99\n'))
    result = run_step('core-e2e-push-and-record', 'c' * 64, tmp_path, env)
    assert result.returncode != 0 and 'LW_CORE_E2E_PROVENANCE' not in result.stdout


@needs_bash
@pytest.mark.parametrize('tool', ['find', 'sort'])
def test_file_list_generator_failure_stops_validation(tmp_path, tool):
    """清單產生器印出正確的清單但以非 0 結束：不能因為比較結果相同而通過。"""
    workspace, sha = make_workspace(tmp_path)
    # Git Bash 會把自己的 /usr/bin 放在 PATH 最前面，所以以 BASH_ENV 定義同名函式（函式優先於 PATH 中的程式）。
    hook = tmp_path / 'bash_env.sh'
    hook.write_text(f'{tool}() {{ command {tool} "$@"; return 3; }}\n', encoding='utf-8', newline='\n')
    control = run_step('validate-target', sha, workspace)
    assert control.returncode == 0, control.stderr  # 對照：沒有替身時通過
    result = run_step('validate-target', sha, workspace, {'BASH_ENV': hook.as_posix()})
    assert result.returncode != 0 and 'LW_CORE_E2E_TAG' not in result.stdout, result.stderr
