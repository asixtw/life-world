# API 正式模板恢復與 E2E 隔離提案

2026-11-06；**只完成唯讀調查、請求格式驗證及方案準備，未獲准也未執行服務設定／IAM／流量變更。** 這是一次性環境修復，不取代正常 main CI/CD，也不涉及 DB DML、Migration 或 GRANT。

## E2E 的實際部署入口

- 現有 Cloud Build 只有啟用中的 API／Web main Trigger，未找到獨立 E2E 部署 Trigger。repo 的 `e2e_plan.py`／`e2e_acceptance.py` 讀取快照或發 HTTP，`run_e2e_local.py` 僅跑本機合成環境；它們不是雲端部署器。
- `deploy/README.api-e2e.md` 及既有 E2E worktree 的同名文件仍要求在 `lw-api-main` 用 Console 建測試 Revision，會改掉最新服務模板。近期稽核也確有使用者身分透過 `gcloud.run.deploy` 操作該服務：台北時間 11/06 02:12、02:24、03:01。e2e Revision `00008-kgk` 建立於03:01:37，creator 與該 CLI 操作者相符；03:04另有 update-traffic 操作。不能把「沒有 E2E Trigger」當成「已停止人工／代理程式部署」。
- 必須先由 Owner 確認 E2E 部署已停止或改向；否則一次性恢復後，下一次舊操作仍會再次污染 main 模板。這個調查沒有停用排程、取消其他人的程序或通知同仁。

最小隔離提案（**另需新資源授權，未建立**）：使用獨立 Cloud Run Service，候選名稱 `lw-api-e2e`，是否已有同名資源在核准前確認。重用既有 E2E image digest、`life_world_e2e`／`lw_e2e_app`、E2E Secret參照、Runtime SA、Private VPC與Cloud SQL instance；不新建 DB。保留 IAM Required，E2E呼叫者僅有目標服務所需權限。可保留原本「stable 100%／測試tag 0%」的受控模式，但放在該獨立服務內。需改向的最小範圍是 E2E 部署／快照命令、`e2e_safety.py` 的服務白名單、local fixture、驗收指引及該服務的 URL／audience。main 上既有 e2e／prestable／hostfix Tag 不移動、不刪除。本機 Caddy／hostfix 路徑不改。這先隔離模板／流量，不宣稱已另做 Runtime SA 權限隔離。

## 一次性恢復的精確差異

唯一來源：本輪接收100%正式流量的 `lw-api-main-c-94975cd3a6854941b1705c5634c777b3`。實際執行前須重新解析當時100%的具名 Revision，不能永久硬編碼本快照名稱；若不是唯一100%、正在 reconciling、來源或 Tag 變動就停止重審。

|欄位|目前 latest/e2e|恢復正式來源|
|---|---|---|
|Database|`life_world_e2e`|`life_world_dev`|
|DB User|`lw_e2e_app`|`lw_app`|
|DB Secret參照|`lw-pg-e2e-password:1`|`lw-pg-app-password-main:1`|
|Business API|`false`|`true`|
|Trusted Hosts|含額外 prestable hostname|完整採用正式 Revision 的 Host 清單；不改 prestable Revision／Tag|

已完整比對而相同的執行設定：同一 image digest `sha256:e7cf92e11bde21704a824c56eea58a773c98c6491bc646849f1881a101607c21`、`lw-api-runtime`、Cloud SQL instance `lw-pg-staging-trial`、其餘環境變數、Private VPC `lw-vpc-staging/lw-subnet-staging`（private-ranges-only）、CPU 1／RAM512Mi、concurrency80、timeout300s、startup TCP8080（timeout240s／period240s／failureThreshold1），沒有另設 liveness probe。Origin保持正式 `https://lw-api-main-162310640466.asia-east1.run.app`。Secret僅核對參照，沒有讀取值。

服務層 max instances=3、IAM／Ingress及其他服務層欄位不在本次 updateMask，原樣保留；這些不是從 Revision 猜出的歷史服務設定。

## 核准後的執行方式（本輪未執行）

1. E2E部署改向／暫停已確認，正式Pipeline沒有活動中的發布鎖，Cloud Run 已收斂。重新GET服務與唯一正式Revision，保存完整原template、resolved traffic、全部Tag、etag、generation；只保存配置與Secret參照，不含Token／Secret值。
2. 根據官方 v2 RevisionTemplate schema，把正式Revision所有可寫模板欄位完整複製，包含containers整體（所有env／Secret參照、ports、resources、probes）、VPC、SA、容量及metadata。只移除輸出專用欄位及既有revision名稱，不用會漏掉其他env或綁定的局部set-env命令。本輪來源具備client、clientVersion、containers、labels、maxInstanceRequestConcurrency、serviceAccount、timeout、vpcAccess；如果屆時有其他合法模板欄位也必須完整處理，遇未知設定停止。
3. 以新讀取的etag送出一次版本化更新：`PATCH https://run.googleapis.com/v2/projects/life-world-513506/locations/asia-east1/services/lw-api-main?updateMask=template,traffic`。body僅含name、etag、**完整正式template**、**完整具名traffic**。不設allowMissing，不沿用舊Revision名稱；由Cloud Run產生新的正式基準Revision。原正式具名Revision100%及各Tag目標完全保留，新基準沒有流量、也不指派任何現有Tag。409／412立即停，不用新etag盲目重送舊body。
4. 等operation完成、服務收斂，讀回確認新Revision Ready、其全部可版本化設定與正式來源相同；原正式100%、hostfix/e2e/prestable及其他Tag全數不變。這不等於業務DML驗證。只有恢復成功後，才重新執行Web／API唯讀Preflight；若還有差異直接回報，不擴大例外。
5. 授權API服務層級Invoker並驗證後，才可核准Merge PR #14，讓既有API／Web Trigger各自建立候選、IAM Smoke及發布／回滾。沒有每次更新都要手動重做模板恢復的設計；前提是E2E不再向main部署。

官方支援：[Service PATCH／validateOnly](https://docs.cloud.google.com/run/docs/reference/rest/v2/projects.locations.services/patch)、[Service etag與收斂語意](https://docs.cloud.google.com/run/docs/reference/rest/v2/projects.locations.services)。本輪只送出 `validateOnly=true` 的完整模板／流量請求，已被API接受；前後etag、generation、latestCreatedRevision、template及trafficStatuses均相同。沒有真正建立基準Revision或驗證其Ready。本輪沒有執行恢復後的Preflight。

## 停止與回復

真正變更前來源／etag／Tag有漂移，或E2E還會部署：停止，不動正式服務。送出後失敗或新基準不Ready：原正式100%與Tags仍固定，先保留它們，不切至新基準、不刪任何Revision。

若需撤銷模板恢復，只在能確認latest仍是本次操作結果、沒有其他操作者變更、原流量與Tag仍完全一致時，以**重新讀取的etag**及**完整變更前template快照**，再做同一種版本化PATCH；它也會建立0%回復Revision，並保持原100%／Tags。若無法證明操作所有權、還在reconciling或etag衝突，停止調查，不覆蓋別人的新部署。這不回復／改寫任何E2E Revision的內容，也不自動調整DB或IAM。
