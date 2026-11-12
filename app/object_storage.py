"""作品檔案的物件儲存：Cloud Storage（JSON API，直接走 HTTPS）與自動測試用的記憶體版本。

資料庫放作品的結構與檔案清單；這裡只放檔案本體（匯出的 HTML，之後的圖片素材）。

設計原則：
- 只新增、不覆寫：寫入一律帶「不存在才建立」的條件（ifGenerationMatch=0）。物件名稱由內容雜湊決定，
  所以同名物件已存在時內容必然相同，視為已寫入。執行身分在 bucket 上也只有新增與讀取的權限，沒有刪除。
- bucket 屬於環境：環境白名單（environment.ENVIRONMENTS）登記每個環境唯一能用的 bucket，
  設定不一致就不啟用；和資料庫、排程佇列的隔離方式相同。
- 不引入新的套件：和 Cloud Tasks 一樣，用 Cloud Run 執行身分的 Access Token 直接呼叫 REST API。
- 錯誤訊息與診斷紀錄不含 Token、物件內容或回應本文。
"""
import json  # Token 回應
import os  # 讀取 bucket 設定（非秘密）
import re  # 驗證物件名稱，避免拼入任意路徑
import threading  # Token 快取
import time  # Token 到期判斷
from urllib.error import HTTPError, URLError  # 辨識不存在、已存在與傳輸錯誤
from urllib.parse import quote  # 物件名稱放進網址
from urllib.request import Request, urlopen  # 單次 HTTPS 呼叫

from .environment import ENVIRONMENTS, emit_diagnostic  # 環境白名單與結構化診斷

METADATA_TOKEN_URL = 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token'
API = 'https://storage.googleapis.com'
NAME_PATTERN = r'[A-Za-z0-9][A-Za-z0-9._\-]*(/[A-Za-z0-9][A-Za-z0-9._\-]*)*'  # 以 / 分段；每段不能是空的，也不能以 . 開頭（擋掉 ..）
MAX_NAME, MAX_OBJECT_BYTES = 512, 32 * 1024 * 1024  # 單一檔案上限 32 MiB：超過就不該整個讀進記憶體


class StorageError(Exception):
    """儲存服務失敗；只帶固定的原因代碼，不含 Token、物件內容或回應本文。"""


def check_name(name):
    """物件名稱只接受安全的 ASCII 路徑；不合格就拒絕，不嘗試修正。"""
    if not isinstance(name, str) or len(name) > MAX_NAME or not re.fullmatch(NAME_PATTERN, name):
        raise ValueError('invalid object name')
    return name


class MemoryStorage:
    """自動測試用：行為和 GcsStorage 相同（只新增、不覆寫），內容放在記憶體。"""
    kind, bucket = 'memory', 'memory'

    def __init__(self):
        self.objects, self.content_types, self.writes = {}, {}, 0  # writes：實際寫入的次數（已存在而略過的不算）

    def put_new(self, name, data, content_type):
        check_name(name)
        if name in self.objects:
            return False
        self.objects[name], self.content_types[name] = bytes(data), content_type
        self.writes += 1
        return True

    def get(self, name):
        return self.objects.get(check_name(name))


class GcsStorage:
    """Cloud Storage JSON API。put_new 回傳 True（新建立）或 False（已存在）；get 回傳內容或 None（不存在）。"""
    kind = 'gcs'

    def __init__(self, bucket, *, environment_id, token_supplier=None, transport=None):
        expected = ENVIRONMENTS.get(environment_id, {}).get('works_bucket')
        if not expected or expected == 'memory' or bucket != expected:
            raise ValueError('Bucket does not belong to this environment')  # 不得把 E2E 的檔案寫進別的環境的 bucket，反之亦然
        self.bucket, self.environment_id = bucket, environment_id
        self._token_supplier = token_supplier or self._metadata_token
        self._transport = transport or self._call
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
    def _call(method, url, body, headers):
        request = Request(url, data=body, headers=headers, method=method)
        with urlopen(request, timeout=30) as response:
            data = response.read(MAX_OBJECT_BYTES + 1)
        if len(data) > MAX_OBJECT_BYTES:
            raise ValueError('object too large')
        return data

    def _request(self, method, url, body, headers):
        """統一的錯誤處理：呼叫端自己判斷 404／412，其餘一律轉成不含細節的 StorageError。"""
        try:
            return self._transport(method, url, body, {'Authorization': 'Bearer ' + self._token_supplier(), **headers})
        except HTTPError:
            raise
        except (URLError, OSError, ValueError, KeyError) as exc:
            raise StorageError(type(exc).__name__) from None

    def put_new(self, name, data, content_type):
        url = f'{API}/upload/storage/v1/b/{self.bucket}/o?uploadType=media&name={quote(check_name(name), safe="")}&ifGenerationMatch=0'
        try:
            self._request('POST', url, bytes(data), {'Content-Type': content_type})
            return True
        except HTTPError as exc:
            if exc.code == 412:
                return False  # 已存在：名稱由內容雜湊決定，內容相同，不需要也不能覆寫
            raise StorageError(f'storage http {exc.code}') from None

    def get(self, name):
        url = f'{API}/storage/v1/b/{self.bucket}/o/{quote(check_name(name), safe="")}?alt=media'
        try:
            return self._request('GET', url, None, {})
        except HTTPError as exc:
            if exc.code == 404:
                return None
            raise StorageError(f'storage http {exc.code}') from None


def build_storage(environ=None):
    """依環境變數建立作品檔案的儲存；沒有設定就回 None（匯出功能不開放）。

    LIFEWORLD_WORKS_BUCKET 必須等於環境白名單登記的 bucket，否則不啟用並留下診斷紀錄（不含 Secret）。
    """
    env = os.environ if environ is None else environ
    bucket = env.get('LIFEWORLD_WORKS_BUCKET', '').strip()
    if not bucket:
        return None
    environment_id = env.get('LIFEWORLD_ENVIRONMENT_ID', '').strip()
    try:
        return GcsStorage(bucket, environment_id=environment_id)
    except ValueError:
        emit_diagnostic({'severity': 'ERROR', 'message': 'lw_work_storage_rejected', 'reason': 'bucket_mismatch',
                         'environment_id': environment_id, 'bucket': bucket, 'service_revision': env.get('K_REVISION')})
        return None
