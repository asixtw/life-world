"""不取 ADC 的 adapter 邊界測試；實際 SQL／交易另在 PG18 驗證。"""
from dataclasses import replace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.errors import DomainError
from app.main import create_app
from app.postgres import PostgresDatabase
from app.runtime import RuntimeSettings


def test_connector_is_lazy_private_adc_and_failure_is_sanitized(tmp_path):
    factory = Mock(side_effect=RuntimeError('sensitive ADC detail'))
    settings = RuntimeSettings(backend='postgresql', connection_mode='cloud_sql',
                               db_password='synthetic-secret', instance_connection_name='local:test:synthetic')
    database = PostgresDatabase(settings, connector_factory=factory)
    app = create_app(data_dir=tmp_path, database=database)
    factory.assert_not_called()  # factory／startup 不取憑證、不連 DB、不做 DDL。
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get('/health').status_code == 200
        factory.assert_not_called()
        assert client.get('/ready').status_code == 503
        response = client.post('/api/auth/guest')
        assert response.status_code == 503
        assert 'sensitive' not in response.text
    assert factory.call_args.kwargs['ip_type'] == 'private'
    assert factory.call_args.kwargs['refresh_strategy'] == 'lazy'
    assert not list(tmp_path.glob('*.sqlite*'))


def test_tcp_tls_cannot_be_disabled_for_remote_address(monkeypatch):
    monkeypatch.setenv('LIFEWORLD_DB_BACKEND','postgresql')
    monkeypatch.setenv('LIFEWORLD_DB_PASSWORD','synthetic')
    monkeypatch.setenv('LIFEWORLD_DB_HOST','10.129.0.3')
    monkeypatch.setenv('LIFEWORLD_PG_TLS','disable')
    with pytest.raises(ValueError, match='TLS'):
        RuntimeSettings.from_env()


def test_https_cookie_origin_csrf_and_hosts(tmp_path):
    settings = RuntimeSettings(secure_cookies=True, trusted_hosts=('api.example.test',),
                               external_origin='https://api.example.test')
    with TestClient(create_app(data_dir=tmp_path, settings=settings), base_url='https://api.example.test') as client:
        guest = client.post('/api/auth/guest')
        cookie = guest.headers['set-cookie'].lower()
        for flag in ('secure','httponly','samesite=strict'):
            assert flag in cookie
        data = {'name':'合成','bio':'測試','timezone':'UTC'}
        assert client.put('/api/profile',json=data).status_code == 403
        client.headers['X-CSRF-Token'] = guest.json()['csrf_token']
        assert client.put('/api/profile',json=data,headers={'Origin':'https://evil.example'}).status_code == 403
        assert client.put('/api/profile',json=data,headers={'Origin':'https://api.example.test'}).status_code == 200
        assert 'access-control-allow-origin' not in client.get('/health',headers={'Origin':'https://evil.example'}).headers
        assert client.get('/health',headers={'Host':'evil.example'}).status_code == 400
    assert 'synthetic-secret' not in repr(replace(settings,db_password='synthetic-secret'))
