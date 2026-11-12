"""僅供歷史資料相容性測試：直接呼叫保留的領域方法，不重新開放 HTTP 產品入口。"""
import httpx
from pydantic import ValidationError
from app.schemas import PersonProfileSave
from app.errors import DomainError


def save_legacy_profile(client, person_id, payload):
    """沿用真 Session/CSRF、DTO 與交易；回應形狀只供既有測試斷言。"""
    try:
        data = PersonProfileSave.model_validate(payload)
        service = client.app.state.service
        owner = service.session(client.cookies.get('lw_session'), client.headers.get('X-CSRF-Token'), True)[0]['id']
        result = service.save_unified_profile(owner, person_id, data)
        return httpx.Response(200, json=result)
    except ValidationError:
        return httpx.Response(422, json={'error': {'code': 'validation_error'}})
    except DomainError as exc:
        return httpx.Response(exc.status, json={'error': {'code': exc.code, 'message': exc.message}})
