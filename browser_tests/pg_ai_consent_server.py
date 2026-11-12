"""受限本機PG18＋明示AI替身；不是Gemini驗收，也不開啟正式AI。"""
from .pg_integration_server import app
from .synthetic_ai_provider import SyntheticProvider
from app.ai_runtime import AIRuntime,AISettings

app.state.ai_runtime=AIRuntime(app.state.service,AISettings(provider='gemini',model='gemini-synthetic',approved=True,max_total_budget_microusd=1_000_000,reservation_microusd=100,max_budget_microusd=100_000,max_owner_daily_calls=500,max_global_calls=5000),provider=SyntheticProvider())
