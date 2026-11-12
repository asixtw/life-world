# Cloud SQL 備份與隔離還原｜待核准正式操作方案

2026-11-12。**僅方案，沒有執行Export/Build/Restore/GRANT或改設定。** Gate A已核准a2eb363的UX，不涵蓋此方案。沿用既有Logical Backup做法，不新增資料庫服務或擅自開自動排程/PITR。

## 固定目標與前置條件

| 項目 | E2E | Alpha |
|---|---|---|
| Project／Instance | life-world-513506／lw-pg-staging-trial | 相同Instance |
| Region／PG | asia-east1／PG18；當次版本須讀回 | 同左 |
| Database | life_world_e2e | life_world_alpha |
| 必須相符的DB Marker | LIFEWORLD_E2E_SYNTHETIC_ONLY_v1 | LIFEWORLD_PUBLIC_ALPHA_GCP144_V1 |
| 既有Owner | lw_e2e_owner | lw_alpha_owner |
| Runtime | lw_e2e_app | lw_alpha_app（繼承lw_alpha_app_role） |

本輪已唯讀確認Instance RUNNABLE、backup enabled=false、PITR=false、Cloud SQL backup list空。歷史post005手動匯出物件仍在，但不是現行010/011還原證明。這些設定不因本方案自動修改。

操作前凍結**Schema/ACL變更**，記錄當時精確應用Commit/Revision/Digest、Schema指紋與Migration收據；一般業務資料由SQL匯出的交易一致快照處理，不能拿不同時間的live count冒稱同一備份基準。先核對既有管理連線的DB/Marker與角色，再執行已存在的READ_ONLY_SCHEMA_SNAPSHOT.sql及本包READ_ONLY_BACKUP_COMPLETENESS.sql。已提供的2026-11-11來源收據保留，不要求重跑舊02；此處是正式操作當時的必要前後指紋，不把歷史快照冒充新還原點。

以下任一項不符即停止：Marker/Owner/PG不符、Schema/ACL在前後側錄間改變、來源角色權限無法查證、匯出操作失敗、無法取得物件generation/checksum、隔離Worker需要新增未核准IAM、來源metadata與dump結構對不上。

## 需Owner分項核准的範圍

1. 兩次**只讀來源的Logical Export作業**（會在既有私有Bucket建立新物件，屬GCP寫入），每庫一份，全新前綴，不覆寫舊檔。
2. 將同時點的去敏metadata/manifest上傳既有Bucket的新前綴。不得含密碼、Token、原始個資或業務內容；原始SQL.gz本身維持私有，不放Git/本機交付。
3. 一次受控PG18.6隔離還原Worker及必要暫存。若採Cloud Build，**另需Build授權**，建議timeout 10分鐘、單次、無對外DB listener、不連來源/網站、不Deploy。
4. 如現有Worker SA無法讀指定物件，停止另提**單物件最小權限**及撤銷方案；本方案不授權新增IAM。

沒有核准自動備份/PITR、保留期或lifecycle變更。若Owner選擇另行開啟，應獨立提出設定Diff與成本，不能把它混進本次Export。

## 取得核准後的精確操作順序

### 1. 側錄與manifest

- 用既有DBA管理路徑讀取兩庫完整目錄與補充Sequence定義/權限，記錄取得時間、PG版本、DB Marker、Owner/ACL、角色屬性/會員、Schema/Table/Sequence Owner及ACL、default ACL、Migration收據及來源指紋。
- 不讀rolpassword或session/token；不以已知預期值補造來源。角色密碼/Secret本就不在此metadata內，隔離驗收如需LOGIN僅用Worker暫時憑證，不能稱已還原正式密碼。
- manifest同時記錄固定產品SHA/Tree與三服務Revision/Digest；所有操作ID、generation、壓縮/解壓SHA256、CRC32C、大小、restore版本與驗證結果彼此連結。

### 2. 新建兩份SQL Export（下列是**待核准命令模板，不執行**）

以核准UTC時間及當時短SHA替換尖括號；兩個URI均需先確認不存在。Bucket沿用`lw-poc-db-backup-513506`，不改公開性/保留規則。

```sh
gcloud sql export sql lw-pg-staging-trial \
  'gs://lw-poc-db-backup-513506/pre011/<approvedUTC>-<approvedSHA>/life_world_e2e.sql.gz' \
  --database=life_world_e2e --project=life-world-513506 --async

gcloud sql export sql lw-pg-staging-trial \
  'gs://lw-poc-db-backup-513506/pre011/<approvedUTC>-<approvedSHA>/life_world_alpha.sql.gz' \
  --database=life_world_alpha --project=life-world-513506 --async
```

- 分別記錄Cloud SQL operation ID；只輪詢同一operation直到DONE，error非空即停止，不自動重試Export或改權限。
- 對新物件讀回generation、大小、CRC32C/MD5及建立時間，之後Worker只讀該**固定generation**。建議用Storage SDK的generation/precondition；不可只靠可被覆寫的路徑。
- metadata前後指紋一致才將側錄與此Export配對。SQL匯出不包含完整DB/角色/Owner/ACL，不能只憑SQL檔存在就解除Gate。

### 3. 隔離Worker還原（需另批Build，現在NOT RUN）

- 固定PG18.6 Image Digest與Worker規格；只Unix socket或隔離container network，無公開port，不掛來源SQL socket/Cloud SQL憑證，不使用網站Runtime身分。
- 核對object generation與CRC32C；實際算壓縮/解壓SHA256、驗gzip完整性，原始資料不列印至Build日誌。每庫使用獨立的空還原目標，禁止覆寫任何既有庫。
- 只依sidecar重建必需角色及Owner/ACL；以dump相容方式還原SQL。角色→DB/Marker→Schema/資料→依sidecar恢復物件Owner/ACL/default ACL，具體次序先用目錄/匯出內容確認；不將缺失metadata硬填成預期值。
- 不執行應用Migration、不填假Migration收據、不自動放寬FK或約束。dump裡的COPY/INSERT manifest為資料筆數基準，實際還原後逐表比對；角色/ACL/Sequence參數與同時點來源側錄逐項比較。
- 驗證所有FK/CHECK有效、序列定義/目前值（若來源授權可讀）、Owner/Marker、Runtime有效欄位權限、跨Owner/API/CSRF與歷史append-only。不讓隔離應用呼叫付費AI或Google。
- SQL匯出若只包含sequence設定而不含完整狀態，或metadata不足以判定完整恢復，結果維持PARTIAL/BLOCKED，不能把近似值當PASS。

### 4. 收據、失敗與回復

PASS必須同時有：兩庫operation成功、固定物件generation/hash、PG版本/隔離證明、Schema/資料manifest與Owner/角色/ACL/Sequence逐項一致、Runtime/Owner隔離及失敗測試通過。只還原資料/結構不等於完整PASS。

失敗時停止後續011/GRANT/Deploy，保留私有Export、來源收據、去敏錯誤代碼，不因失敗重建正式DB、刪資料或重跑010。Worker暫存/短期單物件授權只依核准清理範圍處理；未批准則不擅自刪任何來源物件。

本階段**不做正式資料回灌**。若後續正式資料恢復有需要，先在隔離目標演練與核准停寫/恢復點/資料損失窗口/RTO，另行批准執行；應用回滾不得靠DROP011或刪草稿候選。當前只能規劃，沒有足夠證據宣稱可無損還原現行Alpha。

## 交付與責任

工程負責準備可審查操作/manifest與執行收據；Owner核准範圍及指定備份保留責任，DBA核對既有角色/最小權限，獨立Reviewer審查還原證據。沒有替他人宣稱已接單。Gate B保留BLOCKED，直到上述實際驗收完成。
