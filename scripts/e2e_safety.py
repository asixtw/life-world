"""驗收前的離線配置防護；不呼叫 GCP、不接觸資料庫。"""
import base64
from datetime import datetime
import json
import re
import time
from urllib.parse import urlsplit


class SafetyError(Exception):
    """只承載程式定義的固定原因碼，不包入遠端回應或使用者內容。"""


def require(condition, code):
    if not condition:
        raise SafetyError(code)


def env_values(revision):
    values = revision['spec']['containers'][0]['env']
    require(len({v['name'] for v in values}) == len(values), 'duplicate_env')
    return {v['name']:v.get('value') for v in values}, {v['name']:v for v in values}


def origin(url, local=False):
    parsed = urlsplit(url)
    require(parsed.scheme=='https' and not parsed.username and not parsed.password and
            not parsed.query and not parsed.fragment and parsed.path in ('','/'), 'invalid_origin')
    if local:
        require(parsed.hostname in ('127.0.0.1','localhost'), 'local_must_be_loopback')
    else:
        require(parsed.hostname.endswith('.run.app') and parsed.port is None, 'cloud_must_use_run_app')
    return url.rstrip('/')


def validate_plan(plan, *, allow_local=False, retired=False):
    """核對操作者匯出的 v1 Service／Revision／IAM，不自動調整任何資源。"""
    try:
        local = plan.get('mode')=='local-simulation'
        require(plan.get('mode') in ('cloud','local-simulation'), 'invalid_mode')
        require(not local or allow_local, 'local_simulation_requires_opt_in')
        captured = datetime.fromisoformat(plan['captured_at'])
        require(captured.tzinfo is not None and -60<=time.time()-captured.timestamp()<=900, 'stale_snapshot')
        require(plan['project_id']=='life-world-513506', 'wrong_project')
        namespace = str(plan['project_number']); require(namespace.isdigit(), 'invalid_project_number')
        service, main, tag = plan['service'],plan['main_revision'],plan['tag_revision']
        require(service['metadata']['name']=='lw-api-main', 'wrong_service')
        for resource in (service,main,tag):
            require(str(resource['metadata']['namespace'])==namespace, 'wrong_namespace')
            require(resource['metadata']['labels']['cloud.googleapis.com/location']=='asia-east1', 'wrong_region')
            require(any(c['type']=='Ready' and c['status']=='True' for c in resource['status']['conditions']), 'not_ready')
        annotations = service['metadata'].get('annotations',{})
        require(annotations.get('run.googleapis.com/invoker-iam-disabled','false').lower()=='false', 'iam_disabled')
        require(not any(m in ('allUsers','allAuthenticatedUsers') for b in plan['iam_policy']['bindings']
                        for m in b.get('members',[])), 'public_iam')
        main_name, tag_name = main['metadata']['name'],tag['metadata']['name']
        require(main_name!=tag_name and main_name.startswith('lw-api-main-') and tag_name.startswith('lw-api-main-'), 'wrong_revision')
        for routes in (service['spec']['traffic'],service['status']['traffic']):
            positive = [r for r in routes if r.get('percent',0)>0]
            require(len(positive)==1 and positive[0].get('percent')==100 and
                    positive[0].get('revisionName')==main_name and not positive[0].get('latestRevision'), 'main_not_pinned_100')
            tagged = [r for r in routes if r.get('tag')=='e2e']
            if retired:
                require(not tagged, 'tag_not_removed')
            else:
                require(len(tagged)==1 and tagged[0].get('revisionName')==tag_name and
                        tagged[0].get('percent',0)==0 and not tagged[0].get('latestRevision'), 'tag_not_zero')
        main_url = origin(service['status']['url'],local)
        target = None if retired else origin(next(r['url'] for r in service['status']['traffic'] if r.get('tag')=='e2e'),local)
        for revision,enabled,db,user in ((main,'false','life_world_dev','lw_app'),(tag,'true','life_world_e2e','lw_e2e_app')):
            values, entries = env_values(revision)
            require(values.get('LIFEWORLD_ENABLE_BUSINESS_API')==enabled and values.get('LIFEWORLD_DB_NAME')==db and
                    values.get('LIFEWORLD_DB_USER')==user and values.get('LIFEWORLD_DB_BACKEND')=='postgresql' and
                    values.get('LIFEWORLD_DB_SCHEMA')=='lw_core_draft' and values.get('LIFEWORLD_SECURE_COOKIES')=='true', 'unsafe_runtime_env')
            require('GOOGLE_APPLICATION_CREDENTIALS' not in entries, 'sa_key_not_allowed')
            if not local:
                require(values.get('LIFEWORLD_PG_CONNECTION')=='cloud_sql', 'private_connector_required')
                secret = entries['LIFEWORLD_DB_PASSWORD']; ref = secret.get('valueFrom',{}).get('secretKeyRef',{})
                require('value' not in secret and ref.get('name') and str(ref.get('key','')).isdigit(), 'pinned_secret_required')
                require(revision['spec']['serviceAccountName']=='lw-api-runtime@life-world-513506.iam.gserviceaccount.com', 'wrong_runtime_sa')
        main_env,_ = env_values(main); tag_env,_ = env_values(tag)
        if not local:
            instance = tag_env.get('LIFEWORLD_INSTANCE_CONNECTION_NAME','')
            require(instance.startswith('life-world-513506:asia-east1:') and main_env.get('LIFEWORLD_INSTANCE_CONNECTION_NAME')==instance, 'wrong_sql_instance')
            digests = [r['status']['imageDigest'].split('@')[-1] for r in (main,tag)]
            require(digests[0]==digests[1] and re.fullmatch(r'sha256:[0-9a-f]{64}',digests[0]), 'image_changed')
            require(tag['spec']['containers'][0]['image'].endswith('@'+digests[0]), 'image_must_use_digest')
        if not retired:
            require(target!=main_url, 'main_target_forbidden')
            if not local:
                require(urlsplit(target).hostname.startswith('e2e---lw-api-main-'), 'tag_url_required')
            hosts = {h.strip() for h in tag_env.get('LIFEWORLD_TRUSTED_HOSTS','').split(',')}
            require(not any('*' in h for h in hosts) and urlsplit(target).hostname in hosts and urlsplit(main_url).hostname in hosts, 'trusted_hosts_mismatch')
            require(tag_env.get('LIFEWORLD_EXTERNAL_ORIGIN')==target, 'external_origin_mismatch')
        points = plan.get('expected_points',1); require(type(points) is int and points>0, 'invalid_points')
        return {'audience':main_url,'target':target,'points':points,'local':local}
    except SafetyError:
        raise
    except Exception:
        raise SafetyError('malformed_snapshot') from None


def check_token(token, audience):
    """只做 audience／效期防呆；簽章與 Invoker 權限仍由真正 Cloud Run IAM 驗證。"""
    try:
        require(isinstance(token,str) and len(token)<16384 and not re.search(r'\s',token), 'invalid_token')
        parts = token.split('.'); require(len(parts)==3, 'invalid_token')
        claims = json.loads(base64.urlsafe_b64decode(parts[1]+'='*(-len(parts[1])%4)))
        require(claims['aud']==audience and float(claims['exp'])>time.time()+120, 'token_audience_or_expiry')
    except SafetyError:
        raise
    except Exception:
        raise SafetyError('invalid_token') from None
