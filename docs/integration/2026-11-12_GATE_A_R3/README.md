# PR #26｜Gate A R3 人工意見修正

Gate A：**Changes Requested，待 Owner 親自重審**。沿用四步，不新增資料欄位或正式環境變更。

## 修正前後

| 項目 | 4bc2790 | R3 |
|---|---|---|
| 影像取得 | 圖片／截圖／拍照／名片並列 | 拍照／選取照片；選取後展開「照片用途」指定名片。用途變更保留素材與文字，撤銷先前文字核對，須重新確認 |
| 活動數量 | 所有單位 step=0.000001 | 次等計數預設1、小時0.25、分鐘/公尺1、公里等0.1；非對齊部分完成允許直接輸入，原精度保留 |
| 人物搜尋 | 缺乏區隔的文字按鈕 | 姓名、角色/共同場合、同名識別、選取標記與無結果狀態，分列呈現；不預選互動角色 |
| 補充資訊 | 候選／待核對混用 | 尚未加入資訊 → 已加入N項資訊 → 有N項資訊待你確認 → 已確認並保存；未加入訊息指出人物及資訊類別 |

[前版畫面](../2026-11-12_GATE_A_R2_INTEGRATION/index.html)保留原貌；[本輪實際產品畫面](index.html)。內部DTO的candidate_ref、版本、來源Hash與selected/excluded仍沿用，不因文案修改而改變契約。

## 活動精度決策

需求與Decimal契約允許各單位正小數、最多六位；沒有「次只能整數」的欄位。本輪只調整操作建議。0.5次、1.25小時、2.75公里仍可輸入；既有0.000001不截斷。加減使用十進位定點整數，避免浮點誤差。空白/0仍不累計；數量上限、Confirm、去重、目標進度及獎勵不變。未知自訂單位採0.1作按鈕間距，仍可直接填不同精度。

## Owner 操作

入口維持 http://127.0.0.1:8198/ 。先保存舊頁草稿，再重新整理載入最新前端。以既有本機測試帳密「登入我的世界」，進入 `/#record`。帳號、密碼與Cookie不寫入交付檔。

第一步影像可拍照或選照片；第二步選目標並填0.5等實際量；第三步搜尋既有人物或新增人物，逐人展開補充、指定來源及得知依據、按「加入資訊」；第四步逐人採用/排除，最後確認才保存。保持同一Owner，生日與任職功能沿用。未加入輸入仍阻擋離開保存，並指出所屬人物/類別，不會默默丟棄。

僅隔離本機PG18.0結構副本，受限Runtime與正常Session/CSRF；不連GCP Alpha/E2E。Google、實機相機/Safari、真Gemini/媒體Provider為NOT RUN。媒體自動化使用合成圖片/明示Provider替身，不宣稱實機或辨識模型驗收。

正式Schema、Migration、GRANT、Merge、Build、Deploy及流量皆未變更。Gate A未核准，Gate B/C/D未放行。

## 固定版本與本輪收據

工作區 `/private/tmp/lw-integration-20261111`，分支 `integration/pr24-first-unified-schema010-20261111`。產品Commit `a0bd5985d50881d0123db358e6ec2b88a5a940fb`，App tree `aeb87103599e2a92c3781a2d4da8a7b30ecb54e4`。後續交付Commit只新增文件/證據。

| 收據 | 實際結果 | 範圍 |
|---|---|---|
| API_NODE.log | 772 PASS／87 SKIP，39.31秒 | SQLite API與Node；87項專用PG環境未配置，不能當全綠 |
| UI_API_PG.log | 98 PASS，144.88秒 | R3／四步／生日任職／草稿／媒體／Owner／確認與獎勵 |
| CAPTURE.log | 12 PASS，54.80秒 | 三尺寸R3與完整四步錄影/回讀，多數與98重疊 |
| PG_SQL_READBACK.log | 15 PASS，20.11秒 | 受限lw_e2e_app直接SELECT驗證；與98重疊，JSON收據另附 |
| AI_CONSENT.log | 9 PASS，6.82秒 | 真本機授權/收據API＋明示Provider替身，非真Gemini |
| OWNER_ENTRY_CHECK.json | PASS | 原8198、原帳號正常UI登入、同Owner、業務資料不變、0 JS例外；額外CSRF探測不算通過 |

上述不加總為獨立案例。39張截圖＋3段錄影，涵蓋四步、兩種照片入口、搜尋同名人物、未加入狀態、生日/任職/四維採用排除與正式Confirm後回讀。人工抽查320/390/1440畫面及溢出斷言，不等於Owner設計核准。中間失敗與修正見INTERMEDIATE_FAILURES.md。

重現：`LIFEWORLD_TEST_URL=http://127.0.0.1:8199 python -m pytest browser_tests/test_gate_a_r3.py browser_tests/test_draft_basic_ui.py browser_tests/test_draft_review.py browser_tests/test_experience_four_steps.py browser_tests/test_moment_integration.py browser_tests/test_integration_person_details.py browser_tests/test_media_flow.py -q`。直接SQL收據需既有私密本機設定路徑`LIFEWORLD_INTEGRATION_PG_CONFIG`，不得貼設定內容；不執行bootstrap/DDL/TRUNCATE。

## 下一階段GCP發布審查清單（唯讀準備，未執行雲端操作）

| 檢查 | 最新可用證據／缺口 | 放行前條件 |
|---|---|---|
| PR26 Code Review／安全 | 本輪GitHub唯讀查詢仍Open+Draft、reviews=0、review threads=0；不代表Code Review通過 | 固定候選SHA，審查Owner/Session/CSRF、來源/版本/重送/失敗回滾，P0清零 |
| Alpha/E2E Schema差異 | 2026-11-11 Owner快照兩庫同結構：42表、326欄、81FK；非今日即時快照，ACL/Owner/Migration收據不同 | 以READ_ONLY_SCHEMA_SNAPSHOT.sql重取或確認快照時效後Diff；禁止假設已套用011 |
| Schema011／最小權限 | 生日/任職4表候選；本機46表90FK。正式兩庫缺011，drafts DELETE/data_consents.revoked_at UPDATE仍缺權限；lw_migrator無CONNECT | 審查既有011草案及Runtime逐表/逐欄最小DML、獨立Migration身分、前後驗證與回復，E2E與Alpha分別核准 |
| GuestPurger | 本機90FK vs核准61FK，額外29組（010增量20＋0119）；verify_graph安全停止 | 審清除依賴次序、跨Owner FK、14天/升級/重試及最小維護帳號；不直接放寬白名單，不開正式排程 |
| DraftReview／回復 | 新生日/任職與v2 envelope，舊extra=forbid讀取器不能無損回退 | 完成相容reader、舊/新草稿及混合Revision回歸；保留資料，禁止靠刪候選退版；演練固定前一可用兼容Revision |
| AI授權／Feature Store | PG Feature Store缺表；來源版本/撤回傳播、用途授權與跨Owner仍有Gate B缺口 | 不啟用未核准背景能力；審查本人用量、有限預算/未知費用保留/停用程序；真Gemini另測 |
| Cloud SQL備份/還原 | 已有Metadata與結構快照不是完整還原成功證據 | 核對近期備份/匯出、PITR、Owner/ACL/角色/Sequence/Migration來源收據；隔離還原演練及資料/權限驗證，另行授權 |
| GCP E2E固定映像 | NOT RUN；本輪只有本機PG，無新Image Digest | Gate A/B通過並獨立批准Build/部署/E2E Migration後固定Commit→Build ID→Digest→Revision，受控測Google/Gemini/照片/長音訊/Owner/Confirm/回復；不切Alpha |
| main Build/Deploy | 依2026-11-11 Trigger收據及本候選路徑分析：lw-api-main命中97路徑、舊收據approvalRequired=true；lw-web-main命中0。現分支無.github/workflows；release.py只組lw-api-main/lw-web-main | Merge前重新唯讀核對Trigger、分支/paths/核准、活動Build與三服務Revision/Digest/流量；API保護有效且無其他入口才准入。舊證據不是即時雲端保證 |

詳證沿用../2026-11-11/SCHEMA_DIFF_REVIEW.md、DRAFT_REVIEW_CONTRACT.md、migrations/011_person_basic_details.review.sql、evidence/GUEST_PURGER_FK_AUDIT.json、ai/AI_BUDGET_POLICY.md；本輪路徑分析見TRIGGER_PATH_REVIEW.json，未修改任何Trigger。lw-public是否仍現役8f377fa須發布前即時讀回，本輪不以未查詢狀態冒稱已驗證。

## 停工點／Owner核准事項

四項R3開發已結束，停止新增UX/產品功能。**整體NO-GO**：Gate A等待Owner操作8198及畫廊後核准；Gate B安全/Schema/回復未通過；Gate C GCP NOT RUN；Gate D無授權。現階段Owner只需UX審查及安排Code Review，不要求立即執行SQL。之後Migration、GRANT、Build、Deploy、Merge、Alpha切流及資料匯入必須逐項另外核准。

剩餘差異：手機相機/HEIC與Safari實機、真Google升級聯合驗收、真AI/媒體Provider未測；AI仍沿既有第四步授權/整理，不移植Demo即時假輸出。未知自訂單位間距只屬操作建議，部分完成資料契約不變。正式Alpha維持舊Runtime，本輪本機前端與額度未發布。
