# Integration Release Report｜進行中／NO-GO

2026-11-11。分支`integration/pr24-first-unified-schema010-20261111`，[Draft PR #26](https://github.com/asixtw/life-world/pull/26)。本輪基準7bd852f；本報告與新增UI變更的精確Head/Tree以PR更新收據為準。沒有Merge、Build、Deploy、正式Migration/GRANT、IAM/Secret或Alpha切流。

## 最新驗證（不可加總為單一套件）

| 範圍 | 實際結果／證據 |
|---|---|
| 完整本機API及Node suite | **747 PASS、78 SKIP**；evidence/FULL_LOCAL_SUITE.log。專用PG案例在此跳過，並非全綠 |
| 前一UI階段工作流/精簡人物/用量/世界交換Chromium（同次；本輪授權UI未驗） | **66 PASS**（27工作流/預覽＋18草稿/補充＋10精簡選擇＋3用量＋8 GIS替身）；evidence/COMPACT_PEOPLE_BROWSER.log |
| 最後重複提示文字調整後 | **6 PASS**（三尺寸選擇及補充完整確認），COMPACT_PEOPLE_COPY_BROWSER.log；不與66加總 |
| 人物候選版本衝突／確認503重試 | 追加分開執行 **1 PASS／2 PASS**；CANDIDATE_VERSION_BROWSER.log、CANDIDATE_RETRY_BROWSER.log，不與本次66重複加總 |
| 320/390/1440、長內容/大字/焦點、100人容量 | 已含在上述66項同次執行；WORKFLOW_320_BROWSER.log是早期單項收據 |
| Google世界交換Chromium | 本次66項內含 **8 PASS**；明示GIS替身，非真Google。GOOGLE_TRANSITION_BROWSER.log另為前次單獨收據 |
| 受限本機PG18人物/草稿/AI | **44 PASS**；evidence/WORKFLOW_PG18.log，只在marker合成副本，不連CloudSQL |
| 草稿AI授權專項（本輪） | SQLite **6 PASS**；缺撤回權限的PG額外 **1 PASS**，不與完整套件加總；DRAFT_AI_CONSENT_SCOPE.log、DRAFT_AI_CONSENT_PERMISSION.log |
| 本人AI用量Chromium | evidence/AI_PERSONAL_USAGE_BROWSER.log：3 PASS；metadata fixture，不是真模型 |
| 真Google、新GCP整合Revision、真AI/媒體Provider、Safari | **NOT RUN（本輪）** |

新增紅燈證據：SUMMARY_REVIEW_RED、MULTI_PERSON_UI_RED、MULTI_PERSON_LOCAL_RED、MOBILE_FOCUS_RED，均為實際瀏覽器行為缺失，非環境失敗。測試指令與原始結果保留於evidence。沒有因新UX刪除API斷言或改獎勵規則。

## 已實作／局部整合

- 從main 68102f230aa947a434286ba9260e1ae75f6634b0整合PR22/24/25；Jerry僅採必要資料服務/DTO/SQLite相容Migration，未採大型人物UI或生成入口。精確來源/Tree/重疊見BASELINES.json、OVERLAP_MATRIX.json。
- 多人target/client_ref、待建人物、生日/多任職/歷史共用Confirm交易。版本、Owner、來源及去重保護；晚期失敗整筆回滾。story.pending_people保存草稿不建人，最後人工確認才解析。
- 第三步可在原待建人物介面新增第二位以上、逐人更改稱呼/角色、選精確提及位置、移除候選。確認前沒有新人物；提及不計直接互動。320/390/1440實測。仍非完整Candidate A1/A2人物補充介面。
- 未完成角色可保留為Owner隔離的本機草稿，包含穩定client_ref及「是否關聯人物」選擇；離開後新分頁恢復不自動改related，不先建正式人物。沿用既有IndexedDB，不另存伺服器媒體或改帳號交易。
- 同Owner Google升級只局部解鎖人物區，保留原表單DOM、步驟、原文、數量與不關聯人物選擇；取消/拒絕交換不改訪客資料。真Google聯合驗收仍未執行。
- 第四步返回修改原文時回Step1。保留同Owner同草稿的手動摘要；原文改動後出現明確重核對勾選，確認前不能略過。未改原文不重置；重新核對後只返回查看不重複索取。另一份草稿不沿用摘要。另已新增可選DraftReview JSON契約及「保存核對草稿並離開」，已保存摘要/任務可重新整理讀回；未保存的變更仍不承諾跨Session恢復。
- 手機四步暫時隱藏全域底部導覽，提供明確「離開記錄」，沿用未保存保護；離開恢復導覽，伺服器草稿保留。320/390實測。沒有自行標記UX Approved。
- 草稿DELETE API與局部UI，成功收據後只清精確Owner/draft本機素材。缺DELETE權限會503且關聯資料完整回滾；同request可安全重試。
- 人物詳情生日/任職讀寫、版本歷史、來源撤回與二次確認；保留原值/quote/confirmed_at，append-only撤回歷史。不是刪除原經歷，也不改獎勵。

## Schema與正式環境基線

Owner提供兩份唯讀Schema Snapshot。E2E/Alpha結構相同：42表、326表欄、2序列、81FK、88 indexes；含序列內部欄共332欄、全部約束512。structure SHA256皆`0e3d04411e843b509e120d9e4dd073f304c03f39317cc57958b4c6b78a0f2e8e`。Owner/ACL依庫不同，Migration歷史不同，保留來源，不重跑010或偽造收據。詳見SCHEMA_DIFF_REVIEW.md、SCHEMA_DIFF.json與schema原始快照。

本機PG18.0從空資料建立結構副本，8類catalog相等、零業務資料/收據複製。011審查草案只在此副本試跑，不能當備份還原；原快照缺Sequence完整參數，且CloudSQL是18.6，仍需實際相容性驗收。兩個GCP庫均未有011四表、Feature Store兩表；Runtime缺drafts DELETE。所有正式DDL/DML權限提案仍待審查，本機欄位GRANT不代表正式授權。

- Alpha現役100%仍`lw-public-camera-8f377fa`，Digest `sha256:68f072c973ab40075b1ba5533a55a6324d5c7a3cf71b00920b0dfc589e2e0e75`。
- API主服務仍life_world_dev舊版本；E2E tag `lw-api-main-b8030-11111349`、Digest `sha256:a37a39c4ab1634b53cecd7792e76d5843232ed9c50d646e834c069c722f79dc2`是既有版本，不能當本輪整合版本。其舊commit標籤未驗證真實來源。
- GCP只讀/ready HTTP200只是既有環境證據，不是整合E2E。主API trigger requireApproval=true；main合併前仍須重查Web等實際路徑觸發條件。

## AI P0追加

不再硬編碼US$20最高值；Alpha必須有限配置總額/日額及正預留，次數可提高。E2E explicit unlimited-total只停累計限制，不停日額/次數/總開關/並發；環境及實際PG DB設定均須為隔離E2E。保留PG預留鎖、失敗/未知預留、歷史預留及request去重；未知結果重送409，不冒稱可重取未保存的模型全文。

GET /api/ai/usage只查Session Owner，沒有全域數值或admin視角query；不存在公開admin usage路由。內部管理SQL獨立。UI只顯示本人預留、次數、已知Tokens與收據，預留/供應商回報皆非帳單，換Owner後丟棄延遲回應。

Alpha仍是舊Runtime，非敏感現況/候選設定及停止程序見[AI_BUDGET_POLICY](ai/AI_BUDGET_POLICY.md)、evidence/AI_LIMITS_DEPLOYED_READ_ONLY.json。US$100累計/US$25日額等僅候選建議，未批准/未套用；本輪沒有真模型費用。

## 未完成／發布Gate

1. **完整PR24 Candidate A1/A2四步尚未完成**：第三步人物選擇已換為精簡搜尋/卡片/明確角色，四維補充預設收合；基本資料候選與差異仍待串接；第四步四維候選逐項人工核對與原有事實讀取已接上，不能當成完整人物補充完成；第四步修改區仍保留舊編輯器，但預設畫面已收合為摘要。不能以這組工程截圖取代Owner審查。
2. DraftReview已可保存摘要/任務/四維事實候選及逐人target；SQLite/PG重新登入讀回與同名人物分流已驗證。第三步四維補充已接上；生日/任職候選草稿及同名核對狀態尚未接齊。第四步已可逐人核對已保存四維候選並選用同一Confirm交易；不得誤稱完整人物補充已可用。未支援欄位不開放白填。
3. Feature Store PG兩表未建立；衍生失效/長期記憶與人物基本資料AI上下文尚未完成。來源撤回API不代表Feature Store已驗收。不啟用額外AI。
4. GuestPurger需依真實FK及011新增表審查，維持fail-closed；未啟用正式刪除排程。
5. 正式011/最小權限、完整Sequence補驗、GCP E2E、備份Restore/Rollback演練、真Google聯合驗收、固定Release SHA/Digest/Revision仍待完成。
6. UX Owner核准、Code Review、明確Main Merge及Alpha發布授權均未取得。**保持Draft／NO-GO**，不藉測試PASS跨Gate。


## 本輪第四步摘要與只讀預覽

- 原文及原有媒體功能收合於來源區，活動量/人物修改/後續任務預設收合；預覽與實際Confirm共用當前表單值，不另建測試頁或模擬資料模型。
- 人物卡只顯示名稱、既有/待建/待配對狀態與角色，依person_id/client_ref逐人解析，不把資訊套到第一人。只有本次真正提交的資料才列保存範圍，沒有猜測公司/職稱/生日。當前關聯預覽不是完整人物補充差異預覽。
- Native Dialog手機Bottom Sheet固定標題/完成操作、body獨立捲動；原文不另套第二層小捲軸。320/390/1440長原文及24px大字實測，關閉/Escape後焦點回原卡片。開關預覽無寫入請求、業務state前後相同。
- 回歸發現舊review快取會在新草稿版本覆蓋角色/活動量，已依revision保留人工摘要等輸入、以新版草稿角色/數量為準。核對入口去重；角色/原文改變才失效，僅返回查看保留已核對。新活動量0.75真實Confirm讀回0.75，獎勵僅一筆。
- [390px第四步](screenshots/390-step4-summary.png)、[320px預覽](screenshots/320-step4-person-preview.png)、[1440px預覽](screenshots/1440-step4-person-preview.png)。皆為合成資料，本輪未Deploy、未執行真Google/AI。

### 本輪命令與環境

Python使用/private/tmp/lw-integration-venv，Node使用已驗SHA的/private/tmp/lw-integration-node/node-v24.11.0-darwin-arm64/bin/node。伺服器為隔離SQLite、固定合成時鐘；PG命令只接受已驗證本機marker。下列指令不代表GCP套用授權：

```sh
PATH=/private/tmp/lw-integration-node/node-v24.11.0-darwin-arm64/bin:$PATH LIFEWORLD_NODE=/private/tmp/lw-integration-node/node-v24.11.0-darwin-arm64/bin/node python -m pytest tests -q --tb=short
LIFEWORLD_TEST_URL=http://127.0.0.1:8192 GOOGLE_TRANSITION_TEST_URL=http://127.0.0.1:8188 python -m pytest browser_tests/test_draft_review.py browser_tests/test_integration_person_details.py browser_tests/test_ai_usage_personal.py browser_tests/test_google_world_transition.py -q --tb=short
GOOGLE_TRANSITION_TEST_URL=http://127.0.0.1:8188 python -m pytest browser_tests/test_google_world_transition.py -q --tb=short
LIFEWORLD_INTEGRATION_PG_CONFIG=/private/tmp/lw-integration-pg18-config.json python -m pytest tests/test_pg_integration_person_details.py tests/ai/test_pg_ai_usage.py -q --tb=short
```

未完成範圍仍含：完整多人補充UI與基本資料候選草稿、基本資料/事實原值與新值差異、逐項來源/版本確認、AI手動/選用與首次授權的完整Candidate串接。設計/Review/正式Migration/GCP E2E/Merge/Alpha Gate維持未通過。


## 本輪核對草稿契約

- 詳見[DRAFT_REVIEW_CONTRACT](DRAFT_REVIEW_CONTRACT.md)。沿用draft_stories既有JSON，沒有新建DB表或改正式資料；draft.review與story分開，最後Confirm才將明確選用的四維候選轉為targeted updates。
- 8項SQLite新案例及同契約PG案例，驗證摘要/任務保存、原文改動重核對、手動來源保留、雙Owner隔離、重新登入讀回、同名雙人不合併、無效證據不猜預設、晚期版本衝突全交易回滾與重送。
- Chromium在320/390/1440實際保存核對草稿→重新整理→正式確認；503保存失敗保留輸入，來源重核對後保存讀回；缺來源hash的摘要只保存不會被誤視為已核對。紅燈曾重現保存摘要讀回卻顯示原文，已修復。新畫面[screenshots/390-saved-review-roundtrip.png](screenshots/390-saved-review-roundtrip.png)。不代表Owner UX核准。
- **Rollback風險**：新的experience_draft_v2 JSON須使用支援此格式的reader；不能假定直接退回不支援格式的舊應用可無損讀取。正式部署前須完成reader相容發布/回復驗證。當前沒有在Alpha寫入此格式。


## 本輪第四步逐人人物候選

- 對每位既有person_id與待建client_ref只顯示該目標的四維候選，不依名字配對；原有事實經Owner限定GET讀取，與本次新增分開，不冒稱取代原資料。公司/生日/任職不塞進四維欄位。
- 逐項採用或排除；source_kind仍是輸入管道，evidence_type明確選擇且無預設推測。raw來源變動後需對照當前原文/片段重新勾選；缺失片段不能採用。候選原版本保留，不因讀取新人物資料靜默改expected_person_revision。
- 採用/排除只改本草稿前端狀態；保存核對草稿可跨重新整理恢復，正式Confirm才與人物/事實/來源/經歷/進度/任務/獎勵同交易。與舊單人候選同時選用明確報錯，不靜默丟棄。503後保留核對結果，可重試，不重複建人/計分。
- 抽屜更新單列狀態不重建全表單，關閉焦點回人物卡；較舊GET以Owner/草稿/人物key防止污染新抽屜。320/390/1440的新增與原有→本次資訊畫面已作本機Chromium證據。
- 第三步四維補充已在本輪接上，另以實際UI輸入完成第三步→第四步→Confirm，證據見下一節；既有API種入候選測試仍保留作低層回歸。完整UX、真Google、外部AI與GCP整合Gate不變。

本輪候選畫面：[320px待建人物排除](screenshots/320-targeted-candidate-review.png)、[390px原有/新增事實](screenshots/390-prior-and-candidate-facts.png)、[1440px原有/新增事實](screenshots/1440-prior-and-candidate-facts.png)。此UI階段可回復至dd4bea4支援envelope的reader，但不能據此宣稱Alpha舊Runtime可無損回復新格式。


## 第三步收合補充（本輪，未部署）

- 新模組experience_supplements.js沿用原四步/Owner/草稿與Confirm，不呼叫獨立建人或事實寫入API；每位人物預設收合，加入候選後自動收合並回復焦點，第四步才逐項採用。公司/職稱/生日的本次候選未接通，不開放白填或繞存。
- 已選既有人物與待建人物各自維護四維內容、來源、證據類型；單人舊表單只在需要時轉為穩定legacy client_ref的多人契約，加入第二人不換掉第一人的候選target。同名不合併。
- 未加入候選的文字會阻擋伺服器保存，提供清空本次輸入，不清除已加入候選；既有Owner/draft IndexedDB可保留已加入及尚未完成內容。移除人物不默默把候選轉給別人，需重新關聯或明確移除。伺服器草稿不建人；最終交易才建人/寫事實/計分。
- 實際測試發現僅提及者的事實會被舊參與來源檢查拒絕。修復只對人物事實接受已人工配對且有效的提及來源；其他API的參與/關係來源規則不放寬，不新增參與/互動列。SQLite及受限PG18驗證、相同請求去重與零互動統計通過。
- 320/390/1440實際UI輸入兩位人物不同資訊→返回→保存草稿→逐項核對→Confirm→API讀回事實/一次獎勵通過，不預先種入人物候選。未加入輸入保護及新分頁本機恢復另已測試。其後第三步已改為精簡選擇區，見下一節；完整UX仍需Owner核准。
- fact_sources既有API尚未顯式投影manual/raw輸入管道；該資訊目前保存在已確認草稿的DraftReview JSON，與evidence_type分開。完整來源瀏覽/來源撤回衍生失效仍需完成，不冒稱已全數整合。
- [第三步契約與限制](STEP3_SUPPLEMENT_CONTRACT.md)、[390px](screenshots/390-step3-supplement-input.png)、[1440px](screenshots/1440-step3-supplement-input.png)。保持Draft／NO-GO，沒有正式DB/權限/部署操作。


## 精簡第三步人物選擇（本輪，未部署）

- 移除第三步整份參與/直接互動checkbox列表，改為「選擇既有人物／新增人物」與所選人物卡。角色必須明確選，沒有預設互動。一般日記不必開啟人物；搜尋無結果、關閉、移除與鍵盤焦點已有測試。
- 既有人物提及與未配對稱呼都需選原文精確位置，不默認第一處同名；同一人物既參與又被提及的舊資料分別保留，不改歷史事實。其他原文稱呼與故事標題預設收合。第三步四維補充仍沿用前一階段，不新增AI或正式欄位。
- StoryInput／DraftReview／Confirm契約、Owner及最終交易規則不變；experience_people.js只負責視圖及canonical資料投影，沒有寫入API。第四步修改區與來源管理目前仍用原編輯器，不擅自替換其契約。
- 本機人物行資料以穩定row key保留未完成角色、來源及Owner；沿用既有Media scope。回退至9b0592c可讀伺服器標準草稿，但舊UI不能自動恢復新workflow_existing_people的本機未保存選擇；正式發布前需相容reader/匯出方案，原始素材不自動刪除。Alpha未寫此本機格式。
- 最新main唯讀核對仍68102f230aa947a434286ba9260e1ae75f6634b0。66項Chromium套件含10項新選擇契約：三種人物類型、來源、同人雙角色、Owner隔離、未完成恢復、320/390/1440及基本鍵盤。最後僅重複提示文字調整後重跑6項；當時API/Node為741 PASS/71 SKIP。PG37是同一後端上一階段的實際收據，本輪無後端變更，不宣稱重跑GCP。
- [精簡選擇契約](COMPACT_PEOPLE_CONTRACT.md)、[390px](screenshots/390-compact-person-selection.png)、[1440px](screenshots/1440-compact-person-selection.png)。整體UX、Review、GCP E2E及發布Gate不變。


## 草稿AI授權後端（本輪，未發布）

- 沿用既有data_consents，不新增Schema或另一份同意狀態。提供Owner限定GET/POST/DELETE /api/ai/draft-consent；策略綁提供者/模型/真實或替身/用途/來源範圍。嚴格confirmed=true、CSRF、Owner交易鎖、唯一active索引與request_id收據；撤回後舊請求409，不重新授權，保留同意歷史。
- enabled的/suggest在預留與Provider之前檢查本用途有效同意。背景同意不涵蓋草稿。experience操作不再因背景FeatureStore開關偷偷附帶其他記憶；只送本篇原文與固定指令，摘要/任務/人物資訊仍為待人工核對候選。
- 實際PG測試發現source_scope的既有CHECK要求JSON物件，已依快照/PG驗證修正，沒有放寬CHECK。44項受限PG套件含6項授權/隔離/Provider變更/撤回/背景範圍測試，以及1項撤回權限缺口驗證；最新狀態欄位另單項重驗通過。
- Alpha原快照Runtime僅SELECT/INSERT，無revoked_at UPDATE；本機marker副本測試提議的UPDATE(revoked_at)，Owner/用途/來源等其他欄位仍不可UPDATE。正式GCP未GRANT。後端缺撤回能力時停用本用途，不假稱沒有既存同意或允許無法撤回的授權。
- [契約](ai/DRAFT_AI_CONSENT_CONTRACT.md)、[欄位GRANT審查稿](migrations/DRAFT_AI_CONSENT_COLUMN_GRANT.review.sql)。不是正式套用指令，不新增Migration receipt，不改Schema/Owner/IAM。
- **前端仍未完成**：單一手動/AI選擇、首次告知、有效同意重用、撤回與失敗狀態待接。現有已配置AI的舊按鈕未經新授權會403，不能宣稱功能可用或發布；目前Alpha舊Runtime完全未變。本輪沒有真模型呼叫或新模型費用。

- 測試授權helper已放tests/conftest.py，避免獨立執行RC測試時依賴AI子目錄匯入；RC＋草稿授權獨立命令11 PASS，DRAFT_AI_CONSENT_HELPER.log，不與完整套件重複加總。
