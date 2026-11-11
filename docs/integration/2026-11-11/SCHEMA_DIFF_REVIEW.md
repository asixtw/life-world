# E2E／Alpha即時目錄差異｜2026-11-11

Owner提供兩份Studio結果，原始檔SHA256見 evidence/schema/*.source.json。不是Jerry文件推測。

| 項目 | 實際結果 | 判定 |
|---|---|---|
| DB／Marker／PG18 | life_world_e2e / SYNTHETIC marker；life_world_alpha / PUBLIC_ALPHA marker；皆180006 | PASS，各環境隔離 |
| 結構 | 42表、326表欄位、2 Sequence；83 CHECK、283 NOT NULL、81 FK、41 PK、24 UNIQUE；88索引 | 本次快照範圍完全相同 |
| 欄位／型別／NULL／Default／約束／Index／RLS／View／Function／Trigger | 全項列表逐筆一致 | PASS，非僅比較數量 |
| 結構SHA256 | `0e3d04411e843b509e120d9e4dd073f304c03f39317cc57958b4c6b78a0f2e8e` | 兩庫相同 |
| Runtime表級有效權限 | 各自Runtime在各自DB的42表布林權限矩陣相同 | PASS；不代表新增功能已有足夠權限 |
| Migration收據 | E2E只有010；Alpha保留core/006/007/008及010共5筆 | 不同，保留各自歷史，禁止偽造補收據或重跑已完成Migration |
| DB/Schema Owner與ACL | e2e_owner/e2e_app與alpha_owner/alpha_app_role等不同 | 預期環境差異；原始ACL/列權限與角色資料全部保留供審查 |
| relationship_features/preferences | 兩庫皆無 | Gate B需要獨立增量與授權，不能拿SQLite009冒充PG已存在 |
| person_basic_details/employments及歷史 | 兩庫皆無 | P0新增契約，011草案需審查及隔離PG實測 |
| drafts DELETE | Runtime兩庫皆false | 新DELETE API尚不可部署；需最小DML差異審查，不能自行GRANT |
| Sequence參數／有效Sequence權限 | 首版快照只含物件與ACL，未取seqstart/increment/cache等 | NOT RUN，不能宣稱完整Sequence指紋一致 |

完整機器可讀結構與ACL差異：`evidence/SCHEMA_DIFF.json`。來源快照包含21筆column_acl；表級UPDATE=false的表可能有部分欄位UPDATE，必須按原始列權限檢查，不以表級布林誤判沒有所有更新能力。

## 決策分類

- 保留現況：010兩庫結構、既有Migration歷史、Owner與隔離、目前正式Runtime／流量。
- 相容性修正：所有對010已擴欄的INSERT明確列欄、來源權威採單一link_table模式、舊API共用people。Alpha仍legacy模式時不得雙寫新來源。
- Additive草案：生日/任職目前值與歷史；PG Feature Store另列，不混入011；DELETE最小權限需另行審查。
- 未核准、不得自動納入規劃：Jerry進階劇場/人物作品/AI角色演出/完整角色創作。相容資料保留不等於核准入口或R+1承諾，不把Jerry UI移入PR24。
- 人工裁決：UX整體核准、011實體命名與權限、補齊Migration lineage收據政策、E2E套用批准及正式Alpha發布批准。

尚未進行任何正式SQL寫入、Migration、GRANT、Build或Deploy；Schema結構相同不能替代應用程式讀寫及回滾實測。
