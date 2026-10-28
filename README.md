# Life World · Python 本機 App

從第一顆目標蛋開始，保存真實經歷、手動確認行動貢獻，讓 Lumi 陪伴自己的成長。

這是可執行的本機 MVP，依 [最新產品決策 U-01～06](docs/context/LATEST_PRODUCT_DECISIONS_2026-10-27.md) 建立。產品決策副本隨專案保存，原有交接包與歷史檔案沒有修改。

## 啟動

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

目前支援 Python 3.9 以上；新環境建議使用仍受維護的 Python 版本。`setup.py` 會在專案內建立 `.venv` 並安裝鎖定的依賴，需要下載套件。

另選埠號或資料位置：

```bash
LIFEWORLD_DATA_DIR=/你的/私有資料夾 .venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8010
```

環境變數不會自動從 `.env` 讀取。服務預設僅監聽本機，這個版本不是公開部署的正式產品。

## 已可操作（v0.2 人物流程還原）

- 訪客開始 → 必填 Bio → 三項行動、Lv1–3 與星期規律 → 確認目標蛋 → Lumi 誕生。後端也阻止略過首次目標。
- 記錄文字、過去發生時間、選填目標與人物，保存／恢復草稿。
- 手動編輯摘要，確認小數貢獻與後續任務，再一次保存經歷與積分；相同提交重試不重複入帳。
- 訪客人物操作需要建立本機帳號；原 owner、目標、草稿與積分不變，介面保留原操作內容。
- 四主分頁：世界／目標／紀錄／關係。首頁匿名星圖，關係頁星圖／收藏冊共用搜尋、排序、關注與選取。
- 人物完整頁：人物總覽／共同經歷／合作與目標，支援多角色、標籤、分類、明確關係與目標連結。
- 興趣、飲食、專長、習慣四維度，由已確認經歷建立，附原文來源、衝突處理及資訊變更歷史；不自動猜測未知資訊。
- 真實互動按事件統計，可分類與合併；同次多筆經歷只算一次見面，分類／合併不改積分。
- 人物小劇場四用途：準備、手動演練、訊息草稿、真實相遇回顧；來源可選，私人內容不寫成真實成果，也不自動發送。
- 28 日排程預覽、獨立行動累計、待辦勾選。
- 真實 PNG／JPEG 上傳與預覽、人工確認終極成果；行動次數不會自動完成目標。
- 本機帳號登入／登出、session 撤銷、CSRF、跨帳號存取限制、SQLite 重啟後回讀。

沒有預設密碼或內建假帳號。請在介面自行建立測試用帳號。訪客若遺失 cookie，沒有身分憑證可保證找回；建立帳號後仍須自行記住本機帳號與密碼，目前沒有找回密碼功能。

## 測試

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

程式碼已補繁體中文註解；閱讀順序、各模組用途及獨立 prototype 位置見 [程式導讀與原型入口](docs/CODE_GUIDE_ZH.md)。

## 資料與設定

預設資料庫為 `data/lifeworld.sqlite3`，包含圖片證據的 BLOB，圖片不經公開靜態目錄。完整備份請使用 `scripts/backup.py`（SQLite backup API），不要在服務運作時只複製主檔而忽略 WAL。

`app/config.py` 的 `DemoPolicy` 預設每筆確認經歷 1 分、PNG／JPEG 上限 5 MiB、session 7 天；貢獻保留最多六位小數。這些是本機開發設定，**不是正式產品決策**。目前沒有負向活力衰減。

本機整理會保留原文，尚未連接外部 AI；本機帳號也未接入正式受管身份服務。積分正式數值、媒體條件、跨草稿語意重複事件的自動辨識、完成後更正，以及雲端部署須接續決定；本輪提供使用者明確合併互動事件。見 [開發政策與後續工作](docs/ROADMAP.md)。

API 規格：服務運行時 `/openapi.json`；互動文件 `/docs` 使用 FastAPI 預設外部資產，離線時可讀本機 [API 說明](docs/API.md) 與 `docs/openapi.json`。
