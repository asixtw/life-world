"""素材提供者的組裝邊界；替身只供隔離測試，不連外或讀取憑證。"""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import create_app
from conftest import onboard, register
from test_media import Provider, send


def test_injected_media_provider_does_not_leak_into_another_app(tmp_path):
    """不同App的能力與回應不可因組裝層注入而共用全域provider。"""
    clock = lambda: datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc)
    configured = create_app(data_dir=tmp_path / 'configured', clock=clock)
    unconfigured = create_app(data_dir=tmp_path / 'unconfigured', clock=clock)
    provider = Provider('合成測試候選文字')
    configured.state.media_provider = provider
    with TestClient(configured) as first, TestClient(unconfigured) as second:
        onboard(first)
        onboard(second)
        # Guest在provider之前被拒絕；註冊後才驗證跨App注入隔離。
        assert first.get('/api/media/capabilities').json()['recognition_available'] is False
        assert send(first).status_code == 403
        assert provider.calls == []
        register(first, 'synthetic_media_first')
        register(second, 'synthetic_media_second')
        first_before = first.get('/api/state').json()
        second_before = second.get('/api/state').json()
        assert first.get('/api/media/capabilities').json()['recognition_available'] is True
        assert second.get('/api/media/capabilities').json()['recognition_available'] is False
        result = send(first)
        assert result.status_code == 200
        assert result.json()['text'] == '合成測試候選文字'
        assert result.json()['applied'] is False
        assert send(second).status_code == 503
        assert len(provider.calls) == 1
        assert first.get('/api/state').json() == first_before
        assert second.get('/api/state').json() == second_before
