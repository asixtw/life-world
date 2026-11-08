"""長音訊分段邊界：只用合成PCM，不連線Gemini。"""
import io,wave
from app.audio_transcription import pcm_segments


def test_stream_segments_are_bounded_and_preserve_tail():
    raw=b'\0\1'*(16000*61)
    class Bounded(io.BytesIO):
        def read(self,n=-1):
            assert 0<n<=960000
            return super().read(min(n,17003))
    chunks=list(pcm_segments(Bounded(raw)))
    assert len(chunks)==3
    decoded=[]
    for data in chunks:
        with wave.open(io.BytesIO(data),'rb') as w:
            assert w.getframerate()==16000 and w.getnchannels()==1
            decoded.append(w.readframes(w.getnframes()))
    assert b''.join(decoded)==raw


def test_cancel_stops_before_provider_and_removes_temp(monkeypatch):
    import threading,os
    import pytest
    from app import audio_transcription as audio
    paths=[]
    class Process:
        def __init__(self,args,**kwargs):
            paths.append(args[args.index('-i')+1]);self.stdout=io.BytesIO(b'\0'*32000);self.done=False
        def poll(self):return 0 if self.done else None
        def kill(self):self.done=True
        def wait(self,timeout=None):self.done=True;return 0
    class Runtime:
        enabled=True
        def authorize(self,owner):pass
        def recognize(self,*args):raise AssertionError('cancelled audio must not call provider')
    monkeypatch.setattr(audio.subprocess,'Popen',Process)
    cancel=threading.Event();cancel.set()
    with pytest.raises(Exception) as exc:audio.transcribe(Runtime(),'synthetic-owner',io.BytesIO(b'RIFFsynthetic'),'audio/wav',100,cancel)
    assert exc.value.code=='media_cancelled'
    assert paths and not os.path.exists(paths[0])


def test_failed_provider_keeps_original_upload_and_allows_retry(monkeypatch):
    import threading
    import pytest
    from app import audio_transcription as audio
    class Process:
        def __init__(self,*args,**kwargs):self.stdout=io.BytesIO(b'\0'*32000)
        def poll(self):return 0
        def kill(self):pass
        def wait(self,timeout=None):return 0
    class Runtime:
        enabled=True
        calls=0
        def authorize(self,owner):pass
        def recognize(self,*args):
            self.calls+=1
            if self.calls==1:raise audio.DomainError(502,'provider_failed','synthetic failure')
            return {'text':'合成重試結果','request_id':'synthetic-only','usage':None}
    monkeypatch.setattr(audio.subprocess,'Popen',Process)
    source=io.BytesIO(b'RIFFsynthetic');r=Runtime()
    with pytest.raises(Exception):audio.transcribe(r,'synthetic',source,'audio/wav',100,threading.Event())
    assert source.getvalue()==b'RIFFsynthetic'
    source.seek(0)
    result=audio.transcribe(r,'synthetic',source,'audio/wav',100,threading.Event())
    assert result['text']=='合成重試結果' and result['applied'] is False
