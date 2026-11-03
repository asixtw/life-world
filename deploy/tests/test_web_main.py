"""Web main 部署契約；Shell 驗證以本機函式攔截所有 gcloud 呼叫。"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = yaml.safe_load((ROOT/'deploy/cloudbuild.web.yaml').read_text(encoding='utf-8'))
STEPS = {step['id']:step for step in CONFIG['steps']}
IMAGE = 'asia-east1-docker.pkg.dev/life-world-513506/lw-containers/lw-web'
SHA = '0123456789abcdef0123456789abcdef01234567'
BUILD_IDS = ('11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222')


def substitute(text, sha=SHA, build_id=BUILD_IDS[0], project='life-world-513506'):
    """單次模擬 Cloud Build substitution，保留 $$ 後的 shell 變數。"""
    values = dict(COMMIT_SHA=sha,BUILD_ID=build_id,PROJECT_ID=project)
    return re.sub(r'\$\$|\$\{([A-Z_][A-Z_0-9]*)\}|\$([A-Z_][A-Z_0-9]*)',
        lambda m:'$' if m[0]=='$$' else values[m[1] or m[2]],text)


def shell(script, *, syntax=False, env=None):
    bash = shutil.which('bash') if os.name!='nt' else r'C:\Program Files\Git\bin\bash.exe'
    if not bash or not Path(bash).exists():
        raise RuntimeError('Bash is required for deployment shell validation')
    args=[bash,'--noprofile','--norc']+(['-n'] if syntax else ['-ceu',script])
    return subprocess.run(args,input=script if syntax else None,cwd=ROOT,env=env,
        capture_output=True,text=True,encoding='utf-8')


class WebMainDeployment(unittest.TestCase):
    def test_build_identity_and_step_order(self):
        self.assertEqual(CONFIG['serviceAccount'],'projects/life-world-513506/serviceAccounts/lw-build-main@life-world-513506.iam.gserviceaccount.com')
        self.assertEqual(list(STEPS),['validate-source','react-tests','react-build','image-build','image-push','deploy-main'])
        self.assertEqual(CONFIG['options']['logging'],'CLOUD_LOGGING_ONLY')

    def test_unique_image_tag_is_consistent(self):
        tag=IMAGE+':${COMMIT_SHA}-${BUILD_ID}'
        build=STEPS['image-build']['args']
        self.assertEqual(build[build.index('-t')+1],tag)
        self.assertEqual(STEPS['image-push']['args'],['push',tag])
        self.assertEqual(CONFIG['images'],[tag])
        self.assertIn('$${IMAGE}:${COMMIT_SHA}-${BUILD_ID}',STEPS['deploy-main']['args'][-1])
        self.assertNotEqual(substitute(tag,build_id=BUILD_IDS[0]),substitute(tag,build_id=BUILD_IDS[1]))

    def test_runtime_resources_and_digest(self):
        script=STEPS['deploy-main']['args'][-1]
        self.assertIn('gcloud run deploy lw-web-main ',script)
        self.assertIn('--image="$${IMAGE}@$${DIGEST}"',script)
        for flag in ('--region=asia-east1','--port=8080','--memory=256Mi','--cpu=1',
                     '--min-instances=0','--max-instances=2','--concurrency=80','--timeout=60',
                     '--service-account=lw-web-runtime@life-world-513506.iam.gserviceaccount.com',
                     'environment=main','commit-sha=$COMMIT_SHA'):
            self.assertIn(flag,script)
        self.assertNotIn('staging',script)

    def test_private_access_policy_is_preserved(self):
        source=(ROOT/'deploy/cloudbuild.web.yaml').read_text(encoding='utf-8')
        for forbidden in ('--allow-unauthenticated','--no-invoker-iam-check','set-iam-policy',
                          'add-iam-policy-binding','allUsers','allAuthenticatedUsers'):
            self.assertNotIn(forbidden,source)

    def test_context_and_verification_stages(self):
        args=STEPS['image-build']['args']
        self.assertEqual(args[-1],'collaboration/ui-kit')
        self.assertIn('VCS_REF=$COMMIT_SHA',args)
        docker=(ROOT/'collaboration/ui-kit/Dockerfile').read_text(encoding='utf-8')
        self.assertIn('FROM verify AS build',docker)
        self.assertIn('RUN pnpm test',docker)
        self.assertIn('RUN pnpm run build',docker)
        self.assertIn('RUN nginx -t',docker)
        self.assertIn('Life World UI candidate main',docker)
        self.assertNotIn('candidate staging',docker)

    def test_health_and_web_routing(self):
        source=(ROOT/'collaboration/ui-kit/cloud-nginx.conf').read_text(encoding='utf-8')
        for expected in ('location = /health {','return 200 "ok\\n";','listen 8080;',
                         'location = /api { return 404; }','location ^~ /api/ { return 404; }',
                         'try_files $uri $uri/ /index.html;'):
            self.assertIn(expected,source)

    def test_shell_syntax_after_substitution(self):
        for name in ('validate-source','deploy-main'):
            for build_id in BUILD_IDS:
                with self.subTest(step=name,build_id=build_id):
                    result=shell(substitute(STEPS[name]['args'][-1],build_id=build_id),syntax=True)
                    self.assertEqual(result.returncode,0,result.stderr)

    def test_source_guards(self):
        script=STEPS['validate-source']['args'][-1]
        for sha,project,valid in ((SHA,'life-world-513506',True),('','life-world-513506',False),
                ('abc','life-world-513506',False),('a'*41,'life-world-513506',False),
                ('g'*40,'life-world-513506',False),(SHA,'wrong-project',False)):
            with self.subTest(sha=sha,project=project):
                self.assertEqual(shell(substitute(script,sha=sha,project=project)).returncode==0,valid)

    def test_deploy_mock_uses_exact_digest_and_propagates_errors(self):
        # 模擬器不會呼叫外部 gcloud；未預期參數直接失敗。
        mock=r'''
gcloud() {
  if [ "$1 $2 $3 $4" = 'artifacts docker images describe' ]; then
    printf '%s\n' "$5" > "$MOCK_QUERY"
    [ "$MOCK_LOOKUP_FAIL" = 'false' ] || return 42
    printf '%s\n' "$MOCK_DIGEST"
  elif [ "$1 $2" = 'run deploy' ]; then
    printf '%s\n' "$@" > "$MOCK_DEPLOY"
    [ "$MOCK_DEPLOY_FAIL" = 'false' ] || return 43
  else return 99; fi
}
'''
        cases=[('valid1',BUILD_IDS[0],'sha256:'+'a'*64,False,False),
               ('valid2',BUILD_IDS[1],'sha256:'+'b'*64,False,False),
               ('empty',BUILD_IDS[0],'',False,False),('short',BUILD_IDS[0],'sha256:abc',False,False),
               ('badhex',BUILD_IDS[0],'sha256:'+'g'*64,False,False),
               ('lookup',BUILD_IDS[0],'sha256:'+'a'*64,True,False),
               ('deploy',BUILD_IDS[0],'sha256:'+'a'*64,False,True)]
        with tempfile.TemporaryDirectory() as temporary:
            for name,bid,digest,lookup_fail,deploy_fail in cases:
                with self.subTest(case=name):
                    query,capture=Path(temporary)/('query-'+name),Path(temporary)/('deploy-'+name)
                    env=dict(os.environ,MOCK_QUERY=query.as_posix(),MOCK_DEPLOY=capture.as_posix(),
                        MOCK_DIGEST=digest,MOCK_LOOKUP_FAIL=str(lookup_fail).lower(),MOCK_DEPLOY_FAIL=str(deploy_fail).lower())
                    result=shell(mock+'\n'+substitute(STEPS['deploy-main']['args'][-1],build_id=bid),env=env)
                    self.assertEqual(query.read_text().strip(),IMAGE+':'+SHA+'-'+bid)
                    if name.startswith('valid'):
                        self.assertEqual(result.returncode,0,result.stderr)
                        arguments=capture.read_text().splitlines()
                        self.assertEqual(arguments[:3],['run','deploy','lw-web-main'])
                        self.assertIn('--image='+IMAGE+'@'+digest,arguments)
                    elif deploy_fail:
                        self.assertNotEqual(result.returncode,0)
                        self.assertTrue(capture.exists())
                    else:
                        self.assertNotEqual(result.returncode,0)
                        self.assertFalse(capture.exists())


if __name__=='__main__':
    unittest.main()
