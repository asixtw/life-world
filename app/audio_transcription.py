"""上傳音訊安全暫存與逐段辨識；原素材仍在客戶端，候選不寫正式經歷。"""
import hashlib,io,os,subprocess,tempfile,threading,time,wave
from .errors import DomainError,require

_LOCK=threading.Lock()


def pcm_segments(stream):
    """逐次讀取最多30秒PCM；保留不足一段的尾端，不累積整段解碼內容。"""
    limit=16000*2*30
    while True:
        block=bytearray()
        while len(block)<limit:
            part=stream.read(limit-len(block))
            if not part:break
            block.extend(part)
        if not block:break
        out=io.BytesIO()
        with wave.open(out,'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(block)
        yield out.getvalue()


def transcribe(runtime,owner,file,mime,max_bytes,cancelled,request_id=None):
    """有界暫存後用ffmpeg解碼；每段各自預留預算，取消後不新增模型呼叫。"""
    runtime.authorize(owner)
    require(runtime.enabled,503,'ai_not_configured','辨識服務尚未設定；素材仍保留。')
    require(_LOCK.acquire(blocking=False),429,'media_busy','目前有音訊正在辨識，請稍後重試；素材保留。')
    process=None;timer=None
    try:
        with tempfile.TemporaryDirectory(prefix='lw-audio-') as directory:
            os.chmod(directory,0o700);path=os.path.join(directory,'source')
            digest=hashlib.sha256();size=0
            with open(path,'wb') as target:
                os.chmod(path,0o600)
                while chunk:=file.read(65536):
                    size+=len(chunk);require(size<=max_bytes,413,'upload_too_large','音訊超過傳輸容量；素材仍保留。')
                    digest.update(chunk);target.write(chunk)
            require(size>0,422,'empty_upload','素材不可為空。')
            # 固定本機檔案、協定白名單及單音軌；不接受URL或shell參數。
            try:
                process=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-i',path,'-map','0:a:0','-vn','-ac','1','-ar','16000','-f','s16le','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            except OSError:
                raise DomainError(503,'audio_decoder_unavailable','音訊解碼服務尚未就緒；素材仍保留。') from None
            # 容量/工作逾時是系統保護，不按錄音時長或日轉錄次數收費。
            timer=threading.Timer(240,process.kill);timer.start();started=time.monotonic()
            texts=[];receipts=[];work=None
            for chunk in pcm_segments(process.stdout):
                require(not cancelled.is_set(),499,'media_cancelled','辨識已取消；素材仍保留。')
                require(time.monotonic()-started<240,504,'media_recognition_timeout','辨識逾時；素材保留，可分段重試。')
                # 首段通過取消檢查才啟動工作；後續片段只扣成本，不重複扣工作次數。
                if work is None and hasattr(runtime,'begin_media_work'):work=runtime.begin_media_work(owner,digest.hexdigest(),request_id)
                if work is None:result=runtime.recognize(owner,'audio','audio/wav',chunk)
                else:result=runtime.recognize(owner,'audio','audio/wav',chunk,media_work=work,request_id=work[3]+':'+str(len(receipts)))
                texts.append(result['text']);receipts.append({'request_id':result.get('request_id'),'usage':result.get('usage')})
                require(sum(map(len,texts))<=20000,413,'transcript_review_capacity','校對文字超過目前單筆經歷容量；原音檔保留，請分段整理。')
            require(process.wait(timeout=5)==0 and bool(texts),415,'invalid_audio','無法解碼音軌；素材仍保留。')
            return {'text':'\n'.join(texts),'applied':False,'server_retention':'none','request_ids':receipts,'notice':'真實模型逐段轉錄，請校對後人工確認。','source':{'kind':'audio','mime':mime,'size':size,'sha256':digest.hexdigest()}}
    finally:
        if timer:timer.cancel()
        if process:
            if process.poll() is None:process.kill()
            process.wait()
            if process.stdout:process.stdout.close()
        _LOCK.release()
