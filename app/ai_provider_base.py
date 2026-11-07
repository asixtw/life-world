"""模型傳輸共用型別；錯誤只攜帶固定碼，不洩漏 key/來源內容。"""
from dataclasses import dataclass
from typing import Optional

class EvalError(ValueError):
    """可安全回報的固定碼；保留隔離評測既有名稱相容性。"""

@dataclass(frozen=True)
class ModelResult:
    text:str
    input_tokens:Optional[int]=None
    output_tokens:Optional[int]=None
    cost_microusd:Optional[int]=None
    provider_request_id:Optional[str]=None
