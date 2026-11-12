# PR #26｜AI-Assisted Code Review

2026-11-12，Asia/Taipei。結論：**Changes Requested；Merge Ready NO／GCP E2E Ready NO／Alpha Ready NO**。

本次為 AI 輔助程式審查，非獨立人工批准。Boyi 是 Owner，並非獨立 Code Reviewer；前份 CODE_REVIEW_FOR_BOYI.md／發布報告將 Boyi 稱為獨立人工審查者的敘述不正確，本報告明確更正角色，不代表取得任何 Review approval。Gate A 已由 Owner 核准，仍有效且只綁定 a2eb363 的 UX；本次不撤銷、不擴大。

## 固定基準與方法

- 工作目錄 `/private/tmp/lw-integration-20261111`，原整合分支 `integration/pr24-first-unified-schema010-20261111`；開始時工作區乾淨。
- GitHub 唯讀 GET 核實 PR Head **f3f4c9f5a9a0833d5966e427d9c9a33c85b45731**、Draft=true、main/base **68102f230aa947a434286ba9260e1ae75f6634b0**，與本機相符。
- HEAD Tree `ebf2b6ad6d72ffaa7553c848b0c0422fb4c1593d`；App Tree `c823bdde84ae8ab90c75a45d557cb6cd9e9c0623`，與核准產品 a2eb363 一致。
- PR 868 個檔案含大量文件／畫面；app/deploy/tests 範圍 101 檔、8368 additions／220 deletions。本輪為風險導向抽查，**未宣稱逐行讀完所有 868 檔**。
- 直接閱讀程式及契約，以額外合成探針驗證安全預期；既有 PASS 不當作無缺陷證明。沒有產品修碼、Commit、Push、正式 API 寫入、Migration、GRANT、Build 或 Deploy。

## 已確認缺陷

P0：本輪未發現已證實 P0，並非保證不存在。P3：無新增獨立問題。以下四項探針均以期望安全結果斷言，FAIL 是重現程式缺陷，非測試環境故障。

### F1｜P1：撤回故事後仍可被人物模擬傳給 Provider（繼承 main 的問題）

- **位置**：[ai_routes.py](../../../app/ai_routes.py#L117) 117–126；[people.py](../../../app/people.py#L204) 204–207；[connections.py](../../../app/connections.py#L152) 152–164。
- **原因**：`_fact_sources` 只驗 `fact_sources.revoked_at`，不驗 `experience_stories.available`；simulation 再查 experiences 時也未排除撤回故事。FeatureStore 的重驗不保護此直接輸入路徑，記憶開關關閉時仍可呼叫。
- **重現**：已確認經歷＋人物事實 → POST story availability=false → POST simulation 引用該 fact。探針取得 **HTTP 200、替身 Provider 1 次呼叫**，而非拒絕。沒有真 Gemini 呼叫或付費。
- **影響**：使用者撤回派生來源後，其摘要／事實來源仍可能送至外部模型；不表示原經歷應永久刪除。這不是跨 Owner 洩漏，但違反既有來源撤回用途邊界。
- **最小修復**：統一模型可用來源查詢，排除不可用／撤回來源並在派送前重驗；不足來源拒絕呼叫。若該入口不屬本次發布範圍，可先後端明確封鎖並測試，不擴充劇場功能。
- **測試**：重跑 `test_simulation_does_not_send_withdrawn_story`；增加撤回最後一筆／部分來源、撤回事實、撤回與派送競態、另一 Owner、無記憶與記憶啟用兩路徑。
- **阻擋**：Merge／候選 GCP E2E／Alpha **YES**，修正或證明後端不可到達後才解除；不是要求建造新劇場。

### F2｜P1：生日／任職 API 可把另一人物的故事當成自己的原文證據（PR 新增）

- **位置**：[person_details.py](../../../app/person_details.py#L24) 24–37，及 45–51、66–81；參考 people.py 123–133 的既有人物關聯驗證。
- **原因**：`_details_source(c,owner,source)` 未接收目標 pid，呼叫 `_source_experience` 時不傳 person_ids，只驗同 Owner／quote 子字串。公司／職稱與生日共用此方法。
- **重現**：建立人物甲、乙；故事只有甲參與，原文「人物甲說生日是四月十二日」。PATCH 乙 basic-details，指定該故事及生日引文，取得 **HTTP 200**，乙正式生日被建立。
- **影響**：不是跨帳號越權，而是把甲的來源錯掛乙，破壞人物證據可信度。Confirm 路徑有 linked 檢查，不代表獨立人物 API 也安全。
- **最小修復**：來源驗證帶目標 pid；只允許人工確認的參與／已配對提及，保持提及不計互動。manual 且無經歷來源仍可依契約保存，不以姓名推斷關聯。
- **測試**：`test_unrelated_person_source_rejected`；生日／新增任職／更正任職、僅提及、無關人物／另一 Owner、交易無 History 殘留。
- **阻擋**：Merge／GCP E2E／Alpha **YES**。

### F3｜P1：媒體 AI 不受設定的單帳號／全域每日呼叫次數限制（繼承 main）

- **位置**：[ai_runtime.py](../../../app/ai_runtime.py#L123) 123–134，尤其127；main.py 211–232 是 HTTP 可達路徑。
- **原因**：`operation=='media' or (...)` 直接跳過兩種 call quota，照片也適用，不只長音訊分段。仍保留每日／累計預算及 process concurrency，**不能稱無限費用漏洞**。
- **重現**：每日 owner/global 均設1、日預算大於兩次預留，連續兩次 media；第二次仍成功，未拋 ai_quota_reached。只使用合成 Provider。
- **影響**：公開 Alpha 的設定次數上限不適用媒體，一個帳號可能耗盡共享日預算，使其他人無法正常測試。
- **最小修復**：對媒體設明確有界的帳號／全域額度；若長音訊需按工作而非片段計次，分開記錄工作次數與各片段成本預留，不能把所有 media 豁免。不得僅縮短錄音來避開問題。
- **測試**：`test_media_respects_owner_and_global_call_quota`；照片／音訊分段、跨帳號公平性、並發、取消、失敗保留費用及冪等。
- **阻擋**：本輪明確要求所有帳號配額受控，Merge／GCP E2E／Alpha **YES**，或取得明確分段配額契約並實作對等保護。

### F4｜P2：生日／任職回讀的來源有效標記不隨故事撤回變化（PR 新增）

- **位置**：[person_details.py](../../../app/person_details.py#L94) 94–100；connections.py 160；app/static/person_details.js 10–15。
- **原因**：詳情 API 直接回傳存入時的 `source_status=active`，未合併目前故事可用性；故事撤回只改 experience_stories，不更新／投影此有效狀態。
- **重現**：以本人故事建立生日 → 撤回故事 → GET details；生日仍 `source_status=active`。探針 FAIL；沒有證明此生日已被模型使用，勿與 F1 混稱。
- **影響**：UI／後續消費者可能把失效來源當有效。歷史值應保留，不能為修標記改寫已確認歷史。
- **最小修復**：定義用途有效狀態與歷史保存狀態，讀取時投影有效性或以同交易失效；恢復來源規則明確、不可無條件復活人工撤回值。
- **測試**：`test_withdrawn_story_invalidates_basic_source`；任職同路徑、部分／恢復來源、History append-only、跨 Owner。
- **阻擋**：Gate B 完整來源失效驗收與 Alpha **YES**；Merge／完整 E2E Ready 亦維持 NO。可與 F1 分開修復，不重做 UX。

### F5｜P2：四維人物事實正式來源未持久保存完整輸入來源契約（靜態證據）

- **位置**：[draft_review.py](../../../app/draft_review.py#L75) 75–77；[confirm_targets.py](../../../app/confirm_targets.py#L65) 約65–68；[people.py](../../../app/people.py#L229) 229–230、248–252。
- **證據／原因**：Draft／Targeted DTO 有 source_kind、quote、source_revision，但轉 PersonUpdateCandidate 後，正式 fact_sources INSERT 只有 fact_id、experience_id、evidence_type、revoked_at。生日／任職反而有獨立來源欄位。人工輸入管道不能從 evidence_type 可靠反推。
- **影響**：人物詳情正式 fact source 無法完整回讀「手動提供／原文擷取」及所核對版本、逐項引文；舊 draft 內保留 review 不等於正式 source DTO 完整。未宣稱原文或所有稽核內容被刪除。
- **最小修復**：先凍結最小 provenance 契約，決定正式來源欄位或不可變來源收據；保持原值、Owner、版本及歷史。資料模型調整須另行審查，不自行 Migration。
- **測試**：同一 fact 多次經歷、manual/raw 不同來源、回讀後重登、來源撤回、版本衝突及 PG roundtrip。目前無新增專用動態探針；此項是可直接查驗的投影缺口。
- **阻擋**：Gate B／完整人物補充發布 **YES**；可明確縮減未支援能力後另審，不得冒稱完整契約已閉環。

## 本輪實測（與舊收據分開）

環境：Python 隔離 venv；TestClient 新暫存 SQLite 合成 Owner；AI 測試全部注入 test-transport，無外部 AI。沒有設定 LIFEWORLD_TEST_BACKEND=postgresql，避免共用 pg_support 的 TRUNCATE。PG 僅執行下列無 app fixture 的 catalog 讀取。

| 項目 | 結果 | 證據 |
|---|---|---|
| Google exchange/world transition、DraftReview/basic、格式相容、early validation、多人 Confirm、生日任職、Owner boundary、AI usage/consent/memory race | **90 PASS／0 FAIL／0 SKIP** | [REGRESSION.log](evidence/REGRESSION.log) |
| quantity／experience validation／Soft Life Node | **36 PASS／0 FAIL／0 SKIP** | [NODE.log](evidence/NODE.log) |
| 本機 PG runtime 無 schema CREATE、History DELETE／UPDATE | **1 PASS**；只讀 catalog，不證明全部權限 | [PG_READ_ONLY.log](evidence/PG_READ_ONLY.log) |
| 額外來源／媒體配額探針 | **0 PASS／4 FAIL／0 SKIP**；四個已重現缺陷 | [PROBES.log](evidence/PROBES.log)、[程式](evidence/test_probes.py) |

重現指令（repo root，使用已存在隔離環境）：

```sh
PYTHONPATH=.:tests:tests/ai /private/tmp/lw-integration-venv/bin/python -m pytest docs/integration/2026-11-12_AI_CODE_REVIEW/evidence/test_probes.py -q --tb=short
PYTHONPATH=.:tests:tests/ai /private/tmp/lw-integration-venv/bin/python -m pytest tests/product/test_google_exchange.py tests/product/test_google_world_transition.py tests/test_draft_basic_review.py tests/test_draft_review.py tests/test_draft_format_compatibility.py tests/test_early_validation_defense.py tests/test_integration_confirm_targets.py tests/test_person_basic_api.py tests/test_owner_boundary_matrix.py tests/ai/test_usage_isolation.py tests/ai/test_draft_ai_consent.py tests/ai/test_memory_snapshot_races.py -q --tb=short
/private/tmp/lw-integration-node/node-v24.11.0-darwin-arm64/bin/node --test tests/frontend_quantity.cjs tests/frontend_experience_validation.cjs tests/frontend_softlife.cjs
LIFEWORLD_INTEGRATION_PG_CONFIG=/private/tmp/lw-integration-pg18-config.json PYTHONPATH=.:tests /private/tmp/lw-integration-venv/bin/python -m pytest tests/test_pg_integration_person_details.py::test_runtime_cannot_change_schema_or_delete_history -q --tb=short
```

首次探針誤用 PUT 得405，已修正**審查探針**為正式 PATCH 後重跑，405不列產品缺陷。首次 Node 路徑寫錯，已使用存在的 Node 重跑；上述只列最終有效結果。產品檔案完全未修改。

## 實際閱讀範圍與未覆蓋

- A：external_auth.py、google_identity.py、service.py session/login/confirm；existing Google tests。本輪驗證 nonce／challenge/session／owner 分支，未發現新的已證實跨 Owner 漏洞；不保證不存在。
- B：service.py create/edit/confirm、confirm_targets.py、draft_review.py、person_details.py、schemas.py 對應 DTO、people.py facts/source；實讀交易與版本／去重方法。Confirm 同一連線寫入人物／經歷／來源／任務／帳本，測試涵蓋 late conflict rollback，不把 UI 成功當資料提交成功。
- C：experience_basic.js、experience_quantity.js、experience_validation.js、draft_ai.js；生日真日期／未知年2月29日、任職／數量／目標時區／API error 文案。既有三尺寸畫面／錄影為前輪收據；**本輪 Chromium 320/390/1440 完整操作 NOT RUN**，Gate A 不因此被撤銷。
- D：ai_runtime.py、ai_routes.py、ai_draft_consent.py、relationship_memory.py、media.py、main.py suggest/media 路徑；來源 publish 前有重驗，但不代表所有 Provider 路徑均受保護（F1）。Owner usage SQL 有 owner filter、無公開 admin global endpoint，配額失敗／未知費用保留 reservation。
- E：SQLite 010/011、PG 011 review SQL／最小權限 review SQL、postgres.py 交易隔離、guest_lifecycle.py／guest_maintenance.py、既有 Schema Diff與備份方案。沒有執行 SQL 審查稿。
- F：deploy/release.py runtime_config/api_overrides/source_is_current/traffic 函式、既有 Trigger path inventory及本輪唯讀即時 Trigger／lw-public 流量。
- **NOT RUN**：完整 SQLite 全套、完整 PG18 suite／本輪 PG 寫入與並發、真 Google OAuth／Gemini／Safari／Android、實際 ffmpeg 長錄音、GCP E2E、備份匯出／隔離還原、映像建置與掃描。90 PASS並非全專案全綠。

## 非程式缺陷：發布操作與缺少證據

| Gate B/C 項目 | 已知狀態／限制 | 解阻方式 |
|---|---|---|
| Alpha／E2E Schema | Owner 2026-11-11 快照：兩庫010結構相同，42表326欄81FK2 sequences；Owner/ACL/migration lineage不同；本輪未重取兩庫新快照 | 正式操作前再取只讀指紋，不把歷史快照當即時；不重跑已有006/007/008/010 |
| 011與Runtime | 四張011及最小權限是候選；來源庫快照無011，draft DELETE／consent revoked_at UPDATE有缺口；Alpha migrator無CONNECT | 審核011與精確角色／權限後分項核准；不能直接部署依賴011的功能 |
| GuestPurger | guest_maintenance.py:31只允許Beta維護身分；GuestPurger嚴格表/FK清單不含新010/011，安全停止 | Alpha purge尚未啟用，非資料已被刪。不要移除防護；先審FK/獨立維護帳號或明確保持停用／不宣稱清除閉環 |
| DraftReview rollback | 新碼拒絕未知 envelope，測試PASS；更舊Runtime不能讀v2／生日任職 | 固定相容rollback映像Digest＋混版本演練；不能將8f377fa自動當新資料格式可回退版本 |
| Hidden AI | 預設env false；PG Feature Store兩表及完整背景工作尚未就緒，SQLite規則型context不是真Gemini標籤 | 保持停用、不自動加入Migration；正式能力另審，Gold labels不得冒稱模型輸出 |
| 備份還原 | 先前唯讀收據顯示CloudSQLbackup/PITR未啟用、backup list空；存在舊post005私有export，非現行010/011完整還原證據。本輪未重新查此設定 | 依既有 CLOUD_SQL_BACKUP_RESTORE_PLAN 分別核准export／metadata／隔離restore並實測；不要說完全沒有備份 |
| 固定映像／GCP E2E | 此Head尚無本輪固定Build/Image Digest及真Provider收據 | 先解缺陷／Code Review與Schema／備份阻擋，再申請受控Build/E2E，不能寫假Digest |

## 發布入口唯讀驗證

本輪重新讀取 [TRIGGER_LIVE.json](evidence/TRIGGER_LIVE.json)：lw-api-main、ID 6ffa2066-8edd-4406-9f3f-31f967da57dc、repository正確、^main$、approvalRequired=true；PR app/tests命中includedFiles。Merge會產生待核准Build，不能稱完全不觸發。未核准／拒絕／取消任何Build。

本輪 [PUBLIC_TRAFFIC_LIVE.json](evidence/PUBLIC_TRAFFIC_LIVE.json)：lw-public 100%仍由 lw-public-camera-8f377fa承接。此查詢不含env或Secrets，未宣稱本輪再驗所有服務Digest或所有部署事件。lw-web-main未命中本候選、無GitHub Actions是前輪inventory證據，Merge前仍須重算精確Diff／filters。release.py的既有api_overrides只接受 life_world_dev，不可把自動main發布器直接當E2E/Alpha發布工具；隔離DB／SA／Secret refs及固定Digest要另行審查。

## 待確認，不列已證實缺陷

1. DraftAIConsent require 在route檢查後到reserve／Provider派送仍有時窗；撤回與「已送出」的線性化界線需要定義／可控制競態測試。本輪未證明未授權真外呼，不當成已證實漏洞。
2. FeatureStore publish重驗通過後仍到Provider存在時窗；現有race tests只證明publish前防護。停用／撤回發生在何一階段應阻擋須明確，不用既有PASS宣稱全部競態已解。
3. 正式環境是否已有獨立未記錄變更的011／ACL，沒有新快照不得猜測。

## Owner 決策摘要與建議順序

- **必修／阻擋**：F1撤回資料外傳路徑、F2人物來源錯掛、F3媒體配額豁免；F4有效狀態及F5正式provenance契約納入Gate B。先最小修復／封鎖未核准入口，新增對應回歸；不新增劇場、背景推論或UX重做。
- **可延期**：Jerry進階劇場、人物作品／角色創作、完整用量圖表等不在本輪範圍；保持既有未開能力關閉，不列為未來必做。
- **需人工授權**：任何正式Migration／GRANT、CloudSQL export／隔離restore、Build／固定映像部署／真Provider費用、Merge／Alpha切流均另批。現在不要求Owner執行SQL。
- Gate A **UX APPROVED（a2eb363）**；Gate B **BLOCKED**；Gate C **NOT RUN**；Gate D **NO-GO**。
- AI-assisted review **Changes Requested**；獨立人工 Code Review **尚未通過／不能以Owner本人或本AI自審替代**。

完成本機報告後停止。沒有改產品程式／正式資料或任何雲端設定，沒有Commit／Push。本報告是未提交審查產物，不代表PR已更新。
