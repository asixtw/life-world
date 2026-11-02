-- 人物劇場正式持久化「擬議」：SESSION_RELIABILITY_SPEC.md 的關聯式映射。
-- 不是現有 SQLite、不授權新增 API，也不是已核准 migration；未在 PG 執行。
-- 依賴 POSTGRESQL_CORE_DRAFT.sql 的 lw_core_draft.users。只使用獨立草案 schema。
-- 所有實體 FK 保持 NO ACTION（預設）；永久刪除／快照遮蔽與備份期限待決。
-- DB 約束不涵蓋全部狀態轉移、JSON recipient 身分、生成租約、內容授權或隱私刪除。
BEGIN;
CREATE SCHEMA lw_theater_draft;

CREATE TABLE lw_theater_draft.theater_builder_drafts (
  id text PRIMARY KEY, -- 草稿穩定識別碼，由服務生成
  owner_id text NOT NULL REFERENCES lw_core_draft.users(id), -- 由登入身分決定，不信任客戶端 owner
  revision bigint NOT NULL DEFAULT 1, -- expected_revision 比對
  domain text NOT NULL, -- custom／demo 分域，禁止混場
  stage text NOT NULL, -- 建立步驟；具體 enum 待 UI 契約固定
  situation text NOT NULL DEFAULT '', -- 草稿情境
  purpose text NOT NULL DEFAULT '', -- 草稿目的
  person_ids jsonb NOT NULL DEFAULT '[]'::jsonb, -- 候選人物 ID；元素仍須服務驗證
  selected_source_refs jsonb NOT NULL DEFAULT '[]'::jsonb, -- 候選來源 locator／version，尚非凍結快照
  assumptions jsonb NOT NULL DEFAULT '[]'::jsonb, -- 明示的情境假設
  updated_at timestamptz NOT NULL, -- 服務時間，不默認採客戶端 Date.now
  UNIQUE(owner_id),
  CHECK(revision > 0),
  CHECK(domain IN ('custom','demo')),
  CHECK(jsonb_typeof(person_ids)='array'),
  CHECK(jsonb_typeof(selected_source_refs)='array'),
  CHECK(jsonb_typeof(assumptions)='array')
);

CREATE TABLE lw_theater_draft.theater_sessions (
  id text PRIMARY KEY, -- 新建場次 ID，重練不能沿用
  owner_id text NOT NULL REFERENCES lw_core_draft.users(id), -- 私人擁有者
  revision bigint NOT NULL DEFAULT 1, -- 每個成功命令遞增
  schema_version bigint NOT NULL DEFAULT 1, -- 正式候選 payload 版本，不等同原型 schemaVersion=2
  domain text NOT NULL, -- custom 或 demo
  lifecycle text NOT NULL DEFAULT 'ACTIVE', -- ACTIVE／PAUSED／ENDED；歷史為 ENDED 查詢
  pause_reason text, -- 暫停原因，非人物行為
  scenario_snapshot jsonb NOT NULL, -- 建場時 situation／purpose 凍結
  assumptions_snapshot jsonb NOT NULL DEFAULT '[]'::jsonb, -- 假設不是人物正式事實
  limits_snapshot jsonb NOT NULL, -- 玩家、角色、Lumi、技術重試上限；值需核准
  generation_epoch bigint NOT NULL DEFAULT 0, -- 介入、暫停、離頁、結束使舊生成失效
  input_draft text NOT NULL DEFAULT '', -- 尚未送出的文字；不是已接受 action
  recipient_ids jsonb NOT NULL DEFAULT '[]'::jsonb, -- 輸入草稿對象，以 participant_key 引用；all 需展開
  created_at timestamptz NOT NULL, -- 建場時間
  ended_at timestamptz, -- 結束時間
  end_reason text, -- 結束原因字彙待正式契約固定
  UNIQUE(owner_id,id),
  CHECK(revision > 0 AND schema_version > 0 AND generation_epoch >= 0),
  CHECK(domain IN ('custom','demo')),
  CHECK(lifecycle IN ('ACTIVE','PAUSED','ENDED')),
  CHECK((lifecycle='ENDED' AND ended_at IS NOT NULL AND end_reason IS NOT NULL) OR (lifecycle<>'ENDED' AND ended_at IS NULL AND end_reason IS NULL)),
  CHECK(jsonb_typeof(scenario_snapshot)='object'),
  CHECK(jsonb_typeof(assumptions_snapshot)='array'),
  CHECK(jsonb_typeof(limits_snapshot)='object'),
  CHECK(jsonb_typeof(recipient_ids)='array')
);
-- PAUSED 仍占一場名額；歷史檢視不占用名額。屬待核准的單活動場設計。
CREATE UNIQUE INDEX theater_one_open_owner ON lw_theater_draft.theater_sessions(owner_id) WHERE lifecycle IN ('ACTIVE','PAUSED');
CREATE INDEX theater_owner_history ON lw_theater_draft.theater_sessions(owner_id,lifecycle,created_at DESC,id);

CREATE TABLE lw_theater_draft.theater_participant_snapshots (
  owner_id text NOT NULL, -- 經複合 FK 繼承場次擁有者
  session_id text NOT NULL, -- 固定所屬場次
  participant_key text NOT NULL, -- 場次內識別；custom/demo 明確命名空間
  person_id text NOT NULL, -- 建場來源識別副本，刻意不是 live people FK
  person_version text, -- 來源提供時才填，不捏造正式 revision
  snapshot_version bigint NOT NULL, -- 快照格式版本
  name text NOT NULL, -- 當時名字
  roles jsonb NOT NULL DEFAULT '[]'::jsonb, -- 當時角色
  kind text NOT NULL, -- custom／demo；真實人物的模擬仍不代表本人意見
  captured_at timestamptz NOT NULL, -- 擷取時間
  availability text NOT NULL DEFAULT 'available', -- 失效後不能注入下一輪
  PRIMARY KEY(owner_id,session_id,participant_key),
  UNIQUE(owner_id,session_id,person_id),
  FOREIGN KEY(owner_id,session_id) REFERENCES lw_theater_draft.theater_sessions(owner_id,id),
  CHECK(snapshot_version > 0),
  CHECK(kind IN ('custom','demo')),
  CHECK(availability IN ('available','missing','revoked','redacted')),
  CHECK(jsonb_typeof(roles)='array')
);

CREATE TABLE lw_theater_draft.theater_source_snapshots (
  id text PRIMARY KEY, -- 快照 ID，不冒充上游 sourceId
  owner_id text NOT NULL, -- 同場次 owner
  session_id text NOT NULL, -- 凍結來源所屬場次
  participant_key text NOT NULL, -- 透過 participant 快照取得 personId
  source_id text, -- 上游確有穩定 ID 才填；原型單段來源可為 NULL
  source_locator jsonb NOT NULL, -- 來源表／ID／路徑及擷取限制；不能是任意 SQL
  source_version text, -- 上游版本若不存在保持 NULL
  source_kind text NOT NULL, -- 區分觀測、轉述、假設及 simulation
  content text, -- 凍結可用文字；redacted 可清空，不代表刪除流程已完成
  selected_by_user boolean NOT NULL, -- 明確選取，不能以存在就當同意
  validity text NOT NULL DEFAULT 'valid', -- 不再有效的來源禁止再次生成
  captured_at timestamptz NOT NULL, -- 擷取時間
  FOREIGN KEY(owner_id,session_id,participant_key) REFERENCES lw_theater_draft.theater_participant_snapshots(owner_id,session_id,participant_key),
  CHECK(source_kind IN ('confirmed_observation','user_report','scenario_assumption','simulation')),
  CHECK(validity IN ('valid','revoked','missing','redacted')),
  CHECK(validity<>'valid' OR (content IS NOT NULL AND selected_by_user)),
  CHECK(jsonb_typeof(source_locator)='object')
);
CREATE INDEX theater_sources_revalidation ON lw_theater_draft.theater_source_snapshots(owner_id,source_id,validity);
CREATE INDEX theater_sources_session ON lw_theater_draft.theater_source_snapshots(owner_id,session_id);

CREATE TABLE lw_theater_draft.theater_actions (
  id text PRIMARY KEY, -- 對應 actionId；雙擊／重試沿用
  owner_id text NOT NULL, -- 同場次 owner
  session_id text NOT NULL, -- 固定場次
  payload_fingerprint text NOT NULL, -- 固定 text＋recipientIds 的 canonical hash；演算法版本待定
  text text NOT NULL, -- 被接受時固定的玩家文字
  recipient_ids jsonb NOT NULL, -- 接受時固定對象；需服務核對屬同場
  status text NOT NULL DEFAULT 'accepted', -- 行動與技術嘗試狀態分開
  counted boolean NOT NULL DEFAULT true, -- 接受時計一次的候選規則
  created_at timestamptz NOT NULL, -- 接受時間
  UNIQUE(owner_id,session_id,id),
  FOREIGN KEY(owner_id,session_id) REFERENCES lw_theater_draft.theater_sessions(owner_id,id),
  CHECK(status IN ('accepted','generating','succeeded','failed','interrupted')),
  CHECK(jsonb_typeof(recipient_ids)='array')
);
CREATE INDEX theater_actions_session ON lw_theater_draft.theater_actions(owner_id,session_id,created_at,id);

CREATE TABLE lw_theater_draft.theater_attempts (
  id text PRIMARY KEY, -- 每次技術嘗試獨立 attemptId
  owner_id text NOT NULL, -- 同 action owner
  session_id text NOT NULL, -- 同 action session
  action_id text NOT NULL, -- 技術重試不新增 action
  ordinal bigint NOT NULL, -- 同 action 的第幾次嘗試
  status text NOT NULL DEFAULT 'pending', -- pending／succeeded／failed／interrupted
  epoch bigint NOT NULL, -- 此次生成接受時的 generationEpoch
  error_kind text, -- 技術失敗／拒絕／費用耗盡分類，具體碼待定
  created_at timestamptz NOT NULL, -- 嘗試開始
  finished_at timestamptz, -- 未完成可空
  UNIQUE(owner_id,session_id,action_id,id),
  UNIQUE(owner_id,session_id,action_id,ordinal),
  FOREIGN KEY(owner_id,session_id,action_id) REFERENCES lw_theater_draft.theater_actions(owner_id,session_id,id),
  CHECK(ordinal > 0 AND epoch >= 0),
  CHECK(status IN ('pending','succeeded','failed','interrupted'))
);
-- 只能限制一個尚未完成 attempt；正式工作程序還需租約／逾時／鎖定 Session。
CREATE UNIQUE INDEX theater_one_pending_attempt ON lw_theater_draft.theater_attempts(owner_id,session_id) WHERE status='pending';

CREATE TABLE lw_theater_draft.theater_events (
  id text PRIMARY KEY, -- 事件穩定 ID，展示確認重送沿用
  owner_id text NOT NULL, -- 同場次 owner
  session_id text NOT NULL, -- 固定場次
  action_id text, -- 開場系統事件可空（本文件新增假設，待核准）
  attempt_id text, -- 玩家／系統事件可空，角色生成需服務要求
  sequence bigint NOT NULL, -- 場次內展示順序，不使用 rowid
  speaker_kind text NOT NULL, -- player／participant／system，排除 Lumi
  participant_key text, -- participant 發言必須引用同場快照
  recipient_ids jsonb NOT NULL DEFAULT '[]'::jsonb, -- 角色對象不能含 Lumi 私訊
  behavior text, -- 七種角色行為碼由正式契約再固定
  text text NOT NULL, -- 不論是否展示，均為私人模擬內容
  visibility text NOT NULL DEFAULT 'queued', -- 只有 displayed 可進回顧
  displayed_at timestamptz, -- 客戶端確認展示後由伺服器記錄
  UNIQUE(owner_id,session_id,sequence),
  FOREIGN KEY(owner_id,session_id) REFERENCES lw_theater_draft.theater_sessions(owner_id,id),
  FOREIGN KEY(owner_id,session_id,action_id) REFERENCES lw_theater_draft.theater_actions(owner_id,session_id,id),
  FOREIGN KEY(owner_id,session_id,action_id,attempt_id) REFERENCES lw_theater_draft.theater_attempts(owner_id,session_id,action_id,id),
  FOREIGN KEY(owner_id,session_id,participant_key) REFERENCES lw_theater_draft.theater_participant_snapshots(owner_id,session_id,participant_key),
  CHECK(sequence > 0),
  CHECK(speaker_kind IN ('player','participant','system')),
  CHECK((speaker_kind='participant' AND participant_key IS NOT NULL) OR (speaker_kind<>'participant' AND participant_key IS NULL)),
  CHECK(attempt_id IS NULL OR action_id IS NOT NULL),
  CHECK(visibility IN ('queued','displayed','discarded')),
  CHECK((visibility='displayed' AND displayed_at IS NOT NULL) OR (visibility<>'displayed' AND displayed_at IS NULL)),
  CHECK(jsonb_typeof(recipient_ids)='array')
);
CREATE UNIQUE INDEX theater_one_player_event ON lw_theater_draft.theater_events(owner_id,session_id,action_id) WHERE speaker_kind='player' AND action_id IS NOT NULL;
CREATE INDEX theater_events_recap ON lw_theater_draft.theater_events(owner_id,session_id,visibility,sequence);

CREATE TABLE lw_theater_draft.theater_lumi_private (
  id text PRIMARY KEY, -- 私訊／建議 ID
  owner_id text NOT NULL, -- 僅 owner 可讀
  session_id text NOT NULL, -- 所屬場次
  request_id text NOT NULL, -- Lumi 重送去重；是否允許技術重試另定
  user_text text NOT NULL, -- 使用者私訊
  advice text, -- 未成功或已遮蔽可空
  status text NOT NULL, -- accepted／succeeded／failed／interrupted
  created_at timestamptz NOT NULL, -- 接受時間
  UNIQUE(owner_id,session_id,request_id),
  FOREIGN KEY(owner_id,session_id) REFERENCES lw_theater_draft.theater_sessions(owner_id,id),
  CHECK(status IN ('accepted','succeeded','failed','interrupted'))
);
CREATE INDEX theater_lumi_owner_session ON lw_theater_draft.theater_lumi_private(owner_id,session_id,created_at,id);

CREATE TABLE lw_theater_draft.theater_command_receipts (
  owner_id text NOT NULL REFERENCES lw_core_draft.users(id), -- owner 操作命名空間
  operation text NOT NULL, -- start／end／delete 等命令；不是已存在 HTTP 路由
  request_id text NOT NULL, -- 客戶端同命令重送沿用
  session_id text, -- 可保留已刪場次 ID 的追溯值，刻意無 live FK
  fingerprint text NOT NULL, -- 同 key 異內容回 409
  response jsonb NOT NULL, -- 私人成功回執；刪除流程須同步清理或遮蔽
  created_at timestamptz NOT NULL, -- 留存期限未定，不設自動 TTL
  PRIMARY KEY(owner_id,operation,request_id)
);
COMMIT;
