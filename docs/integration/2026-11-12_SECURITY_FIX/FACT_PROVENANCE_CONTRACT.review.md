# F5｜正式四維人物來源持久化契約（審查稿，未實作／未執行 Migration）

基準f3f4c9f；2026-11-12。範圍只有interests/food/skills/habits的正式來源，不新增人物推論、背景工作或劇場。生日／任職011來源欄位保持原契約。

## 現況與決策

DraftReview已保存target、source_kind、source_sha256、quote、evidence_type；本輪獨立測試證明重登後回讀及跨Owner拒讀。正式fact_sources只有fact_id、experience_id、evidence_type、revoked_at；不能以仍存在的草稿冒充正式provenance，也不能把manual當observed_by_user。

**本輪不擅自用requests或notes塞一套隱藏人物來源資料庫，不將F5標為修復完成。** 提案核准後才擴充正式來源契約；本輪測試將正式欄位回讀標為strict XFAIL（已知缺口），不是PASS。現有payload/資料不刪、不自動回填。

## 最小保存方案（待Owner／DB審查）

優先在既有fact_sources增加目前來源的owner_id、source_kind、source_revision、source_sha256、quote、revision；另需保留逐次證據更正的不可變來源歷史。最小方案為一張append-only `fact_source_history`（候選名稱／版號待定），不因現有表已具備fact revision就宣稱來源歷史完整。也可選既有經審查稽核表，但須具備相同欄位／不可變語意；未核准前不選另一套儲存。

| 欄位 | 寫入與意義 | 回讀 |
|---|---|---|
| owner_id | 從Session取得，禁止payload重派；同Owner FK | 本人API可含或省略；查詢一律限定Owner |
| fact_id / person_id / experience_id | target person_id／client_ref在Confirm內解析為真正ID；不得取第一人或姓名 | 正式來源DTO穩定ID，可點來源 |
| source_kind | manual／raw；輸入管道，不能從evidence_type猜 | source_kind及legacy狀態 |
| source_revision | 候選對應的**草稿revision**，Confirm核對後固定；不是人物revision或來源history revision | source_revision，舊列未知為null |
| source_sha256 | Confirm實際原文UTF-8 SHA256，與候選核對值相符 | 來源指紋，不把雜湊當脫敏或授權 |
| quote | raw必須是該版原文子字串且屬合法人物來源；manual可空，不能補造 | 本人有效來源API回傳；撤回後不得給AI用 |
| evidence_type | stated_by_person／observed_by_user／documented_source，明確選擇 | 同名欄位；使用者核對不代表第三人查證 |
| revision | 每一fact/source映射的證據版本，1起，與source_revision不同 | expected_source_revision供更正／撤回防衝突 |
| confirmed_at／revoked_at | 使用者核對時間／用途撤回時間 | 有效狀態與歷史狀態分開 |
| history_id／change_kind | append-only UUID、created/corrected/source_withdrawn | 本人歷史；Runtime無UPDATE/DELETE權限 |

新候選原文、人物關聯、事實、來源目前值、來源歷史、目標／任務／獎勵及提交收據，必須在同一Confirm連線中提交；失敗全部回滾。相同request_id重送不追加歷史。既有fact同值但不同經歷要保存不同來源，不能覆寫別次來源。更正同一來源也須先保存前版，不修改歷史。

## FK／權限／舊資料相容

- owner_id回填只能從fact與experience各自Owner核對相等後取得；有異常即停止，不自動搬資料。需要 `(fact_id,owner_id)`、`(experience_id,owner_id)` 的唯一鍵／FK，先對來源快照核實已存在索引再提出增量SQL。
- history連到同Owner的fact與experience，Owner/主鍵/target不能UPDATE。Runtime只SELECT/INSERT history；目前來源僅限明確內容／版本／撤回欄位UPDATE；不得擴大Alpha網站刪除權限。
- 舊列source_kind/source_revision/quote未知時保持null並回 `provenance_status=legacy_incomplete`，不假造manual或raw、不填空字串當證據；舊列不能在AI來源路徑冒稱新契約已核對。回填策略另審，不重跑010/011。
- 增量Migration必須有PG18／DB／Marker／Owner／原Schema指紋／已存在物件檢查、完整備份與隔離還原、獨立收據。版號不預先冒用已批准011。
- 新FK會改變GuestPurger圖；在審查新FK和獨立維護帳號前維持fail-closed，不自動擴白名單。
- 舊Runtime可能用 `INSERT INTO fact_sources VALUES (...)`；加欄前先改所有寫入為具名欄位、固定相容Rollback映像、做混版演練。不得直接套表後再發現舊版不可寫。

## API Payload／回讀範例（提案，非已開放欄位）

Confirm沿用目前DraftReview的逐人target／source_kind／source_sha256／quote／evidence_type，新增正式來源版本只由伺服器決定，不從前端相信Owner。`GET /api/people/{person_id}/facts/{fact_id}/evidence`與人物overview的sources應共享同一provenance DTO；生日／任職來源維持011DTO。

```json
{
  "fact_id": "synthetic-fact-id",
  "person_id": "synthetic-person-id",
  "experience_id": "synthetic-experience-id",
  "source_kind": "raw",
  "source_revision": 3,
  "source_sha256": "<server-verified SHA256>",
  "quote": "人物本人說的原文片段",
  "evidence_type": "stated_by_person",
  "revision": 1,
  "provenance_status": "complete",
  "available_for_ai": false
}
```

available_for_ai不能只由完整欄位決定，仍需有效來源、Owner、用途授權、撤回狀態及派送前檢查；本輪人物模擬後端已封鎖，不因這份提案解鎖。

## 驗收與Owner待決

1. 本輪：草稿來源持久化／重登／Owner隔離PASS；正式來源DTO測試strict XFAIL，明示未完成。
2. 核准後：新增／同值多來源／更正history、逐人target、原文版本改動、manual/raw分離、無來源/錯人/跨Owner拒絕、冪等與全交易回滾、撤回／恢復不復活明確撤回資料、PG最小權限／Purger／舊映像相容。
3. Owner需決定是否核准上述正式來源模型與一張必要history候選表；DB審查後才寫最終Migration／GRANT審查稿。未通過前F5與Gate B保持BLOCKED。核准契約不等於核准執行任何正式SQL。

## Owner有條件核准後的四項補充（2026-11-12；尚未正式凍結）

Owner已原則同意擴充fact_sources與一張append-only fact_source_history。本節取代上文「尚待原則核准」狀態；只核准方向，**不核准新增表、Migration、GRANT或正式發布**。下列為正式凍結前待審語意，並非現有API已支援。

### 1. manual輸入與經歷證據分開

- `source_kind=manual`代表使用者手動填入資訊；`raw`代表從原文擷取並核對引用。兩者都不是證據真偽、人物本人認證、模型授權或直接互動標記。
- **本版四維人物事實仍必須至少一筆已確認經歷來源**（FactCreate.source_experience_ids）；manual也必須驗同Owner／目標人物合法關聯。沒有經歷的自由筆記不升格為fact，不擴充無來源正式人物資訊功能。
- manual的quote可空；若提供引用則也須逐字核對來源原文。不得由「我手動輸入」預設observed_by_user；evidence_type仍由使用者明確提供。raw必須有quote且為本次核對版本子字串。
- 生日／任職011允許manual且無經歷的規則，**不自動套到四維fact_sources**。這是兩個已存在的資料契約，不靠把經歷ID填假值來統一。
- 對manual無引用，也保存來源經歷SHA256及核對時間，以追溯實際引用的版本；不得聲稱整句人物資訊逐字出現在該經歷。歷史舊列不從內容猜manual/raw。

### 2. 三種版本與無草稿API

| 路徑／欄位 | source_revision（草稿） | revision（正式來源） | 核對基準 |
|---|---|---|---|
| Confirm／DraftReview | 保存驗證過的draft.revision（正整數），input_origin=draft_confirm | 每一(fact_id,experience_id)獨立1起；每次有效證據更正／撤回／恢復+1 | 原文SHA256、quote、target、Owner；人工核對不等於第三人查證 |
| 人物FactCreate等無草稿API | **null**，input_origin=person_api；不填0或捏造draft | 新來源1起；已有來源更正須expected_source_revision | 讀取不可變experiences.raw_text計SHA256；必要時另記story_revision作人物關聯快照，不把它當草稿版號 |
| 舊列 | 未知保持null，input_origin=legacy_unknown | 不改寫舊證據；遷移首次基線版1可標legacy_incomplete，其後依新規則+1 | 只有可驗證的Owner／fact／experience映射可回填；來源方式、quote及草稿版本不可猜 |

`person_facts.revision`仍是事實的樂觀版本，不能當source_revision或單一來源revision。同一事實不同來源各自有正式revision；事實級競態與來源級競態均須核對，單一交易失敗整筆回滾。experiences目前原文不可經草稿方式修改，不替它發明不存在的原文revision；未來若可改正式原文需另審，不屬本輪。

### 3. 撤回／更正／恢復狀態機

| 目前狀態 | 操作 | 結果／保護 |
|---|---|---|
| active | 一般相同內容重送 | 同request_id回原收據，不追加History／版本；不同request_id但相同證據不無故新增來源 |
| active | 明確更正證據 | 驗expected_source_revision、合法來源與採用；來源revision+1，append corrected History，保留原版 |
| active | 明確撤回 | revoked_at設伺服器時間，revision+1，append source_withdrawn；不刪經歷／來源History／獎勵 |
| withdrawn | 一般create/upsert／Confirm重送或更正 | **不得清空revoked_at**；若試圖重新採用回409 source_restore_required，或保留withdrawn而不採用；不得默默視為restore |
| withdrawn | 明確恢復（未實作的獨立動作） | 必須confirmed、request_id、expected_source_revision及重新核對當前合法來源；新revision才可使目前revoked_at=NULL並append source_restored；舊History撤回時間永久保留 |
| active或withdrawn | 故事available=false | 只改目前用途有效投影，不覆寫記錄狀態；恢復故事也不能復活recorded withdrawn |

「整筆fact狀態」由所有仍有效來源與既有衝突／封存規則決定；恢復一筆來源不得把封存fact或矛盾候選自動變成正式confirmed。`available_for_ai`必須另外查用途授權、來源可用性與派送前狀態；來源恢復不恢復已撤回的AI授權。

**已知現碼缺口**：people.py `_write_fact` 的ON CONFLICT仍會 `revoked_at=NULL`；本輪未改這條正式來源路徑，新增strict XFAIL重現，不隱瞞它。F5凍結／正式實作時必須改為上述狀態機，不能只新增欄位就宣稱解決。這也納入下一階段Gate B阻擋。

### 4. 多來源、舊資料與完整寫入路徑盤點

- 同一事實的不同experience_id各一份目前來源與各自History，不把來源A的evidence_type／quote／撤回覆蓋來源B。同一fact＋experience若從manual更正成raw，屬同一來源的新版本，不製造平行來源或重複fact。
- 多source_experience_ids的舊payload只有一個evidence_type，不能憑空為每個來源產生同一quote。新版寫入應採 `sources[]` 逐來源物件；新舊契約不可同時送兩份互相矛盾的來源，曖昧回422。
- 舊客戶端省略新來源欄位：**只讀相容與安全無損重送可保留**；不得把省略解讀為manual/raw、不得清空已有來源欄位。需要新增／更正卻缺證據者回明確契約錯誤，不自動降級覆寫。實際寫入相容策略須與固定Rollback映像一起驗收後凍結。

| 現有路徑 | 統一後應有行為（提案） |
|---|---|
| LifeWorld.confirm → legacy person_updates | 綁data.person_id及本次經歷，無新來源欄位時不猜類型；不得繞過復原確認 |
| Confirm → targeted_person_updates／DraftReview | 明確target解析、草稿revision／hash核對，逐來源寫目前值＋History，同一交易去重 |
| POST people/{pid}/facts → create_fact → _write_fact | 無草稿版號為null；逐來源核對Owner／人物關聯／證據版本；一般upsert不復活撤回來源 |
| POST facts/{fid}/resolve | 只選擇事實衝突採用，不等於恢復來源；不可代替source restore |
| POST facts/{fid}/sources/revoke | 來源revision與History同交易；最後來源失效維持既有不可用規則 |
| 新的source更正／恢復API | 尚未開放；必須獨立明確動作，不能靠create同值偷偷恢復 |
| story availability／人工角色更正 | 調整來源用途／人物關聯有效投影，保留正式原文與來源歷史，不把提及變互動 |
| GET overview／fact evidence | 同一來源DTO：當前有效狀態、recorded狀態、輸入方式、證據類型、版本、quote／hash與legacy缺口一致 |
| 生日／任職寫入 | 繼續011契約與History，不混進fact_source_history或偷塞四維欄位 |
| 匯入／後台／維護／清除 | 本輪不開新匯入或後台入口；未來不得直接SQL繞過同一驗證。Purger先驗新FK，不審不刪 |

完整程式搜尋需包含 `_write_fact`、`_apply_person_updates`、`create_fact`、`resolve_fact`、`revoke_fact_source` 及所有fact_sources INSERT/UPDATE；不能只改DraftReview新路徑而留舊API復活後門。這份表是下一批實作／Review的範圍清單，不是本輪已實作宣告。

## 正式凍結仍待決

1. 確認manual仍須經歷來源、無草稿API source_revision=null，以及逐來源 `sources[]` 寫入升級／舊客戶端拒絕策略。
2. 決定source更正／恢復的正式DTO、錯誤碼與事實／來源雙版本，不能直接沿用會清空revoked_at的upsert。
3. DB核實複合唯一鍵、來源History最小欄位、history保留／權限、Purger圖及可回讀Rollback映像後，才提交精確Migration／GRANT審查稿。Owner方向核准不等於Schema已凍結。
4. strict XFAIL保持（正式provenance缺欄＋一般upsert復活撤回來源），兩項修正後須以XPASS(strict)迫使移除預期失敗標記再正式驗收，不可改SKIP。
