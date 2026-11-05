# 語音／圖片 Provider 現況與 11/13 接續

日期：2026-11-05。C 線盤點，不新增供應商、不呼叫付費服務、不阻擋今日 Public Alpha 的文字核心。依 Owner 最新決定保留積分累積及 reward_ledger，沒有消費／兌換；舊素材契約中的「不整合積分」不是本輪產品決策。

## 現有可用邊界

| 能力 | 現況與限制 |
|---|---|
| 錄音控制 | `app/static/media.js` 實際使用 getUserMedia／MediaRecorder；可停止、取消、可選試聽及明確上傳。不是即時轉錄。真實 iOS／Safari 麥克風、編碼與時長尚待實機驗證 |
| 素材與草稿 | 圖片／截圖／拍照／名片／音檔可選取；IndexedDB 按 owner／草稿上下文保存，非雲端素材備份或跨裝置來源儲存；原文與手動校對分開，確認前不更新正式經歷 |
| ASR／VLM | `create_app` 預設 `app.state.media_provider=None`。沒有已接上的真實供應商，回503；測試成功回應是注入替身，不是真實辨識 |
| Provider契約 | `MediaProvider.extract(*, kind, mime, content: bytes) -> str`；同步介面、回傳非空且不超過20,000字的候選文字，服務商中立 |
| 後端請求 | GET `/api/media/capabilities` 需session；POST `/api/media/recognize` 需完成引導、session／CSRF／同來源。圖片PNG/JPEG；音訊WAV/WebM/Ogg/MP4/MP3。上限取DemoPolicy，並另限整個multipart大小 |
| 成功語意 | `text`、`applied:false`、`server_retention:none`、kind/mime/size/SHA256；不建立人物／經歷／任務／進度／獎勵。一般素材經人工核對才加入文字，再走既有正式確認交易 |
| 名片 | 校對及複製人物候選，不自動建人物、計見面或更新成果 |
| 逾時與保存 | HTTP等待30秒；取消等待不代表撤回供應商工作／費用。multipart請求結束關閉暫存，不將素材保存到SQLite或靜態目錄；`server_retention:none` 不代表未選供應商的保留承諾 |

## 11/13 待完成

1. Owner 選定 ASR／圖片提供者與預算、秘密注入、資料外傳與供應商保存承諾；不讀取或要求分享金鑰。
2. 真實adapter需驗證完整音訊解碼／時長，明確SDK網路逾時、取消、可計費重試及費用上限。現行容器標頭檢查不能宣稱可完整解碼。
3. 真實手機格式與上傳驗收：iOS／Safari、相機方向、HEIC轉換／拒絕文案、權限拒絕、中斷、重錄、失敗保留。
4. 正式雲端素材／跨裝置來源、保存／刪除政策、名片建檔及配對仍另審；文字跨裝置回讀不能冒充原錄音／圖片亦同步。
5. 公開 Alpha 的未核准處理端點應由 A 線伺服器模式控制，不僅隱藏UI。C 線沒有修改Alpha模式或app/main.py。

## 本輪實際驗證

命令：`python -B -m pytest tests/test_media.py tests/test_media_provider_boundary.py -q --tb=short -p no:cacheprovider`，使用本機隔離venv、合成PNG／WAV及注入Provider，無外部API或憑證。

結果：**21 passed、0 failed、0 skipped**。既有20案例涵蓋格式、空白／超量、四種素材、provider錯誤遮罩、未設定503、CSRF／session／引導及正式domain不變；新增1案例驗證一個App注入provider不會洩漏到另一個App，兩個App的世界均不被辨識操作改動。

初次新案例因未注入固定時鐘，測試fixture的舊安排超出當日而失敗；補齊與fixture一致時鐘後通過。這是測試準備錯誤，不當作新功能TDD紅燈。既有提供者隔離能力本來已存在，本輪為邊界回歸，不新增正式辨識功能。

未做實機、真實ASR／VLM品質、供應商費用或雲端保存測試；沒有CloudSQL、部署或Git發布動作。
