# React Web main 部署交接

更新：2026-11-03。現行部署來源統一為 `main`，Build SA為 `lw-build-main`，Cloud Run目標為 `lw-web-main`。本輪只在隔離工作樹修改、測試及本機commit，沒有Push、PR合併、Cloud Build或GCP部署。舊Cloud Run服務與GitHub staging分支均未刪除。

這是 `collaboration/ui-kit` 的React／Vite候選展示站，尚未接入完整FastAPI／PostgreSQL、真實登入或辨識API。POC、Staging與Production共用main中已驗證來源，不複製不同程式碼；目前此YAML只處理指定Web展示服務。

## 1 來源與變更

本次fetch的 `origin/main` 為 `0bf4ce22c1a9141c8f82629b9b19112478b2b916`，已包含PR8的health及Immutable Tags修正。工作樹為 `C:\LifeWorld_project\life-world-web-main`，短期分支為 `work/web-main-deploy`；本機commit以 `git rev-parse HEAD` 核對。本批尚未進GitHub main，Console必須等核准版本合併main後才建置。

| 檔案 | 用途 |
|---|---|
| [cloudbuild.web.yaml](cloudbuild.web.yaml) | lw-build-main、React測試／編譯、唯一tag、digest部署到lw-web-main |
| [Dockerfile](../collaboration/ui-kit/Dockerfile) | 保留Node24.22.2、pnpm12.16.1與非root Nginx；映像title改為main |
| [cloud-nginx.conf](../collaboration/ui-kit/cloud-nginx.conf) | 維持8080、/health、SPA回退與API404，本輪未修改 |
| [部署契約測試](tests/test_web_main.py) | YAML／Bash、main名稱、私有存取邊界、唯一tag、digest錯誤模擬 |
| 本文件 | 取代原README.web-staging.md的現行指引；歷史紀錄保留在第7節 |

建構context固定為collaboration/ui-kit；既有.dockerignore限制來源與fixture，runtime只複製dist。步驟依序是validate-source、react-tests、react-build、image-build、image-push、deploy-main。Dockerfile仍要求verify成功後才進build，沒有以改名繞過測試。

應用映像仍為 `asia-east1-docker.pkg.dev/life-world-513506/lw-containers/lw-web:${COMMIT_SHA}-${BUILD_ID}`。build、push、digest查詢及images使用同一tag，並保留VCS_REF及commit-sha label。先查本次tag對應的digest，通過sha256格式檢查後才以 `image@sha256:...` 部署；沒有latest或關閉Immutable Tags。同一SHA重建只要求Build ID與tag不同，不要求digest不同。

## 2 Console需要對應修改的欄位

以下為使用者後續操作目標，本輪未讀取或修改任何GCP資源。

| 欄位 | main設定 |
|---|---|
| Project | life-world-513506 |
| Trigger顯示名稱 | lw-web-main；由既有lw-web-staging在Console編輯名稱與來源，避免同時保留兩個會自動部署的Trigger |
| Region | asia-east1，沿用既有connection／repository的region |
| Event | Push to a branch |
| GitHub Repository | asixtw/life-world |
| Connection／Repository資源 | 沿用lw-github／asixtw-life-world；核對既有實際值，不重建連線 |
| Repository resource | projects/life-world-513506/locations/asia-east1/connections/lw-github/repositories/asixtw-life-world |
| Branch Regex | ^main$ |
| Configuration | Repository內Cloud Build configuration file |
| Build YAML | deploy/cloudbuild.web.yaml |
| Trigger Build SA | lw-build-main@life-world-513506.iam.gserviceaccount.com |
| Included files | 保留collaboration/ui-kit/**、deploy/cloudbuild.web.yaml |
| Substitutions | 使用內建PROJECT_ID、COMMIT_SHA、BUILD_ID，不手填固定tag或SHA |
| Logging | CLOUD_LOGGING_ONLY |
| Cloud Run target | lw-web-main，由YAML指定 |
| Runtime SA | lw-web-runtime@life-world-513506.iam.gserviceaccount.com |
| Port／容量 | 8080；1 CPU、256Mi、min0／max2、concurrency80、timeout60秒，維持原值 |
| Cloud Run label | environment=main；保留app、component、commit-sha |

在Cloud Build Triggers找到原Trigger，選Edit核對上表再儲存，名稱、branch與SA須一致。[官方更新方式](https://docs.cloud.google.com/build/docs/automating-builds/create-manage-triggers#update_a_build_trigger)

Trigger啟動建置時以Trigger指定的SA為準，所以必須同時將Console改為lw-build-main，不能只改YAML。[官方SA行為](https://docs.cloud.google.com/build/docs/securing-builds/configure-user-specified-service-accounts)

lw-web-main是新的指定服務目標，Cloud Run不會因此把既有lw-web-staging原地改名。本批不搬移舊URL、網域、流量或IAM，不刪除舊服務。使用者須在後續Cloud Run驗收確認新目標與私人存取；不要把單一main程式主線誤解成必須刪除現有服務。

## 3 私人存取與IAM前置

YAML維持沒有allow-unauthenticated、no-invoker-iam-check或IAM policy命令，也沒有新增Invoker授權。Cloud Run預設執行Invoker IAM檢查，使用者後續在Console維持Require authentication，不授allUsers／allAuthenticatedUsers；既有服務的IAM不由本管線改寫。[官方私人／公開存取機制](https://docs.cloud.google.com/run/docs/authenticating/public)

使用者已提供以下完成狀態，本輪沿用，不冒充GCP實查：

| 主體／資源 | 已完成前置（使用者提供） |
|---|---|
| lw-build-main | 已建立；Cloud Run Developer、Logging Writer已授予 |
| lw-build-main → lw-containers | Artifact Registry Writer已授予 |
| lw-build-main → lw-web-runtime | Service Account User已授予 |

Trigger操作人員對lw-build-main的actAs、既有source-fetch連線與Cloud Run service agent權限仍由使用者核對。此靜態站runtime不額外需要DB／Storage／Editor／Owner角色；不要求SA JSON Key、不自動擴權、不修改Cloud SQL或VPC。

## 4 本機驗證方式

從Repository根目錄執行，Python部署測試依賴獨立列於deploy/tests，不變更FastAPI依賴：

```sh
python -m pip install -r deploy/tests/requirements.txt
python -m unittest discover -s deploy/tests -v
docker build --build-arg VCS_REF="$(git rev-parse HEAD)" -f collaboration/ui-kit/Dockerfile -t lifeworld-web:main-local collaboration/ui-kit
python deploy/tests/smoke_web_image.py --image lifeworld-web:main-local
```

Docker建置會執行既有 `pnpm test`、TypeScript／Vite build與 `nginx -t`。需要獨立跑前端時，在collaboration/ui-kit執行 `pnpm install --frozen-lockfile`、`pnpm test`、`pnpm run build`。本輪實際前端驗證在Linux Docker內，不借用其他dirty工作樹的node_modules。

部署測試的Shell用本機函式攔截所有gcloud；兩個Build ID、六個來源guard、有效／空白／短／非十六進位digest、查詢及部署失敗都在本機驗證，不會呼叫真正GCP命令。Windows需Git Bash與允許MSYS IPC的本機執行環境。

smoke腳本使用額外的python:3.12-slim作為HTTP探針，與被測Nginx共用無外網namespace，不佔用host port或既有API服務。

本機HTTP驗收需確認 `/health` 200／ok、首頁及SPA深連結正常、API／不存在靜態檔／隱藏檔／source map均404，index.html為no-store，runtime非root。這些不等於驗證Cloud Run的IAM。

## 5 本輪結果與未完成事項

本輪在Windows的Git Bash與WSL Ubuntu24.04任務專用Docker29.7.0執行；Docker使用私有socket，未變更系統服務或現有容器。建構來源與測試目錄都是本隔離工作樹。

| 實際驗證 | 本輪結果 |
|---|---|
| YAML／Bash／部署契約 | 9 tests通過，0失敗、0跳過；含六個來源guard與七個假gcloud子案例 |
| Docker內既有React測試 | 18個測試檔、55 tests通過，0失敗、0跳過 |
| TypeScript及Vite production build | 通過，123個modules；沒有改pnpm-lock.yaml |
| Docker runtime／nginx -t | 多階段建置成功，build及啟動後nginx -t均通過 |
| 8080本機HTTP | 9項通過：health、首頁、SPA、index快取、API／不存在資產／隱藏檔／map拒絕 |
| 非root／映像 | UID101；title為main；runtime不含src／node_modules／.env／package.json |

有效紅燈：修改前的lw-build-stg／staging映像title不符合新契約，且deploy-main步驟缺失；修改後9項全綠。沒有放寬既有測試斷言。image只保存在本機tag lifeworld-web:main-local，沒有推送Artifact Registry。

Node基底本輪digest為sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c；Nginx基底為sha256:7377697a821c131a924a7105fafbe7414db4e9fcc77a6f08f776f33f141ec3f8，保留原Dockerfile版本tag。這是本輪下載紀錄，不代表往後tag不會更新。

原始建置與smoke輸出保存在本機工作區外層的web-main-docker-build.log、web-main-smoke.log；不隨程式commit。新測試腳本已隨本批程式交付，可自行重跑。

未執行GCP IAM讀取、Cloud Build、Artifact Registry Push、Cloud Run Deploy或真實服務請求。私人IAM、source-fetch及lw-web-main雲端revision均待後續使用者驗收。沒有修改或中斷PG／FastAPI工程，也沒有刪Git分支／Cloud Run服務。

## 6 後續交付順序

1. 審查本機commit，另行授權Push及PR合併至main；本輪不Push或Merge。
2. 確認main實際包含本次YAML及文件，再由使用者於Console更新Trigger名稱、^main$、Build SA與YAML路徑。
3. 另行核准首次main建置／部署，核對來源commit、唯一tag、Artifact Registry digest及lw-web-main revision一致。
4. 以具權限身分確認/health與展示頁；未授權呼叫維持拒絕。保留現有私人存取原則及舊服務，待另案評估退役。

## 7 歷史驗證紀錄

以下保留當時來源與結果。歷史中的staging、lw-build-stg及deploy-staging只描述舊版本，不是現行操作指引。

### 2026 11 02 原始碼基準


本批以 main `afbe0460ba77bdc03fa0cce85b1900aa59053f6d` 為基準，新增五份部署設定與說明，不修改 UI、正式 App 或資料庫。

該基準已包含完整 ui-kit：package.json 指定 pnpm 12.16.1；React 19.2.0、Vite 7.1.12、TypeScript 5.9.3、Vitest 3.2.4；pnpm-workspace.yaml 允許 esbuild。lockfile 有環境與套件兩個 YAML document，不能只讀第一段就誤判缺依賴。

建構需有完整 package.json、pnpm-lock.yaml、pnpm-workspace.yaml、src、assets 等來源。發布副本已包含來源及本批設定；實際 Linux 容器與 GCP 驗證仍待完成，不能據此宣稱已上線。


### 2026 11 02 初次驗證與2026 11 03 Immutable Tags修正


- 使用 Node 24.22.2（Darwin arm64）與 pnpm 12.16.1，在 main 基準的隔離副本重驗。
- 完整 ui-kit 的隔離副本：`pnpm install --frozen-lockfile` 成功，沒有改 lockfile；`pnpm test` **18 個測試檔／55 項通過**，`pnpm run build` **tsc 與 Vite build 成功**。
- 本輪不執行既有 Windows Chrome 專用視覺腳本，也未修改其路徑；以上不是新 UI 或瀏覽器流程驗收。
- 本輪 PATH 找不到可用 Docker／Nginx／gcloud；因此 Docker build、nginx -t、真實容器 HTTP、Cloud Build、Artifact Registry push、IAM 與 Cloud Run 都未實測。Dockerfile 中的 nginx -t 留作未來 build gate。
- 已執行 YAML 解析、Docker stage／context 結構、Project／Region／兩個 SA／image 路徑一致性、Cloud Build 替換後的 Bash 語法，以及正確 SHA／空 SHA／短 SHA／錯誤 Project 四個來源護欄案例，全部通過。Nginx 只核對文字結構與路由規則，不能代替 nginx -t 或 HTTP 實測；這些檢查亦不代表 Cloud Build 已接受配置。
- Node／pnpm／Nginx image 的 Linux 執行相容性仍需首次 Cloud Build 驗證；本機 Darwin React 通過不能冒充 Linux 容器通過。

#### 2026 11 03 Immutable Tag 衝突修正驗證

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


## 官方依據

- [Cloud Build變數與$$逸出](https://docs.cloud.google.com/build/docs/configuring-builds/substitute-variable-values)
- [Artifact Registry Immutable Tags與digest](https://docs.cloud.google.com/artifact-registry/docs/docker/names)
- [Cloud Run container port契約](https://docs.cloud.google.com/run/docs/container-contract)
- [非root Nginx映像](https://github.com/nginx/docker-nginx-unprivileged)
