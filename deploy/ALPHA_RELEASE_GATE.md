# Public Alpha 候選發布關卡（尚未授權部署）

工程配置與Alpha專用SQL以[候選配置](README.alpha-candidate.md)為準；GCP操作依Owner持有的Master Handoff 20261105 v1，舊交接包只作歷史參考。

本輪僅本機工程交付。維持 lw-api-main 私人與 hostfix 原狀；不得把 React gallery 當業務站。

## 待 Owner 逐項批准的變更

| 項目 | 候選變更 | 回復／停止 |
|---|---|---|
| 資料隔離 | 既有 Instance 另建 life_world_alpha、獨立 lw_alpha_app／權限角色；不得指向 life_world_dev | 停止 Alpha 寫入，保留隔離資料；刪除須另批准 |
| 執行服務 | 新 lw-api-alpha、獨立 runtime SA；使用經驗證 commit digest | 回復已驗證 revision；不得切換 main 流量 |
| Secret | 獨立 DB／HMAC Secret 參照，runtime 僅所需 accessor | 停止寫入／撤除該服務存取；不輸出秘密值 |
| 網路 | 確認 HTTPS URL、精確 Host/Origin、Secure Cookie、可信代理鏈 | 撤除 Alpha 公開入口；依現場 IAM/IAP 機制操作 |
| 容量 | min=0、max=1 候選；世界30總量／20每日、每世界100次寫入／全域3000、64KiB請求、AI關閉 | ALPHA_WRITES_ENABLED=false 停寫；雲端成本仍須監控 |

以上為候選參數，沒有執行任何雲端變更。max instances／配額不等於硬性帳單上限。公開前需現場驗證來源、IAM、跨帳號、實際 HTTPS Cookie/CSRF、PG 最小權限與備份回復。單純本機通過不可代替。

Alpha 提供匿名文字核心；預建 registered 帳號登入須另啟用 LIFEWORLD_ALPHA_LOGIN_ENABLED（預設 false）。claim、媒體辨識及佐證上傳維持封鎖；只有預建帳號可跨裝置回讀，匿名訪客沒有恢復保障。11/13 持久化受邀帳號與真實多模態另驗收。保留積分與 reward_ledger，沒有兌換或消費。
