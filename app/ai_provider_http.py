"""共用 HTTPS 傳輸：固定上限、不追蹤重新導向、不記錄內容。"""
import json
from urllib.request import Request,build_opener,HTTPRedirectHandler
from .ai_provider_base import EvalError

class NoRedirect(HTTPRedirectHandler):
    """不將Authorization或合成來源轉送到另一個未核准目的地。"""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def https_transport(endpoint, body, headers, timeout):
    request = Request(endpoint, data=body, headers=headers, method='POST')
    with build_opener(NoRedirect).open(request, timeout=timeout) as response:
        payload = response.read(128001)
        if len(payload) > 128000:
            raise EvalError('gateway_output_too_large')
        return json.loads(payload)

