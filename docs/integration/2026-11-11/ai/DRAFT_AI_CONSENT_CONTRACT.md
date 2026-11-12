# 草稿AI授權｜後端候選契約，未發布

本篇草稿原文、固定整理指令→摘要/任務/原文明示人物資訊候選，結果不自動套用。source_scope不含媒體、其他人物資料或背景記憶；背景個人化授權不涵蓋未確認草稿。operation=experience已禁止自動注入背景FeatureStore。

沿用data_consents，purpose=ai_generation，subject=ai:draft-experience-summary。policy指紋綁提供者/模型/真實或替身/版本/來源範圍；範圍相同且未撤回可重用，模型或範圍改變需重讀並重新明確授權。source_scope為JSON物件，符合兩庫原有CHECK；不新增資料表或篡改Schema。

GET /api/ai/draft-consent只回目前Session Owner的狀態及非敏感提供者/用途說明。POST須CSRF、request_id、policy_fingerprint與嚴格confirmed=true；Owner交易鎖/active唯一索引/requests冪等收據保護並行與重送。DELETE撤回這個用途的有效同意，保留歷史，不取消已送出的模型請求。撤回後舊grant request_id回409，不會重新授權。非登入401、Guest403，不接受owner_id代查。

啟用真Provider時，POST /api/drafts/{id}/suggest先驗Owner/draft，再驗有效授權，之後才預留額度及呼叫模型。未授權沒有預留或模型呼叫。停用AI時原有手動原文候選相容路徑保留，不能冒稱真AI。任務/劇場/媒體仍使用各自既有授權，不共用本用途。

## 權限Gate

Alpha快照的Runtime僅SELECT/INSERT，無revoked_at UPDATE；不能繞存另一份撤回狀態。後端缺安全撤回能力時回available=false，拒絕授權/模型呼叫，不自行GRANT。本機marker PG18已測試提議的UPDATE(revoked_at)，其他Owner/範圍欄位不得更新。

審查稿見migrations/DRAFT_AI_CONSENT_COLUMN_GRANT.review.sql，只提議單一指定庫Runtime的欄位權限，未在GCP執行。Schema及表Owner不變，不執行Migration。回復前先停用草稿AI，審查有效同意及既有GRANT，不刪同意歷史，不自動回復權限。

## 前端候選（本機已驗證，未發布）

第四步單一「直接使用我的原文／使用AI整理」，預設手動。以後端描述確認提供者/用途/權限；缺安全撤回權限時停用AI選項。首次清楚告知後才POST授權並呼叫，範圍有效則重用；可查看/撤回。未選AI不呼叫模型。沒有localStorage同意旗標，也不將背景授權套給草稿。

切換手動、離開或Owner/草稿改變會丟棄未採用的晚回應，不清空手動摘要/原文/任務。已送出請求仍可能計費。明確502後使用者可主動以新request_id重試；結果未知則沿用原ID，不自動重叫，若409只提供本人收據入口。授權/撤回失敗不假顯示成功。原有AI人物建議現在只讀，不再提供會誤套第一位人物的捷徑；逐人採納尚未完成，需返回第三步核對。

新版suggest送X-Draft-Revision，格式錯誤422、版本不符409，皆在預留/Provider前拒絕；省略仍支援既有客戶端。成功回source_revision/source_sha256綁定捕捉的原文。前端不接受缺版本或不符的候選；模型期間發生其他裝置修改仍由最終Confirm版本鎖拒絕，不宣稱跨模型呼叫持有DB交易。

320/390/1440 Chromium與真本機授權API、明示Provider替身共8 PASS；來源版本已含SQLite與marker PG18。這不是Gemini、Google、Alpha或實機Safari驗收。完整UX/正式權限/GCP E2E/發布Gate維持未通過。
