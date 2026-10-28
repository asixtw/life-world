# Life World App 工作指引

更新：2026-10-28。適用本儲存庫；完整共同指引見 [PRODUCT_GUIDE](docs/PRODUCT_GUIDE.md)。本檔保留長期規則，POC 日期、人力及優先情境改在完整指引的「目前開發階段」更新。

## 開始工作

- 預設使用繁體中文。先讀 [README](README.md)、[共同研發指引](docs/PRODUCT_GUIDE.md)，再依任務核對 [U-01～06](docs/context/LATEST_PRODUCT_DECISIONS_2026-10-27.md)、[需求](docs/REQUIREMENTS.md)、[架構](docs/ARCHITECTURE.md)、[API](docs/API.md)、[後續工作](docs/ROADMAP.md)及相關程式，不要求每次通讀全部資料。
- [EVOLUTION](docs/EVOLUTION.md)記錄實作與原型演進；討論、候選模型及原型不自動視為正式需求。文件衝突須指出，不默默覆蓋已確認方向。
- 現有 App 是 Python／FastAPI、SQLite、原生 JavaScript／HTML／CSS。2026-10-28 使用者確認的暫定目標是 React＋TypeScript、保留 Python、PostgreSQL 與 GCP；目前未遷移。[三人協作基準](docs/team/BASELINE.md)區分現況與目標，[工作包](docs/team/TASK_BOARD.md)限定修改範圍；UI 第一包僅可在獨立展示目錄建立 React，不據此改寫正式程式／資料模型或新增未評審依賴。
- 團隊現為三人、沒有專職前端；產品由使用者確認，全端負責技術整合／審查，資料夥伴做資料核對與分批 AI 製作。先讀[協作入口](docs/team/README.md)，不得把文件／模擬／未執行案例標成工程完成。AI 廠商不預設。
- 團隊共用[規格索引](docs/SPEC_INDEX.md)、[存放規則](docs/STORAGE_RULES.md)與[協作規則](CONTRIBUTING.md)，以共同 Git commit 開工。公開倉庫不放真實資料、媒體、金鑰或私有備份；未決留存／刪除政策明列待決，不擅自設定自動刪除。後續工作以個別分支／PR 交付；本次使用者另行授權發布共同基準。
- 真實資料、帳號、積分及舊資料相容須保護；測試使用隔離資料，不把資料庫、憑證或真實客戶內容寫入測試證據。

## 產品不變條件

- 現實目標 → 經歷 → 人工確認 → 進度／任務／回饋為核心；努力被看見，不設寵物死亡、未登入扣分等懲罰。
- AI 是候選草稿，不虛構事實、不自行確認成果或決定獎勵；私人筆記與模擬不寫入正式事實、進度及積分。
- 參與、提及、人物配對及私人關係須分清；使用者審閱不等於第三人證實。
- 對齊既有導覽與元件，兼顧手機、桌面、空白／失敗／載入及無障礙；不以功能測試取代 UI 驗收。

## 開發與驗證

1. 先列需求、輸入／輸出、成功條件、排除範圍與正常／異常／邊界；再確認架構及必要介面。
2. Python 功能與錯誤修正先寫 pytest，再實際執行確認因缺失或行為錯誤而失敗。環境／依賴失敗不能冒充功能紅燈；必要匯入骨架不提前完成邏輯。
3. 再實作、修正、重跑及必要重構／回歸。不得偷偷改需求、刪案例、放寬斷言或跳過失敗測試；測試本身若有誤，說明修正依據。
4. 涉及權限、重送、交易或 AI 候選時驗證相應規則；前端流程補上適當瀏覽器操作及畫面驗收。純文件以內容、連結及差異檢查，不為湊 TDD 新增程式。
5. 新增及修改的自有程式、測試、腳本逐行加入有意義的繁體中文註解，優先行末。跨行字串／SQL／HTML 模板及不支援註解的格式，在相鄰合法位置逐段說明，不改資料或畫面文字；空白行、第三方、自動產生檔不直接加註解。見 [CODE_GUIDE_ZH](docs/CODE_GUIDE_ZH.md)。
6. 回報實際命令、通過／失敗／跳過數及限制；無法執行就明說，不宣稱通過或沿用歷史結果冒充本輪執行。每個主要閉環或約三個相關模組做一致性審查。

後端：`.venv/bin/python -m pytest -q`。瀏覽器：`.venv/bin/python -m pytest browser_tests -q -x --tb=short`；先依 [README](README.md)啟動隔離測試服務。結果記入 [ACCEPTANCE](docs/ACCEPTANCE.md)，實作變化更新 [EVOLUTION](docs/EVOLUTION.md)。
