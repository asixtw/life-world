"""本機合成AI授權服務：明示替身、零外部網路呼叫，不是Alpha或真Gemini。"""
import json,time
from app.ai_runtime import AIRuntime,AISettings
from app.ai_provider_base import ModelResult
from .integration_server import app


from .synthetic_ai_provider import SyntheticProvider


app.state.ai_runtime=AIRuntime(app.state.service,AISettings(provider='gemini',model='gemini-synthetic',approved=True,max_total_budget_microusd=1_000_000,reservation_microusd=100,max_budget_microusd=100_000,max_owner_daily_calls=500,max_global_calls=5000),provider=SyntheticProvider())
