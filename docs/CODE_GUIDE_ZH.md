# 程式碼註解與 prototype 入口

2026-10-28 交會整合更新：App 現為 v0.3.0，[connections.py](../app/connections.py)與[connections.js](../app/static/connections.js)負責逐經歷角色、配對與故事探索，[003 遷移](../app/migrations/003_connections.sql)保持舊內容相容。最新 100／14 測試與體驗量測見[交會驗收](CONNECTIONS_ACCEPTANCE.md)；下方「本次未重跑」及 81／7 是早前文件整理與 v0.2 的歷史記載。

2026-10-28 文件入口更新：未來新增及修改的自有程式、測試與腳本，逐行加入有意義的繁體中文註解，優先放行末；跨行字串、模板及不支援註解的格式使用相鄰合法說明，不污染資料與畫面。空白行、第三方與自動產生檔不直接加註解。完整八點 TDD 紀律見[共同研發指引](PRODUCT_GUIDE.md)，版本與原型現況見[功能演進](EVOLUTION.md)。下方保留原註解交付及當時測試結果，本次沒有重新執行產品測試。

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

- **Connections v0.3**：完整本機工作區中的 `LifeWorld_Connections_v0.3/prototype.html`，可離線開啟；來源與限制見[演進紀錄](EVOLUTION.md)。此為虛構前端示範，配對僅頁面暫存，並非 App v0.3。
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
