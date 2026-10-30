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


@pytest.mark.parametrize('width', [390, 1440])
def test_beta_memorial_preserves_people_sources_and_has_no_reward(page, wireframe_url, width, tmp_path):
    """紀念品僅呈現摘要；結束目標不能清除人物及原始經歷。"""
    page.set_viewport_size({'width': width, 'height': 844})
    page.goto(wireframe_url)
    page.get_by_role('button', name='載入虛構示例', exact=True).click()
    page.get_by_role('button', name='記錄新經歷', exact=True).click()
    page.get_by_label('今天發生了什麼？').fill('與阿哲討論作品的真實投入。')
    page.get_by_label('稍後核對人物參與及資訊').check()
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
    page.get_by_label('稍後核對人物參與及資訊').check()
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
