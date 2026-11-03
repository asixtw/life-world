"""驗收工具本身的安全邊界：先拒絕錯誤目標，再允許合成寫入。"""
import base64
from copy import deepcopy
from datetime import datetime, timezone
import json
import io
from pathlib import Path
import sys
import time

import httpx
import pytest

from scripts import e2e_acceptance as e2e


def plan():
    main = 'https://lw-api-main-example.a.run.app'
    tagged = 'https://e2e---lw-api-main-example.a.run.app'
    digest = 'sha256:' + 'a' * 64
    def revision(name, enabled, database, user):
        env = {'LIFEWORLD_DB_BACKEND':'postgresql', 'LIFEWORLD_PG_CONNECTION':'cloud_sql',
               'LIFEWORLD_DB_NAME':database, 'LIFEWORLD_DB_SCHEMA':'lw_core_draft',
               'LIFEWORLD_DB_USER':user, 'LIFEWORLD_ENABLE_BUSINESS_API':enabled,
               'LIFEWORLD_SECURE_COOKIES':'true',
               'LIFEWORLD_TRUSTED_HOSTS':'lw-api-main-example.a.run.app,e2e---lw-api-main-example.a.run.app,127.0.0.1,localhost',
               'LIFEWORLD_EXTERNAL_ORIGIN':tagged if enabled == 'true' else main,
               'LIFEWORLD_INSTANCE_CONNECTION_NAME':'life-world-513506:asia-east1:synthetic'}
        return {'metadata':{'name':name,'namespace':'123456','labels':{'cloud.googleapis.com/location':'asia-east1'}},
                'spec':{'serviceAccountName':'lw-api-runtime@life-world-513506.iam.gserviceaccount.com',
                        'containers':[{'image':'registry/lw-api@'+digest,'env':[
                            *[{'name':k,'value':v} for k,v in env.items()],
                            {'name':'LIFEWORLD_DB_PASSWORD','valueFrom':{'secretKeyRef':{'name':'synthetic-secret','key':'1'}}}]}]},
                'status':{'imageDigest':'registry/lw-api@'+digest,'conditions':[{'type':'Ready','status':'True'}]}}
    routes = [{'revisionName':'lw-api-main-stable','percent':100},
              {'revisionName':'lw-api-main-e2e','tag':'e2e','url':tagged}]
    return {'mode':'cloud','captured_at':datetime.now(timezone.utc).isoformat(),
            'project_id':'life-world-513506','project_number':'123456',
            'service':{'metadata':{'name':'lw-api-main','namespace':'123456','labels':{'cloud.googleapis.com/location':'asia-east1'}},
                       'spec':{'traffic':routes},
                       'status':{'url':main,'traffic':routes,'conditions':[{'type':'Ready','status':'True'}]}},
            'main_revision':revision('lw-api-main-stable','false','life_world_dev','lw_app'),
            'tag_revision':revision('lw-api-main-e2e','true','life_world_e2e','lw_e2e_app'),
            'iam_policy':{'bindings':[{'role':'roles/run.invoker','members':['serviceAccount:synthetic@example.iam.gserviceaccount.com']}]}}


def token(audience, exp=None):
    encode = lambda x: base64.urlsafe_b64encode(json.dumps(x).encode()).rstrip(b'=').decode()
    return encode({'alg':'RS256'})+'.'+encode({'aud':audience,'exp':exp or time.time()+1800})+'.synthetic-signature'


def test_valid_cloud_plan_binds_tag_to_database_and_main_audience():
    result = e2e.validate_plan(plan())
    assert result['audience'] == 'https://lw-api-main-example.a.run.app'
    assert result['target'].startswith('https://e2e---')


@pytest.mark.parametrize('defect', ['traffic','latest','same_revision','dev_database','admin_runtime',
    'business_main','iam_public','iam_disabled','wrong_host','wrong_origin','wrong_project',
    'stale','secret_literal','image_changed','not_ready','redirect_url'])
def test_dangerous_plans_are_rejected_before_network(defect):
    p = deepcopy(plan())
    def env(revision, key, value):
        values = p[revision]['spec']['containers'][0]['env']
        values[:] = [x for x in values if x['name'] != key] + [{'name':key,'value':value}]
    if defect == 'traffic': p['service']['status']['traffic'][1]['percent'] = 1
    elif defect == 'latest': p['service']['spec']['traffic'][0]['latestRevision'] = True
    elif defect == 'same_revision': p['tag_revision']['metadata']['name'] = 'lw-api-main-stable'
    elif defect == 'dev_database': env('tag_revision','LIFEWORLD_DB_NAME','life_world_dev')
    elif defect == 'admin_runtime': env('tag_revision','LIFEWORLD_DB_USER','lw_migrator')
    elif defect == 'business_main': env('main_revision','LIFEWORLD_ENABLE_BUSINESS_API','true')
    elif defect == 'iam_public': p['iam_policy']['bindings'][0]['members'].append('allUsers')
    elif defect == 'iam_disabled': p['service']['metadata']['annotations'] = {'run.googleapis.com/invoker-iam-disabled':'true'}
    elif defect == 'wrong_host': env('tag_revision','LIFEWORLD_TRUSTED_HOSTS','*')
    elif defect == 'wrong_origin': env('tag_revision','LIFEWORLD_EXTERNAL_ORIGIN',p['service']['status']['url'])
    elif defect == 'wrong_project': p['tag_revision']['metadata']['namespace'] = '999999'
    elif defect == 'stale': p['captured_at'] = '2020-01-01T00:00:00+00:00'
    elif defect == 'secret_literal': env('tag_revision','LIFEWORLD_DB_PASSWORD','private-password-canary')
    elif defect == 'image_changed': p['tag_revision']['status']['imageDigest'] = 'registry/other@sha256:'+'b'*64
    elif defect == 'not_ready': p['tag_revision']['status']['conditions'][0]['status'] = 'False'
    elif defect == 'redirect_url': p['service']['status']['traffic'][1]['url'] += '/redirect'
    with pytest.raises(e2e.SafetyError):
        e2e.validate_plan(p)


@pytest.mark.parametrize('audience,expiry', [('https://e2e---lw-api-main-example.a.run.app',None),
                                         ('https://lw-api-main-example.a.run.app',1)])
def test_wrong_audience_or_expired_token_rejected(audience, expiry):
    with pytest.raises(e2e.SafetyError):
        e2e.check_token(token(audience,expiry),'https://lw-api-main-example.a.run.app')


def test_no_iam_gate_stops_before_guest_write_and_does_not_leak_response():
    calls = []
    def handler(request):
        calls.append(request.method)
        if request.url.path=='/api/state':
            return httpx.Response(503,json={'error':{'code':'business_api_disabled'}})
        return httpx.Response(200,json={'private':'TOKEN-CANARY COOKIE-CANARY PASSWORD-CANARY'})
    p = plan()
    result = e2e.run_acceptance(p,token(p['service']['status']['url']),transport=httpx.MockTransport(handler))
    assert result['passed'] is False and 'POST' not in calls
    assert 'CANARY' not in json.dumps(result)
    assert any(x['status']=='FAIL' for x in result['checks'])
    assert any(x['name']=='iam_anonymous_denied' and x['status']=='FAIL' for x in result['checks'])


def test_bad_snapshot_never_sends_token_or_network_request():
    p = plan(); p['tag_revision']['spec']['containers'][0]['env'][2]['value'] = 'life_world_dev'
    def forbidden(request):
        raise AssertionError('network must not be called')
    result = e2e.run_acceptance(p,'TOKEN-CANARY',transport=httpx.MockTransport(forbidden))
    assert result['passed'] is False and result['checks'][0]['name']=='preflight'
    assert 'TOKEN-CANARY' not in json.dumps(result)


def test_redirects_are_never_followed_with_credentials():
    hosts = []
    def handler(request):
        hosts.append(request.url.host)
        return httpx.Response(307,headers={'Location':'https://private-canary.example/collect'})
    p = plan()
    result = e2e.run_acceptance(p,token(p['service']['status']['url']),transport=httpx.MockTransport(handler))
    assert result['passed'] is False
    assert set(hosts)=={'lw-api-main-example.a.run.app'}
    assert 'private-canary' not in json.dumps(result)


def test_retired_plan_rejects_remaining_tag():
    with pytest.raises(e2e.SafetyError): e2e.validate_plan(plan(),retired=True)


def test_local_bypass_cannot_target_cloud_url():
    p = plan(); p['mode']='local-simulation'
    with pytest.raises(e2e.SafetyError): e2e.validate_plan(p,allow_local=True)


def test_sql_generation_uses_canonical_schema_and_rejects_injection():
    from scripts.e2e_sql import schema_sql, audit_sql, CORE
    text = schema_sql()
    core = CORE.read_text(encoding='utf-8')
    assert core[core.index('CREATE SCHEMA'):core.index('COMMIT;')] in text
    assert text.index("current_database()<>'life_world_e2e'") < text.index('CREATE SCHEMA')
    # 即使 SQL client 繼續執行，guard 失敗也必須讓後續 DDL 留在 aborted transaction。
    assert text.index('\nBEGIN;\n') < text.index("current_database()<>'life_world_e2e'")
    with pytest.raises(ValueError): audit_sql("'; DROP DATABASE life_world_dev;--")


def test_offline_plan_cli_uses_exported_json(tmp_path, monkeypatch):
    from scripts import e2e_plan
    p = plan(); arguments = ['e2e_plan','--project-number','123456','--out',str(tmp_path/'plan.json')]
    for key in ('service','main_revision','tag_revision','iam_policy'):
        source = tmp_path/(key+'.json'); source.write_text(json.dumps(p[key]),encoding='utf-8-sig')
        arguments += ['--'+key.replace('_','-'),str(source)]
    monkeypatch.setattr(sys,'argv',arguments)
    assert e2e_plan.main()==0
    created = json.loads((tmp_path/'plan.json').read_text(encoding='utf-8'))
    assert e2e.validate_plan(created)['target'].startswith('https://e2e---')


def test_cli_reads_stdin_without_logging_token_or_touching_network(tmp_path, monkeypatch, capsys):
    source = tmp_path/'plan.json'; source.write_text(json.dumps(plan()),encoding='utf-8')
    report = tmp_path/'report.json'
    monkeypatch.setattr(sys,'argv',['e2e_acceptance','--plan',str(source),'--report',str(report),'--token-stdin'])
    monkeypatch.setattr(sys,'stdin',io.StringIO('TOKEN-COOKIE-PASSWORD-CANARY'))
    def no_network(*args, **kwargs): raise AssertionError('network must not be called')
    monkeypatch.setattr(httpx,'Client',no_network)
    assert e2e.main()==1
    contents = report.read_text(encoding='utf-8')+str(capsys.readouterr())
    assert 'CANARY' not in contents
    assert json.loads(report.read_text())['checks'][0]['reason']=='invalid_token'


def test_cli_records_malformed_input_failure_without_echoing_it(tmp_path, monkeypatch, capsys):
    source = tmp_path/'plan.json'; source.write_text('{PASSWORD-CANARY',encoding='utf-8')
    report = tmp_path/'failed.json'
    monkeypatch.setattr(sys,'argv',['e2e_acceptance','--plan',str(source),'--report',str(report),'--token-stdin'])
    monkeypatch.setattr(sys,'stdin',io.StringIO('TOKEN-CANARY'))
    assert e2e.main()!=0
    assert report.exists()
    assert 'CANARY' not in report.read_text()+str(capsys.readouterr())
