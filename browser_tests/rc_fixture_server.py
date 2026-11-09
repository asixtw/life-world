"""僅隔離Chromium RC測試：固定日期與明示AI替身，禁止對外網路模型呼叫。"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
import uvicorn
from app.main import create_app
from app.runtime import RuntimeSettings
from app.ai_runtime import AIRuntime,AISettings
from app.ai_provider_base import ModelResult


class FixtureProvider:
    live=False
    name='test-transport'
    model='explicit-synthetic-fixture'
    def generate(self,prompt,max_output_tokens):
        return ModelResult(json.dumps({'summary':'合成Fixture：今天閱讀15分鐘，整理一個重點。','tasks':['明天閱讀15分鐘']}))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',required=True,type=Path);parser.add_argument('--port',default=8003,type=int);args=parser.parse_args()
    # 此啟動器只能使用本機暫存資料，不沿用App日常資料或Cloud SQL。
    directory=args.data_dir.resolve()
    if not directory.is_relative_to(Path('/private/tmp')):parser.error('必須使用/private/tmp隔離目錄')
    app=create_app(data_dir=directory,settings=RuntimeSettings(backend='sqlite'),clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))
    settings=AISettings(provider='gemini',model='gemini-synthetic',approved=True,reservation_microusd=1,max_budget_microusd=10000,max_total_budget_microusd=10000)
    app.state.ai_runtime=AIRuntime(app.state.service,settings,FixtureProvider())
    uvicorn.run(app,host='127.0.0.1',port=args.port,access_log=False)


if __name__=='__main__':main()
