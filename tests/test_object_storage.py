"""作品檔案的物件儲存（app/object_storage.py）：Cloud Storage 的呼叫方式與環境隔離。

不連網：GcsStorage 以假的傳輸函式驗證送出的網址、標頭與條件；MemoryStorage 是其他自動測試使用的替身。
規則：
- 只新增、不覆寫：寫入一律帶 ifGenerationMatch=0（不存在才建立）；物件已存在（HTTP 412）視為已寫入。
- bucket 屬於環境：環境白名單登記每個環境唯一能用的 bucket，設定不一致就不啟用。
"""
from urllib.error import HTTPError

import pytest

from app.object_storage import GcsStorage, MemoryStorage, StorageError, build_storage

E2E_BUCKET = 'lw-works-e2e-513506'


class Transport:
    """記錄每一次呼叫，並依序回傳預先安排的結果（bytes 或要拋出的例外）。"""

    def __init__(self, *results):
        self.calls, self.results = [], list(results)

    def __call__(self, method, url, body, headers):
        self.calls.append({'method': method, 'url': url, 'body': body, 'headers': dict(headers)})
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def http_error(code):
    return HTTPError('https://storage.googleapis.com/', code, 'error', {}, None)


def gcs(*results):
    transport = Transport(*results)
    return GcsStorage(E2E_BUCKET, environment_id='e2e', token_supplier=lambda: 'token-123', transport=transport), transport


def test_put_new_creates_only_when_the_object_does_not_exist():
    storage, transport = gcs(b'{}', http_error(412))
    assert storage.put_new('works/o1/w1/abc.html', b'<html>', 'text/html; charset=utf-8') is True
    call = transport.calls[0]
    assert call['method'] == 'POST'
    assert call['url'] == ('https://storage.googleapis.com/upload/storage/v1/b/lw-works-e2e-513506/o'
                           '?uploadType=media&name=works%2Fo1%2Fw1%2Fabc.html&ifGenerationMatch=0')
    assert call['body'] == b'<html>'
    assert call['headers'] == {'Authorization': 'Bearer token-123', 'Content-Type': 'text/html; charset=utf-8'}
    assert storage.put_new('works/o1/w1/abc.html', b'<html>', 'text/html; charset=utf-8') is False, '已存在（412）視為已寫入，不覆寫'


def test_get_returns_bytes_or_none_when_missing():
    storage, transport = gcs(b'<html>saved</html>', http_error(404))
    assert storage.get('works/o1/w1/abc.html') == b'<html>saved</html>'
    call = transport.calls[0]
    assert call['method'] == 'GET' and call['body'] is None
    assert call['url'] == 'https://storage.googleapis.com/storage/v1/b/lw-works-e2e-513506/o/works%2Fo1%2Fw1%2Fabc.html?alt=media'
    assert call['headers'] == {'Authorization': 'Bearer token-123'}
    assert storage.get('works/o1/w1/abc.html') is None


def test_other_failures_raise_without_leaking_details():
    storage, _ = gcs(http_error(403), OSError('network down'), http_error(500))
    with pytest.raises(StorageError) as denied:
        storage.put_new('works/o1/w1/abc.html', b'x', 'text/html')
    assert 'token-123' not in str(denied.value)
    with pytest.raises(StorageError):
        storage.put_new('works/o1/w1/abc.html', b'x', 'text/html')
    with pytest.raises(StorageError):
        storage.get('works/o1/w1/abc.html')


@pytest.mark.parametrize('name', ['', '/abs/path', 'a/../b', 'a//b', 'has space.html', 'x' * 600, 'works/o1/w1/檔.html'])
def test_object_names_are_restricted(name):
    storage, transport = gcs()
    with pytest.raises(ValueError):
        storage.put_new(name, b'x', 'text/html')
    with pytest.raises(ValueError):
        storage.get(name)
    assert transport.calls == []


def test_bucket_must_be_the_one_registered_for_the_environment():
    with pytest.raises(ValueError):
        GcsStorage('some-other-bucket', environment_id='e2e')
    with pytest.raises(ValueError):
        GcsStorage(E2E_BUCKET, environment_id='alpha')  # Alpha 還沒有登記 bucket
    with pytest.raises(ValueError):
        GcsStorage(E2E_BUCKET, environment_id='local-test')

    assert build_storage({}) is None, '沒有設定就不啟用'
    assert build_storage({'LIFEWORLD_WORKS_BUCKET': E2E_BUCKET}) is None, '沒有環境代號不啟用'
    assert build_storage({'LIFEWORLD_WORKS_BUCKET': 'some-other-bucket', 'LIFEWORLD_ENVIRONMENT_ID': 'e2e'}) is None
    assert build_storage({'LIFEWORLD_WORKS_BUCKET': E2E_BUCKET, 'LIFEWORLD_ENVIRONMENT_ID': 'alpha'}) is None
    ready = build_storage({'LIFEWORLD_WORKS_BUCKET': E2E_BUCKET, 'LIFEWORLD_ENVIRONMENT_ID': 'e2e'})
    assert isinstance(ready, GcsStorage) and ready.bucket == E2E_BUCKET and ready.kind == 'gcs'


def test_memory_storage_behaves_like_the_real_one():
    storage = MemoryStorage()
    assert storage.put_new('works/o1/w1/abc.html', b'one', 'text/html') is True
    assert storage.put_new('works/o1/w1/abc.html', b'two', 'text/html') is False
    assert storage.get('works/o1/w1/abc.html') == b'one', '不覆寫'
    assert storage.get('works/o1/w1/missing.html') is None
    with pytest.raises(ValueError):
        storage.put_new('a/../b', b'x', 'text/html')
