Life World 世界基底 — 獨立候選 0.1（2026-10-29）

已完成
1. built-in imagegen 生成同一房間日間／Quiet 底圖；已逐張觀看。兩版窗框與牆線目視一致，未做像素配準驗證。
2. 三個真正獨立 RGBA 圖層：低櫃、前景盆栽、Lumi 落點陰影。未把角色、蛋或 UI 烤入底圖。
3. preview.html 可組裝上述圖層，切換 Quiet、直向候選、安全區。日間／Quiet 共用定位。
4. manifest、原生尺寸／alpha／SHA256 與完整提示詞。

重要：不是完成十四類美術交付，也不是正式整合驗收。
日間／Quiet 原生生成尺寸都是 1448×1086，不是要求的 1920×1440。
目前沒有原生 1920×1440 原稿、1280×960 顯示匯出或 768×1024 獨立直向原畫。
HTML 的 1280×960／768×1024 是目標畫框，不等同已交付上述尺寸的素材。
沒有用程式補畫、假分層或把放大圖聲稱原生原稿。
低櫃、盆栽、陰影各自有透明底；不是完整畫面等尺寸對位圖層，必須依 manifest／alpha bounds 放置。
Quiet 目前家具與前景使用 CSS brightness／saturate，不是重新繪製 Quiet 圖層。
Lumi 圖是既有 completion-v2 的尺寸參照副本（含蛋殼），不是新角色稿或正式世界頁角色姿態。

版面候選
背景只在 Lumi 場景；文字和操作位於場景外。
角色盒 112×135 CSS px，手機 scale .85；不是圖片輸出尺寸。
手機橫向場景 16:9；直向 3:4 是同稿裁切及圖層重排。
導航與系統安全區由正式頁面預留；本素材頁沒有冒充完整四分頁 UI。
每用戶一個 Lumi；沒有加入家具購買或經濟系統。

QA 狀態
原生五張生成圖已肉眼檢查；metadata 確認三張圖層 alpha 具有零值及部分透明。
透明圖層有細微半透明邊緣，組裝在亮／暗背景後仍需驗收。
已準備 provenance/render-previews.cjs，但本機 Playwright Chromium 缺少。
系統 Chromium 啟動因 socket Operation not permitted 失敗；隔離外啟動又因 bwrap 無法建立唯讀 sessions 路徑失敗。
故尚未產生組裝桌面／手機截圖，不把 HTML 理論布局當作通過手機裁切測試。
腳本包含此 workspace 絕對路徑，工程環境需調整 root 及 Playwright require 後再執行。

待驗收：Boyi 視覺風格、Jerry 正式路徑／錨點／響應式載入／失敗替代畫面；不同裝置裁切、角色完整顯示、Quiet 對齊。
未改工程 repo；未 push、merge 或部署。
