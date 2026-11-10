"""只驗證設計 Demo 互動，不冒充產品 API／設計核准。"""
from pathlib import Path
import json
import pytest
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
SCENES=['summaryChanged','summaryReviewed','manualUnrelated','aiManual','aiConsentFirst','aiAuthorized','aiFailure','aiCandidate','guestAccount','guestStep3','upgradeConfirm','upgradeSuccess','oldWorldWarning','registeredAccount','authFailure','authCancelled','authUnavailable','authConflict','step1','media','empty','guest','aiOff','step2','goal','step3','existing','new','multiple','mention','step4','multiUpdates','newPreview','updatePreview','noChanges','source','saveFailure','saveSuccess','drafts','draftEmpty','deleteConfirm','deleteFailure','deleteConflict','deleteSuccess','leave']


@pytest.fixture(params=[390,1440])
def page(request):
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':request.param,'height':844 if request.param==390 else 1000},locale='zh-TW')
        page=context.new_page();errors=[];requests=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:requests.append(r.url) if '/api/' in r.url or r.url.startswith('https:') else None)
        yield page
        assert not errors,errors
        assert not requests,'Design Demo must not call APIs or external services'
        context.close();browser.close()


def scene(page,name):
    page.goto((ROOT/'index.html').as_uri()+'?scene='+name)
    expect(page.locator('#main')).not_to_be_empty()


def test_all_scenes_and_screenshots(page):
    width=page.viewport_size['width']
    page.set_viewport_size({'width':width,'height':844 if width==390 else 1000})
    folder=ROOT/'screenshots-r2'/str(width);folder.mkdir(parents=True,exist_ok=True)
    for name in SCENES:
        scene(page,name)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),name
        assert page.locator('.workspace #identity').count()==0
        assert page.locator('.workspace').get_by_role('tab',name='正式帳號').count()==0
        modal=page.locator('#sheet').is_visible()
        page.screenshot(path=str(folder/(name+'.png')),full_page=not modal)
        if modal and page.locator('#sheet .sheet-body').evaluate('(n)=>n.scrollHeight>n.clientHeight+2'):
            page.locator('#sheet .sheet-body').evaluate('(n)=>n.scrollTop=n.scrollHeight')
            page.screenshot(path=str(folder/(name+'-detail-bottom.png')),full_page=False)
        # 最後操作按鈕可捲到可視範圍，手機固定導覽不覆蓋可操作區。
        if not page.locator('#sheet').is_visible() and name.startswith('step'):
            button=page.locator('#main .actions .primary')
            button.scroll_into_view_if_needed()
            box=button.bounding_box()
            if width==390:
                assert not page.locator('.sidebar').is_visible()
                assert box['y']+box['height']<=page.viewport_size['height']+1


def test_four_steps_keep_data_and_no_person_write(page):
    scene(page,'empty')
    page.locator('[data-action=next]').click()
    expect(page.locator('#flow-error')).to_contain_text('請先輸入文字')
    page.locator('#raw-text').fill('與小林讀書，也提到怡君。')
    page.locator('[data-action=next]').click()
    page.locator('[name=goal-mode][value=goal]').check()
    page.locator('#q0').fill('1.5')
    page.locator('[data-action=next]').click()
    page.locator('[name=people-mode][value=some]').check()
    page.locator('[data-action=new-person]').click()
    page.locator('[data-action=add-person]').click()
    expect(page.locator('#person-error')).to_contain_text('請填寫稱呼')
    page.locator('#new-name').fill('小林')
    page.locator('[data-action=add-person]').click()
    page.locator('[data-role]').select_option('interaction')
    page.locator('[data-action=next]').click()
    expect(page.locator('#summary')).to_have_value('與小林讀書，也提到怡君。')
    expect(page.locator('.person-preview')).to_have_count(1)
    page.locator('.person-preview').click()
    expect(page.locator('#sheet')).to_contain_text('確認後會保存')
    expect(page.locator('#sheet')).not_to_contain_text('興趣與嗜好')
    page.locator('[data-action=preview-edit]').click()
    expect(page.locator('[data-role]')).to_have_value('interaction')
    page.locator('[data-action=back]').click()
    expect(page.locator('#q0')).to_have_value('1.5')
    page.locator('[data-action=back]').click()
    expect(page.locator('#raw-text')).to_have_value('與小林讀書，也提到怡君。')


def test_per_person_preview_cancel_source_failure(page):
    scene(page,'updatePreview')
    before=page.evaluate('UX.getState()')
    page.locator('[data-change]').check()
    state=page.evaluate('UX.getState()')
    assert state['people'][0]['changes'][0]['accepted']
    assert state['people'][0]['old']==before['people'][0]['old']
    page.locator('[data-action=source]').click()
    expect(page.locator('#sheet mark')).to_contain_text('怡君說最近開始學攝影')
    page.get_by_role('button',name='返回人物預覽',exact=True).click()
    page.locator('[data-action=reject-change]').click()
    assert not page.evaluate('UX.getState().people[0].changes[0].accepted')
    page.get_by_role('button',name='關閉預覽',exact=True).click()
    page.locator('#review-tools>summary').click()
    page.locator('#save-outcome').select_option('failure')
    page.locator('[data-action=confirm]').click()
    expect(page.locator('#flow-error')).to_contain_text('內容與勾選項目都保留')
    expect(page.locator('#summary')).not_to_be_empty()
    page.locator('#save-outcome').select_option('success')
    page.locator('[data-action=confirm]').click()
    expect(page.locator('.success-panel')).to_contain_text('沒有建立人物')


def test_multi_mentions_and_unsupported_fields(page):
    scene(page,'multiple')
    expect(page.locator('[data-role]')).to_have_count(3)
    page.locator('[data-action=next]').click()
    expect(page.locator('.person-preview')).to_have_count(3)
    for name in ['怡君','小安','阿哲']:
        page.get_by_role('button',name='查看'+name+'本次變更').click()
        expect(page.locator('#sheet-title')).to_contain_text(name)
        page.get_by_role('button',name='關閉預覽',exact=True).click()
    scene(page,'newPreview')
    expect(page.locator('#sheet')).to_contain_text('目前沒有正式保存契約')
    assert page.locator('[data-change]').count()==0
    scene(page,'mention')
    page.locator('[data-action=mention-source]').click()
    expect(page.locator('#sheet mark')).to_have_text('阿哲')
    page.locator('[data-action=accept-mention]').click()
    expect(page.locator('[data-action=mention-source]')).to_contain_text('已核對')


def test_draft_delete_failure_retry_cancel_and_empty(page):
    scene(page,'deleteFailure')
    before=page.evaluate('UX.getState().drafts.length')
    page.get_by_role('button',name='關閉預覽',exact=True).click()
    assert page.evaluate('UX.getState().drafts.length')==before
    page.locator('#review-tools>summary').click()
    page.locator('#delete-outcome').select_option('success')
    page.locator('[data-action=delete-draft]').first.click()
    page.locator('[data-action=delete-now]').click()
    expect(page.locator('#sheet')).not_to_be_visible()
    assert page.evaluate('UX.getState().drafts.length')==before-1
    expect(page.locator('.notice.success')).to_contain_text('示意清單移除')
    scene(page,'deleteConflict')
    conflict_before=page.evaluate('UX.getState().drafts[0].revision')
    page.locator('[data-action=reload-draft]').click()
    expect(page.locator('#sheet')).to_contain_text('已重新載入示意新版本')
    assert page.evaluate('UX.getState().drafts[0].revision')==conflict_before+1
    page.locator('[data-action=delete-now]').click()
    expect(page.locator('#sheet')).not_to_be_visible()
    assert page.evaluate('UX.getState().drafts.length')==1
    scene(page,'draftEmpty')
    expect(page.locator('#main')).to_contain_text('沒有尚未完成的草稿')
    page.locator('#main [data-action=fresh]').last.click()
    expect(page.locator('#raw-text')).to_have_value('')


def test_guest_tools_are_separate_and_keyboard(page):
    scene(page,'guest')
    assert page.locator('.input-tabs button').count()==1
    assert page.locator('#ai-toggle').count()==0
    assert page.locator('.workspace select#identity').count()==0
    page.locator('#raw-text').focus()
    page.keyboard.insert_text('自己的日記。')
    page.locator('[data-action=next]').click()
    page.locator('[data-action=next]').click()
    expect(page.locator('#main')).to_contain_text('本次不關聯人物')
    page.locator('[data-action=next]').click()
    expect(page.locator('.person-preview')).to_have_count(0)


def test_changes_are_scoped_to_each_person(page):
    scene(page,'multiUpdates')
    page.get_by_role('button',name='查看小安本次變更').click()
    page.locator('[data-change]').check()
    state=page.evaluate('UX.getState()')
    assert not state['people'][0]['changes'][0]['accepted']
    assert state['people'][1]['changes'][0]['accepted']
    page.get_by_role('button',name='關閉預覽',exact=True).click()
    page.get_by_role('button',name='查看怡君本次變更').click()
    expect(page.locator('[data-change]')).not_to_be_checked()
    expect(page.locator('#sheet')).not_to_contain_text('登山')
    page.keyboard.press('Escape')
    expect(page.locator('#sheet')).not_to_be_visible()


def test_guest_upgrade_unlocks_only_people_region(page):
    scene(page,'guestStep3')
    before=page.evaluate("""()=>{window.keptHeading=document.querySelector('#main h1');window.keptActions=document.querySelector('#main .actions');return UX.getState();}""")
    page.locator('#people-region [data-action=upgrade]').click()
    page.locator('[data-action=auth-demo]').click()
    expect(page.locator('#people-region [data-action=pick]')).to_be_visible()
    after=page.evaluate('UX.getState()')
    assert after['step']==3 and after['session']['ownerId']==before['session']['ownerId']
    assert after['raw']==before['raw'] and after['qty']==before['qty'] and after['photo']==before['photo'] and after['audio']==before['audio']
    assert page.evaluate("window.keptHeading===document.querySelector('#main h1')&&window.keptActions===document.querySelector('#main .actions')")
    assert after['session']['status']=='registered'
    assert page.locator('#account-region [data-action=upgrade]').count()==0
    page.locator('#people-region [data-action=new-person]').click()
    page.locator('#new-name').fill('新認識的小林')
    page.locator('[data-action=add-person]').click()
    page.locator('[data-role]').select_option('participant')
    page.locator('[data-action=next]').click()
    expect(page.locator('.person-preview')).to_contain_text('新認識的小林')
    page.locator('[data-action=confirm]').click()
    expect(page.locator('.success-panel')).to_be_visible()


@pytest.mark.parametrize('outcome',['failure','cancel','conflict'])
def test_upgrade_failure_or_cancel_preserves_guest(page,outcome):
    scene(page,'guestStep3')
    before=page.evaluate('UX.getState()')
    page.locator('#review-tools>summary').click()
    page.locator('#auth-outcome').select_option(outcome)
    page.locator('#people-region [data-action=upgrade]').click()
    page.locator('[data-action=auth-demo]').click()
    if outcome=='cancel':expect(page.locator('#sheet')).not_to_be_visible()
    else:expect(page.locator('#sheet .notice.error')).to_be_visible()
    after=page.evaluate('UX.getState()')
    assert after['session']==before['session'] and after['raw']==before['raw'] and after['qty']==before['qty'] and after['step']==3
    assert page.locator('#people-region [data-action=pick]').count()==0


def test_old_world_requires_consent_and_switches_owner(page):
    scene(page,'oldWorldWarning')
    before=page.evaluate('UX.getState()')
    page.locator('[data-action=auth-demo]').click()
    expect(page.locator('#sheet .notice.error')).to_contain_text('尚未開始驗證')
    assert page.evaluate('UX.getState().session.ownerId')==before['session']['ownerId']
    page.locator('#discard-consent').check()
    page.locator('[data-action=auth-demo]').click()
    expect(page.locator('#main')).to_contain_text('另一個 Owner 的世界')
    assert page.evaluate('UX.getState().session.ownerId')!=before['session']['ownerId']
    assert page.evaluate('UX.getState().raw')==''


def test_unavailable_account_capabilities_have_no_auth_action(page):
    scene(page,'authUnavailable')
    expect(page.locator('#account-region')).to_contain_text('保存服務暫不可用')
    assert page.locator('.workspace [data-action=upgrade]').count()==0
    page.locator('[data-action=account-menu]').click()
    assert page.locator('#sheet [data-action=auth-demo]').count()==0
    expect(page.locator('#sheet')).to_contain_text('沒有可用的驗證入口')
