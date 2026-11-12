# PR #26｜最小安全修復與提交審查

**最新狀態：Owner已核准A/B/C提交；當次獨立測試、實際Commit及F5剩餘阻擋見[提交收據](SUBMISSION_RECORD.md)。下文未提交描述為提交核准前的歷史記錄。**

**F1 後續（2026-11-12）：Jerry 決定開放人物 AI 模擬、不再阻擋；F1 的 HTTP 與 Runtime 兩道封鎖已移除並救回原本的模擬流程，見 [EVOLUTION](../../EVOLUTION.md) 的「main 發布測試 Step 3 修正」。下文 F1 的描述保留為歷史紀錄。**

2026-11-12。基準 **f3f4c9f5a9a0833d5966e427d9c9a33c85b45731**，原整合分支／工作目錄不變。全部為**未提交本機修改**，無新Commit SHA，未Push。原Gate A核准不自行撤銷；Gate B仍BLOCKED、GCP E2E NOT RUN、Merge/Alpha NO-GO。

## 分批結果與設計決策

| 項目 | 修改／實證 | 狀態 |
|---|---|---|
| F1 | 未核准人物AI角色演出，HTTP及Runtime雙層封鎖simulation，422 simulation_not_released；不讀來源、不預留費用／外呼。私人筆記與歷史不刪 | 本機修復／測試PASS |
| F2 | _details_source帶明確person_id；生日／任職新增與更正驗證同Owner的合法人物參與或人工配對提及；來源拒絕不留目前值／History | SQLite及本機PG PASS |
| F3 | media不再豁免次數；一次照片／整份音訊為一工作，分段各扣成本；全域DB advisory lock，工作與片段去重，素材指紋綁實際bytes | SQLite及本機PG PASS |
| F4 | GET details投影來源目前可用性；新增recorded_source_status、source_available，不改原值／revision／History；故事恢復不能復活人工撤回值 | SQLite及本機PG PASS |
| F5 | [正式來源契約審查稿](FACT_PROVENANCE_CONTRACT.review.md)，不改表、不用notes/requests偷放第二套來源模型；獨立驗證草稿持久化與正式缺口 | 草稿PASS；正式模型/回讀**待核准、未實作** |

第一批先完成F1–F3核對：64 PASS、1 deselected；唯一排除的是明確留待第二批的F4紅燈，不是刪除失敗測試。之後完成F4並重跑原四探針4 PASS。F5正式來源缺口保留strict XFAIL，未宣稱所有問題已閉環。

## 媒體工作／成本契約

- 沿用現有 `LIFEWORLD_AI_OWNER_DAILY_CALLS`、`LIFEWORLD_AI_GLOBAL_DAILY_CALLS` 作滾動24h **工作數**上限（一般AI一次一工作；照片一次一工作；長音訊整份一工作）。日／累計預算、AI總開關、每process並發、音訊既有有界工作逾時仍有效，未改任何Alpha環境值。
- 以既有requests收據 `ai_media_work_v1`記工作ID／建立時間／fingerprint；不另建表。每片段仍在 `ai_attempt_v1` 寫最壞預留額及父work_id，失敗／未知費用不返還預留。不保存原始媒體或模型輸出全文。
- 兩類收據在相同DB全域鎖下判定；不能靠拆segment豁免預算。歷史無parent的media attempt保守各算一工作，不回填或刪除舊收據。舊Runtime**不認得新父工作計次**，混用期間可能誤計／少計新父工作；發布前需固定相容映像並禁止未驗證混用，不能自稱舊版可安全Rollback。
- 前端每次明確點辨識建立一個Idempotency-Key；相同key不重啟工作，同key改素材409。網路自動重送可沿用key；使用者再次明確點擊是新工作、會再用額度。新工作不是承諾無費用重試；伺服器不保存可重播的完整轉錄結果。
- 音訊在首段通過取消檢查後才啟動工作；尚未開始就取消不呼叫Provider。已開始後取消／失敗，已預留成本與工作收據保留，後續觀察到取消便停止片段派送。已送出Provider請求不能承諾被外部取消。
- 父工作handle只在伺服器流程內存在，HTTP不接受客戶端work_id授權；跨Owner handle拒絕。主圖片／音訊HTTP入口仍走Session/CSRF、原媒體檢查及Owner限制。
- 用量API的calls仍是本人**Provider嘗試／片段次數**、reserved仍是預留；不是把數字改成實際帳單，也不公開全域值。它不是「剩餘工作額度」介面。

## 修改檔案與差異

- `app/ai_routes.py`、`app/ai_runtime.py`：封鎖未核准模擬；共享工作配額／每段成本／去重。
- `app/audio_transcription.py`、`app/main.py`、`app/static/media.js`：整份音訊父工作、Idempotency-Key傳遞；未改四步排版或來源校對流程。
- `app/person_details.py`：目標人物來源驗證、唯讀有效狀態投影。
- `tests/ai/test_ai_runtime.py`：原「角色演出成功」測試改驗未核准能力必須拒絕、不讀／不外送；保留事實／筆記不變斷言，不是用skip避開安全測試。
- `tests/ai/test_total_budget.py`：舊media全面豁免斷言改成「一父工作／多段預留／新工作限流」；未降低成本限制。
- 新增 `tests/test_review_security_fixes.py`、`tests/ai/test_media_work_quota.py`、`tests/test_pg_review_security_fixes.py`、`tests/test_fact_provenance_contract.py`。
- [可審查完整產品／測試Diff](evidence/WORKTREE.patch)包含tracked修改及新增測試；[原AI審查](../2026-11-12_AI_CODE_REVIEW/AI_CODE_REVIEW_PR26.md)與紅燈探針保持原貌。四個原探針另有一致性hash紀錄，沒有改斷言。

## 本輪測試（不同套件有重疊，不相加成總測試數）

| 套件 | 最終結果 | 證據 |
|---|---|---|
| 原四個審查探針（原檔未改） | **4 PASS** | [ORIGINAL_PROBES_GREEN.log](evidence/ORIGINAL_PROBES_GREEN.log) |
| AI／Google／DraftReview／生日任職／目標日期／多人Confirm／Owner／媒體相關API | **152 PASS、15 SKIP、1 XFAIL** | [REGRESSION.log](evidence/REGRESSION.log) |
| 媒體工作／預算／媒體API專項 | **30 PASS** | [MEDIA_FINAL.log](evidence/MEDIA_FINAL.log) |
| Node 日期／數量／視覺／音訊生命週期 | **53 PASS** | [NODE.log](evidence/NODE.log) |
| 既有本機PG18受限Runtime | **5 PASS** | [PG.log](evidence/PG.log) |
| F5正式持久化強制執行已知缺口 | **1 FAIL（已知缺少source_kind）**；非環境錯誤 | [F5_KNOWN_GAP.log](evidence/F5_KNOWN_GAP.log) |

15 SKIP是專用PG fixture未啟用，因舊fixture會TRUNCATE／GRANT，沒有為湊綠燈動Owner本機資料；另寫無DDL／GRANT／TRUNCATE的PG驗證，只新增合成Owner與其資料。PG測試包含錯人來源整筆拒絕、原History不變、提及不計互動、撤回／恢復與人工撤回保護、DB advisory lock並發去重及各片段成本。沒有Cloud SQL寫入，也不是GCP E2E。

F5 strict XFAIL是正式欄位尚無核准模型的可重現阻擋；草稿重登持久化與跨Owner測試PASS。未將它算入成功數。詳細命令／關鍵修正檢查見 [VALIDATION.json](evidence/VALIDATION.json)。

NOT RUN：真Google／Gemini、實機Safari／Android、全套SQLite/PG、全四步三尺寸瀏覽器重跑、真ffmpeg長錄音、GCP E2E、Build／備份還原／Migration。合成Provider不冒稱真模型驗收。

## Gate A影響與剩餘風險

- 已核准四步資訊架構／視覺／生日任職漸進揭露**未修改**；不自動撤銷a2eb363核准。
- 需Owner小範圍再看：媒體429／重複送出409保留素材提示、人物詳情的「來源已撤回」顯示，以及四步之外既有模擬按鈕回422未開放狀態。這不授權重做畫面。舊模擬入口UI仍可能顯示按鈕，但後端已拒絕，不可因此宣稱能力已開放。
- 本輪沒有重啟Owner使用中的8198產品服務；原入口仍是前輪已核准候選，**不能用它宣稱已載入新後端修復**。本輪證據來自隔離TestClient及PG測試，不混用人工頁面版本。
- F5正式來源保存、011／最小權限、GuestPurger新FK、相容Rollback映像、備份隔離還原、真Provider／GCP E2E及人工Review仍待完成。沒有宣布Gate B通過或Merge Ready。
- 正常授權與撤回在Provider派送前的細粒度競態仍按原審查「待確認」項列管；本輪透過封鎖模擬消除F1該入口，不宣稱其餘所有AI用途競態全解。
- 原紀錄／raw／目標貢獻／獎勵的正式交易程式未修改；相關晚期版本衝突、重送、來源變更／排除及跨Owner回歸PASS，不代表正式Alpha實測。

## 供Owner確認的提交計畫（未執行）

1. **提交A：`fix(security): block unapproved simulation and bind person sources`**：F1/F2/F4服務變更及對應來源／回滾／PG測試；四個紅燈原探針仍可對照。測試檔有共享fixture，提交前檢查每一Commit可獨立收集測試。
2. **提交B：`fix(ai): bound media jobs and preserve per-segment budget`**：F3 Runtime／audio／main／media header及媒體工作、預算、取消、並發、冪等測試。ai_runtime.py同時有F1服務封鎖，需以hunk分批，不機械分整檔。每批只重跑受影響測試。
3. **提交C：`docs(review): record evidence and propose fact provenance contract`**：原AI審查、當次修復說明、F5審查契約與獨立測試、測試／Diff／hash收據；不放任何秘密或正式資料。
4. Owner確認上述內容後才Commit；取得本輪明確Commit／Push確認再普通Push同一PR #26分支，沒有force／rebase／Merge main。提交後精確SHA重新綁定證據，UX僅做上述影響評估，不自稱重新Approved。
5. F5模型需另外核准後再安排程式及Migration審查稿，正式Migration／GRANT／Build／Deploy／切流仍各別授權。

目前HEAD仍f3f4c9f，所有修復留工作區供審查。等待Owner決定提交及F5契約；本輪不繼續擴充功能。
