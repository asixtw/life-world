"""第四輪修正（Codex FAIL）的兩項後端防護在 Cloud SQL 上的驗收：Local 8030 → Cloud Run e2e → life_world_e2e（PostgreSQL）。

只在明確開啟時執行（建立 persons_ui_ 開頭的合成帳號）：

    LW_E2E_PERSONS=1 .venv\\Scripts\\python.exe -m pytest -q tests/test_integrity_guards_cloudsql_e2e.py

FIX-2　我的經歷只能關聯使用中的真實人物；歷史人物與虛構人物在草稿建立、草稿修改、確認都被後端拒絕，拒絕時不產生草稿、經歷、積分或目標進度。
FIX-3　被人物關係引用為來源的經歷，不能改到讓引用失效（移除最後一位相關的人、封存）；回 409，不修改經歷、關係與來源。
"""
import os
from datetime import datetime, timedelta

import pytest

from test_person_relations_cloudsql_e2e import TAIPEI
from test_persons_cloudsql_e2e import account, create, preflight  # noqa: F401（preflight 是 autouse fixture）

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS') != '1', reason='部署後以 LW_E2E_PERSONS=1 對 Local 8030（Cloud SQL E2E）執行')


def moment():
    """稍早的現在：避免本機與伺服器時鐘差造成未來時間；剛過午夜時維持在今天（目標期間內）。"""
    now = datetime.now(TAIPEI)
    earlier = now - timedelta(minutes=2)
    return (earlier if earlier.date() == now.date() else now).isoformat()


def draft_body(client, **extra):
    goal = client.goal
    return {'raw_text': '今天練習了半小時。', 'occurred_at': moment(), 'goal_id': goal['id'],
            'contributions': [{'action_id': goal['actions'][0]['id'], 'quantity': '0.5'}], **extra}


def totals(client):
    state = client.ok('GET', '/state')
    return (len(state['drafts']), len(state['experiences']), state['rewards']['total'],
            [action['progress'] for goal in state['goals'] for action in goal['actions']])


def confirm_body(d, key, **extra):
    return {'request_id': key, 'expected_revision': d['revision'], 'summary': '練習了半小時。', 'person_id': d.get('person_id'),
            'contributions': d['contributions'], 'tasks': [], **extra}


def rejected(result, status, code):
    assert result[0] == status and result[1]['error']['code'] == code, result


def set_status(client, person, key, status):
    current = client.ok('GET', f"/persons/{person['id']}")['person']
    client.ok('POST', f"/persons/{person['id']}/status", {'request_id': key, 'expected_revision': current['revision'], 'status': status})


def test_my_experiences_only_accept_active_real_people_on_cloud_sql():
    c, _, _ = account('grd')
    real = create(c, '王小明', 'grd-real', description='大學同學')
    hist = create(c, '周瑜', 'grd-hist', person_subtype='historical')
    fict = create(c, '沈知衡', 'grd-fict', person_subtype='original')
    start = totals(c)

    # 草稿建立：歷史人物、虛構人物直接打 API 也被拒絕，什麼都沒留下
    for person in (hist, fict):
        rejected(c.call('POST', '/experiences/drafts', draft_body(c, person_id=person['id'])), 422, 'person_not_recordable')
    mixed = {'title': '聚會', 'participants': [{'person_id': real['id'], 'interacted': True}, {'person_id': fict['id'], 'interacted': False}], 'mentions': []}
    rejected(c.call('POST', '/experiences/drafts', draft_body(c, story=mixed)), 422, 'person_not_recordable')  # 多位人物有一位不合規：整筆拒絕
    assert totals(c) == start

    # 真實人物：草稿可以建立；改成歷史人物被拒絕，草稿維持原樣
    d = c.ok('POST', '/experiences/drafts', draft_body(c, person_id=real['id']))
    rejected(c.call('PUT', f"/drafts/{d['id']}", draft_body(c, person_id=hist['id'], expected_revision=d['revision'])), 422, 'person_not_recordable')
    kept = c.ok('GET', f"/drafts/{d['id']}")
    assert kept['person_id'] == real['id'] and kept['revision'] == d['revision']

    # 確認時重新驗證：改送虛構人物、確認名單混入虛構人物、人物在草稿之後被封存，全部拒絕且不給積分
    before = totals(c)
    rejected(c.call('POST', f"/drafts/{d['id']}/confirm", confirm_body(d, 'grd-c1', person_id=fict['id'])), 422, 'person_not_recordable')
    rejected(c.call('POST', f"/drafts/{d['id']}/confirm", confirm_body(d, 'grd-c2', story=mixed, story_reviewed=True, interaction_type='in_person')),
             422, 'person_not_recordable')
    set_status(c, real, 'grd-arch', 'archived')
    rejected(c.call('POST', f"/drafts/{d['id']}/confirm", confirm_body(d, 'grd-c3')), 409, 'person_archived')
    assert totals(c) == before
    set_status(c, real, 'grd-back', 'active')

    # 合規的照常：真實人物可以確認並得到積分；沒有關聯人物的也可以
    done = c.ok('POST', f"/drafts/{d['id']}/confirm", confirm_body(d, 'grd-c4'))
    alone = c.ok('POST', '/experiences/drafts', draft_body(c, raw_text='自己讀了一章。'))
    c.ok('POST', f"/drafts/{alone['id']}/confirm", confirm_body(alone, 'grd-c5'))
    after = totals(c)
    assert after[1] == before[1] + 2 and after[2] > before[2] and done['experience_id']
    assert c.ok('POST', f"/drafts/{d['id']}/confirm", confirm_body(d, 'grd-c4'))['experience_id'] == done['experience_id']  # 同一請求重送回原結果


def test_relation_sources_stay_valid_when_experiences_change_on_cloud_sql():
    c, _, _ = account('src')
    zhou, sun, lu, qiao = (create(c, name, f'src-{i}', person_subtype='historical') for i, name in enumerate(('周瑜', '孫策', '魯肅', '小喬')))
    x = c.ok('POST', '/person-experiences', {'request_id': 'src-x', 'subject_person_id': zhou['id'], 'participant_ids': [sun['id'], lu['id']],
                                             'title': '平定江東', 'content': '一同平定江東。', 'experience_type': 'historical'})

    def relate(a, b, key, **sources):
        return c.ok('POST', f"/people/{a['id']}/connections", {'request_id': key, 'other_person_id': b['id'], 'relation_types': [{'kind': 'friend'}], **sources})

    def patch(key, revision, **body):
        return c.call('PATCH', f"/person-experiences/{x['id']}", {'request_id': key, 'expected_revision': revision, **body})

    def sources(connection):
        return c.ok('GET', f"/connections/{connection['id']}")['source_person_experience_ids']

    by_participants = relate(sun, lu, 'src-r1', source_person_experience_ids=[x['id']])  # 只靠參與人物和這筆經歷有關
    by_subject = relate(zhou, sun, 'src-r2', source_person_experience_ids=[x['id']])      # 靠主體

    # 移除非必要的參與者：照常
    status, body = patch('src-p1', 1, participant_ids=[sun['id']])
    assert status == 200 and [p['id'] for p in body['participants']] == [sun['id']], body

    # 移除最後一位相關的人：409，經歷、關係、來源都不變；重送結果相同
    rejected(patch('src-p2', 2, participant_ids=[], title='改了標題'), 409, 'relation_source_in_use')
    now = c.ok('GET', f"/person-experiences/{x['id']}")
    assert (now['revision'], now['title'], [p['id'] for p in now['participants']]) == (2, '平定江東', [sun['id']])
    assert sources(by_participants) == [x['id']] and sources(by_subject) == [x['id']]
    rejected(patch('src-p2', 2, participant_ids=[], title='改了標題'), 409, 'relation_source_in_use')
    rejected(patch('src-p3', 2, participant_ids=[qiao['id']]), 409, 'relation_source_in_use')  # 換成不相關的人也一樣
    rejected(patch('src-p4', 9, participant_ids=[]), 409, 'stale_revision')  # Revision 保護維持
    assert patch('src-p5', 2, subject_person_id=sun['id'])[0] == 422  # 主體不能改
    other, _, _ = account('srcb')
    assert other.call('PATCH', f"/person-experiences/{x['id']}", {'request_id': 'src-o', 'expected_revision': 2, 'participant_ids': []})[0] == 404  # Owner 隔離

    # 使用者先調整關係來源，再修改經歷：成功；靠主體的那段關係不受影響；成功的請求重送回原結果
    c.ok('PATCH', f"/connections/{by_participants['id']}", {'request_id': 'src-r1-fix', 'expected_revision': by_participants['revision'], 'source_person_experience_ids': []})
    status, done = patch('src-p6', 2, participant_ids=[])
    assert status == 200 and done['participants'] == [] and done['revision'] == 3, done
    assert patch('src-p6', 2, participant_ids=[]) == (200, done)
    assert sources(by_subject) == [x['id']]

    # 仍被引用時不能封存；移除來源後可以
    rejected(patch('src-p7', 3, status='archived'), 409, 'relation_source_in_use')
    assert c.ok('GET', f"/person-experiences/{x['id']}")['status'] == 'active'
    c.ok('PATCH', f"/connections/{by_subject['id']}", {'request_id': 'src-r2-fix', 'expected_revision': by_subject['revision'], 'source_person_experience_ids': []})
    assert patch('src-p8', 3, status='archived')[0] == 200

    # 我的經歷當來源時，更正故事參與人物同樣不能讓引用失效
    real = create(c, '王小明', 'src-real')
    friend = create(c, '林小華', 'src-friend')
    story = {'title': '午餐', 'participants': [{'person_id': real['id'], 'interacted': True}], 'mentions': []}
    goal = c.goal
    d = c.ok('POST', '/experiences/drafts', {'raw_text': '和王小明吃午餐。', 'occurred_at': moment(), 'goal_id': goal['id'],
                                             'contributions': [{'action_id': goal['actions'][0]['id'], 'quantity': '0.5'}], 'story': story})
    mine = c.ok('POST', f"/drafts/{d['id']}/confirm", confirm_body(d, 'src-m1', story=story, story_reviewed=True, interaction_type='in_person'))['experience_id']
    relation = relate(real, friend, 'src-r3', source_experience_ids=[mine])

    def correct(key, participants):
        current = c.ok('GET', f'/connections/stories/{mine}?manage=true')
        return c.call('PUT', f'/connections/stories/{mine}/people', {'request_id': key, 'expected_revision': current['revision'], 'confirmed': True,
                                                                      'story': {'title': '午餐', 'participants': participants, 'mentions': []}})

    rejected(correct('src-m2', []), 409, 'relation_source_in_use')
    assert [p['id'] for p in c.ok('GET', f'/connections/stories/{mine}?manage=true')['participants']] == [real['id']]
    assert c.ok('GET', f"/connections/{relation['id']}")['source_experience_ids'] == [mine]
    c.ok('PATCH', f"/connections/{relation['id']}", {'request_id': 'src-r3-fix', 'expected_revision': relation['revision'], 'source_experience_ids': []})
    assert correct('src-m3', [])[0] == 200
