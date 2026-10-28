import uvicorn  # 啟動本機 ASGI 服務

if __name__ == '__main__':  # 只在直接執行此檔時啟動工具
    uvicorn.run('app.main:create_app', factory=True, host='127.0.0.1', port=8000)  # 執行此模組的共用工具操作
