"""時間提示使用與業務規則同一伺服器時鐘，不以瀏覽器日期猜測。"""
from conftest import onboard


def test_session_exposes_authoritative_experience_clock(client):
    onboard(client)
    me=client.get('/api/auth/me').json()
    assert me['server_now']=='2026-10-27T07:00:00+00:00'
    assert me['today']=='2026-10-27'
