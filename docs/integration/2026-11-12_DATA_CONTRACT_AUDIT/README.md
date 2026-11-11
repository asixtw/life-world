# v1.1 擬真資料／Hidden AI 契約盤點

2026-11-12。產品程式基準`39af3b9866e98623e9ea873ed7a8a39d8c5dad3b`（PR #26 基本資料閉環凍結後）；附件基準`6d4ba0a3ea3d895678ad733cde2c42f773154f4f`。兩者Schema 011審查SQL相同，機器證據見[AUDIT_EVIDENCE.json](AUDIT_EVIDENCE.json)。本輪只讀附件、既有Owner快照與本機PG catalog；不匯入、呼叫模型、修改DB/權限或發布。

## 範圍與權威

最新Owner指令優先於附件建議或Jerry分支。進階劇場、人物作品、AI角色演出、完整角色創作**未核准，不列R+1/下一版/未來必做**。`works/work_versions/session_turns`等既有結構只作相容保留，不開新入口、不擴充或因而Migration；若要移除，另作資料相容審查。`subject_experiences`等既有能力也不自動變成必備素材。

程式盤點另發現`PUT /api/persons/{person_id}/profile`仍註冊，連到九項profile版本保存；UI未開不代表API已隔離。這是Gate B的範圍/相容性阻擋，須先核對既有資料與客戶端依賴，再隔離未核准的新寫入入口；本輪不刪歷史notes/設定或假稱已關閉。

私人筆記、現實情境準備、Lumi互動屬不同用途。附件S08僅為「模擬不能污染真人事實」的負例，不是劇場功能批准。`people.person_type/subtype`是必要身份/參與防護資料，不能拿來宣稱角色創作系統已核准。

Hidden Relationship Intelligence仍是已確認的MVP P0目標；**產品目標已確認、物理表/用途/啟用/發布未批准、工程未完成**必須分開。依據原`06_RELATIONSHIP_INTELLIGENCE.md`的四類有限特徵、可追溯來源、不確定性與資料治理；舊文件中的劇場提案不能推翻本次範圍裁決。附件標籤名稱及排程建議不自動成為正式ENUM/API。

## 1. Schema／工作簿比對

| 來源／比較 | 結果 | 限制與狀態 |
|---|---|---|
| 010 CSV → E2E/Alpha Owner快照 | **已測試：0欄位差異、0 FK差異**；42表、326表欄、81FK | 快照為2026-11-11，非本輪即時GCP；另有2序列，完整序列參數仍缺 |
| XLSX → 同包CSV/compact FK | **已測試：010/011全部欄、81/9 FK相同** | 10張sheet、0公式；未修改/重算/匯出工作簿 |
| 011 CSV → 本機候選PG18 catalog | **已測試：4表/63欄/9 FK，型別/欄位順序/NULL/default與FK皆0差異** | 本機18.0，不是Cloud SQL18.6套用；SQL與附件基準相同 |
| 011 → GCP快照 | **尚未部署** | 生日/任職目前值及歷史四表不存在；不能直接匯入011資料 |
| PG Feature Store | **尚未實作／待審** | 兩快照皆無relationship_features/preferences；不屬011，不能順手塞入 |
| 擬真內容 | **模板，未完成世界** | 十份content CSV均0列；P-A/P-B、E-001等尚不能對應已交付人物/事件內容 |
| Hidden示例 | **資料檢查通過，非模型驗收** | 10場景、7人工Gold、8禁止標籤、9操作步驟；actual outputs為0列 |

010欄位為text/integer/numeric/jsonb/date/timestamptz等既有實體型別，不把模板的`*_key`或意向欄當成DB欄。011採owner複合FK：人物/Owner、經歷/Owner、任職/人物/Owner；歷史另有revision唯一性。010有部分單ID FK，應用層Owner驗證不可因DB有FK就省略。工作簿/欄位CSV未完整表達CHECK、UNIQUE、索引、ACL及序列參數，不能替代DDL、最小權限與還原審查。

工作簿定位：`03_010欄位!A2:F327`、`04_011候選欄位!A2:F64`、`05_010外鍵!A2:C82`、`06_011候選外鍵!A2:C10`。CSV欄位nullable、default與timestamptz別名經明確正規化比對；不是只比行數。附件SHA256：`1de6ebd8b1c244ed55f4954de94084b29cb3b07faadb988fc9396fee07a0abca`。

## 2. 給資料製作者的輸入契約

以下保留v1.1既有欄位，不改附件；未定的映射列在第3節，未決前不能稱全量匯入契約已凍結。

| 檔案 | 穩定鍵與工程映射／限制 |
|---|---|
| people_content | person_key→唯一people ID；name不是識別碼。同名不同key不合併。角色/共同場合文字不等於互動或人格 |
| birthdays_content | person_key；year可空、月日成對、真日期，未知年2/29合法。不推年齡；空白不冒充已知日期 |
| employments_content | employment_key+person_key；公司/職稱分欄且至少一項，狀態current/past/unknown，起訖日期可空。同人多現職可並存，不自動結束舊職 |
| goals/actions_content | goal_key/action_key；status_intent及schedule_description只是製作意向，不直接改正式狀態/排程或發獎 |
| events_content | event_key、含時區occurred_at、原文保留。participants/interacted/mentioned分開，互動必須是參與的子集，提及不算出席 |
| person_facts_content | fact_key、指定person_key、四維interests/food/skills/habits、明確證據與來源；人工核對才成正式事實 |
| relationships_content | connection_key、兩位明確不同person_key、合法來源；不以名稱/標籤猜關係，也不將User↔Person隱性特徵硬塞雙Person連線 |
| tasks/notes_content | task_key/note_key及來源鍵；completion_intent不是完成收據。私人筆記/模擬不能當正式人物證據或訓練來源 |

- **CSV清單使用分號**，例如`P-A;P-B`，依工作簿`07_內容模板欄位`的participants_keys定義；其餘人物鍵清單用相同規則。若改為JSON交付，清單使用原生array；不要在CSV格內悄悄改成JSON字串或猜不同分隔符。
- 穩定映射鍵應為`(dataset_id, owner_key, entity_kind, external_key)`；dataset_version記內容版本，不因版本提升重建同一人物。不同Owner即使同key仍分離。拒絕空白/重複鍵及懸空引用，不自動大小寫合併或以姓名補配。
- 正式ID/Owner由受控Session/API及離線映射收據建立；製作者不得填Cookie、密碼、Key、DB Owner或任意正式owner_id。不得自行建立sessions、requests、data_consents、ai_generations或reward_ledger。
- 生日/任職`source_kind=manual`可自行記錄，不虛構經歷ID/本人告知；如提供證據仍須合法。`raw`必須有合法source_event_key、原文逐字quote及stated_by_person/observed_by_user/documented_source。輸入管道不等於得知依據。
- 來源版本/hash必須由確定的原文/紀錄生成，保留換行/Unicode；人物提及offset採Unicode codepoint。重複同名/片段須明確核對哪一次，不自動取第一個。
- 內容模板只供製作；重播仍須實際建草稿、人工確認與合法授權，不把review_state/consent_state文字直接插成正式狀態。重送ID依資料版本/Owner/操作穩定生成，不能重複建人/發獎。

## 3. 必須先裁決的差異，不自行改正式規則

| 差異 | 工程影響／建議處理 |
|---|---|
| 基礎模板無dataset/owner/timezone容器；Hidden檔卻有owner_key | 提案：加交付manifest容器，先凍結單世界/多Owner隔離規則；不往每張正式表加欄 |
| Hidden只有occurred_on，正式經歷要求含時區datetime | 日粒度可先作離線評測；正式重播時間需明確提供，不擅自補午夜/中午或猜時區 |
| events缺action_key/實際quantity/unit貢獻 | 不能驗目標更新。提案獨立貢獻明細，以event/action穩定鍵對應；須Owner核對，不從敘述猜數量 |
| mentioned_keys不足以決定原文稱呼/重複位置 | 需明確mention span側錄或JSON物件，不以人名第一次出現自動配對 |
| S06再引用E-001，但內容是撤回操作文字 | 這是操作，不是第二筆經歷/原文更正；source_event_key可重複引用，case_id/step_no才識別操作 |
| **S07規定本人未到場不發獎，現行Confirm每筆正式經歷固定發獎** | 阻擋自動重播：若是純第三人事件，不能經本人Confirm冒充出席。請Owner決定來源路由或測試規則；不自行取消既有獎勵政策 |
| User↔Person、Person↔Person與事件Context不同 | 四scope目標不能都映射第一位人物。User取Owner；Person取指定人；Relationship須明確雙端/情境；Context取事件/場景。配對語意需凍結 |
| 標籤字典、認知狀態與「何時正式採納」尚未成API | Gold命名是提案，不直接加入DB ENUM/正式事實；模型不得自訂Owner、profile_version或採納狀態 |
| actual_model_outputs模板缺費用/預留/來源版本/Prompt版本等欄 | 保留原模板；工程另附執行收據/envelope，與Gold分開；不能讓製作者手填成真呼叫證明 |

## 4. Hidden AI輸出／正式採納契約

[HIDDEN_AI_OUTPUT_CONTRACT.json](HIDDEN_AI_OUTPUT_CONTRACT.json)是**待審的邏輯envelope，不是已部署API/DDL**。四類scope映射`User→user`、`Person→person`、`Relationship→relationship`、`Context→context`。標籤名稱/認知狀態保留有版本字典提案，不宣稱已核准ENUM。

三層分離：

1. **Gold Labels**：人工預期/禁止結果，只作評測，不寫Feature Store或偽造模型收據。
2. **實際AI輸出**：Runtime在合法用途/來源下執行後產生候選，附Commit、dataset/model/prompt/schema版本、實際request標識、延遲/Token/費用；模型版本或費用未知保持NULL，不造版本或當0。附件目前0列，真背景AI驗收**NOT RUN**。
3. **正式採納**：由人工或另行核准的有限政策完成，Server驗Owner/指定subject/有效來源與版本，再分配profile_version/撤回狀態。不是模型自行宣告，也不代表正式person_facts或模型訓練。未有核准政策前不自動採納。

envelope的model/usage等provenance由Runtime包裝，不信任模型回傳的費用/權限。所有source_refs須在已授權集合，quote與hash/版本一致；失效就拒用。失敗/未知請求保留預留收據，reserved不等於帳單。JSON Schema不能單獨證明真模型呼叫、來源合法或跨Owner安全。

生日/任職已能正式保存不代表可傳送給背景AI；來源/欄位/提供者/用途授權仍須個別適用。背景一次同意不涵蓋未確認草稿；草稿摘要授權也不反向涵蓋背景分析。未適當授權的個人/第三人資料不得加入訓練集；現有training_opt_in固定false，不是訓練功能。

## 5. PR #26能力與工程缺口

| 項目 | 狀態／證據 |
|---|---|
| 第三步→草稿→第四步→原子Confirm→人物詳情 | **已實作、已測試：本機PG79項回歸/核心15項**；見[整合報告](../2026-11-11/INTEGRATION_RELEASE_REPORT.md)，非GCP |
| 明確身份/Owner/版本、參與與提及、生日任職/歷史、重送/回滾 | **已實作、已測試**（SQLite與本機PG）；GCP 011/最小權限待審 |
| AI有限預算/預留/本人用量、草稿明確授權/撤回 | **已實作、隔離測試**；Alpha未發布新額度/權限，非背景標籤授權完成 |
| 四類Hidden資料骨架、偏好跨Session/Owner、有限來源規則 | **部分已實作/SQLite測試**；relationship_memory.py為讀取時規則重建，非真Gemini抽取器 |
| 確認後背景觸發/排程、跨worker去重/版本更新 | **尚未實作完整流程**；Confirm未排程Hidden提取，不在每次按鍵呼叫 |
| PG Feature Store、來源hash/revision、撤回/衝突/歷史傳播 | **未完成／啟用前阻擋**；兩表未部署，011不補此缺口 |
| Gold對真模型比較、幻覺/漏標統計、真費用 | **NOT RUN**；CSV沒有provider執行證據，不能報精確率 |

### 啟用前P0審查發現（靜態程式證據，未宣稱修復）

- `relationship_memory.py::context`的records查experiences，未有背景來源撤回/有效性統一過濾；既有來源撤回API涵義不同，不能宣稱S06全傳播。現有測試只驗人物/關係來源撤回，未證明user/context不重用失效事件。
- 同函式以有效fact sources建立`confirmed_interaction`；現在人物事實可來自已確認**提及**，不能據此標成互動。啟用前須查實際角色/雙端，不以來源數推見面。
- `preferences.enabled`不等於具Provider/目的/欄位/版本的背景AI授權；AIDraftConsent只保護草稿用途。`AIRuntime`的tasks/simulation記憶注入需獨立來源/用途審查，不沿用草稿或背景開關假設通過。
- profile_version在讀取快照重建時遞增，不等於有來源版本歷史/語意衝突與削弱引擎。現有規則只看部分關鍵字/最近100筆，不能產出附件精細優先關注Gold或宣稱長期人格已學會。
- 生日/任職的撤回與歷史已可保存，但未串完整Feature Store/cache/個人化上下文失效。上述風險在功能保持未啟用時不能標成真AI已完成；仍列Gate B。

## 6. 可重現驗收與建議順序

```sh
python -m pytest tests/test_synthetic_handoff_audit.py -q
# --local-pg僅限已驗marker本機，讀catalog，不DDL/GRANT/匯入。
LIFEWORLD_INTEGRATION_PG_CONFIG=/private/tmp/lw-integration-pg18-config.json PYTHONPATH=. \
python scripts/audit_synthetic_handoff.py '<Owner提供的v1.1 ZIP路徑>' --local-pg \
 --output /private/tmp/lw-v11-audit.json
```

稽核10項測試：正向Gold與空actual；手填actual不構成真呼叫；錯scope/quote/來源/Owner；草稿/無同意/撤回；撤回操作不覆蓋原文；穩定鍵/參與互動分離；真日期；manual/raw分流；型別/NULL/default/序號漂移；輸出envelope僅候選、禁止模型指定Owner/profile_version。實際附件：0結構差異、0 Gold引用錯誤，**模板仍非可匯入世界、模型驗收NOT RUN**。收據[AUDIT_TESTS.log](AUDIT_TESTS.log)。這些是lint測試，不代替API/PG/AI背景安全E2E。

建議順序限已核准核心：先裁決第3節/補齊資料與映射 → 既有Gate B來源/授權/版本/回退審查及阻擋Bug修正 → 經獨立批准的隔離PG/受控E2E重播 → 真模型固定版本/費用收據與Gold獨立比較 → 人工Review/發布Gate。**不啟動新產品功能開發或把Jerry功能排進下一版。**

Owner需決定：資料容器/時間粒度/貢獻/提及映射；S07來源路由與獎勵預期；標籤字典、背景授權/採納政策與品質門檻。現階段不需重跑Studio SQL，不要求API Key，不執行任何正式匯入/設定。UX審查、Code Review、E2E Migration及Merge/Alpha發布仍各自獨立批准，整體維持**Draft／NO-GO**。
