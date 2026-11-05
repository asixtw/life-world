# Life World · Python 本機 App

> **2026-11-06 Web 串接候選：**[真正業務 UI 與唯讀 gateway](deploy/README.web-gateway.md)已完成本機隔離驗證；React gallery 保留，`/app/`／同來源 `/api` 的雲端啟用仍待指定 IAM 與 API 存取政策確認，不代表 Cloud SQL 業務讀寫已驗收。

> **2026-11-05 工程整合：**先讀[Public Alpha共同交付與未完成事項](docs/RELEASE_PUBLIC_ALPHA_20261105.md)。包含Alpha限流／預建登入與Dashboard；本機驗證通過，Docker及雲端公開驗收未完成，合併main不代表已上線。

> **2026-11-03 Step 18：** [API 雲端 e2e 準備與本機證據](docs/STEP18_API_E2E_ACCEPTANCE.md)、[Console／驗收／清理操作](deploy/README.api-e2e.md)。使用既有 lw-api-main 的 0% Tagged Revision 與獨立合成 DB；本輪只做工具及本機驗證，沒有 GCP 操作。

> **2026-11-05 CI/CD：** [Web 自動發布](deploy/README.web-main.md)、[API 自動發布](deploy/README.api-main.md)已加入候選 digest、IAM 健康檢查、指定 revision 發布、發布鎖與回滾。保留既有 React／SQLite／PG 測試；合入 main 與一次性權限核對前不代表已部署。API 正式設定隔離失敗會阻擋發布，hostfix 保留。

> **2026-11-03 Step 10-4 本機工程：** [PG18 Adapter、API Container 與 GCP 設定交接](docs/STEP10_4_PG_API_HANDOFF.md)。原 SQLite 模式保留；新 PG18 模式在獨立合成容器驗證，API 的 GCP 連線與部署尚未執行。API 建置使用 `deploy/cloudbuild.api.yaml`，不影響 React Web。

> **2026-11-02 後續審查：**[原型修正、Table Schema 與驗收界線](docs/RELEASE_REVIEW_2026-11-02.md)。SQLite 結構已獨立核對；PG／劇場新表僅草案，沒有套用實際資料庫。正式 App 與獨立 Prototype 的狀態請分別查看。

> **2026-11-01 審查快照：**請先讀[目前版本與已知問題](docs/REVIEW_CURRENT_2026-11-01.md)，內含 App／原型差異、啟動方式、審查重點及本次測試。此分支供同仁檢查，尚未合併 main 或部署。

從第一顆目標蛋開始，保存真實經歷、手動確認行動貢獻，讓 Lumi 陪伴自己的成長。

這是可執行的本機 MVP，依 [最新產品決策 U-01～06](docs/context/LATEST_PRODUCT_DECISIONS_2026-10-27.md) 建立。產品決策副本隨專案保存，原有交接包與歷史檔案沒有修改。

開發入口：[共同產品研發指引](docs/PRODUCT_GUIDE.md)、[Codex 專案規則](AGENTS.md)、[App 與原型功能演進](docs/EVOLUTION.md)。App 目前為 v0.4.0；交會已取代星圖，接入真實經歷、來源與人工人物配對。原 Connections v0.3 設計原型另外保留。

團隊先讀[共同規格入口](docs/SPEC_INDEX.md)、[檔案／素材存放規則](docs/STORAGE_RULES.md)、[分支與審查規則](CONTRIBUTING.md)，再到[三人協作入口](docs/team/README.md)領取任務與完整指令。共同起點以本次發布的 Git commit 為準；本機快照保留作歷史備份。PostgreSQL 已新增本機 PG18 Adapter；React Web main 已依使用者回報部署；API 的 GCP 建置、連線與部署仍待驗收；AI 供應商未定。文件發布不提升 App 版本，v0.4 候選的測試與待發範圍見[發布檢查](docs/GITHUB_PUBLISH_V0_4.md)；[v0.3 發布紀錄](docs/GITHUB_PUBLISH.md)保留為歷史。

**具名分工：Boyi（產品／體驗）、Jerry／jerry（全端整合／審查）、歐桑（資料庫／Pro 協作及製作）。**歐桑從[任務總入口](docs/team/PROMPT_OUSANG_START.md)讀取[完整規格 v1.1](docs/team/ART_DELIVERY_SPEC.md)及[三組十五位／可玩模組](docs/team/PROMPT_SIMULATION_001.md)。原十三類加音效第十四類，按 P0 操作核心、P1 房間／角色／美術／動效、P2 音效分批製作／審查，最後整包交齊。Boyi 已確認本機修訂；新版尚未公告／發布或完成工程驗收，既有候選先核對沿用與缺口。十五位／三封面維持 demo，封測入口與正式版保留待評估。

## 啟動

Web 展示站的 main 部署設定、私人存取與 Console 切換方式見 [Web main 部署交接](deploy/README.web-main.md)。該展示站使用獨立 React 容器，不包含 FastAPI／資料庫；本輪只在本機準備與驗證設定，沒有操作 GCP。

Jerry 的資料庫交接：[完整 Table Schema／31 表資料字典](docs/DATABASE_SCHEMA.md)、[PostgreSQL 與功能缺口規劃](docs/database/POSTGRESQL_HANDOFF.md)。依實際 SQLite 及 001–005 查核，不含使用者資料；候選新表與現有結構分開。

**最新完整流程 Wireframe：[開啟原型](collaboration/flow-wireframe/index.html)／[操作說明](collaboration/flow-wireframe/README.md)。**原型獨立呈現目前及規劃流程，全部使用虛構資料；錄音、辨識與夜間明示模擬，與實際 App 分開。習慣調整及本輪驗收見[交付紀錄](docs/HABIT_WIREFRAME_ACCEPTANCE.md)。

在這個 `LifeWorld_App` 資料夾開啟終端機：

```bash
# 本次環境已建立 .venv 並安裝套件，直接執行：
.venv/bin/python -m app
```

瀏覽器開啟 **http://127.0.0.1:8000**。macOS 也可雙擊 `run.command`。

換一台電腦或重新建立環境：

```bash
python3 scripts/setup.py
.venv/bin/python -m app
```

目前支援 Python 3.9 以上；新環境建議使用仍受維護的 Python 版本。`setup.py` 會在專案內建立 `.venv` 並安裝鎖定的依賴，需要下載套件；環境讓 `requirements.lock` 成為唯一來源，基礎 Python 被移除時會重建 `.venv`，不在鎖定檔內的套件也會被移除，手動裝進 `.venv` 的套件不會保留。可用 `python scripts/setup.py --check`（以 `.venv` 的 Python 執行）確認環境與鎖定一致。

另選埠號或資料位置：

```bash
LIFEWORLD_DATA_DIR=/你的/私有資料夾 .venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8010
```

環境變數不會自動從 `.env` 讀取。服務預設僅監聽本機，這個版本不是公開部署的正式產品。

## 本輪素材流程增量（本機，尚未發布）

已接入真實錄音、圖片／截圖／拍照／名片／音檔選取、本機預覽與草稿接續、人工校對及同裝置來源回看。選取不自動上傳，錄完後明確「上傳並轉文字」，試聽可選。素材保存在此裝置，未同步雲端；辨識服務商未設定，預設明確回覆不可用，仍可手動整理。

[本輪驗收](docs/MEDIA_COMPONENTS_ACCEPTANCE.md)／[Jerry 與歐桑的元件、狀態及辨識契約](docs/team/MEDIA_COMPONENT_CONTRACT.md)。原四分頁與視覺保留，月份安排沿用既有真實日期元件；未將 React gallery 或測試控制列併入產品。

## 已可操作（v0.4.0）

- 訪客開始 → 必填 Bio → 目標命名／成果與截止日 → 三個習慣及月／週日期安排 → 核對 → 目標蛋與首次 Lumi；後端阻止略過首次目標或同時啟動第二個。
- 記錄文字、過去發生時間、選填目標與人物，保存／恢復草稿。
- 手動編輯摘要，確認小數貢獻與後續任務，再一次保存經歷與積分；相同提交重試不重複入帳。
- 訪客人物操作需要建立本機帳號；原 owner、目標、草稿與積分不變，介面保留原操作內容。
- 四主分頁：世界／目標／紀錄／關係。首頁與關係頁由交會取代星圖，保留收藏冊的搜尋、排序、關注與選取。
- 交會以已審閱故事為中心，可沿參與者延伸、查看原文來源、人工配對同名提及及返回上一段。配對保存於 SQLite，提及不計見面或獎勵。
- 經歷可選填整理多位參與者、直接互動與原文提及。舊經歷仍保存，先從「等待核對的舊經歷」或紀錄內的來源入口確認角色。
- 人物完整頁：人物總覽／共同經歷／合作與目標，支援多角色、標籤、分類、明確關係與目標連結。
- 興趣、飲食、專長、習慣四維度，由已確認經歷建立，附原文來源、衝突處理及資訊變更歷史；不自動猜測未知資訊。
- 真實互動按事件統計，可分類與合併；同次多筆經歷只算一次見面，分類／合併不改積分。
- 人物小劇場四用途：準備、手動演練、訊息草稿、真實相遇回顧；來源可選，私人內容不寫成真實成果，也不自動發送。
- 真實日期月／週排程、星期快選與單日調整；每次預期量預設 1 次，既有行動總量與進度保留。
- 到期先回顧，選擇延長、成果完成或結束；待處理貢獻逐筆採計且不重複發獎。已完成與曾經挑戰各自收藏，舊目標先補設定。
- 真實 PNG／JPEG 上傳與預覽、人工確認終極成果；行動次數不會自動完成目標。
- 本機帳號登入／登出、session 撤銷、CSRF、跨帳號存取限制、SQLite 重啟後回讀。

沒有預設密碼或內建假帳號。請在介面自行建立測試用帳號。訪客若遺失 cookie，沒有身分憑證可保證找回；建立帳號後仍須自行記住本機帳號與密碼，目前沒有找回密碼功能。

## 測試

v0.4 本輪實測：137 項後端、19 項 Chromium 通過；完整命令、跨日測試啟動方式、手機／桌面截圖及限制見[單一目標驗收](docs/GOAL_FLOW_ACCEPTANCE.md)。一般瀏覽器命令未提供測試時鐘時，跨日案例會明確跳過，不能宣稱完整 19 項通過。

```bash
# API、資料庫、交易與邊界測試
.venv/bin/python -m pytest -q

# 瀏覽器測試：先在另一個終端機啟動隔離測試資料的服務
LIFEWORLD_DATA_DIR=/tmp/lifeworld-browser-test .venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8001

# 安裝 Chromium（目前這台電腦已存在）
.venv/bin/python -m playwright install chromium

# 然後執行真實瀏覽器旅程
.venv/bin/python -m pytest browser_tests -q
```

瀏覽器測試使用全新 browser context 與虛構內容，預設網址 `http://127.0.0.1:8001`；可用 `LIFEWORLD_TEST_URL` 改變。請勿指向正式系統。詳細執行紀錄見 [TDD 與驗收](docs/ACCEPTANCE.md)。

## 專案結構

```text
LifeWorld_App/
├── app/
│   ├── __main__.py        本機啟動入口
│   ├── main.py            FastAPI、路由、錯誤與安全標頭
│   ├── schemas.py         輸入格式與邊界驗證
│   ├── service.py         目標、草稿、確認、積分、人物、佐證與筆記
│   ├── db.py              SQLite 連線、migration、交易
│   ├── config.py          明示的開發政策
│   ├── security.py        Argon2、session 與人物帳號門檻
│   ├── ai.py              整理 provider 介面與手動退路
│   ├── errors.py          可識別的領域錯誤
│   ├── migrations/        版本化資料表
│   └── static/            繁體中文響應式介面，無 Node 建置
├── tests/                 pytest API／交易／邊界／回歸測試
├── browser_tests/         pytest + Chromium 真實旅程
├── scripts/               安裝、OpenAPI 匯出、資料庫備份
├── data/                  本機 SQLite，已排除版本控制
├── docs/                  需求、架構、API、測試證據及後續工作
├── pyproject.toml
├── requirements.txt       本輪驗證的 runtime 依賴
├── requirements.lock      本輪完整測試環境鎖定版本
├── run.command            macOS 啟動器
└── .gitignore
```

本輪逐圖驗收與差異見 [人物流程還原報告](docs/PEOPLE_RESTORATION.md)，截圖使用虛構測試資料。

程式碼已補繁體中文註解；閱讀順序、各模組用途及設計參考界線見 [程式導讀與原型入口](docs/CODE_GUIDE_ZH.md)。

## 資料與設定

預設資料庫為 `data/lifeworld.sqlite3`，包含圖片證據的 BLOB，圖片不經公開靜態目錄。完整備份請使用 `scripts/backup.py`（SQLite backup API），不要在服務運作時只複製主檔而忽略 WAL。

`app/config.py` 的 `DemoPolicy` 預設每筆確認經歷 1 分、PNG／JPEG 上限 5 MiB、session 7 天；貢獻保留最多六位小數。這些是本機開發設定，**不是正式產品決策**。目前沒有負向活力衰減。

本機整理會保留原文，尚未連接外部 AI；本機帳號也未接入正式受管身份服務。積分正式數值、媒體條件、跨草稿語意重複事件的自動辨識、完成後更正，以及雲端部署須接續決定；本輪提供使用者明確合併互動事件。見 [開發政策與後續工作](docs/ROADMAP.md)。

API 規格：服務運行時 `/openapi.json`；互動文件 `/docs` 使用 FastAPI 預設外部資產，離線時可讀本機 [API 說明](docs/API.md) 與 `docs/openapi.json`。

## v0.3 歷史驗收與體驗

當時實際結果：100 項後端、14 項 Chromium 旅程通過；手機／桌面來源、配對、返回、草稿、既有功能與慢網路均有測試。詳見[整合與體驗報告](docs/CONNECTIONS_ACCEPTANCE.md)，包含 300 人／103 段故事的量測與限制。

重做效能驗收時，先啟動上方 **8001 的隔離虛構資料服務**，在 App 根目錄執行 `.venv/bin/python scripts/audit_experience.py`。工具會建立虛構帳號、300 人與 103 段故事，不應對正式資料服務執行。
