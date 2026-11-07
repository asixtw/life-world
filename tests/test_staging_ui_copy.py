"""環境中立標籤與訪客保存契約；不把本機測試當作 Staging DB 驗收。"""

def test_app_shell_does_not_claim_local_environment(client):
    html = client.get('/').text
    assert '本機開發版' not in html
    assert 'Life World 測試版' in html
