"""Unified Person Phase 1–2 缺陷修正（Codex FAIL）：FIX-1 正式回執辨識、FIX-2 封存禁止修改、FIX-3 列表分頁。

後端為明確指定的 SQLite 單元測試；前端分頁與封存編輯頁以 Node 直接執行 app/static/persons.js（假的 API，不開任何網站）。
都不能代替 Local 8030 → Cloud SQL life_world_e2e 的 PostgreSQL 驗收。
"""
import json
import os
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from conftest import confirm_payload, draft, onboard, register
from app import persons as persons_module


def ready(client, username):
    _, goal = onboard(client)
    register(client, username)
    return goal


def create(client, name, request_id, **body):
    response = client.post('/api/persons', json={'request_id': request_id, 'name': name, **body})
    assert response.status_code == 201, response.text
    return response.json()


def save(client, person_id, request_id, expected, **fields):
    return client.put(f'/api/persons/{person_id}/profile', json={'request_id': request_id, 'expected_profile_id': expected, 'fields': fields})


def legacy_note_titles(client, person_id):
    return [n['title'] for n in client.get(f'/api/people/{person_id}/overview').json()['notes']]


def counts(client):
    with client.app.state.service.db.connect() as c:
        return {t: c.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0] for t in ('notes', 'requests', 'people')}


# ---- FIX-1：正式人物設定只認 requests 的保存回執 ----

def test_private_note_with_profile_format_stays_a_private_note(client):
    ready(client, 'fix1_private')
    a = create(client, '甲', 'a')
    v1 = save(client, a['id'], 'pf-1', None, background='正式第一版').json()
    assert v1['version'] == 1
    forged = {'schema': persons_module.PROFILE_SCHEMA, 'version': 9, 'origin': 'manual', 'fields': {'background': '私人筆記，不是人物設定'}}
    note = client.post('/api/notes', json={'person_id': a['id'], 'kind': 'preparation', 'title': persons_module.PROFILE_TITLE,
                                           'content': json.dumps(forged, ensure_ascii=False)})
    assert note.status_code == 201, note.text
    assert persons_module.PROFILE_TITLE in legacy_note_titles(client, a['id'])  # 沒有回執：仍是私人筆記
    profile = client.get(f"/api/persons/{a['id']}").json()['profile']
    assert profile == v1 and profile['fields']['background'] == '正式第一版'  # 沒被第 9 版的格式取代
    v2 = save(client, a['id'], 'pf-2', v1['id'], background='正式第二版')
    assert v2.status_code == 200 and v2.json()['version'] == 2, v2.text  # 依正式版本遞增，不受私人筆記的 9 影響
    assert client.get(f"/api/persons/{a['id']}").json()['profile'] == v2.json()
    titles = legacy_note_titles(client, a['id'])
    assert titles.count(persons_module.PROFILE_TITLE) == 1  # 私人筆記仍在、沒有被刪除或隱藏；兩版正式設定都不在清單
    with client.app.state.service.db.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM notes WHERE id=?', (note.json()['id'],)).fetchone()[0] == 1


def test_profile_retry_does_not_create_a_new_version(client):
    ready(client, 'fix1_retry')
    a = create(client, '甲', 'a')
    first = save(client, a['id'], 'same', None, background='一').json()
    before = counts(client)
    again = save(client, a['id'], 'same', None, background='一')
    assert again.status_code == 200 and again.json() == first
    assert counts(client) == before  # 沒有新的 notes 或回執
    assert client.get(f"/api/persons/{a['id']}").json()['profile']['version'] == 1


def test_receipts_are_bound_to_person_and_owner(client):
    ready(client, 'fix1_bound_a')
    a = create(client, '甲', 'a')
    b = create(client, '乙', 'b')
    save(client, a['id'], 'pa', None, background='甲的設定')
    forged = json.dumps({'schema': persons_module.PROFILE_SCHEMA, 'version': 1, 'origin': 'manual', 'fields': {'background': '乙的私人筆記'}}, ensure_ascii=False)
    note_b = client.post('/api/notes', json={'person_id': b['id'], 'kind': 'preparation', 'title': persons_module.PROFILE_TITLE, 'content': forged}).json()
    owner = a['owner_id']
    with client.app.state.service.db.connect(write=True) as c:  # 甲的回執指向乙的筆記：人物不符，兩邊都不承認
        c.execute('INSERT INTO requests(owner_id,operation,request_id,fingerprint,response) VALUES (?,?,?,?,?)',
                  (owner, persons_module.PROFILE_OPERATION + a['id'], 'crafted', 'x', json.dumps({'id': note_b['id']})))
    assert client.get(f"/api/persons/{b['id']}").json()['profile'] is None
    assert client.get(f"/api/persons/{a['id']}").json()['profile']['fields']['background'] == '甲的設定'
    assert persons_module.PROFILE_TITLE in legacy_note_titles(client, b['id'])
    first_b = save(client, b['id'], 'pb', None, background='乙的正式設定')
    assert first_b.status_code == 200 and first_b.json()['version'] == 1
    other = TestClient(client.app)
    ready(other, 'fix1_bound_b')
    c_person = create(other, '丙', 'c')
    assert save(other, c_person['id'], 'pa', None, background='丙').json()['version'] == 1  # 同一 request_id 在不同帳號各自獨立
    assert client.get(f"/api/persons/{a['id']}").json()['profile']['version'] == 1


# ---- FIX-2：已封存的人物不能修改 ----

def archive(client, person, request_id, revision):
    response = client.post(f"/api/persons/{person['id']}/status", json={'request_id': request_id, 'expected_revision': revision, 'status': 'archived'})
    assert response.status_code == 200, response.text
    return response.json()


def test_archived_person_cannot_be_edited_or_get_new_profile_versions(client):
    goal = ready(client, 'fix2_archived')
    a = create(client, '甲', 'a', description='原簡介')
    b = create(client, '乙', 'b')
    v1 = save(client, a['id'], 'p-1', None, background='封存前').json()
    assert client.post(f"/api/people/{a['id']}/connections", json={'request_id': 'c-1', 'other_person_id': b['id'], 'label': '同事'}).status_code == 201
    d = draft(client, goal, person_id=a['id'])
    assert client.post(f"/api/drafts/{d['id']}/confirm", json=confirm_payload(d, request_id='x-1')).status_code == 201
    archived = archive(client, a, 's-1', 1)
    with client.app.state.service.db.connect() as c:
        row_before = tuple(c.execute('SELECT * FROM people WHERE id=?', (a['id'],)).fetchone())
    before = counts(client)
    patch = client.patch(f"/api/persons/{a['id']}", json={'expected_revision': archived['revision'], 'description': '偷改'})
    assert patch.status_code == 409 and patch.json()['error']['code'] == 'person_archived', patch.text
    put = save(client, a['id'], 'p-2', v1['id'], background='封存後')
    assert put.status_code == 409 and put.json()['error']['code'] == 'person_archived', put.text
    assert save(client, a['id'], 'p-1', None, background='封存前').json() == v1  # 封存前已成功的請求重送：回原回執
    assert counts(client) == before
    with client.app.state.service.db.connect() as c:
        assert tuple(c.execute('SELECT * FROM people WHERE id=?', (a['id'],)).fetchone()) == row_before
    detail = client.get(f"/api/persons/{a['id']}")  # 讀取、關係、經歷照常
    assert detail.status_code == 200 and detail.json()['person']['status'] == 'archived'
    assert [x['person']['id'] for x in detail.json()['connections']] == [b['id']] and detail.json()['experiences']['mine'] == 1
    assert detail.json()['profile'] == v1
    restored = client.post(f"/api/persons/{a['id']}/status", json={'request_id': 's-2', 'expected_revision': archived['revision'], 'status': 'active'}).json()
    edited = client.patch(f"/api/persons/{a['id']}", json={'expected_revision': restored['revision'], 'description': '恢復後修改'})
    assert edited.status_code == 200 and edited.json()['description'] == '恢復後修改'
    v2 = save(client, a['id'], 'p-3', v1['id'], background='恢復後')
    assert v2.status_code == 200 and v2.json()['version'] == 2


# ---- FIX-3：列表分頁（101 位合成人物）----

def page_ids(client, **params):
    body = client.get('/api/persons', params={'limit': 50, **params}).json()
    return [p['id'] for p in body['items']], body['total']


def test_pagination_over_101_people_with_filters_and_archive(client):
    ready(client, 'fix3_pages')
    made = [create(client, f'人物{i:03d}', f'n-{i}', tags=['偶數'] if i % 2 == 0 else [], category='life' if i % 3 == 0 else 'other') for i in range(101)]
    pages = [page_ids(client, sort='name', offset=o) for o in (0, 50, 100)]
    assert [len(ids) for ids, _ in pages] == [50, 50, 1] and {total for _, total in pages} == {101}
    seen = [i for ids, _ in pages for i in ids]
    assert len(seen) == len(set(seen)) == 101 and set(seen) == {p['id'] for p in made}  # 不重複、不遺漏
    assert seen == [p['id'] for p in sorted(made, key=lambda p: p['name'])]
    even = [page_ids(client, q='偶數', sort='name', offset=o) for o in (0, 50)]
    assert [len(ids) for ids, _ in even] == [50, 1] and even[0][1] == 51
    life = [page_ids(client, category='life', sort='name', offset=o) for o in (0, 50)]
    assert [len(ids) for ids, _ in life] == [34, 0] and life[0][1] == 34
    for i, person in enumerate(made[:3]):
        archive(client, person, f'a-{i}', 1)
    active = [page_ids(client, sort='name', offset=o) for o in (0, 50)]
    assert [len(ids) for ids, _ in active] == [50, 48] and active[0][1] == 98
    archived_ids, archived_total = page_ids(client, status='archived', sort='name', offset=0)
    assert archived_total == 3 and archived_ids == [p['id'] for p in made[:3]]


# ---- 前端（Node 執行 persons.js；假的 API）----

NODE_SETUP = r"""
const assert = require('node:assert/strict');
globalThis.window = globalThis;
const replaced = [];
globalThis.history = {replaceState: (_, __, url) => replaced.push(url)};
require('./app/static/persons.js');
const UI = window.PersonsUI;
const people = Array.from({length: 101}, (_, i) => ({id: 'p' + String(i).padStart(3, '0'), owner_id: 'o', name: '人物' + i, aliases: [],
  person_type: 'real', person_subtype: null, description: '', roles: [], tags: [], category: 'other', status: 'active', origin_type: 'manual',
  followed: false, revision: 1, created_at: '2026-11-11T00:00:00+00:00'}));
const calls = [];
const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch]));
const state = {renderGeneration: 1, capabilities: {unified_people: true}, requests: new Map(), route: 'persons'};
const api = async path => {
  calls.push(path);
  const url = new URL('http://local/api' + path);
  if (url.pathname === '/api/persons') {
    const q = url.searchParams.get('q') || '', offset = Number(url.searchParams.get('offset')), limit = Number(url.searchParams.get('limit'));
    const items = people.filter(p => p.name.includes(q));
    return {items: items.slice(offset, offset + limit), total: items.length, offset, limit};
  }
  const id = decodeURIComponent(url.pathname.split('/')[3]);
  return {person: {...people[0], id, status: id === 'archived-one' ? 'archived' : 'active'}, profile: null, connections: [], experiences: {mine: 0, person_experiences: 0}};
};
UI.initialize({state, api, esc, link: (route, label, style = 'secondary') => `<a class="${style}" href="#${esc(route)}">${label}</a>`,
  button: (action, label, style = 'primary', attrs = '') => `<button data-action="${action}" ${attrs}>${label}</button>`,
  heading: (title, subtitle, action = '') => `<h1>${esc(title)}</h1><p>${esc(subtitle)}</p>${action}`,
  empty: (message, action = '') => `<div class="empty">${esc(message)}${action}</div>`, time: x => x, toast() {}, requestId: () => 'r',
  render: async () => {}, navigate() {}});
const cards = html => (html.match(/class="card char-card persons-list-card"/g) || []).length;  // 人物列表卡片（2026-11-11 加上整張可點的樣式）
// 每張人物卡片只有一個連結（整張卡片可點，2026-11-11 卡片整理），以它取得人物 ID
const ids = html => [...html.matchAll(/persons-card-open" href="#persons\/(p\d{3})"/g)].map(m => m[1]);
const has = (html, text) => html.includes(text);
(async () => {
"""


def run_node(script):
    node = os.environ.get('LIFEWORLD_NODE') or shutil.which('node')
    if not node:
        pytest.skip('需要 Node 執行前端模組；可設定 LIFEWORLD_NODE')
    result = subprocess.run([node, '-e', NODE_SETUP + script + '\n})().catch(e => { console.error(e); process.exit(1); });'],
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


def test_frontend_pages_50_50_1_and_links_keep_filters():
    run_node(r"""
const one = await UI.list(new URLSearchParams(''));
assert.equal(cards(one), 50); assert.ok(has(one, '共 101 位 · 第 1／3 頁'));
assert.ok(has(one, 'href="#persons?offset=50">下一頁')); assert.ok(!has(one, '上一頁'));
const two = await UI.list(new URLSearchParams('offset=50'));
assert.equal(cards(two), 50); assert.ok(has(two, '第 2／3 頁'));
assert.ok(has(two, 'href="#persons">上一頁')); assert.ok(has(two, 'href="#persons?offset=100">下一頁'));
const three = await UI.list(new URLSearchParams('offset=100'));
assert.equal(cards(three), 1); assert.ok(has(three, '第 3／3 頁')); assert.ok(!has(three, '下一頁'));
const all = [...ids(one), ...ids(two), ...ids(three)];
assert.equal(all.length, 101); assert.equal(new Set(all).size, 101);
assert.ok(calls.every(path => path.includes('limit=50')));
const filtered = await UI.list(new URLSearchParams('q=人物&type=fictional&category=life&status=archived&sort=name&offset=50'));
const expected = '#persons?q=%E4%BA%BA%E7%89%A9&amp;type=fictional&amp;category=life&amp;status=archived&amp;sort=name';
assert.ok(has(filtered, `href="${expected}">上一頁`), filtered);
assert.ok(has(filtered, `href="${expected}&amp;offset=100">下一頁`));
const sent = new URL('http://local/api' + calls.at(-1)).searchParams;
assert.equal(sent.get('person_type'), 'fictional'); assert.equal(sent.get('category'), 'life'); assert.equal(sent.get('status'), 'archived');
assert.equal(sent.get('sort'), 'name'); assert.equal(sent.get('q'), '人物'); assert.equal(sent.get('offset'), '50');
// 規格 2.0：封存狀態改用篩選區的「狀態」選單（取代切換連結）；條件保留在表單中，重新套用回到第一頁
assert.ok(has(filtered, '<option value="archived" selected>已封存</option>')); assert.ok(has(filtered, '<option value="fictional" selected>虛構</option>'));
assert.ok(has(filtered, '<option value="life" selected>生活</option>')); assert.ok(has(filtered, '<option value="name" selected>姓名</option>'));
""")


def test_frontend_out_of_range_offset_returns_to_a_valid_page():
    run_node(r"""
const far = await UI.list(new URLSearchParams('offset=500'));
assert.equal(cards(far), 1); assert.ok(has(far, '第 3／3 頁')); assert.equal(replaced.at(-1), '#persons?offset=100'); assert.equal(state.route, 'persons?offset=100');
const odd = await UI.list(new URLSearchParams('offset=73'));
assert.ok(has(odd, '第 2／3 頁')); assert.equal(new URL('http://local/api' + calls.at(-1)).searchParams.get('offset'), '50');
const negative = await UI.list(new URLSearchParams('offset=-20'));
assert.ok(has(negative, '第 1／3 頁'));
const search = await UI.list(new URLSearchParams('q=人物1&offset=50'));  // 搜尋後只剩 12 位：回到第 1 頁
assert.equal(cards(search), 12); assert.ok(has(search, '共 12 位 · 第 1／1 頁')); assert.ok(!has(search, '下一頁'));
""")


def test_frontend_archived_edit_url_has_no_submittable_form_and_type_wording():
    run_node(r"""
const archived = await UI.editForm('archived-one');
assert.ok(!has(archived, 'persons-edit-form')); assert.ok(!has(archived, 'type="submit"'));
assert.ok(has(archived, '這位人物已封存，不能修改。')); assert.ok(has(archived, 'href="#persons/archived-one">返回人物詳細頁'));
const active = await UI.editForm('active-one');
assert.ok(has(active, 'id="persons-edit-form"')); assert.ok(has(active, 'type="submit"'));
assert.ok(has(UI.createForm(), '未指定（儲存為真實類型）'));
assert.ok(has(await UI.list(new URLSearchParams('')), '真實類型（含預設）'));
assert.ok(!has(await UI.list(new URLSearchParams('')), '>真實人物<'));
""")
