# 程式碼註解與 prototype 入口

2026-10-27：本次替 `LifeWorld_App` 的 34 個自有程式與設定檔補上繁體中文註解，包含 Python、JavaScript、CSS、HTML、SQL、pytest、工具腳本、macOS 啟動器與 `pyproject.toml`。依賴套件、生成的 OpenAPI JSON、資料庫內容及歷史交接包維持原樣。

## 從哪裡閱讀程式

| 想了解的部分 | 主要檔案 |
|---|---|
| 啟動與服務入口 | [啟動器](../run.command)、[Python 入口](../app/__main__.py)、[API 路由](../app/main.py) |
| 目標、經歷確認與積分 | [領域服務](../app/service.py)、[輸入限制](../app/schemas.py) |
| 人物、維度、來源與互動 | [人物服務](../app/people.py)、[人物前端](../app/static/relationships.js) |
| 畫面、導覽與草稿保護 | [主前端](../app/static/app.js)、[HTML 外殼](../app/static/index.html) |
| 外觀與手機版 | [共用樣式](../app/static/styles.css)、[人物樣式](../app/static/relationships.css)、[色彩](../app/static/tokens.css) |
| 保存與升級資料 | [資料庫管理](../app/db.py)、[初始結構](../app/migrations/001_initial.sql)、[人物遷移](../app/migrations/002_people_360.sql) |
| 身分與整理服務 | [認證](../app/security.py)、[手動整理介面](../app/ai.py)、[開發設定](../app/config.py) |
| 測試、安裝與備份 | `tests/`、`browser_tests/`、`scripts/` |

註解加在可獨立閱讀的敘述末端或區塊邊界。跨行 SQL、HTML 模板與字串保留完整內容，在敘述外說明，避免註解變成使用者看得到的文字。原先壓成一行的 CSS 依規則分行，方便閱讀。

專案根目錄 `index.py`／`index.html` 是既有的 Hello World／空白範本；實際 App 入口是 `python -m app` 與 `app/static/index.html`，須透過 Python 服務開啟。

## Prototype 在哪裡

- **新版可操作 App**：[http://127.0.0.1:8000](http://127.0.0.1:8000)。需先啟動本機 Python 服務，使用 SQLite 保存資料。
- **先前暖白互動 prototype**：工作區根目錄下 `LifeWorld_Workspace_2026-10-27/01_目前工作區/互動原型_待依最新決策修訂/index.html`。此為獨立 HTML 原型，資料與新版 App 分開。
- **原交接包人物卡原型**：工作區根目錄下 `LifeWorld_Master_Handoff_v1.1_AUTH_DRAFT/person360.html`。
- **原交接包核心流程原型**：`LifeWorld_Master_Handoff_v1.1_AUTH_DRAFT/originals/01_Core_Wireframe_v0.6/prototype.html`。
- **原交接包小劇場原型**：`LifeWorld_Master_Handoff_v1.1_AUTH_DRAFT/originals/02_Theater_Wireframe_v0.1/prototype.html`。

歷史原型保留當時設計；新版人物流程的實際還原與差異見 [逐圖驗收報告](PEOPLE_RESTORATION.md)。原型檔案位於 App 儲存庫以外，因此單獨下載 GitHub 的 `LifeWorld_App` 儲存庫不會包含它們。

## 此次修改的驗證

- Python：與修改前逐檔比較有效語彙及 AST，確認只增加註解，執行內容相同。
- JavaScript：核對原始程式行仍完整保留，通過兩份腳本的 Node 語法檢查。
- CSS：以實際 Chromium 比較三份樣式表的 CSSOM，解析結果相同。
- SQL：比較兩次遷移建立的資料結構，結果相同；HTML 與 TOML 也核對僅增加註解。
- 實際後端回歸測試：`.venv/bin/python -m pytest -q`，**81 passed in 4.47s**。
- 實際 Chromium 回歸測試：`.venv/bin/python -m pytest browser_tests -q -x --tb=short`，**7 passed in 26.09s**。

本次為註解與排版修改，沿用既有測試驗證，沒有更動需求或放寬斷言。
