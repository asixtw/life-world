# 成果圖片64KiB誤擋修復（2026-11-13）

Owner已要求套用本次修復；程式/隔離測試、Commit/普通Push、單次Build、0%候選及驗證後lw-public切流，無Migration/GRANT/IAM/Secrets變更、不Merge main。現役基準c73ddf8c83e2eb41d2499a045ef104f14f585bd2，Revision lw-public-intro-c73ddf8，Digest972da0d1ef0efb792c0fd8c443eb25092be9d74e5ed969cb5467541e51af4c01。使用此底層保留介紹畫面/手機圖示與現役其他設定，不能回退421e9b9映像。

缺陷：AlphaBodyLimit只排除辨識媒體，導致POST /api/goals/{id}/evidence的multipart成果圖片誤套文字64KiB護欄。修復：只對精確成果multipart入口改用解析前串流上限，圖片上限依現有policy5MiB加64KiB封裝容量；服務仍驗實際檔案5MiB、格式、Owner及CSRF。一般JSON仍64KiB，假路徑/JSON不冒用圖片額度，音訊另依原設定。

三個app模組改動，前端/資料模型/獎勵不改。新增測試真紅燈3 FAIL/1 PASS後修復；移至現役基準時原圖示test以舊74ebf30比對而1 FAIL，僅改BASE為現役c73ddf8，保留全部原腳本/樣式相等斷言，非放寬需求。最後相關套件49 PASS/0 FAIL（3.08s）；SQLite API＋ASGI串流／Owner/CSRF／>64KiB有效PNG／>5MiB拒絕及圖片/媒體回歸。非本次GCP業務寫入或PG測試，這兩項NOT RUN。

建置僅COPY三個Python模組到固定現役底層；容器網路關閉驗Python3.12 imports，不連DB或呼叫Provider。固定新SHA/Digest後gcloud run deploy lw-public --image=新Digest --revision-suffix=evidence-固定短SHA --no-traffic，不傳env。讀回spec與原版比較僅image/容器名可異；alpha-guest-review更新到候選，驗health/ready/所有前端與介紹/圖示checksum、一般大JSON仍413。成果endpoint匿名POST只可確認401/403，不冒用Owner或建立正式資料；真實登入上傳由Owner使用既有帳號驗收。

全部必要檢查後，讀回無並行變更才gcloud run services update-traffic lw-public --to-revisions=候選Revision=100；原網址不變，前後收據記錄實際Revision/Digest/HTTP結果。若雲端寫入失敗或結果不明即停止，不重試、不切換方法或擴權；保留原Revision，任何未另行核准的DB/流量恢復操作不自行執行。正式檔案與資料列不隨應用回復刪除。
