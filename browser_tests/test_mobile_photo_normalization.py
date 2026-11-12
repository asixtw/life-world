"""大型手機相片於裝置縮圖；辨識為明示替身，不冒稱真模型或真Safari相機。"""
import os,random
from pathlib import Path
import pytest
from PIL import Image
from playwright.sync_api import expect
from test_journey import page
from test_media_flow import prepare


@pytest.mark.parametrize('width',[390,1440])
def test_large_camera_photo_is_optimized_before_upload(page,width,tmp_path):
    page.set_viewport_size({'width':width,'height':950})
    before=os.environ.get('LW_OLD_MEDIA_SCRIPT')
    if before:page.route('**/static/media.js*',lambda route:route.fulfill(path=before,content_type='application/javascript'))
    page.route('**/api/media/capabilities',lambda route:route.fulfill(json={'max_bytes':2000000,'audio_max_bytes':64*1024*1024,'recognition_available':True}))
    prepare(page)
    photo=tmp_path/'手機大型相片.jpg';Image.frombytes('RGB',(3600,2400),random.Random(7).randbytes(3600*2400*3)).save(photo,quality=96)
    assert photo.stat().st_size>5*1024*1024
    uploads=[]
    def recognition(route):
        from email.parser import BytesParser
        from email.policy import default
        content=route.request.post_data_buffer
        message=BytesParser(policy=default).parsebytes(('Content-Type: '+route.request.headers['content-type']+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+content)
        file=next(part for part in message.iter_parts() if part.get_param('name',header='content-disposition')=='file')
        payload=file.get_payload(decode=True)
        assert file.get_content_type()=='image/jpeg' and len(payload)<=2000000
        from io import BytesIO
        with Image.open(BytesIO(payload)) as image:assert max(image.size)<=2400
        uploads.append(len(payload));route.fulfill(json={'text':'手機相片合成辨識候選','applied':False,'server_retention':'none','source':{'kind':'image','mime':'image/jpeg','size':len(payload),'sha256':'a'*64}})
    page.route('**/api/media/recognize',recognition)
    if page.get_by_role('tab',name='拍照／影像',exact=True).count():page.get_by_role('tab',name='拍照／影像',exact=True).click()
    page.locator('[data-media-file="camera"]').set_input_files(str(photo))
    expect(page.locator('.media-item h3')).to_contain_text(photo.name,timeout=15000)
    page.get_by_role('button',name='上傳並辨識文字',exact=True).click();expect(page.get_by_label('校對文字')).to_have_value('手機相片合成辨識候選')
    assert len(uploads)==1
    page.reload();expect(page.locator('.media-item h3')).to_contain_text(photo.name)
    # 原圖不寫入本機工作區；只保留轉換後的有界Blob與原檔名/大小metadata。
    sizes=page.evaluate('''async()=>new Promise((resolve,reject)=>{const r=indexedDB.open('lifeworld-media-local',1);r.onsuccess=()=>{const db=r.result,t=db.transaction('workspaces'),q=t.objectStore('workspaces').getAll();q.onsuccess=()=>{resolve(q.result.flatMap(x=>x.items.map(i=>i.blob.size)));db.close();};q.onerror=()=>reject(q.error);};})''')
    assert sizes and max(sizes)<=2000000
