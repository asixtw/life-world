# Step 07｜React UI 候選展示站的 GCP Staging 交付

更新：2026-11-03（Immutable Tag 修正見 §5.1）。**2026-11-02 原始批次只發布部署設定，未建立 Trigger／GCP 資源、未部署；下文「本輪」保留該批次紀錄。**這是 `collaboration/ui-kit` 的 React／Vite gallery，不是完整 Life World 正式網站；沒有 FastAPI、SQLite、真實登入或辨識 API。

## 1. 原始碼基準與本機差異

本批以 main `afbe0460ba77bdc03fa0cce85b1900aa59053f6d` 為基準，新增五份部署設定與說明，不修改 UI、正式 App 或資料庫。

該基準已包含完整 ui-kit：package.json 指定 pnpm 12.16.1；React 19.2.0、Vite 7.1.12、TypeScript 5.9.3、Vitest 3.2.4；pnpm-workspace.yaml 允許 esbuild。lockfile 有環境與套件兩個 YAML document，不能只讀第一段就誤判缺依賴。

建構需有完整 package.json、pnpm-lock.yaml、pnpm-workspace.yaml、src、assets 等來源。發布副本已包含來源及本批設定；實際 Linux 容器與 GCP 驗證仍待完成，不能據此宣稱已上線。

## 2. 檔案與管線

| 檔案 | 用途 |
|---|---|
| `collaboration/ui-kit/Dockerfile` | Node 24.22.2、pnpm 12.16.1、frozen install → verify → build → 非 root Nginx runtime |
| `collaboration/ui-kit/cloud-nginx.conf` | 8080、SPA 路由、API 404、`/health`、避免隱藏檔／map 外洩 |
| `collaboration/ui-kit/.dockerignore` | ui-kit 建構 context 白名單，排除快取、私人內容及環境檔 |
| `deploy/cloudbuild.web.yaml` | 來源檢查 → React 測試 → build → 映像 → push → digest 部署 |

Docker context 固定是 `collaboration/ui-kit`，不使用 Repository 根目錄，不變更團隊根 `.dockerignore`。既有測試會讀 assets、content、evaluation 的 fixture，所以保留在建構階段；runtime 僅複製 `dist`，不含 node_modules、測試、作者文件或 DB。

Cloud Build 的三次 docker build 使用 verify／build／runtime targets；同一建構可重用 daemon layer cache，沒有 cache 時仍必須通過測試再編譯。Dockerfile 的正常 runtime 建置也不能跳過 verify。不是 vite dev server。

應用映像：`asia-east1-docker.pkg.dev/life-world-513506/lw-containers/lw-web:<完整 COMMIT_SHA>-<BUILD_ID>`，Cloud Build 寫法為 `${COMMIT_SHA}-${BUILD_ID}`。Artifact Registry 永久保留 Immutable Tags；同一 Commit 重新建立 Cloud Build 時會取得不同 BUILD_ID，因此使用不同 tag，不再因重用 Commit SHA tag 而衝突。既有 tag 仍不可改指向其他 digest，也不刪除既有映像。

`image-build`、`image-push`、`deploy-staging` 的 digest 查詢及 `images` 使用完全相同的 tag。push 後查詢本次 tag 的實際 digest，通過 SHA-256 格式檢查後，以 `image@sha256:...` 部署。非 Git Trigger 缺少 40 位 SHA 仍會在第一步失敗，不改用 latest；Docker build arg `VCS_REF` 與 Cloud Run `commit-sha` label 繼續保留完整 Git SHA，另記錄 BUILD_ID 以追溯每次建置。回復以 Cloud Run revision／digest 為準。

基礎映像採版本 tag：Node 24.22.2-bookworm-slim、nginxinc/nginx-unprivileged 1.28-alpine；本輪沒有 Docker pull 或 CVE 掃描。應用 SHA 可追溯，但不代表基礎映像完全不可變；正式核准可再固定驗證過的 base digest。不要虛構尚未拉取的 digest。

## 3. GCP Console Trigger 精確設定

以下是要由人員建立的設定，**本輪沒有實際建立或修改**：

| 欄位 | 填入值 |
|---|---|
| Project | `life-world-513506` |
| Trigger name | `lw-web-staging` |
| Region | `asia-east1`，不得選 global；須與既有 2nd gen connection／repository 一致 |
| Event | Push to a branch |
| Source generation | 2nd generation |
| Connection | `lw-github` |
| Repository | `asixtw-life-world`（GitHub `asixtw/life-world`） |
| Repository resource | `projects/life-world-513506/locations/asia-east1/connections/lw-github/repositories/asixtw-life-world` |
| Branch regex | `^staging$`（本交付建議固定專用分支；不匹配 main 或所有 feature 分支） |
| Configuration | Cloud Build configuration file，Repository 路徑 |
| Config location | `/deploy/cloudbuild.web.yaml`；Repository 相對路徑為 `deploy/cloudbuild.web.yaml` |
| Build service account | `lw-build-stg@life-world-513506.iam.gserviceaccount.com` |
| Included files | `collaboration/ui-kit/**`、`deploy/cloudbuild.web.yaml` |
| Substitutions | 無額外自訂值；PROJECT_ID、BUILD_ID 是 Cloud Build 內建值，COMMIT_SHA 由 Git Trigger 提供 |
| Logging | YAML 已指定 `CLOUD_LOGGING_ONLY` |

先經團隊流程讓 staging 分支包含完整 ui-kit 與本輪設定，再建立 Trigger。本輪未建立 staging 分支。Google 官方指出 Trigger 實際採用 Console 指定的 build SA，因此不能只看 YAML 的 serviceAccount；兩邊必須同為 lw-build-stg。[官方服務帳戶說明](https://docs.cloud.google.com/build/docs/securing-builds/configure-user-specified-service-accounts)

部署目標固定 `lw-web-staging`，區域 asia-east1，Runtime SA `lw-web-runtime@life-world-513506.iam.gserviceaccount.com`，8080，CPU 1／256 MiB／min 0／max 2／concurrency 80／timeout 60 秒。這些是本次展示站初始設定，後續可依實測調整，不代表產品 SLA。

未加 `--allow-unauthenticated` 或 IAM policy 命令：新服務預設需驗證，既有服務的 IAM 不會由本管線主動改寫。若既有服務已公開，這份設定也不會自動收回公開權限，須在 Console 確認。私人 staging 可由授權人員使用 Cloud Run proxy／身份驗證方式驗收；不要為了開頁面臨時建立 SA JSON Key。

## 4. IAM 核對表：需求已列，現況未讀取

使用者提供的 Project、Region、帳戶及資源名稱彼此一致。**本輪 PATH 找不到可用 gcloud，也沒有讀取 GCP IAM；不能確認現有 bindings 已足夠。**Jerry 需在 Console 逐項核對，不能把「帳戶已建立」當成「角色已授予」。

| 主體／資源 | 必要能力／建議最小角色 | 現況 |
|---|---|---|
| lw-build-stg → `lw-containers` Artifact Registry | `roles/artifactregistry.writer`，包含 push／pull／讀 digest；限該 repository | 未驗 |
| lw-build-stg → Cloud Run | `roles/run.developer`；首次建立服務需要 project 範圍 create，既有服務更新可再限縮 | 未驗 |
| lw-build-stg → lw-web-runtime | 該 SA 上的 `roles/iam.serviceAccountUser`（actAs） | 未驗 |
| lw-build-stg → Cloud Logging | project 上 `roles/logging.logWriter`，搭配 CLOUD_LOGGING_ONLY | 未驗 |
| Trigger 建立者／執行者 → Cloud Build | 適當 Cloud Build Editor／自訂 triggers／builds 權限，以及對 lw-build-stg 的 actAs | 未驗 |
| 2nd gen source fetch | 保留既有 Cloud Build service agent／connection 權限；若 source-fetch 顯示 accessReadToken 欠缺，由管理員核對實際失敗 principal，必要時僅授該 repo 的 `roles/cloudbuild.readTokenAccessor` | 未驗 |
| Cloud Run service agent → Artifact Registry | 同 project 正常由 Google 的 Cloud Run service-agent 角色提供拉映像能力；勿把 service-agent 角色授給 runtime/build SA | 未驗 |
| lw-web-runtime | 此純靜態站不呼叫 Google API，不額外要求 DB、Storage、Editor 或 Owner 角色 | 未驗 |

若部署未修改 IAM，無需為此一律授 run.admin；若未來決定公開服務、調整 IAM 或 source-fetch 政策，另審相應權限。本管線不是 `gcloud run deploy --source`，不要混用 source build 的角色要求，也不要求 runtime 擁有建構權限。遇 serviceusage.services.use 等 quota-project 錯誤時，另由管理員依該 principal 審查，不自動擴權。

## 5. 本輪驗證及限制

- 使用 Node 24.22.2（Darwin arm64）與 pnpm 12.16.1，在 main 基準的隔離副本重驗。
- 完整 ui-kit 的隔離副本：`pnpm install --frozen-lockfile` 成功，沒有改 lockfile；`pnpm test` **18 個測試檔／55 項通過**，`pnpm run build` **tsc 與 Vite build 成功**。
- 本輪不執行既有 Windows Chrome 專用視覺腳本，也未修改其路徑；以上不是新 UI 或瀏覽器流程驗收。
- 本輪 PATH 找不到可用 Docker／Nginx／gcloud；因此 Docker build、nginx -t、真實容器 HTTP、Cloud Build、Artifact Registry push、IAM 與 Cloud Run 都未實測。Dockerfile 中的 nginx -t 留作未來 build gate。
- 已執行 YAML 解析、Docker stage／context 結構、Project／Region／兩個 SA／image 路徑一致性、Cloud Build 替換後的 Bash 語法，以及正確 SHA／空 SHA／短 SHA／錯誤 Project 四個來源護欄案例，全部通過。Nginx 只核對文字結構與路由規則，不能代替 nginx -t 或 HTTP 實測；這些檢查亦不代表 Cloud Build 已接受配置。
- Node／pnpm／Nginx image 的 Linux 執行相容性仍需首次 Cloud Build 驗證；本機 Darwin React 通過不能冒充 Linux 容器通過。

### 5.1 2026-11-03｜Immutable Tag 衝突修正驗證

本次來源為 staging `ca7a6f55e795ce8ea612f01066626cb7d687cbce`，只調整映像 tag 與本文件；以工作分支／PR 交付，由管理者審查後合併至 staging。使用者回報該來源的 React 測試、編譯與容器建構已通過，但 image-push 因既有 Immutable Tags 拒絕重用 SHA tag；此回報不列為本次重跑結果。

- 在專案外的隔離目錄，以 Python 3.14、PyYAML 6.0.3 解析 YAML，按 Cloud Build 內建變數及 `$$` 規則做單次替換，再以 Git Bash 5.3.15 執行 `bash -n` 及 Shell 行為驗證：**46 項檢查通過、0 失敗、0 跳過**。
- 同一完整 Commit SHA 搭配 `11111111-1111-4111-8111-111111111111` 與 `22222222-2222-4222-8222-222222222222` 兩個測試 BUILD_ID，產生不同且格式合法的 tag；每次的 image-build、image-push、digest 查詢及 images 均一致。舊設定則在兩個 BUILD_ID 下得到同一 tag，重現衝突條件。
- 六個來源護欄案例：合法 SHA／Project 成功；空 SHA、短 SHA、過長 SHA、非十六進位 SHA、錯誤 Project 均拒絕。
- 七個模擬 gcloud 案例：兩次建置皆查詢各自 tag 的實際 digest，並以 `image@sha256:...` 部署；空／過短／非十六進位 digest、查詢失敗均在部署前停止，部署命令失敗亦回傳失敗。所有 gcloud 呼叫由測試函式攔截，沒有呼叫真實 GCP。
- 已比對所有既有資源設定、SHA 驗證、VCS_REF 與 commit-sha label 均保留；Nginx 與 `/health` 未修改。本次未重跑 React／Docker，未執行 Cloud Build、Artifact Registry push 或 Cloud Run 部署。

首次合併後的 GCP 驗收仍須由管理者確認：

1. Trigger 能解析內建 `COMMIT_SHA`／`BUILD_ID` 與保留的 `$$` 逸出；image-push 及建置結尾 images 上傳／紀錄均成功。
2. 以相同修正後 Commit 重建兩次，核對不同 BUILD_ID 對應不同 tag，兩個 tag 均保留且 Immutable Tags 仍啟用。映像內容可能相同，不要求兩次 digest 必須不同。
3. 核對每次 tag 查出的 Artifact Registry digest 與 Cloud Run revision 的部署 digest 相同，記錄 Git SHA、BUILD_ID、tag、digest 與 revision。
4. 確認原 Project、Region、兩個服務帳戶、Cloud Run 名稱、Port、IAM、Ingress、Autoscaling 保持既有設定，並依 §6 驗證 `/health` 為 200／ok。

## 6. 團隊後續驗收（本輪未執行）

完整原始碼與設定一起準備後，可在具 Docker 的環境從 Repository 根目錄測試：

```sh
docker build --build-arg VCS_REF=local-unpublished -f collaboration/ui-kit/Dockerfile -t lw-web-local collaboration/ui-kit
docker run --rm -p 127.0.0.1:8080:8080 lw-web-local
```

容器啟動後，在另一個終端機確認健康端點；預期 HTTP 200，內容為 `ok`：

```sh
curl -fsS -i http://127.0.0.1:8080/health
```

核對 `/` 為 UI gallery、`/health` 為 200／ok、`/candidate/deep-link` 可 SPA 回退；`/api`、`/api/missing`、`/missing.js`、隱藏檔與 source map 為 404。檢查 index.html 不被長快取，現有圖像／腳本不破圖。

首次 Trigger 執行時，依序看到 validate-source、react-tests、react-build、image-build、image-push、deploy-staging 成功。Artifact Registry 記錄完整 Git SHA＋BUILD_ID tag；Cloud Run revision 的 digest 與 pushed image 相同、port 8080、runtime SA 正確；確認未連正式 DB 或注入秘密。記錄 build ID、Git SHA、digest、revision 與 URL，不把 gallery 稱為完整 Life World。

回復以既有成功 Cloud Run revision 切回流量或指定已驗證 digest，由授權人員操作；不以 latest 猜版本。本輪不執行回復或部署命令。

## 官方依據

- [Cloud Build 內建替換變數與 $$ 逸出](https://docs.cloud.google.com/build/docs/configuring-builds/substitute-variable-values)
- [Artifact Registry tag、digest 與 Immutable Tags](https://docs.cloud.google.com/artifact-registry/docs/docker/names)

- [Cloud Build user-managed SA 與 logging](https://docs.cloud.google.com/build/docs/securing-builds/configure-user-specified-service-accounts)
- [2nd gen GitHub Trigger 與 Region](https://docs.cloud.google.com/build/docs/automating-builds/github/build-repos-from-github?generation=2nd-gen)
- [Cloud Run container port 契約](https://docs.cloud.google.com/run/docs/container-contract)
- [Cloud Run deploy IAM](https://docs.cloud.google.com/run/docs/reference/iam/roles)
- [Cloud Build granular IAM](https://docs.cloud.google.com/build/docs/iam-roles-permissions)
- [非 root Nginx、8080 與 /tmp PID](https://github.com/nginx/docker-nginx-unprivileged)
