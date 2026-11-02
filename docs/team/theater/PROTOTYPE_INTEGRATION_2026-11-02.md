# 全流程 Prototype｜新提交審查與本機整合

更新：2026-11-02。狀態：本機整合候選，未 Commit／Push／合併／部署。入口：[全流程原型](../../../collaboration/flow-wireframe/index.html)／[啟動說明](../../../collaboration/flow-wireframe/README.md)。

## 審查結論與來源

本輪唯讀核對 GitHub 分支，`fix/theater-session-isolation` 指向 `c7a0058b4b08a5f9728bcdb4e54de1cb978ea23f`，包含 `41f41fb` 可靠性修正及 `c7a0058` 驗收文件調整；main 仍為 `8513b55`。後續遠端可能變更，開工仍需核對 SHA。

可沿用：固定人物／來源快照、活動場與歷史檢視隔離、按 ID 刪歷史、玩家行動／技術嘗試分離、清除／示例雙 key 復原日誌、舊引擎唯讀。這些能力可用於獨立原型，不構成正式 API、資料庫或安全交易的驗收。

實際取用 `app.js`、`theater.js` 與兩份瀏覽器測試；未合併 Git 分支，未把同事 PDF、截圖或歷史通過日誌當成本輪證據。取用前四個來源檔與 `6676b61` 相同，既有檔案已先保留本機備份。

## 發現與修正

| 發現 | 同事提交實測 | 本機整合修正 |
|---|---|---|
| 失敗後修改對象再重試 | 原行動寫給阿哲，重試變成怡君 | 玩家事件及生成都使用 action 固定的 recipientIds |
| Lumi 文字跨場 | 新場仍看到上一場私人輸入 | 開場重設私人輸入暫態，不刪原場私人建議 |
| 人物 ID 無效 | 人物頁靜默回退第一位人物 | 顯示「人物已不存在」及返回收藏冊，不代換真人 |
| ASR 草稿跨場 | 舊場轉錄 review 被新場沿用 | 新場從 idle 開始，清空轉錄候選與核對旗標 |

四項均先新增測試並在同事原提交確認失敗，再實作；不是把環境失敗當功能紅燈。

全流程沿用一目標／三習慣、7×4 月循環（第五次手動補選）、點蛋、活動與人物關聯、人工確認、人物 360°、交會、私人演練及示範、回顧與目標旅程。新增可收合的體驗導覽、版本標記與快取更新；世界頁仍使用房間、Lumi、一顆蛋等既有候選美術。手機劇場採有限高度對話捲動，避免對話持續撐長整頁；劇場內導覽與其他頁共用四分頁圖示。

## 本輪驗證

- 同事提交隔離重跑：`pytest browser_tests/test_theater_wireframe.py browser_tests/test_flow_wireframe.py -q --tb=short`，**77 passed，0 failed，0 skipped，107.83 秒**。
- 補充紅燈：`pytest browser_tests/test_prototype_integration.py -q --tb=short`，**4 failed，15.28 秒**，分別對應上表四項。
- 修正後同一四項：**4 passed，0 failed，0 skipped，5.10 秒**。
- 整合第一輪三檔回歸：**81 passed，0 failed，0 skipped，113.03 秒**；最後版面回歸結果見本節後續紀錄，不以第一輪冒充最後版本。
- 最後整體三檔回歸：**81 passed，0 failed，0 skipped，113.46 秒**。其後只將手機人物姓名牌往上移以避開情境標題，另跑版面針對性驗收。
- 最後姓名牌修正後：`pytest browser_tests/test_theater_wireframe.py -q --tb=short -k 'long_name_mobile_layout or compose_remains_visible'`，**3 passed，39 deselected，0 failed，5.93 秒**；四張世界／劇場手機與桌面截圖重取成功，沒有損毀圖片或水平溢出。
- 390×844、1440×1050 實走建立／點蛋／世界與多人演練，檢查圖片載入及水平溢出；截圖均為虛構資料。真機 Safari、軟鍵盤與 safe area 未實測。
- 最初沙箱阻擋 Chromium 啟動，造成 77 項 setup error；改在允許的隔離 Chromium 環境重跑才有上述有效結果。環境失敗不算產品紅燈。

## 使用界線與待完成

1. 本輪不改正式 Python App、API 或 Schema，沒有重新執行正式 App 後端測試；不可把 Wireframe 行為視為正式 App 已同步。
2. 供應商、正式來源 ID／版本、跨帳號權限、跨裝置保存、費用硬限制及撤回資料的留存／刪除仍待工程審查。localStorage revision 與復原日誌不是伺服器交易或安全邊界。
3. 同事的 SR 驗收文件仍有「部分通過」子情境；本輪新增四項不表示整份 [可靠性規格](SESSION_RELIABILITY_SPEC.md) 所有邊界均已關閉。例如真正併發、外部重送與所有晚到故障需正式服務另驗。
4. 既有候選提示音預設關閉，不視為音效交付或 Quiet 音訊規則驗收。本輪未增加美術或音效資產。
5. 模型、轉錄、圖片辨識與登入維持模擬；封測要求的真實辨識門檻尚未完成。只用虛構資料體驗，不輸入真人資料。
6. 本文件與原型未自動發布至 GitHub。原始工作分支與其他未提交修改保留，index 未加入本輪內容。
