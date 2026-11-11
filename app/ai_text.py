"""8445 的文字生成介面（2026-11-10 移植）：Provider 中立的請求、結果與固定錯誤碼。B 原有的 app/ai.py 不變。"""
from dataclasses import dataclass
from typing import Literal, Optional, Protocol


# 以下為 S1 文字生成的供應商中立介面：生成模組只組 Prompt 與驗證結構，不知道是哪家廠商。
PROVIDER_FAILURES = ('provider_refused', 'provider_error', 'invalid_output', 'provider_unavailable', 'provider_timeout')  # 固定錯誤碼，拒絕與故障分開


class ProviderFailure(Exception):
    """固定錯誤碼與可選用量摘要。失敗結果不攜帶原文、URL 或金鑰。"""
    def __init__(self, code, *, result=None, http_status=None, reason=None):
        if code not in PROVIDER_FAILURES:
            code = 'provider_error'  # 未知代碼一律視為一般故障，避免外洩細節
        self.code = code
        self.result = result
        self.http_status = http_status
        self.reason = reason  # 供應商錯誤的列舉原因（例如 API_KEY_INVALID）或分類（api_key／schema／context_length）；不含訊息原文
        super().__init__(code)


@dataclass(frozen=True)
class TextRequest:
    """伺服端組好的單次生成請求；user 只含玩家明確輸入的內容。"""
    system: str
    user: str
    max_output_tokens: int
    response_schema: dict


@dataclass(frozen=True)
class TextResult:
    """Provider 回傳的原始文字與已知用量；未知費用保持 None，不捏造 0。"""
    text: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_microusd: Optional[int] = None
    provider_request_id: Optional[str] = None
    model_version: Optional[str] = None


class TextProvider(Protocol):
    """所有文字生成供應商的共同介面；kind 區分測試用假回應與真實模型。"""
    name: str
    model: str
    kind: Literal['fake', 'live']

    def generate(self, request: TextRequest) -> TextResult:
        ...
