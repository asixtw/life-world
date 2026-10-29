# 歐桑｜完整交付任務總入口

> 本分支只發布交接文件，程式維持 v0.3.0；本機 v0.4／素材進度未發布。範圍、收件及同步狀態以[本次發布說明](DELIVERY_V1_1_RELEASE.md)為準。
更新：2026-10-29。2026-10-28 的具名分工／完整交付要求曾由 Boyi 確認通知同仁；本次 v1.1 增加房間／姿勢／音效明細與 P0／P1／P2 分批，Boyi 已確認本機修訂，尚未公告／發布／同步。不宣稱整包已驗收。

| 人員 | 本次責任 |
|---|---|
| Boyi | 產品機制、流程、視覺、內容、音效聽審與最終體驗 |
| Jerry（jerry） | 全端；資料／API／元件契約、技術審查及正式接入／部署把關 |
| 歐桑 | 資料庫／Pro 協作；完整人物模組、UI、美術、動效、音效候選與交付證據 |
| Codex | 各同仁操作的協作工具，不算第四位同仁，不代替人類審查 |

姓名是顯示名稱，不推測 GitHub 帳號、權限、工時或承接回報。

## 交付入口與範圍

1. [完整規格 v1.1](ART_DELIVERY_SPEC.md)：原十三類＋音效第十四類，尺寸／狀態／數量／優先順序／驗收的完整依據。
2. [可複製製作指令](PROMPT_UI_001.md)：LW-UI-001／LW-ASSET-001／LW-AUDIO-001 的 IDE 任務。
3. [月份／錄音／附件／校對契約](MEDIA_COMPONENT_CONTRACT.md)：對齊已接入本機 App 的行為，與 React 候選分開。
4. [LW-SIM-001](PROMPT_SIMULATION_001.md)：三組十五位擬真人物與完整可玩劇場，原內容／評估要求保留。
5. [交付模板](HANDOFF_TEMPLATE.md)及[任務看板](TASK_BOARD.md)：各批與整包證據、缺口、主責與狀態。

| 順序 | 製作與審查 |
|---|---|
| P0 | 設計基礎、按鈕／輸入／導覽／面板、月份排程、錄音／附件／校對／草稿、圖示 |
| P1 | App 圖示、六姿勢 Lumi、蛋／分層破殼／回饋、房間日間／安靜版、人物美術及轉場 |
| P2 | 五種音效各兩候選，播放格式、來源、靜音及錯誤退路 |

已有合格成果沿用；逐項記「沿用／修改／新增」及驗收狀態。P0 → P1 → P2 各批自測、自修、交 Boyi／Jerry 審查，最後同一專案完整交齊；不以單一小樣為終點，也不以優先級取消後面的交付。

## 現況及邊界

App 是 v0.4.0／Python＋SQLite＋原生前端；目標流程（本機待發布：`../GOAL_FLOW_ACCEPTANCE.md`）及本機素材流程（本機待發布：`../MEDIA_COMPONENTS_ACCEPTANCE.md`）有各自證據。React／PostgreSQL／GCP 尚未遷移；真實辨識供應商、雲端素材保存及正式夜間服務未完成。是否已發布仍依實際來源 commit，不用本機版本推定遠端。

歐桑交獨立 React／TypeScript 元件、資產與可玩模組，Jerry 審查正式接入，Boyi 可藉 Codex 協助。音效先確認工具與輸出使用依據；不能產出就記阻礙，不標完成。即時 AI 未指定端點時，人物包交完整腳本模式及通用介面，明示即時未驗，不宣稱已訓練模型權重或已證實真人預測有效。

## 示範內容及存放

十五位人物／三封面為測試／POC／封測 demo，正式版保留與「人物劇場 → 情境體驗（示範角色）」入口仍待評估。demo 不進真實收藏、來源、互動／見面、進度或積分。共用 UI／Lumi／蛋／房間／音效列 product_candidate，兩者在 manifest 分流。

在 `work/ousang-full-kit` 的 `collaboration/ui-kit/` 製作，原碼、內容、原稿／優化版、測試、評估與交接分區。以 Boyi／Jerry 提供的共同 commit／可分享快照開工，回報 SHA 與本規格版本；新版尚未發布時先取得核准的可分享資料，不擅自 Pull／整合他人的未提交工作。

主要用可讀寫及執行專案的 IDE。Dot 可整理目標、追蹤進度及核對證據；未連接工具時不宣稱監控。各工具按實際帳號能力回報，Pro 不等於所有 API／圖像／音效工具均可用。

## 可直接複製的總指令

```text
請從 App Repository 根目錄開始，讀 AGENTS.md、docs/SPEC_INDEX.md、
docs/STORAGE_RULES.md、docs/team/PROMPT_OUSANG_START.md、
docs/team/ART_DELIVERY_SPEC.md（v1.1）、docs/team/PROMPT_UI_001.md、
docs/team/MEDIA_COMPONENT_CONTRACT.md、docs/team/PROMPT_SIMULATION_001.md。
回報來源 commit／快照 SHA、文件版本與實際工具。

先盤點候選包的沿用／修改／新增與待驗收，再按 P0 操作核心、P1 美術／角色／
房間／動效、P2 五種音效各兩候選逐批完成、自測、自修、交審，最後整包交齊。
原十三類及十五位人物／可玩模組要求均保留，音效是新增第十四類。
在 work/ousang-full-kit 的 collaboration/ui-kit/ 製作獨立專案，
交真實檔案、可操作展示、原稿／分層／顯示版、型別／事件、manifest、
測試結果／截圖／限制及 Jerry 的接入說明。沒有執行的項目標未驗證。
已有合格成果沿用，不為更新規格重做整包，也不把圖像代替互動元件。
產品或正式技術方向有實質衝突時請 Boyi 決策；工具缺少就記阻礙。
不改正式 App／DB／API、獎勵或認證，不自行合併、部署、Push 或代發公告。
```
