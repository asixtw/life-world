"""範例場景裡的「名場面」（2026-11-12）。

使用者的方向：作品要用觀眾熟悉的東西來演。用歷史名場面照原樣演，或改編成現代、商戰、生活、科幻；
熟悉的東西可以省掉解釋，改編帶出驚喜。所以在「從範例場景開始」加上名場面，選了就帶入場景描述，可以再改。
描述用「哪一方」來寫，不寫人名：人物由使用者自己選，並在描述裡補上誰站在哪一方。

只用隔離 SQLite 與 Fake Provider（不連網、不計費）。
"""
from test_person_source_generation import env, fields, person, pick, ready, run_to_end  # noqa: F401

ORIGINAL = ['daily-chat', 'ask-advice', 'disagreement', 'business-visit', 'shared-memory', 'travel-day',
            'tk-red-cliff', 'tk-grain', 'int-ceasefire', 'int-shipping', 'ph-success', 'ph-promise']
FAMOUS = ['fs-hongmen-original', 'fs-hongmen-business', 'fs-heroes-office', 'fs-empty-fort-daily', 'fs-three-visits-scifi']


def test_catalog_offers_famous_scenes_as_they_are_and_adapted(env):
    client, _ = env
    ready(client)
    presets = client.get('/api/generation/catalog').json()['scene_presets']
    ids = [item['id'] for item in presets]
    assert ids[:len(ORIGINAL)] == ORIGINAL, '原有的範例場景與順序不變'
    assert ids[len(ORIGINAL):] == FAMOUS
    famous = {item['id']: item for item in presets if item['id'] in FAMOUS}
    for item in famous.values():
        assert item['title'].startswith('名場面｜'), '在下拉選單裡一眼看得出是名場面'
        assert item['description'].startswith('藍本：'), '描述先講藍本與改編方式，規劃依這個安排橋段'
        assert len(item['description']) <= 400
    assert '照原樣' in famous['fs-hongmen-original']['description'] and '不代表史實' in famous['fs-hongmen-original']['description']
    for key, word in (('fs-hongmen-business', '商戰'), ('fs-heroes-office', '職場'), ('fs-empty-fort-daily', '生活'), ('fs-three-visits-scifi', '科幻')):
        assert word in famous[key]['title'] and word in famous[key]['description']


def test_a_work_can_start_from_a_famous_scene_preset(env):
    client, _ = env
    ready(client)
    presets = {item['id']: item for item in client.get('/api/generation/catalog').json()['scene_presets']}
    wen = person(client, 'p-wen', '溫若岑', profile=fields('P1'), person_subtype='original', description='模型製作者。')
    pan = person(client, 'p-pan', '潘映葵', profile=fields('P2'), person_subtype='original', description='品管抽驗員。')
    started = client.post('/api/generation/runs', json={'request_id': 'run-fs', 'setup': {
        'participants': [pick(wen, position='protagonist'), pick(pan, position='opponent')], 'include_me': False,
        'scene_context': {'description': presets['fs-heroes-office']['description'] + '潘映葵是那位主管，溫若岑是被試探的人。', 'preset_id': 'fs-heroes-office'},
        'output': {'type': 'text', 'text': {'length': 'short', 'form': 'narrative'}}}})
    assert started.status_code == 201, started.text
    detail = run_to_end(client, started.json()['id'])
    assert detail['run']['status'] == 'completed'
    assert detail['setup']['scene']['preset_id'] == 'fs-heroes-office' and detail['setup']['scene']['description'].startswith('藍本：煮酒論英雄')
