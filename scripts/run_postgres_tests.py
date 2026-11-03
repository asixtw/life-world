"""啟動／銷毀本次專用 PG18 容器；只有合成密碼，絕不接受遠端 DB。"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-network', action='store_true', help='供隔離 WSL daemon 使用')
    parser.add_argument('--image', help='測試通過後，對此已建置 image 執行真實 PG smoke')
    parser.add_argument('--junitxml', help='保留不含憑證的 pytest 結果')
    parser.add_argument('--container-tests', action='store_true', help='再以 API 的 Python3.12 執行 SQLite／PG 全量測試')
    parser.add_argument('pytest_args', nargs='*', default=[])
    args = parser.parse_args()
    if args.image and not args.host_network:
        parser.error('--image requires Linux --host-network; use standalone smoke with a dedicated container network in CI')
    if args.container_tests and not args.image:
        parser.error('--container-tests requires --image')
    # JSON argv 不是 shell command，Windows／WSL 路徑不經第二層字串解析。
    docker = json.loads(os.environ.get('LIFEWORLD_TEST_DOCKER_ARGV', '["docker"]'))
    name = 'lw-step10-pg-' + uuid.uuid4().hex[:12]
    env = dict(os.environ, LIFEWORLD_TEST_PG_PASSWORD=secrets.token_urlsafe(30),
               LIFEWORLD_TEST_PG_HOST='127.0.0.1', LIFEWORLD_TEST_PG_PORT='55432',
               LIFEWORLD_TEST_BACKEND='postgresql', PYTHONUTF8='1')
    (ROOT / '.test-runs').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pg-', dir=ROOT / '.test-runs') as tmp:
        envfile = Path(tmp) / 'synthetic.env'
        envfile.write_text('POSTGRES_USER=lw_step10_admin\nPOSTGRES_DB=postgres\nPOSTGRES_PASSWORD='
                           + env['LIFEWORLD_TEST_PG_PASSWORD'] + '\n', encoding='utf-8')
        docker_envfile = str(envfile)
        if docker and docker[0].lower() in ('wsl', 'wsl.exe'):
            docker_envfile = '/mnt/' + envfile.drive[0].lower() + envfile.as_posix()[2:]
        network = ['--network', 'host'] if args.host_network else ['-p', '127.0.0.1:55432:5432']
        port = '55432' if args.host_network else '5432'
        listen = '127.0.0.1' if args.host_network else '*'
        try:
            subprocess.run(docker + ['run', '-d', '--rm', '--name', name, *network,
                           '--env-file', docker_envfile, 'postgres:18.6',
                           '-c', 'port=' + port, '-c', 'listen_addresses=' + listen,
                           '-c', 'cluster_name=lifeworld-step10-4-synthetic'], check=True)
            subprocess.run([sys.executable, '-X', 'utf8', 'scripts/pg_test_bootstrap.py'],
                           cwd=ROOT, env=env, check=True)
            command = [sys.executable, '-X', 'utf8', '-m', 'pytest', '-q', '--tb=short',
                       '--basetemp=' + str(Path(tmp) / 'pytest'), *(args.pytest_args or ['tests'])]
            if args.junitxml:
                command.append('--junitxml=' + args.junitxml)
            result = subprocess.run(command, cwd=ROOT, env=env).returncode
            if result == 0 and args.container_tests:
                if not args.host_network or not args.image:
                    raise ValueError('--container-tests requires --host-network and --image')
                test_env = Path(tmp) / 'test.env'
                test_env.write_text('LIFEWORLD_TEST_PG_PASSWORD='+env['LIFEWORLD_TEST_PG_PASSWORD']+
                    '\nLIFEWORLD_TEST_PG_HOST=127.0.0.1\nLIFEWORLD_TEST_PG_PORT=55432\nPYTHONUTF8=1\n',encoding='utf-8')
                mount_root, mount_env = str(ROOT), str(test_env)
                if docker[0].lower() in ('wsl','wsl.exe'):
                    mount_root = '/mnt/'+ROOT.drive[0].lower()+ROOT.as_posix()[2:]
                    mount_env = '/mnt/'+test_env.drive[0].lower()+test_env.as_posix()[2:]
                # runtime image 的精確 Python／依賴；只在可丟棄容器增加測試套件。
                subprocess.run(docker + ['run','--rm','--network','host','--user','0:0',
                    '-v',mount_root+':/workspace:ro','-w','/workspace','--env-file',mount_env,
                    '-e','LIFEWORLD_DB_BACKEND=sqlite',
                    '--entrypoint','sh',args.image,'-ceu',
                    'python -m pip install --disable-pip-version-check -r requirements.api-test.lock > /tmp/test-install.log && '
                    'python -m pip check && '
                    'python -m pytest tests -q -p no:cacheprovider --basetemp=/tmp/lw-sqlite && '
                    'LIFEWORLD_TEST_BACKEND=postgresql python -m pytest tests -q -p no:cacheprovider --basetemp=/tmp/lw-postgres'],check=True)
            if result == 0 and args.image:
                subprocess.run([sys.executable, '-X', 'utf8', 'scripts/smoke_api_container.py',
                                '--image',args.image,'--network','host' if args.host_network else 'bridge'],
                               cwd=ROOT,env=env,check=True)
            return result
        finally:
            # 只用剛產生的名稱清理本次容器；不使用 prune 或接觸其他資料。
            subprocess.run(docker + ['rm', '-f', '-v', name], check=False)


if __name__ == '__main__':
    raise SystemExit(main())
