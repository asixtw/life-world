# v5.8 公開服務候選邊界

Owner指定`lw-public`為公開主入口，`lw-product-staging`保留IAP與既有流量。沿用PR #20全部模組，不以首頁成功宣稱完整產品已驗收。

`LIFEWORLD_PUBLIC_GATE_CLOSED=true`只在`LIFEWORLD_ENABLE_BUSINESS_API=false`且未掛載Google／測試帳號／AI憑證時成立。它在所有業務與限流DB處理前拒絕私人API；只開放自有靜態素材、首頁、無敏感資料的能力及健康狀態。`/ready`保持503，明示資料與登入Gate未完成，不能當作正式功能Ready。

此模式無持久資料寫入，不採用SQLite保存公開資料，不掛載Staging DB密碼，專用Runtime SA沒有資料或Secret授權。完整Google、帳密、AI、劇場、進度與人工確認程式保留在同一映像，待獨立資料權限與還原Gate驗證後才配置啟用。

未改變既有Staging的設定、IAM、IAP或Revision。公開服務限制最小0／最大1 instance、1vCPU、512MiB，使用既有Artifact Registry與建置SA，不建立第三個長期服務。
