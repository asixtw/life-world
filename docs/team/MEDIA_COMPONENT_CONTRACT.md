# 月份、錄音、附件與校對｜本機整合契約

> 本分支只發布交接文件，程式維持 v0.3.0；本機 v0.4／素材進度未發布。範圍、收件及同步狀態以[本次發布說明](DELIVERY_V1_1_RELEASE.md)為準。
更新：2026-10-29。Boyi 本輪授權補強並接入現有 App；維持 Python／原生前端、四主分頁及原有視覺。沒有將歐桑的展示 gallery 併成正式導覽，也未遷移 React、資料庫或雲端。驗證見本輪驗收（本機待發布：`../MEDIA_COMPONENTS_ACCEPTANCE.md`）。

完整 UI、美術、房間／角色及音效的本輪交付優先級，見[完整規格 v1.1](ART_DELIVERY_SPEC.md)；本文件維持月份／素材／校對及辨識契約邊界，不因規格修訂而改動正式 API。

## 1. 分工與完成界線

- 本機已接入：實際日期月／週元件、真實麥克風控制、本機檔案預覽與保存、校對、重試、取消、同裝置來源回看及草稿入口。
- 歐桑：以這份狀態／事件契約補齊 React 候選元件，仍需獨立交付與審查；本輪不宣稱已代替他交付 React 套件。
- Jerry：審查供應商 adapter、正式格式／大小／時長、上傳工作生命週期、私人雲端儲存及留存／刪除；未決事項不自動成為正式規格。
- 外部 STT／VLM 未接：預設回覆明確 503，使用者可手動校對或保留素材；不產生假的辨識成功、上傳保存回執或正式事實。

## 2. 月份排程

直接使用既有 `GoalsUI` 日期元件：月是預設編輯檢視，週可切換；同一組實際日期共用選取狀態。期限仍由使用者選，月份不等於挑戰期限。

移植到 React 時，容器應提供 `startDate、endDate、selectedDates、cycle、cursor、disabledDates`，由元件發出 `toggleDate、selectWeekday、applyPreset、clear、changeCycle、changePeriod`。星期快選作用於**整個目標可編輯期間**，須明示範圍；不能只畫七顆 checkbox 取代日期資料。

開始後維持三個習慣；名稱僅更正，單位／用途固定；新用量依目標固定時區隔天生效，今天與歷史不重算。排程只代表打算做，不能直接更新進度／獎勵。月底、閏年、跨年、期限外禁選與版本衝突沿用現有規則及測試。

## 3. 錄音與附件狀態／事件

| 元件 | 容器輸入 | 操作事件 | 不變條件 |
|---|---|---|---|
| 錄音 | idle／requesting_permission／recording／ready／processing／review／error、時長、錯誤 | start、stop、cancel、remove、upload | 錄完再明確上傳，不是即時轉錄；試聽可選，不自動播放 |
| 附件 | 本機 Blob、種類、預覽、檔名、大小、處理狀態、錯誤 | select、remove、upload、cancel、retry | 選檔不連外；進度未知時用不定進度，不製造百分比 |
| 校對 | 辨識原文、使用者文字、已核對旗標、素材種類 | edit、confirmText、apply／copy | 編輯取消先前核對；原文不變；等待期間的編輯不被晚回應覆蓋 |

真實控制器位於 `app/static/media.js`。麥克風、IndexedDB、fetch／AbortController 由容器處理，展示元件不直接決定權限、資料保存或獎勵。離開、取消或移除後，遲到的授權與辨識回應不能重新啟動錄音或復活素材；停止／中斷後釋放音軌。

通用 React Button 應繼承原生 button 屬性，傳遞 `type、aria-*、disabled、事件、ref`；不要丟掉表單提交或目前分頁語意。gallery 測試控制列不進產品。圖片／音效／破蛋素材採個別審查，不引入全域 CSS 覆蓋現有 App。

## 4. 本機來源與人工確認

- 選取素材及文字保存在帳號 owner＋草稿上下文區分的 IndexedDB；明示「已保存在此裝置」，不宣稱同步或加密。清除網站資料／更換瀏覽器會失去素材；共用瀏覽器設定檔也不是帳號之間的安全儲存邊界。
- 純素材可從紀錄頁的「此裝置尚未整理的草稿」接續，不強迫輸入假文字；「保留此裝置草稿並離開」必須等本機寫入成功。
- 文字草稿仍使用既有伺服器 API。成功後，以 draft ID 連結同裝置素材，裝置表單另綁定伺服器 revision；有新版時載入新版原文並保留素材，不讓舊快照覆蓋。核對頁及正式經歷可回看同裝置來源。素材本身不進 SQLite、靜態目錄或 Git。
- 本機寫入失敗／配額不足會告知保持此頁；沒有素材的純文字伺服器保存不依賴 IndexedDB。若文字已到伺服器、素材連結失敗，重試更新原草稿，不重新建立另一份。
- 一般素材的校對文字經勾選及「加入經歷文字」才帶入原始輸入，仍需既有草稿及正式確認交易；此操作不增加任何進度或獎勵。
- 名片維持本機人物資料草稿及複製校對文字；不直接帶入經歷、建立人物、計見面或發獎。正式人物配對／建檔及雲端來源關聯仍待下一輪。
- 沒有擅自設定自動到期刪除；使用者可移除素材。這不是正式素材留存政策，也不具備雲端備份／跨裝置恢復。

## 5. HTTP 與提供者介面

### `GET /api/media/capabilities`

需要目前 session；回傳 `recognition_available、max_bytes、image_types、audio_types、server_retention`。`max_bytes` 沿用 `DemoPolicy.max_upload_bytes`，預設 5 MiB，是本機護欄，不代表已核准音訊五分鐘／20 MiB 等前輪候選限制。

### `POST /api/media/recognize`

需要已完成首次引導的 session、CSRF 及同來源。multipart 欄位：`file`、`kind`（`audio／image／screenshot／card`）。只在使用者明確按上傳時呼叫。

```json
{
  "text": "辨識原始候選，仍需人工校對",
  "applied": false,
  "server_retention": "none",
  "source": {"kind": "audio", "mime": "audio/webm", "size": 1234, "sha256": "完整 SHA-256"}
}
```

圖片支援 PNG／JPEG，檢查內容及尺寸；音訊支援 WAV／WebM／Ogg／MP4／MP3，做容器識別，完整音軌／時長／解碼仍須由正式 adapter 驗證。檔案拒絕空白、路徑型檔名、類型不符及超量；總 multipart 請求另限單檔上限＋64 KiB，在解析／磁碟暫存前檢查，包含 chunked 傳輸。

錯誤維持 `{error:{code,message}}`：401／403 身分與 CSRF、409 引導未完成、413 超量、415 不支援／損毀、422 欄位、503 未設定提供者、502 辨識或輸出失敗、504 等待逾時。伺服器不回顯提供者例外、金鑰或素材本文。

後端啟動後可由組裝程式注入 `app.state.media_provider`，實作同步 `extract(*, kind, mime, content: bytes) -> str`。沒有指定供應商或前端金鑰；adapter 須回傳非空且不超過 20,000 字的文字。每次辨識不寫 SQLite、人物、經歷、任務、貢獻或帳本，multipart 暫存檔在請求結束時關閉。

本機端點只提供暫時處理，不承諾取消遠端工作。HTTP 等待上限 30 秒不代表能中止供應商的背景執行；實際 adapter 必須設定 SDK 的網路逾時、取消、重送／計費與資料處理政策。`server_retention: none` 僅指本 App 不另存素材，不代替未選供應商的保留承諾。

## 6. Jerry 合併前的待審清單

1. 正式素材儲存、跨裝置來源關聯、刪除／帳號清除與備份回復政策。
2. 供應商、憑證注入、上傳格式與時長、工作 ID／去重／取消、逾時及費用限制。
3. 真實手機權限、iOS／Safari 音訊格式、拍照及圖片方向／HEIC 處理；目前不假裝已支援 HEIC。
4. 名片正式人物配對／新增及獨立來源保存；圖片／錄音的完整來源不可僅以文字雜湊取代。

以上未決不影響文字人工確認閉環，但未完成前不能宣稱正式多模態雲端服務可交付。
