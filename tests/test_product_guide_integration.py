"""介紹與教學只接產品入口，不建立示例帳號／成果。"""
from pathlib import Path
import hashlib


def test_intro_and_legacy_entry_are_safe_static_routes(client):
    for path in ('/','/intro','/intro/'):
        response=client.get(path)
        assert response.status_code==200
        assert '/static/product-guide.js' in response.text
        assert '/static/pwa-install.js' in response.text
    legacy=client.get('/intro/v05/')
    assert legacy.status_code==200 and '/static/intro/preview.js' in legacy.text
    assert "connect-src 'none'" in legacy.headers['content-security-policy']
    assert not client.cookies


def test_v05_core_files_remain_identical_to_live_baseline():
    root=Path(__file__).resolve().parents[1]/'app/static/intro'
    expected={'index.html':'2eb26b1adacd519c89920c55a8636cfcaa02b969b4298ca4f6a5f45e229041ca',
        'preview.js':'795246e1c550a2f49ad5d934a11289778794ef440c092d83576f2f6bfdf8dcbc',
        'hatch-timing.js':'ec9aa3b3a0677b4cf5e7a674da6b6eb6a47f6b93fed7cb9080d08b24629cea46',
        'preview-v1.css':'a8d1278ebd3c0886727a0cfb920f126a794fbf9356a76da245553899c1dec2ca',
        'entry-bridge.js':'75f60a3935aa9f110196b2d93bbcb95686b7c4f54ebd18c0e61e236478a66f3d'}
    for name,sha in expected.items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha
