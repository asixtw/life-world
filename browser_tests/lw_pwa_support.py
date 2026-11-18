"""只提供127.0.0.1暫存測試服務；不讀取原帳號或雲端設定。"""
from contextlib import contextmanager
from threading import Thread
import socket,time
import uvicorn

@contextmanager
def running(app):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error'))
    thread=Thread(target=server.run,daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started:break
            if not thread.is_alive():raise RuntimeError('Local test server did not start')
            time.sleep(.03)
        assert server.started
        yield f'http://127.0.0.1:{port}'
    finally:
        server.should_exit=True;thread.join(5)

