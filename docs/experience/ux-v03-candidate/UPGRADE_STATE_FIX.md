# R2 補修：第三步升級保留人物選擇

狀態：Changes Requested／整體 UX 尚未核准。保留 R2 設計，只修 Candidate 狀態。

- 根因：`deliverUpgradeFixture()` 強制 `related=true`，空人物列表阻擋下一步。
- 修正：升級僅更新身分／能力及局部人物 UI；保持 related、people、Owner、原文、目標數量與草稿。升級成功展示情境也採相同預設。
- 原先不關聯人物可直接前往第四步；主動選「有相關人物」後才要求新增或選擇人物。
- 測試涵蓋 390／1440：升級成功直接繼續、主動新增人物、原 DOM 保留、取消／失敗／衝突資料不變。
- 紅燈：新增直接繼續測試先實跑，2 failed（390／1440），原因為預設選擇被改動。

## 畫面

- [手機：升級後仍不關聯人物](screenshots-upgrade-fix/390/upgrade-no-people.png)
- [手機：直接進入第四步](screenshots-upgrade-fix/390/upgrade-continue-step4.png)
- [桌面：升級後仍不關聯人物](screenshots-upgrade-fix/1440/upgrade-no-people.png)
- [桌面：直接進入第四步](screenshots-upgrade-fix/1440/upgrade-continue-step4.png)

本輪沒有修改正式 API、PR #22 交易、資料模型或雲端。Gate B/C 保持未完成，真 Google／Alpha／實機驗收 NOT RUN。設計測試不代表 Owner 核准。

本輪完整 Chromium 設計套件：**58 passed in 63.91s**，未跳過。指令：`python -m pytest docs/experience/ux-v03-candidate/tests -q --tb=short`。收據見 [GREEN](evidence/UPGRADE_STATE_GREEN.log) 與 [RED](evidence/UPGRADE_STATE_RED.log)。套件監控正式 API／外部服務請求皆為零，無 JS pageerror。
