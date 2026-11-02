"""實際 App 的習慣修改、失敗保留與衝突退路。"""
from pathlib import Path
import os
import pytest
from playwright.sync_api import expect
from test_journey import BASE, page


@pytest.mark.parametrize('width', [390, 1440])
def test_habit_edit_cancel_failure_and_save(page, width, tmp_path):
    page.set_viewport_size({'width': width, 'height': 844 if width == 390 else 1050})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    # 舊測試 helper 會寫截圖；本案例只用 API 準備資料，實際驗證修改介面。
    page.goto(BASE)
    page.get_by_role('button', name='不用註冊，先開始').click()
    page.locator('#profile-name').fill('修改習慣測試者')
    page.locator('#bio').fill('保留每一天的標準')
    page.get_by_role('button', name='接著，建立第一個目標').click()
    from datetime import date, timedelta
    today = date.fromisoformat(page.request.get(BASE + '/api/auth/me').json()['today'])
    csrf = page.request.get(BASE + '/api/auth/me').json()['csrf_token']
    result = page.request.post(BASE + '/api/goals', headers={'X-CSRF-Token': csrf}, data={
        'request_id': 'browser-create', 'title': '習慣調整旅程', 'outcome': '留下作品',
        'deadline': (today + timedelta(days=10)).isoformat(),
        'actions': [{'title': name, 'dates': [(today + timedelta(days=n)).isoformat() for n in range(11)]} for name in ['閱讀', '整理', '分享']]})
    assert result.status == 201
    goal = result.json()
    page.goto(BASE + '/#goal/' + goal['id'])
    page.get_by_role('button', name='調整未來安排', exact=True).click()
    page.locator('#review-title-0').fill('每日閱讀')
    page.locator('#review-quantity-0').fill('2')
    expect(page.locator('#habit-change-summary')).to_contain_text((today + timedelta(days=1)).isoformat())
    expect(page.locator('#habit-change-summary')).to_contain_text('每日閱讀')
    artifacts = Path(os.environ.get('LIFEWORLD_NEW_ARTIFACTS', str(tmp_path)))
    artifacts.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(artifacts / ('habit-edit-form-' + str(width) + '.png')), full_page=True)
    page.get_by_role('button', name='返回目標', exact=True).click()
    assert page.request.get(BASE + '/api/goals/' + goal['id']).json()['revision'] == goal['revision']
    page.get_by_role('button', name='調整未來安排', exact=True).click()
    page.locator('#review-title-0').fill('每日閱讀')
    page.locator('#review-quantity-0').fill('2')
    page.locator('#goal-review-form input[name=confirmed]').check()
    page.route('**/api/goals/*/review', lambda route: route.abort('failed'))
    page.get_by_role('button', name='確認保存安排', exact=True).click()
    expect(page.locator('#notice')).to_contain_text('目前無法連線')
    expect(page.locator('#review-quantity-0')).to_have_value('2')
    page.unroute('**/api/goals/*/review')
    page.get_by_role('button', name='確認保存安排', exact=True).click()
    expect(page.locator('#goal-review-form')).to_have_count(0)
    a = page.request.get(BASE + '/api/goals/' + goal['id']).json()['actions'][0]
    assert a['title'] == '每日閱讀' and a['per_occurrence'] == '1' and a['quantity_versions'][-1]['quantity'] == '2'
    page.get_by_role('button', name='調整未來安排', exact=True).click()
    page.locator('#review-quantity-0').fill('3')
    page.locator('#goal-review-form input[name=confirmed]').check()
    current = page.request.get(BASE + '/api/goals/' + goal['id']).json()
    assert page.request.post(BASE + '/api/goals/' + goal['id'] + '/review', headers={'X-CSRF-Token': csrf}, data={
        'request_id': 'other-window', 'expected_revision': current['revision'], 'confirmed': True, 'decision': 'schedule',
        'schedules': [{'action_id': x['id'], 'dates': x['dates'], 'weekdays': x['weekdays'], 'cycle': x['cycle']} for x in current['actions']]}).status == 200
    page.get_by_role('button', name='確認保存安排', exact=True).click()
    expect(page.get_by_role('button', name='載入最新版本並重新核對')).to_be_visible()
    expect(page.locator('#review-quantity-0')).to_have_value('3')
    page.get_by_role('button', name='載入最新版本並重新核對').click()
    expect(page.locator('#goal-review-form input[name=confirmed]')).not_to_be_checked()
    page.locator('#goal-review-form input[name=confirmed]').check()
    page.get_by_role('button', name='確認保存安排', exact=True).click()
    expect(page.locator('#goal-review-form')).to_have_count(0)
    path = Path(os.environ.get('LIFEWORLD_NEW_ARTIFACTS', str(tmp_path)))
    path.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path / ('habit-edit-' + str(width) + '.png')), full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert errors == []
