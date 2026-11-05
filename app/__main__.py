import os
from .runtime import flag
import uvicorn  # 啟動本機 ASGI 服務

if __name__ == '__main__':  # 只在直接執行此檔時啟動工具
    uvicorn.run('app.main:create_app', factory=True, host='127.0.0.1', port=8000,proxy_headers=not (flag('LIFEWORLD_AUTH_RATE_ENABLED',False) or os.environ.get('LIFEWORLD_ACCESS_MODE')=='public_alpha'))  # 執行此模組的共用工具操作
