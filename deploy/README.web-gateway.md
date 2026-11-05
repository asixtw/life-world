# Web → FastAPI → PostgreSQL：唯讀串接候選

2026-11-06；本機實作與隔離測試完成，尚未啟用正式雲端入口。這不是 Public Alpha 開放、登入／DML 授權或 Cloud SQL 業務驗收。

## 入口與資料責任

|入口|實際用途|
|---|---|
|`collaboration/ui-kit`／Web `/`|React 元件與合成素材展示；維持原 gallery，不能宣稱是業務 App。|
|`app/static`／Web `/app/`|現有 Life World 業務介面，經伺服端轉送 API 的 `/` 與 `/static/*`；不是把展示元件改名冒充正式功能。|
|Web `/api/*`|同來源唯讀 allowlist，轉送到既有 `lw-api-main` canonical URL；Session／owner 權限仍由 FastAPI 檢查。|
|本機 Caddy|既有設定為 `https://localhost:8443 → 127.0.0.1:8088 → hostfix`；不是 Cloud Run Web 的正式代理。本輪不修改、重啟或佔用它。另一份 8089 Caddyfile 是獨立 E2E 候選。|

核准並啟用後的路徑是：瀏覽器 `/app/` 與 `/api` → 現有 `lw-web-main` 的 Python gateway → 私人 `lw-api-main` → 既有 PostgreSQL adapter → 原 Cloud SQL Private IP／VPC／Secret 綁定。Web 不取得 DB 密碼、不連資料庫，也不新增服務或資料庫。

## 已實作的界線

- `tools/web_server.py` 在 server 以 metadata 取得 runtime SA 的短期 ID token，audience 固定為 API canonical URL；只放在出站 `X-Serverless-Authorization`。不用 SA JSON key、不讀瀏覽器 Google token、不使用環境 HTTP proxy、不跟隨 redirect。依 [Google Cloud 服務間驗證](https://docs.cloud.google.com/run/docs/authenticating/service-to-service)。
- 僅允許既有 GET／HEAD 路由與必要業務靜態資產，未知 API／編碼路徑／跨 Origin／偽造代理鏈不會獲得身分轉送。每次 HTTP 請求獨立 cookie jar，避免跨使用者 Session 混用；保留 Cookie、CSRF、原 Origin、HTTPS、Trusted Host 及 CSP。
- POST／PUT／PATCH／DELETE 一律拒絕，capabilities 明確宣告唯讀，真正 UI 顯示唯讀提示。沒有有效 Session 時不提供建立世界／登入入口；不搬移既有 localhost Cookie。登入也需要 sessions INSERT／DELETE，不能當作純讀取而偷開。
- 新 Web runtime 仍以非 root 執行，原 React tests／build／push／候選發布流程保留；Docker runtime 必須先通過合成 gateway 測試。`tools/**` 原本就在 Web Trigger 與來源新舊檢查範圍，不新增 Trigger。舊 `cloud-nginx.conf` 只保留為先前展示映像的歷史配置，這個 Python runtime 不載入它。
- PR內 `_WEB_API_ORIGIN` 已依實際v2 Service URI設定為 `https://lw-api-main-u5py2jttpa-de.a.run.app`，與固定audience一致；尚未Merge／部署，服務層級IAM仍待授權。由相同CI將它帶入image，不用每次到GCP設定。未配置的獨立啟動仍不連API。啟用後 `/health` 會同時檢查 API capabilities／runtime SA 存取，失敗由既有發布器保留或回復舊流量；這不表示通過 DML 驗證。

## 雲端啟用前精確待決項目（本輪未執行）

1. **API 呼叫身分**：本輪讀到 API service 與 project IAM 都沒有 Web runtime 的明確 binding，未查無權／不相關的組織政策。若沒有等效繼承授權，需要在 **`asia-east1/lw-api-main` 服務資源** 授予 `serviceAccount:lw-web-runtime@life-world-513506.iam.gserviceaccount.com` **`roles/run.invoker`**。不授在 project、不加匿名成員、不替 Web 加 DB／Secret 權限。此 IAM 角色允許調用服務；HTTP 唯讀限制由 gateway 執行，App Session／CSRF 仍是另一道權限。
2. **API 發布護欄修正與其他阻礙**：100% 正式 revision `lw-api-main-c-94975cd3a6854941b1705c5634c777b3` 的 business 為 true，latest/e2e `lw-api-main-00008-kgk` 為 false。本 PR 已依指示準備唯一的 false→正式 true 例外，只調整比較複本，並對新候選明確設定 true；正式政策非明確 true、其他 Runtime 差異或候選變回 false 仍拒絕。latest 還指向 `life_world_e2e`／`lw_e2e_app` 及不同 DB Secret，故維持 fail-closed，不再新增例外。[完整正式模板恢復與E2E隔離方案](README.api-template-recovery.md)已準備，只有validateOnly請求被接受，尚未取得或執行恢復授權；e2e、hostfix與其他Tag未變。
3. **正式業務入口／登入**：目前只準備唯讀 `/app/`，維持現有 Web／API IAM。是否讓一般瀏覽器直接進入、受邀帳號如何取得 Session、何時啟用登入，均須沿用核准的存取政策。本輪沒有加 `allUsers`、公開註冊或新的權限。讀取來源保留原 Origin，API Trusted Hosts 不需因 server-to-server 轉送而加 Web hostname。
4. **資料庫寫入**：`lw_app` 的實際雲端 DML 本輪未核對；不新增 GRANT。登入前至少須確認 users SELECT、sessions SELECT／INSERT／DELETE 的有效權限及限制；其他業務另依實際 SQL／配額表核對。後續寫入也必須核准 API 的 Web Origin，不能改寫瀏覽器 Origin 假裝同來源。`/ready` 的 SELECT 成功不能替代上述驗證。

## 本輪實測與限制

先重現未實作 gateway 的 11 個錯誤，實作後合成安全測試擴至 14 項全過；實際業務唯讀路徑先 1 passed／1 failed（UI 未支援唯讀），補齊後通過。最終合成 14 項＋API／Web 契約與業務測試 14 項，共 **28 passed、0 failed、0 skipped**。Web runtime 鎖定依賴在獨立 TEMP 安裝成功；沒有修改 venv。

Edge 真正執行 `app/static` JavaScript，經同來源 gateway 讀取隔離 SQLite 的既有目標／Session；讀取時禁止任何 `connect(write=True)`，並驗證未知 owner 不可讀、沒有 Session 顯示唯讀而不建立世界。瀏覽器網路透過 Playwright 攔截至 ASGI transport，不是實際外網 TLS／Google IAM／Cloud SQL 驗收。測試可在既有合成 PG 測試模式覆用；本輪沒有重新跑 PG 容器或全部 API 測試。

Docker／Cloud Build／雲端業務讀取／DML／新登入：本輪均未執行，不標通過。現有 hostfix、Caddy、正式流量、Cloud SQL、VPC、Secret、IAM 均未修改。後續核准後仍由既有 main CI/CD 發布，不新增逐次人工 GCP 部署。
