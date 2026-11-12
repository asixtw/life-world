"""多章節作品的 Chrome 畫面驗收：續寫 → 採納 → 下載整部作品。對象是 Local 8030 → Cloud SQL life_world_e2e。

這個測試會真的生成兩章（約 18 次模型呼叫，真實模型、會計費），所以要兩個開關都開才執行：

    LW_E2E_PERSONS_UI=1 LW_E2E_LIVE_GENERATION=1 .venv\\Scripts\\python.exe -m pytest -q browser_tests/test_story_series_ui.py

驗收順序：
1 第 1 章：建立作品並等到「已完成」→ 2 作品頁按「續寫下一章」，進到作品總覽，已定稿 1 章 →
3 填這一章的場景與章名，開始生成；作品頁標示它是草稿 → 4 完成後回作品總覽，草稿可以採納 →
5 採納：已定稿 2 章，草稿清空 → 6 下載整部作品，離線開啟有目錄與兩章 → 7 作品列表出現「看的故事・多章節」。
設定 LW_E2E_SCREENSHOT_DIR 時，會把實際畫面存成 PNG，並留一份下載到的檔案。

2026-11-12 起改用兩位人物：使用者看過生成的作品後指出「看不出人物個性與差異」。原本的驗收只有一位人物、設定只填了四欄，
看不出問題有沒有改善。現在用兩位九欄都填、個性相反的合成人物（慢而仔細的模型製作者、急而果斷的展覽統籌），
場景是兩人必須一起做決定的情況，呈現形式選小說敘事。人物表現得好不好由人閱讀下載到的檔案判斷，這裡不做自動判定。
"""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_creation_people_ui import choice, shot
from test_persons_ui import BASE, page, synthetic_account  # noqa: F401（page 是 fixture）

pytestmark = pytest.mark.skipif(os.environ.get('LW_E2E_PERSONS_UI') != '1' or os.environ.get('LW_E2E_LIVE_GENERATION') != '1',
                                reason='會呼叫真實模型並計費；取得同意後以 LW_E2E_PERSONS_UI=1 LW_E2E_LIVE_GENERATION=1 執行')
TITLE = '屋頂的紋樣（續寫驗收）'
# 兩位合成人物：九欄都填，個性、說話方式、行為習慣與弱點都相反
CAST = r"""async () => {
  const me = await fetch('/api/auth/me', {credentials: 'same-origin'}).then(r => r.json());
  const people = [
    {request_id: 'series-ui-wen', name: '溫若岑', person_subtype: 'original', roles: ['展覽模型製作者'],
     description: '展覽模型製作者，做事慢而仔細，東西沒做完不太願意給人看。',
     profile: {
       background: '做了十一年展覽模型，也接舞臺道具修補。曾經因為一件模型的說明寫得太肯定，被文史工作者當眾指正，從此對寫在標籤上的字特別小心。',
       personality: '慢熱、仔細，寧可慢也不說沒有把握的話。不喜歡正面衝突，被催的時候會先安靜下來做手上的事，但在「不能寫沒根據的話」這件事上不退讓。',
       motivation: '希望觀眾分得清楚哪些是有依據的復原、哪些是她自己的想像；不想再被當眾指正一次。',
       stance: '沒有依據的東西可以展出，但要老實標出來。趕不上寧可留白，也不寫錯。',
       abilities: '手很穩，能用紙、木片和補土做出細到一公釐的構件，看一眼就知道哪裡是後來補上的。不擅長在很多人面前說話。',
       expression: '說話慢，句子短，常停下來找比較準確的詞；不確定的事會直接說不知道。緊張時改談手上的材料，不談自己的感受。很少用驚嘆的語氣。',
       behavior: '說話時手不離開工作檯，習慣先摸一下實物再回答；不同意的時候不會馬上反駁，而是把東西拿給對方看。被催促時動作反而更慢。',
       knowledge_boundary: '懂材料、結構和修補的痕跡；不懂印刷時程、行銷和預算。不能只靠外觀判斷器物的年代與真偽。',
       restrictions: '怕別人看見還沒完成的東西；被當眾質疑時會僵住、說不出話。容易為了一個小地方拖到整體進度。'}},
    {request_id: 'series-ui-shao', name: '邵向晴', person_subtype: 'original', roles: ['展覽統籌'],
     description: '社區展覽的統籌，負責時程與對外聯絡，做事快，講求準時開幕。',
     profile: {
       background: '做了八年活動統籌，辦過三十多場社區展覽。上一檔展覽因為等一件展品延後開幕，被贊助單位撤了下一年的經費，從此把準時看得比什麼都重。',
       personality: '果斷、急性子，習慣馬上做決定，受不了事情懸著。對人直接但不記仇；對方講得出道理她會立刻改口，講不出來就照她的時程走。',
       motivation: '這檔展覽要準時開幕、順利結案，保住明年的經費；也不希望團隊裡的人因為她的催促而離開。',
       stance: '先求有、再求好。觀眾要的是看得懂的故事，細節可以開幕後再補。但她不願意公開說謊。',
       abilities: '能同時記住所有人的時程與截止時間，很會跟廠商談期限；三句話內把事情講成別人聽得懂的版本。看不出模型做工的好壞。',
       expression: '說話快而短，多用「現在」「幾點前」這類時間詞，喜歡直接給選項要對方選；常把別人的長句子替他講成一句結論。著急時會連問兩個問題不等回答。',
       behavior: '一邊說話一邊看手機上的時間、整理桌上的東西，會直接拿起別人的東西來看；談不下去時先提出一個折衷方案，而不是沉默。',
       knowledge_boundary: '懂時程、預算、廠商與觀眾動線；不懂模型工法與文史考據，分不出哪些部分有依據。',
       restrictions: '太急著收尾，常沒聽完就下結論；不喜歡承認自己不懂，會用「這不重要」帶過。事後才發現漏掉的細節。'}}];
  for (const body of people) {
    const r = await fetch('/api/persons', {method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token}, body: JSON.stringify(body)});
    if (!r.ok) throw new Error('persons ' + r.status + ' ' + await r.text());
  }
}"""
SCENE_1 = ('週五晚上八點，社區展覽開幕前一晚的試作桌。紙模型屋頂的紋樣是溫若岑照自己的想像補上的，沒有任何依據，'
           '標籤草稿上卻寫著「復原」。邵向晴來收標籤的定稿，印刷廠半小時後截稿。')
SCENE_2 = ('隔天早上，開幕前二十分鐘。模型旁多了一張早到的觀眾留下的紙條，問屋頂的紋樣是根據什麼復原的。'
           '溫若岑和邵向晴都在場，要在開門前決定怎麼回應。')
WAIT = 900000  # 背景排程逐段生成，實測一章約 5 到 8 分鐘


def test_continue_adopt_and_download_the_whole_work(page, tmp_path):
    page.set_viewport_size({'width': 1440, 'height': 1500})
    synthetic_account(page)
    page.evaluate(CAST)

    # 1. 第 1 章
    page.locator('#nav').get_by_role('link', name='作品').click()
    page.get_by_role('link', name='＋ 建立新作品').first.click()
    page.get_by_role('checkbox', name='包含我').uncheck()
    choice(page, '溫若岑').locator('input[type=checkbox]').check()
    choice(page, '邵向晴').locator('input[type=checkbox]').check()
    page.get_by_role('button', name='下一步：場景').click()
    page.locator('#create-scene').fill(SCENE_1)
    page.locator('button.create-head[data-node="output"]').click()  # ④ 輸出：呈現形式改成小說敘事（行為與神態用敘事寫出來）
    page.get_by_role('radio', name='小說敘事').check()
    page.locator('#create-title').fill(TITLE)
    page.locator('.create-start').get_by_role('button', name='開始生成').click()
    expect(page.locator('#gen-run-panel')).to_contain_text('已完成', timeout=WAIT)

    # 2. 續寫下一章 → 作品總覽
    page.get_by_role('button', name='續寫下一章').click()
    expect(page.get_by_role('heading', name=TITLE)).to_be_visible()
    expect(page.get_by_role('heading', name='已定稿的章節（1）')).to_be_visible()
    expect(page.get_by_role('heading', name='續寫第 2 章')).to_be_visible()
    expect(page.get_by_role('heading', name='草稿')).to_have_count(0)
    shot(page, 'series-01-overview-one-chapter.png')

    # 3. 這一章的場景與章名；開始生成後到草稿的作品頁
    form = page.locator('#series-next-form')
    expect(form.locator('#series-form')).to_have_value('narrative')  # 預設沿用第 1 章的呈現形式（2026-11-12 修正：原本固定預設劇本對白）
    form.get_by_label('這一章的場景與要發生的事（必填）').fill(SCENE_2)
    form.get_by_label('章名（選填，留白時由 AI 規劃）').fill('開門之前')
    form.get_by_role('button', name='開始生成這一章').click()
    expect(page.get_by_role('heading', name='開門之前')).to_be_visible()
    expect(page.get_by_text(f'這是《{TITLE}》的草稿')).to_be_visible()
    expect(page.locator('#gen-run-panel')).to_contain_text('已完成', timeout=WAIT)

    # 4. 回作品總覽：草稿可以採納，主線還是 1 章
    page.get_by_role('link', name='作品總覽').click()
    expect(page.get_by_role('heading', name='已定稿的章節（1）')).to_be_visible()
    expect(page.get_by_role('heading', name='草稿（1）')).to_be_visible()
    expect(page.get_by_text('已完成，等你決定')).to_be_visible()
    shot(page, 'series-02-draft-ready.png')

    # 5. 採納
    page.get_by_role('button', name='採納為第 2 章').click()
    expect(page.get_by_role('heading', name='已定稿的章節（2）')).to_be_visible()
    expect(page.get_by_role('heading', name='草稿（1）')).to_have_count(0)
    expect(page.locator('.series-chapters')).to_contain_text('第 2 章　開門之前')
    expect(page.get_by_role('heading', name='續寫第 3 章')).to_be_visible()
    shot(page, 'series-03-two-chapters.png')

    # 6. 下載整部作品，完全離線開啟
    with page.expect_download() as waiting:
        page.locator('#gen-export').get_by_role('button', name='下載 HTML').click()
    target = tmp_path / 'collection.html'
    waiting.value.save_as(str(target))
    assert waiting.value.suggested_filename == TITLE + '.html'
    offline = page.context.browser.new_context(viewport={'width': 900, 'height': 1400}, offline=True, color_scheme='light', locale='zh-TW')
    reader = offline.new_page()
    problems, requests = [], []
    reader.on('console', lambda message: problems.append(message.text) if message.type in ('error', 'warning') else None)
    reader.on('request', lambda request: requests.append(request.url))
    reader.goto(target.as_uri())
    assert reader.locator('h1').inner_text() == TITLE
    assert reader.locator('.lw-toc').get_by_role('link').count() == 2 and reader.locator('.lw-chapter').count() == 2
    assert '開門之前' in reader.locator('#ch-2 .lw-chapter-title').inner_text()
    assert [url for url in requests if url.split('#')[0] != target.as_uri()] == [] and problems == []
    folder = os.environ.get('LW_E2E_SCREENSHOT_DIR')
    if folder:
        reader.screenshot(path=str(Path(folder) / 'series-04-offline-collection.png'), full_page=True)
        (Path(folder) / 'series-downloaded.html').write_bytes(target.read_bytes())
    offline.close()

    # 7. 作品列表
    page.locator('#nav').get_by_role('link', name='作品').click()
    expect(page.get_by_text('看的故事・多章節').first).to_be_visible()  # 2026-11-12 起清單標籤依玩法命名（原本是「多章節作品」）
