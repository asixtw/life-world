"""在隔離帳號驗證真實 App 的素材流程；辨識回應明確使用測試替身。"""
from datetime import date, timedelta
from pathlib import Path
import os
import pytest
from playwright.sync_api import expect
from test_journey import BASE, PNG, page


def prepare(page):
    """以 API 準備虛構世界，測試集中於這次新增的操作。"""
    page.goto(BASE)
    me = page.request.post(BASE + '/api/auth/guest').json()
    headers = {'X-CSRF-Token': me['csrf_token']}
    page.request.put(BASE + '/api/profile', headers=headers,
                     data={'name': '素材驗收者', 'bio': '保留真實素材', 'timezone': 'Asia/Taipei'})
    today = date.fromisoformat(page.request.get(BASE + '/api/auth/me').json()['today'])
    result = page.request.post(BASE + '/api/goals', headers=headers, data={
        'request_id': 'media-goal', 'title': '素材測試目標', 'outcome': '完成一份作品',
        'deadline': (today + timedelta(days=40)).isoformat(),
        'actions': [{'title': name, 'dates': [today.isoformat()]} for name in ['閱讀', '整理', '分享']]})
    assert result.status == 201
    # 辨識只供已註冊帳號；測試密碼執行期產生，不落盤。
    import secrets
    claimed=page.request.post(BASE+'/api/auth/claim',headers=headers,data={'username':'media_'+secrets.token_hex(6),'password':secrets.token_urlsafe(24)})
    assert claimed.status==200
    page.goto(BASE + '/#record')
    page.reload()  # API 準備後重新載入身分，避免只改 hash 沿用匿名頁面的記憶體狀態。
    expect(page.locator('#record-form')).to_be_visible()


def choose_image(page, kind='image'):
    page.get_by_role('tab',name='拍照／影像',exact=True).click()
    page.locator('[data-media-file="' + ('image' if kind in ('card','screenshot') else kind) + '"]').set_input_files(
        {'name': '虛構測試.png', 'mimeType': 'image/png', 'buffer': PNG})
    expect(page.get_by_text('虛構測試.png', exact=True)).to_be_visible()
    if kind=='card':
        page.locator('[data-media-purpose] > summary').click()
        page.locator('[data-media-card-purpose]').check()
    expect(page.locator('#media-storage')).to_contain_text('已保存在此裝置')


def save_for_review(page):
    # 真正經過四步，不能繼續點已移除的舊單頁保存鈕。
    page.locator('[data-experience-next]').click()
    page.locator('[data-experience-next]').click()
    page.locator('[data-experience-review]').click()


def reveal_photo(page):
    if page.locator('#review-form').count():
        page.locator('[data-review-raw] > summary').click()
    else:page.get_by_role('tab',name='拍照／影像',exact=True).click()


@pytest.mark.parametrize('width', [390, 1440])
def test_attachment_transcript_review_refresh_and_confirm(page, width, tmp_path):
    page.set_viewport_size({'width': width, 'height': 844})
    prepare(page)
    before = page.request.get(BASE + '/api/state').json()['rewards']['total']
    calls = []
    page.on('request', lambda req: calls.append(req.url) if '/api/media/recognize' in req.url else None)
    page.locator('#raw-text').fill('原本的文字')
    choose_image(page)
    assert not calls  # 選檔與本機預覽不等於授權上傳。
    page.get_by_role('button', name='上傳並辨識文字', exact=True).click()
    expect(page.locator('.media-error')).to_contain_text('尚未設定辨識服務')
    expect(page.locator('#raw-text')).to_have_value('原本的文字')
    assert len(calls) == 1
    page.route('**/api/media/recognize', lambda route: route.fulfill(json={
        'text': '原始辨識候選', 'applied': False, 'server_retention': 'none',
        'source': {'kind': 'image', 'mime': 'image/png', 'size': len(PNG), 'sha256': 'a' * 64}}))
    page.get_by_role('button', name='上傳並辨識文字', exact=True).click()
    expect(page.get_by_label('校對文字')).to_have_value('原始辨識候選')
    page.get_by_label('校對文字').fill('人工更正內容')
    expect(page.get_by_role('button', name='加入經歷文字', exact=True)).to_be_disabled()
    page.get_by_label('我已核對這段文字').check()
    page.get_by_role('button', name='加入經歷文字', exact=True).click()
    expect(page.locator('#raw-text')).to_have_value('原本的文字\n\n人工更正內容')
    expect(page.locator('#media-storage')).to_contain_text('已保存在此裝置')
    folder = Path(os.environ.get('LIFEWORLD_MEDIA_ARTIFACTS', str(tmp_path)))
    folder.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(folder / ('media-review-' + str(width) + '.png')), full_page=True)
    page.reload()
    expect(page.locator('#raw-text')).to_have_value('原本的文字\n\n人工更正內容')
    reveal_photo(page)
    expect(page.get_by_text('虛構測試.png', exact=True)).to_be_visible()
    save_for_review(page)
    expect(page.locator('#review-form')).to_be_visible()
    reveal_photo(page)
    expect(page.get_by_text('虛構測試.png', exact=True)).to_be_visible()
    assert page.request.get(BASE + '/api/state').json()['rewards']['total'] == before
    page.get_by_role('button', name='我已核對，確認保存', exact=True).click()
    expect(page.locator('#review-form')).to_have_count(0)
    assert page.request.get(BASE + '/api/state').json()['rewards']['total'] > before
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


def test_card_is_a_local_contact_draft_not_an_experience(page):
    prepare(page)
    choose_image(page, 'card')
    expect(page.locator('.media-item')).to_contain_text('名片只供人物資料校對')
    page.locator('.media-transcript > summary').click()
    page.get_by_label('校對文字').fill('測試姓名，測試公司')
    page.get_by_label('我已核對這段文字').check()
    expect(page.get_by_role('button', name='加入經歷文字', exact=True)).to_have_count(0)
    expect(page.get_by_role('button', name='複製已校對文字', exact=True)).to_be_enabled()
    data = page.request.get(BASE + '/api/state').json()
    assert data['people'] == [] and data['experiences'] == [] and data['rewards']['total'] == 0


def test_permission_denial_and_cancel_preserve_text(page):
    page.add_init_script("""Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {
      value: async () => { throw new DOMException('denied', 'NotAllowedError'); }
    });""")
    prepare(page)
    page.locator('#raw-text').fill('拒絕權限也不能消失')
    if page.get_by_role('tab',name='語音',exact=True).count():page.get_by_role('tab',name='語音',exact=True).click()
    else:page.locator('.media-recorder > summary').click()
    page.get_by_role('button', name='開始錄音', exact=True).click()
    expect(page.locator('#recorder-status')).to_contain_text('未取得麥克風權限')
    expect(page.locator('#raw-text')).to_have_value('拒絕權限也不能消失')
    choose_image(page)
    page.get_by_role('button', name='移除此素材', exact=True).click()
    expect(page.locator('.media-item')).to_have_count(0)
    expect(page.locator('#raw-text')).to_have_value('拒絕權限也不能消失')


def test_recorder_stops_tracks_and_never_uploads_automatically(page):
    # 麥克風測試替身只驗證控制器；實機音質及 iOS 權限仍須另行驗收。
    page.add_init_script("""window.stoppedTracks=0;
      Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async()=>({getTracks:()=>[{stop(){window.stoppedTracks++}}]})});
      window.MediaRecorder=class extends EventTarget {
        static isTypeSupported(t){return t==='audio/webm'}
        constructor(){super();this.state='inactive';this.mimeType='audio/webm'}
        start(){this.state='recording'}
        stop(){this.state='inactive';this.dispatchEvent(new MessageEvent('dataavailable',{data:new Blob([new Uint8Array([26,69,223,163,1])],{type:'audio/webm'})}));this.dispatchEvent(new Event('stop'))}
      };""")
    prepare(page)
    calls = []
    page.on('request', lambda req: calls.append(req.url) if '/api/media/recognize' in req.url else None)
    if page.get_by_role('tab',name='語音',exact=True).count():page.get_by_role('tab',name='語音',exact=True).click()
    else:page.locator('.media-recorder > summary').click()
    page.get_by_role('button', name='開始錄音', exact=True).click()
    expect(page.locator('#recorder-status')).to_contain_text('錄音中')
    page.get_by_role('button', name='停止錄音', exact=True).click()
    expect(page.get_by_role('button', name='上傳並轉文字', exact=True)).to_be_visible()
    assert page.evaluate('window.stoppedTracks') >= 1
    assert calls == []
    expect(page.locator('audio')).to_have_count(1)
    assert page.locator('audio').get_attribute('autoplay') is None
    page.get_by_role('button', name='上傳並轉文字', exact=True).click()
    expect(page.locator('.media-error')).to_contain_text('尚未設定辨識服務')
    expect(page.locator('audio')).to_have_count(1)


def test_month_week_switch_keeps_dates_and_real_period(page):
    # 現有月份元件必須保留，不用七顆展示勾選取代真實日曆。
    page.goto(BASE)
    me = page.request.post(BASE + '/api/auth/guest').json()
    page.request.put(BASE + '/api/profile', headers={'X-CSRF-Token': me['csrf_token']},
                     data={'name': '排程驗收', 'bio': '實際日期', 'timezone': 'Asia/Taipei'})
    today = date.fromisoformat(page.request.get(BASE + '/api/auth/me').json()['today'])
    page.goto(BASE + '/#goal-new')
    page.reload()
    page.locator('#goal-title').fill('月份目標')
    page.get_by_role('button', name='下一步').click()
    page.locator('#outcome').fill('完成作品')
    page.locator('#goal-deadline').fill((today + timedelta(days=65)).isoformat())
    page.get_by_role('button', name='下一步').click()
    expect(page.get_by_role('button', name='按月檢視')).to_have_attribute('aria-pressed', 'true')
    page.get_by_role('button', name='每天', exact=True).click()
    before = page.locator('.gj-schedule-summary').inner_text()
    page.get_by_role('button', name='按週檢視').click()
    expect(page.locator('.gj-day')).to_have_count(7)
    page.get_by_role('button', name='按月檢視').click()
    assert page.locator('.gj-schedule-summary').inner_text() == before
    assert page.locator('.gj-day').count() in (28, 29, 30, 31)
    expect(page.locator('.gj-calendar')).to_contain_text('安排不代表已完成')


def test_cancel_and_remove_inflight_material_does_not_reappear(page):
    prepare(page)
    choose_image(page)
    pending = []
    page.route('**/api/media/recognize', lambda route: pending.append(route))
    page.get_by_role('button', name='上傳並辨識文字', exact=True).click()
    expect(page.get_by_role('button', name='取消辨識', exact=True)).to_be_visible()
    page.get_by_role('button', name='取消辨識', exact=True).click()
    expect(page.locator('.media-error')).to_contain_text('取消')
    page.get_by_role('button', name='移除此素材', exact=True).click()
    expect(page.locator('.media-item')).to_have_count(0)
    if pending:
        pending[0].fulfill(json={'text': '過期回應不得復活素材', 'applied': False})
    page.reload()
    expect(page.locator('.media-item')).to_have_count(0)


def test_navigation_cancel_and_return_keeps_local_draft(page):
    prepare(page)
    page.locator('#raw-text').fill('保留返回位置與文字')
    choose_image(page)
    page.locator('#nav').get_by_role('link', name='世界', exact=True).click()
    page.get_by_role('button', name='繼續編輯', exact=True).click()
    expect(page.locator('#raw-text')).to_have_value('保留返回位置與文字')
    page.get_by_role('tab',name='文字',exact=True).click()
    page.locator('#raw-text').fill('')
    page.reload()
    page.locator('#nav').get_by_role('link', name='世界', exact=True).click()
    page.get_by_role('button',name='保留此裝置草稿並離開',exact=True).click()
    page.goto(BASE + '/#record')
    reveal_photo(page)
    expect(page.get_by_text('虛構測試.png', exact=True)).to_be_visible()


def test_storage_failure_is_not_reported_as_saved(page):
    page.add_init_script("Object.defineProperty(indexedDB,'open',{value:()=>{throw new Error('storage denied')}})")
    prepare(page)
    page.get_by_role('tab',name='拍照／影像',exact=True).click()
    page.locator('[data-media-file="image"]').set_input_files(
        {'name': '不可遺失.png', 'mimeType': 'image/png', 'buffer': PNG})
    expect(page.locator('#media-storage')).to_contain_text('保存失敗')
    expect(page.get_by_text('不可遺失.png', exact=True)).to_be_visible()


def test_another_owner_cannot_see_previous_local_material(page):
    prepare(page)
    choose_image(page)
    page.context.clear_cookies()
    prepare(page)
    expect(page.locator('.media-item')).to_have_count(0)


def test_concurrent_manual_edits_survive_recognition_response(page):
    prepare(page)
    choose_image(page)
    pending = []
    page.route('**/api/media/recognize', lambda route: pending.append(route))
    page.get_by_role('button', name='上傳並辨識文字', exact=True).click()
    expect(page.get_by_role('button', name='取消辨識', exact=True)).to_be_visible()
    page.get_by_label('校對文字').fill('等待時自行更正的內容')
    assert len(pending) == 1
    pending[0].fulfill(json={'text': '供應商原始候選', 'applied': False})
    expect(page.locator('.media-error')).to_contain_text('保留')
    expect(page.get_by_label('校對文字')).to_have_value('等待時自行更正的內容')
    page.get_by_text('查看未修改的辨識原文', exact=True).click()
    expect(page.locator('.media-item .raw-source')).to_contain_text('供應商原始候選')


def test_cancel_pending_permission_releases_late_microphone(page):
    page.add_init_script("""window.released=0;
      Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:()=>new Promise(resolve=>{
        window.allowMicrophone=()=>resolve({getTracks:()=>[{stop(){window.released++}}]});
      })});""")
    prepare(page)
    if page.get_by_role('tab',name='語音',exact=True).count():page.get_by_role('tab',name='語音',exact=True).click()
    else:page.locator('.media-recorder > summary').click()
    page.get_by_role('button', name='開始錄音', exact=True).click()
    expect(page.locator('#recorder-status')).to_contain_text('等待麥克風權限')
    page.get_by_role('button', name='取消錄音', exact=True).click()
    page.evaluate('window.allowMicrophone()')
    expect(page.locator('#recorder-status')).to_contain_text('已取消')
    assert page.evaluate('window.released') == 1
    expect(page.locator('.media-item')).to_have_count(0)


def test_invalid_file_keeps_existing_content(page):
    prepare(page)
    page.locator('#raw-text').fill('仍然保留的文字')
    page.get_by_role('tab',name='拍照／影像',exact=True).click()
    page.locator('[data-media-file="image"]').set_input_files(
        {'name': 'bad.svg', 'mimeType': 'image/svg+xml', 'buffer': b'<svg/>'})
    expect(page.locator('#toast')).to_contain_text('不支援')
    expect(page.locator('#raw-text')).to_have_value('仍然保留的文字')
    expect(page.locator('.media-item')).to_have_count(0)


def test_media_only_draft_can_be_found_without_inventing_text(page):
    prepare(page)
    choose_image(page)
    page.locator('#nav').get_by_role('link', name='紀錄', exact=True).click()
    page.get_by_role('button', name='保留此裝置草稿並離開', exact=True).click()
    expect(page.get_by_role('heading', name='此裝置尚未整理的草稿')).to_be_visible()
    page.reload()
    page.get_by_role('link', name='接續素材草稿', exact=False).click()
    reveal_photo(page)
    expect(page.get_by_text('虛構測試.png', exact=True)).to_be_visible()
    expect(page.locator('#raw-text')).to_have_value('')
    data=page.request.get(BASE+'/api/state').json()
    assert data['experiences']==[] and data['drafts']==[] and data['rewards']['total']==0


def test_server_newer_draft_is_not_overwritten_by_local_fields(page):
    prepare(page)
    page.locator('#raw-text').fill('舊版本機文字')
    choose_image(page)
    save_for_review(page)
    expect(page.locator('#review-form')).to_be_visible()
    saved=page.request.get(BASE+'/api/state').json()['drafts'][0]
    csrf=page.request.get(BASE+'/api/auth/me').json()['csrf_token']
    response=page.request.put(BASE+'/api/drafts/'+saved['id'],headers={'X-CSRF-Token':csrf},data={
        'raw_text':'另一視窗已更新的伺服器原文','occurred_at':saved['occurred_at'],
        'goal_id':saved['goal_id'],'person_id':saved['person_id'],
        'contributions':[],'expected_revision':saved['revision']})
    assert response.status==200
    page.reload()
    page.get_by_role('button', name='返回修改原始草稿', exact=True).click()
    expect(page.locator('#raw-text')).to_have_value('另一視窗已更新的伺服器原文')
    reveal_photo(page)
    expect(page.get_by_text('虛構測試.png', exact=True)).to_be_visible()


def test_text_only_server_save_survives_unavailable_media_storage(page):
    """媒體暫存不可用時，不能阻擋既有文字人工確認閉環。"""
    page.add_init_script("Object.defineProperty(indexedDB,'open',{value:()=>{throw new Error('storage denied')}})")
    prepare(page)
    page.locator('#raw-text').fill('不依賴本機媒體儲存的文字草稿')
    save_for_review(page)
    expect(page.locator('#review-form')).to_be_visible()
    page.locator('[data-review-raw] > summary').click()
    expect(page.locator('.raw-source').first).to_contain_text('不依賴本機媒體儲存的文字草稿')
    assert len(page.request.get(BASE+'/api/state').json()['drafts'])==1
