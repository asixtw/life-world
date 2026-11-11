# 獨立合成人物評測入口

此 CLI 不連正式 App 資料庫。只有完成 Owner 的供應商、Secret 注入及總預算批准後，才可執行真實推論。預設額度只是本機保護參數，不構成付費授權。

先準備（不連外、不讀金鑰）：

```sh
python -m model_eval --directory .local/model-eval prepare --case model_eval/examples/synthetic-1v1.json --request-id synthetic-001 --provider gemini --model gemini-3.5-flash-lite
python -m model_eval --directory .local/model-eval show RUN_ID
```

`run`／`retry` 另外要求批准檔，精確匹配 provider、model、endpoint、budget_microusd、max_attempts，並有 approved=true、owner_reference。金鑰僅從既有環境注入；工具不存取 Secret Manager。未提供批准檔不能執行。不要把批准檔或評測資料提交。

所有金鑰共用同一份預算與次數帳本；不自動輪替或無限重試。成本未知時保留預留額，不能當免費。此預留額不是供應商硬性計費上限，正式執行前還須核定模型價格與單次最大費用。

保存輸入、來源版本、提示詞、回應、Token、延遲、成本狀態與人工評分。停止只丟棄晚到內容，不能撤銷已發生的供應商費用。回應不寫入人物事實、經歷或目標。此輪只完成 mock transport 驗證，未呼叫真實模型。

## 私密儲存平台限制

EvaluationStore 暫只接受 POSIX 平台。Windows 及其他未支援的平台會在任何目錄、資料庫或輸入檔存取前回報 `private_storage_platform_unsupported`；prepare、show、stop、run、retry、score 都會停止。既有資料不刪除也不修改。這是 fail-closed 功能限制，不是 Windows ACL 已修復或私密儲存已驗證。

正常 App／PostgreSQL 核心不使用此獨立評測儲存入口。恢復 Windows 評測支援須另行設計與驗證 NTFS ACL，包括繼承權限與 SQLite 輔助檔案。不能以跳過 POSIX 權限斷言、調整測試預期或修改使用者電腦 ACL 代替產品設計。

POSIX 仍沿用既有 chmod(0700/0600) 實作；本次沒有宣稱驗證所有 POSIX 檔案系統、符號連結、並行攻擊或 ACL 情境。原功能與權限斷言保留；Windows 的既有功能測試會因不支援平台而失敗，不能把完整 Windows 套件標成全通過。
