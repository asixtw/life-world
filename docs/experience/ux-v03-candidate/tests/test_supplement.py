"""人物補充僅測設計記憶體狀態，不代表 API 或持久化能力。"""
import pytest
from playwright.sync_api import expect
from test_candidate import page, scene, ROOT


def add_fact(page,key,dimension,value):
    page.locator(f'[data-supplement="{key}"]>summary').click()
    page.locator(f'[data-dimension="{key}"]').select_option(dimension)
    page.locator(f'[data-fact-value="{key}"]').fill(value)
    page.locator(f'[data-action=add-supplement][data-key="{key}"]').click()


def test_optional_person_supplement_is_independent(page):
    scene(page,'multiple')
    add_fact(page,'yi','interests','底片攝影')
    add_fact(page,'new-an','food','清淡飲食')
    state=page.evaluate('UX.getState()')
    assert state['people'][0]['changes'][-1]['value']=='底片攝影'
    assert state['people'][1]['changes'][-1]['value']=='清淡飲食'
    assert not state['people'][0]['changes'][-1]['accepted']
    page.locator('[data-action=back]').click()
    page.locator('[data-action=next]').click()
    assert page.evaluate('UX.getState().people[0].changes.slice(-1)[0].value')=='底片攝影'


def test_supported_manual_fact_requires_individual_review(page):
    scene(page,'existing')
    add_fact(page,'yi','interests','底片攝影')
    page.locator('[data-action=next]').click()
    page.get_by_role('button',name='查看怡君本次變更').click()
    expect(page.locator('#not-saving')).to_contain_text('底片攝影')
    page.locator('[data-change]').check()
    expect(page.locator('#will-save')).to_contain_text('底片攝影')
    expect(page.locator('#will-save')).to_contain_text('閱讀')


def test_unsupported_birthday_stays_outside_save(page):
    scene(page,'existing')
    add_fact(page,'yi','birthday','05-20')
    page.locator('[data-action=next]').click()
    page.get_by_role('button',name='查看怡君本次變更').click()
    expect(page.locator('#not-saving')).to_contain_text('05-20')
    expect(page.locator('#not-saving')).to_contain_text('尚未支援正式寫入')
    expect(page.locator('#will-save')).not_to_contain_text('05-20')


@pytest.mark.parametrize('width',[320,390,1440])
def test_supplement_visual_states(page,width):
    page.set_viewport_size({'width':width,'height':844 if width<700 else 1000})
    scene(page,'existing')
    folder=ROOT/'screenshots-supplement'/str(width)
    folder.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(folder/'step3-collapsed.png'),full_page=True)
    add_fact(page,'yi','interests','底片攝影')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(folder/'step3-supplement.png'),full_page=True)
    page.locator('[data-action=next]').click()
    page.get_by_role('button',name='查看怡君本次變更').click()
    page.locator('[data-change]').check()
    page.screenshot(path=str(folder/'step4-difference.png'))
    footer=page.locator('.sheet-footer').bounding_box()
    assert footer['y']+footer['height']<=page.viewport_size['height']+1
    page.get_by_role('button',name='完成檢視').click()
    page.screenshot(path=str(folder/'step4-summary.png'),full_page=True)


def test_raw_source_change_invalidates_only_related_fact(page):
    scene(page,'existing')
    page.locator('[data-supplement="yi"]>summary').click()
    page.locator('[data-fact-value="yi"]').fill('攝影')
    page.locator('[data-fact-source="yi"]').select_option('raw')
    page.locator('[data-fact-quote="yi"]').fill('怡君說最近開始學攝影')
    page.locator('[data-action=add-supplement]').click()
    page.locator('[data-action=next]').click()
    page.get_by_role('button',name='查看怡君本次變更').click()
    page.locator('[data-change]').check()
    page.get_by_role('button',name='完成檢視').click()
    page.locator('[data-action=edit][data-step="3"]').click()
    page.locator('[data-action=back]').click()
    page.locator('[data-action=back]').click()
    page.locator('#raw-text').fill('今天獨自閱讀。')
    x=page.evaluate('UX.getState().people[0].changes[0]')
    assert not x['accepted'] and x['needsReview']


def test_new_person_draft_and_failure_preserve_supplement(page):
    scene(page,'new')
    add_fact(page,'new-an','skills','水彩')
    page.locator('[data-action=save-draft]').click()
    assert page.evaluate('UX.getState().drafts[0].payload.people[0].changes[0].value')=='水彩'
    page.locator('[data-action=resume]').first.click()
    assert page.evaluate('UX.getState().people[0].changes[0].value')=='水彩'
    while page.evaluate('UX.getState().step')<4:
        page.locator('[data-action=next]').click()
    page.locator('#review-tools>summary').click()
    page.locator('#save-outcome').select_option('failure')
    page.locator('[data-action=confirm]').click()
    expect(page.locator('#flow-error')).to_contain_text('中斷')
    assert page.evaluate('UX.getState().people[0].isNew')


def test_empty_source_and_duplicate_candidate_validation(page):
    scene(page,'existing')
    page.locator('[data-supplement="yi"]>summary').click()
    page.locator('[data-action=add-supplement]').click()
    expect(page.locator('[data-supplement-error]')).to_contain_text('請輸入')
    page.locator('[data-fact-value="yi"]').fill('攝影')
    page.locator('[data-fact-source="yi"]').select_option('raw')
    page.locator('[data-fact-quote="yi"]').fill('不在原文中')
    page.locator('[data-action=add-supplement]').click()
    assert page.evaluate('UX.getState().people[0].changes.length')==0
    page.locator('[data-fact-source="yi"]').select_option('manual')
    page.locator('[data-action=add-supplement]').click()
    page.locator('[data-fact-value="yi"]').fill('攝影')
    page.locator('[data-action=add-supplement]').click()
    assert page.evaluate('UX.getState().people[0].changes.length')==1


def test_cancelled_new_person_and_pending_edits_are_safe(page):
    scene(page,'step3')
    page.locator('[name=people-mode][value=some]').check()
    page.locator('[data-action=new-person]').click()
    page.locator('#new-name').fill('尚未建立')
    page.get_by_role('button',name='取消',exact=True).click()
    assert page.evaluate('UX.getState().people.length')==0
    page.locator('[name=people-mode][value=none]').check()
    page.locator('[data-action=next]').click()
    assert page.evaluate('UX.getState().step')==4
    scene(page,'existing')
    page.locator('[data-supplement="yi"]>summary').click()
    page.locator('[data-fact-value="yi"]').fill('尚未加入候選')
    page.locator('[data-action=next]').click()
    expect(page.locator('#flow-error')).to_contain_text('尚未加入')
    page.locator('[data-action=back]').click()
    page.locator('[data-action=next]').click()
    expect(page.locator('[data-fact-value="yi"]')).to_have_value('尚未加入候選')
    page.locator('[data-action=clear-supplement]').click()
    page.locator('[data-action=next]').click()
    assert page.evaluate('UX.getState().step')==4


@pytest.mark.parametrize('width',[320,390,1440])
def test_supplement_scenario_screenshots(page,width):
    page.set_viewport_size({'width':width,'height':844 if width<700 else 1000})
    folder=ROOT/'screenshots-supplement'/str(width)
    folder.mkdir(parents=True,exist_ok=True)
    for scenario,key,dimension,value in [('new','new-an','food','喜歡清淡飲食'),('multiple','yi','skills','街景攝影'),('mention','zhe','company','示意組織')]:
        scene(page,scenario)
        add_fact(page,key,dimension,value)
        if scenario=='multiple':
            add_fact(page,'new-an','interests','水彩')
        page.screenshot(path=str(folder/(scenario+'-step3.png')),full_page=True)
        page.locator('[data-action=next]').click()
        page.locator('.person-preview').first.click()
        expect(page.locator('#not-saving')).to_be_visible()
        if scenario in ['multiple','mention']:
            expect(page.locator('#will-save')).not_to_contain_text(value)
        page.screenshot(path=str(folder/(scenario+'-preview.png')))


def test_repeated_confirmation_is_only_one_ui_transition(page):
    """只證明 Candidate 按鈕保護，不冒稱正式交易去重。"""
    scene(page,'new')
    add_fact(page,'new-an','habits','先聽完再回答')
    page.locator('[data-action=next]').click()
    page.evaluate("()=>{const b=document.querySelector('[data-action=confirm]');b.click();b.click();}")
    expect(page.locator('.success-panel')).to_be_visible()
    assert page.evaluate('UX.getState().people.length')==1
    assert page.evaluate('UX.getState().people[0].changes.length')==1
