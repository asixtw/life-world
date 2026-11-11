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

生日/任職等基本資料候選已納入獨立清單，不塞入四維事實；第三/四步基本資料UI仍待整合。前端已接摘要/任務保存及第四步逐人候選採用/排除、證據類型、來源與原有事實預覽，選用後由同一Confirm原子保存；草稿含候選時不得混入舊單人person_updates。第三步已接四維收合補充輸入，人物選擇已換為精簡卡片，完整UX未核准；見STEP3_SUPPLEMENT_CONTRACT.md。生日/任職候選UI仍是整合缺口。

## 測試

測試檔tests/test_draft_review.py；PG同契約於tests/test_pg_integration_person_details.py執行。browser_tests/test_draft_review.py為實際本機API/Chromium，不用真實Alpha、Google或外部AI。收據見INTEGRATION_RELEASE_REPORT.md與evidence。


## 生日與任職候選增量（本機後端，未發布）

review新增birthday_candidates[]、employment_candidates[]；與person_candidates合計最多100項，candidate_ref跨三類唯一。共同欄位target(person_id/client_ref恰一)、expected_revision、source_kind、source_sha256、quote、evidence_type、selected/excluded/needs_review。來源管道不推定證據。自行記錄可不附證據/經歷ID；raw須目前原文hash/片段/明確得知依據，正式來源ID由Confirm綁新經歷，不假造來源。

生日value為birth_year/month/day。草稿可保留不完整或02-31等待修輸入，但needs_review=true且selected撤銷；正式Confirm使用BirthdayValue驗真日期。未知年允許02-29，不推年齡。空白不當成清除；需明確clear=true且value全NULL才接受清除候選。expected_revision為生日紀錄版本，無紀錄為0。

任職value沿用EmploymentPatchValue；employment_id省略是新增（candidate_ref作此批次新增代碼），有值則明確修改該人物既有任職並需版本>=1。草稿保存/讀回只序列化明確提供欄位，不能補成顯式null、清空其他欄位或自動結束另一份工作。新增至少公司/職稱一項；既有PATCH需有變更欄位，合併原值後正式驗證。草稿即驗Owner及employment_id屬指定人物，其他人的任職404。

原文實質更改只使raw候選待重核對，保留輸入值；獨立manual候選不清掉。未排除項目必須selected且完整/來源有效。舊Confirm不選用完整review遇任一已保存候選回409；同時傳review與直接birthday_updates/employment_updates/person updates回422，不混用兩份權威。

確認轉成既有TargetBirthdayUpdate/TargetEmploymentUpdate，與新人物/經歷/任務/事實/目標/獎勵同一交易。晚期版本衝突全部回滾；重送同request返回同收據，不增人物、任職歷史或獎勵。這一增量不新增Schema/GRANT，仍依賴正式Gate尚未套用的011表能力。

### 客戶端與回復邊界

本輪後端完成不代表PR24基本資料UI接好。第三/四步生日、任職輸入/差異/逐項核對的實際瀏覽器驗收NOT RUN，不以API種入候選代替。現有四維畫面不得宣稱已能編輯基本資料候選；完整UI是合併前阻擋。

空清單不序列化，原本四維草稿相容；但舊版DraftReview extra=forbid不認得新欄位，不能假定0eee0a3或Alpha舊映像可無損讀回新候選。正式啟用前須相容reader、固定版本/混合Revision與資料回復演練；不刪候選當回滾。本輪新格式只存在本機合成資料。

測試tests/test_draft_basic_review.py六案例在SQLite與受限marker PG18共用，驗跨Session、同名雙人、source失效、未完成/排除、舊客戶端/混用拒絕、Owner/Guest、任職部分更新、晚期衝突回滾與空白/明確清除。不是GCP或UX核准。
