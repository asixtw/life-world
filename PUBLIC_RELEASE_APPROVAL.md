# lw-public 原網址發布操作方案（Owner已核准執行範圍）

原網址 https://lw-public-162310640466.asia-east1.run.app/#world 不變。固定後端74ebf30、Digest86f4d3443ed31da1c5784d0978e6e1e7e1357bd146c05e639c75612ded39f6ed；僅疊加02cab305既有手機圖示及新版首頁引用，測試3 PASS。先Commit/普通Push隔離整合分支取得完整SHA，不Merge main。context位於/private/tmp/lw-public-pr26-icons-release-context，僅17份靜態檔及建置設定，不含DB資料或.env。MANIFEST.json固定內容hash。

## 一次核准範圍（Owner已於本次對話明確核准）

1. Commit/普通Push本機圖示整合與測試至integration/public-pr26-icons-20261113；不Merge。
2. 一次Cloud Build，沿用既有lw-product-build帳號，timeout600秒，只建置靜態overlay映像；記Build ID/來源SHA/實際Digest，失敗不重試。
3. 固定新Digest部署lw-public新Revision（只更新映像、LIFEWORLD_RELATION_SOURCE_STORE=link_table，0%主流量），測試Tag alpha-guest-review指向新候選。維持現役SA、Secret引用、DB、Origin與Host規則，不Migration/GRANT/IAM/Secrets變更。
4. 候選health/ready/首頁/四步JS/所有icon與manifest逐項HTTP200、圖示hash與來源相符、腳本/樣式仍PR26版本、Runtime設定無非預期差異；確認生日/任職011結構與Owner最小權限的現有驗收證據及核心人工確認流程。如無法證明必要條件，停止不切流；真AI或Alpha業務寫入測試不由這次文件更新推定授權，缺證據須明列，不拿/ready冒充完整PASS。
5. 只有以上必要檢查及核心驗收通過後，將lw-public公開100%切至新Revision；不影響其他服務。
6. 僅在本次切流後健康/就緒失敗、必要靜態檔404或明確新增5xx，且讀回確認沒有其他人改流量時，允許回滾至lw-public-icons-02cab305；保留Tag，不回寫DB。回滾失敗或狀態不明就停止，不換方法。

## 指令模板（未執行；SHA/Digest/Revision須讀回填入，不能把placeholder當真值）

```sh
gcloud builds submit /private/tmp/lw-public-pr26-icons-release-context --project=life-world-513506 --region=asia-east1 --config=/private/tmp/lw-public-pr26-icons-release-context/cloudbuild.yaml --substitutions=_COMMIT=FIXED_COMMIT --gcs-source-staging-dir=gs://lw-product-build-source-513506/pr26-icons --async

gcloud run deploy lw-public --project=life-world-513506 --region=asia-east1 --image=FIXED_IMAGE_AT_DIGEST --revision-suffix=FIXED_REVISION_SUFFIX --no-traffic --update-env-vars=LIFEWORLD_RELATION_SOURCE_STORE=link_table

gcloud run services update-traffic lw-public --project=life-world-513506 --region=asia-east1 --update-tags=alpha-guest-review=VERIFIED_NEW_REVISION

gcloud run services update-traffic lw-public --project=life-world-513506 --region=asia-east1 --to-revisions=VERIFIED_NEW_REVISION=100
# 僅事先核准且符合停止條件的回滾：
gcloud run services update-traffic lw-public --project=life-world-513506 --region=asia-east1 --to-revisions=lw-public-icons-02cab305=100
```

影響：一次建置/映像儲存費、候選Cold Start與新程式開始承接Alpha請求；不聲稱部署不影響資料行為。新Runtime業務寫入仍受既有Session/Owner/CSRF/Confirm契約。回滾應用不會撤銷切流後的資料寫入；不進行資料庫降版。新映像尚未建置，不能提供不存在的最終Digest；核准後先以實際Digest綁定後續操作，若base/流量有並行改動則停止。
