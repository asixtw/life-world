"""僅本機UI授權回歸使用的明示替身，絕不送出外部模型請求。"""
import json,time
from app.ai_provider_base import ModelResult

class SyntheticProvider:
    live=False
    name='synthetic-consent-browser'
    model='synthetic-only'
    def generate(self,prompt,max_output_tokens):
        raw=prompt['case']['raw_text']
        if 'fixture:delay' in raw:time.sleep(.5)  # 僅測晚回應，不用真模型或長等待。
        if 'fixture:failure' in raw:raise ValueError('synthetic-provider-failure')
        return ModelResult(json.dumps({'summary':'合成AI整理候選','tasks':['合成後續任務'],'people':[]}),3,4,None,None)

