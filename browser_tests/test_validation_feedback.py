"""阻擋下一步時必須說明原因、帶到修正位置，並保留草稿。"""
import pytest
from playwright.sync_api import expect
from test_journey import page
from test_flow_wireframe import wireframe_url, open_habit_calendar
from test_theater_wireframe import begin


@pytest.mark.parametrize('width', [390, 1440])
def test_empty_record_explains_and_focuses_input(page, wireframe_url, width):
    page.set_viewport_size({'width': width, 'height': 844})
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='記錄新經歷', exact=True).click()
    page.get_by_role('button', name='整理為草稿', exact=True).click()
    expect(page.locator('#raw')).to_be_focused()
    expect(page.locator('#raw')).to_have_attribute('aria-invalid', 'true')
    expect(page.locator('#raw-error')).to_contain_text('輸入')
    expect(page.locator('#record .form-feedback')).to_contain_text('輸入')
    page.get_by_label('今天發生了什麼？', exact=True).fill('已經輸入，不要遺失')
    expect(page.locator('#raw')).not_to_have_attribute('aria-invalid', 'true')
    expect(page.locator('#raw')).to_have_attribute('aria-describedby', 'raw-hint')
    page.get_by_role('button', name='整理為草稿', exact=True).click()
    expect(page.get_by_label('經歷摘要', exact=True)).to_have_value('已經輸入，不要遺失')
    page.get_by_role('button', name='確認保存', exact=True).click()
    expect(page.locator('#experience-confirm')).to_be_focused()
    expect(page.locator('#review .form-feedback')).to_contain_text('確認')


def test_native_required_has_visible_chinese_feedback(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='開始設定目標', exact=True).click()
    expect(page.locator('#name-error')).to_contain_text('你的稱呼')
    expect(page.locator('#name')).to_be_focused()
    page.get_by_label('你的稱呼', exact=True).fill('測試者')
    page.get_by_role('button', name='開始設定目標', exact=True).click()
    page.get_by_label('目標名稱', exact=True).fill('   ')
    page.get_by_role('button', name='下一步', exact=True).click()
    expect(page.locator('#goal-name-error')).to_contain_text('目標名稱')


def test_missing_schedule_explains_near_calendar(page, wireframe_url):
    open_habit_calendar(page, wireframe_url)
    page.get_by_label('習慣名稱', exact=True).fill('閱讀')
    page.get_by_role('button', name='下一步', exact=True).click()
    expect(page.locator('#wizard .form-feedback')).to_contain_text('至少安排一天')
    expect(page.locator('.schedule-editor')).to_have_attribute('aria-invalid', 'true')
    expect(page.get_by_label('習慣名稱', exact=True)).to_have_value('閱讀')


def test_theater_empty_situation_focuses_field(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='人物劇場', exact=True).click()
    page.get_by_role('button', name='建立我的情境', exact=True).click()
    page.get_by_role('button', name='下一步：選擇人物', exact=True).click()
    expect(page.locator('#theater-situation')).to_be_focused()
    expect(page.locator('#theater-situation-error')).to_contain_text('情境')


def test_incomplete_record_can_still_be_saved_as_draft(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='記錄新經歷', exact=True).click()
    page.get_by_label('實際發生的時間', exact=True).fill('')
    page.get_by_role('button', name='先存草稿，明天再整理', exact=True).click()
    page.reload()
    page.get_by_role('button', name='繼續草稿', exact=True).click()
    expect(page.get_by_label('實際發生的時間', exact=True)).to_have_value('')


def test_hidden_quantity_error_opens_details_without_losing_name(page, wireframe_url):
    open_habit_calendar(page, wireframe_url)
    page.get_by_label('習慣名稱', exact=True).fill('閱讀保留')
    page.locator('#habit-quantity').evaluate('e=>e.value="0"')
    page.get_by_role('button', name='下一步', exact=True).click()
    expect(page.locator('#habit-quantity')).to_be_visible()
    expect(page.locator('#habit-quantity')).to_be_focused()
    expect(page.locator('#habit-quantity-error')).to_contain_text('不可小於')
    expect(page.get_by_label('習慣名稱', exact=True)).to_have_value('閱讀保留')


def test_night_time_error_is_local_and_actionable(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='夜間設定', exact=True).click()
    page.get_by_label('安靜時段開始', exact=True).fill('23:00')
    page.get_by_label('安靜時段結束', exact=True).fill('23:00')
    page.get_by_role('button', name='保存夜間設定', exact=True).click()
    expect(page.locator('#night-end')).to_be_focused()
    expect(page.locator('#settings .form-feedback')).to_contain_text('不同')


def test_manual_review_uses_same_date_validation(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='記錄新經歷', exact=True).click()
    page.get_by_label('今天發生了什麼？', exact=True).fill('保留這段原文')
    page.get_by_label('實際發生的時間', exact=True).fill('')
    page.get_by_role('button', name='手動整理', exact=True).click()
    expect(page.locator('#occurred')).to_be_focused()
    expect(page.locator('#occurred-error')).to_contain_text('實際發生的時間')
    expect(page.get_by_label('今天發生了什麼？', exact=True)).to_have_value('保留這段原文')


def test_lumi_missing_question_has_field_guidance(page, wireframe_url):
    begin(page, wireframe_url, multiple=False)
    page.get_by_role('button', name='私下問 Lumi', exact=True).click()
    page.get_by_role('button', name='取得私人建議', exact=True).click()
    expect(page.locator('#theater-lumi-input')).to_be_focused()
    expect(page.locator('#theater-lumi-input-error')).to_contain_text('問題')
    assert page.evaluate('TheaterUI.snapshot().current.lumiCount') == 0
