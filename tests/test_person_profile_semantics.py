"""人物設定語意定型（2026-11-11 產品裁決）：五區塊九欄位，只描述人物本身。

程式自帶的自動測試（開發時快速檢查）；完成依據是部署後在 Cloud SQL life_world_e2e 的實測。
- 九個 JSON key 不變（person_profile.v1），舊版本相容；restrictions 的語意是「固有限制與弱點」，不是作品演出禁止事項。
- AI 提示詞逐欄說明人物本身的語意，並排除作品場景、演出職務、演出目標、情境指令、範例台詞與外部演出規則。
- AI 可「產生」或「改善」指定欄位（mode），結果仍只回候選。
"""
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import person_profile_ai
from app.ai_providers import FakeProvider
from app.config import DemoPolicy
from app.main import create_app
from conftest import onboard, register

KEYS = ['background', 'personality', 'motivation', 'stance', 'abilities', 'expression', 'behavior', 'knowledge_boundary', 'restrictions']


def test_prompt_describes_person_only_semantics():
    system = person_profile_ai.PERSON_PROFILE.system
    for phrase in ('固有限制與弱點', '核心信念與價值觀', '知識範圍', '行為模式', '說話與表達方式'):
        assert phrase in system, phrase
    for excluded in ('作品場景', '演出職務', '演出目標', '情境', '範例台詞', '演出規則'):
        assert excluded in system, excluded  # 明確列為不要產生的內容
    assert '禁止事項' not in system.replace('不是作品演出的禁止事項', '')
    assert person_profile_ai.PERSON_PROFILE.prompt_version == 'person-profile-v2'
    assert set(person_profile_ai.PersonProfileDraft.model_fields) == set(KEYS)  # 九個 key 不變


@pytest.fixture
def client(tmp_path):
    app = create_app(data_dir=tmp_path, policy=DemoPolicy(points_per_experience=3, max_upload_bytes=4096),
                     clock=lambda: datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc), generation_provider=FakeProvider())
    with TestClient(app) as c:
        onboard(c)
        register(c, 'profile_semantics')
        yield c


def test_improve_mode_is_recorded_and_old_versions_still_read(client):
    person = client.post('/api/persons', json={'request_id': 'p', 'name': '周瑜', 'profile': {'personality': '儒雅', 'restrictions': '禁止事項：不得罵人'}}).json()
    response = client.post('/api/ai/generate', json={'request_id': 'g-improve', 'module': 'person_profile',
                                                     'input': {'person_id': person['id'], 'guidance': '', 'consent': True,
                                                               'target_fields': ['personality'], 'mode': 'improve'}})
    assert response.status_code == 201, response.text
    with client.app.state.service.db.connect() as c:
        row = c.execute("SELECT input_json,prompt_version FROM ai_generations WHERE request_id='g-improve'").fetchone()
    assert json.loads(row['input_json'])['mode'] == 'improve' and row['prompt_version'] == 'person-profile-v2'
    bad = client.post('/api/ai/generate', json={'request_id': 'g-bad', 'module': 'person_profile',
                                                'input': {'person_id': person['id'], 'guidance': '', 'consent': True, 'mode': 'perform'}})
    assert bad.status_code == 422
    profile = client.get(f"/api/persons/{person['id']}").json()['profile']  # 舊版內容照原 key 讀回，不改寫
    assert profile['version'] == 1 and profile['fields']['restrictions'] == '禁止事項：不得罵人'


NODE = r"""
const assert = require('node:assert/strict');
globalThis.window = globalThis; globalThis.history = {replaceState() {}};
require('./app/static/persons.js');
const UI = window.PersonsUI;
const person = {id: 'p1', owner_id: 'o', name: '周瑜', aliases: [], person_type: 'real', person_subtype: 'historical', description: '', roles: [], tags: [],
  category: 'other', status: 'active', origin_type: 'manual', followed: false, revision: 1, created_at: '', notes: '', common_context: ''};
const profile = {id: 'n1', version: 1, saved_at: '2026-11-11T00:00:00+00:00', origin: 'manual', generation_id: null,
  fields: {background: '出身廬江', personality: '儒雅', motivation: '', stance: '', abilities: '', expression: '', behavior: '', knowledge_boundary: '', restrictions: '心高氣傲'}};
const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch]));
UI.initialize({state: {renderGeneration: 1, capabilities: {unified_people: true}, requests: new Map()},
  api: async path => path === '/generation/status' ? {available: true, provider: 'gemini'} : {person, profile, connections: [], experiences: {mine: 0, person_experiences: 0}},
  esc, link: (r, l) => `<a href="#${esc(r)}">${l}</a>`, button: (a, l, s, attrs = '') => `<button data-action="${a}" ${attrs}>${l}</button>`,
  heading: (t, s, a = '') => `<h1>${esc(t)}</h1>${a}`, empty: (m, a = '') => `<div>${esc(m)}${a}</div>`, time: x => x, toast() {}, requestId: () => 'r',
  render: async () => {}, navigate() {}});
(async () => {
  const blocks = ['A｜人物背景', 'B｜人格特質', 'C｜能力與知識', 'D｜行為與表達', 'E｜個人弱點'];
  const labels = ['背景', '性格', '動機', '核心信念與價值觀', '能力與專長', '知識範圍', '行為模式', '說話與表達方式', '固有限制與弱點'];
  const form = await UI.editForm('p1');
  let last = -1;
  for (const block of blocks) { const at = form.indexOf(block); assert.ok(at > last, block); last = at; }  // 五區塊依序出現
  for (const label of labels) assert.ok(form.includes(label), label);
  for (const key of ['background', 'personality', 'motivation', 'stance', 'abilities', 'knowledge_boundary', 'behavior', 'expression', 'restrictions'])
    assert.ok(form.includes(`id="profile-${key}"`), key);
  assert.ok(form.includes('心高氣傲'));  // 舊版內容回填
  assert.ok(!form.includes('禁止事項') && !form.includes('範例台詞') && !form.includes('演出職務：'));
  assert.ok(form.includes('name="ai_mode" value="improve"'));  // 可選「改善現有內容」
  const tab = await UI.detail('p1', 'profile');
  for (const block of blocks) assert.ok(tab.includes(block), 'tab ' + block);
  assert.ok(tab.includes('出身廬江') && tab.includes('心高氣傲') && !tab.includes('禁止事項'));
})().catch(e => { console.error(e); process.exit(1); });
"""


def test_profile_form_and_tab_show_five_blocks_nine_fields():
    node = os.environ.get('LIFEWORLD_NODE') or shutil.which('node')
    if not node:
        pytest.skip('需要 Node 執行前端模組')
    result = subprocess.run([node, '-e', NODE], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
