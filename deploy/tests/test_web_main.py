"""Web main 部署契約；Shell 驗證以本機函式攔截所有 gcloud 呼叫。"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import importlib.util

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
        self.assertEqual(list(STEPS),['validate-source','release-safety-tests','react-tests','react-build','image-build','image-push','deploy-main'])
        self.assertEqual(CONFIG['options']['logging'],'CLOUD_LOGGING_ONLY')

    def test_unique_image_tag_is_consistent(self):
        tag=IMAGE+':${COMMIT_SHA}-${BUILD_ID}'
        build=STEPS['image-build']['args']
        self.assertEqual(build[build.index('-t')+1],tag)
        self.assertEqual(STEPS['image-push']['args'],['push',tag])
        self.assertNotIn('images',CONFIG)  # 正式發布之後不可再有隱藏的映像上傳步驟。
        self.assertEqual(STEPS['deploy-main']['args'], ['deploy/release.py','--component','web',
                         '--commit','$COMMIT_SHA','--build-id','$BUILD_ID','--branch','$BRANCH_NAME'])
        self.assertNotEqual(substitute(tag,build_id=BUILD_IDS[0]),substitute(tag,build_id=BUILD_IDS[1]))

    def test_runtime_resources_and_digest(self):
        script=(ROOT/'deploy/release.py').read_text(encoding='utf-8')
        self.assertIn("'--image=' + image + '@' + digest",script)
        self.assertIn("'--no-traffic'",script)
        self.assertIn("'--revision-suffix=' + self.tag",script)
        self.assertIn("'--service-account=' + runtime_sa",script)
        # 未傳入容量／網路／Secret 設定：沿用服務現況，API 另核對正式 revision。
        for flag in ('--clear-env-vars','--clear-secrets','--clear-vpc-connector','--remove-cloudsql-instances'):
            self.assertNotIn(flag,script)

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
        self.assertIn('RUN python -m unittest -q test_web_server',docker)
        self.assertIn('COPY --from=server-verify',docker)
        self.assertIn('Life World Web main',docker)
        self.assertNotIn('candidate staging',docker)

    def test_health_and_web_routing(self):
        from fastapi.testclient import TestClient
        spec=importlib.util.spec_from_file_location('web_server',ROOT/'collaboration/ui-kit/tools/web_server.py')
        server=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server)
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'index.html').write_text('<h1>gallery</h1>',encoding='utf-8')
            with TestClient(server.create_app(api_origin='',gallery_dir=directory),base_url='https://testserver') as client:
                self.assertEqual(client.get('/health').text,'ok\n')
                self.assertEqual(client.get('/').status_code,200)
                self.assertEqual(client.get('/api/state').status_code,503)
                self.assertEqual(client.get('/missing.js').status_code,404)
                self.assertEqual(client.get('/.env').status_code,404)

    def test_shell_syntax_after_substitution(self):
        for name in ('validate-source',):
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

    def test_both_pipelines_end_with_the_same_guarded_publisher(self):
        api=yaml.safe_load((ROOT/'deploy/cloudbuild.api.yaml').read_text(encoding='utf-8'))
        self.assertEqual(api['steps'][-1]['args'][0],'deploy/release.py')
        self.assertEqual(api['steps'][-1]['args'][2],'api')
        self.assertEqual(api['steps'][-2]['id'],'api-image-push')
        self.assertNotIn('images',api)
        self.assertTrue(any(x['id']=='sqlite-and-real-pg18-tests' for x in api['steps']))
        self.assertTrue(any(x['id']=='api-container-verification' for x in api['steps']))


if __name__=='__main__':
    unittest.main()
