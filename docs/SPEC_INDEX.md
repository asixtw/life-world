# 共同規格入口

更新：2026-10-28。適用 `asixtw/life-world` 全體協作者。本文索引、產品基準、規則與任務均隨儲存庫保存，可直接在 GitHub 閱讀，不需取得產品負責人的完整桌面工作區。


## 依序閱讀

| 文件 | 用途與狀態 |
|---|---|
| [產品基準](PRODUCT_BASELINE.md) | 共用名詞、核心旅程、不變條件、已實作與缺口 |
| [共同研發指引](PRODUCT_GUIDE.md) | 十一節產品／設計原則、TDD 與中文註解規則 |
| [存放規則](STORAGE_RULES.md) | 程式、規格、素材、使用者資料與秘密的存放邊界 |
| [協作規則](../CONTRIBUTING.md) | 分支、共同 commit、PR、規格變更及驗收 |
| [三人分工與任務](team/README.md) | 主責、工作包、可複製提示詞及第一輪交付 |
| [歐桑完整交付入口](team/PROMPT_OUSANG_START.md) | Boyi 已通知並定案的具名任務、VS Code／Codex 工作方式與整包交付 |
| [LW-SIM-001](team/PROMPT_SIMULATION_001.md) | 三組十五位資料、可玩劇場、來源／評估／整合介面；成果尚未交付 |
| [完整 UI／美術／動效](team/ART_DELIVERY_SPEC.md) | 十三類資產／元件、App 圖示／縮圖、蛋與破蛋／轉場，歐桑本輪一次交齊 |
| [流程與狀態](team/FLOWS_AND_STATES.md) | 排程、登入、錄音與夜間的後續行為規格；未實作部分明示 |
| [API](API.md)／[OpenAPI](openapi.json)／[架構](ARCHITECTURE.md) | 現有可執行服務；未來 React／PG 契約由全端另審 |
| [演進](EVOLUTION.md)／[驗收](CONNECTIONS_ACCEPTANCE.md)／[發布檢查](GITHUB_PUBLISH.md) | 實作與證據；歷史結果不替代本輪測試 |

## 決策狀態與變更

| 狀態 | 本次基準 |
|---|---|
| 已確認產品原則 | 真實經歷、人工確認、可追溯來源、人物選填、首次目標後才有 Lumi、去重與權限、不因缺席懲罰 |
| 已確認本輪任務 | Boyi 產品／驗收、Jerry 全端整合／審查、歐桑資料庫／Pro 協作；完整模擬人物及 UI／美術包已由 Boyi 確認通知同仁，不代表成果已驗收 |
| 已實作現況 | v0.3.0 Python／FastAPI、SQLite、原生前端；人物卡、來源、互動與交會，詳見演進 |
| 暫定技術方向 | React＋TypeScript、保留 Python／FastAPI、PostgreSQL、GCP；無專職前端；先邀請 5–8 人網頁試用，使用者可再修改 |
| 待實作方案 | 月／週排程、多模態輸入、真實辨識、夜間模式、React／PG 遷移及雲端部署；不能因文件描述完整就標完成 |
| 待決 | LLM／STT／VLM 供應商與端點、素材留存／刪除與備份期限、正式獎勵政策、月份邊界／續期細節、GCP project／region／權限與成本 |

使用者本次授權發布共同規格與檔案存放規則，不等於補定表中尚未決議的產品政策。沒有明確期限就標待決，不自行替使用者設定雲端自動刪除。

文件衝突先記錄「來源、版本、已確認／暫定／待決、影響、提出者、決定者」，由產品確認行為、全端確認技術影響。核准新決策時同步更新這裡、對應規格、API、測試與任務；保留演進歷史，不把建議冒充已核准功能。舊交接包只供追溯，不凌駕後續已明確確認的變更。

## 第一輪可交接任務

- **歐桑：**[完整總指令](team/PROMPT_OUSANG_START.md)、[十五位／可玩劇場](team/PROMPT_SIMULATION_001.md)、[UI 指令](team/PROMPT_UI_001.md)、[美術／動效清單](team/ART_DELIVERY_SPEC.md)，一次交齊後再安排[資料核對](team/PROMPT_DB_001.md)。
- **Jerry：**[LW-TECH-001 契約／部署審查](team/PROMPT_TECH_001.md)，把關整包與正式 App 接入。
- **Boyi 與 Codex：**[狀態規格](team/FLOWS_AND_STATES.md)、[任務看板](team/TASK_BOARD.md)及產品／體驗驗收。

十五位人物／三封面是測試／POC／封測 demo，正式版是否保留待 Boyi 評估。「人物劇場 → 情境體驗（示範角色）」僅為待確認封測入口，不混入真實人物庫或績效，也不宣稱 App 已接入。

App 儲存庫外的原型與完整工作區沒有隨這次提交上傳；共同實作所需的現況、規則、驗收對照與指令均在本儲存庫內。需要原型檔案時另由產品負責人提供已核對的設計參考，不把本機路徑當成 GitHub 可點連結。
