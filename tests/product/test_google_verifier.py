"""Google verifier契約；mock代表已驗簽SDK邊界，不代表真Google登入。"""
import time
from unittest.mock import patch
import pytest
from app.errors import DomainError
from app.security import digest
from app.google_identity import GoogleVerifier


def claims():
    now=int(time.time())
    return {'iss':'https://accounts.google.com','aud':'test.apps.googleusercontent.com','iat':now,'exp':now+3600,'sub':'google-subject','nonce':'nonce-value'}


def test_valid_sdk_verified_identity():
    with patch('app.google_identity.jwt.decode_header',return_value={'alg':'RS256','kid':'test'}),patch('app.google_identity.id_token.verify_oauth2_token',return_value=claims()) as sdk:
        identity=GoogleVerifier('test.apps.googleusercontent.com').verify('synthetic-token',digest('nonce-value'))
        assert identity==('https://accounts.google.com','google-subject')
        assert sdk.call_args.kwargs['audience']=='test.apps.googleusercontent.com'


@pytest.mark.parametrize('field,value',[('aud','evil'),('iss','evil'),('exp',1),('iat',9999999999),('nonce','wrong'),('sub',''),('iat',True)])
def test_invalid_claims_fail_closed(field,value):
    c=claims();c[field]=value
    with patch('app.google_identity.jwt.decode_header',return_value={'alg':'RS256','kid':'test'}),patch('app.google_identity.id_token.verify_oauth2_token',return_value=c):
        with pytest.raises(DomainError) as err:GoogleVerifier('test.apps.googleusercontent.com').verify('synthetic-token',digest('nonce-value'))
        assert err.value.status==401


def test_bad_signature_and_algorithm():
    for header in [{'alg':'none'},{'alg':'RS256','kid':'test','jku':'https://evil'}]:
        with patch('app.google_identity.jwt.decode_header',return_value=header):
            with pytest.raises(DomainError):GoogleVerifier('test.apps.googleusercontent.com').verify('synthetic-token','0'*64)
    with patch('app.google_identity.jwt.decode_header',return_value={'alg':'RS256','kid':'test'}),patch('app.google_identity.id_token.verify_oauth2_token',side_effect=ValueError('bad signature')):
        with pytest.raises(DomainError):GoogleVerifier('test.apps.googleusercontent.com').verify('synthetic-token','0'*64)


def test_real_rsa_signature_with_local_google_certificate_stub():
    """使用真RS256與SDK驗簽；只有公鑰來源是本機替身，不宣稱真Google。"""
    import json
    from types import SimpleNamespace
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from google.auth import jwt as google_jwt
    from google.auth.crypt import RSASigner
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    pem=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    request=lambda *a,**kw:SimpleNamespace(status=200,data=json.dumps({'local-key':public}).encode())
    signer=RSASigner.from_string(pem,key_id='local-key')
    verifier=GoogleVerifier('test.apps.googleusercontent.com',request=request)
    token=google_jwt.encode(signer,claims()).decode()
    assert verifier.verify(token,digest('nonce-value'))[1]=='google-subject'
    pieces=token.split('.');pieces[2]=('A' if pieces[2][0]!='A' else 'B')+pieces[2][1:]
    with pytest.raises(DomainError):verifier.verify('.'.join(pieces),digest('nonce-value'))
    for field,value in [('aud','other-client'),('iss','https://evil.invalid'),('exp',1),('iat',int(time.time())+3600),('nonce','wrong')]:
        c=claims();c[field]=value
        with pytest.raises(DomainError):verifier.verify(google_jwt.encode(signer,c).decode(),digest('nonce-value'))
