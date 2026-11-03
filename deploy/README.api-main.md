# LIFE WORLD API main 建置交接

此設定將 FastAPI／PostgreSQL 工程整合至 `main`，目前只執行 **Build／Test／Push**，沒有自動部署。Step 11 本機驗證及發布狀態見 [整合交接](../docs/STEP11_API_MAIN_INTEGRATION.md)；[Step 10-4](../docs/STEP10_4_PG_API_HANDOFF.md) 保留歷史紀錄。

## GitHub 發布與未來 Console 設定

本輪只建立本機 commit；尚未 Push、建立 PR 或合併。後續須另外取得授權，將 `work/api-main-integration` 推送、以 PR 審查並合併 `main`，再選已合併的 main SHA 進行雲端建置。遠端實際 CI 應重新核對，不沿用 PR #9 的一次性無 CI 授權。

首次 API 建置可由使用者在 Console 建立以下 Trigger；本輪未建立或修改任何 GCP 資源。

| 欄位 | 設定 |
|---|---|
| Project | `life-world-513506` |
| Region／Artifact Registry location | `asia-east1` |
| Trigger 名稱 | `lw-api-main` |
| Repository | `asixtw/life-world` |
| Branch Regex | `^main$` |
| Build configuration | Repository YAML：`deploy/cloudbuild.api.yaml` |
| Build Service Account | `lw-build-main@life-world-513506.iam.gserviceaccount.com` |
| Artifact Registry repository | `lw-containers` |
| Image | `asia-east1-docker.pkg.dev/life-world-513506/lw-containers/lw-api:${COMMIT_SHA}-${BUILD_ID}` |
| Dockerfile | `deploy/Dockerfile.api` |
| 未來 Cloud Run service | `lw-api-main`（不由本 YAML 建立） |
| 未來 Runtime Service Account | `lw-api-runtime@life-world-513506.iam.gserviceaccount.com` |

建置會拒絕缺少或格式錯誤的來源 SHA／Build ID。每次 build 使用不同 tag，重建相同 commit 也不重用舊 tag，支援 Immutable Tags。保留 SQLite 全套、PostgreSQL **18.6** 合成庫全套、API image build、容器 smoke 與各 layer 秘密掃描後才 push。YAML 的 `images` 也是同一 tag，不使用 `latest`。合成庫與密碼只供該次建置，不連 Cloud SQL、不讀 Secret Manager。

YAML、Trigger 與執行身分都應使用 main；實際 branch 篩選由 Trigger 的 `^main$` 控制。Web 仍使用獨立的 [Web main 設定](README.web-main.md)，本輪不修改其 YAML、Runtime SA、private IAM 或已存在服務。

## 首次建置後的人工 API 連線驗證

先確認雲端 Build／Test／Push 真正成功並記下 image digest；本機通過不能替代此結果。由使用者在 GCP Console 建立私人 `lw-api-main`，選該次核准 digest、Runtime SA `lw-api-runtime`、port `8080`。API 監聽 `0.0.0.0:$PORT`，執行 UID/GID `10001`；保留 IAM 驗證，不授予公開存取。

檢查 Private VPC 網路路徑、Cloud SQL Client、Secret Manager 及 ADC 後，使用 `LIFEWORLD_PG_CONNECTION=cloud_sql`，由 Secret Manager 注入 `lw_app` 密碼。禁止 Service Account JSON 金鑰。Connector 使用 Private IP／lazy refresh；既有 Cloud SQL／VPC 真實名稱不因 main 化擅自改名，應由 Console 核對後設定。完整環境變數清單見歷史交接的設定表；以本文件的 main 名稱為準。

必須設定明確 `LIFEWORLD_TRUSTED_HOSTS`、HTTPS `LIFEWORLD_EXTERNAL_ORIGIN`，Secure Cookie 不可關閉。保持 `LIFEWORLD_ENABLE_BUSINESS_API=false`，先驗 `/health`、`/api/health` 與 `/ready`。`/health` 只表示程序正常；`/ready` 表示可讀必要資料表，**不保證 DML 已獲准**。

依使用者本輪提供的狀態，Cloud SQL `lw_app` 仍只有唯讀權限。正式寫入阻擋為 [DML 權限矩陣](../docs/database/APP_DML_REVIEW_STEP10_4.md) 尚未審核。`deploy/postgres/app_dml_grants.review.sql` 僅為待審草案，本輪只套用在獨立本機合成庫。不可使用 `postgres`、`lw_migrator` 當 Runtime，也不可為了 readiness／測試提高雲端權限。待權限審核、真實連線及 Auth／CSRF 驗證完成，再決定開放業務與是否另以 PR 增加 Cloud Build 部署步驟。

本輪沒有 GCP build、registry push、Cloud Run deploy 或真實 Cloud SQL 連線證據，API 尚未在雲端上線。
