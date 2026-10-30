"""v0.5 劇場原型驗收：模型、錄音與額度皆為明示模擬。"""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect
from test_journey import page
from test_flow_wireframe import wireframe_url


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
    before = page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1'))")
    speak(page)
    state = page.evaluate('TheaterUI.snapshot()')
    assert 1 <= len(state['current']['pending']) <= 2
    unseen = [e['text'] for e in state['current']['pending']]
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
    for text in unseen:
        expect(page.locator('.recap-events')).not_to_contain_text(text)
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
        'CHARACTER_SILENCE' if behavior == 'SILENCE' else behavior
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
