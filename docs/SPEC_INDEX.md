# 共同規格入口

> 2026-11-08 Owner最新範圍：首次公開版包含核心人物理解／劇場、美術核准接入、聲音v0.2規劃及獨立開關。先讀[公開完成矩陣](testing/PUBLIC_RELEASE_MATRIX.md)，不再沿用先凍結核心劇場的發布範圍。RC v3保留；新程式為本機候選，不能當已公開／已部署。

> **2026-11-05 最新共同基準：**[Public Alpha工程交付](RELEASE_PUBLIC_ALPHA_20261105.md)。預建登入獨立開關、無自由註冊；積分保留但無兌換，優先於下方歷史敘述。工程與雲端交付狀態分開驗收。

> **2026-10-29 封測定稿 v1.0：**先讀[完整流程與驗收基準](team/BETA_FLOW_SPEC.md)。封測不做養分／積分／兌換獎勵；保留完成紀念與未達成旅程摘要，人物及來源不刪。劇場同時提供私人演練與示範情境；真實語音與圖片辨識均為封測門檻。下列長期製作項不全是封測必須整合項。

更新：2026-10-29。適用 `asixtw/life-world` 全體協作者。本文索引、產品基準、規則與任務均隨儲存庫保存，可直接在 GitHub 閱讀，不需取得產品負責人的完整桌面工作區。

草案狀態：「變更同步與公告後發布」依 Boyi 於 2026-10-28 最新指示先發布供團隊閱讀，仍待正式定案／公告；GitHub 發布不代表成員電腦或部署已更新。具名任務基準見 `26e36c7`，本次草案版本以包含此修訂的 Git commit 為準。

## 依序閱讀

劇場可靠性與本輪原型／提示規格：[Session 修復](team/theater/SESSION_RELIABILITY_SPEC.md)、[原型整合](team/theater/PROTOTYPE_INTEGRATION_2026-11-02.md)、[表單提示](team/theater/VALIDATION_FEEDBACK_2026-11-02.md)。資料庫接續：[SQLite 現況與 PG／劇場草案](database/schema-2026-11-02/README.md)，PG 未部署。

| 文件 | 用途與狀態 |
|---|---|
| [產品基準](PRODUCT_BASELINE.md) | 共用名詞、核心旅程、不變條件、已實作與缺口 |
| [單一目標與三個習慣](GOAL_FLOW_ACCEPTANCE.md) | v0.4 建立、日期安排、回顧、歷史與本輪實測 |
| [習慣調整與完整原型](HABIT_WIREFRAME_ACCEPTANCE.md)／[Wireframe 入口](../collaboration/flow-wireframe/README.md) | 明日起用量版本、修改與衝突退路；完整流程展示，錄音／辨識／夜間明標模擬 |
| [素材流程驗收](MEDIA_COMPONENTS_ACCEPTANCE.md)／[元件與辨識契約](team/MEDIA_COMPONENT_CONTRACT.md) | 本機錄音、附件、校對與裝置草稿已接入；外部辨識、雲端素材及正式人物建檔待審 |
| [共同研發指引](PRODUCT_GUIDE.md) | 十一節產品／設計原則、TDD 與中文註解規則 |
| [存放規則](STORAGE_RULES.md) | 程式、規格、素材、使用者資料與秘密的存放邊界 |
| [協作規則](../CONTRIBUTING.md) | 分支、共同 commit、PR、規格變更及驗收 |
| [變更同步規則](team/CHANGE_CONTROL.md) | 已授權先發布的草案，待正式定案／公告；涵蓋成員、分工、任務與方向變更 |
| [三人分工與任務](team/README.md) | 主責、工作包、可複製提示詞及第一輪交付 |
| [歐桑完整交付入口](team/PROMPT_OUSANG_START.md) | Boyi 已通知並定案的具名任務、VS Code／Codex 工作方式與整包交付 |
| [LW-SIM-001](team/PROMPT_SIMULATION_001.md) | 三組十五位資料、可玩劇場、來源／評估／整合介面；成果尚未交付 |
| [完整 UI／美術／動效／音效 v1.1](team/ART_DELIVERY_SPEC.md) | 十四類，P0 操作、P1 房間／六姿勢／分層孵化／人物／動效、P2 音效；本機確認，待公告／發布及工程驗收 |
| [流程與狀態](team/FLOWS_AND_STATES.md) | 排程、登入、錄音與夜間的後續行為規格；未實作部分明示 |
| [API](API.md)／[OpenAPI](openapi.json)／[架構](ARCHITECTURE.md) | 現有可執行服務；未來 React／PG 契約由全端另審 |
| [完整 Table Schema](DATABASE_SCHEMA.md)／[Jerry DB 接續規劃](database/POSTGRESQL_HANDOFF.md) | 實際 SQLite 31 表／201 欄位、鍵／索引／頁面資料與結構快照；PostgreSQL／多模態／夜間新表另標提案 |
| [演進](EVOLUTION.md)／[目標驗收](GOAL_FLOW_ACCEPTANCE.md)／[v0.4 發布檢查](GITHUB_PUBLISH_V0_4.md) | 本次候選版本與測試；[交會驗收](CONNECTIONS_ACCEPTANCE.md)及[v0.3 發布檢查](GITHUB_PUBLISH.md)保留為歷史 |

## 決策狀態與變更

| 狀態 | 本次基準 |
|---|---|
| 已確認產品原則 | 真實經歷、人工確認、可追溯來源、人物選填、首次目標後才有 Lumi、去重與權限、不因缺席懲罰 |
| 已確認本輪任務 | Boyi 產品／驗收、Jerry 全端整合／審查、歐桑資料庫／Pro 協作；完整模擬人物及 UI／美術包已由 Boyi 確認通知同仁，不代表成果已驗收 |
| 已實作現況 | 本機 v0.4.0，Python／FastAPI、SQLite、原生前端；單一目標、三個習慣、月／週日期安排與回顧，以及原有人物／交會；GitHub 更新以實際發布 commit 為準 |
| 暫定技術方向 | React＋TypeScript、保留 Python／FastAPI、PostgreSQL、GCP；無專職前端；先邀請 5–8 人網頁試用，使用者可再修改 |
| 待實作方案 | 真實辨識服務、雲端素材來源、夜間模式、React／PG 遷移及雲端部署；本機素材輸入／校對已接入，原生前端已完成的排程不代表 React 整合完成 |
| 待決 | LLM／STT／VLM 供應商與端點、素材留存／刪除與備份期限、長期正式獎勵政策（封測確定不做獎勵）、完成後更正、未排程日進階統計、GCP project／region／權限與成本；截止日必選、固定目標時區及人工延長已於 v0.4 確認 |

先前批次對共同規格／存放規則的發布授權不延伸至本次 v1.1；本次未 Commit／Push、未宣稱公告或部署。表中尚未決議的產品政策保持待決。沒有明確期限就標待決，不自行替使用者設定雲端自動刪除。

文件衝突先記錄「來源、版本、已確認／暫定／待決、影響、提出者、決定者」，由產品確認行為、全端確認技術影響。核准新決策時同步更新這裡、對應規格、API、測試與任務；保留演進歷史，不把建議冒充已核准功能。舊交接包只供追溯，不凌駕後續已明確確認的變更。

## 第一輪可交接任務

- **歐桑：**[完整總指令](team/PROMPT_OUSANG_START.md)、[十五位／可玩劇場](team/PROMPT_SIMULATION_001.md)、[UI 指令](team/PROMPT_UI_001.md)、[美術／動效清單](team/ART_DELIVERY_SPEC.md)，一次交齊後再安排[資料核對](team/PROMPT_DB_001.md)。
- **Jerry：**[LW-TECH-001 契約／部署審查](team/PROMPT_TECH_001.md)，把關整包與正式 App 接入。
- **Boyi 與 Codex：**[狀態規格](team/FLOWS_AND_STATES.md)、[任務看板](team/TASK_BOARD.md)及產品／體驗驗收。

十五位人物／三封面是測試／POC／封測 demo，正式版是否保留待 Boyi 評估。「人物劇場 → 情境體驗（示範角色）」已確認為封測入口，不混入真實人物庫或績效，也不宣稱 App 已接入。

App 儲存庫外的原型與完整工作區沒有隨這次提交上傳；共同實作所需的現況、規則、驗收對照與指令均在本儲存庫內。需要原型檔案時另由產品負責人提供已核對的設計參考，不把本機路徑當成 GitHub 可點連結。

- [Goal Dashboard：資料口徑、API與驗收](GOAL_DASHBOARD.md)（2026-11-03，發布候選；合併狀態見本批審查）。

- [Goal Detail v0.2 產品規格](team/goal-detail/PRODUCT_SPEC_v0.2.md)／[UI交接參考](team/goal-detail/UI_COMPONENT_SPEC_v0.2.md)：本輪詳情重構，實作差異與驗收見[Dashboard紀錄](GOAL_DASHBOARD.md)。

- [HabitScheduleDisclosure v0.3來源](team/goal-detail/HABIT_SCHEDULE_v0.3.md)／[月曆實作與驗收](HABIT_SCHEDULE_ACCEPTANCE.md)：只讀排程，不含每日實際投入API。

- [首頁三習慣摘要與驗收](HOME_HABIT_OVERVIEW.md)：首頁單一挑戰、精確用量及下一安排；[來源包](team/home-habits/README.md)。

- [本批發布審查與未驗證事項](RELEASE_HOME_HABITS_20261103.md)。
