# PR #26 發布前審查｜NO-GO（2026-11-12）

本輪已完成可在本機執行的修復、測試與唯讀雲端盤點；**尚未達 Merge Ready**。Gate A須Owner親自核准；正式備份/還原、011/權限、完整來源契約與受控GCP E2E仍有阻擋。沒有執行正式Migration、GRANT、Build、Deploy、切流或正式資料匯入/刪除。

## 固定候選與操作

- 工作區 `/private/tmp/lw-integration-20261111`；分支 `integration/pr24-first-unified-schema010-20261111`，沿用Draft PR #26。
- 產品Commit `a2eb3632037726b93f3bea82b395fa7e5d010aa6`；App tree `c823bdde84ae8ab90c75a45d557cb6cd9e9c0623`。防呆產品22c99eb；本輪另加0e4940e草稿格式保護、1bbca75來源快照競態保護。已保留並整合遠端並行提交8c82c49的Soft Life視覺，不覆蓋他人工作，沒有Merge main。後續交付Commit只涉及文件/證據。
- Owner入口 **http://127.0.0.1:8198/**。沿用原本機測試帳密，先保存舊頁草稿再重新整理，正常登入後 `/#record`；不需Google。已因後端修復優雅重載相同服務/隔離PG/資料目錄，不重設帳號、Session或資料。
- 防呆畫面與23項驗證：[日期/期間交付](../2026-11-12_GATE_A_VALIDATION/README.md)。四步R3畫面/錄影：[R3證據](../2026-11-12_GATE_A_R3/index.html)。舊畫面保留歷史；本輪合併候選另有[最新三尺寸畫廊](index.html)及ux/36張圖/3錄影，皆合成資料。

## Gate 狀態

| Gate | 結果 | 未放行原因 |
|---|---|---|
| A UX | Changes Requested／待Owner | 四步/防呆已交付；Owner未明確核准，測試不能代替設計簽核 |
| B 資料/安全/相容 | PARTIAL／BLOCKED | 本輪修復兩項安全缺口；正式011與最小權限、Purger新FK、完整來源契約、備份還原/混合Revision演練尚未完成 |
| C 固定SHA/Digest GCP E2E | NOT RUN | 未獲Build/部署/Migration/GRANT授權；不能用本機PG或替身當GCP/真Google/Gemini |
| D main／Alpha | NO-GO | A/B/C與獨立Code Review未通過，Owner未授權Merge或部署 |

## 本輪修復與Code Review結果

1. **草稿未知版本誤讀**：`app/service.py::_draft`原將未知`_format`當舊StoryInput讀回，後續可能覆寫。新版本回409 `draft_format_unsupported`，讀取/修改/確認都保留原列，提示使用相容版本。不把未知資料刪掉或假裝可用。新舊已知格式仍相容。
2. **記憶來源競態**：`FeatureStore.context`重建途中停用或撤回時，舊請求可能重新發布舊特徵。新增寫入前Owner交易內的設定revision、來源可用性、人物事實/來源與互動重驗；不一致回409，不送出本次舊快照，不修改正式經歷/事實/獎勵。沒有在交易內進行模型網路呼叫。
3. **011草案目標防護**：加上已知DB Marker核對；不能只憑同名Database套用。新增最小權限審查稿，沒有執行。來源名稱/版號/收據仍須正式審查凍結。
4. 前輪生日/任職、目標時區/期間、錯誤轉譯與數量保留已提交。保留人工確認、來源Hash、Owner、CSRF、冪等與獎勵；不擴充Jerry功能。

本次為工程自審/測試，**不是獨立Code Review批准**。GitHub即時讀回PR26 Open + Draft，正式reviews空清單（PR26_REVIEWS.json）。需由Reviewer審查下列差異：

| 審查區 | 主要檔案 | 必看斷言 |
|---|---|---|
| 身分/原子確認 | external_auth.py、guest_lifecycle.py、service.py、draft_review.py | 同Owner升級/異Owner切換、明確同意、取消/失敗不清資料、兩人不同ID、晚期衝突整筆回滾 |
| 四步UX/防呆 | experience*.js、media.js、app.js | 原始輸入保留、有效日曆/月日未知年、目標時區、部分量、不提前建人/計分、API拒絕可返回 |
| 資料/來源 | schemas.py、people.py、person_basic_details.py、relationship_memory.py | source_kind/evidence_type分離、來源撤回、版本/Owner、歷史append-only、模擬不污染事實 |
| 發布/回復 | 011 review SQL、MINIMUM_PRIVILEGES.review.sql、deploy/release.py | Marker/角色、最小DML、Trigger、候選無主流量、兼容回退、完整備份 |

## 實測收據（範圍不同，不相加）

| 收據 | 結果 | 限制 |
|---|---|---|
| API_NODE.log | **788 PASS／87 SKIP，33.83秒** | 後端1bbca75全tests；SQLite/Node，87項專用PG容器未配置；視覺整合後另補下列測試 |
| MERGED_UI_PG.log | **26 PASS，63.07秒** | 合併候選a2eb363：23項新防呆＋3尺寸完整四步UI→API→本機PG，36圖/3錄影；與前輪重疊 |
| SOFTLIFE_NODE.log | **5 PASS** | 遠端視覺候選的靜態契約/素材失敗退路，非Owner設計核准 |
| DRAFT_SOURCE_TESTS.log | **28 PASS，2.21秒** | 草稿/來源/競態相關子集；先前階段與完整套件重疊 |
| RELEASE_SAFETY_TESTS.log | **24 PASS** | 發布器單元測試，不是真Build/Deploy |
| DRAFT_COMPAT_LOCAL_PG.json | PASS | 受限lw_e2e_app真本機PG，新v2生日回讀/未知封套拒寫/原文版本不變；合成Owner，非GCP |
| LOCAL_PG_PERMISSION_AUDIT.json | 唯讀PASS | PG18.0、46表/90FK；目前值限定欄UPDATE，兩history無UPDATE/DELETE，Owner/主鍵不可重派（011四表範圍） |
| ../GATE_A_VALIDATION收據 | 23 PASS；較早相關UI118 PASS/API84 PASS | 不冒稱本輪重跑所有UI；防呆畫面320/390/1440，API錯誤保留輸入 |

FORMAT_RED.log、MEMORY_RACE_RED.log保留修正前真紅燈；設定停用/來源撤回競態使用可重現交錯點，不冒稱多程序壓測。真Google、Gemini、媒體Provider、實機Safari/Android均NOT RUN。已送達供應商的既有請求無法靠後續撤回追回；尚需用途同意/dispatch時序審查與受控E2E。

## Alpha／E2E Schema與權限

最新**可取得的業務Schema快照仍為2026-11-11 Owner Studio來源**，不是本輪即時Cloud SQL SQL連線：兩庫均PG18.6、42表/326欄/81FK/2序列，結構指紋一致；Owner/ACL/Migration歷史不同。E2E只有010，Alpha保留core/006/007/008/010，不重跑。詳[既有Diff](../2026-11-11/SCHEMA_DIFF_REVIEW.md)。

正式兩庫快照皆缺011四表與PG Feature Store兩表；本機011結構副本46表/90FK，並非正式Migration已完成。私網管理連線本輪沒有新增，故正式實況最新差異與011執行資格仍需發布前唯讀補驗，不能以GCP Instance版本代替資料表查核。

- 011 Migration仍為審查稿：[011 SQL](../2026-11-11/migrations/011_person_basic_details.review.sql)。凍結前核對實體名/約束/索引/歷史/來源/receipt lineage，先保留同時點備份與原ACL。已有011或Marker不符即停止，不重跑。
- [最小權限稿](MINIMUM_PRIVILEGES.review.sql)是**NOT EXECUTED**。指定E2E `lw_e2e_app`、Alpha `lw_alpha_app_role`；Schema Owner既有角色執行。011目前值SELECT/INSERT與列明內容欄UPDATE；history僅SELECT/INSERT，沒有DELETE/UPDATE或Owner重派。另列drafts DELETE與data_consents UPDATE(revoked_at)所需差異。
- `lw_migrator`在Alpha無CONNECT，不可當成可執行身分。不得以網站Runtime做DDL；不得擴IAM或自建管理帳號。先審查實際既有DBA可SET ROLE能力。
- 權限回復：保存原effective grants及ACL；停新寫入/AI後只撤銷本次新增差異，不盲撤原有權限，不刪history/人/經歷。

## GuestPurger／資料來源／回復阻擋

- **Purger**：本機90 FK，核准圖61 FK，額外29組（01020＋0119），維持`unreviewed_fk`安全停止；Alpha Worker未適配/未啟用排程。需逐表控制Owner、複合FK、跨Owner異常、歷史→current→people次序、14天/升級/中斷/重試審查；不把29組直接加白名單，不改成網站Runtime刪除。現有SQL/media清理流程不能當正式010/011清除已驗收。
- **四維來源契約**：source_kind保存在DraftReview，但fact_sources正式DTO尚未完整投影輸入管道/來源版本；不可把evidence_type當source_kind。需審查最小持久契約/來源對應後再補，不能靠姓名/第一人或猜測還原來源。
- **Hidden memory**：本輪只修舊快照覆寫競態。PG兩表、用途同意、版本/撤回傳播及完整背景處理仍未完成/未核准；不開背景旗標、沒有付費呼叫或訓練集匯入。
- **DraftReview**：新v2/生日/任職不能回舊Alpha/0eee0a3。可審查的相容應用基線為846f250（同已知v2契約），新安全修復不改Schema或格式；但**該Commit未有本輪建置的Rollback Digest**，不能冒稱可立即無損回滾。須固定同Schema reader的候選/rollback雙映像，實際舊/新草稿、混合Revision、重新登入及原子確認演練。未知版本現在拒寫；禁止用DROP表/刪候選當回復。

## 備份／還原：重要阻擋

本輪GCP唯讀：自動backup enabled=false、PITR=false、backup list空；deletion protection=false。見cloudsql_policy.json/cloudsql_backup.json。未修改設定。

**不代表完全不存在手動匯出**：已找到既有2026-11-08 Alpha post005 logical export，GCS唯讀確認generation `1794129895252182`、6017 bytes與舊收據相符（HISTORICAL_EXPORT_OBJECT.json）。歷史交付只證明當時32表/2筆migration資料結構恢復；當時Owner/ACL/Marker完整恢復仍BLOCKED，且早於現行01042表及011，不能當目前可還原保障。沒有下載原始備份或讀業務內容。

正式變更前需另行批准：對E2E/Alpha各保存一致SQL/export＋同時點Owner/角色/ACL/Marker/Sequence/receipt sidecar與物件generation/hash；在隔離PG18.6實際還原，比對表/FK/約束/筆數/權限/Session隔離；確認保留責任與回復時間。是否啟用自動備份/PITR為Owner決策，不擅自開啟；不能把本機結構重建當完整備份恢復。

## main 自動發布影響（本輪即時唯讀）

- `lw-api-main` Trigger `6ffa2066-8edd-4406-9f3f-31f967da57dc`：repo asixtw/life-world、`^main$`、approvalRequired=true。本PR命中app/tests等includedFiles，Merge會觸發需人工核准Build，**不是Merge後完全不建置**。
- 現有Build `3b71f171-045d-4d49-a12b-2226102441bf`，Commit `68102f230aa947a434286ba9260e1ae75f6634b0`，狀態PENDING/approval PENDING，保持不變。新Merge不得誤核准這筆舊Build。
- `lw-web-main` Trigger `711e7258-2725-4007-a555-0f0100b77dbc`未設人工核准；本候選未命中其includedFiles，暫無觸發證據。Merge前若base/head/filters變動須重算。
- global Trigger清單空，現分支沒有.github/workflows。兩Build YAML均調用release.py，服務名組成`lw-api-main`/`lw-web-main`，不以此推論沒有其他外部人工作業；發布前仍核對服務來源連結/活動Build。
- `lw-public` 100%仍`lw-public-camera-8f377fa`，Digest `sha256:68f072c973ab40075b1ba5533a55a6324d5c7a3cf71b00920b0dfc589e2e0e75`。
- API main 100% `lw-api-main-c-94975cd3a6854941b1705c5634c777b3`，Digest `sha256:e7cf92e11bde21704a824c56eea58a773c98c6491bc646849f1881a101607c21`；latestReady另為tag e2e候選，不等於主流量。
- Web main 100% `lw-web-main-c-13023a4b4ed8448bab94ca3502269eda`，Digest `sha256:704d712bf84d236716a9e50ddfaf80c6fe329fed19f1e522dbb4a1346d478ba1`。三服務未改。

## 精確的下一階段操作順序（方案，NOT EXECUTED）

1. Owner核准固定候選UX；獨立Reviewer按上述分區與收據Code Review。若Commit變動，重新核對受影響測試，不沿用不相干綠燈。
2. 先完成來源/011/最小權限/Purger/回復審查與完整備份演練。Owner逐項批准E2E Migration/GRANT，指定既有可用DBA角色；先E2E，不動Alpha。前置DB/Marker/PG/Owner/表指紋不符即停止。
3. **取得Build授權後**，由固定Commit建立不可變Image，收錄Git SHA/Tree、Build ID、VCS_REF、SBOM/掃描結果及registry digest；不把tag當digest，不批准待核准的舊main Build。此刻新Digest尚不存在，不能填假值。
4. **取得E2E部署授權後**，使用既有受控E2E入口。現有`lw-api-main`的e2e tag可供審查，但部署前必須核對該Revision的DB/Marker/SA/Secret references與主服務配置隔離；若無法證明不影響main，停止請Owner核准精確隔離目標，不臨時建立新服務。候選固定Digest、`--no-traffic`，不得切三個main/public的100%。保存原tag/Revision/Digest作路由回復收據。
5. 合成Owner UI→API→PG驗收：Guest/測試帳號、本人操作真Google升級/舊世界、真Gemini明示授權及有限預算、照片/短長音訊、生日任職/多人/來源採用排除、草稿重登/版本/重送/回滾、跨Owner/CSRF、撤回與歷史/獎勵。報告每項PASS/FAIL/SKIP/NOT RUN。真Provider費用須另有核准，未知費用不當零。
6. **回復演練**：E2E驗證失敗先停候選新寫入/AI，將已記錄e2e tag回原Revision（需部署/路由回復授權），保留資料；只用已實測兼容reader/同Schema映像，不DROP011或回舊Alpha解讀新格式。資料恢復另行批准且在隔離環境先演練。
7. A/B/C及備份、獨立Review全通過後，才提請Owner批准**Merge**。以當時精確base/head完成合併，讀回main SHA/Tree與新Build ID；保持人工核准。Merge授權不等於批准Build或Deploy。
8. Owner分別批准正確Commit的Build/Alpha011/權限/部署/切流後才操作。Alpha先0%候選完成啟動/登入/Owner/寫入/資料回讀，再按另行批准的流量比例切換；保存已知相容回滾Revision/Digest。舊8f377fa在新格式寫入後不自動視為資料相容Rollback。任何非預期資源/Schema/流量差異立即停止，不擅自回滾資料。

## 現在需Owner決定／仍不可代辦

1. Gate A人工核准及指定獨立Reviewer。
2. 備份與隔離恢復的執行授權/保留責任；是否啟用自動備份/PITR。
3. 011/最小權限、完整來源持久契約、Purger/相容Rollback審查通過後，另批E2E Migration/GRANT；**現在不要求直接執行SQL**。
4. 固定Image Build、E2E部署與真Google/付費AI驗收各自授權；main Merge/Alpha發布仍另批。

在上述阻擋解除前，正式GCP E2E結果為NOT RUN，無新Image Digest，結論維持**NO-GO**。此報告不授權任何操作。

## 遠端並行提交處理

第一次普通Push被拒（遠端由846f250進到8c82c49）。唯讀Fetch確認新提交只改Soft Life視覺、Lumi圖及測試/文件，沒有覆蓋本輪service.py/relationship_memory.py。使用正常分支Merge a2eb363保留雙方提交，沒有force/rebase或Merge main。新視覺仍為Candidate，需Owner對合併後畫面做Gate A，不能拿舊截圖自動核准。合併後26項UI/PG、5項視覺Node與原入口驗收均PASS，沒有重新冒稱跑完整788項。
