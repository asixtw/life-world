"""API 容器入口；本機 python -m app 仍保留原有預設。"""
import os
import uvicorn


def main():
    port = int(os.environ.get('PORT', '8080'))
    if not 1 <= port <= 65535:
        raise ValueError('Invalid PORT')
    uvicorn.run('app.main:create_app', factory=True, host='0.0.0.0', port=port,
                proxy_headers=True, forwarded_allow_ips=os.environ.get('LIFEWORLD_FORWARDED_ALLOW_IPS', '127.0.0.1'))


if __name__ == '__main__':
    main()
