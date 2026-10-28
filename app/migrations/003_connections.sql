CREATE TABLE draft_stories ( -- 保存尚未確認的人物整理，不改舊草稿欄位
 draft_id TEXT PRIMARY KEY REFERENCES drafts(id), payload TEXT NOT NULL -- 以草稿識別碼與 JSON 保存未審閱角色
); -- 完成草稿延伸表
CREATE TABLE experience_stories ( -- 定義逐經歷的交會狀態
 experience_id TEXT PRIMARY KEY REFERENCES experiences(id), owner_id TEXT NOT NULL REFERENCES users(id), -- 保存來源與帳號
 title TEXT NOT NULL DEFAULT '', reviewed INTEGER NOT NULL DEFAULT 0 CHECK(reviewed IN (0,1)), -- 未核對的舊關聯不進探索
 available INTEGER NOT NULL DEFAULT 1 CHECK(available IN (0,1)), revision INTEGER NOT NULL DEFAULT 1 -- 提供撤回與樂觀鎖
); -- 完成故事狀態表
INSERT INTO experience_stories(experience_id,owner_id) SELECT id,owner_id FROM experiences; -- 舊資料只回填待核對狀態，不改原文或帳本
CREATE INDEX stories_owner_review ON experience_stories(owner_id,reviewed,available); -- 支援帳號可見故事查詢
CREATE TABLE experience_participants ( -- 保留每筆故事的實際參與者
 experience_id TEXT NOT NULL REFERENCES experience_stories(experience_id), person_id TEXT NOT NULL REFERENCES people(id), -- 不使用合併事件的人物聯集
 interacted INTEGER NOT NULL DEFAULT 0 CHECK(interacted IN (0,1)), PRIMARY KEY(experience_id,person_id) -- 同場與直接互動分開
); -- 完成參與來源表
CREATE INDEX participants_person ON experience_participants(person_id,experience_id); -- 支援人物焦點查詢
CREATE TABLE experience_mentions ( -- 保留原文提及與人工身分核對
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL REFERENCES experience_stories(experience_id), -- 保存固定線索與來源
 name TEXT NOT NULL, start INTEGER NOT NULL CHECK(start>=0), end INTEGER NOT NULL CHECK(end>start), -- 以 Unicode 字元定位原文
 status TEXT NOT NULL DEFAULT 'unmatched' CHECK(status IN ('unmatched','matched','rejected')), -- 配對狀態不等於參與
 person_id TEXT REFERENCES people(id), revision INTEGER NOT NULL DEFAULT 1, -- 正式人物與版本
 UNIQUE(experience_id,start,end), CHECK((status='matched' AND person_id IS NOT NULL) OR (status<>'matched' AND person_id IS NULL)) -- 拒絕矛盾與重複來源
); -- 完成原文提及表
CREATE INDEX mentions_person ON experience_mentions(person_id,status,experience_id); -- 支援已配對提及查詢
CREATE TABLE story_history ( -- 保存人工更正、配對與展示撤回歷史
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL REFERENCES experience_stories(experience_id), -- 限制歷史所屬來源
 action TEXT NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL, created_at TEXT NOT NULL -- 保留更正前後與日期
); -- 完成人工操作歷史
CREATE INDEX story_history_source ON story_history(experience_id,created_at); -- 支援本人回讀修改歷史
