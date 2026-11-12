"""「作品 → 下載 HTML」的 Chrome 畫面驗收。對象是 Local 8030 → Cloud SQL life_world_e2e、bucket lw-works-e2e-513506。

這個測試會真的生成一件作品（約 1 次規劃＋8 段，真實模型、會計費），所以要兩個開關都開才執行：

    LW_E2E_PERSONS_UI=1 LW_E2E_LIVE_GENERATION=1 .venv\\Scripts\\python.exe -m pytest -q browser_tests/test_work_export_ui.py

驗收順序：
1 作品 → ＋ 建立新作品，選一位人物、填場景與標題 → 2 開始生成，停在作品頁等到「已完成」→
3 完成後出現「下載 HTML」→ 4 按下去，瀏覽器收到一個 .html 檔 → 5 用完全離線的瀏覽環境開啟那個檔案，看得到標題與每一段 →
6 回到作品頁顯示「上次匯出」→ 7 重新整理後再下載一次，檔案內容相同。
設定 LW_E2E_SCREENSHOT_DIR 時，會把實際畫面存成 PNG。
"""
import hashlib
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_creation_people_ui import choice, shot
from test_persons_ui import BASE, page, synthetic_account  # noqa: F401（page 是 fixture）

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS_UI') != '1' or os.environ.get('LW_E2E_LIVE_GENERATION') != '1',
                                reason='會呼叫真實模型並計費；取得同意後以 LW_E2E_PERSONS_UI=1 LW_E2E_LIVE_GENERATION=1 執行')
TITLE = '留一條接縫（畫面驗收）'

PERSON = """async () => {
  const me = await fetch('/api/auth/me', {credentials: 'same-origin'}).then(r => r.json());
  const r = await fetch('/api/persons', {method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token},
    body: JSON.stringify({request_id: 'export-ui-wen', name: '溫若岑', person_subtype: 'original', description: '願意讓手藝留下接縫。', roles: ['展覽模型製作者'],
      profile: {background: '展覽模型製作者，也接舞臺道具修補。', personality: '手藝要能說明依據；怕別人看見尚未完成的自己。',
        expression: '邊摸索邊確認，常說「先做一小塊」。', knowledge_boundary: '不能只靠身分確定器物年代與真偽。'}})});
  if (!r.ok) throw new Error('persons ' + r.status + ' ' + await r.text());
}"""


def test_generate_a_work_then_download_it_as_offline_html(page, tmp_path):
    page.set_viewport_size({'width': 1440, 'height': 1500})
    synthetic_account(page)
    page.evaluate(PERSON)

    # 1. 建立作品：一位人物（不含我），填場景與標題
    page.locator('#nav').get_by_role('link', name='作品').click()
    page.get_by_role('link', name='＋ 建立新作品').first.click()
    page.get_by_role('checkbox', name='包含我').uncheck()
    choice(page, '溫若岑').locator('input[type=checkbox]').check()
    page.get_by_role('button', name='下一步：場景').click()
    page.locator('#create-scene').fill('週六午後，虛構的社區展覽試作桌；桌上有一個紙模型和兩張標籤草稿。溫若岑一個人在收尾，自言自語地檢查標籤上的用字。')
    page.locator('#create-title').fill(TITLE)

    # 2. 開始生成（真實模型）；作品頁會自己更新進度
    page.locator('.create-start').get_by_role('button', name='開始生成').click()
    expect(page.get_by_role('heading', name=TITLE)).to_be_visible()
    expect(page.get_by_role('button', name='下載 HTML')).to_have_count(0)  # 還沒完成：沒有下載
    expect(page.locator('#gen-run-panel')).to_contain_text('已完成', timeout=900000)  # 背景排程逐段生成，實測一件約 8 分鐘

    # 3. 完成後出現「下載 HTML」
    card = page.locator('#gen-export')
    expect(card.get_by_role('button', name='下載 HTML')).to_be_visible()
    expect(card).to_contain_text('不含人物設定')
    shot(page, 'export-01-completed-work.png')

    # 4. 下載
    with page.expect_download() as waiting:
        card.get_by_role('button', name='下載 HTML').click()
    target = tmp_path / 'first.html'
    waiting.value.save_as(str(target))
    assert waiting.value.suggested_filename == TITLE + '.html'
    data = target.read_bytes()
    assert data.startswith(b'<!doctype html>')

    # 5. 完全離線開啟下載的檔案
    offline = page.context.browser.new_context(viewport={'width': 900, 'height': 1400}, offline=True, color_scheme='light', locale='zh-TW')
    reader = offline.new_page()
    problems, requests = [], []
    reader.on('console', lambda message: problems.append(message.text) if message.type in ('error', 'warning') else None)
    reader.on('request', lambda request: requests.append(request.url))
    reader.goto(target.as_uri())
    assert reader.locator('h1').inner_text() == TITLE
    assert reader.locator('.lw-seg').count() >= 1 and reader.locator('.lw-tools').is_visible()
    assert '溫若岑' in reader.locator('.lw-meta').inner_text()
    assert [url for url in requests if url != target.as_uri()] == [] and problems == []
    folder = os.environ.get('LW_E2E_SCREENSHOT_DIR')
    if folder:
        reader.screenshot(path=str(Path(folder) / 'export-02-offline-reader.png'), full_page=True)
        (Path(folder) / 'export-downloaded.html').write_bytes(data)  # 留一份實際下載到的檔案當證據
    offline.close()

    # 6. 作品頁顯示上次匯出
    expect(card).to_contain_text('上次匯出')

    # 7. 重新整理後再下載一次：內容相同
    page.reload()
    expect(page.locator('#gen-export')).to_contain_text('上次匯出')
    with page.expect_download() as again:
        page.locator('#gen-export').get_by_role('button', name='下載 HTML').click()
    second = tmp_path / 'second.html'
    again.value.save_as(str(second))
    assert hashlib.sha256(second.read_bytes()).hexdigest() == hashlib.sha256(data).hexdigest()
    shot(page, 'export-03-after-download.png')
