# 本機 API

本輪新增：`GET /api/media/capabilities` 及 `POST /api/media/recognize`，提供無副作用的辨識候選介面；需要 session／CSRF，預設服務未設定時回 503。素材不另存在伺服器，完整欄位、限制與錯誤見[素材整合契約](team/MEDIA_COMPONENT_CONTRACT.md)。

人物標記介面於 2026-10-29 改稱「星標」；`followed`／`followed_only` API 欄位與既有排序語意保持相容，沒有通知對方或追蹤動態能力。

## v0.4 單一目標與習慣

2026-10-29 增量：`schedules[]` 可選 `title`（名稱更正）、`per_occurrence`（正數用量字串）、`expected_effective_from`（畫面確認的 ISO 生效日）。單位及行動 ID 不可更換；省略新增欄位維持原值。

用量依固定目標時區隔天生效，需有明天起的安排。同日最後確認值覆蓋明日版本，回顧保留前後快照；衍生 `target` 按日期量加總，舊明確總量不變，不寫貢獻／獎勵。回傳 `actions[].quantity_versions[]`，含 `effective_from`、`quantity`、`created_at`；`per_occurrence` 為目標今天適用量，可能不同於明日量。未定起日舊標準以 `0001-01-01` 標記，畫面稱「原始標準」，不宣稱真實起日。日曆回傳新增 `planned_quantities`，鍵為已安排 action ID，值為該日用量字串。

無後續執行日期回 `422 no_future_occurrence`；`expected_effective_from` 與伺服器隔天不符回 `409 effective_date_changed`，須重新核對；版本衝突仍 `409 revision_conflict`。前端會帶生效日，新呼叫端應同樣提供以防跨午夜誤認。[驗收](HABIT_WIREFRAME_ACCEPTANCE.md)。

新建 `POST /api/goals` 必須提供 `deadline`（當地 ISO 日期）與恰好三筆 `actions`。每筆有 `title`、`dates`（至少一個不重複的期間內日期），`per_occurrence` 預設 `"1"`、`unit` 預設 `"次"`，`cycle` 為 `month`／`week`；`weekdays` 保存星期快選。舊 `target`／`level` 可保留，新介面不要求總量或養分等級。無 `target` 時依每次量 × 安排天數計算顯示總量，絕不寫成已完成。

| 方法 | 路徑 | 契約與用途 |
|---|---|---|
| GET | `/api/goals/{id}` | 回傳 `start_date`、`deadline`、固定 `schedule_timezone`、目標時區 `today`、`revision`、`allowed_actions`、習慣日期、回顧及待處理貢獻 |
| GET | `/api/goals/{id}/calendar?start=…&end=…` | 查詢目標期間內最多 367 個含首尾日期；預設實際一個月，不固定 28 天 |
| POST | `/api/goals/{id}/review` | `request_id`、`expected_revision`、真正布林 `confirmed:true`、`decision`、選填 `reflection`；決策為 `end`／`extend`／`setup`／`schedule` |
| POST | `/api/goals/{id}/pending/{pending_id}/accept` | `request_id`、`expected_revision`、正數 `quantity`、真正布林 `confirmed:true`；逐筆採計，不重新發獎 |
| POST | `/api/goals/{id}/complete` | 沿用佐證與明確成果確認；新式目標另必須帶 `expected_revision`，舊目標與舊成功請求保留相容 |

除 `end` 外，回顧需提供三筆 `schedules`，各為 `action_id`、`dates`、`weekdays`、`cycle`；`extend`／`setup` 必選 `deadline`。`schedule` 不可改截止日。過去安排由後端保留，不接受改寫；延長的新截止日須晚於原日且不早於今天。固定挑戰時區不隨個人時區更動。

公開狀態：`active`、`awaiting_review`、`needs_setup`、`completed`、`ended`。SQLite 原 `status` 的 active／completed 約束保持相容，結束以 `ended_at`／`end_reason` 記錄；所有 App 查詢統一轉為公開生命週期。`end_reason` 為 `early_end`／`expired`。

到期或待補設定時，經歷確認仍產生一次正常獎勵，貢獻進 `pending_contributions`；其狀態為 `pending`／`accepted`／`unapplied`，保留原數量與採計量。目標結束／完成後未採計項目標記 `unapplied`；逐筆採計須處於進行中，發生日期也必須在目標期間。

新目標有未結束目標時回 `409 open_goal_exists`；版本衝突為 `409 revision_conflict`，新成果確認缺版本為 `422 revision_required`。相同成功請求先回既有回執；不因後來到期或結束重建資料。新建立表單與 API 呼叫端須一起更新，不能再送沒有截止日的舊建立格式。完整可執行契約見 [OpenAPI](openapi.json)。

## v0.3 交會 API

草稿／確認新增選填 `story`，包含標題、多位參與者（`person_id`／`interacted`）及原文提及（`name`／`start`／`end`／選填人工 `person_id`）。正式確認另需 `story_reviewed: true`；位置按 Unicode 字元而非 UTF-16 計算。省略新欄位維持舊確認去重指紋。

| 方法 | 路徑 | 用途 |
|---|---|---|
| GET | `/api/connections` | 同帳號、人物焦點、角色分流、時間排序與分頁 |
| GET | `/api/connections/stories/{id}` | 原文、摘要、參與、提及；`manage=true` 為本人管理模式 |
| PUT | `/api/connections/stories/{id}/people` | 人工確認／更正角色，不重發積分 |
| POST | `/api/connections/mentions/{id}/match` | 人工配對、取消或拒絕，不改參與身分 |
| POST | `/api/connections/stories/{id}/availability` | 撤回／恢復探索展示，不刪原文 |

寫入攜帶 `request_id`、`expected_revision`，角色及身分核對另需 `confirmed: true`。舊版本或同 key 不同內容回 409，無效片段回 422，不可存取或已撤回的探索來源回 404。完整邊界見 [CONNECTIONS](CONNECTIONS.md)，實際 schema 見 [openapi.json](openapi.json)。

## 既有 API

完整 schema 與錯誤型別以 `openapi.json` 為準。API prefix 為 `/api`。

| 方法 | 路徑 | 用途 |
|---|---|---|
| GET | `/health` | 狀態及本機模式 |
| POST | `/auth/guest` | 開始／恢復目前 guest session |
| GET | `/auth/me` | owner、身份、Bio、Lumi 狀態與 CSRF |
| PUT | `/profile` | 保存稱呼、Bio、IANA 時區 |
| POST | `/auth/claim` | guest 以本機帳號密碼升級，不改 owner |
| POST | `/auth/login` | 本機帳號登入；訪客衝突需顯式處理 |
| POST | `/auth/logout` | 撤銷 session |
| GET | `/state` | 同一資料庫快照的世界資料 |
| POST | `/goals` | 確認建立目標、三行動與首次 Lumi |
| GET | `/goals/{id}` | 目標、Decimal 累計及佐證清單 |
| GET | `/goals/{id}/calendar` | 依目標固定時區與實際日期查詢安排，參數見 v0.4 契約 |
| POST | `/experiences/drafts` | 保存原始記錄與選填關聯 |
| GET | `/drafts/{id}` | 回讀草稿及 revision |
| PUT | `/drafts/{id}` | 帶 expected_revision 修改未確認草稿 |
| POST | `/drafts/{id}/suggest` | 本機手動整理候選，不直接套用或計分 |
| POST | `/drafts/{id}/confirm` | 人工確認，一次提交經歷／貢獻／任務／積分 |
| POST | `/people` | 建立人物，需 registered |
| PATCH | `/tasks/{id}` | 勾選待辦，不增加貢獻或積分 |
| POST | `/goals/{id}/evidence` | multipart 圖片上傳，欄位 `file` |
| GET | `/evidence/{id}` | 通過 owner 驗證的圖片內容 |
| POST | `/goals/{id}/complete` | 引用證據並明確手動確認成果 |
| POST | `/notes` | 保存私人準備／演練／訊息筆記 |

## 認證

Cookie `lw_session` 為 HttpOnly。先呼叫 guest 或 login，再以回傳 `csrf_token` 送出 `X-CSRF-Token`。每次升級／登入可能輪替 cookie 與 CSRF，前端必須更新。正式資料端點不接受前端 owner ID。

## 確認經歷

```json
{
  "request_id": "穩定且同一提交重試沿用的代碼",
  "expected_revision": 1,
  "summary": "由使用者確認的摘要",
  "person_id": null,
  "contributions": [{"action_id": "目前目標的一項行動 ID", "quantity": "0.5"}],
  "tasks": ["下一次想做的事"]
}
```

積分由開發 policy 產生，不接受前端傳分數；原始文字取自草稿，不由摘要覆寫。`occurred_at` 於草稿保存時驗證帶時區且不在未來，過去日期不設回溯期限。`created_at` 為伺服器確認時間。

## 主要錯誤

一致格式：`{"error":{"code":"revision_conflict","message":"草稿已有新版，請重新核對。"}}`。

- 401：無／失效 session、登入憑證不符。
- 403：CSRF／Origin 拒絕、訪客人物操作需升級。
- 404：資料不存在或不屬目前 owner，不洩漏他人資料。
- 409：先完成 Bio／首目標、revision／idempotency 衝突、已確認、訪客世界衝突、未決政策。
- 413：圖片大小超過 policy。
- 415：媒體格式不符或損毀。
- 422：欄位、日期、小數、行動歸屬、佐證／人工確認條件不符。
- 503：整理 provider 失敗，仍可用手動確認。
- 500：操作完整回滾，沒有成功回執；請沿用同一提交 ID 重試。

參考實作方式：[FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)、[Request Files](https://fastapi.tiangolo.com/tutorial/request-files/)。


## v0.2：人物 360 與互動來源

- `GET /api/people`：共用星圖／收藏冊查詢，支援 q、category、followed_only、sort、limit／offset。排序 priority 依星標人物、進行中目標、最近互動、名稱／ID；含已確認的維度標籤搜尋。
- `PATCH /api/people/{id}`：expected_revision 加欲更新的 name／roles／tags／category／followed／notes／common_context；舊 role 字串仍回傳以相容初版。
- `GET /api/people/{id}/overview`：person、stats、四組 facts、fact_history、interactions、goals、tasks、connections、notes。
- `GET /api/people/{id}/interactions`：可用 kind 篩選 in_person／call／message／other／unknown。
- `POST /api/people/{id}/facts`：request_id、dimension、value、description、evidence_type、source_experience_ids、confirmed=true，可指定 conflicts_with。來源必須是可存取且與該人物相關的已確認經歷。
- `GET /api/people/{id}/facts/{fact_id}/evidence`：回傳人物資訊及原文、摘要、發生時間、證據類型。
- `POST /api/people/{id}/facts/{fact_id}/resolve`：expected_revision；明確採用這項資訊，其他同組衝突保留為 archived。
- `POST /api/people/{id}/facts/{fact_id}/sources/revoke`：expected_revision、experience_id；撤回此項資訊的來源引用，保留原始經歷；沒有有效來源時資訊不列為已知。
- `POST /api/people/{id}/goals`：request_id、goal_id、label；手動關聯不宣稱對方已承諾合作。
- `POST /api/people/{id}/connections`：request_id、other_person_id、label、source_experience_ids；明確建立共同關係，不自動推論。
- `PATCH /api/interactions/{id}`：expected_revision、kind；分類不改積分。
- `POST /api/interactions/{id}/merge`：request_id、expected_revision、source_event_ids；保留主要事件日期與類型，多筆原經歷不刪除，積分不重算。

經歷 Confirm 增加 interaction_type（預設 unknown）、interaction_event_id（關聯同一次互動）、person_updates（只有 selected=true 才更新的四維度候選）。人物資訊、互動、經歷與積分共用交易及 owner 驗證；舊請求的預設欄位不改動原去重指紋。

私人筆記增加 source_experience_ids；來源由後端檢查。筆記、模擬與訊息草稿不呼叫真實經歷確認與記帳。
