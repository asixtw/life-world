# LIFE WORLD Step 11｜FastAPI／PostgreSQL 整合至 main

日期：2026-11-03，Asia/Taipei。本輪範圍為實際整合、重新驗證與本機 commit；未 Push、開 PR、合併或操作 GCP。API 尚未在雲端上線。

## 基準、隔離與保護

- 本輪 fetch 後的 `origin/main`：`4b920e8340087dddcfd62c7ffdc77e850d07a3d7`（PR #9 merge）。
- 新工作樹：`C:\LifeWorld_project\life-world-api-main`；短期分支：`work/api-main-integration`。從乾淨的最新 main 建立。
- Step 10-4 來源：`C:\LifeWorld_project\life-world-step10-4`，分支 `work/step10-4-pg-api`，基準 `7fbe00ba0a992cfb1403f698442936002d902c69`，保留原有 20 tracked 修改及 25 untracked 檔案。
- 原 main 工作樹保留 11 tracked 修改、6 untracked；audit 工作樹保留 6 untracked；Web 工作樹仍在 `e003a462aad27cf0643f35390507d7b23d7ea084` 且乾淨。
- 原四個工作樹均只讀比較 HEAD、porcelain 狀態與來源檔 SHA256，不 Pull／Checkout／Reset／Rebase／Clean。比對不讀取 `.env` 與資料目錄內容，測試不使用真實 SQLite 或 Cloud SQL。
- 以最新 main 為基準保護 Web YAML、main README、UI Dockerfile／nginx／README 及既有部署測試，共 8 檔逐位元組不變。共用 README、ACCEPTANCE、EVOLUTION 以舊基準三方合併，再同時保留 Web 與 API 的追加內容。

## 實際整合範圍

完整新增／修改檔案及來源分類見 [Step 11 manifest](STEP11_FILE_MANIFEST.json)。Step 10-4 的 45 檔全部納入；38 檔內容與原工作樹一致，7 檔因文件合併或 main 設定／測試更新而調整。額外新增本交接、manifest 與 API main 操作指引，共 48 檔。舊 [Step 10-4 manifest](STEP10_4_FILE_MANIFEST.json) 保留為當時尚未 commit 的歷史快照。

繼承的 Windows 依賴鎖、`scripts/setup.py`、UTF-8 讀寫及其測試一併保留：這些修正提供可重現安裝與繁中 Windows 測試相容性，不能只帶走 PG Adapter 而遺漏其依賴與工具。未攜入舊 Web 部署檔、環境、工具、真實資料、秘密或私有媒體。

API main 化同時修改 YAML、Build SA 契約測試、模擬 K_SERVICE 名稱及交接文件；新增實際 Bash substitution 語法與來源識別防護測試。`lw-build-main` 必須完全吻合；保留獨立 image `lw-api`、SHA＋Build ID tag、PG18.6 合成庫、SQLite／PG 測試、image smoke、push。YAML **沒有 deploy 步驟**。未來 Trigger `lw-api-main`、`^main$` 以及 Runtime SA／Cloud Run 的精確設定見 [API main 指引](../deploy/README.api-main.md)。

## 功能與安全界線

保留 SQLite 預設、PG18 Adapter、31 核心表／203 欄／60 FK／2 identity、Decimal／JSONB／TIMESTAMPTZ 型別契約、owner 查詢隔離與交易 advisory lock、冪等回執、原子提交／回滾及有界連線池。Owner 隔離由 service 實施，未新增 RLS。測試的 PG Runtime 使用 `lw_app`；合成庫初始化才使用專用本機管理者與 migration role，絕不把這些角色注入 API。

保留 `/health`、`/ready`、`/api/health`、非 root UID/GID 10001、`0.0.0.0:$PORT`、Secure／HttpOnly／SameSite Cookie、Trusted Hosts、Origin／CSRF 及錯誤遮蔽。Cloud SQL Connector 使用 Private IP／ADC／lazy refresh；本輪實際雲端連線尚未驗證。

Cloud SQL `lw_app` 唯讀為使用者本輪提供的狀態；本輪未查詢或變更雲端。DML 矩陣仍待審，正式寫入不可開放。`/ready` 成功僅證明必要表可讀，不代表寫入權限核准。Cloud Run 模式預設關閉業務 API；不以 `postgres` 或 `lw_migrator` 繞過權限。

## 本輪重新驗證

以下均在新工作樹實際執行，未沿用 Step 10-4 的驗收數字。

| 驗證 | 本輪實際結果 | 本機證據 |
|---|---|---|
| TDD：先要求 Build SA 為 main、尚未修改 YAML | 1 failed；錯誤明確指向舊 lw-build-stg | api-main-red.log/xml |
| API YAML 解析／Build-Test-Push 契約／Bash 語法／來源防護 | 3 passed，1.22 秒 | api-main-green.log/xml |
| Windows Python 3.14.7 SQLite 全套 | **231 passed、14 skipped**，41.47 秒 | sqlite-main.log/xml |
| PostgreSQL 18.6 實際版本 | PostgreSQL 18.6（Debian 18.6-1.pgdg13+2） | postgres-version.log |
| Windows PostgreSQL fixture 全套（含 14 個專用案例） | **245 passed、0 skipped**，74.21 秒 | postgres-main.xml、pg-container-main.log |
| Linux API Python 3.12 SQLite 全套 | **231 passed、14 skipped**，42.42 秒 | pg-container-main.log |
| Linux API Python 3.12 PostgreSQL 全套 | **245 passed、0 skipped、1 warning**，47.59 秒 | pg-container-main.log |
| API Docker build | PASS；新映像 0dc0d0343963 | api-docker-build.log、api-image.json |
| API image 精確測試依賴 | pip check：No broken requirements found | pg-container-main.log |
| 實際容器 HTTP／0.0.0.0／UID 10001／PORT | 8080 與 8091 均 PASS | pg-container-main.log |
| 全 image layers 掃描 | **10,314 檔**，DB／env／SA JSON／私鑰／合成私有資料 canary 均未發現 | pg-container-main.log |
| Web main 既有部署契約 | **9 tests、OK**，1.841 秒；所有 gcloud 為 mock | web-main-contract.log |
| 提交範圍與來源保護 | 48 檔 allowlist、AST、連結、禁止路徑、SQLite magic／私鑰／SA JSON 掃描及 diff --check 通過；4 工作樹與 Web 8 檔不變 | protected.before/after.json |

14 skipped 全部是未啟用 PG fixture 時的專用 PG 案例，已在 PG 全套實際執行。相對舊版 SQLite 229／PG 243，新增兩個 API 建置防護案例後變為 231／245；沒有刪除或放寬舊案例。初次契約驗證因 `.test-runs` 父目錄尚未建立而發生 1 個 fixture setup error；建立新工作樹專用目錄後重跑，這不是功能紅燈，未改斷言。

Linux PG 的 `test_revision_conflict_between_instances` 產生 1 個 `UnsupportedFieldAttributeWarning`（Pydantic 的 `limit` alias metadata）。測試通過，未過濾警告、未改依賴或為此放寬測試；保留為相容性追蹤項目。未以這些本機結果宣稱真實 Cloud Run HTTPS／IAM 或 Cloud SQL 連線已通過。

容器 8080 使用預設 PORT，實測 `/health`、`/ready`、`/api/health`、訪客 Auth、合法帶 token 更新及缺少 CSRF 的 403；8091 模擬 Cloud Run 設定、Secure Cookie 開關與業務關閉時的 503。HTTPS Cookie 屬性、惡意 Origin／Host 與錯誤資訊遮蔽另由全套 API 測試驗證，沒有把本機 HTTP 當成雲端 HTTPS。

本輪建置前另放置 4 個自有合成 canary（根目錄／app 下 env、credentials JSON、key），檢驗 Docker context 排除；全 layers 掃描通過，建置後只移除這 4 個已核對內容的暫存檔，未納入 Git。Harness exit 0，專用 PG／API smoke 容器及其匿名 volume 已清理。

驗證映像 ID：`sha256:0dc0d0343963bf2116a4bd94fe046e62a9c5d8156ec8ed395c323bd92ef3476b`。本機測試 label 為 `4b920e8340087dddcfd62c7ffdc77e850d07a3d7-step11-working`，表示從該 main 基準整合的未提交來源；這不是雲端發布 image。正式 Cloud Build 會在 PR 合併後使用實際 main SHA 作 label／唯一 tag。

## 命令與本機證據

在新工作樹使用獨立 `.venv`（Windows Python 3.14.7），依既有 `requirements.lock` 安裝 41 個此環境生效的鎖定套件。`PYTHONUTF8=1` 會傳入子程序。測試暫存均放 `.test-runs`，不納入 Git。

```powershell
$env:PYTHONUTF8='1'
.venv/Scripts/python.exe -X utf8 -m pytest tests -q --tb=short --basetemp=.test-runs/sqlite-main --junitxml=C:\LifeWorld_project\step11-evidence\sqlite-main.xml
.venv/Scripts/python.exe -X utf8 -m unittest discover -s deploy/tests -v
```

API Docker build 使用本機既有 WSL 隔離 daemon，從**新工作樹**根目錄以 `deploy/Dockerfile.api` 建置 `lifeworld-api:main-integration-local`；未沿用舊 API 成品。Windows 沒有原生 Docker，`LIFEWORLD_TEST_DOCKER_ARGV` 以 JSON argv 指向 WSL 的既有 Docker CLI 與專用 socket，不修改其工具檔案。

```powershell
$env:LIFEWORLD_TEST_DOCKER_ARGV='["wsl","-d","Ubuntu-24.04","-u","root","--exec","/mnt/c/LifeWorld_project/life-world-step10-4/.tools/docker/docker","-H","unix:///tmp/lifeworld-step10-4-docker/docker.sock"]'
.venv/Scripts/python.exe -X utf8 scripts/run_postgres_tests.py --host-network --container-tests --image lifeworld-api:main-integration-local --junitxml C:\LifeWorld_project\step11-evidence\postgres-main.xml
```

實際 build 命令如下（沒有 registry push 或 deploy）：

```powershell
wsl -d Ubuntu-24.04 -u root --exec env DOCKER_BUILDKIT=0 /mnt/c/LifeWorld_project/life-world-step10-4/.tools/docker/docker -H unix:///tmp/lifeworld-step10-4-docker/docker.sock build --network host --build-arg VCS_REF=4b920e8340087dddcfd62c7ffdc77e850d07a3d7-step11-working -t lifeworld-api:main-integration-local -f /mnt/c/LifeWorld_project/life-world-api-main/deploy/Dockerfile.api /mnt/c/LifeWorld_project/life-world-api-main
```

Harness 建立帶 marker 的全新 `postgres:18.6` 合成 cluster，測試後只銷毀該次容器與匿名 volume。容器測試以 read-only 方式掛載新工作樹，在可丟棄的 API Python 3.12 容器中安裝既有 `requirements.api-test.lock`、執行 pip check，再跑 SQLite／PG 全套；不修改 runtime image。最後 smoke 使用原非 root image。PG 全套中明確針對舊 SQLite 遷移／歷史非法狀態的案例仍使用 SQLite，不宣稱每一項測試都只走 PG。

本機原始日誌、JUnit 與保護快照保存在 `C:\LifeWorld_project\step11-evidence\`，不納入 Git：`api-main-red.log/xml`、`api-main-green.log/xml`、`sqlite-main.log/xml`、`postgres-main.xml`、`pg-container-main.log`、`postgres-version.log`、`api-docker-build.log`、`web-main-contract.log`、`protected.before.json`、`protected.after.json`。日誌沒有真實密碼；密碼只存在 harness 的短期合成 env 檔並清理。

## 後續與未驗證項目

GitHub Push／PR／合併需要新一輪授權；本輪只準備本機 commit。發布前重新核對遠端 main、差異、衝突、review 與實際 CI，不沿用 PR #9 的一次性例外。整合 commit 以 Git 本身查詢，避免文件自我引用 SHA。

本機驗收通過後可進入 GitHub 發布準備，合併後再由使用者建立 API Trigger 及進行首次 Cloud Build。Cloud Build 本身、Artifact Registry push、IAM、Private VPC、Secret Manager、ADC 真實連線與 Cloud Run revision 均未執行。正式業務上線另受 DML 審核與真實連線驗收阻擋；API YAML 持續維持 Build／Test／Push，不自動部署。沒有重跑 UI 瀏覽器、雲端負載或備份／還原測試。
