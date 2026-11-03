# LIFE WORLD Step 18｜Cloud Run API 受控端對端驗收

本文件是**由使用者逐步執行的操作方案**。本輪只開發工具並驗證本機 PostgreSQL 18.6，沒有操作 GCP、Push、Merge 或部署。使用者提供的 Cloud SQL `/ready=200`、CRUD／Identity／ROLLBACK 成功及正式 `lw_app` DML 權限屬前置背景，非本輪重新查驗結果。

只使用 `life-world-513506`／`asia-east1` 的現有 `lw-api-main`。既有 stable Revision 保持 100% 流量、`LIFEWORLD_ENABLE_BUSINESS_API=false`。測試 Revision 0%、tag `e2e`，只有它啟用業務。沿用同一映像 digest、Runtime SA／Private VPC 與 Cloud SQL 執行個體；不建立 staging Git 分支或另一個長期服務。

工具、SQL 與本機證據見 [Step 18 交付](../docs/STEP18_API_E2E_ACCEPTANCE.md)。

## 1. 先記錄與凍結現況

使用者在 Console 記下 Project number、Cloud SQL instance connection name、Cloud Run **stable Revision 名稱**、100% 流量、服務標準 URL、image digest、Runtime SA、VPC／subnet／egress、環境變數與 secret 版本。從匯出 Service JSON 的 `status.url` 取得標準 URL，不自行用 tag URL 當 audience。

驗收期間不要讓其他人部署或搬動 `e2e` tag。工具依賴 15 分鐘內的真實配置匯出；它不自行讀取／鎖定 GCP 控制平面。若配置有變，停止並重新匯出，不能繼續用舊 plan。一般流量須固定既有 Revision 名稱，不使用可能指向新修訂的 `LATEST`。

保留 Require authentication／Invoker IAM check，不加入 `allUsers`、`allAuthenticatedUsers`，不關閉 Invoker IAM check。呼叫者使用**已具此服務 Invoker 權限且可無金鑰 impersonate 的 SA**；不假設 Runtime SA 自動有 Invoker。若目前沒有合適呼叫身分，由使用者另行完成最小範圍權限審查，工具不代為授權。

## 2. 準備隔離資料庫與最小權限 SQL

在本機新工作樹執行（只產生 SQL，不連線）：

```powershell
$Py = '.venv/Scripts/python.exe'
& $Py -X utf8 -m scripts.e2e_sql --out .test-runs/e2e-sql
```

由使用者在同一 Cloud SQL instance，以有 CREATE DATABASE／管理新角色權限的 DBA 操作；**這些管理角色不注入 API**。若現有管理身分沒有權限，停止交 DBA，不提升 Runtime 權限。

| 順序 | 連線 DB | SQL／動作 |
|---|---|---|
| 1 | `postgres` | `00_database.sql`；單獨執行，不能包進外層 transaction。建立 `life_world_e2e`、NOLOGIN owner `lw_e2e_owner`、NOLOGIN runtime `lw_e2e_app`；同名物件已存在就停止，不接管。 |
| 2 | `life_world_e2e` | 產生的 `01_schema.sql`，以唯一 canonical 31 表 DDL 建立 schema。DB 名稱／marker guard 與 DDL 在同一 transaction，失敗就回滾。 |
| 3 | `life_world_e2e` | `02_grants.sql`：30 表 SELECT／INSERT、17 UPDATE、6 DELETE；無 DDL／TRUNCATE／migration 表與直接 sequence 權限。 |
| 4 | `life_world_e2e` | `03_verify_permissions.sql`：核對 effective privileges、owner／繼承及序號限制，必須得到 `E2E_PERMISSIONS_PASS`。 |
| 5 | `life_world_dev` | **只讀 metadata** 的 `04_dev_role_probe.sql`，確認 E2E login 無 dev 業務表權限，得到 `E2E_DEV_ROLE_ISOLATION_PASS`。沒有資料列查詢／DML／GRANT／REVOKE；若 PUBLIC 既有權限造成失敗，停止交 DBA，不自動改 dev。 |
| 6 | 管理連線 | 由使用者安全設定 `lw_e2e_app` 的新密碼，例如可信任管理用 psql 的互動 `\password lw_e2e_app`；密碼不放 SQL 檔、命令列或查詢歷史。將同一密碼以 Secret Manager 保存為測試專用 secret 的固定數字版本。 |
| 7 | `life_world_e2e` | `20_enable.sql`：確認 schema 與角色安全後才允許 E2E login。 |

使用 psql 執行 SQL 時加 `-X -v ON_ERROR_STOP=1`；使用 Cloud SQL Studio 時核對所選資料庫並逐檔執行，任一錯誤即停止。不要把 canonical DDL 原檔直接對 dev 執行。產生器不維護第二套 schema，`01_schema.sql` 由 `docs/database/schema-2026-11-02/POSTGRESQL_CORE_DRAFT.sql` 加入交易內防護而成。

專用 DB 具 marker `LIFEWORLD_E2E_SYNTHETIC_ONLY_v1`，owner 是 `lw_e2e_owner`。`lw_e2e_app` 沒有 migration membership、superuser、CREATEDB／CREATEROLE／BYPASSRLS，與 dev 的 `lw_app` 密碼及角色分開。新 secret 若需要授權，只由使用者讓 `lw-api-runtime` 讀取該 secret；不授予公開存取或廣泛 Secret 管理權。

## 3. Console 建立 0% Tagged Revision

Cloud Run → `lw-api-main` → 記錄 stable Revision → Edit and deploy new revision／View diff and redeploy。使用 stable 的**同一 API image digest**，不是 `latest`、Web image 或另一份程式碼。

若尚無可信任的實際 Tagged URL，採兩段準備，避免猜 URL 後啟用業務：

1. 先建立短期安全 Revision：DB／user／secret 選 E2E，但業務開關仍 `false`。取消 **Serve this revision immediately**，部署後確認原 stable 仍 100%。在 Revisions／Manage traffic 的 tag 管理，將 `e2e` 指向此 Revision，百分比為 0，複製平台顯示的實際 Tagged URL。
2. 從此安全配置建立正式驗收 Revision，設定下表的 Tagged Host／Origin，**只有此 Revision** 改為 `true`；同樣取消立即提供流量，維持 0%。Ready 後把 `e2e` tag 移到這個確切 Revision 名稱，仍是 0%，不使用 Latest 指標。
3. 再看流量頁：stable 的原名稱 100%、business=false；驗收 Revision 0%、tag=e2e、business=true。IAM、Private VPC／subnet／egress／Runtime SA 不變。匯出狀態與工具預檢任一不符就停止，不開始寫入測試。

若 Console 版本沒有 tag 管理入口，官方提供的最小替代是由使用者自行執行 `gcloud run services update-traffic lw-api-main --project=life-world-513506 --region=asia-east1 --update-tags=e2e=EXACT_TEST_REVISION`。這只更新 tag；**不要加** `--to-tags`／`--to-latest`／新的流量百分比。本輪未執行。

## 4. 驗收 Revision 環境變數

| 變數／設定 | 測試 Revision 的值 |
|---|---|
| Runtime Service Account | `lw-api-runtime@life-world-513506.iam.gserviceaccount.com` |
| `LIFEWORLD_ENABLE_BUSINESS_API` | `true`；stable 仍 `false` |
| `LIFEWORLD_DB_BACKEND` | `postgresql` |
| `LIFEWORLD_PG_CONNECTION` | `cloud_sql`；Connector 的 Private IP／ADC 設計保留 |
| `LIFEWORLD_INSTANCE_CONNECTION_NAME` | **既有相同 instance connection name**，不得改成新 instance／public IP |
| `LIFEWORLD_DB_NAME` | `life_world_e2e` |
| `LIFEWORLD_DB_SCHEMA` | `lw_core_draft` |
| `LIFEWORLD_DB_USER` | `lw_e2e_app` |
| `LIFEWORLD_DB_PASSWORD` | Secret reference，固定數字版本；不填明文 value |
| `LIFEWORLD_SECURE_COOKIES` | `true` |
| `LIFEWORLD_TRUSTED_HOSTS` | 真實 Tagged URL hostname、標準 service hostname、`127.0.0.1,localhost`；不帶 scheme／port，不使用 `*` |
| `LIFEWORLD_EXTERNAL_ORIGIN` | 實際 **Tagged URL origin**，HTTPS、不帶結尾 `/`、path、query |
| `LIFEWORLD_DB_POOL_SIZE` | 沿用已審查限制；可保守設 `2`，不可忽略同 instance 的總連線容量 |
| `PORT` | Cloud Run 注入 `8080`；不自行設定 K_SERVICE |

禁止 `GOOGLE_APPLICATION_CREDENTIALS`／Service Account JSON Key。登入 session Cookie 與 IAM token 是不同驗證：工具把 IAM token 放 `X-Serverless-Authorization`，App 仍走原 Session／CSRF／Origin，沒有新增公開端點。

## 5. 使用者匯出配置，工具離線預檢

以下命令**只提供使用者之後執行，本輪未執行任何 gcloud**。Cloud Run Revisions 匯出使用 v1 JSON 形狀；若輸出形狀不同，工具拒絕，不跳過預檢。輸出放 `.test-runs`，不要納入 Git。

```powershell
$Project = 'life-world-513506'
$Region = 'asia-east1'
$Stable = '填入原本100%流量的確切Revision名稱'
$TestRevision = '填入0%且e2e標籤指向的確切Revision名稱'
$Dir = '.test-runs/cloud-e2e'
New-Item -ItemType Directory -Force $Dir | Out-Null
function Save-E2ESnapshot([string]$SnapshotFile, [string[]]$GcloudArgs) {
  $SnapshotJson = & gcloud @GcloudArgs
  if ($LASTEXITCODE -ne 0) { throw 'Snapshot export failed; stop without reusing old files' }
  $SnapshotJson | Out-File -Encoding utf8 $SnapshotFile
}
Save-E2ESnapshot "$Dir/service.json" @('run','services','describe','lw-api-main',"--project=$Project","--region=$Region",'--format=json')
Save-E2ESnapshot "$Dir/main.json" @('run','revisions','describe',$Stable,"--project=$Project","--region=$Region",'--format=json')
Save-E2ESnapshot "$Dir/tag.json" @('run','revisions','describe',$TestRevision,"--project=$Project","--region=$Region",'--format=json')
Save-E2ESnapshot "$Dir/iam.json" @('run','services','get-iam-policy','lw-api-main',"--project=$Project","--region=$Region",'--format=json')
$ProjectNumber = gcloud projects describe $Project --format='value(projectNumber)'
if ($LASTEXITCODE -ne 0) { throw 'Project number lookup failed' }
& $Py -X utf8 -m scripts.e2e_plan --service "$Dir/service.json" --main-revision "$Dir/main.json" --tag-revision "$Dir/tag.json" --iam-policy "$Dir/iam.json" --project-number $ProjectNumber --out "$Dir/plan.json"
if ($LASTEXITCODE -ne 0) { throw 'E2E plan rejected; do not run HTTP acceptance' }
```

預檢會核對專案／區域、Ready、stable 100% 固定名稱、e2e 0%、不同 Revision、同 digest／instance、DB／login、固定 secret 版本、私人 IAM、Hosts／Origin。任一安全資訊缺失或為明文 secret 都停止，不能直接修改主要 Revision 來繞過，也不能手填假的配置宣稱通過。

## 6. 正式驗收指令

Audience 必須是 `service.json` 的 **status.url**；Tagged URL 只作請求目的與 Origin。使用新的短期 Google ID token，呼叫者 SA 已具 `run.invoker`，操作者已獲 impersonation 權限。無需 JSON Key，不印出 token、不啟用 HTTP debug／shell tracing。

```powershell
$ServiceUrl = (Get-Content "$Dir/service.json" -Raw | ConvertFrom-Json).status.url
$InvokerSa = '填入已授權且可impersonate的呼叫者SA完整email'
gcloud auth print-identity-token --impersonate-service-account=$InvokerSa --audiences=$ServiceUrl --include-email |
  & $Py -X utf8 -m scripts.e2e_acceptance --plan "$Dir/plan.json" --token-stdin --report "$Dir/result.json"
# 非0即失敗，停止測試並走清理。
```

工具不執行 gcloud、沒有密碼／Token 參數、Token 只在 stdin／記憶體；Cookie 與 CSRF 不寫檔。TLS 驗證開啟、不跟隨 redirect、不使用環境 proxy。JSON 報告記錄固定步驟、預期／實際狀態與固定失敗原因碼，不記錄 URL 回應 body、標頭、Owner ID 或私人內容。任一步失敗停止後續業務寫入，仍嘗試只 GET 驗證主要 Revision 關閉。

涵蓋 IAM 無 token／錯誤 token、health／ready、兩個獨立訪客與 Secure Cookie／Session／CSRF／Origin、各自第一目標及三習慣、`0.123456` 貢獻、積分、相同 request_id 重送、跨 Owner 404、全新 HTTP client 重讀及失敗交易無部分提交。回滾案例是「草稿日期早於新目標開始日」：現有 confirm 在 INSERT experiences 後拒絕採計，工具期待 422／contribution_out_of_range，再查草稿仍為 draft、積分／經歷／任務不變；不新增故障注入後門。

HTTP `passed=true` **不代表已完成清理或直接查過 Cloud SQL**，還必須由使用者執行 DB assertions：

```powershell
$RunId = (Get-Content "$Dir/result.json" -Raw | ConvertFrom-Json).run_id
& $Py -X utf8 -m scripts.e2e_sql --out .test-runs/e2e-sql --run-id $RunId
```

在 `life_world_e2e` 以管理／owner 身分執行產生的 `30_verify_run.sql`，須得到 `E2E_DATABASE_AUDIT_PASS`。它用合成 run ID 定位兩個 Owner，核對持久化、精確 Decimal、唯一 reward／receipt、跨 Owner 及回滾後無殘留。新連線 SQL 查核補足 HTTP 無法證明的資料庫狀態，並非聲稱已強制每次請求落在不同 Cloud Run instance。

## 7. 清理與恢復（即使驗收失敗也要做）

1. 使用者確認 stable 仍為原名稱 100%、business=false；先移除 `e2e` tag，測試 Revision 維持 0%，不要把流量搬到它。
2. 停止使用／刪除這次 0% 測試 Revision（包含前段取得 URL 用的安全修訂），等待 in-flight requests 結束。若 Console 不允許刪除 latest Ready Revision，可從原 stable 配置建立**新的 0%、business=false** 修訂作安全 template（依舊取消立即提供流量），再刪除測試 Revision。未來部署不可直接沿用 business=true 的測試 template。
3. 保留先前 `tag.json` 作退休核對，重新匯出 service／main／IAM、重新產生 plan（同第5節但 `e2e_plan` 加 `--retired`）。Tag 必須已不存在；以新 token 執行 `e2e_acceptance ... --retired`，此模式只 GET main，不能建立訪客。保留原 stable 100% 的證據。
4. 使用者以 DBA 在 **life_world_e2e** 執行 `90_cleanup.sql`。先提交 `lw_e2e_app NOLOGIN`／撤銷此 DB CONNECT，再終止該 login 在此 DB 的連線；確認已排空後清空 30 張業務表並重設 Identity。保留 31 張表與 migration metadata，不 DROP DB、不碰 dev。沒有終止連線權限時交 DBA，不能改用高權限 API Runtime。
5. 要看見 `E2E_CLEANUP_PASS`、`retained_tables=31`、`runtime_login=false`、`runtime_sessions=0`。SQL 內逐表確認全部業務列數為 0。這才是清理完成證據，不能單憑移除 tag 或 HTTP passed 就宣稱資料已清乾淨。
6. 由使用者停用／移除測試專用 secret 版本及臨時呼叫者授權（若本次另外新增）；不變更 dev secret 或其他既有權限。報告保留，TLS／測試憑證不進 Git；工具沒有保存 session/token 檔案。

再次驗收沿用這個專用合成 DB 的 31 表與最小 grants，先核對 marker／角色／資料為空、設定新密碼與固定 secret 版本，再執行 `20_enable.sql`。**不重新執行 00／01 覆蓋既有物件**。建立新的 0% Revision，使用同一流程與新 run ID，結束後再 NOLOGIN／清理。

## 官方依據與尚未驗收

- [Cloud Run traffic／tagged revision](https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration)：無一般流量修訂與 tag URL；本方案不執行流量遷移。
- [服務間驗證](https://docs.cloud.google.com/run/docs/authenticating/service-to-service)：tagged request 的 audience 仍為 service URL，並可使用 X-Serverless-Authorization。
- [ID token impersonation 指令](https://docs.cloud.google.com/sdk/gcloud/reference/auth/print-identity-token)：無 SA JSON Key 的短期 token。
- [v1 Service resource](https://docs.cloud.google.com/run/docs/reference/rest/v1/namespaces.services)：工具核對輸入的 spec／status／traffic 形狀。

真實 IAM signature／Invoker、特定 service 的 IAM policy、tag 路由／流量、Private VPC／Secret Manager／ADC、Cloud SQL DBA 的實際權限及平台 Console UI 均仍須由使用者實測。操作機器要能依既有 ingress／網路政策到達服務；不要為了讓測試通過放寬政策。工具不以本機 HMAC edge model 冒充 Google IAM，也不自動修復雲端配置。
