# Alpha Guest Maintenance適配與最小權限審查（NOT ENABLED）

現有app/guest_maintenance.py仍只接受life_world_beta／lw_beta_maintenance並拒絕網站K_SERVICE。本次不移除此檢查，不以lw_alpha_app刪除資料，不建立排程／角色／Secret或Job。

## 建議適配（尚未實作部署）

未來新增明確、受測試的alpha profile，固定：既有Cloud SQL instance、life_world_alpha／lw_core_draft、marker LIFEWORLD_PUBLIC_ALPHA_GCP144_V1、current_user=lw_alpha_maintenance。CLI要求--execute、max-jobs 1..50、非K_SERVICE，Job名稱與獨立SA白名單，網站Runtime不呼叫此CLI。Beta維持原白名單，禁止只放寬db_name字串檢查。

啟用前用readonly驗證current_database／current_user／server18、Instance、marker、safe role attributes、無owner或管理membership、實際schema與FK全量契約。任一額外表、跨schema入站FK或跨Owner引用即停止batch。Runtime角色與維護角色不得互相繼承。

沿用GuestPurger狀態：pending → media pending/done → completed；錯誤retry與有界last_error_code，最多5次後run_batch回報retry_exhausted並發告警，不悄悄無限重試。完成保留僅Owner識別、時間、狀態、次數的去內容收據。未到14天不刪；已registered／有Google映射即拒刪。這不是恢復功能。

Alpha初期只支援SQL內evidence內容，使用media_cleanup=None，媒體與資料在最後交易一併刪除。未來外部Object Store適配器必須另審owner範圍、租約／競爭、冪等與來源變更後不刪正式媒體；不能把目前可重試callback機制當成已驗證的跨儲存原子交易。

## SQL與權限

[ALPHA_MAINTENANCE_PRIVILEGES_REVIEW.sql](ALPHA_MAINTENANCE_PRIVILEGES_REVIEW.sql)是REVIEW ONLY，最後ROLLBACK，不授權執行。兩角色預設NOLOGIN，啟用LOGIN／密碼及獨立Secret需另批，不放占位密碼進Repo。

- DB CONNECT、lw_core_draft USAGE，無CREATE／TEMP／owner membership。
- 只SELECT判斷owner範圍所需的FK／鍵值與users.status欄位；不讀經歷原文、requests.response、密碼雜湊或媒體bytes。
- guest_abandonments完整SELECT與限定狀態欄位UPDATE；無INSERT／DELETE，收據保留。
- 僅核准業務表DELETE；不授予schema_migrations、auth_rate_buckets、guest_abandonments或external_identities DELETE／TRUNCATE。
- 目前Runtime既有DML及table owner完全不動。
- 合成PG的維護測試角色已用相同欄位原則完成10項轉換／清理驗收，但此正式目標guard SQL審查稿沒有在真Alpha執行。

獨立維護SA若未來獲准，只需現有instance限定Cloud SQL Client與維護專用Secret的Accessor，不給Owner／Editor／DB管理權。網路沿用既有private VPC/subnet，Job不開HTTP、不共用網站Secret。尚未建立任何SA／IAM綁定／Secret或Job。

## 回復／停用

先停止排程並等待或停止已核准的worker，核對執行收據與交易結果；角色NOLOGIN並撤維護專用Secret存取權。這些停用寫入也需另外批准，不能改網站Runtime。不要DROP角色／資料或清理收據。

已提交的實際資料刪除不能以Git／Revision回滾恢復。啟用任何永久刪除前，須取得同一恢復點的可還原Logical Backup+Metadata證據；必要時由DBA在受控隔離環境還原並以審查過的程序恢復指定Owner，不直接整庫覆寫Alpha。未通過此Gate不啟用維護刪除。
