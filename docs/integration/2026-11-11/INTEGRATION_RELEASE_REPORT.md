# PR #26 Integration QA／Release Gate｜NO-GO

2026-11-12。分支`integration/pr24-first-unified-schema010-20261111`，[Draft PR #26](https://github.com/asixtw/life-world/pull/26)。本輪基準`6d4ba0a3ea3d895678ad733cde2c42f773154f4f`，精確交付Head/Tree見PR收據。遠端main唯讀核對仍`68102f230aa947a434286ba9260e1ae75f6634b0`。沒有Merge、Build、Deploy、正式Migration/GRANT、IAM/Secret、Alpha匯入或切流。

**人物基本資料閉環已完成本機驗證，停止功能擴充，轉QA。** 不表示Owner UX Approved或GCP可發布。Jerry進階劇場、人物作品、AI角色演出、完整角色創作未核准，不列R+1或必做未來功能；既有相容表/API不得因此擴充、刪除資料或執行非必要Migration。私人筆記、現實情境準備、Lumi互動與此類角色劇場分開。

## 1. 本輪變更與操作入口

- 新增`app/static/experience_basic.js`；修改`experience_supplements.js`、`experience.js`、`app.js`、`index.html`。沿用四步、逐人收合補充與原生Bottom Sheet，不換框架/設計系統。
- 第三步支援生日（月日成對、年份選填）、公司/職稱/狀態/任職起訖、新增或明確更正既有任職；不預設來源或互動。其他類別的未保存輸入不默默捨棄。新人物用client_ref、既有人物用ID，不依同名合併。
- 第四步逐人顯示原值→本次值、來源與證據、採用/排除、來源/版本重核對。查看/勾選不寫DB；最後Confirm才共同保存人物、基本資料/歷史、經歷、任務、目標、獎勵。無效/未完成日期可留草稿，不可採用；不把未知年轉成假年份或年齡。
- 新增`browser_tests/test_draft_basic_ui.py`、`pg_integration_server.py`；更新四維補充測試的明確來源選擇。沒有新增產品表、Migration或正式權限。
- 可操作候選：本機服務`http://127.0.0.1:8196/`，連**本機marker PG18、lw_e2e_app**，不是GCP/正式入口。可建立合成Guest世界及本機測試帳號；Google/Gemini未啟用，不輸入真實第三人資料。重啟命令見下節，憑證只從既有私密設定讀入，不放Repo。

## 2. 實測與證據

結果分開列出，不能加總成一套或用舊結果冒稱本輪重跑。

| 範圍 | 結果 | 證據 |
|---|---|---|
| UI→API→受限本機PG18，含四步/人物/草稿/用量/Owner/互動/進度/獎勵 | **79 PASS**，126.18秒 | [BASIC_CLOSURE_PG_BROWSER.log](evidence/BASIC_CLOSURE_PG_BROWSER.log) |
| 核心基本資料閉環，補強SQL回滾時點收據後重跑 | **15 PASS**，16.61秒；不與79相加 | [BASIC_CLOSURE_CORE_FINAL.log](evidence/BASIC_CLOSURE_CORE_FINAL.log) |
| 完整SQLite API/Node日期/習慣/前端契約 | **754 PASS、85 SKIP**，39.09秒；專用PG案例在此跳過 | [FULL_LOCAL_SUITE.log](evidence/FULL_LOCAL_SUITE.log) |
| 受限本機PG API/交易/權限（前一後端階段；本輪未改後端） | **51 PASS** | [WORKFLOW_PG18.log](evidence/WORKFLOW_PG18.log) |
| PostgreSQL直接讀回 | `life_world_e2e`／PG18／`lw_e2e_app`，依合成Owner過濾 | [BASIC_UI_PG_READBACK.json](evidence/BASIC_UI_PG_READBACK.json) |
| 本輪GCP、真Google、真Gemini、實機Safari/Android | **NOT RUN** | 不用本機/替身代替 |
| 當前閉環已知FAIL | 0；設計與發布未核准 | 初始缺選項/來源預設紅燈保留於BASIC_UI_RED.log、BASIC_SOURCE_CHOICE_RED.log |

### 必測十項

| 情境 | 本機PG結果／核對方式 |
|---|---|
| 1 無人物日記 | PASS；普通紀錄不進交會待核對，不建立人物 |
| 2 新增兩位人物 | PASS；同一次Confirm建立，client_ref獨立；草稿期不建人 |
| 3 分別公司/職稱/生日 | PASS；320/390/1440均真UI輸入並讀回不同資料 |
| 4 多筆任職歷史 | PASS；同人保留現職及過去任職，各有歷史；更正只改指定任職並留歷史 |
| 5 生日只有月日 | PASS；4/12、未知年2/29，year保持NULL；2/31、年單獨、日單獨不能採用 |
| 6 返回改原文 | PASS；raw候選撤銷採用並重核對；獨立manual生日保留；摘要仍需核對 |
| 7 草稿/重整/重登 | PASS；實際UI登出/登入恢復同Owner與候選；本機未加入輸入另有恢復測試 |
| 8 部分採用/排除 | PASS；排除組織不產生任職/歷史；多人物不互相套用 |
| 9 失敗/重試/衝突 | PASS；503、注入傳輸逾時/回應遺失及同payload重送；晚期任職衝突整筆回滾，再排除安全確認 |
| 10 開人物卡回讀 | PASS；真UI開詳情、API及SQL查基本資料/來源/歷史；互動者1次、提及者0次，獎勵一次 |

SQL收據`late_conflict_before_retry`證明失敗時experiences/reward_ledger均0、沒有待建人物/生日殘留；成功重試後才各1。兩位新人物案例每Owner為3人物（含seed既有1）、2生日、3任職/3任職歷史、1經歷/1獎勵。故障為明示測試注入，不是假稱GCP實際故障。

### 重現

```sh
# 只接受已驗localhost/專用port/cluster/database marker，啟動不DDL/GRANT/清資料。
LIFEWORLD_INTEGRATION_PG_CONFIG=/private/tmp/lw-integration-pg18-config.json \
LIFEWORLD_DATA_DIR=/private/tmp/lw-basic-pg-browser PYTHONPATH=. \
python -m uvicorn browser_tests.pg_integration_server:app --host 127.0.0.1 --port 8196

# 使用同一個明確本機設定執行；不要同時跑會TRUNCATE fixture的PG API suite。
LIFEWORLD_INTEGRATION_PG_CONFIG=/private/tmp/lw-integration-pg18-config.json \
LIFEWORLD_TEST_URL=http://127.0.0.1:8196 python -m pytest \
browser_tests/test_draft_basic_ui.py browser_tests/test_experience_people_picker.py \
browser_tests/test_draft_review.py browser_tests/test_integration_person_details.py \
browser_tests/test_ai_usage_personal.py browser_tests/test_experience_four_steps.py -q --tb=short
```

Python環境`/private/tmp/lw-integration-venv`，Node v24.11.0；本機PG18.0結構副本不是Cloud SQL18.6或備份還原證明。私密設定不得貼出。完整API/Node測試：`LIFEWORLD_NODE=/private/tmp/lw-integration-node/node-v24.11.0-darwin-arm64/bin/node python -m pytest tests -q`。

## 3. UX審查證據

沿用[三尺寸完整四步](screenshots/four-step-regression/README.md)的Step1/2；本輪只補必要Step3/4：

- [320人物卡](screenshots/320-basic-step3.png)、[390人物卡](screenshots/390-basic-step3.png)、[1440人物卡](screenshots/1440-basic-step3.png)。
- [320變更預覽](screenshots/320-basic-preview-2.png)、[390變更預覽](screenshots/390-basic-preview-2.png)、[1440變更預覽](screenshots/1440-basic-preview-2.png)。同尺寸preview-1是另一位待建立人物，資料不互套。
- 原文、素材、四維資訊、AI手動預設、草稿刪除及Google同Owner局部升級未另做第二套流程。畫面模擬手機寬度，不是實機驗收。功能PASS不等於UX Approved。

## 4. Release Gate／剩餘風險

| Gate | 狀態 | 尚需完成 |
|---|---|---|
| A 整體UX | **待Owner核准** | 審核可操作候選與三尺寸畫面；不得自行Approved |
| B Schema/安全/相容 | **未通過** | 010/011實體/最小權限審查；Feature Store來源失效與授權；DraftReview相容reader及混合Revision/回退；GuestPurger新增FK；備份/還原 |
| C 固定SHA/Digest GCP E2E | **NOT RUN** | B審查後依獨立批准套用必要E2E 011/權限，固定映像與合成Owner受控驗收；真Google/Gemini另附實際收據 |
| D Main/Alpha發布 | **NO-GO** | UX、Code Review、必要GCP E2E、P0、安全備份/回復、main自動發布影響及Owner明確授權缺一不可 |

- 2026-11-11 Owner快照：E2E/Alpha結構相同，42表/326表欄/2序列/81FK；結構SHA256`0e3d04411e843b509e120d9e4dd073f304c03f39317cc57958b4c6b78a0f2e8e`。Owner/ACL/遷移收據不同，不重跑010；這不是2026-11-12即時DB讀回。詳[Schema Diff](SCHEMA_DIFF_REVIEW.md)。
- 兩GCP快照均無011四表、PG Feature Store兩表；Runtime缺drafts DELETE與data_consents.revoked_at UPDATE。僅有審查SQL，不自行GRANT。lw_migrator無CONNECT，不能假稱可執行Migration。
- 新生日/任職候選對舊extra=forbid讀取器不完全可逆；舊Alpha/0eee0a3不能直接當無損回退。需相容reader、固定資料契約與演練，不以刪除候選回復。新workflow_existing_people的未保存本機格式亦需相容reader/匯出策略。詳[DraftReview](DRAFT_REVIEW_CONTRACT.md)。
- 四維source_kind目前保存在DraftReview，fact_sources對外DTO尚未完整投影；不能把傳統evidence_type當來源管道。生日/任職有獨立來源欄位與撤回API，不等於Feature Store衍生失效已完成。
- Feature Store目前為有限SQLite規則/讀取時重建，非真Gemini背景自動標籤；PG缺表。撤回來源篩選、提及不變互動、用途同意/版本傳播尚需審查，不開啟背景功能。Gold Labels不是模型成果或訓練完成。
- 2026-11-12 QA：已移除未核准的`PUT /api/persons/{id}/profile`路由註冊，OpenAPI不公開，HTTP回404且不新增notes/requests。origin/main原無此入口；保留領域方法及既有歷史資料讀取，不涉及DB變更。原版本/封存/Owner隔離測試改為明確的領域相容性測試，不能當公開寫入功能已驗收。
- GuestPurger維持Beta專用/安全失敗；新增010/011 FK未完成清除白名單審查，不開Alpha刪除排程。既有正式資料不刪。
- Alpha仍舊Runtime/額度；新AI有限配置、本人用量隔離/可撤回同意未發布。費用、歷史未知預留及停止程序見[AI政策](ai/AI_BUDGET_POLICY.md)，不將預留當帳單。
- Cloud基線lw-public為camera-8f377fa／既有Digest，未更動；main Trigger核准保護屬先前唯讀證據，Gate D前須重新核對所有自動發布入口，不能拿舊讀回保證新Merge安全。

## 5. Owner待辦與範圍凍結

現在只需Owner審核UX與安排PR Code Review，**不要求立即執行SQL**。Gate B審查後才提出精確E2E Migration/最小權限/備份操作供獨立批准；Alpha、main Merge、Cloud Build及發布尚未授權。真Google需本人於受控候選驗證，但本輪未建立GCP候選，勿先宣稱通過。

後續限QA、驗收阻擋Bug/權限/一致性/必要相容性。Jerry未核准功能不變成下一版承諾。v1.1擬真資料與Hidden標籤只做資料契約/工程缺口盤點，不啟用背景AI或匯入正式資料。

資料契約／Hidden AI盤點已收於[v1.1稽核](../2026-11-12_DATA_CONTRACT_AUDIT/README.md)：010/011欄位與FK比對無差異，但模板未完成、S07獎勵預期衝突及背景來源/授權/版本缺口未解除。Gold與實際AI明確分離；本輪無正式匯入或模型呼叫。

## 6. 未核准角色設定入口隔離（QA）

新增2項紅燈測試先證實原入口回200／仍在OpenAPI，移除註冊後通過。本人`/api/profile`與基本人物編輯保留。完整本機SQLite／Node套件 **766 PASS、85 SKIP**（31.73秒）；85項專用PostgreSQL環境測試未在此命令執行，不能宣稱PG全綠。此修改未重跑瀏覽器或GCP，均NOT RUN；前述人物閉環PG證據屬前一功能版本。命令同第2節完整套件，收據[ROLE_PROFILE_BOUNDARY_TESTS.log](ROLE_PROFILE_BOUNDARY_TESTS.log)。

僅關閉新整合帶入的未核准HTTP寫入入口；歷史notes、requests、GET資料、DTO與領域相容方法皆保留。回復應用程式提交會重新開放入口，故不將回復此提交作為核准發布策略。維持Draft／NO-GO。
