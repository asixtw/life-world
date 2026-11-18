"""安裝引導不等於真實手機已完成安裝；純分流測試不呼叫網路。"""
import json,subprocess
from pathlib import Path
import os,shutil
import pytest
ROOT=Path(__file__).resolve().parents[1]
NODE=os.environ.get('LIFEWORLD_NODE') or shutil.which('node')

@pytest.mark.parametrize('env,kind',[
 ({'userAgent':'iPhone Safari','standalone':False},'ios'),
 ({'userAgent':'Android Chrome','promptAvailable':True},'prompt'),
 ({'userAgent':'Android Chrome'},'android'),
 ({'userAgent':'iPhone Instagram'},'inapp'),
 ({'userAgent':'Android FBAN/FB4A'},'inapp'),
 ({'userAgent':'Macintosh','maxTouchPoints':5},'ios'),
 ({'userAgent':'unknown browser'},'generic'),
 ({'userAgent':'iPhone Safari','standalone':True},'installed'),
])
def test_installation_route(env,kind):
    code="global.window={};"+(ROOT/'app/static/pwa-install-model.js').read_text()+"\nprocess.stdout.write(JSON.stringify(window.LifeWorldInstallGuide.route("+json.dumps(env)+")));"
    assert json.loads(subprocess.check_output([str(NODE),'-e',code],text=True))==kind


def test_both_onboarding_and_product_have_manifest_and_shared_help(client):
    for url in ['/']:
        r=client.get(url)
        assert r.status_code==200
        assert '/static/pwa-install.js' in r.text
        assert '/static/mobile-manifest-v1.webmanifest' in r.text
        assert 'data-pwa-open' in r.text
    assert not client.cookies
