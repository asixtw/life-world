# 封測正常寫入與每Owner AI費用（Owner已核准部署，執行前基準）

Owner最新決策取代先前「AI全部無限」：解除每Owner100次、全站3000次終身寫入阻擋但仍記次；AI每日及累計US$20均為每個Owner獨立，不共用全站US$20。不修改訪客建立配額。這是預留金額額度，不是供應商實際帳單保證，總費用可隨帳號數增加。

## 最小變更

- RuntimeSettings新增LIFEWORLD_ALPHA_WRITE_QUOTA_ENFORCED，預設true不影響其他環境；公開Alpha設false後只記寫入次數，不清空/修改既有收據。來源短時間寫入/登入限流、容量、AI停用開關、CSRF及Owner保護不變。
- AISettings新增LIFEWORLD_AI_BUDGET_SCOPE=owner，預設global維持舊環境契約。owner模式所有最近24h與累計費用加總都限制owner_id，舊的本人收據仍計入；同一DB交易鎖內預留，不因多程序/多裝置突破自己的額度。
- 失敗/費用未知不釋放預留，不回傳其他Owner資訊；去重與媒體父工作/片段費用不變。
- 舊LIFEWORLD_AI_HISTORICAL_RESERVATION_MICROUSD屬無法歸戶的全域歷史預留，不重複加到每個Owner，也不刪除/改為零。保留原設定與歷史收據供內部追溯；沒有依據不猜Owner。一般帳號usage仍只顯示自己的metadata。
- 不更改既有AI每帳號/全域每日工作次數（100/1000）、並發/來源防濫用與輸入大小；此次移除的是終身寫入阻擋，AI變更是費用作用域，不暗中擴大其他政策。

## 隔離測試證據

新增5項真紅燈：5 FAIL（B被A費用擋、全域歷史誤加、並發後跨帳號預算、累計寫入硬鎖、未知scope未拒絕）。修復後相關SQLite/API 44 PASS/0 FAIL（3.28s）。本機PG18受限Runtime4 PASS/0 FAIL（0.90s），使用既有marker副本，只新增合成帳號，無TRUNCATE/GRANT/Schema變更；無真Gemini呼叫。測試涵蓋雙Owner日額/累計、日窗跨越、費用未知、並發預留、只記寫入但登入限流不變；一般帳號usage隱私/無登入/訪客、去重、媒體與舊global模式回歸保留。不是正式GCP驗收。

## 正式發布方案（Owner於本輪明確要求部署）

只影響life-world-513506/asia-east1/lw-public。提交/普通Push本機修復，不Merge；固定現役上傳修復映像sha256:6c5eac650057fdbf3dcc68d298dcdb30f95e7c85873601b8a1fa0a53b9014e8c作底，只覆蓋ai_runtime.py、auth_rate_limit.py、runtime.py，保留介紹、圖示及上傳修復。單次Build與無網路容器import驗證，沿用現有SA/Registry，不新增IAM。

新Revision必須將新映像與以下4項設定同一次原子更新，避免先更設定卻仍跑舊程式：

```sh
gcloud run deploy lw-public --project=life-world-513506 --region=asia-east1 \
 --image=FIXED_NEW_IMAGE_AT_DIGEST --revision-suffix=owner-budget-FIXED_SHA --no-traffic \
 --update-env-vars=LIFEWORLD_ALPHA_WRITE_QUOTA_ENFORCED=false,LIFEWORLD_AI_BUDGET_SCOPE=owner,LIFEWORLD_AI_DAILY_BUDGET_MICROUSD=20000000,LIFEWORLD_AI_TOTAL_BUDGET_MICROUSD=20000000
```

固定SHA/新Digest後填入，不填假值。候選Tag更新、讀回設定差異僅上述4項與映像、health/ready/所有前端位元組與原版一致。驗證通過且無並行變更後，依另外核准範圍切lw-public新Revision100%。不執行真實AI付費驗收或正式業務資料寫入，除非核准合成測試範圍。

不需Migration/GRANT/Secrets或資料庫重置；不刪除額度歷史，不修改其他服務。回復可將流量指回本次前的Revision，帳號資料與收據保留；但舊版會重新套用舊共享限額，必須明示。操作前確認現役基準未變；新Build/Deploy/環境設定與切流尚未執行。
