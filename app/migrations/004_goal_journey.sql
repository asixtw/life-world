ALTER TABLE goals ADD COLUMN start_date TEXT; -- 舊目標保留空值，不推定使用者的挑戰日期。
ALTER TABLE goals ADD COLUMN deadline TEXT; -- 截止日使用目標時區的當地日期。
ALTER TABLE goals ADD COLUMN schedule_timezone TEXT; -- 固定挑戰開始時的時區。
ALTER TABLE goals ADD COLUMN revision INTEGER NOT NULL DEFAULT 1; -- 以版本防止舊頁面覆蓋。
ALTER TABLE goals ADD COLUMN ended_at TEXT; -- 另存結束時間，保留舊狀態欄位與外鍵結構。
ALTER TABLE goals ADD COLUMN end_reason TEXT CHECK(end_reason IN ('early_end','expired')); -- 區分提前結束與到期未完成。
ALTER TABLE actions ADD COLUMN per_occurrence TEXT NOT NULL DEFAULT '1'; -- 每次預期量，舊總量不重算。
ALTER TABLE actions ADD COLUMN schedule_dates TEXT; -- 舊排程尚未由使用者重新確認。
ALTER TABLE actions ADD COLUMN cycle TEXT NOT NULL DEFAULT 'month' CHECK(cycle IN ('month','week')); -- 記住編輯週期。
ALTER TABLE actions ADD COLUMN target_is_derived INTEGER NOT NULL DEFAULT 0; -- 僅新式總量依安排日期計算。
CREATE TABLE goal_reviews ( -- 保存期限與排程修改的前後快照。
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT NOT NULL REFERENCES goals(id), -- 回顧歸屬於同一帳號與目標。
 decision TEXT NOT NULL, previous_state TEXT NOT NULL, new_state TEXT NOT NULL, reflection TEXT NOT NULL, created_at TEXT NOT NULL -- 不覆寫歷史回顧。
); -- 回顧與正式修改在同一交易內提交。
CREATE TABLE pending_contributions ( -- 到期後先確認經歷，不提前計入目標。
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT NOT NULL REFERENCES goals(id), -- 權限與目標來源。
 experience_id TEXT NOT NULL REFERENCES experiences(id), action_id TEXT NOT NULL REFERENCES actions(id), quantity TEXT NOT NULL, -- 保留原始建議數量。
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','unapplied')), accepted_quantity TEXT, accepted_at TEXT, -- 人工採計歷史。
 UNIQUE(experience_id,action_id) -- 同筆經歷的同項貢獻只能待處理一次。
); -- 採計只新增 contribution，不新增 reward。
CREATE INDEX pending_goal_idx ON pending_contributions(owner_id,goal_id); -- 支援目標回顧查詢。
