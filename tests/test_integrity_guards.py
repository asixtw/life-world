"""第四輪獨立驗收（Codex FAIL）後補上的兩項後端防護。

FIX-2　我的經歷是本人實際參與的事：關聯人物與故事參與人物只能是使用中的真實人物。
       歷史人物與虛構人物在草稿建立、草稿修改、確認三個地方都被後端拒絕；拒絕時不產生草稿、經歷、積分或目標進度。
FIX-3　人物經歷或我的經歷被人物關係引用為來源時，不能改到讓引用失效（移除最後一位相關的人、封存）。
       先回 409 relation_source_in_use，不修改經歷、不修改關係、不刪除來源；使用者先調整關係來源再修改。

這是本機 SQLite 的開發檢查；正式驗收在 Cloud SQL：tests/test_integrity_guards_cloudsql_e2e.py。
"""
from conftest import confirm_payload, draft, onboard, register

WHEN = '2026-10-27T00:10:00+08:00'


def person(client, key, name, **body):
    response = client.post('/api/persons', json={'request_id': key, 'name': name, **body})
    assert response.status_code == 201, response.text
    return response.json()


def world(client, username='guard_owner'):
    _, goal = onboard(client)
    register(client, username)
    return goal, person(client, 'g-real', '王小明'), person(client, 'g-hist', '周瑜', person_subtype='historical'), person(client, 'g-fict', '沈知衡', person_subtype='original')


def draft_body(goal, **extra):
    return {'raw_text': '今天練習了半小時。', 'occurred_at': WHEN, 'goal_id': goal['id'],
            'contributions': [{'action_id': goal['actions'][0]['id'], 'quantity': '0.5'}], **extra}


def totals(client):
    state = client.get('/api/state').json()
    progress = [action['progress'] for goal in state['goals'] for action in goal['actions']]
    return len(state['drafts']), len(state['experiences']), state['rewards']['total'], progress


def code(response):
    return response.status_code, response.json().get('error', {}).get('code')


def edit_person(client, target, **changes):
    current = client.get(f"/api/persons/{target['id']}").json()['person']
    response = client.patch(f"/api/persons/{target['id']}", json={'expected_revision': current['revision'], **changes})
    assert response.status_code == 200, response.text


def set_status(client, target, key, status):
    current = client.get(f"/api/persons/{target['id']}").json()['person']
    response = client.post(f"/api/persons/{target['id']}/status", json={'request_id': key, 'expected_revision': current['revision'], 'status': status})
    assert response.status_code == 200, response.text


# ---------------- FIX-2 ----------------

def test_real_person_and_no_person_still_work_and_earn_points(client):
    goal, real, _, _ = world(client)
    before = totals(client)
    with_person = draft(client, goal, person_id=real['id'])
    done = client.post(f"/api/drafts/{with_person['id']}/confirm", json=confirm_payload(with_person, request_id='ok-1'))
    assert done.status_code == 201, done.text
    alone = draft(client, goal, raw_text='自己讀了一章。')
    assert client.post(f"/api/drafts/{alone['id']}/confirm", json=confirm_payload(alone, request_id='ok-2')).status_code == 201
    after = totals(client)
    assert after[1] == before[1] + 2 and after[2] > before[2]


def test_historical_and_fictional_people_are_rejected_when_the_draft_is_created(client):
    goal, _, hist, fict = world(client)
    before = totals(client)
    for target in (hist, fict):  # 直接打 API（繞過前端的選擇器）
        assert code(client.post('/api/experiences/drafts', json=draft_body(goal, person_id=target['id']))) == (422, 'person_not_recordable')
    assert totals(client) == before  # 沒有草稿、沒有經歷、沒有積分、沒有目標進度


def test_draft_cannot_be_switched_to_an_ineligible_person(client):
    goal, real, hist, _ = world(client)
    d = draft(client, goal, person_id=real['id'])
    response = client.put(f"/api/drafts/{d['id']}", json=draft_body(goal, person_id=hist['id'], expected_revision=d['revision']))
    assert code(response) == (422, 'person_not_recordable')
    kept = client.get(f"/api/drafts/{d['id']}").json()
    assert kept['person_id'] == real['id'] and kept['revision'] == d['revision']


def test_confirm_checks_the_person_again_and_awards_nothing_on_rejection(client):
    goal, real, hist, fict = world(client)
    d = draft(client, goal, person_id=real['id'])
    before = totals(client)
    # 確認時改送虛構人物、歷史人物
    for key, target in (('c-fict', fict), ('c-hist', hist)):
        response = client.post(f"/api/drafts/{d['id']}/confirm", json=confirm_payload(d, request_id=key, person_id=target['id']))
        assert code(response) == (422, 'person_not_recordable')
    # 草稿建立之後，人物被改成虛構人物、或被封存：確認時重新驗證
    edit_person(client, real, person_type='fictional', person_subtype='original')
    assert code(client.post(f"/api/drafts/{d['id']}/confirm", json=confirm_payload(d, request_id='c-changed'))) == (422, 'person_not_recordable')
    edit_person(client, real, person_type='real', person_subtype=None)
    set_status(client, real, 'arch-1', 'archived')
    assert code(client.post(f"/api/drafts/{d['id']}/confirm", json=confirm_payload(d, request_id='c-archived'))) == (409, 'person_archived')
    assert totals(client) == before  # 全部失敗：仍是一份草稿、沒有經歷、積分與進度不變
    set_status(client, real, 'arch-2', 'active')
    assert client.post(f"/api/drafts/{d['id']}/confirm", json=confirm_payload(d, request_id='c-ok')).status_code == 201


def test_story_participants_are_all_or_nothing(client):
    goal, real, hist, fict = world(client)
    mixed = {'title': '聚會', 'participants': [{'person_id': real['id'], 'interacted': True}, {'person_id': fict['id'], 'interacted': False}], 'mentions': []}
    before = totals(client)
    # 草稿階段：名單裡有一位不合規，整筆拒絕
    assert code(client.post('/api/experiences/drafts', json=draft_body(goal, story=mixed))) == (422, 'person_not_recordable')
    only_hist = {'title': '', 'participants': [{'person_id': hist['id'], 'interacted': False}], 'mentions': []}
    assert code(client.post('/api/experiences/drafts', json=draft_body(goal, story=only_hist))) == (422, 'person_not_recordable')
    assert totals(client) == before
    # 確認階段：草稿合法，確認時送進不合規的名單，同樣整筆拒絕
    good = {'title': '聚會', 'participants': [{'person_id': real['id'], 'interacted': True}], 'mentions': []}
    d = draft(client, goal, story=good)
    body = confirm_payload(d, request_id='s-bad', story=mixed, story_reviewed=True, interaction_type='in_person', tasks=[])
    middle = totals(client)
    assert code(client.post(f"/api/drafts/{d['id']}/confirm", json=body)) == (422, 'person_not_recordable')
    assert totals(client) == middle
    body = confirm_payload(d, request_id='s-ok', story=good, story_reviewed=True, interaction_type='in_person', tasks=[])
    assert client.post(f"/api/drafts/{d['id']}/confirm", json=body).status_code == 201


def test_correcting_an_old_story_keeps_its_people_but_cannot_add_ineligible_ones(client):
    """既有已確認的經歷不追溯：原本就在名單裡的人物（之後才被改成歷史人物）可以留著，但不能再加入不合規的人物。"""
    goal, real, hist, _ = world(client)
    story = {'title': '午餐', 'participants': [{'person_id': real['id'], 'interacted': True}], 'mentions': []}
    d = draft(client, goal, story=story)
    done = client.post(f"/api/drafts/{d['id']}/confirm", json=confirm_payload(d, request_id='old-1', story=story, story_reviewed=True, interaction_type='in_person', tasks=[]))
    assert done.status_code == 201, done.text
    experience_id = done.json()['experience_id']
    edit_person(client, real, person_subtype='historical')
    current = client.get(f'/api/connections/stories/{experience_id}?manage=true').json()
    keep = {'request_id': 'old-keep', 'expected_revision': current['revision'], 'confirmed': True, 'story': {**story, 'title': '午餐（更正標題）'}}
    assert client.put(f'/api/connections/stories/{experience_id}/people', json=keep).status_code == 200
    current = client.get(f'/api/connections/stories/{experience_id}?manage=true').json()
    more = {'request_id': 'old-add', 'expected_revision': current['revision'], 'confirmed': True,
            'story': {**story, 'participants': story['participants'] + [{'person_id': hist['id'], 'interacted': False}]}}
    assert code(client.put(f'/api/connections/stories/{experience_id}/people', json=more)) == (422, 'person_not_recordable')


# ---------------- FIX-3 ----------------

def people4(client, username='source_owner'):
    onboard(client)
    register(client, username)
    return [person(client, f's-{i}', name, person_subtype='historical') for i, name in enumerate(('周瑜', '孫策', '魯肅', '小喬'))]


def experience(client, subject, participants, key='x-1'):
    response = client.post('/api/person-experiences', json={'request_id': key, 'subject_person_id': subject['id'], 'participant_ids': [p['id'] for p in participants],
                                                            'title': '平定江東', 'content': '一同平定江東。', 'experience_type': 'historical'})
    assert response.status_code == 201, response.text
    return response.json()


def relate(client, a, b, key, **sources):
    response = client.post(f"/api/people/{a['id']}/connections", json={'request_id': key, 'other_person_id': b['id'], 'relation_types': [{'kind': 'friend'}], **sources})
    assert response.status_code == 201, response.text
    return response.json()


def patch_experience(client, experience_id, key, revision, **body):
    return client.patch(f'/api/person-experiences/{experience_id}', json={'request_id': key, 'expected_revision': revision, **body})


def sources_of(client, connection_id):
    return client.get(f'/api/connections/{connection_id}').json()['source_person_experience_ids']


def test_person_experience_cannot_be_edited_into_orphaning_a_relation_source(client):
    zhou, sun, lu, qiao = people4(client)
    x = experience(client, zhou, [sun, lu])
    by_participants = relate(client, sun, lu, 'r-1', source_person_experience_ids=[x['id']])   # 只靠參與人物孫策、魯肅和這筆經歷有關
    by_subject = relate(client, zhou, sun, 'r-2', source_person_experience_ids=[x['id']])       # 靠主體周瑜

    # 移除非必要的參與者：孫策／魯肅這段關係還有孫策，照常修改
    ok = patch_experience(client, x['id'], 'p-1', 1, participant_ids=[sun['id']])
    assert ok.status_code == 200 and [p['id'] for p in ok.json()['participants']] == [sun['id']], ok.text

    # 移除最後一位相關的人：拒絕，什麼都不改
    blocked = patch_experience(client, x['id'], 'p-2', 2, participant_ids=[], title='改了標題')
    assert code(blocked) == (409, 'relation_source_in_use'), blocked.text
    assert '孫策' in blocked.json()['error']['message'] and '魯肅' in blocked.json()['error']['message']
    now = client.get(f"/api/person-experiences/{x['id']}").json()
    assert (now['revision'], now['title'], [p['id'] for p in now['participants']]) == (2, '平定江東', [sun['id']])
    assert sources_of(client, by_participants['id']) == [x['id']] and sources_of(client, by_subject['id']) == [x['id']]
    assert code(patch_experience(client, x['id'], 'p-2', 2, participant_ids=[], title='改了標題')) == (409, 'relation_source_in_use')  # 同一請求重送結果一致
    # 換成另一位不相關的人也一樣（小喬不在孫策／魯肅這段關係裡）
    assert code(patch_experience(client, x['id'], 'p-3', 2, participant_ids=[qiao['id']])) == (409, 'relation_source_in_use')

    # 使用者先調整關係來源，再修改經歷：成功。靠主體的那段關係不受參與人物影響
    fixed = client.patch(f"/api/connections/{by_participants['id']}", json={'request_id': 'r-1-fix', 'expected_revision': by_participants['revision'], 'source_person_experience_ids': []})
    assert fixed.status_code == 200, fixed.text
    done = patch_experience(client, x['id'], 'p-4', 2, participant_ids=[])
    assert done.status_code == 200 and done.json()['participants'] == [] and done.json()['revision'] == 3, done.text
    assert patch_experience(client, x['id'], 'p-4', 2, participant_ids=[]).json() == done.json()  # 成功的請求重送回原結果
    assert sources_of(client, by_subject['id']) == [x['id']]

    # 仍被引用時不能封存；移除來源後才可以
    assert code(patch_experience(client, x['id'], 'p-5', 3, status='archived')) == (409, 'relation_source_in_use')
    assert client.get(f"/api/person-experiences/{x['id']}").json()['status'] == 'active'
    client.patch(f"/api/connections/{by_subject['id']}", json={'request_id': 'r-2-fix', 'expected_revision': by_subject['revision'], 'source_person_experience_ids': []})
    assert patch_experience(client, x['id'], 'p-6', 3, status='archived').status_code == 200


def test_guard_keeps_revision_owner_and_subject_rules(client, app):
    from fastapi.testclient import TestClient
    zhou, sun, lu, _ = people4(client)
    x = experience(client, zhou, [sun, lu])
    relate(client, sun, lu, 'r-1', source_person_experience_ids=[x['id']])
    assert code(patch_experience(client, x['id'], 'g-1', 9, participant_ids=[])) == (409, 'stale_revision')  # 版本不符優先回報
    # 主體不能改：沒有這個欄位
    assert patch_experience(client, x['id'], 'g-2', 1, subject_person_id=sun['id']).status_code == 422
    with TestClient(app) as other:  # 另一個帳號看不到，也改不到
        onboard(other)
        register(other, 'source_other')
        assert patch_experience(other, x['id'], 'g-3', 1, participant_ids=[]).status_code == 404
    # 沒有被引用的經歷，清空參與人物與封存都照常
    free = experience(client, zhou, [sun], key='x-2')
    assert patch_experience(client, free['id'], 'g-4', 1, participant_ids=[]).status_code == 200
    assert patch_experience(client, free['id'], 'g-5', 2, status='archived').status_code == 200


def test_my_experience_story_cannot_be_corrected_into_orphaning_a_relation_source(client):
    goal, real, _, _ = world(client, 'story_source_owner')
    friend = person(client, 'g-real-2', '林小華')
    story = {'title': '午餐', 'participants': [{'person_id': real['id'], 'interacted': True}], 'mentions': []}
    d = draft(client, goal, story=story)
    done = client.post(f"/api/drafts/{d['id']}/confirm", json=confirm_payload(d, request_id='ms-1', story=story, story_reviewed=True, interaction_type='in_person', tasks=[]))
    assert done.status_code == 201, done.text
    experience_id = done.json()['experience_id']
    relation = relate(client, real, friend, 'ms-r', source_experience_ids=[experience_id])

    def edit(key, participants, title='午餐'):
        current = client.get(f'/api/connections/stories/{experience_id}?manage=true').json()
        return client.put(f'/api/connections/stories/{experience_id}/people', json={
            'request_id': key, 'expected_revision': current['revision'], 'confirmed': True, 'story': {'title': title, 'participants': participants, 'mentions': []}})

    blocked = edit('ms-2', [])  # 把唯一相關的人從名單拿掉
    assert code(blocked) == (409, 'relation_source_in_use'), blocked.text
    assert [p['id'] for p in client.get(f'/api/connections/stories/{experience_id}?manage=true').json()['participants']] == [real['id']]
    assert client.get(f"/api/connections/{relation['id']}").json()['source_experience_ids'] == [experience_id]
    assert edit('ms-3', story['participants'], title='午餐（改標題）').status_code == 200  # 保留原關聯的更正照常
    client.patch(f"/api/connections/{relation['id']}", json={'request_id': 'ms-fix', 'expected_revision': relation['revision'], 'source_experience_ids': []})
    assert edit('ms-4', []).status_code == 200  # 先調整關係來源，再更正
