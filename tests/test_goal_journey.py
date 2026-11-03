"""單一目標、實際日期排程與到期回顧的契約測試。"""  # 測試先於正式功能建立。
from concurrent.futures import ThreadPoolExecutor  # 驗證兩個視窗同時建立。
from datetime import datetime, timezone  # 以固定時鐘驗證到期邊界。
import copy  # 修改獨立輸入而不污染其他案例。
import sqlite3  # 建立舊版資料庫驗證遷移。
from pathlib import Path  # 讀取既有版本化 SQL。
import pytest  # 使用正常、異常與邊界案例。
from fastapi.testclient import TestClient  # 透過實際 HTTP 介面驗證。
from app.main import create_app  # 重啟隔離 App 驗證保存。
from conftest import guest, draft, confirm_payload  # 沿用身分與人工確認工具。


def setup_user(client, zone='Asia/Taipei'):  # 只準備身分，不提前建立目標。
    me = guest(client)  # 設定合法 CSRF。
    assert client.put('/api/profile', json={'name': '習慣測試者', 'bio': '一段旅程', 'timezone': zone}).status_code == 200  # 保存使用者時區。
    return me  # 讓權限測試可核對 owner。


def payload(key='journey-1', deadline='2026-10-28', dates=None):  # 建立新契約的最小輸入。
    return {'request_id': key, 'title': '完成作品', 'outcome': '完成作品並留下佐證', 'deadline': deadline, 'actions': [{'title': name, 'per_occurrence': '1', 'unit': '次', 'dates': dates or ['2026-10-27', '2026-10-28'], 'weekdays': [0, 1, 2, 3, 4], 'cycle': 'month'} for name in ['練習', '整理', '交流']]}  # 三個習慣各有獨立日期。


def create(client, **kwargs):  # 經 API 建立目標並核對成功。
    result = client.post('/api/goals', json=payload(**kwargs))  # 不繞過輸入與權限檢查。
    assert result.status_code == 201, result.text  # 缺功能應在此形成有效紅燈。
    return result.json()  # 傳回伺服器生成 ID。


def review(client, goal, decision='end', key='review-1', **extra):  # 人工回顧攜帶版本與去重代碼。
    return client.post('/api/goals/' + goal['id'] + '/review', json={'request_id': key, 'expected_revision': goal['revision'], 'decision': decision, 'confirmed': True, **extra})  # 不使用自動結束。


def advance(app, instant='2026-10-28T16:00:00+00:00'):  # 切換至台北截止日結束後。
    app.state.service.clock = lambda: datetime.fromisoformat(instant)  # 不依賴實際牆鐘。


def test_goal_requires_exactly_three_habits_and_explicit_deadline(client):  # 驗證最小建立與預設數量。
    setup_user(client)  # 建立合法前置資料。
    goal = create(client)  # 使用明確截止日建立。
    assert goal['status'] == 'active' and goal['start_date'] == '2026-10-27'  # 開始日由伺服器決定。
    assert goal['deadline'] == '2026-10-28' and goal['schedule_timezone'] == 'Asia/Taipei'  # 固定目標日期基準。
    assert len(goal['actions']) == 3 and goal['actions'][0]['per_occurrence'] == '1'  # 不要求額外總量輸入。
    assert goal['actions'][0]['target'] == '2' and goal['actions'][0]['progress'] == '0'  # 安排不代表完成。
    assert client.get('/api/auth/me').json()['lumi_hatched']  # 提交後才孵化。


@pytest.mark.parametrize('mutation', ['missing_deadline', 'past', 'invalid_date', 'two', 'four', 'blank', 'zero', 'negative', 'nan', 'huge', 'empty_dates', 'duplicate_dates', 'before_start', 'after_deadline'])  # 驗證非法與邊界輸入。
def test_invalid_goal_is_atomic(client, mutation):  # 失敗不能留下目標或孵化。
    setup_user(client)  # 每個案例使用新世界。
    body = copy.deepcopy(payload())  # 保持測試互相隔離。
    if mutation == 'missing_deadline': body.pop('deadline')  # 期限不得省略。
    if mutation == 'past': body['deadline'] = '2026-10-26'  # 不允許過去截止日。
    if mutation == 'invalid_date': body['deadline'] = '2026-02-30'  # 真實日曆驗證。
    if mutation == 'two': body['actions'].pop()  # 不足三個。
    if mutation == 'four': body['actions'].append(copy.deepcopy(body['actions'][0]))  # 不超過三個。
    if mutation == 'blank': body['actions'][0]['title'] = '  '  # 不接受空白名稱。
    if mutation in {'zero', 'negative', 'nan', 'huge'}: body['actions'][0]['per_occurrence'] = {'zero': '0', 'negative': '-1', 'nan': 'NaN', 'huge': '1000000000001'}[mutation]  # 數量必須合法。
    if mutation == 'empty_dates': body['actions'][0]['dates'] = []  # 每個習慣至少一天。
    if mutation == 'duplicate_dates': body['actions'][0]['dates'] = ['2026-10-27', '2026-10-27']  # 拒絕重複日期。
    if mutation == 'before_start': body['actions'][0]['dates'] = ['2026-10-26']  # 排程不可早於開始日。
    if mutation == 'after_deadline': body['actions'][0]['dates'] = ['2026-10-29']  # 排程不可超過期限。
    result = client.post('/api/goals', json=body)  # 驗證公開契約。
    assert result.status_code == 422, result.text  # 明確拒絕無效輸入。
    assert not client.get('/api/auth/me').json()['lumi_hatched']  # 不得部分提交。


def test_one_open_goal_and_idempotency_before_and_after_end(client):  # 驗證單一目標與跨狀態重試。
    setup_user(client)  # 建立身分。
    body = payload()  # 保留原請求。
    goal = create(client)  # 第一次成功。
    assert client.post('/api/goals', json=body).json() == goal  # 重試不被單目標限制誤擋。
    result = client.post('/api/goals', json=payload(key='other'))  # 真正第二個目標。
    assert result.status_code == 409 and result.json()['error']['code'] == 'open_goal_exists'  # 後端阻擋。
    ended = review(client, goal, reflection='先告一段落')  # 提前結束。
    assert ended.status_code == 200, ended.text  # 明確結束後才能接續。
    assert ended.json()['status'] == 'ended' and ended.json()['end_reason'] == 'early_end'  # 歷史原因可辨識。
    assert client.post('/api/goals', json=body).json() == goal  # 舊重試不能新建目標。
    second = create(client, key='next')  # 可建立下一次挑戰。
    assert second['id'] != goal['id']  # 不恢復舊挑戰。
    assert review(client, ended.json(), decision='extend', deadline='2026-10-30').status_code == 409  # 不提供歷史恢復。


def test_concurrent_creates_only_one_commits(app, client):  # 真正同時交易不可產生兩個開啟目標。
    setup_user(client)  # 建立共用帳號。
    token = client.cookies.get('lw_session')  # 模擬同帳號另一視窗。
    csrf = client.headers['X-CSRF-Token']  # 帶入有效寫入憑證。
    def submit(key):  # 每個執行緒使用獨立連線。
        with TestClient(app) as other:  # 避免共用 HTTP client 狀態。
            other.cookies.set('lw_session', token)  # 使用同一合法工作階段。
            return other.post('/api/goals', json=payload(key=key), headers={'X-CSRF-Token': csrf}).status_code  # 嘗試不同新目標。
    with ThreadPoolExecutor(max_workers=2) as pool:  # 真正並行競爭。
        results = list(pool.map(submit, ['race-1', 'race-2']))  # 等待兩次寫入完成。
    assert sorted(results) == [201, 409]  # 只能一個成功。
    assert len(client.get('/api/state').json()['goals']) == 1  # 無殘留第二個目標。


@pytest.mark.parametrize('instant,zone,expected', [('2026-10-28T15:59:59+00:00', 'Asia/Taipei', 'active'), ('2026-10-28T16:00:00+00:00', 'Asia/Taipei', 'awaiting_review'), ('2026-10-29T03:59:59+00:00', 'America/New_York', 'active'), ('2026-10-29T04:00:00+00:00', 'America/New_York', 'awaiting_review')])  # 截止日含當地整天。
def test_expiry_respects_goal_timezone(app, client, instant, zone, expected):  # 精確驗證時區邊界。
    setup_user(client, zone)  # 依帳號時區開始。
    goal = create(client)  # 固定目標的日期基準。
    advance(app, instant)  # 推進測試時鐘。
    assert client.get('/api/goals/' + goal['id']).json()['status'] == expected  # 不以 UTC 日期直接到期。
    if expected == 'awaiting_review': assert client.post('/api/goals', json=payload(key='blocked')).status_code == 409  # 待回顧仍占用唯一名額。


@pytest.mark.parametrize('start,end,count', [('2028-02-28', '2028-03-01', 3), ('2026-12-31', '2027-01-01', 2), ('2026-10-31', '2026-11-01', 2)])  # 真實日期跨月、閏年與跨年。
def test_calendar_uses_real_dates(app, client, start, end, count):  # 不再固定回傳 28 天。
    app.state.service.clock = lambda: datetime.fromisoformat(start + 'T04:00:00+00:00')  # 開始前設定時鐘。
    setup_user(client)  # 讓 session 有效。
    goal = create(client, deadline=end, dates=[start, end])  # 只安排首尾兩天。
    days = client.get('/api/goals/' + goal['id'] + '/calendar?start=' + start + '&end=' + end).json()  # 明確查詢區間。
    assert len(days) == count and days[-1]['date'] == end  # 正確處理真實日曆。
    assert len(days[0]['action_ids']) == 3 and len(days[-1]['action_ids']) == 3  # 所選日期完整保存。


def test_pending_progress_requires_explicit_acceptance_after_extension(app, client):  # 確認經歷與補計進度分離。
    setup_user(client)  # 準備身分。
    goal = create(client)  # 建立短期挑戰。
    advance(app)  # 進入待回顧。
    d = draft(client, goal, occurred_at='2026-10-29T00:00:00+08:00')  # 到期後仍可記錄。
    result = client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d))  # 人工確認真實經歷。
    assert result.status_code == 201, result.text  # 不阻擋經歷保存。
    before = client.get('/api/goals/' + goal['id']).json()  # 讀取待處理資料。
    assert before['actions'][0]['progress'] == '0' and len(before['pending_contributions']) == 1  # 不提前累計。
    points = client.get('/api/state').json()['rewards']['total']  # 保存首次獎勵。
    pending = before['pending_contributions'][0]  # 使用伺服器產生的固定識別碼。
    url = '/api/goals/' + goal['id'] + '/pending/' + pending['id'] + '/accept'  # 獨立補計入口。
    body = {'request_id': 'apply-1', 'expected_revision': before['revision'], 'quantity': '0.5', 'confirmed': True}  # 明確確認數量。
    assert client.post(url, json=body).status_code == 409  # 未延長不能補計。
    extended = review(client, before, decision='extend', deadline='2026-10-31', schedules=[{'action_id': a['id'], 'dates': ['2026-10-30'], 'weekdays': [4], 'cycle': 'month'} for a in goal['actions']])  # 檢視並確認延長安排。
    assert extended.status_code == 200, extended.text  # 延長不修改舊進度。
    body['expected_revision'] = extended.json()['revision']  # 使用最新版本。
    accepted = client.post(url, json=body)  # 逐筆採計。
    assert accepted.status_code == 200, accepted.text  # 應可採計符合日期的貢獻。
    assert client.post(url, json=body).json() == accepted.json()  # 相同請求重送安全。
    after = client.get('/api/goals/' + goal['id']).json()  # 核對正式累計。
    assert after['actions'][0]['progress'] == '0.5'  # 恰好入帳一次。
    assert after['pending_contributions'][0]['status'] == 'accepted'  # 保留決定歷史。
    assert client.get('/api/state').json()['rewards']['total'] == points  # 不再次發獎。


def test_ended_pending_is_retained_but_not_counted(app, client):  # 結束後仍可回顧未採計資訊。
    setup_user(client)  # 準備身分。
    goal = create(client)  # 建立短期目標。
    advance(app)  # 讓目標到期。
    d = draft(client, goal)  # 補記期限內活動同樣等待回顧。
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 201  # 經歷可以確認。
    goal = client.get('/api/goals/' + goal['id']).json()  # 取得目前版本。
    result = review(client, goal)  # 選擇結束。
    assert result.status_code == 200 and result.json()['end_reason'] == 'expired'  # 區分到期未完成。
    archived = result.json()  # 查看保存的舊內容。
    assert archived['pending_contributions'][0]['status'] == 'unapplied'  # 不刪除未採計來源。
    assert archived['actions'][0]['progress'] == '0'  # 不默默補算。
    create(client, key='new-after-expiry', deadline='2026-10-31', dates=['2026-10-30'])  # 未採計資訊不阻擋下一個目標。


def test_review_conflict_and_cross_owner_are_safe(app, client):  # 拒絕版本衝突與越權。
    setup_user(client)  # 準備第一個帳號。
    goal = create(client)  # 建立其目標。
    wrong = dict(goal, revision=goal['revision'] + 1)  # 模擬過時／錯誤版本。
    assert review(client, wrong).status_code == 409  # 不接受未核對狀態。
    with TestClient(app) as other:  # 獨立世界。
        setup_user(other)  # 使用合法但不同 owner。
        assert review(other, goal).status_code == 404  # 不洩漏其他人的內容。
    assert review(client, goal).status_code == 200  # 原擁有者仍可結束。


def test_old_database_is_preserved_without_invented_deadline(tmp_path):  # 遷移前資料原樣保留。
    path = tmp_path / 'lifeworld.sqlite3'  # 建立隔離舊資料。
    with sqlite3.connect(path) as c:  # 不讀寫真實使用者 DB。
        c.execute('CREATE TABLE schema_migrations(version TEXT PRIMARY KEY)')  # 模擬舊遷移狀態。
        for sql in sorted(Path('app/migrations').glob('00[1-3]_*.sql')):  # 只套用舊三版。
            c.executescript(sql.read_text())  # 建立真實舊結構。
            c.execute('INSERT INTO schema_migrations VALUES (?)', (sql.name,))  # 記錄舊版本。
        c.execute("INSERT INTO users(id,status,name,bio,timezone,hatched_at,created_at) VALUES ('legacy','registered','舊使用者','保留','Asia/Taipei','2026-10-01','2026-10-01')")  # 無真實帳密資料。
        for key in ['old-a', 'old-b']: c.execute("INSERT INTO goals(id,owner_id,title,outcome,status,created_at) VALUES (?,'legacy',?,'舊成果','active','2026-10-01')", (key, key))  # 舊版允許多目標。
    app = create_app(data_dir=tmp_path)  # 實際執行新增遷移。
    with app.state.service.db.connect() as c:  # 核對遷移後內容。
        rows = c.execute('SELECT * FROM goals ORDER BY id').fetchall()  # 兩個目標都存在。
        assert len(rows) == 2 and all(row['deadline'] is None for row in rows)  # 不猜日期、不自動結束。
        assert all(row['title'] == row['id'] and row['status'] == 'active' for row in rows)  # 舊欄位保持不變。
        assert not c.execute('PRAGMA foreign_key_check').fetchall()  # 關聯完整性維持。
    state = app.state.service.state('legacy')  # 舊目標可正常讀取。
    assert all(goal['status'] == 'needs_setup' for goal in state['goals'])  # 提供待整理狀態。


@pytest.mark.parametrize('new_deadline', ['2026-10-27', '2026-10-28'])  # 延長不能縮短或維持原期限。
def test_invalid_extension_does_not_change_schedule(client, new_deadline):  # 全部資料必須一起回滾。
    setup_user(client)  # 準備帳號。
    goal = create(client)  # 原截止日為 28 日。
    result = review(client, goal, decision='extend', deadline=new_deadline, schedules=[{'action_id': a['id'], 'dates': a['dates']} for a in goal['actions']])  # 試圖非法延長。
    assert result.status_code == 422  # 不接受舊截止日。
    current = client.get('/api/goals/' + goal['id']).json()  # 檢查交易未寫入。
    assert current['revision'] == goal['revision'] and current['actions'] == goal['actions']  # 排程與版本不變。


def test_modify_future_preserves_past_progress_and_review_history(app, client):  # 未來安排改動不重算過去投入。
    setup_user(client)  # 準備帳號。
    goal = create(client)  # 建立兩日挑戰。
    d = draft(client, goal, occurred_at='2026-10-27T12:00:00+08:00')  # 期限內投入。
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 201  # 正式累計。
    advance(app, '2026-10-28T04:00:00+00:00')  # 在第二天調整未來。
    goal = client.get('/api/goals/' + goal['id']).json()  # 取得當前版本。
    schedules = [{'action_id': a['id'], 'dates': ['2026-10-28'], 'cycle': 'week'} for a in goal['actions']]  # 只提交未來日期。
    result = review(client, goal, decision='schedule', schedules=schedules)  # 保存安排。
    assert result.status_code == 200, result.text  # 合法未來修改應成功。
    updated = result.json()  # 查看回顧資料。
    assert updated['actions'][0]['dates'] == ['2026-10-27', '2026-10-28']  # 過去日期自動保留。
    assert updated['actions'][0]['progress'] == '0.5' and len(updated['reviews']) == 1  # 真實累計不變。
    assert client.get('/api/state').json()['rewards']['total'] == 3  # 改安排不發獎。
    schedules[0]['dates'] = ['2026-10-26', '2026-10-28']  # 嘗試修改期外過去日期。
    assert review(client, updated, decision='schedule', key='bad-past', schedules=schedules).status_code == 422  # 不降低歷史保護。


def test_same_day_goal_and_default_once(client):  # 最短挑戰與預設數量有效。
    setup_user(client)  # 準備身分。
    body = payload(deadline='2026-10-27', dates=['2026-10-27'])  # 只挑戰今天。
    for action in body['actions']: action.pop('per_occurrence')  # 使用預設一次。
    result = client.post('/api/goals', json=body)  # 建立當日目標。
    assert result.status_code == 201, result.text  # 當天截止可接受。
    assert all(a['per_occurrence'] == '1' and a['target'] == '1' for a in result.json()['actions'])  # 不要求額外輸入。


def test_profile_timezone_change_does_not_shift_existing_goal(app, client):  # 挑戰時區在開始時固定。
    setup_user(client)  # 原時區台北。
    goal = create(client)  # 建立挑戰。
    client.put('/api/profile', json={'name': '測試者', 'bio': '保留', 'timezone': 'America/New_York'})  # 帳號改時區。
    advance(app)  # 台北已到期，紐約尚未到期。
    updated = client.get('/api/goals/' + goal['id']).json()  # 按目標原時區判定。
    assert updated['status'] == 'awaiting_review' and updated['schedule_timezone'] == 'Asia/Taipei'  # 不延長或縮短原挑戰。


def test_old_multi_goal_requires_explicit_cleanup(sqlite_app, sqlite_client):  # 舊多目標不替使用者選擇保留者。
    # 舊 SQLite 可存在重複開啟目標；PG 草案的 unique index 不允許建出此舊狀態。
    app, client = sqlite_app, sqlite_client
    me = setup_user(client)  # 取得測試 owner。
    goal = create(client)  # 先建立合法資料。
    with app.state.service.db.connect(write=True) as c:  # 僅修改隔離測試資料庫。
        c.execute('UPDATE goals SET deadline=NULL,start_date=NULL,schedule_timezone=NULL WHERE id=?', (goal['id'],))  # 模擬舊目標。
        c.execute("INSERT INTO goals(id,owner_id,title,outcome,status,created_at) VALUES ('other-old',?,'另一個舊目標','保留','active','2026-10-01T00:00:00+00:00')", (me['owner_id'],))  # 模擬舊版多目標。
    legacy = client.get('/api/goals/' + goal['id']).json()  # 顯示待補設定。
    schedules = [{'action_id': a['id'], 'dates': a['dates']} for a in legacy['actions']]  # 使用者明確核對安排。
    result = review(client, legacy, decision='setup', deadline='2026-10-28', schedules=schedules)  # 其他目標尚未結束。
    assert result.status_code == 409 and result.json()['error']['code'] == 'legacy_multiple_goals'  # 必須先整理。
    other = client.get('/api/goals/other-old').json()  # 舊資料仍可讀。
    assert review(client, other).status_code == 200  # 手動結束其他目標。
    assert review(client, legacy, decision='setup', key='setup-after-cleanup', deadline='2026-10-28', schedules=schedules).status_code == 200  # 保留者才可開始。


def test_review_and_pending_require_real_boolean_and_csrf(client):  # 不以數字取代明確確認。
    setup_user(client)  # 準備帳號。
    goal = create(client)  # 建立挑戰。
    body = {'request_id': 'false-confirm', 'expected_revision': goal['revision'], 'decision': 'end', 'confirmed': 1}  # 假布林確認。
    assert client.post('/api/goals/' + goal['id'] + '/review', json=body).status_code == 422  # 嚴格檢查確認旗標。
    body['confirmed'] = True  # 使用合法確認。
    saved = client.headers.pop('X-CSRF-Token')  # 移除寫入憑證。
    assert client.post('/api/goals/' + goal['id'] + '/review', json=body).status_code == 403  # 不允許無 CSRF 寫入。
    client.headers['X-CSRF-Token'] = saved  # 恢復合法工作階段。
    assert client.get('/api/goals/' + goal['id']).json()['status'] == 'active'  # 失敗未關閉挑戰。


def test_new_goal_completion_requires_reviewed_revision(client):  # 成果確認不可繞過新目標版本檢查。
    from test_evidence_notes import upload  # 使用真實有效的虛構 PNG。
    setup_user(client)  # 準備身分。
    goal = create(client)  # 建立新式目標。
    evidence = upload(client, goal).json()  # 成果佐證仍需合法上傳。
    body = {'request_id': 'complete-version', 'evidence_ids': [evidence['id']], 'confirmed': True}  # 尚未帶入核對版本。
    url = '/api/goals/' + goal['id'] + '/complete'  # 使用既有完成 API。
    assert client.post(url, json=body).status_code == 422  # 新目標必須明確傳版本。
    body['expected_revision'] = goal['revision'] + 1  # 模擬錯誤版本。
    assert client.post(url, json=body).status_code == 409  # 不默默接受舊畫面。
    body['expected_revision'] = goal['revision']  # 使用已檢視的正確版本。
    assert client.post(url, json=body).status_code == 200  # 合法成果仍可確認。
    assert client.post(url, json=body).status_code == 200  # 成功後同請求可重試。


def test_browser_clock_server_refuses_actual_data_directory():  # 防止測試時鐘工具啟動正式資料。
    import subprocess, sys  # 執行真正測試啟動器。
    result = subprocess.run([sys.executable, '-m', 'browser_tests.clock_server', '--data-dir', 'data', '--clock-file', '/tmp/lw-refused-clock.txt'], capture_output=True, text=True)  # 不啟動瀏覽器或覆寫資料。
    assert result.returncode == 2 and '不能使用正式資料目錄' in result.stderr  # 必須在啟動服務前拒絕。
