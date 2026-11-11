"""8030 AI 生成路由（2026-11-10 自 8445 的 app/main.py 移植）：角色卡 AI 草稿、T1／T2 逐段生成、進度、恢復。

- Provider 依 LIFEWORLD_AI_* 設定建立：gemini（真實）或 fake（開發與測試）；沒有設定時回 503，不假裝成功。
- 背景排程（P1，與 8445 相同）：有 LIFEWORLD_TASKS_* 設定時用 Cloud Tasks（lw-roleplay-e2e）。開始生成即排入第 0 段，
  Cloud Tasks 以 OIDC 呼叫 POST /internal/roleplay/tasks；Worker 一次只做一段（一次 Gemini 呼叫），保存成功才排入下一段。
  前端只讀取進度；關閉瀏覽器不影響生成。
- 沒有排程設定時（本機開發與測試）退回逐段推進：POST /api/generation/runs/{id}/step 每次推進一段。
- 產品內部不限制次數；每次真實呼叫前檢查每日金額上限；用完時依 24 小時時間窗延後排程，額度恢復後自動繼續。
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import math
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from . import portrayal  # noqa: F401（匯入時把 F06A 的兩個生成模組登錄到共用端點）
from . import person_profile_ai  # noqa: F401（第三階段：AI 產生人物設定）
from . import roleplay
from . import theater  # noqa: F401（匯入時把人物劇場的演出模組登錄到共用端點）
from .ai_config import AiSettings
from .ai_providers import build_provider
from .ai_text import ProviderFailure
from .errors import DomainError
from .gen_schemas import GenerateRequest
from .generation import call_provider, watch_late_usage
from .step_queue import StepQueue, derive_entry
from .task_queue import QueueError, build_task_queue

logger = logging.getLogger(__name__)
OPEN_MODULES = ('character_card', 'story_opening', 'character_reply', 'person_portrayal', 'portrayal_reply',
                'theater_performance', 'person_profile')  # 角色卡草稿、F04 故事開場、F05 互動回合、F06A 人物演繹與試演、人物劇場、人物設定


def install(app, service, current, settings=None, provider=None, task_queue=None):
    settings = settings or AiSettings.from_env()
    app.state.gen_settings = settings
    app.state.gen_provider = provider if provider is not None else build_provider(settings)
    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='lw-generation')
    # 有排程佇列（Cloud Tasks；測試用記憶體佇列）就在背景生成；否則退回頁面逐段推進。
    queue = task_queue if task_queue is not None else (build_task_queue() or StepQueue(service.db.backend))
    background = not isinstance(queue, StepQueue)
    app.state.step_queue = app.state.task_queue = queue

    async def require_environment():
        """開始或恢復前，以實際連線確認資料庫屬於這個佇列的環境；不一致就拒絕並留下診斷紀錄（與 8445 相同）。"""
        if not background:
            return
        identity, mismatch = await run_in_threadpool(roleplay.check_environment, service, queue)
        if mismatch:
            roleplay.task_diagnostic(queue, identity, None, 'rejected', mismatch, {'phase': 'start'}, 'ERROR')
            raise DomainError(503, 'environment_mismatch', '這個環境的資料庫設定與排程不一致，已停止自動生成。')

    async def enqueue(owner, work_id, step=0, attempt=0, message='排程暫時無法加入，請再試一次。'):
        try:
            await run_in_threadpool(roleplay.enqueue_step, queue, owner, work_id, step, attempt)
        except QueueError:
            raise DomainError(503, 'queue_unavailable', message) from None

    def provider_or_503():
        provider_now = app.state.gen_provider
        if provider_now is None:
            raise DomainError(503, 'ai_provider_unavailable', 'AI 生成尚未設定；不會產生假裝成功的內容。')
        return provider_now

    @app.get('/api/generation/status', tags=['Generation'])
    def generation_status(request: Request):
        current(request)
        provider_now = app.state.gen_provider
        return {'available': provider_now is not None, 'provider': getattr(provider_now, 'name', None),
                'provider_kind': getattr(provider_now, 'kind', None), 'model': getattr(provider_now, 'model', None),
                'background': background}  # True：後端排程生成，頁面只讀取進度

    @app.post('/api/ai/generate', status_code=201, tags=['AI'])
    async def ai_generate(request: Request, data: GenerateRequest):
        """單次生成（角色卡草稿）：交易外呼叫 Provider，套用總時限；同一 request_id 不重複呼叫。"""
        user = await run_in_threadpool(current, request, True)
        provider_now = provider_or_503()
        if data.module not in OPEN_MODULES:
            raise DomainError(422, 'module_unavailable', '這個生成模組在 8030 尚未開放。')
        prepared = await run_in_threadpool(service.ai_prepare, user['id'], data, provider_now, settings)
        if 'replay' in prepared:
            return service.ai_replay(prepared['replay'])
        started, result, failure, pending = time.monotonic(), None, None, None
        try:
            result, failure, pending = await call_provider(provider_now, prepared['request'], settings.timeout_seconds, executor)
        except ProviderFailure as exc:
            failure, result = exc.code, exc.result
        except Exception as exc:
            logger.error('AI provider failed (%s)', type(exc).__name__)  # 只記錄例外類型，不記錄內容或金鑰
            failure = 'provider_error'
        latency = int((time.monotonic() - started) * 1000)
        try:
            return await run_in_threadpool(service.ai_finish, user['id'], prepared, provider_now, result, failure, latency)
        finally:  # 逾時（HTTP 回 504）後 Gemini 才回來：失敗已寫入，晚到的用量另外補記與結算
            watch_late_usage(service, executor, user['id'], prepared, provider_now, pending)

    @app.get('/api/ai/generations/{generation_id}', tags=['AI'])
    def ai_generation(generation_id: str, request: Request):
        return service.generation(current(request)['id'], generation_id)

    @app.get('/api/generation/catalog', tags=['Generation'])
    def generation_catalog(request: Request):
        current(request)
        return service.generation_catalog()

    @app.post('/api/generation/runs', status_code=201, tags=['Generation'])
    async def generation_start(request: Request, data: roleplay.GenerationStart):
        """建立作品（排隊中）並記下第 0 段（規劃）；之後由頁面逐段推進。"""
        user = await run_in_threadpool(current, request, True)
        provider_now = provider_or_503()
        await require_environment()
        result = await run_in_threadpool(service.start_generation, user['id'], data, provider_now.name)
        # 作品已建立（排隊中）；沿用同一個 request_id 重送即可再次排入（同名 Task 不會重複）。
        await enqueue(user['id'], result['id'], message='作品已建立，但排程暫時無法加入。請再按一次「開始生成」。')
        return result

    @app.get('/api/roleplay/styles', tags=['Roleplay'])
    def roleplay_styles(request: Request):
        """8445 相容：風格目錄（與 /api/generation/catalog 的 styles 相同）。"""
        current(request)
        return {'items': service.generation_catalog()['styles']}

    @app.get('/api/generation/runs', tags=['Generation'])
    @app.get('/api/roleplay', tags=['Roleplay'])  # 8445 相容別名（讀取）
    def generation_list(request: Request):
        return service.roleplay_list(current(request)['id'])

    @app.get('/api/generation/runs/{work_id}', tags=['Generation'])
    @app.get('/api/roleplay/{work_id}', tags=['Roleplay'])  # 8445 相容別名：舊作品（roleplay_session）也用同一個詳情
    def generation_detail(work_id: str, request: Request):
        return service.roleplay_detail(current(request)['id'], work_id)

    @app.post('/api/generation/runs/{work_id}/resume', tags=['Generation'])
    @app.post('/api/roleplay/{work_id}/resume', tags=['Roleplay'])  # 8445 相容別名：恢復舊作品
    async def generation_resume(work_id: str, request: Request, data: roleplay.ResumeRequest):
        """恢復失敗（或因金額上限暫停）的作品：從下一段的新嘗試繼續，已保存的段落不重做。"""
        user = await run_in_threadpool(current, request, True)
        provider_now = provider_or_503()
        await require_environment()
        result = await run_in_threadpool(service.resume_roleplay, user['id'], work_id, data, provider_now.name)
        await enqueue(user['id'], work_id, result['step'], result['attempt'], '已恢復，但排程暫時無法加入。請再按一次「恢復」。')
        return result

    @app.post('/api/generation/runs/{work_id}/step', tags=['Generation'])
    async def generation_step(work_id: str, request: Request):
        """推進一段並回傳最新進度；需要等待（重試延遲）時回 wait_seconds，頁面稍後再呼叫。"""
        user = await run_in_threadpool(current, request, True)
        owner = user['id']
        if background:  # 背景排程：生成由 Worker 推進，這裡只回傳進度（不呼叫 Provider）
            detail = await run_in_threadpool(service.roleplay_detail, owner, work_id)
            return {'outcome': 'background', 'reason': None, 'detail': detail, 'wait_seconds': 3}
        provider_now = provider_or_503()
        entry = queue.take(work_id)
        if entry is not None and entry['payload']['owner_id'] != owner:
            queue.enqueue('', entry['payload'], max(0, entry['not_before'] - time.time()))  # 不是自己的作品：放回，不執行
            entry = None
        elif entry is None:
            entry = await run_in_threadpool(derive_entry, service, owner, work_id, queue.environment_id)
        outcome, reason = 'none', None
        if entry is not None:
            wait = entry['not_before'] - time.time()
            if wait > 0:
                queue.enqueue('', entry['payload'], wait)
            else:
                task = roleplay.TaskPayload.model_validate(entry['payload'])
                outcome, reason = await roleplay.run_roleplay_task(service, provider_now, settings, queue, task, executor)
        detail = await run_in_threadpool(service.roleplay_detail, owner, work_id)
        upcoming = queue.peek(work_id)
        return {'outcome': outcome, 'reason': reason, 'detail': detail,
                'wait_seconds': math.ceil(max(0, upcoming['not_before'] - time.time())) if upcoming else None}

    @app.post('/internal/roleplay/tasks', include_in_schema=False)
    async def roleplay_task(request: Request):
        """Cloud Tasks 的 Worker（與 8445 相同）：一個 Task 一段。不在 /api 之下；由 Cloud Run IAM（OIDC）驗證呼叫者。"""
        if not background:
            return JSONResponse({'error': {'code': 'not_found', 'message': 'Not Found'}}, status_code=404)
        meta = {'task_name': request.headers.get('x-cloudtasks-taskname'), 'retry_count': request.headers.get('x-cloudtasks-taskretrycount'),
                'queue_header': request.headers.get('x-cloudtasks-queuename')}
        if queue.kind == 'cloud_tasks' and meta['queue_header'] != queue.queue_name:
            roleplay.task_diagnostic(queue, None, None, 'rejected', 'queue_mismatch', meta, 'WARNING')  # 別的環境的 Queue 不得送進來
            return JSONResponse({'error': {'code': 'forbidden', 'message': '只接受本環境排程佇列的呼叫。'}}, status_code=403)
        try:
            task = roleplay.TaskPayload.model_validate(await request.json())
        except Exception:
            roleplay.task_diagnostic(queue, None, None, 'rejected', 'invalid_task', meta, 'WARNING')
            return JSONResponse({'error': {'code': 'invalid_task', 'message': 'Task 內容不合格。'}}, status_code=200)  # 不讓 Cloud Tasks 無限重送
        try:
            outcome, reason = await roleplay.run_roleplay_task(service, app.state.gen_provider, settings, queue, task, executor, meta)
            if outcome == 'rejected':
                return {'outcome': 'rejected', 'reason': reason}  # 環境不一致：不重試（回 200），診斷紀錄已寫入
        except QueueError:
            logger.warning('Roleplay enqueue failed')
            return JSONResponse({'error': {'code': 'queue_unavailable', 'message': '排程暫時無法加入。'}}, status_code=503)  # 讓 Cloud Tasks 重送（Worker 冪等）
        except DomainError as exc:
            if exc.status >= 500 or exc.code in ('transaction_conflict', 'write_conflict'):
                roleplay.task_diagnostic(queue, None, task, 'retry', exc.code, meta, 'WARNING')
                return JSONResponse({'error': {'code': exc.code, 'message': exc.message}}, status_code=503)  # 資料庫暫時錯誤：讓 Cloud Tasks 重送
            roleplay.task_diagnostic(queue, None, task, 'stopped', exc.code, meta, 'WARNING')
            return {'outcome': 'stopped', 'code': exc.code}
        return {'outcome': outcome}

