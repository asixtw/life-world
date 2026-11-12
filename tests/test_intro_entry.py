"""介紹為安全公開靜態讀取；即使Gate封閉，也不能接觸DB或開啟寫入。"""
from fastapi.testclient import TestClient
from app.main import create_app
from app.runtime import RuntimeSettings


def test_public_intro_works_without_database_and_keeps_private_gate_closed(tmp_path):
    app=create_app(tmp_path,settings=RuntimeSettings(public_gate_closed=True,business_enabled=False))
    def forbidden(*args,**kwargs):raise AssertionError('介紹不得連接資料庫')
    app.state.service.db.connect=forbidden
    with TestClient(app) as client:
        for path in ['/intro','/intro/']:
            response=client.get(path)
            assert response.status_code==200
            assert 'text/html' in response.headers['content-type']
            assert "connect-src 'none'" in response.headers['content-security-policy']
            assert response.headers['cache-control']=='no-store'
            assert '/static/intro/preview.js' in response.text
            assert client.head(path).status_code==200
        assert client.get('/static/intro/assets/art/v1/egg-deep-512.png').status_code==200
        assert not client.cookies
        assert client.get('/api/state').status_code==401
        assert client.post('/api/auth/guest',json={}).status_code==503
        assert client.post('/intro').status_code==503
        assert client.get('/intro/private').status_code!=200


def test_intro_route_does_not_change_product_shell_or_apis(client):
    assert client.get('/intro').status_code==200
    shell=client.get('/')
    assert '/static/intro-preference.js' in shell.text
    assert 'intro-menu' in shell.text
    assert client.post('/intro',json={}).status_code==405
    assert client.get('/api/auth/me').status_code==401
    # 介紹沒有建立Owner；正式訪客仍由既有明確POST開始。
    response=client.post('/api/auth/guest')
    assert response.status_code in (200,201)
    assert response.json()['lumi_hatched'] is False


def test_copied_intro_assets_match_recorded_sources(client):
    """相對路徑／音檔換成產品路徑後，逐檔校驗來源及交付內容。"""
    from pathlib import Path
    import hashlib,json
    root=Path(__file__).resolve().parents[1];directory=root/'app/static/intro'
    manifest=json.loads((directory/'asset-manifest.json').read_text())
    for item in manifest['copied']+manifest['generated']:
        file=(directory/item['path']).resolve()
        assert file.is_relative_to(directory)
        assert hashlib.sha256(file.read_bytes()).hexdigest()==item['sha256'],item['path']
        response=client.get('/static/intro/'+item['path'])
        assert response.status_code==200
        assert hashlib.sha256(response.content).hexdigest()==item['sha256']
        assert 'set-cookie' not in response.headers
    assert len(manifest['copied'])==19
