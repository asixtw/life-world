# Integration Release Report｜進行中／NO-GO

2026-11-11。分支 `integration/pr24-first-unified-schema010-20261111`。未Merge main，未Build／Deploy，未執行正式SQL寫入。

| 項目 | 狀態 | 證據／剩餘工作 |
|---|---|---|
| main／PR22/24/25／Jerry精確SHA、Tree | PASS | BASELINES.json |
| PR重疊與整合來源 | PASS（本機） | OVERLAP_MATRIX.json；22/24/25合併本機，EVOLUTION保留雙邊歷史；Jerry只選資料服務/DTO/SQLite相容Migration，未取UI/生成入口 |
| API／語意契約提交 | READY | CONTRACT_V1.md + PERSON_BASIC_DETAILS_CONTRACT.md，後者取代延後生日/公司/職稱的舊規則 |
| GCP服務/觸發器只讀 | PASS | evidence/；API主Trigger requireApproval=true；Web路徑需最終diff重查 |
| E2E/Alpha已知結構 | PASS（快照範圍） | SCHEMA_DIFF_REVIEW.md；42表326欄2序列，81FK；Structure SHA256兩庫相同 |
| Sequence完整參數/有效權限 | NOT RUN | 首版SQL未含所有序列參數，需補驗；不稱完整Schema發布核准 |
| 兩庫Migration歷史 | 不同／保留 | E2E010一筆，Alpha5筆，不重跑或偽造補齊 |
| 多人Confirm與草稿DELETE | 本機實作／部分PG PASS | target/client_ref、同Owner/revision/來源、全交易/去重；現有Runtime沒有drafts DELETE權限，DML審查阻擋部署 |
| 生日/多任職API與歷史 | 本機實作／部分PG PASS | BASIC_API_GREEN 29 PASS（含DTO/目標）；BASIC_ATOMIC 5 PASS，包括多人資料正確定向及晚期失敗整筆回滾 |
| 人物/來源/Google交換回歸 | PASS（SQLite） | DATA_CORE 122 PASS，真Google另驗 |
| 完整SQLite suite | PASS／有跳過 | 本輪718 PASS、49 SKIP、0 FAIL；16項本機PG另行執行PASS，其他舊PG專用測試未執行，詳見FULL_LOCAL_SUITE.log，不稱全部測試全綠 |
| PR24新UI正式整合 | IN PROGRESS | 目前僅PR24舊產品四步及Candidate參考；尚未把A1/A2新人物補充、詳情/草稿刪除全接API |
| 010 GuestPurger／新增FK | BLOCKED | 需按真實81FK與011新增表審查，保持fail-closed，不啟用清理排程 |
| 生日任職來源撤回/衍生失效 | IN PROGRESS | 已驗來源Owner及available；主動撤回歷史與衍生失效仍待完整串接/測試 |
| 增量Migration | REVIEW ONLY / GCP NOT RUN | migrations/011草案，SQLite等價只供隔離測試；本機PG18草案試跑PASS，GCP未執行；最小權限另審 |
| 009 Feature Store PG | BLOCKED | 兩庫皆無兩表，不能用SQLite009冒稱存在，不啟用背景AI |
| Integration Draft PR | IN PROGRESS | [Draft PR #26](https://github.com/asixtw/life-world/pull/26)，持續顯示所有缺口 |
| 新main SHA | NOT RUN | 保持68102f230aa947a434286ba9260e1ae75f6634b0 |
| E2E新SHA/Digest/Revision | NOT RUN | 現有tag為lw-api-main-b8030-11111349／a37a39c4…，不是本輪整合部署；標籤仍82d0925不能冒稱固定來源驗證 |
| Alpha新SHA/Digest/Revision | NOT RUN | 現役lw-public-camera-8f377fa，Digest 68f072c9…，100%不變 |
| 備份/Restore/Rollback演練 | NOT RUN（本輪） | 不沿用舊備份PASS作新發布驗收；Migration不可假設隨應用Rollback回復 |
| UX/CodeReview/Merge/Alpha授權 | BLOCKED | Owner UX尚未Approved，不Merge、不Deploy、不正式Migration |

下一步：完成PR24 UI/API接線與草稿媒體清理、P0來源撤回及完整回歸；擴充隔離PG18交易/011與FK/最小權限審查，後續經明確批准才進E2E套用。禁止把快照相等、SQLite PASS或Draft PR當成可發布。

## 本輪追加證據（不等於發布驗收）

- 本機PG18.0從Owner快照建立無業務資料副本，8類structure逐項相等；缺失的原Sequence參數仍未證明。
- 同一011審查SQL僅於本機試跑成功。8項PG測試PASS：生日/任職歷史、多人物、Owner隔離、重送、回滾、Runtime負向權限、Migration重跑拒絕。見 evidence/PG18_STRUCTURAL_COPY_RECEIPT.json 與 PG18_PERSON_DETAILS.log。
- 正式草稿刪除權限及011四表仍不存在於兩個GCP資料庫；本機測試授權不能視為正式授權。
- 人物詳情與草稿刪除局部API/UI已接線；完整四步Candidate A1/A2串接、來源撤回、Purger適配及真Google聯合驗收仍未完成。

## 第三步同Owner升級與PG交易補驗

- `PG18_PERSON_DETAILS.log`：16 PASS。包含受限Runtime、多人資料與草稿刪除。刻意撤除本機drafts DELETE後，API回503且draft_stories刪除回滾；只恢復本機提議權限後，同request_id重試成功且不重做。
- `STEP3_UPGRADE_RED.log`：390/1440原先2 FAIL，實際重現升級後人物區未解鎖。
- `STEP3_UPGRADE_BROWSER.log`：8 PASS。僅局部解鎖第三步，原Owner/表單DOM/原文/數量及未關聯人物狀態保留，可直接進第四步。取消/拒絕交換不改訪客資料。GIS為明示替身，真Google NOT RUN。
- `screenshots/390-step3-upgrade-unlocked.png`及1440版本是局部整合證據，仍為舊版產品人物區，不宣稱A1/A2完整UX或Owner核准。
- 本輪完整SQLite718/42skip收據早於上述局部解鎖修改；最後source checkpoint須重新執行完整套件，不能當作新HEAD完整驗收。

- 最小DML提案補驗：先重現table-level UPDATE允許Owner改派的負向紅燈，改為欄位UPDATE後16 PASS；Owner/person_id/id不可改，History不能UPDATE/DELETE。只改本機marker副本，正式GRANT仍待審查。
- 完整套件最新718 PASS、49 SKIP；其後僅追加1項PG專用負向測試及本機fixture欄位授權修改，16項PG套件已涵蓋該變更。

## 來源撤回增量驗收

- 生日與指定任職新增明確source-withdrawal API及詳情頁二次確認。原值、quote、confirmed_at與舊版本保留，僅source_status/revision/updated_at更新、追加source_withdrawn歷史。
- 正常/未確認/跨Owner/CSRF/版本/同request不同payload/重試/再次撤回無變更皆測試。注入收據失敗時目前值、History及request收據一併回滾；PG受限欄位DML不擴大。
- 最新完整本機API：720 PASS、52 SKIP。獨立本機PG18 suite：18 PASS。人物資料Chromium（含390/1440撤回取消/確認）：6 PASS。真Google/GCP/AI仍NOT RUN；不是整體產品完成。
- 現有Feature Store PG表不存在，人物基本資料尚未接AI上下文；衍生特徵失效仍IN PROGRESS，不以來源狀態API代替長期記憶驗收。
- 本輪唯讀remote核對main仍68102f230aa947a434286ba9260e1ae75f6634b0。沒有Merge、Deploy、正式Migration或GRANT。

## P0追加：AI測試額度與帳號隔離（本輪實作，Alpha尚未部署）

- 移除AISettings寫死US$20最高值；Alpha採明確有限總額/日額、可配置提高每日次數。隔離E2E的explicit unlimited-total模式僅停用累計限制，仍保留日額/次數/總開關/並發，from_env及PG Runtime限制目標庫及public_alpha模式。
- 保留耐久預留、PG advisory lock、失敗/未知費用不釋放，新增可配置每process在途上限與request id去重（重送409，不冒稱可重取未保存的模型全文）。歷史預留納入有限總額，不能靠重啟歸零。
- GET /api/ai/usage SQL以Session Owner過濾，只回本人預留/次數/Tokens/收據。全域預算/剩餘額/歷史預留不回一般API；沒有公開admin usage路由，query admin/owner_id不能擴權。內部管理監控SQL另外隔離，未新增IAM/DB授權。
- UI只顯示「我的AI用量與收據」，預留及供應商回報均不當成實際帳單。換Owner後不顯示延遲的前帳號收據。
- 最新完整本機suite：732 PASS、62 SKIP；AI專項36 PASS/7 PG SKIP；另以本機PG18受限Runtime執行該7項PASS。UI metadata fixture 390/1440及延遲Owner切換3 PASS。沒有呼叫真模型；不能宣稱Alpha新額度或真AI本輪E2E已PASS。
- Alpha唯讀現況仍100% lw-public-camera-8f377fa：Owner每日100、全域1000、每次預留500000microusd、日額19000000、累計19000000、歷史1000000，舊程式未換。既有E2E缺AI批准/累計設定，不宣稱已可真呼叫。
- [額度建議與停用/恢復程序](ai/AI_BUDGET_POLICY.md)：候選Alpha有限US$100累計、US$25/滾動24h、維持US$0.50每次預留，約50次模型預留/日，Owner500/全域5000次、每process4在途。這是待Owner決定及發布Gate的建議，未批准/未套用，不是帳單預測。
- 測試證據：AI_POLICY_SQLITE.log / AI_POLICY_PG18.log / AI_PERSONAL_USAGE_BROWSER.log；實際非敏感設定白名單 AI_LIMITS_DEPLOYED_READ_ONLY.json。無API Key/Token/Secret。

多人草稿同步追加：story.pending_people保存及Confirm解析已在SQLite/PG實測；新增3項PG後人物/草稿PG共21 PASS。舊UI保留新版名單，返回修改原文回Step1；人物瀏覽器7 PASS。完整Candidate新增/編輯/補充/差異預覽仍未完成，不能以此兼容摘要替代最終四步UX。
