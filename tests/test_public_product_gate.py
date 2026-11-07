"""沿用公開Alpha護欄於指定Product Staging；缺任何安全設定則fail-closed。"""
from dataclasses import replace
import pytest
from app.runtime import RuntimeSettings


def public_settings(**changes):
    values=dict(backend='postgresql',db_name='life_world_product_staging',db_user='lw_product_staging_app',db_password='synthetic-only',access_mode='public_alpha',google_client_id='synthetic.apps.googleusercontent.com',secure_cookies=True,external_origin='https://product.example.test',auth_rate_enabled=True,auth_rate_secret='synthetic-hmac-'*4,auth_source_mode='proxy',auth_trusted_proxies=('127.0.0.1/32',))
    values.update(changes)
    return RuntimeSettings(**values)


def test_product_public_profile_uses_existing_database_with_google_and_caps():
    s=public_settings()
    assert s.alpha_worlds_total>0 and s.alpha_storage_bytes>0


@pytest.mark.parametrize('changes',[{'google_client_id':''},{'secure_cookies':False},{'external_origin':'http://product.example.test'},{'auth_rate_enabled':False},{'auth_rate_secret':''},{'auth_source_mode':'unconfigured'},{'auth_source_mode':'proxy','auth_trusted_proxies':()},{'db_name':'life_world_main'},{'db_user':'lw_app'}])
def test_product_public_profile_rejects_missing_boundary(changes):
    with pytest.raises(ValueError):public_settings(**changes)
