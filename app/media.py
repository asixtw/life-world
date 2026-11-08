"""供應商中立的素材辨識邊界；不保存素材、不寫正式經歷或帳本。"""
from hashlib import sha256
from io import BytesIO
from pathlib import PurePath
from typing import Protocol
import warnings
import wave

from PIL import Image, UnidentifiedImageError
from starlette.responses import JSONResponse

from .errors import DomainError, require


IMAGE_TYPES = {'image/png': 'PNG', 'image/jpeg': 'JPEG'}
AUDIO_TYPES = ('audio/wav', 'audio/x-wav', 'audio/webm', 'audio/ogg', 'audio/mp4', 'audio/mpeg')


class MediaBodyLimit:
    """在 multipart 解析／暫存前限制總量，包含未提供 Content-Length 的串流。"""
    def __init__(self, app, max_bytes):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'] != '/api/media/recognize':
            return await self.app(scope, receive, send)
        size = 0
        started = False
        exceeded = False
        rejected = False
        from starlette.exceptions import HTTPException
        class UploadLimitExceeded(HTTPException):
            def __init__(self):
                super().__init__(413, "素材超過目前傳輸容量；原素材仍保留於此裝置。")

        async def bounded_receive():
            nonlocal size, exceeded
            message = await receive()
            if message['type'] == 'http.request':
                size += len(message.get('body', b''))
                if size > self.max_bytes:
                    exceeded = True
                    raise UploadLimitExceeded()
            return message

        async def tracked_send(message):
            nonlocal started, rejected
            if exceeded:
                # Starlette 可能先處理 HTTPException；統一保留既有 API 錯誤契約。
                if not rejected:
                    rejected = True
                    await JSONResponse({'error': {'code': 'upload_too_large',
                        'message': '素材超過目前傳輸容量；原素材仍保留於此裝置。'}}, status_code=413)(scope, receive, send)
                return
            if message['type'] == 'http.response.start':
                started = True
            await send(message)

        try:
            # 逐段傳入 multipart parser，讓 UploadFile 自行 spooling；不複製整個音檔到 RAM。
            return await self.app(scope, bounded_receive, tracked_send)
        except UploadLimitExceeded:
            if started:
                raise
            response = JSONResponse({'error': {'code': 'upload_too_large',
                'message': '素材超過目前傳輸容量；原始素材仍保留於此裝置。'}}, status_code=413)
            return await response(scope, receive, send)


class MediaProvider(Protocol):
    """實際供應商由組裝層注入；回傳原始辨識文字，不能自行更新資料。"""
    def extract(self, *, kind: str, mime: str, content: bytes) -> str:
        ...


def validate_media(kind, filename, mime, content, max_bytes):
    """限制傳輸量及檔案類型；副檔名與客戶端 MIME 都不能單獨作信任依據。"""
    require(bool(filename) and len(filename) <= 200 and '\\' not in filename
            and PurePath(filename).name == filename, 422, 'invalid_filename', '請使用不含路徑的檔名。')
    require(bool(content), 422, 'empty_upload', '素材不可為空。')
    require(len(content) <= max_bytes, 413, 'upload_too_large', '素材超過目前本機傳輸上限。')
    mime = (mime or '').split(';')[0].strip().lower()
    if kind != 'audio':
        require(mime in IMAGE_TYPES, 415, 'unsupported_media', '圖片及名片目前支援 PNG、JPEG。')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as image:
                    if image.format != IMAGE_TYPES[mime] or image.width * image.height > 16000000:
                        raise ValueError('Invalid image')
                    image.verify()
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
                Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise DomainError(415, 'invalid_image', '圖片格式不符或已損毀，請重新選取。')
    else:
        require(mime in AUDIO_TYPES, 415, 'unsupported_media', '請選取 WAV、WebM、Ogg、MP4 或 MP3 音訊。')
        # 容器識別不是完整解碼；正式供應商仍須驗證音軌、時長及可解碼性。
        valid = ((mime == 'audio/webm' and content.startswith(b'\x1aE\xdf\xa3'))
                 or (mime == 'audio/ogg' and content.startswith(b'OggS'))
                 or (mime == 'audio/mp4' and content[4:8] == b'ftyp')
                 or (mime == 'audio/mpeg' and (content.startswith(b'ID3')
                     or (len(content) > 1 and content[0] == 255 and content[1] & 224 == 224))))
        if mime in ('audio/wav', 'audio/x-wav'):
            try:
                with wave.open(BytesIO(content), 'rb') as audio:
                    valid = audio.getnframes() > 0 and bool(audio.readframes(1))
            except (wave.Error, EOFError):
                valid = False
        require(valid, 415, 'invalid_audio', '音訊格式不符或已損毀，原素材仍保留在此裝置。')
    return mime


def recognize(provider, kind, mime, content):
    """隔離供應商錯誤與敏感訊息，只將有限長度的候選文字交回人工校對。"""
    require(provider is not None, 503, 'media_provider_unavailable',
            '尚未設定辨識服務。素材仍在此裝置，可手動輸入或稍後重試。')
    try:
        text = provider.extract(kind=kind, mime=mime, content=content)
        if not isinstance(text, str) or not text.strip() or len(text) > 20000:
            raise ValueError('Invalid recognition output')
    except Exception:
        raise DomainError(502, 'media_recognition_failed', '辨識未完成。請保留素材、重試或手動校對。')
    return {'text': text, 'applied': False, 'server_retention': 'none',
            'source': {'kind': kind, 'mime': mime, 'size': len(content), 'sha256': sha256(content).hexdigest()}}
