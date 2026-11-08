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
