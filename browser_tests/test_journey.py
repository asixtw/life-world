"""Actual Chromium journeys; run explicitly against an isolated local server."""
import base64
import os
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import sync_playwright, expect

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGNkaGBgYGBgYmBgYGBgAAAGKgCE5tEtPAAAAABJRU5ErkJggg==')
BASE = os.environ.get('LIFEWORLD_TEST_URL', 'http://127.0.0.1:8001')
ARTIFACTS = Path(__file__).resolve().parent.parent / 'docs' / 'artifacts'


@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1050}, locale='zh-TW')
        page = context.new_page()
        page.set_default_timeout(10000)
        yield page
        context.close()
        browser.close()


def create_goal(page, title):
    page.locator('#goal-title').fill(title)
    page.locator('#outcome').fill('完成一個自己的作品，並提供照片佐證。')
    for i, (action, unit) in enumerate([('練習', '小時'), ('記錄', '篇'), ('交流', '次')]):
        page.locator('#action-title-' + str(i)).fill(action)
        page.locator('#target-' + str(i)).fill('10')
        page.locator('#unit-' + str(i)).fill(unit)
    page.get_by_role('button', name='確認設定，建立目標蛋').click()


def onboarding(page):
    page.goto(BASE)
    expect(page.get_by_role('heading', name='把每一步，種成自己的世界。')).to_be_visible()
    expect(page.locator('.lumi')).to_have_count(0)
    page.get_by_role('button', name='不用註冊，先開始').click()
    page.locator('#profile-name').fill('測試小光')
    page.locator('#bio').fill('以真實的一小步，建立自己的世界。')
    page.get_by_role('button', name='接著，建立第一個目標').click()
    expect(page.locator('#goal-form')).to_be_visible()
    expect(page.locator('.lumi')).to_have_count(0)
    create_goal(page, '第一個作品')
    expect(page.get_by_role('heading', name='目標蛋誕生了。 你好，我是 Lumi。')).to_be_visible()
    page.get_by_role('link', name='進入我的世界').click()
    expect(page.get_by_role('heading', name='測試小光，歡迎回來。')).to_be_visible()


def test_complete_browser_journey_with_upgrade_preserves_selected_goal_and_contribution(page):
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    onboarding(page)
    page.locator('#nav').get_by_role('link', name='目標花園').click()
    page.get_by_role('link', name='新的目標').click()
    create_goal(page, '第二個作品')
    expect(page.get_by_role('heading', name='第二個作品')).to_be_visible()
    goals = page.request.get(BASE + '/api/state').json()['goals']
    goal = next(g for g in goals if g['title'] == '第二個作品')
    action_id = goal['actions'][0]['id']
    page.locator('#nav').get_by_role('link', name='記錄經歷').click()
    page.locator('#goal-id').select_option(goal['id'])
    page.locator('#raw-text').fill('這一份原文，需要在升級帳號後完整保留。')
    page.locator('#occurred-at').fill('2001-01-01T23:50')
    page.locator('#quantity-' + action_id).fill('0.25')
    page.get_by_role('button', name='新增人物').click()
    page.locator('#username').fill('browser_' + uuid4().hex[:12])
    page.locator('#password').fill('browser-test-password-2026')
    page.get_by_role('button', name='建立帳號，繼續原本的操作').click()
    expect(page.locator('#account-dialog')).not_to_be_visible()
    expect(page.locator('#raw-text')).to_have_value('這一份原文，需要在升級帳號後完整保留。')
    expect(page.locator('#occurred-at')).to_have_value('2001-01-01T23:50')
    expect(page.locator('#goal-id')).to_have_value(goal['id'])
    expect(page.locator('#quantity-' + action_id)).to_have_value('0.25')
    page.get_by_role('button', name='新增人物').click()
    page.locator('#person-name').fill('虛構的同行朋友')
    page.locator('#person-role').fill('一起創作')
    page.get_by_role('button', name='保存人物').click()
    expect(page.locator('#quantity-' + action_id)).to_have_value('0.25')
    page.get_by_role('button', name='保存草稿並進入核對').click()
    expect(page.locator('#review-form')).to_be_visible()
    page.locator('#summary').fill('由我確認的四分之一小時練習。')
    page.locator('#followups').fill('明天再練習')
    page.get_by_role('button', name='我已核對，確認保存').click()
    expect(page.get_by_text('由我確認的四分之一小時練習。', exact=True)).to_be_visible()
    world = page.request.get(BASE + '/api/state').json()
    assert world['rewards']['total'] == 1
    assert next(g for g in world['goals'] if g['id'] == goal['id'])['actions'][0]['progress'] == '0.25'
    assert world['experiences'][0]['person_id'] == world['people'][0]['id']
    page.locator('#nav').get_by_role('link', name='記錄經歷').click()
    expect(page.locator('#raw-text')).to_have_value('')
    page.locator('#nav').get_by_role('link', name='目標花園').click()
    page.locator('a[href="#goal/' + goal['id'] + '"]').click()
    expect(page.get_by_role('button', name='確認完成並收藏成果')).to_be_disabled()
    page.locator('#evidence-file').set_input_files({'name':'作品.png','mimeType':'image/png','buffer':PNG})
    page.get_by_role('button', name='上傳佐證').click()
    expect(page.locator('.photo-grid img')).to_have_count(1)
    page.locator('[name=confirmed]').check()
    page.locator('#reflection').fill('已達成自己的作品成果。')
    page.get_by_role('button', name='確認完成並收藏成果').click()
    expect(page.get_by_role('heading', name='這段成果，已經收藏。')).to_be_visible()
    page.locator('#nav').get_by_role('link', name='私人小劇場').click()
    page.locator('#note-kind').select_option('simulation')
    page.locator('#note-title').fill('下一次見面的練習')
    page.locator('#note-content').fill('這是模擬，不是真人發言。')
    page.get_by_role('button', name='保存私人筆記').click()
    expect(page.get_by_role('heading', name='下一次見面的練習')).to_be_visible()
    assert page.request.get(BASE + '/api/state').json()['rewards']['total'] == 1
    page.locator('#nav').get_by_role('link', name='我的世界').click()
    expect(page.get_by_role('heading', name='測試小光，歡迎回來。')).to_be_visible()
    expect(page.locator('#toast')).not_to_have_class('visible')
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / 'desktop-world.png'), full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    expect(page.get_by_role('heading', name='測試小光，歡迎回來。')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(ARTIFACTS / 'mobile-world.png'), full_page=True)
    assert errors == []


def test_saved_draft_survives_refresh_and_logout_login(page):
    onboarding(page)
    page.locator('#nav').get_by_role('link', name='記錄經歷').click()
    page.locator('#raw-text').fill('先保存，稍後再確認。')
    page.get_by_role('button', name='先存草稿').click()
    expect(page.get_by_role('link', name='繼續核對')).to_be_visible()
    page.reload()
    expect(page.get_by_role('link', name='繼續核對')).to_be_visible()
    page.locator('#account-button').click()
    page.get_by_role('button', name='建立帳號，保存世界').click()
    username = 'return_' + uuid4().hex[:12]
    page.locator('#username').fill(username)
    page.locator('#password').fill('return-password-2026')
    page.get_by_role('button', name='建立帳號，繼續原本的操作').click()
    expect(page.locator('#account-dialog')).not_to_be_visible()
    page.locator('#account-button').click()
    page.get_by_role('button', name='登出', exact=True).click()
    expect(page.get_by_role('button', name='登入我的世界')).to_be_visible()
    page.get_by_role('button', name='登入我的世界').click()
    page.locator('#username').fill(username)
    page.locator('#password').fill('return-password-2026')
    page.locator('#login-form').get_by_role('button', name='登入我的世界', exact=True).click()
    expect(page.get_by_role('heading', name='測試小光，歡迎回來。')).to_be_visible()
    page.locator('#nav').get_by_role('link', name='經歷收藏').click()
    page.get_by_role('link', name='繼續核對').click()
    expect(page.locator('.raw-source')).to_have_text('先保存，稍後再確認。')
    assert page.request.get(BASE + '/api/state').json()['rewards']['total'] == 0


def test_unsaved_record_can_be_saved_before_navigation(page):
    onboarding(page)
    page.locator('#nav').get_by_role('link', name='記錄經歷').click()
    page.locator('#raw-text').fill('導覽離開前，這段原文需要先保存。')
    page.locator('#nav').get_by_role('link', name='目標花園').click()
    expect(page.get_by_role('heading', name='離開前，留住這段內容。')).to_be_visible()
    page.get_by_role('button', name='先存草稿並離開').click()
    expect(page.get_by_role('heading', name='照顧你的目標花園。')).to_be_visible()
    page.locator('#nav').get_by_role('link', name='經歷收藏').click()
    page.get_by_role('link', name='繼續核對').click()
    expect(page.locator('.raw-source')).to_have_text('導覽離開前，這段原文需要先保存。')
