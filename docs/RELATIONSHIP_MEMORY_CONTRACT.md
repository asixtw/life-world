# Hidden Relationship Intelligence：MVP P0

沿用同一PostgreSQL與來源模型，沒有另建服務。兩表保存明示偏好及四類有限來源特徵；欄位包含owner、subject type/id、feature key/value、source refs、context、epistemic status、model version、profile version、revocation state。讀取AI上下文前重驗已確認來源，撤回的舊快照清空並失效。停用或刪除會實際刪除衍生特徵，不刪正式來源。

`GET/PUT/DELETE /api/personalization`只作用於Session Owner；PUT/DELETE須CSRF。啟用須明確選擇，預設關閉。個人化內容只傳給既有AI Runtime，模型輸出不回寫Feature Store。training_opt_in固定false，僅有未來評測資料契約，不代表模型訓練。

本機驗證：隨機帳密登出／重新登入偏好持續、雙Owner隔離、四類特徵及人物來源撤回。完整矛盾／第二事件更新／PG18與線上長期記憶仍未驗收，不標PASS。

Alpha BLOCKED：新增表及最小DML需要增量009，原Alpha完整Metadata/ACL/Role還原Gate未PASS。候選SQL [009](database/009_relationship_memory_alpha_review.sql)保留ROLLBACK且無Migration收據，不可當成執行包。不得自動DDL、重跑007/008或挪用其他表冒充Feature Store。Runtime旗標LIFEWORLD_RELATIONSHIP_MEMORY_ENABLED保持false，其他功能照常部署。
