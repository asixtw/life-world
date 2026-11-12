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

部署準備中；以下實績與收據於操作完成後更新，不預先宣稱上線。

## 發布前驗收

現役基底移植後：後端與發布白名單 **53 PASS／0 FAIL／0 SKIP**，瀏覽器及Guest／正式孵化 **18 PASS／0 FAIL／0 SKIP**，即將用於雲端的唯讀HTTP／瀏覽器檢查先在本機 **4 PASS／0 FAIL／0 SKIP**。收據：[後端](RELEASE_BACKEND_FINAL.xml)／[瀏覽器](RELEASE_BROWSER.xml)／[唯讀檢查](release/LIVE_TEST_LOCAL.xml)。初版02cab305上的驗收另留存，未用作421e9b95發布證明。
