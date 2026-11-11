"""M0 修正 F5：lw-core-e2e 的建置來源白名單（只讀檔案）。"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / 'deploy/core-e2e-build-sources.txt'
REQUIRED = {'requirements.api.lock', 'deploy/Dockerfile.core-e2e', 'deploy/cloudbuild.core-e2e.yaml', '.dockerignore',
            'app/main.py', 'app/serve.py', 'app/deployment_profile.py', 'app/postgres.py', 'app/static/index.html'}
DENIED = re.compile(r'(^|/)(\.env[^/]*|data/.*|__pycache__/.*)$|\.(pyc|sqlite3?|db|key|pem|p12)$|service[-_]?account|credential', re.I)


def entries():
    return [line for line in ALLOWLIST.read_text(encoding='utf-8').splitlines() if line and not line.startswith('#')]


def test_allowlist_is_sorted_unique_relative_and_safe():
    items = entries()
    assert items == sorted(set(items))
    for item in items:
        assert re.fullmatch(r'[A-Za-z0-9._/-]+', item) and not item.startswith('/') and '..' not in item.split('/')
        assert not DENIED.search(item), item


def test_allowlist_contains_required_files_and_migrations():
    items = set(entries())
    assert REQUIRED <= items
    assert any(item.startswith('app/migrations/') and item.endswith('.sql') for item in items)
    assert any(item.startswith('app/static/') for item in items)


def test_every_listed_file_exists_as_a_regular_file():
    for item in entries():
        path = ROOT / item
        assert path.is_file() and not path.is_symlink(), item


def test_app_directory_matches_the_allowlist_exactly():
    """app/ 下的檔案與清單必須完全一致：新增或刪除 app 檔案時，要同步審查這份清單（快取目錄除外，由準備腳本另外拒絕）。"""
    on_disk = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'app').rglob('*')
               if p.is_file() and '__pycache__' not in p.parts}
    listed = {item for item in entries() if item.startswith('app/')}
    assert on_disk == listed
