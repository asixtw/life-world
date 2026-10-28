# 交付進度（2026-10-28）

共同來源 commit `1c9d502f32688bcc3c73e4b99a2cc3724c179047`；分支 `work/ousang-full-kit`，僅改 `collaboration/ui-kit/`。使用者已選 A：本套件用文件指定十五人；沈知衡屬另一套原創長版卡。

## 已實作

- `content/personas.v1.json` 三組各五人，固定 ID、版本、時間界線、動力／視角／語言／邊界及來源 ID。`content/scenarios.v1.json` 六場各三條不同主路徑，每條再有兩個次選擇，均可到達結尾。
- `content/examples.v1.json` 45 段四回合生成示例；`evaluation/inputs.v1.json` 30 個新情境，與 `evaluation/reference.v1.json` 的評分規則／參考方向物理分檔。所有示例、劇情均明示生成或詮釋，沒有冒充引文。
- `content/sources.v1.json` 收錄史書、哲學文本、聯合國／IAEA／IMO／美國國務院公開材料；`reviewed=false`，仍待人工逐條核對。國際組為虛構職務代表，場景是假設，公開背景截止 2024-12-31。
- 共用圖像兩 ZIP 經使用者手動下載至 `C:\Users\t6vmp\Downloads\`。runtime SHA256 `10bd8f58f04739587f8478fc9a4afec0a871022f95277f19f73382373d7ab363`；originals SHA256 `a603a9d32e1d534f71163563a6120ce53689ee75b4e96b12a4943942ef6d35d0`。54 檔安全合併至 `assets/shared-art/`；清單中的 35 個原稿／輸出檔 SHA256 全數吻合，來源 manifest 雜湊 `9086464441b2b0b322c74fb81e4c7cf9b38ff5862b017546cfcdc247363102af`。原稿與輸出、來源紀錄分開保存。
- `AssetGallery` 可切換八項實際 PNG；孵化畫面接靜置、微光、初裂、深裂與 Lumi。App favicon／分享圖已進 `public/`。open 階段顯示深裂圖並明示分離蛋殼缺件，不虛稱圖已完成。
- `src/contracts.ts`、`engine.ts`、`Theater.tsx` 支援選角、選場、來源、分支、回顧、返回、重設、手動匯出與未設定 live adapter 退路；全部與正式資料隔離。

## 驗證與缺口

最近一次 `tsc -b`、`vite build`、`vitest run` 通過：41 模組、3 個測試檔、12 個案例。瀏覽器已驗選角、來源面板、兩輪分支結尾與返回；新接入的蛋、分享圖及圖示裁切在 390×844 均載入，劇場和畫廊無水平溢位或小於 44 CSS px 的可見按鈕。匯出已重試成功，`Downloads/simulation-7b36f892-9310-41a0-a28c-be530d52c958.json` 可讀，包含 `usageScope=demo`、`channel=script`、`exportKind=life-world-simulation`、`importToRealExperience=false`。實際截圖檔、全部新畫面的跨瀏覽器檢查仍待補。

- 十五肖像、三封面尚未交付；`assets/expected-persona-art.v1.json` 記需求而不放空路徑。四項共用美術 `shellsplit`／`completion`／獨立 nourishment 光效／`world-base` 曾遭圖像工具阻擋，沒有檔案，不能標完成。
- 即時 AI 端點、正式 App／DB、實際麥克風／附件上傳未接；Boyi／Jerry 尚未審查。來源的 `reviewed=false` 不等於已人工驗證。
- Library 原生 materialize 在 Windows 缺 `os.setxattr` 而失敗；本次依使用者明確提供的本地 ZIP 讀取，保留原 Library ID `libfile_c1337d18a09081918aaa69c3951f8e1c` 和 `libfile_5fb88fe851e8819198ee4243b4e37f07`，不宣稱本機 xattr 已寫入。
