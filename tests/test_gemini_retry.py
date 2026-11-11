"""Gemini 回 HTTP 503（UNAVAILABLE，服務暫時過載）時自動重試一次（2026-11-11 Jerry 決定）。

程式自帶的自動測試：以假的傳輸層模擬 Gemini 回應（不連網、不計費）。重試發生在同一次生成內，
金額預留仍只有一次；只重試 503，其他錯誤（429 額度、400 格式、401／403 金鑰、500）不重試。
"""
import io
import json
from urllib.error import HTTPError

import pytest

from app.ai_providers import GeminiProvider
from app.ai_text import ProviderFailure, TextRequest

REQUEST = TextRequest(system='系統', user='{"module":"person_profile"}', max_output_tokens=500, response_schema={'type': 'object'})
OK = {'candidates': [{'content': {'parts': [{'text': '{"background":"ok"}'}]}, 'finishReason': 'STOP'}],
      'usageMetadata': {'promptTokenCount': 10, 'candidatesTokenCount': 5}, 'modelVersion': 'gemini-test', 'responseId': 'resp-1'}


def http_error(code, status):
    body = json.dumps({'error': {'code': code, 'status': status, 'message': 'synthetic'}}).encode()
    return HTTPError('https://example.invalid/model', code, status, {}, io.BytesIO(body))


def provider(responses, records):
    calls = []

    def transport(endpoint, body, headers, timeout):
        calls.append(1)
        item = responses[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    p = GeminiProvider('gemini-test', key_supplier=lambda: 'synthetic-not-a-real-key', transport=transport,
                       diagnostics=records.append, retry_delay_seconds=0)
    return p, calls


def test_503_is_retried_once_and_then_succeeds():
    records = []
    p, calls = provider([http_error(503, 'UNAVAILABLE'), OK], records)
    result = p.generate(REQUEST)
    assert result.text == '{"background":"ok"}' and result.input_tokens == 10
    assert len(calls) == 2
    assert records[-1]['outcome'] == 'ok' and records[-1]['http_status'] == 200 and records[-1]['retried_after'] == 503


def test_second_503_fails_without_a_third_call():
    records = []
    p, calls = provider([http_error(503, 'UNAVAILABLE'), http_error(503, 'UNAVAILABLE'), OK], records)
    with pytest.raises(ProviderFailure) as failure:
        p.generate(REQUEST)
    assert failure.value.code == 'provider_error' and len(calls) == 2
    assert records[-1]['http_status'] == 503 and records[-1]['retried_after'] == 503


@pytest.mark.parametrize('code,status', [(429, 'RESOURCE_EXHAUSTED'), (500, 'INTERNAL'), (400, 'INVALID_ARGUMENT'), (403, 'PERMISSION_DENIED')])
def test_other_errors_are_not_retried(code, status):
    records = []
    p, calls = provider([http_error(code, status), OK], records)
    with pytest.raises(ProviderFailure):
        p.generate(REQUEST)
    assert len(calls) == 1 and records[-1]['retried_after'] is None


def test_success_without_error_calls_once():
    records = []
    p, calls = provider([OK], records)
    assert p.generate(REQUEST).text == '{"background":"ok"}'
    assert len(calls) == 1 and records[-1]['retried_after'] is None
