# 第三步逐人補充｜本機整合候選

2026-11-11。延伸DraftReview既有契約，不新增步驟、資料庫或AI。不是Owner UX核准。

每位已選人物的資訊可選填，預設收合；資訊類別為interests/food/skills/habits。輸入管道manual/raw與evidence_type本人告知/使用者觀察/文件記載分開，不預設證據。raw需手動提供存在於當前原文的片段；保存到伺服器後第四步依來源hash重核對。候選逐項確認前selected=false。每次加入後清空本次輸入並收合，不刪已加入項。

module只改flow.personCandidates與supplementInputs。本機保存在既有Owner/草稿IndexedDB，復原驗Owner及資料形狀，無新儲存服務；伺服器使用既有DraftReview JSON。未加入候選的有意義文字會阻擋保存，提示加入或清空；離開可保留本機草稿。候選target不在關聯中時需重新關聯或明確移除，不自動刪資料或轉移到第一位人物。

新人物仍為pending，只有最終Confirm建立。舊單人表單如有補充，以草稿內穩定client_ref=legacy轉成story.pending_people；加入第二位人物沿用第一人的鍵。server同交易處理事實、來源、經歷、進度、任務、獎勵及冪等收據。保存/取消經歷不建人；同名不合併。Guest仍不開人物補充，原地升級只解鎖能力。

已人工配對且reviewed/available的提及可作明確人物事實的來源；不改來源的角色、不增互動或見面，也不放寬其他API的參與或關係來源規則。跨Owner、無效來源與版本由原後端再次驗證。raw/manual目前保存在草稿review；fact_sources對外API仍只投影傳統證據類型，完整來源瀏覽仍待整合。

公司/職稱/生日的經歷候選介面不開放；不以notes/tags/skills替代。人物選擇仍沿用舊fieldset，尚待精簡至Candidate；這不是完整UX驗收。沒有呼叫外部AI或GCP寫入，發布與Migration Gate不變。測試收據見INTEGRATION_RELEASE_REPORT.md。
