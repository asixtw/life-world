# 公開介紹部署｜2026-11-13

Owner最新指示「ok 幫我做到部署」，本批提交、Push、Build、同一lw-public零流量候選及驗證後切流在授權範圍。未授權DB、IAM、Secrets、發布Gate解鎖或產品資料寫入，本批不執行。

## 現役基底查核

- 服務：`life-world-513506 / asia-east1 / lw-public`。
- 現役Revision：`lw-public-pr26-icons-421e9b9`，100%且帶`alpha-guest-review`。
- 不可變映像：`asia-east1-docker.pkg.dev/life-world-513506/lw-product-candidates/lw-product@sha256:c3ec8b6a3a71f1101f143cd08841a20b3ceba1c227f93b6bbc637e1e7dc3ae55`。
- 現役Git：`421e9b95c21a4abd1059f3c235545649e12ca830`。線上index與app.js逐byte等於此提交；index SHA256 `bd52c3c872b16e94a6259a3b6eb8aea7531f6a6f7e906f2f4070e1d508f7d8d6`，app.js `e310336da83d157a0d4486fa9a024a2f94673c421f605b46024eb6c91588808b`。
- 初版來源功能提交`49f4dda`留在本機；發布分支從現役421e9b95另行移植。測試將新增介紹片段移除後，原main.py／app.js／index.html必須與現役來源完全相同，避免回退PR26更新。

## 本批操作單元

1. Commit並Push`release/public-intro-20261113`，不Push main。
2. `scripts/prepare_public_intro_context.py`明確列管30個runtime檔。Cloud Build沿用既有建置帳號、來源bucket與映像儲存庫；FROM固定c3ec8b6a，無RUN、USER、CMD或依賴重裝。
3. `gcloud run deploy lw-public --image <新digest> --no-traffic --revision-suffix <本批版本> --region asia-east1 --project life-world-513506`。不傳入env／Secret／IAM／DB設定；比較原／新有效Revision spec（僅映像可不同）及保護性metadata。
4. 現有TrustedHost允許的review tag用於候選驗證：`gcloud run services update-traffic lw-public --set-tags alpha-guest-review=<新Revision> ...`。正式數字網址此時仍100%舊Revision；僅review網址先驗證新版。
5. 候選匿名HTTP／逐檔雜湊與瀏覽器介紹通過，且重讀確認無他人修改後，`gcloud run services update-traffic lw-public --to-revisions <新Revision>=100 ...`。tag與正式網址最後都對應本批新Revision，延續原先review與正式同版的關係。
6. 讀回Revision、digest、流量與設定，再驗證指定正式網址。全程不登入真人帳號、不建立正式測試世界、不呼叫AI。

寫入失敗或結果不明即停止後續雲端寫入，只有限次唯讀查核，不重送、不改用另一方式。舊Revision保留；若需要回復，先提供當時狀態與精確回復指令，由Owner核准後執行，不自動改流量。

## 結果

**已發布：lw-public-intro-c73ddf8，100%正式流量。**

## 發布前驗收

現役基底移植後：後端與發布白名單 **53 PASS／0 FAIL／0 SKIP**，瀏覽器及Guest／正式孵化 **18 PASS／0 FAIL／0 SKIP**，即將用於雲端的唯讀HTTP／瀏覽器檢查先在本機 **4 PASS／0 FAIL／0 SKIP**。收據：[後端](RELEASE_BACKEND_FINAL.xml)／[瀏覽器](RELEASE_BROWSER.xml)／[唯讀檢查](release/LIVE_TEST_LOCAL.xml)。初版02cab305上的驗收另留存，未用作421e9b95發布證明。

## 候選發現與同批修正

850e03c的Cloud Build與零流量Deploy皆成功，設定讀回完全符合預期；HTTP／全部素材逐byte校驗亦通過。隨後應用程式瀏覽器驗收出現 **2 PASS／2 FAIL**，失敗限320／390手機首次開始：程式尚在下載、畫面先呈現可點按鈕，場景初始化重排時第一次操作落空。此時未切正式流量，僅review tag在候選。

[原始失敗XML](release/CANDIDATE_LIVE.xml)／[載入診斷](release/START_DIAGNOSTIC.json)保留；沒有把它當成通過。新增三尺寸「阻擋preview.js下載」測試，先 **3 FAIL**，修正為初始化後才啟用開始／跳過／聲音控制，再 **3 PASS**。本次必要修正仍限已授權介紹功能，未改正式產品流程；修正後以新提交／新Build建立候選，不重送任何失敗的雲端寫入（先前雲端寫入均成功，無結果不明）。正式流量保留421e9b95，直到修正後候選完整通過。

## 最終實績

- 已Push發布分支`release/public-intro-20261113`，Runtime來源提交`c73ddf8c83e2eb41d2499a045ef104f14f585bd2`；未Merge／Push main。
- 最終Cloud Build `51c3d429-2348-4edc-be69-c7fa768e77d4` **SUCCESS**，新Digest `sha256:972da0d1ef0efb792c0fd8c443eb25092be9d74e5ed969cb5467541e51af4c01`。
- Revision `lw-public-intro-c73ddf8`，正式100%；`alpha-guest-review`同版，舊421e9b95與初次850e03c候選保留零流量。
- 原／新有效Revision spec與服務template spec去除映像後精確一致，網路／容量註記不變。沒有改DB、IAM、Secrets、Host白名單、登入或正式產品流程；僅新增介紹路由與入口。
- 修正版針對性檢查 **5 PASS／0 FAIL**，包含慢速載入的瀏覽器回歸 **21 PASS／0 FAIL**；修正版候選線上 **4 PASS／0 FAIL（14.86秒）**，指定正式數字網址 **4 PASS／0 FAIL（18.19秒）**。沒有SKIP；正式驗收未登入真人、未建立世界或呼叫AI，測試攔截任何產品寫入。
- 三尺寸完整介紹、固定`#welcome`入口、完成後不重複提示與選單另開重看通過。原生Safari／Android及陌生訪客理解度仍NOT RUN。

[正式介紹](https://lw-public-162310640466.asia-east1.run.app/intro)／[正式入口](https://lw-public-162310640466.asia-east1.run.app/#welcome)／[發布收據](release/RELEASE_RECEIPT.json)／[最終流量](release/FINAL_STATE.json)／[有效設定比對](release/CANDIDATE_CONFIG_FINAL.json)／[修正版候選XML](release/CANDIDATE_LIVE_FINAL.xml)／[正式XML](release/PRODUCTION_LIVE.xml)／[30檔發布白名單](release/CONTEXT_MANIFEST_FINAL.json)。

正式畫面：[390手機入口](release/screenshots/390-production-entry.png)／[390介紹](release/screenshots/390-production-intro.png)／[1440桌面入口](release/screenshots/1440-production-entry.png)／[1440介紹](release/screenshots/1440-production-intro.png)。
