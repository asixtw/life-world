# Alpha 02：探針 → ROLLBACK → 驗證 → 原始COMMIT

最新決策已定案：**不拆02A/B/C、不將OWNER TO移出交易、不改原始02內容**。本包只由Owner在同一Cloud SQL Studio、相同DBA、life_world_alpha操作；工程沒有在真Alpha執行。

已接受Owner證據：Product Restore PASS；Alpha 01/01B與空應用庫PASS（postgres非superuser但具CREATEROLE/CREATEDB及有效授權）；公開OAuth Origin已儲存。以上不重跑。

## 實際操作順序

1. **先存基線**：執行`02_PRE_POST_VERIFY.sql`，保存完整Result及state_snapshot／snapshot_fingerprint_md5。應correct_target/pg18=true、alpha_role_count=0、database_owner=cloudsqlsuperuser、core_still_absent=true。這是本次ACL比對基線，不是重跑01B。
2. **交易探針**：整檔單次Run `02_TRANSACTION_PROBE.sql`。必須全部看到before=0、inside_transaction=1、after_rollback=0，且沒有SQL錯誤。不能僅以最後0判PASS；失敗即停止02，不手動DROP探針角色或繼續。
3. **原始02 ROLLBACK演練**：整檔單次Run `02_PUBLIC_ROLES_ROLLBACK.sql`。除了最後COMMIT改ROLLBACK，與原始02逐byte一致。必須全程無錯誤、跑到最後ROLLBACK，特別包含最後GRANT CONNECT TO SESSION_USER。不要分段、換DBA或換執行環境。
4. **驗證沒有殘留**：再執行同一`02_PRE_POST_VERIFY.sql`。角色數仍0、owner仍cloudsqlsuperuser；完整snapshot／fingerprint必須與第1步相同，包含Database ACL、public ACL、其他穩定Schema及三角色membership。若不同或任一錯誤立即停止，不進COMMIT。
5. **public唯讀盤點**：執行`02_PUBLIC_SCHEMA_INVENTORY.sql`。列擴充套件、public所有Relations、Functions/Procedures。若有非預期物件，先確認依賴；不要自行改REVOKE、原始02或管理Schema。沒有非預期物件就記錄結果。
6. **正式02**：上述皆符合後，直接整檔單次Run `02_PUBLIC_ROLES_COMMIT.sql`；它與原始e1ca…版本完全相同，只有一個BEGIN/COMMIT交易。不需要再開設計討論，不拆分、不重跑已成功初始化。
7. **正式驗收**：執行`02_PRE_POST_VERIFY.sql`。應alpha_role_count=3、owner=lw_alpha_owner、committed_owner=true、all_three_attributes_safe=true、dba_can_connect=true、dba_can_set_owner=true、runtime_owner_membership_forbidden=false、core_still_absent=true。snapshot.roles中三者NOLOGIN、無super/createdb/createrole/replication/bypassrls；Runtime只隸屬DML角色、不是Owner。檢查Database ACL與public ACL符合原始02。正式COMMIT後snapshot本來就會改變，不要求等於原基線。

所有步驟保持相同DBA與Studio；角色及membership是Cluster層級。public Schema與既有google_vacuum_mgmt不自行修改。快照忽略會話臨時Schema，不比較OID分配器／活動統計；目標是邏輯狀態及權限沒有殘留。錯誤時停止並先ROLLBACK該失敗交易，不自行清理角色或修改設計。

Owner回傳各階段Result／成功或精確錯誤文字即可，不要提供密碼、Token、Cookie或私密Activation內容。完成正式02後，依既有VNEXT操作單逐檔03→04→05→007→008→09→10→11→私密12；本包不等於後續步驟已執行。

## SHA-256

|檔案|SHA-256|
|---|---|
| 02_PRE_POST_VERIFY.sql | `8a5f72269d1ff7166e3f65111644df7d7c2c40a7588a9dbedaae3fe88a6aba0e` |
| 02_PUBLIC_ROLES_COMMIT.sql | `e1ca757b9e7d46e22332c688d17743fef1b0973dfbb5166b45089d4c1ce55d35` |
| 02_PUBLIC_ROLES_REVIEW.sql | `e1ca757b9e7d46e22332c688d17743fef1b0973dfbb5166b45089d4c1ce55d35` |
| 02_PUBLIC_ROLES_ROLLBACK.sql | `9b4edc30c887c14c215b43084f44d241ae309cef07b11e2ee082c03532ca529e` |
| 02_PUBLIC_SCHEMA_INVENTORY.sql | `6810c8e3b520622b6cae9dfd6ae1457c22eab5541140ad15f85438c257b6ae43` |
| 02_TRANSACTION_PROBE.sql | `bed4820586dae593bbf2f1a1fb2db0a17369e5bee1b609544bbc96948325d98d` |

## 本輪驗證範圍

原始SHA已實際核對；COMMIT逐byte相同；ROLLBACK還原那一處替換後逐byte相同。SQL在真Alpha的探針、演練、COMMIT及驗收均NOT RUN，必須由Owner在原Studio取得實際結果。既有PG18合成02測試不取代此處的Studio交易驗證。
