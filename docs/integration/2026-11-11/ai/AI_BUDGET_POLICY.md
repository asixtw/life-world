# PR26 AI費用與本人用量契約（候選，未發布）

本輪不Merge/Deploy，不改Alpha環境或DB。真AI新額度驗收NOT RUN；測試全部明示Provider替身，零外部模型呼叫。

## 設定與環境界線

所有金額單位microusd（1 USD = 1,000,000）。不再有US$20程式最高值。Alpha必須`LIFEWORLD_AI_BUDGET_MODE=finite`，批准AI時必須配置正的累計上限、每次預留與每日預算；累計上限必須高於歷史預留。總開關仍為`LIFEWORLD_AI_CALLS_APPROVED=false/true`；缺Provider/模型/憑證不呼叫模型。

| 設定 | 現役Alpha唯讀值 | Alpha建議候選（尚未批准/套用） |
|---|---:|---:|
| OWNER_DAILY_CALLS | 100 | 500 |
| GLOBAL_DAILY_CALLS | 1000 | 5000 |
| RESERVATION_MICROUSD | 500000 | 500000（先保留既有每次US$0.50） |
| DAILY_BUDGET_MICROUSD | 19000000 | 25000000（US$25預留/滾動24h） |
| TOTAL_BUDGET_MICROUSD | 19000000 | 100000000（US$100累計預留含歷史） |
| HISTORICAL_RESERVATION_MICROUSD | 1000000 | 保留已核實、且不在目前requests帳本的歷史預留，不可為增加額度任意歸零 |
| BUDGET_MODE | 舊版無此設定 | finite |
| MAX_CONCURRENT_CALLS | 舊版無此設定 | 4（每process） |

上表各變數前綴皆`LIFEWORLD_AI_`。既有E2E revision只有Provider/model/輸出1536tokens、每次預留500000及日額19000000；未明確批准AI、未配置累計上限，不能視為真AI可用。詳見`../evidence/AI_LIMITS_DEPLOYED_READ_ONLY.json`，只保留非敏感白名單。

建議值是待Owner選定的有限測試配置，不是花費承諾，也不是已核准支出。每次US$0.50預留下，US$25日額最多允許50次模型預留（所有帳號合計）；媒體分段各自占預留，可能比使用者操作次數多。Owner可再提高有限日額/總額而不改程式，但仍走發布Gate。模型實際帳單未知；每次預留須按所選模型、輸入/輸出/媒體容量核實最壞成本，不宣稱此數值可保證任何模型的實際費用。

日額/次數採滾動24小時，不是午夜重置；累計預留跨重啟保存。舊錄音分段沿用不按文字呼叫次數阻擋的政策，但每段仍受日額、累計預算與在途並發限制。未知/失敗不釋放預留，不刪帳本。累計成本控制加上設定的歷史預留；調整前須避免歷史與目前帳本重複計入。

隔離E2E可明確設定`BUDGET_MODE=isolated_e2e_unlimited_total`、`TOTAL_BUDGET_MICROUSD=0`。from_env要求DB_NAME恰為life_world_e2e且ACCESS_MODE不是public_alpha；Postgres AIRuntime再次核對實際DB設定。這只停用累計限制，不停用日額、次數、AI總開關或並發。Alpha不允許無限模式。金額採有界整數、呼叫次數為1..1,000,000、並發1..128，避免溢位或無限配置。

## 一般帳號API與內部監控

GET /api/ai/usage依實際Session取得Owner，不接受owner_id/scope/admin來擴權。未登入401、Guest403；只回本人calls、reserved_microusd、已回報Tokens、費用未知次數與最多100筆本人預留/結果收據。reserved是預留，reported_cost是供應商回報，兩者皆非最終帳單，actual_invoice_cost永遠未知(NULL)。未回報Tokens的0是已知加總，不能當成實際使用0。

不回全域預算、全域消耗、剩餘額或歷史預留設定。沒有公開`/api/ai/admin/usage`，亦未新建管理者帳號系統。全域監控限既有受控DBA/營運唯讀連線，見`GLOBAL_AI_MONITOR_READ_ONLY.sql`；不得將此查詢掛到一般帳號API或將Runtime帳密交付使用者。本輪未GRANT任何監控權限。

預留交易沿用SQLite寫入鎖/PG advisory transaction lock；新增每process在途Semaphore，拒絕時不預留，finally釋放。跨process預留上限由DB保護；不是全叢集分散式在途Semaphore，需以Cloud Run instances × concurrency規劃總在途容量。

`Idempotency-Key`可用於draft suggest，tasks/simulation可帶request_id。同Owner相同key/內容只預留一次；重送409 `ai_request_already_reserved`，不得假裝重新拿到未持久化的模型全文。key改內容409；沒有自動重呼叫未知結果。模型候選仍須人工確認。既有正式Confirm/任務去重不變。

## 停止呼叫與回復

1. 觸及日額/總額時預留交易自動拒絕新呼叫，保留手動經歷流程；不清除帳本以繞過限制。
2. 計畫停止：取得Owner發布授權，使用既有固定SHA/映像及發布管線建立`CALLS_APPROVED=false`候選；驗證/ready、Guest/登入、手動確認後，依批准程序切流。只建立0%候選不會停用現役Revision。
3. 已在途的呼叫可能完成並產生費用；保留收據，不承諾即時取消供應商請求。多Revision同時運作時逐一盤點有流量者，不能只改服務模板就宣稱全停。
4. 恢復前以內部監控確認失敗/未知預留、歷史預留及有限額度，Owner批准新設定後再走同一候選驗證程序。不要更換API Key、授權其他SA、清DB或擴權作為恢復捷徑。

本輪沒有執行以上正式操作。Alpha仍使用舊Runtime，不能以本機PASS宣稱新額度已可在Alpha使用。
