# 交付進度（2026-10-28）

## 最後來源與離開流程覆核

保留題 `hold-ph-zhuangzi-1` 改為夢中許諾與醒後核對的事件，與曲木寓言分離。IMO 來源改為 2024-05-24 的 MSC 108 新聞稿，精確記錄頁面行 25–38；不再引用含 2026 更新的熱點頁作 2024 依據。四筆來源只標 `machine_checked_locator`，其餘十一筆為 `unverified`，十五筆人工 `reviewed` 仍為 false。孵化與轉場在播放中卸載時各送出一次取消回呼；完成後離開不再送取消，純函式契約測試涵蓋此邊界。

## 本輪行為與來源修正

`content/script-voices.v1.json` 現為十五人物在各自兩場劇情、三條主路線的 90 句專屬回應，另有逐人追問語氣。`engine.ts` 依 session 人物與路線選取回應，`speakerId` 綁定發話者；具名場景敘述保持旁白，不把其他人的話錯標給所選角色。六場同場換五個人物的回應差異已加入測試。

30 個保留題換成與 45 段開發示例不同的事件，評估參考新增逐題情境要點、0–3 分尺度及具體失敗條件；`evaluation/README.md` 記錄四組已移除的事件重疊。來源中的《Apology》、《Republic》改為 Perseus 精確作品紀錄；IAEA 改為 2024-11-19 的 GOV/2024/61 PDF。十五人物六項設定各有 `fieldEvidence`，虛構職務的內在設定全為設計假設；十五筆 `reviewed` 仍為 false。查證範圍、生成提示及模型可見性記於 `docs/CONTENT_PROVENANCE.md`。

孵化重播使用 `replay` 事件，Quiet／介面及 OS 減少動效均直接定格；轉場新增 `start`／`complete`／`cancel` 回呼。紀錄頁以本地 SVG、文字檔及 25–100% 原生進度條展示附件 fixture。`tsc -b`、16 項 Vitest 及 Vite build（64 模組）通過。Chrome 390×844 已實測柏拉圖兩輪對話至結尾、圖片 fixture 載入與 100% 進度，頁面無水平溢位或破圖。未取得可寫入套件的截圖檔；實機、Safari 及人工來源審查仍待做。

## 本輪人物美術與內容更新

六個使用者手動下載的角色美術 ZIP 已逐一核對父任務提供的 SHA256，安全合併為三組。各組 manifest 對應的 70 個原稿／輸出檔及套件清單中的 18 個顯示檔均通過 SHA256 核對；保留原稿、1024 主圖、256 頭像、圓形裁切、1600×900 與 800×450 封面和 provenance。十五肖像及三封面均在劇場實際載入，國際組為虛構職務肖像，歷史與哲學組為藝術詮釋，皆只供 demo。

45 段多輪示例改為逐人撰寫，30 題保留情境及各自參考答案也改為具體不同題目。六場劇場 18 條主路線的首輪回應與後果已區分；有名字的場景發言標成旁白轉述，避免把其他人物的話歸給玩家選的人物。12 個測試增加示例、題目、參考答案和分支回應唯一性檢查，`tsc -b`、`vitest run`、`vite build` 全部通過，建置共 61 模組。Chrome 390×844 已逐一切換十五人物，15 張肖像及三張封面全數載入，無水平溢位；操作柏拉圖的承諾場景至第二輪。未取得可寫入套件的瀏覽器截圖檔，實機、Safari、Boyi／Jerry 人工審查仍待做。

共同來源 commit `1c9d502f32688bcc3c73e4b99a2cc3724c179047`；分支 `work/ousang-full-kit`，僅改 `collaboration/ui-kit/`。使用者已選 A：本套件用文件指定十五人；沈知衡屬另一套原創長版卡。

## 已實作

- `content/personas.v1.json` 三組各五人，固定 ID、版本、時間界線、動力／視角／語言／邊界及來源 ID。`content/scenarios.v1.json` 六場各三條不同主路徑，每條再有兩個次選擇，均可到達結尾。
- `content/examples.v1.json` 45 段四回合生成示例；`evaluation/inputs.v1.json` 30 個新情境，與 `evaluation/reference.v1.json` 的評分規則／參考方向物理分檔。所有示例、劇情均明示生成或詮釋，沒有冒充引文。
- `content/sources.v1.json` 收錄史書、哲學文本、聯合國／IAEA／IMO／美國國務院公開材料；`reviewed=false`，仍待人工逐條核對。國際組為虛構職務代表，場景是假設，公開背景截止 2024-12-31。
- 共用圖像兩 ZIP 經使用者手動下載至 `C:\Users\t6vmp\Downloads\`。runtime SHA256 `10bd8f58f04739587f8478fc9a4afec0a871022f95277f19f73382373d7ab363`；originals SHA256 `a603a9d32e1d534f71163563a6120ce53689ee75b4e96b12a4943942ef6d35d0`。54 檔安全合併至 `assets/shared-art/`；清單中的 35 個原稿／輸出檔 SHA256 全數吻合，來源 manifest 雜湊 `9086464441b2b0b322c74fb81e4c7cf9b38ff5862b017546cfcdc247363102af`。原稿與輸出、來源紀錄分開保存。
- `AssetGallery` 可切換八項實際 PNG；孵化畫面接靜置、微光、初裂、深裂與 Lumi。App favicon／分享圖已進 `public/`。open 階段顯示深裂圖並明示分離蛋殼缺件，不虛稱圖已完成。
- `src/contracts.ts`、`engine.ts`、`Theater.tsx` 支援選角、選場、來源、分支、回顧、返回、重設、手動匯出與未設定 live adapter 退路；全部與正式資料隔離。

## 驗證與缺口

最近一次 `tsc -b`、`vite build`、`vitest run` 通過：61 模組、3 個測試檔、12 個案例。瀏覽器已驗選角、來源面板、兩輪分支結尾與返回；新接入的蛋、分享圖及圖示裁切在 390×844 均載入，劇場和畫廊無水平溢位或小於 44 CSS px 的可見按鈕。匯出已重試成功，`Downloads/simulation-7b36f892-9310-41a0-a28c-be530d52c958.json` 可讀，包含 `usageScope=demo`、`channel=script`、`exportKind=life-world-simulation`、`importToRealExperience=false`。實際截圖檔、全部新畫面的跨瀏覽器檢查仍待補。

- 十五肖像、三封面已接入並驗證顯示檔雜湊；映射見 `assets/persona-art-map.v1.json`。四項共用美術 `shellsplit`／`completion`／獨立 nourishment 光效／`world-base` 曾遭圖像工具阻擋，沒有檔案，不能標完成。
- 即時 AI 端點、正式 App／DB、實際麥克風／附件上傳未接；Boyi／Jerry 尚未審查。來源的 `reviewed=false` 不等於已人工驗證。
- Library 原生 materialize 在 Windows 缺 `os.setxattr` 而失敗；本次依使用者明確提供的本地 ZIP 讀取，保留原 Library ID `libfile_c1337d18a09081918aaa69c3951f8e1c` 和 `libfile_5fb88fe851e8819198ee4243b4e37f07`，不宣稱本機 xattr 已寫入。
