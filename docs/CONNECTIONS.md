# Connections 正式整合｜需求、契約與邊界

2026-10-28：使用者明確要求「現在開始整合」，並更正為「交會取代星圖，完成後再做完整測試」。本輪沿用 Python／SQLite／原生前端，交會取代關係頁及首頁的星圖入口，保留收藏冊與四個主導覽。原始 v0.3 原型不修改。

## 需求與實作預設

- 故事單位是單筆已確認經歷；標題為選填，不提供時顯示摘要前段，日期沿用實際發生時間。未審閱故事不進探索。
- `story` 包含 `title`、`participants`、`mentions`；草稿可保存未確認的人物整理，正式確認另需 `story_reviewed: true`。沒有 `story` 的舊 API 保持相容，舊人物關聯標為待確認，不猜測參與。
- 參與者保存 `person_id` 與 `interacted`。後者代表使用者明確確認有直接互動，預設 false；只有此旗標者接入互動統計，見面仍須實體事件。同一人在不同來源的參與名單分開保存。
- 提及保存 `name`、原文 Unicode 字元的 `start`／`end`、選填人工配對的 `person_id`。片段須與原文完全吻合；同名不同位置可分別核對，候選不能自動配對。前端與 Python 均按 Unicode 字元而非 UTF-16 位移計數。
- 先配對既有人物，允許待核對、略過、拒絕、取消及更正。新建人物沿用既有人物入口，本輪不做 AI 辨識或名片共用校對。
- 角色更正、配對、撤回交會展示不修改既有原文、貢獻與獎勵；保留修改歷史。提及不增加互動、出席、見面、進度或獎勵，不建立 `person_connections`。
- 同一人物可同時有參與連結及原文提及片段，但不重算參與；單筆重複參與人或重複提及位置拒絕。主要 `person_id` 在明確故事中只能是參與者，避免將提及者當主要互動對象。
- 探索查詢按發生時間及固定 ID 穩定排序，支援最近／較早、人物焦點、參與／已配對提及、分頁。初始選最近故事，參與者先顯示三位，其餘由使用者展開。
- 返回保存故事、焦點、提及來源、查詢、展開內容及捲動；僅本次登入頁面記憶體保存探索歷史，刷新保留 URL 的當前焦點，配對／人物資料由伺服器保存。登出或切換帳號清除快取。

## 增量 API

- 草稿建立／更新及確認新增選填 `story`，確認新增 `story_reviewed`，舊預設欄位不破壞舊去重指紋。
- `GET /api/connections`：`person_id`、`involvement=participant|mention|legacy`、`sort=recent|oldest`、`limit`（1～50）、`offset`；只查同帳號且可見故事，預設排除舊未審閱關聯。
- `GET /api/connections/stories/{id}`：日期、原文／摘要、參與、提及及來源位置；`manage=true` 可供本人修正待審閱／已撤回故事，探索模式不顯示這些來源。
- `PUT /api/connections/stories/{id}/people`：`request_id`、`expected_revision`、`story`、`confirmed: true`；確認舊關聯或更正人物，不重發積分。
- `POST /api/connections/mentions/{id}/match`：`request_id`、`expected_revision`、`status=matched|unmatched|rejected`、`person_id`、`confirmed: true`；改配對不改參與者。
- `POST /api/connections/stories/{id}/availability`：`request_id`、`expected_revision`、`available`；撤回探索展示或恢復，不刪原始經歷。

寫入沿用 session、CSRF、帳號門檻、owner、版本與重送去重。同 key 不同內容／舊版本回 409；錯誤原文位置回 422；不可存取來源回 404。配對回執不作來源讀取的替代途徑。

## 測試先行

正常：多人／提及草稿保存、人工確認、故事分頁、持久配對、人物頁串接及完整探索路線。

異常：跨帳號、訪客寫入、來源片段錯誤、未明確核對、重送不同內容、版本衝突、保存失敗及已撤回來源。

邊界：無人物、只有提及、同名、同名多處出現、emoji 位移、同場未互動、事件合併後人物聯集、舊資料遷移、更多參與者及無下一段故事。核心規則先用 pytest 紅燈；手機 390×844 與桌面另做真實 Chromium 流程與截圖。

不包含真實 AI、月／週排程、框架更換、全站身分／部署或 3,000 人負載承諾。測試結果與限制完成後記入驗收及演進紀錄。
