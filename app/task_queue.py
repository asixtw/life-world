# 2026-11-10 自 8445（life-world-react-integrated/app/task_queue.py）原樣移植。
"""P1 排程式生成的佇列：雲端用 Cloud Tasks，自動測試用記憶體內的假佇列。

一個 Task 只處理一段（規劃或一段演出）。Task 名稱由呼叫端決定（作品＋段號＋嘗試序號），
同名 Task 只會被接受一次，所以重送或重複排入不會讓同一段被執行兩次；Worker 本身也是冪等的。

環境隔離（app/environment.py）：
- 每個佇列屬於一個環境（e2e／alpha），Queue 名稱、Worker 網址與期望的資料庫都由白名單決定。
- 設定與白名單不一致時不建立佇列（排程生成不啟用），並留下錯誤診斷紀錄。

雲端版不新增套件：
- 以 Cloud Run 的 metadata server 取得執行身分（lw-api-runtime）的 Access Token，呼叫 Cloud Tasks REST v2。
- Task 以 OIDC 身分呼叫內部 Worker，由 Cloud Run IAM 驗證呼叫者。
- 不輸出 Token、Task 內容或回應本文。
"""
import base64  # Cloud Tasks 的 HTTP body 必須是 base64
from datetime import datetime, timedelta, timezone  # 延後執行的排程時間
import json  # Task 內容
import os  # 讀取佇列設定（非秘密）
import re  # 驗證設定格式，避免拼入任意 URL
import threading  # Token 快取
import time  # Token 到期判斷
from urllib.error import HTTPError, URLError  # 辨識已存在的 Task 與傳輸錯誤
from urllib.parse import urlsplit  # 核對 Worker 主機
from urllib.request import Request, urlopen  # 單次 HTTPS 呼叫

from .environment import BASE, ENVIRONMENTS, emit_diagnostic, expected_for  # 環境白名單

METADATA_TOKEN_URL = 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token'
QUEUE_PATTERN = r'projects/[a-z][a-z0-9\-]{4,61}[a-z0-9]/locations/[a-z0-9\-]+/queues/[A-Za-z0-9\-]{1,100}'
NAME_PATTERN = r'[A-Za-z0-9_\-]{1,500}'


class QueueError(Exception):
    """排入失敗（不含 Token 或回應本文）；呼叫端回 503，讓 Cloud Tasks 或使用者稍後重試。"""


class InMemoryQueue:
    """自動測試用：記錄排入的 Task，由測試依序送到內部 Worker；同名 Task 只接受一次。"""
    kind = 'memory'

    def __init__(self, environment_id='local-test', expected_database=None):
        self.environment_id = environment_id
        self.queue_name = ENVIRONMENTS[environment_id]['queue']
        self.expected = expected_for(environment_id, database=expected_database)
        self.tasks, self._names = [], set()

    def enqueue(self, name, payload, delay_seconds=0):
        if not re.fullmatch(NAME_PATTERN, name):
            raise QueueError('invalid task name')
        if name in self._names:
            return False  # 與 Cloud Tasks 的 ALREADY_EXISTS 相同：已排入過就不再排
        self._names.add(name)
        self.tasks.append({'name': name, 'payload': dict(payload), 'delay_seconds': int(delay_seconds)})
        return True

    def pop(self):
        return self.tasks.pop(0) if self.tasks else None


class CloudTasksQueue:
    """Cloud Tasks REST v2；HTTP 409（同名 Task 已存在）視為已排入。Queue 必須是該環境的 Queue。"""
    kind = 'cloud_tasks'

    def __init__(self, queue_path, worker_url, service_account, audience, *, environment_id, token_supplier=None, transport=None,
                 expected_database=None, expected_schema=None, expected_marker=BASE):
        if environment_id not in ENVIRONMENTS or ENVIRONMENTS[environment_id]['queue'] == 'memory':
            raise ValueError('Unknown cloud environment')
        if not re.fullmatch(QUEUE_PATTERN, queue_path):
            raise ValueError('Invalid Cloud Tasks queue path')
        if queue_path.rsplit('/', 1)[1] != ENVIRONMENTS[environment_id]['queue']:
            raise ValueError('Queue belongs to another environment')  # 不得把 E2E Task 排入 Alpha Queue，反之亦然
        if not re.fullmatch(r'https://[a-z0-9.\-]+\.run\.app/internal/roleplay/tasks', worker_url):
            raise ValueError('Invalid worker URL')
        prefix = ENVIRONMENTS[environment_id]['worker_host_prefix']
        if prefix and not urlsplit(worker_url).hostname.startswith(prefix):
            raise ValueError('Worker URL belongs to another environment')
        if not re.fullmatch(r'[a-z0-9\-]+@[a-z0-9\-]+\.iam\.gserviceaccount\.com', service_account):
            raise ValueError('Invalid invoker service account')
        if not re.fullmatch(r'https://[a-z0-9.\-]+\.run\.app(/[A-Za-z0-9/_\-]*)?', audience):
            raise ValueError('Invalid OIDC audience')
        self.environment_id = environment_id
        self.expected = expected_for(environment_id, database=expected_database, schema=expected_schema, marker=expected_marker)
        self.queue_path, self.worker_url, self.service_account, self.audience = queue_path, worker_url, service_account, audience
        self.queue_name = queue_path.rsplit('/', 1)[1]  # Worker 用來核對 X-CloudTasks-QueueName
        self._token_supplier = token_supplier or self._metadata_token
        self._transport = transport or self._post
        self._lock, self._token, self._expires = threading.Lock(), None, 0.0

    def _metadata_token(self):
        """Cloud Run 執行身分的 Access Token；快取到到期前 60 秒。"""
        with self._lock:
            if self._token and time.monotonic() < self._expires - 60:
                return self._token
            request = Request(METADATA_TOKEN_URL, headers={'Metadata-Flavor': 'Google'})
            with urlopen(request, timeout=5) as response:
                data = json.loads(response.read(16384))
            self._token, self._expires = data['access_token'], time.monotonic() + int(data.get('expires_in', 300))
            return self._token

    @staticmethod
    def _post(url, body, headers):
        request = Request(url, data=body, headers=headers, method='POST')
        with urlopen(request, timeout=10) as response:
            response.read(65536)
            return response.status

    def enqueue(self, name, payload, delay_seconds=0):
        if not re.fullmatch(NAME_PATTERN, name):
            raise QueueError('invalid task name')
        task = {'name': f'{self.queue_path}/tasks/{name}', 'dispatchDeadline': '300s',
                'httpRequest': {'httpMethod': 'POST', 'url': self.worker_url, 'headers': {'Content-Type': 'application/json'},
                                'body': base64.b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode(),
                                'oidcToken': {'serviceAccountEmail': self.service_account, 'audience': self.audience}}}
        if delay_seconds > 0:
            when = datetime.now(timezone.utc) + timedelta(seconds=int(delay_seconds))
            task['scheduleTime'] = when.strftime('%Y-%m-%dT%H:%M:%SZ')
        try:
            token = self._token_supplier()
            self._transport(f'https://cloudtasks.googleapis.com/v2/{self.queue_path}/tasks', json.dumps({'task': task}).encode(),
                            {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
            return True
        except HTTPError as exc:
            if exc.code == 409:
                return False  # ALREADY_EXISTS：同一段的同一次嘗試已排入
            raise QueueError(f'cloud tasks http {exc.code}') from None
        except (URLError, OSError, ValueError, KeyError) as exc:
            raise QueueError(type(exc).__name__) from None


def _reject(reason, env, environment_id):
    """設定與環境白名單不一致：不啟用排程生成，留下錯誤診斷（不含 Secret）。"""
    emit_diagnostic({'severity': 'ERROR', 'message': 'lw_roleplay_environment_rejected', 'reason': reason,
                     'environment_id': environment_id, 'database_name': env.get('LIFEWORLD_DB_NAME'),
                     'database_schema': env.get('LIFEWORLD_DB_SCHEMA'), 'queue': env.get('LIFEWORLD_TASKS_QUEUE'),
                     'service_revision': env.get('K_REVISION')})
    return None


def build_task_queue(environ=None):
    """依環境變數建立佇列；沒有佇列設定就回 None（正式 100% Revision 沒有這些設定，排程生成維持關閉）。

    有佇列設定時，環境代號、資料庫後端、資料庫名稱、Schema、Queue 與 Worker 網址都必須符合白名單，否則不啟用。
    """
    env = os.environ if environ is None else environ
    queue_path = env.get('LIFEWORLD_TASKS_QUEUE', '').strip()
    if not queue_path:
        return None
    environment_id = env.get('LIFEWORLD_ENVIRONMENT_ID', '').strip()
    expected = ENVIRONMENTS.get(environment_id)
    if expected is None or expected['queue'] == 'memory':
        return _reject('unknown_environment', env, environment_id)
    if env.get('LIFEWORLD_DB_BACKEND', 'sqlite') != expected['backend']:
        return _reject('backend_mismatch', env, environment_id)
    if env.get('LIFEWORLD_DB_NAME', '') != expected['database']:
        return _reject('database_mismatch', env, environment_id)
    if expected['schema'] is not None and env.get('LIFEWORLD_DB_SCHEMA', 'lw_core_draft') != expected['schema']:
        return _reject('schema_mismatch', env, environment_id)
    worker_url = env.get('LIFEWORLD_TASKS_WORKER_URL', '').strip()
    audience = env.get('LIFEWORLD_TASKS_AUDIENCE', '').strip() or worker_url.split('/internal/', 1)[0]
    try:
        return CloudTasksQueue(queue_path, worker_url, env.get('LIFEWORLD_TASKS_INVOKER_SA', '').strip(), audience,
                               environment_id=environment_id)
    except ValueError as exc:
        return _reject(str(exc), env, environment_id)
