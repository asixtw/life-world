"""供應商中立的JSON gateway adapter；只對明確核准的HTTPS目標單次呼叫。"""
import json
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .core import EvalError, ModelResult


from app.ai_provider_http import NoRedirect, https_transport


class JsonGatewayProvider:
    """固定目標／模型，不自動換key、重試或猜測任何廠商專用API格式。"""
    live = True

    def __init__(self, name, model, endpoint, *, key_supplier, transport=None):
        parsed = urlsplit(endpoint)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or not name or not model):
            raise EvalError('invalid_gateway')
        self.name, self.model, self.endpoint = name, model, endpoint
        self._key_supplier = key_supplier
        self._transport = transport or https_transport
        self.metadata = {'name': name, 'model': model, 'endpoint': endpoint, 'protocol': 'lw-json-gateway-v1'}

    def generate(self, prompt, max_output_tokens):
        """秘密延遲到已取得呼叫批准與額度預留後才讀；失敗只回固定碼。"""
        try:
            secret = self._key_supplier()
            if not isinstance(secret, str) or not secret.strip() or '\n' in secret or '\r' in secret:
                raise EvalError('credential_unavailable')
            body = json.dumps({'model': self.model, 'prompt': prompt, 'max_output_tokens': max_output_tokens}, ensure_ascii=False).encode()
            payload = self._transport(self.endpoint, body, {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + secret}, 30)
            usage = payload.get('usage') or {}
            return ModelResult(payload['text'], usage.get('input_tokens'), usage.get('output_tokens'),
                               payload.get('cost_microusd'), payload.get('request_id'))
        except Exception:
            # 不回顯SDK/HTTP例外，避免其中的header、URL或來源正文流入一般log。
            raise EvalError('gateway_failed') from None
