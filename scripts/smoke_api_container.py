"""以 Docker CLI 驗證 API 映像；只接受本機合成 PG，絕不 push／deploy。"""
import argparse
import io
import json
import os
import re
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent.parent

# 此程式在非 root runtime container 內執行，驗證真實 HTTP 與監聽地址。
PROBE = r'''
import http.cookiejar,json,os,time,urllib.request,urllib.error
assert os.getuid()==10001
port=int(os.environ['PORT'])
for attempt in range(60):
    try:
        assert json.load(urllib.request.urlopen('http://127.0.0.1:%d/health'%port))=={'status':'ok'}
        break
    except Exception:
        time.sleep(.25)
else:
    raise AssertionError('process health did not become ready')
listeners=open('/proc/net/tcp').read().upper()
assert '00000000:%04X'%port in listeners
assert json.load(urllib.request.urlopen('http://127.0.0.1:%d/ready'%port))=={'status':'ready'}
assert json.load(urllib.request.urlopen('http://127.0.0.1:%d/api/health'%port))['status']=='ok'
jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def call(path, data=None, method='GET', csrf=None):
    headers={'Content-Type':'application/json'}
    if csrf: headers['X-CSRF-Token']=csrf
    request=urllib.request.Request('http://127.0.0.1:%d'%port+path, data=None if data is None else json.dumps(data).encode(), headers=headers,method=method)
    return opener.open(request)
if os.environ.get('K_SERVICE'):
    try: call('/api/auth/guest',{},'POST')
    except urllib.error.HTTPError as e: assert e.code==503
    else: raise AssertionError('cloud business gate must be closed')
else:
    guest=json.load(call('/api/auth/guest',{},'POST'))
    assert guest['status']=='guest'
    json.load(call('/api/profile',{'name':'synthetic-container','bio':'synthetic only','timezone':'UTC'},'PUT',guest['csrf_token']))
    try: call('/api/profile',{'name':'x','bio':'x','timezone':'UTC'},'PUT')
    except urllib.error.HTTPError as e: assert e.code==403
    else: raise AssertionError('CSRF must be enforced')
print('HTTP health/readiness/auth/CSRF + 0.0.0.0:%d + nonroot: PASS'%port)
'''


def scan_archive(path, layers=False):
    """檢查所有 image layers；即使後續刪檔也不能掩蓋先前 COPY 的秘密。"""
    checked = 0
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        if layers:
            manifest = json.load(archive.extractfile('manifest.json'))
            names = {n for item in manifest for n in item['Layers']}
            for member in members:
                if member.name in names:
                    checked += scan_layer(archive.extractfile(member), member.name)
        else:
            checked += scan_layer_members(archive, members)
    return checked


def scan_layer(stream, name):
    with tarfile.open(fileobj=stream, mode='r|*') as archive:
        return scan_layer_members(archive, archive)


def scan_layer_members(archive, members):
    count = 0
    for member in members:
        if not member.isfile():
            continue
        path = PurePosixPath(member.name)
        # OS CA bundle／套件資料 JSON 不等於 private key；憑證內容另作語意檢查。
        assert not any(p in ('.git','.tools','.venv','local-preview') for p in path.parts), member.name
        assert not (path.name.startswith('.env') or path.suffix in ('.sqlite','.sqlite3','.db','.key')), member.name
        if path.suffix == '.json':
            assert 'service-account' not in path.name.lower() and 'service_account' not in path.name.lower(), member.name
        if member.size <= 2_000_000 and (path.suffix in ('.json','.pem','.txt','.py','.env') or 'canary' in path.name):
            content = archive.extractfile(member).read()
            assert b'LIFEWORLD_SYNTHETIC_IMAGE_CANARY' not in content, member.name
            # SDK 的 marker 常數不含私鑰；真正 PEM block 必須連同 base64 內文拒絕。
            assert not re.search(rb'-----BEGIN (?:RSA |EC |ENCRYPTED )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{64,}',content), member.name
            if path.suffix == '.json':
                try:
                    data = json.loads(content)
                except (ValueError,UnicodeError):
                    data = None
                assert not (isinstance(data,dict) and (data.get('type') == 'service_account' or 'private_key' in data)), member.name
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    parser.add_argument('--network',default='host')
    parser.add_argument('--pg-host',default='127.0.0.1',choices=['127.0.0.1','localhost','lw-pg18-tests'])
    parser.add_argument('--pg-port',default='55432')
    parser.add_argument('--password-env-file')
    parser.add_argument('--docker-in-container',action='store_true')
    args = parser.parse_args()
    docker = ([str(ROOT / '.step10-tests/docker')] if args.docker_in_container else
              json.loads(os.environ.get('LIFEWORLD_TEST_DOCKER_ARGV','["docker"]')))
    password = os.environ.get('LIFEWORLD_TEST_PG_PASSWORD','')
    if args.password_env_file:
        password = dict(line.split('=',1) for line in Path(args.password_env_file).read_text().splitlines() if '=' in line)['POSTGRES_PASSWORD']
    if not password:
        raise ValueError('Synthetic test password required')
    (ROOT / '.test-runs').mkdir(exist_ok=True)
    def run(*argv, **kwargs):
        return subprocess.run(docker + list(argv), check=True, **kwargs)
    with tempfile.TemporaryDirectory(prefix='image-',dir=ROOT / '.test-runs') as tmp:
        # Env file 只包含合成密碼；不會寫入 image 或命令列。
        envfile = Path(tmp) / 'synthetic.env'
        envfile.write_text('\n'.join(['LIFEWORLD_DB_BACKEND=postgresql','LIFEWORLD_DB_USER=lw_app',
            'LIFEWORLD_DB_NAME=life_world_dev','LIFEWORLD_DB_SCHEMA=lw_core_draft',
            'LIFEWORLD_DB_PASSWORD='+password,'LIFEWORLD_DB_HOST='+args.pg_host,
            'LIFEWORLD_DB_PORT='+args.pg_port,'LIFEWORLD_PG_TLS=disable',
            'LIFEWORLD_TRUSTED_HOSTS=127.0.0.1,localhost'])+'\n',encoding='utf-8')
        docker_env = str(envfile)
        if docker[0].lower() in ('wsl','wsl.exe'):
            docker_env = '/mnt/' + envfile.drive[0].lower() + envfile.as_posix()[2:]
        for port, cloud in ((8080,False),(8091,True)):
            name = 'lw-api-smoke-' + uuid.uuid4().hex[:12]
            try:
                extra = ['-e','PORT='+str(port)] if cloud else []  # 第一輪真的使用映像的預設 PORT。
                if cloud:
                    extra += ['-e','K_SERVICE=synthetic-local-cloud-run','-e','LIFEWORLD_SECURE_COOKIES=true']
                run('run','-d','--rm','--name',name,'--network',args.network,'--env-file',docker_env,*extra,args.image)
                run('exec',name,'python','-c',PROBE)
            finally:
                subprocess.run(docker + ['rm','-f','-v',name],check=False)
        # docker save 同時檢查依賴層與 runtime 層，非只看最後檔案系統。
        image_tar = Path(tmp) / 'image.tar'
        with image_tar.open('wb') as output:
            run('save',args.image,stdout=output)
        count = scan_archive(image_tar,layers=True)
        print('Image layer files scanned:',count,'; no DB/env/SA key/private data canary: PASS')


if __name__ == '__main__':
    main()
