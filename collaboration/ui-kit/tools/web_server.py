"""Web 同來源唯讀 gateway；Google 身分只留在伺服器端。"""
import asyncio
import base64
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response

API_ORIGIN = 'https://lw-api-main-u5py2jttpa-de.a.run.app'
WEB_HOSTS = ('lw-web-main-u5py2jttpa-de.a.run.app', 'lw-web-main-162310640466.asia-east1.run.app')
METADATA_IDENTITY = 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity'
MAX_RESPONSE = 8 * 1024 * 1024
IDENTIFIER = r'[A-Za-z0-9_-]+'
READ_PATH = re.compile(r'/api/(?:health|capabilities|auth/me|state|media/capabilities|people|connections'
    r'|goals/' + IDENTIFIER + r'(?:/(?:dashboard|calendar))?|drafts/' + IDENTIFIER
    + r'|people/' + IDENTIFIER + r'/(?:overview|interactions|facts/' + IDENTIFIER + r'/evidence)'
    + r'|connections/stories/' + IDENTIFIER + r'|evidence/' + IDENTIFIER + r')')
RESPONSE_HEADERS = ('content-type', 'content-security-policy', 'x-content-type-options',
                    'referrer-policy', 'x-frame-options', 'retry-after', 'content-disposition')


def failure(status, code, message):
    return JSONResponse({'error': {'code': code, 'message': message}}, status_code=status,
                        headers={'Cache-Control': 'no-store'})


class MetadataIdentity:
    """使用既有 runtime SA 的 metadata ID token；不讀 key／環境 token，不作瀏覽器身分。"""
    def __init__(self, transport=None, clock=time.time):
        self.transport, self.clock = transport, clock
        self.lock, self.token, self.until = asyncio.Lock(), '', 0

    async def __call__(self):
        async with self.lock:
            if self.token and self.clock() < self.until:
                return self.token
            async with httpx.AsyncClient(transport=self.transport, timeout=3, trust_env=False,
                                         follow_redirects=False) as client:
                response = await client.get(METADATA_IDENTITY, headers={'Metadata-Flavor': 'Google'},
                                            params={'audience': API_ORIGIN, 'format': 'full'})
                response.raise_for_status()
            token = response.text.strip()
            if len(token) > 16384 or '\r' in token or '\n' in token:
                raise ValueError('Invalid metadata identity')
            parts = token.split('.')
            if len(parts) != 3:
                raise ValueError('Invalid metadata identity')
            claims = json.loads(base64.urlsafe_b64decode(parts[1] + '=' * (-len(parts[1]) % 4)))
            expires = claims.get('exp', 0)
            # 只利用 metadata 回傳的期限作快取；真正 JWT 簽章／IAM 檢查仍由 Cloud Run 執行。
            if claims.get('aud') != API_ORIGIN or not isinstance(expires, (int, float)) or expires <= self.clock() + 60:
                raise ValueError('Invalid metadata audience or expiry')
            self.token, self.until = token, min(self.clock() + 300, expires - 60)
            return token


def create_app(api_origin=None, token_provider=None, upstream_transport=None, gallery_dir=None):
    """保留 gallery 根目錄；/app/ 取真正 API HTML，/api 與 /static 固定轉送同一 API。

    預設未配置 upstream 即封鎖，部署不會暗中替服務增加業務入口或資料庫權限。
    transport／provider 僅由測試注入；環境不能指定任意 URL、Tag 或 Google 憑證。
    """
    origin = os.environ.get('LIFEWORLD_WEB_API_ORIGIN', '') if api_origin is None else api_origin
    if origin not in ('', API_ORIGIN):
        raise ValueError('Only the approved canonical API origin is allowed')
    identity = token_provider or MetadataIdentity()
    gallery = Path(gallery_dir or os.environ.get('LIFEWORLD_WEB_GALLERY_DIR', '/srv/gallery')).resolve()
    cloud = bool(os.environ.get('K_SERVICE'))
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def boundaries(request, call_next):
        try:
            authority = urlsplit('//' + request.headers.get('host', ''))
            host = authority.hostname
            allowed = host in WEB_HOSTS or any(re.fullmatch(r'c-[0-9a-f]{32}---' + re.escape(h), host or '') for h in WEB_HOSTS)
            allowed = allowed or (not cloud and host in ('localhost', '127.0.0.1', 'testserver'))
            allowed = allowed or (request.url.path == '/health' and host in ('localhost', '127.0.0.1'))
            if not allowed or authority.username or authority.password or authority.path or authority.query or authority.fragment:
                raise ValueError('Invalid Host')
            authority.port  # 拒絕格式錯誤的 port；不信任瀏覽器提供的 Forwarded Host。
        except ValueError:
            return failure(400, 'invalid_host', '無效的網站主機。')
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        if cloud:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    async def forward(request, target):
        if not origin:
            return failure(503, 'api_not_configured', '業務服務尚未啟用。')
        expected_origin = ('https' if cloud else request.url.scheme) + '://' + request.headers['host']
        if request.headers.get('origin', expected_origin) != expected_origin or request.headers.get('sec-fetch-site') == 'cross-site':
            return failure(403, 'origin_rejected', '不允許跨來源存取。')
        if request.headers.get('content-length', '0') != '0' or request.headers.get('transfer-encoding'):
            return failure(400, 'invalid_read_request', '唯讀請求不可包含本文。')
        try:
            token = await asyncio.wait_for(identity(), timeout=5)
            if not isinstance(token, str) or not token or '\r' in token or '\n' in token:
                raise ValueError('Invalid server identity')
        except Exception:
            return failure(503, 'api_identity_unavailable', '業務服務身分驗證尚未就緒。')

        headers = {k: request.headers[k] for k in ('cookie', 'origin', 'x-csrf-token', 'accept') if k in request.headers}
        # 絕不轉送瀏覽器的 Google 身分或偽造代理鏈；Host 由固定 upstream URL 決定。
        headers['X-Serverless-Authorization'] = 'Bearer ' + token
        query = request.scope.get('query_string', b'')
        if len(query) > 8192:
            return failure(400, 'invalid_query', '查詢參數過長。')
        url = httpx.URL(origin).copy_with(raw_path=target.encode('ascii') + (b'?' + query if query else b''))

        async def exchange():
            # 每個請求獨立 client，避免上游 Set-Cookie 的 cookie jar 混入其他使用者。
            async with httpx.AsyncClient(transport=upstream_transport, timeout=10, trust_env=False,
                                         follow_redirects=False) as client:
                async with client.stream(request.method, url, headers=headers) as upstream:
                    if 300 <= upstream.status_code < 400:
                        raise ValueError('Upstream redirect refused')
                    chunks, size = [], 0
                    async for chunk in upstream.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_RESPONSE:
                            raise ValueError('Upstream response too large')
                        chunks.append(chunk)
                    body = b''.join(chunks)
                    if token.encode() in body:
                        raise ValueError('Identity must not be returned')
                    if upstream.status_code in (401, 403) and 'application/json' not in upstream.headers.get('content-type', ''):
                        raise ValueError('Cloud Run authentication failed')
                    if target == '/api/capabilities' and upstream.status_code == 200 and request.method == 'GET':
                        capabilities = json.loads(body)
                        capabilities.update(read_only=True, writes_available=False, accounts_available=False,
                                            registration_available=False, media_available=False)
                        body = json.dumps(capabilities).encode()
                    response = Response(body if request.method != 'HEAD' else b'', status_code=upstream.status_code,
                                        headers={k: upstream.headers[k] for k in RESPONSE_HEADERS if k in upstream.headers})
                    response.headers['Cache-Control'] = 'no-store'
                    for cookie in upstream.headers.get_list('set-cookie'):
                        response.raw_headers.append((b'set-cookie', cookie.encode('latin-1')))
                    return response
        try:
            return await asyncio.wait_for(exchange(), timeout=20)
        except Exception:
            # 不回傳 exception／upstream 原文；其中可能有權杖、內部 URL 或私人內容。
            return failure(502, 'api_unavailable', '業務服務暫時不可用，請稍後再試。')

    @app.api_route('/{path:path}', methods=['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
    async def route(request: Request, path: str):
        if request.method not in ('GET', 'HEAD'):
            return failure(403, 'read_only', '目前僅開放資料回讀，登入與資料寫入尚未啟用。')
        raw = request.scope.get('raw_path', b'')
        if b'%' in raw or '//' in path or any(part.startswith('.') for part in path.split('/')):
            return Response(status_code=404)
        if path == 'health':
            if origin:
                # 啟用串接後，候選的健康檢查也必須驗證 runtime SA 真能讀 API。
                # capabilities 不執行業務 DML；失敗則既有發布器保留／回復舊流量。
                probe = await forward(request, '/api/capabilities')
                if probe.status_code != 200:
                    return failure(503, 'api_unavailable', '業務服務尚未就緒。')
            return PlainTextResponse('ok\n')
        if path == 'app':
            return RedirectResponse('/app/')
        if path == 'app/':
            return await forward(request, '/')
        if READ_PATH.fullmatch('/' + path) or re.fullmatch(r'static/[A-Za-z0-9_-]+\.(?:js|css)', path):
            return await forward(request, '/' + path)
        if path == 'api' or path.startswith(('api/', 'static/', 'app/')):
            return Response(status_code=404)
        if Path(path).suffix.lower() == '.map':
            return Response(status_code=404)
        file = (gallery / path).resolve()
        if gallery not in file.parents and file != gallery:
            return Response(status_code=404)
        if not file.is_file():
            if Path(path).suffix:
                return Response(status_code=404)
            file = gallery / 'index.html'
        if not file.is_file():
            return Response(status_code=404)
        return FileResponse(file, headers={'Cache-Control': 'no-store' if file.name == 'index.html' else 'public, max-age=3600'})

    return app


if __name__ == '__main__':
    import uvicorn
    # 不信任瀏覽器提供的代理鏈；Cloud Run HTTPS 的外部 Origin 用固定規則驗證。
    uvicorn.run('web_server:create_app', factory=True, host='0.0.0.0', port=int(os.environ.get('PORT', '8080')),
                proxy_headers=False, access_log=False)
