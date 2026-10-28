"""Original relationship flows: real data, provenance, events, compatibility."""  # 說明此模組的責任與實作邊界
from pathlib import Path  # 以跨平台方式組合檔案路徑
import sqlite3  # 讀寫 SQLite、執行遷移與一致性備份

import pytest  # 使用測試資源、參數化及例外斷言
from fastapi.testclient import TestClient  # 載入此模組需要的相依工具

from conftest import onboard, register, draft, confirm_payload, goal_payload  # 共用測試資料與前置流程


def person(client, name='林先生', **extra):  # 建立虛構人物並回傳伺服器結果
    r = client.post('/api/people', json=dict(name=name, **extra))  # 透過實際測試用戶端操作 API 並保留回應
    assert r.status_code == 201, r.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    return r.json()  # 回傳後續測試步驟所需資料


def event(client, goal, p, key='visit-1', kind='in_person', **extra):  # 建立並人工確認一筆虛構互動經歷
    d = draft(client, goal, person_id=p['id'])  # 讀取原始草稿與人工貢獻設定
    r = client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(
        d, request_id=key, interaction_type=kind, **extra))  # 透過實際測試用戶端操作 API 並保留回應
    assert r.status_code == 201, r.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    return r.json()  # 回傳後續測試步驟所需資料


def fact_body(experience_id, **extra):  # 建立附來源與明確確認旗標的人物資訊測試資料
    return dict(request_id='fact-1', dimension='food', value='不太吃辣', description='本人在午餐時提到。',
                evidence_type='stated_by_person', source_experience_ids=[experience_id], confirmed=True, **extra)  # 回傳後續測試步驟所需資料


def overview(client, p):  # 取得人物完整頁的 API 結果
    r = client.get('/api/people/' + p['id'] + '/overview')  # 透過實際測試用戶端操作 API 並保留回應
    assert r.status_code == 200, r.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    return r.json()  # 回傳後續測試步驟所需資料


def test_rich_person_and_optimistic_update(client):  # 驗證：多角色人物更新與舊版本拒絕
    onboard(client); register(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    p = person(client, roles=['客戶', '跑步夥伴'], tags=['音樂'], category='business', followed=True)  # 準備目前人物的完整基本資料
    assert p['roles'] == ['客戶', '跑步夥伴']  # 斷言多角色人物更新與舊版本拒絕的預期結果
    assert p['followed'] is True  # 斷言多角色人物更新與舊版本拒絕的預期結果
    body = dict(expected_revision=p['revision'], name='林先生', roles=['合作夥伴'], tags=['登山'],
                category='life', followed=False, notes='原備註', common_context='同學')  # 保存「body」供後續驗證或回傳使用
    r = client.patch('/api/people/' + p['id'], json=body)  # 透過實際測試用戶端操作 API 並保留回應
    assert r.status_code == 200, r.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert r.json()['revision'] == p['revision'] + 1  # 核對資料版本或版本衝突結果
    assert client.patch('/api/people/' + p['id'], json=body).status_code == 409  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert overview(client, p)['person']['common_context'] == '同學'  # 斷言多角色人物更新與舊版本拒絕的預期結果


def test_search_and_priority_shared_by_both_views(client):  # 驗證：星圖與收藏冊共用搜尋及分層排序
    _, goal = onboard(client); register(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    a = person(client, '阿雅', roles=['朋友'], tags=['音樂'], followed=True)  # 建立虛構人物並回傳伺服器結果
    b = person(client, '小林', roles=['教練'])  # 建立虛構人物並回傳伺服器結果
    c = person(client, '小陳')  # 建立虛構人物並回傳伺服器結果
    r = client.post('/api/people/' + b['id'] + '/goals', json={'request_id':'link', 'goal_id':goal['id'], 'label':'準備作品'})  # 透過實際測試用戶端操作 API 並保留回應
    assert r.status_code == 201, r.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    d = draft(client, goal, person_id=c['id'], goal_id=None, contributions=[])  # 讀取原始草稿與人工貢獻設定
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    items = client.get('/api/people').json()['items']  # 透過實際測試用戶端操作 API 並保留回應
    assert [p['id'] for p in items] == [a['id'], b['id'], c['id']]  # 斷言星圖與收藏冊共用搜尋及分層排序的預期結果
    for query, expected in [('音樂', a), ('教練', b), ('靠近更好的自己', b)]:  # 逐項處理測試資料與預期結果
        result = client.get('/api/people', params={'q':query}).json()  # 透過實際測試用戶端操作 API 並保留回應
        assert [p['id'] for p in result['items']] == [expected['id']]  # 斷言星圖與收藏冊共用搜尋及分層排序的預期結果
    assert client.get('/api/people', params={'followed_only':True}).json()['total'] == 1  # 斷言星圖與收藏冊共用搜尋及分層排序的預期結果
    assert client.get('/api/people', params={'sort':'invalid'}).status_code == 422  # 核對 HTTP 狀態，避免失敗請求被當成成功


def test_overview_empty_dimensions_are_not_fabricated(client):  # 驗證：未知維度保持空白，不產生假事實
    onboard(client); register(client); p = person(client, notes='這只是舊備註，不是已驗證偏好。')  # 完成訪客、Bio 與第一目標的測試前置流程
    data = overview(client, p)  # 取得人物完整頁的 API 結果
    assert data['facts'] == {'interests':[], 'food':[], 'skills':[], 'habits':[]}  # 斷言未知維度保持空白，不產生假事實的預期結果
    assert data['stats'] == {'meetings':0, 'interactions':0, 'last_interaction_at':None}  # 斷言未知維度保持空白，不產生假事實的預期結果
    assert data['person']['notes'] == p['notes']  # 斷言未知維度保持空白，不產生假事實的預期結果


def test_distinct_event_stats_classification_and_merge_preserve_rewards(client):  # 驗證：事件分類與合併不重複計見面且保留積分
    _, goal = onboard(client); register(client); p = person(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    a = event(client, goal, p, 'one', 'in_person')  # 建立並人工確認一筆虛構互動經歷
    b = event(client, goal, p, 'two', 'call')  # 建立並人工確認一筆虛構互動經歷
    event(client, goal, p, 'three', 'unknown')  # 建立並人工確認一筆虛構互動經歷
    data = overview(client, p)  # 取得人物完整頁的 API 結果
    assert data['stats']['meetings'] == 1  # 斷言事件分類與合併不重複計見面且保留積分的預期結果
    assert data['stats']['interactions'] == 3  # 斷言事件分類與合併不重複計見面且保留積分的預期結果
    events = client.get('/api/people/' + p['id'] + '/interactions').json()['items']  # 透過實際測試用戶端操作 API 並保留回應
    assert len(events) == 3  # 斷言事件分類與合併不重複計見面且保留積分的預期結果
    target = next(e for e in events if e['id'] == a['interaction_event_id'])  # 準備互動合併要保留的主要事件
    body = {'request_id':'merge-1','expected_revision':target['revision'], 'source_event_ids':[b['interaction_event_id']]}  # 保存「body」供後續驗證或回傳使用
    r = client.post('/api/interactions/' + target['id'] + '/merge', json=body)  # 透過實際測試用戶端操作 API 並保留回應
    assert r.status_code == 200, r.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.post('/api/interactions/' + target['id'] + '/merge', json=body).json() == r.json()  # 斷言事件分類與合併不重複計見面且保留積分的預期結果
    data = overview(client, p)  # 取得人物完整頁的 API 結果
    assert data['stats']['meetings'] == 1  # 斷言事件分類與合併不重複計見面且保留積分的預期結果
    assert data['stats']['interactions'] == 2  # 斷言事件分類與合併不重複計見面且保留積分的預期結果
    assert len(data['interactions'][0]['experiences']) in (1,2)  # 斷言事件分類與合併不重複計見面且保留積分的預期結果
    world = client.get('/api/state').json()  # 透過實際測試用戶端操作 API 並保留回應
    assert world['rewards']['total'] == 9  # 核對積分帳本符合本案例預期
    assert len(world['experiences']) == 3  # 斷言事件分類與合併不重複計見面且保留積分的預期結果
    assert world['goals'][0]['actions'][0]['progress'] == '1.5'  # 斷言事件分類與合併不重複計見面且保留積分的預期結果


def test_attach_multiple_experiences_to_same_event(client):  # 驗證：同事件多筆經歷只算一次互動
    _, goal = onboard(client); register(client); p = person(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    a = event(client, goal, p)  # 建立並人工確認一筆虛構互動經歷
    event(client, goal, p, 'attachment', 'unknown', interaction_event_id=a['interaction_event_id'])  # 建立並人工確認一筆虛構互動經歷
    assert overview(client, p)['stats']['meetings'] == 1  # 斷言同事件多筆經歷只算一次互動的預期結果
    assert overview(client, p)['stats']['interactions'] == 1  # 斷言同事件多筆經歷只算一次互動的預期結果


def test_classify_legacy_unknown_without_award(client):  # 驗證：分類舊未分類事件不發新積分
    _, goal = onboard(client); register(client); p = person(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    r = event(client, goal, p, kind='unknown')  # 建立並人工確認一筆虛構互動經歷
    e = overview(client, p)['interactions'][0]  # 保存「e」供後續驗證或回傳使用
    assert e['kind'] == 'unknown'  # 斷言分類舊未分類事件不發新積分的預期結果
    body = {'expected_revision':e['revision'], 'kind':'in_person'}  # 保存「body」供後續驗證或回傳使用
    assert client.patch('/api/interactions/' + e['id'], json=body).status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.patch('/api/interactions/' + e['id'], json=body).status_code == 409  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert overview(client, p)['stats']['meetings'] == 1  # 斷言分類舊未分類事件不發新積分的預期結果
    assert client.get('/api/state').json()['rewards']['total'] == 3  # 核對積分帳本符合本案例預期


def test_fact_provenance_dedup_and_no_extra_points(client):  # 驗證：同值事實可增加來源而不重複計分
    _, goal = onboard(client); register(client); p = person(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    a = event(client, goal, p)  # 建立並人工確認一筆虛構互動經歷
    path = '/api/people/' + p['id'] + '/facts'  # 保存「path」供後續驗證或回傳使用
    body = fact_body(a['experience_id'])  # 建立附來源與明確確認旗標的人物資訊測試資料
    r = client.post(path, json=body)  # 透過實際測試用戶端操作 API 並保留回應
    assert r.status_code == 201, r.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.post(path, json=body).json()['id'] == r.json()['id']  # 斷言同值事實可增加來源而不重複計分的預期結果
    b = event(client, goal, p, 'second')  # 建立並人工確認一筆虛構互動經歷
    body.update(request_id='fact-2', source_experience_ids=[b['experience_id']])  # 合併本次明確設定的欄位
    assert client.post(path, json=body).json()['id'] == r.json()['id']  # 斷言同值事實可增加來源而不重複計分的預期結果
    facts = overview(client, p)['facts']['food']  # 準備依四個維度分組的已確認與衝突資訊
    assert len(facts) == 1  # 斷言同值事實可增加來源而不重複計分的預期結果
    sources = client.get(path + '/' + r.json()['id'] + '/evidence').json()['sources']  # 透過實際測試用戶端操作 API 並保留回應
    assert len(sources) == 2  # 斷言同值事實可增加來源而不重複計分的預期結果
    assert sources[0]['raw_text'] == '今天練習了半小時，感到很充實。'  # 斷言同值事實可增加來源而不重複計分的預期結果
    assert sources[0]['evidence_type'] == 'stated_by_person'  # 斷言同值事實可增加來源而不重複計分的預期結果
    assert client.get('/api/state').json()['rewards']['total'] == 6  # 核對積分帳本符合本案例預期


def test_fact_conflict_resolution_and_source_revocation(client):  # 驗證：衝突資訊需人工採用且來源可撤回
    _, goal = onboard(client); register(client); p = person(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    a = event(client, goal, p)  # 建立並人工確認一筆虛構互動經歷
    path = '/api/people/' + p['id'] + '/facts'  # 保存「path」供後續驗證或回傳使用
    first = client.post(path, json=fact_body(a['experience_id'])).json()  # 透過實際測試用戶端操作 API 並保留回應
    body = fact_body(a['experience_id']); body.update(request_id='opposite', value='可以吃辣', conflicts_with=first['id'])  # 建立附來源與明確確認旗標的人物資訊測試資料
    second = client.post(path, json=body).json()  # 透過實際測試用戶端操作 API 並保留回應
    assert {f['status'] for f in overview(client, p)['facts']['food']} == {'conflict'}  # 斷言衝突資訊需人工採用且來源可撤回的預期結果
    assert client.post(path + '/' + second['id'] + '/resolve', json={'expected_revision':second['revision']}).status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    active = overview(client, p)['facts']['food']  # 保存「active」供後續驗證或回傳使用
    assert [f['value'] for f in active] == ['可以吃辣']  # 斷言衝突資訊需人工採用且來源可撤回的預期結果
    assert active[0]['status'] == 'confirmed'  # 斷言衝突資訊需人工採用且來源可撤回的預期結果
    r = client.post(path + '/' + second['id'] + '/sources/revoke', json={'expected_revision':active[0]['revision'], 'experience_id':a['experience_id']})  # 透過實際測試用戶端操作 API 並保留回應
    assert r.status_code == 200, r.text  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert overview(client, p)['facts']['food'] == []  # 斷言衝突資訊需人工採用且來源可撤回的預期結果
    assert client.get('/api/state').json()['rewards']['total'] == 3  # 核對積分帳本符合本案例預期


def test_dimension_tags_are_searchable_and_archived_conflicts_are_visible(client):  # 驗證：維度標籤可搜尋且封存衝突仍可回溯
    _, goal = onboard(client); register(client); p = person(client); a = event(client, goal, p)  # 完成訪客、Bio 與第一目標的測試前置流程
    path = '/api/people/' + p['id'] + '/facts'  # 保存「path」供後續驗證或回傳使用
    first = client.post(path, json=fact_body(a['experience_id'])).json()  # 透過實際測試用戶端操作 API 並保留回應
    assert client.get('/api/people', params={'q':'不太吃辣'}).json()['total'] == 1  # 斷言維度標籤可搜尋且封存衝突仍可回溯的預期結果
    body = fact_body(a['experience_id']); body.update(request_id='contradiction', value='可以吃辣', conflicts_with=first['id'])  # 建立附來源與明確確認旗標的人物資訊測試資料
    new = client.post(path, json=body).json()  # 透過實際測試用戶端操作 API 並保留回應
    client.post(path + '/' + new['id'] + '/resolve', json={'expected_revision':new['revision']})  # 透過實際測試用戶端操作 API 並保留回應
    data = overview(client, p)  # 取得人物完整頁的 API 結果
    assert [f['id'] for f in data['fact_history']] == [first['id']]  # 斷言維度標籤可搜尋且封存衝突仍可回溯的預期結果
    assert data['fact_history'][0]['status'] == 'archived'  # 斷言維度標籤可搜尋且封存衝突仍可回溯的預期結果
    body = fact_body(a['experience_id']); body['request_id'] = 'cannot-silently-reactivate'  # 建立附來源與明確確認旗標的人物資訊測試資料
    assert client.post(path, json=body).status_code == 409  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert client.post(path + '/' + first['id'] + '/resolve', json={'expected_revision':data['fact_history'][0]['revision']}).status_code == 200  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert overview(client, p)['facts']['food'][0]['value'] == '不太吃辣'  # 斷言維度標籤可搜尋且封存衝突仍可回溯的預期結果


@pytest.mark.parametrize('change', [{'confirmed':False}, {'source_experience_ids':[]}, {'dimension':'psychology'}, {'value':'   '}])  # 以同一組斷言涵蓋多種正常、異常或邊界輸入
def test_fact_requires_explicit_confirmation_and_valid_evidence(client, change):  # 驗證：人物資訊必須明確確認並有有效來源
    _, goal = onboard(client); register(client); p = person(client); a = event(client, goal, p)  # 完成訪客、Bio 與第一目標的測試前置流程
    body = fact_body(a['experience_id']); body.update(change)  # 建立附來源與明確確認旗標的人物資訊測試資料
    assert client.post('/api/people/' + p['id'] + '/facts', json=body).status_code == 422  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert overview(client, p)['facts']['food'] == []  # 斷言人物資訊必須明確確認並有有效來源的預期結果


def test_confirmation_only_writes_explicitly_selected_person_updates(client):  # 驗證：經歷確認只採用已勾選的人物更新
    _, goal = onboard(client); register(client); p = person(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    d = draft(client, goal, person_id=p['id'])  # 讀取原始草稿與人工貢獻設定
    body = confirm_payload(d, person_updates=[{'dimension':'interests','value':'登山','description':'本人陳述',
            'evidence_type':'stated_by_person','selected':False}])  # 建立攜帶版本與提交代碼的人工確認測試資料
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=body).status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert overview(client, p)['facts']['interests'] == []  # 斷言經歷確認只採用已勾選的人物更新的預期結果
    d = draft(client, goal, person_id=p['id']); body['expected_revision'] = d['revision']; body['request_id'] = 'selected'  # 讀取原始草稿與人工貢獻設定
    body['person_updates'][0]['selected'] = True  # 保存「body['person_updates'][0]['selected']」供後續驗證或回傳使用
    assert client.post('/api/drafts/' + d['id'] + '/confirm', json=body).status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert overview(client, p)['facts']['interests'][0]['value'] == '登山'  # 斷言經歷確認只採用已勾選的人物更新的預期結果


def test_goal_context_connections_and_private_sources(client):  # 驗證：目標上下文、明確人物關係及私人引用來源
    _, goal = onboard(client); register(client); p = person(client); other = person(client, '王先生')  # 完成訪客、Bio 與第一目標的測試前置流程
    a = event(client, goal, p)  # 建立並人工確認一筆虛構互動經歷
    r = client.post('/api/people/' + p['id'] + '/goals', json={'request_id':'goal-link','goal_id':goal['id'],'label':'整理合作提案'})  # 透過實際測試用戶端操作 API 並保留回應
    assert r.status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert overview(client, p)['goals'][0]['id'] == goal['id']  # 斷言目標上下文、明確人物關係及私人引用來源的預期結果
    assert overview(client, p)['tasks'][0]['title'] == '明天繼續練習'  # 斷言目標上下文、明確人物關係及私人引用來源的預期結果
    body = {'request_id':'connection','other_person_id':other['id'],'label':'創業交流會認識','source_experience_ids':[a['experience_id']]}  # 保存「body」供後續驗證或回傳使用
    assert client.post('/api/people/' + p['id'] + '/connections', json=body).status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert overview(client, other)['connections'][0]['person']['id'] == p['id']  # 斷言目標上下文、明確人物關係及私人引用來源的預期結果
    note = {'person_id':p['id'],'kind':'simulation','title':'練習','content':'模擬而已','source_experience_ids':[a['experience_id']]}  # 保存「note」供後續驗證或回傳使用
    assert client.post('/api/notes', json=note).status_code == 201  # 核對 HTTP 狀態，避免失敗請求被當成成功
    assert overview(client, p)['notes'][0]['source_experience_ids'] == [a['experience_id']]  # 斷言目標上下文、明確人物關係及私人引用來源的預期結果
    assert overview(client, p)['stats']['interactions'] == 1  # 斷言目標上下文、明確人物關係及私人引用來源的預期結果
    assert client.get('/api/state').json()['rewards']['total'] == 3  # 核對積分帳本符合本案例預期


def test_guest_gates_and_cross_owner_all_new_resources(app, client):  # 驗證：新資源的訪客限制及跨帳號存取拒絕
    _, goal = onboard(client)  # 完成訪客、Bio 與第一目標的測試前置流程
    assert client.get('/api/people').json()['items'] == []  # 斷言新資源的訪客限制及跨帳號存取拒絕的預期結果
    assert client.post('/api/people/x/facts', json=fact_body('x')).status_code == 403  # 核對 HTTP 狀態，避免失敗請求被當成成功
    register(client); p = person(client); a = event(client, goal, p)  # 升級測試帳號並更新 CSRF 標頭
    f = client.post('/api/people/' + p['id'] + '/facts', json=fact_body(a['experience_id'])).json()  # 透過實際測試用戶端操作 API 並保留回應
    with TestClient(app) as other:  # 以區塊生命週期確保資源在結束時關閉
        _, g = onboard(other); register(other, 'other_user'); own = person(other)  # 完成訪客、Bio 與第一目標的測試前置流程
        assert other.get('/api/people/' + p['id'] + '/overview').status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功
        assert other.patch('/api/people/' + p['id'], json={'expected_revision':1, 'followed':True}).status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功
        assert other.get('/api/people/' + p['id'] + '/facts/' + f['id'] + '/evidence').status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功
        assert other.patch('/api/interactions/' + a['interaction_event_id'], json={'expected_revision':1,'kind':'call'}).status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功
        assert other.post('/api/people/' + own['id'] + '/goals', json={'request_id':'x','goal_id':goal['id']}).status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功
        assert other.post('/api/people/' + own['id'] + '/facts', json=fact_body(a['experience_id'])).status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功
        assert other.post('/api/people/' + own['id'] + '/connections', json={'request_id':'x','other_person_id':p['id'],'label':'x'}).status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功
        assert other.post('/api/notes', json={'person_id':own['id'],'kind':'preparation','title':'x','content':'x','source_experience_ids':[a['experience_id']]}).status_code == 404  # 核對 HTTP 狀態，避免失敗請求被當成成功


def test_person_update_failure_rolls_back_confirmation(app, client, monkeypatch):  # 驗證：人物更新失敗時整筆經歷確認回滾
    _, goal = onboard(client); register(client); p = person(client); d = draft(client, goal, person_id=p['id'])  # 完成訪客、Bio 與第一目標的測試前置流程
    def fail(*args, **kwargs): raise RuntimeError('injected people write failure')  # 注入測試用失敗以驗證交易整體回滾
    monkeypatch.setattr(app.state.service, '_apply_person_updates', fail)  # 注入替代行為，驗證失敗時不會部分寫入
    with TestClient(app, raise_server_exceptions=False) as safe:  # 以區塊生命週期確保資源在結束時關閉
        safe.cookies.update(client.cookies); safe.headers.update(client.headers)  # 合併本次明確設定的欄位
        assert safe.post('/api/drafts/' + d['id'] + '/confirm', json=confirm_payload(d)).status_code == 500  # 核對 HTTP 狀態，避免失敗請求被當成成功
    world = client.get('/api/state').json()  # 透過實際測試用戶端操作 API 並保留回應
    assert world['experiences'] == [] and world['rewards']['total'] == 0  # 核對積分帳本符合本案例預期
    assert overview(client, p)['stats']['interactions'] == 0  # 斷言人物更新失敗時整筆經歷確認回滾的預期結果


def test_upgrade_migrates_legacy_without_inventing_facts_or_changing_rewards(tmp_path):  # 驗證：舊資料升級不杜撰事實且保留原角色與積分
    from app.main import create_app  # 使用正式 App 工廠建立服務或測試實例
    db = tmp_path / 'lifeworld.sqlite3'  # 保存「db」供後續驗證或回傳使用
    with sqlite3.connect(db) as c:  # 以區塊生命週期確保資源在結束時關閉
        c.executescript((Path('app/migrations/001_initial.sql')).read_text())  # 執行目前交易中的參數化查詢
        c.execute('CREATE TABLE schema_migrations(version TEXT PRIMARY KEY)')  # 定義已套用遷移版本
        c.execute("INSERT INTO schema_migrations VALUES ('001_initial.sql')")  # 新增已套用遷移版本
        c.execute("INSERT INTO users(id,status,name,bio,created_at,hatched_at) VALUES ('u','registered','u','bio','2026-01-01','2026-01-01')")  # 新增帳號與個人介紹
        c.execute("INSERT INTO people VALUES ('p','u','林先生','客戶、朋友','原文偏好不是事實','2026-01-01')")  # 新增人物基本資料
        c.execute("INSERT INTO drafts VALUES ('d','u',NULL,'p','原文','2026-01-01T00:00:00+00:00','[]','confirmed',1,'2026-01-01','2026-01-01')")  # 新增經歷草稿
        c.execute("INSERT INTO experiences VALUES ('e','u','d',NULL,'p','原文','摘要','2026-01-01T00:00:00+00:00','2026-01-02')")  # 新增已確認經歷
        c.execute("INSERT INTO reward_ledger VALUES ('r','u','e',7,'old','2026-01-02')")  # 新增積分帳本
    app = create_app(data_dir=tmp_path)  # 準備本機 FastAPI 應用程式
    data = app.state.service.person_overview('u','p')  # 組合人物三分頁需要的事實、來源與互動資料
    assert data['person']['roles'] == ['客戶、朋友']  # 斷言舊資料升級不杜撰事實且保留原角色與積分的預期結果
    assert data['person']['notes'] == '原文偏好不是事實'  # 斷言舊資料升級不杜撰事實且保留原角色與積分的預期結果
    assert data['stats']['meetings'] == 0 and data['stats']['interactions'] == 1  # 斷言舊資料升級不杜撰事實且保留原角色與積分的預期結果
    assert data['interactions'][0]['kind'] == 'unknown'  # 斷言舊資料升級不杜撰事實且保留原角色與積分的預期結果
    assert all(not facts for facts in data['facts'].values())  # 斷言舊資料升級不杜撰事實且保留原角色與積分的預期結果
    assert app.state.service.state('u')['rewards']['total'] == 7  # 核對積分帳本符合本案例預期
    assert create_app(data_dir=tmp_path).state.service.person_overview('u','p')['stats']['interactions'] == 1  # 斷言舊資料升級不杜撰事實且保留原角色與積分的預期結果
