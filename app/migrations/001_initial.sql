CREATE TABLE users ( -- 定義帳號與個人介紹
 id TEXT PRIMARY KEY, status TEXT NOT NULL CHECK(status IN ('guest','registered')), -- 定義固定識別碼、資料狀態
 username TEXT UNIQUE, password_hash TEXT, name TEXT NOT NULL DEFAULT '', bio TEXT NOT NULL DEFAULT '', -- 定義本機帳號名稱、password_hash、顯示稱呼、自我介紹
 timezone TEXT NOT NULL DEFAULT 'Asia/Taipei', hatched_at TEXT, created_at TEXT NOT NULL -- 定義IANA 時區、hatched_at、建立時間
); -- 完成帳號與個人介紹的欄位與資料限制
CREATE TABLE sessions ( -- 定義登入工作階段
 token_hash TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), -- 定義token_hash、所屬帳號
 csrf_token TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL -- 定義csrf_token、expires_at、建立時間
); -- 完成登入工作階段的欄位與資料限制
CREATE INDEX session_owner_idx ON sessions(owner_id); -- 建立查詢索引，支援所屬帳號或時間排序
CREATE TABLE goals ( -- 定義目標
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), title TEXT NOT NULL, -- 定義固定識別碼、所屬帳號、標題
 outcome TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','completed')), -- 定義目標的終極成果說明、資料狀態
 created_at TEXT NOT NULL, completed_at TEXT, reflection TEXT NOT NULL DEFAULT '' -- 定義建立時間、completed_at、目標完成感想
); -- 完成目標的欄位與資料限制
CREATE INDEX goals_owner_idx ON goals(owner_id); -- 建立查詢索引，支援所屬帳號或時間排序
CREATE TABLE actions ( -- 定義目標行動
 id TEXT PRIMARY KEY, goal_id TEXT NOT NULL REFERENCES goals(id), owner_id TEXT NOT NULL REFERENCES users(id), -- 定義固定識別碼、關聯目標識別碼、所屬帳號
 title TEXT NOT NULL, unit TEXT NOT NULL, target TEXT NOT NULL, -- 定義標題、行動計量單位、行動預期累計值
 level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 3), weekdays TEXT NOT NULL, position INTEGER NOT NULL -- 定義建立時的養分等級、每週預計執行日（週一為 0）、position
); -- 完成目標行動的欄位與資料限制
CREATE TABLE people ( -- 定義人物基本資料
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), name TEXT NOT NULL, -- 定義固定識別碼、所屬帳號、顯示稱呼
 role TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL -- 定義舊版完整角色文字、自行記錄的備註（不自動轉成事實）、建立時間
); -- 完成人物基本資料的欄位與資料限制
CREATE TABLE drafts ( -- 定義經歷草稿
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT REFERENCES goals(id), -- 定義固定識別碼、所屬帳號、關聯目標識別碼
 person_id TEXT REFERENCES people(id), raw_text TEXT NOT NULL, occurred_at TEXT NOT NULL, -- 定義關聯人物識別碼、原始經歷文字（保留空白與換行）、帶時區的實際發生時間
 contributions TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('draft','confirmed')), -- 定義本次要累計的行動貢獻清單、資料狀態
 revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL -- 定義資料版本、建立時間、updated_at
); -- 完成經歷草稿的欄位與資料限制
CREATE TABLE experiences ( -- 定義已確認經歷
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), draft_id TEXT NOT NULL UNIQUE REFERENCES drafts(id), -- 定義固定識別碼、所屬帳號、draft_id
 goal_id TEXT REFERENCES goals(id), person_id TEXT REFERENCES people(id), raw_text TEXT NOT NULL, -- 定義關聯目標識別碼、關聯人物識別碼、原始經歷文字（保留空白與換行）
 summary TEXT NOT NULL, occurred_at TEXT NOT NULL, created_at TEXT NOT NULL -- 定義使用者核對後的經歷摘要、帶時區的實際發生時間、建立時間
); -- 完成已確認經歷的欄位與資料限制
CREATE INDEX experiences_owner_idx ON experiences(owner_id); -- 建立查詢索引，支援所屬帳號或時間排序
CREATE TABLE contributions ( -- 定義行動貢獻
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL REFERENCES experiences(id), -- 定義固定識別碼、所屬帳號、已確認經歷識別碼
 action_id TEXT NOT NULL REFERENCES actions(id), quantity TEXT NOT NULL, -- 定義本次貢獻所屬行動識別碼、本次人工確認的貢獻量
 UNIQUE(experience_id, action_id) -- 定義唯一鍵、主鍵或外鍵限制
); -- 完成行動貢獻的欄位與資料限制
CREATE TABLE reward_ledger ( -- 定義積分帳本
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL UNIQUE REFERENCES experiences(id), -- 定義固定識別碼、所屬帳號、已確認經歷識別碼
 points INTEGER NOT NULL CHECK(points>0), rule_version TEXT NOT NULL, created_at TEXT NOT NULL -- 定義points、積分規則的開發版本代號、建立時間
); -- 完成積分帳本的欄位與資料限制
CREATE TABLE tasks ( -- 定義下一步待辦
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL REFERENCES experiences(id), -- 定義固定識別碼、所屬帳號、已確認經歷識別碼
 title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0 CHECK(done IN (0,1)) -- 定義標題、待辦完成狀態（不代表行動貢獻）
); -- 完成下一步待辦的欄位與資料限制
CREATE TABLE evidence ( -- 定義圖片佐證
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT NOT NULL REFERENCES goals(id), -- 定義固定識別碼、所屬帳號、關聯目標識別碼
 filename TEXT NOT NULL, mime TEXT NOT NULL, digest TEXT NOT NULL, content BLOB NOT NULL, size INTEGER NOT NULL, -- 定義filename、mime、digest、私人筆記內容、size
 created_at TEXT NOT NULL, UNIQUE(owner_id, goal_id, digest) -- 定義建立時間
); -- 完成圖片佐證的欄位與資料限制
CREATE TABLE completions ( -- 定義目標完成紀錄
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT NOT NULL UNIQUE REFERENCES goals(id), -- 定義固定識別碼、所屬帳號、關聯目標識別碼
 evidence_ids TEXT NOT NULL, reflection TEXT NOT NULL, created_at TEXT NOT NULL -- 定義完成目標所引用的佐證識別碼、目標完成感想、建立時間
); -- 完成目標完成紀錄的欄位與資料限制
CREATE TABLE notes ( -- 定義私人筆記
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), person_id TEXT REFERENCES people(id), -- 定義固定識別碼、所屬帳號、關聯人物識別碼
 kind TEXT NOT NULL CHECK(kind IN ('preparation','simulation','message')), title TEXT NOT NULL, -- 定義互動或私人筆記的分類、標題
 content TEXT NOT NULL, created_at TEXT NOT NULL -- 定義私人筆記內容、建立時間
); -- 完成私人筆記的欄位與資料限制
CREATE TABLE requests ( -- 定義去重請求
 owner_id TEXT NOT NULL REFERENCES users(id), operation TEXT NOT NULL, request_id TEXT NOT NULL, -- 定義所屬帳號、operation、重送去重用的提交代碼
 fingerprint TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(owner_id, operation, request_id) -- 定義fingerprint、response
); -- 完成去重請求的欄位與資料限制
