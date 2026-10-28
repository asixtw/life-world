"""交會資料契約、來源與人工配對的行為驗證。"""  # 本測試只使用隔離虛構資料
import sqlite3  # 驗證舊版資料的增量遷移
from pathlib import Path  # 取得專案內的舊遷移來源
from fastapi.testclient import TestClient  # 建立另一個不共用帳號的用戶端
import pytest  # 以參數化涵蓋異常及邊界情境
from conftest import onboard, register, draft, confirm_payload  # 沿用既有真實 API 測試工具


def people(client):  # 建立可追蹤的虛構人物
    onboard(client); register(client)  # 完成首目標與人物帳號門檻
    result = []  # 保存依序建立的人物
    for name in ['小安', '怡君', '怡君']:  # 故意建立同名人物驗證不自動合併
        response = client.post('/api/people', json={'name': name})  # 透過正式 API 新增人物
        assert response.status_code == 201, response.text  # 先確認測試前置成功
        result.append(response.json())  # 保留各自固定 ID
    return result  # 回傳不同身分的測試人物


def story_data(p, raw='今天與小安吃飯，提到怡君。'):  # 建立一位參與及一位未配對提及
    start = raw.index('怡君')  # 使用 Python Unicode 字元位移
    return {'title': '午餐的故事', 'participants': [{'person_id': p[0]['id'], 'interacted': True}], 'mentions': [{'name': '怡君', 'start': start, 'end': start + 2}]}  # 未指定提及的正式身分


def saved_story(client, p, request_id='story-1', raw='今天與小安吃飯，提到怡君。', **overrides):  # 經由真實草稿及確認保存故事
    data = story_data(p, raw)  # 產生有效的原文來源
    data.update(overrides)  # 允許測試不同人物／標題情境
    response = client.post('/api/experiences/drafts', json={'raw_text': raw, 'occurred_at': '2026-01-01T12:00:00+08:00', 'contributions': [], 'story': data})  # 草稿先保存未審閱角色
    assert response.status_code == 201, response.text  # 驗證新草稿契約可用
    d = response.json()  # 取得伺服器版本
    body = confirm_payload(d, request_id=request_id, story=data, story_reviewed=True, interaction_type='in_person', tasks=[])  # 明確核對人物後確認
    response = client.post('/api/drafts/' + d['id'] + '/confirm', json=body)  # 使用既有交易確認入口
    assert response.status_code == 201, response.text  # 失敗不能被當成正式保存
    return response.json(), d, body  # 提供來源與重送驗證資料


def detail(client, experience_id, **params):  # 讀取交會的真實故事內容
    response = client.get('/api/connections/stories/' + experience_id, params=params)  # 來源由後端檢查權限
    assert response.status_code == 200, response.text  # 要求完整來源成功
    return response.json()  # 回傳解析後內容


def match(client, mention, person_id, key='match-1', **overrides):  # 明確配對或解除配對
    body = {'request_id': key, 'expected_revision': mention['revision'], 'status': 'matched' if person_id else 'unmatched', 'person_id': person_id, 'confirmed': True}  # 不把名字相同視為已確認
    body.update(overrides)  # 供版本／拒絕案例使用
    return client.post('/api/connections/mentions/' + mention['id'] + '/match', json=body)  # 使用獨立人工配對入口


def test_draft_roundtrip_confirm_and_durable_match(client, app):  # 正常：草稿、確認與持久配對不改參與及積分
    p = people(client)  # 建立虛構人物
    receipt, d, body = saved_story(client, p)  # 保存未配對提及
    assert client.get('/api/drafts/' + d['id']).json()['story'] == d['story']  # 確認後仍保留草稿整理內容
    before = client.get('/api/state').json()  # 記下獎勵與正式資料
    s = detail(client, receipt['experience_id'])  # 讀取正式來源
    assert [x['id'] for x in s['participants']] == [p[0]['id']]  # 被提及者不能進入參與名單
    m = s['mentions'][0]  # 取得待核對的原名線索
    assert m['person_id'] is None and m['status'] == 'unmatched'  # 同名人物也不得自動配對
    response = match(client, m, p[2]['id'])  # 人工選第二位同名者
    assert response.status_code == 200, response.text  # 確認配對已保存
    assert match(client, m, p[2]['id']).json() == response.json()  # 相同請求重送回同一回執
    fresh = TestClient(app); fresh.cookies.update(client.cookies)  # 使用新的讀取用戶端排除頁面暫存
    assert detail(fresh, s['id'])['mentions'][0]['person_id'] == p[2]['id']  # 配對存在資料庫
    assert client.get('/api/connections', params={'person_id': p[2]['id'], 'involvement': 'mention'}).json()['total'] == 1  # 僅在已核對提及查詢出現
    stats = client.get('/api/people/' + p[2]['id'] + '/overview').json()['stats']  # 檢查提及者互動統計
    assert stats['meetings'] == 0 and stats['interactions'] == 0  # 配對不等於見面
    assert client.get('/api/state').json()['rewards'] == before['rewards']  # 不因配對重發獎勵
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=body).json() == receipt  # 新欄位仍具確認去重


@pytest.mark.parametrize('change', ['range', 'duplicate_person', 'duplicate_span', 'unreviewed', 'foreign_person'])  # 涵蓋異常原文、重複與確認旗標
def test_rejects_invalid_links_atomically(client, change):  # 異常：關聯錯誤不留下半份經歷或獎勵
    p = people(client); raw = '今天與小安吃飯，提到怡君。'  # 準備固定原文
    data = story_data(p, raw)  # 建立合法基準
    if change == 'range': data['mentions'][0]['start'] = 0  # 刻意指定不吻合的來源位置
    if change == 'duplicate_person': data['participants'] *= 2  # 同人重複參與拒絕
    if change == 'duplicate_span': data['mentions'] *= 2  # 同位置重複線索拒絕
    if change == 'foreign_person': data['participants'][0]['person_id'] = 'not-owned'  # 不可信的人物 ID
    d = draft(client, client.get('/api/state').json()['goals'][0], raw_text=raw, contributions=[])  # 先保存不含新資料的草稿
    response = client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d, story=data, story_reviewed=change != 'unreviewed', contributions=[]))  # 在確認交易驗證全部輸入
    assert response.status_code in (404, 422), response.text  # 不接受無效關聯
    assert not client.get('/api/state').json()['experiences']  # 沒有半份經歷
    assert client.get('/api/state').json()['rewards']['total'] == 0  # 沒有錯發積分
    assert client.get('/api/drafts/' + d['id']).json()['status'] == 'draft'  # 原草稿仍可修正


def test_unicode_mentions_multiple_occurrences_and_only_mentions(client):  # 邊界：emoji 與同名多次提及不誤定位
    p = people(client); raw = '🌱怡君說起另一位怡君。'  # UTF-16 與 Unicode 位移不同的原文
    receipt, _, _ = saved_story(client, p, raw=raw, participants=[], mentions=[{'name': '怡君', 'start': 1, 'end': 3}, {'name': '怡君', 'start': 8, 'end': 10}])  # 分別保存兩處未配對人名
    s = detail(client, receipt['experience_id'])  # 回讀兩處來源
    assert len(s['participants']) == 0 and len(s['mentions']) == 2  # 只有提及也可成為故事
    assert all(s['raw_text'][m['start']:m['end']] == m['name'] for m in s['mentions'])  # 位置必須精確
    assert client.get('/api/people/' + p[0]['id'] + '/overview').json()['stats']['interactions'] == 0  # 不產生互動


def test_participation_without_direct_interaction_and_merged_sources(client):  # 邊界：同場與合併都不能擴張單筆故事名單
    p = people(client)  # 建立不同參與者
    a, _, _ = saved_story(client, p, participants=[{'person_id': p[0]['id'], 'interacted': True}, {'person_id': p[1]['id'], 'interacted': False}])  # 第二人只有同場
    b, _, _ = saved_story(client, p, request_id='story-2', participants=[{'person_id': p[2]['id'], 'interacted': True}])  # 另一筆故事的互動者不同
    assert client.get('/api/people/' + p[1]['id'] + '/overview').json()['stats']['meetings'] == 0  # 同場不自動算見面
    response = client.post('/api/interactions/' + a['interaction_event_id'] + '/merge', json={'request_id': 'merge', 'expected_revision': 1, 'source_event_ids': [b['interaction_event_id']]})  # 合併同一次實際事件
    assert response.status_code == 200, response.text  # 沿用事件合併能力
    assert [x['id'] for x in detail(client, b['experience_id'])['participants']] == [p[2]['id']]  # 不套用合併後人物聯集
    assert len(detail(client, a['experience_id'])['participants']) == 2  # 原來源名單仍獨立


def test_match_conflicts_unmatch_reject_and_history(client):  # 異常：版本與重送衝突可回復且保留歷史
    p = people(client); receipt, _, _ = saved_story(client, p)  # 建立待配對來源
    m = detail(client, receipt['experience_id'])['mentions'][0]  # 取得第一版線索
    response = match(client, m, p[1]['id'])  # 先完成配對
    assert response.status_code == 200, response.text  # 保存第一版變化
    assert match(client, m, p[2]['id']).status_code == 409  # 同 key 不同內容不可覆蓋
    assert match(client, m, p[2]['id'], key='old-version').status_code == 409  # 不同 key 的舊版本也拒絕
    current = detail(client, receipt['experience_id'])['mentions'][0]  # 取得新版線索
    assert match(client, current, None, key='unmatch').status_code == 200  # 可取消身分配對
    current = detail(client, receipt['experience_id'])['mentions'][0]  # 再讀最新版本
    assert match(client, current, None, key='reject', status='rejected').status_code == 200  # 拒絕候選不刪原句
    result = detail(client, receipt['experience_id'], manage=True)  # 本人可查修正歷史
    assert len(result['history']) == 3  # 配對／取消／拒絕均有記錄
    assert result['raw_text'] == '今天與小安吃飯，提到怡君。'  # 原文始終不變


def test_withdrawal_hides_source_and_paths_but_preserves_original(client):  # 異常：撤回交會展示後不得用舊連結繼續讀來源
    p = people(client); receipt, _, _ = saved_story(client, p)  # 建立可探索故事
    s = detail(client, receipt['experience_id']); before = client.get('/api/state').json()  # 保存原資料
    m = s['mentions'][0]  # 保存舊配對入口
    response = client.post('/api/connections/stories/' + s['id'] + '/availability', json={'request_id': 'withdraw', 'expected_revision': s['revision'], 'available': False})  # 撤回派生探索展示
    assert response.status_code == 200, response.text  # 撤回成功
    assert client.get('/api/connections/stories/' + s['id']).status_code == 404  # 探索來源失效
    assert client.get('/api/connections').json()['total'] == 0  # 搜尋及人物路徑同步移除
    assert match(client, m, p[1]['id']).status_code == 404  # 舊線索不可再配對
    after = client.get('/api/state').json()  # 原始紀錄仍在本人收藏
    assert after['experiences'] == before['experiences'] and after['rewards'] == before['rewards']  # 不刪原文或帳本
    assert detail(client, s['id'], manage=True)['available'] is False  # 本人仍有管理退路


def test_cross_account_access_and_guest_gate(client, app):  # 安全：不能讀取或配對另一帳號資料
    p = people(client); receipt, _, _ = saved_story(client, p)  # 第一個帳號的私人故事
    s = detail(client, receipt['experience_id'])  # 取得私人來源 ID
    with TestClient(app) as other:  # 另一份 Cookie 代表不同帳號
        onboard(other)  # 保持訪客狀態
        response = other.post('/api/experiences/drafts', json={'raw_text': '提到怡君', 'occurred_at': '2026-01-01T00:00:00Z', 'story': {'participants': [], 'mentions': [{'name': '怡君', 'start': 2, 'end': 4}]}})  # 訪客也不能以純提及繞過人物門檻
        assert response.status_code == 403, response.text  # 後端執行升級要求
        register(other, 'another_user')  # 允許使用人物功能後仍不能越權
        assert other.get('/api/connections').json()['total'] == 0  # 不洩露第一個帳號故事
        assert other.get('/api/connections/stories/' + s['id'], params={'manage': True}).status_code == 404  # 管理模式也不能繞權限
        assert match(other, s['mentions'][0], p[1]['id']).status_code == 404  # 寫入不能跨帳號


def test_legacy_review_and_empty_story_do_not_reaward(client):  # 相容：舊單一人物不猜測，可人工分類但不重發獎勵
    p = people(client); goal = client.get('/api/state').json()['goals'][0]  # 取得既有目標
    d = draft(client, goal, person_id=p[0]['id'])  # 舊 API 僅有一位關聯人物
    receipt = client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).json()  # 保留原確認行為
    assert client.get('/api/connections').json()['total'] == 0  # 不推測共同參與
    assert client.get('/api/connections', params={'involvement': 'legacy'}).json()['total'] == 1  # 有待核對入口
    s = detail(client, receipt['experience_id'], manage=True)  # 管理入口可讀舊原文
    before = client.get('/api/state').json()['rewards']  # 保存原帳本
    body = {'request_id': 'review-old', 'expected_revision': s['revision'], 'confirmed': True, 'story': {'title': '獨自練習', 'participants': [], 'mentions': []}}  # 使用者明確判定沒有共同參與
    response = client.put('/api/connections/stories/' + s['id'] + '/people', json=body)  # 不重做原經歷確認
    assert response.status_code == 200, response.text  # 可補分類
    assert detail(client, s['id'])['participants'] == []  # 不再推定舊人物參與
    assert client.get('/api/state').json()['rewards'] == before  # 不補發或扣除積分


def test_stable_pagination_and_draft_edit(client):  # 邊界：分頁不重複，草稿角色可重讀與更正
    p = people(client)  # 建立資料起點
    first, d, _ = saved_story(client, p)  # 第一份已確認故事
    second, _, _ = saved_story(client, p, request_id='next-story', title='另一段')  # 相同日期的另一份故事
    a = client.get('/api/connections', params={'limit': 1}).json()  # 取得第一頁
    b = client.get('/api/connections', params={'limit': 1, 'offset': 1}).json()  # 取得第二頁
    assert a['total'] == 2 and a['items'][0]['id'] != b['items'][0]['id']  # 同日期以固定 ID 分頁
    assert client.get('/api/connections', params={'limit': 0}).status_code == 422  # 無效分頁拒絕
    goal = client.get('/api/state').json()['goals'][0]  # 使用既有草稿測試工具
    draft_data = draft(client, goal, story=story_data(p), raw_text='今天與小安吃飯，提到怡君。')  # 先保存整理內容
    body = {k: draft_data[k] for k in ['raw_text', 'occurred_at', 'goal_id', 'person_id', 'contributions']}  # 只提交允許修改的欄位
    body.update(expected_revision=draft_data['revision'], story={'title': '新標題', 'participants': [], 'mentions': []})  # 明確清空人物清單
    response = client.put('/api/drafts/' + draft_data['id'], json=body)  # 版本化更新草稿
    assert response.status_code == 200 and response.json()['story']['title'] == '新標題'  # 新內容可重讀


def test_migration_preserves_legacy_rows_and_rewards(tmp_path):  # 遷移：v0.2 原欄位、帳本及人物不得被改寫
    from app.db import Database  # 延後載入以使用正式遷移器
    path = tmp_path / 'lifeworld.sqlite3'  # 模擬既有資料庫位置
    c = sqlite3.connect(str(path))  # 建立尚無新遷移的 SQLite
    c.execute('CREATE TABLE schema_migrations (version TEXT PRIMARY KEY)')  # 建立既有版本標記
    for name in ['001_initial.sql', '002_people_360.sql']:  # 僅套用舊版結構
        c.executescript((Path(__file__).parents[1] / 'app/migrations' / name).read_text())  # 使用原始舊遷移
        c.execute('INSERT INTO schema_migrations VALUES (?)', (name,))  # 記錄已執行版本
    c.execute("INSERT INTO users(id,status,created_at) VALUES ('u','registered','2026-01-01')")  # 建立虛構舊帳號
    c.execute("INSERT INTO drafts VALUES ('d','u',NULL,NULL,'舊原文','2026-01-01','[]','confirmed',1,'2026-01-01','2026-01-01')")  # 建立原草稿
    c.execute("INSERT INTO experiences VALUES ('x','u','d',NULL,NULL,'舊原文','舊摘要','2026-01-01','2026-01-01')")  # 建立舊經歷
    c.execute("INSERT INTO reward_ledger VALUES ('r','u','x',7,'old','2026-01-01')")  # 保留舊版獎勵規則
    before = {table: c.execute('SELECT * FROM ' + table).fetchall() for table in ['users', 'drafts', 'experiences', 'reward_ledger']}  # 保存完整舊資料
    c.commit(); c.close()  # 模擬舊服務停止
    db = Database(tmp_path)  # 正式遷移新結構
    with db.connect() as c:  # 驗證新結構與舊內容
        for table, rows in before.items(): assert [tuple(r) for r in c.execute('SELECT * FROM ' + table)] == rows  # 舊欄位完整相同
        assert c.execute("SELECT reviewed FROM experience_stories WHERE experience_id='x'").fetchone()[0] == 0  # 舊故事只標待確認
        assert not c.execute('PRAGMA foreign_key_check').fetchall()  # 外鍵仍完整


def test_person_overview_includes_participation_and_mentions_separately(client):  # 人物卡：同場故事與提及各自導通來源
    p = people(client)  # 建立主參與者與提及人物
    receipt, _, _ = saved_story(client, p, participants=[{'person_id': p[0]['id'], 'interacted': True}, {'person_id': p[1]['id'], 'interacted': False}])  # 第二人只參與未直接互動
    s = detail(client, receipt['experience_id'])  # 取得可人工配對的來源
    assert match(client, s['mentions'][0], p[2]['id']).status_code == 200  # 提及指向另一人物
    overview = client.get('/api/people/' + p[1]['id'] + '/overview').json()  # 同場人物沒有互動事件也應看得到故事
    assert overview['stories'][0]['id'] == s['id'] and overview['stats']['meetings'] == 0  # 參與故事與見面統計分開
    mentioned = client.get('/api/people/' + p[2]['id'] + '/overview').json()  # 讀提及者卡片
    assert mentioned['mentions'][0]['id'] == s['id'] and not mentioned['stories']  # 不混入共同參與


@pytest.mark.parametrize('operation', ['match_false', 'foreign_match', 'stale_people', 'stale_available'])  # 人工確認、所有權與版本錯誤
def test_new_writes_reject_invalid_confirmation_owner_or_revision(client, app, operation):  # 異常：拒絕無效操作且不改正式資料
    p = people(client); receipt, _, _ = saved_story(client, p)  # 建立第一版故事
    s = detail(client, receipt['experience_id'])  # 取得目前有效來源
    before = client.get('/api/state').json()['rewards']  # 保存帳本基準
    if operation == 'match_false': response = match(client, s['mentions'][0], p[1]['id'], confirmed=False)  # 不接受未確認身分
    elif operation == 'foreign_match':  # 使用另一帳號的真實人物 ID
        with TestClient(app) as other:  # 不共用 Cookie
            onboard(other); register(other, 'owner_other')  # 建立另一份世界
            foreign = other.post('/api/people', json={'name': '別人的人物'}).json()['id']  # 取得確實存在的跨帳號 ID
        response = match(client, s['mentions'][0], foreign)  # 不可偷用他人資料
    elif operation == 'stale_people': response = client.put('/api/connections/stories/' + s['id'] + '/people', json={'request_id': 'stale', 'expected_revision': 2, 'confirmed': True, 'story': {'participants': []}})  # 拒絕不存在的版本
    else: response = client.post('/api/connections/stories/' + s['id'] + '/availability', json={'request_id': 'stale', 'expected_revision': 2, 'available': False})  # 展示狀態也不能覆蓋較新資料
    assert response.status_code in (404, 409, 422), response.text  # 所有無效操作明確拒絕
    assert detail(client, s['id'])['revision'] == 1  # 失敗沒有半份角色更新
    assert client.get('/api/state').json()['rewards'] == before  # 拒絕操作不碰帳本
