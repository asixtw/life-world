"""受保護Tag可同源操作，不能冒用其他已允許Origin。"""
from dataclasses import replace
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.runtime import RuntimeSettings

CANON='https://lw-product-staging-162310640466.asia-east1.run.app'
TAG='https://gcp144-review---lw-product-staging-u5py2jttpa-de.a.run.app'

@pytest.mark.parametrize('base,origin,status',[(TAG,TAG,201),(TAG.replace('https://','http://'),TAG,201),(CANON,CANON,201),(TAG,CANON,403),(TAG,'https://evil.example',403)])
def test_exact_same_origin_guest(tmp_path,base,origin,status):
    settings=replace(RuntimeSettings(),external_origin=CANON,trusted_hosts=(CANON.split('//')[1],TAG.split('//')[1]),write_origins=(TAG,))
    with TestClient(create_app(data_dir=tmp_path,settings=settings),base_url=base) as client:
        response=client.post('/api/auth/guest',headers={'Origin':origin})
        assert response.status_code==status
        if status==403:assert response.json()['error']['code']=='origin_rejected'

@pytest.mark.parametrize('origin',['*','https://evil.example','http://gcp144-review---lw-product-staging-u5py2jttpa-de.a.run.app',TAG+'/path'])
def test_bad_write_origin_configuration(origin):
    with pytest.raises(ValueError):
        replace(RuntimeSettings(),trusted_hosts=(TAG.split('//')[1],),write_origins=(origin,))

def test_tag_origin_does_not_bypass_csrf_or_enable_google(tmp_path):
    """Tag只修Origin：缺少CSRF仍拒絕，Google未配置仍明確關閉。"""
    settings=replace(RuntimeSettings(),external_origin=CANON,trusted_hosts=(CANON.split('//')[1],TAG.split('//')[1]),write_origins=(TAG,))
    with TestClient(create_app(data_dir=tmp_path,settings=settings),base_url=TAG) as client:
        guest=client.post('/api/auth/guest',headers={'Origin':TAG}).json()
        profile={'name':'合成測試','bio':'閱讀','timezone':'Asia/Taipei'}
        assert client.put('/api/profile',json=profile,headers={'Origin':TAG}).status_code==403
        assert client.put('/api/profile',json=profile,headers={'Origin':TAG,'X-CSRF-Token':guest['csrf_token']}).status_code==200
        cap=client.get('/api/capabilities').json()
        assert cap['google_login_available'] is False
        assert cap['writes_available'] is True
        assert settings.external_origin==CANON

@pytest.mark.parametrize('origin,expected',[(TAG,200),(CANON,403),('https://evil.example',403)])
def test_google_challenge_on_exact_tag(tmp_path,origin,expected):
    """僅驗證OAuth來源Gate；不冒充真實Google驗簽或正式PG。"""
    settings=replace(RuntimeSettings(),external_origin=CANON,trusted_hosts=(CANON.split('//')[1],TAG.split('//')[1]),write_origins=(TAG,),google_client_id='123-synthetic.apps.googleusercontent.com')
    app=create_app(data_dir=tmp_path,settings=settings)
    # 僅在本測試可丟棄SQLite建立Google表；不連Product、不執行正式Migration。
    with app.state.service.db.connect(write=True) as c:
        c.execute('CREATE TABLE IF NOT EXISTS external_identities(provider TEXT,issuer TEXT,subject TEXT,owner_id TEXT,created_at TEXT)')
    with TestClient(app,base_url=TAG) as client:
        guest=client.post('/api/auth/guest',headers={'Origin':TAG}).json()
        result=client.post('/api/auth/external/challenge',json={'mode':'upgrade'},headers={'Origin':origin,'X-CSRF-Token':guest['csrf_token']})
        assert result.status_code==expected,result.text
        if expected==200:assert result.json()['client_id']==settings.google_client_id
