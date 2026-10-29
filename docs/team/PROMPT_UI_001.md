# LW-UI-001／LW-ASSET-001／LW-AUDIO-001｜歐桑完整交付指令

> 本分支只發布交接文件，程式維持 v0.3.0；本機 v0.4／素材進度未發布。範圍、收件及同步狀態以[本次發布說明](DELIVERY_V1_1_RELEASE.md)為準。
版本：v1.1；更新：2026-10-29。Boyi 已確認本機修訂：P0 操作核心、P1 美術／角色／房間／動效、P2 音效；歐桑製作，Boyi 驗收體驗及聽審，Jerry 審查正式接入。本修訂尚未公告／推送，不把先前任務的通知當成本次已同步。

## 必讀與交付範圍

依序讀[總入口](PROMPT_OUSANG_START.md)、[完整十四類規格](ART_DELIVERY_SPEC.md)、[月份／錄音／附件／校對契約](MEDIA_COMPONENT_CONTRACT.md)、[流程狀態](FLOWS_AND_STATES.md)及[人物模組任務](PROMPT_SIMULATION_001.md)。尺寸、數量、圖層、音效及驗收以完整規格 v1.1 為本輪依據。

既有合格成果沿用，每項分開記錄「沿用／修改／新增」與「待驗收／已驗收」。先對照實際候選包及已提供的本機契約，附來源 commit／SHA，不因舊文件寫未交付就重新生成整包，也不自行認定候選已符合新版。

P0、P1、P2 分批自測、修正、交審，最後以同一個可啟動專案完整交齊。十四類及人物模組均保留，P2 不是取消；正式人物設定與模擬範圍仍依 LW-SIM-001。

## 工具與工作區

使用可實際讀寫／執行專案的 IDE，回報帳號實際可用的程式、圖像及音效工具版本，不因 Pro 推定已取得 API、權限或輸出工具。Dot 可整理目標及核對證據；無存取權時不宣稱監控 IDE。

分支 `work/ousang-full-kit`，僅在 `collaboration/ui-kit/` 製作獨立 React＋TypeScript 元件、資料、資產、測試及交接。沿用正式 App 的 [tokens](../../app/static/tokens.css)及[樣式](../../app/static/styles.css)，不改根目錄工具鏈、正式 App／DB／API 或確認交易。

## 可直接複製給 Codex

```text
你正在協助歐桑完成 Life World 的 LW-UI-001／LW-ASSET-001／LW-AUDIO-001，
並與既有 LW-SIM-001 人物／劇場包整合成同一可啟動交付專案。
Boyi 確認產品、視覺與聲音，Jerry 審查契約及正式接入，歐桑負責製作與證據。

先切至 App Repository 根目錄，讀 AGENTS.md、docs/SPEC_INDEX.md、
docs/STORAGE_RULES.md、docs/team/PROMPT_OUSANG_START.md、
docs/team/ART_DELIVERY_SPEC.md（v1.1）、docs/team/MEDIA_COMPONENT_CONTRACT.md、
docs/team/FLOWS_AND_STATES.md、docs/team/PROMPT_SIMULATION_001.md。
核對 Boyi／Jerry 提供的完整來源 commit／可分享快照與文件版本。
新版尚未發布遠端時，不能把舊 main 或舊規格當成已同步。

先盤點已交候選，逐項記錄 P0／P1／P2、十四類、資產 ID、沿用／修改／新增、
驗收狀態、證據、缺口與限制。可用成果沿用，不重新生成所有圖像。
按批次製作、自測、自修、交審，最後整包交齊；小樣僅內部檢查。
實質產品機制、Lumi 識別或正式技術方向衝突才請決策，不默默縮減清單。

P0：完整按鈕／輸入／四分頁／卡片／面板／通用狀態，實際月份與週排程，
錄音／附件／校對／草稿及一致 SVG 操作圖示。
月是檢視週期，不是預填期限；星期快選套用可編輯目標期間，安排不算完成。
保留三個習慣、名稱僅更正、單位固定、新用量按目標時區隔天生效。
錄完後明確上傳轉文字，試聽可選，選檔及停止均不自動上傳。
處理權限拒絕、格式／容量、儲存失敗、取消、重試、晚回應及版本衝突。
原素材／辨識原文／校對文字分開，名片不自動建立人物、見面或成果。
Button 傳遞 type、aria-*、disabled、事件與 ref，CSS 不覆蓋正式 App。

P1：App 圖示／縮圖／裁切，六種 Lumi 姿勢，蛋全狀態及可操作孵化，
獨立左右蛋殼／Lumi／光效／陰影，一般回饋用無蛋殼 Lumi，
同房間日間／安靜版與手機構圖，空白狀態、指定轉場、十五頭像與三封面。
尺寸、狀態 ID、格式與數量依完整規格，不用空路徑或圖片取代互動元件。
Lumi 只在首次目標確認後出現，跳過、重播及關閉均不改進度或獎勵。

P2：ui-tap、draft-saved、experience-confirmed、first-hatch、goal-completed，
每種兩個候選，48 kHz WAV 原稿及 AAC／M4A、Ogg 播放版，附使用依據。
聲音預設關閉仍屬候選預設；Quiet 無聲、頁面不自動播放、失敗不阻擋操作。
沒有音效工具或不能匯出真實檔案時明列阻礙，交 Boyi 協調，該項保持未完成。

全部在 work/ousang-full-kit 的 collaboration/ui-kit/ 製作，
元件交真正 React／TypeScript／CSS／SVG、typed props／回呼／狀態／範例。
保留正常／焦點／停用／載入／錯誤，支援鍵盤、44 CSS px 觸控目標與長內容。
日間／Quiet／減少動效可展示，反覆進出清理計時器、音軌及 overlay。
來源／角色／回執切換不得發出舊完成回呼。fixture 明示，不假裝已串接。
不更換 AI 廠商、不做正式 DB／獎勵交易；模擬不進正式人物、進度或積分。

附 assets/manifest.json，填 ID、路徑、用途、尺寸／格式／大小、版本、
主題／狀態、來源／工具／使用依據、alt、錨點及事件，原稿和顯示版分開。
共用資產標 product_candidate，人物／情境標 demo。
新增與修改程式採關鍵邏輯繁體中文註解，遵循既有 TDD 與正常／異常／邊界驗證。
實際操作 390×844 及桌面，附命令、結果、截圖與實機／Safari 未驗事項。
依 docs/team/HANDOFF_TEMPLATE.md 填逐項交付矩陣、缺陷、重跑及 Jerry 接入說明。
未執行不得寫通過，缺項維持未完成，不降低驗收標準。
不要自行合併、部署、Push、代發公告或修改正式 App／資料庫／認證設定。
```

每批審查與最終整包審查分開記錄。文件、素材生成、gallery 驗收及正式 App 接入各有狀態，不互相替代。
