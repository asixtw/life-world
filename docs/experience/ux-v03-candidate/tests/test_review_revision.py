"""Owner 五項修正的設計回歸，不代表產品/API驗收。"""
import pytest
from playwright.sync_api import expect
from test_candidate import page, scene


def test_raw_change_marks_summary_without_losing_manual_text(page):
    scene(page,'step4')
    page.locator('#summary').fill('我親自整理的摘要。')
    page.locator('[data-action=edit][data-step="2"]').click()
    page.locator('[data-action=back]').click()
    page.locator('#raw-text').fill('來源已改為另一段真實經歷。')
    assert page.evaluate('UX.getState().summaryNeedsReview') is True
    assert page.evaluate('UX.getState().summary')=='我親自整理的摘要。'


def test_person_sheet_has_separate_scroll_and_fixed_actions(page):
    scene(page,'newPreview')
    assert page.locator('#sheet .sheet-body').count()==1
    assert page.locator('#sheet .sheet-footer [data-action=close]').count()==1
    expect(page.locator('#will-save')).to_contain_text('確認後會保存')
    expect(page.locator('#not-saving')).to_contain_text('此次完成後不會保留到人物檔案')


def test_mobile_focus_hides_nav_and_restores_after_leave(page):
    page.set_viewport_size({'width':390,'height':844})
    scene(page,'step1')
    assert not page.locator('.sidebar').is_visible()
    page.locator('#main [data-action=leave]').click()
    page.locator('[data-action=discard]').click()
    expect(page.locator('.sidebar')).to_be_visible()


def test_ai_has_one_explicit_choice_default_manual(page):
    scene(page,'step1')
    assert page.locator('[name=organize-mode]').count()==2
    expect(page.locator('[name=organize-mode][value=manual]')).to_be_checked()
    assert page.locator('#ai-toggle,#ai-consent').count()==0


def test_summary_recheck_blocks_confirmation_and_preserves_text(page):
    scene(page,'step4')
    page.locator('#summary').fill('手動編輯過，必須保留的摘要。')
    page.locator('[data-action=edit][data-step="2"]').click()
    page.locator('[data-action=back]').click()
    page.locator('#raw-text').fill('完全不同的原文，改為獨自散步。')
    for _ in range(3):page.locator('[data-action=next]').click()
    expect(page.locator('#summary')).to_have_value('手動編輯過，必須保留的摘要。')
    expect(page.locator('#summary-review-notice')).to_contain_text('來源已修改')
    page.locator('[data-action=confirm]').click()
    expect(page.locator('#flow-error')).to_contain_text('重新核對摘要')
    page.locator('[data-action=review-summary]').click()
    assert not page.evaluate('UX.getState().summaryNeedsReview')
    page.locator('[data-action=confirm]').click()
    expect(page.locator('.success-panel')).to_be_visible()


def test_unchanged_source_and_unrelated_manual_information(page):
    scene(page,'multiUpdates')
    for name in ['怡君','小安']:
        page.get_by_role('button',name='查看'+name+'本次變更').click()
        page.locator('[data-change]').check()
        page.get_by_role('button',name='關閉預覽',exact=True).click()
    page.locator('[data-action=edit][data-step="2"]').click()
    page.locator('[data-action=back]').click()
    original=page.locator('#raw-text').input_value()
    # 未改原文的返回，不取消摘要或任何人的核對。
    for _ in range(3):page.locator('[data-action=next]').click()
    state=page.evaluate('UX.getState()')
    assert not state['summaryNeedsReview'] and all(p['changes'][0]['accepted'] for p in state['people'][:2])
    page.locator('[data-action=edit][data-step="2"]').click()
    page.locator('[data-action=back]').click()
    page.locator('#raw-text').fill(original.replace('開始學攝影','改練習水彩'))
    state=page.evaluate('UX.getState()')
    assert state['summaryNeedsReview']
    assert not state['people'][0]['changes'][0]['accepted']
    assert state['people'][0]['changes'][0]['needsReview']
    assert state['people'][1]['changes'][0]['accepted']


def test_ai_first_authorization_reuse_manual_and_failure(page):
    scene(page,'step1')
    assert page.evaluate('UX.getState().aiPreviewRequests')==0
    page.locator('[name=organize-mode][value=ai]').check()
    expect(page.locator('#sheet')).to_contain_text('Google Gemini')
    expect(page.locator('#sheet')).to_contain_text('未確認草稿的文字原文')
    assert page.evaluate('UX.getState().aiPreviewRequests')==0
    page.locator('[data-action=cancel-ai]').click()
    expect(page.locator('[name=organize-mode][value=manual]')).to_be_checked()
    page.locator('[name=organize-mode][value=ai]').check()
    page.locator('[data-action=approve-ai]').click()
    page.wait_for_function("UX.getState().aiState==='candidate'")
    assert page.evaluate('UX.getState().aiPreviewRequests')==1
    page.locator('[name=organize-mode][value=manual]').check()
    page.locator('[name=organize-mode][value=ai]').check()
    expect(page.locator('#sheet')).not_to_be_visible()
    page.wait_for_function("UX.getState().aiPreviewRequests===2&&UX.getState().aiState==='candidate'")
    page.locator('#review-tools>summary').click()
    page.locator('#ai-outcome').select_option('failure')
    original=page.locator('#raw-text').input_value()
    page.locator('[data-action=run-ai]').click()
    expect(page.locator('#ai-error')).to_be_visible()
    expect(page.locator('#raw-text')).to_have_value(original)
    page.locator('[data-action=manual-mode]').click()
    expect(page.locator('[name=organize-mode][value=manual]')).to_be_checked()


def test_ai_reply_cannot_overwrite_changed_source(page):
    scene(page,'aiAuthorized')
    page.locator('[data-action=run-ai]').click()
    page.locator('#raw-text').fill('等待時改了原文，舊候選不得套入。')
    page.wait_for_function("UX.getState().aiState==='stale'")
    assert page.evaluate('UX.getState().summary')==''


@pytest.mark.parametrize('presentation',['normal','large-text','zoom','short-viewport'])
def test_sheet_small_screen_large_text_zoom_and_scroll(page,presentation):
    from test_candidate import ROOT
    width=320 if page.viewport_size['width']==1440 else 390
    page.set_viewport_size({'width':width,'height':(380 if presentation=='short-viewport' else 568 if width==320 else 844)})
    scene(page,'newPreview')
    if presentation=='large-text':
        page.add_style_tag(content='.sheet-body,.sheet-body p,.sheet-body strong,.sheet-body .small,.sheet-body .badge,.sheet-footer button{font-size:22px!important;line-height:1.6!important}')
    if presentation=='zoom':
        client=page.context.new_cdp_session(page)
        client.send('Emulation.setPageScaleFactor',{'pageScaleFactor':1.5})
        page.wait_for_function('visualViewport.scale>1.4')
    page.wait_for_function("parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--usable-width'))<=visualViewport.width+1")
    geometry=page.evaluate("""()=>{const b=n=>{const r=document.querySelector(n).getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right}};return {head:b('.sheet-head'),foot:b('.sheet-footer'),body:b('.sheet-body'),v:{top:visualViewport.offsetTop,bottom:visualViewport.offsetTop+visualViewport.height,left:visualViewport.offsetLeft,right:visualViewport.offsetLeft+visualViewport.width}}}""")
    assert geometry['head']['top']>=geometry['v']['top']-2
    assert geometry['foot']['bottom']<=geometry['v']['bottom']+2
    assert geometry['foot']['left']>=geometry['v']['left']-2
    assert geometry['foot']['right']<=geometry['v']['right']+2
    before=page.locator('.sheet-footer').bounding_box()
    page.locator('.sheet-body').evaluate('(n)=>n.scrollTop=n.scrollHeight')
    after=page.locator('.sheet-footer').bounding_box()
    assert abs(before['y']-after['y'])<1
    expect(page.locator('.sheet-footer [data-action=close]')).to_be_visible()
    assert page.locator('#will-save').get_by_text('公司',exact=True).count()==0
    folder=ROOT/'screenshots-r2'/str(width);folder.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(folder/('preview-'+presentation+'.png')),full_page=False)
    page.locator('.sheet-body').focus()
    page.keyboard.press('Tab')
    assert page.evaluate("document.querySelector('#sheet').contains(document.activeElement)")
    page.locator('.sheet-footer [data-action=close]').click()
    expect(page.locator('#sheet')).not_to_be_visible()


def test_ai_summary_is_not_relabelled_as_fresh_after_raw_edit(page):
    scene(page,'aiCandidate')
    previous=page.locator('#summary').input_value()
    page.locator('[data-action=edit][data-step="2"]').click()
    page.locator('[data-action=back]').click()
    page.locator('#raw-text').fill('改成新的來源，原先的AI候選沒有重新生成。')
    for _ in range(3):page.locator('[data-action=next]').click()
    expect(page.locator('#summary')).to_have_value(previous)
    expect(page.locator('#summary-origin')).to_contain_text('來源已修改')
    assert page.evaluate('UX.getState().aiPreviewRequests')==0
    page.locator('[data-action=review-summary]').click()
    expect(page.locator('#summary-origin')).to_contain_text('已人工重核對')


def test_manual_path_never_requests_ai_preview(page):
    scene(page,'step1')
    for _ in range(3):page.locator('[data-action=next]').click()
    assert page.evaluate('UX.getState().aiPreviewRequests')==0
    assert not page.evaluate('UX.getState().aiCandidate')
    expect(page.locator('#sheet')).not_to_be_visible()


def test_save_leave_resume_and_discard_have_distinct_state(page):
    scene(page,'step4')
    page.locator('#summary').fill('保存前手動摘要，不能丟失。')
    page.locator('[data-action=edit][data-step="2"]').click()
    page.locator('[data-action=back]').click()
    page.locator('#raw-text').fill('已保存草稿的新原文。')
    page.locator('#main [data-action=save-draft]').click()
    expect(page.locator('.sidebar')).to_be_visible()
    assert page.evaluate('UX.getState().drafts.length')==3
    page.locator('[data-action=resume]').first.click()
    expect(page.locator('#raw-text')).to_have_value('已保存草稿的新原文。')
    for _ in range(3):page.locator('[data-action=next]').click()
    expect(page.locator('#summary')).to_have_value('保存前手動摘要，不能丟失。')
    expect(page.locator('#summary-review-notice')).to_be_visible()
    page.locator('[data-action=edit][data-step="2"]').click()
    page.locator('[data-action=back]').click()
    page.locator('#raw-text').fill('這些修改尚未保存，接著要捨棄。')
    page.locator('#main [data-action=leave]').click()
    page.locator('[data-action=discard]').click()
    assert page.evaluate('UX.getState().drafts.length')==3
    page.locator('[data-action=resume]').first.click()
    expect(page.locator('#raw-text')).to_have_value('已保存草稿的新原文。')
