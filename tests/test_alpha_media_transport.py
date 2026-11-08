"""媒體路由與 JSON 護欄分離；只驗證傳輸，不冒稱真實辨識。"""
import asyncio
from app.auth_rate_limit import AlphaBodyLimit
from app.media import MediaBodyLimit


def exchange(path, chunks, limit=200000):
    received=[];sent=[]
    async def app(scope,receive,send):
        while True:
            event=await receive();received.append(event)
            if not event.get('more_body'):break
        await send({'type':'http.response.start','status':200,'headers':[]})
        await send({'type':'http.response.body','body':b'ok'})
    events=[{'type':'http.request','body':part,'more_body':i<len(chunks)-1} for i,part in enumerate(chunks)]
    async def receive():return events.pop(0)
    async def send(event):sent.append(event)
    asyncio.run(AlphaBodyLimit(MediaBodyLimit(app,limit))({'type':'http','path':path,'method':'POST'},receive,send))
    return received,sent


def test_audio_over_json_limit_reaches_media_handler():
    received,sent=exchange('/api/media/recognize',[b'a'*40000,b'b'*40000])
    assert sent[0]['status']==200
    # 不先合併整個媒體本文，保留 ASGI 串流分段供 multipart 暫存。
    assert [len(e['body']) for e in received]==[40000,40000]


def test_json_limit_remains_strict():
    _,sent=exchange('/api/goals',[b'a'*70000])
    assert sent[0]['status']==413


def test_media_limit_still_rejects_chunked_overflow():
    _,sent=exchange('/api/media/recognize',[b'a'*40000,b'b'*40000],limit=70000)
    assert sent[0]['status']==413
