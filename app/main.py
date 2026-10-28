"""HTTP adapter; domain writes live in service.py, not in browser storage."""  # 說明此模組的責任與實作邊界
from pathlib import Path  # 以跨平台方式組合檔案路徑
import logging  # 記錄服務錯誤類型而不輸出敏感本文
import os  # 讀取資料目錄或測試網址等環境設定
from typing import Literal, Optional  # 宣告可選欄位、清單與受限字串型別

from fastapi import FastAPI, Request, UploadFile, File, Query  # 建立 HTTP API、請求與上傳欄位
from fastapi.exceptions import RequestValidationError  # 捕捉輸入驗證錯誤
from fastapi.responses import FileResponse, JSONResponse, Response  # 建立 JSON、圖片與首頁回應
from fastapi.staticfiles import StaticFiles  # 提供前端靜態資源
from starlette.middleware.trustedhost import TrustedHostMiddleware  # 限制此本機服務接受的主機名稱

from .config import DemoPolicy  # 載入本機開發設定
from .db import Database  # 載入 SQLite 交易與遷移管理器
from .errors import DomainError  # 共用領域錯誤與條件檢查
from . import schemas  # 載入此模組需要的相依工具
from .service import LifeWorld  # 載入負責原子交易的領域服務

logger = logging.getLogger(__name__)  # 準備只記錄錯誤類型與路徑的紀錄器


def create_app(data_dir=None, policy=None, clock=None):  # 建立 API、服務與靜態頁面入口
    policy = policy or DemoPolicy()  # 準備本機開發設定
    data_dir = data_dir or os.environ.get('LIFEWORLD_DATA_DIR') or Path(__file__).resolve().parent.parent / 'data'  # 準備本次 App 使用的資料目錄
    service = LifeWorld(Database(data_dir), policy, clock)  # 準備負責交易與領域規則的服務物件
    app = FastAPI(title='Life World Local API', version='0.3.0', description='本機開發版；開發設定不是正式產品規則。')  # 交會正式整合的增量版本
    app.state.service = service  # 保存「app.state.service」供後續驗證或回傳使用
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver', '[::1]'])  # 執行此模組的共用工具操作

    @app.exception_handler(DomainError)  # 註冊此 HTTP 路由、例外處理器或中介層
    async def domain_error(request, exc):  # 將領域錯誤轉成一致的 HTTP 回應
        return JSONResponse({'error': {'code': exc.code, 'message': exc.message}}, status_code=exc.status)  # 回傳將領域錯誤轉成一致的 HTTP 回應的結果

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
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):  # 依目前條件選擇下一步處理分支
            origin = request.headers.get('origin')  # 保存「origin」供後續驗證或回傳使用
            expected = str(request.base_url).rstrip('/')  # 保存「expected」供後續驗證或回傳使用
            if origin and origin != expected:  # 依目前條件選擇下一步處理分支
                return JSONResponse({'error': {'code': 'origin_rejected', 'message': '不允許跨來源寫入。'}}, status_code=403)  # 回傳檢查寫入來源並加入安全與快取標頭的結果
        response = await call_next(request)  # 保存「response」供後續驗證或回傳使用
        response.headers['X-Content-Type-Options'] = 'nosniff'  # 設定回應的安全或快取標頭
        response.headers['Referrer-Policy'] = 'same-origin'  # 設定回應的安全或快取標頭
        response.headers['X-Frame-Options'] = 'DENY'  # 設定回應的安全或快取標頭
        if request.url.path.startswith('/api/'):  # 依目前條件選擇下一步處理分支
            response.headers['Cache-Control'] = 'no-store'  # 設定回應的安全或快取標頭
        if request.url.path == '/':  # 依目前條件選擇下一步處理分支
            response.headers['Cache-Control'] = 'no-store'  # 設定回應的安全或快取標頭
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"  # 設定回應的安全或快取標頭
        return response  # 回傳檢查寫入來源並加入安全與快取標頭的結果

    def current(request, write=False):  # 驗證目前工作階段，寫入時同時檢查 CSRF
        return service.session(request.cookies.get('lw_session'), request.headers.get('X-CSRF-Token'), write)[0]  # 回傳驗證目前工作階段，寫入時同時檢查 CSRF的結果

    def cookie(response, token):  # 設定不可由 JavaScript 讀取的工作階段 Cookie
        response.set_cookie('lw_session', token, httponly=True, secure=policy.secure_cookies,
                            samesite='strict', path='/', max_age=policy.session_hours * 3600)  # 執行此模組的共用工具操作

    @app.get('/api/health', tags=['System'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def health():  # 回報本機服務的健康狀態
        return {'status': 'ok', 'mode': 'local-development'}  # 回傳回報本機服務的健康狀態的結果

    @app.post('/api/auth/guest', tags=['Identity'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def guest(request: Request, response: Response):  # 取得既有訪客身分或建立新的訪客世界
        result, token, created = service.guest(request.cookies.get('lw_session'))  # 取得既有訪客身分或建立新的訪客世界
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
        result, token = service.login(data, request.cookies.get('lw_session'))  # 核對密碼並建立工作階段，不合併訪客資料
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

    @app.get('/api/goals/{goal_id}/calendar', tags=['Goals'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def calendar(goal_id: str, request: Request):  # 依目前每週規律產生 28 日預覽；月週期另項實作
        return service.calendar(current(request)['id'], goal_id)  # 回傳依目前每週規律產生 28 日預覽；月週期另項實作的結果

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
        return service.suggest(current(request, True)['id'], draft_id)  # 回傳建立可手動審閱的整理候選，不寫入正式事實的結果

    @app.post('/api/drafts/{draft_id}/confirm', status_code=201, tags=['Experiences'])  # 註冊此 HTTP 路由、例外處理器或中介層
    def confirm(draft_id: str, request: Request, data: schemas.Confirm):  # 以單一交易保存經歷、貢獻、人物更新與一次積分
        return service.confirm(current(request, True)['id'], draft_id, data)  # 回傳以單一交易保存經歷、貢獻、人物更新與一次積分的結果

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

    @app.get('/', include_in_schema=False)  # 註冊此 HTTP 路由、例外處理器或中介層
    def index():  # 提供 App 的 HTML 外殼
        return FileResponse(static / 'index.html')  # 回傳提供 App 的 HTML 外殼的結果

    return app  # 回傳建立 API、服務與靜態頁面入口的結果
