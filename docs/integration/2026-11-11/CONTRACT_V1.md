# 整合契約 V1｜待 Code Review，不代表 UX／Migration／發布核准

2026-11-11。來源SHA見 BASELINES.json，四來源重疊與路徑見 OVERLAP_MATRIX.json。新分支只整合，不改來源分支。

## UX與來源邊界

PR24是四步／人物選填／逐項來源核對的權威，保留Candidate未核准狀態。先整合PR22安全交換、PR24既有產品修復與設計參考、PR25資源池與聲音必要修正。Jerry採單一people資料能力，不能整份覆寫UI、導覽或開AI。subject_experiences與本人experiences分流，前者永不觸發本人目標或獎勵。

## Confirm增量介面（提交審查的工程契約）

保留既有request_id、expected_revision、summary、contributions、story、person_id與舊person_updates相容。

- 新增 `pending_people[]`：`client_ref`（單次請求唯一）、name、relation（interaction/participant/mention）、start（僅提及且原文範圍合法）。不因同名合併。舊pending_person相容，但不能與新清單混用。
- 新增 `targeted_person_updates[]`：`target`（person_id 或 client_ref，恰一）、expected_person_revision（既有人物必需）、dimension（四維度）、value、description、evidence_type、selected、source_kind、source_revision、quote（raw必須）、conflicts_with。
- source_kind只代表manual/raw；evidence_type必須由使用者選定或沿用同候選已確認來源，不能由輸入管道推定。未知欄位／無效目標拒絕。公司／職稱／生日不接受繞存其他欄位。
- 最終確認同一DB交易：驗Owner/來源/revision→原始payload指紋/冪等查詢→解析pending_people→驗結構化人物類型與狀態→寫經歷/來源/人物事實/任務/目標貢獻/獎勵→收據。任何錯誤整筆回滾；不改寫傳入DTO以影響重送指紋。
- 被提及的人物不計互動／見面。虛構、歷史、封存人物不得用於本人真實經歷的真人互動與計分。subject_experiences獨立端點，不借Confirm繞過。

## 已保存草稿刪除

`DELETE /api/drafts/{id}`：body request_id、expected_revision；既有Session/CSRF/Origin檢查。只允許目前Owner的未確認草稿；已確認409，版本不符409，跨Owner404，重送同請求回原收據。刪除前核對媒體／來源FK，DB交易先處理引用，外部素材刪除須與其他Owner隔離且可重試，不能刪掉共享素材。未保存修改的捨棄只在本機，不呼叫此API。

## Schema010選取與權威

people維持唯一主檔；person_type/subtype/aliases/status/description/origin_type以實際Alpha核准結構為準，不把交接DDL直接套用。/api/people與/api/persons共用人物讀寫與Owner/類型檢查；Jerry九項完整角色設定、人物作品、進階劇場與角色創作不因分支存在而核准；不列R+1或已承諾未來工作。僅保留必要資料相容，未核准入口不得新增或開啟。

person_facts/fact_sources是正式核對資訊；relationship_features/preferences僅授權範圍內衍生資料，不互覆。person_connections來源需單一部署模式：link_table為新目標，舊JSON僅轉移前兼容，禁止兩邊獨立寫成權威。

## DB與發布Gate

正式010/新增差異Migration僅在完整E2E/Alpha機器可讀Fingerprint比對後提出，先隔離PG18測試，後續授權DBA才可執行。SQLite009不假設存在PG。GuestPurger維持fail-closed，010新表/FK需逐一核對所有權與刪除契約，不能單純放寬表集合。

GCP只讀已確認lw-public仍camera-8f377fa 100%；API主觸發器RequireApproval=true。服務template是最新版本，不能代表100%Revision的環境，下一步按Revision驗。UX、CodeReview、E2E、Owner明確Merge及Alpha發布授權皆未完成，不觸發正式Merge/Alpha切流。

## 多人待建立草稿增量（本機整合，未部署）

既有 `draft_stories.payload` 保存 `story.pending_people[]`，每項為 `{client_ref,name,relation,start?}`，不新增DB欄位。`relation` 是 interaction / participant / mention，提及必須對應本次原文Unicode位置。client_ref唯一且不依姓名合併，所有參與/提及數量含待建立者合計各不得超過100。Guest不能提交人物候選。

草稿POST/PUT/GET不建人、不計分；相同版本/Owner/來源驗證沿用原交易。原文變更使提及位置失效時422並保留先前草稿版本，前端應提示重新核對，不自動猜新位置。最後Confirm可採 `story.pending_people` 或既有頂層 `pending_people`，不得同時傳兩份；也不得混用legacy `pending_person`。最後人工story_reviewed後才建人，回 `created_people` client_ref→id，同交易保存經歷/任務/事實/貢獻/獎勵，失敗整筆回滾，request_id重試不重建。

現有產品編輯器補了讀取/重存的名單保護，能逐人顯示並確認；完整Candidate的新增/修改/逐項補充與差異預覽仍須後續接線。此相容保護不能視為多人UX完成或發布Gate通過。原PR22帳號交易不變。
