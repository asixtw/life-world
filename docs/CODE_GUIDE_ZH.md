# 程式碼註解與 prototype 入口

## 現行中文註解規範（2026-10-29）

1. 採「關鍵邏輯中文註解」，不再要求每行程式都有註解；簡單且語意明確的程式碼不需要註解。
2. 函式及重要模組說明用途；複雜函式補充參數、回傳值與副作用。
3. 重要業務規則、演算法、狀態轉換、例外處理及安全限制，必須保留適當的中文說明。
4. 優先解釋「為什麼這樣設計」，不逐字翻譯程式碼。
5. 保留有價值的既有註解，不無差別刪除，也不為刪註解產生大量無關 Diff。
6. 優先使用清楚的函式名稱、變數名稱與型別標註；未來新程式及有修改的相關邏輯遵循本規範。
7. 註解使用語言合法語法；跨行 SQL／HTML 模板、字串及無註解格式，在相鄰合法位置說明，不污染資料或畫面；不直接改寫第三方或自動產生檔。
8. 程式碼教學在對話中使用繁體中文解說，不把所有教學文字塞進原始碼。

本次只更新指引，不批次重寫程式或清理既有註解。開發方式依 [AGENTS](../AGENTS.md) 及[共同研發指引](PRODUCT_GUIDE.md)。下方為版本與交付歷史，不延續舊的逐行要求。

2026-10-29 v0.4 更新：[goals.py](../app/goals.py)、[goals.js](../app/static/goals.js)、[004 遷移](../app/migrations/004_goal_journey.sql)負責單一挑戰、三個習慣日期安排、到期回顧與待處理貢獻。實測 137 項後端、19 項 Chromium 通過，見[本輪驗收](GOAL_FLOW_ACCEPTANCE.md)；下方 v0.3／v0.2 數字與未重跑敘述為各次歷史紀錄。

2026-10-28 交會整合歷史：當時 App 為 v0.3.0，[connections.py](../app/connections.py)與[connections.js](../app/static/connections.js)負責逐經歷角色、配對與故事探索，[003 遷移](../app/migrations/003_connections.sql)保持舊內容相容。最新 100／14 測試與體驗量測見[交會驗收](CONNECTIONS_ACCEPTANCE.md)；下方「本次未重跑」及 81／7 是早前文件整理與 v0.2 的歷史記載。

2026-10-28 文件入口更新（歷史）：當時採逐行中文註解；此要求已由上方 2026-10-29「關鍵邏輯中文註解」取代。保留當時交付與測試記錄供追溯，不作為新程式規則。完整開發紀律見[共同研發指引](PRODUCT_GUIDE.md)，版本現況見[功能演進](EVOLUTION.md)。

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

## App 與設計參考

- **可操作 App**：[http://127.0.0.1:8000](http://127.0.0.1:8000)，啟動方式見 [README](../README.md)。正式內容由 Python／SQLite 保存。
- **設計與原型**：Connections v0.3、早期互動原型與交接包是獨立設計來源，不包含於此 App Repository。個人工作區的存放位置另行管理，不作啟動前提。
- **共同查證入口**：[人物流程還原驗收](PEOPLE_RESTORATION.md)、[交會整合驗收](CONNECTIONS_ACCEPTANCE.md)、[目標流程驗收](GOAL_FLOW_ACCEPTANCE.md)與[功能演進](EVOLUTION.md)保存可共享的結果、差異及限制。

## 此次修改的驗證

- Python：與修改前逐檔比較有效語彙及 AST，確認只增加註解，執行內容相同。
- JavaScript：核對原始程式行仍完整保留，通過兩份腳本的 Node 語法檢查。
- CSS：以實際 Chromium 比較三份樣式表的 CSSOM，解析結果相同。
- SQL：比較兩次遷移建立的資料結構，結果相同；HTML 與 TOML 也核對僅增加註解。
- 實際後端回歸測試：`.venv/bin/python -m pytest -q`，**81 passed in 4.47s**。
- 實際 Chromium 回歸測試：`.venv/bin/python -m pytest browser_tests -q -x --tb=short`，**7 passed in 26.09s**。

本次為註解與排版修改，沿用既有測試驗證，沒有更動需求或放寬斷言。
