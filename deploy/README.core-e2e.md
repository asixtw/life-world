# 8030 整合版（lw-core-e2e）M0：E2E 連線與環境確認

依據：`C:\LifeWorld_project\LIFE_WORLD_MVP_DEVELOPMENT_PLAN_20261109_v3.md`（MVP 計畫第 3 版）；M0 修正依 `LIFE_WORLD_M0_CODEX_REVIEW_20261109.md` 的 F1～F7，V3 修正依 `LIFE_WORLD_M0_CODEX_REVIEW_V2_20261109.md` 的 F2～F7，V4 修正依 `LIFE_WORLD_M0_CODEX_REVIEW_V3_20261109.md` 的 F2、F4～F7，V5 修正依 `LIFE_WORLD_M0_CODEX_REVIEW_V4_20261109.md` 的 F2、F5～F7，V6 修正依 `LIFE_WORLD_M0_CODEX_REVIEW_V5_20261109.md` 的 F6、F7。本文件只說明 M0 的程式與設定；**雲端資源尚未建立**，建立的每一步都要使用者另行核准。

## 架構

```text
瀏覽器 → Caddy HTTPS 127.0.0.1:8030（lw-core-compare.localhost）
       → 127.0.0.1:8093（gcloud run services proxy，只連 lw-core-e2e）
       → Cloud Run lw-core-e2e（本資料夾的程式；映像內有 core-e2e 的唯讀標記）
       → Cloud SQL life_world_e2e／lw_e2e_app／lw_core_draft（PostgreSQL 18.6，只有 Private IP）
```

8445（`lw-api-main` 的 e2e tag、8092、5178）完全不使用、不修改。

## 部署設定檔 `core-e2e`（`app/deployment_profile.py`）

- **啟用的依據（F1）：**
  - 專用映像（`deploy/Dockerfile.core-e2e`）以 root 建立唯讀的標記檔 `/etc/lifeworld/deployment-profile`（內容 `core-e2e`，權限 0444）。runtime UID 10001 與 Cloud Run 的環境變數都無法移除或改寫它。
  - 標記存在時一定強制驗證。`LIFEWORLD_DEPLOYMENT_PROFILE` 只能「不設定」或「等於 `core-e2e`」；設成空字串或其他值都拒絕啟動，所以不會因為覆寫而降級。
  - 標記不是一般檔案、不是 root 擁有、其他人可寫，或內容不是已知設定檔，也拒絕啟動。
  - 一般映像沒有標記：只有明確設定 `LIFEWORLD_DEPLOYMENT_PROFILE=core-e2e` 時才啟用；沒有設定時，Public Core 原有的行為完全不變。
  - `app.serve`、`python -m app`、`uvicorn app.main:create_app --factory` 都以同一個 factory 啟動，都先經過核對。
- **建連前**（`create_app` 第一步，在讀取設定物件與建立資料庫物件之前）：
  - 以下設定都必須明確存在，而且等於核准值：`LIFEWORLD_DB_BACKEND=postgresql`、`LIFEWORLD_DB_NAME=life_world_e2e`、`LIFEWORLD_DB_USER=lw_e2e_app`、`LIFEWORLD_DB_SCHEMA=lw_core_draft`、`LIFEWORLD_PG_CONNECTION=cloud_sql`、`LIFEWORLD_INSTANCE_CONNECTION_NAME=life-world-513506:asia-east1:lw-pg-staging-trial`、`LIFEWORLD_EXPECTED_DB_MARKER=LIFEWORLD_E2E_SYNTHETIC_ONLY_v1`，以及 `LIFEWORLD_DB_PASSWORD`（Secret 參照）。
  - SQLite、正式庫（`life_world_dev`／`lw_app`）、Alpha（`life_world_alpha`／`lw_alpha_app`）、Product Staging 一律拒絕。
  - 不接受注入的資料庫或設定物件。
  - M0 尚未開放的功能一律拒絕：任何 `LIFEWORLD_AI_*`、`LIFEWORLD_TASKS_*`、`LIFEWORLD_ENVIRONMENT_ID`、Google 登入、測試帳號種子與白名單；關係記憶、限流、公開 Gate 只能是 `false`；存取模式只能是 `legacy`。
  - **替代憑證（F3）：** `GOOGLE_APPLICATION_CREDENTIALS`、`GOOGLE_API_USE_CLIENT_CERTIFICATE`、`GOOGLE_AUTH_TOKEN`、`CLOUDSDK_CONFIG`、任何 `CLOUDSDK_AUTH_*` 與 `GCE_METADATA_*`，以及 gcloud 使用者 ADC 檔的預設位置存在時，都拒絕啟動。Cloud SQL Connector 照原本使用 ADC，所以只會用 Cloud Run 綁定的 runtime service account。
  - **代理設定（V3 F3）：** `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`NO_PROXY` 的任何大小寫寫法（例如 `https_proxy`、`No_Proxy`）一律拒絕啟動，所以 metadata 與 Cloud SQL 的請求不會經過外部代理。環境變數名稱比對時一律轉成大寫，ADC 覆寫變數也一樣。
- **建連後**：每一條新的實體連線（包括 pool 重新連線），在交給程式之前核對 `current_database()`、`current_user`、`session_user`、`current_schema()`、`server_version_num`（`180006`）與資料庫標記（查詢一律寫明 `pg_catalog`）。任何一項不符或查不到，就關閉這條連線。
- **連線狀態（F2）：** 核對時暫時切成 autocommit，之後一定要還原並讀回確認；最後交出的連線必須是 autocommit=False。做不到就關閉這條連線，絕不放回 pool。
  - **V3：** 切成 autocommit 之後，先讀回確認真的是 `True`，才執行身分查詢。設定失敗、讀回不符，或設定「靜默無效」（沒有錯誤但讀回仍是 False），都關閉連線、不放回 pool，而且**一條查詢都不執行**（啟動與 pool 重新連線都一樣；測試以查詢次數 0 驗證）。
  - **V4：** 基底的 `PostgresDatabase._open`（`app/postgres.py`）在**第一個 cursor 之前**就讀回確認 autocommit 為 `True`，而且驅動程式回報沒有未結束的交易（pg8000 的 `_in_transaction`）；初始化的 SHOW／SET 完成、切回交易模式後，再確認 autocommit 為 `False` 且沒有交易。任何一項不成立就關閉連線、不入池（Guard 對應為 `connection_state_unconfirmed`／`connection_state_unrestorable`）。這同時適用於沒有 core-e2e 設定檔的一般 PostgreSQL 連線；正常連線的初始化順序不變。
  - **V5：** 交易狀態必須由驅動程式明確回報：`_in_transaction` 屬性存在、型別正好是 bool、而且是 False，才算沒有交易；缺少屬性、讀取失敗、None、0、空字串或其他型別一律視為無法確認，在第一個 SQL 之前關閉連線、不入池（鎖定的 pg8000 1.31.6 提供 bool）。
- **啟動時**先建立一條連線完成核對；連線失敗或身分不符，`create_app` 丟出 `DeploymentProfileError`，服務不會啟動。之後的連線若不符，該請求回 503，不會使用那條連線。
- **注意：** Cloud SQL 若升級小版本（例如 18.7），服務會拒絕啟動，要先更新 `server_version_num`。

## 建置設定

- `deploy/Dockerfile.core-e2e`：與 `deploy/Dockerfile.api` 只差兩處：建立唯讀標記的 `RUN`，以及 HEALTHCHECK 以 `LIFEWORLD_TRUSTED_HOSTS` 的第一個主機名稱作為 `Host`（避免被 TrustedHostMiddleware 擋下）。`tests/test_core_e2e_build_config.py` 檢查。
- `deploy/cloudbuild.core-e2e.yaml`（F4，V3 改寫）：
  - 只接受兩個替換值：`_SOURCE_MANIFEST_SHA256`（封裝內來源清單的 SHA-256）與 `_PACKAGE_SHA256`（固定封裝 `.tgz` 的 SHA-256）。它們只放在 `options.env`，由 Bash 以已加引號的變數讀取，不寫進任何 Bash 程式文字，不使用 eval。
  - **tag 由建置自己產生：** `m0-<來源清單 SHA-256>-<Cloud Build 的 BUILD_ID>`。BUILD_ID 每次建置都不同（UUID），所以同一秒、同一個來源 SHA、同時建置，tag 也一定不同；不再有「先查 tag 是否存在、再推送」的步驟，也不以錯誤訊息文字（例如 `NOT_FOUND`）判斷任何事。
  - 不可覆寫：Artifact Registry `lw-containers` 已啟用 `immutableTags`（唯讀查詢確認）；即使之後有人想移動 tag，也無法覆寫。
  - 步驟：`validate-target`（專案、BUILD_ID 格式、兩個 SHA 的格式、`sha256sum -c` 來源清單、上傳檔案清單正好等於來源清單、Dockerfile 含唯讀標記）→ `verify-package`（以 `gcloud builds describe` 讀這次建置的來源物件 bucket／object／generation，限定 `life-world-513506_cloudbuild`，再以 `gcloud storage cat` 取回那個 generation 計算 SHA-256，必須等於 `_PACKAGE_SHA256`）→ 建置（標籤含來源清單、封裝與 build ID）→ 推送並記錄。
  - **provenance 綁定這次推送的 digest：** 從 `docker push` 的輸出取得 digest，並確認本機映像的 RepoDigests 包含同一個 `repo@digest`，才輸出 `LW_CORE_E2E_PROVENANCE build_id=… source_manifest_sha256=… package_sha256=… image=repo@sha256:…`。之後不再以 tag 回查 digest。
  - **V4：** 每個 Bash 步驟都開啟 `pipefail`。`docker inspect` 先單獨執行並取得自己的退出碼（不經過 pipeline），退出碼必須是 0，而且 RepoDigests 必須**正好只有一筆**、等於 `repo@<這次 push 的 digest>`，才輸出 provenance。`validate-target` 的兩份檔案清單先各自完整產生（產生器失敗就停止）再以 `cmp` 比較，不再使用 process substitution。
  - 專案、Registry、Repository、映像名稱都是固定值。不部署、不執行 `release.py`。
- `deploy/core-e2e-build-sources.txt`（F5）：建置來源的白名單。`app/` 下的檔案必須與它完全一致（`tests/test_core_e2e_build_sources.py` 檢查）。

## 本機啟動（B 資料夾之外）

`C:\LifeWorld_project\LifeWorld-STARTUP\core-e2e-8030\`：

| 檔案 | 用途 |
|---|---|
| `Start-CoreE2E-8030.ps1` | F6：需要核准的映像 digest 與服務網址（格式先核對）。唯讀核對實際承接 100% 流量的 Ready Revision（映像 digest、runtime SA、環境變數、Secret 與 Secret 別名、沒有掛載或入口覆寫）與服務網址；拒絕重複的環境變數名稱、同時有字面值與 Secret 參照、與 `latestRevision` 矛盾的明確 Revision。8093 的 `/health`、`/ready` 不跟隨轉址；8030 HTTPS 的 `/ready` 同時取得 curl 退出碼、HTTP 狀態與 body，三者都要通過（退出碼 0、HTTP 200、`status=ready`）。F7：與 Stop 互斥（具名 mutex）；每次啟動有自己的 Run ID；任何例外（包括非預期的例外）都只回收這次 Run ID 的程序，回收不完整時如實寫在錯誤訊息中。V4（F6）：`/ready` 只有 JSON object、`status` 為字串而且以序數比較精確等於 `ready` 才通過（陣列、null、布林、數字一律拒絕）；8093 與 8030 的探測都經過 `Invoke-CoreProbe`：固定的 System32 `curl.exe`、第一個參數 `-q`（不讀 curlrc）、`--noproxy '*'`、不跟隨轉址。V5：先以 .NET 的 JSON→XML 讀取器（不合併重複的鍵）確認頂層只有一個 `status`、型別是字串，重複的鍵（不論順序）一律拒絕。V6：整份 body 先依 RFC 8259 嚴格剖析（NaN、Infinity、01、1.、不合法的跳脫、未結束的字串、尾端內容都拒絕），不再轉成 PSCustomObject；只看頂層成員（名稱解碼後以序數比較、不能重複），巢狀的 `status`／`Status` 不影響判斷 |
| `Stop-CoreE2E-8030.ps1` | F7：與 Start 互斥（等待鎖，逾時以 2 結束）。只停止同一個 Run ID、而且以持有的程序 handle 證明所有權的程序：建立時間、執行檔、完整命令列、父程序都相符，紀錄的角色預期值（proxy：服務網址樣式、8093；Caddy：本資料夾的 Caddyfile、8030）也相符。子孫程序同樣以 handle 停止。證明不了就拒絕並以 1 結束；PID 已被較晚建立的程序重用時，不停止它，只移除紀錄。V4（F7）：讀取 `Process.Handle` 取得並保留真正的 OS handle（只呼叫 GetProcessById 不會保留），核對與停止都使用同一個 handle；每個子孫都各自取得 handle、核對建立時間與親子邊，所有 handle 持有到最後，停止後重新列舉，快照之後才出現的子程序也會停止。拿不到 handle、停止失敗或根程序已結束但仍有可能屬於它的程序時，保留紀錄（含沒有停止的子孫）並回報 CLEANUP INCOMPLETE，不依連接埠猜測。V5：根與中介程序都已結束時，角色的連接埠（依 `-Ports` 的順序：HTTPS、proxy）若仍有任何監聽者，無法證明它不屬於這次 Run：保留紀錄並回報 CLEANUP INCOMPLETE，不停止它；監聽者消失後，下一次 Stop 才清除紀錄。V6：刪除任何一筆紀錄之前（根程序一開始已結束、PID 已重用、或剛由 Stop 停止）都經過同一個連接埠判斷；連接埠查詢分成「沒有監聽者」「有監聽者」「查詢失敗（例如 PermissionDenied）」，只有第一種才清除紀錄 |
| `CoreE2E.Common.ps1` | 上面兩個腳本共用的核對、鎖、狀態（原子寫入）與程序函式 |
| `Caddyfile.core-e2e-8030` | 8030 的 HTTPS 站台；沿用既有已信任的本機 CA |
| `Prepare-CoreE2EBuild.ps1` | F5：Source、StageRoot 與它們的每一層父目錄都不能是 junction／符號連結；依白名單複製 87 個檔案、產生來源清單，以 `tar --format ustar` 封裝成一個 `.tgz` 固定封裝（只有一般檔案），核對後刪除工作目錄。V4：封裝必須含核准的 `deploy/cloudbuild.core-e2e.yaml`；輸出封裝路徑、封裝 SHA-256、來源清單 SHA-256 與 **Cloud Build 設定 SHA-256**。只在本機處理。V5：gzip 以壓縮等級 0（stored block）產生；gcloud 只接受 .zip／.tgz／.gz，不能改用未壓縮的 .tar |
| `Test-CoreE2EPackage.ps1` | F5（V4）：送出前核對封裝。封裝只讀一次；**解包之前**先檢查完整的 tar header：只接受 POSIX ustar 的一般檔案，拒絕 hardlink、symlink、目錄、FIFO、裝置、pax／GNU 延伸 header、重複路徑（不分大小寫）、絕對路徑、`..`、反斜線；gzip 只能有一個 member，tar 結尾之後只能是 0。再核對封裝、來源清單、Cloud Build 設定與每個檔案的 SHA-256，通過後才以同一份位元組寫到隔離目錄、從磁碟再核對一次。V5：自行解析 gzip 外框（header FLG=0、只接受 stored block、最後一個 block 之後正好是 8 位元組 trailer、之後不能有任何位元組），證明只有一個 member 而且輸入完整消耗；ISIZE 自行核對，CRC32 由 .NET GZipStream 重新解壓核對，兩邊輸出必須相同 |
| `Submit-CoreE2EBuild.ps1` | F5（V4）：R4c 的受控提交，需要封裝、來源清單、Cloud Build 設定三個 SHA-256（同一次 Prepare 的輸出）。把核對過的封裝位元組複製到全新的隔離目錄，從**這份核准封裝**取出 `deploy/cloudbuild.core-e2e.yaml` 作為 `--config`；本腳本沒有指定設定檔的參數，也不讀工作樹中的 YAML。呼叫 gcloud 前一刻再核對一次。沒有 `-Execute` 只顯示指令；`-Execute` 會執行 Cloud Build，必須先取得使用者核准。V5：封裝副本與設定檔以「唯讀、拒絕寫入與刪除」的 handle 鎖住並經由 handle 核對，一直持有到 gcloud 結束；結束後再核對一次；不輸出任何暫存路徑 |
| `tests/test_core_e2e_scripts.py` | 以替身程序與合成資料測試上面的腳本 |

R4 只能以 `Submit-CoreE2EBuild.ps1` 上傳這個固定封裝與它內含的 Cloud Build 設定，不能上傳資料夾，也不能另外指定設定檔；建置端再以 `verify-package` 與 `validate-target` 核對一次。

8030 也是舊的本機 SQLite 比較站使用的連接埠，兩者不能同時執行。

**共用 CA（W1）：** 沿用既有、已信任的本機 CA，不建立新的 Root，也不修改 8445 的 Caddy 設定。啟動前確認 CA 的四個檔案完整；設定驗證改用一次性的隔離儲存目錄；啟動後確認 root 與 intermediate 沒有改變，而且只多出 `lw-core-compare.localhost` 自己的 leaf 憑證。Windows 上兩個 Caddy 同時初始化的檔案鎖風險：**NOT VERIFIED**。

## 作品檔案用的 Cloud Storage（2026-11-11 建立，尚未接上程式）

使用者在 2026-11-11 核准新增一個 bucket 與它的讀寫權限，用途是存放作品的檔案（之後的圖片素材、匯出的 HTML／ZIP）。作品的結構與檔案清單仍然放在 Cloud SQL。

| 項目 | 設定 |
|---|---|
| 名稱 | `lw-works-e2e-513506`（只給 e2e 用） |
| 位置、等級 | `asia-east1`、STANDARD |
| 存取控制 | 統一 bucket 層級存取；禁止公開存取（enforced） |
| 生命週期、版本、保留政策 | 都沒有設定。保留多久還沒有決定，所以沒有設任何自動刪除。軟刪除是預設的 7 天 |
| 權限 | `lw-api-runtime` 在這個 bucket 上有 `roles/storage.objectCreator` 與 `roles/storage.objectViewer` |

注意：

- 服務帳號可以新增和讀取物件，不能刪除也不能覆寫。寫入要用「不存在才建立」的條件，檔名用內容雜湊；同名物件再上傳會被拒絕。
- `lw-api-runtime` 是 `lw-api-main` 所有 revision 共用的服務帳號，不只是 e2e 標籤。
- 專案擁有者、編輯者、檢視者的預設繫結是 Cloud Storage 自動建立的，沒有另外調整。
- 還沒做的：程式還沒有讀寫這個 bucket，部署腳本也還沒有把 bucket 名稱交給服務；服務帳號的權限還沒有實際用過。
- Alpha（`lw-public`，服務帳號 `lw-public-runtime`）沒有對應的 bucket，要用時另外核准、另外建立。

## 尚未完成（需要使用者逐項核准）

R1～R6：runtime SA、Cloud SQL Client、DB 密碼 Secret 的讀取權、Cloud Build、Cloud Run 服務、invoker。完成之前，**不能宣稱 E2E 連線已經通過**。
