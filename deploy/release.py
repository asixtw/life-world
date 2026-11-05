"""既有 Cloud Run 的自動候選發布；只用標準庫，不改 IAM 或執行 migration。"""
import argparse
import copy
from fnmatch import fnmatchcase
from datetime import datetime
import json
import os
import re
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PROJECT = 'life-world-513506'
REGION = 'asia-east1'
OWNER = 'lifeworld.dev/release-build'
COMMIT = 'lifeworld.dev/release-commit'
CREATED = 'lifeworld.dev/release-created'
PENDING = 'lifeworld.dev/release-pending'
PREVIOUS = 'lifeworld.dev/release-previous'
REVISION_TYPE = 'TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION'
TRIGGERS = {'web': '711e7258-2725-4007-a555-0f0100b77dbc',
            'api': '6ffa2066-8edd-4406-9f3f-31f967da57dc'}
WEB_FILES = tuple('collaboration/ui-kit/' + x for x in (
    'Dockerfile', '.dockerignore', 'cloud-nginx.conf', 'package.json', 'pnpm-lock.yaml',
    'pnpm-workspace.yaml', 'index.html', 'tsconfig.json', 'vite.config.ts',
    'src/**', 'public/**', 'assets/**', 'content/**', 'evaluation/**', 'tests/**', 'tools/**')) + (
    'deploy/cloudbuild.web.yaml', 'deploy/release.py', 'deploy/tests/test_release.py')
API_FILES = ('app/**', 'tests/**', 'scripts/**', 'deploy/Dockerfile.api', 'deploy/cloudbuild.api.yaml',
             'deploy/postgres/**', 'deploy/tests/**', 'deploy/release.py', 'requirements*', 'pyproject.toml',
             '.dockerignore', 'docs/database/schema-2026-11-02/*.sql')
RUNTIME_FIELDS = ('serviceAccount', 'vpcAccess', 'volumes', 'executionEnvironment', 'encryptionKey',
                  'maxInstanceRequestConcurrency', 'sessionAffinity', 'timeout', 'scaling', 'containers',
                  'healthCheckDisabled', 'nodeSelector', 'serviceMesh', 'gpuZonalRedundancyDisabled')
ORIGIN = 'LIFEWORLD_EXTERNAL_ORIGIN'
HOSTS = 'LIFEWORLD_TRUSTED_HOSTS'
LOCK_WAIT_SECONDS = 900
LOCK_POLL_SECONDS = 5


def snapshot_traffic(service):
    """保存實際路由，不把 latest 指標帶入候選部署或回滾。"""
    result = []
    for item in service.get('trafficStatuses', []):
        revision = item.get('revision', '').rsplit('/', 1)[-1]
        if not revision:
            raise ValueError('Traffic has no resolved revision')
        if item.get('percent', 0):
            result.append({'type': REVISION_TYPE, 'revision': revision, 'percent': item['percent']})
        if item.get('tag'):
            result.append({'type': REVISION_TYPE, 'revision': revision, 'tag': item['tag']})
    if sum(x.get('percent', 0) for x in result) != 100:
        raise ValueError('Traffic is not a complete, reconciled 100 percent allocation')
    return result


def positive_traffic(traffic):
    return sorted((x['revision'].rsplit('/', 1)[-1], x['percent']) for x in traffic if x.get('percent', 0))


def tag_map(service):
    return {x['tag']: x['revision'].rsplit('/', 1)[-1] for x in snapshot_traffic(service) if x.get('tag')}


def promoted_traffic(service, revision):
    return [{'type': REVISION_TYPE, 'revision': revision, 'percent': 100}] + [
        x for x in snapshot_traffic(service) if x.get('tag')]


def source_is_current(comparison, component):
    """允許後續不相關 main commit，避免檔案過濾讓唯一相關建置永遠無法發布。"""
    if comparison.get('status') == 'identical':
        return True
    files = comparison.get('files', [])
    if comparison.get('status') != 'ahead' or len(files) >= 300:
        return False  # GitHub compare 的檔案上限不能當成完整來源證據。
    paths = WEB_FILES if component == 'web' else API_FILES
    return not any(any(fnmatchcase(path, pattern) for pattern in paths) for item in files
                   for path in (item.get('filename', ''), item.get('previous_filename', '')) if path)


def runtime_config(template):
    """完整比較執行設定；僅排除本次必須變動的映像、Origin 與測試 Host。"""
    result = {k: copy.deepcopy(template[k]) for k in RUNTIME_FIELDS if k in template}
    for container in result.get('containers', []):
        container.pop('image', None)
        container['env'] = sorted((x for x in container.get('env', []) if x['name'] not in (ORIGIN, HOSTS)),
                                  key=lambda x: x['name'])
    return result


def api_overrides(service, production, tag):
    """正式流量 revision 才是 API 設定來源；latest 可能是 localhost hostfix。"""
    current = service['template']
    if len(production.get('containers', [])) != 1 or runtime_config(current) != runtime_config(production):
        raise ValueError('API runtime differs from production; automatic release is blocked')
    env = {x['name']: x for x in production['containers'][0].get('env', [])}
    if len(env) != len(production['containers'][0].get('env', [])):
        raise ValueError('Duplicate API environment names')
    values = {k: v.get('value') for k, v in env.items()}
    origin = values.get(ORIGIN, '')
    parsed = urlsplit(origin)
    formal_hosts = values.get(HOSTS, '').split(',')
    if (parsed.scheme != 'https' or parsed.path or parsed.query or parsed.fragment or parsed.port
            or parsed.username or parsed.password or not parsed.hostname
            or parsed.hostname not in formal_hosts):
        raise ValueError('API production Origin/Hosts are not a verified HTTPS origin')
    if any(not re.fullmatch(r'[a-z0-9.-]+', h) or h in ('localhost', '127.0.0.1') for h in formal_hosts):
        raise ValueError('API production Trusted Hosts are unsafe')
    if (values.get('LIFEWORLD_DB_BACKEND') != 'postgresql'
            or values.get('LIFEWORLD_PG_CONNECTION') != 'cloud_sql'
            or values.get('LIFEWORLD_DB_NAME') != 'life_world_dev'
            or values.get('LIFEWORLD_INSTANCE_CONNECTION_NAME') != PROJECT + ':' + REGION + ':lw-pg-staging-trial'
            or values.get('LIFEWORLD_SECURE_COOKIES') != 'true'
            or not env.get('LIFEWORLD_DB_PASSWORD', {}).get('valueSource', {}).get('secretKeyRef')
            or not production.get('vpcAccess')):
        raise ValueError('API database/network/secret binding is not the existing approved configuration')
    for name, item in env.items():
        if re.search(r'PASSWORD|SECRET|TOKEN|PRIVATE_KEY', name) and item.get('value'):
            raise ValueError('API credentials must remain Secret Manager references')
    host = urlsplit(service['uri']).hostname
    if not host or not host.endswith('.run.app'):
        raise ValueError('Unexpected Cloud Run canonical URL')
    # 只移除本發布器的舊候選 Host，避免每次發布累積環境變數；不碰 hostfix revision。
    hosts = [h for h in formal_hosts if not re.fullmatch(r'c-[0-9a-f]{32}---' + re.escape(host), h)]
    return {ORIGIN: origin, HOSTS: ','.join(dict.fromkeys(hosts + [host, tag + '---' + host]))}


def rollback_owned(service, build_id, revision):
    return (service.get('annotations', {}).get(OWNER) == build_id
            and positive_traffic(snapshot_traffic(service)) == [(revision, 100)])


class ReleaseError(RuntimeError):
    pass


class Conflict(ReleaseError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 不將健康檢查的 IAM token 轉送到另一個網址。


class Cloud:
    def __init__(self):
        self.token = None
        self.opener = build_opener(NoRedirect)

    def gcloud(self, *args, timeout=60):
        try:
            result = subprocess.run([os.environ.get('GCLOUD', 'gcloud'), *args],
                                    capture_output=True, text=True, timeout=timeout, check=True)
        except (subprocess.SubprocessError, OSError) as exc:
            # 不輸出 stderr／請求本文：它們可能含權杖或環境設定。
            raise ReleaseError('gcloud command failed: ' + ' '.join(args[:3])) from exc
        return result.stdout.strip()

    def json(self, url, method='GET', body=None, authenticated=True):
        headers = {'User-Agent': 'lifeworld-release', 'Accept': 'application/json'}
        if authenticated:
            if self.token is None:
                self.token = self.gcloud('auth', 'print-access-token', '--quiet')
            headers['Authorization'] = 'Bearer ' + self.token
        data = None if body is None else json.dumps(body).encode()
        if data is not None:
            headers['Content-Type'] = 'application/json'
        try:
            with self.opener.open(Request(url, data=data, headers=headers, method=method), timeout=25) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code in (409, 412):
                raise Conflict('Cloud Run etag changed; no blind overwrite') from exc
            raise ReleaseError('Control-plane request failed: HTTP ' + str(exc.code)) from exc

    def wait(self, operation):
        deadline = time.monotonic() + 180
        while not operation.get('done'):
            if time.monotonic() >= deadline:
                raise ReleaseError('Cloud Run operation timed out')
            time.sleep(1)
            operation = self.json('https://run.googleapis.com/v2/' + operation['name'])
        if operation.get('error'):
            raise ReleaseError('Cloud Run operation failed')

    def health(self, url, audience, component):
        token = self.gcloud('auth', 'print-identity-token', '--audiences=' + audience, '--quiet')
        checks = [('/health', 'ok')] if component == 'web' else [('/health', 'ok'), ('/ready', 'ready')]
        for path, expected in checks:
            for attempt in range(3):
                try:
                    req = Request(url + path, headers={'Authorization': 'Bearer ' + token})
                    with self.opener.open(req, timeout=15) as response:
                        body = response.read(4096).decode()
                        parsed = None if component == 'web' else json.loads(body)
                        valid = body.strip() == expected if component == 'web' else isinstance(parsed, dict) and parsed.get('status') == expected
                        if response.status == 200 and valid:
                            break
                except (OSError, ValueError):
                    pass
                if attempt == 2:
                    raise ReleaseError('Authenticated health check failed: ' + path)
                time.sleep(2)


class Publisher:
    def __init__(self, component, commit, build_id, cloud=None):
        self.component, self.commit, self.build_id = component, commit, build_id
        self.cloud = cloud or Cloud()
        self.service = 'lw-' + component + '-main'
        self.name = 'projects/' + PROJECT + '/locations/' + REGION + '/services/' + self.service
        self.url = 'https://run.googleapis.com/v2/' + self.name
        self.tag = 'c-' + build_id.replace('-', '')
        self.revision = self.service + '-' + self.tag
        self.acquired = False

    def get(self):
        return self.cloud.json(self.url)

    def build(self, build_id):
        return self.cloud.json('https://cloudbuild.googleapis.com/v1/projects/' + PROJECT
                               + '/locations/' + REGION + '/builds/' + build_id)

    def compare(self, base, head):
        return self.cloud.json('https://api.github.com/repos/asixtw/life-world/compare/' + base + '...' + head,
                               authenticated=False)

    def fresh(self):
        comparison = self.compare(self.commit, 'main')
        if comparison.get('status') == 'ahead' and comparison.get('merge_base_commit', {}).get('sha') != self.commit:
            return False
        return source_is_current(comparison, self.component)

    def patch(self, service, **fields):
        if not service.get('etag'):
            raise ReleaseError('Missing Cloud Run etag')
        body = {'name': self.name, 'etag': service['etag'], **fields}
        operation = self.cloud.json(self.url + '?' + urlencode({'updateMask': ','.join(fields)}), 'PATCH', body)
        self.cloud.wait(operation)

    def owned(self):
        service = self.get()
        if service.get('annotations', {}).get(OWNER) != self.build_id:
            raise ReleaseError('Release ownership changed')
        return service

    def acquire(self):
        """同一服務以 etag 原子取得鎖；不以租約逾時搶走仍執行中的發布。"""
        # 涵蓋前一版候選部署／驗證；同時保留時間與次數上限，不形成無限輪詢。
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        for _ in range(LOCK_WAIT_SECONDS // LOCK_POLL_SECONDS + 1):
            service = self.get()
            owner = service.get('annotations', {}).get(OWNER)
            busy = service.get('reconciling', False)
            if owner == self.build_id:
                raise ReleaseError('This build already has an active publisher')
            if owner:
                if not re.fullmatch(r'[0-9a-f-]{36}', owner):
                    raise ReleaseError('Unknown release lock owner')
                # 只在原 build 已結束且 Cloud Run 已完成操作時復原遺留鎖。
                status = self.build(owner).get('status')
                busy = busy or status not in ('SUCCESS', 'FAILURE', 'INTERNAL_ERROR', 'TIMEOUT', 'CANCELLED', 'EXPIRED')
            if not busy:
                if owner and service.get('annotations', {}).get(PENDING):
                    try:
                        self.recover_pending(service, owner)
                    except Conflict:
                        pass
                    continue
                annotations = {**service.get('annotations', {}), OWNER: self.build_id}
                try:
                    self.patch(service, annotations=annotations, traffic=snapshot_traffic(service))
                    self.acquired = True
                    return self.owned()
                except Conflict:
                    pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(LOCK_POLL_SECONDS, remaining))
        raise ReleaseError('Another release is active; bounded lock wait expired')

    def restore(self, service, journal):
        """只有本次候選仍持有正式流量，或流量尚未切換，才可回復。"""
        previous = journal['traffic']
        if (sum(x.get('percent', 0) for x in previous) != 100
                or any(x.get('type') != REVISION_TYPE or not x.get('revision') for x in previous)):
            raise ReleaseError('Invalid saved rollback allocation')
        live = positive_traffic(snapshot_traffic(service))
        if live not in ([(journal['candidate'], 100)], positive_traffic(previous)):
            raise ReleaseError('Rollback refused: another actor changed production traffic')
        annotations = dict(service.get('annotations', {}))
        for key in (COMMIT, CREATED, PENDING):
            annotations.pop(key, None)
        for key in (COMMIT, CREATED):
            if journal.get(key):
                annotations[key] = journal[key]
        traffic = [x for x in previous if x.get('percent')] + [
            x for x in snapshot_traffic(service) if x.get('tag')]
        self.patch(service, annotations=annotations, traffic=traffic)

    def recover_pending(self, service, owner):
        """Build 被取消／逾時時，下一個 build 先完成原發布的回復，再取得鎖。"""
        journal = json.loads(service['annotations'][PENDING])
        expected = self.service + '-c-' + owner.replace('-', '')
        if journal.get('candidate') != expected:
            raise ReleaseError('Unexpected pending release journal')
        self.restore(service, journal)

    def api_config(self, service):
        if tag_map(service).get('hostfix') != 'lw-api-main-00004-yiv':
            raise ReleaseError('Protected hostfix tag no longer matches the approved revision')
        positive = positive_traffic(snapshot_traffic(service))
        if len(positive) != 1 or positive[0][1] != 100:
            raise ReleaseError('API production revision is ambiguous; automatic release blocked')
        production = self.cloud.json(self.url + '/revisions/' + positive[0][0])
        overrides = api_overrides(service, production, self.tag)
        return production, overrides

    def not_older_than_release(self, service, created):
        annotations = service.get('annotations', {})
        last = annotations.get(COMMIT)
        if last and last != self.commit:
            if self.compare(last, self.commit).get('status') != 'ahead':
                return False
        if last == self.commit and annotations.get(CREATED):
            return datetime.fromisoformat(created.replace('Z', '+00:00')) >= datetime.fromisoformat(
                annotations[CREATED].replace('Z', '+00:00'))
        return True

    def cleanup(self):
        if not self.acquired:
            return
        try:
            service = self.owned()
            if service.get('reconciling') or service.get('annotations', {}).get(PENDING):
                return  # 未完成的操作由下一個 build 查明原 build 結束後再接手。
            annotations = dict(service.get('annotations', {}))
            annotations.pop(OWNER, None)
            traffic = [x for x in snapshot_traffic(service) if x.get('tag') != self.tag]
            self.patch(service, annotations=annotations, traffic=traffic)
        except ReleaseError:
            print('WARNING: release cleanup deferred; next build will verify the previous build status')

    def run(self):
        build = self.build(self.build_id)
        substitutions = build.get('substitutions', {})
        if (build.get('buildTriggerId') != TRIGGERS[self.component]
                or substitutions.get('COMMIT_SHA') != self.commit or substitutions.get('BRANCH_NAME') != 'main'):
            raise ReleaseError('Build is not the existing main push trigger')
        created = build['createTime']
        if not self.fresh():
            print('SKIPPED: a newer relevant main commit exists')
            return
        # 先取得身分權杖，缺權限時在建立候選或修改服務前即停止。
        initial = self.get()
        if initial.get('invokerIamDisabled'):
            raise ReleaseError('Authenticated invocation must remain enabled')
        self.cloud.gcloud('auth', 'print-identity-token', '--audiences=' + initial['uri'], '--quiet')
        published = False
        try:
            service = self.acquire()
            if not self.fresh() or not self.not_older_than_release(service, created):
                print('SKIPPED: this build has been superseded')
                return
            previous = snapshot_traffic(service)
            previous_tags = tag_map(service)
            if self.tag in previous_tags:
                raise ReleaseError('Candidate tag already exists; refusing reassignment')
            annotations_before = dict(service.get('annotations', {}))
            runtime_sa = 'lw-' + self.component + '-runtime@' + PROJECT + '.iam.gserviceaccount.com'
            if service['template'].get('serviceAccount') != runtime_sa:
                raise ReleaseError('Unexpected runtime service account')
            production, overrides = self.api_config(service) if self.component == 'api' else (None, {})
            image = REGION + '-docker.pkg.dev/' + PROJECT + '/lw-containers/lw-' + self.component
            digest = self.cloud.gcloud('artifacts', 'docker', 'images', 'describe',
                                       image + ':' + self.commit + '-' + self.build_id,
                                       '--project=' + PROJECT, '--format=value(image_summary.digest)')
            if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
                raise ReleaseError('Invalid immutable image digest')
            args = ['run', 'deploy', self.service, '--project=' + PROJECT, '--region=' + REGION,
                    '--platform=managed', '--image=' + image + '@' + digest, '--no-traffic',
                    '--tag=' + self.tag, '--revision-suffix=' + self.tag, '--service-account=' + runtime_sa,
                    '--update-labels=commit-sha=' + self.commit, '--quiet']
            if overrides:
                args.append('--update-env-vars=^|^' + '|'.join(k + '=' + v for k, v in overrides.items()))
            self.cloud.gcloud(*args, timeout=480)
            candidate = self.cloud.json(self.url + '/revisions/' + self.revision)
            if candidate['containers'][0]['image'] != image + '@' + digest:
                raise ReleaseError('Candidate does not use the verified image digest')
            if production is not None:
                if runtime_config(candidate) != runtime_config(production):
                    raise ReleaseError('Candidate changed API runtime configuration')
                env = {x['name']: x.get('value') for x in candidate['containers'][0]['env']}
                if any(env.get(k) != v for k, v in overrides.items()):
                    raise ReleaseError('Candidate did not receive the formal API Origin/Hosts')
            service = self.owned()
            if any(tag_map(service).get(k) != v for k, v in previous_tags.items()):
                raise ReleaseError('An existing tag changed; refusing traffic publication')
            tagged = [x for x in service['trafficStatuses'] if x.get('tag') == self.tag]
            if len(tagged) != 1 or tagged[0]['revision'].rsplit('/', 1)[-1] != self.revision:
                raise ReleaseError('Candidate tag is not bound to the exact candidate revision')
            candidate_url = tagged[0]['uri']
            if urlsplit(candidate_url).hostname != self.tag + '---' + urlsplit(service['uri']).hostname:
                raise ReleaseError('Unexpected candidate URL')
            self.cloud.health(candidate_url, service['uri'], self.component)
            if not self.fresh():
                print('SKIPPED: newer source arrived while checking the candidate')
                return
            service = self.owned()
            if positive_traffic(snapshot_traffic(service)) != positive_traffic(previous):
                raise ReleaseError('Production traffic changed during candidate verification')
            journal = {'traffic': previous, 'candidate': self.revision,
                       COMMIT: annotations_before.get(COMMIT), CREATED: annotations_before.get(CREATED)}
            annotations = {**service.get('annotations', {}), COMMIT: self.commit, CREATED: created,
                           PREVIOUS: json.dumps(previous), PENDING: json.dumps(journal)}
            try:
                # 指紋、回復紀錄及明確流量在同一 etag 更新；回應遺失也不能當成未發布。
                self.patch(service, annotations=annotations, traffic=promoted_traffic(service, self.revision))
                published = True
                live = self.owned()
                if not rollback_owned(live, self.build_id, self.revision):
                    raise ReleaseError('Production did not resolve to the candidate revision')
                self.cloud.health(live['uri'], live['uri'], self.component)
                live = self.owned()
                completed = dict(live['annotations'])
                completed.pop(PENDING, None)
                self.patch(live, annotations=completed)
            except Exception:
                live = self.owned()
                if live.get('reconciling'):
                    raise ReleaseError('Publication outcome pending; retained recovery journal and lock')
                self.restore(live, journal)
                print('ROLLED_BACK: restored the previous explicit traffic allocation')
                raise
            state = {'component': self.component, 'commit': self.commit, 'build': self.build_id,
                     'revision': self.revision, 'digest': digest, 'previous_traffic': previous, 'published': published}
            # Cloud Logging 與服務上的 release-previous 皆保留上一版，不保存執行環境或憑證。
            print(json.dumps(state))
        finally:
            self.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', choices=('web', 'api'), required=True)
    parser.add_argument('--commit', default='')
    parser.add_argument('--build-id', default='')
    parser.add_argument('--branch', default='')
    parser.add_argument('--preflight', action='store_true', help='只讀取現況並驗證 API 隔離，不部署或取得發布鎖')
    args = parser.parse_args()
    if args.preflight:
        publisher = Publisher(args.component, '', '0' * 36)
        service = publisher.get()
        snapshot_traffic(service)
        if args.component == 'api':
            publisher.api_config(service)
        print('PREFLIGHT_OK: existing runtime configuration is isolated; no cloud changes made')
        return
    if (args.branch != 'main' or not re.fullmatch(r'[0-9a-f]{40}', args.commit)
            or not re.fullmatch(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', args.build_id)):
        raise ReleaseError('Release requires a main commit and a valid Cloud Build ID')
    Publisher(args.component, args.commit, args.build_id).run()


if __name__ == '__main__':
    try:
        main()
    except (ReleaseError, ValueError, KeyError, OSError) as error:
        print('RELEASE_BLOCKED: ' + str(error))
        raise SystemExit(1)
