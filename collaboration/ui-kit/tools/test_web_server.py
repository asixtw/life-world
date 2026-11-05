"""合成 upstream／metadata，不呼叫 GCP、不建立或讀取真實帳號。"""
import base64
import json
from pathlib import Path
import tempfile
import unittest

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from web_server import API_ORIGIN, MetadataIdentity, create_app


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.gallery = Path(self.directory.name)
        (self.gallery / 'index.html').write_text('<h1>React gallery</h1>', encoding='utf-8')
        self.calls, self.tokens = [], 0
        self.upstream = FastAPI()

        @self.upstream.api_route('/{path:path}', methods=['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH'])
        async def backend(request: Request, path: str):
            self.calls.append(request)
            if path == '':
                return HTMLResponse('<h1>Business UI</h1><script src="/static/app.js"></script>',
                                    headers={'Content-Security-Policy': "default-src 'self'"})
            if path == 'api/capabilities':
                return {'writes_available': True, 'accounts_available': True, 'registration_available': True}
            if request.query_params.get('redirect'):
                return RedirectResponse('https://untrusted.invalid/')
            if request.query_params.get('reflect'):
                return Response('private-google-identity')
            if request.query_params.get('large'):
                return Response(b'x' * (8 * 1024 * 1024 + 1))
            response = JSONResponse({'cookie': request.headers.get('cookie', ''), 'path': path})
            response.headers['X-Serverless-Authorization'] = 'must-not-leak'
            response.set_cookie('lw_session', 'test-session', secure=True, httponly=True, samesite='strict')
            return response

        async def identity():
            self.tokens += 1
            return 'private-google-identity'

        self.app = create_app(api_origin=API_ORIGIN, token_provider=identity,
                              upstream_transport=httpx.ASGITransport(app=self.upstream), gallery_dir=self.gallery)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='https://testserver')

    async def asyncTearDown(self):
        await self.client.aclose()
        self.directory.cleanup()

    async def test_original_gallery_and_health_survive_without_backend_configuration(self):
        app = create_app(api_origin='', gallery_dir=self.gallery)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://testserver') as client:
            self.assertIn('React gallery', (await client.get('/')).text)
            self.assertEqual((await client.get('/health')).text.strip(), 'ok')
            self.assertEqual((await client.get('/api/auth/me')).status_code, 503)
            for path in ('/missing.js', '/.env', '/private.map'):
                self.assertEqual((await client.get(path)).status_code, 404)

    async def test_real_business_ui_is_separate_from_react_gallery(self):
        response = await self.client.get('/app/')
        self.assertIn('Business UI', response.text)
        self.assertEqual(response.headers['content-security-policy'], "default-src 'self'")
        self.assertEqual(self.calls[-1].url.path, '/')
        self.assertIn('React gallery', (await self.client.get('/')).text)

    async def test_enabled_gateway_health_fails_closed_when_iam_is_unavailable(self):
        async def missing_identity():
            raise RuntimeError('unavailable')
        app = create_app(api_origin=API_ORIGIN, token_provider=missing_identity, gallery_dir=self.gallery)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://testserver') as client:
            self.assertEqual((await client.get('/health')).status_code, 503)
        self.assertEqual((await self.client.get('/health')).status_code, 200)

    async def test_existing_source_maps_are_not_published(self):
        (self.gallery / 'private.map').write_text('private source', encoding='utf-8')
        self.assertEqual((await self.client.get('/private.map')).status_code, 404)

    async def test_cookies_csrf_and_origin_survive_but_browser_identity_does_not(self):
        response = await self.client.get('/api/state?limit=2', headers={
            'Cookie': 'lw_session=owner-session', 'Origin': 'https://testserver', 'X-CSRF-Token': 'original-csrf',
            'Authorization': 'Bearer browser-token', 'X-Serverless-Authorization': 'Bearer browser-token',
            'X-Forwarded-Host': 'attacker.invalid', 'X-Forwarded-For': '1.2.3.4'})
        sent = self.calls[-1]
        self.assertEqual(sent.headers['x-serverless-authorization'], 'Bearer private-google-identity')
        self.assertNotIn('authorization', sent.headers)
        self.assertNotIn('x-forwarded-for', sent.headers)
        self.assertEqual(sent.headers['cookie'], 'lw_session=owner-session')
        self.assertEqual(sent.headers['origin'], 'https://testserver')
        self.assertEqual(sent.headers['x-csrf-token'], 'original-csrf')
        self.assertEqual(str(sent.url), API_ORIGIN + '/api/state?limit=2')
        self.assertNotIn('x-serverless-authorization', response.headers)
        self.assertNotIn('private-google-identity', response.text)
        cookie = response.headers['set-cookie'].lower()
        self.assertTrue(all(x in cookie for x in ('secure', 'httponly', 'samesite=strict')))
        self.assertEqual(response.headers['cache-control'], 'no-store')

    async def test_upstream_cookie_jar_cannot_cross_browser_sessions(self):
        await self.client.get('/api/state', headers={'Cookie': 'lw_session=owner-a'})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='https://testserver') as other:
            response = await other.get('/api/state')
        self.assertEqual(response.json()['cookie'], '')

    async def test_every_write_is_blocked_even_with_valid_csrf(self):
        for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            response = await self.client.request(method, '/api/auth/login', headers={
                'Origin': 'https://testserver', 'X-CSRF-Token': 'valid'}, json={'example': 'synthetic'})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['error']['code'], 'read_only')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.tokens, 0)

    async def test_foreign_origin_and_fetch_site_are_rejected_before_minting_identity(self):
        for headers in ({'Origin': 'https://attacker.invalid'}, {'Sec-Fetch-Site': 'cross-site'}):
            response = await self.client.get('/api/state', headers=headers)
            self.assertEqual(response.status_code, 403)
        self.assertEqual(self.tokens, 0)

    async def test_upstream_targets_are_fixed_and_routes_are_allowlisted(self):
        for path in ('/api/ready', '/api/admin/reset', '/api/%2e%2e/health', '/api//evil.invalid', '/static/.env'):
            self.assertEqual((await self.client.get(path)).status_code, 404, path)
        self.assertEqual(self.tokens, 0)
        for origin in ('http://localhost', 'https://evil.invalid', API_ORIGIN + '/path', 'https://hostfix---' + API_ORIGIN[8:]):
            with self.assertRaises(ValueError):
                create_app(api_origin=origin, gallery_dir=self.gallery)

    async def test_no_redirect_token_echo_or_unbounded_response(self):
        for query in ('redirect=1', 'reflect=1', 'large=1'):
            response = await self.client.get('/api/state?' + query)
            self.assertEqual(response.status_code, 502)
            self.assertNotIn('location', response.headers)
            self.assertNotIn('private-google-identity', response.text)

    async def test_capabilities_advertise_read_only_without_changing_the_backend(self):
        response = await self.client.get('/api/capabilities')
        self.assertTrue(response.json()['read_only'])
        self.assertFalse(response.json()['writes_available'])
        self.assertFalse(response.json()['accounts_available'])
        self.assertFalse(response.json()['registration_available'])

    async def test_missing_identity_fails_closed_without_unauthenticated_retry(self):
        async def broken():
            raise RuntimeError('secret text must not appear')
        self.app = create_app(api_origin=API_ORIGIN, token_provider=broken,
                              upstream_transport=httpx.ASGITransport(app=self.upstream), gallery_dir=self.gallery)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='https://testserver') as client:
            response = await client.get('/api/state')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret text', response.text)
        self.assertEqual(self.calls, [])


class MetadataTests(unittest.IsolatedAsyncioTestCase):
    async def test_wrong_audience_or_expired_metadata_is_not_cached(self):
        for claims in ({'aud': 'https://attacker.invalid', 'exp': 4600}, {'aud': API_ORIGIN, 'exp': 1000}):
            payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b'=')
            async def metadata(request):
                return httpx.Response(200, text='header.' + payload.decode() + '.synthetic-signature')
            provider = MetadataIdentity(transport=httpx.MockTransport(metadata), clock=lambda: 1000)
            with self.assertRaises(ValueError):
                await provider()
            self.assertEqual(provider.token, '')

    async def test_server_only_metadata_cache_uses_exact_audience(self):
        calls = []
        now = [1000]
        def token(exp):
            payload = base64.urlsafe_b64encode(json.dumps({'aud': API_ORIGIN, 'exp': exp}).encode()).rstrip(b'=')
            return 'header.' + payload.decode() + '.synthetic-signature'
        async def metadata(request):
            calls.append(request)
            return httpx.Response(200, text=token(now[0] + 3600))
        provider = MetadataIdentity(transport=httpx.MockTransport(metadata), clock=lambda: now[0])
        self.assertEqual(await provider(), await provider())
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].url.params['audience'], API_ORIGIN)
        self.assertEqual(calls[0].headers['metadata-flavor'], 'Google')
        now[0] += 301
        await provider()
        self.assertEqual(len(calls), 2)


if __name__ == '__main__':
    unittest.main()
