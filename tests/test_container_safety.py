"""影像掃描須拒絕實際資料／私鑰，同時容許認證 SDK 的程式模組。"""
from io import BytesIO
import importlib.util
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location('image_smoke',Path(__file__).resolve().parents[1] / 'scripts/smoke_api_container.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def archive(tmp_path,name,content):
    path = tmp_path / 'layer.tar'
    with tarfile.open(path,'w') as tar:
        member = tarfile.TarInfo(name)
        member.size = len(content)
        tar.addfile(member,BytesIO(content))
    return path


def test_sdk_module_name_and_pem_marker_constant_are_not_a_private_key(tmp_path):
    path = archive(tmp_path,'opt/venv/google/auth/service_account.py',b'MARKER = "-----BEGIN PRIVATE KEY-----"')
    assert smoke.scan_archive(path) == 1


@pytest.mark.parametrize('name,content',[
    ('srv/.env',b'synthetic'),
    ('srv/data.sqlite3',b'synthetic'),
    ('srv/service-account.json',b'{}'),
    ('srv/arbitrary.json',b'{"type":"service_account","private_key":"synthetic"}'),
    ('srv/private.txt',b'-----BEGIN PRIVATE KEY-----\n'+b'A'*128+b'\n-----END PRIVATE KEY-----'),
    ('srv/local-preview/content.txt',b'synthetic'),
    ('srv/canary.txt',b'LIFEWORLD_SYNTHETIC_IMAGE_CANARY'),
])
def test_private_files_or_content_are_rejected(tmp_path,name,content):
    with pytest.raises(AssertionError):
        smoke.scan_archive(archive(tmp_path,name,content))
