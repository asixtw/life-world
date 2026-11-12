"""R3四項人工意見接真本機API/PG；不改Decimal/Owner/Confirm契約。"""
import os
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_journey import page,BASE,PNG,supplement_source
from test_integration_person_details import seed


def shot(page,width,name):
    # 三尺寸真產品畫面；只在明確提供產物目錄時保存，避免改寫歷史收據。
    directory=os.environ.get('LIFEWORLD_UX_ARTIFACT_DIR')
    if directory:
        target=Path(directory);target.mkdir(parents=True,exist_ok=True)
        expect(page.locator('#toast')).not_to_have_class('visible')
        page.screenshot(path=str(target/f'{width}-r3-{name}.png'),full_page=True)


def record(page,raw='這次有兩位人物小安閱讀，也提到R3新人物。'):
    person,headers=seed(page);page.goto(BASE+'/#record');page.reload();page.locator('#raw-text').fill(raw)
    return person,headers


@pytest.mark.parametrize('width',[320,390,1440])
def test_photo_acquisition_and_card_purpose_are_separate(page,width):
    page.set_viewport_size({'width':width,'height':900});record(page)
    page.get_by_role('tab',name='拍照／影像',exact=True).click()
    labels=page.locator('.media-inputs label:visible')
    assert labels.all_text_contents()==['拍照','選取照片']
    shot(page,width,'photo-entry')
    calls=[];page.on('request',lambda r:calls.append(r.url) if '/api/media/recognize' in r.url else None)
    page.get_by_label('選取照片',exact=True).set_input_files({'name':'畫面截圖.png','mimeType':'image/png','buffer':PNG})
    item=page.locator('[data-media-id]');ident=item.get_attribute('data-media-id')
    item.locator('[data-media-purpose] > summary').click();item.get_by_label('這是一張名片',exact=True).check()
    expect(item).to_have_attribute('data-media-kind','card')
    expect(item.locator('[data-media=copy]')).to_have_count(1)
    assert item.get_attribute('data-media-id')==ident and calls==[]
    item.locator('[data-media-purpose] > summary').click();item.get_by_label('這是一張名片',exact=True).uncheck()
    expect(item).to_have_attribute('data-media-kind','image')
    assert page.request.get(BASE+'/api/state').json()['experiences']==[]
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')


@pytest.mark.parametrize('width',[320,390,1440])
def test_count_default_and_partial_amount_keep_exact_contribution(page,width):
    page.set_viewport_size({'width':width,'height':900});record(page)
    state=page.request.get(BASE+'/api/state').json();goal=state['goals'][0];action=goal['actions'][0]
    page.locator('[data-experience-next]').click();page.locator('#goal-id').select_option(goal['id'])
    quantity=page.locator('[name="quantity-'+action['id']+'"]');expect(quantity).to_have_attribute('step','1')
    quantity.fill('0.5');assert quantity.evaluate('(n)=>n.checkValidity()')
    expect(quantity).to_have_value('0.5')
    page.locator('[data-quantity-up="'+action['id']+'"]').click();expect(quantity).to_have_value('1.5')
    quantity.fill('0.000001');assert quantity.evaluate('(n)=>n.checkValidity()')
    page.locator('[data-experience-next]').click();page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible()
    page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    after=page.request.get(BASE+'/api/state').json()
    assert after['goals'][0]['actions'][0]['progress']=='0.000001'
    assert len(after['experiences'])==len(after['rewards']['events'])==1


@pytest.mark.parametrize('width',[320,390,1440])
def test_person_rows_and_information_states_are_owner_targeted(page,width):
    page.set_viewport_size({'width':width,'height':900});person,headers=record(page)
    other=page.request.post(BASE+'/api/people',headers=headers,data={'name':person['name'],'roles':['朋友'],'common_context':'另一所學校'}).json()
    page.reload();page.locator('#raw-text').fill('這次有兩位人物小安閱讀，也提到R3新人物。')
    page.locator('[data-experience-next]').click();page.locator('#goal-id').select_option('');page.locator('[data-experience-next]').click()
    page.get_by_role('button',name='選擇既有人物',exact=True).click()
    rows=page.locator('[data-workflow-pick]');expect(rows).to_have_count(2)
    for row in rows.all():expect(row).to_have_class('person-search-row')
    shot(page,width,'person-search')
    page.locator('[data-workflow-search]').fill('絕對沒有這個人');expect(page.locator('[data-workflow-no-match]')).to_be_visible()
    page.locator('[data-workflow-search]').fill('');page.locator('[data-workflow-pick="'+person['id']+'"]').click();page.locator('[data-workflow-role]').select_option('interaction')
    page.get_by_role('button',name='選擇既有人物',exact=True).click();expect(page.locator('[data-workflow-pick="'+person['id']+'"]')).to_contain_text('已選擇')
    page.locator('[data-workflow-pick="'+other['id']+'"]').click();page.locator('[data-workflow-role]').nth(1).select_option('participant')
    card=page.locator('[data-supplement-person="existing:'+person['id']+'"]');card.locator('summary').first.click();card.locator('[data-supplement-input=dimension]').select_option('interests');card.locator('[data-supplement-input=value]').fill('桌遊')
    expect(card.locator('[data-supplement-input-status]')).to_contain_text(person['name']);expect(card.locator('[data-supplement-input-status]')).to_contain_text('興趣與嗜好');expect(card.locator('[data-supplement-input-status]')).to_contain_text('尚未加入資訊')
    page.locator('[data-experience-review]').click()
    expect(page.locator('#record-form')).to_be_visible();expect(page.locator('#notice')).to_contain_text(person['name']);expect(card.locator('[data-supplement-input=value]')).to_have_value('桌遊')
    shot(page,width,'unadded-information')
    supplement_source(card);card.locator('[data-supplement-input=source_kind]').select_option('manual');card.locator('[data-supplement-input=evidence_type]').select_option('stated_by_person');card.get_by_role('button',name='加入資訊',exact=True).click()
    expect(card).to_contain_text('已加入 1 項資訊')
    text=page.locator('#record-form').inner_text();assert '候選' not in text and '待核對' not in text
    page.get_by_role('button',name='＋ 新增人物',exact=True).click();pending=page.locator('[data-pending-target]');pending.locator('[data-target-name]').fill('R3新人物');pending.locator('[data-target-role]').select_option('mention');pending.locator('[data-target-start]').select_option(str('這次有兩位人物小安閱讀，也提到R3新人物。'.index('R3新人物')))
    page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible();expect(page.locator('[data-review-candidate-status]')).to_contain_text('待你確認')
    page.locator('[data-experience-preview="existing:'+person['id']+'"]').click();page.locator('[data-candidate-select]').check();page.get_by_role('button',name='完成檢視',exact=True).click();page.locator('#story-reviewed').check();page.get_by_role('button',name='我已核對，確認保存',exact=True).click()
    expect(page.locator('#review-form')).to_have_count(0);expect(page.locator('#app')).to_contain_text('已確認並保存')
    assert page.request.get(BASE+'/api/people/'+person['id']+'/overview').json()['facts']['interests'][0]['value']=='桌遊'
    assert page.request.get(BASE+'/api/people/'+other['id']+'/overview').json()['facts']['interests']==[]
