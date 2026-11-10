# 四步經歷與人物關聯：本輪契約

Base main 68102f2；PR #22 獨立、不重寫 Google。

- ExperienceFlowState：ownerId、draftId、expectedRevision、currentStep、rawText、occurredAt、goalId、contributions、personId、pendingPerson、story、editedSummary、dirty、requestId、mediaScope。單一 record DOM 保留 1–3 步資料及媒體；既有 review 路由作第 4 步，沿用保存／版本／冪等。
- Step 1 原文與既有媒體；2 目標活動量可略過；3 明確選參與／互動／原文提及，可多人；4 可編輯摘要、人物角色、貢獻、任務與人工確認。Guest 不開媒體／人物／AI。
- API 向後相容擴充 StoryInput.pending_person：name、relation(participant/interaction/mention)、start(提及 Unicode 位置)。存在 draft_stories JSON，沒有新 Schema。保存草稿不建立人物；confirm 必須 story_reviewed，在同一交易建立人物、關聯、經歷、任務、進度、獎勵；相同 request_id 回同收據。管理故事 API 不允許 pending_person。
- 人物選項來自目前 Owner 完整 /state.people；角色／標籤多選加自由輸入，共同場合單一字串。保留既有含分隔符標籤，不拆已選值。
- 交會 legacy 僅明確主要人物線索；正式 participant 僅參與表，mention 僅人工配對提及。總數與分頁同條件；原始歷史與獎勵不改。
- 站內離開沿用保存／捨棄未存修改／繼續。既存伺服器草稿不會被「捨棄未存修改」刪掉，清楚告知；不擴大 Runtime DELETE。

測試：先重現無人物 legacy／錯誤分頁／提及混入參與；人物選項空白／去重／特殊字元／Owner；pending 建人前零寫入、確認原子性、重送、Guest與越權、回滾；Chromium 手機桌面四步與返回、取消、錯誤保留。真 Google、Gemini、正式 Alpha 不在本輪執行。
