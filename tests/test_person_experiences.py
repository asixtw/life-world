"""人物經歷（Unified Person E1）：人物自己的經歷，使用者不必參與。

程式自帶的自動測試（開發時快速檢查）；完成依據是部署後在 Cloud SQL life_world_e2e 的實測
（tests/test_person_experiences_cloudsql_e2e.py、browser_tests/test_persons_experiences_ui.py）。

2026-11-11 產品裁決：
- 兩種經歷分開：我的經歷（experiences，草稿→核對→確認，計積分與目標）與人物經歷（subject_experiences，直接儲存，不計積分、目標與互動統計）。
- 人物經歷欄位：標題（選填）、主體（必填，一位）、其他參與人物（選填、最多 50 位）、內容（必填）、性質（真實／歷史／虛構，建立後不能改）、
  發生時間（不知道／年／年月／完整日期）、時間描述（選填）。建立者就是登入帳號，不另外填。
- 可以只有主體、沒有其他參與人物。已封存的人物不能被選為主體或新加入的參與人物。
- 封存不刪除；已封存的經歷唯讀、可恢復。主體人物已封存時不能新增、修改、封存或恢復。
- 不因共同參與自動建立關係；不自動修改人物設定。
"""
import pytest
from fastapi.testclient import TestClient

from conftest import confirm_payload, draft, onboard, register

KEYS = {'id', 'owner_id', 'revision', 'status', 'title', 'content', 'experience_type', 'origin_type', 'occurred_precision', 'occurred_on',
        'occurred_label', 'created_at', 'updated_at', 'subject', 'participants'}
PERSON_KEYS = {'id', 'name', 'person_type', 'person_subtype', 'status', 'description'}


def world(client, username='exp_owner'):
    """帳號、四位人物（周瑜是真實人物，孫策、魯肅、小喬是歷史人物），一筆與周瑜有關的已確認我的經歷。"""
    _, goal = onboard(client)
    register(client, username)
    # 我的經歷只能關聯真實人物（2026-11-11 起後端也檢查），所以有我的經歷的這一位不設歷史子類型；其餘三位是歷史人物
    people = {name: client.post('/api/persons', json={'request_id': f'{username}-{name}', 'name': name, 'description': name + '的簡介',
                                                       **({} if name == '周瑜' else {'person_subtype': 'historical'})}).json() for name in ('周瑜', '孫策', '魯肅', '小喬')}
    d = draft(client, goal, person_id=people['周瑜']['id'], raw_text='與周瑜討論合作。')
    done = client.post(f"/api/drafts/{d['id']}/confirm", json=confirm_payload(d, request_id=f'{username}-confirm', summary='與周瑜討論合作'))
    assert done.status_code == 201, done.text
    return people, done.json()['experience_id']


def create(client, subject, request_id='e-1', **body):
    payload = {'request_id': request_id, 'subject_person_id': subject['id'], 'content': '平定江東，建立基業。', 'experience_type': 'historical', **body}
    return client.post('/api/person-experiences', json=payload)


def patch(client, experience_id, request_id, expected_revision, **body):
    return client.patch(f'/api/person-experiences/{experience_id}', json={'request_id': request_id, 'expected_revision': expected_revision, **body})


def tab(client, person, archived=False):
    response = client.get(f"/api/persons/{person['id']}/experiences" + ('?archived=true' if archived else ''))
    assert response.status_code == 200, response.text
    return response.json()


def set_person_status(client, person, request_id, status):
    current = client.get(f"/api/persons/{person['id']}").json()['person']
    response = client.post(f"/api/persons/{person['id']}/status", json={'request_id': request_id, 'expected_revision': current['revision'], 'status': status})
    assert response.status_code == 200, response.text


def test_create_shows_on_subject_and_participant_pages_and_does_not_touch_points_or_relations(client):
    people, record = world(client)
    before = client.get('/api/state').json()
    response = create(client, people['周瑜'], participant_ids=[people['孫策']['id'], people['魯肅']['id']], title='平定江東',
                      occurred_precision='year', occurred_on='208', occurred_label='建安十三年')
    assert response.status_code == 201, response.text
    item = response.json()
    assert set(item) == KEYS and set(item['subject']) == PERSON_KEYS
    assert (item['title'], item['content'], item['experience_type'], item['origin_type'], item['status'], item['revision']) == \
        ('平定江東', '平定江東，建立基業。', 'historical', 'manual', 'active', 1)
    assert (item['occurred_precision'], item['occurred_on'], item['occurred_label']) == ('year', '0208', '建安十三年')
    assert item['subject']['id'] == people['周瑜']['id'] and sorted(p['name'] for p in item['participants']) == ['孫策', '魯肅']
    assert client.get(f"/api/person-experiences/{item['id']}").json() == item

    for name, role in (('周瑜', 'subject'), ('孫策', 'participant'), ('魯肅', 'participant')):
        listed = tab(client, people[name])['person_experiences']
        assert listed['total'] == 1 and listed['archived_total'] == 0
        assert listed['items'][0]['id'] == item['id'] and listed['items'][0]['role'] == role
    assert tab(client, people['小喬'])['person_experiences'] == {'items': [], 'total': 0, 'archived_total': 0}

    # 我的經歷與人物經歷分開：周瑜有一筆我的經歷；孫策沒有
    records = tab(client, people['周瑜'])['records']
    assert records['total'] == 1 and records['items'][0]['id'] == record and records['items'][0]['summary'] == '與周瑜討論合作'
    assert tab(client, people['孫策'])['records'] == {'items': [], 'total': 0}
    # 不計積分、不進我的經歷、不自動建立關係、不改人物設定
    after = client.get('/api/state').json()
    assert after['rewards'] == before['rewards'] and after['experiences'] == before['experiences']
    detail = client.get(f"/api/persons/{people['周瑜']['id']}").json()
    assert detail['connections'] == [] and detail['profile'] is None
    assert detail['experiences'] == {'mine': 1, 'person_experiences': 1}


def test_subject_alone_is_enough_and_title_and_date_are_optional(client):
    people, _ = world(client)
    item = create(client, people['周瑜'], content='少年時在廬江求學。').json()
    assert (item['title'], item['participants'], item['occurred_precision'], item['occurred_on'], item['occurred_label']) == ('', [], 'unknown', None, '')


@pytest.mark.parametrize('precision,on,expected', [('year', '208', '0208'), ('month', '208-12', '0208-12'), ('day', '0208-12-01', '0208-12-01'),
                                                   ('day', '2026-02-28', '2026-02-28'), ('unknown', None, None)])
def test_date_precision_is_kept_as_entered(client, precision, on, expected):
    people, _ = world(client)
    item = create(client, people['周瑜'], occurred_precision=precision, occurred_on=on).json()
    assert (item['occurred_precision'], item['occurred_on']) == (precision, expected)
    assert client.get(f"/api/person-experiences/{item['id']}").json()['occurred_on'] == expected


@pytest.mark.parametrize('body', [
    {'content': '   '}, {'experience_type': 'legend'}, {'title': 'x' * 201}, {'occurred_label': 'x' * 121},
    {'occurred_precision': 'year'}, {'occurred_precision': 'year', 'occurred_on': '208-12'}, {'occurred_precision': 'month', 'occurred_on': '208-13'},
    {'occurred_precision': 'day', 'occurred_on': '2026-02-30'}, {'occurred_precision': 'unknown', 'occurred_on': '208'},
    {'occurred_precision': 'year', 'occurred_on': '0'}, {'occurred_on': '208'}, {'owner_participates': True}])
def test_invalid_input_is_rejected_and_nothing_is_saved(client, body):
    people, _ = world(client)
    response = create(client, people['周瑜'], **body)
    assert response.status_code == 422, response.text
    assert tab(client, people['周瑜'])['person_experiences']['total'] == 0


def test_participant_rules(client):
    people, _ = world(client)
    zhou, sun = people['周瑜'], people['孫策']
    for ids, status, code in (([zhou['id']], 422, 'validation_error'), ([sun['id'], sun['id']], 422, 'validation_error'), (['missing'], 404, 'not_found')):
        response = create(client, zhou, participant_ids=ids)
        assert response.status_code == status and response.json()['error']['code'] == code, response.text
    assert create(client, zhou, participant_ids=[f'p{i}' for i in range(51)]).status_code == 422  # 最多 50 位
    assert tab(client, zhou)['person_experiences']['total'] == 0


def test_archived_people_cannot_be_chosen_and_archived_subject_locks_the_experience(client):
    people, _ = world(client)
    zhou, sun, lu = people['周瑜'], people['孫策'], people['魯肅']
    set_person_status(client, lu, 'lu-1', 'archived')
    for response in (create(client, lu, request_id='x1'), create(client, zhou, request_id='x2', participant_ids=[lu['id']])):
        assert response.status_code == 409 and response.json()['error']['code'] == 'person_archived', response.text
    set_person_status(client, lu, 'lu-2', 'active')
    item = create(client, zhou, participant_ids=[sun['id'], lu['id']]).json()

    # 參與人物後來被封存：經歷仍可編輯，既有的參與人物保留；但不能把已封存的人物新加進來
    set_person_status(client, lu, 'lu-3', 'archived')
    edited = patch(client, item['id'], 'p-1', 1, title='仍可修改')
    assert edited.status_code == 200 and sorted(p['name'] for p in edited.json()['participants']) == ['孫策', '魯肅']
    assert next(p for p in edited.json()['participants'] if p['name'] == '魯肅')['status'] == 'archived'
    kept = patch(client, item['id'], 'p-2', 2, participant_ids=[lu['id']])
    assert kept.status_code == 200 and [p['name'] for p in kept.json()['participants']] == ['魯肅']
    removed = patch(client, item['id'], 'p-3', 3, participant_ids=[])
    assert removed.status_code == 200 and removed.json()['participants'] == []
    again = patch(client, item['id'], 'p-4', 4, participant_ids=[lu['id']])
    assert again.status_code == 409 and again.json()['error']['code'] == 'person_archived'

    # 主體人物已封存：不能修改、封存或恢復；讀取照常
    set_person_status(client, zhou, 'zhou-1', 'archived')
    for request_id, body in (('p-5', {'title': '封存後修改'}), ('p-6', {'status': 'archived'})):
        locked = patch(client, item['id'], request_id, 4, **body)
        assert locked.status_code == 409 and locked.json()['error']['code'] == 'person_archived', locked.text
    assert tab(client, zhou)['person_experiences']['items'][0]['title'] == '仍可修改'


def test_patch_edits_fields_checks_revision_and_replays(client):
    people, _ = world(client)
    zhou, sun, qiao = people['周瑜'], people['孫策'], people['小喬']
    item = create(client, zhou, participant_ids=[sun['id']], title='赤壁').json()
    change = {'title': '赤壁之戰', 'content': '火燒連環船。', 'occurred_precision': 'month', 'occurred_on': '208-12',
              'occurred_label': '建安十三年冬', 'participant_ids': [qiao['id']]}
    edited = patch(client, item['id'], 'p-1', 1, **change)
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert (body['title'], body['content'], body['occurred_precision'], body['occurred_on'], body['occurred_label'], body['revision']) == \
        ('赤壁之戰', '火燒連環船。', 'month', '0208-12', '建安十三年冬', 2)
    assert [p['name'] for p in body['participants']] == ['小喬'] and body['experience_type'] == 'historical'
    assert tab(client, sun)['person_experiences']['total'] == 0 and tab(client, qiao)['person_experiences']['total'] == 1

    stale = patch(client, item['id'], 'p-2', 1, title='過期')
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'stale_revision'
    assert patch(client, item['id'], 'p-1', 1, **change).json() == body  # 同一請求重送：回原結果
    assert patch(client, item['id'], 'p-3', 2).status_code == 422  # 沒有要改的欄位
    assert patch(client, item['id'], 'p-4', 2, experience_type='fictional').status_code == 422  # 性質建立後不能改
    cleared = patch(client, item['id'], 'p-5', 2, occurred_precision='unknown', occurred_label='').json()
    assert (cleared['occurred_precision'], cleared['occurred_on'], cleared['occurred_label'], cleared['title']) == ('unknown', None, '', '赤壁之戰')
    assert create(client, zhou, participant_ids=[sun['id']], title='赤壁').json() == item  # 建立請求重送：回原結果，不另建一筆
    assert tab(client, zhou)['person_experiences']['total'] == 1


def test_archive_hides_restores_and_never_deletes(client):
    people, _ = world(client)
    zhou, sun = people['周瑜'], people['孫策']
    item = create(client, zhou, participant_ids=[sun['id']], title='平定江東').json()
    archived = patch(client, item['id'], 'a-1', 1, status='archived')
    assert archived.status_code == 200 and archived.json()['status'] == 'archived' and archived.json()['revision'] == 2
    for person in (zhou, sun):
        assert tab(client, person)['person_experiences'] == {'items': [], 'total': 0, 'archived_total': 1}
        assert [x['id'] for x in tab(client, person, archived=True)['person_experiences']['items']] == [item['id']]
    assert client.get(f"/api/persons/{zhou['id']}").json()['experiences']['person_experiences'] == 0
    for request_id, body in (('a-2', {'title': '封存後修改'}), ('a-3', {'status': 'archived'}), ('a-4', {'status': 'active', 'title': '順便改'})):
        blocked = patch(client, item['id'], request_id, 2, **body)
        assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'experience_archived', blocked.text
    restored = patch(client, item['id'], 'a-5', 2, status='active').json()
    assert (restored['status'], restored['title'], restored['revision']) == ('active', '平定江東', 3)
    assert [p['name'] for p in restored['participants']] == ['孫策'] and tab(client, sun)['person_experiences']['total'] == 1


def test_known_dates_come_first_newest_first_and_unknown_dates_last(client):
    people, _ = world(client)
    zhou = people['周瑜']
    for request_id, title, precision, on in (('s-1', '不知道時間', 'unknown', None), ('s-2', '赤壁', 'month', '208-12'),
                                             ('s-3', '求學', 'year', '190'), ('s-4', '也不知道', 'unknown', None), ('s-5', '平定江東', 'day', '0199-06-01')):
        assert create(client, zhou, request_id=request_id, title=title, occurred_precision=precision, occurred_on=on).status_code == 201
    titles = [x['title'] for x in tab(client, zhou)['person_experiences']['items']]
    assert titles[:3] == ['赤壁', '平定江東', '求學'] and set(titles[3:]) == {'不知道時間', '也不知道'}


def test_other_account_cannot_read_write_or_use_my_people(client):
    people, _ = world(client)
    zhou = people['周瑜']
    item = create(client, zhou, title='平定江東').json()
    other = TestClient(client.app)  # 另一個帳號（獨立的 Cookie）
    other_people, _ = world(other, 'exp_other')
    assert other.get(f"/api/person-experiences/{item['id']}").status_code == 404
    assert patch(other, item['id'], 'o-1', 1, title='盜改').status_code == 404
    assert patch(other, item['id'], 'o-2', 1, status='archived').status_code == 404
    assert other.get(f"/api/persons/{zhou['id']}/experiences").status_code == 404
    assert create(other, zhou, request_id='o-3').status_code == 404
    assert create(other, other_people['周瑜'], request_id='o-4', participant_ids=[zhou['id']]).status_code == 404
    assert tab(other, other_people['周瑜'])['person_experiences']['total'] == 0
    assert client.get(f"/api/person-experiences/{item['id']}").json() == item  # 原帳號的資料沒有被動到
