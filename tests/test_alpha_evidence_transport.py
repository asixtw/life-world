"""成果圖片沿用既有容量，不能誤套文字護欄；只使用隔離合成資料。"""
import asyncio
from io import BytesIO
from datetime import datetime, timezone
from random import Random

from fastapi.testclient import TestClient
from PIL import Image

from app.auth_rate_limit import AlphaBodyLimit
from app.main import create_app
from app.media import MediaBodyLimit
from conftest import onboard, register


def exchange(path, chunks, *, multipart=True, evidence_limit=200000):
    """無Content-Length的分段請求也必須在解析前受限。"""
    received=[];sent=[]
    async def downstream(scope, receive, send):
        while True:
            event=await receive();received.append(event)
            if not event.get('more_body'):break
        await send({'type':'http.response.start','status':200,'headers':[]})
        await send({'type':'http.response.body','body':b'ok'})
    events=[{'type':'http.request','body':part,'more_body':i<len(chunks)-1} for i,part in enumerate(chunks)]
    async def receive():return events.pop(0)
    async def send(event):sent.append(event)
    scope={'type':'http','path':path,'method':'POST','headers':[(b'content-type',b'multipart/form-data; boundary=test' if multipart else b'application/json')]}
    asyncio.run(AlphaBodyLimit(MediaBodyLimit(downstream, max_bytes=evidence_limit))(scope,receive,send))
    return received,sent


def test_evidence_over_json_limit_streams_without_copying():
    received,sent=exchange('/api/goals/synthetic/evidence',[b'a'*40000,b'b'*40000])
    assert sent[0]['status']==200
    assert [len(e['body']) for e in received]==[40000,40000]


def test_evidence_request_limit_is_inclusive_and_rejects_overflow():
    _,sent=exchange('/api/goals/synthetic/evidence',[b'a'*70000,b'b'*10000],evidence_limit=80000)
    assert sent[0]['status']==200
    _,sent=exchange('/api/goals/synthetic/evidence',[b'a'*70000,b'b'*10001],evidence_limit=80000)
    assert sent[0]['status']==413


def test_other_paths_and_json_cannot_claim_image_limit():
    for path,multipart in [('/api/goals',True),('/api/goals/synthetic/evidence/other',True),('/api/goals/synthetic/evidence',False)]:
        _,sent=exchange(path,[b'a'*70000],multipart=multipart)
        assert sent[0]['status']==413


def test_real_image_upload_over_64k_keeps_csrf_and_owner_isolation(tmp_path):
    app=create_app(data_dir=tmp_path,clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))
    # 補上公開版的同一本文護欄，帳號建立仍使用隔離本機既有流程。
    app.add_middleware(AlphaBodyLimit)
    image=Image.frombytes('RGB',(256,128),Random(7).randbytes(256*128*3));out=BytesIO();image.save(out,format='PNG');data=out.getvalue()
    assert len(data)>65536
    with TestClient(app) as client:
        _,goal=onboard(client);register(client)
        url='/api/goals/'+goal['id']+'/evidence'
        denied=client.post(url,headers={'X-CSRF-Token':'wrong'},files={'file':('synthetic.png',data,'image/png')})
        assert denied.status_code==403
        good=client.post(url,files={'file':('synthetic.png',data,'image/png')})
        assert good.status_code==201,good.text
        assert client.get('/api/evidence/'+good.json()['id']).content==data
        with TestClient(app) as other:
            onboard(other);register(other,'evidence_other')
            assert other.post(url,files={'file':('synthetic.png',data,'image/png')}).status_code==404
        too_large=data+b'\0'*(5*1024*1024+1-len(data))
        assert client.post(url,files={'file':('large.png',too_large,'image/png')}).status_code==413
