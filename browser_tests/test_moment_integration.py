"""R2資訊架構接真實API；來源/時間與人物輸入不因分頁或錯誤遺失。"""
from test_journey import supplement_source
from test_journey import set_occurred
import pytest
import os
from pathlib import Path
from playwright.sync_api import expect
from test_journey import page,BASE,PNG
from test_integration_person_details import seed

ART=Path(os.environ.get('LIFEWORLD_UX_ARTIFACT_DIR',str(Path(__file__).resolve().parents[1]/'docs/integration/2026-11-12_GATE_A_R2_INTEGRATION')))

def shot(page,width,name):
    ART.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(ART/f'{width}-{name}.png'),full_page=True)


def start(page):
    person,_=seed(page);page.goto(BASE+'/#record');page.reload()
    expect(page.locator('#occurred-at')).to_have_value('2026-10-27T15:00')
    return person


@pytest.mark.parametrize('width',[320,390,1440])
def test_moment_tabs_keep_text_media_and_time_feedback(page,width):
    page.set_viewport_size({'width':width,'height':900});start(page)
    expect(page.get_by_role('heading',name='記錄這一刻。',exact=True)).to_be_visible()
    page.locator('#raw-text').fill('原文保留，素材不是自動確認。')
    page.get_by_role('tab',name='拍照／影像',exact=True).click()
    page.locator('[data-media-file=image]').set_input_files({'name':'synthetic.png','mimeType':'image/png','buffer':PNG})
    expect(page.locator('.media-item')).to_be_visible();shot(page,width,'step1-photo')
    page.get_by_role('tab',name='語音',exact=True).click();expect(page.locator('#raw-text')).not_to_be_visible();shot(page,width,'step1-audio')
    page.get_by_role('tab',name='文字',exact=True).click();expect(page.locator('#raw-text')).to_have_value('原文保留，素材不是自動確認。')
    page.locator('[data-moment-time] summary').click();set_occurred(page,'2026-10-28T12:00')
    page.locator('[data-experience-next]').click();expect(page.locator('[data-moment-time-error]')).to_contain_text('未來');shot(page,width,'time-error')
    expect(page.locator('#experience-step-title')).to_have_text('記錄這一刻。')
    assert not page.request.get(BASE+'/api/state').json()['drafts']
    set_occurred(page,'2026-10-27T12:00');page.locator('[data-experience-next]').click()
    expect(page.locator('#experience-step-title')).to_have_text('目標活動數量')
    page.locator('[data-experience-prev]').click();page.get_by_role('tab',name='拍照／影像',exact=True).click();expect(page.locator('.media-item')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')


def test_category_change_preserves_visible_unadded_input_and_can_add_next(page):
    person=start(page);page.locator('#raw-text').fill('人物資訊由我核對。');set_occurred(page,'2026-10-27T12:00')
    page.locator('[data-experience-next]').click();page.locator('[data-experience-next]').click()
    page.get_by_role('button',name='選擇既有人物',exact=True).click();page.locator('[data-workflow-pick="'+person['id']+'"]').click();page.locator('[data-workflow-role]').select_option('interaction')
    card=page.locator('[data-supplement-person]');card.locator('summary').first.click()
    category=card.locator('[data-supplement-input=dimension]');category.select_option('interests');card.locator('[data-supplement-input=value]').fill('閱讀')
    category.select_option('birthday');expect(category).to_have_value('interests')
    expect(card.locator('[data-supplement-input=value]')).to_be_visible();expect(card.locator('[data-supplement-status]')).to_contain_text('先加入')
    card.get_by_role('button',name='加入待核對項目',exact=True).click()
    expect(card.locator('[data-supplement-input=source_kind]')).to_be_visible()
    supplement_source(card);card.locator('[data-supplement-input=source_kind]').select_option('manual');card.locator('[data-supplement-input=evidence_type]').select_option('stated_by_person')
    card.get_by_role('button',name='加入待核對項目',exact=True).click();expect(card).to_contain_text('閱讀')
    card.locator('summary').first.click();category.select_option('birthday');card.locator('[data-supplement-input=birth_month]').fill('6');card.locator('[data-supplement-input=birth_day]').fill('15')
    card.get_by_role('button',name='加入待核對項目',exact=True).click();supplement_source(card);card.locator('[data-supplement-input=source_kind]').select_option('manual');card.get_by_role('button',name='加入待核對項目',exact=True).click()
    expect(card).to_contain_text('6 月 15 日')
    assert page.request.get(BASE+'/api/people/'+person['id']+'/details').json()['birthday'] is None


def test_empty_media_flow_returns_to_text_without_early_write(page):
    start(page);page.get_by_role('tab',name='語音',exact=True).click()
    page.locator('[data-experience-next]').click()
    expect(page.get_by_role('tab',name='文字',exact=True)).to_have_attribute('aria-selected','true')
    expect(page.locator('#raw-text')).to_be_focused()
    assert not page.request.get(BASE+'/api/state').json()['drafts']


def test_manual_media_text_returns_to_text_tab_without_provider_call(page):
    start(page);page.locator('#raw-text').fill('原文')
    page.get_by_role('tab',name='拍照／影像',exact=True).click()
    page.locator('[data-media-file=image]').set_input_files({'name':'manual.png','mimeType':'image/png','buffer':PNG})
    requests=[];page.on('request',lambda r:requests.append(r.url) if '/api/media/recognize' in r.url else None)
    page.locator('.media-transcript > summary').click();page.get_by_label('校對文字',exact=True).fill('合成校對文字')
    page.get_by_label('我已核對這段文字').check();page.get_by_role('button',name='加入經歷文字',exact=True).click()
    expect(page.get_by_role('tab',name='文字',exact=True)).to_have_attribute('aria-selected','true')
    expect(page.locator('#raw-text')).to_have_value('原文\n\n合成校對文字')
    assert requests==[]
    page.get_by_role('tab',name='拍照／影像',exact=True).click();expect(page.locator('.media-item')).to_have_count(1)
