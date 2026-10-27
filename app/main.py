"""HTTP adapter; domain writes live in service.py, not in browser storage."""
from pathlib import Path
import logging
import os

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import DemoPolicy
from .db import Database
from .errors import DomainError
from . import schemas
from .service import LifeWorld

logger = logging.getLogger(__name__)


def create_app(data_dir=None, policy=None, clock=None):
    policy = policy or DemoPolicy()
    data_dir = data_dir or os.environ.get('LIFEWORLD_DATA_DIR') or Path(__file__).resolve().parent.parent / 'data'
    service = LifeWorld(Database(data_dir), policy, clock)
    app = FastAPI(title='Life World Local API', version='0.1.0', description='本機開發版；開發設定不是正式產品規則。')
    app.state.service = service
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver', '[::1]'])

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse({'error': {'code': exc.code, 'message': exc.message}}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Never echo passwords or sensitive raw payloads through Pydantic input fields.
        fields = ['.'.join(str(p) for p in e['loc'][1:]) for e in exc.errors()]
        return JSONResponse({'error': {'code': 'validation_error', 'message': '請檢查欄位內容與格式。', 'fields': fields}}, status_code=422)

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        logger.error('Operation failed: %s %s (%s)', request.method, request.url.path, type(exc).__name__)
        return JSONResponse({'error': {'code': 'internal_error', 'message': '操作未完成，請保留目前內容並重試。'}}, status_code=500)

    @app.middleware('http')
    async def security_headers(request, call_next):
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            expected = str(request.base_url).rstrip('/')
            if origin and origin != expected:
                return JSONResponse({'error': {'code': 'origin_rejected', 'message': '不允許跨來源寫入。'}}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        if request.url.path == '/':
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        return response

    def current(request, write=False):
        return service.session(request.cookies.get('lw_session'), request.headers.get('X-CSRF-Token'), write)[0]

    def cookie(response, token):
        response.set_cookie('lw_session', token, httponly=True, secure=policy.secure_cookies,
                            samesite='strict', path='/', max_age=policy.session_hours * 3600)

    @app.get('/api/health', tags=['System'])
    def health():
        return {'status': 'ok', 'mode': 'local-development'}

    @app.post('/api/auth/guest', tags=['Identity'])
    def guest(request: Request, response: Response):
        result, token, created = service.guest(request.cookies.get('lw_session'))
        response.status_code = 201 if created else 200
        if token:
            cookie(response, token)
        return result

    @app.get('/api/auth/me', tags=['Identity'])
    def me(request: Request):
        user, csrf = service.session(request.cookies.get('lw_session'))
        return service.public_user(user, csrf)

    @app.put('/api/profile', tags=['Identity'])
    def profile(request: Request, data: schemas.Profile):
        return service.profile(current(request, True)['id'], data)

    @app.post('/api/auth/claim', tags=['Identity'])
    def claim(request: Request, response: Response, data: schemas.Credentials):
        result, token = service.claim(current(request, True), data)
        cookie(response, token)
        return result

    @app.post('/api/auth/login', tags=['Identity'])
    def login(request: Request, response: Response, data: schemas.Login):
        if request.cookies.get('lw_session'):
            try:
                current(request, True)
            except DomainError as exc:
                if exc.status != 401:
                    raise
        result, token = service.login(data, request.cookies.get('lw_session'))
        cookie(response, token)
        return result

    @app.post('/api/auth/logout', status_code=204, tags=['Identity'])
    def logout(request: Request):
        current(request, True)
        service.logout(request.cookies['lw_session'])
        response = Response(status_code=204)
        response.delete_cookie('lw_session', path='/', secure=policy.secure_cookies, httponly=True, samesite='strict')
        return response

    @app.get('/api/state', tags=['World'])
    def state(request: Request):
        return service.state(current(request)['id'])

    @app.post('/api/goals', status_code=201, tags=['Goals'])
    def create_goal(request: Request, data: schemas.GoalCreate):
        return service.create_goal(current(request, True)['id'], data)

    @app.get('/api/goals/{goal_id}', tags=['Goals'])
    def get_goal(goal_id: str, request: Request):
        return service.goal(current(request)['id'], goal_id)

    @app.get('/api/goals/{goal_id}/calendar', tags=['Goals'])
    def calendar(goal_id: str, request: Request):
        return service.calendar(current(request)['id'], goal_id)

    @app.post('/api/experiences/drafts', status_code=201, tags=['Experiences'])
    def create_draft(request: Request, data: schemas.DraftCreate):
        return service.create_draft(current(request, True)['id'], data)

    @app.get('/api/drafts/{draft_id}', tags=['Experiences'])
    def get_draft(draft_id: str, request: Request):
        return service.draft(current(request)['id'], draft_id)

    @app.put('/api/drafts/{draft_id}', tags=['Experiences'])
    def edit_draft(draft_id: str, request: Request, data: schemas.DraftEdit):
        return service.edit_draft(current(request, True)['id'], draft_id, data)

    @app.post('/api/drafts/{draft_id}/suggest', tags=['Experiences'])
    def suggest(draft_id: str, request: Request):
        return service.suggest(current(request, True)['id'], draft_id)

    @app.post('/api/drafts/{draft_id}/confirm', status_code=201, tags=['Experiences'])
    def confirm(draft_id: str, request: Request, data: schemas.Confirm):
        return service.confirm(current(request, True)['id'], draft_id, data)

    @app.post('/api/people', status_code=201, tags=['People'])
    def create_person(request: Request, data: schemas.PersonCreate):
        return service.create_person(current(request, True)['id'], data)

    @app.post('/api/goals/{goal_id}/evidence', status_code=201, tags=['Evidence'])
    async def upload(goal_id: str, request: Request, file: UploadFile = File(...)):
        try:
            owner = current(request, True)['id']
            service.goal(owner, goal_id)
            content = await file.read(policy.max_upload_bytes + 1)
            return service.upload(owner, goal_id, file.filename, file.content_type, content)
        finally:
            await file.close()

    @app.get('/api/evidence/{evidence_id}', tags=['Evidence'])
    def evidence(evidence_id: str, request: Request):
        result = service.evidence(current(request)['id'], evidence_id)
        return Response(result['content'], media_type=result['mime'],
                        headers={'Content-Security-Policy': "default-src 'none'; sandbox", 'Cache-Control': 'no-store'})

    @app.post('/api/goals/{goal_id}/complete', tags=['Goals'])
    def complete(goal_id: str, request: Request, data: schemas.Complete):
        return service.complete(current(request, True)['id'], goal_id, data)

    @app.post('/api/notes', status_code=201, tags=['Creative notes'])
    def create_note(request: Request, data: schemas.NoteCreate):
        return service.create_note(current(request, True)['id'], data)

    @app.patch('/api/tasks/{task_id}', tags=['Experiences'])
    def task(task_id: str, request: Request, data: schemas.TaskEdit):
        return service.edit_task(current(request, True)['id'], task_id, data)

    static = Path(__file__).parent / 'static'
    app.mount('/static', StaticFiles(directory=static), name='static')

    @app.get('/', include_in_schema=False)
    def index():
        return FileResponse(static / 'index.html')

    return app
