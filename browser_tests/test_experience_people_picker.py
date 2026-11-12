"""第三步角色/來源/Owner與本機草稿；真本機API，不是Google或Alpha驗收。"""
from test_journey import set_occurred
from uuid import uuid4
import pytest
from playwright.sync_api import expect
from test_journey import page,BASE
from test_integration_person_details import seed


def record(page,raw):
    page.goto(BASE+'/#record');page.reload();page.locator('#raw-text').fill(raw);set_occurred(page,'2026-10-27T12:00')
    page.locator('[data-experience-next]').click();page.locator('#goal-id').select_option('');page.locator('[data-experience-next]').click()


@pytest.mark.parametrize('kind,subtype',[('real',None),('fictional',None),('real','historical')])
def test_person_type_and_explicit_mention_source_do_not_create_interaction(page,kind,subtype):
    _,headers=seed(page)
    response=page.request.post(BASE+'/api/persons',headers=headers,data={'request_id':uuid4().hex,'name':'來源人物','person_type':kind,'person_subtype':subtype});assert response.ok,response.text();p=response.json()
    raw='只在日記提到來源人物。';record(page,raw)
    page.get_by_role('button',name='選擇既有人物',exact=True).click();page.locator('[data-workflow-pick="'+p['id']+'"]').click()
    row=page.locator('[data-workflow-person]').first
    expect(row.locator('[data-workflow-role]')).to_have_value('')
    if kind=='fictional' or subtype=='historical':
        expect(row.locator('[data-workflow-role] option[value=interaction]')).to_have_count(0)
        expect(row.locator('[data-workflow-role] option[value=participant]')).to_have_count(0)
    row.locator('[data-workflow-role]').select_option('mention')
    expect(row.locator('[data-workflow-start]')).to_have_value('')
    page.locator('[data-experience-review]').click();expect(page.locator('#notice')).to_contain_text('原文位置')
    assert not page.request.get(BASE+'/api/state').json()['drafts']
    row.locator('[data-workflow-start]').select_option(str(raw.index('來源人物')))
    page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible()
    page.locator('#story-reviewed').check();page.get_by_role('button',name='我已核對，確認保存',exact=True).click();expect(page.locator('#review-form')).to_have_count(0)
    overview=page.request.get(BASE+'/api/people/'+p['id']+'/overview').json();assert overview['stats']['interactions']==0
    state=page.request.get(BASE+'/api/state').json();assert len(state['experiences'])==len(state['rewards']['events'])==1


def test_incomplete_known_role_restores_locally_without_default_or_extra_card(page):
    p,_=seed(page);record(page,'尚未選完人物角色的記錄。')
    page.get_by_role('button',name='選擇既有人物',exact=True).click();page.locator('[data-workflow-pick="'+p['id']+'"]').click()
    key=page.locator('[data-workflow-person]').get_attribute('data-row-key')
    page.locator('#nav').get_by_role('link',name='世界',exact=True).click();page.get_by_role('button',name='保留此裝置草稿並離開',exact=True).click()
    expect(page.locator('#world-relationships')).to_be_visible()
    other=page.context.new_page()
    try:
        other.goto(BASE+'/#record');expect(other.locator('#raw-text')).to_have_value('尚未選完人物角色的記錄。')
        other.locator('[data-experience-next]').click();other.locator('[data-experience-next]').click()
        row=other.locator('[data-workflow-person]');expect(row).to_have_count(1);assert row.get_attribute('data-row-key')==key
        expect(row.locator('[data-workflow-role]')).to_have_value('')
        assert not other.request.get(BASE+'/api/state').json()['drafts']
    finally:other.close()


def test_existing_participation_and_same_person_mention_both_survive_edit(page):
    p,headers=seed(page);raw='人物小安來過，也提到人物小安。';pos=raw.rindex('人物小安')
    response=page.request.post(BASE+'/api/experiences/drafts',headers=headers,data={'raw_text':raw,'occurred_at':'2026-10-27T00:00:00Z','contributions':[],'story':{'participants':[{'person_id':p['id'],'interacted':True}],'mentions':[{'person_id':p['id'],'name':'人物小安','start':pos,'end':pos+4}]}});assert response.ok,response.text();d=response.json()
    page.goto(BASE+'/#review/'+d['id']);page.reload();page.get_by_role('button',name='返回修改原始草稿',exact=True).click();page.locator('[data-experience-next]').click();page.locator('[data-experience-next]').click()
    rows=page.locator('[data-workflow-person]');expect(rows).to_have_count(2)
    expect(rows.nth(0).locator('[data-workflow-role]')).to_have_value('interaction');expect(rows.nth(1).locator('[data-workflow-role]')).to_have_value('mention');expect(rows.nth(1).locator('[data-workflow-start]')).to_have_value(str(pos))
    page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible()
    read=page.request.get(BASE+'/api/drafts/'+d['id']).json()['story']
    assert read['participants']==d['story']['participants'] and read['mentions']==d['story']['mentions']


def test_picker_uses_only_current_session_owner_people(page):
    own,_=seed(page);context=page.context.browser.new_context();other=context.new_page()
    try:
        foreign,_=seed(other);record(page,'自己的記錄。');page.get_by_role('button',name='選擇既有人物',exact=True).click()
        expect(page.locator('[data-workflow-pick="'+own['id']+'"]')).to_have_count(1)
        expect(page.locator('[data-workflow-pick="'+foreign['id']+'"]')).to_have_count(0)
    finally:context.close()


@pytest.mark.parametrize('width',[320,390,1440])
def test_compact_picker_empty_search_keyboard_and_layout(page,width):
    from pathlib import Path
    page.set_viewport_size({'width':width,'height':950});p,_=seed(page);record(page,'人物選擇與鍵盤測試。')
    opener=page.get_by_role('button',name='選擇既有人物',exact=True);opener.focus();opener.press('Enter')
    search=page.locator('[data-workflow-search]');expect(search).to_be_focused()
    search.fill('不會存在的搜尋名字');expect(page.locator('[data-workflow-no-match]')).to_be_visible()
    search.fill(p['name']);expect(page.locator('[data-workflow-no-match]')).not_to_be_visible()
    page.locator('[data-workflow-pick="'+p['id']+'"]').press('Enter')
    role=page.locator('[data-workflow-role]');expect(role).to_be_focused();expect(role).to_have_value('')
    role.select_option('participant')
    expect(page.locator('[data-compact] .participant-options')).to_have_count(0)
    expect(page.locator('#story-title')).not_to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    art=Path(__file__).resolve().parents[1]/'docs/integration/2026-11-11/screenshots';art.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(art/f'{width}-compact-person-selection.png'),full_page=True)
    opener.click();page.get_by_role('button',name='關閉選擇',exact=True).press('Enter')
    expect(opener).to_be_focused();expect(page.locator('[data-workflow-picker]')).to_be_hidden()
    assert len(page.request.get(BASE+'/api/state').json()['people'])==1 and not page.request.get(BASE+'/api/state').json()['drafts']


def test_unmatched_name_requires_explicit_span_and_preserves_second_occurrence(page):
    _,headers=seed(page);raw='提到小安，後來又提到小安。';record(page,raw)
    page.locator('#include-story').check();page.locator('[data-workflow-extra] > summary').click()
    page.get_by_role('button',name='只記錄原文中的稱呼',exact=True).click()
    page.locator('[name=mention_name]').fill('小安');expect(page.locator('[name=mention_start]')).to_have_value('')
    page.locator('[data-experience-review]').click();expect(page.locator('#notice')).to_contain_text('原文稱呼與位置')
    assert not page.request.get(BASE+'/api/state').json()['drafts']
    page.locator('[name=mention_start]').select_option(str(raw.rindex('小安')))
    page.locator('[data-experience-review]').click();expect(page.locator('#review-form')).to_be_visible()
    d=page.request.get(BASE+'/api/state').json()['drafts'][0]
    assert d['story']['mentions']==[{'name':'小安','person_id':None,'start':raw.rindex('小安'),'end':raw.rindex('小安')+2}]
    assert len(page.request.get(BASE+'/api/state').json()['people'])==1
