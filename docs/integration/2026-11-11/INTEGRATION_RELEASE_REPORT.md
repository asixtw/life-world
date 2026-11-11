# Integration Release Report｜進行中／NO-GO

2026-11-11。分支`integration/pr24-first-unified-schema010-20261111`，[Draft PR #26](https://github.com/asixtw/life-world/pull/26)。本輪基準fac5900；本報告與新增UI變更的精確Head/Tree以PR更新收據為準。沒有Merge、Build、Deploy、正式Migration/GRANT、IAM/Secret或Alpha切流。

## 最新驗證（不可加總為單一套件）

| 範圍 | 實際結果／證據 |
|---|---|
| 完整本機API及Node suite | **732 PASS、62 SKIP**；evidence/FULL_LOCAL_SUITE.log。專用PG案例在此跳過，並非全綠 |
| 人物/草稿/摘要/本機多人快照/手機專注Chromium | **18 PASS**；evidence/WORKFLOW_BROWSER.log |
| 最窄320px及100人容量 | 已含在上述18項同次執行；額外WORKFLOW_320_BROWSER.log保留早期單項收據 |
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

1. **完整PR24 Candidate A1/A2四步尚未完成**：逐人收合補充、人工核對候選、第四步摘要式可點擊差異/來源Bottom Sheet仍待串接；當前第三步還含舊fieldset，第四步仍有舊核對表單。新增卡片不是最終UX驗收，不能以這組截圖取代Owner審查。
2. 伺服器草稿尚未保存完整補充候選/手動摘要的跨Session狀態；同名人物核對的跨伺服器草稿恢復需補齊契約，避免重複詢問。未支援欄位不開放白填，不將公司/生日塞進tags/notes。
3. Feature Store PG兩表未建立；衍生失效/長期記憶與人物基本資料AI上下文尚未完成。來源撤回API不代表Feature Store已驗收。不啟用額外AI。
4. GuestPurger需依真實FK及011新增表審查，維持fail-closed；未啟用正式刪除排程。
5. 正式011/最小權限、完整Sequence補驗、GCP E2E、備份Restore/Rollback演練、真Google聯合驗收、固定Release SHA/Digest/Revision仍待完成。
6. UX Owner核准、Code Review、明確Main Merge及Alpha發布授權均未取得。**保持Draft／NO-GO**，不藉測試PASS跨Gate。
