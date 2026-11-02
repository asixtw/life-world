"""v0.5 劇場原型驗收：模型、錄音與額度皆為明示模擬。"""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect
from test_journey import page
from test_flow_wireframe import wireframe_url

# 截圖只包含隔離 Chromium 的虛構示例資料。
EVIDENCE = Path('docs/artifacts/theater-reliability')

def capture_evidence(page, name):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / name), full_page=True)



def begin(page, url, multiple=True):
    """從完整流程進入建立器，不直接注入場次資料。"""
    page.goto(url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='人物劇場', exact=True).click()
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    page.get_by_label('你想模擬什麼情境？', exact=True).fill('一起討論下次作品分工。')
    page.get_by_role('button', name='下一步：選擇人物', exact=True).click()
    page.get_by_label('加入阿哲', exact=True).check()
    if multiple:
        page.get_by_label('加入怡君', exact=True).check()
    page.get_by_label('這次你希望練習什麼？', exact=True).select_option('理解立場')
    page.get_by_role('button', name='檢查本場設定', exact=True).click()
    page.get_by_role('button', name='確認開始演練', exact=True).click()


def speak(page, text='你們希望怎麼分工？'):
    page.get_by_label('你的發言', exact=True).fill(text)
    page.get_by_role('button', name='送出發言', exact=True).click()
    expect(page.locator('[data-theater-event]')).not_to_have_count(0)
    expect(page.get_by_role('button', name='送出發言', exact=True)).to_be_enabled()


def qa(page, result):
    page.locator('details.theater-qa').evaluate('e => e.open = true')
    page.get_by_label('下一次模擬結果', exact=True).select_option(result)


@pytest.mark.parametrize('width', [390, 1440])
def test_v05_builder_bounded_group_stop_lumi_and_recap(page, wireframe_url, width, tmp_path):
    """未展示台詞不進回顧；Lumi 只進私人區，正式示例資料不變。"""
    page.set_viewport_size({'width': width, 'height': 844 if width == 390 else 1050})
    errors, external = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: external.append(r.url) if '/api/' in r.url or not r.url.startswith(wireframe_url) else None)
    begin(page, wireframe_url)
    expect(page.get_by_role('heading', name='多人情境演練', exact=True)).to_be_visible()
    expect(page.get_by_label('本場在場人物示意')).to_contain_text('阿哲')
    expect(page.get_by_label('本場在場人物示意')).to_contain_text('怡君')
    before = page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1'))")
    speak(page)
    state = page.evaluate('TheaterUI.snapshot()')
    assert 1 <= len(state['current']['pending']) <= 2
    unseen = [e['eventId'] for e in state['current']['pending']]  # 同文字的新回應不等於舊 queued 復活。
    page.get_by_role('button', name='暫停演練', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current.pending.length') == 0
    page.get_by_role('button', name='私下問 Lumi', exact=True).click()
    page.get_by_label('想問 Lumi 什麼？', exact=True).fill('怎樣問才不讓人有壓力？')
    page.get_by_role('button', name='取得私人建議', exact=True).click()
    expect(page.locator('.lumi-private')).to_contain_text('先問對方最在意的限制')
    page.get_by_role('button', name='返回演練', exact=True).click()
    expect(page.locator('.theater-transcript')).not_to_contain_text('先問對方最在意的限制')
    speak(page, '我想先聽聽各自的限制。')
    artifacts=Path(os.environ.get('LIFEWORLD_NEW_ARTIFACTS', str(tmp_path)))
    artifacts.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(artifacts/f'theater-dialogue-{width}.png'), full_page=True)
    page.get_by_role('button', name='結束本場', exact=True).click()
    expect(page.get_by_role('heading', name='本場演練回顧', exact=True)).to_be_visible()
    for event_id in unseen:
        assert event_id not in [e['eventId'] for e in page.evaluate('TheaterUI.snapshot().current.events')]  # 以穩定事件 ID 查取消後作廢。
    after = page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1'))")
    for key in ['people', 'records', 'goal', 'points']:
        assert before[key] == after[key]
    assert errors == [] and external == []
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


def test_v05_silence_error_retry_and_asr_review(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    qa(page, 'SILENCE')
    speak(page)
    expect(page.locator('.theater-transcript')).to_contain_text('對方暫時沒有回應')
    qa(page, 'PROVIDER_ERROR')
    page.get_by_label('你的發言', exact=True).fill('這句失敗後仍要保留。')
    page.get_by_role('button', name='送出發言', exact=True).click()
    expect(page.locator('.theater-error')).to_contain_text('服務故障')
    page.reload()
    expect(page.get_by_label('你的發言', exact=True)).to_have_value('這句失敗後仍要保留。')
    page.get_by_role('button', name='重試本次發言', exact=True).click()
    expect(page.locator('.theater-transcript')).to_contain_text('這句失敗後仍要保留。')
    assert page.locator('[data-speaker="user"]').filter(has_text='這句失敗後仍要保留。').count() == 1
    page.get_by_role('button', name='錄音轉文字（模擬）', exact=True).click()
    page.get_by_role('button', name='模擬拒絕麥克風', exact=True).click()
    expect(page.locator('.theater-asr')).to_contain_text('仍可直接打字')
    page.get_by_role('button', name='模擬允許麥克風', exact=True).click()
    page.get_by_role('button', name='停止錄音', exact=True).click()
    page.get_by_role('button', name='模擬轉錄失敗', exact=True).click()
    page.get_by_role('button', name='重試轉錄（模擬）', exact=True).click()
    page.get_by_label('校對轉錄文字', exact=True).fill('先確認我們的時間。')
    page.get_by_role('button', name='加入發言草稿', exact=True).click()
    expect(page.locator('.theater-asr')).to_contain_text('請先核對')
    page.get_by_label('我已核對轉錄內容', exact=True).check()
    page.get_by_role('button', name='加入發言草稿', exact=True).click()
    expect(page.get_by_label('你的發言', exact=True)).to_have_value('先確認我們的時間。')


def test_v05_limits_history_delete_and_new_session(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    for i in range(8):
        speak(page, f'第{i+1}次練習')
    expect(page.get_by_role('heading', name='本場演練回顧', exact=True)).to_be_visible()
    expect(page.locator('main')).to_contain_text('BUDGET_EXHAUSTED')
    old = page.evaluate('TheaterUI.snapshot().current.id')
    page.get_by_role('button', name='再練一次', exact=True).click()
    page.get_by_role('button', name='確認開始演練', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current.id') != old
    assert page.locator('[data-theater-event]').count() == 0
    page.get_by_role('button', name='結束本場', exact=True).click()
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.get_by_role('button', name='演練歷史', exact=True).click()
    page.once('dialog', lambda d: d.accept())
    page.get_by_role('button', name='刪除本場紀錄', exact=True).first.click()
    assert len(page.evaluate('TheaterUI.snapshot().history')) == 1


def test_v05_late_response_draft_validation_and_demo_isolation(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='人物劇場', exact=True).click()
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    page.get_by_role('button', name='下一步：選擇人物', exact=True).click()
    expect(page.locator('.theater-error')).to_contain_text('請描述')
    page.get_by_label('你想模擬什麼情境？', exact=True).fill('討論分工')
    page.reload()
    expect(page.get_by_label('你想模擬什麼情境？', exact=True)).to_have_value('討論分工')
    page.get_by_role('button', name='下一步：選擇人物', exact=True).click()
    page.get_by_role('button', name='檢查本場設定', exact=True).click()
    expect(page.locator('.theater-error')).to_contain_text('至少選一位')
    page.get_by_label('加入阿哲', exact=True).check()
    page.get_by_role('button', name='檢查本場設定', exact=True).click()
    page.get_by_role('button', name='確認開始演練', exact=True).click()
    page.get_by_label('你的發言', exact=True).fill('尚未生成的內容不能復活')
    page.get_by_role('button', name='送出發言', exact=True).click()
    page.get_by_role('button', name='暫停演練', exact=True).click()
    page.wait_for_timeout(700)
    assert page.locator('[data-speaker]:not([data-speaker="user"])').count() == 0
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.get_by_role('button', name='情境體驗（示範角色）', exact=True).click()
    page.get_by_role('button', name='三國策略', exact=True).click()
    expect(page.get_by_alt_text('三國策略示範封面')).to_be_visible()
    page.get_by_label('加入劉備', exact=True).check()
    page.get_by_role('button', name='開始腳本示範', exact=True).click()
    expect(page.locator('main')).to_contain_text('示範角色')
    assert page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).people.length") == 3


@pytest.mark.parametrize('behavior', ['ANSWER', 'ASK_BACK', 'SILENCE', 'DEFER', 'CLOSING', 'EVADE', 'MONOLOGUE'])
def test_v05_seven_behaviors_are_visible_and_bounded(page, wireframe_url, behavior):
    """七種角色行為有可辨識結果，且不會無限自動播放。"""
    begin(page, wireframe_url, multiple=True)
    qa(page, behavior)
    speak(page, '這次先討論各自的時間。')
    expect(page.locator('.theater-transcript')).to_contain_text(
        {'ANSWER':'回應','ASK_BACK':'反問','SILENCE':'暫時沉默','DEFER':'暫緩答覆','CLOSING':'準備結束','EVADE':'轉移話題','MONOLOGUE':'持續表達'}[behavior]
    )
    assert page.locator('[data-speaker]:not([data-speaker="user"])').count() <= 2
    page.get_by_role('button', name='結束本場', exact=True).click()
    assert page.locator('.recap-events [data-speaker]:not([data-speaker="user"])').count() <= 2


def test_v05_return_to_hub_and_resume_without_losing_turn(page, wireframe_url):
    """返回人物劇場與重新整理仍能接續未結束的私人演練。"""
    begin(page, wireframe_url, multiple=False)
    speak(page, '先把目標說清楚。')
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.reload()
    page.get_by_role('button', name='繼續目前演練', exact=True).click()
    expect(page.locator('.theater-transcript')).to_contain_text('先把目標說清楚。')
    assert page.evaluate('TheaterUI.snapshot().current.actions') == 1


@pytest.mark.parametrize('width', [390, 1440])
def test_v05_compose_remains_visible_after_each_turn(page, wireframe_url, width):
    """每次發言與角色回應後，輸入區保持可見，無需反覆手動捲動。"""
    page.set_viewport_size({'width': width, 'height': 844 if width == 390 else 1050})
    begin(page, wireframe_url, multiple=True)
    for index in range(2):
        page.get_by_label('你的發言', exact=True).fill(f'第 {index + 1} 次發言')
        page.get_by_role('button', name='送出發言', exact=True).click()
        page.wait_for_timeout(550)
        visible = page.get_by_label('你的發言', exact=True).evaluate('el => { const r=el.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight - 60; }')
        assert visible, f'{width}px 第 {index + 1} 輪輸入區未在視窗中'


def test_group_preview_uses_plain_language_instead_of_internal_c1(page, wireframe_url):
    """產品畫面說明你與多位模擬人物，內部分級不成為使用者文案。"""
    begin(page, wireframe_url, multiple=True)
    page.get_by_role('button', name='結束本場', exact=True).click()
    page.get_by_role('button', name='再練一次', exact=True).click()
    expect(page.locator('main')).to_contain_text('你與 2 位模擬人物')
    expect(page.locator('main')).not_to_contain_text('C1')


def test_named_recipient_responds_first_with_readable_behavior(page, wireframe_url):
    """指定發言對象要由該人物先回應，畫面不暴露英文行為代碼。"""
    begin(page, wireframe_url, multiple=True)
    page.get_by_label('發言對象', exact=True).select_option('jun')
    speak(page, '怡君，你的時間安排呢？')
    page.wait_for_timeout(550)
    response=page.locator('[data-theater-event]:not([data-speaker="user"])').first
    expect(response).to_have_attribute('data-speaker','怡君')
    expect(response.locator('header small')).to_have_text('回應')

# 以實際操作檢查草稿與活動場隔離；舊畫面測試不足以攔下人物漂移。
def test_sr01_active_cast_is_immutable_while_editing_new_draft(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    page.get_by_label('發言對象', exact=True).select_option('zhe')
    original = page.evaluate('TheaterUI.snapshot().current')
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.once('dialog', lambda dialog: dialog.accept())
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    if page.get_by_role('button', name='返回修改人物', exact=True).count():
        page.get_by_role('button', name='返回修改人物', exact=True).click()
    if page.get_by_role('button', name='下一步：選擇人物', exact=True).count():
        page.get_by_role('button', name='下一步：選擇人物', exact=True).click()
    page.get_by_label('加入阿哲', exact=True).uncheck()
    page.get_by_label('加入怡君', exact=True).check()
    page.get_by_role('button', name='返回情境描述', exact=True).click()
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.get_by_role('button', name='繼續目前演練', exact=True).click()
    current = page.evaluate('TheaterUI.snapshot().current')
    assert current['id'] == original['id']
    assert current['personIds'] == original['personIds']
    assert current['participantSnapshots'] == original['participantSnapshots']
    assert current['sourceSnapshots'] == original['sourceSnapshots']
    assert current['limitsSnapshot'] == original['limitsSnapshot']
    assert current['recipient'] == original['recipient']
    page.get_by_label('你的發言', exact=True).fill('原場人物仍是阿哲')
    page.get_by_role('button', name='送出發言', exact=True).click()
    page.get_by_role('button', name='繼續旁聽', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current.events.length'), page.evaluate('TheaterUI.snapshot()')
    assert page.evaluate('TheaterUI.snapshot().current.events.at(-1).speaker') == original['participantSnapshots'][0]['name']
    expect(page.get_by_label('本場在場人物示意')).to_contain_text('阿哲')
    expect(page.get_by_label('本場在場人物示意')).not_to_contain_text('怡君')
    capture_evidence(page, 'sr01-active-cast.png')


# 查看歷史後刷新仍須有原活動場，而非把歷史複本當成活動場。
def test_sr04_history_view_keeps_active_session(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    page.get_by_role('button', name='結束本場', exact=True).click()
    page.get_by_role('button', name='再練一次', exact=True).click()
    page.get_by_role('button', name='確認開始演練', exact=True).click()
    active_id = page.evaluate('TheaterUI.snapshot().current.id')
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.get_by_role('button', name='演練歷史', exact=True).click()
    page.get_by_role('button', name='查看本場回顧', exact=True).click()
    page.reload()
    assert page.evaluate('TheaterUI.snapshot().current.id') == active_id
    history_id = page.evaluate('TheaterUI.snapshot().viewingHistoryId')
    assert history_id is not None
    history_before = page.evaluate('TheaterUI.snapshot().history')
    assert page.locator('[data-theater="send"]').count() == 0
    assert page.locator('[data-theater="delete:'+history_id+'"]').count() == 0
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.get_by_role('button', name='繼續目前演練', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current.id') == active_id
    assert page.evaluate('TheaterUI.snapshot().history') == history_before
    capture_evidence(page, 'sr04-history-view.png')

# 新場取代須留下唯一歷史，取消時不得清空原場輸入。
def test_sr02_sr03_replace_transaction(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    page.get_by_label('你的發言', exact=True).fill('原場尚未送出')
    active = page.evaluate('TheaterUI.snapshot().current.id')
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.once('dialog', lambda d: d.accept())
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    page.get_by_role('button', name='下一步：選擇人物', exact=True).click()
    page.get_by_role('button', name='檢查本場設定', exact=True).click()
    page.once('dialog', lambda d: d.dismiss())
    page.get_by_role('button', name='確認開始演練', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current.id') == active
    assert page.evaluate('TheaterUI.snapshot().current.input') == '原場尚未送出'
    draft_after_cancel = page.evaluate('TheaterUI.snapshot().draft')
    assert draft_after_cancel['situation'] == '一起討論下次作品分工。'
    assert draft_after_cancel['people'] == ['zhe']
    capture_evidence(page, 'sr02-cancel-new-session.png')
    page.once('dialog', lambda d: d.accept())
    page.get_by_role('button', name='確認開始演練', exact=True).click()
    state = page.evaluate('TheaterUI.snapshot()')
    assert state['current']['id'] != active
    assert state['current']['actions'] == 0
    assert state['history'][-1]['id'] == active
    assert len([h for h in state['history'] if h['id'] == active]) == 1
    assert state['history'][-1]['events'] == []
    assert state['current']['events'] == []
    assert state['current']['unresolved'] == ''


# 快照、來源撤回及技術重試要以狀態欄位驗證。
def test_sr06_sr07_sr08_snapshots_revocation_and_retry(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='人物劇場', exact=True).click()
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    page.get_by_label('你想模擬什麼情境？', exact=True).fill('討論作品')
    page.get_by_role('button', name='下一步：選擇人物', exact=True).click()
    page.get_by_label('加入阿哲', exact=True).check()
    page.get_by_role('button', name='檢查本場設定', exact=True).click()
    page.get_by_label('使用 阿哲 的已記錄來源', exact=True).check()
    page.get_by_role('button', name='確認開始演練', exact=True).click()
    original = page.evaluate('TheaterUI.snapshot().current')
    page.evaluate("""() => {const k='lifeworld:flow-wireframe:v1';const s=JSON.parse(localStorage.getItem(k));s.people[0].name='改名後';localStorage.setItem(k,JSON.stringify(s));}""")
    page.reload()
    expect(page.get_by_label('本場在場人物示意')).to_contain_text('阿哲')
    assert page.evaluate('TheaterUI.snapshot().current.sourceSnapshots') == original['sourceSnapshots']
    page.evaluate("""() => {const k='lifeworld:flow-wireframe:v1';const s=JSON.parse(localStorage.getItem(k));s.people[0].source='已撤回';localStorage.setItem(k,JSON.stringify(s));}""")
    page.reload()
    state = page.evaluate('TheaterUI.snapshot().current')
    assert state['paused'] and state['actions'] == 0
    assert state['sourceSnapshots'][0]['validity'] == 'invalid'
    expect(page.locator('.theater-main')).to_contain_text('已撤回或變更')
    capture_evidence(page, 'sr07-source-revoked.png')


# 服務失敗時行動已接受且只計一次，重試沿用原行動。
def test_sr08_sr09_retry_ids_and_last_action(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    qa(page, 'PROVIDER_ERROR')
    page.get_by_label('你的發言', exact=True).fill('重試不另計次')
    page.get_by_role('button', name='送出發言', exact=True).click()
    failed = page.evaluate('TheaterUI.snapshot().current')
    assert failed['actions'] == 1 and len(failed['actionRecords']) == 1
    page.get_by_role('button', name='重試本次發言', exact=True).click()
    success = page.evaluate('TheaterUI.snapshot().current')
    assert success['actions'] == 1
    assert success['actionRecords'][0]['actionId'] == failed['actionRecords'][0]['actionId']
    assert len(success['actionRecords'][0]['attempts']) == 2
    assert len([e for e in success['events'] if e['speaker'] == 'user']) == 1
    page.get_by_role('button', name='繼續旁聽', exact=True).click()
    shown = page.evaluate('TheaterUI.snapshot().current')
    assert len([e for e in shown['events'] if e['speaker'] != 'user']) == 1
    assert len({e['eventId'] for e in shown['events']}) == len(shown['events'])
    capture_evidence(page, 'sr08-retry.png')


# 清除前取消不動兩個資料域，確認後保留無關 key。
def test_sr13_reset_scoped_keys(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    page.evaluate("localStorage.setItem('unrelated:test','keep')")
    page.once('dialog', lambda d: d.dismiss())
    page.get_by_role('button', name='清除本原型資料', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current') is not None
    capture_evidence(page, 'sr13-cancel-reset.png')
    page.once('dialog', lambda d: d.accept())
    page.get_by_role('button', name='清除本原型資料', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current') is None
    assert page.evaluate("localStorage.getItem('unrelated:test')") == 'keep'


# 舊頁 revision 必須拒絕寫入，保留未送文字。
def test_sr20_second_tab_conflict(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    other = page.context.new_page()
    other.goto(wireframe_url)
    other.get_by_label('你的發言', exact=True).fill('第二頁先寫')
    page.get_by_label('你的發言', exact=True).fill('第一頁未送文字')
    expect(page.locator('.theater-error')).to_contain_text('其他分頁已更新')
    assert page.evaluate('TheaterUI.snapshot().current.input') == '第一頁未送文字'
    assert other.evaluate('TheaterUI.snapshot().current.input') == '第二頁先寫'
    capture_evidence(page, 'sr20-conflict.png')
    other.close()

# 同一份虛構場次在手機與桌面實際截圖，並核對畫面沒有橫向溢出。
@pytest.mark.parametrize('width,height', [(390, 844), (1440, 1050)])
def test_sr19_mobile_desktop_and_sound_toggle(page, wireframe_url, width, height):
    page.set_viewport_size({'width': width, 'height': height})
    begin(page, wireframe_url, multiple=True)
    assert page.evaluate('TheaterUI.snapshot().soundEnabled') is False
    expect(page.get_by_role('button', name='提示音：關閉（點此開啟）')).to_be_visible()
    capture_evidence(page, f'sr19-live-{width}.png')
    page.get_by_role('button', name='提示音：關閉（點此開啟）').click()
    assert page.evaluate('TheaterUI.snapshot().soundEnabled') is True
    page.reload()
    assert page.evaluate('TheaterUI.snapshot().soundEnabled') is True
    page.get_by_role('button', name='提示音：開啟（點此靜音）').click()
    assert page.evaluate('TheaterUI.snapshot().soundEnabled') is False
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    capture_evidence(page, f'sound-off-{width}.png')

# 刷新不補播已排隊內容；舊版歷史可讀但沒有被偽造的來源快照。
def test_sr11_sr16_refresh_pending_and_legacy_migration(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    page.get_by_label('你的發言', exact=True).fill('刷新前已送')
    page.get_by_role('button', name='送出發言', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current.pending.length') == 1
    page.reload()
    state = page.evaluate('TheaterUI.snapshot()')
    assert state['current']['pending'] == []
    assert len([e for e in state['current']['events'] if e['speaker'] != 'user']) == 0
    assert state['current']['actions'] == 1
    assert len(state['current']['actionRecords']) == 1
    assert len(state['current']['actionRecords'][0]['attempts']) == 1
    assert state['current']['actionRecords'][0]['attempts'][0]['status'] == 'succeeded'
    page.evaluate("""() => { const key='lifeworld:theater-wireframe:v05';localStorage.setItem(key,JSON.stringify({stage:'situation',draft:{situation:'',purpose:'理解立場',people:[],sources:[]},current:null,history:[{id:'old-one',situation:'舊版故事',events:[{speaker:'user',text:'曾說過的話'}],actions:1,endReason:'由你結束'}]})); }""")
    page.reload()
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.get_by_role('button', name='演練歷史', exact=True).click()
    expect(page.locator('main')).to_contain_text('缺少當時人物／來源版本')
    assert page.evaluate('TheaterUI.snapshot().history[0].sourceSnapshots') is None
    old_id = page.evaluate('TheaterUI.snapshot().history[0].id')
    page.reload()
    assert page.evaluate('TheaterUI.snapshot().history.length') == 1
    assert page.evaluate('TheaterUI.snapshot().history[0].id') == old_id
    capture_evidence(page, 'sr16-legacy-history.png')

# 刪歷史採穩定 ID；取消刪除和刪 H1 都不影響活動場與 H2。
def test_sr05_delete_one_history_preserves_other_and_active(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    page.get_by_role('button', name='結束本場', exact=True).click()
    page.get_by_role('button', name='再練一次', exact=True).click()
    page.get_by_role('button', name='確認開始演練', exact=True).click()
    page.get_by_role('button', name='結束本場', exact=True).click()
    page.get_by_role('button', name='再練一次', exact=True).click()
    page.get_by_role('button', name='確認開始演練', exact=True).click()
    page.get_by_label('你的發言', exact=True).fill('目前場次輸入')
    before = page.evaluate('TheaterUI.snapshot()')
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.get_by_role('button', name='演練歷史', exact=True).click()
    page.once('dialog', lambda d: d.dismiss())
    page.get_by_role('button', name='刪除本場紀錄', exact=True).first.click()
    assert page.evaluate('TheaterUI.snapshot().history.length') == 2
    page.once('dialog', lambda d: d.accept())
    page.get_by_role('button', name='刪除本場紀錄', exact=True).first.click()
    after = page.evaluate('TheaterUI.snapshot()')
    assert [h['id'] for h in after['history']] == [before['history'][1]['id']]
    assert after['current']['id'] == before['current']['id']
    assert after['current']['input'] == '目前場次輸入'
    capture_evidence(page, 'sr05-history-delete.png')


# 示例載入先確認；取消保留目前場，確認後清除舊場與歷史。
def test_sr14_demo_replace_prompt(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    active = page.evaluate('TheaterUI.snapshot().current.id')
    page.once('dialog', lambda d: d.dismiss())
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current.id') == active
    capture_evidence(page, 'sr14-cancel-demo.png')
    page.once('dialog', lambda d: d.accept())
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current') is None
    assert page.evaluate('TheaterUI.snapshot().history') == []


# 已有場次與資料錯誤不應靜默重置原始儲存內容。
def test_sr15_corrupt_and_newer_schema_are_readonly(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    key = 'lifeworld:theater-wireframe:v05'
    page.evaluate("k => localStorage.setItem(k,'{bad-json')", key)
    page.reload()
    page.get_by_role('button', name='人物劇場', exact=True).click()
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    assert page.evaluate('localStorage.getItem("lifeworld:theater-wireframe:v05")') == '{bad-json'
    page.evaluate("k => localStorage.setItem(k,JSON.stringify({schemaVersion:999,revision:7,draft:{situation:'future',people:[],sources:[]},history:[]}))", key)
    page.reload()
    assert page.evaluate('JSON.parse(localStorage.getItem("lifeworld:theater-wireframe:v05")).schemaVersion') == 999
    page.get_by_role('button', name='返回修改人物', exact=True).click()
    assert page.evaluate('JSON.parse(localStorage.getItem("lifeworld:theater-wireframe:v05")).schemaVersion') == 999
    expect(page.locator('.theater-error')).to_contain_text('版本較新')

# 暫停與介入作廢 queued；晚到回應不能回到 events。
def test_sr10_epoch_discards_queued_after_pause(page, wireframe_url):
    begin(page, wireframe_url, multiple=True)
    speak(page, '先說明我的想法')
    queued = page.evaluate('TheaterUI.snapshot().current.pending.map(e => e.eventId)')
    assert queued
    previous_epoch = page.evaluate('TheaterUI.snapshot().current.generationEpoch')
    page.get_by_role('button', name='暫停演練', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current.generationEpoch') > previous_epoch
    page.wait_for_timeout(600)
    state = page.evaluate('TheaterUI.snapshot().current')
    assert state['pending'] == []
    assert not any(e['eventId'] in queued for e in state['events'])
    capture_evidence(page, 'sr10-pause-discard.png')


# 私訊獨立保存，回顧只含已展示事件，再練不帶前場承諾或額度。
def test_sr17_lumi_private_and_repractice(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    page.get_by_role('button', name='私下問 Lumi', exact=True).click()
    page.get_by_label('想問 Lumi 什麼？', exact=True).fill('我的私訊')
    page.get_by_role('button', name='取得私人建議', exact=True).click()
    state = page.evaluate('TheaterUI.snapshot().current')
    assert len(state['lumiPrivate']) == 1
    assert all('我的私訊' not in e['text'] for e in state['events'])
    page.get_by_role('button', name='返回演練', exact=True).click()
    page.get_by_role('button', name='結束本場', exact=True).click()
    page.get_by_role('button', name='再練一次', exact=True).click()
    page.get_by_role('button', name='確認開始演練', exact=True).click()
    fresh = page.evaluate('TheaterUI.snapshot().current')
    assert fresh['actions'] == 0 and fresh['events'] == [] and fresh['lumiPrivate'] == []

# 建立入口的接續／取代／取消三種選擇，只有明確取代才重設草稿。
def test_sr12_builder_draft_choices(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='人物劇場', exact=True).click()
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    page.get_by_label('你想模擬什麼情境？', exact=True).fill('尚未完成的草稿')
    draft_id = page.evaluate('TheaterUI.snapshot().draft.id')
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.once('dialog', lambda d: d.accept())
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().draft.id') == draft_id
    expect(page.get_by_label('你想模擬什麼情境？', exact=True)).to_have_value('尚未完成的草稿')
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    def cancel_choices(dialog):
        dialog.dismiss()
    page.on('dialog', cancel_choices)
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    page.remove_listener('dialog', cancel_choices)
    assert page.evaluate('TheaterUI.snapshot().draft.id') == draft_id
    choices = iter([False, True])
    def replace_choice(dialog):
        dialog.accept() if next(choices) else dialog.dismiss()
    page.on('dialog', replace_choice)
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    page.remove_listener('dialog', replace_choice)
    assert page.evaluate('TheaterUI.snapshot().draft.id') != draft_id
    expect(page.get_by_label('你想模擬什麼情境？', exact=True)).to_have_value('')

# 最後一個玩家額度已計次，技術失敗後仍可沿同一 actionId 重試。
def test_sr09_last_action_retry_uses_existing_budget(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    page.evaluate("""() => {const key='lifeworld:theater-wireframe:v05';const s=JSON.parse(localStorage.getItem(key));s.current.actions=7;localStorage.setItem(key,JSON.stringify(s));}""")
    page.reload()
    qa(page, 'PROVIDER_ERROR')
    page.get_by_label('你的發言', exact=True).fill('最後一次')
    page.get_by_role('button', name='送出發言', exact=True).click()
    failed = page.evaluate('TheaterUI.snapshot().current')
    assert failed['actions'] == 8
    page.get_by_role('button', name='重試本次發言', exact=True).click()
    success = page.evaluate('TheaterUI.snapshot().current')
    assert success['actions'] == 8
    assert success['actionRecords'][-1]['actionId'] == failed['actionRecords'][-1]['actionId']
    assert len(success['actionRecords'][-1]['attempts']) == 2


# 模擬儲存額滿，不能說已保存或丟掉螢幕上的草稿。
def test_sr15_storage_quota_keeps_visible_draft(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    page.evaluate("""() => {const original=Storage.prototype.setItem;Storage.prototype.setItem=function(key,value){if(key==='lifeworld:theater-wireframe:v05')throw new DOMException('Quota','QuotaExceededError');return original.call(this,key,value);};}""")
    page.get_by_label('你的發言', exact=True).fill('無法儲存的文字')
    expect(page.get_by_label('你的發言', exact=True)).to_have_value('無法儲存的文字')
    expect(page.locator('.theater-error')).to_contain_text('尚未保存')
    page.get_by_role('button', name='送出發言', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current.actions') == 0
    expect(page.get_by_label('你的發言', exact=True)).to_have_value('無法儲存的文字')
    capture_evidence(page, 'sr15-storage-failure.png')


# 使用假的音訊裝置計數，驗證靜音、手勢後確認音與刷新不補播。
def test_sound_is_opt_in_and_no_refresh_replay(page, wireframe_url):
    page.add_init_script("""window.__tones=0;window.AudioContext=class {constructor(){this.currentTime=0;this.destination={};this.state='running';}createOscillator(){return {frequency:{value:0},connect(){return this},start(){window.__tones++},stop(){}}}createGain(){return {gain:{setValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){return this}}}resume(){return Promise.resolve()}};""")
    begin(page, wireframe_url, multiple=False)
    assert page.evaluate('window.__tones') == 0
    page.get_by_role('button', name='提示音：關閉（點此開啟）').click()
    assert page.evaluate('window.__tones') == 1
    page.get_by_label('你的發言', exact=True).fill('有提示音的行動')
    page.get_by_role('button', name='送出發言', exact=True).click()
    assert page.evaluate('window.__tones') == 2
    page.reload()
    assert page.evaluate('window.__tones') == 0
    page.get_by_role('button', name='提示音：開啟（點此靜音）').click()
    assert page.evaluate('window.__tones') == 0

# 拒絕 AudioContext 解鎖時要關閉偏好並顯示文字；錯誤及完成只響一次。
def test_sound_completion_error_and_resume_rejection(page, wireframe_url):
    page.add_init_script("""window.__tones=[];window.AudioContext=class {constructor(){this.currentTime=0;this.destination={};this.state='running';}createOscillator(){return {frequency:{value:0},connect(){return this},start(){window.__tones.push(this.frequency.value)},stop(){}}}createGain(){return {gain:{setValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){return this}}}resume(){return Promise.resolve()}};""")
    begin(page, wireframe_url, multiple=False)
    page.get_by_role('button', name='提示音：關閉（點此開啟）').click()
    assert page.evaluate('window.__tones') == [440]
    qa(page, 'PROVIDER_ERROR')
    page.get_by_label('你的發言', exact=True).fill('音效失敗測試')
    page.get_by_role('button', name='送出發言', exact=True).click()
    assert page.evaluate('window.__tones') == [440, 220]
    page.get_by_role('button', name='重試本次發言', exact=True).dblclick()
    assert page.evaluate('window.__tones') == [440, 220, 440]
    page.get_by_role('button', name='結束本場', exact=True).dblclick()
    assert page.evaluate('window.__tones') == [440, 220, 440, 660]


def test_sound_rejected_or_unavailable_falls_back_to_text(page, wireframe_url):
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("""window.__tones=0;window.AudioContext=class {constructor(){this.currentTime=0;this.destination={};this.state='suspended';}resume(){return Promise.reject(new Error('blocked by browser'))}createOscillator(){window.__tones++;throw Error('must not play')}};""")
    begin(page, wireframe_url, multiple=False)
    page.get_by_role('button', name='提示音：關閉（點此開啟）').click()
    expect(page.get_by_role('button', name='提示音：關閉（點此開啟）')).to_be_visible()
    expect(page.locator('.theater-error')).to_contain_text('文字提示仍可使用')
    assert page.evaluate('TheaterUI.snapshot().soundEnabled') is False
    assert page.evaluate('window.__tones') == 0
    assert not errors
    capture_evidence(page, 'sound-resume-denied.png')
    page.reload()
    assert page.evaluate('TheaterUI.snapshot().soundEnabled') is False

    page.add_init_script('window.AudioContext = undefined')
    page.reload()
    page.get_by_role('button', name='提示音：關閉（點此開啟）').click()
    expect(page.locator('.theater-error')).to_contain_text('文字提示仍可使用')
    assert page.evaluate('TheaterUI.snapshot().soundEnabled') is False

# 第二個 key 寫入失敗時，示例取代退回原本兩份原始位元組。
def test_sr14_two_key_failure_rolls_back_and_retries(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    before = page.evaluate("""() => ({main:localStorage.getItem('lifeworld:flow-wireframe:v1'),theater:localStorage.getItem('lifeworld:theater-wireframe:v05')})""")
    page.evaluate("""() => {const original=Storage.prototype.removeItem;window.__removeItem=original;let failed=false;Storage.prototype.removeItem=function(key){if(key==='lifeworld:theater-wireframe:v05'&&!failed){failed=true;throw new DOMException('Injected','UnknownError');}return original.call(this,key);};}""")
    page.once('dialog', lambda d: d.accept())
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    expect(page.get_by_role('status')).to_contain_text('原有內容已保留')
    after = page.evaluate("""() => ({main:localStorage.getItem('lifeworld:flow-wireframe:v1'),theater:localStorage.getItem('lifeworld:theater-wireframe:v05')})""")
    assert before == after
    assert page.evaluate('TheaterUI.snapshot().current') is not None
    capture_evidence(page, 'sr14-transaction-rollback.png')
    page.once('dialog', lambda d: d.accept())
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current') is None
    assert page.evaluate("localStorage.getItem('lifeworld:flow-wireframe:transaction:v1')") is None


# 模擬中斷的 prepared 與 committed 日誌；每次重載都得到一致狀態。
def test_sr13_transaction_journal_recovery_is_idempotent(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    before = page.evaluate("""() => ({main:localStorage.getItem('lifeworld:flow-wireframe:v1'),theater:localStorage.getItem('lifeworld:theater-wireframe:v05')})""")
    page.evaluate("""saved => {const next=JSON.parse(saved.main);next.name='交易後示例';next.route='world';const tx={version:1,phase:'prepared',beforeMain:saved.main,beforeTheater:saved.theater,nextMain:JSON.stringify(next),nextTheater:null};localStorage.setItem('lifeworld:flow-wireframe:transaction:v1',JSON.stringify(tx));localStorage.setItem('lifeworld:flow-wireframe:v1',tx.nextMain);}""", before)
    page.reload()
    assert page.evaluate("localStorage.getItem('lifeworld:flow-wireframe:v1')") == before['main']
    assert page.evaluate("localStorage.getItem('lifeworld:theater-wireframe:v05')") == before['theater']
    assert page.evaluate("localStorage.getItem('lifeworld:flow-wireframe:transaction:v1')") is None
    page.evaluate("""saved => {const next=JSON.parse(saved.main);next.name='交易後示例';next.route='world';const tx={version:1,phase:'committed',beforeMain:saved.main,beforeTheater:saved.theater,nextMain:JSON.stringify(next),nextTheater:null};localStorage.setItem('lifeworld:flow-wireframe:transaction:v1',JSON.stringify(tx));}""", before)
    page.reload()
    assert page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).name") == '交易後示例'
    assert page.evaluate("localStorage.getItem('lifeworld:theater-wireframe:v05')") is None
    assert page.evaluate("localStorage.getItem('lifeworld:flow-wireframe:transaction:v1')") is None
    page.reload()
    assert page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).name") == '交易後示例'

# 清除失敗不能只剩一個資料域；取消與成功重試之後仍保留無關 key。
def test_sr13_reset_failure_is_recoverable(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    page.evaluate("localStorage.setItem('unrelated:test','keep')")
    before = page.evaluate("""() => ({main:localStorage.getItem('lifeworld:flow-wireframe:v1'),theater:localStorage.getItem('lifeworld:theater-wireframe:v05')})""")
    page.evaluate("""() => {const original=Storage.prototype.removeItem;let failed=false;Storage.prototype.removeItem=function(key){if(key==='lifeworld:theater-wireframe:v05'&&!failed){failed=true;throw Error('Injected reset failure');}return original.call(this,key);};}""")
    page.once('dialog', lambda d: d.accept())
    page.get_by_role('button', name='清除本原型資料', exact=True).click()
    expect(page.get_by_role('status')).to_contain_text('原有內容已保留')
    assert page.evaluate("localStorage.getItem('lifeworld:flow-wireframe:v1')") == before['main']
    assert page.evaluate("localStorage.getItem('lifeworld:theater-wireframe:v05')") == before['theater']
    page.once('dialog', lambda d: d.accept())
    page.get_by_role('button', name='清除本原型資料', exact=True).click()
    assert page.evaluate("localStorage.getItem('lifeworld:theater-wireframe:v05')") is None
    assert page.evaluate("localStorage.getItem('unrelated:test')") == 'keep'

# 草稿人物 ID 已失效時必須明示，不能回退成第一位真人。
def test_sr07_missing_person_id_blocks_start(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='人物劇場', exact=True).click()
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    page.get_by_label('你想模擬什麼情境？', exact=True).fill('失效人物案例')
    page.get_by_role('button', name='下一步：選擇人物', exact=True).click()
    page.evaluate("""() => {const key='lifeworld:theater-wireframe:v05',s=JSON.parse(localStorage.getItem(key));s.draft.people=['missing-id'];localStorage.setItem(key,JSON.stringify(s));}""")
    page.reload()
    page.get_by_role('button', name='檢查本場設定', exact=True).click()
    expect(page.locator('.theater-error')).to_contain_text('人物已不存在')
    assert page.evaluate('TheaterUI.snapshot().current') is None


# 雙擊開始與送出仍只建立一場及一筆玩家行動。
def test_sr03_sr09_double_click_is_idempotent(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='人物劇場', exact=True).click()
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    page.get_by_label('你想模擬什麼情境？', exact=True).fill('雙擊測試')
    page.get_by_role('button', name='下一步：選擇人物', exact=True).click()
    page.get_by_label('加入阿哲', exact=True).check()
    page.get_by_role('button', name='檢查本場設定', exact=True).click()
    page.get_by_role('button', name='確認開始演練', exact=True).dblclick()
    started = page.evaluate('TheaterUI.snapshot()')
    assert started['current']['actions'] == 0 and started['history'] == []
    page.get_by_label('你的發言', exact=True).fill('雙擊不重送')
    page.get_by_role('button', name='送出發言', exact=True).dblclick()
    result = page.evaluate('TheaterUI.snapshot().current')
    assert result['id'] == started['current']['id']
    assert result['actions'] == 1 and len(result['actionRecords']) == 1
    assert len([e for e in result['events'] if e['speaker'] == 'user']) == 1

# 長姓名在 390px 預覽及活動場仍不應造成橫向溢出。
def test_sr19_long_name_mobile_layout(page, wireframe_url):
    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.evaluate("""() => {const key='lifeworld:flow-wireframe:v1',s=JSON.parse(localStorage.getItem(key));s.people[0].name='超長虛構人物名字'.repeat(12);localStorage.setItem(key,JSON.stringify(s));}""")
    page.reload()
    page.get_by_role('button', name='人物劇場', exact=True).click()
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    page.get_by_label('你想模擬什麼情境？', exact=True).fill('長姓名版面')
    page.get_by_role('button', name='下一步：選擇人物', exact=True).click()
    page.locator('[data-theater-person="zhe"]').check()
    page.get_by_role('button', name='檢查本場設定', exact=True).click()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.get_by_role('button', name='確認開始演練', exact=True).click()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    capture_evidence(page, 'sr19-long-name-390.png')

# 活動人物被刪除時，快照仍顯示原名，但不得再接受行動。
def test_sr07_active_person_removed_pauses_without_new_action(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    original = page.evaluate('TheaterUI.snapshot().current')
    page.evaluate("""() => {const k='lifeworld:flow-wireframe:v1',s=JSON.parse(localStorage.getItem(k));s.people=s.people.filter(p=>p.id!=='zhe');localStorage.setItem(k,JSON.stringify(s));}""")
    page.reload()
    current = page.evaluate('TheaterUI.snapshot().current')
    assert current['id'] == original['id']
    assert current['participantSnapshots'] == original['participantSnapshots'][:0] + [{**original['participantSnapshots'][0], 'availability': 'missing'}]
    assert current['paused'] and current['actions'] == 0
    expect(page.locator('.theater-main')).to_contain_text('人物 阿哲 已不存在')
    capture_evidence(page, 'sr07-person-removed.png')
    page.get_by_role('button', name='送出發言', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current.actions') == 0


# 來源在建立前失效時不能產生一場缺來源的活動場。
def test_sr07_removed_source_blocks_start(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='人物劇場', exact=True).click()
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    page.get_by_label('你想模擬什麼情境？', exact=True).fill('來源在開始前撤回')
    page.get_by_role('button', name='下一步：選擇人物', exact=True).click()
    page.get_by_label('加入阿哲', exact=True).check()
    page.get_by_role('button', name='檢查本場設定', exact=True).click()
    page.get_by_label('使用 阿哲 的已記錄來源', exact=True).check()
    page.evaluate("""() => {const k='lifeworld:flow-wireframe:v1',s=JSON.parse(localStorage.getItem(k));s.people.find(p=>p.id==='zhe').source='';localStorage.setItem(k,JSON.stringify(s));}""")
    page.reload()
    page.get_by_role('button', name='確認開始演練', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current') is None
    expect(page.locator('.theater-error')).to_contain_text('來源不存在或已撤回')


@pytest.mark.parametrize('transition', ['pause', 'lumi', 'end', 'intervene'])
def test_sr10_late_queued_response_is_discarded_for_transitions(page, wireframe_url, transition):
    begin(page, wireframe_url, multiple=True)
    speak(page, '第一次發言')
    old_ids = page.evaluate('TheaterUI.snapshot().current.pending.map(e=>e.eventId)')
    assert old_ids
    old_epoch = page.evaluate('TheaterUI.snapshot().current.generationEpoch')
    if transition == 'pause':
        page.get_by_role('button', name='暫停演練', exact=True).click()
    elif transition == 'lumi':
        page.get_by_role('button', name='私下問 Lumi', exact=True).click()
    elif transition == 'end':
        page.get_by_role('button', name='結束本場', exact=True).click()
    else:
        page.get_by_label('你的發言', exact=True).fill('介入覆蓋未展示回應')
        page.get_by_role('button', name='介入討論', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().current.generationEpoch') > old_epoch
    page.wait_for_timeout(650)
    state = page.evaluate('TheaterUI.snapshot()')
    assert not any(e['eventId'] in old_ids for e in state['current']['events'])
    if transition != 'intervene':
        assert state['current']['pending'] == []
    if transition == 'end':
        assert not any(e['eventId'] in old_ids for e in state['history'][-1]['events'])


def test_sr10_replace_session_drops_old_queued_response(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    speak(page, '舊場尚有未展示回應')
    old = page.evaluate('TheaterUI.snapshot().current')
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.once('dialog', lambda d: d.accept())
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    page.get_by_role('button', name='下一步：選擇人物', exact=True).click()
    page.get_by_role('button', name='檢查本場設定', exact=True).click()
    page.once('dialog', lambda d: d.accept())
    page.get_by_role('button', name='確認開始演練', exact=True).click()
    page.wait_for_timeout(650)
    state = page.evaluate('TheaterUI.snapshot()')
    assert state['current']['id'] != old['id']
    assert state['history'][-1]['id'] == old['id']
    assert not any(e['eventId'] in [q['eventId'] for q in old['pending']] for e in state['history'][-1]['events'])
    assert state['current']['events'] == []


def test_sr09_completed_action_cannot_be_retried_or_replayed(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    speak(page, '不可重送的行動')
    before = page.evaluate('TheaterUI.snapshot().current')
    page.evaluate("""() => {const b=document.createElement('button');b.dataset.theater='retry';b.textContent='測試重送';document.body.append(b);b.click();b.remove()}""")
    after = page.evaluate('TheaterUI.snapshot().current')
    assert after['actions'] == before['actions']
    assert after['actionRecords'] == before['actionRecords']
    assert after['events'] == before['events']
    expect(page.locator('.theater-error')).to_contain_text('已完成或無法再重試')

# 人物卡帶入時仍須讓使用者選擇接續、取消或另建。
def test_sr12_person_card_with_existing_draft_choices(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='人物劇場', exact=True).click()
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    page.get_by_label('你想模擬什麼情境？', exact=True).fill('保留中的草稿')
    old = page.evaluate('TheaterUI.snapshot().draft')
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.get_by_role('button', name='與阿哲演練', exact=True).click()
    page.once('dialog', lambda d: d.accept())
    page.get_by_role('button', name='建立與此人物的情境', exact=True).click()
    resumed = page.evaluate('TheaterUI.snapshot().draft')
    assert resumed['id'] == old['id'] and resumed['situation'] == old['situation']
    assert resumed['people'] == old['people']
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.get_by_role('button', name='與阿哲演練', exact=True).click()
    decisions = iter([False, False])
    def cancel(dialog):
        dialog.accept() if next(decisions) else dialog.dismiss()
    page.on('dialog', cancel)
    page.get_by_role('button', name='建立與此人物的情境', exact=True).click()
    page.remove_listener('dialog', cancel)
    assert page.evaluate('TheaterUI.snapshot().draft.id') == old['id']
    page.get_by_role('button', name='返回人物劇場', exact=True).click()
    page.get_by_role('button', name='與阿哲演練', exact=True).click()
    decisions = iter([False, True])
    def replace(dialog):
        dialog.accept() if next(decisions) else dialog.dismiss()
    page.on('dialog', replace)
    page.get_by_role('button', name='建立與此人物的情境', exact=True).click()
    page.remove_listener('dialog', replace)
    fresh = page.evaluate('TheaterUI.snapshot().draft')
    assert fresh['id'] != old['id']
    assert fresh['people'] == ['zhe']
    assert fresh['situation'] == ''
    capture_evidence(page, 'sr12-person-card-draft.png')


# 390px 長姓名、焦點與輸入捲動都在 Chromium 可見範圍。
def test_sr19_mobile_focus_and_scroll_after_long_name(page, wireframe_url):
    page.set_viewport_size({'width': 390, 'height': 844})
    begin(page, wireframe_url, multiple=False)
    page.get_by_label('你的發言', exact=True).fill('很長的虛構發言。' * 60)
    page.get_by_label('你的發言', exact=True).focus()
    assert page.evaluate("document.activeElement.id === 'theater-speech'")
    assert page.evaluate("""() => {const r=document.activeElement.getBoundingClientRect();return r.top>=0&&r.top<innerHeight&&document.documentElement.scrollWidth<=innerWidth}""")
    page.get_by_role('button', name='送出發言', exact=True).click()
    expect(page.get_by_label('你的發言', exact=True)).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    capture_evidence(page, 'sr19-mobile-focus.png')


# 刷新時在磁碟中標記為尚未完成的 attempt 不得重送或展示角色事件。
def test_sr11_pending_attempt_refresh_is_not_replayed(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    speak(page, '未完成嘗試')
    page.evaluate("""() => {const k='lifeworld:theater-wireframe:v05',s=JSON.parse(localStorage.getItem(k));s.current.actionRecords.at(-1).status='pending';s.current.actionRecords.at(-1).attempts.at(-1).status='pending';localStorage.setItem(k,JSON.stringify(s));}""")
    page.reload()
    current = page.evaluate('TheaterUI.snapshot().current')
    assert current['pending'] == []
    assert current['actions'] == 1
    assert current['actionRecords'][-1]['actionId']
    assert current['actionRecords'][-1]['attempts'][-1]['status'] == 'interrupted'
    assert current['actionRecords'][-1]['status'] == 'interrupted'
    assert len([e for e in current['events'] if e['speaker'] == 'user']) == 1
    assert not any(e['speaker'] != 'user' for e in current['events'])
    page.wait_for_timeout(600)
    assert page.evaluate('TheaterUI.snapshot().current.pending.length') == 0

# 等待瀏覽器解除音訊暫停時離頁／暫停應取消舊音，結束只可播放完成音。
@pytest.mark.parametrize('transition,expected', [
    ('返回人物劇場', []),
    ('暫停演練', []),
    ('結束本場', [660]),
])
def test_sound_pending_unlock_respects_session_transition(page, wireframe_url, transition, expected):
    page.add_init_script("""window.__tones=[];window.__unlock=new Promise(resolve=>window.__resolveUnlock=resolve);window.AudioContext=class {constructor(){this.currentTime=0;this.destination={};this.state='suspended';}resume(){return window.__unlock}createOscillator(){return {frequency:{value:0},connect(){return this},start(){window.__tones.push(this.frequency.value)},stop(){}}}createGain(){return {gain:{setValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){return this}}}};""")
    begin(page, wireframe_url, multiple=False)
    page.get_by_role('button', name='提示音：關閉（點此開啟）').click()
    assert page.evaluate('window.__tones') == []
    page.get_by_role('button', name=transition, exact=True).click()
    page.evaluate('window.__resolveUnlock()')
    page.wait_for_timeout(50)
    assert page.evaluate('window.__tones') == expected
