"""辨識僅回傳候選，不持久化素材，也不寫人物、進度或積分。"""
from io import BytesIO
import wave

import pytest
from PIL import Image
from conftest import guest, onboard


def image_bytes():
    """產生不含真實資料的有效圖片。"""
    out = BytesIO()
    Image.new('RGB', (2, 2), 'green').save(out, 'PNG')
    return out.getvalue()


def audio_bytes():
    """產生短靜音 WAV，驗證音訊入口。"""
    out = BytesIO()
    with wave.open(out, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b'\0' * 160)
    return out.getvalue()


class Provider:
    """測試替身；不會連接任何外部服務。"""
    def __init__(self, text='待人工核對的文字', fails=False):
        self.text, self.fails, self.calls = text, fails, []

    def extract(self, *, kind, mime, content):
        self.calls.append((kind, mime, content))
        if self.fails:
            raise RuntimeError('秘密服務憑證不得出現在回應')
        return self.text


def send(client, kind='image', mime='image/png', content=None, name='sample.png'):
    return client.post('/api/media/recognize', data={'kind': kind},
                       files={'file': (name, image_bytes() if content is None else content, mime)})


def test_capabilities_do_not_claim_available_provider(client):
    onboard(client)
    response = client.get('/api/media/capabilities')
    assert response.status_code == 200
    assert response.json()['recognition_available'] is False
    assert response.json()['server_retention'] == 'none'
    assert response.json()['max_bytes'] == 4096


def test_unconfigured_provider_is_an_explicit_failure(client):
    onboard(client)
    response = send(client)
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'media_provider_unavailable'


@pytest.mark.parametrize('kind,mime,content,name', [
    ('image', 'image/png', image_bytes(), 'image.png'),
    ('screenshot', 'image/png', image_bytes(), 'screen.png'),
    ('card', 'image/png', image_bytes(), 'card.png'),
    ('audio', 'audio/wav', audio_bytes(), 'voice.wav'),
])
def test_recognition_never_changes_domain_data(app, client, kind, mime, content, name):
    onboard(client)
    before = client.get('/api/state').json()
    app.state.media_provider = Provider()
    response = send(client, kind, mime, content, name)
    assert response.status_code == 200
    result = response.json()
    assert result['text'] == '待人工核對的文字' and result['applied'] is False
    assert result['source']['size'] == len(content)
    assert result['source']['kind'] == kind
    assert len(result['source']['sha256']) == 64
    assert result['server_retention'] == 'none'
    assert client.get('/api/state').json() == before
    assert len(app.state.media_provider.calls) == 1


@pytest.mark.parametrize('kind,mime,content,name,status', [
    ('image', 'image/png', b'', 'empty.png', 422),
    ('image', 'image/png', b'not an image', 'broken.png', 415),
    ('image', 'image/svg+xml', b'<svg/>', 'image.svg', 415),
    ('image', 'image/png', image_bytes(), '../image.png', 422),
    ('audio', 'audio/wav', b'fake audio', 'bad.wav', 415),
    ('image', 'image/png', b'x' * 4097, 'large.png', 413),
    ('card', 'audio/wav', audio_bytes(), 'voice.wav', 415),
    ('invalid', 'image/png', image_bytes(), 'image.png', 422),
])
def test_reject_invalid_material_without_calling_provider(app, client, kind, mime, content, name, status):
    onboard(client)
    app.state.media_provider = Provider()
    response = send(client, kind, mime, content, name)
    assert response.status_code == status
    assert app.state.media_provider.calls == []


@pytest.mark.parametrize('text,fails', [('', False), ('x' * 20001, False), (None, False), ('', True)],
                         ids=['empty', 'too-long', 'non-text', 'provider-error'])
def test_provider_failure_is_sanitized_and_has_no_side_effect(app, client, text, fails):
    onboard(client)
    before = client.get('/api/state').json()
    app.state.media_provider = Provider(text, fails)
    response = send(client)
    assert response.status_code == 502
    assert '秘密' not in response.text
    assert client.get('/api/state').json() == before


def test_media_requires_session_csrf_and_onboarding(app, client):
    assert send(client).status_code == 401
    guest(client)
    assert send(client).status_code == 409
    onboard(client)
    client.headers.pop('X-CSRF-Token')
    assert send(client).status_code == 403


def test_chunked_oversize_request_is_rejected_before_multipart_spooling(client):
    """沒有 Content-Length 也必須限制整個請求，不能先寫滿暫存磁碟才拒絕。"""
    onboard(client)
    chunks = iter([b'x' * 70000])
    response = client.post('/api/media/recognize', content=chunks,
                           headers={'Content-Type': 'multipart/form-data; boundary=testing'})
    assert response.status_code == 413
    assert response.json()['error']['code'] == 'upload_too_large'
