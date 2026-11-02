
#### B.3.1 `theater_builder_drafts`（擬議）

**來源／新增假設**：附件 §5 BuilderDraft；新增 domain、單 owner UNIQUE 為本文件提案。
**資料主權**：owner_id 是登入 owner；直接或經複合 FK 連到所屬 Session，僅本人可讀寫。
**隔離／風險**：JSON 人物／來源沒有元素 FK；建場必須重新驗證。更新草稿不得碰既有 Session。

| 欄位 | PG 候選型別 | PK | NN | Default | FK | 用途 |
|---|---|---|---|---|---|---|
| `id` | `text` | 1 | 是 | — | — | 草稿穩定識別碼，由服務生成 |
| `owner_id` | `text` | — | 是 | — | lw_core_draft.users.id | 由登入身分決定，不信任客戶端 owner |
| `revision` | `bigint` | — | 是 | `1` | — | expected_revision 比對 |
| `domain` | `text` | — | 是 | — | — | custom／demo 分域，禁止混場 |
| `stage` | `text` | — | 是 | — | — | 建立步驟；具體 enum 待 UI 契約固定 |
| `situation` | `text` | — | 是 | `''` | — | 草稿情境 |
| `purpose` | `text` | — | 是 | `''` | — | 草稿目的 |
| `person_ids` | `jsonb` | — | 是 | `'[]'::jsonb` | — | 候選人物 ID；元素仍須服務驗證 |
| `selected_source_refs` | `jsonb` | — | 是 | `'[]'::jsonb` | — | 候選來源 locator／version，尚非凍結快照 |
| `assumptions` | `jsonb` | — | 是 | `'[]'::jsonb` | — | 明示的情境假設 |
| `updated_at` | `timestamptz` | — | 是 | — | — | 服務時間，不默認採客戶端 Date.now |

**表層鍵／CHECK**（皆為候選；欄位內 PK／直接 FK 見上表）：
```sql
UNIQUE(owner_id)
CHECK(revision > 0)
CHECK(domain IN ('custom','demo'))
CHECK(jsonb_typeof(person_ids)='array')
CHECK(jsonb_typeof(selected_source_refs)='array')
CHECK(jsonb_typeof(assumptions)='array')
```

**明確索引**：
```sql
-- 無；PK／UNIQUE 自動支援索引仍存在
```

#### B.3.2 `theater_sessions`（擬議）

**來源／新增假設**：附件 §3–6 Session；schema_version、domain 與一致性 CHECK 為本文件提案。
**資料主權**：owner_id 是登入 owner；直接或經複合 FK 連到所屬 Session，僅本人可讀寫。
**隔離／風險**：單 ACTIVE/PAUSED 部分 unique 待核准；lifecycle 狀態轉移、limits JSON 內容、epoch 更新需服務交易。歷史保留原列而非另複製。

| 欄位 | PG 候選型別 | PK | NN | Default | FK | 用途 |
|---|---|---|---|---|---|---|
| `id` | `text` | 1 | 是 | — | — | 新建場次 ID，重練不能沿用 |
| `owner_id` | `text` | — | 是 | — | lw_core_draft.users.id | 私人擁有者 |
| `revision` | `bigint` | — | 是 | `1` | — | 每個成功命令遞增 |
| `schema_version` | `bigint` | — | 是 | `1` | — | 正式候選 payload 版本，不等同原型 schemaVersion=2 |
| `domain` | `text` | — | 是 | — | — | custom 或 demo |
| `lifecycle` | `text` | — | 是 | `'ACTIVE'` | — | ACTIVE／PAUSED／ENDED；歷史為 ENDED 查詢 |
| `pause_reason` | `text` | — | 否 | — | — | 暫停原因，非人物行為 |
| `scenario_snapshot` | `jsonb` | — | 是 | — | — | 建場時 situation／purpose 凍結 |
| `assumptions_snapshot` | `jsonb` | — | 是 | `'[]'::jsonb` | — | 假設不是人物正式事實 |
| `limits_snapshot` | `jsonb` | — | 是 | — | — | 玩家、角色、Lumi、技術重試上限；值需核准 |
| `generation_epoch` | `bigint` | — | 是 | `0` | — | 介入、暫停、離頁、結束使舊生成失效 |
| `input_draft` | `text` | — | 是 | `''` | — | 尚未送出的文字；不是已接受 action |
| `recipient_ids` | `jsonb` | — | 是 | `'[]'::jsonb` | — | 輸入草稿對象，以 participant_key 引用；all 需展開 |
| `created_at` | `timestamptz` | — | 是 | — | — | 建場時間 |
| `ended_at` | `timestamptz` | — | 否 | — | — | 結束時間 |
| `end_reason` | `text` | — | 否 | — | — | 結束原因字彙待正式契約固定 |

**表層鍵／CHECK**（皆為候選；欄位內 PK／直接 FK 見上表）：
```sql
UNIQUE(owner_id,id)
CHECK(revision > 0 AND schema_version > 0 AND generation_epoch >= 0)
CHECK(domain IN ('custom','demo'))
CHECK(lifecycle IN ('ACTIVE','PAUSED','ENDED'))
CHECK((lifecycle='ENDED' AND ended_at IS NOT NULL AND end_reason IS NOT NULL) OR (lifecycle<>'ENDED' AND ended_at IS NULL AND end_reason IS NULL))
CHECK(jsonb_typeof(scenario_snapshot)='object')
CHECK(jsonb_typeof(assumptions_snapshot)='array')
CHECK(jsonb_typeof(limits_snapshot)='object')
CHECK(jsonb_typeof(recipient_ids)='array')
```

**明確索引**：
```sql
CREATE UNIQUE INDEX theater_one_open_owner ON lw_theater_draft.theater_sessions(owner_id) WHERE lifecycle IN ('ACTIVE','PAUSED');
CREATE INDEX theater_owner_history ON lw_theater_draft.theater_sessions(owner_id,lifecycle,created_at DESC,id);
```

#### B.3.3 `theater_participant_snapshots`（擬議）

**來源／新增假設**：附件 §4.2／§5 ParticipantSnapshot；participant_key 是本文件場次內識別。
**資料主權**：owner_id 是登入 owner；直接或經複合 FK 連到所屬 Session，僅本人可讀寫。
**隔離／風險**：person_id 刻意無 live FK；修改名字不能覆寫快照。kind/domain 與來源 owner 必須在建場和後續生成時檢查。

| 欄位 | PG 候選型別 | PK | NN | Default | FK | 用途 |
|---|---|---|---|---|---|---|
| `owner_id` | `text` | 1 | 是 | — | lw_theater_draft.theater_sessions.owner_id（複合） | 經複合 FK 繼承場次擁有者 |
| `session_id` | `text` | 2 | 是 | — | lw_theater_draft.theater_sessions.id（複合） | 固定所屬場次 |
| `participant_key` | `text` | 3 | 是 | — | — | 場次內識別；custom/demo 明確命名空間 |
| `person_id` | `text` | — | 是 | — | — | 建場來源識別副本，刻意不是 live people FK |
| `person_version` | `text` | — | 否 | — | — | 來源提供時才填，不捏造正式 revision |
| `snapshot_version` | `bigint` | — | 是 | — | — | 快照格式版本 |
| `name` | `text` | — | 是 | — | — | 當時名字 |
| `roles` | `jsonb` | — | 是 | `'[]'::jsonb` | — | 當時角色 |
| `kind` | `text` | — | 是 | — | — | custom／demo；真實人物的模擬仍不代表本人意見 |
| `captured_at` | `timestamptz` | — | 是 | — | — | 擷取時間 |
| `availability` | `text` | — | 是 | `'available'` | — | 失效後不能注入下一輪 |

**表層鍵／CHECK**（皆為候選；欄位內 PK／直接 FK 見上表）：
```sql
PRIMARY KEY(owner_id,session_id,participant_key)
UNIQUE(owner_id,session_id,person_id)
FOREIGN KEY(owner_id,session_id) REFERENCES lw_theater_draft.theater_sessions(owner_id,id)
CHECK(snapshot_version > 0)
CHECK(kind IN ('custom','demo'))
CHECK(availability IN ('available','missing','revoked','redacted'))
CHECK(jsonb_typeof(roles)='array')
```

**明確索引**：
```sql
-- 無；PK／UNIQUE 自動支援索引仍存在
```

#### B.3.4 `theater_source_snapshots`（擬議）

**來源／新增假設**：附件 §4.2／§5 SourceSnapshot；locator 與 source_kind 正式字彙為本文件候選。
**資料主權**：owner_id 是登入 owner；直接或經複合 FK 連到所屬 Session，僅本人可讀寫。
**隔離／風險**：可空 source_id 明示上游缺正式 ID；有效快照必須有內容並被選取。不能把 invalid 標記當成刪除完成；locator 可含私人 metadata。

| 欄位 | PG 候選型別 | PK | NN | Default | FK | 用途 |
|---|---|---|---|---|---|---|
| `id` | `text` | 1 | 是 | — | — | 快照 ID，不冒充上游 sourceId |
| `owner_id` | `text` | — | 是 | — | lw_theater_draft.theater_participant_snapshots.owner_id（複合） | 同場次 owner |
| `session_id` | `text` | — | 是 | — | lw_theater_draft.theater_participant_snapshots.session_id（複合） | 凍結來源所屬場次 |
| `participant_key` | `text` | — | 是 | — | lw_theater_draft.theater_participant_snapshots.participant_key（複合） | 透過 participant 快照取得 personId |
| `source_id` | `text` | — | 否 | — | — | 上游確有穩定 ID 才填；原型單段來源可為 NULL |
| `source_locator` | `jsonb` | — | 是 | — | — | 來源表／ID／路徑及擷取限制；不能是任意 SQL |
| `source_version` | `text` | — | 否 | — | — | 上游版本若不存在保持 NULL |
| `source_kind` | `text` | — | 是 | — | — | 區分觀測、轉述、假設及 simulation |
| `content` | `text` | — | 否 | — | — | 凍結可用文字；redacted 可清空，不代表刪除流程已完成 |
| `selected_by_user` | `boolean` | — | 是 | — | — | 明確選取，不能以存在就當同意 |
| `validity` | `text` | — | 是 | `'valid'` | — | 不再有效的來源禁止再次生成 |
| `captured_at` | `timestamptz` | — | 是 | — | — | 擷取時間 |

**表層鍵／CHECK**（皆為候選；欄位內 PK／直接 FK 見上表）：
```sql
FOREIGN KEY(owner_id,session_id,participant_key) REFERENCES lw_theater_draft.theater_participant_snapshots(owner_id,session_id,participant_key)
CHECK(source_kind IN ('confirmed_observation','user_report','scenario_assumption','simulation'))
CHECK(validity IN ('valid','revoked','missing','redacted'))
CHECK(validity<>'valid' OR (content IS NOT NULL AND selected_by_user))
CHECK(jsonb_typeof(source_locator)='object')
```

**明確索引**：
```sql
CREATE INDEX theater_sources_revalidation ON lw_theater_draft.theater_source_snapshots(owner_id,source_id,validity);
CREATE INDEX theater_sources_session ON lw_theater_draft.theater_source_snapshots(owner_id,session_id);
```

#### B.3.5 `theater_actions`（擬議）

**來源／新增假設**：附件 §5 Action／§6；id 即 actionId，fingerprint 是本文件補強。
**資料主權**：owner_id 是登入 owner；直接或經複合 FK 連到所屬 Session，僅本人可讀寫。
**隔離／風險**：接受時計一次須先鎖 Session 再檢總額；same ID 不同內容衝突。counted 不得重試時清回 false。

| 欄位 | PG 候選型別 | PK | NN | Default | FK | 用途 |
|---|---|---|---|---|---|---|
| `id` | `text` | 1 | 是 | — | — | 對應 actionId；雙擊／重試沿用 |
| `owner_id` | `text` | — | 是 | — | lw_theater_draft.theater_sessions.owner_id（複合） | 同場次 owner |
| `session_id` | `text` | — | 是 | — | lw_theater_draft.theater_sessions.id（複合） | 固定場次 |
| `payload_fingerprint` | `text` | — | 是 | — | — | 固定 text＋recipientIds 的 canonical hash；演算法版本待定 |
| `text` | `text` | — | 是 | — | — | 被接受時固定的玩家文字 |
| `recipient_ids` | `jsonb` | — | 是 | — | — | 接受時固定對象；需服務核對屬同場 |
| `status` | `text` | — | 是 | `'accepted'` | — | 行動與技術嘗試狀態分開 |
| `counted` | `boolean` | — | 是 | `true` | — | 接受時計一次的候選規則 |
| `created_at` | `timestamptz` | — | 是 | — | — | 接受時間 |

**表層鍵／CHECK**（皆為候選；欄位內 PK／直接 FK 見上表）：
```sql
UNIQUE(owner_id,session_id,id)
FOREIGN KEY(owner_id,session_id) REFERENCES lw_theater_draft.theater_sessions(owner_id,id)
CHECK(status IN ('accepted','generating','succeeded','failed','interrupted'))
CHECK(jsonb_typeof(recipient_ids)='array')
```

**明確索引**：
```sql
CREATE INDEX theater_actions_session ON lw_theater_draft.theater_actions(owner_id,session_id,created_at,id);
```

#### B.3.6 `theater_attempts`（擬議）

**來源／新增假設**：附件 §5 Attempt／§6；新增 ordinal 與時間欄位供追溯。
**資料主權**：owner_id 是登入 owner；直接或經複合 FK 連到所屬 Session，僅本人可讀寫。
**隔離／風險**：只允許一個 pending 的索引不是完整生成租約；全場技術重試總額不能只用每 action ordinal 限制。

| 欄位 | PG 候選型別 | PK | NN | Default | FK | 用途 |
|---|---|---|---|---|---|---|
| `id` | `text` | 1 | 是 | — | — | 每次技術嘗試獨立 attemptId |
| `owner_id` | `text` | — | 是 | — | lw_theater_draft.theater_actions.owner_id（複合） | 同 action owner |
| `session_id` | `text` | — | 是 | — | lw_theater_draft.theater_actions.session_id（複合） | 同 action session |
| `action_id` | `text` | — | 是 | — | lw_theater_draft.theater_actions.id（複合） | 技術重試不新增 action |
| `ordinal` | `bigint` | — | 是 | — | — | 同 action 的第幾次嘗試 |
| `status` | `text` | — | 是 | `'pending'` | — | pending／succeeded／failed／interrupted |
| `epoch` | `bigint` | — | 是 | — | — | 此次生成接受時的 generationEpoch |
| `error_kind` | `text` | — | 否 | — | — | 技術失敗／拒絕／費用耗盡分類，具體碼待定 |
| `created_at` | `timestamptz` | — | 是 | — | — | 嘗試開始 |
| `finished_at` | `timestamptz` | — | 否 | — | — | 未完成可空 |

**表層鍵／CHECK**（皆為候選；欄位內 PK／直接 FK 見上表）：
```sql
UNIQUE(owner_id,session_id,action_id,id)
UNIQUE(owner_id,session_id,action_id,ordinal)
FOREIGN KEY(owner_id,session_id,action_id) REFERENCES lw_theater_draft.theater_actions(owner_id,session_id,id)
CHECK(ordinal > 0 AND epoch >= 0)
CHECK(status IN ('pending','succeeded','failed','interrupted'))
```

**明確索引**：
```sql
CREATE UNIQUE INDEX theater_one_pending_attempt ON lw_theater_draft.theater_attempts(owner_id,session_id) WHERE status='pending';
```

#### B.3.7 `theater_events`（擬議）

**來源／新增假設**：附件 §5 Event；speaker_kind、sequence、nullable action/attempt 是本文件補充，須核准。
**資料主權**：owner_id 是登入 owner；直接或經複合 FK 連到所屬 Session，僅本人可讀寫。
**隔離／風險**：CHECK 不阻止 discarded 改回 queued；帶條件 UPDATE 與 Session/attempt/epoch 核對不可省。JSON 對象必須同場；回顧只取 displayed。

| 欄位 | PG 候選型別 | PK | NN | Default | FK | 用途 |
|---|---|---|---|---|---|---|
| `id` | `text` | 1 | 是 | — | — | 事件穩定 ID，展示確認重送沿用 |
| `owner_id` | `text` | — | 是 | — | lw_theater_draft.theater_participant_snapshots.owner_id（複合） | 同場次 owner |
| `session_id` | `text` | — | 是 | — | lw_theater_draft.theater_participant_snapshots.session_id（複合） | 固定場次 |
| `action_id` | `text` | — | 否 | — | lw_theater_draft.theater_attempts.action_id（複合） | 開場系統事件可空（本文件新增假設，待核准） |
| `attempt_id` | `text` | — | 否 | — | lw_theater_draft.theater_attempts.id（複合） | 玩家／系統事件可空，角色生成需服務要求 |
| `sequence` | `bigint` | — | 是 | — | — | 場次內展示順序，不使用 rowid |
| `speaker_kind` | `text` | — | 是 | — | — | player／participant／system，排除 Lumi |
| `participant_key` | `text` | — | 否 | — | lw_theater_draft.theater_participant_snapshots.participant_key（複合） | participant 發言必須引用同場快照 |
| `recipient_ids` | `jsonb` | — | 是 | `'[]'::jsonb` | — | 角色對象不能含 Lumi 私訊 |
| `behavior` | `text` | — | 否 | — | — | 七種角色行為碼由正式契約再固定 |
| `text` | `text` | — | 是 | — | — | 不論是否展示，均為私人模擬內容 |
| `visibility` | `text` | — | 是 | `'queued'` | — | 只有 displayed 可進回顧 |
| `displayed_at` | `timestamptz` | — | 否 | — | — | 客戶端確認展示後由伺服器記錄 |

**表層鍵／CHECK**（皆為候選；欄位內 PK／直接 FK 見上表）：
```sql
UNIQUE(owner_id,session_id,sequence)
FOREIGN KEY(owner_id,session_id) REFERENCES lw_theater_draft.theater_sessions(owner_id,id)
FOREIGN KEY(owner_id,session_id,action_id) REFERENCES lw_theater_draft.theater_actions(owner_id,session_id,id)
FOREIGN KEY(owner_id,session_id,action_id,attempt_id) REFERENCES lw_theater_draft.theater_attempts(owner_id,session_id,action_id,id)
FOREIGN KEY(owner_id,session_id,participant_key) REFERENCES lw_theater_draft.theater_participant_snapshots(owner_id,session_id,participant_key)
CHECK(sequence > 0)
CHECK(speaker_kind IN ('player','participant','system'))
CHECK((speaker_kind='participant' AND participant_key IS NOT NULL) OR (speaker_kind<>'participant' AND participant_key IS NULL))
CHECK(attempt_id IS NULL OR action_id IS NOT NULL)
CHECK(visibility IN ('queued','displayed','discarded'))
CHECK((visibility='displayed' AND displayed_at IS NOT NULL) OR (visibility<>'displayed' AND displayed_at IS NULL))
CHECK(jsonb_typeof(recipient_ids)='array')
```

**明確索引**：
```sql
CREATE UNIQUE INDEX theater_one_player_event ON lw_theater_draft.theater_events(owner_id,session_id,action_id) WHERE speaker_kind='player' AND action_id IS NOT NULL;
CREATE INDEX theater_events_recap ON lw_theater_draft.theater_events(owner_id,session_id,visibility,sequence);
```

#### B.3.8 `theater_lumi_private`（擬議）

**來源／新增假設**：附件 §5 lumiPrivate／§8 SR-17；本文件獨立成表。
**資料主權**：owner_id 是登入 owner；直接或經複合 FK 連到所屬 Session，僅本人可讀寫。
**隔離／風險**：一般角色上下文與 recap 不得 JOIN；request 去重不等於內容授權。advice NULL 不代表可自動補產生或退費。

| 欄位 | PG 候選型別 | PK | NN | Default | FK | 用途 |
|---|---|---|---|---|---|---|
| `id` | `text` | 1 | 是 | — | — | 私訊／建議 ID |
| `owner_id` | `text` | — | 是 | — | lw_theater_draft.theater_sessions.owner_id（複合） | 僅 owner 可讀 |
| `session_id` | `text` | — | 是 | — | lw_theater_draft.theater_sessions.id（複合） | 所屬場次 |
| `request_id` | `text` | — | 是 | — | — | Lumi 重送去重；是否允許技術重試另定 |
| `user_text` | `text` | — | 是 | — | — | 使用者私訊 |
| `advice` | `text` | — | 否 | — | — | 未成功或已遮蔽可空 |
| `status` | `text` | — | 是 | — | — | accepted／succeeded／failed／interrupted |
| `created_at` | `timestamptz` | — | 是 | — | — | 接受時間 |

**表層鍵／CHECK**（皆為候選；欄位內 PK／直接 FK 見上表）：
```sql
UNIQUE(owner_id,session_id,request_id)
FOREIGN KEY(owner_id,session_id) REFERENCES lw_theater_draft.theater_sessions(owner_id,id)
CHECK(status IN ('accepted','succeeded','failed','interrupted'))
```

**明確索引**：
```sql
CREATE INDEX theater_lumi_owner_session ON lw_theater_draft.theater_lumi_private(owner_id,session_id,created_at,id);
```

#### B.3.9 `theater_command_receipts`（擬議）

**來源／新增假設**：附件重複開始／重送要求；本文件仿照既有 requests 增加正式候選。
**資料主權**：owner_id 是登入 owner；直接或經複合 FK 連到所屬 Session，僅本人可讀寫。
**隔離／風險**：session_id 無 FK 是為刪除後追溯；response 含私人副本，永久刪除時也須處理。成功回執不能讓被刪 Session 復活。

| 欄位 | PG 候選型別 | PK | NN | Default | FK | 用途 |
|---|---|---|---|---|---|---|
| `owner_id` | `text` | 1 | 是 | — | lw_core_draft.users.id | owner 操作命名空間 |
| `operation` | `text` | 2 | 是 | — | — | start／end／delete 等命令；不是已存在 HTTP 路由 |
| `request_id` | `text` | 3 | 是 | — | — | 客戶端同命令重送沿用 |
| `session_id` | `text` | — | 否 | — | — | 可保留已刪場次 ID 的追溯值，刻意無 live FK |
| `fingerprint` | `text` | — | 是 | — | — | 同 key 異內容回 409 |
| `response` | `jsonb` | — | 是 | — | — | 私人成功回執；刪除流程須同步清理或遮蔽 |
| `created_at` | `timestamptz` | — | 是 | — | — | 留存期限未定，不設自動 TTL |

**表層鍵／CHECK**（皆為候選；欄位內 PK／直接 FK 見上表）：
```sql
PRIMARY KEY(owner_id,operation,request_id)
```

**明確索引**：
```sql
-- 無；PK／UNIQUE 自動支援索引仍存在
```
