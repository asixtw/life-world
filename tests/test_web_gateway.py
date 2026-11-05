"""真正 app/static → gateway → FastAPI → 隔離 DB；不連線或寫入 Cloud SQL。"""
from dataclasses import replace
import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient
import httpx
import pytest

from app.main import create_app
from conftest import onboard

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('web_server', ROOT / 'collaboration/ui-kit/tools/web_server.py')
gateway = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway)


def business_gateway(app, tmp_path):
    """既有 SQLite／PG 測試 DB 共用領域層，只替換出站 IAM 與 HTTP transport。"""
    settings = replace(app.state.settings, trusted_hosts=('lw-api-main-u5py2jttpa-de.a.run.app',),
                       secure_cookies=True, external_origin='https://testserver')
    backend = create_app(database=app.state.service.db, policy=app.state.service.policy,
                         clock=app.state.service.clock, settings=settings)
    async def identity():
        return 'synthetic-server-identity'
    gallery = tmp_path / 'gallery'
    gallery.mkdir(exist_ok=True)
    (gallery / 'index.html').write_text('<h1>gallery fixture</h1>', encoding='utf-8')
    return gateway.create_app(api_origin=gateway.API_ORIGIN, token_provider=identity,
                              upstream_transport=httpx.ASGITransport(app=backend), gallery_dir=gallery)


def test_existing_business_pages_and_owner_reads_do_not_issue_database_writes(client, app, tmp_path, monkeypatch):
    me, goal = onboard(client)
    session = client.cookies.get('lw_session')
    connect = app.state.service.db.connect
    def readonly(*args, **kwargs):
        assert not kwargs.get('write', False), 'GET gateway must not issue database writes'
        return connect(*args, **kwargs)
    monkeypatch.setattr(app.state.service.db, 'connect', readonly)
    with TestClient(business_gateway(app, tmp_path), base_url='https://testserver') as web:
        headers = {'Cookie': 'lw_session=' + session}
        page = web.get('/app/')
        assert '/static/app.js' in page.text and 'content-security-policy' in page.headers
        assert web.get('/static/app.js').status_code == 200
        assert web.get('/api/auth/me', headers=headers).json()['owner_id'] == me['owner_id']
        state = web.get('/api/state', headers=headers)
        assert state.status_code == 200 and state.json()['goals'][0]['id'] == goal['id']
        assert web.get('/api/goals/' + goal['id'] + '/dashboard', headers=headers).status_code == 200
        assert web.get('/api/goals/another-owner-goal', headers=headers).status_code == 404
        assert web.get('/api/state', headers={'Cookie': 'lw_session=invalid'}).status_code == 401
        assert web.post('/api/auth/login', json={}, headers={'Origin': 'https://testserver'}).status_code == 403


def test_business_ui_honors_read_only_capability_instead_of_creating_guest_worlds(client, app, tmp_path):
    from playwright.sync_api import sync_playwright
    me, goal = onboard(client)
    session = client.cookies.get('lw_session')
    with TestClient(business_gateway(app, tmp_path), base_url='https://testserver') as web:
        with sync_playwright() as p:
            candidates = (p.chromium.executable_path,
                          r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                          r'C:\Program Files\Google\Chrome\Application\chrome.exe')
            executable = next((path for path in candidates if Path(path).is_file()), None)
            if executable is None:
                pytest.skip('No installed browser; API/SQL contract remains separately tested')
            browser = p.chromium.launch(executable_path=executable, headless=True)
            try:
                context = browser.new_context()
                context.add_cookies([{'name': 'lw_session', 'value': session, 'url': 'https://testserver',
                                     'secure': True, 'httpOnly': True, 'sameSite': 'Strict'}])
                seen = []
                def route_http(route):
                    request = route.request
                    assert request.url.startswith('https://testserver/')
                    assert 'x-serverless-authorization' not in request.all_headers()
                    assert 'authorization' not in request.all_headers()
                    seen.append((request.method, request.url))
                    response = web.request(request.method, request.url, headers=request.all_headers())
                    route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)
                context.route('**/*', route_http)
                page = context.new_page()
                page.set_default_timeout(5000)
                page.goto('https://testserver/app/')
                page.locator('#read-only-notice').wait_for(state='visible')
                page.get_by_text(goal['title'], exact=False).first.wait_for()
                assert page.locator('#app').inner_text()
                assert any(url.endswith('/api/state') for method, url in seen)
                assert all(method == 'GET' for method, url in seen)
                # 無 Session 的同一真正 UI 只能說明唯讀，不能建立世界或誘導登入。
                context.clear_cookies()
                page.reload()
                page.get_by_text('目前僅開放資料回讀。', exact=True).wait_for()
                assert page.locator('[data-action="guest"]').count() == 0
                assert page.locator('[data-action="login-dialog"]').count() == 0
                page.screenshot(path=str(tmp_path / 'readonly-business-ui.png'), full_page=True)
                context.close()
            finally:
                browser.close()
