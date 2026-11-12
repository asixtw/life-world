"""HTTP adapter; domain writes live in service.py, not in browser storage."""  # 說明此模組的責任與實作邊界
from pathlib import Path  # 以跨平台方式組合檔案路徑
from datetime import date  # 解析日曆查詢的實際日期。
from contextlib import asynccontextmanager
from dataclasses import replace
from threading import Lock
import logging  # 記錄服務錯誤類型而不輸出敏感本文
import os  # 讀取資料目錄或測試網址等環境設定
from typing import Literal, Optional  # 宣告可選欄位、清單與受限字串型別

from fastapi import FastAPI, Request, UploadFile, File, Query, Form  # 建立 HTTP API、請求與上傳欄位
from starlette.concurrency import run_in_threadpool
import asyncio
from fastapi.exceptions import RequestValidationError  # 捕捉輸入驗證錯誤
from fastapi.responses import FileResponse, JSONResponse, Response  # 建立 JSON、圖片與首頁回應
from fastapi.staticfiles import StaticFiles  # 提供前端靜態資源
from starlette.middleware.trustedhost import TrustedHostMiddleware  # 限制此本機服務接受的主機名稱

from .config import DemoPolicy  # 載入本機開發設定
from .db import Database  # 載入 SQLite 交易與遷移管理器
from .runtime import RuntimeSettings
from .security import require_registered
from .errors import DomainError, require  # 共用領域錯誤與條件檢查
from . import relation_sources
from . import schemas  # 載入此模組需要的相依工具
from .service import LifeWorld  # 載入負責原子交易的領域服務
from . import media
from .auth_rate_limit import AuthRateLimiter, AlphaDatabase, AlphaBodyLimit, protection_unavailable

logger = logging.getLogger(__name__)  # 準備只記錄錯誤類型與路徑的紀錄器


def create_app(data_dir=None, policy=None, clock=None, database=None, settings=None, iap_verifier=None, google_verifier=None):  # PG factory 不執行 DDL
    settings = settings or getattr(database, 'settings', None) or RuntimeSettings.from_env()
    # 尚未通過資料Gate的公開候選不掛載或啟動任何AI／建帳流程。
    if settings.public_gate_closed and (os.environ.get('LIFEWORLD_AI_CALLS_APPROVED')=='true' or os.environ.get('LIFEWORLD_AI_API_KEY') or os.environ.get('LIFEWORLD_TEST_ACCOUNT_SEED')):
        raise ValueError('Closed public gate must not mount private AI/account credentials')
    policy = policy or DemoPolicy()
    if settings.secure_cookies:
        policy = replace(policy, secure_cookies=True)
    data_dir = data_dir or os.environ.get('LIFEWORLD_DATA_DIR') or Path(__file__).resolve().parent.parent / 'data'  # 準備本次 App 使用的資料目錄
    if database is None and settings.backend == 'postgresql':
        from .postgres import PostgresDatabase
        database = PostgresDatabase(settings)
    service = LifeWorld(database or Database(data_dir), policy, clock)
    limiter=AuthRateLimiter(settings,service.now)
    limiter.backend=service.db.backend
    if settings.access_mode=='public_alpha':service.db=AlphaDatabase(service.db,limiter)
    lifespan_lock, active_lifespans = Lock(), 0

    @asynccontextmanager
    async def lifespan(app):
        nonlocal active_lifespans
        with lifespan_lock:
            active_lifespans += 1
        try:
            yield
        finally:
            with lifespan_lock:
                active_lifespans -= 1
                if active_lifespans == 0:
                    service.db.close()

    app = FastAPI(title='Life World Local API', version='0.4.0', description='本機開發版；開發設定不是正式產品規則。', lifespan=lifespan)
    if settings.auth_source_mode=='iap':
        from .iap import IAPVerifier
        app.state.iap_verifier=iap_verifier or IAPVerifier()
    app.state.external_auth = None
    if settings.google_client_id:
        from .google_identity import GoogleVerifier
        from .external_auth import ExternalAuth
        app.state.external_auth = ExternalAuth(service,google_verifier or GoogleVerifier(settings.google_client_id),limiter)
    app.state.settings = settings
    if os.environ.get('LIFEWORLD_TEST_ACCOUNT_SEED'):
        import json
        from .test_account import provision
        provision(service,settings,json.loads(os.environ['LIFEWORLD_TEST_ACCOUNT_SEED']))
    if settings.relation_source_store:
        if settings.relation_source_store not in ('legacy_jsonb','link_table'):
            raise ValueError('Unknown relation source store')
        service.relation_source_store = settings.relation_source_store
    app.state.service = service  # 保存「app.state.service」供後續驗證或回傳使用
    app.state.media_provider = None  # 未選供應商時不假裝辨識成功，也不接觸正式資料。
    from .ai_routes import install as install_ai_routes
    from .relationship_memory import install as install_memory
    install_memory(app)
    install_ai_routes(app)  # 保留既有GIS/IAP邊界；僅組裝預設停用的AI候選。
    audio_max_bytes=int(os.environ.get('LIFEWORLD_AUDIO_MAX_BYTES',str(policy.max_upload_bytes)))
    if not 1<=audio_max_bytes<=64*1024*1024:raise ValueError('Audio capacity must be bounded to 64MiB')
    app.add_middleware(media.MediaBodyLimit, max_bytes=max(policy.max_upload_bytes,audio_max_bytes) + 65536,
                       evidence_max_bytes=policy.max_upload_bytes + 65536)
    if settings.access_mode=='public_alpha':app.add_middleware(AlphaBodyLimit)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.trusted_hosts))

    @app.exception_handler(DomainError)  # 註冊此 HTTP 路由、例外處理器或中介層
    async def domain_error(request, exc):  # 將領域錯誤轉成一致的 HTTP 回應
        return JSONResponse({'error': {'code': exc.code, 'message': exc.message}}, status_code=exc.status,headers=getattr(exc,'headers',None))  # 回傳將領域錯誤轉成一致的 HTTP 回應的結果

    @app.exception_handler(RequestValidationError)  # 註冊此 HTTP 路由、例外處理器或中介層
    async def validation_error(request, exc):  # 回報欄位格式錯誤，避免回傳密碼與原文
        # Never echo passwords or sensitive raw payloads through Pydantic input fields.
        fields = ['.'.join(str(p) for p in e['loc'][1:]) for e in exc.errors()]  # 只回傳錯誤欄位路徑，不把密碼或經歷原文回顯到錯誤內容
        return JSONResponse({'error': {'code': 'validation_error', 'message': '請檢查欄位內容與格式。', 'fields': fields}}, status_code=422)  # 回傳回報欄位格式錯誤，避免回傳密碼與原文的結果

    @app.exception_handler(Exception)  # 註冊此 HTTP 路由、例外處理器或中介層
    async def internal_error(request, exc):  # 記錄錯誤類型並回覆可重試訊息
        logger.error('Operation failed: %s %s (%s)', request.method, request.url.path, type(exc).__name__)  # 執行此模組的共用工具操作
        return JSONResponse({'error': {'code': 'internal_error', 'message': '操作未完成，請保留目前內容並重試。'}}, status_code=500)  # 回傳記錄錯誤類型並回覆可重試訊息的結果

    @app.middleware('http')  # 註冊此 HTTP 路由、例外處理器或中介層
    async def security_headers(request, call_next):  # 檢查寫入來源並加入安全與快取標頭
        if settings.public_gate_closed:
            # 在限流、身分或業務處理之前封閉，確保公開請求不會連接DB。
            safe=request.method in ('GET','HEAD') and (request.url.path in ('/','/intro','/intro/','/health','/ready','/api/health','/api/capabilities') or request.url.path.startswith('/static/'))
            if request.url.path=='/api/auth/me' and request.method=='GET':
                return JSONResponse({'error':{'code':'unauthenticated','message':'尚未登入。'}},status_code=401,headers={'Cache-Control':'no-store'})
            if not safe:
                # 尚未登入的私人API回401；登入建立入口則明示環境Gate尚未完成。
                private_api=request.url.path.startswith('/api/') and not request.url.path.startswith('/api/auth/')
                return JSONResponse({'error':{'code':'unauthenticated' if private_api else 'release_gate_closed','message':'私人世界尚待資料保存與登入驗收，暫不接受資料或AI操作。'}},status_code=401 if private_api else 503,headers={'Cache-Control':'no-store'})
        # IAP只保護入口，App仍須原有Session／CSRF；只有GET/HEAD健康探針豁免。
        if settings.auth_source_mode=='iap' and not (request.method in ('GET','HEAD') and request.url.path in ('/health','/ready')):
            tokens=request.headers.getlist('x-goog-iap-jwt-assertion')
            try:
                from .iap import denied
                if len(tokens)!=1:raise denied()
                request.state.lw_iap_subject=await run_in_threadpool(app.state.iap_verifier.verify,tokens[0])
            except DomainError as exc:
                return JSONResponse({'error':{'code':exc.code,'message':exc.message}},status_code=exc.status,headers={'Cache-Control':'no-store'})
        # 登入／註冊管道由明確政策控制，Google只是其中一種身分來源。
        if request.url.path=='/api/auth/claim' and not settings.registration_enabled:
            return JSONResponse({'error':{'code':'registration_unavailable','message':'目前未開放一般帳密註冊，訪客仍可繼續。'}},status_code=403,headers={'Cache-Control':'no-store'})
        if request.url.path=='/api/auth/login' and not settings.password_login_available:
            return JSONResponse({'error':{'code':'password_login_unavailable','message':'帳密登入尚未啟用，請使用已開放的登入方式。'}},status_code=403,headers={'Cache-Control':'no-store'})
        if settings.access_mode=='public_alpha' and request.method not in ('GET','HEAD','OPTIONS'):
            blocked=request.url.path=='/api/auth/claim'
            blocked=blocked or (request.url.path=='/api/auth/login' and not (settings.alpha_login_enabled or settings.test_login_usernames))
            if blocked:
                return JSONResponse({'error':{'code':'alpha_feature_unavailable','message':'本輪Alpha尚未開放此功能；帳號登入需由管理者啟用。'}},status_code=403,headers={'Cache-Control':'no-store'})
        if request.url.path=='/api/media/recognize' and request.method=='POST':
            try:
                media_user,_=service.session(request.cookies.get('lw_session'),request.headers.get('X-CSRF-Token'),True)
                require_registered(media_user)
            except DomainError as exc:
                return JSONResponse({'error':{'code':exc.code,'message':exc.message}},status_code=exc.status,headers={'Cache-Control':'no-store'})
        if settings.access_mode=='public_alpha' and request.method in ('POST','PUT','PATCH','DELETE') and request.url.path.startswith('/api/') and not request.url.path.startswith('/api/auth/'):
            try:
                source=limiter.source(request)
                def source_write_gate():
                    with service.db.connect(write=True) as c:
                        return limiter.take(c,'alpha_owner_writes',('v2:global-write' if settings.auth_source_mode=='shared' else 'source-write:'+source),max(settings.alpha_source_writes,settings.alpha_global_writes) if settings.auth_source_mode=='shared' else settings.alpha_source_writes,3600)
                error=await run_in_threadpool(source_write_gate)
                if error:raise error
            except DomainError as exc:
                return JSONResponse({'error':{'code':exc.code,'message':exc.message}},status_code=exc.status,headers=getattr(exc,'headers',{'Cache-Control':'no-store'}))
        # 未核准的 Cloud Run revision 只供健康／連線驗證，不接業務讀寫。
        if not settings.business_enabled and not settings.public_gate_closed and request.url.path not in ('/health', '/ready', '/api/health'):
            return JSONResponse({'error': {'code': 'business_api_disabled', 'message': '此服務尚未開放業務操作。'}}, status_code=503)
        if request.url.path == '/api/media/recognize':
            # 在 multipart 解析前限制一般已知長度請求，路由內另有串流讀取上限。
            length = request.headers.get('content-length', '')
            if length.isdigit() and int(length) > max(policy.max_upload_bytes,audio_max_bytes) + 65536:
                return JSONResponse({'error': {'code': 'upload_too_large', 'message': '素材超過目前本機傳輸上限。'}}, status_code=413)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):  # 依目前條件選擇下一步處理分支
            origin = request.headers.get('origin')  # 保存「origin」供後續驗證或回傳使用
            expected = settings.external_origin or str(request.base_url).rstrip('/')
            # Tag額外來源只授權同一個實際請求Host，不能跨允許來源送出寫入；OAuth仍只用external_origin。
            # Cloud Run在TLS終止後使用內部HTTP，不能依內部scheme判斷瀏覽器Origin，也不信任X-Forwarded-*。
            same_authority = not origin or origin.split('://', 1)[-1] == request.url.netloc
            allowed = (expected,) + settings.write_origins
            if origin and (origin not in allowed or (settings.write_origins and not same_authority)):
                return JSONResponse({'error': {'code': 'origin_rejected', 'message': '不允許跨來源寫入。'}}, status_code=403)  # 回傳檢查寫入來源並加入安全與快取標頭的結果
        response = await call_next(request)  # 保存「response」供後續驗證或回傳使用
        response.headers['X-Content-Type-Options'] = 'nosniff'  # 設定回應的安全或快取標頭
        response.headers['Referrer-Policy'] = 'same-origin'  # 設定回應的安全或快取標頭
        response.headers['X-Frame-Options'] = 'DENY'  # 設定回應的安全或快取標頭
        if request.url.path.startswith('/api/'):  # 依目前條件選擇下一步處理分支
            response.headers['Cache-Control'] = 'no-store'  # 設定回應的安全或快取標頭
        if request.url.path == '/':  # 依目前條件選擇下一步處理分支
            response.headers['Cache-Control'] = 'no-store'  # 設定回應的安全或快取標頭
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"  # Blob 音訊只供使用者主動試聽，不自動播放。
        if request.url.path=='/' and settings.google_client_id:
            # GIS需跨來源Origin Referer；只送Origin，不送私人路徑或查詢字串。
            response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
            csp=response.headers['Content-Security-Policy']
            csp=csp.replace("script-src 'self'","script-src 'self' https://accounts.google.com/gsi/client").replace("style-src 'self'","style-src 'self' 'sha256-RU4sU0AaS8IBGZx8XrGt/pa9A5SLA3dQszGeqT5L3Kw=' https://accounts.google.com/gsi/style").replace("connect-src 'self'","connect-src 'self' https://accounts.google.com/gsi/")
            response.headers['Content-Security-Policy']=csp+"; frame-src https://accounts.google.com/gsi/"
            response.headers['Cross-Origin-Opener-Policy']='same-origin-allow-popups'
        return response  # 回傳檢查寫入來源並加入安全與快取標頭的結果

    def current(request, write=False):  # 驗證目前工作階段，寫入時同時檢查 CSRF
        return service.session(request.cookies.get('lw_session'), request.headers.get('X-CSRF-Token'), write)[0]  # 回傳驗證目前工作階段，寫入時同時檢查 CSRF的結果

    @app.get('/api/media/capabilities', tags=['Media'])
    def media_capabilities(request: Request):
        """傳回實際可用能力與傳輸護欄，不把本機設定宣稱為正式素材政策。"""
        user = current(request)
        return {'recognition_available': user['status']=='registered' and (app.state.ai_runtime.enabled or app.state.media_provider is not None),
                'max_bytes': min(policy.max_upload_bytes,app.state.ai_runtime.settings.max_media_bytes) if app.state.ai_runtime.enabled else policy.max_upload_bytes, 'audio_max_bytes': audio_max_bytes, 'server_retention': 'none',
                'image_types': list(media.IMAGE_TYPES), 'audio_types': list(media.AUDIO_TYPES)}

    @app.post('/api/media/recognize', tags=['Media'])
    async def recognize_media(request: Request, file: UploadFile = File(...),
                              kind: Literal['audio', 'image', 'screenshot', 'card'] = Form(...)):
        """僅接受明確上傳；回應是候選文字，不建立人物、經歷、貢獻或獎勵。"""
        try:
            user = current(request, True)
            # 辨識屬登入功能；在provider呼叫前由後端拒絕Guest。
            require_registered(user)
            with service.db.connect() as connection:
                service._onboarded(connection, user['id'])
            if kind=='audio' and app.state.ai_runtime.enabled:
                mime=(file.content_type or '').split(';')[0].lower()
                require(mime in media.AUDIO_TYPES,415,'unsupported_media','請選取支援的音訊格式。')
                require(file.size is not None and 0<file.size<=audio_max_bytes,413,'upload_too_large','音訊超過傳輸容量；素材仍保留。')
                from .audio_transcription import transcribe
                from threading import Event
                cancelled=Event()
                async def watch_disconnect():
                    while True:
                        if await request.is_disconnected():cancelled.set();return
                        await asyncio.sleep(.25)
                watcher=asyncio.create_task(watch_disconnect())
                try:
                    return await run_in_threadpool(transcribe,app.state.ai_runtime,user['id'],file.file,mime,audio_max_bytes,cancelled,request.headers.get('Idempotency-Key'))
                finally:
                    cancelled.set();watcher.cancel()
            image_limit=min(policy.max_upload_bytes,app.state.ai_runtime.settings.max_media_bytes) if app.state.ai_runtime.enabled else policy.max_upload_bytes
            content = await file.read(image_limit + 1)
            mime = media.validate_media(kind, file.filename, file.content_type, content, image_limit)
            try:
                if app.state.ai_runtime.enabled:
                    return await asyncio.wait_for(run_in_threadpool(app.state.ai_runtime.recognize,user['id'],kind,mime,content,request_id=request.headers.get('Idempotency-Key')),timeout=30)
                return await asyncio.wait_for(run_in_threadpool(
                    media.recognize, app.state.media_provider, kind, mime, content), timeout=30)
            except asyncio.TimeoutError:
                raise DomainError(504, 'media_recognition_timeout', '辨識逾時。素材仍保留，請稍後重試。')
        finally:
            await file.close()  # multipart 暫存檔隨請求關閉，不另行保存素材。

    def cookie(response, token):  # 設定不可由 JavaScript 讀取的工作階段 Cookie
        response.set_cookie('lw_session', token, httponly=True, secure=policy.secure_cookies,
                            samesite='strict', path='/', max_age=policy.session_hours * 3600)  # 執行此模組的共用工具操作

    def external(request):
        # 入口必須由明確啟用的公開OAuth契約配置，沒有client即fail-closed。
        if app.state.external_auth is None:raise DomainError(503,'google_not_configured','Google登入尚未設定，訪客仍可繼續。')
        expected=settings.external_origin or str(request.base_url).rstrip('/')
        # GIS與一般寫入使用同一精確Tag白名單；仍必須有Origin，不變更Google audience或IAP audience。
        origin=request.headers.get('origin')
        same_authority=bool(origin) and origin.split('://',1)[-1]==request.url.netloc
        if origin not in ((expected,)+settings.write_origins) or (settings.write_origins and not same_authority):
            raise DomainError(403,'origin_rejected','請從本站重新開始登入。')
        try:
            with service.db.connect() as c:c.execute('SELECT provider,issuer,subject,owner_id,created_at FROM external_identities LIMIT 0')
        except Exception:raise DomainError(503,'google_schema_not_ready','Google登入尚未完成設定，訪客資料會保留。') from None
        return app.state.external_auth

    @app.post('/api/auth/external/challenge',tags=['Identity'])
    def google_challenge(request:Request,data:schemas.GoogleChallenge):
        return external(request).challenge(request.cookies.get('lw_session'),request.headers.get('X-CSRF-Token'),data.mode,data.discard_guest)

    @app.post('/api/auth/external/exchange',tags=['Identity'])
    def google_exchange(request:Request,response:Response,data:schemas.GoogleExchange):
        result,token,replayed=external(request).exchange(request.cookies.get('lw_session'),request.headers.get('X-CSRF-Token'),data.challenge_id,data.credential)
        if token:cookie(response,token)
        return {**result,'replayed':replayed}

    @app.post('/api/auth/external/status',tags=['Identity'])
    def google_exchange_status(request:Request,data:schemas.GoogleExchangeStatus):
        # 採同源POST與當前CSRF；只SELECT既有requests，不新增Schema或權限。
        return external(request).status(request.cookies.get('lw_session'),request.headers.get('X-CSRF-Token'),data.challenge_id)

    @app.get('/api/health', tags=['System'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def health():  # 回報本機服務的健康狀態
        return {'status': 'ok', 'mode': 'cloud-preparation' if settings.cloud_run else 'local-development'}

    @app.get('/health', tags=['System'])
    def process_health():
        return {'status': 'ok'}

    @app.get('/ready', tags=['System'])
    def readiness():
        if settings.public_gate_closed:
            return JSONResponse({'status':'unavailable','reason':'release_gates_pending'},status_code=503,headers={'Cache-Control':'no-store'})
        try:
            service.db.check_ready()
            if service.relation_source_store == relation_sources.LINK:
                # 明確啟用010時，缺必要表/權限即未就緒，禁止退回另一份來源權威。
                with service.db.connect() as c:
                    c.execute('SELECT connection_id,owner_id,experience_id,subject_experience_id,source_position FROM person_connection_experience_sources LIMIT 0')
                    c.execute('SELECT id,owner_id,status FROM subject_experiences LIMIT 0')
                    c.execute('SELECT subject_experience_id,owner_id,person_id,role FROM subject_experience_people LIMIT 0')
            limiter.ready(service.db)
            if app.state.feature_store is not None:
                with service.db.connect() as c:
                    c.execute('SELECT owner_id FROM relationship_features LIMIT 0')
                    c.execute('SELECT owner_id FROM relationship_memory_preferences LIMIT 0')
            if settings.google_client_id:
                with service.db.connect() as c:
                    c.execute('SELECT provider,issuer,subject,owner_id,created_at FROM external_identities LIMIT 0')
                    c.execute('SELECT owner_id,abandoned_at,purge_after,status,attempts,last_error_code,completed_at,media_state,media_attempts FROM guest_abandonments LIMIT 0')
        except Exception as exc:
            logger.warning('Readiness failed (%s)', type(exc).__name__)
            return JSONResponse({'status': 'unavailable'}, status_code=503, headers={'Cache-Control': 'no-store'})
        return JSONResponse({'status': 'ready'}, headers={'Cache-Control': 'no-store'})

    @app.get('/api/capabilities',tags=['Identity'])
    def capabilities():
        if settings.public_gate_closed:
            return {'access_mode':settings.access_mode,'public_gate_closed':True,'accounts_available':False,'password_login_available':False,'registration_available':False,'media_available':False,'google_login_available':False,'ai_available':False,'ai_status':'release_gates_pending','writes_available':False,'points':'accumulation_only','redemption_available':False}
        """公開模式說明不含憑證／內部資料；UI與後端共用範圍。"""
        alpha=settings.access_mode=='public_alpha'
        return {'access_mode':settings.access_mode,'accounts_available':settings.password_login_available,
                'password_login_available':settings.password_login_available,
                'registration_available':not alpha and settings.registration_enabled,
                'media_available':app.state.ai_runtime.enabled or app.state.media_provider is not None,
                'relationship_memory_available':app.state.feature_store is not None,
                'relation_sources':service.relation_source_store, 'unified_people':service.unified_people_available(),
                'google_login_available':bool(settings.google_client_id),'ai_available':app.state.ai_runtime.enabled,
                'ai_status':'configured_not_verified' if app.state.ai_runtime.enabled else 'not_configured','writes_available':settings.alpha_writes_enabled if alpha else True,
                'points':'accumulation_only','redemption_available':False}

    @app.post('/api/auth/guest', tags=['Identity'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def guest(request: Request, response: Response):  # 取得既有訪客身分或建立新的訪客世界
        try:
            result, token, created = service.guest(request.cookies.get('lw_session'),admission=lambda c:limiter.guest_admission(c,request))  # 取得既有訪客身分或建立新的訪客世界
        except DomainError:raise
        except Exception:raise protection_unavailable() from None
        response.status_code = 201 if created else 200  # 保存「response.status_code」供後續驗證或回傳使用
        if token:  # 依目前條件選擇下一步處理分支
            cookie(response, token)  # 設定不可由 JavaScript 讀取的工作階段 Cookie
        return result  # 回傳取得既有訪客身分或建立新的訪客世界的結果

    @app.get('/api/auth/me', tags=['Identity'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def me(request: Request):  # 回傳目前登入身分與 CSRF 代碼
        user, csrf = service.session(request.cookies.get('lw_session'))  # 核對登入期限，寫入操作另檢查 CSRF
        return service.public_user(user, csrf)  # 回傳回傳目前登入身分與 CSRF 代碼的結果

    @app.put('/api/profile', tags=['Identity'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def profile(request: Request, data: schemas.Profile):  # 保存個人介紹與時區
        return service.profile(current(request, True)['id'], data)  # 回傳保存個人介紹與時區的結果

    @app.post('/api/auth/claim', tags=['Identity'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def claim(request: Request, response: Response, data: schemas.Credentials):  # 將原訪客世界升級為本機帳號並輪換工作階段
        result, token = service.claim(current(request, True), data)  # 將原訪客世界升級為本機帳號並輪換工作階段
        cookie(response, token)  # 設定不可由 JavaScript 讀取的工作階段 Cookie
        return result  # 回傳將原訪客世界升級為本機帳號並輪換工作階段的結果

    @app.post('/api/auth/login', tags=['Identity'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def login(request: Request, response: Response, data: schemas.Login):  # 核對密碼並建立工作階段，不合併訪客資料
        if request.cookies.get('lw_session'):  # 依目前條件選擇下一步處理分支
            try:  # 保護可能失敗的操作，交由下方例外分支處理
                current(request, True)  # 驗證目前工作階段，寫入時同時檢查 CSRF
            except DomainError as exc:  # 處理此類預期例外並保留明確失敗結果
                if exc.status != 401:  # 依目前條件選擇下一步處理分支
                    raise  # 中止目前操作並向呼叫端傳遞錯誤
        try:
            result, token = service.login(data, request.cookies.get('lw_session'),limiter=limiter,request=request,registered_only=True,allowed_usernames=settings.test_login_usernames or None)  # 核對密碼並建立工作階段，不合併訪客資料
        except DomainError:raise
        except Exception:raise protection_unavailable() from None
        cookie(response, token)  # 設定不可由 JavaScript 讀取的工作階段 Cookie
        return result  # 回傳核對密碼並建立工作階段，不合併訪客資料的結果

    @app.post('/api/auth/logout', status_code=204, tags=['Identity'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def logout(request: Request):  # 撤銷目前工作階段
        current(request, True)  # 驗證目前工作階段，寫入時同時檢查 CSRF
        service.logout(request.cookies['lw_session'])  # 撤銷目前工作階段
        response = Response(status_code=204)  # 保存「response」供後續驗證或回傳使用
        response.delete_cookie('lw_session', path='/', secure=policy.secure_cookies, httponly=True, samesite='strict')  # 執行此模組的共用工具操作
        return response  # 回傳撤銷目前工作階段的結果

    @app.get('/api/state', tags=['World'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def state(request: Request):  # 組合目前帳號的世界資料與開發設定
        return service.state(current(request)['id'])  # 回傳組合目前帳號的世界資料與開發設定的結果

    @app.post('/api/goals', status_code=201, tags=['Goals'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def create_goal(request: Request, data: schemas.GoalCreate):  # 在同一交易建立目標、行動並孵化 Lumi
        return service.create_goal(current(request, True)['id'], data)  # 回傳在同一交易建立目標、行動並孵化 Lumi的結果

    @app.get('/api/goals/{goal_id}', tags=['Goals'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def get_goal(goal_id: str, request: Request):  # 讀取目前帳號可存取的目標
        return service.goal(current(request)['id'], goal_id)  # 回傳讀取目前帳號可存取的目標的結果

    @app.get('/api/goals/{goal_id}/dashboard', tags=['Goals'])
    def goal_dashboard(goal_id: str, request: Request):
        """只讀 owner 的目標儀表板，不更新進度或帳本。"""
        return service.goal_dashboard(current(request)['id'], goal_id)

    @app.get('/api/goals/{goal_id}/calendar', tags=['Goals'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def calendar(goal_id: str, request: Request, start: Optional[date] = None, end: Optional[date] = None):  # 依實際日期分頁查看安排。
        return service.calendar(current(request)['id'], goal_id, start, end)  # 不固定四週或 28 天。

    @app.post('/api/goals/{goal_id}/review', tags=['Goals'])  # 人工延長、結束與舊目標設定。
    def review_goal(goal_id: str, request: Request, data: schemas.GoalReview):  # 與版本和去重一起驗證。
        return service.review_goal(current(request, True)['id'], goal_id, data)  # 不自動宣告成果。

    @app.post('/api/goals/{goal_id}/pending/{pending_id}/accept', tags=['Goals'])  # 延長後逐筆採計。
    def accept_pending(goal_id: str, pending_id: str, request: Request, data: schemas.PendingAccept):  # 獨立於經歷確認交易。
        return service.accept_pending(current(request, True)['id'], goal_id, pending_id, data)  # 不重複發獎。

    @app.post('/api/experiences/drafts', status_code=201, tags=['Experiences'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def create_draft(request: Request, data: schemas.DraftCreate):  # 保存尚未確認、不計分的原始經歷草稿
        return service.create_draft(current(request, True)['id'], data)  # 回傳保存尚未確認、不計分的原始經歷草稿的結果

    @app.get('/api/drafts/{draft_id}', tags=['Experiences'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def get_draft(draft_id: str, request: Request):  # 取得經權限檢查的經歷草稿
        return service.draft(current(request)['id'], draft_id)  # 回傳取得經權限檢查的經歷草稿的結果

    @app.put('/api/drafts/{draft_id}', tags=['Experiences'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def edit_draft(draft_id: str, request: Request, data: schemas.DraftEdit):  # 檢查版本後更新尚未確認的草稿
        return service.edit_draft(current(request, True)['id'], draft_id, data)  # 回傳檢查版本後更新尚未確認的草稿的結果

    @app.post('/api/drafts/{draft_id}/suggest', tags=['Experiences'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def suggest(draft_id: str, request: Request):  # 建立可手動審閱的整理候選，不寫入正式事實
        who=current(request,True)['id']
        if app.state.ai_runtime.enabled:
            app.state.ai_runtime.authorize(who)
            source=service.draft(who,draft_id)
            require(source['status']=='draft',409,'already_confirmed','這份草稿已經確認。')
            # 舊客戶端可省略；新版明確綁定讀取版本，衝突發生在預留與模型之前。
            expected=request.headers.get('X-Draft-Revision')
            if expected is not None:
                require(expected.isascii() and expected.isdecimal() and len(expected)<=10 and int(expected)>0,422,'invalid_draft_revision','草稿版本格式不正確。')
                require(int(expected)==source['revision'],409,'source_revision_conflict','草稿已在其他畫面修改，請重新讀取並核對。')
            app.state.draft_ai_consent.require(who)  # 授權檢查在預留額度與傳送原文之前。
            result=app.state.ai_runtime.generate(who,'experience',{'raw_text':source['raw_text']},request_id=request.headers.get('Idempotency-Key'))
            return {**result,'source_revision':source['revision'],'source_sha256':source['raw_sha256']}
        return service.suggest(who,draft_id)  # 未啟用模型時仍明示原文候選。

    @app.delete('/api/drafts/{draft_id}', tags=['Experiences'])
    def delete_saved_draft(draft_id: str, request: Request, data: schemas.DraftDelete):
        """刪除已保存草稿與捨棄本機修改分開，沿用寫入CSRF/Owner驗證。"""
        return service.delete_draft(current(request, True)['id'], draft_id, data)

    @app.post('/api/drafts/{draft_id}/confirm', status_code=201, tags=['Experiences'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def confirm(draft_id: str, request: Request, data: schemas.Confirm):  # 以單一交易保存經歷、貢獻、人物更新與一次積分
        return service.confirm(current(request, True)['id'], draft_id, data)  # 回傳以單一交易保存經歷、貢獻、人物更新與一次積分的結果

    @app.get('/api/persons', tags=['Persons'])  # Unified Person：搜尋、篩選與排序
    def persons(request: Request, q: str = Query('', max_length=200), person_type: Literal['', 'real', 'fictional'] = '',
                person_subtype: Literal['', 'historical', 'original'] = '', category: Literal['', 'business', 'life', 'learning', 'other'] = '',
                status: Literal['active', 'archived'] = 'active', sort: Literal['recent', 'name'] = 'recent',
                limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        return service.persons_list(current(request)['id'], q, person_type, person_subtype, category, status, sort, limit, offset)

    @app.post('/api/persons', status_code=201, tags=['Persons'])  # Unified Person：新增（同名可並存）
    def create_unified_person(request: Request, data: schemas.PersonsCreate):
        return service.create_unified_person(current(request, True)['id'], data)

    @app.get('/api/persons/{person_id}', tags=['Persons'])  # 人物詳細：基本資料、人物設定、關係與經歷摘要
    def unified_person(person_id: str, request: Request):
        return service.unified_person(current(request)['id'], person_id)

    @app.patch('/api/persons/{person_id}', tags=['Persons'])  # 編輯基本資料（revision 防覆蓋）
    def edit_unified_person(person_id: str, request: Request, data: schemas.PersonsEdit):
        return service.edit_unified_person(current(request, True)['id'], person_id, data)

    @app.post('/api/persons/{person_id}/status', tags=['Persons'])  # 封存或恢復（不刪除）
    def set_unified_person_status(person_id: str, request: Request, data: schemas.PersonsStatus):
        return service.set_unified_person_status(current(request, True)['id'], person_id, data)

    @app.get('/api/persons/{person_id}/connection-sources', tags=['Persons'])  # 可引用為關係來源的我的紀錄（與兩端至少一人有關）
    def person_connection_sources(person_id: str, request: Request, other_person_id: str = Query(..., min_length=1, max_length=128)):
        return service.connection_sources(current(request)['id'], person_id, other_person_id)

    # 九項角色設定不在核准範圍：不註冊寫入入口，歷史版本讀取與資料保持相容。

    @app.get('/api/persons/{person_id}/experiences', tags=['Persons'])  # 人物頁「經歷」分頁：我的紀錄與人物經歷兩區
    def person_experience_lists(person_id: str, request: Request, archived: bool = False):
        return service.person_experience_lists(current(request)['id'], person_id, archived)

    @app.get('/api/person-experiences', tags=['Persons'])  # 紀錄頁：本人帳號的全部人物經歷（archived=true 列出已封存的）
    def person_experiences_list(request: Request, archived: bool = False, limit: int = Query(200, ge=1, le=200), offset: int = Query(0, ge=0)):
        return service.person_experiences_list(current(request)['id'], archived, limit, offset)

    @app.post('/api/person-experiences', status_code=201, tags=['Persons'])  # 新增人物經歷（不計積分、目標與互動統計）
    def create_person_experience(request: Request, data: schemas.PersonExperienceCreate):
        return service.create_person_experience(current(request, True)['id'], data)

    @app.get('/api/person-experiences/{experience_id}', tags=['Persons'])  # 讀單一人物經歷
    def person_experience(experience_id: str, request: Request):
        return service.person_experience(current(request)['id'], experience_id)

    @app.patch('/api/person-experiences/{experience_id}', tags=['Persons'])  # 編輯、封存或恢復（revision 防覆蓋）
    def patch_person_experience(experience_id: str, request: Request, data: schemas.PersonExperiencePatch):
        return service.patch_person_experience(current(request, True)['id'], experience_id, data)


    @app.get('/api/connections/{connection_id}', tags=['Connections'])  # 010：讀單一關係（來源為兩個 ID 陣列）
    def get_connection(connection_id: str, request: Request):
        return service.get_connection(current(request)['id'], connection_id)

    @app.patch('/api/connections/{connection_id}', tags=['Connections'])  # 010：編輯說明與來源（Migration 010 後開放）
    def patch_connection(connection_id: str, request: Request, data: schemas.ConnectionPatch):
        return service.patch_connection(current(request, True)['id'], connection_id, data)


    @app.get('/api/people/{person_id}/details', tags=['People'])
    def person_basic_details(person_id: str, request: Request):
        return service.person_details(current(request)['id'], person_id)

    @app.patch('/api/people/{person_id}/basic-details', tags=['People'])
    def update_basic_details(person_id: str, request: Request, data: schemas.BirthdayWrite):
        return service.write_person_details(current(request, True)['id'], person_id, data, 'birthday')

    @app.post('/api/people/{person_id}/employments', status_code=201, tags=['People'])
    def create_employment(person_id: str, request: Request, data: schemas.EmploymentCreate):
        return service.write_person_details(current(request, True)['id'], person_id, data, 'employment')

    @app.patch('/api/people/{person_id}/employments/{employment_id}', tags=['People'])
    def update_employment(person_id: str, employment_id: str, request: Request, data: schemas.EmploymentPatch):
        return service.write_person_details(current(request, True)['id'], person_id, data, 'employment', employment_id)

    @app.post('/api/people/{person_id}/basic-details/source-withdrawal', tags=['People'])
    def withdraw_birthday_source(person_id: str, request: Request, data: schemas.PersonDetailSourceWithdrawal):
        return service.withdraw_person_detail_source(current(request, True)['id'], person_id, data, 'birthday')

    @app.post('/api/people/{person_id}/employments/{employment_id}/source-withdrawal', tags=['People'])
    def withdraw_employment_source(person_id: str, employment_id: str, request: Request, data: schemas.PersonDetailSourceWithdrawal):
        return service.withdraw_person_detail_source(current(request, True)['id'], person_id, data, 'employment', employment_id)

    @app.post('/api/people', status_code=201, tags=['People'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def create_person(request: Request, data: schemas.PersonCreate):  # 建立人物並保留舊角色欄位的相容性
        return service.create_person(current(request, True)['id'], data)  # 回傳建立人物並保留舊角色欄位的相容性的結果

    @app.get('/api/people', tags=['People'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def people(request: Request, q: str = Query('', max_length=200),
               category: Literal['', 'business', 'life', 'learning', 'other'] = '', followed_only: bool = False,
               sort: Literal['priority', 'recent', 'name'] = 'priority',
               limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):  # 查詢人物並套用篩選、排序與分頁
        return service.people_list(current(request)['id'], q, category, followed_only, sort, limit, offset)  # 回傳查詢人物並套用篩選、排序與分頁的結果

    @app.patch('/api/people/{person_id}', tags=['People'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def edit_person(person_id: str, request: Request, data: schemas.PersonEdit):  # 檢查版本後更新使用者明確送出的欄位
        return service.edit_person(current(request, True)['id'], person_id, data)  # 回傳檢查版本後更新使用者明確送出的欄位的結果

    @app.get('/api/people/{person_id}/overview', tags=['People'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def person_overview(person_id: str, request: Request):  # 組合人物三分頁需要的事實、來源與互動資料
        return service.person_overview(current(request)['id'], person_id)  # 回傳組合人物三分頁需要的事實、來源與互動資料的結果

    @app.get('/api/people/{person_id}/interactions', tags=['People'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def interactions(person_id: str, request: Request, kind: Optional[Literal['in_person', 'call', 'message', 'other', 'unknown']] = None):  # 列出人物互動事件，可依類型篩選
        return service.interactions(current(request)['id'], person_id, kind)  # 回傳列出人物互動事件，可依類型篩選的結果

    @app.post('/api/people/{person_id}/facts', status_code=201, tags=['People'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def create_fact(person_id: str, request: Request, data: schemas.FactCreate):  # 明確確認來源後新增人物資訊，支援重送去重
        return service.create_fact(current(request, True)['id'], person_id, data)  # 回傳明確確認來源後新增人物資訊，支援重送去重的結果

    @app.get('/api/people/{person_id}/facts/{fact_id}/evidence', tags=['People'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def fact_evidence(person_id: str, fact_id: str, request: Request):  # 回傳指定人物資訊與有效來源經歷
        return service.fact_evidence(current(request)['id'], person_id, fact_id)  # 回傳回傳指定人物資訊與有效來源經歷的結果

    @app.post('/api/people/{person_id}/facts/{fact_id}/resolve', tags=['People'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def resolve_fact(person_id: str, fact_id: str, request: Request, data: schemas.Revision):  # 人工採用一項資訊並封存同組衝突項
        return service.resolve_fact(current(request, True)['id'], person_id, fact_id, data)  # 回傳人工採用一項資訊並封存同組衝突項的結果

    @app.post('/api/people/{person_id}/facts/{fact_id}/sources/revoke', tags=['People'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def revoke_source(person_id: str, fact_id: str, request: Request, data: schemas.SourceRevoke):  # 撤回人物資訊所引用的一筆來源
        return service.revoke_fact_source(current(request, True)['id'], person_id, fact_id, data)  # 回傳撤回人物資訊所引用的一筆來源的結果

    @app.post('/api/people/{person_id}/goals', status_code=201, tags=['People'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def link_goal(person_id: str, request: Request, data: schemas.GoalLink):  # 建立使用者明確設定的人物與目標關聯
        return service.link_person_goal(current(request, True)['id'], person_id, data)  # 回傳建立使用者明確設定的人物與目標關聯的結果

    @app.post('/api/people/{person_id}/connections', status_code=201, tags=['People'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def connection(person_id: str, request: Request, data: schemas.ConnectionCreate):  # 建立兩位人物間的明確關係
        return service.create_connection(current(request, True)['id'], person_id, data)  # 回傳建立兩位人物間的明確關係的結果

    @app.patch('/api/interactions/{event_id}', tags=['People'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def edit_interaction(event_id: str, request: Request, data: schemas.InteractionEdit):  # 檢查版本後重新分類互動事件
        return service.edit_interaction(current(request, True)['id'], event_id, data)  # 回傳檢查版本後重新分類互動事件的結果

    @app.post('/api/interactions/{event_id}/merge', tags=['People'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def merge_interactions(event_id: str, request: Request, data: schemas.InteractionMerge):  # 合併同一次互動，保留經歷與既有積分
        return service.merge_interactions(current(request, True)['id'], event_id, data)  # 回傳合併同一次互動，保留經歷與既有積分的結果

    @app.get('/api/connections', tags=['Connections'])  # 依焦點及來源種類分頁探索
    def stories(request: Request, person_id: Optional[str] = Query(None, min_length=1, max_length=128), involvement: Literal['participant', 'mention', 'legacy'] = 'participant', sort: Literal['recent', 'oldest'] = 'recent', limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0)):  # 限制單次顯示量與排序白名單
        return service.stories(current(request)['id'], person_id, involvement, sort, limit, offset)  # 後端檢查人物與故事所有權

    @app.get('/api/connections/stories/{experience_id}', tags=['Connections'])  # 讀取參與／提及與原文來源
    def story(experience_id: str, request: Request, manage: bool = False):  # 本人可管理舊未核對或已撤回來源
        return service.story_detail(current(request)['id'], experience_id, manage)  # 探索模式拒絕不可見來源

    @app.put('/api/connections/stories/{experience_id}/people', tags=['Connections'])  # 獨立人工分類與更正入口
    def story_people(experience_id: str, request: Request, data: schemas.StoryPeopleEdit):  # 不重做原經歷確認或發獎勵
        return service.edit_story_people(current(request, True)['id'], experience_id, data)  # 版本、權限及去重在交易內處理

    @app.post('/api/connections/mentions/{mention_id}/match', tags=['Connections'])  # 人工配對原文所指人物
    def mention_match(mention_id: str, request: Request, data: schemas.MentionMatch):  # 不改參與或人物私人關係
        return service.match_mention(current(request, True)['id'], mention_id, data)  # 來源失效時拒絕操作

    @app.post('/api/connections/stories/{experience_id}/availability', tags=['Connections'])  # 撤回或恢復交會展示
    def story_availability(experience_id: str, request: Request, data: schemas.StoryAvailability):  # 原文與獎勵仍保留
        return service.story_availability(current(request, True)['id'], experience_id, data)  # 只調整派生探索狀態

    @app.post('/api/goals/{goal_id}/evidence', status_code=201, tags=['Evidence'])  # 註冊此 HTTP 路由、例外處理器或中介層
    async def upload(goal_id: str, request: Request, file: UploadFile = File(...)):  # 驗證權限與圖片內容後保存目標佐證
        try:  # 保護可能失敗的操作，交由下方例外分支處理
            owner = current(request, True)['id']  # 準備目前資料所屬帳號識別碼
            service.goal(owner, goal_id)  # 讀取目標及其行動累計
            content = await file.read(policy.max_upload_bytes + 1)  # 保存「content」供後續驗證或回傳使用
            return service.upload(owner, goal_id, file.filename, file.content_type, content)  # 回傳驗證權限與圖片內容後保存目標佐證的結果
        finally:  # 不論成功或失敗都執行必要清理
            await file.close()  # 關閉已使用完畢的資源

    @app.get('/api/evidence/{evidence_id}', tags=['Evidence'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def evidence(evidence_id: str, request: Request):  # 讀取所屬帳號可存取的佐證內容
        result = service.evidence(current(request)['id'], evidence_id)  # 準備本次操作的回傳資料
        return Response(result['content'], media_type=result['mime'],
                        headers={'Content-Security-Policy': "default-src 'none'; sandbox", 'Cache-Control': 'no-store'})  # 回傳讀取所屬帳號可存取的佐證內容的結果

    @app.post('/api/goals/{goal_id}/complete', tags=['Goals'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def complete(goal_id: str, request: Request, data: schemas.Complete):  # 檢查佐證與人工確認後收藏目標成果
        return service.complete(current(request, True)['id'], goal_id, data)  # 回傳檢查佐證與人工確認後收藏目標成果的結果

    @app.post('/api/notes', status_code=201, tags=['Creative notes'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def create_note(request: Request, data: schemas.NoteCreate):  # 保存私人準備、模擬或訊息草稿，不改正式成果
        return service.create_note(current(request, True)['id'], data)  # 回傳保存私人準備、模擬或訊息草稿，不改正式成果的結果

    @app.patch('/api/tasks/{task_id}', tags=['Experiences'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def task(task_id: str, request: Request, data: schemas.TaskEdit):  # 更新待辦勾選狀態
        return service.edit_task(current(request, True)['id'], task_id, data)  # 回傳更新待辦勾選狀態的結果

    static = Path(__file__).parent / 'static'  # 準備實際 App 靜態資源目錄
    app.mount('/static', StaticFiles(directory=static), name='static')  # 執行此模組的共用工具操作

    @app.api_route('/intro', methods=['GET','HEAD'], include_in_schema=False)
    @app.api_route('/intro/', methods=['GET','HEAD'], include_in_schema=False)
    def intro():
        # 只讀取靜態介紹，不建立Session或查DB；禁止介紹連線任何API。
        csp="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
        return FileResponse(static / 'intro' / 'index.html',headers={'Cache-Control':'no-store','Content-Security-Policy':csp})

    @app.get('/', include_in_schema=False)  # 註冊此 HTTP 路由、例外處理器或中介層
    def index():  # 提供 App 的 HTML 外殼
        return FileResponse(static / 'index.html')  # 回傳提供 App 的 HTML 外殼的結果

    return app  # 回傳建立 API、服務與靜態頁面入口的結果
