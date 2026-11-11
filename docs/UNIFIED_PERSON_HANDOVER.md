# Unified Person 階段交接說明

更新：2026-11-11（第四輪，依獨立驗收修正）。分支 `jerry_unified_person`（不合併到 main）。這份文件給接手的開發者：這個階段做了什麼、程式在哪裡、怎麼驗證、還沒做什麼。

## 1. 這個階段完成的功能

| 功能 | 畫面 | 主要程式 |
|---|---|---|
| 人物列表、新增、編輯、封存／恢復 | `#persons`、`#persons-new`、`#persons-edit/{id}` | `app/persons.py`、`app/static/persons.js` |
| 人物設定（五區塊九欄位，每次儲存新增一版） | 人物頁「人物設定」頁籤、編輯頁 | 同上 |
| AI 產生／改善人物設定（只回填勾選的欄位，不自動儲存） | 編輯頁 | `app/person_profile_ai.py` |
| 人物關係（新增、編輯、封存、恢復；來源可引用我的經歷與人物經歷） | 人物頁「關係」頁籤 | `app/people.py`、`app/relation_sources.py` |
| 人物經歷（新增、查看、編輯、封存、恢復；可加參與人物） | 人物頁「經歷」頁籤、紀錄頁「人物經歷」頁籤 | `app/person_experiences.py` |
| 紀錄頁三個頁籤：我的經歷／人物經歷／全部 | `#history`、`#history?view=people`、`#history?view=all` | `app/static/app.js`（`historyPage`）、`persons.js`（`recordsPage`） |
| 記下我的經歷時，「關聯人物」只列使用中的真實人物（不含歷史人物與虛構人物） | `#record`、`#review/{id}` | `app/static/app.js`（`personField`）、`persons.js`（`recordableIds`） |
| 我的設定（使用者本人的設定，AI 扮演「我」時使用） | 人物首頁最上方的卡片、右上角帳號視窗的「我的設定」按鈕 → `#persona` | `app/self_persona.py`、`app/static/works.js`（`personaView`）、`persons.js`（`selfCard`、`accountEntry`） |
| 左側導覽：世界／目標／紀錄／人物／作品 | 全站 | `app/static/app.js`（`navigation`）、`persons.js`（`legacyNav`） |

人物頁網址是 `#persons/{id}?tab=overview|profile|experiences|relations`。人物列表的卡片整張可點，進入人物頁；完整的編輯表單只從人物頁的「編輯人物」進入。

兩條主要的填寫流程（2026-11-11 第三輪定案）：

- **人物 → 我的設定**：進入「人物」，最上方是「我的設定」卡片（還沒建立時是「建立我的設定」），下面才是搜尋與人物列表。搜尋、篩選、翻頁或看封存時不顯示這張卡片。我的設定頁歸在「人物」底下，返回連結回人物首頁。
- **紀錄 → 我的經歷**：進入「紀錄」，第一個頁籤是「我的經歷」→「＋ 新的經歷」→ 記下 → 核對 → 確認 → 回到我的經歷。

畫面上的名稱在這一輪改過：「我的紀錄」改稱「我的經歷」，「我的人設」的頁面與入口改稱「我的設定」。程式、API 與資料表的名稱沒有改（`experiences`、`self_persona`、`/api/self-persona`）；後端的同意文字與作品建立流程裡仍寫「我的人設」，我的設定頁上有一行說明兩者是同一份資料。

左側導覽在人物系統可用時不再列出舊的「關係」「角色」。這兩個頁面沒有刪除：`#people`、`#person/{id}`、`#characters` 仍可由網址進入，作品建立流程裡也有前往角色卡的連結。人物系統不可用（資料庫還沒升到 010、或不是以 `link_table` 部署）時，導覽維持原本的入口。

## 2. 資料分類原則（已裁決，請沿用）

- **我的經歷**（2026-11-11 前畫面上稱為「我的紀錄」）：使用者本人實際參與的生活紀錄。走草稿 → 核對 → 確認，會計入積分與目標。只能關聯真實人物。資料表 `experiences`。
- **人物經歷**：以人物為主體的經歷，使用者不必參與；性質是真實、歷史或虛構。直接儲存，不計積分、目標與互動統計。資料表 `subject_experiences`、`subject_experience_people`。
- **我的設定**（資料上的名稱是「我的人設」）：使用者本人的設定，給 AI 扮演「我」時使用。一個帳號一份，每次保存新增一版，要另外按「我同意」才會送給 AI。資料表 `works`、`work_versions`（`kind='self_persona'`）、`data_consents`。
- **作品**：作品內的場景、演出職稱與演出內容。這個階段沒有動作品。人物是獨立的；作品裡的演出職稱不是人物，也不回寫人物設定。
- 共同參與不會自動建立人物關係；新增經歷不會自動修改人物設定。

## 3. 資料模型（Schema 010，這個階段沒有新增資料表或欄位）

- `people`：人物主檔（含 010 的 `aliases`、`person_type`、`person_subtype`、`description`、`origin_type`、`status`）。
- 人物設定存在 `notes`（`kind='preparation'`、`title='person_profile.v1'`），內容是 JSON：`{schema, version, previous_id, origin, generation_id, fields}`，`fields` 有九個 key：`background`、`personality`、`motivation`、`stance`、`abilities`、`expression`、`behavior`、`knowledge_boundary`、`restrictions`。
  - 只新增不更新。正式版本靠 `requests` 的回執辨識：`operation='persons:profile:{person_id}'`，`response.id` 等於那一版的 `notes.id`。沒有回執的同格式筆記只是私人筆記。
  - 欄位上限：背景 3000、性格 2000、動機／核心信念／能力／固有限制 1500、行為模式 2000、說話與表達方式 2000、知識範圍 1000。
- `person_connections`：同一對人物只有一筆；`relation_types`（最多 10 種，API 只讀寫 `kind`）、`description`（雙方共用）、`confirmation_status`（`archived` 表示封存）、`revision`。
- `person_connection_experience_sources`：關係來源，一列指向一筆我的經歷或一筆人物經歷，`source_position` 保存順序。
- `subject_experiences`：`experience_type`（real／historical／fictional，建立後 App 不能改）、`title`、`raw_text`、`occurred_at`＋`occurred_precision`（unknown／year／month／day）、`occurred_label`、`status`、`revision`。
- `subject_experience_people`：`role` 是 `subject` 或 `participant`。一筆經歷一位主體、0 到 50 位參與人物。
- 我的人設的內容（`work_versions.content_json`）有十二欄加真實程度：`display_name`、`public_profile`、`personality`、`speaking_style`（四欄必填）、`motivation`、`values`、`behavior`、`knowledge`、`relationships`、`boundaries`、`appearance`、`sample_lines`（最多 3 句）、`truth_level`（real／mixed／ideal）。欄位名稱和人物設定的九欄不同，兩者沒有合併。

## 4. API

| 方法與路徑 | 用途 |
|---|---|
| `GET/POST /api/persons`、`GET/PATCH /api/persons/{id}`、`POST /api/persons/{id}/status` | 人物列表、新增、讀取、編輯、封存／恢復 |
| `PUT /api/persons/{id}/profile` | 儲存一版人物設定（`expected_profile_id` 防覆蓋） |
| `POST /api/ai/generate`（module `person_profile`） | AI 產生人物設定候選 |
| `POST /api/people/{id}/connections`、`PATCH /api/connections/{id}` | 建立、編輯、封存、恢復關係；`source_experience_ids` 與 `source_person_experience_ids` 各自獨立 |
| `GET /api/persons/{id}/connection-sources?other_person_id=` | 可引用的來源（我的經歷＋人物經歷） |
| `GET /api/persons/{id}/experiences` | 人物頁「經歷」頁籤的兩區資料 |
| `GET/POST /api/person-experiences`、`GET/PATCH /api/person-experiences/{id}` | 人物經歷總列表、新增、讀取、編輯、封存／恢復 |
| `GET/PUT /api/self-persona`、`POST /api/self-persona/consent` | 讀取、保存我的人設（已有人設時要帶 `expected_revision`）；同意或撤回給 AI 使用 |

寫入都帶 `request_id`（重送回原結果）與 `expected_revision`（版本不符回 409）。

### 資料完整性的後端規則（2026-11-11 第四輪修正）

| 規則 | 在哪裡檢查 | 不符合時 |
|---|---|---|
| 我的經歷的關聯人物與故事參與人物，只能是使用中的真實人物（歷史人物、虛構人物一律拒絕） | `service.py` 的 `_recordable_person`，由 `_related`（草稿建立、草稿修改、確認）與 `connections.py` 的 `_validate_story` 呼叫 | 422 `person_not_recordable`；人物已封存回 409 `person_archived`。拒絕發生在寫入之前，不會留下草稿、經歷、積分或目標進度 |
| 被人物關係引用為來源的人物經歷，不能封存，也不能把參與人物改到和那段關係無關 | `person_experiences.py` 的 `patch_person_experience` → `relation_sources.require_still_related` | 409 `relation_source_in_use`，訊息會指出是哪一段關係；經歷、關係、來源都不變 |
| 被人物關係引用為來源的我的經歷，更正故事參與人物後仍要和那段關係有關 | `connections.py` 的 `edit_story_people` → 同一個檢查 | 同上 |

補充：

- 名單裡只要有一位不合規，整筆請求拒絕，不會部分成功。
- 已經確認的舊經歷不追溯：更正舊故事時，原本就在名單裡的人物可以留著，但不能再加入不合規的人物。
- 人物類型是 Schema 010 的欄位，所以第一條規則只在 `link_table` 模式生效；舊結構沒有類型可查，維持原行為。
- 使用者要先到那段關係移除來源，才能封存或修改經歷。已封存的關係也算引用。
- 前端的篩選（記下經歷時只列真實人物）只是方便選擇，不是防護。

## 5. 怎麼驗證

- 本機快速檢查（SQLite，只當輔助）：`python -m pytest -q tests --ignore=tests/product/test_google_verifier.py --ignore=tests/product/test_staging_iap_config.py`（這兩個檔案需要本機沒有安裝的 Google 驗證套件）。這個階段相關的測試檔：`tests/test_persons*.py`、`tests/test_person_*.py`、`tests/test_records_page_view.py`、`tests/test_relation_sources.py`、`tests/test_nav_and_self_persona_view.py`、`tests/test_persona_works.py`。前端畫面測試用 Node 直接執行 `app/static/persons.js`。
- 正式驗收只認 PostgreSQL：Local 8030 → Cloud Run `lw-api-main` 的 e2e 標籤 → Cloud SQL `life_world_e2e`。
  - API：`LW_E2E_PERSONS=1 LW_E2E_RELATION_SOURCES=1 python -m pytest tests/test_person*_cloudsql_e2e.py tests/test_persons_cloudsql_e2e.py tests/test_relation_sources_cloudsql_e2e.py tests/test_self_persona_cloudsql_e2e.py`
  - Chrome：`LW_E2E_PERSONS_UI=1 python -m pytest browser_tests/test_persons*_ui.py browser_tests/test_records_page_ui.py browser_tests/test_self_persona_entry_ui.py`
  - 兩者都會建立 `persons_ui_` 開頭的合成帳號。
- 部署腳本與本機啟動器不在這個倉庫裡（在 `C:\LifeWorld_project\LifeWorld-STARTUP\`）；建置清單是 `deploy/core-e2e-build-sources.txt`，新增 `app/` 底下的檔案要加進清單。
- 最近一次的數字見 `docs/ACCEPTANCE.md` 最後一節。

## 6. 還沒做、交接清單

以下是已知但沒做的項目，原則是「先讓每個填寫入口能用，防呆之後再補」：

1. `#record`（記下經歷）的「＋ 新增人物」開的是舊的人物表單。「關聯人物」下拉只列使用中的真實人物，這是前端另外讀一次人物列表做的篩選，真實人物超過 100 位或讀取失敗時會退回不篩選；不合規的人物送出時由後端拒絕（見第 4 節的後端規則）。
1a. 人物建立我的經歷之後，仍然可以把人物類型改成歷史或虛構，或把人物封存；既有的我的經歷不會被擋下或改動。這條路徑這一輪沒有處理。
2. 人物經歷的性質建立後不能改（資料庫權限只允許更新標題、內容、時間與狀態）；選錯要封存後重建。
3. 人物經歷的參與人物只有連續輸入加入；依標籤全選、從內容辨識人物候選、找不到人物時保留表單內容前往新增，都還沒做。
4. 人物經歷沒有「被提及人物」「直接互動」的填寫欄位（資料表支援）。
5. 新人物頁沒有「已確認事實」「筆記」的填寫入口；它們只在舊的關係頁（`#person/{id}`），而舊關係頁現在沒有導覽入口，只能由網址進入。
6. 總覽的經歷統計、AI 依經歷建議更新人物設定，還沒做。
7. 舊關係頁對已存在的關係再送一次，仍會覆蓋 label 與來源（不動描述與類型）。
8. 作品還是讀角色卡，沒有改成引用人物；角色卡頁（`#characters`）沒有導覽入口，由作品建立流程的連結或網址進入。
9. 我的設定和人物設定是兩套欄位、兩種儲存方式。「我」在人物首頁只是一張卡片，不是人物列表裡的一筆人物，所以不能當人物經歷的主體或參與人物、不能和人物建立關係。
10. 舊的瀏覽器測試（`browser_tests/test_character_cards_ui.py`、`test_connections.py`、`test_people.py`）靠點擊導覽的「關係」「角色」進入頁面；在人物系統啟用的環境要改成由網址進入才能執行。這一輪沒有修改也沒有執行它們。
11. 已經開著的頁面不會自動換成新版程式，部署後要重新整理。
12. 沒有在 Cloud SQL 上逐一實測這個階段以外的表單（目標、角色、作品、私人筆記、個人資料）。

## 7. 資料基線：lw_user 的 15 位人物

`life_world_e2e` 的 `lw_user` 帳號有 15 位原創虛構人物（原始 15 張人物卡）。2026-11-11 的狀態：

- 每位人物都有第 2 版人物設定（9／9 欄），第 1 版保留為前一版。第 2 版把原卡的章節整段放進來，獨立驗收指出其中混入了場次狀態、演出指令與系統規則。
- 第 3 版已經準備好（批次 `orig15-v3-20261111`）：把第 2 版逐句分類，排除場次狀態、場次專屬的關係狀態、系統與工程規則、演出控制指令，共 402 句，其餘原文保留，只刪不改。第 3 版已在 2026-11-11 執行並核對：15 位人物的最新版都是第 3 版（9／9 欄），第 1、2 版保留，原有人物備註沒有變動。
- 人物經歷 20 筆。16 筆取自原卡（每位 1 到 2 筆，沒有參與人物、日期不確定）；另外 4 筆是為了展示多人參與而寫的範例，內容開頭標了「（範例資料）」，原卡裡沒有。
- 人物關係 6 筆，全部是範例（說明開頭標了「（範例資料）」），其中 5 筆引用了上面的範例經歷當來源。原卡沒有寫這 15 位人物彼此的關係。
- 我的設定已填（第 1 版，十二欄），內容是範例，每欄開頭標了「（範例資料）」；沒有替這個帳號按同意，所以 AI 還不能使用它。
- 我的經歷 3 筆，都是範例（內容開頭標了「（範例資料）」），其中 1 筆是用網站的「記下 → 核對 → 確認」流程建立的；這 3 筆讓這個帳號有 3 點積分，目標的每日行動也有了進度。
- 另有 1 位範例真實人物「阿哲（範例）」，用來展示我的經歷可以關聯真實人物；其中 1 筆我的經歷關聯了他。

資料檔、SQL 批次腳本、寫入前備份與對照報告含完整文字，沒有放進這個倉庫，位置在 `C:\LifeWorld_project\alpha-unification-20261110\lw_user_import\`：`v2\`（先看 `lw_user_original15_v2_REPORT.md`）與 `v3\`（先看 `lw_user_original15_v3_REPORT.md`，逐句對照在 `lw_user_original15_v3_MAPPING.md`）。

## 8. Alpha 資料庫的 010 升級

`life_world_alpha` 已在 2026-11-11 升到 010（Jerry 以 `postgres` 執行）。升級後核對：42 張表、326 個欄位、81 條外鍵、88 個索引，和 `life_world_e2e` 的結構一致。升級腳本的審視結果、實際採用的腳本與核對查詢在倉庫外：`C:\LifeWorld_project\alpha-unification-20261110\alpha_migration_010_review\`（先看 `ALPHA_MIGRATION_010_REVIEW_20261111.md`）。

Alpha 的網站（Cloud Run `lw-public`）還是舊程式。升級後做過唯讀檢查：`/ready`、`/health`、`/api/capabilities`、首頁都回 200；會寫入的功能沒有在 Alpha 上實測。

還要注意兩件事：

- Alpha 現行的舊程式（revision `lw-public-camera-8f377fa`；相關檔案和 `68102f2` 相同）的訪客清除工作（`app/guest_maintenance.py` → `GuestPurger._purge`）會因為外鍵與表清單改變而拒絕執行（`unreviewed_fk`、`unreviewed_table`）；這個分支的程式兩種結構都支援（`app/guest_fk.py` 的 `CONTRACTS`）。網站本身不做這個檢查，推論可以繼續用舊程式，但沒有實測。
- 要在 Alpha 使用這個分支的人物功能，除了換程式，還要以 `link_table` 的關係來源設定部署（和 E2E 相同），否則 `/api/persons` 會回 `unified_people_not_enabled`。
