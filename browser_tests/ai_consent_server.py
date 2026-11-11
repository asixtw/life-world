"""本機合成AI授權服務：明示替身、零外部網路呼叫，不是Alpha或真Gemini。"""
import json,time
from app.ai_runtime import AIRuntime,AISettings
from app.ai_provider_base import ModelResult
from .integration_server import app


class SyntheticProvider:
    live=False
    name='synthetic-consent-browser'
    model='synthetic-only'
    def generate(self,prompt,max_output_tokens):
        raw=prompt['case']['raw_text']
        if 'fixture:delay' in raw:time.sleep(.5)  # 僅測晚回應，不用真模型或長等待。
        if 'fixture:failure' in raw:raise ValueError('synthetic-provider-failure')
        return ModelResult(json.dumps({'summary':'合成AI整理候選','tasks':['合成後續任務'],'people':[]}),3,4,None,None)


app.state.ai_runtime=AIRuntime(app.state.service,AISettings(provider='gemini',model='gemini-synthetic',approved=True,max_total_budget_microusd=1_000_000,reservation_microusd=100,max_budget_microusd=100_000,max_owner_daily_calls=500,max_global_calls=5000),provider=SyntheticProvider())
