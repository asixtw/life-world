# 2026-11-10 自 8445（life-world-react-integrated/app/ai_config.py）原樣移植。
"""AI 生成的本機設定；只含非秘密值，金鑰在呼叫當下才由 Provider 讀取。

這些預設值是 Local 測試用的保守上限，不是正式產品的價格或額度決策。
"""
from dataclasses import dataclass  # 設定值不可變
import os  # 讀取環境變數（App 不讀 .env）
import re  # 驗證模型名稱格式

from .runtime import flag  # 沿用既有布林旗標解析，拒絕模糊值

PROVIDERS = ('', 'fake', 'gemini')  # '' 表示未設定；不允許未知供應商默默退回其他選項


@dataclass(frozen=True)
class AiSettings:
    provider: str = ''  # '', 'fake', 'gemini'
    model: str = ''  # 真實模型型號須由使用者核准後才填
    live_approved: bool = False  # 明確授權付費呼叫的開關；未開啟時不建立真實 Provider
    timeout_seconds: float = 30.0  # 單次生成總時限（設計目標，非已驗證效能）
    max_output_tokens: int = 600  # 每次最多輸出 Token
    owner_daily_limit: int = 10  # 每位使用者滾動 24 小時次數上限（含失敗）
    global_daily_limit: int = 50  # 全站滾動 24 小時次數上限
    fake_delay_ms: int = 0  # 假回應延遲，供本機驗證取消與載入狀態
    cloud_run: bool = False

    def __post_init__(self):
        if self.provider not in PROVIDERS:
            raise ValueError('Unknown AI provider')
        if self.cloud_run and self.provider == 'fake':
            raise ValueError('Fake AI provider is not allowed on Cloud Run')  # 雲端不得把假回應呈現給使用者
        if not 0 < self.timeout_seconds <= 120 or not 1 <= self.max_output_tokens <= 2000:
            raise ValueError('Invalid AI timeout or output limit')
        for value in (self.owner_daily_limit, self.global_daily_limit):
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 100000:
                raise ValueError('Invalid AI quota')
        if not 0 <= self.fake_delay_ms <= 60000:
            raise ValueError('Invalid fake delay')
        if self.model and not re.fullmatch(r'[a-z0-9][a-z0-9.\-]{0,100}', self.model):
            raise ValueError('Invalid AI model name')

    @classmethod
    def from_env(cls):
        """只讀非秘密設定；LIFEWORLD_AI_API_KEY 不在此讀取，避免進入設定物件或 repr。"""
        return cls(provider=os.environ.get('LIFEWORLD_AI_PROVIDER', '').strip().lower(),
                   model=os.environ.get('LIFEWORLD_AI_MODEL', '').strip(),
                   live_approved=flag('LIFEWORLD_AI_LIVE_APPROVED', False),
                   timeout_seconds=float(os.environ.get('LIFEWORLD_AI_TIMEOUT_SECONDS', '30')),
                   max_output_tokens=int(os.environ.get('LIFEWORLD_AI_MAX_OUTPUT_TOKENS', '600')),
                   owner_daily_limit=int(os.environ.get('LIFEWORLD_AI_OWNER_DAILY_LIMIT', '10')),
                   global_daily_limit=int(os.environ.get('LIFEWORLD_AI_GLOBAL_DAILY_LIMIT', '50')),
                   fake_delay_ms=int(os.environ.get('LIFEWORLD_AI_FAKE_DELAY_MS', '0')),
                   cloud_run=bool(os.environ.get('K_SERVICE')))
