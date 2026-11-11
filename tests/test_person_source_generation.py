"""建立作品可以選「人物」：引用同帳號人物的正式人物設定（person_profile.v1，有正式回執的最新版），開始時鎖定版本與內容雜湊。

驗證重點（2026-11-11 第一個作品生成的前置開發）：
1. 建立頁可選的人物清單：只列本人使用中的人物，標出有沒有正式人物設定。
2. 規劃階段只看得到公開簡介；輪到人物發言時送出鎖定版本的九欄；輪到「我」發言時送出我的設定；雙方的私有內容互不可見。
3. 同名的舊角色卡、格式相同但沒有正式回執的筆記，都不會取代正式人物設定。
4. 開始之後才存的新版本不會被進行中的作品使用；鎖定的版本被改動或失去回執就停止。
5. 不能加入的人物（沒有人物設定、已封存、別人的）在建立前就被拒絕，沒有呼叫模型、沒有建立作品。
6. 生成不會寫回人物、人物設定、我的經歷或積分。

這是本機 SQLite 的開發檢查（擷取型 Fake Provider，不連網、不計費）；PostgreSQL 上的驗收在 tests/test_person_source_cloudsql_e2e.py。
"""
from datetime import datetime, timezone
import json

import pytest
from fastapi.testclient import TestClient

from app.ai_providers import FakeProvider
from app.config import DemoPolicy
from app.main import create_app
from conftest import onboard, register

NINE = ('background', 'personality', 'motivation', 'stance', 'abilities', 'expression', 'behavior', 'knowledge_boundary', 'restrictions')
PERSONA_KEY = {'restrictions': 'weaknesses'}  # 人物設定的「固有限制與弱點」描述人物本身，不是演出規則；送給模型時用不會被誤讀的名稱
SELF = {'display_name': '小光', 'public_profile': '〔SELF公開〕喜歡桌遊的上班族。', 'personality': '〔SELF:personality〕', 'speaking_style': '語氣平穩',
        'motivation': '〔SELF:motivation〕', 'values': '〔SELF:values〕', 'boundaries': '〔SELF:boundaries〕'}
PRIVATE_MARKS = ('〔P1:', '〔P2:', '〔SELF:', '〔CARD:', '〔NOTE:')


def fields(tag):
    """九欄各放一個獨一無二的標記，方便在送給模型的內容裡逐欄核對。"""
    return {key: f'〔{tag}:{key}〕' for key in NINE}


class Capture(FakeProvider):
    """輸出與 Fake 相同，另外記下每一次實際送出的請求（system／user／schema）。"""

    def __init__(self):
        super().__init__()
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return super().generate(request)


@pytest.fixture
def env(tmp_path):
    provider = Capture()
    app = create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                     clock=lambda: datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc), generation_provider=provider)
    with TestClient(app) as client:
        yield client, provider


def ready(client, username='cast_owner'):
    onboard(client)
    register(client, username)


def person(client, key, name, profile=None, **body):
    payload = {'request_id': key, 'name': name, **body}
    if profile is not None:
        payload['profile'] = profile
    response = client.post('/api/persons', json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def profile_of(client, person_id):
    return client.get(f'/api/persons/{person_id}').json()['profile']


def save_profile(client, person_id, key, values):
    current = profile_of(client, person_id)
    response = client.put(f'/api/persons/{person_id}/profile',
                          json={'request_id': key, 'expected_profile_id': current['id'] if current else None, 'fields': values})
    assert response.status_code == 200, response.text
    return response.json()


def archive(client, target, key='arch'):
    current = client.get(f"/api/persons/{target['id']}").json()['person']
    response = client.post(f"/api/persons/{target['id']}/status", json={'request_id': key, 'expected_revision': current['revision'], 'status': 'archived'})
    assert response.status_code == 200, response.text


def with_me(client):
    assert client.put('/api/self-persona', json={'request_id': 'sp-1', 'content': SELF}).status_code == 200
    assert client.post('/api/self-persona/consent', json={'request_id': 'sc-1', 'granted': True}).json()['consent'] is not None


def pick(target, **extra):
    return {'source': 'person', 'ref': {'person_id': target['id']}, **extra}


def start(client, participants, include_me=False, request_id='run-1'):
    body = {'request_id': request_id, 'setup': {'participants': participants, 'include_me': include_me,
                                                'scene_context': {'description': '週六午後，社區展覽的試作桌。'},
                                                'output': {'type': 'text', 'text': {'length': 'short', 'form': 'script'}}}}
    return client.post('/api/generation/runs', json=body)


def step(client, work_id):
    result = client.post(f'/api/generation/runs/{work_id}/step')
    assert result.status_code == 200, result.text
    return result.json()


def run_to_end(client, work_id, limit=60):
    for _ in range(limit):
        detail = step(client, work_id)['detail']
        if detail['run']['status'] in ('completed', 'failed'):
            return detail
    raise AssertionError('沒有在預期步數內結束')


def sent(provider, module):
    return [payload for payload in (json.loads(request.user) for request in provider.requests) if payload['module'] == module]


def text_of(payload):
    return json.dumps(payload, ensure_ascii=False)


def code(response):
    return response.status_code, response.json().get('error', {}).get('code')


def side_effects(client, owner):
    """生成不應該動到的資料：人物、人物設定與回執、我的設定、同意、我的經歷與積分。"""
    with client.app.state.service.db.connect() as db:
        counts = [db.execute(sql, (owner,)).fetchone()[0] for sql in (
            'SELECT count(*) FROM people WHERE owner_id=?', 'SELECT coalesce(sum(revision),0) FROM people WHERE owner_id=?',
            'SELECT count(*) FROM notes WHERE owner_id=?', "SELECT count(*) FROM requests WHERE owner_id=? AND operation LIKE 'persons:profile:%'",
            "SELECT count(*) FROM work_versions WHERE owner_id=? AND content_schema='self_persona.v1'", 'SELECT count(*) FROM data_consents WHERE owner_id=?')]
    state = client.get('/api/state').json()
    return counts, len(state['experiences']), len(state['drafts']), state['rewards']['total']


def test_creation_page_lists_my_active_people_and_marks_who_has_a_formal_profile(env):
    client, _ = env
    ready(client)
    full = person(client, 'p-full', '溫若岑', profile=fields('P1'), person_subtype='original', description='願意讓手藝留下接縫。', roles=['展覽模型製作者'])
    empty = person(client, 'p-empty', '阿哲')
    gone = person(client, 'p-gone', '封存的人', profile=fields('P1'))
    archive(client, gone)
    other = TestClient(client.app)
    ready(other, 'cast_other')
    theirs = person(other, 'p-theirs', '別人的人物', profile=fields('P2'))

    listing = client.get('/api/generation/people')
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body['enabled'] is True
    items = {item['id']: item for item in body['items']}
    assert set(items) == {full['id'], empty['id']}, '只列本人使用中的人物；已封存與別人的都不在'
    assert theirs['id'] not in items
    formal = profile_of(client, full['id'])
    assert items[full['id']] == {'id': full['id'], 'name': '溫若岑', 'description': '願意讓手藝留下接縫。', 'person_type': 'fictional',
                                'person_subtype': 'original', 'roles': ['展覽模型製作者'], 'profile': {'id': formal['id'], 'version': 1}}
    assert items[empty['id']]['profile'] is None, '沒有正式人物設定的人物列出來但標示不能選'

    client.app.state.service.relation_source_store = 'legacy_jsonb'  # 人物系統還沒啟用的環境
    assert client.get('/api/generation/people').json() == {'enabled': False, 'items': []}
    assert code(start(client, [pick(full)])) == (409, 'unified_people_not_enabled')


def test_person_and_me_use_the_locked_formal_profile_and_stay_private_from_each_other(env):
    client, provider = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original', description='〔P1公開〕願意讓手藝留下接縫。')
    formal = profile_of(client, wen['id'])
    owner = wen['owner_id']
    # 兩個干擾來源：同名的舊角色卡，以及格式相同、版號更高、但沒有正式回執的筆記。兩者都不得取代正式人物設定。
    card = client.post('/api/characters', json={'request_id': 'card-1', 'content': {
        'name': '溫若岑', 'kind': 'fictional', 'tagline': '〔CARD:tagline〕', 'background': '〔CARD:background〕', 'personality': '〔CARD:personality〕', 'voice': '〔CARD:voice〕'}})
    assert card.status_code == 201, card.text
    stray = {'schema': 'person_profile.v1', 'version': 9, 'previous_id': formal['id'], 'origin': 'manual', 'generation_id': None, 'fields': fields('NOTE')}
    with client.app.state.service.db.connect(write=True, owner=owner) as db:
        db.execute('INSERT INTO notes(id,owner_id,person_id,kind,title,content,created_at) VALUES (?,?,?,?,?,?,?)',
                   ('stray-note', owner, wen['id'], 'preparation', 'person_profile.v1', json.dumps(stray, ensure_ascii=False), '2026-10-27T08:00:00+00:00'))
    with_me(client)
    before = side_effects(client, owner)

    started = start(client, [{**pick(wen, position='supporting'), 'ref': {'person_id': wen['id'], 'profile_id': formal['id']}}], include_me=True)
    assert started.status_code == 201, started.text
    assert started.json()['module_id'] == 'T2'
    detail = run_to_end(client, started.json()['id'])
    assert detail['run']['status'] == 'completed', detail['run']

    plans, segments = sent(provider, 'roleplay_plan'), sent(provider, 'roleplay_segment')
    assert len(plans) == 1
    cast = {member['id']: member for member in plans[0]['cast']}
    assert cast['c1'] == {'id': 'c1', 'name': '溫若岑', 'public_profile': '〔P1公開〕願意讓手藝留下接縫。', 'is_user': False, 'role': '配角'}
    assert cast['self']['public_profile'] == SELF['public_profile'] and cast['self']['is_user'] is True
    assert not any(mark in text_of(plans[0]) for mark in PRIVATE_MARKS), '規劃只看得到公開簡介'

    expected = {'name': '溫若岑', 'kind': 'fictional', 'public_profile': '〔P1公開〕願意讓手藝留下接縫。',
                **{PERSONA_KEY.get(key, key): value for key, value in fields('P1').items()}}
    hers = [payload for payload in segments if payload['turn']['speaker']['id'] == 'c1']
    mine = [payload for payload in segments if payload['turn']['speaker']['id'] == 'self']
    assert hers and mine and len(hers) + len(mine) == len(segments)
    for payload in hers:
        speaker = payload['turn']['speaker']
        assert speaker['persona'] == expected, '人物發言時送出鎖定版本的九欄'
        assert speaker['is_user'] is False and speaker['role'] == '配角'
        assert payload['others'] == [{'id': 'self', 'name': '小光', 'public_profile': SELF['public_profile'], 'is_user': True, 'role': None}]
        assert not any(mark in text_of(payload) for mark in ('〔SELF:', '〔CARD:', '〔NOTE:', '〔P2:')), '看不到我的設定的私有欄位，也沒有混入舊卡或無回執筆記'
    for payload in mine:
        persona = payload['turn']['speaker']['persona']
        assert payload['turn']['speaker']['is_user'] is True
        assert {key: persona[key] for key in ('personality', 'motivation', 'values', 'boundaries')} == {key: SELF[key] for key in ('personality', 'motivation', 'values', 'boundaries')}
        assert payload['others'] == [cast['c1']]
        assert not any(mark in text_of(payload) for mark in ('〔P1:', '〔CARD:', '〔NOTE:')), '我發言時看不到人物的九欄'

    with client.app.state.service.db.connect() as db:
        stored = [json.loads(row['input_json']) for row in db.execute("SELECT input_json FROM ai_generations WHERE module='roleplay_segment' ORDER BY created_at").fetchall()]
    refs = [item['persona_ref'] for item in stored if item['speaker_id'] == 'c1']
    assert refs and all(ref == refs[0] for ref in refs)
    assert {key: refs[0][key] for key in ('source', 'person_id', 'profile_id', 'version')} == {'source': 'person', 'person_id': wen['id'], 'profile_id': formal['id'], 'version': 1}
    assert len(refs[0]['content_sha256']) == 64, '生成紀錄留下來源人物、人物設定版本與內容雜湊'

    shown = {member['id']: member for member in detail['cast']}
    assert shown['c1']['source'] == 'person' and shown['c1']['person_id'] == wen['id'] and shown['c1']['version'] == 1
    assert shown['self']['source'] == 'self' and shown['self']['is_user'] is True
    assert side_effects(client, owner) == before, '生成不寫回人物、人物設定、我的設定、同意、我的經歷或積分'


def test_a_running_work_keeps_its_locked_version_and_a_new_work_uses_the_latest(env):
    client, provider = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original', description='模型製作者')
    work_id = start(client, [pick(wen)]).json()['id']
    assert step(client, work_id)['outcome'] == 'planned'
    assert step(client, work_id)['outcome'] == 'saved'
    newer = save_profile(client, wen['id'], 'pf-2', fields('P2'))
    assert newer['version'] == 2
    detail = run_to_end(client, work_id)
    assert detail['module'] == 'T1' and detail['run']['status'] == 'completed'
    personas = [payload['turn']['speaker']['persona'] for payload in sent(provider, 'roleplay_segment')]
    assert personas and all(persona['background'] == '〔P1:background〕' for persona in personas), '進行中的作品不會跳到新版本'
    assert {member['id']: member['version'] for member in detail['cast']} == {'c1': 1}

    provider.requests.clear()
    second = start(client, [pick(wen)], request_id='run-2')
    assert second.status_code == 201, second.text
    later = run_to_end(client, second.json()['id'])
    assert later['cast'][0]['version'] == 2
    assert all(payload['turn']['speaker']['persona']['background'] == '〔P2:background〕' for payload in sent(provider, 'roleplay_segment')), '新作品使用當時最新的正式版本'


def test_archiving_a_person_keeps_a_running_work_going_but_blocks_new_works(env):
    client, _ = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original')
    work_id = start(client, [pick(wen)]).json()['id']
    assert step(client, work_id)['outcome'] == 'planned'
    archive(client, wen)  # 封存不刪除任何資料：鎖定的人物設定還在，進行中的作品照常完成（和角色卡相同）
    assert run_to_end(client, work_id)['run']['status'] == 'completed'
    assert code(start(client, [pick(wen)], request_id='run-2')) == (409, 'person_archived')


def test_people_who_cannot_be_cast_are_rejected_before_anything_is_created(env):
    client, provider = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original')
    first = profile_of(client, wen['id'])
    save_profile(client, wen['id'], 'pf-2', fields('P2'))
    blank = person(client, 'p-blank', '還沒填設定的人')
    gone = person(client, 'p-gone', '封存的人', profile=fields('P1'))
    archive(client, gone)
    other = TestClient(client.app)
    ready(other, 'cast_other')
    theirs = person(other, 'p-theirs', '別人的人物', profile=fields('P2'))
    card = client.post('/api/characters', json={'request_id': 'card-1', 'content': {'name': '溫若岑', 'kind': 'fictional'}}).json()
    card_ref = {'ref': {'work_id': card['id'], 'version_no': card['current_version']}}

    assert code(start(client, [pick(blank)], request_id='r1')) == (409, 'person_profile_required')
    assert code(start(client, [pick(gone)], request_id='r2')) == (409, 'person_archived')
    assert code(start(client, [pick(theirs)], request_id='r3')) == (404, 'not_found'), '別人的人物一律 404，不透露是否存在'
    assert code(start(client, [{'source': 'person', 'ref': {'person_id': 'no-such-person'}}], request_id='r4')) == (404, 'not_found')
    stale = {'source': 'person', 'ref': {'person_id': wen['id'], 'profile_id': first['id']}}
    assert code(start(client, [stale], request_id='r5')) == (409, 'person_profile_changed'), '畫面讀到的不是最新版時不開始'
    assert start(client, [pick(wen), pick(wen)], request_id='r6').status_code == 422, '同一位人物不能重複選'
    assert code(start(client, [pick(wen), card_ref], request_id='r7')) == (422, 'duplicate_cast_name'), '人物與同名角色卡不能一起出場'
    assert start(client, [{'source': 'person', 'ref': {'work_id': card['id'], 'version_no': 1}}], request_id='r8').status_code == 422, '來源和引用格式要相符'
    assert code(start(client, [pick(wen), pick(blank)], request_id='r9')) == (409, 'person_profile_required'), '名單裡有一位不合規就整筆拒絕'

    assert provider.requests == [], '被拒絕時沒有呼叫模型'
    assert client.get('/api/works?kind=generated_work').json()['total'] == 0, '被拒絕時沒有建立作品'


def test_generation_stops_when_the_locked_profile_is_changed_or_loses_its_receipt(env):
    client, _ = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original')
    lin = person(client, 'p-lin', '潘映葵', profile=fields('P1'), person_subtype='original')
    owner, service = wen['owner_id'], client.app.state.service

    first = start(client, [pick(wen)], request_id='run-a').json()['id']
    assert step(client, first)['outcome'] == 'planned'
    assert step(client, first)['outcome'] == 'saved'
    formal = profile_of(client, wen['id'])
    tampered = {'schema': 'person_profile.v1', 'version': 1, 'previous_id': None, 'origin': 'manual', 'generation_id': None, 'fields': fields('P2')}
    with service.db.connect(write=True, owner=owner) as db:  # 模擬鎖定的那一版被直接改動（正常操作只會新增版本）
        db.execute('UPDATE notes SET content=? WHERE id=? AND owner_id=?', (json.dumps(tampered, ensure_ascii=False), formal['id'], owner))
    stopped = run_to_end(client, first)
    assert stopped['run']['status'] == 'failed' and stopped['run']['error']['code'] == 'source_unavailable'
    assert len(stopped['segments']) == 1, '已生成的段落保留'

    second = start(client, [pick(lin)], request_id='run-b').json()['id']
    assert step(client, second)['outcome'] == 'planned'
    with service.db.connect(write=True, owner=owner) as db:  # 那一版不再是正式人物設定（沒有回執）
        db.execute('DELETE FROM requests WHERE owner_id=? AND operation=?', (owner, 'persons:profile:' + lin['id']))
    lost = run_to_end(client, second)
    assert lost['run']['status'] == 'failed' and lost['run']['error']['code'] == 'source_unavailable'
    assert lost['segments'] == []


def test_people_and_cards_can_share_one_work_and_card_references_still_work(env):
    client, provider = env
    ready(client)
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original', description='模型製作者')
    system = client.get('/api/characters/system').json()['items'][0]
    card = client.post('/api/characters/copy', json={'request_id': 'copy-0', 'source_kind': 'system', 'source_id': system['id'], 'source_version': system['version']}).json()
    started = start(client, [pick(wen, position='protagonist'), {'source': 'card', 'ref': {'work_id': card['id'], 'version_no': card['current_version']}, 'position': 'opponent'}])
    assert started.status_code == 201, started.text
    detail = run_to_end(client, started.json()['id'])
    assert detail['module'] == 'T2' and detail['run']['status'] == 'completed'
    assert [(member['id'], member['source'], member['position']) for member in detail['cast']] == [('c1', 'person', 'protagonist'), ('c2', 'card', 'opponent')]
    by_speaker = {payload['turn']['speaker']['id']: payload['turn']['speaker']['persona'] for payload in sent(provider, 'roleplay_segment')}
    assert by_speaker['c1']['abilities'] == '〔P1:abilities〕' and 'weaknesses' in by_speaker['c1']
    assert by_speaker['c2']['name'] == card['title'] and 'weaknesses' not in by_speaker['c2'], '角色卡照原本的欄位送出'

    cards = client.get('/api/characters?status=active')
    assert cards.status_code == 200, cards.text
    assert next(item for item in cards.json()['items'] if item['id'] == card['id'])['used_by'] == 1, '含人物的作品不影響角色卡的引用統計'
    assert client.get(f"/api/characters/{card['id']}/references").status_code == 200
    center = client.get('/api/works/center?tab=all').json()
    assert center['total'] == 1 and center['items'][0]['id'] == started.json()['id']
