# 經歷四步流程與人物關聯修復（Draft，未部署）

> **2026-11-10 Owner 設計關卡：Changes Requested。** 舊第三／四步畫面未獲設計核准；先審查 [UX v0.3 Candidate](../ux-v03-candidate/README.md) 與[合併前清單](../ux-v03-candidate/MERGE_GATES.md)。收到「UX v0.3 核准」前不進行後續產品串接、Merge 或 Deploy。原下方功能測試不等於設計核准。


以 main `68102f230aa947a434286ba9260e1ae75f6634b0` 為基準。Owner 最新整合指令優先於交接附件原「暫緩四步」範圍。v0.2 原型只作 UX 參考，沒有採用模擬 AI。

## 修改與原因

- `app/static/experience.js`：原生 DOM 分為原文／媒體、目標活動量、人物角色三步；既有 review 頁為第四步。換步不拆媒體元件，不重新建立表單，支援返回。
- `app/static/app.js`、`index.html`、`media.css`：掛接四步、明確人物選擇及最終確認；Guest 只有文字。保留現有視覺／Lumi／媒體服務與人工 AI 候選。
- `relationships.js`：同 Owner `/state.people` 彙整角色／標籤多選與共同場合 datalist；新值仍可輸入，舊含分隔符標籤不拆分；不新增表或 API。
- `schemas.py`、`service.py`：可選 `story.pending_person` 保存在既有草稿 JSON。最終確認交易才建立人物及來源，沿用 Owner lock、版本與冪等收據；失敗回滾全部正式寫入。
- `connections.py`：待核對僅舊主要人物線索；正式參與僅明確參與者，提及獨立查詢。總數／排序／分頁同條件，原文及獎勵不刪改。
- `connections.js`：清楚核對入口、待新增人物最小欄位與原文提及位置；不自動推定出席／互動或合併同名。

[狀態與 API 契約](CONTRACT.md)。沒有 Migration、Runtime GRANT、正式 Alpha 寫入、外部模型呼叫、Cloud Build 或 Deploy。

## 相容性與限制

舊 API 不帶 pending_person 的 JSON 與確認指紋保持原狀。新增欄位是可選，部署前須先審查後端／前端一起發布；回滾舊應用時，含新欄位的未確認草稿不保證可被舊版編輯（原文仍在），應保留本版或先導出草稿候選，禁止清除資料遷就回滾。

保存伺服器草稿與正式確認分開。捨棄只清未保存修改與當次本機來源，既存伺服器草稿仍保留；未新增需擴權的 DELETE API。AI／多媒體辨識沿用原服務與明確同意，本輪不宣稱真模型驗收。圖片與音訊須先人工校對成文字，不能以空白素材直接確認。

PR #22 維持獨立審查；本輪不改 external_auth、Google callback、Guest 清除邏輯。共同檔案 app.js／schemas.py／API 文件仍須在正式合併時核對。整合檢查與測試收據見 evidence；真人 Google、正式 Alpha、付費 AI、實機 iOS／Android：NOT RUN。

## 驗收與回復

本機 SQLite／Node、隔離 PG18、獨立 Chromium 皆使用合成資料；詳細命令與結果見 evidence。手機 390px、桌面 1440px [截圖](screenshots/)。截圖不是線上或真模型證據。

人工 Code Review → 重新核對 main 與 #22 精確版本 → 另行取得建置／候選部署授權。沒有應用發布，因此現役版本無須回滾；本 PR 可直接撤回程式變更，不動資料庫。
