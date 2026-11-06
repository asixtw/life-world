# GCP-143 AI 隔離候選（未啟用）

這是獨立分支的本機工程候選，不是已部署功能。既有 Gemini generateContent Adapter 已移至 app 共用，model_eval 仍相容；不改 Dockerfile、Cloud Build、Gallery 或資料表。

| 功能 | 候選實作 | 真實 API | Browser | PostgreSQL |
|---|---|---|---|---|
| 經歷整理 | 既有 suggest → 嚴格 summary/tasks JSON → 可編輯 → 既有 confirm | BLOCKED | NOT RUN | NOT RUN |
| 確認後任務建議 | 讀本人已確認經歷 → 候選 → 使用者確認 tasks；requests 冪等、不重複獎勵 | BLOCKED | NOT RUN | NOT RUN |
| 圖片／名片／語音 | 沿用 media 驗證、大小/時間上限；inlineData → 待校對文字 | BLOCKED | NOT RUN | NOT RUN |
| 人物模擬 | 本人指定的 confirmed 且仍有來源的 facts → 私人模擬；不寫 facts/notes | BLOCKED | NOT RUN | NOT RUN |

隔離自動測試使用傳輸替身，僅證明契約／權限／人工確認，不代替真實模型能力。

## API

- 既有 POST `/api/drafts/{id}/suggest`：真實 Provider 啟用時回傳 summary、tasks、provider、model、applied=false。未設定仍明示本機手動原文。
- POST `/api/experiences/{id}/task-suggestions`，`{consent:true}`：僅讀本人已確認經歷；回傳候選、不寫 tasks。
- POST `/api/experiences/{id}/tasks`，`{request_id,tasks,confirmed:true}`：人工選擇/修改後建立；沿用既有 requests/tasks，重送不重複，points_awarded=0。
- POST `/api/people/{id}/simulation`，`{consent:true,fact_ids:[...],message}`：只用仍有來源的 confirmed facts；回傳 simulation=true、applied=false，不把模型猜測寫成人物事實。
- 既有 POST `/api/media/recognize`：啟用後使用同一後端模型與額度，圖片／名片／語音都是人工校對草稿，不保存上傳內容。

所有 AI 路徑均需 registered Owner、既有 Session/CSRF/Owner isolation；模型呼叫不持有 SQL 交易鎖。

## 啟用條件（Owner 尚未核准，不執行）

後端環境需明確配置 `LIFEWORLD_AI_PROVIDER=gemini`、已核准模型 ID、`LIFEWORLD_AI_CALLS_APPROVED=true`，及透過既有後端 Secrets 注入 `LIFEWORLD_AI_API_KEY`。前端/Git 不接收 key。沒有 key 不宣稱 configured；有設定也只標 configured_not_verified，不能當作真實 API PASS。

每次呼叫先以既有 requests 表預留一次 attempt 與最壞情況金額；PostgreSQL 共用 advisory lock／SQLite 寫鎖保護全站額度。失敗不釋放預留額，不自動重送、不輪替 key，不把未知帳單寫成零。預留額必須由 Owner 根據實際模型定價與最大輸入/輸出確認；本候選不宣稱已取得供應商帳單／免費額度／每模型能力。

最小首批授權提案：指定一個已核實可用的 Gemini 模型，僅合成內容，最多 5 次全站呼叫、每 Owner 每日 2 次，文字輸入 8KiB、媒體 1MB、輸出 512 tokens；實際費用總上限與每次最壞預留額需 Owner/計費管理者核定後才設定 `LIFEWORLD_AI_BUDGET_MICROUSD`／`LIFEWORLD_AI_RESERVATION_MICROUSD`。目前兩者預設 0，正式呼叫停用。調高額度或傳送真實人物/媒體需獨立核准。

尚需：模型/配額查核、Runtime Secret 版本與存取權核准、費用上限、真實 API 合成 smoke、手機/桌面實際操作、隔離 PostgreSQL API 整合驗收。未讀任何 Secret 值，未呼叫外部付費 API。
