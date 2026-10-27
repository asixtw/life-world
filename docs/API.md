# 本機 API

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
| GET | `/goals/{id}/calendar` | 依使用者時區預覽未來 28 天 |
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
