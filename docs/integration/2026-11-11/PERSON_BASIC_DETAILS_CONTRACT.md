# Gate B P0：人物生日與任職契約 V1

Owner於2026-11-11確認邏輯語意，取代CONTRACT_V1對公司/職稱/生日延後的規則；**實體DDL、正式Migration、UX與發布仍待各別Gate**。

- 單一people主檔，生日目前值與版本歷史分開。birth_year/month/day皆nullable，月日同有或同空，年份不能單獨存在；真正日期驗證，未知年份允許2/29，不推算年齡。
- 任職紀錄公司與職稱分欄，一筆至少一項，多份目前工作允許；新增不覆寫舊工作，不能自動結束前職。valid_from/to可空，不能補今天；有日期時結束不得早於開始。
- 基本資料與任職皆有Owner、人工確認、來源管道、得知依據、來源經歷可空、revision與異動歷史。直接輸入無經歷時可標「自行記錄」，evidence_type可以未知/NULL，不虛構observed或經歷ID；由經歷提交的事實仍依A2明確選擇證據。
- 候選與正式資料分離，AI只在有效授權時提供候選。本輪不新增真模型呼叫；讀人物頁不自動呼叫模型。不得寫入skills/tags/notes冒充基本欄位。
- 初步實體提案：person_basic_details目前生日、person_basic_detail_history更正歷史；person_employments多筆工作、person_employment_history更正歷史。這是待實況比對後審查的名稱，不是已凍結DDL；可由既有可靠稽核機制取代history表，但不能只覆寫。
- 與people、experiences用同Owner複合FK；日期、狀態、至少一欄、revision等CHECK與Owner/person查詢索引。未取得兩庫完整目錄前不出可執行正式DDL，不重跑010。

## API增量提案

GET /api/people/{id}/details 回生日、目前/歷史任職、正式事實、有效來源、必要revision。PATCH basic-details（生日）、POST employments、PATCH employments/{eid}，request_id去重、expected_revision衝突，不另建人物主檔。/api/persons採共用資料服務與相同Owner/封存限制，保留舊API。

Confirm新增 birthday_updates[] / employment_updates[]：每項target(person_id或client_ref)、source_kind、source_revision、quote、evidence_type、selected；existing需expected_revision，新工作需client_ref，不能把候選自動分給第一位人物。使用者最後確認同一交易寫新人物、經歷、生日/任職及歷史、事實/來源、任務、目標與獎勵。任何失敗全部回滾；相同request_id重送沿用原收據。

來源撤回策略：歷史保留但來源標為失效；依賴它的衍生feature失效，不自行判真偽或覆寫其他工作，正式顯示清楚待核對。直接記錄且無經歷ID的資料不受無關來源撤回影響。GuestPurger對新增FK維持fail-closed，須另審所有權與刪除順序，不能僅加入allowlist。

人物詳情可完整編輯；第三步維持收合選填、多人獨立；第四步差異與來源預覽。正式契約及交易完成並驗收後，才將已支援欄位改為會保存；Candidate不提前假裝完成。

下一步：收到E2E/Alpha只讀Snapshot→機器可讀差異分類→提出增量DDL與最小權限審查→隔離PG18驗證→經審查核准才E2E Migration。Alpha只讀，需額外DBA/Owner發布授權。

## 本機來源撤回增量（正式環境未啟用）

`POST /api/people/{id}/basic-details/source-withdrawal`、`POST /api/people/{id}/employments/{eid}/source-withdrawal` 使用 `{request_id, expected_revision, confirmed:true}`。前者作用生日目前值、後者只作用指定任職，不廣播到其他人物或工作。需正式帳號、Owner及CSRF。未勾確認422、無權404、舊版/同request不同payload409。

撤回保留值、quote及原confirmed_at，source_status改withdrawn、revision加一；同交易append-only新增source_withdrawn歷史及去重收據。相同請求回同收據；已withdrawn且使用新request/正確revision為無變更，不自動恢復來源、不重複歷史。整筆交易失敗時全部回滾。重新確認資料需既有寫入API、較新revision與使用者核對，不提供無條件恢復。

來源撤回不等於隱藏交會故事、不刪經歷、不改積分；不能把既有story availability自動當成這個撤回意圖。人物頁清楚顯示待核對。Feature Store在兩庫尚不存在；衍生特徵與AI上下文失效仍是獨立未完成Gate，本API通過不代表長期記憶已完成。
