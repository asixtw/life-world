"""只驗證正式原生站圖示與靜態設定；不登入、不連正式DB或AI。"""
import json
import subprocess
from pathlib import Path
from html.parser import HTMLParser

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
STATIC=ROOT/'app/static'
BASE='74ebf30fdb3262f57dcb92cb3a9119ce0f247224'


class Head(HTMLParser):
    """取出head宣告，比對保留的腳本／樣式與新增品牌連結。"""
    def __init__(self):super().__init__();self.links=[];self.scripts=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='link':self.links.append(attrs)
        if tag=='script':self.scripts.append(attrs)


def test_public_head_preserves_product_scripts_and_styles():
    before=Head();before.feed(subprocess.check_output(['git','show',BASE+':app/static/index.html'],text=True))
    after=Head();after.feed((STATIC/'index.html').read_text())
    assert before.scripts==after.scripts
    assert [item for item in before.links if item['rel']=='stylesheet']==[item for item in after.links if item['rel']=='stylesheet']
    assert any(item['rel']=='apple-touch-icon' and item.get('sizes')=='180x180' for item in after.links)
    assert any(item['rel']=='manifest' and item['href']=='/static/mobile-manifest-v1.webmanifest' for item in after.links)


def test_public_manifest_has_product_identity_and_world_entry():
    manifest=json.loads((STATIC/'mobile-manifest-v1.webmanifest').read_text())
    assert manifest['id']=='/' and manifest['name']=='Life World' and manifest['short_name']=='Life World'
    assert manifest['start_url']=='/#world' and manifest['scope']=='/'
    assert manifest['display']=='standalone'
    assert {(x['sizes'],x['purpose']) for x in manifest['icons']}=={('192x192','any'),('512x512','any'),('192x192','maskable'),('512x512','maskable')}
    assert all(x['src'].startswith('/static/art/mobile-web-v1/') for x in manifest['icons'])


def test_public_static_icons_are_anonymously_served_without_product_runtime():
    app=FastAPI();app.mount('/static',StaticFiles(directory=STATIC))
    with TestClient(app) as client:
        response=client.get('/static/mobile-manifest-v1.webmanifest')
        assert response.status_code==200
        assert response.headers['content-type'].split(';')[0] in ('application/manifest+json','application/json')
        paths=[x['src'] for x in response.json()['icons']]
        head=Head();head.feed((STATIC/'index.html').read_text())
        paths += [x['href'] for x in head.links if x['rel'] in ('icon','apple-touch-icon')]
        for path in paths:
            response=client.get(path)
            assert response.status_code==200
            assert response.content.startswith((b'\x89PNG\r\n\x1a\n',b'\0\0\1\0'))
            assert 'set-cookie' not in response.headers
