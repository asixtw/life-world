"""對同事交付再補獨立邊界驗收，避免只重跑原有斷言。"""
from playwright.sync_api import expect
from test_journey import page
from test_flow_wireframe import wireframe_url
from test_theater_wireframe import begin, qa


def test_retry_keeps_original_recipient(page, wireframe_url):
    begin(page, wireframe_url)
    page.get_by_label('發言對象', exact=True).select_option('zhe')
    qa(page, 'PROVIDER_ERROR')
    page.get_by_label('你的發言', exact=True).fill('阿哲，請問你的想法？')
    page.get_by_role('button', name='送出發言', exact=True).click()
    page.get_by_label('發言對象', exact=True).select_option('jun')
    page.get_by_role('button', name='重試本次發言', exact=True).click()
    page.wait_for_timeout(550)
    current = page.evaluate('TheaterUI.snapshot().current')
    assert current['events'][0]['recipient'] == '阿哲'
    assert current['events'][1]['speaker'] == '阿哲'
    assert current['actions'] == 1


def test_lumi_input_is_session_private(page, wireframe_url):
    begin(page, wireframe_url)
    page.get_by_role('button', name='私下問 Lumi', exact=True).click()
    page.get_by_label('想問 Lumi 什麼？', exact=True).fill('只屬於舊場的私人文字')
    page.get_by_role('button', name='返回演練', exact=True).click()
    page.get_by_role('button', name='結束本場', exact=True).click()
    page.get_by_role('button', name='再練一次', exact=True).click()
    page.get_by_role('button', name='確認開始演練', exact=True).click()
    page.get_by_role('button', name='私下問 Lumi', exact=True).click()
    expect(page.get_by_label('想問 Lumi 什麼？', exact=True)).to_have_value('')


def test_missing_person_never_becomes_first_person(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.evaluate("""() => {const k='lifeworld:flow-wireframe:v1',s=JSON.parse(localStorage.getItem(k));s.selected='missing';s.route='person';localStorage.setItem(k,JSON.stringify(s));}""")
    page.reload()
    expect(page.get_by_role('heading', name='人物已不存在', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='加入星標', exact=False)).to_have_count(0)


def test_new_builder_cannot_inherit_previous_asr(page, wireframe_url):
    begin(page, wireframe_url)
    page.get_by_role('button', name='錄音轉文字（模擬）', exact=True).click()
    page.get_by_role('button', name='模擬允許麥克風', exact=True).click()
    page.get_by_role('button', name='停止錄音', exact=True).click()
    page.get_by_role('button', name='模擬轉錄成功', exact=True).click()
    page.get_by_role('button', name='結束本場', exact=True).click()
    page.get_by_role('button', name='再練一次', exact=True).click()
    page.get_by_role('button', name='確認開始演練', exact=True).click()
    assert page.evaluate('TheaterUI.snapshot().asr') == 'idle'
