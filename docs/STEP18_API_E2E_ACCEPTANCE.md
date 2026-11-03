# Step 18｜API 雲端端對端驗收準備與本機證據

2026-11-03。由最新 fetch 的 `origin/main` **5f015a616f3497a4fb948b143b09d8e625005f74** 建立 `C:\LifeWorld_project\life-world-api-e2e`，短期分支 `work/api-e2e-acceptance`。成果留在獨立工作樹供審查；本輪沒有 Commit／Push／Merge／GCP 操作，既有 dirty 工作樹保留。

## 使用者執行入口

[完整 Console／環境變數／正式指令／清理操作](../deploy/README.api-e2e.md)。實際雲端驗收須由使用者逐步執行；本機沒有連 Cloud SQL／Cloud Run，也沒有取得 Google ID token。

雲端前置狀態（已部署 lw-api-main、私人 PG18.6 ready 200、正式 DML／Identity／CRUD／ROLLBACK 已驗證）依使用者提供，不冒充本輪查驗。測試方案只在現有服務新增短期 0% tagged revisions，沿用同 digest、Runtime SA 與 Private VPC；正常 stable 仍 100% 且 business=false。

## 實作內容

| 檔案 | 用途 |
|---|---|
| `scripts/e2e_acceptance.py` | 正式 CLI；Google ID token 只由 stdin 讀入；失敗安全報告。 |
| `scripts/e2e_safety.py` | 離線匯出配置、0% tag、100% stable、IAM、DB／login、Hosts／Origin、同 digest 與 audience 防護。 |
| `scripts/e2e_flow.py` | 真實 HTTP／HTTPS 驗收流程；兩個獨立 Cookie jar，主要 URL 僅 GET；不新增 API 端點。 |
| `scripts/e2e_plan.py` | 組合使用者匯出的 v1 Service／兩個 Revision／IAM JSON，先驗證再寫 plan，不自動呼叫 GCP。 |
| `scripts/e2e_sql.py` | 由唯一 canonical 31 表 SQL 產生同 transaction guard 的建表 SQL，另產生 run-specific SQL audit。 |
| `scripts/run_e2e_local.py` | 一次性 PG18.6、兩個真實 loopback HTTPS API、本機 HMAC edge 拒絕模型、SQL 查核及清理。 |
| `deploy/postgres/e2e/00_database.sql` | 初次建立專用 DB、NOLOGIN owner／runtime；同名物件已存在就停止。 |
| `02_grants.sql` | 新 runtime 的 30 SELECT／INSERT、17 UPDATE、6 DELETE 最小矩陣。 |
| `03_verify_permissions.sql` | 核對 effective privileges、role／sequence 限制，不輸出資料列。 |
| `04_dev_role_probe.sql` | 在 dev 只讀 metadata 確認 E2E login 無業務表權限，不改 dev。 |
| `20_enable.sql` | Schema／角色通過、密碼及 secret 人工設定後啟用 E2E login。 |
| `90_cleanup.sql` | Guard 後先提交 NOLOGIN／撤銷 CONNECT，再終止 E2E 連線、清 30 表、保留 schema／migration metadata。 |
| `tests/test_e2e_acceptance.py` | 安全配置、拒絕目標、Token audience／效期、redirect、報告遮蔽、SQL guard 與 CLI 測試。 |

根 README、ACCEPTANCE、EVOLUTION 同步增加入口／驗收紀錄；App 程式、API／Web Dockerfile、Cloud Build YAML、原 schema 與所有 Web 部署檔維持 main 內容，沒有變更目前服務行為。

## 本輪實際驗證

本機 PostgreSQL 實際版本：**18.6（Debian 18.6-1.pgdg13+2）**。新工具透過開啟 TLS 驗證的真實 HTTPS socket 呼叫兩個 uvicorn／FastAPI app，不只使用 MockTransport。DB runtime 為 `lw_e2e_app`，不是管理者；初始化／清理才使用本次容器的本機專用管理者。

| 驗證 | 實際結果 |
|---|---|
| 真 PG18.6＋真 HTTPS e2e | **49 個 HTTP／契約檢查全部 PASS** |
| Tag 退休模型、主要 app 保持關閉 | **9 個檢查全部 PASS** |
| 獨立 SQL audit／最小權限／Identity／rollback | PASS；31 表、30／30／17／6 effective privileges |
| 清理／保護 | 30 張業務表全部空、runtime NOLOGIN／0 sessions；dev 合成資料指紋不變 |
| 新工具防護／CLI 測試 | **28 個案例通過**，納入下列全套 |
| 最終完整 SQLite／工具回歸 | **259 passed、14 skipped、0 failed／error，43.47 秒** |
| 既有 Web main 契約 | **9 tests，OK，2.539 秒**；gcloud 全為 mock |

HTTP e2e 以全新合成 run ID 驗證 IAM 模型拒絕、Guest／Session／Secure Cookie／CSRF／Origin、第一目標三習慣、跨 Owner 讀寫拒絕、Decimal 0.123456、唯一 reward／receipt、全新 client 重讀、INSERT 後自然失敗的 rollback；並在前後只 GET 驗證主要 app 關閉。完整檔案清單見 [Step 18 manifest](STEP18_FILE_MANIFEST.json)。

獨立 SQL 連線核對實際持久化、31 表／2 identity、30／30／17／6 權限、Identity INSERT 後 rollback 與直接 nextval 拒絕。另確認 E2E login 寫 dev 被拒、dev 上執行 cleanup 被 guard 拒絕。結束先退休 tag 模型並關閉 HTTPS app，執行交付的 cleanup SQL，全部 30 張業務表空、runtime NOLOGIN、無連線；dev 合成哨兵與 31 表資料指紋前後一致。容器、匿名 volume、合成 env、TLS private key 均由 harness finally 清理。

本機 HMAC edge **不能證明 Google IAM signature／Invoker 權限或真實 0% 流量**，報告明列 `mode=local-simulation`。正式 CLI 不接受 local 模式；真實 Cloud Run 的匿名／無效 token 拒絕、有效 ID token、tag routing 需由使用者執行。HTTP passed 也不代表已做 SQL audit／資料清理；正式流程另須產生 30_verify_run.sql 並由使用者查 SQL。

## 可重現本機命令

```powershell
$env:PYTHONUTF8='1'
$env:LIFEWORLD_TEST_DOCKER_ARGV='["wsl","-d","Ubuntu-24.04","-u","root","--exec","/mnt/c/LifeWorld_project/life-world-step10-4/.tools/docker/docker","-H","unix:///tmp/lifeworld-step10-4-docker/docker.sock"]'
.venv/Scripts/python.exe -X utf8 -m scripts.run_e2e_local --report C:\LifeWorld_project\step18-evidence\local-e2e-delivery.json
.venv/Scripts/python.exe -X utf8 -m pytest tests -q --tb=short --basetemp=.test-runs/step18-delivery --junitxml=C:\LifeWorld_project\step18-evidence\regression-delivery.xml
.venv/Scripts/python.exe -X utf8 -m unittest discover -s deploy/tests -v
```

此機器使用既有隔離 WSL Docker daemon，**不修改舊工具檔或舊工作樹**。在一般 Linux Docker 可使用原生 docker；本機 harness 需要 Linux host networking、可用 OpenSSL（`--openssl` 可指定路徑）、127.0.0.1:55438 可用。harness 不接受遠端 PG 目標，每次產生唯一容器名稱與全新合成資料。

## 原始證據與限制

本機 `C:\LifeWorld_project\step18-evidence\` 保存原始 stdout／JUnit／JSON，不納入 Git：

- `local-e2e-delivery.json/log`：最終真 PG／HTTPS、SQL、最小權限及清理結果。
- `regression-delivery.xml/log`：本輪完整 SQLite／工具回歸；14 個既有 PG 專用案例於此模式跳過。本輪 PG 證據來自新 e2e harness，沒有把 Step 11 的 245 passed 當成本輪重跑結果。
- `web-contract.log`：既有 Web 9 項契約；gcloud 全為本機 mock。
- `guards-red.log`：初版安全防護 20 failed／1 passed，確認不安全配置不能被接受。
- `sql-guard-red.log`：確認 DB guard 必須在 DDL 交易內；修正後新工具回歸與真 PG SQL 再通過。

前幾輪本機準備失敗分別是隔離 PG 的 psql 埠未指定及系統 OpenSSL 配置差異，均已修正重跑；不把 setup error 當功能紅燈或驗收成功。所有失敗報告只留固定階段／SQLSTATE，不輸出密碼、Token、Cookie 或資料列。

尚未驗證：真實 Cloud Run v1 匯出形狀、Console tag 管理介面／Revision 退休限制、實際 Google IAM／呼叫者權限、Private VPC／Secret Manager／ADC／Cloud SQL 管理者權限與雲端 SQL。使用者若遇配置缺失／權限不符，應停止處理該項，不以公開 IAM、高權限 Runtime、修改 dev 或主流量來讓測試變綠。亦未執行 UI 瀏覽器、負載或平台故障驗收。

## PR #11 合併前補正｜快照來源與 Direct VPC

P1 修正建立 Plan 自行更新 captured_at 的缺口：由操作者的同批唯讀匯出記錄 batch ID、整批與每檔匯出起訖時間、原始 byte SHA256。Builder 逐檔核對外部證據與實際 JSON，保留最早匯出時間作 captured_at，另列 created_at；Plan 內解析後 JSON 再以穩定內容 SHA256 綁定，執行時重驗四份來源紀錄、時間與內容。缺少證據、超過15分鐘、未來／逆序時間、跨批次或任一指紋不符均拒絕；重新建立 Plan 不能讓舊來源變新。成功報告保留來源時間與指紋供追溯。

P2 從實際 stable／e2e v1 Revision `metadata.annotations` 檢查 `run.googleapis.com/network-interfaces` 與 `run.googleapis.com/vpc-access-egress`：只允許同一專案的 `lw-vpc-staging`／`lw-subnet-staging`、`private-ranges-only`，兩修訂的 Direct VPC 設定相同，拒絕有效的 `run.googleapis.com/vpc-access-connector`。不從 service template 或不存在的 spec 欄位推測。格式依據見 [官方 Direct VPC v1 YAML](https://docs.cloud.google.com/run/docs/configuring/vpc-direct-vpc#yaml)。

本輪在原短期分支實測：新增負向案例先得到 **34 failed／29 passed**；修正後工具單元 **63 passed**，完整回歸 **294 passed／14 skipped（38.04秒）**，PG18.6＋HTTPS **49項**、退休／清理 **9項**、Web契約 **9項（1.725秒）**通過。文件的 PowerShell 整批匯出流程以本機 gcloud 替身執行，四份 JSON 的原始 SHA256 與離線 Plan 成功核對；沒有執行真正 gcloud。

本輪原始證據保存在 `C:\LifeWorld_project\pr11-fix-evidence\`：`red.log/xml`、`unit.log/xml`、`regression.log/xml`、`local-e2e.log/json`、`web-contract.log`、`export-mock.log`。不納入 Git。清理結果仍為30張業務表空、runtime NOLOGIN／0連線，dev合成資料指紋不變。API、核心 DDL、DML 權限 SQL、Dockerfile、Cloud Build YAML 及既有安全配置不變。

這些時間與指紋是本機匯出證據，不是 GCP 簽章或持續狀態監測。工具不能偵測匯出後的所有 GCP 外部變更；**驗收期間必須凍結配置**。真實 Direct VPC 路由／Google IAM／Cloud SQL 雲端驗收仍未執行；本機模型不冒充這些結果。
