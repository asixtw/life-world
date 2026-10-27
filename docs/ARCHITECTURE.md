# 架構與資料邊界

## 模組

瀏覽器只呈現與收集輸入；正式資料存於 Python 服務的 SQLite。靜態前端不使用 localStorage 保存人物、session token 或假資料庫。

```mermaid
flowchart LR
 UI[繁體中文 HTML / CSS / JS] --> HTTP[FastAPI / main.py]
 HTTP --> Schema[schemas.py 驗證]
 HTTP --> Service[service.py 領域操作]
 Service --> Identity[security.py]
 Service --> AI[ai.py 整理介面]
 Service --> DB[db.py / SQLite transaction]
 DB --> Migrations[migrations/001_initial.sql]
```

## 資料

`users` 的 owner ID 在 guest → registered 時保持不變。`sessions` 只保存 token 雜湊、CSRF 與失效時間，升級時撤銷舊工作階段並換新 token。

`goals` 與三筆 `actions` 一次建立，並同交易寫入首次 `hatched_at`。星期規律屬於各行動；28 天為預覽視窗，沒有將 28 個布林值當永久排程。單日例外／歷史規則版本尚未開放。

`drafts` 保存原始記錄、帶時區轉 UTC 的發生時間、選填人物與貢獻、revision。正式確認產生 `experiences`、`contributions`、`tasks`、`reward_ledger`，全部放在同一寫入交易。任何步驟失敗都回滾，草稿仍可重試。

小數以標準化十進位字串保存，由 Python Decimal 精確累加；不以浮點 SUM 計算正式進度。前端 progress bar 僅是顯示，數字以後端回傳為準。

`requests` 記錄 owner／operation／request ID／請求指紋／回執。同 key 同內容回原回執，不同內容回 409。SQLite `BEGIN IMMEDIATE` 序列化併發寫入，唯一約束保護每份草稿及積分事件。

`people` 跨目標存在；人物統計是已確認紀錄筆數，**不聲稱是去重後的實際見面次數**。多份草稿是否屬同一次真實相遇，尚待正式事件辨識政策。

`evidence` 以 BLOB 保存，通過 owner／goal 檢查及 Pillow 格式／損毀驗證才能引用。`completions` 必須由使用者明確確認並帶同目標證據；不以 action progress 自動完成。

`notes` 保存 preparation／simulation／message，沒有呼叫正式經歷確認與計分流程。

## 安全與失敗

- 存取前檢查 session 與有效期；所有寫入（啟動 guest 及無既有 session 的登入除外）需 CSRF。
- 過期 session 不能讀寫；帳號切換不合併訪客世界。登入既有帳號前明確確認是否離開原訪客身分。
- 驗證錯誤只回欄位路徑，不回傳原密碼／敏感 input；未知錯誤不暴露 SQL、原文或堆疊。
- 服務綁定 127.0.0.1，限制 Host、拒絕跨來源寫入。HttpOnly、SameSite=strict cookie；Secure 預設關閉以支援本機 HTTP。
- 人物／目標／草稿／佐證逐筆檢查 owner；不相信前端傳來的 owner、積分或完成狀態。
- CSP 阻止外部腳本，使用者文字以跳脫內容呈現；圖片必須通過認證，禁止 MIME 猜測。
- API 與圖片不快取；登出清除前端世界資料並撤銷該 session。

本機模式未包含正式服務的受管驗證、TLS／proxy、全站登入速率限制、媒體掃描、離線同步、備份保留政策或災難復原部署；上線整合見 ROADMAP。
