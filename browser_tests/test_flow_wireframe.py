"""完整流程原型只處理本機虛構狀態，不連正式 API。"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import os
import pytest
from playwright.sync_api import expect
from test_journey import page


@pytest.fixture
def wireframe_url():
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(Path('collaboration/flow-wireframe').resolve())))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield 'http://127.0.0.1:' + str(server.server_port)
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.mark.parametrize('width', [390, 1440])
def test_full_wireframe_goal_record_people_and_night(page, wireframe_url, width, tmp_path):
    page.set_viewport_size({'width': width, 'height': 844 if width == 390 else 1050})
    errors, api_calls = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda r: api_calls.append(r.url) if '/api/' in r.url else None)
    page.goto(wireframe_url)
    expect(page.get_by_text('獨立互動原型', exact=False).first).to_be_visible()
    page.get_by_label('你的稱呼').fill('原型測試者')
    page.get_by_role('button', name='開始設定目標', exact=True).click()
    page.get_by_label('目標名稱', exact=True).fill('做出一份作品')
    page.get_by_role('button', name='下一步', exact=True).click()
    page.get_by_label('達成的樣子').fill('完成一份可分享的作品')
    page.get_by_label('截止日', exact=True).fill('2027-01-31')
    page.get_by_role('button', name='下一步', exact=True).click()
    for name in ['閱讀', '整理', '分享']:
        page.get_by_label('習慣名稱', exact=True).fill(name)
        page.get_by_role('button', name='平日', exact=True).click()
        page.get_by_role('button', name='下一步', exact=True).click()
    page.get_by_role('button', name='確認開始挑戰', exact=True).click()
    page.get_by_role('button', name='進入我的世界', exact=True).click()
    artifacts = Path(os.environ.get('LIFEWORLD_NEW_ARTIFACTS', str(tmp_path)))
    artifacts.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(artifacts / ('wireframe-world-' + str(width) + '.png')), full_page=True)
    page.get_by_role('button', name='記錄新經歷', exact=True).click()
    page.get_by_label('實際發生的時間').fill('2026-10-28T21:15')
    page.get_by_label('今天發生了什麼？').fill('與阿哲、小安討論作品，閱讀了三十分鐘。')
    page.get_by_role('button', name='錄音', exact=True).click()
    page.get_by_role('button', name='開始模擬錄音', exact=True).click()
    page.get_by_role('button', name='停止', exact=True).click()
    page.get_by_role('button', name='模擬試聽', exact=True).click()
    page.get_by_role('button', name='模擬辨識失敗', exact=True).click()
    expect(page.get_by_label('今天發生了什麼？')).to_have_value('與阿哲、小安討論作品，閱讀了三十分鐘。')
    page.get_by_role('button', name='手動整理', exact=True).click()
    page.get_by_label('確認經歷內容正確').check()
    page.get_by_role('button', name='確認保存', exact=True).click()
    expect(page.get_by_role('heading', name='這段經歷已留下')).to_be_visible()
    page.get_by_role('button', name='回到世界', exact=True).click()
    page.get_by_role('button', name='關係', exact=True).click()
    page.get_by_role('button', name='收藏冊', exact=True).click()
    page.get_by_role('button', name='查看阿哲', exact=True).click()
    page.get_by_role('button', name='☆ 加入星標', exact=True).click()
    expect(page.get_by_role('button', name='★ 已加星標', exact=True)).to_have_attribute('aria-pressed', 'true')
    page.get_by_role('button', name='★ 已加星標', exact=True).click()
    expect(page.get_by_role('button', name='☆ 加入星標', exact=True)).to_have_attribute('aria-pressed', 'false')
    page.get_by_role('button', name='查看人物卡', exact=True).click()
    page.get_by_role('button', name='飲食偏好', exact=True).click()
    page.get_by_role('button', name='查看來源', exact=True).click()
    expect(page.get_by_role('dialog')).to_contain_text('虛構示例')
    page.get_by_role('button', name='關閉來源', exact=True).click()
    page.get_by_role('button', name='開啟小劇場', exact=True).click()
    page.get_by_role('button', name='情境演練', exact=True).click()
    page.get_by_label('私人筆記').fill('練習如何邀請對方看作品。')
    page.get_by_role('button', name='保存私人筆記', exact=True).click()
    expect(page.get_by_role('status')).to_contain_text('不改人物事實、進度或積分')
    page.get_by_role('button', name='返回人物卡', exact=True).click()
    page.get_by_role('button', name='探索相關故事', exact=True).click()
    page.locator('.story').evaluate('el => Promise.all(el.getAnimations().map(a => a.finished))')
    page.screenshot(path=str(artifacts / ('wireframe-connections-' + str(width) + '.png')), full_page=True)
    page.get_by_role('button', name='探索小安', exact=True).click()
    expect(page.get_by_text('正在探索：小安', exact=True)).to_be_visible()
    page.get_by_role('button', name='上一段探索', exact=True).click()
    expect(page.get_by_text('正在探索：阿哲', exact=True)).to_be_visible()
    page.get_by_role('button', name='夜間設定', exact=True).click()
    page.get_by_label('示範當地時間').fill('2026-10-29T23:40')
    page.get_by_role('button', name='套用示範時間', exact=True).click()
    page.get_by_role('button', name='同意夜間自動切換', exact=True).click()
    expect(page.locator('body')).to_have_class('quiet')
    page.get_by_role('button', name='世界', exact=True).click()
    page.get_by_role('button', name='記錄新經歷', exact=True).click()
    page.get_by_label('今天發生了什麼？').fill('夜間先留下一段草稿。')
    page.get_by_role('button', name='先存草稿，明天再整理', exact=True).click()
    page.reload()
    page.get_by_role('button', name='繼續草稿', exact=True).click()
    expect(page.get_by_label('今天發生了什麼？')).to_have_value('夜間先留下一段草稿。')
    artifacts = Path(os.environ.get('LIFEWORLD_NEW_ARTIFACTS', str(tmp_path)))
    artifacts.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(artifacts / ('wireframe-night-' + str(width) + '.png')), full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert api_calls == [] and errors == []


def test_business_card_is_not_an_experience_or_reward(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='記錄新經歷', exact=True).click()
    page.get_by_role('button', name='名片', exact=True).click()
    page.get_by_role('button', name='填入虛構名片示例', exact=True).click()
    page.get_by_role('button', name='整理為草稿', exact=True).click()
    page.get_by_label('人物稱呼').fill('虛構名片人物')
    page.get_by_label('確認人物資訊與來源').check()
    page.get_by_role('button', name='只保存人物資料', exact=True).click()
    expect(page.get_by_role('status')).to_contain_text('沒有新增見面、經歷或獎勵')


def test_monthly_nth_weekday_schedule_spans_months_and_preserves_exact_dates(page, wireframe_url):
    """月週期需能設定每月第二、四個週日，跨月套用且不誤判為完成。"""
    page.goto(wireframe_url)
    page.get_by_label('你的稱呼').fill('月排程測試者')
    page.get_by_role('button', name='開始設定目標', exact=True).click()
    # 固定原型時鐘，避免測試依執行當日而改變可安排的日期。
    page.evaluate("""() => {
        const key = 'lifeworld:flow-wireframe:v1';
        const state = JSON.parse(localStorage.getItem(key));
        state.demoTime = '2026-10-30T12:00';
        localStorage.setItem(key, JSON.stringify(state));
    }""")
    page.reload()
    page.get_by_label('目標名稱', exact=True).fill('每月回顧')
    page.get_by_role('button', name='下一步', exact=True).click()
    page.get_by_label('達成的樣子').fill('固定回顧作品')
    page.get_by_label('截止日', exact=True).fill('2027-01-31')
    page.get_by_role('button', name='下一步', exact=True).click()
    page.get_by_label('習慣名稱', exact=True).fill('整理作品')
    page.get_by_role('button', name='每月固定', exact=True).click()
    page.get_by_role('button', name='第 2 週，週日', exact=True).click()
    page.get_by_role('button', name='第 4 週，週日', exact=True).click()
    page.get_by_role('button', name='套用每月規律', exact=True).click()
    state = page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).wizard.actions[0]")
    assert state['dates'] == ['2026-11-08', '2026-11-22', '2026-12-13', '2026-12-27', '2027-01-10', '2027-01-24']
    expect(page.locator('#wizard')).to_contain_text('每月第 2、4 個週日')
    expect(page.locator('#wizard')).to_contain_text('已安排')


@pytest.mark.parametrize('width', [390, 1440])
def test_world_uses_reusable_art_in_day_and_quiet(page, wireframe_url, width):
    """世界頁應實際載入房間、Lumi 與目標蛋；Quiet 切換不破圖。"""
    page.set_viewport_size({'width': width, 'height': 844})
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    for alt in ['日間房間', '日間的 Lumi', '目前目標蛋']:
        image = page.get_by_role('img', name=alt, exact=True)
        expect(image).to_be_visible()
        page.wait_for_function('(name) => [...document.images].some(img => img.alt === name && img.complete && img.naturalWidth > 0)', arg=alt)
    assert page.locator('nav .nav-icon').count() == 4
    page.wait_for_function('() => { const img=document.querySelector(".brand img"); return img && img.complete && img.naturalWidth > 0; }')
    page.get_by_role('button', name='夜間設定', exact=True).click()
    page.get_by_role('button', name='本次開啟安靜模式', exact=True).click()
    page.get_by_role('button', name='世界', exact=True).click()
    for alt in ['安靜房間', '安靜的 Lumi']:
        image = page.get_by_role('img', name=alt, exact=True)
        expect(image).to_be_visible()
        page.wait_for_function('(name) => [...document.images].some(img => img.alt === name && img.complete && img.naturalWidth > 0)', arg=alt)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


@pytest.mark.parametrize('width', [390, 1440])
def test_beta_memorial_preserves_people_sources_and_has_no_reward(page, wireframe_url, width, tmp_path):
    """紀念品僅呈現摘要；結束目標不能清除人物及原始經歷。"""
    page.set_viewport_size({'width': width, 'height': 844})
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='記錄新經歷', exact=True).click()
    page.get_by_label('今天發生了什麼？').fill('與阿哲討論作品的真實投入。')
    goal_id=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).goal.id")
    page.get_by_label('關聯目標',exact=True).select_option(goal_id)
    page.get_by_role('button', name='關聯已有人物', exact=True).click()
    page.get_by_role('button', name='選取阿哲', exact=True).click()
    page.get_by_role('button', name='整理為草稿', exact=True).click()
    page.get_by_label('確認經歷內容正確').check()
    page.get_by_label('確認關聯人物：阿哲（實際參與，非僅提及）').check()
    page.get_by_role('button', name='確認保存', exact=True).click()
    expect(page.locator('main')).not_to_contain_text('養分')
    page.get_by_role('button', name='回到世界', exact=True).click()
    expect(page.locator('main')).not_to_contain_text('養分')
    page.get_by_role('button', name='查看目前挑戰', exact=True).click()
    page.get_by_role('button', name='回顧這次挑戰', exact=True).click()
    page.get_by_label('回顧感想').fill('完成了第一輪練習，下一次繼續。')
    page.get_by_label('我已核對成果或結束選擇').check()
    page.get_by_role('button', name='結束這次挑戰', exact=True).click()
    page.get_by_role('button', name='查看旅程紀錄', exact=True).click()
    expect(page.get_by_role('heading', name='旅程紀錄', exact=True)).to_be_visible()
    expect(page.locator('main')).to_contain_text('完成了第一輪練習')
    expect(page.locator('main')).not_to_contain_text('與阿哲討論作品的真實投入。')
    artifacts = Path(os.environ.get('LIFEWORLD_NEW_ARTIFACTS', str(tmp_path)))
    artifacts.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(artifacts / f'beta-memorial-{width}.png'), full_page=True)
    page.get_by_role('button', name='查看相關人物：阿哲', exact=True).click()
    page.get_by_role('button', name='合作與目標', exact=True).click()
    expect(page.locator('main')).to_contain_text('已結束')
    page.reload()
    state = page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1'))")
    assert state['people'][0]['food'] == '不吃辣'
    assert state['records'][0]['summary'] == '與阿哲討論作品的真實投入。'
    assert state.get('points', 0) == 0
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


def test_beta_theater_demo_is_separate_and_media_gate_is_explicit(page, wireframe_url):
    """示範劇場不產生正式資料；服務未接不能冒充封測就緒。"""
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='人物劇場', exact=True).click()
    page.get_by_role('button', name='情境體驗（示範角色）', exact=True).click()
    page.get_by_role('button', name='三國策略', exact=True).click()
    page.get_by_role('button', name='開始腳本示範', exact=True).click()
    page.get_by_label('你的回應').fill('先確認各方希望保護什麼。')
    page.get_by_role('button', name='模擬對話失敗', exact=True).click()
    expect(page.get_by_label('你的回應')).to_have_value('先確認各方希望保護什麼。')
    page.reload()
    expect(page.get_by_label('你的回應')).to_have_value('先確認各方希望保護什麼。')
    page.get_by_role('button', name='送出模擬回應', exact=True).click()
    expect(page.locator('main')).to_contain_text('預寫示意')
    page.get_by_role('button', name='結束並回顧', exact=True).click()
    expect(page.locator('main')).to_contain_text('先確認各方希望保護什麼。')
    state = page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1'))")
    assert len(state['people']) == 3 and state['records'] == []
    page.get_by_role('button', name='紀錄', exact=True).click()
    page.get_by_role('button', name='記錄新經歷', exact=True).click()
    page.get_by_role('button', name='錄音', exact=True).click()
    expect(page.locator('main')).to_contain_text('封測必備：真實語音及圖片辨識')


def test_beta_story_text_is_not_rendered_as_html(page, wireframe_url):
    """新加入交會的經歷仍須當文字，不能執行內容中的 HTML。"""
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='記錄新經歷', exact=True).click()
    payload = '<img src=x onerror="window.injected=true">'
    page.get_by_label('今天發生了什麼？').fill(payload)
    page.get_by_role('button', name='關聯已有人物', exact=True).click()
    page.get_by_role('button', name='選取阿哲', exact=True).click()
    page.get_by_role('button', name='整理為草稿', exact=True).click()
    page.get_by_label('確認經歷內容正確').check()
    page.get_by_label('確認關聯人物：阿哲（實際參與，非僅提及）').check()
    page.get_by_role('button', name='確認保存', exact=True).click()
    page.get_by_role('button', name='回到世界', exact=True).click()
    page.get_by_role('button', name='探索交會', exact=True).click()
    page.get_by_role('button', name='查看另一段故事', exact=True).click()
    expect(page.locator('main')).to_contain_text(payload)
    page.get_by_role('button', name='查看人物卡', exact=True).click()
    page.get_by_role('button', name='共同經歷', exact=True).click()
    expect(page.locator('main')).to_contain_text(payload)
    assert page.evaluate('window.injected !== true')


@pytest.mark.parametrize('width', [390, 1440])
def test_multi_person_private_rehearsal_is_explicit_persistent_and_isolated(page, wireframe_url, width, tmp_path):
    """多人物由使用者明選；模擬往返不改人物、目標或真實經歷。"""
    page.set_viewport_size({'width':width, 'height':844})
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    before = page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1'))")
    page.get_by_role('button', name='人物劇場', exact=True).click()
    page.get_by_role('button', name='開始多人演練', exact=True).click()
    expect(page.get_by_role('status')).to_contain_text('至少選一位')
    page.get_by_label('加入阿哲', exact=True).check()
    page.get_by_label('加入怡君', exact=True).check()
    page.get_by_label('演練情境').fill('練習三人協調作品分工。')
    page.get_by_role('button', name='開始多人演練', exact=True).click()
    expect(page.get_by_role('heading', name='私人多人演練', exact=True)).to_be_visible()
    assert page.get_by_label('回應對象').locator('option').all_text_contents() == ['阿哲','怡君']
    page.get_by_label('回應對象').select_option('jun')
    page.get_by_label('你的演練發言').fill('怡君，你希望負責哪個部分？')
    page.get_by_role('button', name='模擬回應失敗', exact=True).click()
    page.reload()
    expect(page.get_by_label('你的演練發言')).to_have_value('怡君，你希望負責哪個部分？')
    page.get_by_role('button', name='送出演練發言', exact=True).click()
    expect(page.locator('[data-speaker="jun"]')).to_contain_text('預寫示意')
    expect(page.locator('[data-speaker="an"]')).to_have_count(0)
    page.get_by_role('button', name='結束演練並回顧', exact=True).click()
    expect(page.get_by_role('heading', name='私人演練回顧', exact=True)).to_be_visible()
    after = page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1'))")
    for key in ['people','records','goal','points']:
        assert before[key] == after[key], key
    artifacts = Path(os.environ.get('LIFEWORLD_NEW_ARTIFACTS', str(tmp_path)))
    artifacts.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(artifacts / f'multi-rehearsal-{width}.png'), full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


def test_multiple_demo_roles_can_join_without_creating_real_people(page, wireframe_url):
    """示範角色多人同場，但不進入真實人物庫。"""
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='人物劇場', exact=True).click()
    page.get_by_role('button', name='情境體驗（示範角色）', exact=True).click()
    page.get_by_label('加入劉備', exact=True).check()
    page.get_by_role('button', name='開始腳本示範', exact=True).click()
    page.get_by_label('選擇角色').select_option('1')
    page.get_by_label('你的回應').fill('我們如何合作？')
    page.get_by_role('button', name='送出模擬回應', exact=True).click()
    expect(page.locator('main')).to_contain_text('劉備')
    assert page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).people.length") == 3


def test_beta_login_errors_and_memorial_complete_are_explicit_simulations(page, wireframe_url):
    """登入線框不收真憑證；完成紀念及人物關聯不混成獎勵。"""
    from test_journey import PNG
    page.goto(wireframe_url)
    page.get_by_role('button', name='查看登入流程', exact=True).click()
    page.get_by_role('button', name='模擬登入失敗', exact=True).click()
    expect(page.get_by_role('status')).to_contain_text('登入未成功')
    page.get_by_role('button', name='帳號恢復', exact=True).click()
    expect(page.locator('main')).to_contain_text('一次性復原碼')
    page.get_by_role('button', name='返回登入', exact=True).click()
    page.get_by_role('button', name='模擬登入既有世界', exact=True).click()
    page.get_by_role('button', name='查看目前挑戰', exact=True).click()
    page.get_by_role('button', name='回顧這次挑戰', exact=True).click()
    page.get_by_label('成果佐證（原型僅預覽檔名）').set_input_files({'name':'demo.png','mimeType':'image/png','buffer':PNG})
    page.get_by_label('我已核對成果或結束選擇').check()
    page.get_by_role('button', name='確認完成成果', exact=True).click()
    page.get_by_role('button', name='查看完成紀念', exact=True).click()
    expect(page.get_by_role('heading', name='完成紀念', exact=True)).to_be_visible()
    expect(page.locator('main')).to_contain_text('尚無已確認人物')
    page.reload()
    expect(page.get_by_role('heading', name='完成紀念', exact=True)).to_be_visible()
    page.get_by_role('button', name='返回目標旅程', exact=True).click()
    expect(page.get_by_role('button', name='查看完成紀念', exact=True)).to_be_visible()


@pytest.mark.parametrize('width', [390, 1440])
def test_beta_screen_inventory_has_no_overflow_or_api_calls(page, wireframe_url, width, tmp_path):
    """靜態畫面盤點補充實際動線驗證，不冒充真實服務或實機測試。"""
    page.set_viewport_size({'width':width, 'height':844 if width==390 else 1050})
    errors, api_calls = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda r: api_calls.append(r.url) if '/api/' in r.url else None)
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    artifacts = Path(os.environ.get('LIFEWORLD_NEW_ARTIFACTS', str(tmp_path)))
    artifacts.mkdir(parents=True, exist_ok=True)
    for route in ['login','recovery','intro','wizard','world','goal','record','review',
                  'success','records','connections','cards','person','theater-hub',
                  'theater','demo-theater','goal-review','journey','settings']:
        page.evaluate('(route) => go(route)', route)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), route
        page.screenshot(path=str(artifacts / f'beta-{route}-{width}.png'), full_page=True)
    assert errors == [] and api_calls == []


def test_history_survives_next_challenge_and_cancelled_extension(page, wireframe_url):
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='查看目前挑戰', exact=True).click()
    page.get_by_role('button', name='回顧這次挑戰', exact=True).click()
    page.get_by_label('延長截止日').fill('2027-01-31')
    page.get_by_role('button', name='延長並檢視三習慣安排', exact=True).click()
    page.get_by_role('button', name='取消修改', exact=True).click()
    expect(page.get_by_text('2027-01-31', exact=False)).to_have_count(0)
    page.get_by_role('button', name='回顧這次挑戰', exact=True).click()
    page.get_by_label('我已核對成果或結束選擇').check()
    page.get_by_role('button', name='結束這次挑戰', exact=True).click()
    expect(page.get_by_role('heading', name='完成作品', exact=True)).to_be_visible()
    page.get_by_role('button', name='建立下一個目標', exact=True).click()
    page.get_by_role('button', name='稍後繼續', exact=True).click()
    page.get_by_role('button', name='目標', exact=True).click()
    page.get_by_role('button', name='目標旅程', exact=True).click()
    page.get_by_role('button', name='曾經挑戰', exact=True).click()
    expect(page.get_by_role('heading', name='完成作品', exact=True)).to_be_visible()


def test_image_preview_remove_and_quiet_opt_out(page, wireframe_url):
    import base64
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='記錄新經歷', exact=True).click()
    page.get_by_role('button', name='圖片', exact=True).click()
    page.locator('#file').set_input_files({'name':'fictional.png', 'mimeType':'image/png', 'buffer':base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGNkaGBgYGBgYmBgYGBgAAAGKgCE5tEtPAAAAABJRU5ErkJggg==')})
    expect(page.get_by_alt_text('本機附件預覽')).to_be_visible()
    page.get_by_role('button', name='移除附件', exact=True).click()
    expect(page.get_by_alt_text('本機附件預覽')).to_have_count(0)
    page.get_by_role('button', name='夜間設定', exact=True).click()
    page.get_by_label('示範當地時間').fill('2026-10-29T23:40')
    page.get_by_role('button', name='套用示範時間', exact=True).click()
    page.get_by_role('button', name='暫不啟用', exact=True).click()
    expect(page.locator('body')).not_to_have_class('quiet')
    page.reload()
    expect(page.get_by_role('button', name='同意夜間自動切換')).to_have_count(0)


def open_habit_calendar(page, url, deadline='2026-12-31'):
    """從建立流程進入日期編輯，固定示範時鐘以驗證跨月。"""
    page.goto(url)
    page.get_by_label('你的稱呼').fill('操作驗收者')
    page.get_by_role('button', name='開始設定目標', exact=True).click()
    page.evaluate("""() => {
        const key='lifeworld:flow-wireframe:v1';
        const state=JSON.parse(localStorage.getItem(key));
        state.demoTime='2026-10-30T12:00';
        localStorage.setItem(key, JSON.stringify(state));
    }""")
    page.reload()
    page.get_by_label('目標名稱', exact=True).fill('規律整理作品')
    page.get_by_role('button', name='下一步', exact=True).click()
    page.get_by_label('達成的樣子').fill('每月持續整理作品')
    page.get_by_label('截止日', exact=True).fill(deadline)
    page.get_by_role('button', name='下一步', exact=True).click()
    page.get_by_label('習慣名稱', exact=True).fill('整理作品')


@pytest.mark.parametrize('width', [390, 1440])
def test_schedule_modes_and_bottom_actions_have_clear_click_targets(page, wireframe_url, width):
    """建立頁的空導覽不能覆蓋日期或底部下一步，規律只展開選中的模式。"""
    page.set_viewport_size({'width': width, 'height': 844})
    open_habit_calendar(page, wireframe_url)
    expect(page.get_by_role('button', name='每月固定', exact=True)).to_be_visible()
    expect(page.get_by_role('group', name='每月固定日期規律')).not_to_be_visible()
    expect(page.locator('#nav')).not_to_be_visible()
    page.get_by_role('button', name='2026-10-30', exact=True).click()
    target=page.get_by_role('button', name='下一步', exact=True)
    target.scroll_into_view_if_needed()
    assert target.evaluate("el => {const r=el.getBoundingClientRect(); return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}")
    target.click()
    expect(page.get_by_role('heading', name='第二個重要習慣', exact=True)).to_be_visible()


def test_future_months_and_explicit_deadline_adjustment(page, wireframe_url):
    """期間內的後續月份可選；期間外需明示原因且可由使用者調整期限。"""
    open_habit_calendar(page, wireframe_url, deadline='2026-10-30')
    page.get_by_role('button', name='下一個月', exact=True).click()
    expect(page.get_by_role('button', name='2026-11-08', exact=True)).to_be_disabled()
    expect(page.locator('.schedule-period')).to_contain_text('2026-10-30')
    expect(page.locator('.calendar-notice')).to_contain_text('不在挑戰期間')
    page.get_by_role('button', name='調整截止日', exact=True).click()
    page.get_by_label('調整挑戰截止日', exact=True).fill('2026-12-31')
    page.get_by_role('button', name='確認截止日', exact=True).click()
    page.get_by_role('button', name='2026-11-08', exact=True).click()
    page.get_by_role('button', name='下一個月', exact=True).click()
    page.get_by_role('button', name='2026-12-13', exact=True).click()
    state=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).wizard")
    assert state['deadline']=='2026-12-31'
    assert state['actions'][0]['dates']==['2026-11-08','2026-12-13']
    page.reload()
    expect(page.get_by_role('button', name='2026-12-13', exact=True)).to_have_attribute('aria-pressed','true')


def test_click_hatch_skip_replay_and_leave_do_not_recreate_goal(page, wireframe_url):
    """首次建立可點蛋、跳過、重播；動畫不重建目標或發獎。"""
    open_habit_calendar(page, wireframe_url)
    for name in ['整理作品','閱讀','分享']:
        page.get_by_label('習慣名稱', exact=True).fill(name)
        page.get_by_role('button', name='平日', exact=True).click()
        page.get_by_role('button', name='下一步', exact=True).click()
    page.get_by_role('button', name='確認開始挑戰', exact=True).click()
    before=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1'))")
    egg=page.get_by_role('button', name='點擊目標蛋，喚醒 Lumi', exact=True)
    expect(egg).to_be_visible()
    egg.click()
    expect(page.locator('.hatch-stage')).to_have_attribute('data-stage','glow')
    page.get_by_role('button', name='跳過動畫', exact=True).click()
    expect(page.locator('.hatch-stage')).to_have_attribute('data-stage','complete')
    page.get_by_role('button', name='重播破蛋', exact=True).click()
    expect(page.locator('.hatch-stage')).to_have_attribute('data-stage','glow')
    page.get_by_role('button', name='進入我的世界', exact=True).click()
    page.wait_for_timeout(3500)
    expect(page.get_by_role('heading', name='你的世界，歡迎回來', exact=True)).to_be_visible()
    after=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1'))")
    assert after['goal']==before['goal'] and after['records']==[] and after['points']==0


def test_record_people_drafts_are_confirmed_individually_and_feed_connections(page, wireframe_url):
    """同一經歷可選舊人物、草擬新人物及標示提及，確認前不能建立人物。"""
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='記錄新經歷', exact=True).click()
    page.get_by_label('今天發生了什麼？').fill('與阿哲和小雨整理作品，談起怡君。')
    page.get_by_role('button', name='關聯已有人物', exact=True).click()
    page.get_by_role('button', name='選取阿哲', exact=True).click()
    page.get_by_role('button', name='關聯已有人物', exact=True).click()
    page.get_by_role('button', name='選取怡君', exact=True).click()
    page.get_by_label('怡君在這段經歷中的角色', exact=True).select_option('mentioned')
    page.get_by_role('button', name='新增人物', exact=True).click()
    page.get_by_label('新人物稱呼', exact=True).fill('小雨')
    page.get_by_label('與你的關係或角色', exact=True).fill('作品夥伴')
    page.get_by_role('button', name='加入本次人物草稿', exact=True).click()
    assert len(page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).people"))==3
    page.reload()
    expect(page.locator('.record-people')).to_contain_text('小雨')
    page.get_by_role('button', name='整理為草稿', exact=True).click()
    page.get_by_label('確認經歷內容正確').check()
    page.get_by_label('確認關聯人物：阿哲（實際參與，非僅提及）').check()
    page.get_by_label('確認關聯人物：怡君（僅被提及）').check()
    page.get_by_label('確認新增並關聯人物：小雨（實際參與）').check()
    page.get_by_role('button', name='確認保存', exact=True).click()
    state=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1'))")
    assert len(state['people'])==4
    links=state['records'][0]['peopleLinks']
    assert len(links)==3 and [x['name'] for x in links if x['relation']=='mentioned']==['怡君']
    page.get_by_role('button', name='回到世界', exact=True).click()
    page.get_by_role('button', name='探索交會', exact=True).click()
    page.get_by_role('button', name='查看另一段故事', exact=True).click()
    expect(page.get_by_role('button', name='探索小雨', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='探索怡君', exact=True)).to_have_count(0)
    assert state['points']==0


def create_first_goal_for_hatch(page, url):
    """完整建立第一個目標，讓孵化驗收使用真實原型操作。"""
    open_habit_calendar(page, url)
    for name in ['整理作品','閱讀','分享']:
        page.get_by_label('習慣名稱', exact=True).fill(name)
        page.get_by_role('button', name='平日', exact=True).click()
        page.get_by_role('button', name='下一步', exact=True).click()
    page.get_by_role('button', name='確認開始挑戰', exact=True).click()


def test_hatch_refresh_restarts_visual_only_and_animation_completes(page, wireframe_url):
    """重整中斷的孵化可重新點蛋，完整序列仍能到完成。"""
    create_first_goal_for_hatch(page, wireframe_url)
    before=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).goal.id")
    page.get_by_role('button', name='點擊目標蛋，喚醒 Lumi', exact=True).click()
    page.reload()
    page.get_by_role('button', name='點擊目標蛋，喚醒 Lumi', exact=True).click()
    expect(page.locator('.hatch-stage')).to_have_attribute('data-stage','complete',timeout=5000)
    assert page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).goal.id")==before


@pytest.mark.parametrize('preference', ['reduced-motion','quiet'])
def test_hatch_respects_static_preferences(page, wireframe_url, preference):
    """安靜與減少動效皆直接顯示結果，不強迫播放破蛋。"""
    create_first_goal_for_hatch(page, wireframe_url)
    if preference=='reduced-motion':
        page.emulate_media(reduced_motion='reduce')
    else:
        page.evaluate("""() => {const key='lifeworld:flow-wireframe:v1'; const state=JSON.parse(localStorage.getItem(key)); state.demoTime='2026-10-30T23:30'; state.night.choice=true;localStorage.setItem(key,JSON.stringify(state));}""")
        page.reload()
    page.get_by_role('button', name='點擊目標蛋，喚醒 Lumi', exact=True).click()
    expect(page.locator('.hatch-stage')).to_have_attribute('data-stage','complete')
    expect(page.get_by_role('button', name='跳過動畫', exact=True)).to_have_count(0)


def test_cancelled_and_unconfirmed_new_people_are_not_created(page, wireframe_url):
    """取消、刷新與存草稿保留輸入，但未勾選的人物不進收藏冊或交會。"""
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='記錄新經歷', exact=True).click()
    page.get_by_label('今天發生了什麼？').fill('今天整理作品。')
    page.get_by_role('button', name='新增人物', exact=True).click()
    page.get_by_label('新人物稱呼', exact=True).fill('未確認人物')
    page.get_by_role('button', name='取消新增', exact=True).click()
    assert len(page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).people"))==3
    page.get_by_role('button', name='新增人物', exact=True).click()
    expect(page.get_by_label('新人物稱呼', exact=True)).to_have_value('未確認人物')
    page.get_by_role('button', name='加入本次人物草稿', exact=True).click()
    page.get_by_role('button', name='先存草稿，明天再整理', exact=True).click()
    page.reload()
    page.get_by_role('button', name='繼續草稿', exact=True).click()
    page.get_by_role('button', name='整理為草稿', exact=True).click()
    page.get_by_label('確認經歷內容正確').check()
    page.get_by_role('button', name='確認保存', exact=True).click()
    state=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1'))")
    assert len(state['people'])==3 and state['records'][0]['peopleLinks']==[]
    assert state['records'][0]['person'] is False and state['points']==0


@pytest.mark.parametrize('width', [390, 1440])
def test_month_grid_independent_cells_repeat_by_calendar_month(page, wireframe_url, width):
    """7×4 各格獨立，不能把所選週次與星期做笛卡兒積。"""
    page.set_viewport_size({'width':width,'height':844})
    open_habit_calendar(page,wireframe_url)
    page.get_by_role('button',name='每月固定',exact=True).click()
    grid=page.get_by_role('group',name='每月四週安排')
    assert grid.locator('button[data-month-slot]').count()==28
    for name in ['第 1 週，週一','第 2 週，週四','第 4 週，週日']:
        grid.get_by_role('button',name=name,exact=True).click()
    expect(grid.get_by_role('button',name='第 1 週，週四',exact=True)).to_have_attribute('aria-pressed','false')
    page.get_by_label('每月重複這份安排',exact=True).check()
    page.get_by_role('button',name='套用每月規律',exact=True).click()
    state=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).wizard.actions[0]")
    assert state['dates']==['2026-11-02','2026-11-12','2026-11-22','2026-12-07','2026-12-10','2026-12-27']
    page.reload()
    expect(grid.get_by_role('button',name='第 2 週，週四',exact=True)).to_have_attribute('aria-pressed','true')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


def test_month_grid_can_apply_only_visible_month(page, wireframe_url):
    """關閉月循環只套用目前月份；保留其他月份已有的單日安排。"""
    open_habit_calendar(page,wireframe_url)
    page.get_by_role('button',name='2026-10-30',exact=True).click()
    page.get_by_role('button',name='下一個月',exact=True).click()
    page.get_by_role('button',name='每月固定',exact=True).click()
    page.get_by_role('button',name='第 2 週，週日',exact=True).click()
    page.get_by_label('每月重複這份安排',exact=True).uncheck()
    page.get_by_role('button',name='套用每月規律',exact=True).click()
    state=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).wizard.actions[0]")
    assert state['dates']==['2026-10-30','2026-11-08']
    assert state['monthlyRule']['repeat'] is False


def test_weekday_toggle_reflects_dates_and_refresh(page, wireframe_url):
    """星期快選與日曆共用狀態，按下反色，重整保留，取消清除同星期日期。"""
    open_habit_calendar(page,wireframe_url)
    page.get_by_role('button',name='每週固定',exact=True).click()
    day=page.get_by_role('button',name='每週三',exact=True)
    expect(day).to_have_attribute('aria-pressed','false')
    color_before=day.evaluate('el=>getComputedStyle(el).backgroundColor')
    day.click()
    expect(day).to_have_attribute('aria-pressed','true')
    assert day.evaluate('el=>getComputedStyle(el).backgroundColor')!=color_before
    page.reload()
    expect(day).to_have_attribute('aria-pressed','true')
    day.click()
    expect(day).to_have_attribute('aria-pressed','false')
    assert page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).wizard.actions[0].dates")==[]


def test_record_selects_actual_habit_and_stores_only_confirmed_contribution(page, wireframe_url):
    """選擇具體活動，校對可改選且清除舊確認，最後採計綁定正確識別碼。"""
    page.goto(wireframe_url)
    page.get_by_role('button',name='載入虛構示例',exact=True).click()
    page.get_by_role('button',name='記錄新經歷',exact=True).click()
    page.get_by_label('今天發生了什麼？').fill('今天整理作品並分享。')
    goal=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).goal")
    page.get_by_label('關聯目標',exact=True).select_option(goal['id'])
    page.get_by_label('關聯的習慣／活動任務',exact=True).select_option(label='整理')
    page.get_by_role('button',name='整理為草稿',exact=True).click()
    expect(page.get_by_label('確認「整理」的實際投入',exact=True)).not_to_be_checked()
    page.get_by_label('確認「整理」的實際投入',exact=True).check()
    page.get_by_label('關聯的習慣／活動任務',exact=True).select_option(label='分享')
    expect(page.get_by_label('確認「分享」的實際投入',exact=True)).not_to_be_checked()
    page.get_by_label('實際投入量',exact=True).fill('2')
    page.get_by_label('確認「分享」的實際投入',exact=True).check()
    page.get_by_label('確認經歷內容正確').check()
    page.get_by_role('button',name='確認保存',exact=True).click()
    state=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1'))")
    record=state['records'][0]
    assert record['goalId']==goal['id']
    assert record['actionId']==state['goal']['actions'][2]['id']
    assert record['contribution'] is True and record['quantity']=='2'
    assert state['points']==0


def test_unassociated_record_has_no_goal_and_out_of_period_cannot_contribute(page, wireframe_url):
    """未選目標不可暗中關聯；選了目標也不能把期間外日期直接採計。"""
    page.goto(wireframe_url)
    page.get_by_role('button',name='載入虛構示例',exact=True).click()
    page.get_by_role('button',name='記錄新經歷',exact=True).click()
    page.get_by_label('今天發生了什麼？').fill('與目標無關的紀錄。')
    page.get_by_role('button',name='整理為草稿',exact=True).click()
    page.get_by_label('確認經歷內容正確').check()
    page.get_by_role('button',name='確認保存',exact=True).click()
    record=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).records[0]")
    assert record['goalId'] is None and record['actionId'] is None and record['contribution'] is False
    page.get_by_role('button',name='查看紀錄',exact=True).click()
    page.get_by_role('button',name='記錄新經歷',exact=True).click()
    page.get_by_label('今天發生了什麼？').fill('2020 年的閱讀回憶。')
    page.get_by_label('實際發生的時間').fill('2020-01-02T12:00')
    goal=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).goal")
    page.get_by_label('關聯目標',exact=True).select_option(goal['id'])
    page.get_by_label('關聯的習慣／活動任務',exact=True).select_option(label='閱讀')
    page.get_by_role('button',name='整理為草稿',exact=True).click()
    expect(page.get_by_label('確認「閱讀」的實際投入',exact=True)).to_be_disabled()
    expect(page.locator('.contribution-notice')).to_contain_text('不在挑戰期間')
    page.get_by_label('確認經歷內容正確').check()
    page.get_by_role('button',name='確認保存',exact=True).click()
    record=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).records[1]")
    assert record['contribution'] is False and record['pending'] is False


def test_followup_task_can_be_selected_by_a_later_record(page, wireframe_url):
    """後續任務要有名稱與識別碼，下一次記錄可明確選取，建立本身不算投入。"""
    page.goto(wireframe_url)
    page.get_by_role('button',name='載入虛構示例',exact=True).click()
    page.get_by_role('button',name='記錄新經歷',exact=True).click()
    page.get_by_label('今天發生了什麼？').fill('整理作品，準備下次討論。')
    goal=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).goal")
    page.get_by_label('關聯目標',exact=True).select_option(goal['id'])
    page.get_by_label('關聯的習慣／活動任務',exact=True).select_option(label='整理')
    page.get_by_role('button',name='整理為草稿',exact=True).click()
    page.get_by_label('建立後續任務（選填）',exact=True).check()
    page.get_by_label('後續任務名稱',exact=True).fill('整理下次討論筆記')
    page.get_by_label('後續任務日期',exact=True).fill('2026-11-01')
    page.get_by_label('確認經歷內容正確').check()
    page.get_by_role('button',name='確認保存',exact=True).click()
    before=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1'))")
    assert before['records'][0]['contribution'] is False
    task=before['tasks'][0]
    assert task['title']=='整理下次討論筆記' and task['goalId']==goal['id']
    page.get_by_role('button',name='查看紀錄',exact=True).click()
    page.get_by_role('button',name='記錄新經歷',exact=True).click()
    page.get_by_label('今天發生了什麼？').fill('已整理好討論筆記。')
    page.get_by_label('關聯目標',exact=True).select_option(goal['id'])
    page.get_by_label('關聯的習慣／活動任務',exact=True).select_option(task['id'])
    page.reload()
    expect(page.get_by_label('關聯的習慣／活動任務',exact=True)).to_have_value(task['id'])
    page.get_by_role('button',name='整理為草稿',exact=True).click()
    page.get_by_label('確認「整理下次討論筆記」的實際投入',exact=True).check()
    page.get_by_label('確認經歷內容正確').check()
    page.get_by_role('button',name='確認保存',exact=True).click()
    after=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1'))")
    assert after['records'][1]['actionId']==task['id'] and after['records'][1]['activityType']=='task'
    assert after['points']==0


def test_expired_goal_contribution_stays_pending(page, wireframe_url):
    """逾期經歷可保留關聯與待處理投入，不能與期間內直接採計混淆。"""
    page.goto(wireframe_url)
    page.get_by_role('button',name='載入虛構示例',exact=True).click()
    page.evaluate("""() => {const key='lifeworld:flow-wireframe:v1';const state=JSON.parse(localStorage.getItem(key));state.demoTime='2026-10-30T12:00';state.goal.start='2026-10-01';state.goal.deadline='2026-10-29';localStorage.setItem(key,JSON.stringify(state));}""")
    page.reload()
    page.get_by_role('button',name='記錄新經歷',exact=True).click()
    page.get_by_label('今天發生了什麼？').fill('逾期後繼續分享作品。')
    goal=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).goal")
    page.get_by_label('關聯目標',exact=True).select_option(goal['id'])
    page.get_by_label('關聯的習慣／活動任務',exact=True).select_option(label='分享')
    page.get_by_role('button',name='整理為草稿',exact=True).click()
    expect(page.locator('.contribution-notice')).to_contain_text('待回顧')
    page.get_by_label('確認「分享」的實際投入',exact=True).check()
    page.get_by_label('確認經歷內容正確').check()
    page.get_by_role('button',name='確認保存',exact=True).click()
    record=page.evaluate("JSON.parse(localStorage.getItem('lifeworld:flow-wireframe:v1')).records[0]")
    assert record['contribution'] is False and record['pending'] is True
