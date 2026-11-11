# 草稿AI授權｜後端候選契約，未發布

本篇草稿原文、固定整理指令→摘要/任務/原文明示人物資訊候選，結果不自動套用。source_scope不含媒體、其他人物資料或背景記憶；背景個人化授權不涵蓋未確認草稿。operation=experience已禁止自動注入背景FeatureStore。

沿用data_consents，purpose=ai_generation，subject=ai:draft-experience-summary。policy指紋綁提供者/模型/真實或替身/版本/來源範圍；範圍相同且未撤回可重用，模型或範圍改變需重讀並重新明確授權。source_scope為JSON物件，符合兩庫原有CHECK；不新增資料表或篡改Schema。

GET /api/ai/draft-consent只回目前Session Owner的狀態及非敏感提供者/用途說明。POST須CSRF、request_id、policy_fingerprint與嚴格confirmed=true；Owner交易鎖/active唯一索引/requests冪等收據保護並行與重送。DELETE撤回這個用途的有效同意，保留歷史，不取消已送出的模型請求。撤回後舊grant request_id回409，不會重新授權。非登入401、Guest403，不接受owner_id代查。

啟用真Provider時，POST /api/drafts/{id}/suggest先驗Owner/draft，再驗有效授權，之後才預留額度及呼叫模型。未授權沒有預留或模型呼叫。停用AI時原有手動原文候選相容路徑保留，不能冒稱真AI。任務/劇場/媒體仍使用各自既有授權，不共用本用途。

## 權限Gate

Alpha快照的Runtime僅SELECT/INSERT，無revoked_at UPDATE；不能繞存另一份撤回狀態。後端缺安全撤回能力時回available=false，拒絕授權/模型呼叫，不自行GRANT。本機marker PG18已測試提議的UPDATE(revoked_at)，其他Owner/範圍欄位不得更新。

審查稿見migrations/DRAFT_AI_CONSENT_COLUMN_GRANT.review.sql，只提議單一指定庫Runtime的欄位權限，未在GCP執行。Schema及表Owner不變，不執行Migration。回復前先停用草稿AI，審查有效同意及既有GRANT，不刪同意歷史，不自動回復權限。

## 尚未完成

本輪先完成後端及隔離SQLite/PG測試；單一手動/AI選擇、首次告知/有效授權重用/撤回的正式前端仍需接上。現有配置AI的舊整理按鈕在未授權時會被403安全攔截，不能宣稱可供Owner使用或部署。完整UX/真AI/真Google/GCP E2E/發布Gate維持未通過。
