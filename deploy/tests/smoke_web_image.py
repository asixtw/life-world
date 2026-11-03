"""本機 Web image smoke；容器使用無外網網路，不呼叫 GCP。"""
import argparse
import json
import os
import subprocess
import uuid


PROBE = r'''
import json,time,urllib.request,urllib.error
base='http://127.0.0.1:8080'
def get(path):
    try:
        with urllib.request.urlopen(base+path,timeout=3) as r: return r.status,r.headers,r.read()
    except urllib.error.HTTPError as r:
        return r.code,r.headers,r.read()
for attempt in range(60):
    try:
        if get('/health')[0]==200: break
    except OSError: pass
    time.sleep(.2)
else: raise AssertionError('Nginx did not become ready')
checks=[]
def check(condition,name):
    assert condition,name
    checks.append(name)
status,headers,content=get('/health')
check(status==200 and content==b'ok\n','health 200/ok')
status,headers,index=get('/')
check(status==200 and b'<html' in index,'homepage HTML')
check(get('/candidate/deep-link')[2]==index,'SPA deep-link fallback')
check(get('/index.html')[1].get('Cache-Control')=='no-store','index no-store')
for path in ('/api','/api/missing','/missing.js','/.env','/app.js.map'):
    check(get(path)[0]==404,path+' 404')
print(json.dumps({'http_checks_passed':len(checks),'checks':checks}))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',default='lifeworld-web:main-local')
    parser.add_argument('--expected-revision')
    args=parser.parse_args()
    docker=json.loads(os.environ.get('LIFEWORLD_DOCKER_ARGV','["docker"]'))
    def run(*arguments,capture=False):
        return subprocess.run(docker+list(arguments),check=True,
                              capture_output=capture,text=capture,encoding='utf-8' if capture else None)
    metadata=json.loads(run('image','inspect',args.image,capture=True).stdout)[0]
    config=metadata['Config']
    assert config['User'] not in ('','root','0','0:0'),config['User']
    assert config['Labels']['org.opencontainers.image.title']=='Life World UI candidate main'
    assert '8080/tcp' in config['ExposedPorts']
    if args.expected_revision:
        assert config['Labels']['org.opencontainers.image.revision']==args.expected_revision
    name='lw-web-main-smoke-'+uuid.uuid4().hex[:12]
    try:
        # 不發布host port、不使用host network；既有API服務不會受影響。
        run('run','-d','--rm','--name',name,'--network','none',args.image)
        run('exec',name,'nginx','-t')
        uid=run('exec',name,'id','-u',capture=True).stdout.strip()
        assert uid!='0'
        # Python helper共用被測容器的封閉network namespace，只有loopback HTTP。
        run('run','--rm','--network','container:'+name,'--entrypoint','python','python:3.12-slim','-c',PROBE)
        run('exec',name,'sh','-ceu',
            "test ! -d /usr/share/nginx/html/node_modules; "
            "test ! -e /usr/share/nginx/html/package.json; "
            "test ! -e /usr/share/nginx/html/.env; "
            "test ! -d /usr/share/nginx/html/src",capture=True)
        print('Nonroot UID '+uid+'; main image title; port8080; runtime source exclusions: PASS')
    finally:
        subprocess.run(docker+['rm','-f','-v',name],check=False)


if __name__=='__main__':
    main()
