"""合成 IAP audience 測試；不公開專案、帳號或真實部署設定。"""
import time
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from google.auth import jwt
from google.auth.crypt.es256 import ES256Signer
from app.iap import IAPVerifier,expected_audience
from app.errors import DomainError

AUD='/projects/123456789/locations/test-region/services/test-product'


def test_existing_canonical_origin_derives_iap_audience(monkeypatch):
    monkeypatch.delenv('LIFEWORLD_IAP_AUDIENCE',raising=False)
    monkeypatch.setenv('K_SERVICE','test-product')
    monkeypatch.setenv('LIFEWORLD_EXTERNAL_ORIGIN','https://test-product-123456789.test-region.run.app')
    assert expected_audience()==AUD
    monkeypatch.setenv('LIFEWORLD_EXTERNAL_ORIGIN','https://unrelated.example.invalid')
    with pytest.raises(ValueError):expected_audience()


def test_iap_real_es256_signature_and_wrong_audience():
    key=ec.generate_private_key(ec.SECP256R1())
    private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    signer=ES256Signer.from_string(private,key_id='synthetic-key')
    verifier=IAPVerifier(fetch=lambda:{'synthetic-key':public},audience=AUD)
    claims={'iss':'https://cloud.google.com/iap','aud':AUD,'iat':int(time.time()),'exp':int(time.time())+300,'sub':'synthetic-user'}
    token=jwt.encode(signer,claims).decode()
    assert verifier.verify(token)=='iap:https://cloud.google.com/iap:synthetic-user'
    with pytest.raises(DomainError):verifier.verify(jwt.encode(signer,{**claims,'aud':AUD+'-wrong'}).decode())
