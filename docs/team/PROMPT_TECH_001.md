# LW-TECH-001｜全端整合與部署審查指令

主責：全端夥伴，技術整合與程式審查。使用者確認產品與範圍，資料夥伴核對模型。第一輪可與 UI 獨立展示同步進行；此包不建立雲端資源。

```text
任務：LW-TECH-001，Life World 技術契約與部署審查。
你是整合與程式審查負責人，不被假定全職承包全部功能。
先回報可投入時間與實際可用環境，閱讀同一來源快照的
docs/team/BASELINE.md、FLOWS_AND_STATES.md、INTEGRATION_REVIEW.md、
既有 docs/API.md、ARCHITECTURE.md、OpenAPI 與實際程式。

本輪方向：React＋TypeScript／Vite／React Router；保留 Python FastAPI；
SQLite 遷移 PostgreSQL；前後端全放 GCP，POC 不做原生 App。
LLM／STT／VLM 介面分開，不預設供應商。使用者可提出後續修改。

交付一：契約差異
- 區分現有端點與未實作能力，保留 /api 相容及來源／ID 語意。
- 定義排程週期、版本與日期；附件擁有權／來源與刪除；
  辨識 job 狀態、取消、重試、逾時及重送；媒體單獨草稿；
  名片人物草稿與人工配對，不強迫捏造一次見面。
- 前後端同一份 schema／錯誤／去重／revision／人工確認契約，
  TypeScript 型別由 OpenAPI 對齊，避免兩套格式。
- 確認交易仍原子保存經歷、貢獻、任務與唯一獎勵；候選不直接入帳。

交付二：部署與儲存分工
- Cloud Run Web 同源提供 React 靜態產物與 API；Cloud SQL PostgreSQL
  保存正式資料；私人 Cloud Storage 保存素材；Secret Manager 保存秘密。
- 長辨識工作規劃 Cloud Tasks 與受認證的私人 worker，不靠 Web 請求
  結束後的背景執行；任務狀態／重試與錯誤持久化並防重複正式寫入。
- 列容器、migration 執行方式、服務帳號／最小權限、連線池與實例上限、
  HTTPS／trusted proxy／Host／Origin／Secure cookie 與 CSRF。
- 不把 SQLite 放 Cloud Run 暫存檔案系統，也不把 DB 放物件儲存當磁碟。
- 測試與試用環境隔離，列健康檢查、無敏感原文的日誌、備份／還原、
  資料相容的版本回復、建置／測試／發布步驟與實際資源費用估算依據。

交付三：試用帳號
- 第一輪沿用帳密，補邀請與一次性復原碼；沿用現有 Argon2，
  邀請也限制首次 guest 入口，不能繞過註冊限制造訪 AI 服務。
- 復原碼只存雜湊、使用一次、重設撤銷舊 session 且保留 owner；
  登入／復原需要失敗保護，不洩漏帳號是否存在。
- 第三方身分服務、GCP project／region／domain／權限與 AI 端點未提供者
  明列待填；不要憑空配置或索取使用者在聊天貼密碼與金鑰。

交付四：審查結論
每個契約寫「可沿用／需變更／待決／阻擋」，附依據、負責角色、
影響功能與驗收案例。先出報告，不直接重寫主程式、執行遷移、
建立付費資源或推送主分支。後續程式變更依 pytest TDD、中文註解、
瀏覽器驗收及 HANDOFF_TEMPLATE.md 交接；未執行的測試如實標示。
```

## 對照文件

- [Cloud Run／Cloud SQL 官方整合](https://docs.cloud.google.com/sql/docs/postgres/connect-run)
- [Cloud Run 容器檔案系統限制](https://docs.cloud.google.com/run/docs/container-contract#file_system_access)
- [非同步工作](https://docs.cloud.google.com/run/docs/triggering/using-tasks)
- [Secret Manager 與 Cloud Run](https://docs.cloud.google.com/run/docs/configuring/services/secrets)

以上作為審查入口，實作前須核對當時官方限制與團隊環境；本文件不代表已配置上述服務。
