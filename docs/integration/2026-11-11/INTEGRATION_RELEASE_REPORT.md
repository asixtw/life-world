# Integration Release Report｜進行中／NO-GO

2026-11-11。分支`integration/pr24-first-unified-schema010-20261111`，[Draft PR #26](https://github.com/asixtw/life-world/pull/26)。本輪基準6ae0322；本報告與新增UI變更的精確Head/Tree以PR更新收據為準。沒有Merge、Build、Deploy、正式Migration/GRANT、IAM/Secret或Alpha切流。

## 最新驗證（不可加總為單一套件）

| 範圍 | 實際結果／證據 |
|---|---|
| 完整本機API及Node suite | **732 PASS、62 SKIP**；evidence/FULL_LOCAL_SUITE.log。專用PG案例在此跳過，並非全綠 |
| 工作流/預覽及本人AI用量Chromium（同次） | **30 PASS**（27工作流/預覽＋3用量畫面）；evidence/WORKFLOW_BROWSER.log |
| 320/390/1440、長內容/大字/焦點、100人容量 | 已含在上述30項同次執行；WORKFLOW_320_BROWSER.log是早期單項收據 |
| Google世界交換Chromium | **8 PASS**；evidence/GOOGLE_TRANSITION_BROWSER.log，明示GIS替身，非真Google |
| 受限本機PG18人物/草稿/AI | **28 PASS**；evidence/WORKFLOW_PG18.log，只在marker合成副本，不連CloudSQL |
| AI專項 | evidence/AI_POLICY_SQLITE.log：36 PASS/7 PG SKIP；AI_POLICY_PG18.log：另行7 PASS |
| 本人AI用量Chromium | evidence/AI_PERSONAL_USAGE_BROWSER.log：3 PASS；metadata fixture，不是真模型 |
| 真Google、新GCP整合Revision、真AI/媒體Provider、Safari | **NOT RUN（本輪）** |

新增紅燈證據：SUMMARY_REVIEW_RED、MULTI_PERSON_UI_RED、MULTI_PERSON_LOCAL_RED、MOBILE_FOCUS_RED，均為實際瀏覽器行為缺失，非環境失敗。測試指令與原始結果保留於evidence。沒有因新UX刪除API斷言或改獎勵規則。

## 已實作／局部整合

- 從main 68102f230aa947a434286ba9260e1ae75f6634b0整合PR22/24/25；Jerry僅採必要資料服務/DTO/SQLite相容Migration，未採大型人物UI或生成入口。精確來源/Tree/重疊見BASELINES.json、OVERLAP_MATRIX.json。
- 多人target/client_ref、待建人物、生日/多任職/歷史共用Confirm交易。版本、Owner、來源及去重保護；晚期失敗整筆回滾。story.pending_people保存草稿不建人，最後人工確認才解析。
- 第三步可在原待建人物介面新增第二位以上、逐人更改稱呼/角色、選精確提及位置、移除候選。確認前沒有新人物；提及不計直接互動。320/390/1440實測。仍非完整Candidate A1/A2人物補充介面。
- 未完成角色可保留為Owner隔離的本機草稿，包含穩定client_ref及「是否關聯人物」選擇；離開後新分頁恢復不自動改related，不先建正式人物。沿用既有IndexedDB，不另存伺服器媒體或改帳號交易。
- 同Owner Google升級只局部解鎖人物區，保留原表單DOM、步驟、原文、數量與不關聯人物選擇；取消/拒絕交換不改訪客資料。真Google聯合驗收仍未執行。
- 第四步返回修改原文時回Step1。保留同Owner同草稿的手動摘要；原文改動後出現明確重核對勾選，確認前不能略過。未改原文不重置；重新核對後只返回查看不重複索取。另一份草稿不沿用摘要。此為活躍流程狀態，尚未新增伺服器草稿摘要契約，不能承諾跨Session恢復未保存摘要。
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

1. **完整PR24 Candidate A1/A2四步尚未完成**：逐人收合補充、人工核對候選及基本資料原值→新值差異仍待串接；第四步只讀關聯/待建姓名/來源Bottom Sheet已接上，不能當成完整人物補充完成；當前第三步還含舊fieldset，第四步修改區仍保留舊編輯器，但預設畫面已收合為摘要。不能以這組工程截圖取代Owner審查。
2. 伺服器草稿尚未保存完整補充候選/手動摘要的跨Session狀態；同名人物核對的跨伺服器草稿恢復需補齊契約，避免重複詢問。未支援欄位不開放白填，不將公司/生日塞進tags/notes。
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
LIFEWORLD_NODE=/private/tmp/lw-integration-node/node-v24.11.0-darwin-arm64/bin/node python -m pytest tests -q --tb=short
LIFEWORLD_TEST_URL=http://127.0.0.1:8190 python -m pytest browser_tests/test_integration_person_details.py browser_tests/test_ai_usage_personal.py -q --tb=short
GOOGLE_TRANSITION_TEST_URL=http://127.0.0.1:8188 python -m pytest browser_tests/test_google_world_transition.py -q --tb=short
LIFEWORLD_INTEGRATION_PG_CONFIG=/private/tmp/lw-integration-pg18-config.json python -m pytest tests/test_pg_integration_person_details.py tests/ai/test_pg_ai_usage.py -q --tb=short
```

未完成範圍仍含：完整多人補充候選的跨Session草稿保存、基本資料/事實原值與新值差異、逐項來源/版本確認、AI手動/選用與首次授權的完整Candidate串接。設計/Review/正式Migration/GCP E2E/Merge/Alpha Gate維持未通過。
