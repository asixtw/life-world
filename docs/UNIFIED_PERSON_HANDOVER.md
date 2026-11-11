# Unified Person 階段交接說明

更新：2026-11-11。分支 `jerry_unified_person`（不合併到 main）。這份文件給接手的開發者：這個階段做了什麼、程式在哪裡、怎麼驗證、還沒做什麼。

## 1. 這個階段完成的功能

| 功能 | 畫面 | 主要程式 |
|---|---|---|
| 人物列表、新增、編輯、封存／恢復 | `#persons`、`#persons-new`、`#persons-edit/{id}` | `app/persons.py`、`app/static/persons.js` |
| 人物設定（五區塊九欄位，每次儲存新增一版） | 人物頁「人物設定」頁籤、編輯頁 | 同上 |
| AI 產生／改善人物設定（只回填勾選的欄位，不自動儲存） | 編輯頁 | `app/person_profile_ai.py` |
| 人物關係（新增、編輯、封存、恢復；來源可引用我的紀錄與人物經歷） | 人物頁「關係」頁籤 | `app/people.py`、`app/relation_sources.py` |
| 人物經歷（新增、查看、編輯、封存、恢復） | 人物頁「經歷」頁籤、紀錄頁「人物經歷」頁籤 | `app/person_experiences.py` |
| 紀錄頁三個頁籤：我的紀錄／人物經歷／全部 | `#history`、`#history?view=people`、`#history?view=all` | `app/static/app.js`（`historyPage`）、`persons.js`（`recordsPage`） |

人物頁網址是 `#persons/{id}?tab=overview|profile|experiences|relations`。人物列表的卡片整張可點，進入人物頁；完整的編輯表單只從人物頁的「編輯人物」進入。

## 2. 資料分類原則（已裁決，請沿用）

- **我的紀錄**：使用者本人實際參與的生活紀錄。走草稿 → 核對 → 確認，會計入積分與目標。資料表 `experiences`。
- **人物經歷**：以人物為主體的經歷，使用者不必參與；性質是真實、歷史或虛構。直接儲存，不計積分、目標與互動統計。資料表 `subject_experiences`、`subject_experience_people`。
- **作品**：作品內的場景、演出職稱與演出內容。這個階段沒有動作品。人物是獨立的；作品裡的演出職稱不是人物，也不回寫人物設定。
- 共同參與不會自動建立人物關係；新增經歷不會自動修改人物設定。

## 3. 資料模型（Schema 010，這個階段沒有新增資料表或欄位）

- `people`：人物主檔（含 010 的 `aliases`、`person_type`、`person_subtype`、`description`、`origin_type`、`status`）。
- 人物設定存在 `notes`（`kind='preparation'`、`title='person_profile.v1'`），內容是 JSON：`{schema, version, previous_id, origin, generation_id, fields}`，`fields` 有九個 key：`background`、`personality`、`motivation`、`stance`、`abilities`、`expression`、`behavior`、`knowledge_boundary`、`restrictions`。
  - 只新增不更新。正式版本靠 `requests` 的回執辨識：`operation='persons:profile:{person_id}'`，`response.id` 等於那一版的 `notes.id`。沒有回執的同格式筆記只是私人筆記。
  - 欄位上限：背景 3000、性格 2000、動機／核心信念／能力／固有限制 1500、行為模式 2000、說話與表達方式 2000、知識範圍 1000。
- `person_connections`：同一對人物只有一筆；`relation_types`（最多 10 種，API 只讀寫 `kind`）、`description`（雙方共用）、`confirmation_status`（`archived` 表示封存）、`revision`。
- `person_connection_experience_sources`：關係來源，一列指向一筆我的紀錄或一筆人物經歷，`source_position` 保存順序。
- `subject_experiences`：`experience_type`（real／historical／fictional，建立後 App 不能改）、`title`、`raw_text`、`occurred_at`＋`occurred_precision`（unknown／year／month／day）、`occurred_label`、`status`、`revision`。
- `subject_experience_people`：`role` 是 `subject` 或 `participant`。一筆經歷一位主體、0 到 50 位參與人物。

## 4. API

| 方法與路徑 | 用途 |
|---|---|
| `GET/POST /api/persons`、`GET/PATCH /api/persons/{id}`、`POST /api/persons/{id}/status` | 人物列表、新增、讀取、編輯、封存／恢復 |
| `PUT /api/persons/{id}/profile` | 儲存一版人物設定（`expected_profile_id` 防覆蓋） |
| `POST /api/ai/generate`（module `person_profile`） | AI 產生人物設定候選 |
| `POST /api/people/{id}/connections`、`PATCH /api/connections/{id}` | 建立、編輯、封存、恢復關係；`source_experience_ids` 與 `source_person_experience_ids` 各自獨立 |
| `GET /api/persons/{id}/connection-sources?other_person_id=` | 可引用的來源（我的紀錄＋人物經歷） |
| `GET /api/persons/{id}/experiences` | 人物頁「經歷」頁籤的兩區資料 |
| `GET/POST /api/person-experiences`、`GET/PATCH /api/person-experiences/{id}` | 人物經歷總列表、新增、讀取、編輯、封存／恢復 |

寫入都帶 `request_id`（重送回原結果）與 `expected_revision`（版本不符回 409 `stale_revision`）。

## 5. 怎麼驗證

- 本機快速檢查（SQLite，只當輔助）：`python -m pytest -q tests`。這個階段相關的測試檔：`tests/test_persons*.py`、`tests/test_person_*.py`、`tests/test_records_page_view.py`、`tests/test_relation_sources.py`。前端畫面測試用 Node 直接執行 `app/static/persons.js`。
- 正式驗收只認 PostgreSQL：Local 8030 → Cloud Run `lw-api-main` 的 e2e 標籤 → Cloud SQL `life_world_e2e`。
  - API：`LW_E2E_PERSONS=1 python -m pytest tests/test_person*_cloudsql_e2e.py tests/test_persons_cloudsql_e2e.py`
  - Chrome：`LW_E2E_PERSONS_UI=1 python -m pytest browser_tests/test_persons*_ui.py browser_tests/test_records_page_ui.py`
  - 兩者都會建立 `persons_ui_` 開頭的合成帳號。
- 部署腳本與本機啟動器不在這個倉庫裡（在 `C:\LifeWorld_project\LifeWorld-STARTUP\`）；建置清單是 `deploy/core-e2e-build-sources.txt`，新增 `app/` 底下的檔案要加進清單。
- 最近一次的數字見 `docs/ACCEPTANCE.md` 最後一節。

## 6. 還沒做、交接清單

以下是已知但沒做的項目，原則是「先讓每個填寫入口能用，防呆之後再補」：

1. `#record`（記下經歷）的「關聯人物」下拉沒有依人物類型或封存狀態篩選；「＋ 新增人物」開的是舊的人物表單。
2. 人物經歷的性質建立後不能改（資料庫權限只允許更新標題、內容、時間與狀態）；選錯要封存後重建。
3. 人物經歷的參與人物只有連續輸入加入；依標籤全選、從內容辨識人物候選、找不到人物時保留表單內容前往新增，都還沒做。
4. 人物經歷沒有「被提及人物」「直接互動」的填寫欄位（資料表支援）。
5. 新人物頁沒有「已確認事實」「筆記」的填寫入口，仍在舊的「關係」頁（`#person/{id}`）。
6. 總覽的經歷統計、AI 依經歷建議更新人物設定，還沒做。
7. 舊的「關係」「角色」導覽入口還在。舊關係頁對已存在的關係再送一次，仍會覆蓋 label 與來源（不動描述與類型）。
8. 作品還是讀角色卡，沒有改成引用人物。
9. 已經開著的頁面不會自動換成新版程式，部署後要重新整理。
10. 沒有在 Cloud SQL 上逐一實測這個階段以外的表單（目標、角色、作品、私人筆記、個人資料）。

## 7. 資料基線：lw_user 的 15 位人物

`life_world_e2e` 的 `lw_user` 帳號有 15 位原創虛構人物（原始 15 張人物卡）。2026-11-11 提交時的狀態：

- 每位人物有第 1 版人物設定（8／9 欄，缺「能力」）；沈知衡有 1 筆用網站功能新增的人物經歷。15 位人物的總覽、人物設定、經歷、關係四個頁籤與編輯頁都已逐頁檢查，可以正常顯示。
- 第 2 版人物設定（9／9 欄）與其餘 15 筆人物經歷在 SQL 批次 `orig15-v2-20261111`，要由有資料庫權限的人在 Cloud SQL Studio 執行；提交時還沒有執行。

內容全部取自原卡、原文照錄；原卡的演出設定與工程章節沒有放進人物設定。資料檔、SQL 批次腳本、寫入前備份與對照報告含完整文字，沒有放進這個倉庫，位置在 `C:\LifeWorld_project\alpha-unification-20261110\lw_user_import\v2\`（先看 `lw_user_original15_v2_REPORT.md`）。
