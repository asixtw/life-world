"""媒體父工作只計一次，片段成本/並發/重送仍受保護；只有合成Provider。"""
import hashlib
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from test_ai_runtime import prepared
from conftest import onboard,register


def test_audio_segments_count_one_work_but_reserve_every_segment(prepared):
    app,c,me,g,r,p=prepared;owner=me['owner_id']
    r.settings=replace(r.settings,max_owner_daily_calls=1,max_global_calls=1,max_budget_microusd=1000)
    p.text='{"text":"合成片段"}'
    work=r.begin_media_work(owner,'hash','audio-job')
    for i in range(3):r.recognize(owner,'audio','audio/wav',b'pcm'+bytes([i]),media_work=work,request_id='segment-'+str(i))
    assert len(p.calls)==3 and r.usage(owner)['reserved_microusd']==300
    with pytest.raises(Exception) as e:r.begin_media_work(owner,'other','another-job')
    assert e.value.code=='ai_quota_reached'
    # 即使同一父工作，成本不會豁免。
    r.settings=replace(r.settings,max_budget_microusd=300)
    with pytest.raises(Exception) as e:r.recognize(owner,'audio','audio/wav',b'fourth',media_work=work)
    assert e.value.code=='ai_quota_reached' and len(p.calls)==3


def test_media_work_concurrent_duplicate_and_owner_isolation(prepared):
    app,c,me,g,r,p=prepared;owner=me['owner_id']
    def start(_):
        try:return r.begin_media_work(owner,'same','same-job')
        except Exception as e:return e.code
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(start,range(4)))
    works=[x for x in results if isinstance(x,tuple)]
    assert len(works)==1 and results.count('ai_request_already_reserved')==3 and p.calls==[]
    with TestClient(app) as other:
        who,_=onboard(other);register(other,'media_other')
        p.text='{"text":"合成"}'
        with pytest.raises(Exception) as e:r.recognize(who['owner_id'],'audio','audio/wav',b'pcm',media_work=works[0])
        assert e.value.code=='media_work_owner' and p.calls==[]
        # 甲用盡自己的工作額度不會剝奪乙的獨立額度（仍受共同全域上限）。
        r.settings=replace(r.settings,max_owner_daily_calls=1)
        r.recognize(who['owner_id'],'image','image/png',b'synthetic')
        assert r.usage(owner)['calls']==0 and r.usage(who['owner_id'])['calls']==1


def test_failed_segment_keeps_cost_and_retry_is_explicit_new_work(prepared):
    app,c,me,g,r,p=prepared;owner=me['owner_id']
    work=r.begin_media_work(owner,'hash','failed-job');p.text='invalid JSON'
    with pytest.raises(Exception):r.recognize(owner,'audio','audio/wav',b'pcm',media_work=work,request_id='seg-one')
    with pytest.raises(Exception) as e:r.recognize(owner,'audio','audio/wav',b'pcm',media_work=work,request_id='seg-one')
    assert e.value.code=='ai_request_already_reserved' and len(p.calls)==1
    with pytest.raises(Exception) as e:r.begin_media_work(owner,'hash','failed-job')
    assert e.value.code=='ai_request_already_reserved'
    assert r.usage(owner)['unknown_cost_calls']==1 and r.usage(owner)['reserved_microusd']==100
    r.begin_media_work(owner,'hash','explicit-new-job')


def test_photo_idempotency_binds_actual_bytes(prepared):
    app,c,me,g,r,p=prepared;p.text='{"text":"合成"}'
    r.recognize(me['owner_id'],'image','image/png',b'one',request_id='photo')
    with pytest.raises(Exception) as e:r.recognize(me['owner_id'],'image','image/png',b'two',request_id='photo')
    assert e.value.code=='request_conflict' and len(p.calls)==1


def test_real_audio_work_cancel_stops_segments_and_keeps_reserved_cost(prepared,monkeypatch):
    """以真Runtime配額＋合成ffmpeg輸出驗取消，不呼叫外網或讀真錄音。"""
    import io,threading
    from app import audio_transcription as audio
    app,c,me,g,r,p=prepared;cancel=threading.Event()
    class Process:
        def __init__(self,*args,**kw):self.stdout=io.BytesIO(b'\0'*(16000*2*61))
        def poll(self):return 0
        def kill(self):pass
        def wait(self,timeout=None):return 0
    monkeypatch.setattr(audio.subprocess,'Popen',Process)
    original=p.generate;p.text='{"text":"合成片段"}'
    def generate(*args):
        result=original(*args);cancel.set();return result
    p.generate=generate
    with pytest.raises(Exception) as e:audio.transcribe(r,me['owner_id'],io.BytesIO(b'RIFFsynthetic'),'audio/wav',100,cancel,'cancel-job')
    assert e.value.code=='media_cancelled' and len(p.calls)==1
    assert r.usage(me['owner_id'])['reserved_microusd']==100
    with pytest.raises(Exception) as e:r.begin_media_work(me['owner_id'],hashlib.sha256(b'RIFFsynthetic').hexdigest(),'cancel-job')
    assert e.value.code=='ai_request_already_reserved'
