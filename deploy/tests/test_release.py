"""只驗證發布的關鍵邊界；全部使用合成控制平面資料，不呼叫 GCP。"""
import copy
import importlib.util
from pathlib import Path
import unittest
from contextlib import chdir, redirect_stdout
import io
import json
import tempfile
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('release', Path(__file__).parents[1] / 'release.py')
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def service():
    return {'uri': 'https://api-example.a.run.app', 'annotations': {},
            'trafficStatuses': [{'revision': 'old', 'percent': 100},
                                {'revision': 'fixed', 'tag': 'hostfix', 'uri': 'https://hostfix---api-example.a.run.app'}],
            'template': {'serviceAccount': 'lw-api-runtime@life-world-513506.iam.gserviceaccount.com',
                         'vpcAccess': {'egress': 'PRIVATE_RANGES_ONLY',
                                       'networkInterfaces': [{'network': 'existing', 'subnetwork': 'existing-subnet'}]},
                         'timeout': '300s', 'maxInstanceRequestConcurrency': 80, 'scaling': {},
                         'containers': [{'image': 'old-image', 'resources': {'limits': {'cpu': '1000m', 'memory': '512Mi'},
                                                                             'cpuIdle': True, 'startupCpuBoost': True}, 'env': [
                             {'name': 'LIFEWORLD_DB_BACKEND', 'value': 'postgresql'},
                             {'name': 'LIFEWORLD_PG_CONNECTION', 'value': 'cloud_sql'},
                             {'name': 'LIFEWORLD_DB_NAME', 'value': 'life_world_alpha'},
                             {'name': 'LIFEWORLD_DB_USER', 'value': 'lw_alpha_app'},
                             {'name': 'LIFEWORLD_INSTANCE_CONNECTION_NAME', 'value': 'life-world-513506:asia-east1:lw-pg-staging-trial'},
                             {'name': 'LIFEWORLD_DB_PASSWORD', 'valueSource': {'secretKeyRef': {'secret': 'existing-secret', 'version': '1'}}},
                             {'name': 'LIFEWORLD_EXTERNAL_ORIGIN', 'value': 'https://api-example.a.run.app'},
                             {'name': 'LIFEWORLD_TRUSTED_HOSTS', 'value': 'api-example.a.run.app'},
                             {'name': 'LIFEWORLD_SECURE_COOKIES', 'value': 'true'}]}]}}


def env_item(spec, name):
    return next(x for x in spec['containers'][0]['env'] if x['name'] == name)


def set_env(spec, name, value):
    env = spec['containers'][0]['env']
    env[:] = [x for x in env if x['name'] != name] + [{'name': name, 'value': value}]


class ReleaseSafety(unittest.TestCase):
    def test_snapshot_pins_latest_and_preserves_hostfix(self):
        result = release.snapshot_traffic(service())
        self.assertEqual(result[0], {'type': 'TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION', 'revision': 'old', 'percent': 100})
        self.assertEqual(result[1]['tag'], 'hostfix')
        self.assertEqual(result[1]['revision'], 'fixed')

    def test_promotion_keeps_existing_tags(self):
        result = release.promoted_traffic(service(), 'candidate')
        self.assertEqual([x for x in result if x.get('percent')],
                         [{'type': 'TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION', 'revision': 'candidate', 'percent': 100}])
        self.assertIn({'type': 'TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION', 'revision': 'fixed', 'tag': 'hostfix'}, result)

    def test_incomplete_traffic_is_rejected(self):
        current = service()
        current['trafficStatuses'][0]['percent'] = 50
        with self.assertRaises(ValueError):
            release.snapshot_traffic(current)

    def test_later_irrelevant_commit_does_not_block_web(self):
        diff = {'status': 'ahead', 'files': [{'filename': 'app/main.py'}]}
        self.assertTrue(release.source_is_current(diff, 'web'))
        self.assertFalse(release.source_is_current(diff, 'api'))

    def test_old_or_renamed_source_is_rejected(self):
        self.assertFalse(release.source_is_current({'status': 'behind', 'files': []}, 'web'))
        diff = {'status': 'ahead', 'files': [{'filename': 'old.txt', 'previous_filename': 'collaboration/ui-kit/src/App.tsx'}]}
        self.assertFalse(release.source_is_current(diff, 'web'))

    def test_shared_release_change_blocks_both_components(self):
        diff = {'status': 'ahead', 'files': [{'filename': 'deploy/release.py'}]}
        for component in ('web', 'api'):
            self.assertFalse(release.source_is_current(diff, component))

    def test_web_dockerignored_documentation_does_not_trigger_release(self):
        diff = {'status': 'ahead', 'files': [{'filename': 'collaboration/ui-kit/docs/HANDOFF.md'}]}
        self.assertTrue(release.source_is_current(diff, 'web'))

    def test_large_compare_is_not_treated_as_complete_source_evidence(self):
        self.assertFalse(release.source_is_current({'status': 'ahead', 'files': [{'filename': 'docs/x'}] * 300}, 'web'))

    def test_api_replaces_only_hostfix_origin_and_hosts(self):
        current = service()
        production = copy.deepcopy(current['template'])
        current['template']['containers'][0]['env'][-3]['value'] = 'https://localhost:8443'
        result = release.api_overrides(current, production, 'c-test')
        self.assertEqual(result['LIFEWORLD_EXTERNAL_ORIGIN'], 'https://api-example.a.run.app')
        self.assertIn('c-test---api-example.a.run.app', result['LIFEWORLD_TRUSTED_HOSTS'].split(','))
        self.assertEqual(set(result), {'LIFEWORLD_EXTERNAL_ORIGIN', 'LIFEWORLD_TRUSTED_HOSTS'})

    def test_api_network_or_secret_drift_blocks_release(self):
        """正式 revision 本身缺私有網路，或密碼不是 Secret 參照，就阻擋。"""
        for field in ('vpcAccess', 'containers'):
            current = service()
            production = copy.deepcopy(current['template'])
            if field == 'vpcAccess':
                production.pop('vpcAccess')
            else:
                set_env(production, 'LIFEWORLD_DB_PASSWORD', 'plain-password')
            with self.subTest(field=field), self.assertRaises(ValueError):
                release.api_overrides(current, production, 'c-test')

    def test_template_drift_from_local_e2e_deploys_no_longer_blocks_release(self):
        """同一服務也部署本機用的 e2e 標籤，服務範本常是 e2e 設定；設定來源只看正式 revision（2026-11-05 起因此被擋）。"""
        current = service()
        production = copy.deepcopy(current['template'])
        current['template']['vpcAccess']['egress'] = 'ALL_TRAFFIC'
        set_env(current['template'], 'LIFEWORLD_DB_NAME', 'life_world_e2e')
        result = release.api_overrides(current, production, 'c-test')
        self.assertEqual(set(result), {'LIFEWORLD_EXTERNAL_ORIGIN', 'LIFEWORLD_TRUSTED_HOSTS'})

    def test_api_release_accepts_only_the_alpha_database(self):
        """2026-11-12：Cloud Run 只連 life_world_alpha；dev、e2e 或其他資料庫的正式設定一律不發布。"""
        for name, value in (('LIFEWORLD_DB_NAME', 'life_world_dev'), ('LIFEWORLD_DB_NAME', 'life_world_e2e'),
                            ('LIFEWORLD_DB_USER', 'lw_app'), ('LIFEWORLD_DB_USER', 'lw_e2e_app'),
                            ('LIFEWORLD_INSTANCE_CONNECTION_NAME', 'other:asia-east1:other')):
            production = copy.deepcopy(service()['template'])
            set_env(production, name, value)
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                release.api_overrides(service(), production, 'c-test')
        self.assertTrue(release.api_overrides(service(), copy.deepcopy(service()['template']), 'c-test'))

    def test_api_deploy_copies_the_production_config_instead_of_the_template(self):
        production = copy.deepcopy(service()['template'])
        overrides = {'LIFEWORLD_EXTERNAL_ORIGIN': 'https://api-example.a.run.app', 'LIFEWORLD_TRUSTED_HOSTS': 'h1,h2'}
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'env.json')
            flags = release.api_deploy_flags(production, overrides, path)
            env = json.loads(Path(path).read_text(encoding='utf-8'))
        self.assertEqual((env['LIFEWORLD_DB_NAME'], env['LIFEWORLD_DB_USER']), ('life_world_alpha', 'lw_alpha_app'))
        self.assertEqual(env['LIFEWORLD_TRUSTED_HOSTS'], 'h1,h2')
        self.assertNotIn('LIFEWORLD_DB_PASSWORD', env)  # 憑證只以 Secret 參照傳入，不寫進檔案
        for flag in ('--env-vars-file=' + path, '--set-secrets=LIFEWORLD_DB_PASSWORD=existing-secret:1',
                     '--network=existing', '--subnet=existing-subnet', '--vpc-egress=private-ranges-only',
                     '--timeout=300', '--cpu=1000m', '--memory=512Mi', '--concurrency=80',
                     '--min-instances=0', '--max-instances=default', '--cpu-throttling', '--cpu-boost'):
            self.assertIn(flag, flags)

    def test_localhost_production_is_never_used(self):
        current = service()
        production = copy.deepcopy(current['template'])
        production['containers'][0]['env'][-3]['value'] = 'https://localhost:8443'
        with self.assertRaises(ValueError):
            release.api_overrides(current, production, 'c-test')

    def test_rollback_cannot_overwrite_another_publisher(self):
        current = service()
        current['annotations'] = {'lifeworld.dev/release-build': 'ours'}
        current['trafficStatuses'][0]['revision'] = 'candidate'
        self.assertTrue(release.rollback_owned(current, 'ours', 'candidate'))
        self.assertFalse(release.rollback_owned(current, 'other-build', 'candidate'))
        current['trafficStatuses'][0]['revision'] = 'newer'
        self.assertFalse(release.rollback_owned(current, 'ours', 'candidate'))


class FakeCloud:
    """模擬真實的發布副作用及失敗點；不依程式輸出宣稱發布成功。"""
    def __init__(self, publisher):
        self.publisher, self.commands, self.checks = publisher, [], 0

    def gcloud(self, *args, **kwargs):
        self.commands.append(args)
        if args[0] == 'auth':
            return 'synthetic-token'
        if args[0] == 'artifacts':
            return 'sha256:' + 'a' * 64
        if args[:2] == ('run', 'deploy'):
            self.image = next(x.split('=', 1)[1] for x in args if x.startswith('--image='))
            env_file = next((x.split('=', 1)[1] for x in args if x.startswith('--env-vars-file=')), None)
            if env_file:  # api：只依這次給的部署參數重建候選設定，不沿用服務範本
                self.candidate = copy.deepcopy(self.publisher.production)
                env = [{'name': k, 'value': v} for k, v in json.loads(Path(env_file).read_text(encoding='utf-8')).items()]
                for item in next(x.split('=', 1)[1] for x in args if x.startswith('--set-secrets=')).split(','):
                    name, ref = item.split('=', 1)
                    secret, version = ref.rsplit(':', 1)
                    env.append({'name': name, 'valueSource': {'secretKeyRef': {'secret': secret, 'version': version}}})
                self.candidate['containers'][0]['env'] = env
                self.candidate['containers'][0].update(self.publisher.candidate_changes)
            self.publisher.state['trafficStatuses'].append({
                'revision': self.publisher.revision, 'tag': self.publisher.tag,
                'uri': 'https://' + self.publisher.tag + '---api-example.a.run.app'})
            return ''
        raise AssertionError(args)

    def json(self, url, **kwargs):
        if '/revisions/' in url:
            if url.endswith('/revisions/' + self.publisher.revision) and getattr(self, 'candidate', None):
                return {**copy.deepcopy(self.candidate), 'containers': [{**self.candidate['containers'][0], 'image': self.image}]}
            if url.endswith('/revisions/old') and self.publisher.component == 'api':
                return copy.deepcopy(self.publisher.production)
            return {'containers': [{'image': self.image}]}
        raise AssertionError(url)

    def health(self, *args):
        self.checks += 1
        if self.checks == self.publisher.fail_health:
            raise release.ReleaseError('synthetic health failure')


class FakePublisher(release.Publisher):
    def __init__(self, *, fail_health=0, lost_response=False, conflict=False, component='web', candidate_changes=None):
        super().__init__(component, 'a' * 40, '11111111-1111-4111-8111-111111111111')
        self.state = service()
        self.state['etag'] = '0'
        self.state['template']['serviceAccount'] = 'lw-' + component + '-runtime@life-world-513506.iam.gserviceaccount.com'
        if component == 'api':  # 受保護的 hostfix 標籤名稱
            self.state['trafficStatuses'][1]['revision'] = 'lw-api-main-00004-yiv'
        self.production = copy.deepcopy(self.state['template'])  # 正式 revision（alpha）的設定
        self.candidate_changes = candidate_changes or {}
        self.cloud = FakeCloud(self)
        self.fail_health, self.lost_response, self.conflict = fail_health, lost_response, conflict
        self.allocations = []

    def get(self):
        return copy.deepcopy(self.state)

    def build(self, build_id):
        return {'buildTriggerId': release.TRIGGERS[self.component], 'createTime': '2026-11-05T00:00:00Z',
                'substitutions': {'COMMIT_SHA': self.commit, 'BRANCH_NAME': 'main'}, 'status': 'FAILURE'}

    def fresh(self):
        return True

    def patch(self, current, **fields):
        if current['etag'] != self.state['etag']:
            raise release.Conflict('synthetic etag conflict')
        publishing = positive(fields.get('traffic', [])) == [(self.revision, 100)]
        if publishing and self.conflict:
            raise release.Conflict('synthetic racing publisher')
        self.state.update({k: copy.deepcopy(v) for k, v in fields.items() if k != 'traffic'})
        if 'traffic' in fields:
            self.allocations.append(positive(fields['traffic']))
            self.state['trafficStatuses'] = copy.deepcopy(fields['traffic'])
            for item in self.state['trafficStatuses']:
                if item.get('tag'):
                    item['uri'] = 'https://' + item['tag'] + '---api-example.a.run.app'
        self.state['etag'] = str(int(self.state['etag']) + 1)
        if publishing and self.lost_response:
            self.lost_response = False
            raise release.ReleaseError('synthetic lost response after accepted promotion')


def positive(traffic):
    return release.positive_traffic(traffic)


class ReleaseExecution(unittest.TestCase):
    def test_lock_accepts_a_previous_build_finishing_after_four_minutes(self):
        publisher = FakePublisher()
        owner = '22222222-2222-4222-8222-222222222222'
        publisher.state['annotations'][release.OWNER] = owner
        clock = [0.0]
        publisher.build = lambda bid: {'status': 'WORKING' if clock[0] < 240 else 'SUCCESS'}
        # 以虛擬時間跨過舊 180 秒界線；不實際等待，也不接管執行中的 build。
        with patch.object(release.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(
                release.time, 'sleep', side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)):
            current = publisher.acquire()
        self.assertGreaterEqual(clock[0], 240)
        self.assertEqual(current['annotations'][release.OWNER], publisher.build_id)

    def test_lock_stops_after_fifteen_minutes_without_stealing_a_live_build(self):
        publisher = FakePublisher()
        owner = '22222222-2222-4222-8222-222222222222'
        publisher.state['annotations'][release.OWNER] = owner
        publisher.build = lambda bid: {'status': 'WORKING'}
        clock = [0.0]
        with patch.object(release.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(
                release.time, 'sleep', side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)):
            with self.assertRaisesRegex(release.ReleaseError, 'bounded lock wait expired'):
                publisher.acquire()
        self.assertEqual(clock[0], 900)
        self.assertEqual(publisher.state['annotations'][release.OWNER], owner)
        self.assertFalse(publisher.acquired)

    def execute(self, publisher):
        with tempfile.TemporaryDirectory() as directory, chdir(directory), patch.object(release.time, 'sleep'), redirect_stdout(io.StringIO()):
            publisher.run()

    def test_success_uses_digest_no_traffic_and_keeps_old_tag(self):
        publisher = FakePublisher()
        self.execute(publisher)
        self.assertEqual(positive(release.snapshot_traffic(publisher.state)), [(publisher.revision, 100)])
        self.assertEqual(release.tag_map(publisher.state)['hostfix'], 'fixed')
        deploy = next(x for x in publisher.cloud.commands if x[:2] == ('run', 'deploy'))
        self.assertIn('--no-traffic', deploy)
        self.assertTrue(any(x.endswith('@sha256:' + 'a' * 64) for x in deploy))

    def test_failed_candidate_never_receives_traffic(self):
        publisher = FakePublisher(fail_health=1)
        with self.assertRaises(release.ReleaseError):
            self.execute(publisher)
        self.assertEqual(positive(release.snapshot_traffic(publisher.state)), [('old', 100)])

    def test_post_publish_failure_restores_previous_traffic(self):
        publisher = FakePublisher(fail_health=2)
        with self.assertRaises(release.ReleaseError):
            self.execute(publisher)
        self.assertEqual(positive(release.snapshot_traffic(publisher.state)), [('old', 100)])
        self.assertEqual(release.tag_map(publisher.state)['hostfix'], 'fixed')

    def test_lost_promotion_response_is_also_rolled_back(self):
        publisher = FakePublisher(lost_response=True)
        with self.assertRaises(release.ReleaseError):
            self.execute(publisher)
        self.assertEqual(positive(release.snapshot_traffic(publisher.state)), [('old', 100)])

    def test_etag_conflict_never_overwrites_production(self):
        publisher = FakePublisher(conflict=True)
        with self.assertRaises(release.Conflict):
            self.execute(publisher)
        self.assertEqual(positive(release.snapshot_traffic(publisher.state)), [('old', 100)])

    def test_invalid_digests_never_deploy_a_candidate(self):
        for digest in ('', 'sha256:abc', 'sha256:' + 'g' * 64):
            publisher = FakePublisher()
            original = publisher.cloud.gcloud
            publisher.cloud.gcloud = lambda *args, **kwargs: digest if args[0] == 'artifacts' else original(*args, **kwargs)
            with self.subTest(digest=digest), self.assertRaises(release.ReleaseError):
                self.execute(publisher)
            self.assertFalse(any(x[:2] == ('run', 'deploy') for x in publisher.cloud.commands))

    def test_an_active_owner_cannot_be_stolen(self):
        publisher = FakePublisher()
        publisher.state['annotations'][release.OWNER] = '22222222-2222-4222-8222-222222222222'
        original = publisher.build
        publisher.build = lambda bid: {**original(bid), 'status': 'WORKING'}
        with self.assertRaises(release.ReleaseError):
            self.execute(publisher)
        self.assertEqual(publisher.state['annotations'][release.OWNER], '22222222-2222-4222-8222-222222222222')
        self.assertFalse(any(x[:2] == ('run', 'deploy') for x in publisher.cloud.commands))

    def test_cancelled_publish_is_recovered_before_the_next_deployment(self):
        publisher = FakePublisher()
        owner = '22222222-2222-4222-8222-222222222222'
        abandoned = publisher.service + '-c-' + owner.replace('-', '')
        previous = release.snapshot_traffic(publisher.state)
        publisher.state['annotations'] = {release.OWNER: owner, release.PENDING: json.dumps({
            'traffic': previous, 'candidate': abandoned})}
        publisher.state['trafficStatuses'][0]['revision'] = abandoned
        self.execute(publisher)
        self.assertIn([('old', 100)], publisher.allocations)
        self.assertNotIn(release.PENDING, publisher.state['annotations'])

    def test_older_rebuild_of_same_commit_does_not_replace_newer_build(self):
        publisher = FakePublisher()
        publisher.state['annotations'] = {release.COMMIT: publisher.commit, release.CREATED: '2026-11-05T01:00:00Z'}
        self.execute(publisher)
        self.assertFalse(any(x[:2] == ('run', 'deploy') for x in publisher.cloud.commands))

    def test_api_release_promotes_an_alpha_candidate_even_when_the_template_is_e2e(self):
        publisher = FakePublisher(component='api')
        set_env(publisher.state['template'], 'LIFEWORLD_DB_NAME', 'life_world_e2e')  # 本機 e2e 部署留下的範本
        publisher.state['template']['vpcAccess']['egress'] = 'ALL_TRAFFIC'
        self.execute(publisher)
        self.assertEqual(positive(release.snapshot_traffic(publisher.state)), [(publisher.revision, 100)])
        deploy = next(x for x in publisher.cloud.commands if x[:2] == ('run', 'deploy'))
        self.assertIn('--no-traffic', deploy)
        self.assertIn('--vpc-egress=private-ranges-only', deploy)
        self.assertEqual(env_item(publisher.cloud.candidate, 'LIFEWORLD_DB_NAME')['value'], 'life_world_alpha')

    def test_api_dev_production_is_refused_before_any_deploy(self):
        publisher = FakePublisher(component='api')
        set_env(publisher.production, 'LIFEWORLD_DB_NAME', 'life_world_dev')
        with self.assertRaises(ValueError):
            self.execute(publisher)
        self.assertFalse(any(x[:2] == ('run', 'deploy') for x in publisher.cloud.commands))
        self.assertEqual(positive(release.snapshot_traffic(publisher.state)), [('old', 100)])

    def test_api_candidate_with_a_different_runtime_never_receives_traffic(self):
        changed = {'resources': {'limits': {'cpu': '1000m', 'memory': '1Gi'}, 'cpuIdle': True, 'startupCpuBoost': True}}
        publisher = FakePublisher(component='api', candidate_changes=changed)
        with self.assertRaisesRegex(release.ReleaseError, 'Candidate changed API runtime configuration'):
            self.execute(publisher)
        self.assertEqual(positive(release.snapshot_traffic(publisher.state)), [('old', 100)])

    def test_lock_cas_conflict_is_re_read_instead_of_overwritten(self):
        publisher = FakePublisher()
        original = publisher.patch
        attempts = []

        def concurrent_write(current, **fields):
            if not attempts:
                attempts.append(True)
                publisher.state['etag'] = '1'
                raise release.Conflict('another build acquired this etag first')
            return original(current, **fields)

        publisher.patch = concurrent_write
        self.execute(publisher)
        self.assertEqual(positive(release.snapshot_traffic(publisher.state)), [(publisher.revision, 100)])


if __name__ == '__main__':
    unittest.main()
