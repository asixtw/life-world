"""驗收工具本身的安全邊界：先拒絕錯誤目標，再允許合成寫入。"""
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import io
from pathlib import Path
import sys
import time
from uuid import uuid4

import httpx
import pytest

from scripts import e2e_acceptance as e2e


SOURCE_KEYS = ('service','main_revision','tag_revision','iam_policy')


def seal(p, stamp=None):
    """合成匯出證據；測試配置政策時同步內容指紋，避免只測到 checksum 拒絕。"""
    stamp = stamp or p['captured_at']; batch = uuid4().hex
    sources = {}
    for key in SOURCE_KEYS:
        digest = hashlib.sha256(json.dumps(p[key],sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
        sources[key] = {'filename':key+'.json','batch_id':batch,'export_started_at':stamp,'exported_at':stamp,
                        'sha256':digest,'content_sha256':digest}
    p['captured_at'] = stamp
    p['snapshot_evidence'] = {'version':1,'batch_id':batch,'started_at':stamp,'completed_at':stamp,'sources':sources}
    return p


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
        return {'metadata':{'name':name,'namespace':'123456','labels':{'cloud.googleapis.com/location':'asia-east1'},
                            'annotations':{'run.googleapis.com/network-interfaces':json.dumps([{'network':'lw-vpc-staging','subnetwork':'lw-subnet-staging'}]),
                                           'run.googleapis.com/vpc-access-egress':'private-ranges-only'}},
                'spec':{'serviceAccountName':'lw-api-runtime@life-world-513506.iam.gserviceaccount.com',
                        'containers':[{'image':'registry/lw-api@'+digest,'env':[
                            *[{'name':k,'value':v} for k,v in env.items()],
                            {'name':'LIFEWORLD_DB_PASSWORD','valueFrom':{'secretKeyRef':{'name':'synthetic-secret','key':'1'}}}]}]},
                'status':{'imageDigest':'registry/lw-api@'+digest,'conditions':[{'type':'Ready','status':'True'}]}}
    routes = [{'revisionName':'lw-api-main-stable','percent':100},
              {'revisionName':'lw-api-main-e2e','tag':'e2e','url':tagged}]
    return seal({'mode':'cloud','captured_at':datetime.now(timezone.utc).isoformat(),
            'project_id':'life-world-513506','project_number':'123456',
            'service':{'metadata':{'name':'lw-api-main','namespace':'123456','labels':{'cloud.googleapis.com/location':'asia-east1'}},
                       'spec':{'traffic':routes},
                       'status':{'url':main,'traffic':routes,'conditions':[{'type':'Ready','status':'True'}]}},
            'main_revision':revision('lw-api-main-stable','false','life_world_dev','lw_app'),
            'tag_revision':revision('lw-api-main-e2e','true','life_world_e2e','lw_e2e_app'),
            'iam_policy':{'bindings':[{'role':'roles/run.invoker','members':['serviceAccount:synthetic@example.iam.gserviceaccount.com']}]}})


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
    seal(p)
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
        p['snapshot_evidence']['sources'][key]['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        arguments += ['--'+key.replace('_','-'),str(source)]
    (tmp_path/'snapshot-evidence.json').write_text(json.dumps(p['snapshot_evidence']),encoding='utf-8')
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


@pytest.mark.parametrize('defect', ['missing','missing_source','stale_source','future_source','different_batch',
    'bad_order','missing_raw_hash','wrong_content','plan_changed','captured_at_refreshed'])
def test_snapshot_evidence_is_required_fresh_and_bound_to_plan(defect):
    p = plan(); evidence = p['snapshot_evidence']; source = evidence['sources']['service']
    if defect=='missing': del p['snapshot_evidence']
    elif defect=='missing_source': del evidence['sources']['iam_policy']
    elif defect=='stale_source': source['export_started_at']=(datetime.now(timezone.utc)-timedelta(minutes=16)).isoformat()
    elif defect=='future_source': source['exported_at']=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()
    elif defect=='different_batch': source['batch_id']=uuid4().hex
    elif defect=='bad_order': source['exported_at']=(datetime.now(timezone.utc)-timedelta(seconds=30)).isoformat()
    elif defect=='missing_raw_hash': del source['sha256']
    elif defect=='wrong_content': source['content_sha256']='0'*64
    elif defect=='plan_changed': p['service']['metadata']['synthetic_change']='after export'
    elif defect=='captured_at_refreshed': p['captured_at']=datetime.now(timezone.utc).isoformat()
    with pytest.raises(e2e.SafetyError): e2e.validate_plan(p)


@pytest.mark.parametrize('defect', ['missing','stale','raw_tampered','missing_source'])
def test_plan_rebuild_cannot_refresh_old_or_unrecorded_sources(tmp_path, monkeypatch, defect):
    from scripts import e2e_plan
    stamp = (datetime.now(timezone.utc)-timedelta(minutes=16)).isoformat() if defect=='stale' else None
    p = seal(plan(),stamp); output=tmp_path/'plan.json'
    arguments=['e2e_plan','--project-number','123456','--out',str(output)]
    for key in SOURCE_KEYS:
        source=tmp_path/(key+'.json'); source.write_text(json.dumps(p[key]),encoding='utf-8-sig')
        p['snapshot_evidence']['sources'][key]['sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
        arguments+=['--'+key.replace('_','-'),str(source)]
    if defect=='raw_tampered':
        # 即使只改格式，原始檔 byte SHA256 也必須失敗。
        with (tmp_path/'service.json').open('a',encoding='utf-8') as stream: stream.write('\n')
    if defect=='missing_source': del p['snapshot_evidence']['sources']['tag_revision']
    if defect!='missing': (tmp_path/'snapshot-evidence.json').write_text(json.dumps(p['snapshot_evidence']),encoding='utf-8')
    monkeypatch.setattr(sys,'argv',arguments)
    assert e2e_plan.main()==2
    assert not output.exists()


@pytest.mark.parametrize('revision', ['main_revision','tag_revision'])
@pytest.mark.parametrize('defect', ['missing_interfaces','missing_egress','network','subnet','egress','connector',
    'malformed_interfaces','extra_interface','other_project','network_tags'])
def test_direct_vpc_uses_actual_revision_annotations(revision, defect):
    p=plan(); annotations=p[revision]['metadata']['annotations']
    interfaces=[{'network':'lw-vpc-staging','subnetwork':'lw-subnet-staging'}]
    if defect=='missing_interfaces': del annotations['run.googleapis.com/network-interfaces']
    elif defect=='missing_egress': del annotations['run.googleapis.com/vpc-access-egress']
    elif defect=='network': interfaces[0]['network']='other-network'
    elif defect=='subnet': interfaces[0]['subnetwork']='other-subnet'
    elif defect=='egress': annotations['run.googleapis.com/vpc-access-egress']='all-traffic'
    elif defect=='connector': annotations['run.googleapis.com/vpc-access-connector']='projects/123456/locations/asia-east1/connectors/other'
    elif defect=='malformed_interfaces': annotations['run.googleapis.com/network-interfaces']='not-json'
    elif defect=='extra_interface': interfaces.append(dict(interfaces[0]))
    elif defect=='other_project': interfaces[0]['network']='projects/other-project/global/networks/lw-vpc-staging'
    elif defect=='network_tags': interfaces[0]['tags']='unexpected-tag'
    if defect not in ('missing_interfaces','malformed_interfaces'):
        annotations['run.googleapis.com/network-interfaces']=json.dumps(interfaces)
    seal(p)
    with pytest.raises(e2e.SafetyError,match='direct_vpc'):
        e2e.validate_plan(p)


def test_direct_vpc_accepts_same_project_fully_qualified_resource_names():
    p=plan()
    p['tag_revision']['metadata']['annotations']['run.googleapis.com/network-interfaces']=json.dumps([{
        'network':'projects/life-world-513506/global/networks/lw-vpc-staging',
        'subnetwork':'projects/123456/regions/asia-east1/subnetworks/lw-subnet-staging'}])
    seal(p)
    assert e2e.validate_plan(p)['target'].startswith('https://e2e---')
