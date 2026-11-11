# DraftReview｜整合候選契約（未發布）

2026-11-11。API實作與隔離測試，不代表UX核准或正式Migration授權。

## 保存及讀回

沿用POST /api/experiences/drafts、PUT /api/drafts/{id}、GET /api/drafts/{id}。PUT須expected_revision；原有Owner、Session、CSRF、身分權限不變。新增可選review；省略保留既有資料，明確null移除核對內容。story與review分開；review不會建立人物、正式事實、任務或獎勵。

review包含summary、summary_source_sha256、summary_needs_review、tasks及person_candidates。GET另回raw_sha256。hash只綁定使用者核對的原文版本，並非AI成功或事實已查證的收據。

每項候選需唯一candidate_ref、target(person_id或client_ref恰一個)、dimension(interests/food/skills/habits)、value、description、source_kind(manual/raw)、evidence_type(本人告知/使用者觀察/文件記載)、來源hash/quote、existing person revision及selected/excluded/needs_review。未填完可保存；後端不猜證據類型，不把手動輸入等同觀察。client_ref必須在本草稿story.pending_people內，person_id須屬目前Owner。最多100項候選/20任務；沿用HTTP容量保護。

原文變動保留摘要和候選文字；摘要依來源hash標記重核對，raw候選來源變動或片段不再存在則撤銷selected。獨立manual候選不因無關原文變動而失效。重核對不等於向第三人證實。

## 最後確認

Confirm可明確傳review，或use_saved_review=true選用已保存內容。summary/tasks須與選用內容一致；所有候選必須逐項selected或excluded，未核對/來源失效不寫入。不可混用legacy person_updates與targeted_person_updates。選用內容轉為既有逐人targeted updates，與建人/經歷/進度/任務/獎勵及冪等收據同交易；失敗全部回滾。

舊客戶端若遇已保存人物候選而不選用完整契約，回409 saved_review_required，不默默漏存。僅摘要的舊Confirm在來源變動時須reviewed_summary_sha256等於目前原文hash。原有request_id指紋未因省略新增欄位而變動。

## 儲存與回復限制

同一draft_stories.payload使用experience_draft_v2 envelope：story與review。既有純StoryInput JSON仍可讀。沒有新建資料表、Migration或擴權；但不支援envelope的舊程式不可直接拿來當無損回滾版本，正式發布前需reader相容策略及回復演練。本輪Alpha沒有寫入新格式。

生日/任職等基本資料候選尚未納入本DraftReview DTO，不塞入四維事實。前端已接摘要/任務保存及第四步逐人候選採用/排除、證據類型、來源與原有事實預覽，選用後由同一Confirm原子保存；草稿含候選時不得混入舊單人person_updates。第三步已接四維收合補充輸入，人物選擇已換為精簡卡片，完整UX未核准；見STEP3_SUPPLEMENT_CONTRACT.md。生日/任職候選UI仍是整合缺口。

## 測試

測試檔tests/test_draft_review.py；PG同契約於tests/test_pg_integration_person_details.py執行。browser_tests/test_draft_review.py為實際本機API/Chromium，不用真實Alpha、Google或外部AI。收據見INTEGRATION_RELEASE_REPORT.md與evidence。
