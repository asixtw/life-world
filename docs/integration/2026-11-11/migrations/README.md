# 增量Migration草案（GCP未執行）

Owner已核准生日及任職語意，允許先準備草案；E2E/Alpha唯讀Snapshot已收到且結構相同。`011_person_basic_details.review.sql`不是可直接執行的最終Owner包，實體名稱/版號未凍結，未產生收據。

快照已證明010具備people(id,owner_id)及experiences(id,owner_id)唯一鍵；如實況不同，須分類相容性差異，不能自動改舊表或重跑010。兩份History用結構化欄位保留每版；業務服務必須同交易新增history與更新目前值，不依賴可被跳過的前端。

最小權限草案：Runtime對目前值表SELECT/INSERT、限定可改內容/來源狀態/revision的UPDATE；History僅SELECT/INSERT，不UPDATE/DELETE；Owner/FK不允許Runtime改寫。公開Runtime沒有DDL、角色管理或跨Schema權限。GuestPurger由獨立維護角色，需核准新表/FK契約、history→current→people刪除順序；未審查時保持fail-closed。

失敗處理：套用失敗整個DDL交易ROLLBACK；成功後不得為了程式回滾DROP表或刪歷史。先關閉新寫入能力、回應用程式舊版，保留新增資料，必要修正走新Migration。驗證SQL需檢查真日期、同Owner FK、雙工作並存、版本歷史與權限，隔離PG18.0副本試跑與16項API/權限測試PASS，仍非GCP相容性/發布核准。正式E2E/AlphaMigration均不得由本稿自動執行。


## 草稿AI撤回欄位權限（新審查項，非Migration）

[DRAFT_AI_CONSENT_COLUMN_GRANT.review.sql](DRAFT_AI_CONSENT_COLUMN_GRANT.review.sql)僅提議單一指定庫Runtime的UPDATE(revoked_at)，不GRANT其他欄位、不改Owner/Schema。正式Alpha/E2E目前未執行；本機marker PG18只測同等欄位權限及不足時fail-closed。前端授權整合尚未完成，不可因此進入發布。回復須先停用草稿AI並審查有效同意及原GRANT，不刪同意歷史。
