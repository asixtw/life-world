# lw-public 手機主畫面圖示｜2026-11-13核准批次

Owner於本對話明確授權將已製作的iPhone／Android／maskable／favicon功能Push並上線到`https://lw-public-162310640466.asia-east1.run.app/#world`。此批准僅限本功能，不是整合main後端、資料庫、登入或世界流程的發布批准。

## 精確範圍

- 正式服務：`life-world-513506 / asia-east1 / lw-public`。
- 目前正式Revision：`lw-public-camera-8f377fa`，100%流量，保留既有`alpha-guest-review` tag。
- 基底Git：`8f377fa1dd0b196c9963b194b5bfbfcc95a5fa55`。實際下載的首頁與該提交index逐byte相同（SHA256 `a91f266d0decae509632abd53c0f393bf2187de27f28b5550e3fbe806dd8633b`）。
- 基底映像：`asia-east1-docker.pkg.dev/life-world-513506/lw-product-candidates/lw-product@sha256:68f072c973ab40075b1ba5533a55a6324d5c7a3cf71b00920b0dfc589e2e0e75`。
- 新版直接FROM這份不可變映像，只COPY靜態index、manifest與圖示。沒有重裝依賴、RUN、USER、CMD或後端程式變更，不將較新main的產品功能夾帶發布。
- 圖示位於`/static/art/mobile-web-v1/`；原稿1254方形，所有衍生PNG不透明。原始Lumi參考、生成提示詞、SHA與Owner對指定站點的授權狀態記於同目錄。
- manifest為正式產品專屬：`name=Life World`、`id=/`、`start_url=/#world`、`scope=/`，不用元件展示站的id或名稱。沒有新增Service Worker或離線承諾。

## 本批發布方式

1. 在`release/public-mobile-icons-20261113`建立提交，僅Push此功能分支；不推main，避免誤觸`lw-api-main`的App路徑自動發布。
2. `scripts/prepare_public_icon_context.py`產生17個靜態檔的白名單context。`deploy/cloudbuild.public-icons.yaml`只建置／推送映像，沿用既有`lw-product-build`身分、`lw-product-build-source-513506`來源bucket與`lw-product-candidates`儲存庫。
3. 以不可變新Digest部署`lw-public`零流量候選，保留目前執行設定及舊tag；比較容器執行設定指紋、候選健康、首頁與manifest／圖示精確內容後，才將指定服務100%切至候選。
4. 切流前重讀舊Revision／流量，其他操作者已修改或結果不明即停止。所有Cloud寫入失敗／結果不明均不重送、不另起Build、不繞過檢查；只做有期限的唯讀查核。
5. 最後讀回新Revision／Digest／100%流量，檢查指定數字網址及匿名靜態資源。沒有真人帳號登入、產品資料寫入、真實AI呼叫、Migration、IAM、Secrets或權限變更。

舊Revision保留，可回復流量；若需要額外回復，先核對只有本批候選持有流量、沒有其他操作者修改，再依Owner指示處理，不能把舊批次回復授權擴張到此服務。

## 驗收

`tests/test_public_mobile_icons.py`先取得4項有效紅燈，再實作。綠燈驗證產品腳本／樣式完全保留、正式產品manifest、匿名靜態路徑與MIME，以及不可變基底只覆蓋靜態檔。僅用獨立StaticFiles ASGI測試，不連正式DB。

原圖、14PNG與ICO之前已有7項本機驗收及320／390／1440裁切預覽；本批另驗證候選及正式網址的實際bytes／宣告。iPhone／Android真實加入主畫面、已安裝捷徑的系統快取更新仍需實機驗證，不能以HTTP或頭部宣告通過冒充。

實際Commit、Build、映像、Revision、測試與發布結果在本批完成後的工作區交付收據記錄；本文件不預先宣稱發布成功。
