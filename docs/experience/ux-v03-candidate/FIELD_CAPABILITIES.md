[2026-11-11 人物補充延伸 Candidate：契約差異與 Gate B 待辦](PERSON_SUPPLEMENT_REVIEW.md)。整體 UX 尚未核准，不以設計補充解鎖工程 Gate。

# 人物與草稿能力核對：設計缺口，不是新資料模型核准

基準：PR24 `7013894`；本輪只讀 Repo、既有 Alpha 初始化 SQL 與歷史收據。**未連正式 DB 做即時欄位查詢**，不能以這份文件冒稱當前 Cloud SQL schema 驗收。

來源：`app/schemas.py` 的 PersonCreate／PersonUpdateCandidate／Confirm／PendingPerson；`app/people.py::_apply_person_updates`；`app/service.py::confirm`；`app/migrations/002_people_360.sql`；Repo `docs/database/schema-2026-11-02/POSTGRESQL_CORE_DRAFT.sql`；Owner 已執行的工作區 `2026-11-08_ALPHA_03_05_FINAL 2/03_CORE_EMPTY_ONLY.sql`（people 約244行、person_facts 約271行）；既有 `OWNER_DBA_RECEIPT.json` 證明34表及帳號，不含逐欄位即時查核。

| 資料 | 現有契約與保存能力 | v0.3 預覽界線 |
|---|---|---|
| 姓名、角色、標籤、分類、備註、共同場合 | PersonCreate／people 已有；獨立建人 API 會立即寫入 | 不在第三步直接呼叫。PR24 pending_person 只帶 name/relation/start，最終確認才建一位人物 |
| 興趣／飲食／專長背景／互動習慣 | person_facts 四個 dimension＋value/description/source/revision；PersonUpdateCandidate 逐項 selected | 可展示有來源的既有值＋新增候選；不代表自動覆寫原值。Demo「閱讀 ＋ 攝影」是保留閱讀並新增，不是以攝影替換 |
| 真正更正既有事實 | conflicts_with 能指向衝突；現有來源／歷史／更正行為需分開核對 | 不把衝突當作已確定新事實。明確覆寫／取代需另有版本、原 fact 與動作契約 |
| 工作／職稱、公司 | people 沒有 job/company 欄；PersonCreate／PersonUpdateCandidate 沒有獨立 key。skills 泛類不等於公司欄位 | **缺口**。有原文示例才顯示，標「尚無正式保存契約」、不可勾入保存。不塞 tags/notes 假支持 |
| 多人物異動 | Confirm.person_updates 沒有 person_id，套到單一 data.person_id；PR24 僅一個 pending_person | **缺口**。Demo 以每人 key 分開核對，但正式定向提交尚未完成，不冒稱多人後端已可用 |
| 來源 | fact_sources 綁正式 experience_id；StoryMention 有精確原文字元區間；候選 description 並非完整通用引用DTO | 預覽顯示此人物的原文引用及輸入／候選來源；多人跨來源檢查與確認需補契約 |
| 已保存草稿刪除 | 現有沒有 DELETE 草稿安全 API；MediaUI.discard 只處理本機 | Demo 刪除只改記憶體清單，所有畫面標「示意／未接 API」；正式 API NOT IMPLEMENTED |

## 最小調整提案（未寫 SQL／未執行）

1. 多人定向先擴充 API DTO，不必建立新資料庫：`person_changes[]` 每筆必須帶 `target.person_id` 或本次 `new_person.client_ref`、`expected_person_revision`、`candidate_id`、欄位、值、來源與 `selected`。預覽／確認共用驗證器與內容指紋；禁止無 target 的候選自行配到第一人。現有單人 payload 可向後相容保留，但不可混用兩條語意。
2. 新人物採有上限的 `pending_people[]`，以 client_ref 連回角色、來源、候選。最終交易先驗所有 Owner／來源／版本，再建立人物、解析 references；取消不建人，任何錯誤回滾，cached request receipt 先查以防重建。實際實作需核准後審查。
3. 工作／公司若確定要以正式欄位管理，最小候選是在既有 person_facts 增加可空白 `attribute_key`（如 job_title/company），保留 owner/person/source/revision 與舊維度；指定哪個舊 fact 被更正、有效時間與來源。屬**增量 Migration 提案**，唯一性／CHECK／舊資料回填策略、備份 Gate 及 Runtime 最小權限需另審；本輪沒有執行，也不選定未核准的最終模型。
4. 不新增公司表／CRM平台／帳號系統；若 Owner 不採新欄位，本輪就隱藏其保存能力，只呈現原文不宣稱結構化保存。

## 草稿刪除契約提案

`DELETE /api/drafts/{id}`（NOT IMPLEMENTED）：攜帶 expected_revision、request_id；先 Session／CSRF／Origin／Owner，再鎖定草稿狀態與版本。status 非 draft 拒絕，明確禁止刪正式 experiences／reward。刪除 draft_stories 等受允許依賴，AI稽核與成本收據依留存契約保留，不直接概括 cascade；完成前需盤點所有 FK 和JSON引用。成功與去重收據同一交易，重試先查 Owner 對應收據；回應未知先查狀態，不宣稱成功。版本衝突先回讀最新內容，再二次確認。

只在伺服器成功後解除該 Owner／該草稿本機引用；共用素材不可誤刪，保留原檔與移除原檔需明確分開。Runtime 現有 DELETE 範圍與必要 GRANT 尚待最小權限審查，不以此文件授權擴權。

## PR22 升級聯合接線提案

UI 只接受實際 `/auth/me`／capabilities 與 PR22 已提交交換收據。upgrade 同 Owner：保留四步狀態及原表單 DOM，只重新初始化帳號、媒體能力／人物選擇區；不呼叫全頁 render 造成資料遺失。login 不同 Owner：沿 PR22 明確放棄、安全交換及本機分 Owner 清理，不承諾保留原表單。取消／驗證失敗／衝突維持 Guest；回應未知先 reconcile，不盲目再交換。此項真聯合驗收 **NOT RUN**，本輪 Demo 只有標明 DESIGN_FIXTURE_ONLY 的會話情境。

## R2 補充（設計能力分類）

- A區只列姓名／本次角色與已核對、具保存能力的資訊。B區列未採用／來源失效／工作公司未支援／多人定向未接通的資訊；保留核對不等於納入寫入。沒有擴充Schema來讓畫面看似能用。
- 摘要來源與AI候選來源各自追蹤；原文變更保留手動摘要並阻擋確認直到重新核對。Demo只做保守字串／引用判定，不冒充語意一致性模型。
- AI授權示意按Owner、提供者、資料範圍、用途、版本區分；正式仍須後端授權收據、到期與撤回。背景授權不適用未確認草稿。UI成功不構成真模型／資料保存驗收。
