# Step 10 4 FastAPI PostgreSQL 與容器工程交接

> Step 10-4 歷史工程與測試紀錄。Step 11 的 main 整合、重新測試與發布界線請以 [最新整合交接](STEP11_API_MAIN_INTEGRATION.md) 及 [API main 操作指引](../deploy/README.api-main.md) 為準；下列舊測試數不代表 Step 11 結果。API 名稱已同步 main，實際 Cloud SQL／VPC 舊資源名稱保留。

日期：2026-11-03。判定：**Step 10-4 當時判定：READY FOR GCP CONFIGURATION**。

本輪在獨立工作樹實作原 FastAPI 的 PG18 adapter、API 容器與 Build／Push 設定。SQLite 預設模式保留。GCP 的資源名稱與目前權限取自使用者交接，沒有連線驗證，也沒有部署、GRANT、IAM 或 Cloud SQL 變更。試用環境僅可使用合成資料。

## A 已實作與工作樹界線

原位置 `C:\LifeWorld_project\life-world` 的分支為 main，HEAD 為 `7fbe00ba0a992cfb1403f698442936002d902c69`。開工時已有11個 tracked 修改，以及 dependency／setup 測試等未追蹤檔。為保留這些工作，新增 `work/step10-4-pg-api` 分支與 `C:\LifeWorld_project\life-world-step10-4` 工作樹，複製11個既有修改與2份既有測試作為實際基準；沒有複製資料目錄、SQLite 或 .env。未 commit、push 或 merge。

| 本輪程式／設定 | 功能 |
|---|---|
| `app/runtime.py` | 明確 backend、TCP／cloud_sql、schema、pool、TLS、trusted hosts、HTTPS cookie 與雲端業務開關 |
| `app/postgres.py` | pg8000、row mapping／型別邊界、有界 pool、owner 交易鎖、rollback 與固定錯誤碼 |
| `app/db.py` | 保留 SQLite migrations／BEGIN IMMEDIATE，增加共同 audit／health／close 介面 |
| `app/service.py`、`app/goals.py`、`app/people.py`、`app/connections.py` | 沿用原業務規則，明確 bool、SQL UPSERT、audit_seq 與 owner 鎖 |
| `app/main.py`、`app/serve.py` | 正式 App factory、三個健康入口、PORT、0.0.0.0、明確 Host／Origin、Secure Cookie 與 lifespan 清理 |
| `deploy/Dockerfile.api`、`.dockerignore` | Python3.12 多階段 API image、UID/GID10001、只 COPY App 與鎖定依賴 |
| `deploy/cloudbuild.api.yaml` | 專用 build SA，SQLite／PG18 測試後建置、容器驗證、唯一 tag、push；無 deploy |
| `deploy/postgres/app_dml_grants.review.sql` | 待審最小 DML；僅由合成測試 bootstrap 使用 |
| `scripts/pg_test_bootstrap.py`、`scripts/run_postgres_tests.py` | 專用 PG18 容器、cluster marker／database marker、migration／app 分權、自動清理 |
| `scripts/smoke_api_container.py` | 兩個 Port、真實 PG readiness／auth、cloud gate、所有 image layers 排除資料／憑證 |
| `tests/test_api_runtime.py`、`test_postgres_adapter.py`、`test_postgres_integration.py`、`test_api_build_config.py`、`test_container_safety.py`、`pg_support.py` | 本輪新增驗證 |
| `tests/conftest.py`、`test_evidence_notes.py`、`test_goal_journey.py` | 同一 API 套件切換 PG；重啟沿用 backend；SQLite 舊多目標案例獨立保留 |
| `requirements.txt`、`requirements.lock`、`pyproject.toml`、`requirements.api*.in/lock`、`.gitignore` | PG driver／選用 cloud extra 與獨立 runtime／test locks；排除本機工具和合成測試產物 |
| 本交接、`database/APP_DML_REVIEW_STEP10_4.md`、README／ACCEPTANCE／EVOLUTION | 操作、31表差異、權限與本輪驗收 |

完整逐檔狀態見 [變更清單](STEP10_4_FILE_MANIFEST.json)。

`README.md`、`app/db.py`、`docs/ACCEPTANCE.md`、`docs/EVOLUTION.md`、`pyproject.toml`、`requirements.lock`、`requirements.txt` 是本輪與既有修改重疊檔案。`scripts/setup.py`、`scripts/export_openapi.py`、`tests/test_connections.py`、`tests/test_people.py` 及 `tests/test_dependency_lock.py`、`tests/test_setup_script.py` 是沿用的既有修改，沒有把它們冒充本輪新增功能。

## Adapter 與交易設計

不設定 `LIFEWORLD_DB_BACKEND` 時沿用 SQLite 及既有 `python -m app` 的本機8000入口。PG 明確設定為 `postgresql`，錯字、缺密碼、未知連線模式、錯誤 schema、錯誤版本、連線／ADC／TLS 失敗都不會退回 SQLite。PG App factory 與 startup 不做 DDL，不讀 schema_migrations，也不套用 SQLite migrations。

pg8000 1.31.6 原生 qmark parser 處理 `?` bind；值始終參數化，不用 SQL 字串搜尋替換。schema 識別字先以嚴格字元規則驗證，再設定 search_path 為指定 schema 加 pg_catalog。audit 排序欄位只接受兩張受控表名。保留並逐條修正 SQL：bool 用原生 bool／TRUE／FALSE、SUM 使用 CASE、OR IGNORE 改具體 conflict target、start/end 識別字加引號，identity 的 INSERT 明列原有欄位。

SQLite 寫入仍用 BEGIN IMMEDIATE。PG 用 READ COMMITTED，先取得 schema＋owner 的 transaction advisory lock，才讀版本與去重回執；鎖由資料庫跨 App instances 管理。未知 owner 的 guest／login／logout 使用獨立 identity 鎖。Owner隔離由原service的查詢與_owned檢查實施，本輪未啟用RLS；lw_app是後端共用身分，不供前端直連。不同 owner 不共享業務鎖；username 等跨 owner 唯一性最後由 DB 約束保護。純讀取用 REPEATABLE READ READ ONLY，讓聚合畫面同一快照。確認經歷、貢獻、人物來源、待辦、積分、draft 狀態與 request receipt 都同交易提交。沒有自動重跑交易或 AI／外部呼叫。

每個 App 有界 pool 預設4連線、上限32；等待5秒，lock_timeout5秒，statement_timeout15秒。取得失敗回503、衝突／timeout回409、權限不足回503，固定訊息不輸出 SQL 或連線細節。rollback 後歸還連線；無法 rollback 的連線丟棄，lifespan 結束關閉 pool／Connector。部署容量仍需按 max instances × 每 instance pool 調整，這不是負載測試結論。

PG row 邊界提供原 service 需要的 row[name]／row[0]／dict(row)。NUMERIC 以 Decimal 精確轉十進位字串；API 仍限制最多六位小數，adapter 另外驗證更長精度沒有 float 損失。JSONB 解碼後回既有 service JSON 字串介面，保存結構值；key順序／空白由 JSONB 正規化。既存 fingerprint 欄位原樣保存，計算仍依原 encoded／省略新預設值的規則，沒有重算歷史指紋。TIMESTAMPTZ 回 UTC ISO、DATE 回日曆日期；boolean 在舊 API 輸出邊界保留0/1，領域必要欄位仍輸出 bool。

cloud_sql 模式使用 Connector1.23.0＋pg8000、`ip_type=private`、lazy refresh，首次 DB 請求才取得 ADC。沒有 credentials 檔參數、SA JSON 或 public fallback。Connector 不建立 VPC 路由；VPC 設定仍由使用者完成。見 [Connector 官方說明](https://github.com/GoogleCloudPlatform/cloud-sql-python-connector)。

TCP 本機 loopback 可不加 TLS；其他主機預設驗證 TLS。明確 disable 只容許 loopback 與合成 CI alias lw-pg18-tests，不接受交接的10.129.0.3。雲端優先採 Connector，避免自行分發憑證。

## 31表對應與 Migration 差異

唯一建表來源為 [POSTGRESQL_CORE_DRAFT.sql](database/schema-2026-11-02/POSTGRESQL_CORE_DRAFT.sql)，SHA256 `4521c963084dedfeb250d95945f8258dccf677e8db8cb7272cfa7251381a7492`，原檔未修改。本輪在本機合成 PG18.6 真正執行；原檔2026-11-02的草案註記屬當時快照。SQLite 001–005 仍只在 SQLite 執行。沒有執行 POSTGRESQL_THEATER_PROPOSAL.sql。

31表保留同名、text ID 與原業務欄位；201欄變203欄，只增加 goal_reviews／story_history 的 audit_seq。60個有效 FK、10個明確索引、2個 identity sequences；PG 主鍵與 unique 約束各有系統索引，不應把它們誤算為只有10個實體索引。

| 同名 Table | SQLite → PG 欄數 | PG 特殊型別 |
|---|---|---|
| `actions` | 13 → 13 | target `numeric`; weekdays `jsonb`; per_occurrence `numeric`; schedule_dates `jsonb`; target_is_derived `boolean` |
| `completions` | 6 → 6 | evidence_ids `jsonb`; created_at `timestamptz` |
| `contributions` | 5 → 5 | quantity `numeric` |
| `draft_stories` | 2 → 2 | payload `jsonb` |
| `drafts` | 11 → 11 | occurred_at `timestamptz`; contributions `jsonb`; created_at `timestamptz`; updated_at `timestamptz` |
| `evidence` | 9 → 9 | content `bytea`; created_at `timestamptz` |
| `experience_mentions` | 9 → 9 | ID／其他文字與 bigint |
| `experience_participants` | 3 → 3 | interacted `boolean` |
| `experience_stories` | 6 → 6 | reviewed `boolean`; available `boolean` |
| `experiences` | 9 → 9 | occurred_at `timestamptz`; created_at `timestamptz` |
| `fact_sources` | 4 → 4 | revoked_at `timestamptz` |
| `goal_reviews` | 8 → 9 | previous_state `jsonb`; new_state `jsonb`; created_at `timestamptz` |
| `goals` | 14 → 14 | created_at `timestamptz`; completed_at `timestamptz`; start_date `date`; deadline `date`; ended_at `timestamptz` |
| `habit_quantity_versions` | 4 → 4 | effective_from `date`; quantity `numeric`; created_at `timestamptz` |
| `interaction_events` | 5 → 5 | occurred_at `timestamptz` |
| `interaction_experiences` | 2 → 2 | ID／其他文字與 bigint |
| `interaction_people` | 2 → 2 | ID／其他文字與 bigint |
| `note_sources` | 2 → 2 | ID／其他文字與 bigint |
| `notes` | 7 → 7 | created_at `timestamptz` |
| `pending_contributions` | 9 → 9 | quantity `numeric`; accepted_quantity `numeric`; accepted_at `timestamptz` |
| `people` | 12 → 12 | created_at `timestamptz`; roles `jsonb`; tags `jsonb`; followed `boolean` |
| `person_connections` | 6 → 6 | source_experience_ids `jsonb` |
| `person_facts` | 11 → 11 | created_at `timestamptz` |
| `person_goals` | 4 → 4 | ID／其他文字與 bigint |
| `requests` | 5 → 5 | response `jsonb` |
| `reward_ledger` | 6 → 6 | created_at `timestamptz` |
| `schema_migrations` | 1 → 1 | ID／其他文字與 bigint |
| `sessions` | 5 → 5 | expires_at `timestamptz`; created_at `timestamptz` |
| `story_history` | 7 → 8 | before_json `jsonb`; after_json `jsonb`; created_at `timestamptz` |
| `tasks` | 5 → 5 | done `boolean` |
| `users` | 9 → 9 | hatched_at `timestamptz`; created_at `timestamptz` |

PG PK 強制 NOT NULL。PG 比 SQLite 現況多 `one_open_goal_per_owner` partial unique index，禁止同 owner 同時開兩個目標。既有「舊多目標待人工整理」案例保留在 SQLite 專用 fixture；PG 另以實際 uniqueness／同時建立案例驗證禁止新增，沒有刪除舊測試斷言。其他 SQLite 歷史 migration 案例也仍測 SQLite，不能將全套 PG fixture 執行數誤稱每一案都連 PG。

CORE DRAFT 是空庫最終結構，沒有001–005歷史 backfill／版本填寫、roles、grants、seed 或 ETL；本機 bootstrap 明確以 migration role 套用，再套用 DML 審查檔。已建立的 GCP31表不可再執行這份建表 SQL。正式舊資料轉換、無效 JSON／日期、重複目標清理與資料匯入均未進行。

## B 重複驗證方法與結果

### 環境

Windows Python3.14.7；API image Python3.12；FastAPI0.128.8；pg8000 1.31.6；PostgreSQL18.6。沒有現成 Docker Desktop，因此在既有 Ubuntu24.04 WSL 中下載官方 Docker29.7.0 static binaries，使用任務專用 socket、vfs、host network 與 `/tmp/lifeworld-step10-4-docker` state，不更動系統 Docker service／防火牆。Docker工具在忽略的 .tools，沒有進 Git 或 image；未使用的 PG portable 備援下載與解壓檔已清除。專用daemon與本機image保留供檢查，本輪測試容器和匿名volume均已清除。

postgres:18.6 下載 digest為 `sha256:3a4264520e121176619f54ff867d12774bc81e95e7b84db58d63bccdb6144b81`；python:3.12-slim 為 `sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30`。可重跑 tag；本輪 digest供核對，不代表日後 tag 不會更新。

### 一般 Docker 的重跑指令

在本工作樹執行；root lock 包含本機測試套件，Cloud Connector／API容器使用另外的 API lock。setup.py 會移除 root lock 以外套件，雲端 extra 請用獨立 venv，Python至少3.11，容器固定3.12。

```powershell
$env:PYTHONUTF8='1'
.venv/Scripts/python.exe -m pip install -r requirements.lock
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/python.exe scripts/run_postgres_tests.py tests

docker build --build-arg VCS_REF=local-uncommitted -f deploy/Dockerfile.api -t lifeworld-api:step10-4-local .
```

最後兩步只使用本機 Docker，不要替換成 cloud SQL 位置。測試 harness 自動隨機產生本次合成密碼，pg_admin 只存在專用容器；cluster_name 與 database comment 雙 marker 不符就拒絕清資料，host allowlist 不接受 Cloud SQL。finally 只清除自己建立的容器與匿名 volume，不使用 prune。

### 本機 WSL 實際指令

若專用daemon未啟動，先執行保留的本機helper：`wsl -d Ubuntu-24.04 -u root --exec sh /mnt/c/LifeWorld_project/life-world-step10-4/.tools/bootstrap_docker.sh`。它只管理本次獨立socket，沒有GCP動作。

```powershell
$env:PYTHONUTF8='1'
$env:LIFEWORLD_TEST_DOCKER_ARGV='["wsl","-d","Ubuntu-24.04","-u","root","--exec","/mnt/c/LifeWorld_project/life-world-step10-4/.tools/docker/docker","-H","unix:///tmp/lifeworld-step10-4-docker/docker.sock"]'
.venv/Scripts/python.exe scripts/run_postgres_tests.py --host-network --container-tests --image lifeworld-api:step10-4-local --junitxml .test-runs/postgres-full-final.xml tests
```

--container-tests 會在可丟棄 API runtime image 中加入鎖定測試套件，再跑 Linux SQLite／PG18 全量測試；來源 read-only 掛載，原 image 不變。--image smoke 使用 Linux host network，必須搭配 --host-network。一般 Windows Docker Desktop 不啟用 host networking 時，可先重跑發布localhost55432的 PG API測試，映像 smoke 改在 Linux runner／準備的 Cloud Build 內跑。

| 本輪驗證 | 結果 |
|---|---|
| Windows SQLite 最終全套 | 229 passed、14 skipped（PG專用案例）；40.80秒 |
| Windows PG18 fixture全套＋14個專用 PG案例 | 243 passed、0 skipped、1個Pydantic alias warning；68.22秒 |
| Linux Python3.12 SQLite 全套 | 229 passed、14 skipped（PG專用案例）；43.20秒 |
| Linux Python3.12 PG18 全套 | 243 passed、0 skipped、0 warning；47.33秒 |
| 容器8080／8091、程序／DB健康、auth／CSRF、非root、cloud gate | 兩個Port全部PASS；本機image ID c2dd0e0e84b4 |
| 所有 image layers 與合成秘密 canary 排除 | 10,314個檔案項目掃描PASS，四個canary皆排除並已清除 |
| 31表逐欄型別／NOT NULL／FK與最終DML審查檔 | 14個PG專用測試再次全部通過；8.01秒 |
| 原工作樹來源完整性 | 807個檔案SHA256完全一致，無變更 |

第一輪真實功能紅燈包含健康入口／backend設定6 failed、Connector／TLS安全邊界2 failed；均有修正後測試。PG初輪找出 driver Cursor 不支援 context manager，改為 closing；最初測試本身的 sessions 欄位、owner_id 名稱及超過 API六位小數限制也已依既有 schema／規格修正。Windows cp950／sandbox temp錯誤屬環境問題，不算功能紅燈。映像掃描已用測試區分 SDK 程式模組／PEM marker 常數與實際憑證內容，仍拒絕 .env／SQLite／SA JSON／真正 PEM block／canary。

最終完整連續驗證原始標準輸出保存在 `.test-runs/final-validation.log`；專用catalog案例紀錄在 `.test-runs/pg-catalog-final.log`；Pydantic在並行案例產生alias metadata warning，斷言全通過，未以filter隱藏。31表型別／NOT NULL與60條FK逐欄核對既有001–005建立的全新合成SQLite參照；兩個identity以ALWAYS確認，原工作樹資料未使用。

JUnit evidence 保存在忽略的 `.test-runs/sqlite-release.xml` 與 `.test-runs/postgres-full-final.xml`；不含真實資料。Linux 執行與 image smoke 的 stdout 結果亦記入本輪結果表。UI程式未改，本輪未重跑瀏覽器驗收或負載測試。交付前安全／建置邊界19項全部通過，git diff --check沒有空白錯誤（只有CRLF提示）。最終縮小DML審查檔的CONNECT授權範圍並加強catalog斷言後，14項專用PG案例通過；再依本文件整套指令連續跑Windows PG、Linux SQLite／PG及image smoke，整個harness exit 0，最後所有測試容器及匿名volume均清除。

## 容器與 Cloud Build

映像只包含官方 Python、鎖定 runtime 套件與 app；不包含 repository .git、測試、資料目錄、.env、SA JSON或本機工具。建置曾放入4個合成 canary 檔（含 app內 .env／SQLite／service-account.json）來驗證 context 排除；驗證後清除。映像本機 tag 為 lifeworld-api:step10-4-local，來源 label 註記基準 SHA 加 dirty，不能當已提交的產物發布。

`python -m app.serve` 監聽0.0.0.0、PORT預設8080；舊本機入口不變。/api/health保留；/health只證明程序；/ready 以 App 身分查 users/goals，不暴露連線設定，失敗503。readiness成功不代表DML已授權，這點已用只有SELECT的合成情境驗證。

K_SERVICE存在時要求PG、明確Host、Secure Cookie，業務預設503，只有健康入口可用。維持HttpOnly、SameSite=Strict、CSRF與Origin，沒有新增 CORS。若React採獨立網域，現階段不能直接以跨站cookie呼叫API，需另行評審同來源proxy或認證／CORS契約。

Cloud Build配置使用 lw-build-main，先測SQLite與真PG18合成庫，再建置API、驗證映像並push到 `asia-east1-docker.pkg.dev/life-world-513506/lw-containers/lw-api:${COMMIT_SHA}-${BUILD_ID}`。SHA需40位、Build ID需UUID形式；缺少即失敗。image label保留完整commit。沒有gcloud命令、deploy step、trigger或Web變更。參考 [Cloud Build schema](https://docs.cloud.google.com/build/docs/build-config-file-schema) 與 [substitutions](https://docs.cloud.google.com/build/docs/configuring-builds/substitute-variable-values)。

## C 未完成與限制

沒有執行 Cloud Build、Artifact Registry push、Cloud Run部署／健康請求、Cloud SQL連線、ADC／IAM或Secret Manager驗證。Connector只有本機接線／失敗替身測試，不能據此聲稱GCP連線成功。原有本機認證及DemoPolicy仍為試作規則，沒有新增正式身分服務。未做故障切換、長時間pool重連、負載與實機瀏覽器驗收。

本輪交付在獨立未提交分支，需正常程式審查／本機commit／另行授權發布；沒有推送、合併或改動原工作樹資料。正式SQLite資料轉移與雲端migration部署流程不在本輪執行範圍。

## D 由使用者在 GCP Console 完成

1. **DB權限審查**：按照 [31表／2 Sequence矩陣](database/APP_DML_REVIEW_STEP10_4.md) 與待審SQL，核對既有31表／owner後，僅增加App必要DML；schema_migrations持續禁止。先用合成資料及ROLLBACK驗證，不能重跑建表檔，也不建立劇場9表。
2. **Runtime IAM**：將 lw-api-runtime 指定為未來API執行身分，核對 Cloud SQL Client（roles/cloudsql.client）與 Cloud SQL Admin API；只對所需secret給 Secret Manager Secret Accessor（roles/secretmanager.secretAccessor）。不建立JSON Key；ADC使用執行SA。此處仍採lw_app帳密，不是IAM DB Authentication。
3. **Secret Manager**：由使用者保存lw_app密碼，Cloud Run secret env注入 LIFEWORLD_DB_PASSWORD，固定核准版本。migration密碼不注入API，也不提供給Build SA。
4. **VPC**：Cloud Run同region asia-east1，Direct VPC egress選 lw-vpc-staging／lw-subnet-staging，private-ranges-only；核對Cloud Run service agent對subnet的權限與路由。Connector需要至SQL Admin API的TCP443與Cloud SQL private IP的TCP3307，依 [官方連線埠說明](https://docs.cloud.google.com/sql/docs/postgres/connect-compute-engine) 核對egress。不能把IAM授權當成有網路路徑。依 [Direct VPC官方設定](https://docs.cloud.google.com/run/docs/configuring/vpc-direct-vpc) 審查既有角色，無需為本App授予廣泛網路管理權。
5. **Build IAM與來源**：lw-build-main只需Artifact Registry Writer（roles/artifactregistry.writer，指定lw-containers）及 Logs Writer（roles/logging.logWriter）等既有必要權限；提交建置者需要使用該SA的權限。以核准commit選本API設定，確認commit與build ID tag唯一；不新增自動deploy trigger、不動lw-web-main或舊Web服務。此處尚未替使用者觸發任何build。
6. **Cloud Run測試revision**：未來lw-api-main使用核准image digest、runtime SA、port8080、先維持IAM限制存取及業務開關false；初始可保守設min0/max2、concurrency8、pool4，仍須按實際Cloud SQL連線容量審查。不是沿用React Dockerfile或Web服務設定。

| Cloud Run變數 | 待設定值 |
|---|---|
| LIFEWORLD_DB_BACKEND | postgresql |
| LIFEWORLD_PG_CONNECTION | cloud_sql |
| LIFEWORLD_INSTANCE_CONNECTION_NAME | life-world-513506:asia-east1:lw-pg-staging-trial |
| LIFEWORLD_DB_NAME / SCHEMA / USER | life_world_dev / lw_core_draft / lw_app |
| LIFEWORLD_DB_PASSWORD | Secret Manager注入，不是明文設定檔 |
| LIFEWORLD_DB_POOL_SIZE | 4，按容量再調整 |
| LIFEWORLD_TRUSTED_HOSTS | 精確API host，加127.0.0.1,localhost供本機probe；不含scheme／port，不用* |
| LIFEWORLD_EXTERNAL_ORIGIN | 精確API HTTPS origin，例如核准的run.app URL；待實際URL確定 |
| LIFEWORLD_SECURE_COOKIES | true |
| LIFEWORLD_ENABLE_BUSINESS_API | false，雲端驗收與另行核准後才true |

Cloud Run的PORT由平台注入；K_SERVICE由平台提供。不要設定 GOOGLE_APPLICATION_CREDENTIALS、不要上傳SA JSON，也不用把private IP當成Connector的instance name。雲端probe的Host要符合明確allowlist；liveness用/health，/ready另測DB可讀，依 [健康檢查設定](https://docs.cloud.google.com/run/docs/configuring/healthchecks) 設定，避免因DB暫斷而把程序健康與資料就緒混為一談。

雲端連線、拒絕未授權請求、HTTPS Cookie／Origin、合成交易／回滾、DML權限、Secrets與日誌遮罩全部實測並另行核准後，才開啟業務流量。30天免費試用的一般備份／還原尚未具備，持續只用合成資料。

## E 發布判定

**Step 10-4 當時判定：READY FOR GCP CONFIGURATION**。本機 SQLite／真實 PG18、Python3.12 API容器、31表結構、角色／DML／identity、跨實例並行、rollback、安全入口與映像內容均已實測通過。這個判定只表示可進入使用者的 GCP Console 設定階段；GCP Build／Push／連線／部署未執行，業務流量維持關閉，不能標示雲端上線成功。
