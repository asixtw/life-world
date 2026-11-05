# Alpha候選配置：NOT_READY

新版GCP Master Handoff 20261105 v1由Owner工作線保管；本文件僅工程契約，不能取代其G0–G4授權。base HEAD不是Release SHA；沒有Commit、build digest或雲端部署證據。

## SQL責任

- `postgres/alpha_roles_database.review.sql`：獨立Alpha owner／migrator／app角色與CONNECT契約；只在已批准的空Alpha庫、由DBA審查，不含密碼、不建庫、不觸碰dev。角色已存在則失敗回滾。
- `postgres/auth_rate_limit.review.sql`：僅dev增量，context必須life_world_dev，保留lw_app_role；不是Alpha腳本。
- `postgres/alpha_auth_rate_limit.review.sql`：僅Alpha限流表結構，context必須life_world_alpha，沒有dev授權；不修改歷史31表快照。
- `postgres/alpha_app_grants.review.sql`：Alpha完整DML白名單，lw_alpha_app_role，禁止schema_migrations／sequence直接操作／限流表DELETE；sessions等6表DELETE沿用核心需求，不宣稱全無DELETE。

DBA前置：獨立Alpha migration owner／runtime role，lw_alpha_app只繼承lw_alpha_app_role，不可繼承dev或migration角色；不得以superuser執行App。runtime無schema CREATE／table ownership。檢查所有直接與繼承權限及PUBLIC，REVOKE單一role不會消除其他來源。

CONNECT：Alpha DB先撤PUBLIC CONNECT/TEMP，僅核准維運與Alpha app角色能CONNECT。對原dev DB撤PUBLIC CONNECT可能影響同仁，不能由Alpha腳本自動做；須DBA先盤點並保留已授權dev使用者。若dev仍開PUBLIC CONNECT，Alpha可能能連dev，必須至少驗schema/table讀寫拒絕，不能自稱CONNECT完全隔離。兩方向都需驗證：Alpha→dev與dev→Alpha。禁止修改共享dev權限來湊測試通過。

SQL為review-only、顯式交易。不用IF NOT EXISTS吞錯；重跑CREATE表應失敗且rollback，DBA需以migration紀錄管理已套用版本；不能只重播GRANT冒稱修復所有漂移。

## 非敏感ENV／秘密參照

|設定|候選值|
|---|---|
|LIFEWORLD_ACCESS_MODE|public_alpha|
|LIFEWORLD_DB_BACKEND / PG_CONNECTION|postgresql / cloud_sql|
|LIFEWORLD_DB_NAME / DB_USER / DB_SCHEMA|life_world_alpha / lw_alpha_app / lw_core_draft|
|LIFEWORLD_SECURE_COOKIES / ENABLE_BUSINESS_API|true / true|
|LIFEWORLD_AUTH_RATE_ENABLED / AUTH_SOURCE_MODE|true / proxy|
|LIFEWORLD_ALPHA_LOGIN_ENABLED|預設false；Owner另批部署時可true，只允許預建registered登入，claim永遠封鎖|
|LIFEWORLD_AUTH_TRUSTED_PROXIES|NOT_READY：需PRIVATE Alpha來源證據，不猜CIDR|
|LIFEWORLD_TRUSTED_HOSTS|NOT_READY：實際唯一Alpha hostname|
|LIFEWORLD_EXTERNAL_ORIGIN|NOT_READY：實際完整HTTPS origin|
|LIFEWORLD_INSTANCE_CONNECTION_NAME|NOT_READY：Owner核准的既有Instance connection name|
|LIFEWORLD_DB_PASSWORD|專用Alpha DB Secret名稱／固定版本占位，不填值|
|LIFEWORLD_AUTH_RATE_SECRET|專用Alpha HMAC Secret名稱／固定版本占位，不填值|
|LIFEWORLD_ALPHA_WORLDS_TOTAL / WORLDS_DAILY|30 / 20，候選易耗盡上限|
|LIFEWORLD_ALPHA_OWNER_WRITES / GLOBAL_WRITES|100 / 3000|
|LIFEWORLD_ALPHA_WRITES_ENABLED|true；停寫須部署新revision並處理舊tag|
|LIFEWORLD_DB_POOL_SIZE|4候選|

app/serve.py在Alpha關閉Uvicorn proxy_headers自動改寫；實際peer與轉送鏈需OwnerPRIVATE環境驗證。Origin為空時現有app/main.py以request.base_url推導，不能把空ENV視為指定localhost或HTTPS；Alpha必須明填。

## 建置與版本

本機容器build/smoke需Docker；未執行就BLOCKED。API Dockerfile只COPY app，模型CLI不進runtime。API Cloud Build YAML會push映像，不部署API；Web YAML會部署lw-web-main。Trigger regex實況由Owner查，不Push或合main以免觸發。

候選需鎖29基線及增量SHA256、精確diff、測試結果。Owner另批Commit後才有RC SHA，再另批build取得digest；base e9f966不冒充Alpha SHA。不能先填假digest。NOT_READY欄位未完成前不可部署。


## 預建帳號登入最小安全方案

兩條旅程獨立：匿名POST /api/auth/guest依原來源／世界容量；既有registered透過POST /api/auth/login登入，不建立新世界或自動註冊。LIFEWORLD_ALPHA_LOGIN_ENABLED預設false，啟用時保留共用DB來源／全域限流、軟帳號失敗桶、Session輪換、已有Session的CSRF及訪客衝突確認。啟用登入不代表啟用claim、密碼找回、Google OAuth或管理者建帳號API。

預建帳號由Owner／DBA在隔離Alpha庫依核准程序建立，只保存密碼hash；此輪沒有建立雲端帳號、傳送密碼或交付含密碼的名單。帳號數及重設／撤銷流程需Owner確認；不要從main複製私人帳號與密碼。未知帳號回401，不自動建立。

匿名世界30總量／24h20只約束guest建立；DBA預建帳號不經guest配額，不能將兩者合計稱30世界硬上限。預建數量另核准；登入來源30/15m、全域3000/24h仍生效；每owner與全域業務寫入配額維持。正確密碼可越過軟帳號失敗桶，但不能越過來源／全域限流。

零目標registered首登走個人資料→三習慣／目標→Lumi；第二裝置獨立登入回讀同owner資料，登出只撤銷該Session。登入不合併匿名訪客世界；若目前有訪客，需CSRF與明確捨棄訪客確認。原訪客資料不移轉、不宣稱可恢復。

本機已驗不等於HTTPS雲端驗收：Owner須對確切新Commit／image digest、固定Host／Origin、Secure Cookie、PRIVATE入口及預建合成帳號測試另批准；舊候選SHA不含本輪登入差異，不可直接宣稱已支援。

業務停寫不等於完全不寫DB：啟用預建登入時仍需更新限流桶與Session以支援回讀；撤除所有存取需Owner另處理Alpha入口。
