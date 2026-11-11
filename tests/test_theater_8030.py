"""8030 人物劇場多角色演出（自 8445 移植）：演出設定（系統角色＋自己的角色卡，固定版本）→ 生成 → 原樣保存 → 改設定另存版本 → 規則與擁有者隔離。

只用隔離 SQLite 與 Fake Provider（不連網、不計費）。
"""
from fastapi.testclient import TestClient

from test_generation_8030 import client, copy_card, ready  # noqa: F401（pytest fixture）


def system(client, index):
    return client.get('/api/characters/system').json()['items'][index]


def cast_content(members, title='霧港夜談'):
    return {'title': title, 'scenario': {'text': '霧港的夜晚，兩支商隊在碼頭相遇，誰也不肯先讓路。', 'preset_id': None},
            'mode': 'faithful', 'direction': '節奏緊湊，最後留下懸念。', 'cast': members}


def system_member(item, position='protagonist'):
    return {'source': 'system', 'id': item['id'], 'version': item['version'], 'name': item['name'], 'position': position}


def card_member(card, position='opponent'):
    return {'source': 'card', 'id': card['id'], 'version': str(card['current_version']), 'name': card['version']['content']['name'], 'position': position}


def save_cast(client, members, request_id='cast-1'):
    response = client.post('/api/theater/casts', json={'request_id': request_id, 'content': cast_content(members)})
    assert response.status_code == 201, response.text
    return response.json()


def perform(client, cast, request_id='perform-1'):
    return client.post('/api/ai/generate', json={'request_id': request_id, 'module': 'theater_performance',
                                                 'input': {'cast_work_id': cast['id'], 'cast_version': cast['current_version']}})


def test_cast_perform_save_and_edit_cast(client):
    ready(client, 'theater_owner')
    card = copy_card(client, 1)
    cast = save_cast(client, [system_member(system(client, 0)), card_member(card)])
    assert cast['kind'] == 'theater_cast' and cast['version']['origin'] == 'human'
    generated = perform(client, cast)
    assert generated.status_code == 201, generated.text
    output = generated.json()['output']
    names = {member['name'] for member in output['cast']}
    assert output['cast_ref'] == {'work_id': cast['id'], 'version_no': 1} and 6 <= len(output['lines']) <= 12
    assert all(line['speaker'] in names | {'旁白'} for line in output['lines'])
    saved = client.post('/api/theater/performances', json={'request_id': 'save-perf', 'generation_id': generated.json()['generation']['id']})
    assert saved.status_code == 201, saved.text
    work = saved.json()
    assert work['kind'] == 'theater_performance' and work['version']['origin'] == 'ai' and work['version']['content'] == output
    assert client.post('/api/theater/performances', json={'request_id': 'save-perf', 'generation_id': generated.json()['generation']['id']}).json()['id'] == work['id']
    edited = client.post(f"/api/theater/casts/{cast['id']}/versions", json={'request_id': 'cast-edit', 'expected_revision': cast['revision'], 'base_version': 1,
                                                                             'content': {**cast_content([system_member(system(client, 0)), card_member(card)]), 'mode': 'free'}})
    assert edited.status_code == 201 and edited.json()['current_version'] == 2, edited.text
    assert client.get(f"/api/works/{work['id']}").json()['version']['content']['cast_ref']['version_no'] == 1, '已保存的演出仍引用原設定版本'
    assert client.get('/api/works?kind=theater_performance').json()['total'] == 1


def test_cast_rules(client):
    ready(client, 'theater_rules')
    card = copy_card(client, 1)
    first = system(client, 0)
    duplicate = client.post('/api/theater/casts', json={'request_id': 'dup', 'content': cast_content([system_member(first), system_member(first, 'opponent')])})
    assert duplicate.status_code == 422, '同一角色不能重複上場'
    solo = client.post('/api/theater/casts', json={'request_id': 'solo', 'content': cast_content([system_member(first)])})
    assert solo.status_code == 422, '至少 2 位'
    wrong = client.post('/api/theater/casts', json={'request_id': 'wrong', 'content': cast_content([system_member(first), {**card_member(card), 'name': '冒名'}])})
    assert wrong.status_code == 409 and wrong.json()['error']['code'] == 'source_mismatch'
    narrator = client.post('/api/theater/casts', json={'request_id': 'nar', 'content': cast_content([{**system_member(first), 'name': '旁白'}, card_member(card)])})
    assert narrator.status_code in (409, 422)
    cast = save_cast(client, [system_member(first), card_member(card)])
    generated = perform(client, cast).json()
    client.post(f"/api/characters/{card['id']}/status", json={'request_id': 'arch', 'expected_revision': card['revision'], 'status': 'archived'})
    blocked = client.post('/api/theater/performances', json={'request_id': 'save-after-archive', 'generation_id': generated['generation']['id']})
    assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'character_archived'


def test_other_account_cannot_use_cast_or_card(client):
    ready(client, 'theater_a')
    card = copy_card(client, 1)
    cast = save_cast(client, [system_member(system(client, 0)), card_member(card)])
    generated = perform(client, cast).json()
    other = TestClient(client.app)
    ready(other, 'theater_b')
    assert perform(other, cast, 'steal').status_code == 404
    assert other.post('/api/theater/performances', json={'request_id': 'steal-save', 'generation_id': generated['generation']['id']}).status_code == 404
    borrowed = other.post('/api/theater/casts', json={'request_id': 'borrow', 'content': cast_content([system_member(system(other, 0)), card_member(card)])})
    assert borrowed.status_code == 404, '不能把別人的角色卡加入陣容'


def test_archived_cast_cannot_start_generation_and_never_calls_provider(tmp_path, monkeypatch):
    """已封存的演出設定：在呼叫 Provider 與預留金額之前就拒絕；恢復後可以正常演出。"""
    from test_generation_8030 import LiveFake, ledger, make_client

    class Counting(LiveFake):
        calls = 0

        def generate(self, request):
            type(self).calls += 1
            return super().generate(request)
    monkeypatch.setenv('LIFEWORLD_AI_RESERVATION_MICROUSD', '1000')
    monkeypatch.setenv('LIFEWORLD_AI_DAILY_BUDGET_MICROUSD', '100000')
    Counting.calls = 0
    with make_client(tmp_path, Counting()) as c:
        ready(c, 'theater_archived')
        cast = save_cast(c, [system_member(system(c, 0)), card_member(copy_card(c, 1))])
        archived = c.post(f"/api/works/{cast['id']}/status", json={'request_id': 'arch', 'expected_revision': cast['revision'], 'status': 'archived'})
        assert archived.status_code == 200
        blocked = perform(c, cast, 'perform-archived')
        assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'work_archived'
        assert Counting.calls == 0 and ledger(c) == [], '沒有呼叫 Provider，也沒有預留金額'
        restored = c.post(f"/api/works/{cast['id']}/status", json={'request_id': 'restore', 'expected_revision': archived.json()['revision'], 'status': 'active'})
        assert restored.status_code == 200
        assert perform(c, cast, 'perform-restored').status_code == 201 and Counting.calls == 1, '恢復後可以正常演出'


def test_cast_lists_its_performances_and_editing_keeps_them(client):
    """演出設定頁：列出由這個設定產生的所有演出（含用到的設定版本）；修改設定只新增版本，既有演出內容不變；舊分頁不能覆寫。"""
    ready(client, 'theater_list')
    card = copy_card(client, 1)
    cast = save_cast(client, [system_member(system(client, 0)), card_member(card)])
    first = perform(client, cast, 'p1').json()
    saved_1 = client.post('/api/theater/performances', json={'request_id': 's1', 'generation_id': first['generation']['id']}).json()
    edited = client.post(f"/api/theater/casts/{cast['id']}/versions", json={'request_id': 'edit', 'expected_revision': cast['revision'], 'base_version': 1,
                                                                             'content': {**cast_content([system_member(system(client, 0)), card_member(card)], '霧港夜談・改'), 'mode': 'free'}})
    assert edited.status_code == 201, edited.text
    stale = client.post(f"/api/theater/casts/{cast['id']}/versions", json={'request_id': 'edit-old-tab', 'expected_revision': cast['revision'], 'base_version': 1,
                                                                            'content': cast_content([system_member(system(client, 0)), card_member(card)], '舊分頁')})
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'stale_version', '舊分頁不能覆寫演出設定'
    second = perform(client, edited.json(), 'p2').json()
    saved_2 = client.post('/api/theater/performances', json={'request_id': 's2', 'generation_id': second['generation']['id']}).json()
    other_cast = save_cast(client, [system_member(system(client, 0)), system_member(system(client, 2), 'opponent')], 'cast-other')
    other = perform(client, other_cast, 'p3').json()
    client.post('/api/theater/performances', json={'request_id': 's3', 'generation_id': other['generation']['id']})
    listed = client.get(f"/api/theater/casts/{cast['id']}/performances")
    assert listed.status_code == 200, listed.text
    items = listed.json()['items']
    assert [(i['id'], i['cast_version']) for i in items] == [(saved_2['id'], 2), (saved_1['id'], 1)], '只列這個設定的演出，新的在前'
    assert all(i['lines'] >= 6 for i in items)
    assert client.get(f"/api/works/{saved_1['id']}").json()['version']['content'] == saved_1['version']['content'], '修改設定不覆寫既有演出'
    outsider = TestClient(client.app)
    ready(outsider, 'theater_list_b')
    assert outsider.get(f"/api/theater/casts/{cast['id']}/performances").status_code == 404
