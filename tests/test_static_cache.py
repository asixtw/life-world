"""部署後瀏覽器必須拿到新版前端（2026-11-11：Jerry 重啟網站後仍看不到新的「人物」頁）。

原因：/static/ 的 JS／CSS 沒有 Cache-Control，瀏覽器可自行沿用舊檔。修正：
1. /static/ 回應 Cache-Control: no-cache（每次向伺服器確認，未變更時 304）。
2. 首頁的 JS／CSS 網址附上依內容計算的版本（?v=…）；首頁本身 no-store，部署後網址改變，舊快取不會被使用。
"""
import re


def asset_urls(html):
    return re.findall(r'(?:src|href)="(/static/[^"]+\.(?:js|css)[^"]*)"', html)


def test_static_assets_must_be_revalidated(client):
    response = client.get('/static/app.js')
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-cache'
    assert response.headers.get('etag')


def test_index_versions_every_script_and_stylesheet(client):
    first = client.get('/')
    assert first.status_code == 200 and first.headers['cache-control'] == 'no-store'
    assert "script-src 'self'" in first.headers['content-security-policy']
    urls = asset_urls(first.text)
    assert urls and all(re.search(r'\?v=[0-9a-f]{12}$', url) for url in urls), urls
    assert any(url.startswith('/static/persons.js?v=') for url in urls) and any(url.startswith('/static/app.js?v=') for url in urls)
    assert asset_urls(client.get('/').text) == urls  # 同一版本內穩定
    versioned = client.get(urls[0])
    assert versioned.status_code == 200 and versioned.headers['cache-control'] == 'no-cache'
